<script lang="ts">
	import {
		TableSkeleton,
		PlotSkeleton,
		PageSkeleton,
		NetworksListSkeleton,
		RunDetailSkeleton
	} from '$lib/components/skeletons';
</script>

<div class="max-w-[80rem] mx-auto py-8 space-y-12 px-4">
	<h1 class="text-2xl font-bold">Skeleton Components Preview</h1>

	<section>
		<h2 class="text-lg font-semibold mb-4 text-muted-foreground">1. TableSkeleton (default: 5 rows, 6 cols)</h2>
		<TableSkeleton />
	</section>

	<section>
		<h2 class="text-lg font-semibold mb-4 text-muted-foreground">2. PlotSkeleton</h2>
		<div class="h-[400px] border border-border rounded-lg overflow-hidden">
			<PlotSkeleton />
		</div>
	</section>

	<section>
		<h2 class="text-lg font-semibold mb-4 text-muted-foreground">3. RunDetailSkeleton</h2>
		<RunDetailSkeleton />
	</section>

	<section>
		<h2 class="text-lg font-semibold mb-4 text-muted-foreground">4. NetworksListSkeleton (sidebar)</h2>
		<div class="w-64 border border-border rounded-lg p-2 bg-sidebar">
			<NetworksListSkeleton />
		</div>
	</section>

	<section>
		<h2 class="text-lg font-semibold mb-4 text-muted-foreground">5. PageSkeleton</h2>
		<PageSkeleton />
	</section>
</div>
