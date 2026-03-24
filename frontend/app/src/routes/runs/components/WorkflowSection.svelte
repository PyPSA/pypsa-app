<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { runs } from '$lib/api/client.js';
	import type { Workflow, WorkflowRule, ApiError } from '$lib/types.js';
	import { getJobLogPath } from '$lib/utils.js';
	import RulePanel from './RulePanel.svelte';
	import { ChevronRight, GitBranch, Layers, Network, Terminal } from 'lucide-svelte';
	import * as Table from '$lib/components/ui/table';

	let { runId, isTerminal, isFailedRun = false }: { runId: string; isTerminal: boolean; isFailedRun?: boolean } = $props();

	let workflow = $state<Workflow | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let expandedRuleName = $state<string | null>(null);
	let sectionOpen = $state(true);

	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let tickTimer: ReturnType<typeof setInterval> | null = null;
	let tick = $state(0);

	const progressPct = $derived(
		workflow && workflow.total_job_count > 0
			? Math.round((workflow.jobs_finished / workflow.total_job_count) * 100)
			: 0
	);

	function ruleStatus(rule: WorkflowRule): 'done' | 'running' | 'pending' | 'failed' {
		if (rule.jobs?.some(j => j.status === 'ERROR')) return 'failed';
		if (rule.total_job_count === 0) return 'pending';
		if (rule.jobs_finished >= rule.total_job_count) return 'done';
		if (isTerminal) {
			if (rule.jobs_finished > 0) return 'done';
			return isFailedRun ? 'failed' : 'pending';
		}
		if (rule.jobs_finished > 0) return 'running';
		if (rule.jobs?.some(j => j.started_at)) return 'running';
		return 'pending';
	}

	function ruleHasJobs(rule: WorkflowRule): boolean {
		return (rule.jobs?.length ?? 0) > 0;
	}

	function getRuleLogPath(rule: WorkflowRule): string | null {
		for (const job of rule.jobs ?? []) {
			const logPath = getJobLogPath(job);
			if (logPath) return logPath;
		}
		return null;
	}

	function ruleDuration(rule: WorkflowRule): number {
		let total = 0;
		let count = 0;
		for (const job of rule.jobs ?? []) {
			if (!job.started_at) continue;
			const start = new Date(job.started_at).getTime();
			const end = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
			total += Math.max(0, end - start) / 1000;
			count++;
		}
		return count > 1 ? total / count : total;
	}

	function formatDuration(secs: number): string {
		if (secs < 60) return `${Math.round(secs)}s`;
		const m = Math.floor(secs / 60);
		const s = Math.round(secs % 60);
		if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
		const h = Math.floor(m / 60);
		const rm = m % 60;
		return rm > 0 ? `${h}h ${rm}m` : `${h}h`;
	}

	const maxDuration = $derived.by(() => {
		void tick;
		if (!workflow) return 0;
		let max = 0;
		for (const rule of workflow.rules) {
			max = Math.max(max, ruleDuration(rule));
		}
		return max;
	});

	const anyWildcards = $derived(workflow ? workflow.rules.some(r => r.total_job_count > 1) : false);
	const anyLogs = $derived(workflow ? workflow.rules.some(r => !!getRuleLogPath(r)) : false);

	const sortedRules = $derived.by(() => {
		if (!workflow) return [];
		const rg = workflow.rulegraph;
		if (!rg) return workflow.rules;

		// Build adjacency: source → targets (source must come before targets)
		const successors = new Map<string, string[]>();
		const inDegree = new Map<string, number>();
		for (const n of rg.nodes) {
			successors.set(n.rule, []);
			inDegree.set(n.rule, 0);
		}
		for (const l of rg.links) {
			successors.get(l.sourcerule)?.push(l.targetrule);
			inDegree.set(l.targetrule, (inDegree.get(l.targetrule) ?? 0) + 1);
		}

		// Kahn's algorithm — stable topological sort
		const queue = [...inDegree.entries()].filter(([, d]) => d === 0).map(([n]) => n);
		const order: string[] = [];
		while (queue.length > 0) {
			const node = queue.shift()!;
			order.push(node);
			for (const succ of successors.get(node) ?? []) {
				const d = (inDegree.get(succ) ?? 1) - 1;
				inDegree.set(succ, d);
				if (d === 0) queue.push(succ);
			}
		}

		const rank = new Map(order.map((name, i) => [name, i]));
		return [...workflow.rules].sort(
			(a, b) => (rank.get(a.name) ?? Infinity) - (rank.get(b.name) ?? Infinity)
		);
	});

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

	onMount(() => {
		fetchWorkflow();
		pollTimer = setInterval(() => {
			if (!isTerminal) fetchWorkflow();
		}, 3000);
		tickTimer = setInterval(() => tick++, 1000);
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
		if (tickTimer) clearInterval(tickTimer);
	});

	$effect(() => {
		if (isTerminal) {
			if (pollTimer) {
				fetchWorkflow();
				clearInterval(pollTimer);
				pollTimer = null;
			}
			if (tickTimer) {
				clearInterval(tickTimer);
				tickTimer = null;
			}
		}
	});
</script>

