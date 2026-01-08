<script>
	import { authStore } from '$lib/stores/auth.svelte.js';
	import ScanButton from './ScanButton.svelte';
	import UploadButton from './UploadButton.svelte';

	let { scanning = false, onScan } = $props();
</script>

<div class="flex justify-end gap-2 mb-4">
	{#if authStore.hasPermission('networks:scan')}
		<ScanButton {scanning} {onScan} />
	{/if}
	<UploadButton />
</div>
