<script>
	import { Upload, Globe, FileUp } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';

	let { variant = 'default', size = 'sm', label = 'Upload' } = $props();

	function handleUploadFromUrl() {
		alert('Upload from URL - Coming soon!');
	}

	function handleUploadFromLocal() {
		alert('Upload from local file - Coming soon!');
	}
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger asChild>
		{#snippet child({ props })}
			<Button {variant} {size} {...props}>
				<Upload class="h-4 w-4 mr-2" />
				{label}
			</Button>
		{/snippet}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="end">
		<DropdownMenu.Item onclick={handleUploadFromUrl}>
			<Globe class="h-4 w-4 mr-2" />
			Upload from URL
		</DropdownMenu.Item>
		<DropdownMenu.Item onclick={handleUploadFromLocal}>
			<FileUp class="h-4 w-4 mr-2" />
			Upload from local file
		</DropdownMenu.Item>
	</DropdownMenu.Content>
</DropdownMenu.Root>
