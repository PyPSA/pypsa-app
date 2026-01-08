<script>
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { rows = 5 } = $props();
</script>

<div class="bg-card rounded-lg border border-border overflow-hidden">
	<div class="overflow-x-auto">
		<table class="w-full">
			<thead>
				<tr class="border-b border-border bg-muted/30">
					<th class="h-12 px-4 text-left align-middle">
						<Skeleton class="h-4 w-16" />
					</th>
					<th class="h-12 px-4 text-left align-middle">
						<Skeleton class="h-4 w-12" />
					</th>
					<th class="h-12 px-4 text-left align-middle">
						<Skeleton class="h-4 w-20" />
					</th>
					<th class="h-12 px-4 text-left align-middle">
						<Skeleton class="h-4 w-24" />
					</th>
					<th class="h-12 px-4 text-left align-middle">
						<Skeleton class="h-4 w-16" />
					</th>
					<th class="h-12 px-4 text-left align-middle">
						<Skeleton class="h-4 w-14" />
					</th>
				</tr>
			</thead>
			<tbody>
				{#each Array(rows) as _, i}
					<tr class="border-b border-border/50" style="animation-delay: {i * 75}ms">
						<!-- Filename -->
						<td class="p-4">
							<div class="flex flex-col gap-1.5">
								<Skeleton class="h-4 w-36" />
								<Skeleton class="h-3 w-48 opacity-60" />
							</div>
						</td>
						<!-- Size -->
						<td class="p-4">
							<Skeleton class="h-4 w-16" />
						</td>
						<!-- Components -->
						<td class="p-4">
							<div class="flex gap-1.5">
								<Skeleton class="h-5 w-12 rounded-full" />
								<Skeleton class="h-5 w-14 rounded-full" />
								<Skeleton class="h-5 w-10 rounded-full" />
							</div>
						</td>
						<!-- Dimensions -->
						<td class="p-4">
							<div class="flex gap-2">
								<Skeleton class="h-4 w-12" />
								<Skeleton class="h-4 w-10" />
							</div>
						</td>
						<!-- Tags -->
						<td class="p-4">
							<div class="flex gap-1.5">
								<Skeleton class="h-5 w-16 rounded-full" />
								<Skeleton class="h-5 w-12 rounded-full" />
							</div>
						</td>
						<!-- Actions -->
						<td class="p-4">
							<div class="flex justify-end gap-1">
								<Skeleton class="h-8 w-8 rounded-md" />
								<Skeleton class="h-8 w-8 rounded-md" />
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
