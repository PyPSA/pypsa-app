<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import type { PlotCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { humanizeStatistic, humanizePlotType } from './plotRenderer.js';
	import PlotCard from './PlotCard.svelte';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';

	interface GroupItem {
		plot: PlotCardDefinition;
		label: string;
	}

	interface NetworkFacets {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	}

	interface Props {
		items: GroupItem[];
		networkId: string;
		parentPlot: PlotCardDefinition;
		facets?: NetworkFacets;
		onedit?: () => void;
		onremove?: () => void;
		onfullscreen?: () => void;
		showActions?: boolean;
		initialTab?: number;
		ontabchange?: (index: number) => void;
	}

	let { items, networkId, parentPlot, facets, onedit, onremove, onfullscreen, showActions = true, initialTab = 0, ontabchange }: Props = $props();

	let activeIndex = $state(0);
	$effect(() => {
		activeIndex = initialTab;
	});
	let overflowing = $state(false);
	let measureEl: HTMLDivElement | undefined = $state();
	let headerEl: HTMLDivElement | undefined = $state();
	let observer: ResizeObserver | undefined;

	let groupTitle = $derived(
		parentPlot.name || `${humanizeStatistic(parentPlot.statistic)} ${humanizePlotType(parentPlot.plotType)}`,
	);

	let activeItem = $derived(items[activeIndex] ?? items[0]);

	$effect(() => {
		if (activeIndex >= items.length) {
			activeIndex = 0;
		}
	});

	function setTab(index: number) {
		activeIndex = index;
		ontabchange?.(index);
	}

	function checkOverflow() {
		if (!measureEl || !headerEl) return;
		// Available width = header width - title - actions - gaps (approximate)
		const available = headerEl.clientWidth - 200;
		overflowing = measureEl.scrollWidth > available;
	}

	onMount(() => {
		if (headerEl) {
			observer = new ResizeObserver(() => checkOverflow());
			observer.observe(headerEl);
		}
		checkOverflow();
	});

	onDestroy(() => {
		observer?.disconnect();
	});

	// Re-check when items change
	$effect(() => {
		void items.length;
		void items.map((i) => i.label).join();
		tick().then(() => checkOverflow());
	});
</script>

<div class="group/card bg-card rounded-lg border border-border overflow-hidden flex flex-col h-full relative">
	<!-- Hidden measure container — always rendered to detect overflow -->
	<div bind:this={measureEl} class="measure-tabs" aria-hidden="true">
		{#each items as item (item.label)}
			<span class="px-2 py-0.5 text-xs">{item.label}</span>
		{/each}
	</div>

	<!-- Header: title + tabs/dropdown + actions -->
	<div bind:this={headerEl} class="card-drag-handle flex items-center gap-2 px-2 py-1 border-b border-border/50 shrink-0 min-w-0 cursor-grab">
		{#if onfullscreen}
			<button class="text-xs font-medium text-muted-foreground shrink-0 hover:text-foreground transition-colors cursor-pointer" onclick={onfullscreen}>{groupTitle}</button>
		{:else}
			<span class="text-xs font-medium text-foreground shrink-0">{groupTitle}</span>
		{/if}
		<div class="w-px h-4 bg-border shrink-0"></div>

		{#if overflowing}
			<select
				class="text-xs bg-transparent border border-border rounded px-1.5 py-0.5 text-foreground"
				value={activeIndex}
				onchange={(e) => setTab(Number((e.target as HTMLSelectElement).value))}
			>
				{#each items as item, i (item.label)}
					<option value={i}>{item.label}</option>
				{/each}
			</select>
		{:else}
			<div class="min-w-0 flex items-center gap-0.5 overflow-hidden">
				{#each items as item, i (item.label)}
					<button
						class="px-2 py-0.5 text-xs rounded shrink-0 transition-colors {activeIndex === i
							? 'bg-primary text-primary-foreground'
							: 'text-muted-foreground hover:bg-accent hover:text-foreground'}"
						onclick={() => setTab(i)}
					>
						{item.label}
					</button>
				{/each}
			</div>
		{/if}

		<div class="flex-1"></div>

		{#if showActions}
			<div class="flex items-center gap-0.5 shrink-0">
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
		{/if}
	</div>

	<!-- Active plot -->
	<div class="flex-1 min-h-0">
		{#if activeItem}
			{#key activeItem.label}
				<PlotCard
					plot={activeItem.plot}
					{networkId}
					{facets}
					showActions={false}
				/>
			{/key}
		{/if}
	</div>
</div>

<style>
	.measure-tabs {
		position: absolute;
		visibility: hidden;
		pointer-events: none;
		display: flex;
		gap: 0.125rem;
		white-space: nowrap;
		height: 0;
		overflow: visible;
	}
</style>
