<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy, tick } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { networks, plots } from '$lib/api/client.js';
	import type { Network as NetworkType, PlotData, PlotResponse, ApiError } from '$lib/types.js';
	import type { ViewConfig } from '$lib/types.js';
	import ComponentBrowser from './components/ComponentBrowser.svelte';
	import NetworkMap from './components/NetworkMap.svelte';
	import SaveViewDialog from './components/SaveViewDialog.svelte';
	import ViewSelector from './components/ViewSelector.svelte';
	import { formatFileSize, formatDate, formatRelativeTime, formatNumber, getDirectoryPath, getTagType, getTagColor } from '$lib/utils.js';
	import { Network, AlertCircle, FolderOpen, Clock, CalendarRange, Waypoints, ChevronLeft, ChevronRight, SlidersHorizontal, PanelRight } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import NavNetworkFilters from '$lib/components/sidebar/NavNetworkFilters.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Tabs from '$lib/components/ui/tabs';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import NetworkDetailSkeleton from './components/NetworkDetailSkeleton.svelte';
	import PlotSkeleton from './components/PlotSkeleton.svelte';

	import {
		networksList as networksListStore,
		loadingNetworks as loadingNetworksStore,
		selectedNetworkIds,
		compareMode as compareModeStore,
		selectedCarriers as selectedCarriersStore,
		selectedCountries as selectedCountriesStore,
		showIndividualPlots,
		availableCarriers as availableCarriersStore,
		availableCountries as availableCountriesStore,
		filtersPanelCollapsed as filtersPanelCollapsedStore,
		selectNetwork,
		setCompareMode
	} from '$lib/stores/networkPageStore';

	// Local interfaces for extended runtime data
	interface NetworkWithFacets extends Omit<NetworkType, 'dimensions_count' | 'components_count'> {
		dimensions_count?: Record<string, number>;
		components_count?: Record<string, number>;
		facets?: {
			carriers?: Record<string, { nice_name?: string; color?: string }>;
			countries?: string[];
		};
		meta?: {
			carriers?: Record<string, { nice_name?: string; color?: string }>;
			[key: string]: unknown;
		};
		file_hash?: string;
		[key: string]: unknown;
	}

	interface CarrierPlot {
		carrier: string;
		carrierName: string;
		plotData: PlotData;
	}

	interface ExtendedPlotData extends Record<string, unknown> {
		statistic?: string;
		plotType?: string;
		plot_data?: PlotData;
		cache_hit?: boolean;
		multiplePlots?: CarrierPlot[];
	}

	interface TabConfig {
		id: string;
		label: string;
		statistic: string;
		plotType: string;
		parameters: Record<string, unknown>;
	}

	// Props for layout
	let { children } = $props();

	let network = $state<NetworkWithFacets | null>(null);
	let selectedNetworks = $state<NetworkWithFacets[]>([]); // For compare mode - populated from network IDs
	let plotData = $state<ExtendedPlotData | null>(null);
	let loading = $state<boolean>(true);
	let loadingInfo = $state<boolean>(false); // For loading multiple networks
	let error = $state<string | null>(null);

	let loadingPlot = $state<boolean>(false);
	let plotDiv = $state<HTMLDivElement | undefined>();
	let Plotly = $state<any>();
	let activeTab = $state<string>('energy-balance-timeseries');
	let loadNetworkTimeout: ReturnType<typeof setTimeout>;
	let hashCopied = $state<boolean>(false);
	let updateHistoryExpanded = $state<boolean>(false);
	let resizeHandler: (() => void) | undefined;



	// Compare mode state - derived from URL and synced with store
	let compareMode = $state<boolean>(false);

	// Request tracking to prevent race conditions
	let plotRequestId = 0;
	let componentMounted = true;

	// Filter state - using stores, but keeping local references for backwards compatibility
	// Sync stores with local state using $derived
	let selectedCarriers = $derived<string[]>(Array.from($selectedCarriersStore));
	let selectedCountries = $derived<string[]>(Array.from($selectedCountriesStore));
	let individualPlots = $derived<boolean>($showIndividualPlots);

	// Track previous filter state to avoid infinite loops
	let lastFilterState = '';
	let isLoadingInitial = false;

	// Merged facets from all selected networks (for compare mode)
	let mergedCarriers: Record<string, any> = {};
	let mergedCountries: string[] = [];

	// Get network ID(s) from URL params
	let networkId = $derived($page.url.searchParams.get('id'));
	let networkIds = $derived($page.url.searchParams.get('ids')?.split(',').filter(Boolean) || []);

	// Set breadcrumb to show network name
	const breadcrumbLabel = $derived(network?.filename || (compareMode ? 'Compare' : 'Network'));
	$effect(() => {
		breadcrumbStore.set([{ label: breadcrumbLabel }]);
	});


	// Determine if we're in compare mode based on URL - check for 'ids' param existence
	$effect(() => {
		if (browser) {
			compareMode = $page.url.searchParams.has('ids');
		}
	});

	// Sync URL params with store selection
	$effect(() => {
		if (browser) {
			if (compareMode && networkIds.length > 0) {
				// Sync compare mode IDs and store
				selectedNetworkIds.set(new Set(networkIds));
				compareModeStore.set(true);
			} else if (!compareMode && networkId) {
				// Sync single mode ID and store
				selectedNetworkIds.set(new Set([networkId]));
				compareModeStore.set(false);
			}
		}
	});

	// Watch for compare mode toggle from store and update URL
	$effect(() => {
		if (browser) {
			const storeCompareMode = $compareModeStore;
			const currentIds = Array.from($selectedNetworkIds);

			// If compare mode is toggled on and we're currently in single network mode
			if (storeCompareMode && !compareMode && networkId && currentIds.length > 0) {
				// Convert from ?id=xxx to ?ids=xxx
				const idsParam = currentIds.join(',');
				goto(`/database/network?ids=${idsParam}`, { replaceState: false });
			}
			// If compare mode is toggled off and we're in compare mode
			else if (!storeCompareMode && compareMode && currentIds.length > 0) {
				// Convert from ?ids=xxx to ?id=xxx (use first network)
				goto(`/database/network?id=${currentIds[0]}`, { replaceState: false });
			}
		}
	});

	// Auto-reload plot when filters change (debounced)
	let filterUpdateTimeout: ReturnType<typeof setTimeout>;
	$effect(() => {
		// Create a fingerprint of current filter state
		const currentFilterState = JSON.stringify([selectedCarriers, selectedCountries, individualPlots, activeTab, compareMode ? networkIds : networkId]);

		// Only update if filters actually changed and we're not in initial load
		// Check for network data in both single mode (network) and compare mode (selectedNetworks)
		const hasNetworkData = compareMode ? selectedNetworks.length > 0 : !!network;
		if (browser && hasNetworkData && Plotly && activeTab && selectedCarriers.length > 0 && currentFilterState !== lastFilterState && !isLoadingInitial) {
			lastFilterState = currentFilterState;
			// Cancel any pending plot updates
			clearTimeout(filterUpdateTimeout);
			filterUpdateTimeout = setTimeout(() => {
				const activeTabConfig = tabs.find(t => t.id === activeTab);
				if (activeTabConfig && componentMounted) {
					loadPlotsForCarriers();
				}
			}, 500); // Increased debounce to 500ms
		}
	});

	// Reload network(s) when ID(s) change (with debouncing)
	$effect(() => {
		if (browser) {
			if (compareMode && networkIds.length > 0) {
				clearTimeout(loadNetworkTimeout);
				loadNetworkTimeout = setTimeout(() => {
					loadSelectedNetworks();
				}, 200);
			} else if (!compareMode && networkId) {
				clearTimeout(loadNetworkTimeout);
				loadNetworkTimeout = setTimeout(() => {
					loadNetwork();
				}, 200);
			}
		}
	});

	// Tab configuration with statistic and plot type
	// Note: x, y, stacked parameters omitted - let PyPSA use its defaults
	const tabs: TabConfig[] = [
		{
			id: 'energy-balance-timeseries',
			label: 'Energy Balance Timeseries',
			statistic: 'energy_balance',
			plotType: 'area',
			parameters: {}
		},
		{
			id: 'energy-balance-totals',
			label: 'Energy Balance Totals',
			statistic: 'energy_balance',
			plotType: 'bar',
			parameters: {}
		},
		{
			id: 'capacity-totals',
			label: 'Capacity Totals',
			statistic: 'installed_capacity',
			plotType: 'bar',
			parameters: {}
		},
		{
			id: 'capex-totals',
			label: 'CAPEX Totals',
			statistic: 'capex',
			plotType: 'bar',
			parameters: {}
		},
		{
			id: 'opex-totals',
			label: 'OPEX Totals',
			statistic: 'opex',
			plotType: 'bar',
			parameters: {}
		}
	];

	onMount(async () => {
		// Load networks list for sidebar
		await loadNetworksList();

		// Load Plotly first (needed for both single and compare mode)
		if (browser) {
			Plotly = await import('plotly.js-dist');

			// Add resize handler for responsive plots
			resizeHandler = () => {
				if (Plotly && componentMounted) {
					// Resize single merged plot
					if (plotDiv && document.body.contains(plotDiv)) {
						try {
							Plotly.Plots.resize(plotDiv);
						} catch (err: unknown) {
							console.warn('Error resizing single plot on window resize:', err);
						}
					}

					// Resize all individual plots
					if (plotData?.multiplePlots) {
						plotData.multiplePlots.forEach((plot: CarrierPlot, index: number) => {
							const plotElement = document.getElementById(`plot-${index}`);
							if (plotElement && document.body.contains(plotElement)) {
								try {
									Plotly.Plots.resize(plotElement);
								} catch (err: unknown) {
									console.warn(`Error resizing plot-${index} on window resize:`, err);
								}
							}
						});
					}
				}
			};
			window.addEventListener('resize', resizeHandler);
		}

		// Network loading is handled by the $effect that watches networkId/networkIds changes
		// Set initial loading state if no network is selected
		if (!networkId && (!networkIds || networkIds.length === 0)) {
			loading = false;
		}
	});

	async function loadNetworksList() {
		loadingNetworksStore.set(true);
		try {
			const response = await networks.list();

			networksListStore.set(response.data);
			loadingNetworksStore.set(false);

			// Auto-select first network if no network is currently selected and no URL params
			const hasUrlParams = $page.url.searchParams.has('id') || $page.url.searchParams.has('ids');
			if (browser && !hasUrlParams && response.data.length > 0) {
				const firstNetworkId = response.data[0].id;
				goto(`/database/network?id=${firstNetworkId}`);
			}
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) {
				loadingNetworksStore.set(false);
				return;
			}
			console.error('Failed to load networks list:', err);
			loadingNetworksStore.set(false);
		}
	}

	async function loadNetwork() {
		if (!networkId) return;

		loading = true;
		error = null;
		plotData = null;

		try {
			network = await networks.get(networkId) as NetworkWithFacets;
			loading = false;

			// Reset filters when loading a new network
			resetFiltersState();

			// Set active tab (reactive statement will trigger plot load)
			activeTab = tabs[0].id;

		} catch (err: unknown) {
			console.error('Error loading network:', err);
			error = (err as Error).message;
			loading = false;
		}
	}

	async function loadSelectedNetworks() {
		if (!networkIds || networkIds.length === 0) {
			selectedNetworks = [];
			mergedCarriers = {};
			mergedCountries = [];
			plotData = null;
			return;
		}

		loadingInfo = true;
		loading = false;
		error = null;

		try {
			// Get individual network info
			const networkPromises = networkIds.map(id => networks.get(id));
			selectedNetworks = await Promise.all(networkPromises) as NetworkWithFacets[];

			// Merge facets from all networks
			mergeFacets();

			loadingInfo = false;

			// Reset filters when loading new networks
			resetFiltersStateForComparison();

			// Set active tab (reactive statement will trigger plot load)
			activeTab = tabs[0].id;
		} catch (err: unknown) {
			console.error('Error loading networks:', err);
			error = (err as Error).message;
			loadingInfo = false;
		}
	}

	function mergeFacets() {
		// Merge carriers from all networks
		mergedCarriers = {};
		mergedCountries = [];

		selectedNetworks.forEach(network => {
			// Merge carriers
			if (network?.facets?.carriers) {
				Object.entries(network.facets.carriers).forEach(([key, value]) => {
					if (!mergedCarriers[key]) {
						mergedCarriers[key] = value;
					}
				});
			}

			// Merge countries
			if (network?.facets?.countries) {
				network.facets.countries.forEach(country => {
					if (!mergedCountries.includes(country)) {
						mergedCountries.push(country);
					}
				});
			}
		});

		// Sort merged countries
		mergedCountries.sort();
	}

	function resetFiltersStateForComparison() {
		isLoadingInitial = true;

		// Save current selections to preserve when switching modes
		const currentCarriers = new Set($selectedCarriersStore);
		const currentCountries = new Set($selectedCountriesStore);

		// Update available carriers/countries in store for sidebar
		if (mergedCarriers && Object.keys(mergedCarriers).length > 0) {
			const carriersArray = Object.entries(mergedCarriers).map(([name, data]) => ({
				name,
				nice_name: data.nice_name || name
			}));
			availableCarriersStore.set(carriersArray);
		} else {
			availableCarriersStore.set([]);
		}

		if (mergedCountries && mergedCountries.length > 0) {
			availableCountriesStore.set([...mergedCountries]);
		} else {
			availableCountriesStore.set([]);
		}

		// Preserve existing selections if they're still valid, otherwise use defaults
		const defaultCarriers = ['AC', 'Hydrogen Storage', 'Low Voltage'];
		if (mergedCarriers && Object.keys(mergedCarriers).length > 0) {
			const availableCarriers = Object.keys(mergedCarriers);

			// Try to preserve existing selections
			const preservedCarriers = Array.from(currentCarriers).filter(c => availableCarriers.includes(c));

			if (preservedCarriers.length > 0) {
				// Keep existing selections that are still available
				selectedCarriersStore.set(new Set(preservedCarriers));
			} else {
				// No existing selections or none are valid, use defaults
				const selectedCarriersArray = defaultCarriers.filter(c => availableCarriers.includes(c));
				if (selectedCarriersArray.length === 0 && availableCarriers.length > 0) {
					selectedCarriersStore.set(new Set([availableCarriers[0]]));
				} else {
					selectedCarriersStore.set(new Set(selectedCarriersArray));
				}
			}
		} else {
			selectedCarriersStore.set(new Set());
		}

		// Preserve existing country selections or select all by default
		if (mergedCountries && mergedCountries.length > 0) {
			const preservedCountries = Array.from(currentCountries).filter(c => mergedCountries.includes(c));

			if (preservedCountries.length > 0) {
				// Keep existing selections that are still available
				selectedCountriesStore.set(new Set(preservedCountries));
			} else {
				// No existing selections, select all by default
				selectedCountriesStore.set(new Set(mergedCountries));
			}
		} else {
			selectedCountriesStore.set(new Set());
		}

		// Allow reactive updates and trigger initial plot load
		setTimeout(() => {
			// Set filter state AFTER setting isLoadingInitial to prevent reactive trigger
			isLoadingInitial = false;
			lastFilterState = JSON.stringify([selectedCarriers, selectedCountries, individualPlots, activeTab, networkIds]);

			// Trigger initial plot load (only if Plotly is loaded)
			if (selectedCarriers.length > 0 && Plotly) {
				loadPlotsForCarriers();
			} else if (selectedCarriers.length > 0 && !Plotly) {
				// Plotly not loaded yet, wait a bit and try again
				const checkPlotly = setInterval(() => {
					if (Plotly) {
						clearInterval(checkPlotly);
						loadPlotsForCarriers();
					}
				}, 100);
			} else {
				loadingPlot = false;
			}
		}, 100);
	}

	function resetFiltersState() {
		// Prevent reactive updates during initial setup
		isLoadingInitial = true;

		// Save current selections to preserve when switching modes
		const currentCarriers = new Set($selectedCarriersStore);
		const currentCountries = new Set($selectedCountriesStore);

		// Update available carriers/countries in store for sidebar
		if (network?.facets?.carriers) {
			const carriersArray = Object.entries(network.facets.carriers).map(([name, data]) => ({
				name,
				nice_name: data.nice_name || name
			}));
			availableCarriersStore.set(carriersArray);
		} else {
			availableCarriersStore.set([]);
		}

		if (network?.facets?.countries && network.facets.countries.length > 0) {
			availableCountriesStore.set([...network.facets.countries]);
		} else {
			availableCountriesStore.set([]);
		}

		// Preserve existing selections if they're still valid, otherwise use defaults
		const defaultCarriers = ['AC', 'Hydrogen Storage', 'Low Voltage'];
		if (network?.facets?.carriers) {
			const availableCarriers = Object.keys(network.facets.carriers);

			// Try to preserve existing selections
			const preservedCarriers = Array.from(currentCarriers).filter(c => availableCarriers.includes(c));

			if (preservedCarriers.length > 0) {
				// Keep existing selections that are still available
				selectedCarriersStore.set(new Set(preservedCarriers));
			} else {
				// No existing selections or none are valid, use defaults
				const selectedCarriersArray = defaultCarriers.filter(c => availableCarriers.includes(c));
				if (selectedCarriersArray.length === 0 && availableCarriers.length > 0) {
					selectedCarriersStore.set(new Set([availableCarriers[0]]));
				} else {
					selectedCarriersStore.set(new Set(selectedCarriersArray));
				}
			}
		} else {
			selectedCarriersStore.set(new Set());
		}

		// Preserve existing country selections or select all by default
		if (network?.facets?.countries && network.facets.countries.length > 0) {
			const preservedCountries = Array.from(currentCountries).filter(c => network!.facets!.countries!.includes(c));

			if (preservedCountries.length > 0) {
				// Keep existing selections that are still available
				selectedCountriesStore.set(new Set(preservedCountries));
			} else {
				// No existing selections, select all by default
				selectedCountriesStore.set(new Set(network.facets.countries));
			}
		} else {
			selectedCountriesStore.set(new Set());
		}

		// Allow reactive updates and trigger initial plot load
		setTimeout(() => {
			// Set filter state AFTER setting isLoadingInitial to prevent reactive trigger
			isLoadingInitial = false;
			// Update lastFilterState to match what reactive statement will compute
			lastFilterState = JSON.stringify([selectedCarriers, selectedCountries, individualPlots, activeTab, networkId]);

			// Trigger initial plot load (only if Plotly is loaded)
			if (selectedCarriers.length > 0 && Plotly) {
				loadPlotsForCarriers();
			} else if (selectedCarriers.length > 0 && !Plotly) {
				// Plotly not loaded yet, wait a bit and try again
				const checkPlotly = setInterval(() => {
					if (Plotly) {
						clearInterval(checkPlotly);
						loadPlotsForCarriers();
					}
				}, 100);
			} else {
				// No carriers available, stop loading
				loadingPlot = false;
			}
		}, 100);
	}

	function switchNetwork(newNetworkId: string) {
		if (compareMode) {
			// In compare mode, clicking should toggle selection
			toggleNetworkSelection(newNetworkId);
		} else {
			// In single mode, switch to that network
			goto(`/database/network?id=${newNetworkId}`);
		}
	}

	function toggleNetworkSelection(networkId: string) {
		const currentIds = networkIds || [];
		let newIds: string[];

		if (currentIds.includes(networkId)) {
			newIds = currentIds.filter(id => id !== networkId);
		} else {
			newIds = [...currentIds, networkId];
		}

		updateURL(newIds);
	}

	function toggleCompareMode() {
		if (!compareMode) {
			// Switching to compare mode
			if (networkId) {
				// Convert current single network to multi-select
				goto(`/database/network?ids=${networkId}`);
			} else {
				// No network selected, just enable compare mode with empty selection
				goto('/database/network?ids=');
			}
		} else {
			// Switching to single mode
			if (networkIds.length > 0) {
				// Keep only first network
				goto(`/database/network?id=${networkIds[0]}`);
			} else {
				// No networks selected, just disable compare mode
				goto('/database/network');
			}
		}
	}

	function clearSelection() {
		updateURL([]);
		selectedNetworks = [];
		plotData = null;
	}

	function updateURL(ids: string[]) {
		if (ids.length === 0 && compareMode) {
			// Keep compare mode active even with no selection
			goto('/database/network?ids=');
		} else if (ids.length === 0) {
			// Single mode with no selection
			goto('/database/network');
		} else if (ids.length === 1 && !compareMode) {
			// Single mode with one network
			goto(`/database/network?id=${ids[0]}`);
		} else {
			// Compare mode with one or more networks
			goto(`/database/network?ids=${ids.join(',')}`);
		}
	}

	onDestroy(() => {
		componentMounted = false;
		breadcrumbStore.clear();
		if (browser && resizeHandler) {
			window.removeEventListener('resize', resizeHandler);
		}
		// Clean up pending network load timeout
		clearTimeout(loadNetworkTimeout);
		clearTimeout(filterUpdateTimeout);
	});

