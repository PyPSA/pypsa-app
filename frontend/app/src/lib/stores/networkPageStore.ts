import { writable, derived } from "svelte/store";
import type { Network } from "$lib/types.js";

// Network selection state
export const selectedNetworkIds = writable<Set<string>>(new Set());
export const networksList = writable<Network[]>([]);
export const loadingNetworks = writable<boolean>(true);

// Derived state
export const selectedNetworks = derived(
  [networksList, selectedNetworkIds],
  ([$networksList, $selectedNetworkIds]) => {
    return $networksList.filter((network) =>
      $selectedNetworkIds.has(network.id),
    );
  },
);

export const hasSelection = derived(
  selectedNetworkIds,
  ($ids) => $ids.size > 0,
);

// Actions
export function selectNetwork(networkId: string): void {
  selectedNetworkIds.set(new Set([networkId]));
}

export function clearSelection(): void {
  selectedNetworkIds.set(new Set());
}
