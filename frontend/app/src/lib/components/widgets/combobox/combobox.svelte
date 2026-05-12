<script lang="ts">
	import type { Snippet } from 'svelte';
	import { tick } from 'svelte';
	import Search from '@lucide/svelte/icons/search';
	import Check from '@lucide/svelte/icons/check';
	import * as Popover from '$lib/components/ui/popover';

	export type ComboboxOption = {
		value: string;
		label: string;
		keywords?: string;
	};

	type Props = {
		options: ComboboxOption[];
		value?: string;
		onSelect: (value: string) => void | Promise<void>;
		trigger: Snippet<[{ props: Record<string, unknown> }]>;
		itemSnippet?: Snippet<[ComboboxOption]>;
		searchPlaceholder?: string;
		emptyText?: string;
		width?: string;
		align?: 'start' | 'center' | 'end';
		closeOnSelect?: boolean;
	};

	let {
		options,
		value,
		onSelect,
		trigger,
		itemSnippet,
		searchPlaceholder = 'Search...',
		emptyText = 'No results.',
		width = 'w-64',
		align = 'start',
		closeOnSelect = true
	}: Props = $props();

	let open = $state(false);
	let query = $state('');
	let activeIndex = $state(0);
	let inputEl = $state<HTMLInputElement | null>(null);

	const listboxId = `combobox-${Math.random().toString(36).slice(2, 10)}`;

	const filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		if (!q) return options;
		return options.filter((o) => {
			const hay = `${o.label} ${o.keywords ?? ''}`.toLowerCase();
			return hay.includes(q);
		});
	});

	// Clamp the active index against the current filtered list without writing
	// state inside an effect (avoids redundant runs when the index is already valid).
	const clampedIndex = $derived(Math.min(activeIndex, Math.max(0, filtered.length - 1)));

	$effect(() => {
		if (open) {
			query = '';
			activeIndex = 0;
			tick().then(() => inputEl?.focus());
		}
	});

	async function pick(v: string) {
		await onSelect(v);
		if (closeOnSelect) open = false;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			activeIndex = Math.min(clampedIndex + 1, filtered.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			activeIndex = Math.max(clampedIndex - 1, 0);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const item = filtered[clampedIndex];
			if (item) pick(item.value);
		} else if (e.key === 'Escape') {
			open = false;
		}
	}
</script>

<Popover.Root bind:open>
	<Popover.Trigger>
		{#snippet child({ props }: { props: Record<string, unknown> })}
			{@render trigger({ props })}
		{/snippet}
	</Popover.Trigger>
	<Popover.Content class="{width} p-0" {align}>
		<div class="flex items-center gap-2 border-b px-2">
			<Search class="size-3.5 shrink-0 text-muted-foreground" />
			<input
				bind:this={inputEl}
				bind:value={query}
				onkeydown={onKeydown}
				type="text"
				placeholder={searchPlaceholder}
				class="w-full bg-transparent py-2 text-sm outline-none placeholder:text-muted-foreground"
				role="combobox"
				aria-controls={listboxId}
				aria-expanded={open}
				aria-activedescendant={filtered.length > 0
					? `${listboxId}-opt-${clampedIndex}`
					: undefined}
			/>
		</div>
		<div class="max-h-64 overflow-y-auto py-1" role="listbox" id={listboxId}>
			{#if filtered.length === 0}
				<p class="px-3 py-2 text-xs text-muted-foreground">{emptyText}</p>
			{:else}
				{#each filtered as option, i (option.value)}
					{@const selected = option.value === value}
					<button
						type="button"
						role="option"
						id="{listboxId}-opt-{i}"
						aria-selected={selected}
						class="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted {i ===
						clampedIndex
							? 'bg-muted'
							: ''}"
						onmouseenter={() => (activeIndex = i)}
						onclick={() => pick(option.value)}
					>
						<Check
							class="size-3.5 shrink-0 {selected ? 'opacity-100' : 'opacity-0'}"
						/>
						<div class="min-w-0 flex-1 text-left">
							{#if itemSnippet}
								{@render itemSnippet(option)}
							{:else}
								<span class="truncate">{option.label}</span>
							{/if}
						</div>
					</button>
				{/each}
			{/if}
		</div>
	</Popover.Content>
</Popover.Root>
