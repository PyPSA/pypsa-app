<script lang="ts">
	import type { RunStatus } from '$lib/types.js';
	import StatusBadge from './StatusBadge.svelte';

	let { run }: { run: { status: RunStatus } } = $props();
</script>

<StatusBadge status={run.status} />
