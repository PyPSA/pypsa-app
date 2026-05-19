<script lang="ts">
	import { onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { admin, apiKeys } from '$lib/api/client.js';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Plus from '@lucide/svelte/icons/plus';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';
	import DateTime from '$lib/components/DateTime.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import AssignmentList from '$lib/components/admin/AssignmentList.svelte';
	import ApiKeyReveal from '$lib/components/admin/ApiKeyReveal.svelte';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { toast } from 'svelte-sonner';
	import type { User, Backend, ApiKey, UserStatsResponse } from '$lib/types.js';
	import type { FilterAst } from '$lib/filters/ast';
	import { serialize as serializeDsl } from '$lib/filters/dsl';
	import { formatFileSize, formatRelativeTime, formatDate, copyToClipboard } from '$lib/utils.js';

	const userId = $derived($page.params.id as string);

	let user = $state<User | null>(null);
	let loading = $state(true);
	let allPermissions = $state<string[]>([]);
	let userBackends = $state<Backend[]>([]);
	let allBackends = $state<Backend[]>([]);
	let userKeys = $state<ApiKey[]>([]);
	let stats = $state<UserStatsResponse | null>(null);

	let confirmDeleteOpen = $state(false);

	let createKeyOpen = $state(false);
	let newKeyName = $state('');
	let newKeyExpiryDays = $state(90);
	let creatingKey = $state(false);
	let createdKey = $state<string | null>(null);

	let confirmDeleteKeyOpen = $state(false);
	let keyToDelete = $state<ApiKey | null>(null);

	$effect(() => {
		if (!createKeyOpen) {
			createdKey = null;
			newKeyName = '';
			newKeyExpiryDays = 90;
		}
	});

	const isSelf = $derived(user?.id === authStore.user?.id);

	type PermGroup = { name: string; perms: { full: string; action: string }[] };

	const groupedPermissions = $derived.by<PermGroup[]>(() => {
		const map = new Map<string, { full: string; action: string }[]>();
		for (const full of allPermissions) {
			const [ns, action = full] = full.split(':', 2);
			if (!map.has(ns)) map.set(ns, []);
			map.get(ns)!.push({ full, action });
		}
		return Array.from(map, ([name, perms]) => ({ name, perms }));
	});

	$effect(() => {
		if (userId) loadAll();
	});

	$effect(() => {
		if (user) {
			breadcrumbStore.set([
				{ label: 'Users', href: '/admin/users' },
				{ label: user.username }
			]);
		}
	});

	onDestroy(() => {
		breadcrumbStore.clear();
	});

	async function loadAll() {
		loading = true;
		try {
			const [u, perms, backends, allB, userStats] = await Promise.all([
				admin.getUser(userId),
				admin.getPermissions(),
				admin.listUserBackends(userId),
				admin.listBackends(),
				admin.getUserStats(userId)
			]);
			user = u;
			allPermissions = perms.permissions as string[];
			userBackends = backends;
			allBackends = allB;
			stats = userStats;
			if (u.role === 'bot') {
				userKeys = await admin.listUserApiKeys(userId);
			} else {
				userKeys = [];
			}
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}

	async function updateRole(newRole: string) {
		if (!user) return;
		try {
			user = await admin.updateUserRole(user.id, newRole);
			toast.success(`Role updated to ${user.role}`);
			if (user.role === 'bot') {
				userKeys = await admin.listUserApiKeys(user.id);
			} else {
				userKeys = [];
			}
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function deleteUser() {
		if (!user) return;
		try {
			const username = user.username;
			await admin.deleteUser(user.id);
			confirmDeleteOpen = false;
			toast.success(`User ${username} deleted`);
			goto('/admin/users');
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function assignBackend(backendId: string) {
		if (!user) return;
		try {
			await admin.assignBackendToUser(user.id, backendId);
			userBackends = await admin.listUserBackends(user.id);
			toast.success('Backend assigned');
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function removeBackend(backendId: string) {
		if (!user) return;
		try {
			await admin.unassignBackendFromUser(user.id, backendId);
			userBackends = await admin.listUserBackends(user.id);
			toast.success('Backend removed');
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function createApiKey() {
		if (!user || !newKeyName.trim()) return;
		creatingKey = true;
		try {
			const result = await apiKeys.create(newKeyName.trim(), newKeyExpiryDays, user.id);
			createdKey = result.key ?? null;
			newKeyName = '';
			newKeyExpiryDays = 90;
			userKeys = await admin.listUserApiKeys(user.id);
			if (!createdKey) {
				toast.success('API key created');
				createKeyOpen = false;
			}
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			creatingKey = false;
		}
	}

	async function deleteApiKey() {
		if (!keyToDelete || !user) return;
		try {
			await apiKeys.delete(keyToDelete.id);
			confirmDeleteKeyOpen = false;
			keyToDelete = null;
			toast.success('API key deleted');
			userKeys = await admin.listUserApiKeys(user.id);
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	const STATUS_COLORS: Record<string, string> = {
		COMPLETED: 'bg-primary text-primary-foreground',
		RUNNING: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
		SETUP: 'bg-secondary text-secondary-foreground',
		UPLOADING: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
		PENDING: 'bg-secondary text-secondary-foreground',
		FAILED: 'bg-destructive text-white dark:bg-destructive/70',
		ERROR: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
		CANCELLED: 'bg-accent text-accent-foreground',
	};

	const ACTIVE_STATUSES = ['PENDING', 'SETUP', 'RUNNING', 'UPLOADING'];

	const barSegments = $derived.by(() => {
		if (!stats || stats.runs_total === 0) return [];
		const entries = Object.entries(stats.runs_by_status);
		let activeCount = 0;
		const presentActive: string[] = [];
		const segments: { label: string; count: number; color: string; statuses: string[] }[] = [];
		for (const [status, count] of entries) {
			if (ACTIVE_STATUSES.includes(status)) {
				activeCount += count;
				presentActive.push(status);
			} else {
				segments.push({
					label: status.toLowerCase(),
					count,
					color: STATUS_COLORS[status] ?? 'bg-muted-foreground/30 text-muted-foreground',
					statuses: [status]
				});
			}
		}
		if (activeCount > 0) {
			segments.unshift({
				label: 'running',
				count: activeCount,
				color: STATUS_COLORS['RUNNING'],
				statuses: presentActive
			});
		}
		return segments;
	});

	// Build a `?q=…` link by serializing a small AST of `field:values` leaves.
	// Goes through the canonical DSL serializer so values with spaces or
	// punctuation get quoted correctly.
	function filterUrl(base: string, leaves: { field: string; values: string[] }[]): string {
		const children: FilterAst[] = leaves
			.filter(l => l.values.length > 0)
			.map(l => ({ type: 'in', field: l.field, values: l.values }));
		if (children.length === 0) return base;
		const ast: FilterAst = children.length === 1 ? children[0] : { type: 'and', children };
		return `${base}?q=${encodeURIComponent(serializeDsl(ast))}`;
	}

	const BACKEND_COLORS = [
		'bg-indigo-200 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
		'bg-teal-200 text-teal-800 dark:bg-teal-900 dark:text-teal-200',
		'bg-fuchsia-200 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-200',
		'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200',
		'bg-emerald-200 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
		'bg-pink-200 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
	];

	function roleBadgeVariant(role: string) {
		if (role === 'admin') return 'default' as const;
		if (role === 'bot' || role === 'user') return 'secondary' as const;
		return 'outline' as const;
	}
</script>

<svelte:head>
	<title>Admin - {user?.username ?? 'User'} - PyPSA App</title>
</svelte:head>

<div class="space-y-6">
	{#if loading || !user}
		<p class="text-muted-foreground">Loading...</p>
	{:else}
		<header class="flex items-center gap-4">
			<Avatar.Root class="size-12">
				<Avatar.Image src={user.avatar_url} alt={user.username} />
				<Avatar.Fallback>{user.username.substring(0, 2).toUpperCase()}</Avatar.Fallback>
			</Avatar.Root>
			<div class="flex-1 space-y-0.5">
				<div class="flex items-center gap-2">
					<h1 class="text-xl font-semibold">{user.username}</h1>
					<Badge variant={roleBadgeVariant(user.role)}>{user.role}</Badge>
					{#if isSelf}
						<Badge variant="outline">you</Badge>
					{/if}
				</div>
				<p class="text-xs text-muted-foreground">
					{user.email || 'No email'} · Last login: <DateTime value={user.last_login} />
				</p>
			</div>
		</header>

		<section class="space-y-2 rounded-md border p-4">
			<h2 class="text-sm font-semibold">Profile</h2>
			<dl class="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-xs">
				<dt class="text-muted-foreground">ID</dt>
				<dd class="font-mono">{user.id}</dd>
				<dt class="text-muted-foreground">Email</dt>
				<dd>{user.email || '—'}</dd>
				<dt class="text-muted-foreground">Created</dt>
				<dd><DateTime value={user.created_at} /></dd>
				<dt class="text-muted-foreground">Last login</dt>
				<dd><DateTime value={user.last_login} /></dd>
				<dt class="text-muted-foreground">Role</dt>
				<dd>
					{#if isSelf}
						<span>{user.role} (cannot change own role)</span>
					{:else}
						<select
							class="rounded border bg-background px-2 py-1 text-xs"
							value={user.role}
							onchange={(e: Event) => updateRole((e.target as HTMLSelectElement).value)}
						>
							<option value="admin">admin</option>
							<option value="user">user</option>
							<option value="bot">bot</option>
							<option value="pending">pending</option>
						</select>
					{/if}
				</dd>
			</dl>
		</section>

		<section class="space-y-2 rounded-md border p-4">
			<h2 class="text-sm font-semibold">Permissions</h2>
			<div class="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-x-4 gap-y-3">
				{#each groupedPermissions as group (group.name)}
					<div class="space-y-1">
						<p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
							{group.name}
						</p>
						<ul class="space-y-0.5">
							{#each group.perms as perm (perm.full)}
								{@const granted = user.permissions?.includes(perm.full)}
								<li class="flex items-center gap-2 text-xs">
									{#if granted}
										<Check class="size-3.5 text-emerald-600 dark:text-emerald-500" />
										<span>{perm.action}</span>
									{:else}
										<X class="size-3.5 text-muted-foreground/60" />
										<span class="text-muted-foreground/70">{perm.action}</span>
									{/if}
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>
		</section>

		{#if stats}
			<section class="space-y-2 rounded-md border p-4">
				<h2 class="text-sm font-semibold">Activity</h2>
				<dl class="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-xs">
					<dt class="text-muted-foreground">Networks</dt>
					<dd>
						<a href={filterUrl('/networks', [{ field: 'owner', values: [user.username] }])} class="underline-offset-2 hover:underline">{stats.networks_count}</a>
						{#if stats.networks_count > 0}
							<span class="text-muted-foreground">({formatFileSize(stats.total_storage_bytes)})</span>
						{/if}
					</dd>
					<dt class="text-muted-foreground">Runs</dt>
					<dd>
						<a href={filterUrl('/runs', [{ field: 'owner', values: [user.username] }])} class="underline-offset-2 hover:underline">{stats.runs_total}</a>
						{#if barSegments.length > 0}
							<div class="mt-1 flex h-5 w-full overflow-hidden rounded text-[10px] font-medium leading-5">
								{#each barSegments as seg}
									{@const pct = (seg.count / stats.runs_total) * 100}
									<a
										href={filterUrl('/runs', [
											{ field: 'owner', values: [user.username] },
											{ field: 'status', values: seg.statuses }
										])}
										class="overflow-hidden text-center transition-opacity hover:opacity-80 {seg.color}"
										style="width: {pct}%"
										title="{seg.count} {seg.label} — click to filter"
									>
										{#if pct >= 15}
											<span class="px-1">{seg.count} {seg.label}</span>
										{:else if pct >= 8}
											<span class="px-0.5">{seg.count}</span>
										{/if}
									</a>
								{/each}
							</div>
						{/if}
						{#if Object.keys(stats.runs_by_backend).length > 0}
							<div class="mt-1 flex h-5 w-full overflow-hidden rounded text-[10px] font-medium leading-5">
								{#each Object.entries(stats.runs_by_backend) as [name, count], i}
									{@const pct = (count / stats.runs_total) * 100}
									<a
										href={filterUrl('/runs', [
											{ field: 'owner', values: [user.username] },
											{ field: 'backend', values: [name] }
										])}
										class="overflow-hidden text-center transition-opacity hover:opacity-80 {BACKEND_COLORS[i % BACKEND_COLORS.length]}"
										style="width: {pct}%"
										title="{count} on {name} — click to filter"
									>
										{#if pct >= 15}
											<span class="px-1">{count} {name}</span>
										{:else if pct >= 8}
											<span class="px-0.5">{count}</span>
										{/if}
									</a>
								{/each}
							</div>
						{/if}
					</dd>
					<dt class="text-muted-foreground">Last activity</dt>
					<dd>
						{#if stats.last_activity}
							<span title={formatDate(stats.last_activity)}>{formatRelativeTime(stats.last_activity)}</span>
						{:else}
							<span class="text-muted-foreground">—</span>
						{/if}
					</dd>
				</dl>
			</section>
		{/if}

		<section class="space-y-2 rounded-md border p-4">
			<h2 class="text-sm font-semibold">Backends</h2>
			<AssignmentList
				items={userBackends}
				candidates={allBackends}
				labelOf={(b) => b.name}
				onAdd={assignBackend}
				onRemove={removeBackend}
				emptyText="No backends assigned."
				addLabel="Assign backend"
			/>
		</section>

		{#if user.role === 'bot'}
			<section class="space-y-2 rounded-md border p-4">
				<div class="flex items-center justify-between">
					<h2 class="text-sm font-semibold">API keys</h2>
					<Button size="sm" variant="outline" onclick={() => (createKeyOpen = true)}>
						<Plus class="mr-1 size-3.5" />
						Create API key
					</Button>
				</div>
				{#if userKeys.length === 0}
					<p class="text-xs text-muted-foreground">No API keys.</p>
				{:else}
					<table class="w-full text-xs">
						<thead class="text-left text-muted-foreground">
							<tr>
								<th class="py-1 pr-2 font-normal">Name</th>
								<th class="py-1 pr-2 font-normal">Prefix</th>
								<th class="py-1 pr-2 font-normal">Created</th>
								<th class="py-1 pr-2 font-normal">Last used</th>
								<th class="py-1 pr-2 font-normal">Expires</th>
								<th class="py-1"></th>
							</tr>
						</thead>
						<tbody>
							{#each userKeys as key (key.id)}
								<tr class="border-t">
									<td class="py-1.5 pr-2">{key.name}</td>
									<td class="py-1.5 pr-2 font-mono">{key.key_prefix}...</td>
									<td class="py-1.5 pr-2"><DateTime value={key.created_at} /></td>
									<td class="py-1.5 pr-2"><DateTime value={key.last_used_at} /></td>
									<td class="py-1.5 pr-2"><DateTime value={key.expires_at} /></td>
									<td class="py-1.5">
										<Button
											variant="ghost"
											size="icon"
											class="size-6"
											onclick={() => {
												keyToDelete = key;
												confirmDeleteKeyOpen = true;
											}}
											title="Delete"
										>
											<Trash2 class="size-3.5 text-destructive" />
										</Button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</section>
		{/if}

		{#if !isSelf}
			<section class="space-y-2 rounded-md border border-destructive/30 p-4">
				<h2 class="text-sm font-semibold text-destructive">Danger zone</h2>
				<Button variant="destructive" size="sm" onclick={() => (confirmDeleteOpen = true)}>
					Delete user
				</Button>
			</section>
		{/if}
	{/if}
</div>

<Dialog.Root bind:open={confirmDeleteOpen}>
	<Dialog.Content class="max-w-xs">
		<Dialog.Header>
			<Dialog.Title>Delete User</Dialog.Title>
			<Dialog.Description>
				Delete user "{user?.username}"? Cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		<div class="flex justify-end gap-2">
			<Button variant="outline" size="sm" onclick={() => (confirmDeleteOpen = false)}
				>Cancel</Button
			>
			<Button variant="destructive" size="sm" onclick={deleteUser}>Delete</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={confirmDeleteKeyOpen}>
	<Dialog.Content class="max-w-xs">
		<Dialog.Header>
			<Dialog.Title>Delete API Key</Dialog.Title>
			<Dialog.Description>
				Delete API key "{keyToDelete?.name}"? Cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		<div class="flex justify-end gap-2">
			<Button variant="outline" size="sm" onclick={() => (confirmDeleteKeyOpen = false)}
				>Cancel</Button
			>
			<Button variant="destructive" size="sm" onclick={deleteApiKey}>Delete</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={createKeyOpen}>
	<Dialog.Content class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Create API Key</Dialog.Title>
			<Dialog.Description>
				Create an API key for {user?.username}.
			</Dialog.Description>
		</Dialog.Header>
		{#if createdKey}
			<ApiKeyReveal
				token={createdKey}
				onDone={() => {
					createdKey = null;
					createKeyOpen = false;
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
					<Button variant="outline" size="sm" onclick={() => (createKeyOpen = false)}
						>Cancel</Button
					>
					<Button
						size="sm"
						disabled={!newKeyName.trim() || creatingKey}
						onclick={createApiKey}
					>
						{creatingKey ? 'Creating...' : 'Create'}
					</Button>
				</div>
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
