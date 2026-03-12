<script lang="ts">
	import type { RunSummary } from '$lib/types.js';
	let { run }: { run: RunSummary } = $props();
</script>

{#if run.total_job_count != null}
	<span>{run.jobs_finished ?? 0}/{run.total_job_count}</span>
{:else}
	<span>—</span>
{/if}
