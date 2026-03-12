<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import { Switch } from '$lib/components/ui/switch';
	import { Button } from '$lib/components/ui/button';
	import NetworksListSkeleton from './NetworksListSkeleton.svelte';
	import {
		networksList,
		loadingNetworks,
		selectedNetworkIds,
		compareMode,
		toggleNetwork,
		selectNetwork,
		clearSelection,
		toggleCompareMode
	} from '$lib/stores/networkPageStore';

	function handleNetworkClick(networkId: string, event: MouseEvent) {
		// Prevent default if clicking on checkbox
		if ((event.target as HTMLInputElement).type === 'checkbox') {
			return;
		}

		if ($compareMode) {
			// Toggle network in compare mode
			toggleNetwork(networkId);
			// Update URL with all selected network IDs
			const ids = Array.from($selectedNetworkIds);
			if (ids.length > 0) {
				goto(`/database/network?ids=${ids.join(',')}`);
			} else {
				goto('/database/network');
			}
		} else {
			// Select single network
			selectNetwork(networkId);
			goto(`/database/network?id=${networkId}`);
		}
	}

	function handleCheckboxChange(networkId: string) {
		toggleNetwork(networkId);
		// Update URL with all selected network IDs
		const ids = Array.from($selectedNetworkIds);
		if (ids.length > 0) {
			goto(`/database/network?ids=${ids.join(',')}`);
		} else {
			goto('/database/network');
		}
	}

	function handleClearSelection() {
		clearSelection();
		goto('/database/network');
	}
</script>

<Sidebar.Group class="flex-1 flex flex-col overflow-hidden">
	<Sidebar.GroupLabel>
		<div class="flex items-center justify-between w-full">
			<span>Networks</span>
			<div class="flex items-center gap-2">
				<span class="text-xs text-muted-foreground">Compare</span>
				<Switch checked={$compareMode} onCheckedChange={toggleCompareMode} class="scale-75" />
			</div>
		</div>
	</Sidebar.GroupLabel>
	<Sidebar.GroupContent class="flex-1 overflow-hidden">
		{#if $loadingNetworks}
			<NetworksListSkeleton />
		{:else if $networksList.length === 0}
			<div class="text-sm text-muted-foreground text-center py-4">No networks found</div>
		{:else}
			<div class="flex flex-col gap-2 h-full">
				<Sidebar.Menu class="flex-1 overflow-y-auto">
					{#each $networksList as network}
						{@const isSelected = $selectedNetworkIds.has(network.id)}
						<Sidebar.MenuItem>
							{#if $compareMode}
								<Sidebar.MenuButton isActive={isSelected}>
									{#snippet child({ props }: { props: Record<string, unknown> })}
										<button
											{...props}
											onclick={(e) => handleNetworkClick(network.id, e)}
										>
											<input
												type="checkbox"
												checked={isSelected}
												onchange={() => handleCheckboxChange(network.id)}
												class="w-3.5 h-3.5 rounded border-border shrink-0"
											/>
											<span>{network.filename}</span>
										</button>
									{/snippet}
								</Sidebar.MenuButton>
							{:else}
								<Sidebar.MenuButton isActive={isSelected}>
									{#snippet child({ props }: { props: Record<string, unknown> })}
										<a
											{...props}
											href="/database/network?id={network.id}"
											onclick={(e) => {
												e.preventDefault();
												handleNetworkClick(network.id, e);
											}}
										>
											<span>{network.filename}</span>
										</a>
									{/snippet}
								</Sidebar.MenuButton>
							{/if}
						</Sidebar.MenuItem>
					{/each}
				</Sidebar.Menu>

				{#if $compareMode && $selectedNetworkIds.size > 0}
					<Button variant="outline" size="sm" onclick={handleClearSelection} class="w-full">
						Clear Selection ({$selectedNetworkIds.size})
					</Button>
				{/if}
			</div>
		{/if}
	</Sidebar.GroupContent>
</Sidebar.Group>
