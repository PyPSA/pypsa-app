<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton';

	let { rows = 5, columns = 6 } = $props();
</script>

<div class="bg-card rounded-lg border border-border overflow-hidden">
	<div class="overflow-x-auto">
		<table class="w-full">
			<thead>
				<tr class="border-b border-border bg-muted/30">
					{#each Array(columns) as _}
						<th class="h-12 px-4 text-left align-middle">
							<Skeleton class="h-4 w-16" />
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each Array(rows) as _, i}
					<tr class="border-b border-border/50" style="animation-delay: {i * 75}ms">
						{#each Array(columns) as _}
							<td class="p-4">
								<Skeleton class="h-4 w-24" />
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
