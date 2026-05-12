<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { reportStore } from '$lib/stores/reportStore.svelte.js';
	import type { CardDefinition, PlotCardDefinition, ExploreCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import PlotCard from './PlotCard.svelte';
	import PlotGroup from './PlotGroup.svelte';
	import MarkdownCard from './MarkdownCard.svelte';
	import ExploreCard from './ExploreCard.svelte';
	import OverviewCard from './OverviewCard.svelte';
	import MapCard from './MapCard.svelte';
	import ComponentTableCard from './ComponentTableCard.svelte';
	import type { NetworkWithFacets } from '../types.js';
	import type { GridStack as GridStackType } from 'gridstack';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import 'gridstack/dist/gridstack.min.css';

	interface NetworkFacets {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	}

	interface GroupItem {
		plot: PlotCardDefinition;
		label: string;
	}

	interface ResolvedCard {
		resolvedId: string;
		card: CardDefinition;
		x: number;
		y: number;
		w: number;
		h: number;
		// For groups (expandBy plots)
		isGroup: boolean;
		groupItems?: GroupItem[];
	}

	interface Props {
		report: import('$lib/stores/reportStore.svelte.js').Report;
		networkId: string;
		network: NetworkWithFacets;
		slug: string;
		facets: NetworkFacets;
		oneditplot: (plot: PlotCardDefinition) => void;
		oneditexplore?: (card: ExploreCardDefinition) => void;
		onready?: () => void;
		fullscreenCardId?: string | null;
		fullscreenTab?: number;
		ontabchange?: (index: number) => void;
	}

	let { report, networkId, network, slug, facets, oneditplot, oneditexplore, onready, fullscreenCardId, fullscreenTab = 0, ontabchange }: Props = $props();

	let gridEl: HTMLDivElement | undefined = $state();
	let grid: GridStackType | undefined;
	let mounted = $state(false);
	let gridReady = $state(false);
	let dragging = $state(false);
	let resizing = $state(false);
	let resizeBadge: HTMLDivElement | null = null;
	const pendingItems = new Set<HTMLElement>();
	function resolveCards(cards: CardDefinition[], facets: NetworkFacets): ResolvedCard[] {
		const resolved: ResolvedCard[] = [];

		for (const card of cards) {
			if (card.type === 'markdown' || card.type === 'explore' || card.type === 'map' || card.type === 'overview' || card.type === 'component_table') {
				resolved.push({
					resolvedId: card.id,
					card,
					x: card.x,
					y: card.y,
					w: card.w,
					h: card.h,
					isGroup: false,
				});
				continue;
			}

			const plot = card as PlotCardDefinition;

			if (!plot.expandBy) {
				resolved.push({
					resolvedId: plot.id,
					card: plot,
					x: plot.x,
					y: plot.y,
					w: plot.w,
					h: plot.h,
					isGroup: false,
				});
				continue;
			}

			let items: GroupItem[] = [];

			if (plot.expandBy === 'bus_carrier' && facets.carriers) {
				const carrierKeys = plot.parameters.bus_carrier?.length
					? plot.parameters.bus_carrier
					: Object.keys(facets.carriers);
				items = carrierKeys
					.filter((name) => name && name !== 'none' && name in facets.carriers!)
					.map((name) => ({
						label: facets.carriers![name].nice_name || name,
						plot: { ...plot, parameters: { ...plot.parameters, bus_carrier: [name] }, expandBy: undefined },
					}));
			} else if (plot.expandBy === 'country' && facets.countries) {
				const match = plot.parameters.query?.match(/country in \[(.+)]/);
				const selectedCountries = match
					? match[1].split(',').map((c) => c.trim().replace(/'/g, '')).filter(Boolean)
					: facets.countries.filter((c) => c && c !== 'none');
				items = selectedCountries
					.filter((c) => c && c !== 'none' && facets.countries!.includes(c))
					.map((c) => ({
						label: c,
						plot: { ...plot, parameters: { ...plot.parameters, query: `country in ['${c}']` }, expandBy: undefined },
					}));
			}

			if (items.length === 0) {
				resolved.push({
					resolvedId: plot.id,
					card: plot,
					x: plot.x,
					y: plot.y,
					w: plot.w,
					h: plot.h,
					isGroup: false,
				});
				continue;
			}

			resolved.push({
				resolvedId: plot.id,
				card: plot,
				x: plot.x,
				y: plot.y,
				w: plot.w,
				h: plot.h,
				isGroup: true,
				groupItems: items,
			});
		}

		return resolved;
	}

	let resolvedCards = $derived(resolveCards(report.cards, facets));
	let fullscreenRc = $derived(fullscreenCardId ? resolvedCards.find((rc) => rc.resolvedId === fullscreenCardId) : null);

	function gsAttrs(rc: ResolvedCard): Record<string, string> {
		const attrs: Record<string, string> = {
			'gs-id': rc.resolvedId,
			'gs-x': String(rc.x),
			'gs-y': String(rc.y),
			'gs-w': String(rc.w),
			'gs-h': String(rc.h),
		};
		if ((rc.card as any).autoPosition) {
			attrs['gs-auto-position'] = 'true';
		}

		return attrs;
	}

	function syncToStore() {
		if (!grid) return;
		const items = grid.getGridItems().map((el) => {
			const node = (el as any).gridstackNode;
			return {
				id: el.getAttribute('gs-id') ?? '',
				x: node?.x ?? 0,
				y: node?.y ?? 0,
				w: node?.w ?? 12,
				h: node?.h ?? 5,
			};
		});
		reportStore.updateLayout(report.id, items);
	}

	async function initGrid() {
		if (!gridEl || grid) return;

		const { GridStack } = await import('gridstack');

		grid = GridStack.init(
			{
				column: 24,
				columnOpts: {
					columnMax: 24,
					breakpoints: [
						{ w: 768, c: 1 },
						{ w: 1200, c: 12 },
						{ w: 1600, c: 24 },
					],
					layout: 'moveScale',
				},
				cellHeight: 80,
				margin: 8,
				float: false,
				animate: false,
				minRow: 1,
				handleClass: 'card-drag-handle',
				resizable: { handles: 'se,e,s', autoHide: false },
				removable: '.report-trash-zone',
			},
			gridEl,
		);

		requestAnimationFrame(() => {
			gridEl?.classList.add('grid-stack-animate');
		});

		grid.on('dragstart', () => {
			dragging = true;
			gridEl?.classList.add('is-dragging');
		});
		grid.on('dragstop', () => {
			dragging = false;
			gridEl?.classList.remove('is-dragging');
			syncToStore();
		});
		grid.on('resizestart', (_event: Event, target: any) => {
			resizing = true;
			const el = target instanceof HTMLElement ? target : target?.el;
			const node = el?.gridstackNode;
			if (el && node) {
				resizeBadge = document.createElement('div');
				resizeBadge.className = 'gs-resize-badge';
				resizeBadge.textContent = `${node.w} × ${node.h}`;
				el.appendChild(resizeBadge);
			}
		});
		grid.on('resize', (_event: Event, target: any) => {
			const el = target instanceof HTMLElement ? target : target?.el;
			const node = el?.gridstackNode;
			if (resizeBadge && node) {
				resizeBadge.textContent = `${node.w} × ${node.h}`;
			}
		});
		grid.on('resizestop', () => {
			resizing = false;
			resizeBadge?.remove();
			resizeBadge = null;
			syncToStore();
		});
		grid.on('removed', (_event: Event, nodes: any[]) => {
			for (const node of nodes) {
				if (node?.id) reportStore.removeCard(report.id, node.id);
			}
		});

		gridReady = true;

		// Pick up any items mounted before grid was ready
		for (const el of pendingItems) {
			try {
				grid.makeWidget(el);
			} catch {
				// already managed
			}
		}
		pendingItems.clear();

		onready?.();
	}

	function destroyGrid() {
		if (grid) {
			grid.offAll();
			grid.destroy(false);
			grid = undefined;
		}
		gridReady = false;
		pendingItems.clear();
	}

	// gsItem action: hooks Svelte lifecycle into gridstack add/remove
	function gsItem(node: HTMLElement) {
		if (gridReady && grid) {
			try {
				grid.makeWidget(node);
			} catch {
				// already managed (initial auto-pickup)
			}
		} else {
			pendingItems.add(node);
		}
		return {
			destroy() {
				pendingItems.delete(node);
				if (gridReady && grid) {
					try {
						grid.removeWidget(node, false, false);
					} catch {
						// node not tracked
					}
				}
			},
		};
	}

	// Batch DOM swap when switching reports — prevents intermediate relayouts.
	// $effect.pre runs before DOM updates so batchUpdate(true) wraps the swap.
	// Animation is disabled during the swap so items snap to position instead of
	// sliding from (0,0), which caused heavy layout shift.
	let lastReportId = '';
	let batchPending = false;
	$effect.pre(() => {
		const id = report.id;
		if (id !== lastReportId && mounted && grid && !batchPending) {
			lastReportId = id;
			batchPending = true;
			gridEl?.classList.remove('grid-stack-animate');
			grid.batchUpdate(true);
			tick().then(() => {
				if (grid) grid.batchUpdate(false);
				requestAnimationFrame(() => {
					gridEl?.classList.add('grid-stack-animate');
				});
				batchPending = false;
			});
		}
	});

	onMount(async () => {
		mounted = true;
		lastReportId = report.id;
		await initGrid();

		// B1: Staggered entry animation
		if (gridEl) {
			const items = gridEl.querySelectorAll<HTMLElement>('.grid-stack-item');
			items.forEach((el, i) => {
				el.style.opacity = '0';
				el.style.transform = 'translateY(12px)';
				el.style.transition = 'opacity 300ms ease, transform 300ms ease';
				setTimeout(() => {
					el.style.opacity = '1';
					el.style.transform = 'translateY(0)';
					setTimeout(() => {
						el.style.removeProperty('transform');
						el.style.removeProperty('transition');
					}, 350);
				}, 0);
			});
		}
	});

	onDestroy(() => {
		destroyGrid();
	});
</script>

{#if fullscreenRc}
	{@const rc = fullscreenRc}
	<div class="flex flex-col h-[calc(100vh-8rem)]">
		<div class="flex-1 min-h-0">
			{#if rc.card.type === 'markdown'}
				<MarkdownCard
					card={rc.card}
					onupdate={(content) => reportStore.updateCard(report.id, rc.card.id, { content })}
				/>
			{:else if rc.card.type === 'explore'}
				<ExploreCard
					card={rc.card}
					{networkId}
				/>
			{:else if rc.card.type === 'map'}
				<MapCard
					card={rc.card}
					{networkId}
				/>
			{:else if rc.card.type === 'overview'}
				<OverviewCard
					card={rc.card}
					{network}
				/>
			{:else if rc.card.type === 'component_table'}
				<ComponentTableCard
					card={rc.card}
					{networkId}
					{network}
					reportId={report.id}
				/>
			{:else if rc.isGroup && rc.groupItems}
				<PlotGroup
					items={rc.groupItems}
					{networkId}
					{facets}
					parentPlot={rc.card as PlotCardDefinition}
					initialTab={fullscreenTab}
					{ontabchange}
				/>
			{:else}
				<PlotCard
					plot={rc.card as PlotCardDefinition}
					{networkId}
					{facets}
				/>
			{/if}
		</div>
	</div>
{:else}
<div class="flex flex-col gap-4 min-w-0">
	<div
		class="report-trash-zone fixed right-4 top-1/2 z-50 flex flex-col items-center justify-center gap-2 rounded-2xl bg-destructive text-white shadow-2xl text-sm font-medium"
		class:report-trash-zone--active={dragging}
		aria-hidden="true"
	>
		<Trash2 class="h-6 w-6" />
		<span>Delete</span>
	</div>
	<div bind:this={gridEl} class="grid-stack -mx-[8px]" class:is-resizing={resizing} class:grid-stack--hidden={!gridReady}>
		{#each resolvedCards as rc (rc.resolvedId)}
			<div use:gsItem class="grid-stack-item" {...gsAttrs(rc)}>
				<div class="grid-stack-item-content">
					{#if rc.card.type === 'markdown'}
						<MarkdownCard
							card={rc.card}
							onupdate={(content) => reportStore.updateCard(report.id, rc.card.id, { content })}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
							onfullscreen={() => goto(`/networks/${networkId}/report/${slug}?card=${rc.resolvedId}`)}
						/>
					{:else if rc.card.type === 'explore'}
						<ExploreCard
							card={rc.card}
							{networkId}
							onedit={() => oneditexplore?.(rc.card as ExploreCardDefinition)}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
							onfullscreen={() => goto(`/networks/${networkId}/report/${slug}?card=${rc.resolvedId}`)}
						/>
					{:else if rc.card.type === 'map'}
						<MapCard
							card={rc.card}
							{networkId}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
							onfullscreen={() => goto(`/networks/${networkId}/report/${slug}?card=${rc.resolvedId}`)}
						/>
					{:else if rc.card.type === 'overview'}
						<OverviewCard
							card={rc.card}
							{network}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
						/>
					{:else if rc.card.type === 'component_table'}
						<ComponentTableCard
							card={rc.card}
							{networkId}
							{network}
							reportId={report.id}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
							onfullscreen={() => goto(`/networks/${networkId}/report/${slug}?card=${rc.resolvedId}`)}
						/>
					{:else if rc.isGroup && rc.groupItems}
						<PlotGroup
							items={rc.groupItems}
							{networkId}
							{facets}
							parentPlot={rc.card as PlotCardDefinition}
							onedit={() => oneditplot(rc.card as PlotCardDefinition)}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
							onfullscreen={() => goto(`/networks/${networkId}/report/${slug}?card=${rc.resolvedId}`)}
						/>
					{:else}
						<PlotCard
							plot={rc.card as PlotCardDefinition}
							{networkId}
							{facets}
							onedit={() => oneditplot(rc.card as PlotCardDefinition)}
							onremove={() => reportStore.removeCard(report.id, rc.card.id)}
							onfullscreen={() => goto(`/networks/${networkId}/report/${slug}?card=${rc.resolvedId}`)}
						/>
					{/if}
				</div>
			</div>
		{/each}
	</div>

	{#if resolvedCards.length === 0}
		<div class="grid-empty-state flex items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30 p-12 text-muted-foreground">
			<p class="text-sm">No cards yet. Add a plot, map, or note to get started.</p>
		</div>
	{/if}
</div>
{/if}

<style>
	:global(.grid-stack) {
		min-height: 100px;
	}


	:global(.grid-stack-item-content) {
		border-radius: 0.5rem;
		overflow: hidden;
		cursor: default;
	}

	:global(.grid-stack > .grid-stack-item > .ui-resizable-handle) {
		z-index: 20;
	}

	:global(.grid-stack-item > .ui-resizable-se) {
		background-image: none !important;
	}

	/* A5: Drag lift effect */
	:global(.grid-stack-item.ui-draggable-dragging) {
		z-index: 40 !important;
		opacity: 1 !important;
	}

	:global(.grid-stack-item.ui-draggable-dragging > .grid-stack-item-content) {
		box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35) !important;
		transform: scale(1.01);
		border: 1px solid var(--color-primary, #3b82f6);
	}

	/* A2: Placeholder/drop target */
	:global(.grid-stack-placeholder > .placeholder-content) {
		border: 2px dashed var(--color-primary, #3b82f6) !important;
		border-radius: 0.8125rem;
		background: color-mix(in srgb, var(--color-primary, #3b82f6) 5%, transparent) !important;
	}

	/* B2: Hide Plotly during resize */
	:global(.grid-stack.is-resizing .js-plotly-plot) {
		visibility: hidden;
	}

	:global(.grid-stack.is-resizing .grid-stack-item-content) {
		background: var(--color-muted, #f5f5f5);
	}

	/* B3: Grab cursor during drag + disable card interactions */
	:global(.grid-stack.is-dragging .card-drag-handle) {
		cursor: grabbing !important;
	}

	:global(.grid-stack.is-dragging .grid-stack-item-content) {
		pointer-events: none;
	}

	/* B4: Perf — contain layout recalc to each card during drag */
	:global(.grid-stack.is-dragging .grid-stack-item) {
		will-change: transform;
	}

	:global(
		.grid-stack.is-dragging
			.grid-stack-item:not(.ui-draggable-dragging)
			> .grid-stack-item-content
	) {
		contain: strict;
	}

	/* C1: Resize dimension badge */
	:global(.gs-resize-badge) {
		position: absolute;
		bottom: 8px;
		right: 36px;
		background: var(--color-background, #fff);
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: 4px;
		padding: 2px 6px;
		font-size: 11px;
		font-weight: 500;
		color: var(--color-muted-foreground, #888);
		z-index: 50;
		pointer-events: none;
		font-variant-numeric: tabular-nums;
		opacity: 0.8;
	}

	/* Trash zone */
	.report-trash-zone {
		width: 80px;
		height: 80px;
		transform: translate(calc(100% + 1rem), -50%);
		opacity: 0;
		pointer-events: none;
		transition: transform 180ms ease, opacity 180ms ease;
	}

	.report-trash-zone--active {
		transform: translate(0, -50%);
		opacity: 1;
		pointer-events: auto;
	}

	:global(.grid-stack-item.grid-stack-item-removing) {
		opacity: 0.4;
	}

	/* B4: Trash zone pulse on hover */
	:global(.report-trash-zone.ui-droppable-over) {
		transform: translate(0, -50%) scale(1.08);
		animation: trash-pulse 800ms ease-in-out infinite;
	}

	@keyframes trash-pulse {
		0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
		50% { box-shadow: 0 0 16px 4px rgba(239, 68, 68, 0.3); }
	}

	/* Hide grid until gridstack has positioned items */
	:global(.grid-stack.grid-stack--hidden) {
		visibility: hidden;
	}

	/* C2: Empty state */
	.grid-empty-state {
		min-height: 200px;
	}
</style>
