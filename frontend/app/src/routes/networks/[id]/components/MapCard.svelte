<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { plots } from '$lib/api/client.js';
	import type { ApiError } from '$lib/types.js';
	import type { MapCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { PlotSkeleton } from '$lib/components/skeletons';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';

	interface Props {
		card: MapCardDefinition;
		networkId: string;
		onremove?: () => void;
		onfullscreen?: () => void;
	}

	let { card, networkId, onremove, onfullscreen }: Props = $props();

	let mapEl: HTMLDivElement | undefined = $state();
	let canvasEl: HTMLCanvasElement | undefined = $state();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let deckInstance: any = null;
	let mapInstance: any = null;
	let mounted = true;
	let resizeObserver: ResizeObserver | undefined;

	function resolveAccessors(props: Record<string, any>): Record<string, any> {
		const resolved: Record<string, any> = {};
		for (const [key, value] of Object.entries(props)) {
			if (typeof value === 'string' && value.startsWith('@@=')) {
				const expr = value.slice(3);
				const match = expr.match(/^\[(.+)\]$/);
				if (match) {
					const fields = match[1].split(',').map((f: string) => f.trim());
					resolved[key] = (d: any) => fields.map((f: string) => d[f]);
				} else {
					resolved[key] = (d: any) => d[expr];
				}
			} else {
				resolved[key] = value;
			}
		}
		return resolved;
	}

	async function loadAndRender() {
		loading = true;
		error = null;

		try {
			const spec = await plots.generateExplore(networkId, card.parameters as any) as any;

			if (!mounted) return;

			const [{ Deck, MapView }, layers, maplibregl] = await Promise.all([
				import('@deck.gl/core'),
				import('@deck.gl/layers'),
				import('maplibre-gl'),
			]);
			await import('maplibre-gl/dist/maplibre-gl.css');

			if (!mounted || !mapEl || !canvasEl) return;

			const LAYER_MAP: Record<string, any> = {
				ScatterplotLayer: layers.ScatterplotLayer,
				PathLayer: layers.PathLayer,
				PolygonLayer: layers.PolygonLayer,
			};

			const deckLayers = (spec.layers || []).map((layerSpec: any) => {
				const LayerClass = LAYER_MAP[layerSpec['@@type']];
				if (!LayerClass) return null;
				const { '@@type': _, ...props } = layerSpec;
				return new LayerClass(resolveAccessors(props));
			}).filter(Boolean);

			if (deckInstance) {
				deckInstance.finalize();
				deckInstance = null;
			}
			if (mapInstance) {
				mapInstance.remove();
				mapInstance = null;
			}

			const ivs = spec.initialViewState ?? {
				longitude: 10,
				latitude: 50,
				zoom: 3,
			};

			// Create maplibre-gl basemap
			const MapLib = maplibregl.default ?? maplibregl;
			mapInstance = new MapLib.Map({
				container: mapEl,
				style: spec.mapStyle || 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
				center: [ivs.longitude, ivs.latitude],
				zoom: ivs.zoom,
				bearing: ivs.bearing ?? 0,
				pitch: ivs.pitch ?? 0,
				interactive: false,
				attributionControl: false,
			});

			// Create deck.gl overlay on canvas
			const { width, height } = mapEl.getBoundingClientRect();
			deckInstance = new Deck({
				canvas: canvasEl,
				width,
				height,
				initialViewState: ivs,
				controller: true,
				layers: deckLayers,
				views: new MapView({ repeat: true }),
				onViewStateChange: ({ viewState }: any) => {
					if (mapInstance) {
						const { longitude, latitude, zoom, bearing, pitch } = viewState;
						mapInstance.jumpTo({ center: [longitude, latitude], zoom, bearing, pitch });
					}
				},
				getTooltip: (info: any) => {
					const object = info?.object;
					if (!object) return null;
					const html = object.tooltip_html ?? object.tooltip;
					return html ? { html } : null;
				},
			});

			loading = false;

			// Trigger resize after loading state clears so map recalculates dimensions
			setTimeout(() => {
				if (mapInstance) mapInstance.resize();
				handleResize();
			}, 100);
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) {
				loading = false;
				return;
			}
			console.error('MapCard error:', err);
			error = (err as Error).message;
			loading = false;
		}
	}

	function handleResize() {
		if (deckInstance && mapEl) {
			const { width, height } = mapEl.getBoundingClientRect();
			deckInstance.setProps({ width, height });
			if (mapInstance) mapInstance.resize();
		}
	}

	onMount(() => {
		if (mapEl) {
			resizeObserver = new ResizeObserver(() => handleResize());
			resizeObserver.observe(mapEl);
		}
	});

	let prevKey = '';
	$effect(() => {
		const key = JSON.stringify([card.parameters, networkId]);
		if (key !== prevKey) {
			prevKey = key;
			loadAndRender();
		}
	});

	onDestroy(() => {
		mounted = false;
		if (deckInstance) {
			deckInstance.finalize();
			deckInstance = null;
		}
		if (mapInstance) {
			mapInstance.remove();
			mapInstance = null;
		}
		if (resizeObserver) {
			resizeObserver.disconnect();
		}
	});
</script>

<div class="group/card bg-card rounded-lg border border-border overflow-hidden flex flex-col h-full relative">
	<!-- Header bar -->
	<div class="card-drag-handle flex items-center justify-between px-3 py-1 border-b border-border/50 shrink-0 cursor-grab">
		{#if onfullscreen}
			<button class="text-xs font-medium text-muted-foreground truncate hover:text-foreground transition-colors cursor-pointer" onclick={onfullscreen}>Map</button>
		{:else}
			<span class="text-xs font-medium text-muted-foreground truncate">Map</span>
		{/if}
		<div class="flex items-center gap-0.5">
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props })}
						<Button variant="ghost" size="icon" class="h-6 w-6" {...props}>
							<Ellipsis class="h-3 w-3" />
						</Button>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end" class="w-36">
					<DropdownMenu.Item onclick={onremove}>
						<Trash2 class="h-3.5 w-3.5 mr-2" />
						Remove
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</div>
	</div>

	<!-- Map area -->
	<div class="relative flex-1 min-h-0">
		<!-- Map layers always rendered so they get proper dimensions -->
		<div class="absolute inset-0">
			<div bind:this={mapEl} style="position: absolute !important; inset: 0;"></div>
			<canvas bind:this={canvasEl} class="absolute inset-0 w-full h-full"></canvas>
		</div>
		<!-- Loading/error overlay on top -->
		{#if loading}
			<div class="absolute inset-0 z-10">
				<PlotSkeleton />
			</div>
		{:else if error}
			<div class="absolute inset-0 z-10 flex items-center justify-center p-6 text-sm text-destructive bg-card">
				<p>{error}</p>
			</div>
		{/if}
	</div>
</div>
