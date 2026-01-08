<script>
	import { Search, X, Eye, EyeOff } from 'lucide-svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import OwnerFilter from './OwnerFilter.svelte';
	import { authStore } from '$lib/stores/auth.svelte.js';

	let {
		filters = { search: '', owners: new Set() },
		availableOwners = [],
		columns = [],
		columnVisibility = {},
		onFilterChange,
		onColumnVisibilityChange
	} = $props();

	// Check if any filter is active
	const hasActiveFilters = $derived(
		filters.search.length > 0 || filters.owners.size > 0
	);

	function handleSearchInput(e) {
		onFilterChange?.({ ...filters, search: e.target.value });
	}

	function clearSearch() {
		onFilterChange?.({ ...filters, search: '' });
	}

	function handleOwnersChange(owners) {
		onFilterChange?.({ ...filters, owners });
	}

	function clearAllFilters() {
		onFilterChange?.({ search: '', owners: new Set() });
	}

	function toggleColumn(columnId, checked) {
		onColumnVisibilityChange?.({
			...columnVisibility,
			[columnId]: checked
		});
	}
</script>

<div class="flex items-center gap-2 mb-6 flex-wrap">
	<!-- Search -->
	<div class="relative w-64">
		<Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
		<Input
			type="text"
			placeholder="Search..."
			value={filters.search}
			oninput={handleSearchInput}
			class="h-8 pl-9 pr-8 text-sm"
		/>
		{#if filters.search}
			<button
				type="button"
				class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-muted rounded"
				onclick={clearSearch}
			>
				<X class="h-3 w-3 text-muted-foreground" />
			</button>
		{/if}
	</div>

	<!-- Owner Filter (only when authenticated) -->
	{#if authStore.authEnabled && authStore.user}
		<OwnerFilter
			selected={filters.owners}
			{availableOwners}
			onChange={handleOwnersChange}
		/>
	{/if}

	<!-- Clear All (right next to filters) -->
	{#if hasActiveFilters}
		<Button variant="ghost" size="sm" class="h-8" onclick={clearAllFilters}>
			<X class="h-4 w-4 mr-1" />
			Clear
		</Button>
	{/if}

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Column Visibility -->
	<DropdownMenu.Root>
		<DropdownMenu.Trigger asChild>
			{#snippet child({ props })}
				<Button variant="outline" size="sm" class="h-8" {...props}>
					<Eye class="h-4 w-4 mr-1" />
					Columns
				</Button>
			{/snippet}
		</DropdownMenu.Trigger>
		<DropdownMenu.Content align="end">
			<DropdownMenu.Label>Toggle Columns</DropdownMenu.Label>
			<DropdownMenu.Separator />
			{#each columns as column}
				{#if column.accessorKey || column.id}
					{@const columnId = column.id || column.accessorKey}
					{@const isVisible = columnVisibility[columnId] !== false}
					<DropdownMenu.CheckboxItem
						checked={isVisible}
						onCheckedChange={(checked) => toggleColumn(columnId, checked)}
					>
						{#if isVisible}
							<Eye class="h-4 w-4 mr-2" />
						{:else}
							<EyeOff class="h-4 w-4 mr-2" />
						{/if}
						{column.header}
					</DropdownMenu.CheckboxItem>
				{/if}
			{/each}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
</div>
