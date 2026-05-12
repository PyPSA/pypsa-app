<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { networks, admin } from '$lib/api/client.js';
	import { formatFileSize, getTagType, getTagColor, saveTablePref, buildOwnerOptions, loadTablePrefs, clampPage } from '$lib/utils.js';
	import Network from '@lucide/svelte/icons/network';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Combobox } from '$lib/components/widgets/combobox';
	import { Label } from '$lib/components/ui/label';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import Button from '$lib/components/ui/button/button.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { createColumns } from './components/columns.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { TableSkeleton } from '$lib/components/skeletons';
	import type { Network as NetworkType, User, NetworkUpdate, ApiError, Visibility } from '$lib/types.js';
	import type { FilterCategory } from '$lib/components/widgets/filter-dialog';
	import type { FilterAst } from '$lib/filters/ast';
	import { emptyAnd, isEmpty as astIsEmpty } from '$lib/filters/ast';
	import { parse as parseDsl, serialize as serializeDsl } from '$lib/filters/dsl';
	import type { ColumnDef, SortingState, VisibilityState } from '@tanstack/table-core';

	// Components
	import ActionsBar from './components/ActionsBar.svelte';

	// Data state
	let networksList = $state<NetworkType[]>([]);
	let loading = $state(true);
	let totalNetworks = $state(0);
	let deletingId = $state<string | null>(null);
	let updatingVisibilityId = $state<string | null>(null);

	// Admin: owner reassignment dialog
	let editDialogOpen = $state(false);
	let editNetwork = $state<NetworkType | null>(null);
	let editOwner = $state<string | undefined>(undefined);
	let allUsers = $state<User[]>([]);
	let saving = $state(false);

	const userOptions = $derived(allUsers.map((u) => ({
		value: u.id,
		label: u.username,
		keywords: u.email ?? ''
	})));

	// Filter state. The category key is `owner` (singular) to match the backend
	// AST/DSL field name; the `?q=` URL param carries the DSL string.
	let filter = $state<FilterAst>(emptyAnd());

	// Pagination state
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Table state
	const defaultSorting: SortingState = [{ id: 'created_at', desc: true }];
	let sorting = $state<SortingState>([...defaultSorting]);
	let columnVisibility = $state<VisibilityState>({});

	// Available owners from API (all unique owners across all visible networks)
	let availableOwners = $state<User[]>([]);

	const hasActiveFilters = $derived(!astIsEmpty(filter));
	const viewState = $derived.by(() => {
		if (loading) return 'loading';
		if (networksList.length === 0 && hasActiveFilters) return 'no-matches';
		if (networksList.length === 0) return 'empty';
		return 'data';
	});

	const ownerOptions = $derived(buildOwnerOptions(availableOwners, authStore.user?.username));

	const filterCategories = $derived<FilterCategory[]>([
		{ key: 'owner', label: 'Owner', description: 'Who uploaded it', hideChipPrefix: true, options: ownerOptions, condition: authStore.authEnabled && !!authStore.user },
	]);

	// Columns config - only recreate when authEnabled changes
	// Use getters for dynamic values to avoid recreating columns on every state change
	const columns = $derived.by(() => {
		const authEnabled = authStore.authEnabled ?? false;
		const isAdmin = authStore.isAdmin ?? false;
		return createColumns({
			getTagType,
			getTagColor,
			formatFileSize,
			handleDelete,
			handleVisibilityToggle,
			canEditNetwork,
			authEnabled,
			handleOwnerChange: isAdmin ? openOwnerDialog : undefined,
			getDeletingId: () => deletingId,
			getUpdatingVisibilityId: () => updatingVisibilityId
		});
	});

	// Auto-show the path column when an external row exists; explicit user toggle wins.
	const hasExternal = $derived(networksList.some((n) => n.is_external));
	let userTouchedFilePath = $state(false);
	$effect(() => {
		if (userTouchedFilePath) return;
		const want = hasExternal;
		if (columnVisibility.file_path !== want) {
			columnVisibility = { ...columnVisibility, file_path: want };
		}
	});

	const VALID_PAGE_SIZES = [10, 25, 50, 100];

	function restoreFromUrl() {
		const params = $page.url.searchParams;

		const prefs = loadTablePrefs('networks');
		pageSize = (prefs.pageSize && VALID_PAGE_SIZES.includes(prefs.pageSize)) ? prefs.pageSize : 25;
		if (prefs.columnVisibility) {
			columnVisibility = prefs.columnVisibility;
			// User has a saved preference for the path column — don't auto-toggle it.
			if ('file_path' in prefs.columnVisibility) userTouchedFilePath = true;
		}

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

		const q = params.get('q');
		if (q) {
			const result = parseDsl(q);
			if (result.errors.length === 0) filter = result.ast;
		}
	}

	onMount(async () => {
		restoreFromUrl();
		await loadNetworks();
	});

	async function loadNetworks() {
		loading = true;
		try {
			const skip = (currentPage - 1) * pageSize;
			const filterQ = astIsEmpty(filter) ? undefined : JSON.stringify(filter);

			const sort_by = sorting[0]?.id;
			const sort_dir = sorting[0] ? (sorting[0].desc ? 'desc' : 'asc') : undefined;
			const response = await networks.list(skip, pageSize, {
				sort_by,
				sort_dir,
				filter_q: filterQ,
			});

			networksList = response.data;
			totalNetworks = response.meta.total;
			if (response.meta.owners) {
				availableOwners = response.meta.owners;
			}

			const clamped = clampPage(currentPage, pageSize, totalNetworks);
			if (clamped !== null) {
				currentPage = clamped;
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
		const dsl = astIsEmpty(filter) ? '' : serializeDsl(filter);
		if (dsl) url.searchParams.set('q', dsl);
		else url.searchParams.delete('q');
		await goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
	}

	async function handleFilterChange(ast: FilterAst) {
		filter = ast;
		currentPage = 1;
		await updateURL();
		await loadNetworks();
	}

	function handleSortingChange(newSorting: SortingState) {
		sorting = newSorting;
		currentPage = 1;
		loadNetworks();
	}

	function handleColumnVisibilityChange(visibility: VisibilityState) {
		if (visibility.file_path !== columnVisibility.file_path) {
			userTouchedFilePath = true;
		}
		columnVisibility = visibility;
		saveTablePref('networks', 'columnVisibility', visibility);
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
		saveTablePref('networks', 'pageSize', size);
		await updateURL();
		await loadNetworks();
	}

	async function handleUpload() {
		await loadNetworks();
	}

	// Delete confirmation dialog state. Replaces a bare `confirm()` so we can
	// surface the "also delete file from disk" checkbox for external networks.
	let deleteDialogOpen = $state(false);
	let deleteTarget = $state<NetworkType | null>(null);
	let deleteRemoveFile = $state(false);

	function handleDelete(networkId: string) {
		if (deletingId) return;
		const target = networksList.find((n) => n.id === networkId) ?? null;
		deleteTarget = target;
		deleteRemoveFile = false;
		deleteDialogOpen = true;
	}

	async function confirmDelete() {
		if (!deleteTarget || deletingId) return;
		const networkId = deleteTarget.id;
		const removeFile = !!deleteTarget.is_external && deleteRemoveFile;
		deleteDialogOpen = false;
		deletingId = networkId;
		try {
			if (authStore.isAdmin) {
				await admin.deleteNetwork(networkId, removeFile);
			} else {
				await networks.delete(networkId, removeFile);
			}
			await loadNetworks();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			deletingId = null;
			deleteTarget = null;
		}
	}

	async function handleVisibilityToggle(networkId: string, newVisibility: Visibility) {
		if (updatingVisibilityId) return;
		updatingVisibilityId = networkId;
		try {
			if (authStore.isAdmin) {
				await admin.updateNetwork(networkId, { visibility: newVisibility });
			} else {
				await networks.updateVisibility(networkId, newVisibility);
			}
			await loadNetworks();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			updatingVisibilityId = null;
		}
	}

	async function openOwnerDialog(network: NetworkType) {
		if (!authStore.isAdmin) return;
		editNetwork = network;
		editOwner = network.owner.id;
		editDialogOpen = true;
		if (allUsers.length === 0) {
			try {
				const response = await admin.listUsers(0, 1000);
				allUsers = response.data;
			} catch (err) {
				toast.error(`Failed to load users: ${(err as Error).message}`);
			}
		}
	}

	async function saveOwnerChange() {
		if (!editNetwork || saving) return;
		if (editOwner === editNetwork.owner.id) {
			editDialogOpen = false;
			return;
		}
		saving = true;
		try {
			await admin.updateNetwork(editNetwork.id, { user_id: editOwner });
			await loadNetworks();
			editDialogOpen = false;
		} catch (err) {
			toast.error(`Failed to update owner: ${(err as Error).message}`);
		} finally {
			saving = false;
		}
	}

	function viewNetwork(networkId: string) {
		goto(`/networks/${networkId}`);
	}

	function canEditNetwork(network: NetworkType) {
		// Auth disabled = single-user/local mode; backend bypasses ownership checks.
		if (authStore.authEnabled === false) return true;
		if (!authStore.user) return false;
		return authStore.isAdmin || network.owner.id === authStore.user.id;
	}

</script>

<div class="min-h-screen">
	<div class="max-w-[80rem] mx-auto py-8">
		<!-- Actions Bar (Scan + Upload) -->
		<ActionsBar onUpload={handleUpload} />

		<!-- Content based on view state -->
		{#if viewState === 'loading'}
			<TableSkeleton rows={pageSize > 10 ? 10 : pageSize} />
		{:else if viewState === 'empty'}
			<EmptyState icon={Network} title="No Networks" description="Get started by uploading a network file." />
		{:else}
			<DataTable
				data={networksList}
				columns={columns as any}
				totalItems={totalNetworks}
				{currentPage}
				{pageSize}
				bind:sorting
				{defaultSorting}
				bind:columnVisibility
				onSortingChange={handleSortingChange}
				{filterCategories}
				{filter}
				onFilterAstChange={handleFilterChange}
				onColumnVisibilityChange={handleColumnVisibilityChange}
				onPageChange={handlePageChange}
				onPageSizeChange={handlePageSizeChange}
				onRowClick={(network) => viewNetwork(network.id)}
			/>
		{/if}
	</div>
</div>

<!-- Delete confirmation dialog -->
<Dialog.Root bind:open={deleteDialogOpen}>
	<Dialog.Content class="max-w-sm">
		{#if deleteTarget}
			<Dialog.Header>
				<Dialog.Title>Delete network?</Dialog.Title>
				<Dialog.Description class="text-xs text-muted-foreground">
					{deleteTarget.filename}
				</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-3 py-4 text-sm">
				{#if deleteTarget.is_external}
					<p class="text-muted-foreground">
						This network was registered in place. By default the underlying file is kept on disk and only the database reference is removed.
					</p>
					<label class="flex items-start gap-2 cursor-pointer">
						<Checkbox bind:checked={deleteRemoveFile} class="mt-0.5" />
						<span>
							<span class="font-medium">Also delete the file from disk</span>
							{#if deleteTarget.file_path}
								<span class="block text-xs text-muted-foreground mt-0.5 font-mono break-all">
									{deleteTarget.file_path}
								</span>
							{/if}
						</span>
					</label>
				{:else}
					<p class="text-muted-foreground">
						This will remove both the database record and the file from disk. This action cannot be undone.
					</p>
				{/if}
			</div>
			<Dialog.Footer class="flex gap-2">
				<Button variant="outline" size="sm" onclick={() => (deleteDialogOpen = false)}>
					Cancel
				</Button>
				<Button variant="destructive" size="sm" onclick={confirmDelete}>
					Delete
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>

<!-- Admin: Change Owner Dialog -->
<Dialog.Root bind:open={editDialogOpen}>
	<Dialog.Content class="max-w-xs">
		{#if editNetwork}
			<Dialog.Header>
				<Dialog.Title>Change Owner</Dialog.Title>
				<Dialog.Description class="text-xs text-muted-foreground">
					{editNetwork.filename}
				</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-4 py-4">
				<div class="space-y-2">
					<Label class="text-xs">Owner</Label>
					<Combobox
						options={userOptions}
						value={editOwner}
						onSelect={(v) => { editOwner = v; }}
						searchPlaceholder="Search users..."
						emptyText="No users found."
						width="w-full"
					>
						{#snippet trigger({ props })}
							{@const ownerUser = allUsers.find((u) => u.id === editOwner)}
							<button
								{...props}
								type="button"
								class="flex w-full items-center justify-between rounded-md border bg-background px-3 py-2 text-sm"
							>
								<span class={ownerUser ? '' : 'text-muted-foreground'}>
									{ownerUser?.username || 'Select owner...'}
								</span>
							</button>
						{/snippet}
					</Combobox>
				</div>
			</div>
			<Dialog.Footer class="flex gap-2">
				<Button variant="outline" size="sm" onclick={() => (editDialogOpen = false)} disabled={saving}>
					Cancel
				</Button>
				<Button size="sm" onclick={saveOwnerChange} disabled={saving}>
					{#if saving}
						<Loader2 class="mr-1 size-4 animate-spin" />
					{/if}
					Save
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
