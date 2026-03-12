<script lang="ts">
	import { ChevronDown, X } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import * as Popover from '$lib/components/ui/popover';
	import { Checkbox } from '$lib/components/ui/checkbox';

	/**
	 * Reusable multi-select filter with checkboxes.
	 *
	 * The `selected` Set contains IDs of checked items.
	 * Parent component decides what empty set means for filtering.
	 *
	 * Props:
	 * - emptyMeansAll: if true, empty set displays as "All" (default: true)
	 */

	interface FilterOption {
		id: string;
		label: string;
		avatarUrl?: string;
		icon?: typeof import('lucide-svelte').X;
	}

	let {
		label = 'Filter',
		options = [] as FilterOption[],
		selected = new Set<string>(),
		onChange,
		align = 'start' as 'start' | 'center' | 'end',
		width = 'w-48',
		emptyMeansAll = true,
		showNone = true
	}: {
		label?: string;
		options?: FilterOption[];
		selected?: Set<string>;
		onChange?: (selected: Set<string>) => void;
		align?: 'start' | 'center' | 'end';
		width?: string;
		emptyMeansAll?: boolean;
		showNone?: boolean;
	} = $props();

	let open = $state(false);

	const NONE_MARKER = '__none__';

	const allIds = $derived(new Set(options.map(o => o.id)));
	const allExplicitlySelected = $derived(options.length > 0 && options.every(o => selected.has(o.id)));
	const isEmpty = $derived(selected.size === 0);
	const isExplicitNone = $derived(selected.has(NONE_MARKER));

	// For display: empty set = all, __none__ marker = none
	const effectivelyAll = $derived(isEmpty && emptyMeansAll || allExplicitlySelected);

	const displayLabel = $derived.by(() => {
		if (isExplicitNone) return 'None';
		if (isEmpty) return emptyMeansAll ? 'All' : 'None';
		if (allExplicitlySelected) return 'All';
		if (selected.size === 1) {
			const selectedId = Array.from(selected)[0];
			const opt = options.find(o => o.id === selectedId);
			return opt?.label || selectedId;
		}
		return `${selected.size} selected`;
	});

	// Filter is active when not showing all
	const isFiltered = $derived(!effectivelyAll || isExplicitNone);

	function setOptionChecked(optionId: string, checked: boolean) {
		if (isExplicitNone) {
			// Currently "none" - user clicks to check one item
			onChange?.(new Set([optionId]));
		} else if (isEmpty && emptyMeansAll) {
			// Currently showing "all" (empty set). User wants to uncheck one.
			// Select all EXCEPT the clicked one.
			const newSelected = new Set(allIds);
			newSelected.delete(optionId);
			onChange?.(newSelected);
		} else {
			const newSelected = new Set(selected);
			if (checked) {
				newSelected.add(optionId);
			} else {
				newSelected.delete(optionId);
			}
			// If all are now selected, reset to empty (which means "all")
			if (emptyMeansAll && newSelected.size === options.length) {
				onChange?.(new Set());
			} else if (newSelected.size === 0) {
				// User manually deselected all
				onChange?.(showNone ? new Set([NONE_MARKER]) : new Set());
			} else {
				onChange?.(newSelected);
			}
		}
	}

	function selectAll() {
		onChange?.(new Set());
	}

	function selectNone() {
		onChange?.(new Set([NONE_MARKER]));
	}

	function handleClear(e: MouseEvent) {
		e.stopPropagation();
		selectAll();
	}

	// Visual checkbox state
	function isOptionChecked(optionId: string) {
		if (isExplicitNone) return false;
		if (isEmpty && emptyMeansAll) return true;
		return selected.has(optionId);
	}
</script>

<Popover.Root bind:open>
	<Popover.Trigger>
		{#snippet child({ props })}
			<Button
				variant="outline"
				size="sm"
				class="h-8 gap-1 px-2 {isFiltered ? 'bg-accent' : ''}"
				{...props}
			>
				<span class="text-muted-foreground">{label}:</span>
				<span class="truncate max-w-24">{displayLabel}</span>
				{#if isFiltered}
					<button
						type="button"
						class="ml-1 rounded-full p-0.5 hover:bg-muted"
						onclick={handleClear}
					>
						<X class="h-3 w-3" />
					</button>
				{:else}
					<ChevronDown class="h-3 w-3 text-muted-foreground" />
				{/if}
			</Button>
		{/snippet}
	</Popover.Trigger>
	<Popover.Content class="{width} p-2" {align}>
		<!-- Quick actions -->
		<div class="flex gap-1 mb-2 pb-2 border-b">
			<Button
				variant={effectivelyAll && !isExplicitNone ? 'secondary' : 'ghost'}
				size="sm"
				class="h-7 text-xs flex-1"
				onclick={selectAll}
			>
				All
			</Button>
			{#if showNone}
				<Button
					variant={isExplicitNone ? 'secondary' : 'ghost'}
					size="sm"
					class="h-7 text-xs flex-1"
					onclick={selectNone}
				>
					None
				</Button>
			{/if}
		</div>

		<!-- Option checkboxes -->
		<div class="space-y-1 max-h-48 overflow-y-auto">
			{#each options as option}
				{@const checked = isOptionChecked(option.id)}
				<button
					type="button"
					class="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer w-full text-left"
					onclick={() => setOptionChecked(option.id, !checked)}
				>
					<Checkbox
						{checked}
						tabindex={-1}
					/>
					{#if option.avatarUrl}
						<img src={option.avatarUrl} alt="" class="h-4 w-4 rounded-full" />
					{:else if option.icon}
						<option.icon class="h-3.5 w-3.5 text-muted-foreground" />
					{/if}
					<span class="text-sm truncate">{option.label}</span>
				</button>
			{/each}
		</div>
	</Popover.Content>
</Popover.Root>
