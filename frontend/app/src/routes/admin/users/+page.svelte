<script lang="ts">
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { admin, apiKeys } from '$lib/api/client.js';
	import { formatDate } from '$lib/utils.js';
	import { Check, Clock, User as UserIcon, Shield, Settings, Bot, Plus, Trash2, Copy, Key } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Table from '$lib/components/ui/table';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Tabs from '$lib/components/ui/tabs';
	import { Badge } from '$lib/components/ui/badge';
	import UsersSkeleton from './components/UsersSkeleton.svelte';
	import { toast } from 'svelte-sonner';
	import type { User, ApiKey } from '$lib/types.js';

	let users = $state<User[]>([]);
	let loading = $state(true);
	let filter = $state('all');
	let selectedUser = $state<User | null>(null);
	let dialogOpen = $state(false);
	let allPermissions = $state<string[]>([]);
	let rolePermissions = $state<Record<string, string[]>>({});

	// Create User dialog
	let createUserOpen = $state(false);
	let newUsername = $state('');
	let newUserRole = $state('bot');
	let newAvatarUrl = $state('');
	let creatingUser = $state(false);

	// API Keys
	let keys = $state<ApiKey[]>([]);
	let keysLoading = $state(true);
	let createKeyOpen = $state(false);
	let newKeyName = $state('');
	let newKeyUserId = $state('');
	let newKeyExpiryDays = $state(90);
	let creatingKey = $state(false);
	let createdKey = $state<string | null>(null);

	let botUsers = $derived(users.filter(u => u.role === 'bot'));

	onMount(async () => {
		await Promise.all([loadUsers(), loadPermissions(), loadApiKeys()]);
	});

	async function loadPermissions() {
		try {
			const response = await admin.getPermissions();
			allPermissions = response.permissions as string[];
			rolePermissions = response.role_permissions as Record<string, string[]>;
		} catch (err) {
			toast.error(`Failed to load permissions: ${(err as Error).message}`);
		}
	}

	async function loadUsers() {
		loading = true;
		try {
			const role = filter === 'all' ? null : filter;
			const response = await admin.listUsers(0, 100, role);
			users = response.data;
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}

	async function loadApiKeys() {
		keysLoading = true;
		try {
			keys = await apiKeys.list();
		} catch (err) {
			toast.error(`Failed to load API keys: ${(err as Error).message}`);
		} finally {
			keysLoading = false;
		}
	}

	async function approveUser(userId: string) {
		try {
			await admin.approveUser(userId);
			await loadUsers();
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function updateRole(userId: string, newRole: string) {
		try {
			await admin.updateUserRole(userId, newRole);
			await loadUsers();
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function deleteUser(userId: string, username: string) {
		if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
			return;
		}
		try {
			await admin.deleteUser(userId);
			await loadUsers();
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function handleFilterChange(newFilter: string) {
		filter = newFilter;
		await loadUsers();
	}

	function openPermissions(user: User) {
		selectedUser = user;
		dialogOpen = true;
	}

	function getRole(user: User) {
		return user.role;
	}

	function getRoleBadgeVariant(role: string) {
		if (role === 'admin') return 'default';
		if (role === 'bot') return 'secondary';
		if (role === 'user') return 'secondary';
		return 'outline';
	}

	async function createUser() {
		if (!newUsername.trim()) return;
		creatingUser = true;
		try {
			await admin.createUser(newUsername.trim(), newUserRole, newAvatarUrl.trim() || undefined);
			newUsername = '';
			newUserRole = 'bot';
			newAvatarUrl = '';
			createUserOpen = false;
			await loadUsers();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			creatingUser = false;
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
				createKeyOpen = false;
			}
			await loadApiKeys();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			creatingKey = false;
		}
	}

	async function deleteApiKey(keyId: string, keyName: string) {
		if (!confirm(`Are you sure you want to delete API key "${keyName}"?`)) return;
		try {
			await apiKeys.delete(keyId);
			await loadApiKeys();
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
	}

	function getUsernameById(userId: string): string {
		return users.find(u => u.id === userId)?.username ?? userId.slice(0, 8);
	}

</script>

<svelte:head>
	<title>Admin - User Management - PyPSA App</title>
</svelte:head>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-bold">User Management</h1>
		<p class="text-muted-foreground">Manage user accounts, permissions, and API keys</p>
	</div>

	<Tabs.Root value="users">
		<Tabs.List>
			<Tabs.Trigger value="users">Users</Tabs.Trigger>
			<Tabs.Trigger value="api-keys">API Keys</Tabs.Trigger>
		</Tabs.List>

		<!-- Users Tab -->
		<Tabs.Content value="users" class="space-y-4">
			<div class="flex items-center justify-between">
				<div class="flex gap-2">
					<Button
						variant={filter === 'all' ? 'default' : 'outline'}
						size="sm"
						onclick={() => handleFilterChange('all')}
					>
						All
					</Button>
					<Button
						variant={filter === 'pending' ? 'default' : 'outline'}
						size="sm"
						onclick={() => handleFilterChange('pending')}
					>
						<Clock class="mr-1 size-4" />
						Pending
					</Button>
					<Button
						variant={filter === 'user' ? 'default' : 'outline'}
						size="sm"
						onclick={() => handleFilterChange('user')}
					>
						<UserIcon class="mr-1 size-4" />
						Users
					</Button>
					<Button
						variant={filter === 'admin' ? 'default' : 'outline'}
						size="sm"
						onclick={() => handleFilterChange('admin')}
					>
						<Shield class="mr-1 size-4" />
						Admins
					</Button>
					<Button
						variant={filter === 'bot' ? 'default' : 'outline'}
						size="sm"
						onclick={() => handleFilterChange('bot')}
					>
						<Bot class="mr-1 size-4" />
						Bots
					</Button>
				</div>
				<Button size="sm" onclick={() => createUserOpen = true}>
					<Plus class="mr-1 size-4" />
					Create User
				</Button>
			</div>

			{#if loading}
				<UsersSkeleton />
			{:else if users.length === 0}
				<p class="text-muted-foreground">No users found.</p>
			{:else}
				<div class="rounded-md border">
					<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>User</Table.Head>
								<Table.Head>Email</Table.Head>
								<Table.Head>Role</Table.Head>
								<Table.Head>Created</Table.Head>
								<Table.Head>Last Login</Table.Head>
								<Table.Head class="text-right">Actions</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each users as user}
								{@const userRole = getRole(user)}
								<Table.Row>
									<Table.Cell>
										<div class="flex items-center gap-2">
											<Avatar.Root class="size-8">
												<Avatar.Image class="" src={user.avatar_url} alt={user.username} />
												<Avatar.Fallback class="">
													{user.username.substring(0, 2).toUpperCase()}
												</Avatar.Fallback>
											</Avatar.Root>
											<span class="font-medium">{user.username}</span>
										</div>
									</Table.Cell>
									<Table.Cell>{user.email || '-'}</Table.Cell>
									<Table.Cell>
										<Badge variant={getRoleBadgeVariant(userRole)}>
											{userRole}
										</Badge>
									</Table.Cell>
									<Table.Cell>{formatDate(user.created_at)}</Table.Cell>
									<Table.Cell>{formatDate(user.last_login)}</Table.Cell>
									<Table.Cell class="text-right">
										<div class="flex justify-end gap-1">
											{#if userRole === 'pending'}
												<Button
													variant="ghost"
													size="icon"
													class="size-8"
													onclick={() => approveUser(user.id)}
													title="Approve"
												>
													<Check class="size-4 text-green-600" />
												</Button>
											{/if}
											<Button
												variant="ghost"
												size="icon"
												class="size-8"
												onclick={() => openPermissions(user)}
												title="Permissions"
											>
												<Settings class="size-4" />
											</Button>
										</div>
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>
				</div>
			{/if}
		</Tabs.Content>

		<!-- API Keys Tab -->
		<Tabs.Content value="api-keys" class="space-y-4">
			<div class="flex items-center justify-end">
				<Button size="sm" onclick={() => { createdKey = null; createKeyOpen = true; }}>
					<Plus class="mr-1 size-4" />
					Create API Key
				</Button>
			</div>

			{#if keysLoading}
				<div class="text-muted-foreground text-sm">Loading API keys...</div>
			{:else if keys.length === 0}
				<p class="text-muted-foreground text-sm">No API keys created yet.</p>
			{:else}
				<div class="rounded-md border">
					<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>Name</Table.Head>
								<Table.Head>Prefix</Table.Head>
								<Table.Head>Bot User</Table.Head>
								<Table.Head>Created</Table.Head>
								<Table.Head>Last Used</Table.Head>
								<Table.Head>Expires</Table.Head>
								<Table.Head class="text-right">Actions</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each keys as key}
								<Table.Row>
									<Table.Cell>
										<div class="flex items-center gap-2">
											<Key class="size-4 text-muted-foreground" />
											<span class="font-medium">{key.name}</span>
										</div>
									</Table.Cell>
									<Table.Cell><code class="text-xs">{key.key_prefix}...</code></Table.Cell>
									<Table.Cell>{getUsernameById(key.user_id)}</Table.Cell>
									<Table.Cell>{formatDate(key.created_at)}</Table.Cell>
									<Table.Cell>{formatDate(key.last_used_at)}</Table.Cell>
									<Table.Cell>{formatDate(key.expires_at)}</Table.Cell>
									<Table.Cell class="text-right">
										<Button
											variant="ghost"
											size="icon"
											class="size-8"
											onclick={() => deleteApiKey(key.id, key.name)}
											title="Delete"
										>
											<Trash2 class="size-4 text-destructive" />
										</Button>
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>
				</div>
			{/if}
		</Tabs.Content>
	</Tabs.Root>
</div>

<!-- Permissions Dialog -->
<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Content class="max-w-xs">
		{#if selectedUser}
			{@const userRole = getRole(selectedUser)}
			<Dialog.Header>
				<Dialog.Title class="flex items-center gap-2 text-sm">
					<Avatar.Root class="size-6">
						<Avatar.Image class="" src={selectedUser.avatar_url} alt={selectedUser.username} />
						<Avatar.Fallback class="text-xs">
							{selectedUser.username.substring(0, 2).toUpperCase()}
						</Avatar.Fallback>
					</Avatar.Root>
					{selectedUser.username}
				</Dialog.Title>
			</Dialog.Header>
			<div class="space-y-3 text-xs">
				<div class="space-y-1 text-muted-foreground">
					<p>{selectedUser.email || 'No email'}</p>
					<p>Created: {formatDate(selectedUser.created_at)}</p>
					<p>Last login: {formatDate(selectedUser.last_login)}</p>
				</div>
				<div class="flex items-center justify-between">
					<span class="text-muted-foreground">Role</span>
					{#if selectedUser.id === authStore.user?.id}
						<Badge variant="outline" class="text-xs">{userRole} (you)</Badge>
					{:else}
						<select
							class="rounded border bg-background px-2 py-1 text-xs"
							value={userRole}
							onchange={(e: Event) => updateRole(selectedUser!.id, (e.target as HTMLSelectElement).value)}
						>
							<option value="admin">admin</option>
							<option value="user">user</option>
							<option value="bot">bot</option>
							<option value="pending">pending</option>
						</select>
					{/if}
				</div>
				<div class="space-y-1">
					<span class="text-muted-foreground">Permissions</span>
					<div class="flex flex-wrap gap-1">
						{#each allPermissions as perm}
							{@const hasPerm = selectedUser.permissions?.includes(perm)}
							<code class="rounded px-1.5 py-0.5 text-xs {hasPerm ? 'bg-muted' : 'bg-muted/30 text-muted-foreground line-through'}">{perm}</code>
						{/each}
					</div>
				</div>
				{#if selectedUser.id !== authStore.user?.id}
					<button
						class="text-destructive hover:underline"
						onclick={() => { deleteUser(selectedUser!.id, selectedUser!.username); dialogOpen = false; }}
					>
						Delete user
					</button>
				{/if}
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>

<!-- Create User Dialog -->
<Dialog.Root bind:open={createUserOpen}>
	<Dialog.Content class="max-w-xs">
		<Dialog.Header>
			<Dialog.Title>Create User</Dialog.Title>
			<Dialog.Description>Create a new user account.</Dialog.Description>
		</Dialog.Header>
		<div class="space-y-4">
			<div class="space-y-2">
				<label for="new-username" class="text-sm font-medium">Username</label>
				<input
					id="new-username"
					type="text"
					class="w-full rounded-md border bg-background px-3 py-2 text-sm"
					placeholder="username"
					bind:value={newUsername}
					onkeydown={(e: KeyboardEvent) => { if (e.key === 'Enter') createUser(); }}
				/>
			</div>
			<div class="space-y-2">
				<label for="new-user-role" class="text-sm font-medium">Role</label>
				<select
					id="new-user-role"
					class="w-full rounded-md border bg-background px-3 py-2 text-sm"
					bind:value={newUserRole}
				>
					<option value="bot">bot</option>
				</select>
				<p class="text-xs text-muted-foreground">Only bot users can be created via the admin panel.</p>
			</div>
			<div class="space-y-2">
				<label for="new-avatar-url" class="text-sm font-medium">Avatar URL <span class="text-muted-foreground font-normal">(optional)</span></label>
				<input
					id="new-avatar-url"
					type="url"
					class="w-full rounded-md border bg-background px-3 py-2 text-sm"
					placeholder="https://github.com/user.png"
					bind:value={newAvatarUrl}
				/>
			</div>
			<div class="flex justify-end gap-2">
				<Button variant="outline" size="sm" onclick={() => createUserOpen = false}>Cancel</Button>
				<Button size="sm" disabled={!newUsername.trim() || creatingUser} onclick={createUser}>
					{creatingUser ? 'Creating...' : 'Create'}
				</Button>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>

<!-- Create API Key Dialog -->
<Dialog.Root bind:open={createKeyOpen}>
	<Dialog.Content class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Create API Key</Dialog.Title>
			<Dialog.Description>Create a new API key linked to a bot user.</Dialog.Description>
		</Dialog.Header>

		{#if createdKey}
			<div class="space-y-4">
				<div class="rounded-md border border-green-500/30 bg-green-500/10 p-3">
					<p class="mb-2 text-sm font-medium">API key created successfully!</p>
					<p class="mb-2 text-xs text-muted-foreground">Copy this key now. You won't be able to see it again.</p>
					<div class="flex items-center gap-2">
						<code class="flex-1 break-all rounded bg-muted px-2 py-1 text-xs">{createdKey}</code>
						<Button variant="outline" size="icon" class="size-8 shrink-0" onclick={() => copyToClipboard(createdKey!)} title="Copy">
							<Copy class="size-4" />
						</Button>
					</div>
				</div>
				<div class="flex justify-end">
					<Button size="sm" onclick={() => { createdKey = null; createKeyOpen = false; }}>Done</Button>
				</div>
			</div>
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
					<select
						id="key-user"
						class="w-full rounded-md border bg-background px-3 py-2 text-sm"
						bind:value={newKeyUserId}
					>
						<option value="">Select a user...</option>
						{#each botUsers as bot}
							<option value={bot.id}>{bot.username}</option>
						{/each}
					</select>
					{#if botUsers.length === 0}
						<p class="text-xs text-muted-foreground">No bot users available. Create one first.</p>
					{/if}
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
					<Button variant="outline" size="sm" onclick={() => createKeyOpen = false}>Cancel</Button>
					<Button size="sm" disabled={!newKeyName.trim() || !newKeyUserId || creatingKey} onclick={createApiKey}>
						{creatingKey ? 'Creating...' : 'Create'}
					</Button>
				</div>
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