async function loadPlot(statistic: string, plotType: string, parameters: Record<string, unknown> = {}) {
		// Increment request ID to invalidate any previous in-flight requests
		const currentRequestId = ++plotRequestId;

		loadingPlot = true;
		try {
			// Use networkIds for compare mode, networkId for single mode
			const ids = compareMode ? networkIds : networkId!;
			const response = await plots.generate(ids, statistic, plotType, parameters);

			// Check if this request is still valid (not superseded by a newer request)
			if (currentRequestId !== plotRequestId || !componentMounted) {
				return;
			}

			plotData = { statistic, plotType, ...response };
			loadingPlot = false;

			// Wait for Svelte to update DOM, then render plot
			await tick();

			// Check again if request is still valid
			if (currentRequestId !== plotRequestId || !componentMounted) {
				return;
			}

			// Wait up to 1 second for plotDiv to be bound
			let attempts = 0;
			while (!plotDiv && attempts < 20 && currentRequestId === plotRequestId && componentMounted) {
				await new Promise(resolve => setTimeout(resolve, 50));
				attempts++;
			}

			// Final check before proceeding
			if (currentRequestId !== plotRequestId || !componentMounted) {
				return;
			}


			if (plotDiv && response.plot_data && Plotly) {
				// Check if container has dimensions - retry up to 1 second
				let rect = plotDiv.getBoundingClientRect();
				attempts = 0;
				while ((rect.width === 0 || rect.height === 0) && attempts < 10 && currentRequestId === plotRequestId && componentMounted) {
					console.warn('Plot container has no dimensions, waiting...');
					await new Promise(resolve => setTimeout(resolve, 100));
					rect = plotDiv.getBoundingClientRect();
					attempts++;
				}

				// Final check before rendering
				if (currentRequestId !== plotRequestId || !componentMounted) {
					return;
				}

				if (rect.width === 0 || rect.height === 0) {
					console.error('Plot container still has no dimensions after waiting', rect);
					return;
				}


				// Final element existence check right before rendering
				if (!plotDiv || !document.body.contains(plotDiv)) {
					console.error('plotDiv no longer exists in DOM, aborting render');
					return;
				}

				// Validate plot data exists
				if (!response.plot_data || !response.plot_data.data) {
					console.error('Invalid plot data, aborting render');
					toast.error('Plot data is missing or invalid');
					return;
				}

				// Cleanup existing plot if any (prevents memory leaks and rendering conflicts)
				if ((plotDiv as any)._plotly) {
					try {
						Plotly.purge(plotDiv);
					} catch (purgeErr: unknown) {
						console.warn('Plotly.purge warning:', purgeErr);
					}
				}

				// Ensure layout uses full width - don't set explicit width, use autosize
				const layout = {
					...(response.plot_data.layout as Record<string, unknown>),
					autosize: true,
					width: undefined,  // Remove any explicit width to allow full responsive behavior
					height: undefined,  // Remove any explicit height too
					margin: { l: 60, r: 30, t: 30, b: 60 }
				};

				try {
					// Final guard: verify element still valid and request not superseded
					if (!plotDiv || !document.body.contains(plotDiv) || currentRequestId !== plotRequestId || !componentMounted) {
						return;
					}

					// response.plot_data is the full Plotly figure JSON
					Plotly.newPlot(plotDiv, response.plot_data.data, layout, {
						responsive: true,
						displayModeBar: true,
						displaylogo: false
					});

					// Force a resize to ensure full width after plot is created
					await new Promise(resolve => setTimeout(resolve, 100));
					// Check element still exists before resizing
					if (plotDiv && document.body.contains(plotDiv) && currentRequestId === plotRequestId && componentMounted) {
						Plotly.Plots.resize(plotDiv);
					}
				} catch (plotlyErr: unknown) {
					console.error('Plotly.newPlot error:', plotlyErr);
					toast.error(`Failed to render plot: ${(plotlyErr as Error).message}`);
				}
			} else {
				console.error('Missing plot data or Plotly:', {
					plotDiv: !!plotDiv,
					plotData: !!response?.plot_data,
					Plotly: !!Plotly
				});
			}
		} catch (err: unknown) {
			// Only handle error if this is still the current request
			if (currentRequestId === plotRequestId) {
				if ((err as ApiError).cancelled) {
					loadingPlot = false;
					return;
				}
				toast.error((err as Error).message);
				loadingPlot = false;
				plotData = null; // Clear old plot data when error occurs
			}
		}
	}

	function getComponentCount(component: string, fallback: string[] = [], net: NetworkWithFacets | null = null) {
		const mapping = (net || network)?.components_count;
		if (!mapping) return 0;
		const keys = [component, ...fallback];
		for (const key of keys) {
			if (key in mapping) {
				return mapping[key] ?? 0;
			}
		}
		return 0;
	}
	function getRelativePath(fullPath: string) {
		if (!fullPath) return '';
		// Remove /data/networks prefix if present
		if (fullPath.includes('/data/networks/')) {
			return fullPath.split('/data/networks/')[1] || fullPath;
		} else if (fullPath.includes('/networks/')) {
			return fullPath.split('/networks/')[1] || fullPath;
		}
		return fullPath;
	}

	async function copyToClipboard(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			hashCopied = true;
			setTimeout(() => {
				hashCopied = false;
			}, 2000);
		} catch (err: unknown) {
			console.error('Failed to copy to clipboard:', err);
		}
	}

	function buildCurrentViewConfig(): ViewConfig {
		return {
			active_tab: activeTab,
			statistic: tabs.find(t => t.id === activeTab)?.statistic,
			plot_type: tabs.find(t => t.id === activeTab)?.plotType,
			selected_carriers: selectedCarriers,
			selected_countries: selectedCountries,
			individual_plots: individualPlots,
			analysis_type: undefined,
			analysis_parameters: {},
			selected_component: undefined,
			component_columns: undefined,
			compare_network_ids: compareMode ? networkIds : [],
			extra: {},
		};
	}

	function handleLoadView(config: ViewConfig) {
		// Apply carriers
		if (config.selected_carriers?.length > 0) {
			selectedCarriersStore.set(new Set(config.selected_carriers));
		}
		// Apply countries
		if (config.selected_countries?.length > 0) {
			selectedCountriesStore.set(new Set(config.selected_countries));
		}
		// Apply individual plots
		if (config.individual_plots !== undefined) {
			showIndividualPlots.set(config.individual_plots);
		}
		// Apply tab
		if (config.active_tab) {
			activeTab = config.active_tab;
		}
	}

	function buildFilterParameters(tabConfig: TabConfig, carriers: string[]) {
		const params: Record<string, unknown> = {
			...tabConfig.parameters
		};

		// Add bus_carrier parameter for energy balance (PyPSA parameter name)
		if (carriers && carriers.length > 0) {
			params.bus_carrier = carriers;
		}

		// Add country filter ONLY if not all countries are selected
		// Use the appropriate country list based on mode
		const allCountries = compareMode ? mergedCountries : (network?.facets?.countries || []);
		if (selectedCountries.length > 0 && selectedCountries.length < allCountries.length) {
			// Format: "country in ['DE', 'FR']"
			const formattedCountries = selectedCountries.map(c => `'${c}'`).join(', ');
			params.query = `country in [${formattedCountries}]`;
		}
		// If all countries selected: don't add query (PyPSA-Explorer behavior)

		return params;
	}

	async function loadPlotsForCarriers() {
		if (!selectedCarriers || selectedCarriers.length === 0) {
			return;
		}

		const activeTabConfig = tabs.find(t => t.id === activeTab);
		if (!activeTabConfig) return;

		// Increment request ID to invalidate any previous in-flight requests
		const currentRequestId = ++plotRequestId;


		try {
			if (individualPlots) {
				// Create separate plots for each carrier (stacked)
				loadingPlot = true;

				const carrierPlots: CarrierPlot[] = [];
				for (const carrier of selectedCarriers) {
					// Check if request is still valid before each carrier
					if (currentRequestId !== plotRequestId || !componentMounted) {
						return;
					}

					try {
						// Build parameters for single carrier
						const parameters = buildFilterParameters(activeTabConfig, [carrier]);

						// Generate plot for this carrier (use appropriate IDs based on mode)
						const ids = compareMode ? networkIds : networkId!;
						const response = await plots.generate(ids, activeTabConfig.statistic, activeTabConfig.plotType, parameters);

						// Check again after async operation
						if (currentRequestId !== plotRequestId || !componentMounted) {
							return;
						}

						// Get carrier name from appropriate source
						const carrierInfo = compareMode ? mergedCarriers : network?.meta?.carriers;
						carrierPlots.push({
							carrier,
							carrierName: carrierInfo?.[carrier]?.nice_name || carrier,
							plotData: response.plot_data
						});
					} catch (err: unknown) {
						console.error(`Failed to generate plot for carrier ${carrier}:`, err);
					}
				}

				// Final check before setting plot data
				if (currentRequestId !== plotRequestId || !componentMounted) {
					return;
				}

				// Store multiple plots
				plotData = {
					statistic: activeTabConfig.statistic,
					plotType: activeTabConfig.plotType,
					multiplePlots: carrierPlots
				};
				loadingPlot = false;

				// Wait for Svelte to update DOM before rendering plots
				await tick();
				await new Promise(resolve => setTimeout(resolve, 50));

				// Check again before rendering
				if (currentRequestId !== plotRequestId || !componentMounted) {
					return;
				}

				if (Plotly) {
					for (let index = 0; index < carrierPlots.length; index++) {
						// Check for each plot
						if (currentRequestId !== plotRequestId || !componentMounted) {
							return;
						}

						const plot = carrierPlots[index];
						const plotDivId = `plot-${index}`;

						// Wait for element to be available
						let plotElement = document.getElementById(plotDivId);
						let attempts = 0;
						while (!plotElement && attempts < 20 && currentRequestId === plotRequestId && componentMounted) {
							await new Promise(resolve => setTimeout(resolve, 50));
							plotElement = document.getElementById(plotDivId);
							attempts++;
						}

						// Check after waiting
						if (currentRequestId !== plotRequestId || !componentMounted) {
							return;
						}

						if (plotElement && plot.plotData) {
							// Check if container has dimensions - retry up to 1 second
							let rect = plotElement.getBoundingClientRect();
							attempts = 0;
							while ((rect.width === 0 || rect.height === 0) && attempts < 10 && currentRequestId === plotRequestId && componentMounted) {
								console.warn(`Plot container ${plotDivId} has no dimensions, waiting...`);
								await new Promise(resolve => setTimeout(resolve, 100));
								rect = plotElement.getBoundingClientRect();
								attempts++;
							}

							// Check after dimension wait
							if (currentRequestId !== plotRequestId || !componentMounted) {
								return;
							}

							if (rect.width === 0 || rect.height === 0) {
								console.error(`Plot container ${plotDivId} still has no dimensions after waiting`);
								continue;
							}

							// Final element existence check right before rendering
							if (!plotElement || !document.body.contains(plotElement)) {
								console.error(`${plotDivId} no longer exists in DOM, skipping render`);
								continue;
							}

							// Use autosize without explicit width/height for responsive behavior
							const layout = {
								...(plot.plotData.layout as Record<string, unknown>),
								autosize: true,
								width: undefined,  // Remove explicit width
								height: undefined,  // Remove explicit height
								margin: { l: 60, r: 30, t: 40, b: 60 },
								title: plot.carrierName
							};

							try {
								Plotly.newPlot(plotElement, plot.plotData.data, layout, {
									responsive: true,
									displayModeBar: true,
									displaylogo: false
								});

								// Resize after initial render
								await new Promise(resolve => setTimeout(resolve, 50));
								// Check element still exists before resizing
								if (plotElement && document.body.contains(plotElement) && currentRequestId === plotRequestId && componentMounted) {
									Plotly.Plots.resize(plotElement);
								}
							} catch (plotlyErr: unknown) {
								console.error(`Plotly.newPlot error for ${plotDivId}:`, plotlyErr);
							}
						}
					}
				}
			} else {
				// Merge all carriers into a single plot (combined)
				const parameters = buildFilterParameters(activeTabConfig, selectedCarriers);
				await loadPlot(activeTabConfig.statistic, activeTabConfig.plotType, parameters);
			}
		} catch (err: unknown) {
			console.error('Error in loadPlotsForCarriers:', err);
			// Only handle error if this is still the current request
			if (currentRequestId === plotRequestId) {
				if ((err as ApiError).cancelled) {
					loadingPlot = false;
					return;
				}
				toast.error((err as Error).message);
				loadingPlot = false;
				plotData = null; // Clear old plot data when error occurs
			}
		}
	}

	function resetFilters() {
		resetFiltersState();
	}
