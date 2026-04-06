<script lang="ts">
	import { onDestroy } from 'svelte';
	import { networks } from '$lib/api/client.js';
	import type { ComponentSummary, ComponentDataResponse, ApiError } from '$lib/types.js';
	import { Database, Search, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ArrowUpDown, ArrowUp, ArrowDown, Loader2 } from 'lucide-svelte';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import Button from '$lib/components/ui/button/button.svelte';

	let { networkId }: { networkId: string } = $props();

	// State
	let components = $state<ComponentSummary[]>([]);
	let selectedComponent = $state<ComponentSummary | null>(null);
	let componentData = $state<ComponentDataResponse | null>(null);
	let loadingComponents = $state(false);
	let loadingData = $state(false);
	let error = $state<string | null>(null);

	// Pagination
	let currentPage = $state(1);
	let pageSize = $state(50);

	// Sorting
	let sortBy = $state<string | null>(null);
	let sortDesc = $state(false);

	// Search
	let searchQuery = $state('');
	let searchTimeout: ReturnType<typeof setTimeout>;

	// Derived
	let totalPages = $derived(componentData ? Math.ceil(componentData.total / pageSize) : 0);
	let skip = $derived((currentPage - 1) * pageSize);

	// Cleanup on unmount
	onDestroy(() => {
		clearTimeout(searchTimeout);
	});

	// Load components list when networkId changes
	$effect(() => {
		if (networkId) {
			loadComponents();
		}
	});

	// Reload data when pagination/sort/search changes (single reactive source of truth)
	$effect(() => {
		if (selectedComponent && networkId) {
			// Track all reactive values that should trigger a reload
			const _page = currentPage;
			const _sort = sortBy;
			const _sortDir = sortDesc;
			const _search = searchQuery;
			loadComponentData();
		}
	});

	async function loadComponents() {
		loadingComponents = true;
		// Reset stale state from previous network
		selectedComponent = null;
		componentData = null;
		error = null;
		try {
			const response = await networks.getComponents(networkId);
			components = response.components;
			// Auto-select first component (the $effect above will trigger data load)
			if (components.length > 0) {
				selectedComponent = components[0];
				currentPage = 1;
				sortBy = null;
				sortDesc = false;
				searchQuery = '';
			}
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) return;
			error = (err as Error).message;
		} finally {
			loadingComponents = false;
		}
	}

	function selectComponent(comp: ComponentSummary) {
		selectedComponent = comp;
		currentPage = 1;
		sortBy = null;
		sortDesc = false;
		searchQuery = '';
		// The $effect watching selectedComponent will trigger loadComponentData
	}

	async function loadComponentData() {
		if (!selectedComponent) return;
		loadingData = true;
		try {
			componentData = await networks.getComponentData(networkId, selectedComponent.name, {
				skip,
				limit: pageSize,
				sort_by: sortBy ?? undefined,
				sort_desc: sortDesc,
				search: searchQuery || undefined,
			});
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) return;
			error = (err as Error).message;
		} finally {
			loadingData = false;
		}
	}

	function handleSort(column: string) {
		if (sortBy === column) {
			if (sortDesc) {
				// Third click: clear sort
				sortBy = null;
				sortDesc = false;
			} else {
				sortDesc = true;
			}
		} else {
			sortBy = column;
			sortDesc = false;
		}
		currentPage = 1;
		// The $effect will trigger loadComponentData
	}

	function handleSearch(e: Event) {
		const value = (e.target as HTMLInputElement).value;
		clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			searchQuery = value;
			currentPage = 1;
			// The $effect will trigger loadComponentData
		}, 300);
	}

	function goToPage(page: number) {
		if (page >= 1 && page <= totalPages) {
			currentPage = page;
		}
	}

	// Category display helpers
	function getCategoryLabel(category: string | null): string {
		if (!category) return 'Core';
		return category.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
	}

	function getCategoryColor(category: string | null): string {
		switch (category) {
			case 'controllable_one_port': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
			case 'controllable_branch': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
			case 'passive_branch': return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300';
			default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300';
		}
	}

	function formatCellValue(value: unknown, dtype: string): string {
		if (value === null || value === undefined) return '-';
		if (typeof value === 'number') {
			if (dtype.startsWith('float')) {
				return Number.isInteger(value) ? value.toString() : value.toFixed(4);
			}
			return value.toLocaleString();
		}
		if (typeof value === 'boolean') return value ? 'true' : 'false';
		return String(value);
	}
</script>

