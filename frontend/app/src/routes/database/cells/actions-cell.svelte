<script>
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { MoreVertical, Lock, Globe, Trash2, Loader2 } from 'lucide-svelte';

	let { network, handleDelete, handleVisibilityToggle, canEdit, isDeleting = false, isUpdatingVisibility = false } = $props();

	const isPublic = $derived(network.visibility === 'public');
	const isLoading = $derived(isDeleting || isUpdatingVisibility);
</script>

{#if canEdit}
	<div onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()} role="button" tabindex="-1">
		<DropdownMenu.Root>
			<DropdownMenu.Trigger asChild>
				{#snippet child({ props })}
					<Button variant="ghost" size="sm" {...props} class="h-8 w-8 p-0" disabled={isLoading}>
						{#if isLoading}
							<Loader2 class="h-4 w-4 animate-spin" />
						{:else}
							<MoreVertical class="h-4 w-4" />
						{/if}
						<span class="sr-only">Open menu</span>
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				<DropdownMenu.Item
					onclick={() => handleVisibilityToggle(network.id, isPublic ? 'private' : 'public')}
					disabled={isLoading}
				>
					{#if isUpdatingVisibility}
						<Loader2 class="h-4 w-4 mr-2 animate-spin" />
						Updating...
					{:else if isPublic}
						<Lock class="h-4 w-4 mr-2" />
						Make private
					{:else}
						<Globe class="h-4 w-4 mr-2" />
						Make public
					{/if}
				</DropdownMenu.Item>
				<DropdownMenu.Separator />
				<DropdownMenu.Item
					onclick={() => handleDelete(network.id)}
					class="text-destructive focus:text-destructive"
					disabled={isLoading}
				>
					{#if isDeleting}
						<Loader2 class="h-4 w-4 mr-2 animate-spin" />
						Deleting...
					{:else}
						<Trash2 class="h-4 w-4 mr-2" />
						Delete
					{/if}
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>
{/if}
