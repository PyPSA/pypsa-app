<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { networks } from '$lib/api/client.js';
	import type { MapDataResponse, ApiError } from '$lib/types.js';
	import { Loader2, MapPin, Layers } from 'lucide-svelte';

	let {
		networkId,
		carriers = undefined,
		onBusClick = undefined,
	}: {
		networkId: string;
		carriers?: string[];
		onBusClick?: (busName: string, carrier: string, country: string) => void;
	} = $props();

	let mapContainer = $state<HTMLDivElement | undefined>();
	let map = $state<any>(null);
	let L = $state<any>(null);
	let mapData = $state<MapDataResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busLayer = $state<any>(null);
	let branchLayer = $state<any>(null);
	let legendExpanded = $state(false);

	// Color mode: 'carrier' or 'country'
	let colorMode = $state<'carrier' | 'country'>('carrier');

	// Load map when networkId changes (not carriers — we color client-side)
	$effect(() => {
		if (networkId && browser) {
			loadMapData();
		}
	});

	// Re-render layers when data or color mode changes
	$effect(() => {
		if (map && L && mapData) {
			const _mode = colorMode;
			renderLayers();
		}
	});

	onMount(async () => {
		if (!browser) return;
		L = await import('leaflet');
		await import('leaflet/dist/leaflet.css');
	});

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
			zoomControl: false,
			attributionControl: false,
		});

		// CartoDB Positron — clean, minimal basemap for data viz
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
			maxZoom: 18,
			subdomains: 'abcd',
		}).addTo(map);

		// Compact zoom control in top-right
		L.control.zoom({ position: 'topright' }).addTo(map);

		// Compact attribution in bottom-right
		L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map);
	}

	async function loadMapData() {
		loading = true;
		error = null;
		try {
			mapData = await networks.getMapData(networkId);
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) return;
			error = (err as Error).message;
		} finally {
			loading = false;
		}
	}

	function getBusColor(props: Record<string, unknown>): string {
		if (!mapData) return '#94a3b8';
		if (colorMode === 'country' && props.country) {
			return mapData.country_colors[props.country as string] || '#94a3b8';
		}
		if (props.carrier) {
			return mapData.carrier_colors[props.carrier as string] || '#94a3b8';
		}
		return '#94a3b8';
	}

	function getBusRadius(props: Record<string, unknown>): number {
		const cap = (props.gen_capacity as number) || 0;
		if (cap > 5000) return 8;
		if (cap > 1000) return 6;
		if (cap > 100) return 5;
		return 4;
	}

	function renderLayers() {
		if (!map || !L || !mapData) return;

		// Clear existing
		if (busLayer) { map.removeLayer(busLayer); busLayer = null; }
		if (branchLayer) { map.removeLayer(branchLayer); branchLayer = null; }

		// --- Branches ---
		if (mapData.branches.features.length > 0) {
			branchLayer = L.geoJSON(mapData.branches, {
				style: (feature: any) => {
					const p = feature.properties;
					const isLink = p.type === 'link';
					const isCrossBorder = p.cross_border;
					const cap = p.capacity || 100;

					// Width: logarithmic scale of capacity
					const weight = Math.max(1.5, Math.min(5, Math.log10(cap + 1)));

					return {
						color: isCrossBorder ? '#f59e0b' : isLink ? '#8b5cf6' : '#64748b',
						weight,
						opacity: isCrossBorder ? 0.9 : 0.5,
						dashArray: isLink ? '6 4' : undefined,
					};
				},
				onEachFeature: (feature: any, layer: any) => {
					const p = feature.properties;
					const parts = [
						`<strong>${p.name}</strong>`,
						`${p.bus0} → ${p.bus1}`,
					];
					if (p.capacity) parts.push(`Capacity: ${Math.round(p.capacity).toLocaleString()} MW`);
					if (p.carrier) parts.push(`Carrier: ${p.carrier}`);
					if (p.cross_border) parts.push(`<span style="color:#f59e0b">Cross-border (${p.countries})</span>`);
					parts.push(`<span style="color:#999">${p.type}</span>`);
					layer.bindPopup(`<div style="font-size:11px;line-height:1.5">${parts.join('<br>')}</div>`);

					layer.on('mouseover', () => layer.setStyle({ weight: (layer.options?.weight || 2) + 2, opacity: 1 }));
					layer.on('mouseout', () => branchLayer?.resetStyle(layer));
				},
			}).addTo(map);
		}

		// --- Buses ---
		if (mapData.buses.features.length > 0) {
			busLayer = L.geoJSON(mapData.buses, {
				pointToLayer: (feature: any, latlng: any) => {
					const p = feature.properties;
					const color = getBusColor(p);
					const radius = getBusRadius(p);

					return L.circleMarker(latlng, {
						radius,
						fillColor: color,
						color: '#fff',
						weight: 1.5,
						opacity: 1,
						fillOpacity: 0.85,
					});
				},
				onEachFeature: (feature: any, layer: any) => {
					const p = feature.properties;
					const parts = [`<strong>${p.name}</strong>`];
					if (p.carrier) parts.push(`Carrier: ${p.carrier}`);
					if (p.country) parts.push(`Country: ${p.country}`);
					if (p.v_nom) parts.push(`V_nom: ${p.v_nom} kV`);
					if (p.generators) parts.push(`Generators: ${p.generators} (${Math.round(p.gen_capacity || 0).toLocaleString()} MW)`);
					if (p.gen_carriers) parts.push(`Gen types: ${(p.gen_carriers as string[]).join(', ')}`);
					if (p.loads) parts.push(`Loads: ${p.loads}`);
					if (p.storage) parts.push(`Storage: ${p.storage}`);
					layer.bindPopup(`<div style="font-size:11px;line-height:1.5">${parts.join('<br>')}</div>`);

					// Click-to-filter
					if (onBusClick) {
						layer.on('click', () => {
							onBusClick(p.name, p.carrier || '', p.country || '');
						});
						layer.getElement?.()?.style?.setProperty('cursor', 'pointer');
					}

					// Hover effect
					layer.on('mouseover', () => layer.setStyle({ radius: getBusRadius(p) + 2, weight: 2.5 }));
					layer.on('mouseout', () => layer.setStyle({ radius: getBusRadius(p), weight: 1.5 }));
				},
			}).addTo(map);
		}

		// Fit bounds
		if (mapData.bounds) {
			map.fitBounds([
				mapData.bounds.southwest,
				mapData.bounds.northeast,
			], { padding: [20, 20], maxZoom: 10 });
		}
	}

	// Color legend entries
	let legendEntries = $derived.by(() => {
		if (!mapData) return [];
		const colors = colorMode === 'country' ? mapData.country_colors : mapData.carrier_colors;
		return Object.entries(colors).sort((a, b) => a[0].localeCompare(b[0]));
	});
