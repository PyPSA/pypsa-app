<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import { saveTablePref, buildOwnerOptions, loadTablePrefs, clampPage } from '$lib/utils.js';
	import { RUN_FINAL_STATUSES } from '$lib/types.js';
	import type { RunSummary, User, BackendPublic, ApiError, Visibility } from '$lib/types.js';
	import type { FilterCategory } from '$lib/components/widgets/filter-dialog';
	import type { FilterAst } from '$lib/filters/ast';
	import { emptyAnd, isEmpty as astIsEmpty } from '$lib/filters/ast';
	import { parse as parseDsl, serialize as serializeDsl } from '$lib/filters/dsl';
	import type { SortingState, VisibilityState } from '@tanstack/table-core';
	import DataTable from '$lib/components/DataTable.svelte';
	import StatusBadge from './cells/StatusBadge.svelte';
	import * as Avatar from '$lib/components/ui/avatar';
	import Play from '@lucide/svelte/icons/play';
	import Plus from '@lucide/svelte/icons/plus';
	import Button from '$lib/components/ui/button/button.svelte';
	import { toast } from 'svelte-sonner';
	import { createColumns } from './components/columns.js';
	import CreateRunDialog from './components/CreateRunDialog.svelte';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { TableSkeleton } from '$lib/components/skeletons';

	// Data state
	let runsList = $state<RunSummary[]>([]);
	let loading = $state(true);
	let totalRuns = $state(0);
	let cancellingId = $state<string | null>(null);
	let removingId = $state<string | null>(null);
	let updatingVisibilityId = $state<string | null>(null);
	let createOpen = $state(false);

	// Filter categories use the singular field names that match the backend
	// AST/DSL (e.g. `status`, not `statuses`). The `?q=` URL param carries
	// the DSL string.
	let filter = $state<FilterAst>(emptyAnd());
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
	const defaultSorting: SortingState = [{ id: 'created_at', desc: true }];
	let sorting = $state<SortingState>([...defaultSorting]);
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
	const hasActiveFilters = $derived(!astIsEmpty(filter));
	const viewState = $derived.by(() => {
		if (loading) return 'loading';
		if (runsList.length === 0 && hasActiveFilters) return 'no-matches';
		if (runsList.length === 0) return 'empty';
		return 'data';
	});

	const ownerOptions = $derived(buildOwnerOptions(availableOwners, authStore.user?.username));

	const filterCategories = $derived<FilterCategory[]>([
		{ key: 'status', label: 'Status', hideChipPrefix: true, options: availableStatuses.map(s => ({ id: s, label: s })) },
		{ key: 'workflow', label: 'Workflow', description: 'Repository URL', options: availableWorkflows.map(w => ({ id: w, label: w })) },
		{ key: 'owner', label: 'Owner', description: 'Who created it', hideChipPrefix: true, options: ownerOptions, condition: authStore.authEnabled && !!authStore.user },
		{ key: 'git_ref', label: 'Branch', description: 'Git branch or tag', options: availableGitRefs.map(r => ({ id: r, label: r })) },
		{ key: 'configfile', label: 'Config', description: 'Config file path', options: availableConfigfiles.map(c => ({ id: c, label: c })) },
		{ key: 'backend', label: 'Backend', description: 'Execution backend', options: availableBackends.map(b => ({ id: b.name, label: b.name })) },
	]);

	function canEditRun(run: RunSummary): boolean {
		if (!authStore.user) return false;
		if (authStore.user.permissions?.includes('runs:manage_all')) return true;
		return run.owner?.id === authStore.user.id;
	}

	const columns = $derived.by(() => {
		const authEnabled = authStore.authEnabled ?? false;
		return createColumns({
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

	const VALID_PAGE_SIZES = [10, 25, 50, 100];

	function restoreFromUrl() {
		const params = $page.url.searchParams;

		const prefs = loadTablePrefs('runs');
		pageSize = (prefs.pageSize && VALID_PAGE_SIZES.includes(prefs.pageSize)) ? prefs.pageSize : 25;
		if (prefs.columnVisibility) columnVisibility = prefs.columnVisibility;

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
		await loadRuns();
	});

	async function loadRuns(silent = false) {
		if (!silent) loading = true;
		try {
			const skip = (currentPage - 1) * pageSize;
			// API sends JSON-encoded AST; the URL carries the DSL string.
			const filterQ = astIsEmpty(filter) ? undefined : JSON.stringify(filter);

			const sort_by = sorting[0]?.id;
			const sort_dir = sorting[0] ? (sorting[0].desc ? 'desc' : 'asc') : undefined;
			const response = await runs.list(skip, pageSize,
				{ sort_by, sort_dir, filter_q: filterQ }
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
		const url = new URL(window.location.href);
		url.searchParams.set('page', currentPage.toString());
		url.searchParams.set('size', pageSize.toString());
		const dsl = astIsEmpty(filter) ? '' : serializeDsl(filter);
		if (dsl) url.searchParams.set('q', dsl);
		else url.searchParams.delete('q');
		await goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
	}

	function handleSortingChange(newSorting: SortingState) {
		sorting = newSorting;
		currentPage = 1;
		loadRuns();
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

	async function handleFilterChange(ast: FilterAst) {
		filter = ast;
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
		<div class="flex justify-end mb-4">
			<Button size="sm" onclick={() => (createOpen = true)}>
				<Plus class="size-4" /> Create Run
			</Button>
		</div>
		<!-- Content based on view state -->
		{#if viewState === 'loading'}
			<TableSkeleton rows={pageSize > 10 ? 10 : pageSize} />
		{:else if viewState === 'empty'}
			<EmptyState icon={Play} title="No Runs" description="No workflow runs yet." />
		{:else}
			<DataTable
				data={runsList}
				columns={columns as any}
				totalItems={totalRuns}
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
				onRowClick={(run: RunSummary) => goto(`/runs/${run.id}`)}
			>
				{#snippet renderOption({ category, option })}
					{#if category.key === 'status'}
						<StatusBadge status={option.id} />
					{:else if category.key === 'owner'}
						<span class="inline-flex items-center gap-1.5">
							<Avatar.Root class="h-5 w-5">
								{#if option.avatarUrl}
									<Avatar.Image src={option.avatarUrl} alt={option.label} />
								{/if}
								<Avatar.Fallback class="text-[10px]">{option.label.slice(0, 2).toUpperCase()}</Avatar.Fallback>
							</Avatar.Root>
							<span class="truncate">{option.label}</span>
						</span>
					{:else}
						<span class="truncate">{option.label}</span>
					{/if}
				{/snippet}
			</DataTable>
		{/if}
	</div>
</div>

<CreateRunDialog bind:open={createOpen} onCreated={() => loadRuns()} />
