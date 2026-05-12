<script lang="ts" generics="TData">
	import {
		createTable,
		getCoreRowModel,
		getSortedRowModel,
		type ColumnDef,
		type SortingState,
		type VisibilityState,
		type Updater
	} from '@tanstack/svelte-table';
	import * as Table from '$lib/components/ui/table';
	import * as PaginationUI from '$lib/components/ui/pagination';
	import * as Select from '$lib/components/ui/select';
	import FlexRender from '$lib/components/ui/data-table/flex-render.svelte';
	import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { TokenSearchInput } from '$lib/components/ui/filter-dialog';
	import type { FilterCategory, FilterOption } from '$lib/components/ui/filter-dialog';
	import type { FilterAst } from '$lib/filters/ast';
	import { emptyAnd } from '$lib/filters/ast';
	import type { Snippet } from 'svelte';

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	type ColumnWithAccessor = { header?: any; id?: string; accessorKey?: string };

	let {
		data,
		columns,
		pageSize = 25,
		sorting = $bindable([]),
		columnVisibility = $bindable({}),
		onRowClick = undefined,
		totalItems = undefined,
		currentPage = $bindable(1),
		onPageChange = undefined,
		onPageSizeChange = undefined,
		// Column visibility
		onColumnVisibilityChange = undefined,
		// Sorting callback
		onSortingChange: onSortingChangeProp = undefined,
		defaultSorting = undefined,
		// Filters
		filterCategories = [],
		filter = undefined,
		onFilterAstChange = undefined,
		renderOption = undefined,
	}: {
		data: TData[];
		columns: ColumnDef<TData, unknown>[];
		pageSize?: number;
		sorting?: SortingState;
		columnVisibility?: VisibilityState;
		onRowClick?: (row: TData) => void;
		totalItems?: number;
		currentPage?: number;
		onPageChange?: (page: number) => void;
		onPageSizeChange?: (size: number) => void;
		onColumnVisibilityChange?: (visibility: VisibilityState) => void;
		onSortingChange?: (sorting: SortingState) => void;
		defaultSorting?: SortingState;
		filterCategories?: FilterCategory[];
		filter?: FilterAst;
		onFilterAstChange?: (ast: FilterAst) => void;
		renderOption?: Snippet<[{ category: FilterCategory; option: FilterOption }]>;
	} = $props();

	// Pagination logic
	const effectiveTotalItems = $derived(totalItems ?? data.length);
	const effectivePage = $derived(currentPage);
	const effectivePageSize = $derived(pageSize);

	const showPagination = $derived(effectiveTotalItems > effectivePageSize);

	function handlePageChange(page: number) {
		onPageChange?.(page);
	}

	function handlePageSizeChange(size: number) {
		onPageSizeChange?.(size);
	}

	const filterAst = $derived<FilterAst>(filter ?? emptyAnd());

	function handleAstChange(ast: FilterAst) {
		onFilterAstChange?.(ast);
	}

	// Toolbar visibility
	let showColumnVisibility = $derived(onColumnVisibilityChange != null);
	let showFilters = $derived(filterCategories != null && filterCategories.length > 0);
	let showToolbar = $derived(showColumnVisibility || showFilters);

	// Column visibility helpers
	const visibleColumns = $derived<ColumnWithAccessor[]>(
		showColumnVisibility ? (columns as unknown as ColumnWithAccessor[]) : []
	);

	function toggleColumn(columnId: string, checked: boolean) {
		onColumnVisibilityChange?.({
			...columnVisibility,
			[columnId]: checked
		});
	}

	// Pagination display values
	const totalPages = $derived(Math.ceil(effectiveTotalItems / effectivePageSize) || 1);
	const startItem = $derived(effectiveTotalItems === 0 ? 0 : (effectivePage - 1) * effectivePageSize + 1);
	const endItem = $derived(Math.min(effectivePage * effectivePageSize, effectiveTotalItems));
	const isFirstPage = $derived(effectivePage === 1);
	const isLastPage = $derived(effectivePage === totalPages);
	const pageSizeOptions = [10, 25, 50, 100];

	function goToPage(page: number) {
		if (page >= 1 && page <= totalPages && page !== effectivePage) {
			handlePageChange(page);
		}
	}

	function handlePageSizeSelect(value: string | undefined) {
		if (value) handlePageSizeChange(parseInt(value));
	}

	// TanStack table instance
	const table = createTable<TData>({
		get data() {
			return data;
		},
		get columns() {
			return columns;
		},
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		manualPagination: true,
		get pageCount() {
			return Math.ceil(effectiveTotalItems / effectivePageSize);
		},
		state: {
			get sorting() {
				return sorting;
			},
			get columnVisibility() {
				return columnVisibility;
			}
		},
		onSortingChange: (updater: Updater<SortingState>) => {
			const prev = sorting;
			let next = typeof updater === 'function' ? updater(sorting) : updater;
			if (next.length === 0 && defaultSorting && defaultSorting.length > 0) {
				const defCol = defaultSorting[0];
				if (prev.length === 1 && prev[0].id === defCol.id) {
					next = [{ id: prev[0].id, desc: !prev[0].desc }];
				} else {
					next = defaultSorting;
				}
			}
			sorting = next;
			onSortingChangeProp?.(sorting);
		},
		onColumnVisibilityChange: (updater: Updater<VisibilityState>) => {
			columnVisibility = typeof updater === 'function' ? updater(columnVisibility) : updater;
		}
	});
