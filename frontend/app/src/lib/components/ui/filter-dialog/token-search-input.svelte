<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { Snippet } from 'svelte';
	import X from '@lucide/svelte/icons/x';
	import Search from '@lucide/svelte/icons/search';
	import CircleHelp from '@lucide/svelte/icons/circle-help';
	import * as Popover from '$lib/components/ui/popover';
	import type { FilterCategory, FilterOption } from './index.js';
	import type { FilterAst } from '$lib/filters/ast';
	import { equals as astEquals, isEmpty as astIsEmpty, emptyAnd } from '$lib/filters/ast';
	import { parse, serialize, type ParseError } from '$lib/filters/dsl';
	import { suggestMode } from './tokenizer.js';

	interface Props {
		categories: FilterCategory[];
		filter: FilterAst;
		onFilterChange: (ast: FilterAst) => void;
		placeholder?: string;
		renderOption?: Snippet<[{ category: FilterCategory; option: FilterOption }]>;
	}

	let {
		categories,
		filter,
		onFilterChange,
		placeholder = 'Search…',
		renderOption
	}: Props = $props();

	let rawText = $state('');
	let mounted = $state(false);
	let focused = $state(false);
	let cursor = $state(0);
	let highlightIdx = $state(0);
	let errors = $state<ParseError[]>([]);
	let inputEl = $state<HTMLInputElement | null>(null);
	let listEl = $state<HTMLUListElement | null>(null);
	let lastCommittedFilter = $state<FilterAst | null>(null);

	const visibleCategories = $derived(
		categories.filter(c => c.condition === undefined || c.condition)
	);

	onMount(() => {
		rawText = serialize(filter);
		lastCommittedFilter = filter;
		mounted = true;
	});

	$effect(() => {
		if (!mounted) return;
		if (focused) return;
		if (lastCommittedFilter && astEquals(filter, lastCommittedFilter)) return;
		rawText = serialize(filter);
		lastCommittedFilter = filter;
	});

	$effect(() => {
		errors = parse(rawText).errors;
	});

	const suggestion = $derived(suggestMode(rawText, cursor));

	type PopoverItem =
		| { kind: 'key'; category: FilterCategory }
		| { kind: 'value'; category: FilterCategory; option: FilterOption }
		| { kind: 'operator'; label: string };

	const OPERATORS = ['NOT', 'OR', 'AND'];

	const popoverItems = $derived.by<PopoverItem[]>(() => {
		if (!focused) return [];
		if (suggestion.kind === 'key') {
			const prefix = suggestion.prefix.toLowerCase();
			const keys: PopoverItem[] = visibleCategories
				.filter(
					c =>
						c.key.toLowerCase().startsWith(prefix) ||
						c.label.toLowerCase().startsWith(prefix)
				)
				.map(c => ({ kind: 'key' as const, category: c }));
			const ops: PopoverItem[] = OPERATORS
				.filter(op => op.toLowerCase().startsWith(prefix))
				.map(op => ({ kind: 'operator' as const, label: op }));
			return [...keys, ...ops];
		}
		if (suggestion.kind === 'value') {
			const cat = visibleCategories.find(c => c.key === suggestion.key);
			if (!cat) return [];
			const partial = suggestion.partial.toLowerCase();
			const opts = partial
				? cat.options.filter(
						o =>
							o.id.toLowerCase().includes(partial) ||
							o.label.toLowerCase().includes(partial)
					)
				: cat.options;
			return opts
				.slice(0, 50)
				.map(option => ({ kind: 'value' as const, category: cat, option }));
		}
		if (suggestion.kind === 'none' && rawText.slice(0, cursor).match(/(^|\s)$/)) {
			const keys: PopoverItem[] = visibleCategories.map(c => ({ kind: 'key' as const, category: c }));
			const hasContent = rawText.trim().length > 0;
			const ops: PopoverItem[] = hasContent
				? OPERATORS.map(op => ({ kind: 'operator' as const, label: op }))
				: [];
			return [...keys, ...ops];
		}
		return [];
	});

	const showPopover = $derived(focused && popoverItems.length > 0);

	$effect(() => {
		void popoverItems.length;
		highlightIdx = 0;
	});

	$effect(() => {
		if (!listEl) return;
		const el = listEl.children[highlightIdx] as HTMLElement | undefined;
		el?.scrollIntoView({ block: 'nearest' });
	});

	function setTextAndCursor(next: string, nextCursor: number) {
		rawText = next;
		cursor = nextCursor;
		tick().then(() => {
			if (!inputEl) return;
			inputEl.value = next;
			inputEl.focus();
			inputEl.selectionStart = nextCursor;
			inputEl.selectionEnd = nextCursor;
		});
	}

	function syncCursor() {
		if (!inputEl) return;
		cursor = inputEl.selectionStart ?? rawText.length;
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		rawText = target.value;
		cursor = target.selectionStart ?? target.value.length;
	}

	function commit() {
		const r = parse(rawText);
		errors = r.errors;
		if (r.errors.length > 0) return;
		lastCommittedFilter = r.ast;
		if (!astEquals(r.ast, filter)) onFilterChange(r.ast);
	}

	function pickKey(cat: FilterCategory) {
		const insertField = `${cat.key}:`;
		if (suggestion.kind === 'key') {
			const before = rawText.slice(0, suggestion.tokenStart);
			const after = rawText.slice(suggestion.tokenEnd);
			setTextAndCursor(
				before + insertField + after,
				suggestion.tokenStart + insertField.length
			);
			return;
		}
		const before = rawText.slice(0, cursor);
		const after = rawText.slice(cursor);
		setTextAndCursor(before + insertField + after, cursor + insertField.length);
	}

	function pickValue(cat: FilterCategory, option: FilterOption): boolean {
		if (suggestion.kind !== 'value') return false;
		const current = rawText.slice(suggestion.valueStart, suggestion.tokenEnd);
		if (current === option.id) return false;
		const before = rawText.slice(0, suggestion.valueStart);
		const after = rawText.slice(suggestion.tokenEnd);
		const next = before + option.id + after;
		const nextCursor = suggestion.valueStart + option.id.length;
		setTextAndCursor(next, nextCursor);
		return true;
	}

	function pickOperator(op: string) {
		if (suggestion.kind === 'key') {
			const before = rawText.slice(0, suggestion.tokenStart);
			const after = rawText.slice(suggestion.tokenEnd);
			const insert = op + ' ';
			setTextAndCursor(before + insert + after, suggestion.tokenStart + insert.length);
			return;
		}
		const before = rawText.slice(0, cursor);
		const after = rawText.slice(cursor);
		const insert = op + ' ';
		setTextAndCursor(before + insert + after, cursor + insert.length);
	}

	function pickHighlighted(): boolean {
		const item = popoverItems[highlightIdx];
		if (!item) return false;
		if (item.kind === 'key') { pickKey(item.category); return true; }
		if (item.kind === 'operator') { pickOperator(item.label); return true; }
		return pickValue(item.category, item.option);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			(e.target as HTMLInputElement).blur();
			return;
		}
		if (showPopover && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
			e.preventDefault();
			const dir = e.key === 'ArrowDown' ? 1 : -1;
			highlightIdx = (highlightIdx + dir + popoverItems.length) % popoverItems.length;
			return;
		}
		if (e.key === 'Tab' && showPopover) {
			e.preventDefault();
			pickHighlighted();
			return;
		}
		if (e.key === 'Enter') {
			e.preventDefault();
			if (showPopover && pickHighlighted()) return;
			commit();
			inputEl?.blur();
			return;
		}
	}

	function handleBlur() {
		focused = false;
		// Re-parse directly: `errors` is set by an $effect and may lag a fast type-then-blur.
		if (parse(rawText).errors.length === 0) commit();
	}

	function clearAll() {
		errors = [];
		const next = emptyAnd();
		lastCommittedFilter = next;
		rawText = '';
		onFilterChange(next);
	}

	const showClear = $derived(rawText.length > 0 || !astIsEmpty(filter));
	const hasError = $derived(errors.length > 0);
