<script lang="ts">
	import type { WorkflowError } from '$lib/types.js';
	import * as Alert from '$lib/components/ui/alert';
	import { AlertTriangle, ChevronDown, ChevronRight } from 'lucide-svelte';

	let { errors }: { errors: WorkflowError[] } = $props();

	let expandedIndex = $state<number | null>(null);

	function toggle(i: number) {
		expandedIndex = expandedIndex === i ? null : i;
	}
</script>

{#if errors.length > 0}
	<div class="space-y-2">
		{#each errors as error, i}
			<Alert.Root variant="destructive">
				<AlertTriangle class="h-4 w-4" />
				<Alert.Title class="flex items-center gap-2">
					{#if error.rule}
						<span class="font-mono text-xs">{error.rule}</span> —
					{/if}
					{error.exception}
				</Alert.Title>
				{#if error.traceback}
					<Alert.Description>
						<button
							class="flex items-center gap-1 text-xs mt-1 opacity-70 hover:opacity-100"
							onclick={() => toggle(i)}
						>
							{#if expandedIndex === i}
								<ChevronDown class="h-3 w-3" />
							{:else}
								<ChevronRight class="h-3 w-3" />
							{/if}
							Traceback
						</button>
						{#if expandedIndex === i}
							<pre class="mt-2 text-xs whitespace-pre-wrap font-mono bg-destructive/10 p-2 rounded overflow-x-auto">{error.traceback}</pre>
						{/if}
					</Alert.Description>
				{/if}
			</Alert.Root>
		{/each}
	</div>
{/if}
