<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { networks } from '$lib/api/client.js';
	import { formatFileSize, formatDate, getDirectoryPath, getTagType, getTagColor } from '$lib/utils.js';
	import Pagination from '$lib/components/Pagination.svelte';
	import { Network, FolderOpen } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';
	import DataTable from '$lib/components/DataTable.svelte';
	import { createColumns } from './components/columns.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TableSkeleton from '$lib/components/TableSkeleton.svelte';
	import type { Network as NetworkType, User, ApiError } from '$lib/types.js';
	import type { ColumnDef, SortingState, VisibilityState, Row } from '@tanstack/table-core';

	// Components
	import ActionsBar from './components/ActionsBar.svelte';
	import FilterBar from './components/FilterBar.svelte';

	// Data state
	let networksList = $state<NetworkType[]>([]);
	let loading = $state(true);
	let totalNetworks = $state(0);
	let deletingId = $state<string | null>(null);  // Track which network is being deleted
	let updatingVisibilityId = $state<string | null>(null);  // Track which network visibility is being updated

	// Filter state (unified)
	let filters = $state<{ search: string; owners: Set<string> }>({
		search: '',
		owners: new Set()  // empty = all, contains IDs = filter to those
	});

	// Pagination state
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Table state
	let sorting = $state<SortingState>([]);
	let columnVisibility = $state<VisibilityState>({});
	let expandedComponents = $state<Set<string>>(new Set());

	// Available owners from API (all unique owners across all visible networks)
	let availableOwners = $state<User[]>([]);

	// Derived: view state for conditional rendering
	const viewState = $derived.by(() => {
		if (loading) return 'loading';
		// Empty when no filters and no networks
		if (networksList.length === 0 && filters.owners.size === 0) return 'empty';
		// No matches when filters active but no results
		if (networksList.length === 0) return 'no-matches';
		return 'data';
	});

	// Columns config - only recreate when authEnabled changes
	// Use getters for dynamic values to avoid recreating columns on every state change
	const columns = $derived.by(() => {
		// Only depend on authEnabled for conditional columns
		const authEnabled = authStore.authEnabled ?? false;
		return createColumns({
			getDirectoryPath,
			getTagType,
			getTagColor,
			formatFileSize,
			formatDate,
			handleDelete,
			toggleComponentsExpanded,
			getExpandedComponents: () => expandedComponents,
			handleVisibilityToggle,
			canEditVisibility,
			authEnabled,
			getDeletingId: () => deletingId,
			getUpdatingVisibilityId: () => updatingVisibilityId
		});
	});

	function networkFilterFn(row: Row<NetworkType>, columnId: string, filterValue: string) {
		const searchStr = filterValue.toLowerCase();
		const network = row.original;
		if (network.filename?.toLowerCase().includes(searchStr)) return true;
		if (network.name?.toLowerCase().includes(searchStr)) return true;
		if (network.file_path?.toLowerCase().includes(searchStr)) return true;
		if (network.tags && Array.isArray(network.tags)) {
			return network.tags.some((tag) => {
				if (typeof tag === 'string') return tag.toLowerCase().includes(searchStr);
				if (typeof tag === 'object' && tag.name) return tag.name.toLowerCase().includes(searchStr);
				return false;
			});
		}
		return false;
	}

	onMount(async () => {
		if (browser) {
			const savedPageSize = localStorage.getItem('networksPageSize');
			if (savedPageSize) pageSize = parseInt(savedPageSize);
		}

		const urlPage = $page.url.searchParams.get('page');
		const urlSize = $page.url.searchParams.get('size');

		if (urlPage) {
			const parsed = parseInt(urlPage);
			if (!isNaN(parsed) && parsed > 0) currentPage = parsed;
		}
		if (urlSize) {
			const parsed = parseInt(urlSize);
			if (!isNaN(parsed) && [10, 25, 50, 100].includes(parsed)) pageSize = parsed;
		}

		await loadNetworks();
	});

	async function loadNetworks() {
		loading = true;
		try {
			const skip = (currentPage - 1) * pageSize;

			// Convert owner Set to API format (use 'me' for current user's ID)
			const ownerIds = filters.owners.size > 0
				? Array.from(filters.owners).map(id => id === authStore.user?.id ? 'me' : id)
				: null;

			const response = await networks.list(skip, pageSize, ownerIds);

			networksList = response.data;
			totalNetworks = response.meta.total;
			if (response.meta.owners) {
				availableOwners = response.meta.owners;
			}

			const totalPages = Math.ceil(totalNetworks / pageSize);
			if (currentPage > totalPages && totalPages > 0) {
				currentPage = totalPages;
				await updateURL();
				return loadNetworks();
			}
		} catch (err) {
			if ((err as ApiError).cancelled) return;
			toast.error((err as Error).message);
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

	async function handleFilterChange(newFilters: { search: string; owners: Set<string> }) {
		filters = newFilters;
		currentPage = 1;
		await updateURL();
		await loadNetworks();
	}

	function handleColumnVisibilityChange(visibility: VisibilityState) {
		columnVisibility = visibility;
	}

	async function handlePageChange(page: number) {
		currentPage = page;
		await updateURL();
		await loadNetworks();
		if (browser) window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function handlePageSizeChange(size: number) {
		pageSize = size;
		currentPage = 1;
		if (browser) localStorage.setItem('networksPageSize', size.toString());
		await updateURL();
		await loadNetworks();
	}

	async function handleUpload() {
		await loadNetworks();
	}

	async function handleDelete(networkId: string) {
		if (deletingId) return;  // Prevent double-click
		if (!confirm('Are you sure you want to delete this network? This will remove both the database record and the file from disk. This action cannot be undone.')) {
			return;
		}
		deletingId = networkId;
		try {
			await networks.delete(networkId);
			await loadNetworks();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			deletingId = null;
		}
	}

	async function handleVisibilityToggle(networkId: string, newVisibility: "public" | "private") {
		if (updatingVisibilityId) return;  // Prevent double-click
		updatingVisibilityId = networkId;
		try {
			await networks.updateVisibility(networkId, newVisibility);
			await loadNetworks();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			updatingVisibilityId = null;
		}
	}

	function viewNetwork(networkId: string) {
		goto(`/network?id=${networkId}`);
	}

	function toggleComponentsExpanded(networkId: string) {
		if (expandedComponents.has(networkId)) {
			expandedComponents.delete(networkId);
		} else {
			expandedComponents.add(networkId);
		}
		expandedComponents = expandedComponents;
	}

	function canEditVisibility(network: NetworkType) {
		if (!authStore.authEnabled || !authStore.user) return false;
		// Only owner can edit - admin powers are on /admin/networks
		return network.owner.id === authStore.user.id;
	}

</script>

<div class="min-h-screen">
	<div class="max-w-[80rem] mx-auto py-8">
		<!-- Actions Bar (Scan + Upload) -->
		<ActionsBar onUpload={handleUpload} />

		<!-- Filter Bar (always visible) -->
		<FilterBar
			{filters}
			{availableOwners}
			{columns}
			{columnVisibility}
			onFilterChange={handleFilterChange}
			onColumnVisibilityChange={handleColumnVisibilityChange}
		/>

		<!-- Content based on view state -->
		{#if viewState === 'loading'}
			<TableSkeleton rows={pageSize > 10 ? 10 : pageSize} />
		{:else if viewState === 'empty'}
			<EmptyState icon={Network} title="No Networks" description="Get started by uploading a network file." />
		{:else if viewState === 'no-matches'}
			<EmptyState icon={FolderOpen} title="No Results" description="No networks match your current filters." />
		{:else}
			<DataTable
				data={networksList}
				columns={columns as any}
				totalItems={totalNetworks}
				{pageSize}
				bind:sorting
				bind:columnVisibility
				globalFilter={filters.search}
				globalFilterFn={networkFilterFn as any}
				onRowClick={(network) => viewNetwork(network.id)}
			/>

			<div class="mt-6">
				<Pagination
					{currentPage}
					{pageSize}
					totalItems={totalNetworks}
					onPageChange={handlePageChange}
					onPageSizeChange={handlePageSizeChange}
				/>
			</div>
		{/if}
	</div>
</div>
