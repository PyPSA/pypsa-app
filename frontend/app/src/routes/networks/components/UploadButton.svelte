<script lang="ts">
	import Upload from '@lucide/svelte/icons/upload';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import FileUp from '@lucide/svelte/icons/file-up';
	import LinkIcon from '@lucide/svelte/icons/link';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { networks } from '$lib/api/client.js';
	import { toast } from 'svelte-sonner';
	import UrlImportDialog from './UrlImportDialog.svelte';

	interface UploadButtonProps {
		variant?: 'default' | 'link' | 'destructive' | 'secondary' | 'outline' | 'ghost';
		size?: 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm' | 'icon-lg';
		label?: string;
		onUpload?: () => void;
	}

	let {
		variant = 'default',
		size = 'sm',
		label = 'Add network',
		onUpload
	}: UploadButtonProps = $props();

	let importing = $state(false);
	let fileInput: HTMLInputElement;
	let urlOpen = $state(false);

	async function handleFileSelected(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		importing = true;
		try {
			const { task_id } = await networks.upload(file);
			await networks.pollImport(task_id);
			toast.success('Network imported');
			onUpload?.();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			importing = false;
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

<DropdownMenu.Root>
	<DropdownMenu.Trigger>
		{#snippet child({ props }: { props: Record<string, unknown> })}
			<Button {variant} {size} {...props} disabled={importing}>
				{#if importing}
					<LoaderCircle class="h-4 w-4 mr-2 animate-spin" />
					Importing...
				{:else}
					<Upload class="h-4 w-4 mr-2" />
					{label}
					<ChevronDown class="h-4 w-4 ml-2" />
				{/if}
			</Button>
		{/snippet}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="end">
		<DropdownMenu.Item onclick={() => fileInput.click()} disabled={importing}>
			<FileUp class="h-4 w-4 mr-2" />
			From file
		</DropdownMenu.Item>
		<DropdownMenu.Item onclick={() => (urlOpen = true)} disabled={importing}>
			<LinkIcon class="h-4 w-4 mr-2" />
			From URL
		</DropdownMenu.Item>
	</DropdownMenu.Content>
</DropdownMenu.Root>

<UrlImportDialog
	bind:open={urlOpen}
	onSuccess={() => onUpload?.()}
/>
