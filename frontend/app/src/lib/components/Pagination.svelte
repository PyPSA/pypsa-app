<script>
	import * as Pagination from '$lib/components/ui/pagination';
	import * as Select from '$lib/components/ui/select';

	let {
		currentPage = 1,
		pageSize = 25,
		totalItems = 0,
		onPageChange = () => {},
		onPageSizeChange = () => {}
	} = $props();

	// Calculate pagination values
	const totalPages = $derived(Math.ceil(totalItems / pageSize) || 1);
	const startItem = $derived(totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1);
	const endItem = $derived(Math.min(currentPage * pageSize, totalItems));
	const isFirstPage = $derived(currentPage === 1);
	const isLastPage = $derived(currentPage === totalPages);

	// Selected page size for Select component
	const selectedValue = $derived(pageSize.toString());

	// Page size options
	const pageSizeOptions = [10, 25, 50, 100];

	function goToPage(page) {
		if (page >= 1 && page <= totalPages && page !== currentPage) {
			onPageChange(page);
		}
	}

	function handlePageSizeChange(value) {
		if (value) {
			const newSize = parseInt(value);
			onPageSizeChange(newSize);
		}
	}

</script>

<div class="flex flex-col items-center gap-4">
	<div class="text-sm text-muted-foreground">
		{#if totalItems === 0}
			No items
		{:else}
			Showing {startItem}-{endItem} of {totalItems.toLocaleString()}
		{/if}
	</div>

	<div class="flex items-center gap-2">
		<Pagination.Root count={totalItems} perPage={pageSize} page={currentPage} onPageChange={(page) => goToPage(page)}>
			{#snippet children({ pages })}
				<Pagination.Content class="[&_button]:h-7 [&_button]:text-xs [&_button:not(:has(svg))]:w-7">
					<Pagination.Item>
						<Pagination.PrevButton class="w-auto px-2" onclick={() => goToPage(currentPage - 1)} disabled={isFirstPage} />
					</Pagination.Item>

					{#each pages as page}
						{#if page.type === 'ellipsis'}
							<Pagination.Item>
								<Pagination.Ellipsis />
							</Pagination.Item>
						{:else}
							<Pagination.Item>
								<Pagination.Link {page} isActive={currentPage === page.value} onclick={() => goToPage(page.value)}>
									{page.value}
								</Pagination.Link>
							</Pagination.Item>
						{/if}
					{/each}

					<Pagination.Item>
						<Pagination.NextButton class="w-auto px-2" onclick={() => goToPage(currentPage + 1)} disabled={isLastPage} />
					</Pagination.Item>
				</Pagination.Content>
			{/snippet}
		</Pagination.Root>

		<div class="flex items-center gap-2">
			<span class="text-xs text-muted-foreground">Per page:</span>
			<Select.Root type="single" value={selectedValue} onValueChange={handlePageSizeChange}>
				<Select.Trigger class="h-7 w-[70px] text-xs">
					{selectedValue}
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
