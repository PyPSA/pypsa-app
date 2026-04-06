<script lang="ts">
	import { savedViews } from '$lib/api/client.js';
	import type { SavedView, ViewConfig, ApiError } from '$lib/types.js';
	import { LayoutDashboard, ChevronDown, Trash2, Globe, Lock, Loader2 } from 'lucide-svelte';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { toast } from 'svelte-sonner';

	let {
		networkId,
		onLoadView = () => {},
	}: {
		networkId: string | null;
		onLoadView?: (config: ViewConfig) => void;
	} = $props();

	let open = $state(false);
	let views = $state<SavedView[]>([]);
	let loading = $state(false);
	let totalViews = $state(0);

	async function loadViews() {
		loading = true;
		try {
			const response = await savedViews.list(networkId ?? undefined);
			views = response.data;
			totalViews = response.total;
		} catch (err: unknown) {
			if ((err as ApiError).cancelled) return;
			console.error('Failed to load views:', err);
		} finally {
			loading = false;
		}
	}

	function toggleDropdown() {
		open = !open;
		if (open) loadViews();
	}

	function handleSelect(view: SavedView) {
		onLoadView(view.config as ViewConfig);
		open = false;
		toast.success(`Loaded view "${view.name}"`);
	}

	async function handleDelete(e: Event, view: SavedView) {
		e.stopPropagation();
		if (!confirm(`Delete view "${view.name}"?`)) return;
		try {
			await savedViews.delete(view.id);
			views = views.filter(v => v.id !== view.id);
			totalViews--;
			toast.success(`View "${view.name}" deleted`);
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to delete view');
		}
	}

	function handleClickOutside(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.view-selector-dropdown')) {
			open = false;
		}
	}

	function formatDate(dateStr?: string): string {
		if (!dateStr) return '';
		return new Date(dateStr).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
		});
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="relative view-selector-dropdown">
	<Button variant="outline" size="sm" class="h-8 text-xs gap-1.5" onclick={toggleDropdown}>
		<LayoutDashboard size={14} />
		Views
		{#if totalViews > 0}
			<Badge variant="secondary" class="text-xs ml-0.5 px-1.5 py-0">{totalViews}</Badge>
		{/if}
		<ChevronDown size={12} class="ml-0.5 transition-transform {open ? 'rotate-180' : ''}" />
	</Button>

	{#if open}
		<div class="absolute right-0 top-full mt-1 w-72 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden">
			{#if loading}
				<div class="p-4 flex items-center justify-center">
					<Loader2 size={16} class="animate-spin text-muted-foreground" />
				</div>
			{:else if views.length === 0}
				<div class="p-4 text-center text-sm text-muted-foreground">
					No saved views yet
				</div>
			{:else}
				<div class="max-h-[300px] overflow-y-auto">
					{#each views as view}
						<div
							onclick={() => handleSelect(view)}
							onkeydown={(e) => { if (e.key === 'Enter') handleSelect(view); }}
							role="button"
							tabindex="0"
							class="w-full text-left px-3 py-2.5 hover:bg-muted/50 transition-colors border-b border-border/30 last:border-b-0 group cursor-pointer"
						>
							<div class="flex items-center justify-between gap-2">
								<div class="min-w-0 flex-1">
									<div class="flex items-center gap-1.5">
										{#if view.visibility === 'public'}
											<Globe size={11} class="text-green-600 shrink-0" />
										{:else}
											<Lock size={11} class="text-muted-foreground shrink-0" />
										{/if}
										<span class="text-sm font-medium truncate">{view.name}</span>
									</div>
									{#if view.description}
										<div class="text-xs text-muted-foreground truncate mt-0.5">{view.description}</div>
									{/if}
									<div class="text-xs text-muted-foreground/60 mt-0.5">
										{view.owner.username} — {formatDate(view.updated_at || view.created_at)}
									</div>
								</div>
								<button
									onclick={(e) => handleDelete(e, view)}
									class="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive p-1"
									title="Delete view"
								>
									<Trash2 size={13} />
								</button>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
