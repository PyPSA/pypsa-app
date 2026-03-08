<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { runs } from '$lib/api/client.js';
	import { formatRelativeTime, formatDuration } from '$lib/utils.js';
	import { RUN_FINAL_STATUSES, RUN_SETTLED_STATUSES } from '$lib/types.js';
	import type { Run, ApiError, OutputFile } from '$lib/types.js';
	import { Button } from '$lib/components/ui/button';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import { ArrowLeft, Terminal, RotateCw, X, Trash2, Loader2, MoreVertical, Settings2, ChevronRight, ExternalLink, FolderArchive } from 'lucide-svelte';
	import OutputFilesTree from '../components/OutputFilesTree.svelte';
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
	let configOpen = $state(false);

	let outputFiles = $state<OutputFile[] | null>(null);
	let outputsOpen = $state(true);
	let outputsLoading = $state(false);
	let outputsError = $state<string | null>(null);
	let outputsUnavailable = $state(false);

	let eventSource: EventSource | null = null;
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let tickInterval: ReturnType<typeof setInterval> | null = null;
	let logContainer: HTMLDivElement;

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

	$effect(() => {
		if (isTerminal && outputFiles === null && !outputsLoading) {
			let cancelled = false;
			outputsLoading = true;
			runs.listOutputs(runId).then((files) => {
				if (!cancelled) outputFiles = files;
			}).catch((err: unknown) => {
				if (cancelled) return;
				if ((err as ApiError).status === 404) {
					outputsUnavailable = true;
				} else if (!(err as ApiError).cancelled) {
					outputsError = (err as Error).message;
				}
			}).finally(() => {
				if (!cancelled) outputsLoading = false;
			});
			return () => { cancelled = true; };
		}
	});
	const actionBusy = $derived(cancelling || rerunning || removing);

	const duration = $derived.by(() => {
		if (!isTerminal) tick; // reference tick to force re-evaluation
		return formatDuration(run?.started_at, run?.completed_at);
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

	onMount(async () => {
		await loadRun();
		startLogStream();
	});

	onDestroy(() => {
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

		eventSource.onmessage = (event) => {
			logs.push(event.data);
			scrollToBottom();
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
		<!-- Back button -->
		<Button variant="ghost" class="mb-4 gap-2" onclick={() => goto('/runs')}>
			<ArrowLeft class="h-4 w-4" />
			Back to Runs
		</Button>

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
				<div class="flex items-center gap-4 mb-4">
					<StatusCell {run} />
					<h1 class="text-lg font-semibold">
						{#if workflowDisplay}
							{workflowDisplay}
						{:else}
							Run {run.id.slice(0, 8)}
						{/if}
					</h1>
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
								<DropdownMenu.Separator />
								<DropdownMenu.Item onclick={handleRemove} disabled={actionBusy} class="text-destructive focus:text-destructive">
									<Trash2 class="h-4 w-4 mr-2" />
									Remove
								</DropdownMenu.Item>
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					</div>
				</div>

				<div class="grid grid-cols-2 md:grid-cols-4 gap-y-3 gap-x-6 text-sm text-muted-foreground">
					{#if run.git_ref || run.git_sha}
						<div>
							<span class="font-medium text-foreground">Ref:</span>
							{run.git_ref || ''}{run.git_sha ? `@${run.git_sha.slice(0, 8)}` : ''}
						</div>
					{/if}
					{#if duration}
						<div>
							<span class="font-medium text-foreground">Duration:</span>
							{duration}
						</div>
					{/if}
					<div>
						<span class="font-medium text-foreground">Created:</span>
						{formatRelativeTime(run.created_at)}
					</div>
					{#if run.exit_code !== null && run.exit_code !== undefined}
						<div>
							<span class="font-medium text-foreground">Exit code:</span>
							{run.exit_code}
						</div>
					{/if}
				</div>
			</div>

			<!-- Logs -->
			<div class="bg-card rounded-lg border border-border overflow-hidden">
				<div class="flex items-center gap-2 px-4 py-3 border-b border-border">
					<Terminal class="h-4 w-4 text-muted-foreground" />
					<span class="text-sm font-medium">Logs</span>
					<a
						href={`${runs.logsUrl(runId)}?format=text`}
						target="_blank"
						rel="noopener noreferrer"
						class="ml-auto text-muted-foreground hover:text-foreground transition-colors"
						title="Open logs in new window"
					>
						<ExternalLink class="h-4 w-4" />
					</a>
				</div>
				<div
					bind:this={logContainer}
					class="bg-zinc-950 text-zinc-200 p-4 font-mono text-xs leading-5 overflow-y-auto"
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
			</div>

			<!-- Files -->
			{#if isTerminal}
				<div class="bg-card rounded-lg border border-border overflow-hidden mt-4">
					<button
						class="flex items-center gap-2 px-4 py-3 w-full text-left hover:bg-accent/50 transition-colors"
						onclick={() => (outputsOpen = !outputsOpen)}
					>
						<FolderArchive class="h-4 w-4 text-muted-foreground" />
						<span class="text-sm font-medium">Files</span>
						{#if outputsLoading}
							<Loader2 class="h-3.5 w-3.5 animate-spin text-muted-foreground" />
						{:else if outputsError}
							<span class="text-xs text-destructive">{outputsError}</span>
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
							<OutputFilesTree files={outputFiles} {runId} />
						</div>
					{/if}
				</div>
			{/if}

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
