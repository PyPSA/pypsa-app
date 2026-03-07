<script lang="ts">
	import { Upload, LoaderCircle } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import { networks } from '$lib/api/client.js';
	import { toast } from 'svelte-sonner';

	interface UploadButtonProps {
		variant?: 'default' | 'link' | 'destructive' | 'secondary' | 'outline' | 'ghost';
		size?: 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm' | 'icon-lg';
		label?: string;
		onUpload?: () => void;
	}

	let { variant = 'default', size = 'sm', label = 'Upload', onUpload }: UploadButtonProps = $props();

	let uploading = $state(false);
	let fileInput: HTMLInputElement;

	async function handleFileSelected(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		uploading = true;
		try {
			await networks.upload(file);
			onUpload?.();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			uploading = false;
			input.value = '';
		}
	}
</script>

<input
	bind:this={fileInput}
	type="file"
	accept=".nc"
	class="hidden"
	onchange={handleFileSelected}
/>

<Button {variant} {size} onclick={() => fileInput.click()} disabled={uploading}>
	{#if uploading}
		<LoaderCircle class="h-4 w-4 mr-2 animate-spin" />
		Uploading...
	{:else}
		<Upload class="h-4 w-4 mr-2" />
		{label}
	{/if}
</Button>
