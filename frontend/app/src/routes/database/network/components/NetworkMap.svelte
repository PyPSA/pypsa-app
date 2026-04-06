<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { networks } from '$lib/api/client.js';
	import type { MapDataResponse, ApiError } from '$lib/types.js';
	import { Loader2, MapPin } from 'lucide-svelte';

	let {
		networkId,
		carriers = undefined,
	}: {
		networkId: string;
		carriers?: string[];
	} = $props();

	let mapContainer = $state<HTMLDivElement | undefined>();
	let map = $state<any>(null);
	let L = $state<any>(null);
	let mapData = $state<MapDataResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busLayer = $state<any>(null);
	let branchLayer = $state<any>(null);

	// Load map when networkId or carriers change
	$effect(() => {
		if (networkId && browser) {
			loadMapData();
		}
	});

	// Re-render layers when data changes
	$effect(() => {
		if (map && L && mapData) {
			renderLayers();
		}
	});

	onMount(async () => {
		if (!browser) return;

		// Dynamic import of Leaflet (client-only)
		L = await import('leaflet');

		// Import CSS
		await import('leaflet/dist/leaflet.css');
	});

	// Initialize map once container and Leaflet are ready
	$effect(() => {
		if (L && mapContainer && !map && browser) {
			initMap();
		}
	});

	onDestroy(() => {
		if (map) {
			map.remove();
			map = null;
		}
	});

	function initMap() {
		if (!mapContainer || !L) return;

		map = L.map(mapContainer, {
			center: [51, 10],
			zoom: 5,
			zoomControl: true,
			attributionControl: true,
		});

		// Use OpenStreetMap tiles (no API key needed)
		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
			maxZoom: 18,
		}).addTo(map);
	}

	async function loadMapData() {
		loading = true;
		error = null;
		try {
			mapData = await networks.getMapData(networkId, carriers);
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) return;
			error = (err as Error).message;
		} finally {
			loading = false;
		}
	}

	function renderLayers() {
		if (!map || !L || !mapData) return;

		// Clear existing layers
		if (busLayer) { map.removeLayer(busLayer); busLayer = null; }
		if (branchLayer) { map.removeLayer(branchLayer); branchLayer = null; }

		// Draw branches (lines/links) first so buses render on top
		if (mapData.branches.features.length > 0) {
			branchLayer = L.geoJSON(mapData.branches, {
				style: (feature: any) => {
					const isLink = feature.properties.type === 'link';
					return {
						color: isLink ? '#8b5cf6' : '#3b82f6',
						weight: Math.max(1.5, Math.min(4, (feature.properties.capacity || 100) / 500)),
						opacity: 0.7,
						dashArray: isLink ? '6 4' : undefined,
					};
				},
				onEachFeature: (feature: any, layer: any) => {
					const p = feature.properties;
					layer.bindPopup(
						`<div class="text-xs">
							<div class="font-bold">${p.name}</div>
							<div>${p.bus0} → ${p.bus1}</div>
							${p.capacity ? `<div>Capacity: ${p.capacity.toLocaleString()} MW</div>` : ''}
							<div class="text-gray-500">${p.type}</div>
						</div>`
					);
				},
			}).addTo(map);
		}

		// Draw buses
		if (mapData.buses.features.length > 0) {
			busLayer = L.geoJSON(mapData.buses, {
				pointToLayer: (_feature: any, latlng: any) => {
					return L.circleMarker(latlng, {
						radius: 5,
						fillColor: '#ef4444',
						color: '#991b1b',
						weight: 1,
						opacity: 0.9,
						fillOpacity: 0.7,
					});
				},
				onEachFeature: (feature: any, layer: any) => {
					const p = feature.properties;
					layer.bindPopup(
						`<div class="text-xs">
							<div class="font-bold">${p.name}</div>
							${p.carrier ? `<div>Carrier: ${p.carrier}</div>` : ''}
							${p.v_nom ? `<div>V_nom: ${p.v_nom} kV</div>` : ''}
							${p.country ? `<div>Country: ${p.country}</div>` : ''}
						</div>`
					);
				},
			}).addTo(map);
		}

		// Fit bounds
		if (mapData.bounds) {
			map.fitBounds([
				mapData.bounds.southwest,
				mapData.bounds.northeast,
			], { padding: [30, 30], maxZoom: 10 });
		}
	}
</script>

<div class="relative w-full h-full min-h-[300px] rounded-lg overflow-hidden border border-border">
	<div bind:this={mapContainer} class="w-full h-full" style="min-height: 300px;"></div>

	{#if loading}
		<div class="absolute inset-0 flex items-center justify-center bg-card/80 z-[500]">
			<div class="flex items-center gap-2 text-sm text-muted-foreground">
				<Loader2 size={16} class="animate-spin" />
				Loading map...
			</div>
		</div>
	{/if}

	{#if error}
		<div class="absolute inset-0 flex items-center justify-center bg-card/80 z-[500]">
			<div class="text-sm text-destructive">{error}</div>
		</div>
	{/if}

	{#if mapData && !loading}
		<div class="absolute bottom-2 left-2 z-[500] bg-card/90 backdrop-blur-sm border border-border rounded px-2 py-1 text-xs text-muted-foreground">
			<MapPin size={10} class="inline mr-1" />
			{mapData.total_buses} buses, {mapData.total_branches} branches
		</div>
	{/if}
</div>

<style>
	:global(.leaflet-container) {
		font-family: inherit;
	}
</style>
