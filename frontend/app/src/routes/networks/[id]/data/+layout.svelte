<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/stores';
	import { getContext } from 'svelte';
	import type { NetworkWithFacets } from '../types.js';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';

	let { children }: { children?: Snippet } = $props();

	const ctx = getContext<{ network: NetworkWithFacets | null; networkId: string }>('networkData');

	const components = $derived.by(() => {
		if (!ctx.network?.components_count) return [];
		return Object.entries(ctx.network.components_count).sort(([a], [b]) => a.localeCompare(b));
	});

	const activeComponent = $derived($page.params.component ?? '');

	$effect(() => {
		const label = activeComponent || 'Data';
		breadcrumbStore.set([
			{ label: ctx.network?.filename || 'Network', href: `/networks/${ctx.networkId}` },
			{ label: 'Data', href: `/networks/${ctx.networkId}/data` },
			...(activeComponent ? [{ label: activeComponent, href: `/networks/${ctx.networkId}/data/${activeComponent}` }] : [])
		]);
	});
</script>

<div class="flex gap-6">
	<nav class="w-40 shrink-0 space-y-0.5">
		{#if !ctx.network}
			{#each Array(8) as _}
				<div class="h-7 rounded-md bg-muted/40 animate-pulse"></div>
			{/each}
		{:else}
			{#each components as [name]}
				<a
					href="/networks/{ctx.networkId}/data/{name}"
					class="block truncate px-3 py-1.5 rounded-md text-sm transition-colors {activeComponent === name ? 'bg-accent text-accent-foreground font-medium' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}"
				>
					{name}
				</a>
			{/each}
		{/if}
	</nav>
	<div class="flex-1 min-w-0">
		{@render children?.()}
	</div>
</div>
