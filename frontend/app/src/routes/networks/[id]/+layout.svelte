<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/stores';
	import { onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { networks } from '$lib/api/client.js';
	import type { NetworkWithFacets } from './types.js';
	import AlertCircle from '@lucide/svelte/icons/alert-circle';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { selectedNetworkIds } from '$lib/stores/networkPageStore';
	import { reportStore } from '$lib/stores/reportStore.svelte.js';
	import { PageSkeleton } from '$lib/components/skeletons';
	import { setContext } from 'svelte';

	let { children }: { children?: Snippet } = $props();

	let network = $state<NetworkWithFacets | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let networkId = $derived($page.params.id!);

	setContext('networkData', {
		get network() { return network; },
		get loading() { return loading; },
		get error() { return error; },
		get networkId() { return networkId; },
	});

	let loadTimeout: ReturnType<typeof setTimeout>;
	$effect(() => {
		if (browser && networkId) {
			clearTimeout(loadTimeout);
			loadTimeout = setTimeout(() => loadNetwork(), 200);
		}
	});

	async function loadNetwork() {
		if (!networkId) return;

		loading = true;
		error = null;

		try {
			network = (await networks.get(networkId)) as NetworkWithFacets;
			selectedNetworkIds.set(new Set([networkId]));
		} catch (err: unknown) {
			console.error('Error loading network:', err);
			error = (err as Error).message;
		} finally {
			loading = false;
		}
		if (network) {
			reportStore.loadForNetwork(networkId);
		}
	}

	const breadcrumbLabel = $derived(network?.filename || 'Network');
	$effect(() => {
		breadcrumbStore.set([{ label: breadcrumbLabel, href: `/networks/${networkId}` }]);
	});

	onDestroy(() => {
		breadcrumbStore.clear();
		clearTimeout(loadTimeout);
	});
</script>

{#if loading}
	<PageSkeleton />
{:else if error && !network}
	<div class="flex items-center justify-center h-full w-full">
		<div class="text-center">
			<AlertCircle size={64} class="mx-auto mb-4 text-destructive" strokeWidth={1.5} />
			<h2 class="text-2xl font-bold mb-2">Error Loading Network</h2>
			<p class="text-muted-foreground">{error}</p>
		</div>
	</div>
{:else if network}
	{@const isDataRoute = $page.url.pathname.includes(`/networks/${networkId}/data`)}
	<div class="-mx-4 px-4 border-b border-border">
		<div class="flex items-center gap-1">
			<a
				href="/networks/{networkId}"
				class="px-3 py-1.5 -mb-px text-sm font-medium transition-colors border-b-2 {!isDataRoute ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}"
			>Reports</a>
			<a
				href="/networks/{networkId}/data"
				class="px-3 py-1.5 -mb-px text-sm font-medium transition-colors border-b-2 {isDataRoute ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}"
			>Data</a>
		</div>
	</div>
	{#if network.file_missing}
		<div class="my-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
			<div class="flex items-start gap-2">
				<AlertCircle class="size-4 mt-0.5 shrink-0" />
				<div>
					<div class="font-medium">Network file is no longer available</div>
					<div class="mt-1 text-xs">
						The underlying file was moved or deleted. Charts and component data cannot be rendered.
						{#if network.file_path}
							<div class="mt-1 font-mono break-all">{network.file_path}</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{/if}
	{@render children?.()}
{/if}