</script>

<div class="relative w-full h-full min-h-[300px] rounded-lg overflow-hidden">
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
		<!-- Stats badge -->
		<div class="absolute bottom-2 left-2 z-[500] bg-card/90 backdrop-blur-sm border border-border rounded px-2 py-1 text-[10px] text-muted-foreground">
			<MapPin size={9} class="inline mr-0.5" />
			{mapData.total_buses} buses · {mapData.total_branches} branches
		</div>

		<!-- Color mode toggle + Legend -->
		<div class="absolute top-2 left-2 z-[500]">
			<!-- Toggle button -->
			<button
				onclick={() => legendExpanded = !legendExpanded}
				class="bg-card/90 backdrop-blur-sm border border-border rounded px-2 py-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
			>
				<Layers size={10} />
				{colorMode === 'carrier' ? 'Carrier' : 'Country'}
			</button>

			{#if legendExpanded}
				<div class="mt-1 bg-card/95 backdrop-blur-sm border border-border rounded p-2 max-h-[200px] overflow-y-auto min-w-[120px]">
					<!-- Mode switch -->
					<div class="flex gap-1 mb-1.5 text-[10px]">
						<button
							onclick={() => { colorMode = 'carrier'; }}
							class="px-1.5 py-0.5 rounded {colorMode === 'carrier' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}"
						>Carrier</button>
						<button
							onclick={() => { colorMode = 'country'; }}
							class="px-1.5 py-0.5 rounded {colorMode === 'country' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}"
						>Country</button>
					</div>

					<!-- Color entries -->
					{#each legendEntries as [name, color]}
						<div class="flex items-center gap-1.5 py-0.5 text-[10px]">
							<span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:{color}"></span>
							<span class="truncate">{name}</span>
						</div>
					{/each}

					{#if legendEntries.length === 0}
						<div class="text-[10px] text-muted-foreground">No data</div>
					{/if}

					<!-- Branch legend -->
					<div class="mt-1.5 pt-1.5 border-t border-border/50 space-y-0.5">
						<div class="flex items-center gap-1.5 text-[10px]">
							<span class="w-4 h-0.5 bg-[#64748b] shrink-0"></span>
							<span>AC Line</span>
						</div>
						<div class="flex items-center gap-1.5 text-[10px]">
							<span class="w-4 h-0.5 shrink-0" style="border-top: 2px dashed #8b5cf6"></span>
							<span>DC Link</span>
						</div>
						<div class="flex items-center gap-1.5 text-[10px]">
							<span class="w-4 h-0.5 bg-[#f59e0b] shrink-0"></span>
							<span>Cross-border</span>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	:global(.leaflet-container) {
		font-family: inherit;
		background: #f8fafc;
	}
	:global(.leaflet-popup-content-wrapper) {
		border-radius: 8px;
		box-shadow: 0 2px 8px rgba(0,0,0,0.15);
	}
	:global(.leaflet-popup-content) {
		margin: 8px 12px;
	}
</style>