</script>

{#if mounted}
	<div class="flex flex-col gap-1">
		<div class="relative">
			<div
				class="flex items-center gap-2 min-h-9 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-xs transition-[color,box-shadow]
					focus-within:border-ring focus-within:ring-ring/50 focus-within:ring-[3px]
					aria-invalid:ring-destructive/20 aria-invalid:border-destructive"
				aria-invalid={hasError || undefined}
			>
				<Search class="h-4 w-4 text-muted-foreground shrink-0" />

				<input
					bind:this={inputEl}
					type="text"
					value={rawText}
					oninput={handleInput}
					onkeydown={handleKeydown}
					onkeyup={syncCursor}
					onclick={syncCursor}
					onfocus={() => (focused = true)}
					onblur={handleBlur}
					{placeholder}
					class="flex-1 bg-transparent outline-none placeholder:text-muted-foreground font-mono text-sm field-sizing-content min-w-[8rem]"
					aria-invalid={hasError}
					spellcheck="false"
					autocomplete="off"
					autocapitalize="off"
					autocorrect="off"
				/>

				{#if showClear}
					<button
						type="button"
						class="text-muted-foreground hover:text-foreground shrink-0"
						onmousedown={e => {
							e.preventDefault();
							e.stopPropagation();
							clearAll();
						}}
						aria-label="Clear filter"
					>
						<X class="h-2.5 w-2.5" />
					</button>
				{/if}

				<Popover.Root>
					<Popover.Trigger>
						{#snippet child({ props })}
							<button
								{...props}
								type="button"
								tabindex={-1}
								class="flex items-center justify-center h-6 w-6 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors shrink-0"
								aria-label="Filter syntax help"
							>
								<CircleHelp class="h-3.5 w-3.5" />
							</button>
						{/snippet}
					</Popover.Trigger>
					<Popover.Content side="bottom" align="end" class="w-72 text-xs leading-relaxed">
						<p class="font-medium text-sm mb-2">Filter syntax</p>

						<p class="text-muted-foreground mb-1">Operators</p>
						<div class="flex flex-col gap-0.5 mb-3">
							<div class="flex items-center justify-between">
								<span>And</span>
								<code class="font-mono text-[11px] text-muted-foreground">AND</code>
							</div>
							<div class="flex items-center justify-between">
								<span>Or</span>
								<code class="font-mono text-[11px] text-muted-foreground">OR</code>
							</div>
							<div class="flex items-center justify-between">
								<span>Not</span>
								<code class="font-mono text-[11px] text-muted-foreground">NOT / -</code>
							</div>
							<div class="flex items-center justify-between">
								<span>Multi-value</span>
								<code class="font-mono text-[11px] text-muted-foreground">field:a,b</code>
							</div>
							<div class="flex items-center justify-between">
								<span>Grouping</span>
								<code class="font-mono text-[11px] text-muted-foreground">( … )</code>
							</div>
						</div>

						<p class="text-muted-foreground mb-1">Fields</p>
						<div class="flex flex-col gap-0.5">
							{#each visibleCategories as cat (cat.key)}
								<div class="flex items-center justify-between">
									<span>{cat.label}</span>
									<code class="font-mono text-[11px] text-muted-foreground">{cat.key}:..</code>
								</div>
							{/each}
						</div>
					</Popover.Content>
				</Popover.Root>
			</div>

			{#if showPopover}
				<div
					data-state="open"
					class="absolute left-0 top-full z-50 mt-1 w-full max-w-md flex flex-col overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md
						data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
				>
					<ul bind:this={listEl} class="overflow-auto py-1 max-h-56">
						{#each popoverItems as item, i (item.kind === 'key' ? 'k:' + item.category.key : item.kind === 'operator' ? 'op:' + item.label : 'v:' + item.category.key + '/' + item.option.id)}
							<li>
								<button
									type="button"
									class="flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm transition-colors {i === highlightIdx ? 'bg-accent text-accent-foreground' : ''}"
									onmouseenter={() => (highlightIdx = i)}
									onmousedown={e => {
										e.preventDefault();
										highlightIdx = i;
										pickHighlighted();
									}}
								>
									{#if item.kind === 'key'}
										<span class="font-mono text-xs">{item.category.key}</span>
										<span class="ml-auto text-muted-foreground">{item.category.description ?? item.category.label}</span>
									{:else if item.kind === 'operator'}
										<span class="font-mono text-xs">{item.label}</span>
										<span class="ml-auto text-muted-foreground">{item.label === 'AND' ? 'All must match (implied when omitted)' : item.label === 'OR' ? 'Any can match' : 'Exclude matches'}</span>
									{:else if renderOption}
										{@render renderOption({ category: item.category, option: item.option })}
									{:else}
										<span>{item.option.label}</span>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
		{#if hasError}
			<div class="text-xs text-destructive">
				{errors[0].message}
			</div>
		{/if}
	</div>
{/if}
