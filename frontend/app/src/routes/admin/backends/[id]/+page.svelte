<script lang="ts">
	import { onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { admin } from '$lib/api/client.js';
	import DateTime from '$lib/components/DateTime.svelte';
	import * as Avatar from '$lib/components/ui/avatar';
	import { Badge } from '$lib/components/ui/badge';
	import AssignmentList from '$lib/components/admin/AssignmentList.svelte';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { toast } from 'svelte-sonner';
	import type { Backend, User } from '$lib/types.js';

	const backendId = $derived($page.params.id as string);

	let backend = $state<Backend | null>(null);
	let loading = $state(true);
	let assignedUsers = $state<User[]>([]);
	let allUsers = $state<User[]>([]);

	$effect(() => {
		if (backendId) loadAll();
	});

	$effect(() => {
		if (backend) {
			breadcrumbStore.set([
				{ label: 'Backends', href: '/admin/backends' },
				{ label: backend.name }
			]);
		}
	});

	onDestroy(() => {
		breadcrumbStore.clear();
	});

	async function loadAll() {
		loading = true;
		try {
			// TODO: replace with a server-side search endpoint; instances with more
			// than this many users will see truncated assignment candidates.
			const USER_CANDIDATE_CAP = 10000;
			const [b, users, allU] = await Promise.all([
				admin.getBackend(backendId),
				admin.listBackendUsers(backendId),
				admin.listUsers(0, USER_CANDIDATE_CAP)
			]);
			backend = b;
			assignedUsers = users;
			allUsers = allU.data;
		} catch {
		} finally {
			loading = false;
		}
	}

	async function assignUser(userId: string) {
		if (!backend) return;
		try {
			await admin.assignUserToBackend(backend.id, userId);
			assignedUsers = await admin.listBackendUsers(backend.id);
			toast.success('User assigned');
		} catch {}
	}

	async function removeUser(userId: string) {
		if (!backend) return;
		try {
			await admin.unassignUserFromBackend(backend.id, userId);
			assignedUsers = await admin.listBackendUsers(backend.id);
			toast.success('User removed');
		} catch {}
	}
</script>

<svelte:head>
	<title>Admin - {backend?.name ?? 'Backend'} - PyPSA App</title>
</svelte:head>

<div class="space-y-6">
	{#if loading || !backend}
		<p class="text-muted-foreground">Loading...</p>
	{:else}
		<header class="space-y-1">
			<div class="flex items-center gap-2">
				<h1 class="text-xl font-semibold">{backend.name}</h1>
				<Badge variant={backend.is_active ? 'default' : 'outline'}>
					{backend.is_active ? 'active' : 'inactive'}
				</Badge>
			</div>
			<p class="text-sm text-muted-foreground break-all">{backend.url}</p>
		</header>

		<section class="space-y-2 rounded-md border p-4">
			<h2 class="text-sm font-semibold">Overview</h2>
			<dl class="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-xs">
				<dt class="text-muted-foreground">ID</dt>
				<dd class="font-mono">{backend.id}</dd>
				<dt class="text-muted-foreground">URL</dt>
				<dd class="break-all">{backend.url}</dd>
				<dt class="text-muted-foreground">Status</dt>
				<dd>{backend.is_active ? 'active' : 'inactive'}</dd>
				<dt class="text-muted-foreground">Created</dt>
				<dd><DateTime value={backend.created_at} /></dd>
				<dt class="text-muted-foreground">Updated</dt>
				<dd><DateTime value={backend.updated_at} /></dd>
			</dl>
		</section>

		<section class="space-y-2 rounded-md border p-4">
			<h2 class="text-sm font-semibold">Assigned users</h2>
			<AssignmentList
				items={assignedUsers}
				candidates={allUsers}
				labelOf={(u) => u.username}
				onAdd={assignUser}
				onRemove={removeUser}
				emptyText="No users assigned."
				addLabel="Assign user"
			>
				{#snippet rowSnippet(user: User)}
					<a
						href="/admin/users/{user.id}"
						class="flex items-center gap-2 text-sm hover:underline"
					>
						<Avatar.Root class="size-6">
							<Avatar.Image src={user.avatar_url} alt={user.username} />
							<Avatar.Fallback class="text-xs">
								{user.username.substring(0, 2).toUpperCase()}
							</Avatar.Fallback>
						</Avatar.Root>
						<span>{user.username}</span>
						<Badge variant="outline" class="text-[10px]">{user.role}</Badge>
					</a>
				{/snippet}
			</AssignmentList>
		</section>

	{/if}
</div>
