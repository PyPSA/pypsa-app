<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { RunStatus, RunNetwork } from '$lib/types.js';
	import DateTime from '$lib/components/DateTime.svelte';
	import StatusCell from '../cells/status-cell.svelte';
	import GitBranch from '@lucide/svelte/icons/git-branch';
	import Clock from '@lucide/svelte/icons/clock';
	import Calendar from '@lucide/svelte/icons/calendar';
	import Server from '@lucide/svelte/icons/server';
	import Network from '@lucide/svelte/icons/network';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';

	interface RunLike {
		id: string;
		status: RunStatus;
		git_ref?: string | null;
		git_sha?: string | null;
		created_at: string;
		backend: { name: string };
		networks: RunNetwork[];
		owner?: { username: string; avatar_url?: string } | null;
	}

	interface Props {
		run: RunLike;
		configDisplay: string | null;
		workflowDisplay: string | null;
		duration: string | null;
		isTerminal: boolean;
		progress?: { total: number; done: number; pct: number } | null;
		actions?: Snippet;
		extraChips?: Snippet;
	}

	let {
		run,
		configDisplay,
		workflowDisplay,
		duration,
		isTerminal,
		progress = null,
		actions,
		extraChips,
	}: Props = $props();
</script>

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
		{#if actions}
			<div class="ml-auto">
				{@render actions()}
			</div>
		{/if}
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
			<DateTime value={run.created_at} />
		</div>
		<div class="h-4 w-px bg-border"></div>
		<div class="flex items-center gap-1.5">
			<Server class="h-3.5 w-3.5" />
			<span>{run.backend.name}</span>
		</div>
		{#if extraChips}
			{@render extraChips()}
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

	<!-- Row 3: Output networks list -->
	{#if run.networks.length > 0}
		<div class="mt-4">
			<p class="text-[10px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Output networks</p>
			<div class="flex flex-col">
				{#each run.networks as network}
					<a
						href="/networks/{network.id}"
						class="flex items-center gap-1.5 -mx-1.5 px-1.5 py-0.5 rounded hover:bg-accent transition-colors"
					>
						<Network class="h-3 w-3 text-muted-foreground shrink-0" />
						<span class="font-mono text-xs flex-1 truncate">{network.source_path ?? network.filename}</span>
						<ChevronRight class="h-3 w-3 text-muted-foreground shrink-0" />
					</a>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Progress bar -->
	{#if !isTerminal && progress}
		<div class="mt-4">
			<div class="flex justify-between mb-1">
				<span class="text-xs text-muted-foreground">{progress.done}/{progress.total}</span>
				<span class="text-xs text-muted-foreground">{progress.pct}%</span>
			</div>
			<div class="h-1.5 w-full rounded-full bg-muted overflow-hidden">
				<div class="h-full rounded-full bg-primary transition-all duration-500" style="width: {progress.pct}%"></div>
			</div>
		</div>
	{/if}
</div>
