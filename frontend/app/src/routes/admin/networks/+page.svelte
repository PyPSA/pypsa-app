<script lang="ts">
	import { onMount } from 'svelte';
	import { admin } from '$lib/api/client.js';
	import { formatFileSize, formatDate } from '$lib/utils.js';
	import { toast } from 'svelte-sonner';
	import type { Network, User, NetworkFilters, NetworkUpdate } from '$lib/types.js';
	import { Globe, Lock, Settings, Loader2 } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Table from '$lib/components/ui/table';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import { Badge } from '$lib/components/ui/badge';
	import { Label } from '$lib/components/ui/label';

	let networks = $state<Network[]>([]);
	let users = $state<User[]>([]);
	let loading = $state(true);
	let filter = $state('all');
	let selectedNetwork = $state<Network | null>(null);
	let dialogOpen = $state(false);

	// Form state for editing
	let editOwner = $state<string | undefined>(undefined);
	let editVisibility = $state<string | undefined>(undefined);

	// Loading states
	let saving = $state(false);
	let deleting = $state(false);
	let usersLoadFailed = $state(false);
	let confirmDeleteOpen = $state(false);

	onMount(async () => {
		await Promise.all([loadNetworks(), loadUsers()]);
	});

	async function loadNetworks() {
		loading = true;
		try {
			const filters: NetworkFilters = {};
			if (filter === 'public') filters.visibility = 'public';
			else if (filter === 'private') filters.visibility = 'private';

			const response = await admin.listNetworks(0, 100, filters);
			networks = response.data;
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}

	async function loadUsers() {
		try {
			const response = await admin.listUsers(0, 1000);
			users = response.data;
			usersLoadFailed = false;
		} catch (err) {
			toast.error(`Failed to load users: ${(err as Error).message}. Owner changes disabled.`);
			usersLoadFailed = true;
		}
	}

	async function handleFilterChange(newFilter: string) {
		filter = newFilter;
		await loadNetworks();
	}

	function openNetworkDialog(network: Network) {
		selectedNetwork = network;
		editOwner = network.owner.id;
		editVisibility = network.visibility;
		dialogOpen = true;
	}

	async function saveChanges() {
		if (!selectedNetwork || saving) return;

		const updates: NetworkUpdate = {};

		// Handle owner change
		if (editOwner !== selectedNetwork.owner.id) {
			updates.user_id = editOwner;
		}

		// Handle visibility change
		if (editVisibility !== selectedNetwork.visibility) {
			updates.visibility = editVisibility as NetworkUpdate['visibility'];
		}

		if (Object.keys(updates).length === 0) {
			dialogOpen = false;
			return;
		}

		saving = true;
		try {
			await admin.updateNetwork(selectedNetwork.id, updates);
			await loadNetworks();
			dialogOpen = false;
		} catch (err) {
			const changedFields = Object.keys(updates).join(', ');
			toast.error(`Failed to update "${selectedNetwork.filename}" (${changedFields}): ${(err as Error).message}`);
		} finally {
			saving = false;
		}
	}

	function confirmDelete() {
		confirmDeleteOpen = true;
	}

	async function deleteNetwork() {
		if (!selectedNetwork || deleting) return;

		deleting = true;
		try {
			await admin.deleteNetwork(selectedNetwork.id);
			await loadNetworks();
			confirmDeleteOpen = false;
			dialogOpen = false;
		} catch (err) {
			toast.error(`Failed to delete "${selectedNetwork.filename}": ${(err as Error).message}`);
		} finally {
			deleting = false;
		}
	}

	function getVisibilityBadge(visibility: string) {
		if (visibility === 'public') return { variant: 'default' as const, label: 'Public', icon: Globe };
		return { variant: 'outline' as const, label: 'Private', icon: Lock };
	}

</script>

<svelte:head>
	<title>Admin - Network Management - PyPSA App</title>
</svelte:head>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold">Network Management</h1>
		<p class="text-muted-foreground">Manage all networks, change ownership and visibility</p>
	</div>

	<div class="flex gap-2">
		<Button
			variant={filter === 'all' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('all')}
		>
			All Networks
		</Button>
		<Button
			variant={filter === 'public' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('public')}
		>
			<Globe class="mr-1 size-4" />
			Public
		</Button>
		<Button
			variant={filter === 'private' ? 'default' : 'outline'}
			size="sm"
			onclick={() => handleFilterChange('private')}
		>
			<Lock class="mr-1 size-4" />
			Private
		</Button>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-muted-foreground">
			<Loader2 class="size-4 animate-spin" />
			Loading networks...
		</div>
	{:else if networks.length === 0}
		<p class="text-muted-foreground">No networks found.</p>
	{:else}
		<div class="rounded-md border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>Filename</Table.Head>
						<Table.Head>Owner</Table.Head>
						<Table.Head>Visibility</Table.Head>
						<Table.Head>Size</Table.Head>
						<Table.Head>Created</Table.Head>
						<Table.Head class="text-right">Actions</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each networks as network}
						{@const visBadge = getVisibilityBadge(network.visibility)}
						<Table.Row class="cursor-pointer transition-colors hover:bg-muted/50" onclick={() => openNetworkDialog(network)}>
							<Table.Cell>
								<div class="flex flex-col">
									<span class="font-medium">{network.filename}</span>
									{#if network.name}
										<span class="text-xs text-muted-foreground">{network.name}</span>
									{/if}
								</div>
							</Table.Cell>
							<Table.Cell>
								<div class="flex items-center gap-2">
									<Avatar.Root class="size-6">
										<Avatar.Image src={network.owner.avatar_url} alt={network.owner.username} />
										<Avatar.Fallback class="text-xs">
											{network.owner.username.substring(0, 2).toUpperCase()}
										</Avatar.Fallback>
									</Avatar.Root>
									<span class="text-sm">{network.owner.username}</span>
								</div>
							</Table.Cell>
							<Table.Cell>
								<Badge variant={visBadge.variant} class="gap-1">
									<svelte:component this={visBadge.icon} class="size-3" />
									{visBadge.label}
								</Badge>
							</Table.Cell>
							<Table.Cell>{formatFileSize(network.file_size)}</Table.Cell>
							<Table.Cell>{formatDate(network.created_at)}</Table.Cell>
							<Table.Cell class="text-right">
								<Button
									variant="ghost"
									size="icon"
									class="size-8"
									onclick={(e) => { e.stopPropagation(); openNetworkDialog(network); }}
									title="Edit"
								>
									<Settings class="size-4" />
								</Button>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</div>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Content class="max-w-sm">
		{#if selectedNetwork}
			<Dialog.Header>
				<Dialog.Title>Edit Network</Dialog.Title>
				<Dialog.Description class="text-xs text-muted-foreground">
					{selectedNetwork.filename}
				</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-4 py-4">
				<!-- Owner Select -->
				<div class="space-y-2">
					<Label class="text-xs">Owner</Label>
					<Select.Root type="single" name="owner" bind:value={editOwner} disabled={usersLoadFailed}>
						<Select.Trigger class="w-full">
							{#if usersLoadFailed}
								<span class="text-muted-foreground">Failed to load users</span>
							{:else}
								{@const ownerUser = users.find(u => u.id === editOwner)}
								{ownerUser?.username || 'Select owner...'}
							{/if}
						</Select.Trigger>
						<Select.Content>
							{#each users as user}
								<Select.Item value={user.id}>{user.username}</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
				</div>

				<!-- Visibility Select -->
				<div class="space-y-2">
					<Label class="text-xs">Visibility</Label>
					<Select.Root type="single" name="visibility" bind:value={editVisibility}>
						<Select.Trigger class="w-full">
							{editVisibility === 'public' ? 'Public' : 'Private'}
						</Select.Trigger>
						<Select.Content>
							<Select.Item value="public">
								<div class="flex items-center gap-2">
									<Globe class="size-4" />
									Public
								</div>
							</Select.Item>
							<Select.Item value="private">
								<div class="flex items-center gap-2">
									<Lock class="size-4" />
									Private
								</div>
							</Select.Item>
						</Select.Content>
					</Select.Root>
				</div>

				<!-- Network Info -->
				<div class="space-y-1 text-xs text-muted-foreground border-t pt-4">
					<p>Size: {formatFileSize(selectedNetwork.file_size)}</p>
					<p>Created: {formatDate(selectedNetwork.created_at)}</p>
					<p class="truncate" title={selectedNetwork.file_path}>Path: {selectedNetwork.file_path}</p>
				</div>
			</div>
			<Dialog.Footer class="flex gap-2">
				<Button variant="outline" size="sm" onclick={() => dialogOpen = false} disabled={saving || deleting}>
					Cancel
				</Button>
				<Button size="sm" onclick={saveChanges} disabled={saving || deleting}>
					{#if saving}
						<Loader2 class="mr-1 size-4 animate-spin" />
					{/if}
					Save
				</Button>
				<Button variant="destructive" size="sm" class="ml-auto" onclick={confirmDelete} disabled={saving || deleting}>
					Delete
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
