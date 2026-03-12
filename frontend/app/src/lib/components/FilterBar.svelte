<script lang="ts">
	import { Search, X, SlidersHorizontal } from 'lucide-svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { FilterDialog } from '$lib/components/ui/filter-dialog';
	import type { FilterState, FilterCategory } from '$lib/components/ui/filter-dialog';
	import type { ColumnDef, VisibilityState } from '@tanstack/table-core';

	type ColumnWithAccessor = ColumnDef<unknown, unknown> & { accessorKey?: string };

	interface FilterBarProps {
		filterCategories?: FilterCategory[];
		filters?: FilterState;
		onFilterChange?: (filters: FilterState) => void;
		search?: string;
		onSearchChange?: (search: string) => void;
		columns?: ColumnWithAccessor[];
		columnVisibility?: VisibilityState;
		onColumnVisibilityChange?: (visibility: VisibilityState) => void;
	}

	let {
		filterCategories = [],
		filters = {},
		onFilterChange,
		search,
		onSearchChange,
		columns = [],
		columnVisibility = {},
		onColumnVisibilityChange
	}: FilterBarProps = $props();

	function handleSearchInput(e: Event) {
		onSearchChange?.((e.target as HTMLInputElement).value);
	}

	function clearSearch() {
		onSearchChange?.('');
	}

	function toggleColumn(columnId: string, checked: boolean) {
		onColumnVisibilityChange?.({
			...columnVisibility,
			[columnId]: checked
		});
	}
</script>

<div class="flex items-center gap-2 mb-6 flex-wrap">
	<!-- Filter Dialog -->
	<FilterDialog
		categories={filterCategories}
		{filters}
		onFilterChange={(newFilters: FilterState) => onFilterChange?.(newFilters)}
	/>

	<!-- Search (optional) -->
	{#if onSearchChange !== undefined}
		<div class="relative w-64">
			<Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
			<Input
				type="text"
				placeholder="Search..."
				value={search ?? ''}
				oninput={handleSearchInput}
				class="h-8 pl-9 pr-8 text-sm"
			/>
			{#if search}
				<button
					type="button"
					class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-muted rounded"
					onclick={clearSearch}
				>
					<X class="h-3 w-3 text-muted-foreground" />
				</button>
			{/if}
		</div>
	{/if}

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Column Visibility -->
	<DropdownMenu.Root>
		<DropdownMenu.Trigger>
			{#snippet child({ props }: { props: Record<string, unknown> })}
				<Button variant="ghost" size="icon" class="h-8 w-8" {...props}>
					<SlidersHorizontal class="h-4 w-4" />
				</Button>
			{/snippet}
		</DropdownMenu.Trigger>
		<DropdownMenu.Content align="end">
			<DropdownMenu.Label>Toggle Columns</DropdownMenu.Label>
			<DropdownMenu.Separator />
			{#each columns as column}
				{#if (column.accessorKey || column.id) && column.header}
					{@const columnId = (column.id || column.accessorKey) as string}
					{@const isVisible = columnVisibility[columnId] !== false}
					<DropdownMenu.CheckboxItem
						checked={isVisible}
						onCheckedChange={(checked: boolean) => toggleColumn(columnId, checked)}
					>
						{column.header}
					</DropdownMenu.CheckboxItem>
				{/if}
			{/each}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
</div>
