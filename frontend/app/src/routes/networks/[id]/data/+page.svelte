<script lang="ts">
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { getContext } from 'svelte';
	import type { NetworkWithFacets } from '../types.js';

	const ctx = getContext<{ network: NetworkWithFacets | null; networkId: string }>('networkData');

	$effect(() => {
		if (!browser || !ctx.network?.components_count) return;
		const first = Object.keys(ctx.network.components_count).sort()[0];
		if (first) {
			goto(`/networks/${ctx.networkId}/data/${first}`, { replaceState: true });
		}
	});
</script>
