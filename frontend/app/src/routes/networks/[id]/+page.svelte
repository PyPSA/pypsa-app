<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { reportStore } from '$lib/stores/reportStore.svelte.js';
	import { slugify } from '$lib/utils.js';

	let networkId = $derived($page.params.id!);

	$effect(() => {
		if (!browser || !networkId) return;
		const slug = slugify(reportStore.activeReport.name) || 'overview';
		goto(`/networks/${networkId}/report/${slug}`, { replaceState: true });
	});
</script>
