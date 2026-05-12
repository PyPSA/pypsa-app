<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { showContentArea = false } = $props();
</script>

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
{#if showContentArea}
	<Skeleton class="h-96 w-full rounded-lg" />
{/if}
