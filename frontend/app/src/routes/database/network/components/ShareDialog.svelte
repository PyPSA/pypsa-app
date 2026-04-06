<script lang="ts">
	import { networks } from '$lib/api/client.js';
	import type { User, ApiError } from '$lib/types.js';
	import { Share2, X, UserPlus, Trash2, Loader2, Globe, Lock } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import { toast } from 'svelte-sonner';

	let {
		networkId,
		isOwner = false,
	}: {
		networkId: string;
		isOwner?: boolean;
	} = $props();

	let open = $state(false);
	let loading = $state(false);
	let sharedUsers = $state<User[]>([]);
	let searchQuery = $state('');
	let searchResults = $state<User[]>([]);
	let searching = $state(false);
	let searchTimeout: ReturnType<typeof setTimeout>;

	function openDialog() {
		if (!isOwner) return;
		open = true;
		loadShares();
	}

	function closeDialog() {
		open = false;
		searchQuery = '';
		searchResults = [];
	}

	async function loadShares() {
		loading = true;
		try {
			const response = await networks.getShares(networkId);
			sharedUsers = response.shared_with;
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to load shares');
		} finally {
			loading = false;
		}
	}

	function handleSearch(e: Event) {
		const value = (e.target as HTMLInputElement).value;
		searchQuery = value;
		clearTimeout(searchTimeout);
		if (!value.trim()) {
			searchResults = [];
			return;
		}
		searchTimeout = setTimeout(async () => {
			searching = true;
			try {
				const results = await networks.searchUsers(value);
				searchResults = results.filter(
					u => !sharedUsers.some(su => su.id === u.id)
				);
			} catch {
				searchResults = [];
			} finally {
				searching = false;
			}
		}, 300);
	}

	async function handleShare(user: User) {
		try {
			const response = await networks.shareWith(networkId, user.id);
			sharedUsers = response.shared_with;
			searchQuery = '';
			searchResults = [];
			toast.success(`Shared with ${user.username}`);
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to share');
		}
	}

	async function handleUnshare(user: User) {
		try {
			const response = await networks.unshare(networkId, user.id);
			sharedUsers = response.shared_with;
			toast.success(`Removed ${user.username}`);
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to remove share');
		}
	}
</script>

{#if isOwner}
	<Button variant="outline" size="sm" class="h-8 text-xs gap-1.5" onclick={openDialog}>
		<Share2 size={14} />
		Share
		{#if sharedUsers.length > 0}
			<Badge variant="secondary" class="text-xs ml-0.5 px-1.5 py-0">{sharedUsers.length}</Badge>
		{/if}
	</Button>
{/if}

{#if open}
	<div
		class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
		onclick={closeDialog}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-card border border-border rounded-lg shadow-xl w-[400px] max-w-[90vw]"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="flex items-center justify-between p-4 border-b border-border">
				<h3 class="font-semibold text-sm flex items-center gap-2">
					<Share2 size={14} />
					Share Network
				</h3>
				<button onclick={closeDialog} class="text-muted-foreground hover:text-foreground">
					<X size={16} />
				</button>
			</div>

			<div class="p-4 space-y-3">
				<!-- Add user search -->
				<div>
					<label for="share-search" class="block text-xs font-medium text-muted-foreground mb-1">Add people</label>
					<div class="relative">
						<UserPlus size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
						<input
							id="share-search"
							type="text"
							value={searchQuery}
							oninput={handleSearch}
							placeholder="Search users..."
							class="w-full h-9 rounded-md border border-input bg-background pl-8 pr-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						/>
					</div>

					{#if searchResults.length > 0}
						<div class="mt-1 border border-border rounded-md max-h-[150px] overflow-y-auto">
							{#each searchResults as user}
								<button
									onclick={() => handleShare(user)}
									class="w-full text-left px-3 py-2 hover:bg-muted/50 text-sm flex items-center gap-2 border-b border-border/30 last:border-b-0"
								>
									{#if user.avatar_url}
										<img src={user.avatar_url} alt="" class="w-5 h-5 rounded-full" />
									{/if}
									<span>{user.username}</span>
								</button>
							{/each}
						</div>
					{/if}
				</div>

				<!-- Shared users list -->
				<div>
					<div class="text-xs font-medium text-muted-foreground mb-2">
						Shared with {sharedUsers.length} user{sharedUsers.length !== 1 ? 's' : ''}
					</div>

					{#if loading}
						<div class="flex items-center justify-center py-4">
							<Loader2 size={16} class="animate-spin text-muted-foreground" />
						</div>
					{:else if sharedUsers.length === 0}
						<div class="text-sm text-muted-foreground text-center py-4">
							Not shared with anyone yet
						</div>
					{:else}
						<div class="space-y-1">
							{#each sharedUsers as user}
								<div class="flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-muted/30 group">
									<div class="flex items-center gap-2">
										{#if user.avatar_url}
											<img src={user.avatar_url} alt="" class="w-5 h-5 rounded-full" />
										{/if}
										<span class="text-sm">{user.username}</span>
									</div>
									<button
										onclick={() => handleUnshare(user)}
										class="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive p-1"
										title="Remove access"
									>
										<Trash2 size={13} />
									</button>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
