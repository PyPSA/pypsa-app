<script>
	import * as Avatar from '$lib/components/ui/avatar';
	import * as Tooltip from '$lib/components/ui/tooltip';

	let { network } = $props();

	const owner = $derived(network.owner);
</script>

{#if owner}
	<Tooltip.Root>
		<Tooltip.Trigger>
			<Avatar.Root class="h-6 w-6">
				{#if owner.avatar_url}
					<Avatar.Image src={owner.avatar_url} alt={owner.username} />
				{/if}
				<Avatar.Fallback class="text-xs">
					{owner.username.substring(0, 2).toUpperCase()}
				</Avatar.Fallback>
			</Avatar.Root>
		</Tooltip.Trigger>
		<Tooltip.Content>
			<p>{owner.username}</p>
		</Tooltip.Content>
	</Tooltip.Root>
{/if}
