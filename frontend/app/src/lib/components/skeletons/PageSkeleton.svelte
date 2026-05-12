<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton';
</script>

<div class="flex flex-col items-center justify-center h-[60vh] gap-3">
	<Skeleton class="h-4 w-48 rounded" />
	<Skeleton class="h-3 w-32 rounded opacity-60" />
	<Skeleton class="h-3 w-56 rounded opacity-40" />
</div>
