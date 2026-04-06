<script lang="ts">
	import { onDestroy } from 'svelte';
	import { networks } from '$lib/api/client.js';
	import type { ComponentSummary, ComponentDataResponse, ApiError } from '$lib/types.js';
	import { Database, Search, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ArrowUpDown, ArrowUp, ArrowDown, Loader2, Pencil, Save, X } from 'lucide-svelte';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { toast } from 'svelte-sonner';

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

	// Edit mode
	let editMode = $state(false);
	let pendingEdits = $state<Map<string, Map<string, unknown>>>(new Map());
	let saving = $state(false);

	// Derived
	let totalPages = $derived(componentData ? Math.ceil(componentData.total / pageSize) : 0);
	let skip = $derived((currentPage - 1) * pageSize);
	let hasEdits = $derived(pendingEdits.size > 0);
	let editCount = $derived(() => {
		let count = 0;
		for (const cols of pendingEdits.values()) count += cols.size;
		return count;
	});

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
			const _page = currentPage;
			const _sort = sortBy;
			const _sortDir = sortDesc;
			const _search = searchQuery;
			loadComponentData();
		}
	});

	async function loadComponents() {
		loadingComponents = true;
		selectedComponent = null;
		componentData = null;
		editMode = false;
		pendingEdits = new Map();
		error = null;
		try {
			const response = await networks.getComponents(networkId);
			components = response.components;
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
		if (editMode && hasEdits) {
			if (!confirm('You have unsaved changes. Discard them?')) return;
		}
		selectedComponent = comp;
		currentPage = 1;
		sortBy = null;
		sortDesc = false;
		searchQuery = '';
		editMode = false;
		pendingEdits = new Map();
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
		if (editMode) return; // Disable sort while editing
		if (sortBy === column) {
			if (sortDesc) {
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
	}

	function handleSearch(e: Event) {
		const value = (e.target as HTMLInputElement).value;
		clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			searchQuery = value;
			currentPage = 1;
		}, 300);
	}

	function goToPage(page: number) {
		if (page >= 1 && page <= totalPages) {
			currentPage = page;
		}
	}

	// Edit mode functions
	function toggleEditMode() {
		if (editMode && hasEdits) {
			if (!confirm('You have unsaved changes. Discard them?')) return;
		}
		editMode = !editMode;
		pendingEdits = new Map();
	}

	function handleCellEdit(rowIndex: string, column: string, value: string, dtype: string) {
		const parsed = parseValue(value, dtype);
		const rowEdits = pendingEdits.get(rowIndex) ?? new Map();

		// Check if the new value matches the original
		if (componentData) {
			const rowIdx = componentData.index.indexOf(rowIndex);
			const colIdx = componentData.columns.indexOf(column);
			if (rowIdx >= 0 && colIdx >= 0) {
				const original = componentData.data[rowIdx][colIdx];
				if (parsed === original || (parsed === null && original === null)) {
					rowEdits.delete(column);
					if (rowEdits.size === 0) {
						pendingEdits.delete(rowIndex);
					}
					pendingEdits = new Map(pendingEdits); // trigger reactivity
					return;
				}
			}
		}

		rowEdits.set(column, parsed);
		pendingEdits.set(rowIndex, rowEdits);
		pendingEdits = new Map(pendingEdits); // trigger reactivity
	}

	function parseValue(value: string, dtype: string): unknown {
		if (value === '' || value === '-') return null;
		if (dtype.startsWith('float')) {
			const num = parseFloat(value);
			return isNaN(num) ? value : num;
		}
		if (dtype.startsWith('int') || dtype.startsWith('uint')) {
			const num = parseInt(value, 10);
			return isNaN(num) ? value : num;
		}
		if (dtype === 'bool') return value === 'true' || value === '1';
		return value;
	}

	function getEditedValue(rowIndex: string, column: string): unknown | undefined {
		return pendingEdits.get(rowIndex)?.get(column);
	}

	function isEdited(rowIndex: string, column: string): boolean {
		return pendingEdits.get(rowIndex)?.has(column) ?? false;
	}

	async function saveEdits() {
		if (!selectedComponent || !hasEdits) return;
		saving = true;

		// Convert Map to plain object for API
		const updates: Record<string, Record<string, unknown>> = {};
		for (const [rowIndex, colEdits] of pendingEdits) {
			updates[rowIndex] = {};
			for (const [col, val] of colEdits) {
				updates[rowIndex][col] = val;
			}
		}

		try {
			const result = await networks.updateComponentData(networkId, selectedComponent.name, updates);
			toast.success(result.message);
			pendingEdits = new Map();
			editMode = false;
			// Reload data to reflect saved changes
			await loadComponentData();
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to save changes');
		} finally {
			saving = false;
		}
	}

	function cancelEdits() {
		pendingEdits = new Map();
		editMode = false;
	}

	// Display helpers
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

	function getCellDisplayValue(rowIdx: number, colIdx: number): string {
		if (!componentData) return '-';
		const rowIndex = componentData.index[rowIdx];
		const column = componentData.columns[colIdx];
		const dtype = componentData.dtypes[column] || '';
		const edited = getEditedValue(rowIndex, column);
		if (edited !== undefined) {
			return formatCellValue(edited, dtype);
		}
		return formatCellValue(componentData.data[rowIdx][colIdx], dtype);
	}

	function getCellRawValue(rowIdx: number, colIdx: number): string {
		if (!componentData) return '';
		const rowIndex = componentData.index[rowIdx];
		const column = componentData.columns[colIdx];
		const edited = getEditedValue(rowIndex, column);
		const value = edited !== undefined ? edited : componentData.data[rowIdx][colIdx];
		if (value === null || value === undefined) return '';
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

					<div class="flex items-center gap-2 shrink-0">
						<!-- Search (disabled in edit mode) -->
						{#if !editMode}
							<div class="relative">
								<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
								<input
									type="text"
									placeholder="Search by name..."
									value={searchQuery}
									oninput={handleSearch}
									class="h-8 w-48 rounded-md border border-input bg-background pl-8 pr-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
								/>
							</div>
						{/if}

						<!-- Edit controls -->
						{#if editMode}
							{#if hasEdits}
								<Badge variant="secondary" class="text-xs">
									{editCount()} change{editCount() !== 1 ? 's' : ''}
								</Badge>
							{/if}
							<Button variant="ghost" size="sm" class="h-8 text-xs" onclick={cancelEdits} disabled={saving}>
								<X size={14} class="mr-1" />
								Cancel
							</Button>
							<Button variant="default" size="sm" class="h-8 text-xs" onclick={saveEdits} disabled={!hasEdits || saving}>
								{#if saving}
									<Loader2 size={14} class="mr-1 animate-spin" />
									Saving...
								{:else}
									<Save size={14} class="mr-1" />
									Save
								{/if}
							</Button>
						{:else}
							<Button variant="ghost" size="icon" class="h-8 w-8" onclick={toggleEditMode} title="Edit component data">
								<Pencil size={14} />
							</Button>
						{/if}
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
									<th class="text-left px-3 py-2 font-semibold text-muted-foreground border-b border-border whitespace-nowrap bg-muted/50">
										<button
											onclick={() => handleSort('__index__')}
											class="flex items-center gap-1 hover:text-foreground transition-colors {editMode ? 'cursor-default' : 'cursor-pointer'}"
											disabled={editMode}
										>
											Name
											{#if sortBy === '__index__'}
												{#if sortDesc}
													<ArrowDown size={12} />
												{:else}
													<ArrowUp size={12} />
												{/if}
											{:else if !editMode}
												<ArrowUpDown size={10} class="opacity-40" />
											{/if}
										</button>
									</th>
									{#each componentData.columns as col}
										<th class="text-left px-3 py-2 font-semibold text-muted-foreground border-b border-border whitespace-nowrap">
											<button
												onclick={() => handleSort(col)}
												class="flex items-center gap-1 hover:text-foreground transition-colors {editMode ? 'cursor-default' : 'cursor-pointer'}"
												disabled={editMode}
											>
												{col}
												{#if sortBy === col}
													{#if sortDesc}
														<ArrowDown size={12} />
													{:else}
														<ArrowUp size={12} />
													{/if}
												{:else if !editMode}
													<ArrowUpDown size={10} class="opacity-40" />
												{/if}
											</button>
										</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each componentData.data as row, rowIdx}
									{@const rowIndex = componentData.index[rowIdx]}
									<tr class="border-b border-border/30 hover:bg-muted/20 transition-colors">
										<td class="px-3 py-1.5 font-mono font-medium text-foreground/90 whitespace-nowrap border-r border-border/30 bg-muted/10">
											{rowIndex}
										</td>
										{#each row as cell, colIdx}
											{@const column = componentData.columns[colIdx]}
											{@const dtype = componentData.dtypes[column] || ''}
											{@const edited = isEdited(rowIndex, column)}
											{#if editMode}
												<td class="px-0.5 py-0.5 {edited ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''}">
													<input
														type="text"
														value={getCellRawValue(rowIdx, colIdx)}
														onchange={(e) => handleCellEdit(rowIndex, column, (e.target as HTMLInputElement).value, dtype)}
														class="w-full h-full px-2 py-1 text-xs bg-transparent border border-transparent rounded
															hover:border-border focus:border-primary focus:outline-none
															{edited ? 'border-yellow-400 dark:border-yellow-600' : ''}"
													/>
												</td>
											{:else}
												{@const formatted = getCellDisplayValue(rowIdx, colIdx)}
												<td class="px-3 py-1.5 text-foreground/70 whitespace-nowrap max-w-[200px] truncate" title={formatted}>
													{formatted}
												</td>
											{/if}
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
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(1)} disabled={currentPage === 1 || editMode}>
								<ChevronsLeft size={14} />
							</Button>
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(currentPage - 1)} disabled={currentPage === 1 || editMode}>
								<ChevronLeft size={14} />
							</Button>
							<span class="px-2 tabular-nums">
								{currentPage} / {totalPages}
							</span>
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(currentPage + 1)} disabled={currentPage === totalPages || editMode}>
								<ChevronRight size={14} />
							</Button>
							<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => goToPage(totalPages)} disabled={currentPage === totalPages || editMode}>
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
