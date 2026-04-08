<script lang="ts">
	import { savedViews } from '$lib/api/client.js';
	import type { ViewConfig, SavedView, ApiError } from '$lib/types.js';
	import { Bookmark, Loader2, X, Globe, Lock } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import { toast } from 'svelte-sonner';

	let {
		networkId,
		currentConfig,
		onSaved = () => {},
	}: {
		networkId: string | null;
		currentConfig: ViewConfig;
		onSaved?: (view: SavedView) => void;
	} = $props();

	let open = $state(false);
	let saving = $state(false);
	let name = $state('');
	let description = $state('');
	let isPublic = $state(false);

	function openDialog() {
		open = true;
		name = '';
		description = '';
		isPublic = false;
	}

	function closeDialog() {
		open = false;
	}

	async function handleSave() {
		if (!name.trim()) return;
		saving = true;
		try {
			const view = await savedViews.create({
				name: name.trim(),
				description: description.trim() || undefined,
				network_id: networkId || undefined,
				visibility: isPublic ? 'public' : 'private',
				config: currentConfig,
			});
			toast.success(`View "${view.name}" saved`);
			onSaved(view);
			closeDialog();
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to save view');
		} finally {
			saving = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && name.trim()) handleSave();
		if (e.key === 'Escape') closeDialog();
	}
</script>

<Button variant="outline" size="sm" class="h-8 text-xs gap-1.5" onclick={openDialog}>
	<Bookmark size={14} />
	Save View
</Button>

{#if open}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
		onclick={closeDialog}
		onkeydown={handleKeydown}
		role="dialog"
		tabindex="-1"
	>
		<!-- Dialog -->
		<div
			class="bg-card border border-border rounded-lg shadow-xl w-[400px] max-w-[90vw]"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="flex items-center justify-between p-4 border-b border-border">
				<h3 class="font-semibold text-sm">Save Dashboard View</h3>
				<button onclick={closeDialog} class="text-muted-foreground hover:text-foreground">
					<X size={16} />
				</button>
			</div>

			<div class="p-4 space-y-3">
				<div>
					<label for="view-name" class="block text-xs font-medium text-muted-foreground mb-1">Name</label>
					<input
						id="view-name"
						type="text"
						bind:value={name}
						placeholder="e.g., Energy Balance DE"
						class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						onkeydown={handleKeydown}
					/>
				</div>

				<div>
					<label for="view-desc" class="block text-xs font-medium text-muted-foreground mb-1">Description (optional)</label>
					<input
						id="view-desc"
						type="text"
						bind:value={description}
						placeholder="Short description..."
						class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
					/>
				</div>

				<div class="flex items-center gap-2">
					<button
						onclick={() => isPublic = !isPublic}
						class="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
					>
						{#if isPublic}
							<Globe size={14} class="text-green-600" />
							<span>Public — visible to all users</span>
						{:else}
							<Lock size={14} />
							<span>Private — only visible to you</span>
						{/if}
					</button>
				</div>

				<!-- Config summary -->
				<div class="bg-muted/50 rounded-md p-2.5 text-xs text-muted-foreground space-y-1">
					<div class="font-medium text-foreground/80 mb-1">View configuration:</div>
					{#if currentConfig.active_tab}
						<div>Tab: <Badge variant="secondary" class="text-xs ml-1">{currentConfig.active_tab}</Badge></div>
					{/if}
					{#if currentConfig.selected_carriers.length > 0}
						<div>Carriers: {currentConfig.selected_carriers.length} selected</div>
					{/if}
					{#if currentConfig.selected_countries.length > 0}
						<div>Countries: {currentConfig.selected_countries.length} selected</div>
					{/if}
					{#if currentConfig.selected_component}
						<div>Component: {currentConfig.selected_component}</div>
					{/if}
				</div>
			</div>

			<div class="flex justify-end gap-2 p-4 border-t border-border">
				<Button variant="ghost" size="sm" onclick={closeDialog} disabled={saving}>
					Cancel
				</Button>
				<Button variant="default" size="sm" onclick={handleSave} disabled={!name.trim() || saving}>
					{#if saving}
						<Loader2 size={14} class="mr-1 animate-spin" />
					{/if}
					Save
				</Button>
			</div>
		</div>
	</div>
{/if}
