<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import Globe from '@lucide/svelte/icons/globe';
	import LockKeyhole from '@lucide/svelte/icons/lock-keyhole';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import type { Visibility } from '$lib/types.js';

	let { item, canEdit, onToggle }: {
		item: { id: string; visibility: Visibility; owner?: { id: string } | null };
		canEdit: boolean;
		onToggle: (id: string, visibility: Visibility) => void;
	} = $props();

	const isSystem = $derived(!item.owner);
	const isPublic = $derived(item.visibility === 'public');
	const Icon = $derived(isPublic ? Globe : LockKeyhole);
	const iconClass = 'h-4 w-4 text-muted-foreground';
</script>

{#if isSystem}
	<div class="h-8 w-8"></div>
{:else}
	<div onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()} role="button" tabindex="-1">
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props }: { props: Record<string, unknown> })}
					{#if canEdit}
						<Button
							variant="ghost"
							size="sm"
							class="h-8 w-8 p-0"
							onclick={() => onToggle(item.id, isPublic ? 'private' : 'public')}
							{...props}
						>
							<Icon class={iconClass} />
						</Button>
					{:else}
						<div class="h-8 w-8 flex items-center justify-center" {...props}>
							<Icon class={iconClass} />
						</div>
					{/if}
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content>
				{isPublic ? 'Visible to all users' : 'Only visible to the owner'}
			</Tooltip.Content>
		</Tooltip.Root>
	</div>
{/if}
