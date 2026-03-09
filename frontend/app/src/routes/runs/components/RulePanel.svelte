<script lang="ts">
	import type { WorkflowRule } from '$lib/types.js';
	import * as Table from '$lib/components/ui/table';
	import { ChevronRight } from 'lucide-svelte';

	let { rule }: { rule: WorkflowRule } = $props();

	let expandedJobIndex = $state<number | null>(null);

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

	function jobDuration(job: { started_at?: string; end_time?: string }): number {
		if (!job.started_at) return 0;
		const start = new Date(job.started_at).getTime();
		const end = job.end_time ? new Date(job.end_time).getTime() : Date.now();
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

	function shortPath(path: string): string {
		return path
			.replace(/^\/app\/\.snakedispatch\/jobs\/[^/]+\//, '')
			.replace(/\s*\(retrieve from storage\)$/, '');
	}

	function jobHasFiles(job: { files?: { file_type: string; path: string }[] }): boolean {
		return (job.files?.length ?? 0) > 0;
	}
</script>

{#if rule.jobs?.length === 1}
	{@const job = rule.jobs[0]}
	{@const inputs = job.files?.filter(f => f.file_type === 'INPUT') ?? []}
	{@const outputs = job.files?.filter(f => f.file_type === 'OUTPUT') ?? []}
	{#if inputs.length > 0 || outputs.length > 0}
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
	{/if}
{:else if rule.jobs?.length > 1}
	<Table.Root class="text-xs">
		<Table.Header>
			<Table.Row class="hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent">
				<Table.Head class="h-7 py-1 pr-3">Wildcards</Table.Head>
				<Table.Head class="h-7 py-1 pr-3 text-right">Duration</Table.Head>
				<Table.Head class="h-7 py-1 pr-3 text-right w-0">Threads</Table.Head>
				<Table.Head class="h-7 py-1 w-4 p-0"></Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each rule.jobs as job, i}
				{@const hasFiles = jobHasFiles(job)}
				{@const duration = jobDuration(job)}
				{@const status = job.status.toLowerCase()}
				{@const inputs = job.files?.filter(f => f.file_type === 'INPUT') ?? []}
				{@const outputs = job.files?.filter(f => f.file_type === 'OUTPUT') ?? []}
				<Table.Row
					class="{hasFiles ? 'cursor-pointer' : 'hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent'} {hasFiles && expandedJobIndex === i ? 'border-0' : ''}"
					onclick={() => { if (hasFiles) expandedJobIndex = expandedJobIndex === i ? null : i; }}
				>
					<Table.Cell class="py-1 pr-3 font-mono w-0">
						<div class="flex items-center gap-2">
							<span class="inline-block h-1.5 w-1.5 rounded-full shrink-0 {statusDotColor(job.status)}"></span>
							<span class="truncate max-w-[20rem]">{formatWildcards(job.wildcards)}</span>
						</div>
					</Table.Cell>
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
					<Table.Cell class="py-1 pr-3 text-right text-muted-foreground w-0">{job.threads}</Table.Cell>
					<Table.Cell class="py-1 pl-2 w-4">
						{#if hasFiles}
							<ChevronRight
								class="h-3 w-3 text-muted-foreground transition-transform duration-200"
								style={expandedJobIndex === i ? 'transform: rotate(90deg)' : ''}
							/>
						{/if}
					</Table.Cell>
				</Table.Row>
				{#if hasFiles && expandedJobIndex === i}
					<Table.Row class="hover:[&,&>svelte-css-wrapper]:[&>th,td]:bg-transparent">
						<Table.Cell colspan={4} class="py-1 pl-2">
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
						</Table.Cell>
					</Table.Row>
				{/if}
			{/each}
		</Table.Body>
	</Table.Root>
{:else}
	<p class="text-xs text-muted-foreground">No jobs yet.</p>
{/if}
