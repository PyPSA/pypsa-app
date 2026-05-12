<script lang="ts" module>
	// LRU cache for plot data — shared across all PlotCard instances
	const PLOT_CACHE_MAX = 50;
	const plotCache = new Map<string, import('$lib/types.js').PlotData>();

	function cacheKey(networkId: string, statistic: string, plotType: string, parameters: Record<string, unknown>): string {
		return JSON.stringify([networkId, statistic, plotType, parameters]);
	}

	function cacheGet(key: string): import('$lib/types.js').PlotData | undefined {
		const v = plotCache.get(key);
		if (v !== undefined) {
			plotCache.delete(key);
			plotCache.set(key, v);
		}
		return v;
	}

	function cacheSet(key: string, value: import('$lib/types.js').PlotData): void {
		if (plotCache.has(key)) plotCache.delete(key);
		plotCache.set(key, value);
		while (plotCache.size > PLOT_CACHE_MAX) {
			const oldest = plotCache.keys().next().value;
			if (oldest === undefined) break;
			plotCache.delete(oldest);
		}
	}
</script>

<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { plots } from '$lib/api/client.js';
	import type { PlotData, ApiError } from '$lib/types.js';
	import type { PlotCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { loadPlotly, renderPlot, purgePlot, resizePlot, plotTitle } from './plotRenderer.js';
	import { PlotSkeleton } from '$lib/components/skeletons';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import ChartNoAxesColumn from '@lucide/svelte/icons/chart-no-axes-column';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import * as Tooltip from '$lib/components/ui/tooltip';

	interface NetworkFacets {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	}

	interface Props {
		plot: PlotCardDefinition;
		networkId: string;
		facets?: NetworkFacets;
		onedit?: () => void;
		onremove?: () => void;
		onfullscreen?: () => void;
		label?: string;
		showActions?: boolean;
	}

	let { plot, networkId, facets, onedit, onremove, onfullscreen, label, showActions = true }: Props = $props();

	// Sanitize parameters against available facets
	function sanitizeParameters(
		params: Record<string, any>,
		facets: NetworkFacets | undefined,
	): { params: Record<string, any>; hints: string[] } {
		if (!facets) return { params, hints: [] };

		const hints: string[] = [];
		let sanitized = { ...params };

		// Sanitize bus_carrier
		if (sanitized.bus_carrier?.length && facets.carriers) {
			const available = Object.keys(facets.carriers);
			const requested: string[] = sanitized.bus_carrier;
			const valid = requested.filter((c) => available.includes(c));
			const dropped = requested.filter((c) => !available.includes(c));

			if (dropped.length > 0) {
				if (valid.length > 0) {
					sanitized = { ...sanitized, bus_carrier: valid };
					hints.push(`Carriers ${dropped.join(', ')} not available on this network`);
				} else {
					sanitized = { ...sanitized, bus_carrier: [] };
					hints.push('All selected carriers unavailable — showing all');
				}
			}
		}

		// Sanitize country query
		if (sanitized.query && facets.countries) {
			const match = sanitized.query.match(/country in \[(.+)]/);
			if (match) {
				const requested = match[1]
					.split(',')
					.map((c: string) => c.trim().replace(/'/g, ''))
					.filter(Boolean);
				const valid = requested.filter((c: string) => facets.countries!.includes(c));
				const dropped = requested.filter((c: string) => !facets.countries!.includes(c));

				if (dropped.length > 0) {
					if (valid.length > 0) {
						sanitized = { ...sanitized, query: `country in [${valid.map((c: string) => `'${c}'`).join(',')}]` };
						hints.push(`Countries ${dropped.join(', ')} not available on this network`);
					} else {
						const { query: _, ...rest } = sanitized;
						sanitized = rest;
						hints.push('All selected countries unavailable — showing all');
					}
				}
			}
		}

		return { params: sanitized, hints };
	}

	let sanitized = $derived(sanitizeParameters(plot.parameters, facets));
	let effectivePlot = $derived({ ...plot, parameters: sanitized.params });
	let adjustmentHints = $derived(sanitized.hints);

	let cardEl: HTMLDivElement | undefined = $state();
	let plotEl: HTMLDivElement | undefined = $state();
	let Plotly: any = $state();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let emptyData = $state(false);
	let visible = $state(false);
	let mounted = true;
	let requestId = 0;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let resizeObserver: ResizeObserver | undefined;
	let visibilityObserver: IntersectionObserver | undefined;
	let resizeRaf = 0;

	let title = $derived(plot.name || plotTitle(plot.statistic, plot.plotType));

	async function waitForLayout(): Promise<void> {
		await tick();
		await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
	}

	async function generatePlot() {
		const currentReqId = ++requestId;
		error = null;
		emptyData = false;

		const ep = effectivePlot;
		const key = cacheKey(networkId, ep.statistic, ep.plotType, ep.parameters);
		const cached = cacheGet(key);

		if (cached) {
			loading = false;
			if (!Plotly) Plotly = await loadPlotly();
			if (currentReqId !== requestId || !mounted) return;
			await waitForLayout();
			if (currentReqId !== requestId || !mounted || !plotEl) return;
			renderPlot(plotEl, cached, Plotly);
			return;
		}

		loading = true;

		try {
			if (!Plotly) {
				Plotly = await loadPlotly();
			}

			const response = await plots.generate(networkId, ep.statistic, ep.plotType, ep.parameters);

			if (currentReqId !== requestId || !mounted) return;

			const traces = response.plot_data.data;
			if (!traces || (Array.isArray(traces) && traces.length === 0)) {
				emptyData = true;
				loading = false;
				return;
			}

			cacheSet(key, response.plot_data);
			loading = false;

			await waitForLayout();
			if (currentReqId !== requestId || !mounted || !plotEl) return;

			renderPlot(plotEl, response.plot_data, Plotly);
		} catch (err: unknown) {
			if (currentReqId !== requestId) return;
			if ((err as ApiError).cancelled) {
				loading = false;
				return;
			}
			const msg = (err as Error).message;
			if (/empty/i.test(msg)) {
				emptyData = true;
			} else {
				error = msg;
			}
			loading = false;
		}
	}

	// Regenerate when plot definition changes (and card is visible)
	let lastDefKey = '';
	$effect(() => {
		if (!visible) return;
		const ep = effectivePlot;
		const key = JSON.stringify([ep.statistic, ep.plotType, ep.parameters, networkId]);
		if (key !== lastDefKey) {
			const isFirst = lastDefKey === '';
			lastDefKey = key;
			clearTimeout(debounceTimer);
			if (isFirst) {
				// First run — fetch immediately (no debounce)
				if (mounted) generatePlot();
			} else {
				debounceTimer = setTimeout(() => {
					if (mounted) generatePlot();
				}, 500);
			}
		}
	});

	// Lazy load: defer fetch until card scrolls into view
	$effect(() => {
		if (!cardEl || visible) return;
		visibilityObserver?.disconnect();
		const target = cardEl;
		visibilityObserver = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					visible = true;
					visibilityObserver?.disconnect();
					visibilityObserver = undefined;
				}
			},
			{ rootMargin: '200px' },
		);
		visibilityObserver.observe(target);
		return () => {
			visibilityObserver?.disconnect();
			visibilityObserver = undefined;
		};
	});

	// Track plot container size; resize plotly when it changes
	$effect(() => {
		if (!plotEl) return;
		resizeObserver?.disconnect();
		const target = plotEl;
		resizeObserver = new ResizeObserver(() => {
			if (resizeRaf) cancelAnimationFrame(resizeRaf);
			resizeRaf = requestAnimationFrame(() => {
				resizeRaf = 0;
				if (Plotly && mounted) resizePlot(target, Plotly);
			});
		});
		resizeObserver.observe(target);
		return () => {
			resizeObserver?.disconnect();
			resizeObserver = undefined;
		};
	});

	onDestroy(() => {
		mounted = false;
		clearTimeout(debounceTimer);
		if (resizeRaf) cancelAnimationFrame(resizeRaf);
		resizeObserver?.disconnect();
		visibilityObserver?.disconnect();
		if (plotEl && Plotly) purgePlot(plotEl, Plotly);
	});
