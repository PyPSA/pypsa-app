<script lang="ts">
	import { untrack } from 'svelte';
	import type { WorkflowRule } from '$lib/types.js';
	import { runs } from '$lib/api/client.js';
	import { getJobLogPath } from '$lib/utils.js';
	import * as Table from '$lib/components/ui/table';
	import { ChevronRight, Terminal, ExternalLink, RotateCw } from 'lucide-svelte';

	let { rule, runId }: { rule: WorkflowRule; runId: string } = $props();

	let expandedJobIndex = $state<number | null>(null);
	let logCache = $state<Record<number, string>>({});
	let logLoading = $state<Record<number, boolean>>({});
	let activeTabOverride = $state<'files' | 'logs' | null>(null);
	let activeJobTab = $state<Record<number, 'files' | 'logs'>>({});

	// Reset state when rule changes (e.g. clicking different rule in DAG).
	// Track by name to avoid resetting on every poll cycle (which recreates rule objects).
	// Writes are wrapped in untrack() so only rule.name is a dependency.
	let prevRuleName = $state<string | null>(null);
	$effect(() => {
		const name = rule.name;
		untrack(() => {
			if (name !== prevRuleName) {
				prevRuleName = name;
				logCache = {};
				logLoading = {};
				activeTabOverride = null;
				activeJobTab = {};
				expandedJobIndex = null;
			}
		});
	});

	// For single-job rules: default to 'files' if files exist, else 'logs'
	const activeTab = $derived.by(() => {
		if (activeTabOverride) return activeTabOverride;
		if (rule.jobs?.length !== 1) return 'files';
		const job = rule.jobs[0];
		const hasFiles = (job.files?.some(f => f.file_type === 'INPUT') ?? false) ||
			(job.files?.some(f => f.file_type === 'OUTPUT') ?? false);
		return hasFiles ? 'files' : 'logs';
	});

	// Auto-load log when single-job defaults to logs tab
	$effect(() => {
		if (activeTab === 'logs' && rule.jobs?.length === 1) {
			const logPath = getJobLogPath(rule.jobs[0]);
			if (logPath && logCache[0] === undefined && !logLoading[0]) loadLog(0, logPath);
		}
	});

	async function refreshLog(jobIndex: number, logPath: string) {
		delete logCache[jobIndex];
		logLoading[jobIndex] = false;
		await loadLog(jobIndex, logPath);
	}

	async function loadLog(jobIndex: number, logPath: string) {
		if (logCache[jobIndex] !== undefined || logLoading[jobIndex]) return;
		logLoading[jobIndex] = true;
		try {
			const url = `${runs.outputDownloadUrl(runId, logPath)}?format=text`;
			const resp = await fetch(url, { credentials: 'include' });
			logCache[jobIndex] = resp.ok ? await resp.text() : `Failed to fetch log (${resp.status})`;
		} catch {
			logCache[jobIndex] = 'Failed to fetch log';
		}
		logLoading[jobIndex] = false;
	}

	function formatWildcards(wildcards: Record<string, string> | null): string {
		if (!wildcards || Object.keys(wildcards).length === 0) return '—';
		return Object.entries(wildcards).map(([k, v]) => `${k}=${v}`).join(', ');
	}

	function statusDotColor(status: string): string {
		switch (status.toLowerCase()) {
			case 'success':
			case 'finished': return 'bg-primary';
			case 'running': return 'bg-yellow-500';
			case 'failed': return 'bg-red-500';
			default: return 'bg-muted-foreground/30';
		}
	}

	function jobDuration(job: { started_at?: string; completed_at?: string }): number {
		if (!job.started_at) return 0;
		const start = new Date(job.started_at).getTime();
		const end = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
		return Math.max(0, Math.round((end - start) / 1000));
	}

	function formatDuration(secs: number): string {
		if (secs < 60) return `${secs}s`;
		const mins = Math.floor(secs / 60);
		const remSecs = secs % 60;
		if (mins < 60) return `${mins}m ${remSecs}s`;
		const hrs = Math.floor(mins / 60);
		const remMins = mins % 60;
		return `${hrs}h ${remMins}m`;
	}

	const maxDuration = $derived.by(() => {
		let max = 0;
		for (const job of rule.jobs ?? []) {
			max = Math.max(max, jobDuration(job));
		}
		return max;
	});

	const anyJobLogs = $derived.by(() => {
		for (const job of rule.jobs ?? []) {
			if (getJobLogPath(job)) return true;
		}
		return false;
	});

	function shortPath(path: string): string {
		return path
			.replace(/^\/app\/\.snakedispatch\/jobs\/[^/]+\//, '')
			.replace(/\s*\(retrieve from storage\)$/, '');
	}

	function jobHasFiles(job: { files?: { file_type: string; path: string }[] }): boolean {
		return (job.files?.length ?? 0) > 0;
	}

	function jobIsExpandable(job: { files?: { file_type: string; path: string }[]; log?: string }): boolean {
		return jobHasFiles(job) || !!getJobLogPath(job);
	}
</script>

{#snippet jobDetail(jobIndex: number, inputs: {file_type: string; path: string}[], outputs: {file_type: string; path: string}[], logPath: string | null, currentTab: 'files' | 'logs', setTab: (tab: 'files' | 'logs') => void)}
	{@const hasFiles = inputs.length > 0 || outputs.length > 0}
	{@const hasLog = !!logPath}
	{#if hasFiles || hasLog}
		<div class="flex flex-col gap-1.5">
			<div class="flex items-center gap-3">
				{#if hasFiles}
					<button
						class="text-xs pb-0.5 border-b-2 transition-colors {currentTab === 'files' ? 'border-foreground text-foreground font-medium' : 'border-transparent text-muted-foreground hover:text-foreground'}"
						onclick={(e) => { e.stopPropagation(); setTab('files'); }}
					>Files</button>
				{/if}
				{#if hasLog}
					<button
						class="text-xs pb-0.5 border-b-2 transition-colors {currentTab === 'logs' ? 'border-foreground text-foreground font-medium' : 'border-transparent text-muted-foreground hover:text-foreground'}"
						onclick={(e) => { e.stopPropagation(); setTab('logs'); if (logPath) loadLog(jobIndex, logPath); }}
					>Logs</button>
				{/if}
				{#if currentTab === 'logs' && hasLog && logPath}
					<a
						href="{runs.outputDownloadUrl(runId, logPath)}?format=text"
						target="_blank"
						rel="noopener noreferrer"
						class="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:underline transition-colors"
						onclick={(e) => e.stopPropagation()}
					>
						<ExternalLink class="h-3.5 w-3.5" />
						Raw logs
					</a>
					<button
						class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
						onclick={(e) => { e.stopPropagation(); if (logPath) refreshLog(jobIndex, logPath); }}
						disabled={logLoading[jobIndex]}
						title="Refresh log"
					>
						<RotateCw class="h-3 w-3 {logLoading[jobIndex] ? 'animate-spin' : ''}" />
					</button>
				{/if}
			</div>
			{#if currentTab === 'files' && hasFiles}
				<div class="flex gap-6 text-[10px] text-muted-foreground">
					{#if inputs.length > 0}
						<div class="flex-1 min-w-0">
							<span class="font-medium">Inputs</span>
							<ul class="mt-0.5 space-y-px">
								{#each inputs as f}
									<li class="font-mono truncate" title={f.path}>{shortPath(f.path)}</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if outputs.length > 0}
						<div class="flex-1 min-w-0">
							<span class="font-medium">Outputs</span>
							<ul class="mt-0.5 space-y-px">
								{#each outputs as f}
									<li class="font-mono truncate" title={f.path}>{shortPath(f.path)}</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
			{:else if currentTab === 'logs' && hasLog && logPath}
				{#if logLoading[jobIndex]}
					<span class="text-xs text-muted-foreground">Loading…</span>
				{:else if logCache[jobIndex] !== undefined}
					<pre class="max-h-[300px] overflow-auto rounded bg-zinc-950 p-2 font-mono text-xs leading-5 text-zinc-200 whitespace-pre-wrap">{logCache[jobIndex]}</pre>
				{/if}
			{/if}
		</div>
	{/if}
{/snippet}

{#if rule.jobs?.length === 1}
	{@const job = rule.jobs[0]}
	{@const inputs = job.files?.filter(f => f.file_type === 'INPUT') ?? []}
	{@const outputs = job.files?.filter(f => f.file_type === 'OUTPUT') ?? []}
	{@const logPath = getJobLogPath(job)}
	{@render jobDetail(0, inputs, outputs, logPath, activeTab, (tab) => { activeTabOverride = tab; })}
{:else if rule.jobs?.length > 1}
	<Table.Root class="text-xs">
		<Table.Header>
			<Table.Row class="hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent">
				<Table.Head class="h-7 py-1 pr-3">Wildcards</Table.Head>
				{#if anyJobLogs}
					<Table.Head class="h-7 py-1 w-4 p-0"></Table.Head>
				{/if}
				<Table.Head class="h-7 py-1 pr-3 text-right">Duration</Table.Head>
				<Table.Head class="h-7 py-1 w-4 p-0"></Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each rule.jobs as job, i}
				{@const expandable = jobIsExpandable(job)}
				{@const duration = jobDuration(job)}
				{@const status = job.status.toLowerCase()}
				{@const inputs = job.files?.filter(f => f.file_type === 'INPUT') ?? []}
				{@const outputs = job.files?.filter(f => f.file_type === 'OUTPUT') ?? []}
				<Table.Row
					class="{expandable ? 'cursor-pointer' : 'hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent'} {expandable && expandedJobIndex === i ? 'border-0' : ''}"
					onclick={() => { if (expandable) expandedJobIndex = expandedJobIndex === i ? null : i; }}
				>
					<Table.Cell class="py-1 pr-3 font-mono w-0">
						<div class="flex items-center gap-2">
							<span class="inline-block h-1.5 w-1.5 rounded-full shrink-0 {statusDotColor(job.status)}"></span>
							<span class="truncate max-w-[20rem]">{formatWildcards(job.wildcards)}</span>
						</div>
					</Table.Cell>
					{#if anyJobLogs}
						<Table.Cell class="py-1 w-4 text-center">
							{#if getJobLogPath(job)}
								<Terminal class="h-3 w-3 text-muted-foreground inline-block" />
							{/if}
						</Table.Cell>
					{/if}
					<Table.Cell class="py-1 pr-3">
						{#if duration > 0}
							<div class="flex items-center gap-2">
								<div class="flex-1 h-1.5 rounded-full overflow-hidden">
									<div
										class="h-full rounded-full {status === 'running' ? 'bg-yellow-500' : 'bg-primary'}"
										style="width: {maxDuration > 0 ? (duration / maxDuration) * 100 : 0}%"
									></div>
								</div>
								<span class="tabular-nums text-muted-foreground whitespace-nowrap">{formatDuration(duration)}</span>
							</div>
						{:else}
							<span class="text-muted-foreground text-right block">&mdash;</span>
						{/if}
					</Table.Cell>
					<Table.Cell class="py-1 pl-2 w-4">
						{#if expandable}
							<ChevronRight
								class="h-3 w-3 text-muted-foreground transition-transform duration-200"
								style={expandedJobIndex === i ? 'transform: rotate(90deg)' : ''}
							/>
						{/if}
					</Table.Cell>
				</Table.Row>
				{#if expandable && expandedJobIndex === i}
					<Table.Row class="hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent">
						<!-- colspan: Wildcards + Duration + Chevron = 3, plus optional log column -->
						<Table.Cell colspan={3 + (anyJobLogs ? 1 : 0)} class="py-1 pl-2">
							{@const logPath = getJobLogPath(job)}
							{@const hasFiles = inputs.length > 0 || outputs.length > 0}
							{@const defaultJobTab = hasFiles ? 'files' : 'logs'}
							{@const currentTab = activeJobTab[i] ?? defaultJobTab}
							{@render jobDetail(i, inputs, outputs, logPath, currentTab, (tab) => { activeJobTab[i] = tab; })}
						</Table.Cell>
					</Table.Row>
				{/if}
			{/each}
		</Table.Body>
	</Table.Root>
{:else}
	<p class="text-xs text-muted-foreground">No jobs yet.</p>
{/if}
