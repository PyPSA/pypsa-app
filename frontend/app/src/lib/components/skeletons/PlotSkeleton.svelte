<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { title = '', message = '' } = $props();

	const leftBars = Array(5)
		.fill(0)
		.map((_, i) => 10 + Math.floor(Math.random() * 25) + i * 5);
	const rightBars = Array(5)
		.fill(0)
		.map((_, i) => 10 + Math.floor(Math.random() * 25) + (4 - i) * 5);
</script>

<div class="h-full w-full @container">
	{#if title}
		<h3 class="mb-3 text-lg font-semibold">{title}</h3>
	{/if}
	<div class="relative flex h-full w-full flex-col overflow-hidden bg-card p-4 @md:p-6">
		<div class="flex min-h-0 flex-1">
			<!-- Y-axis labels -->
			<div class="hidden flex-col justify-between py-4 pr-3 @sm:flex">
				{#each Array(4) as _, i}
					<Skeleton class="h-3 w-8" style="animation-delay: {i * 30}ms" />
				{/each}
			</div>

			<div class="flex min-h-0 flex-1 flex-col">
				<div class="flex flex-1 items-end gap-1 px-2 pb-2">
					{#each leftBars as barHeight, i}
						<div class="flex flex-1 flex-col justify-end">
							<Skeleton
								class="w-full rounded-t opacity-30"
								style="height: {barHeight}%; animation-delay: {i * 40}ms"
							/>
						</div>
					{/each}

					{#each rightBars as barHeight, i}
						<div class="flex flex-1 flex-col justify-end">
							<Skeleton
								class="w-full rounded-t opacity-30"
								style="height: {barHeight}%; animation-delay: {(i + 5) * 40}ms"
							/>
						</div>
					{/each}
				</div>

				<!-- X-axis labels -->
				<div class="hidden justify-between border-t border-border/30 pt-2 @sm:flex">
					{#each Array(5) as _, i}
						<Skeleton class="h-3 w-10" style="animation-delay: {i * 40}ms" />
					{/each}
				</div>
			</div>
		</div>

		<!-- Legend -->
		<div class="hidden shrink-0 justify-center gap-4 pt-4 @md:flex">
			{#each Array(3) as _, i}
				<div class="flex items-center gap-1.5" style="animation-delay: {i * 50}ms">
					<Skeleton class="h-3 w-3 rounded-sm" />
					<Skeleton class="h-3 w-16" />
				</div>
			{/each}
		</div>

		<!-- Centered spinner overlay -->
		<div class="absolute inset-0 flex items-center justify-center">
			<div class="flex flex-col items-center gap-3">
				<div class="relative h-10 w-10 @md:h-12 @md:w-12">
					<div class="absolute inset-0 rounded-full border-[3px] border-accent"></div>
					<div
						class="absolute inset-0 animate-spin rounded-full border-[3px] border-primary border-t-transparent"
					></div>
				</div>
				{#if message}
					<span class="text-center text-xs font-medium text-muted-foreground @md:text-sm"
						>{message}</span
					>
				{/if}
			</div>
		</div>
	</div>
</div>