{#if workflow && (workflow.total_job_count > 0 || workflow.errors.length > 0)}
<div class="bg-card rounded-lg border border-border overflow-hidden mb-4">
	<button
		class="flex items-center gap-2 px-4 py-3 w-full text-left hover:bg-accent/50 transition-colors"
		onclick={() => (sectionOpen = !sectionOpen)}
	>
		<GitBranch class="h-4 w-4 text-muted-foreground" />
		<span class="text-sm font-medium">Workflow</span>
		<span class="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full">
			{workflow.jobs_finished}/{workflow.total_job_count}
		</span>
		{#if workflow.rulegraph}
			<a
				href="/runs/{runId}/dag"
				class="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:underline transition-colors"
				onclick={(e) => e.stopPropagation()}
			>
				<Network class="h-3.5 w-3.5" />
				View DAG
			</a>
		{/if}
		<ChevronRight
			class="h-4 w-4 text-muted-foreground {workflow.rulegraph ? '' : 'ml-auto'} transition-transform duration-200"
			style={sectionOpen ? 'transform: rotate(90deg)' : ''}
		/>
	</button>

	{#if sectionOpen}
		<div class="border-t border-border p-4 space-y-3">
			<!-- Rules table -->
			{#if workflow.rules.length > 0}
				<Table.Root class="text-xs">
					<Table.Header>
						<Table.Row class="hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent">
							<Table.Head class="h-7 pr-3 w-0">Rule</Table.Head>
							{#if anyWildcards}
								<Table.Head class="h-7 w-4 p-0"></Table.Head>
							{/if}
							{#if anyLogs}
								<Table.Head class="h-7 w-4 p-0"></Table.Head>
							{/if}
							<Table.Head class="h-7 pr-3 text-right">Duration</Table.Head>
							<Table.Head class="h-7 w-4 p-0"></Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each sortedRules as rule}
							{@const status = ruleStatus(rule)}
							{@const hasJobs = ruleHasJobs(rule)}
							{@const duration = ruleDuration(rule)}
							{@const ruleLogPath = getRuleLogPath(rule)}
							{@const hasNonEmptyLog = !!ruleLogPath}
							<Table.Row
								class="{hasJobs ? 'cursor-pointer' : 'hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent'} {hasJobs && expandedRuleName === rule.name ? 'border-0' : ''}"
								onclick={() => { if (hasJobs) expandedRuleName = expandedRuleName === rule.name ? null : rule.name; }}
							>
								<Table.Cell class="py-1.5 pr-3 font-mono w-0">
									<div class="flex items-center gap-2">
										<span class="inline-block h-1.5 w-1.5 rounded-full shrink-0
											{status === 'done' ? 'bg-primary' : status === 'failed' ? 'bg-red-500' : status === 'running' ? 'bg-yellow-500' : 'bg-muted-foreground/30'}
										"></span>
										{rule.name}
									</div>
								</Table.Cell>
								{#if anyWildcards}
									<Table.Cell class="py-1.5 w-4 text-center">
										{#if rule.total_job_count > 1}
											<span class="text-muted-foreground text-xs inline-flex items-center gap-0.5">
												<Layers class="h-3 w-3" />
												{rule.jobs_finished < rule.total_job_count
													? `${rule.jobs_finished}/${rule.total_job_count}`
													: `×${rule.total_job_count}`}
											</span>
										{/if}
									</Table.Cell>
								{/if}
								{#if anyLogs}
									<Table.Cell class="py-1.5 w-4 text-center">
										{#if hasNonEmptyLog}
											<span class="text-muted-foreground"><Terminal class="h-3 w-3 inline-block" /></span>
										{/if}
									</Table.Cell>
								{/if}
								<Table.Cell class="py-1.5 pr-3">
									{#if duration > 0}
										<div class="flex items-center gap-2">
											<div class="flex-1 h-1.5 rounded-full overflow-hidden">
												<div
													class="h-full rounded-full {status === 'failed' ? 'bg-red-500' : status === 'running' ? 'bg-yellow-500' : 'bg-primary'}"
													style="width: {maxDuration > 0 ? (duration / maxDuration) * 100 : 0}%"
												></div>
											</div>
											<span class="tabular-nums text-muted-foreground whitespace-nowrap">{rule.total_job_count > 1 ? 'ø ' : ''}{formatDuration(duration)}</span>
										</div>
									{:else}
										<span class="text-muted-foreground text-right block">&mdash;</span>
									{/if}
								</Table.Cell>
								<Table.Cell class="py-1.5 pl-2 w-4">
									{#if hasJobs}
										<ChevronRight
											class="h-3 w-3 text-muted-foreground transition-transform duration-200"
											style={expandedRuleName === rule.name ? 'transform: rotate(90deg)' : ''}
										/>
									{/if}
								</Table.Cell>
							</Table.Row>
							{#if hasJobs && expandedRuleName === rule.name}
								<Table.Row class="hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent">
									<!-- colspan: Rule + Duration + Chevron = 3, plus optional wildcards + logs columns -->
									<Table.Cell colspan={3 + (anyWildcards ? 1 : 0) + (anyLogs ? 1 : 0)} class="pt-1 pb-2 pl-6 pr-2">
										<RulePanel {rule} {runId} />
									</Table.Cell>
								</Table.Row>
							{/if}
						{/each}
					</Table.Body>
				</Table.Root>
			{/if}
		</div>
	{/if}
</div>
{/if}