</script>

<style>
	/* Ensure Plotly plots use full width */
	:global(.js-plotly-plot) {
		width: 100% !important;
	}

	:global(.plotly) {
		width: 100% !important;
	}

	:global(.plot-container) {
		width: 100% !important;
	}

	:global(.svg-container) {
		width: 100% !important;
	}
</style>

{#if compareMode && networkIds.length === 0}
			<div class="flex items-center justify-center h-full w-full">
				<div class="text-center">
					<Network size={64} class="mx-auto mb-4 text-muted-foreground" strokeWidth={1.5} />
					<h2 class="text-2xl font-bold mb-2">Select Networks for Comparison</h2>
					<p class="text-muted-foreground">
						Choose one or more networks from the sidebar to compare their statistics and plots
					</p>
				</div>
			</div>
		{:else if compareMode && loadingInfo}
			<NetworkDetailSkeleton />
		{:else if compareMode && error}
			<div class="flex items-center justify-center h-full w-full">
				<div class="text-center">
					<AlertCircle size={64} class="mx-auto mb-4 text-destructive" strokeWidth={1.5} />
					<h2 class="text-2xl font-bold mb-2">Error Loading Networks</h2>
					<p class="text-muted-foreground mb-4">{error}</p>
				</div>
			</div>
		{:else if compareMode && selectedNetworks.length > 0}
			<div class="flex gap-6">
				<!-- Main Content -->
				<div class="flex-1 min-w-0">
					<!-- Compare View -->
					<!-- Header -->
					<div class="mb-8">
					<h1 class="text-3xl font-bold mb-2">Network Comparison</h1>
					<p class="text-muted-foreground">{selectedNetworks.length} network{selectedNetworks.length > 1 ? 's' : ''} selected</p>
				</div>

				<!-- Networks Overview -->
				<div class="bg-card rounded-lg border border-border p-6 mb-8">
					<h2 class="text-xl font-semibold mb-4">Selected Networks</h2>
					<div class="space-y-3">
						{#each selectedNetworks as net}
							<div class="border-b border-border/50 pb-3 last:border-b-0">
								<div class="flex items-center justify-between mb-2">
									<h3 class="font-semibold">{net.filename}</h3>
									<span class="text-xs text-muted-foreground">{formatFileSize(net.file_size)}</span>
								</div>
								<div class="grid grid-cols-2 gap-4 text-sm">
									<div>
										<span class="text-muted-foreground">Components:</span>
										<span class="ml-2 font-medium">
											{#if net.components_count && Object.keys(net.components_count).length > 0}
												{Object.keys(net.components_count).length} types
											{:else}
												N/A
											{/if}
										</span>
									</div>
									{#if net.dimensions_count}
										<div>
											<span class="text-muted-foreground">Timesteps:</span>
											<span class="ml-2 font-medium">{net.dimensions_count.timesteps || 0}</span>
										</div>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				</div>

				<!-- Plots Section (reuse existing plot rendering) -->
				<div class="w-full bg-card rounded-lg border border-border p-6">
					<h2 class="text-xl font-semibold mb-6">Plots & Statistics</h2>

					<!-- Tab Navigation -->
					<Tabs.Root bind:value={activeTab} class="mb-6">
						<Tabs.List>
							{#each tabs as tab}
								<Tabs.Trigger value={tab.id} disabled={loadingPlot}>
									{tab.label}
								</Tabs.Trigger>
							{/each}
						</Tabs.List>
					</Tabs.Root>

					<!-- Plot Content (shared with single mode) -->
					{#if loadingPlot}
						{#if individualPlots && selectedCarriers.length > 1}
							<div class="space-y-6">
								{#each selectedCarriers.slice(0, 3) as carrier, i}
									<PlotSkeleton title={carrier} />
								{/each}
							</div>
						{:else}
							<PlotSkeleton />
						{/if}
					{:else if plotData?.plot_data || plotData?.multiplePlots}
						<div class="w-full space-y-6">
							{#if plotData.cache_hit}
								<div class="flex justify-end mb-2">
									<span class="text-xs bg-green-600 text-white px-2 py-1 rounded">Cached</span>
								</div>
							{/if}

							{#if plotData.multiplePlots && plotData.multiplePlots.length > 0}
								{#each plotData.multiplePlots as plot, index}
									<div class="w-full">
										<h3 class="text-lg font-semibold mb-3">{plot.carrierName}</h3>
										<div class="w-full rounded-lg border-2 border-border/50 shadow-md overflow-hidden bg-white h-[500px]">
											<div
												id="plot-{index}"
												class="w-full h-full"
											></div>
										</div>
									</div>
								{/each}
							{:else}
								{#key (plotData.statistic ?? '') + (plotData.plotType ?? '') + (plotData.cache_hit || '')}
									<div class="w-full rounded-lg border-2 border-border/50 shadow-md overflow-hidden bg-white h-[500px]">
										<div bind:this={plotDiv} class="w-full h-full"></div>
									</div>
								{/key}
							{/if}
						</div>
					{:else if plotData && !plotData.plot_data && !plotData.multiplePlots}
						<div class="text-center py-12">
							<div class="bg-yellow-50 border border-yellow-300 text-yellow-800 px-4 py-3 rounded-lg inline-block">
								<div class="font-semibold mb-2">Invalid Plot Data</div>
								<p class="text-sm">The plot data received is incomplete or invalid.</p>
							</div>
						</div>
					{:else}
						<div class="text-center py-12">
							<div class="flex flex-col items-center gap-3">
								<svg class="w-16 h-16 text-muted-foreground/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
								</svg>
								<p class="text-muted-foreground">Select carriers and filters to generate a plot</p>
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Filters Panel -->
			<div class="shrink-0 transition-all duration-300 ease-in-out {$filtersPanelCollapsedStore ? 'w-0' : 'w-80'}">
				<div class="sticky top-4">
					{#if !$filtersPanelCollapsedStore}
						<!-- Expanded state - full filters panel matching sidebar style -->
						<div class="bg-sidebar border-l border-sidebar-border h-full rounded-l-lg overflow-hidden shadow-sm">
							<!-- Header matching sidebar header -->
							<div class="flex h-14 items-center border-b border-sidebar-border px-4 bg-sidebar">
								<div class="flex items-center gap-2">
									<SlidersHorizontal size={16} class="text-sidebar-foreground" />
									<h3 class="font-semibold text-sm text-sidebar-foreground">Filters & Options</h3>
								</div>
							</div>
							<!-- Content -->
							<div class="p-4 bg-sidebar">
								<NavNetworkFilters />
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>
		{:else if loading && !network}
			<NetworkDetailSkeleton />
		{:else if error && !network}
			<div class="flex items-center justify-center h-full w-full">
				<div class="text-center">
					<AlertCircle size={64} class="mx-auto mb-4 text-destructive" strokeWidth={1.5} />
					<h2 class="text-2xl font-bold mb-2">Error Loading Network</h2>
					<p class="text-muted-foreground">{error}</p>
				</div>
			</div>
		{:else if !networkId && !compareMode}
		<!-- Empty state for single mode with no networks available -->
		<div class="flex items-center justify-center h-full w-full">
			<div class="text-center">
				<Network size={64} class="mx-auto mb-4 text-muted-foreground" strokeWidth={1.5} />
				<h2 class="text-2xl font-bold mb-2">No Networks Available</h2>
				<p class="text-muted-foreground">
					Upload networks in the Database to get started
				</p>
			</div>
		</div>
	{:else if network}
			<div class="flex gap-6">
				<!-- Main Content -->
				<div class="flex-1 min-w-0">
					<!-- Header -->
					<div class="mb-8 flex items-start justify-between">
				<div>
					<h1 class="text-3xl font-bold mb-2">{network.filename}</h1>
					{#if network.name}
						<p class="text-muted-foreground">{network.name}</p>
					{/if}
				</div>
				<div class="flex items-center gap-2 shrink-0">
					<ViewSelector networkId={networkId} onLoadView={handleLoadView} />
					<SaveViewDialog networkId={networkId} currentConfig={buildCurrentViewConfig()} />
				</div>
			</div>

			<!-- Network Overview with Map -->
			<div class="grid grid-cols-5 gap-6 mb-8">
				<!-- Network Overview -->
				<div class="col-span-4 bg-card rounded-lg border border-border p-6">
					<h2 class="text-xl font-semibold mb-3">Network Overview</h2>

					<table class="w-full text-sm">
						<tbody>
							<!-- File -->
							<tr class="border-b border-border/50 hover:bg-muted/30">
								<td class="py-1.5 pr-4 text-muted-foreground w-28">File</td>
								<td class="py-1.5">
									<div class="flex items-center gap-2">
										<span class="font-medium">{network.filename}</span>
										<span class="text-xs text-muted-foreground">({formatFileSize(network.file_size)})</span>
									</div>
								</td>
							</tr>

							<!-- Path -->
							{#if network.file_path}
								{@const dirPath = getDirectoryPath(network.file_path)}
								<tr class="border-b border-border/50 hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground w-28">Path</td>
									<td class="py-1.5">
										<div class="text-xs font-mono text-muted-foreground" title={network.file_path}>
											{dirPath || '-'}
										</div>
									</td>
								</tr>
							{/if}

							<!-- Name -->
							<tr class="border-b border-border/50 hover:bg-muted/30">
								<td class="py-1.5 pr-4 text-muted-foreground w-28">Name</td>
								<td class="py-1.5">
									<div class="text-sm" title={network.name || ''}>
										{network.name || '-'}
									</div>
								</td>
							</tr>

							<!-- Last Updated -->
								<tr class="border-b border-border/50 hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground w-28">Last Updated</td>
									<td class="py-1.5">
										{#if network.update_history && network.update_history.length > 0}
											{@const lastUpdate = network.update_history[network.update_history.length - 1]}
											{#if network.update_history.length > 1}
												<div>
													<button
														onclick={() => updateHistoryExpanded = !updateHistoryExpanded}
														class="text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer text-left flex items-center gap-1"
														title="Click to see full history"
													>
														<span>{formatDate(lastUpdate)}</span>
														<span class="text-muted-foreground/60">({network.update_history.length})</span>
														<svg
															xmlns="http://www.w3.org/2000/svg"
															width="12"
															height="12"
															viewBox="0 0 24 24"
															fill="none"
															stroke="currentColor"
															stroke-width="2"
															stroke-linecap="round"
															stroke-linejoin="round"
															class="transition-transform {updateHistoryExpanded ? 'rotate-180' : ''}"
														>
															<polyline points="6 9 12 15 18 9"></polyline>
														</svg>
													</button>

													{#if updateHistoryExpanded}
														<div class="mt-2 space-y-1 pl-2 border-l-2 border-border">
															{#each [...network.update_history].reverse() as updateTime, idx}
																<div class="text-xs text-muted-foreground">
																	<span class="text-muted-foreground/60">#{network.update_history.length - idx}</span>
																	<span class="ml-2">{formatDate(updateTime)}</span>
																</div>
															{/each}
														</div>
													{/if}
												</div>
											{:else}
												<div class="text-xs text-muted-foreground">
													{formatDate(lastUpdate)}
												</div>
											{/if}
										{:else}
											<div class="text-xs text-muted-foreground">-</div>
										{/if}
									</td>
								</tr>

								<!-- Created At -->
								<tr class="border-b border-border/50 hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground w-28">Created At</td>
									<td class="py-1.5">
										<div class="text-xs text-muted-foreground">
											{formatDate(network.created_at)}
										</div>
									</td>
								</tr>

								<!-- Hash -->
								<tr class="border-b border-border/50 hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground w-28">Hash</td>
									<td class="py-1.5">
										{#if network.file_hash}
											<div class="flex items-start gap-2">
												<button
													onclick={() => copyToClipboard(network!.file_hash!)}
													class="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer text-left break-all"
													title="Click to copy"
												>
													{network.file_hash}
												</button>
												{#if hashCopied}
													<span class="text-xs text-primary whitespace-nowrap">Copied!</span>
												{/if}
											</div>
										{:else}
											<div class="text-xs text-muted-foreground">-</div>
										{/if}
									</td>
								</tr>
							</tbody>
					</table>

					<!-- Full Width Sections Below -->
				<div class="mt-4 overflow-x-auto">
					<table class="w-full text-sm">
						<tbody>
							<!-- Dimensions - Horizontal -->
							{#if network.dimensions_count && (network.dimensions_count.timesteps || network.dimensions_count.periods || network.dimensions_count.scenarios)}
								<tr class="border-b border-border/50 hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground w-32">Dimensions</td>
									<td class="py-1.5">
										<div class="flex items-center gap-3 flex-wrap">
											{#if network.dimensions_count.timesteps}
												<div class="inline-flex items-center gap-1 text-xs">
													<Clock size={12} class="text-muted-foreground" />
													<span class="font-semibold">{network.dimensions_count.timesteps.toLocaleString()}</span>
												</div>
											{/if}
											{#if network.dimensions_count.periods}
												<div class="inline-flex items-center gap-1 text-xs">
													<CalendarRange size={12} class="text-muted-foreground" />
													<span class="font-semibold">{network.dimensions_count.periods.toLocaleString()}</span>
												</div>
											{/if}
											{#if network.dimensions_count.scenarios}
												<div class="inline-flex items-center gap-1 text-xs">
													<Waypoints size={12} class="text-muted-foreground" />
													<span class="font-semibold">{network.dimensions_count.scenarios.toLocaleString()}</span>
												</div>
											{/if}
										</div>
									</td>
								</tr>
							{/if}

							<!-- Components -->
							{#if network.components_count && Object.keys(network.components_count).length > 0}
								<tr class="border-b border-border/50 hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground align-top w-32">Components</td>
									<td class="py-1.5">
										<div class="flex flex-wrap gap-1">
											{#each Object.entries(network.components_count) as [component, count]}
												<span class="inline-flex items-center gap-1 bg-muted px-1.5 py-0.5 rounded text-xs">
													<span class="text-muted-foreground">{component}:</span>
													<span class="font-semibold">{count.toLocaleString()}</span>
												</span>
											{/each}
										</div>
									</td>
								</tr>
							{/if}

							<!-- Tags -->
							{#if network.tags && Array.isArray(network.tags) && network.tags.length > 0}
								<tr class="hover:bg-muted/30">
									<td class="py-1.5 pr-4 text-muted-foreground align-top w-32">Tags</td>
									<td class="py-1.5">
										<div class="flex flex-wrap gap-1.5">
											{#each network.tags as tag}
												{@const tagType = getTagType(tag)}
												{@const colorClass = getTagColor(tagType)}
												{#if typeof tag === 'object' && tag.name && tag.url}
													<a
														href={tag.url}
														target="_blank"
														rel="noopener noreferrer"
														class="inline-flex hover:opacity-80 transition-opacity"
														title={tag.url}
													>
														<Badge variant="secondary" class={colorClass}>
															{tag.name}
															<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="ml-1 opacity-70">
																<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
																<polyline points="15 3 21 3 21 9"></polyline>
																<line x1="10" y1="14" x2="21" y2="3"></line>
															</svg>
														</Badge>
													</a>
												{:else if typeof tag === 'string'}
													<Badge variant="secondary" class={colorClass}>
														{tag}
													</Badge>
												{/if}
											{/each}
										</div>
									</td>
								</tr>
							{/if}
						</tbody>
					</table>
				</div>
				</div>

				<!-- Network Map -->
				{#if networkId}
					<div class="col-span-1">
						<div class="bg-card rounded-lg border border-border overflow-hidden h-full min-h-[300px]">
							<NetworkMap networkId={networkId} carriers={selectedCarriers} />
						</div>
					</div>
				{/if}

			</div>

			<!-- Component Data Browser -->
			{#if networkId}
				<div class="mb-8">
					<h2 class="text-xl font-semibold mb-4">Component Data</h2>
					<ComponentBrowser networkId={networkId} />
				</div>
			{/if}

			<!-- Plots Section with Tabs -->
			<div class="w-full bg-card rounded-lg border border-border p-6">
				<h2 class="text-xl font-semibold mb-6">Plots & Statistics</h2>

				<!-- Tab Navigation -->
				<Tabs.Root bind:value={activeTab} class="mb-6">
					<Tabs.List>
						{#each tabs as tab}
							<Tabs.Trigger value={tab.id} disabled={loadingPlot}>
								{tab.label}
							</Tabs.Trigger>
						{/each}
					</Tabs.List>
				</Tabs.Root>

				<!-- Plot Content -->
				{#if loadingPlot}
					{#if individualPlots && selectedCarriers.length > 1}
						<div class="space-y-6">
							{#each selectedCarriers.slice(0, 3) as carrier, i}
								<PlotSkeleton title={carrier} />
							{/each}
						</div>
					{:else}
						<PlotSkeleton />
					{/if}
				{:else if plotData?.plot_data || plotData?.multiplePlots}
					<div class="w-full space-y-6">
						{#if plotData.cache_hit}
							<div class="flex justify-end mb-2">
								<span class="text-xs bg-green-600 text-white px-2 py-1 rounded">Cached</span>
							</div>
						{/if}

						{#if plotData.multiplePlots && plotData.multiplePlots.length > 0}
							<!-- Separate plots for each carrier -->
							{#each plotData.multiplePlots as plot, index}
								<div class="w-full">
									<h3 class="text-lg font-semibold mb-3">{plot.carrierName}</h3>
									<div class="w-full rounded-lg border-2 border-border/50 shadow-md overflow-hidden bg-white h-[500px]">
										<div
											id="plot-{index}"
											class="w-full h-full"
										></div>
									</div>
								</div>
							{/each}
						{:else}
							<!-- Single merged plot - use key to force recreation when data changes -->
							{#key (plotData.statistic ?? '') + (plotData.plotType ?? '') + (plotData.cache_hit || '')}
								<div class="w-full rounded-lg border-2 border-border/50 shadow-md overflow-hidden bg-white h-[500px]">
									<div bind:this={plotDiv} class="w-full h-full"></div>
								</div>
							{/key}
						{/if}
					</div>
				{:else if plotData && !plotData.plot_data && !plotData.multiplePlots}
					<div class="text-center py-12">
						<div class="bg-yellow-50 border border-yellow-300 text-yellow-800 px-4 py-3 rounded-lg inline-block">
							<div class="font-semibold mb-2">Invalid Plot Data</div>
							<p class="text-sm">The plot data received is incomplete or invalid.</p>
						</div>
					</div>
				{:else}
					<div class="text-center py-12">
						<div class="flex flex-col items-center gap-3">
							<svg class="w-16 h-16 text-muted-foreground/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
							</svg>
							<p class="text-muted-foreground">Select carriers and filters to generate a plot</p>
						</div>
					</div>
				{/if}
			</div>
		</div>

		<!-- Filters Panel -->
		<div class="shrink-0 transition-all duration-300 ease-in-out {$filtersPanelCollapsedStore ? 'w-0' : 'w-80'}">
			<div class="sticky top-4">
				{#if !$filtersPanelCollapsedStore}
					<!-- Expanded state - full filters panel matching sidebar style -->
					<div class="bg-sidebar border-l border-sidebar-border h-full rounded-l-lg overflow-hidden shadow-sm">
						<!-- Header matching sidebar header -->
						<div class="flex h-14 items-center border-b border-sidebar-border px-4 bg-sidebar">
							<div class="flex items-center gap-2">
								<SlidersHorizontal size={16} class="text-sidebar-foreground" />
								<h3 class="font-semibold text-sm text-sidebar-foreground">Filters & Options</h3>
							</div>
						</div>
						<!-- Content -->
						<div class="p-4 bg-sidebar">
							<NavNetworkFilters />
						</div>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
