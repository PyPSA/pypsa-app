<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { networks } from '$lib/api/client.js';
	import { formatFileSize, formatDate, getDirectoryPath, getTagType, getTagColor } from '$lib/utils.js';
	import Pagination from '$lib/components/Pagination.svelte';
	import { CircleAlert } from 'lucide-svelte';
	import * as Alert from '$lib/components/ui/alert';
	import DataTable from './components/data-table.svelte';
	import { createColumns } from './components/columns.js';
	import { authStore } from '$lib/stores/auth.svelte.js';

	// Components
	import ActionsBar from './components/ActionsBar.svelte';
	import FilterBar from './components/FilterBar.svelte';
	import EmptyState from './components/EmptyState.svelte';
	import TableSkeleton from './components/TableSkeleton.svelte';

	// Data state
	let networksList = $state([]);
	let loading = $state(true);
	let error = $state(null);
	let scanning = $state(false);
	let totalNetworks = $state(0);
	let deletingId = $state(null);  // Track which network is being deleted
	let updatingVisibilityId = $state(null);  // Track which network visibility is being updated

	// Filter state (unified)
	let filters = $state({
		search: '',
		owners: new Set()  // empty = all, contains IDs = filter to those
	});

	// Pagination state
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Table state
	let sorting = $state([]);
	let columnVisibility = $state({});
	let expandedComponents = $state(new Set());

	// Available owners from API (all unique owners across all visible networks)
	let availableOwners = $state([]);

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
		const authEnabled = authStore.authEnabled;
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
			if (!isNaN(parsed) && [1, 10, 25, 50, 100].includes(parsed)) pageSize = parsed;
		}

		await loadNetworks();
	});

	async function loadNetworks() {
		loading = true;
		error = null;
		try {
			// Handle "none" filter - show empty results without API call
			if (filters.owners.has('__none__')) {
				networksList = [];
				totalNetworks = 0;
				loading = false;
				return;
			}

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
			if (err.cancelled) return;
			error = err.message;
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

	async function handleFilterChange(newFilters) {
		filters = newFilters;
		currentPage = 1;
		await updateURL();
		await loadNetworks();
	}

	function handleColumnVisibilityChange(visibility) {
		columnVisibility = visibility;
	}

	async function handlePageChange(page) {
		currentPage = page;
		await updateURL();
		await loadNetworks();
		if (browser) window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function handlePageSizeChange(size) {
		pageSize = size;
		currentPage = 1;
		if (browser) localStorage.setItem('networksPageSize', size.toString());
		await updateURL();
		await loadNetworks();
	}

	async function handleScan() {
		scanning = true;
		error = null;
		try {
			await networks.scan();
			await loadNetworks();
		} catch (err) {
			error = err.message;
		} finally {
			scanning = false;
		}
	}

	async function handleDelete(networkId) {
		if (deletingId) return;  // Prevent double-click
		if (!confirm('Are you sure you want to delete this network? This will remove both the database record and the file from disk. This action cannot be undone.')) {
			return;
		}
		deletingId = networkId;
		error = null;
		try {
			await networks.delete(networkId);
			await loadNetworks();
		} catch (err) {
			if (!err.cancelled) error = err.message;
		} finally {
			deletingId = null;
		}
	}

	async function handleVisibilityToggle(networkId, newVisibility) {
		if (updatingVisibilityId) return;  // Prevent double-click
		updatingVisibilityId = networkId;
		error = null;
		try {
			await networks.updateVisibility(networkId, newVisibility);
			await loadNetworks();
		} catch (err) {
			if (!err.cancelled) error = err.message;
		} finally {
			updatingVisibilityId = null;
		}
	}

	function viewNetwork(networkId) {
		goto(`/network?id=${networkId}`);
	}

	function toggleComponentsExpanded(networkId) {
		if (expandedComponents.has(networkId)) {
			expandedComponents.delete(networkId);
		} else {
			expandedComponents.add(networkId);
		}
		expandedComponents = expandedComponents;
	}

	function canEditVisibility(network) {
		if (!authStore.authEnabled || !authStore.user) return false;
		// Only owner can edit - admin powers are on /admin/networks
		return network.owner?.id === authStore.user.id;
	}

</script>

<div class="min-h-screen">
	<div style="max-width: 80rem; margin: 0 auto; padding-top: 2rem; padding-bottom: 2rem;">
		<!-- Actions Bar (Scan + Upload) -->
		<ActionsBar {scanning} onScan={handleScan} />

		<!-- Filter Bar (always visible) -->
		<FilterBar
			{filters}
			{availableOwners}
			{columns}
			{columnVisibility}
			onFilterChange={handleFilterChange}
			onColumnVisibilityChange={handleColumnVisibilityChange}
		/>

		<!-- Error Alert -->
		{#if error}
			<Alert.Root variant="destructive" class="mb-4">
				<CircleAlert class="size-4" />
				<Alert.Title>Error</Alert.Title>
				<Alert.Description>{error}</Alert.Description>
			</Alert.Root>
		{/if}

		<!-- Content based on view state -->
		{#if viewState === 'loading'}
			<TableSkeleton rows={pageSize > 10 ? 10 : pageSize} />
		{:else if viewState === 'empty'}
			<EmptyState type="empty" />
		{:else if viewState === 'no-matches'}
			<EmptyState type="no-matches" />
		{:else}
			<DataTable
				data={networksList}
				{columns}
				totalItems={totalNetworks}
				{pageSize}
				bind:sorting
				bind:columnVisibility
				globalFilter={filters.search}
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
