<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { getContext, onMount, onDestroy } from 'svelte';
	import Plus from '@lucide/svelte/icons/plus';
	import BarChart3 from '@lucide/svelte/icons/bar-chart-3';
	import NotepadText from '@lucide/svelte/icons/notepad-text';
	import MapIcon from '@lucide/svelte/icons/map';
	import Info from '@lucide/svelte/icons/info';
	import TableIcon from '@lucide/svelte/icons/table';
	import * as Dialog from '$lib/components/ui/dialog';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { reportStore, STATISTICS, CHART_TYPES, type PlotCardDefinition, type ExploreCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { slugify } from '$lib/utils.js';
	import ReportTabs from '../../components/ReportTabs.svelte';
	import ReportGrid from '../../components/ReportGrid.svelte';
	import PlotEditorDialog from '../../components/PlotEditorDialog.svelte';
	import ExploreEditorDialog from '../../components/ExploreEditorDialog.svelte';
	import type { NetworkWithFacets } from '../../types.js';

	const ctx = getContext<{
		network: NetworkWithFacets | null;
		networkId: string;
	}>('networkData');

	let cardPickerOpen = $state(false);
	let editorOpen = $state(false);
	let editingPlot = $state<PlotCardDefinition | null>(null);
	let exploreEditorOpen = $state(false);
	let editingExplore = $state<ExploreCardDefinition | null>(null);

	let slug = $derived($page.params.slug!);
	let networkId = $derived(ctx.networkId);
	let network = $derived(ctx.network!);

	let fullscreenCardId = $derived($page.url.searchParams.get('card'));
	let fullscreenTab = $derived(Number($page.url.searchParams.get('tab') ?? 0));

	$effect(() => {
		if (!browser) return;
		const match = reportStore.reports.find((r) => slugify(r.name) === slug);
		if (match) {
			if (reportStore.activeReportId !== match.id) {
				reportStore.setActiveReport(match.id);
			}
		} else {
			const defaultSlug = slugify(reportStore.reports[0].name) || 'overview';
			goto(`/networks/${networkId}/report/${defaultSlug}`, { replaceState: true });
		}
	});

	const breadcrumbLabel = $derived(network?.filename || 'Network');
	$effect(() => {
		const active = reportStore.activeReport;
		if (fullscreenCardId) {
			const fc = active.cards.find((c) => c.id === fullscreenCardId);
			if (fc) {
				let cardTitle = fc.name;
				if (!cardTitle) {
					if (fc.type === 'plot') {
						const plot = fc as PlotCardDefinition;
						const stat = STATISTICS.find((s) => s.value === plot.statistic);
						const chart = CHART_TYPES.find((c) => c.value === plot.plotType);
						cardTitle = (stat?.label ?? plot.statistic) + (chart ? ` ${chart.label}` : '');
					} else {
						cardTitle = fc.type.charAt(0).toUpperCase() + fc.type.slice(1);
					}
				}
				breadcrumbStore.set([
					{ label: breadcrumbLabel, href: `/networks/${networkId}/report/${slug}` },
					{ label: cardTitle },
				]);
				return;
			}
		}
		breadcrumbStore.set([
			{ label: breadcrumbLabel },
		]);
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && fullscreenCardId) {
			e.preventDefault();
			goto(`/networks/${networkId}/report/${slug}`);
		}
	}

	function handleTabChange(index: number) {
		const url = new URL($page.url);
		if (index === 0) {
			url.searchParams.delete('tab');
		} else {
			url.searchParams.set('tab', String(index));
		}
		goto(url.toString(), { replaceState: true, noScroll: true, keepFocus: true });
	}

	onMount(() => {
		window.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		if (browser) window.removeEventListener('keydown', handleKeydown);
	});

	function openCardPicker() {
		cardPickerOpen = true;
	}

	function addStatisticsPlot() {
		editingPlot = null;
		cardPickerOpen = false;
		setTimeout(() => { editorOpen = true; }, 300);
	}

	function addMarkdownCard() {
		reportStore.addCard(reportStore.activeReport.id, {
			id: crypto.randomUUID(),
			type: 'markdown',
			content: '',
			x: 0,
			y: 0,
			w: 8,
			h: 5,
			autoPosition: true,
		} as any);
		cardPickerOpen = false;
	}

	function addExploreCard() {
		editingExplore = null;
		cardPickerOpen = false;
		setTimeout(() => { exploreEditorOpen = true; }, 300);
	}

	function addComponentTableCard() {
		const components = network.components_count ? Object.keys(network.components_count) : [];
		const defaultComponent = components[0] ?? 'Bus';
		reportStore.addCard(reportStore.activeReport.id, {
			id: crypto.randomUUID(),
			type: 'component_table',
			component: defaultComponent,
			x: 0,
			y: 0,
			w: 12,
			h: 6,
			autoPosition: true,
		} as any);
		cardPickerOpen = false;
	}

	function addOverviewCard() {
		reportStore.addCard(reportStore.activeReport.id, {
			id: crypto.randomUUID(),
			type: 'overview',
			x: 0,
			y: 0,
			w: 5,
			h: 4,
			autoPosition: true,
		} as any);
		cardPickerOpen = false;
	}

	function openEditPlot(plot: PlotCardDefinition) {
		editingPlot = plot;
		editorOpen = true;
	}

	function openEditExplore(card: ExploreCardDefinition) {
		editingExplore = card;
		exploreEditorOpen = true;
	}

	function handleExploreSave(card: ExploreCardDefinition) {
		const report = reportStore.activeReport;
		if (editingExplore) {
			reportStore.updateCard(report.id, editingExplore.id, card);
		} else {
			reportStore.addCard(report.id, { ...card, type: 'explore', x: 0, y: 0, w: 8, h: 8, autoPosition: true } as any);
		}
		exploreEditorOpen = false;
	}

	function handleEditorSave(plot: PlotCardDefinition) {
		const report = reportStore.activeReport;
		if (editingPlot) {
			if (editingPlot.expandBy && !plot.expandBy) {
				plot = { ...plot, w: 8, h: 5 };
			}
			reportStore.updateCard(report.id, editingPlot.id, plot);
		} else {
			reportStore.addCard(report.id, { ...plot, type: 'plot', x: 0, y: 0, w: 8, h: 5, autoPosition: true } as any);
		}
		editorOpen = false;
	}
</script>

<div class="flex-1 min-w-0">
	{#if !fullscreenCardId}
		<div class="flex items-center justify-between mb-1">
			<ReportTabs {networkId} />
			<button
				class="shrink-0 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
				onclick={openCardPicker}
			>
				<Plus class="h-4 w-4" />
				Add Card
			</button>
		</div>
	{/if}
	<ReportGrid
		report={reportStore.activeReport}
		{networkId}
		{network}
		{slug}
		facets={network.facets ?? {}}
		oneditplot={openEditPlot}
		oneditexplore={openEditExplore}
		{fullscreenCardId}
		{fullscreenTab}
		ontabchange={handleTabChange}
	/>
</div>

<Dialog.Root bind:open={cardPickerOpen}>
	<Dialog.Content class="sm:max-w-7xl max-h-[90vh] overflow-hidden flex flex-col" onOpenAutoFocus={(e) => e.preventDefault()}>
		<Dialog.Header>
			<Dialog.Title>Add Card</Dialog.Title>
		</Dialog.Header>
		<div class="grid grid-cols-5 gap-3 py-4">
			<button
				class="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-accent hover:border-foreground/20 transition-colors cursor-pointer"
				onclick={addStatisticsPlot}
			>
				<BarChart3 class="h-8 w-8 text-muted-foreground" />
				<span class="text-sm font-medium">Statistics Plot</span>
			</button>
			<button
				class="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-accent hover:border-foreground/20 transition-colors cursor-pointer"
				onclick={addMarkdownCard}
			>
				<NotepadText class="h-8 w-8 text-muted-foreground" />
				<span class="text-sm font-medium">Markdown</span>
			</button>
			<button
				class="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-accent hover:border-foreground/20 transition-colors cursor-pointer"
				onclick={addExploreCard}
			>
				<MapIcon class="h-8 w-8 text-muted-foreground" />
				<span class="text-sm font-medium">Explore</span>
			</button>
			<button
				class="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-accent hover:border-foreground/20 transition-colors cursor-pointer"
				onclick={addComponentTableCard}
			>
				<TableIcon class="h-8 w-8 text-muted-foreground" />
				<span class="text-sm font-medium">Component Table</span>
			</button>
			<button
				class="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-accent hover:border-foreground/20 transition-colors cursor-pointer"
				onclick={addOverviewCard}
			>
				<Info class="h-8 w-8 text-muted-foreground" />
				<span class="text-sm font-medium">Overview</span>
			</button>
		</div>
	</Dialog.Content>
</Dialog.Root>

<PlotEditorDialog
	bind:open={editorOpen}
	{networkId}
	facets={network.facets ?? {}}
	initialPlot={editingPlot}
	onsave={handleEditorSave}
	onclose={() => (editorOpen = false)}
/>

<ExploreEditorDialog
	bind:open={exploreEditorOpen}
	{networkId}
	facets={network.facets ?? {}}
	initialCard={editingExplore}
	onsave={handleExploreSave}
	onclose={() => (exploreEditorOpen = false)}
/>
