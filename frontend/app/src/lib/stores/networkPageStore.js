import { writable, derived } from "svelte/store";

// Network selection state
export const selectedNetworkIds = writable(new Set());
export const compareMode = writable(false);
export const networksList = writable([]);
export const loadingNetworks = writable(true);

// Filter state
export const selectedCarriers = writable(new Set());
export const selectedCountries = writable(new Set());
export const showIndividualPlots = writable(true);
export const filtersPanelCollapsed = writable(false);

// Available options (populated from network data)
export const availableCarriers = writable([]);
export const availableCountries = writable([]);

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
export function toggleNetwork(networkId) {
  selectedNetworkIds.update((ids) => {
    const newIds = new Set(ids);
    if (newIds.has(networkId)) {
      newIds.delete(networkId);
    } else {
      newIds.add(networkId);
    }
    return newIds;
  });
}

export function selectNetwork(networkId) {
  selectedNetworkIds.set(new Set([networkId]));
}

export function clearSelection() {
  selectedNetworkIds.set(new Set());
}

export function toggleCompareMode() {
  compareMode.update((v) => !v);
}

export function setCompareMode(value) {
  compareMode.set(value);
}

export function toggleCarrier(carrier) {
  selectedCarriers.update((carriers) => {
    const newCarriers = new Set(carriers);
    if (newCarriers.has(carrier)) {
      newCarriers.delete(carrier);
    } else {
      newCarriers.add(carrier);
    }
    return newCarriers;
  });
}

export function toggleCountry(country) {
  selectedCountries.update((countries) => {
    const newCountries = new Set(countries);
    if (newCountries.has(country)) {
      newCountries.delete(country);
    } else {
      newCountries.add(country);
    }
    return newCountries;
  });
}

export function resetFilters() {
  selectedCarriers.set(new Set());
  selectedCountries.set(new Set());
  showIndividualPlots.set(false);
}

export function resetAll() {
  clearSelection();
  resetFilters();
  compareMode.set(false);
}
