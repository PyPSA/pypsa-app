<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import { formatRelativeTime, formatDuration, formatDate } from '$lib/utils.js';
	import { RUN_FINAL_STATUSES, RUN_SETTLED_STATUSES } from '$lib/types.js';
	import type { Run, ApiError, OutputFile, RunNetwork, Workflow } from '$lib/types.js';
	import { Button } from '$lib/components/ui/button';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import { Terminal, RotateCw, X, Trash2, Loader2, MoreVertical, Settings2, ChevronRight, ExternalLink, FolderArchive, GitBranch, Clock, Calendar, Server, Globe, LockKeyhole } from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import OutputFilesTree from '../components/OutputFilesTree.svelte';
	import WorkflowSection from '../components/WorkflowSection.svelte';
	import { toast } from 'svelte-sonner';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import StatusCell from '../cells/status-cell.svelte';

	const runId = $derived($page.params.id as string);

	let run = $state<Run | null>(null);
	let logs = $state<string[]>([]);
	let loading = $state(true);
	let streaming = $state(false);
	let streamDone = $state(false);

	let rerunning = $state(false);
	let cancelling = $state(false);
	let removing = $state(false);
	let togglingVisibility = $state(false);
	let configOpen = $state(false);
	let logsOpen = $state(true);

	let outputFiles = $state<OutputFile[] | null>(null);
	let outputsOpen = $state(false);
	let outputsLoading = $state(false);
	let outputsUnavailable = $state(false);
	let workflow = $state<Workflow | null>(null);

	let eventSource: EventSource | null = null;
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let tickInterval: ReturnType<typeof setInterval> | null = null;
	let logContainer: HTMLDivElement = $state(undefined as unknown as HTMLDivElement);

	// Live duration ticker
	let tick = $state(0);

	const isTerminal = $derived(
		run && RUN_FINAL_STATUSES.has(run.status)
	);

	$effect(() => {
		if (!isTerminal && !tickInterval) {
			tickInterval = setInterval(() => tick++, 1000);
		} else if (isTerminal && tickInterval) {
			clearInterval(tickInterval);
			tickInterval = null;
		}
	});
	const isSettled = $derived(
		run !== null && RUN_SETTLED_STATUSES.has(run.status)
	);

	let outputsFetched = $state(false);

	$effect(() => {
		if (isTerminal && !outputsFetched) {
			outputsFetched = true;
			outputsLoading = true;
			runs.listOutputs(runId).then((files) => {
				outputFiles = files;
			}).catch((err: unknown) => {
				if (!(err as ApiError).cancelled) {
					outputsUnavailable = true;
				}
			}).finally(() => {
				outputsLoading = false;
			});
			fetch(`/api/v1/runs/${runId}/workflow`, { credentials: 'include' })
				.then((r) => r.ok ? r.json() as Promise<Workflow> : null)
				.then((w) => { workflow = w; })
				.catch(() => {
					// Workflow data is optional for file badges
				});
		}
	});
	// Poll workflow data for running runs (progress bar)
	$effect(() => {
		if (run && !isTerminal && run.status !== 'PENDING') {
			const fetchWorkflow = () => {
				fetch(`/api/v1/runs/${runId}/workflow`, { credentials: 'include' })
					.then((r) => r.ok ? r.json() as Promise<Workflow> : null)
					.then((w) => { if (w) workflow = w; })
					.catch(() => {});
			};
			fetchWorkflow();
			const interval = setInterval(fetchWorkflow, 5000);
			return () => clearInterval(interval);
		}
	});

	const actionBusy = $derived(cancelling || rerunning || removing || togglingVisibility);

	const duration = $derived.by(() => {
		if (!isTerminal) tick; // reference tick to force re-evaluation
		return formatDuration(run?.started_at, run?.completed_at);
	});

	const createdDisplay = $derived.by(() => {
		if (!isTerminal) tick; // force re-evaluation for active runs
		return formatRelativeTime(run?.created_at);
	});

	const workflowDisplay = $derived.by(() => {
		if (!run) return null;
		let source = run.workflow;
		if (source.startsWith('https://github.com/')) {
			source = source.replace('https://github.com/', '');
		}
		source = source.replace(/\.git$/, '');
		return source;
	});

	const configDisplay = $derived(
		run?.configfile?.split('/').pop() ?? null
	);

	$effect(() => {
		// React to runId changes (e.g. rerun navigating to new run)
		void runId;
		// Reset state
		run = null;
		logs = [];
		loading = true;
		streaming = false;
		streamDone = false;
		outputFiles = null;
		outputsOpen = false;
		outputsLoading = false;
		outputsUnavailable = false;
		outputsFetched = false;
		workflow = null;
		configOpen = false;
		logsOpen = true;
		stopLogStream();
		if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
		// Load new run
		loadRun().then(() => startLogStream());
	});

	const breadcrumbLabel = $derived.by(() => {
		if (!run) return '...';
		if (configDisplay) return configDisplay;
		const repo = workflowDisplay?.split('/').pop() || '';
		let label = repo;
		const ref = run.git_ref || run.git_sha?.slice(0, 8) || '';
		if (ref) label += `@${ref}`;
		return label || run.id.slice(0, 8);
	});

	$effect(() => {
		breadcrumbStore.set([{ label: breadcrumbLabel }]);
	});

	onDestroy(() => {
		breadcrumbStore.clear();
		stopLogStream();
		if (pollInterval) clearInterval(pollInterval);
		if (tickInterval) clearInterval(tickInterval);
	});

	async function loadRun() {
		loading = true;
		try {
			run = await runs.get(runId);
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}

	function startLogStream() {
		if (eventSource) return;

		const url = runs.logsUrl(runId);
		eventSource = new EventSource(url, { withCredentials: true });
		streaming = true;

		let pendingLines: string[] = [];
		let flushScheduled = false;

		function flushLogs() {
			if (pendingLines.length > 0) {
				logs.push(...pendingLines);
				pendingLines = [];
				scrollToBottom();
			}
			flushScheduled = false;
		}

		eventSource.onmessage = (event) => {
			pendingLines.push(event.data);
			if (!flushScheduled) {
				flushScheduled = true;
				requestAnimationFrame(flushLogs);
			}
		};

		eventSource.addEventListener('done', () => {
			streamDone = true;
			streaming = false;
			eventSource!.close();
			eventSource = null;
			// Refresh run data to get final status
			loadRun();
		});

		eventSource.onerror = () => {
			streaming = false;
			if (eventSource) {
				eventSource.close();
				eventSource = null;
			}
			// Start polling for status if not terminal
			const terminal = run && RUN_FINAL_STATUSES.has(run.status);
			if (!terminal) {
				startPolling();
			}
		};
	}

	function stopLogStream() {
		if (eventSource) {
			eventSource.close();
			eventSource = null;
			streaming = false;
		}
	}

	function startPolling() {
		if (pollInterval) return;
		pollInterval = setInterval(async () => {
			try {
				run = await runs.get(runId);
				if (isTerminal && pollInterval) {
					clearInterval(pollInterval);
					pollInterval = null;
				}
			} catch {
				// ignore polling errors
			}
		}, 5000);
	}

	async function runAction(setBusy: (v: boolean) => void, action: () => Promise<void>) {
		if (!run) return;
		setBusy(true);
		try {
			await action();
		} catch (err) {
			if (!(err as ApiError).cancelled) toast.error((err as Error).message);
		} finally {
			setBusy(false);
		}
	}

	const handleCancel = () => runAction(v => cancelling = v, async () => {
		await runs.cancel(run!.id);
		run = await runs.get(runId);
	});

	const handleRerun = () => runAction(v => rerunning = v, async () => {
		const newRun = await runs.rerun(run!);
		goto(`/runs/${newRun.id}`);
	});

	const handleRemove = () => runAction(v => removing = v, async () => {
		await runs.remove(run!.id);
		goto('/runs');
	});

	const canEditRun = $derived(
		run && authStore.user && (
			authStore.user.permissions?.includes('runs:manage_all') ||
			run.owner?.id === authStore.user.id
		)
	);

	const handleToggleVisibility = () => runAction(v => togglingVisibility = v, async () => {
		const newVis = run!.visibility === 'public' ? 'private' : 'public';
		await runs.updateVisibility(run!.id, newVis);
		run = await runs.get(runId);
	});

	function scrollToBottom() {
		requestAnimationFrame(() => {
			if (logContainer) {
				logContainer.scrollTop = logContainer.scrollHeight;
			}
		});
	}
</script>

<div class="min-h-screen">
	<div class="max-w-[80rem] mx-auto py-8">
		{#if loading && !run}
			<!-- Loading skeleton -->
			<div class="bg-card rounded-lg border border-border p-6 mb-4">
				<div class="flex items-center gap-4 mb-4">
					<Skeleton class="h-6 w-20 rounded-full" />
					<Skeleton class="h-5 w-64" />
				</div>
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
					<Skeleton class="h-4 w-32" />
					<Skeleton class="h-4 w-24" />
					<Skeleton class="h-4 w-28" />
					<Skeleton class="h-4 w-20" />
				</div>
			</div>
			<Skeleton class="h-96 w-full rounded-lg" />
		{:else if run}
			<!-- Run header -->
			<div class="bg-card rounded-lg border border-border p-6 mb-4">
				<!-- Row 1: Identity & Actions -->
				<div class="flex items-center gap-3 mb-3">
					<StatusCell {run} />
					<div class="min-w-0">
						{#if configDisplay && workflowDisplay}
							<p class="text-xs text-muted-foreground truncate">{workflowDisplay}</p>
						{/if}
						<h1 class="text-lg font-semibold font-mono truncate">
							{#if configDisplay}
								{configDisplay}
							{:else if workflowDisplay}
								{workflowDisplay}
							{:else}
								Run {run.id.slice(0, 8)}
							{/if}
						</h1>
					</div>
					<div class="ml-auto">
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								{#snippet child({ props }: { props: Record<string, unknown> })}
									<Button variant="ghost" size="sm" {...props} class="h-8 w-8 p-0" disabled={actionBusy}>
										{#if actionBusy}
											<Loader2 class="h-4 w-4 animate-spin" />
										{:else}
											<MoreVertical class="h-4 w-4" />
										{/if}
										<span class="sr-only">Actions</span>
									</Button>
								{/snippet}
							</DropdownMenu.Trigger>
							<DropdownMenu.Content align="end">
								{#if !isSettled}
									<DropdownMenu.Item onclick={handleCancel} disabled={actionBusy}>
										<X class="h-4 w-4 mr-2" />
										Cancel
									</DropdownMenu.Item>
								{/if}
								{#if isSettled}
									<DropdownMenu.Item onclick={handleRerun} disabled={actionBusy}>
										<RotateCw class="h-4 w-4 mr-2" />
										Rerun
									</DropdownMenu.Item>
								{/if}
								{#if canEditRun}
									<DropdownMenu.Item onclick={handleToggleVisibility} disabled={actionBusy}>
										{#if run?.visibility === 'public'}
											<LockKeyhole class="h-4 w-4 mr-2" />
											Make private
										{:else}
											<Globe class="h-4 w-4 mr-2" />
											Make public
										{/if}
									</DropdownMenu.Item>
								{/if}
								<DropdownMenu.Separator />
								<DropdownMenu.Item onclick={handleRemove} disabled={actionBusy} class="text-destructive focus:text-destructive">
									<Trash2 class="h-4 w-4 mr-2" />
									Remove
								</DropdownMenu.Item>
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					</div>
				</div>

				<!-- Row 2: Metrics chips -->
				<div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
					{#if run.git_ref || run.git_sha}
						<div class="flex items-center gap-1.5">
							<GitBranch class="h-3.5 w-3.5" />
							<span>{run.git_ref || ''}{run.git_sha ? `@${run.git_sha.slice(0, 8)}` : ''}</span>
						</div>
						<div class="h-4 w-px bg-border"></div>
					{/if}
					{#if duration}
						<div class="flex items-center gap-1.5">
							<Clock class="h-3.5 w-3.5" />
							<span>{duration}</span>
						</div>
						<div class="h-4 w-px bg-border"></div>
					{/if}
					<div class="flex items-center gap-1.5">
						<Calendar class="h-3.5 w-3.5" />
						<span title={formatDate(run.created_at)}>{createdDisplay}</span>
					</div>
					<div class="h-4 w-px bg-border"></div>
					<div class="flex items-center gap-1.5">
						<Server class="h-3.5 w-3.5" />
						<span>{run.backend.name}</span>
					</div>
					{#if authStore.authEnabled}
						<div class="h-4 w-px bg-border"></div>
						<div class="flex items-center gap-1.5">
							{#if run.visibility === 'public'}
								<Globe class="h-3.5 w-3.5" />
								<span>Public</span>
							{:else}
								<LockKeyhole class="h-3.5 w-3.5" />
								<span>Private</span>
							{/if}
						</div>
					{/if}
					{#if run.networks.length > 0}
						<div class="h-4 w-px bg-border"></div>
						<div class="flex items-center gap-1.5">
							{#each run.networks as network, i}
								{#if i > 0}<span>,</span>{/if}
								<a href="/database/network?id={network.id}" class="underline hover:text-foreground">
									{network.filename}
								</a>
							{/each}
						</div>
					{/if}
					{#if run.owner}
						<div class="flex items-center gap-1.5 ml-auto">
							{#if run.owner.avatar_url}
								<img src={run.owner.avatar_url} alt={run.owner.username} class="h-4 w-4 rounded-full" />
							{/if}
							<span>{run.owner.username}</span>
						</div>
					{/if}
				</div>

				<!-- Row 4: Progress bar (running runs only) -->
				{#if !isTerminal && run.status !== 'PENDING' && workflow}
					{@const total = workflow.total_job_count}
					{@const done = workflow.jobs_finished}
					{@const pct = total > 0 ? Math.round((done / total) * 100) : 0}
					<div class="mt-4">
						<div class="flex justify-between mb-1">
							<span class="text-xs text-muted-foreground">{done}/{total}</span>
							<span class="text-xs text-muted-foreground">{pct}%</span>
						</div>
						<div class="h-1.5 w-full rounded-full bg-muted overflow-hidden">
							<div class="h-full rounded-full bg-primary transition-all duration-500" style="width: {pct}%"></div>
						</div>
					</div>
				{/if}
			</div>

			<!-- Workflow -->
			{#if run.status !== 'PENDING'}
				<WorkflowSection {runId} isTerminal={!!isTerminal} isFailedRun={run.status === 'FAILED' || run.status === 'ERROR'} />
			{/if}

			<!-- Files -->
			{#if isTerminal}
				<div class="bg-card rounded-lg border border-border overflow-hidden">
					<button
						class="flex items-center gap-2 px-4 py-3 w-full text-left hover:bg-accent/50 transition-colors"
						onclick={() => (outputsOpen = !outputsOpen)}
					>
						<FolderArchive class="h-4 w-4 text-muted-foreground" />
						<span class="text-sm font-medium">Files</span>
						{#if outputsLoading}
							<Loader2 class="h-3.5 w-3.5 animate-spin text-muted-foreground" />
						{:else if outputsUnavailable}
							<span class="text-xs text-muted-foreground">no longer available</span>
						{:else if outputFiles && outputFiles.length > 0}
							<span class="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full">
								{outputFiles.length}
							</span>
						{/if}
						{#if outputFiles && outputFiles.length > 0}
							<ChevronRight
								class="h-4 w-4 text-muted-foreground ml-auto transition-transform duration-200"
								style={outputsOpen ? 'transform: rotate(90deg)' : ''}
							/>
						{/if}
					</button>
					{#if outputsOpen && outputFiles && outputFiles.length > 0}
						<div class="border-t border-border px-4 py-3">
							<OutputFilesTree files={outputFiles} {runId} {workflow} />
						</div>
					{/if}
				</div>
			{/if}

			<!-- Logs -->
			<div class="bg-card rounded-lg border border-border overflow-hidden mt-4">
				<button
					class="flex items-center gap-2 px-4 py-3 w-full text-left hover:bg-accent/50 transition-colors"
					onclick={() => (logsOpen = !logsOpen)}
				>
					<Terminal class="h-4 w-4 text-muted-foreground" />
					<span class="text-sm font-medium">Logs</span>
					<a
						href={`${runs.logsUrl(runId)}?format=text`}
						target="_blank"
						rel="noopener noreferrer"
						class="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:underline transition-colors"
						onclick={(e) => e.stopPropagation()}
					>
						<ExternalLink class="h-3.5 w-3.5" />
						Raw logs
					</a>
					<ChevronRight
						class="h-4 w-4 text-muted-foreground transition-transform duration-200"
						style={logsOpen ? 'transform: rotate(90deg)' : ''}
					/>
				</button>
				{#if logsOpen}
					<div
						bind:this={logContainer}
						class="border-t border-border bg-zinc-950 text-zinc-200 p-4 font-mono text-xs leading-5 overflow-y-auto"
						style="max-height: 70vh; min-height: 20rem;"
					>
						{#if logs.length === 0}
							<span class="text-zinc-500">
								{#if streaming}
									Waiting for logs...
								{:else if isTerminal}
									No logs available.
								{:else}
									Connecting...
								{/if}
							</span>
						{:else}
							{#each logs as line, i}
								<div class="whitespace-pre-wrap hover:bg-zinc-900/50">{line}</div>
							{/each}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Configuration -->
			<div class="bg-card rounded-lg border border-border overflow-hidden mt-4">
				<button
					class="flex items-center gap-2 px-4 py-3 w-full text-left hover:bg-accent/50 transition-colors"
					onclick={() => (configOpen = !configOpen)}
				>
					<Settings2 class="h-4 w-4 text-muted-foreground" />
					<span class="text-sm font-medium">Configuration</span>
					<ChevronRight
						class="h-4 w-4 text-muted-foreground ml-auto transition-transform duration-200"
						style={configOpen ? 'transform: rotate(90deg)' : ''}
					/>
				</button>
				{#if configOpen}
					<dl class="border-t border-border px-4 py-3 grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
						<dt class="text-muted-foreground">Workflow</dt>
						<dd class="font-mono text-xs break-all">{run.workflow}</dd>

						{#if run.configfile}
							<dt class="text-muted-foreground">Config</dt>
							<dd class="font-mono text-xs">{run.configfile}</dd>
						{/if}

						{#if run.snakemake_args?.length}
							<dt class="text-muted-foreground">Args</dt>
							<dd class="font-mono text-xs">{run.snakemake_args.join(' ')}</dd>
						{/if}

						{#if run.cache}
							<dt class="text-muted-foreground">Cache</dt>
							<dd class="font-mono text-xs">
								key: {run.cache.key}, dirs: {run.cache.dirs.join(', ')}
							</dd>
						{/if}

						{#if run.import_networks?.length}
							<dt class="text-muted-foreground">Import networks</dt>
							<dd class="font-mono text-xs">{run.import_networks.join(', ')}</dd>
						{/if}

						{#if run.extra_files && Object.keys(run.extra_files).length}
							<dt class="text-muted-foreground">Extra files</dt>
							<dd class="font-mono text-xs">{Object.keys(run.extra_files).join(', ')}</dd>
						{/if}
					</dl>
				{/if}
			</div>
		{/if}
	</div>
</div>
