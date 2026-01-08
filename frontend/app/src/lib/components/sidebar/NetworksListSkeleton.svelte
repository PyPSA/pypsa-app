<script>
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { count = 8 } = $props();
</script>

<div class="space-y-1 px-2">
	{#each Array(count) as _, i}
		<div
			class="flex items-center gap-2 h-8 px-2 rounded-md"
			style="animation-delay: {i * 50}ms"
		>
			<Skeleton class="h-4 w-4 rounded shrink-0" />
			<Skeleton class="h-4 flex-1 max-w-[160px]" />
		</div>
	{/each}
</div>