</script>

{#if showToolbar}
	<div class="mb-6 flex items-center gap-2 flex-wrap">
		{#if showFilters}
			<div class="flex-1 min-w-[16rem] max-w-[40rem]">
				<TokenSearchInput
					categories={filterCategories}
					filter={filterAst}
					onFilterChange={handleAstChange}
					{renderOption}
				/>
			</div>
		{/if}

		<div class="flex-1"></div>

		{#if showColumnVisibility && visibleColumns.length > 0}
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
					{#each visibleColumns as column}
						{#if (column.accessorKey || column.id) && column.header}
							{@const columnId = (column.id || column.accessorKey) as string}
							{@const isVisible = columnVisibility[columnId] !== false}
							<DropdownMenu.CheckboxItem
								checked={isVisible}
								onCheckedChange={(checked: boolean) => toggleColumn(columnId, checked)}
								closeOnSelect={false}
							>
								{column.header}
							</DropdownMenu.CheckboxItem>
						{/if}
					{/each}
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		{/if}
	</div>
{/if}

<div class="bg-card rounded-lg border border-border overflow-hidden">
	<div class="overflow-x-auto">
		<Table.Root>
			<Table.Header>
				{#each table.getHeaderGroups() as headerGroup}
					<Table.Row>
						{#each headerGroup.headers as header}
							<Table.Head>
								{#if !header.isPlaceholder}
									{#if header.column.getCanSort()}
										<button
											class="flex items-center gap-2 hover:text-foreground transition-colors"
											onclick={header.column.getToggleSortingHandler()}
										>
											<!-- eslint-disable-next-line @typescript-eslint/no-explicit-any -->
											<FlexRender
												content={header.column.columnDef.header as any}
												context={header.getContext() as any}
											/>
											{#if header.column.getIsSorted() === 'asc'}
												<ArrowUp class="h-4 w-4" />
											{:else if header.column.getIsSorted() === 'desc'}
												<ArrowDown class="h-4 w-4" />
											{:else}
												<ArrowUpDown class="h-4 w-4 opacity-50" />
											{/if}
										</button>
									{:else}
										<!-- eslint-disable-next-line @typescript-eslint/no-explicit-any -->
										<FlexRender
											content={header.column.columnDef.header as any}
											context={header.getContext() as any}
										/>
									{/if}
								{/if}
							</Table.Head>
						{/each}
					</Table.Row>
				{/each}
			</Table.Header>
			<Table.Body>
				{#each table.getRowModel().rows as row}
					<Table.Row
						class="hover:bg-muted/30 transition-colors {onRowClick ? 'cursor-pointer' : ''}"
						onclick={() => onRowClick?.(row.original)}
					>
						{#each row.getVisibleCells() as cell}
							<Table.Cell>
								<!-- eslint-disable-next-line @typescript-eslint/no-explicit-any -->
								<FlexRender
									content={cell.column.columnDef.cell as any}
									context={cell.getContext() as any}
								/>
							</Table.Cell>
						{/each}
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</div>

{#if showPagination}
	<div class="mt-6 flex flex-col items-center gap-4">
		<div class="text-sm text-muted-foreground">
			{#if effectiveTotalItems === 0}
				No items
			{:else}
				Showing {startItem}-{endItem} of {effectiveTotalItems.toLocaleString()}
			{/if}
		</div>

		<div class="flex items-center gap-2">
			<PaginationUI.Root count={effectiveTotalItems} perPage={effectivePageSize} page={effectivePage} onPageChange={(page) => goToPage(page)}>
				{#snippet children({ pages })}
					<PaginationUI.Content class="[&_button]:h-7 [&_button]:text-xs [&_button:not(:has(svg))]:w-7">
						<PaginationUI.Item>
							<PaginationUI.PrevButton class="w-auto px-2" onclick={() => goToPage(effectivePage - 1)} disabled={isFirstPage} />
						</PaginationUI.Item>

						{#each pages as page}
							{#if page.type === 'ellipsis'}
								<PaginationUI.Item>
									<PaginationUI.Ellipsis />
								</PaginationUI.Item>
							{:else}
								<PaginationUI.Item>
									<PaginationUI.Link {page} isActive={effectivePage === page.value} onclick={() => goToPage(page.value)}>
										{page.value}
									</PaginationUI.Link>
								</PaginationUI.Item>
							{/if}
						{/each}

						<PaginationUI.Item>
							<PaginationUI.NextButton class="w-auto px-2" onclick={() => goToPage(effectivePage + 1)} disabled={isLastPage} />
						</PaginationUI.Item>
					</PaginationUI.Content>
				{/snippet}
			</PaginationUI.Root>

			<div class="flex items-center gap-2">
				<span class="text-xs text-muted-foreground">Per page:</span>
				<Select.Root type="single" value={effectivePageSize.toString()} onValueChange={handlePageSizeSelect}>
					<Select.Trigger class="h-7 w-[70px] text-xs">
						{effectivePageSize}
					</Select.Trigger>
					<Select.Content>
						{#each pageSizeOptions as size}
							<Select.Item value={size.toString()}>
								{size}
							</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>
		</div>
	</div>
{/if}
