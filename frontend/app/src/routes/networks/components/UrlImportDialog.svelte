<script lang="ts">
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import { networks } from '$lib/api/client.js';
	import { toast } from 'svelte-sonner';

	interface Props {
		open: boolean;
		onSuccess?: () => void;
	}

	let { open = $bindable(false), onSuccess }: Props = $props();

	let url = $state('');
	let importing = $state(false);

	$effect(() => {
		if (!open) url = '';
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!url.trim() || importing) return;
		importing = true;
		try {
			const { task_id } = await networks.fromUrl(url.trim());
			await networks.pollImport(task_id);
			toast.success('Network imported');
			onSuccess?.();
			open = false;
			url = '';
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			importing = false;
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-md">
		<Dialog.Header>
			<Dialog.Title>Import network from URL</Dialog.Title>
			<Dialog.Description>Paste a direct link to a PyPSA .nc file.</Dialog.Description>
		</Dialog.Header>
		<form onsubmit={handleSubmit} class="space-y-4">
			<input
				type="url"
				bind:value={url}
				placeholder="https://example.com/network.nc"
				class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
				disabled={importing}
				required
			/>
			<div class="flex justify-end gap-2">
				<Button
					type="button"
					variant="outline"
					size="sm"
					onclick={() => (open = false)}
					disabled={importing}
				>
					Cancel
				</Button>
				<Button type="submit" size="sm" disabled={importing || !url.trim()}>
					{#if importing}
						<LoaderCircle class="h-4 w-4 mr-2 animate-spin" />
						Importing...
					{:else}
						Import
					{/if}
				</Button>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>