<div class="w-full bg-card rounded-lg border border-border">
	<div class="flex h-full min-h-[500px]">
		<!-- Component Sidebar -->
		<div class="w-56 shrink-0 border-r border-border bg-muted/30">
			<div class="p-3 border-b border-border">
				<h3 class="font-semibold text-sm flex items-center gap-2">
					<Database size={14} />
					Components
				</h3>
			</div>

			{#if loadingComponents}
				<div class="p-4 space-y-2">
					{#each Array(5) as _}
						<div class="h-8 bg-muted animate-pulse rounded"></div>
					{/each}
				</div>
			{:else}
				<div class="p-1 space-y-0.5 max-h-[500px] overflow-y-auto">
					{#each components as comp}
						<button
							onclick={() => selectComponent(comp)}
							class="w-full text-left px-3 py-2 rounded-md text-sm transition-colors
								{selectedComponent?.name === comp.name
									? 'bg-primary/10 text-primary font-medium'
									: 'hover:bg-muted text-foreground/80'}"
						>
							<div class="flex items-center justify-between">
								<span class="truncate">{comp.name}</span>
								<span class="text-xs text-muted-foreground ml-1 tabular-nums">{comp.count}</span>
							</div>
						</button>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Data Table -->
		<div class="flex-1 min-w-0 flex flex-col">
			{#if selectedComponent}
				<!-- Header -->
				<div class="p-3 border-b border-border flex items-center justify-between gap-3">
					<div class="flex items-center gap-2 min-w-0">
						<h3 class="font-semibold text-sm truncate">{selectedComponent.name}</h3>
						<Badge variant="secondary" class="text-xs shrink-0">
							{selectedComponent.count} rows
						</Badge>
						{#if selectedComponent.category}
							<Badge variant="outline" class="text-xs shrink-0 {getCategoryColor(selectedComponent.category)}">
								{getCategoryLabel(selectedComponent.category)}
							</Badge>
						{/if}
						{#if selectedComponent.has_dynamic}
							<Badge variant="outline" class="text-xs shrink-0 bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300">
								Time Series
							</Badge>
						{/if}
					</div>

					<!-- Search (controlled input that resets when component changes) -->
					<div class="relative shrink-0">
						<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
						<input
							type="text"
							placeholder="Search by name..."
							value={searchQuery}
							oninput={handleSearch}
							class="h-8 w-48 rounded-md border border-input bg-background pl-8 pr-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						/>
					</div>
				</div>

				<!-- Table -->
				<div class="flex-1 overflow-auto">
					{#if loadingData}
						<div class="flex items-center justify-center h-full">
							<Loader2 size={24} class="animate-spin text-muted-foreground" />
						</div>
					{:else if componentData && componentData.data.length > 0}
						<table class="w-full text-xs">
							<thead class="sticky top-0 bg-muted/80 backdrop-blur-sm z-10">
								<tr>
									<!-- Index column -->
									<th class="text-left px-3 py-2 font-semibold text-muted-foreground border-b border-border whitespace-nowrap bg-muted/50">
										<button
											onclick={() => handleSort('__index__')}
											class="flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer"
										>
											Name
											{#if sortBy === '__index__'}
												{#if sortDesc}
													<ArrowDown size={12} />
												{:else}
													<ArrowUp size={12} />
												{/if}
											{:else}
												<ArrowUpDown size={10} class="opacity-40" />
											{/if}
										</button>
									</th>
									{#each componentData.columns as col}
										<th class="text-left px-3 py-2 font-semibold text-muted-foreground border-b border-border whitespace-nowrap">
											<button
												onclick={() => handleSort(col)}
												class="flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer"
											>
												{col}
												{#if sortBy === col}
													{#if sortDesc}
														<ArrowDown size={12} />
													{:else}
														<ArrowUp size={12} />
													{/if}
												{:else}
													<ArrowUpDown size={10} class="opacity-40" />
												{/if}
											</button>
										</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each componentData.data as row, rowIdx}
									<tr class="border-b border-border/30 hover:bg-muted/20 transition-colors">
										<td class="px-3 py-1.5 font-mono font-medium text-foreground/90 whitespace-nowrap border-r border-border/30 bg-muted/10">
											{componentData.index[rowIdx]}
										</td>
										{#each row as cell, colIdx}
											{@const formatted = formatCellValue(cell, componentData.dtypes[componentData.columns[colIdx]] || '')}
											<td class="px-3 py-1.5 text-foreground/70 whitespace-nowrap max-w-[200px] truncate" title={formatted}>
												{formatted}
											</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					{:else if componentData}
						<div class="flex items-center justify-center h-full text-muted-foreground text-sm">
							{searchQuery ? 'No matching rows found' : 'No data available'}
						</div>
					{/if}
				</div>

				<!-- Pagination -->
				{#if componentData && componentData.total > pageSize}
					<div class="px-3 py-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
						<div>
							Showing {skip + 1}-{Math.min(skip + pageSize, componentData.total)} of {componentData.total.toLocaleString()}
						</div>
						<div class="flex items-center gap-1">
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(1)} disabled={currentPage === 1}>
								<ChevronsLeft size={14} />
							</Button>
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(currentPage - 1)} disabled={currentPage === 1}>
								<ChevronLeft size={14} />
							</Button>
							<span class="px-2 tabular-nums">
								{currentPage} / {totalPages}
							</span>
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(currentPage + 1)} disabled={currentPage === totalPages}>
								<ChevronRight size={14} />
							</Button>
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(totalPages)} disabled={currentPage === totalPages}>
								<ChevronsRight size={14} />
							</Button>
						</div>
					</div>
				{/if}
			{:else}
				<div class="flex items-center justify-center h-full text-muted-foreground text-sm">
					Select a component type to view its data
				</div>
			{/if}
		</div>
	</div>
</div>
