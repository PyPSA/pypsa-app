<script>
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { rows = 5 } = $props();
</script>

<div class="rounded-md border">
	<table class="w-full">
		<thead>
			<tr class="border-b bg-muted/30">
				<th class="h-12 px-4 text-left">
					<Skeleton class="h-4 w-12" />
				</th>
				<th class="h-12 px-4 text-left">
					<Skeleton class="h-4 w-14" />
				</th>
				<th class="h-12 px-4 text-left">
					<Skeleton class="h-4 w-10" />
				</th>
				<th class="h-12 px-4 text-left">
					<Skeleton class="h-4 w-16" />
				</th>
				<th class="h-12 px-4 text-left">
					<Skeleton class="h-4 w-20" />
				</th>
				<th class="h-12 px-4 text-right">
					<Skeleton class="h-4 w-16 ml-auto" />
				</th>
			</tr>
		</thead>
		<tbody>
			{#each Array(rows) as _, i}
				<tr class="border-b" style="animation-delay: {i * 75}ms">
					<!-- User (avatar + name) -->
					<td class="p-4">
						<div class="flex items-center gap-2">
							<Skeleton class="h-8 w-8 rounded-full shrink-0" />
							<Skeleton class="h-4 w-24" />
						</div>
					</td>
					<!-- Email -->
					<td class="p-4">
						<Skeleton class="h-4 w-36" />
					</td>
					<!-- Role -->
					<td class="p-4">
						<Skeleton class="h-5 w-14 rounded-full" />
					</td>
					<!-- Created -->
					<td class="p-4">
						<Skeleton class="h-4 w-20" />
					</td>
					<!-- Last Login -->
					<td class="p-4">
						<Skeleton class="h-4 w-20" />
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
