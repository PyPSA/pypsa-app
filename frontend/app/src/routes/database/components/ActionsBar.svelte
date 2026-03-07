<script lang="ts">
	import UploadButton from './UploadButton.svelte';

	let { onUpload }: { onUpload?: () => void } = $props();
</script>

<div class="flex justify-end gap-2 mb-4">
	<UploadButton {onUpload} />
</div>
