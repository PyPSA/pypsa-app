<script>
	import { Button } from '$lib/components/ui/button';
	import { Share2, Lock } from 'lucide-svelte';
	import * as Tooltip from '$lib/components/ui/tooltip';

	let { network, canEdit, onToggle } = $props();

	const isSystem = $derived(!network.owner);
	const isPublic = $derived(network.visibility === 'public');
	const Icon = $derived(isPublic ? Share2 : Lock);
	const iconClass = 'h-4 w-4 text-muted-foreground';
</script>

{#if isSystem}
	<div class="h-8 w-8"></div>
{:else}
	<div onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()} role="button" tabindex="-1">
		<Tooltip.Root>
			<Tooltip.Trigger asChild>
				{#snippet child({ props })}
					{#if canEdit}
						<Button
							variant="ghost"
							size="sm"
							class="h-8 w-8 p-0"
							onclick={() => onToggle(network.id, isPublic ? 'private' : 'public')}
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
				{isPublic ? 'Visible to all users' : 'Only visible to you'}
			</Tooltip.Content>
		</Tooltip.Root>
	</div>
{/if}
