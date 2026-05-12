<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { getContext } from 'svelte';
	import { reportStore } from '$lib/stores/reportStore.svelte.js';
	import { slugify } from '$lib/utils.js';
	import type { NetworkWithFacets } from './types.js';

	let networkId = $derived($page.params.id!);
	// Layout sets this context; we read it to detect file_missing so we don't
	// redirect into a report page that can only render a 404 anyway.
	const ctx = getContext<{ network: NetworkWithFacets | null }>('networkData');

	$effect(() => {
		if (!browser || !networkId) return;
		if (ctx?.network?.file_missing) return;
		const slug = slugify(reportStore.activeReport.name) || 'overview';
		goto(`/networks/${networkId}/report/${slug}`, { replaceState: true });
	});
</script>
