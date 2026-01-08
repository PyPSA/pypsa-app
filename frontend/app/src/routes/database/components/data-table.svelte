<script>
	import { createTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel } from '@tanstack/svelte-table';
	import * as Table from '$lib/components/ui/table';
	import FlexRender from '$lib/components/ui/data-table/flex-render.svelte';
	import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-svelte';

	let { data, columns, totalItems, pageSize, sorting = $bindable([]), columnVisibility = $bindable({}), globalFilter = $bindable(''), onRowClick } = $props();

	const table = createTable({
		get data() {
			return data;
		},
		get columns() {
			return columns;
		},
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel(),
		manualPagination: true,
		get pageCount() {
			return Math.ceil(totalItems / pageSize);
		},
		state: {
			get sorting() {
				return sorting;
			},
			get columnVisibility() {
				return columnVisibility;
			},
			get globalFilter() {
				return globalFilter;
			}
		},
		onSortingChange: (updater) => {
			sorting = typeof updater === 'function' ? updater(sorting) : updater;
		},
		onColumnVisibilityChange: (updater) => {
			columnVisibility = typeof updater === 'function' ? updater(columnVisibility) : updater;
		},
		onGlobalFilterChange: (updater) => {
			globalFilter = typeof updater === 'function' ? updater(globalFilter) : updater;
		},
		globalFilterFn: (row, columnId, filterValue) => {
			const searchStr = filterValue.toLowerCase();
			const network = row.original;

			// Search in filename
			if (network.filename?.toLowerCase().includes(searchStr)) return true;

			// Search in network name
			if (network.name?.toLowerCase().includes(searchStr)) return true;

			// Search in file path
			if (network.file_path?.toLowerCase().includes(searchStr)) return true;

			// Search in tags
			if (network.tags && Array.isArray(network.tags)) {
				return network.tags.some((tag) => {
					if (typeof tag === 'string') {
						return tag.toLowerCase().includes(searchStr);
					} else if (typeof tag === 'object' && tag.name) {
						return tag.name.toLowerCase().includes(searchStr);
					}
					return false;
				});
			}

			return false;
		}
	});
</script>

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
											<FlexRender
												content={header.column.columnDef.header}
												context={header.getContext()}
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
										<FlexRender
											content={header.column.columnDef.header}
											context={header.getContext()}
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
						class="hover:bg-muted/30 transition-colors cursor-pointer"
						onclick={() => onRowClick?.(row.original)}
					>
						{#each row.getVisibleCells() as cell}
							<Table.Cell>
								<FlexRender
									content={cell.column.columnDef.cell}
									context={cell.getContext()}
								/>
							</Table.Cell>
						{/each}
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</div>
