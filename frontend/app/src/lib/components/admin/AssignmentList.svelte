<script lang="ts" generics="T extends { id: string }">
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/button/button.svelte';
	import { Combobox, type ComboboxOption } from '$lib/components/widgets/combobox';

	type Props = {
		items: T[];
		candidates: T[];
		labelOf: (item: T) => string;
		keywordsOf?: (item: T) => string;
		onAdd: (id: string) => void | Promise<void>;
		onRemove: (id: string) => void | Promise<void>;
		emptyText?: string;
		addLabel?: string;
		searchPlaceholder?: string;
		rowSnippet?: import('svelte').Snippet<[T]>;
	};

	let {
		items,
		candidates,
		labelOf,
		keywordsOf,
		onAdd,
		onRemove,
		emptyText = 'Nothing assigned.',
		addLabel = 'Assign',
		searchPlaceholder = 'Search...',
		rowSnippet
	}: Props = $props();

	const assignedIds = $derived(new Set(items.map((i) => i.id)));
	const options = $derived<ComboboxOption[]>(
		candidates
			.filter((c) => !assignedIds.has(c.id))
			.map((c) => ({
				value: c.id,
				label: labelOf(c),
				keywords: keywordsOf?.(c)
			}))
	);
</script>

<div class="space-y-2">
	{#if items.length === 0}
		<p class="text-xs text-muted-foreground">{emptyText}</p>
	{:else}
		<div class="space-y-1">
			{#each items as item (item.id)}
				<div class="flex items-center justify-between rounded-md border px-3 py-2">
					{#if rowSnippet}
						{@render rowSnippet(item)}
					{:else}
						<span class="text-sm">{labelOf(item)}</span>
					{/if}
					<Button
						variant="ghost"
						size="icon"
						class="size-7"
						onclick={() => onRemove(item.id)}
						title="Remove"
					>
						<Trash2 class="size-3.5 text-destructive" />
					</Button>
				</div>
			{/each}
		</div>
	{/if}

	{#if candidates.length === 0}
		<p class="text-xs text-muted-foreground">No candidates available.</p>
	{:else if options.length > 0}
		<Combobox {options} onSelect={onAdd} {searchPlaceholder} emptyText="No matches.">
			{#snippet trigger({ props })}
				<Button variant="outline" size="sm" {...props}>
					<Plus class="mr-1 size-3.5" />
					{addLabel}
				</Button>
			{/snippet}
		</Combobox>
	{/if}
</div>
