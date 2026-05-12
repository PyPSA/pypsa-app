<script lang="ts">
	import { goto } from '$app/navigation';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import { NetworksListSkeleton } from '$lib/components/skeletons';
	import {
		networksList,
		loadingNetworks,
		selectedNetworkIds,
		selectNetwork,
	} from '$lib/stores/networkPageStore';

	function handleNetworkClick(networkId: string) {
		selectNetwork(networkId);
		goto(`/networks/${networkId}`);
	}
</script>

<Sidebar.Group class="flex-1 flex flex-col overflow-hidden">
	<Sidebar.GroupLabel>Networks</Sidebar.GroupLabel>
	<Sidebar.GroupContent class="flex-1 overflow-hidden">
		{#if $loadingNetworks}
			<NetworksListSkeleton />
		{:else if $networksList.length === 0}
			<div class="text-sm text-muted-foreground text-center py-4">No networks found</div>
		{:else}
			<Sidebar.Menu class="flex-1 overflow-y-auto">
				{#each $networksList as network}
					{@const isSelected = $selectedNetworkIds.has(network.id)}
					<Sidebar.MenuItem>
						<Sidebar.MenuButton isActive={isSelected}>
							{#snippet child({ props }: { props: Record<string, unknown> })}
								<a
									{...props}
									href="/networks/{network.id}"
									onclick={(e) => {
										// Allow new-tab / new-window opens to fall through to the
										// browser's default <a> behaviour — store will sync on the
										// new page's mount.
										if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
										e.preventDefault();
										handleNetworkClick(network.id);
									}}
								>
									<span>{network.filename}</span>
								</a>
							{/snippet}
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
				{/each}
			</Sidebar.Menu>
		{/if}
	</Sidebar.GroupContent>
</Sidebar.Group>
