<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { getContext } from 'svelte';
	import { networks } from '$lib/api/client.js';
	import { clampPage, loadTablePrefs, saveTablePref } from '$lib/utils.js';
	import { buildColumns } from './columns.js';
	import type { ComponentDataResponse } from '$lib/types.js';
	import type { NetworkWithFacets } from '../../types.js';
	import type { SortingState, VisibilityState } from '@tanstack/table-core';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Input } from '$lib/components/ui/input';
	import { TableSkeleton } from '$lib/components/skeletons';
	import AlertCircle from '@lucide/svelte/icons/alert-circle';
	import Search from '@lucide/svelte/icons/search';
	import X from '@lucide/svelte/icons/x';

	const ctx = getContext<{ network: NetworkWithFacets | null; networkId: string }>('networkData');

	type RowData = Record<string, unknown>;

	let component = $derived($page.params.component!);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let response = $state<ComponentDataResponse | null>(null);

	let currentPage = $state(1);
	let pageSize = $state(25);
	let sorting = $state<SortingState>([]);
	let columnVisibility = $state<VisibilityState>({});
	let search = $state('');
	let searchDebounced = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | undefined;

	const storageKey = $derived(`data-${component}`);

	const columns = $derived.by(() => {
		if (!response) return [];
		return buildColumns(response.columns, response.dtypes);
	});

	const tableData = $derived.by((): RowData[] => {
		if (!response) return [];
		return response.data.map((row, i) => {
			const obj: RowData = { __index__: response!.index[i] };
			response!.columns.forEach((col, j) => {
				obj[col] = row[j];
			});
			return obj;
		});
	});

	const VALID_PAGE_SIZES = [10, 25, 50, 100];

	onMount(() => {
		const prefs = loadTablePrefs(storageKey);
		if (prefs.pageSize && VALID_PAGE_SIZES.includes(prefs.pageSize)) pageSize = prefs.pageSize;
		if (prefs.columnVisibility) columnVisibility = prefs.columnVisibility;

		const params = $page.url.searchParams;
		const urlPage = params.get('page');
		if (urlPage) {
			const parsed = parseInt(urlPage);
			if (!isNaN(parsed) && parsed > 0) currentPage = parsed;
		}
		const urlSize = params.get('size');
		if (urlSize) {
			const parsed = parseInt(urlSize);
			if (!isNaN(parsed) && VALID_PAGE_SIZES.includes(parsed)) pageSize = parsed;
		}
	});

	let prevFetchKey = '';
	$effect(() => {
		const sortBy = sorting[0]?.id ?? '';
		const sortDir = sorting[0]?.desc ? 'desc' : sorting[0] ? 'asc' : '';
		const key = `${ctx.networkId}-${component}-${currentPage}-${pageSize}-${sortBy}-${sortDir}-${searchDebounced}`;
		if (key !== prevFetchKey) {
			prevFetchKey = key;
			fetchData(sortBy, sortDir);
		}
	});

	async function fetchData(sortBy: string, sortDir: string) {
		loading = true;
		error = null;
		try {
			const offset = (currentPage - 1) * pageSize;
			response = await networks.getComponentData(ctx.networkId, component, {
				offset,
				limit: pageSize,
				sort_by: sortBy || undefined,
				sort_dir: sortDir || undefined,
				search: searchDebounced || undefined,
			});

			const clamped = clampPage(currentPage, pageSize, response.total);
			if (clamped !== null) {
				currentPage = clamped;
				await updateURL();
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load data';
		} finally {
			loading = false;
		}
	}

	async function updateURL() {
		if (!browser) return;
		const url = new URL(window.location.href);
		url.searchParams.set('page', currentPage.toString());
		url.searchParams.set('size', pageSize.toString());
		await goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
	}

	function handleSearchChange(value: string) {
		search = value;
		clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			searchDebounced = value;
			currentPage = 1;
			updateURL();
		}, 400);
	}

	async function handlePageChange(p: number) {
		currentPage = p;
		await updateURL();
		if (browser) window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function handlePageSizeChange(size: number) {
		pageSize = size;
		currentPage = 1;
		saveTablePref(storageKey, 'pageSize', size);
		await updateURL();
	}

	let visibilityHydrated = false;
	$effect(() => {
		const vis = columnVisibility;
		if (!visibilityHydrated) { visibilityHydrated = true; return; }
		saveTablePref(storageKey, 'columnVisibility', vis);
	});
</script>

{#if loading && !response}
	<TableSkeleton rows={pageSize > 10 ? 10 : pageSize} />
{:else if error}
	<div class="flex items-center justify-center py-12">
		<div class="text-center">
			<AlertCircle size={48} class="mx-auto mb-3 text-destructive" strokeWidth={1.5} />
			<p class="text-sm text-muted-foreground">{error}</p>
		</div>
	</div>
{:else if response}
	<div class="mb-4 flex items-center gap-2">
		<div class="relative w-64">
			<Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
			<Input
				type="text"
				placeholder="Search..."
				value={search}
				oninput={(e: Event) => handleSearchChange((e.target as HTMLInputElement).value)}
				class="h-8 pl-9 pr-8 text-sm"
			/>
			{#if search}
				<button
					type="button"
					class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-muted rounded"
					onclick={() => handleSearchChange('')}
				>
					<X class="h-3 w-3 text-muted-foreground" />
				</button>
			{/if}
		</div>
	</div>
	<DataTable
		data={tableData}
		columns={columns as any}
		bind:sorting
		bind:columnVisibility
		totalItems={response.total}
		bind:currentPage
		{pageSize}
		onPageChange={handlePageChange}
		onPageSizeChange={handlePageSizeChange}
	/>
{/if}
