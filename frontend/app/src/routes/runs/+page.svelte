<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import { formatRelativeTime } from '$lib/utils.js';
	import { RUN_FINAL_STATUSES } from '$lib/types.js';
	import type { Run, ApiError } from '$lib/types.js';
	import type { SortingState } from '@tanstack/table-core';
	import Pagination from '$lib/components/Pagination.svelte';
	import { Play } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';
	import DataTable from '$lib/components/DataTable.svelte';
	import { createColumns } from './components/columns.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TableSkeleton from '$lib/components/TableSkeleton.svelte';

	// Data state
	let runsList = $state<Run[]>([]);
	let loading = $state(true);
	let totalRuns = $state(0);
	let cancellingId = $state<string | null>(null);
	let removingId = $state<string | null>(null);

	// Pagination state
	let currentPage = $state(1);
	let pageSize = $state(25);

	// Table state
	let sorting = $state<SortingState>([]);

	// Live duration ticker 
	let tick = $state(0);
	let tickInterval: ReturnType<typeof setInterval> | null = null;
	const hasActiveRuns = $derived(runsList.some(r => !RUN_FINAL_STATUSES.has(r.status)));
	$effect(() => {
		if (hasActiveRuns && !tickInterval) {
			tickInterval = setInterval(() => tick++, 1000);
		} else if (!hasActiveRuns && tickInterval) {
			clearInterval(tickInterval);
			tickInterval = null;
		}
	});
	onDestroy(() => { if (tickInterval) clearInterval(tickInterval); });

	// View state for conditional rendering
	const viewState = $derived.by(() => {
		if (loading) return 'loading';
		if (runsList.length === 0) return 'empty';
		return 'data';
	});

	const columns = $derived.by(() => {
		const authEnabled = authStore.authEnabled ?? false;
		return createColumns({
			formatRelativeTime,
			handleCancel,
			handleRemove,
			handleRerun,
			authEnabled,
			getCancellingId: () => cancellingId,
			getRemovingId: () => removingId,
			getTick: () => tick
		});
	});

	onMount(async () => {
		if (browser) {
			const savedPageSize = localStorage.getItem('runsPageSize');
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

		await loadRuns();
	});

	async function loadRuns() {
		loading = true;
		try {
			const skip = (currentPage - 1) * pageSize;
			const response = await runs.list(skip, pageSize);

			runsList = response.data;
			totalRuns = response.meta.total;

			const totalPages = Math.ceil(totalRuns / pageSize);
			if (currentPage > totalPages && totalPages > 0) {
				currentPage = totalPages;
				await updateURL();
				return loadRuns();
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

	async function handlePageChange(page: number) {
		currentPage = page;
		await updateURL();
		await loadRuns();
		if (browser) window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function handlePageSizeChange(size: number) {
		pageSize = size;
		currentPage = 1;
		if (browser) localStorage.setItem('runsPageSize', size.toString());
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

	async function handleRerun(run: Run) {
		try {
			const newRun = await runs.rerun(run);
			goto(`/runs/${newRun.id}`);
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
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
				{pageSize}
				bind:sorting
				onRowClick={(run: Run) => goto(`/runs/${run.id}`)}
			/>

			<div class="mt-6">
				<Pagination
					{currentPage}
					{pageSize}
					totalItems={totalRuns}
					onPageChange={handlePageChange}
					onPageSizeChange={handlePageSizeChange}
				/>
			</div>
		{/if}
	</div>
</div>
