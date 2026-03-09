<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import type { Run, Workflow, ApiError } from '$lib/types.js';
	import { RUN_FINAL_STATUSES } from '$lib/types.js';
	import WorkflowDag from '../../components/WorkflowDag.svelte';
	import RulePanel from '../../components/RulePanel.svelte';
	import { Loader2 } from 'lucide-svelte';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { sidebarStore } from '$lib/stores/sidebar.svelte.js';

	const runId = $derived($page.params.id as string);

	let workflow = $state<Workflow | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let selectedRuleName = $state<string | null>(null);

	let run = $state<Run | null>(null);
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let isTerminal = $state(false);

	const selectedRule = $derived(
		workflow && selectedRuleName
			? workflow.rules.find(r => r.name === selectedRuleName) ?? null
			: null
	);

	async function fetchWorkflow() {
		try {
			workflow = await runs.workflow(runId);
			error = null;
		} catch (err) {
			if ((err as ApiError).cancelled) return;
			if ((err as ApiError).status === 404) {
				error = null;
				workflow = null;
			} else {
				error = (err as Error).message;
			}
		} finally {
			loading = false;
		}
	}

	const breadcrumbLabel = $derived.by(() => {
		if (!run) return runId.slice(0, 8);
		let source = run.workflow;
		if (source.startsWith('https://github.com/')) {
			source = source.replace('https://github.com/', '');
		}
		source = source.replace(/\.git$/, '');
		const repo = source.split('/').pop() || '';
		let label = repo;
		const ref = run.git_ref || run.git_sha?.slice(0, 8) || '';
		if (ref) label += `@${ref}`;
		return label || run.id.slice(0, 8);
	});

	async function checkRunStatus() {
		try {
			run = await runs.get(runId);
			if (RUN_FINAL_STATUSES.has(run.status)) {
				isTerminal = true;
				if (pollTimer) {
					clearInterval(pollTimer);
					pollTimer = null;
				}
			}
		} catch {
			// ignore
		}
	}

	let previousSidebarOpen = true;

	onMount(() => {
		previousSidebarOpen = sidebarStore.open;
		sidebarStore.open = false;
		fetchWorkflow();
		checkRunStatus();
		pollTimer = setInterval(() => {
			if (!isTerminal) {
				fetchWorkflow();
				checkRunStatus();
			}
		}, 3000);
	});

	$effect(() => {
		breadcrumbStore.set([
			{ label: breadcrumbLabel, href: `/runs/${runId}` },
			{ label: 'DAG' }
		]);
	});

	onDestroy(() => {
		sidebarStore.open = previousSidebarOpen;
		breadcrumbStore.clear();
		if (pollTimer) clearInterval(pollTimer);
	});
</script>

<div class="flex flex-col flex-1 -mx-4 -mb-4 overflow-hidden">
	<!-- Job count badge -->
	{#if workflow}
		<div class="px-4 py-2 text-xs text-muted-foreground shrink-0">
			{workflow.jobs_finished}/{workflow.total_job_count} jobs
		</div>
	{/if}

	<!-- Content -->
	<div class="flex-1 flex overflow-hidden">
		<!-- DAG area -->
		<div class="flex-1 overflow-auto p-4">
			{#if loading && !workflow}
				<div class="flex items-center justify-center h-full">
					<Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
				</div>
			{:else if error}
				<div class="flex items-center justify-center h-full text-sm text-destructive">
					{error}
				</div>
			{:else if workflow?.rulegraph}
				<WorkflowDag
					rulegraph={workflow.rulegraph}
					rules={workflow.rules}
					onSelectRule={(name) => { selectedRuleName = name; }}
				/>
			{:else}
				<div class="flex items-center justify-center h-full text-sm text-muted-foreground">
					No DAG available.
				</div>
			{/if}
		</div>

		<!-- Side panel for selected rule -->
		{#if selectedRule}
			<div class="w-96 border-l border-border overflow-y-auto p-4 bg-card shrink-0">
				<div class="flex items-center justify-between mb-3">
					<span class="text-sm font-medium">Rule Details</span>
					<button
						class="text-xs text-muted-foreground hover:text-foreground"
						onclick={() => selectedRuleName = null}
					>
						Close
					</button>
				</div>
				<RulePanel rule={selectedRule} />
			</div>
		{/if}
	</div>
</div>