</script>

<div bind:this={cardEl} class="group/card bg-card overflow-hidden flex flex-col h-full relative {showActions ? 'rounded-lg border border-border' : ''}">
	{#if showActions}
		<!-- Header bar -->
		<div class="card-drag-handle flex items-center justify-between px-3 py-1 border-b border-border/50 shrink-0 cursor-grab">
			<div class="flex items-center gap-1 min-w-0">
				{#if onfullscreen}
						<button class="text-xs font-medium text-muted-foreground truncate hover:text-foreground transition-colors cursor-pointer" onclick={onfullscreen}>{label ?? title}</button>
					{:else}
						<span class="text-xs font-medium text-muted-foreground truncate">{label ?? title}</span>
					{/if}
				{#if adjustmentHints.length > 0}
					<Tooltip.Root>
						<Tooltip.Trigger>
							{#snippet child({ props }: { props: Record<string, unknown> })}
								<span class="shrink-0 flex items-center" {...props}>
									<TriangleAlert class="h-3 w-3 text-amber-500" />
								</span>
							{/snippet}
						</Tooltip.Trigger>
						<Tooltip.Content>
							{#each adjustmentHints as hint}
								<p>{hint}</p>
							{/each}
						</Tooltip.Content>
					</Tooltip.Root>
				{/if}
			</div>
			<div class="flex items-center gap-0.5">
				<Button variant="ghost" size="icon" class="h-6 w-6" onclick={onedit}>
					<Pencil class="h-3 w-3" />
				</Button>
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
	{/if}

	<!-- Plot area -->
	<div class="relative flex-1 min-h-0">
		{#if loading}
			<PlotSkeleton />
		{:else if emptyData}
			<div class="flex flex-col items-center justify-center gap-2 p-6 h-full text-muted-foreground">
				<ChartNoAxesColumn class="h-8 w-8 opacity-40" />
				<p class="text-sm">No data available</p>
			</div>
		{:else if error}
			<div class="flex items-center justify-center p-6 text-sm text-destructive h-full">
				<p>{error}</p>
			</div>
		{:else}
			<div class="overflow-hidden h-full">
				<div bind:this={plotEl} class="w-full h-full"></div>
			</div>
		{/if}
	</div>
</div>

<style>
	:global(.js-plotly-plot),
	:global(.plotly),
	:global(.plot-container),
	:global(.svg-container) {
		width: 100% !important;
	}
</style>
