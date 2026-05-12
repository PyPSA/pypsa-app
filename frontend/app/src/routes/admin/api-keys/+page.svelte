<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { admin, apiKeys } from '$lib/api/client.js';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/button/button.svelte';
	import { Combobox } from '$lib/components/ui/combobox';
	import * as Dialog from '$lib/components/ui/dialog';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import DateTime from '$lib/components/DateTime.svelte';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import ApiKeyReveal from '$lib/components/admin/ApiKeyReveal.svelte';
	import { TableSkeleton } from '$lib/components/skeletons';
	import type { FilterCategory } from '$lib/components/ui/filter-dialog';
	import type { FilterAst } from '$lib/filters/ast';
	import { emptyAnd } from '$lib/filters/ast';
	import { filterStateFromAst } from '$lib/filters/legacy';
	import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
	import BadgeCell from '$lib/components/cells/BadgeCell.svelte';
	import { byDate, copyToClipboard } from '$lib/utils.js';
	import { toast } from 'svelte-sonner';
	import type { User, ApiKey } from '$lib/types.js';
	import type { ColumnDef, SortingState } from '@tanstack/table-core';

	let allKeys = $state<ApiKey[]>([]);
	let keysLoading = $state(true);
	let filter = $state<FilterAst>(emptyAnd());
	let sorting = $state<SortingState>([]);
	let botUsers = $state<User[]>([]);
	const botOptions = $derived(botUsers.map((u) => ({ value: u.id, label: u.username })));

	let createOpen = $state(false);
	let newKeyName = $state('');
	let newKeyUserId = $state('');
	let newKeyExpiryDays = $state(90);
	let creatingKey = $state(false);
	let createdKey = $state<string | null>(null);

	let detailOpen = $state(false);
	let selectedKey = $state<ApiKey | null>(null);

	let confirmDeleteOpen = $state(false);

	$effect(() => {
		if (!createOpen) {
			createdKey = null;
			newKeyName = '';
			newKeyUserId = '';
			newKeyExpiryDays = 90;
		}
	});

	function isExpired(key: ApiKey): boolean {
		return !!key.expires_at && new Date(key.expires_at) < new Date();
	}

	const filterCategories = $derived<FilterCategory[]>([
		{
			key: 'users',
			label: 'Owner',
			options: botUsers.map((u) => ({ id: u.id, label: u.username }))
		},
		{
			key: 'status',
			label: 'Status',
			options: [
				{ id: 'active', label: 'Active' },
				{ id: 'expired', label: 'Expired' }
			]
		}
	]);

	const filterState = $derived(filterStateFromAst(filter, ['users', 'status']));
	const filterUserIds = $derived(filterState.users ?? new Set<string>());
	const filterStatus = $derived(filterState.status ?? new Set<string>());

	let keys = $derived(
		allKeys.filter((k) => {
			if (filterUserIds.size && !filterUserIds.has(k.owner.id)) return false;
			if (filterStatus.size) {
				const s = isExpired(k) ? 'expired' : 'active';
				if (!filterStatus.has(s)) return false;
			}
			return true;
		})
	);

	const columns: ColumnDef<ApiKey, unknown>[] = [
		{
			accessorKey: 'name',
			header: 'Name',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => info.getValue() as string
		},
		{
			accessorKey: 'key_prefix',
			header: 'Prefix',
			enableSorting: false,
			cell: (info) => `${info.getValue() as string}...`
		},
		{
			id: 'owner',
			header: 'Owner',
			enableSorting: true,
			cell: (info) => info.row.original.owner.username
		},
		{
			accessorKey: 'created_at',
			header: 'Created',
			enableSorting: true,
			sortingFn: byDate<ApiKey>((r) => r.created_at),
			cell: (info) => renderComponent(DateTime, { value: info.getValue() as string })
		},
		{
			accessorKey: 'last_used_at',
			header: 'Last used',
			enableSorting: true,
			sortingFn: byDate<ApiKey>((r) => r.last_used_at),
			cell: (info) => renderComponent(DateTime, { value: info.getValue() as string })
		},
		{
			accessorKey: 'expires_at',
			header: 'Expires',
			enableSorting: true,
			sortingFn: byDate<ApiKey>((r) => r.expires_at),
			cell: (info) => renderComponent(DateTime, { value: info.getValue() as string })
		},
		{
			id: 'status',
			header: 'Status',
			enableSorting: false,
			cell: (info) => {
				const expired = isExpired(info.row.original);
				return renderComponent(BadgeCell, {
					label: expired ? 'expired' : 'active',
					variant: expired ? 'outline' : 'default'
				});
			}
		}
	];

	onMount(async () => {
		await Promise.all([loadApiKeys(), loadBotUsers()]);
	});

	$effect(() => {
		breadcrumbStore.set([{ label: 'API Keys' }]);
	});

	onDestroy(() => {
		breadcrumbStore.clear();
	});

	async function loadBotUsers() {
		try {
			const response = await admin.listUsers(0, 100, {
				filter_q: JSON.stringify({ type: 'in', field: 'role', values: ['bot'] })
			});
			botUsers = response.data;
		} catch (err) {
			toast.error(`Failed to load bot users: ${(err as Error).message}`);
		}
	}

	async function loadApiKeys() {
		keysLoading = true;
		try {
			allKeys = await apiKeys.list();
		} catch (err) {
			toast.error(`Failed to load API keys: ${(err as Error).message}`);
		} finally {
			keysLoading = false;
		}
	}

	async function createApiKey() {
		if (!newKeyName.trim() || !newKeyUserId) return;
		creatingKey = true;
		try {
			const result = await apiKeys.create(newKeyName.trim(), newKeyExpiryDays, newKeyUserId);
			createdKey = result.key ?? null;
			newKeyName = '';
			newKeyUserId = '';
			newKeyExpiryDays = 90;
			if (!createdKey) {
				toast.success('API key created');
				createOpen = false;
			}
			await loadApiKeys();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			creatingKey = false;
		}
	}

	async function deleteApiKey() {
		if (!selectedKey) return;
		try {
			await apiKeys.delete(selectedKey.id);
			confirmDeleteOpen = false;
			detailOpen = false;
			selectedKey = null;
			toast.success('API key deleted');
			await loadApiKeys();
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

</script>

<svelte:head>
	<title>Admin - API Keys - PyPSA App</title>
</svelte:head>

<div class="flex justify-end mb-4">
	<Button size="sm" onclick={() => (createOpen = true)}>
		<Plus class="mr-1 size-4" />
		Create API Key
	</Button>
</div>

{#if keysLoading}
	<TableSkeleton rows={3} columns={7} />
{:else if keys.length === 0}
	<p class="text-muted-foreground text-sm">No API keys.</p>
{:else}
	<DataTable
		data={keys}
		columns={columns as any}
		bind:sorting
		{filterCategories}
		{filter}
		onFilterAstChange={(ast) => (filter = ast)}
		onRowClick={(key: ApiKey) => {
			selectedKey = key;
			detailOpen = true;
		}}
	/>
{/if}

<Dialog.Root bind:open={detailOpen}>
	<Dialog.Content class="max-w-md">
		{#if selectedKey}
			{@const expired = isExpired(selectedKey)}
			<Dialog.Header>
				<Dialog.Title>{selectedKey.name}</Dialog.Title>
				<Dialog.Description>API key details.</Dialog.Description>
			</Dialog.Header>
			<dl class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-xs">
				<dt class="text-muted-foreground">ID</dt>
				<dd class="font-mono break-all">{selectedKey.id}</dd>
				<dt class="text-muted-foreground">Prefix</dt>
				<dd class="font-mono">{selectedKey.key_prefix}...</dd>
				<dt class="text-muted-foreground">Owner</dt>
				<dd>
					<button
						type="button"
						class="hover:underline"
						onclick={() => {
							detailOpen = false;
							goto(`/admin/users/${selectedKey!.owner.id}`);
						}}
					>
						{selectedKey.owner.username}
					</button>
				</dd>
				<dt class="text-muted-foreground">Status</dt>
				<dd>
					<Badge variant={expired ? 'outline' : 'default'}>
						{expired ? 'expired' : 'active'}
					</Badge>
				</dd>
				<dt class="text-muted-foreground">Created</dt>
				<dd><DateTime value={selectedKey.created_at} /></dd>
				<dt class="text-muted-foreground">Last used</dt>
				<dd><DateTime value={selectedKey.last_used_at} /></dd>
				<dt class="text-muted-foreground">Expires</dt>
				<dd><DateTime value={selectedKey.expires_at} /></dd>
			</dl>
			<div class="flex justify-end gap-2 pt-2">
				<Button variant="outline" size="sm" onclick={() => (detailOpen = false)}>Close</Button>
				<Button variant="destructive" size="sm" onclick={() => (confirmDeleteOpen = true)}>
					<Trash2 class="mr-1 size-3.5" />
					Delete
				</Button>
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={confirmDeleteOpen}>
	<Dialog.Content class="max-w-xs">
		<Dialog.Header>
			<Dialog.Title>Delete API Key</Dialog.Title>
			<Dialog.Description>
				Delete "{selectedKey?.name}"? Cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		<div class="flex justify-end gap-2">
			<Button variant="outline" size="sm" onclick={() => (confirmDeleteOpen = false)}
				>Cancel</Button
			>
			<Button variant="destructive" size="sm" onclick={deleteApiKey}>Delete</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={createOpen}>
	<Dialog.Content class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Create API Key</Dialog.Title>
			<Dialog.Description>Create an API key linked to a bot user.</Dialog.Description>
		</Dialog.Header>
		{#if createdKey}
			<ApiKeyReveal
				token={createdKey}
				onDone={() => {
					createdKey = null;
					createOpen = false;
				}}
			/>
		{:else}
			<div class="space-y-4">
				<div class="space-y-2">
					<label for="key-name" class="text-sm font-medium">Name</label>
					<input
						id="key-name"
						type="text"
						class="w-full rounded-md border bg-background px-3 py-2 text-sm"
						placeholder="CI/CD Pipeline"
						bind:value={newKeyName}
					/>
				</div>
				<div class="space-y-2">
					<label for="key-user" class="text-sm font-medium">User</label>
					<Combobox
						options={botOptions}
						value={newKeyUserId}
						onSelect={(v) => { newKeyUserId = v; }}
						searchPlaceholder="Search bot users..."
						emptyText={botUsers.length === 0 ? 'No bot users available. Create one first.' : 'No users found.'}
						width="w-full"
					>
						{#snippet trigger({ props })}
							{@const selectedBot = botUsers.find((u) => u.id === newKeyUserId)}
							<button
								{...props}
								type="button"
								class="flex w-full items-center justify-between rounded-md border bg-background px-3 py-2 text-sm"
							>
								<span class={selectedBot ? '' : 'text-muted-foreground'}>
									{selectedBot?.username || 'Select a user...'}
								</span>
							</button>
						{/snippet}
					</Combobox>
				</div>
				<div class="space-y-2">
					<label for="key-expiry" class="text-sm font-medium">Expires in (days)</label>
					<input
						id="key-expiry"
						type="number"
						class="w-full rounded-md border bg-background px-3 py-2 text-sm"
						min="1"
						max="365"
						bind:value={newKeyExpiryDays}
					/>
				</div>
				<div class="flex justify-end gap-2">
					<Button variant="outline" size="sm" onclick={() => (createOpen = false)}
						>Cancel</Button
					>
					<Button
						size="sm"
						disabled={!newKeyName.trim() || !newKeyUserId || creatingKey}
						onclick={createApiKey}
					>
						{creatingKey ? 'Creating...' : 'Create'}
					</Button>
				</div>
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
