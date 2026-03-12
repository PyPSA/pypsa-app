<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton';
</script>

<div class="flex gap-6">
	<!-- Main Content -->
	<div class="flex-1 min-w-0">
		<!-- Header -->
		<div class="mb-8">
			<Skeleton class="h-9 w-64 mb-2" />
			<Skeleton class="h-4 w-48 opacity-60" />
		</div>

		<!-- Network Overview with Map -->
		<div class="grid grid-cols-5 gap-6 mb-8">
			<!-- Network Overview Card -->
			<div class="col-span-4 bg-card rounded-lg border border-border p-6">
				<Skeleton class="h-6 w-40 mb-4" />

				<div class="space-y-3">
					<!-- File row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-16 mr-8" />
						<div class="flex items-center gap-2">
							<Skeleton class="h-4 w-32" />
							<Skeleton class="h-3 w-16 opacity-60" />
						</div>
					</div>

					<!-- Path row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-16 mr-8" />
						<Skeleton class="h-3 w-56" />
					</div>

					<!-- Name row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-16 mr-8" />
						<Skeleton class="h-4 w-40" />
					</div>

					<!-- Last Updated row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-24 mr-8" />
						<Skeleton class="h-3 w-20" />
					</div>

					<!-- Created At row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-20 mr-8" />
						<Skeleton class="h-3 w-24" />
					</div>

					<!-- Hash row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-12 mr-8" />
						<Skeleton class="h-3 w-80 font-mono" />
					</div>

					<!-- Dimensions row -->
					<div class="flex items-center border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-24 mr-8" />
						<div class="flex gap-3">
							<Skeleton class="h-4 w-16" />
							<Skeleton class="h-4 w-12" />
							<Skeleton class="h-4 w-14" />
						</div>
					</div>

					<!-- Components row -->
					<div class="flex items-start border-b border-border/50 pb-3">
						<Skeleton class="h-4 w-24 mr-8 mt-0.5" />
						<div class="flex flex-wrap gap-1.5">
							{#each Array(8) as _, i}
								<Skeleton class="h-5 w-20 rounded" style="animation-delay: {i * 50}ms" />
							{/each}
						</div>
					</div>

					<!-- Tags row -->
					<div class="flex items-start pt-1">
						<Skeleton class="h-4 w-12 mr-8 mt-0.5" />
						<div class="flex flex-wrap gap-1.5">
							<Skeleton class="h-5 w-24 rounded-full" />
							<Skeleton class="h-5 w-16 rounded-full" />
							<Skeleton class="h-5 w-20 rounded-full" />
						</div>
					</div>
				</div>
			</div>

			<!-- Map Card -->
			<div class="col-span-1 bg-card rounded-lg border border-border p-3">
				<div class="flex items-center gap-2 mb-2">
					<Skeleton class="h-4 w-4" />
					<Skeleton class="h-4 w-10" />
				</div>
				<Skeleton class="aspect-4/3 w-full rounded-md" />
				<div class="mt-2 flex items-center justify-center">
					<Skeleton class="h-3 w-16" />
				</div>
			</div>
		</div>

		<!-- Plots Section -->
		<div class="w-full bg-card rounded-lg border border-border p-6">
			<Skeleton class="h-6 w-36 mb-6" />

			<!-- Tab Navigation -->
			<div class="flex gap-1 mb-6 p-1 bg-muted rounded-lg w-fit">
				{#each Array(5) as _, i}
					<Skeleton class="h-8 w-32 rounded-md" style="animation-delay: {i * 30}ms" />
				{/each}
			</div>

			<!-- Plot Area -->
			<div class="w-full rounded-lg border-2 border-border/50 bg-muted/20 h-[500px] flex items-center justify-center">
				<div class="text-center">
					<Skeleton class="h-12 w-12 rounded-full mx-auto mb-3" />
					<Skeleton class="h-4 w-32 mx-auto" />
				</div>
			</div>
		</div>
	</div>

	<!-- Filters Panel Skeleton -->
	<div class="shrink-0 w-80">
		<div class="sticky top-4">
			<div class="bg-sidebar border-l border-sidebar-border rounded-l-lg overflow-hidden shadow-sm">
				<!-- Header -->
				<div class="flex h-14 items-center border-b border-sidebar-border px-4">
					<div class="flex items-center gap-2">
						<Skeleton class="h-4 w-4" />
						<Skeleton class="h-4 w-28" />
					</div>
				</div>
				<!-- Content -->
				<div class="p-4 space-y-4">
					<!-- Carriers section -->
					<div class="space-y-2">
						<Skeleton class="h-4 w-16" />
						<div class="space-y-1.5">
							{#each Array(6) as _, i}
								<div class="flex items-center gap-2" style="animation-delay: {i * 40}ms">
									<Skeleton class="h-4 w-4 rounded" />
									<Skeleton class="h-4 w-24" />
								</div>
							{/each}
						</div>
					</div>

					<!-- Countries section -->
					<div class="space-y-2 pt-2">
						<Skeleton class="h-4 w-20" />
						<div class="space-y-1.5">
							{#each Array(4) as _, i}
								<div class="flex items-center gap-2" style="animation-delay: {i * 40}ms">
									<Skeleton class="h-4 w-4 rounded" />
									<Skeleton class="h-4 w-16" />
								</div>
							{/each}
						</div>
					</div>

					<!-- Options section -->
					<div class="space-y-2 pt-2">
						<Skeleton class="h-4 w-16" />
						<div class="flex items-center gap-2">
							<Skeleton class="h-5 w-9 rounded-full" />
							<Skeleton class="h-4 w-28" />
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</div>
