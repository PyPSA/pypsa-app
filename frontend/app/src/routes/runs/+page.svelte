<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import { formatRelativeTime, saveTablePref, buildOwnerOptions } from '$lib/utils.js';
	import { restoreTableState, buildTableURL, filtersToAPI, clampPage } from '$lib/table-url-state.js';
	import { RUN_FINAL_STATUSES } from '$lib/types.js';
	import type { RunSummary, User, BackendPublic, ApiError, Visibility } from '$lib/types.js';
	import type { FilterState, FilterCategory } from '$lib/components/ui/filter-dialog';
	import type { SortingState, VisibilityState } from '@tanstack/table-core';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import StatusBadge from './cells/StatusBadge.svelte';
	import { Play } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';
	import CreateRunDialog from './components/CreateRunDialog.svelte';
	import PaginatedTable from '$lib/components/PaginatedTable.svelte';
	import { createColumns } from './components/columns.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TableSkeleton from '$lib/components/TableSkeleton.svelte';

	// Data state
	let runsList = $state<RunSummary[]>([]);
	let loading = $state(true);
	let totalRuns = $state(0);
	let cancellingId = $state<string | null>(null);
	let removingId = $state<string | null>(null);
	let updatingVisibilityId = $state<string | null>(null);

	const FILTER_KEYS = ['statuses', 'workflows', 'owners', 'git_refs', 'configfiles', 'backends'] as const;
	let filters = $state({ statuses: new Set<string>(), workflows: new Set<string>(), owners: new Set<string>(), git_refs: new Set<string>(), configfiles: new Set<string>(), backends: new Set<string>() });
	let availableStatuses = $state<string[]>([]);
	let availableWorkflows = $state<string[]>([]);
	let availableOwners = $state<User[]>([]);
	let availableGitRefs = $state<string[]>([]);
	let availableConfigfiles = $state<string[]>([]);
	let availableBackends = $state<BackendPublic[]>([]);

	// Pagination state
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Table state
	let sorting = $state<SortingState>([]);
	const defaultColumnVisibility: VisibilityState = { jobs: false, backend: false };
	let columnVisibility = $state<VisibilityState>({ ...defaultColumnVisibility });

	function handleColumnVisibilityChange(v: VisibilityState) {
		columnVisibility = v;
		saveTablePref('runs', 'columnVisibility', v);
	}

	// Live duration ticker + polling for fresh data while runs are active
	let tick = $state(0);
	let tickInterval: ReturnType<typeof setInterval> | null = null;
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	const hasActiveRuns = $derived(runsList.some(r => !RUN_FINAL_STATUSES.has(r.status)));
	$effect(() => {
		if (hasActiveRuns) {
			if (!tickInterval) tickInterval = setInterval(() => tick++, 1000);
			if (!pollInterval) pollInterval = setInterval(() => loadRuns(true), 5000);
		} else {
			if (tickInterval) { clearInterval(tickInterval); tickInterval = null; }
			if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
		}
	});
	onDestroy(() => {
		if (tickInterval) clearInterval(tickInterval);
		if (pollInterval) clearInterval(pollInterval);
	});

	// View state for conditional rendering
	const hasActiveFilters = $derived(
		Object.values(filters).some(s => s.size > 0)
	);
	const viewState = $derived.by(() => {
		if (loading) return 'loading';
		if (runsList.length === 0 && hasActiveFilters) return 'no-matches';
		if (runsList.length === 0) return 'empty';
		return 'data';
	});

	const ownerOptions = $derived(buildOwnerOptions(availableOwners, authStore.user?.id));

	const filterCategories = $derived<FilterCategory[]>([
		{ key: 'statuses', label: 'Status', options: availableStatuses.map(s => ({ id: s, label: s })) },
		{ key: 'workflows', label: 'Workflow', options: availableWorkflows.map(w => ({ id: w, label: w })) },
		{ key: 'owners', label: 'Owner', options: ownerOptions, condition: authStore.authEnabled && !!authStore.user },
		{ key: 'git_refs', label: 'Branch', options: availableGitRefs.map(r => ({ id: r, label: r })) },
		{ key: 'configfiles', label: 'Config', options: availableConfigfiles.map(c => ({ id: c, label: c })) },
		{ key: 'backends', label: 'Backend', options: availableBackends.map(b => ({ id: b.id, label: b.name })) },
	]);

	function canEditRun(run: RunSummary): boolean {
		if (!authStore.user) return false;
		if (authStore.user.permissions?.includes('runs:manage_all')) return true;
		return run.owner?.id === authStore.user.id;
	}

	const columns = $derived.by(() => {
		const authEnabled = authStore.authEnabled ?? false;
		return createColumns({
			formatRelativeTime,
			handleCancel,
			handleRemove,
			handleRerun,
			handleVisibilityToggle,
			canEditRun,
			authEnabled,
			getCancellingId: () => cancellingId,
			getRemovingId: () => removingId,
			getUpdatingVisibilityId: () => updatingVisibilityId,
			getTick: () => tick
		});
	});

	onMount(async () => {
		const state = restoreTableState($page.url.searchParams, 'runs', FILTER_KEYS);
		currentPage = state.page;
		pageSize = state.pageSize;
		if (state.columnVisibility) columnVisibility = state.columnVisibility;
		for (const key of FILTER_KEYS) {
			filters[key] = state.filters[key] ?? new Set();
		}

		await loadRuns();
	});

	async function loadRuns(silent = false) {
		if (!silent) loading = true;
		try {
			const skip = (currentPage - 1) * pageSize;
			const apiFilters = filtersToAPI<{ statuses: string[]; workflows: string[]; owners: string[]; git_refs: string[]; configfiles: string[]; backends: string[] }>(filters, FILTER_KEYS);

			const response = await runs.list(skip, pageSize,
				Object.keys(apiFilters).length > 0 ? apiFilters : undefined
			);

			runsList = response.data;
			totalRuns = response.meta.total;
			if (response.meta.statuses) availableStatuses = response.meta.statuses;
			if (response.meta.workflows) availableWorkflows = response.meta.workflows;
			if (response.meta.owners) availableOwners = response.meta.owners;
			if (response.meta.git_refs) availableGitRefs = response.meta.git_refs;
			if (response.meta.configfiles) availableConfigfiles = response.meta.configfiles;
			if (response.meta.backends) availableBackends = response.meta.backends;

			const clamped = clampPage(currentPage, pageSize, totalRuns);
			if (clamped !== null) {
				currentPage = clamped;
				await updateURL();
				return loadRuns(silent);
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
		const url = buildTableURL(new URL(window.location.href), currentPage, pageSize, filters, FILTER_KEYS);
		await goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
	}

	async function handlePageChange(page: number) {
		currentPage = page;
		await updateURL();
		await loadRuns();
		if (browser) window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function handlePageSizeChange(size: number) {
		pageSize = size;
		currentPage = 1;
		saveTablePref('runs', 'pageSize', size);
		await updateURL();
		await loadRuns();
	}

	async function handleFilterChange(newFilters: FilterState) {
		for (const key of FILTER_KEYS) {
			filters[key] = newFilters[key] ?? new Set();
		}
		currentPage = 1;
		await updateURL();
		await loadRuns();
	}

	async function handleCancel(runId: string) {
		if (cancellingId) return;
		if (!confirm('Are you sure you want to cancel this run?')) {
			return;
		}
		cancellingId = runId;
		try {
			await runs.cancel(runId);
			await loadRuns();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			cancellingId = null;
		}
	}

	async function handleRerun(run: RunSummary) {
		try {
			const fullRun = await runs.get(run.id);
			const newRun = await runs.rerun(fullRun);
			goto(`/runs/${newRun.id}`);
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		}
	}

	async function handleVisibilityToggle(runId: string, visibility: Visibility) {
		if (updatingVisibilityId) return;
		updatingVisibilityId = runId;
		try {
			await runs.updateVisibility(runId, visibility);
			await loadRuns(true);
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			updatingVisibilityId = null;
		}
	}

	async function handleRemove(runId: string) {
		if (removingId) return;
		if (!confirm('Are you sure you want to remove this run? This will delete all associated files and cannot be undone.')) {
			return;
		}
		removingId = runId;
		try {
			await runs.remove(runId);
			await loadRuns();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			removingId = null;
		}
	}
</script>

<div class="min-h-screen">
	<div class="max-w-[80rem] mx-auto py-8">
		<!-- Header with New Run button -->
		<div class="flex items-center justify-between mb-4">
			<div></div>
			<CreateRunDialog />
		</div>

		<!-- Filter bar always visible (except during initial load) -->
		{#if viewState !== 'loading' && viewState !== 'empty'}
			<FilterBar
				{filterCategories}
				{filters}
				{columns}
				{columnVisibility}
				onFilterChange={handleFilterChange}
				onColumnVisibilityChange={handleColumnVisibilityChange}
			>
				{#snippet renderOption({ category, option })}
					{#if category.key === 'statuses'}
						<StatusBadge status={option.id} />
					{:else}
						<span class="truncate">{option.label}</span>
					{/if}
				{/snippet}
			</FilterBar>
		{/if}

		<!-- Content based on view state -->
		{#if viewState === 'loading'}
			<TableSkeleton rows={pageSize > 10 ? 10 : pageSize} />
		{:else if viewState === 'empty'}
			<EmptyState icon={Play} title="No Runs" description="No workflow runs yet." />
		{:else if viewState === 'no-matches'}
			<EmptyState icon={Play} title="No Matching Runs" description="No runs match the current filters." />
		{:else}
			<PaginatedTable
				mode="server"
				data={runsList}
				columns={columns as any}
				totalItems={totalRuns}
				{currentPage}
				{pageSize}
				bind:sorting
				bind:columnVisibility
				onPageChange={handlePageChange}
				onPageSizeChange={handlePageSizeChange}
				onRowClick={(run: RunSummary) => goto(`/runs/${run.id}`)}
			/>
		{/if}
	</div>
</div>
