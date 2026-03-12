<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { title = '', height = 500, message = 'Generating plot...' } = $props();

	// Pre-generate bar heights - shorter bars that frame the center
	const leftBars = Array(8).fill(0).map((_, i) => 30 + Math.floor(Math.random() * 80) + (i * 8));
	const rightBars = Array(8).fill(0).map((_, i) => 30 + Math.floor(Math.random() * 80) + ((7-i) * 8));
</script>

<div class="w-full">
	{#if title}
		<h3 class="text-lg font-semibold mb-3">{title}</h3>
	{/if}
	<div
		class="w-full rounded-lg border-2 border-border/50 bg-card overflow-hidden"
		style="height: {height}px"
	>
		<div class="h-full w-full p-6 flex flex-col">
			<!-- Chart area -->
			<div class="flex flex-1 min-h-0">
				<!-- Y-axis labels -->
				<div class="flex flex-col justify-between py-4 pr-3">
					{#each Array(6) as _, i}
						<Skeleton class="h-3 w-8" style="animation-delay: {i * 30}ms" />
					{/each}
				</div>

				<!-- Chart content area with integrated loading -->
				<div class="flex-1 flex flex-col min-h-0">
					<div class="flex-1 flex items-end gap-1 px-2 pb-2">
						<!-- Left side bars -->
						{#each leftBars as barHeight, i}
							<div class="flex-1 flex flex-col justify-end">
								<Skeleton
									class="w-full rounded-t opacity-60"
									style="height: {barHeight}px; animation-delay: {i * 40}ms"
								/>
							</div>
						{/each}

						<!-- Center: integrated loading indicator -->
						<div class="flex-[3] flex flex-col items-center justify-center gap-3 py-8">
							<div class="relative h-12 w-12">
								<div class="absolute inset-0 rounded-full border-[3px] border-accent"></div>
								<div class="absolute inset-0 rounded-full border-[3px] border-primary border-t-transparent animate-spin"></div>
							</div>
							<span class="text-sm font-medium text-muted-foreground">{message}</span>
						</div>

						<!-- Right side bars -->
						{#each rightBars as barHeight, i}
							<div class="flex-1 flex flex-col justify-end">
								<Skeleton
									class="w-full rounded-t opacity-60"
									style="height: {barHeight}px; animation-delay: {(i + 8) * 40}ms"
								/>
							</div>
						{/each}
					</div>

					<!-- X-axis labels -->
					<div class="flex justify-between pt-2 border-t border-border/30 shrink-0">
						{#each Array(8) as _, i}
							<Skeleton class="h-3 w-10" style="animation-delay: {i * 40}ms" />
						{/each}
					</div>
				</div>
			</div>

			<!-- Legend -->
			<div class="flex justify-center gap-4 pt-4 shrink-0">
				{#each Array(4) as _, i}
					<div class="flex items-center gap-1.5" style="animation-delay: {i * 50}ms">
						<Skeleton class="h-3 w-3 rounded-sm" />
						<Skeleton class="h-3 w-16" />
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>
