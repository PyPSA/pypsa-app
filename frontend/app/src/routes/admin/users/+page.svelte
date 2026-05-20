<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { admin } from '$lib/api/client.js';
	import Plus from '@lucide/svelte/icons/plus';
	import Users from '@lucide/svelte/icons/users';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import DataTable from '$lib/components/DataTable.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import type { FilterCategory } from '$lib/components/widgets/filter-dialog';
	import type { FilterAst } from '$lib/filters/ast';
	import { emptyAnd, isEmpty as astIsEmpty } from '$lib/filters/ast';
	import { parse as parseDsl, serialize as serializeDsl } from '$lib/filters/dsl';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { TableSkeleton } from '$lib/components/skeletons';
	import { createColumns } from '../components/user-columns.js';
	import { toast } from 'svelte-sonner';
	import type { User } from '$lib/types.js';
	import type { SortingState } from '@tanstack/table-core';

	const roleOptions = ['admin', 'user', 'bot', 'pending'];

	let users = $state<User[]>([]);
	let totalUsers = $state(0);
	let loading = $state(true);
	let filter = $state<FilterAst>(emptyAnd());
	let currentPage = $state(1);
	let pageSize = $state(25);
	const defaultSorting: SortingState = [{ id: 'created_at', desc: true }];
	let sorting = $state<SortingState>([...defaultSorting]);

	let createOpen = $state(false);
	let newUsername = $state('');
	let newUserRole = $state('bot');
	let newAvatarUrl = $state('');
	let creatingUser = $state(false);

	const filterCategories: FilterCategory[] = [
		{
			key: 'role',
			label: 'Role',
			options: roleOptions.map((r) => ({ id: r, label: r }))
		}
	];

	const columns = $derived(
		createColumns({
			onApprove: approveUser,
			onOpenPermissions: (user) => goto(`/admin/users/${user.id}`)
		})
	);

	function restoreFromUrl() {
		const params = $page.url.searchParams;
		const urlPage = params.get('page');
		if (urlPage) {
			const parsed = parseInt(urlPage);
			if (!isNaN(parsed) && parsed > 0) currentPage = parsed;
		}
		const urlSize = params.get('size');
		if (urlSize) {
			const parsed = parseInt(urlSize);
			if (!isNaN(parsed) && parsed > 0) pageSize = parsed;
		}
		const q = params.get('q');
		if (q) {
			const result = parseDsl(q);
			if (result.errors.length === 0) filter = result.ast;
		}
	}

	async function updateURL() {
		if (!browser) return;
		const url = new URL(window.location.href);
		url.searchParams.set('page', currentPage.toString());
		url.searchParams.set('size', pageSize.toString());
		const dsl = astIsEmpty(filter) ? '' : serializeDsl(filter);
		if (dsl) url.searchParams.set('q', dsl);
		else url.searchParams.delete('q');
		await goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
	}

	onMount(async () => {
		restoreFromUrl();
		await loadUsers();
	});

	$effect(() => {
		breadcrumbStore.set([{ label: 'Users' }]);
	});

	onDestroy(() => {
		breadcrumbStore.clear();
	});

	async function loadUsers() {
		loading = true;
		try {
			const skip = (currentPage - 1) * pageSize;
			const filterQ = astIsEmpty(filter) ? undefined : JSON.stringify(filter);
			const sort_by = sorting[0]?.id;
			const sort_dir = sorting[0]?.desc ? 'desc' : 'asc';
			const response = await admin.listUsers(skip, pageSize, {
				sort_by,
				sort_dir,
				filter_q: filterQ
			});
			users = response.data;
			totalUsers = response.meta.total;
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}

	async function handleSortingChange(newSorting: SortingState) {
		sorting = newSorting;
		currentPage = 1;
		await loadUsers();
	}

	async function handleFilterChange(ast: FilterAst) {
		filter = ast;
		currentPage = 1;
		await updateURL();
		await loadUsers();
	}

	async function handlePageChange(p: number) {
		currentPage = p;
		await updateURL();
		await loadUsers();
	}

	async function handlePageSizeChange(size: number) {
		pageSize = size;
		currentPage = 1;
		await updateURL();
		await loadUsers();
	}

	async function approveUser(userId: string) {
		try {
			await admin.approveUser(userId);
			toast.success('User approved');
			await loadUsers();
		} catch (err) {
			toast.error((err as Error).message);
		}
	}

	async function createUser() {
		if (!newUsername.trim()) return;
		creatingUser = true;
		try {
			await admin.createUser(
				newUsername.trim(),
				newUserRole,
				newAvatarUrl.trim() || undefined
			);
			newUsername = '';
			newUserRole = 'bot';
			newAvatarUrl = '';
			createOpen = false;
			toast.success('User created');
			await loadUsers();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			creatingUser = false;
		}
	}
</script>

<svelte:head>
	<title>Admin - Users - PyPSA App</title>
</svelte:head>

<div class="flex justify-end mb-4">
	<Button size="sm" onclick={() => (createOpen = true)}>
		<Plus class="mr-1 size-4" />
		Create User
	</Button>
</div>

{#if loading}
	<TableSkeleton rows={5} columns={6} />
{:else if users.length === 0}
	<EmptyState
		icon={Users}
		title="No Users"
		description="No users match the current filter."
	/>
{:else}
	<DataTable
		data={users}
		columns={columns as any}
		totalItems={totalUsers}
		{currentPage}
		{pageSize}
		bind:sorting
		{defaultSorting}
		onSortingChange={handleSortingChange}
		{filterCategories}
		{filter}
		onFilterAstChange={handleFilterChange}
		onPageChange={handlePageChange}
		onPageSizeChange={handlePageSizeChange}
		onRowClick={(user: User) => goto(`/admin/users/${user.id}`)}
	/>
{/if}

<Dialog.Root bind:open={createOpen}>
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
					onkeydown={(e: KeyboardEvent) => {
						if (e.key === 'Enter') createUser();
					}}
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
				<p class="text-xs text-muted-foreground">
					Only bot users can be created via the admin panel.
				</p>
			</div>
			<div class="space-y-2">
				<label for="new-avatar-url" class="text-sm font-medium"
					>Avatar URL
					<span class="text-muted-foreground font-normal">(optional)</span></label
				>
				<input
					id="new-avatar-url"
					type="url"
					class="w-full rounded-md border bg-background px-3 py-2 text-sm"
					placeholder="https://github.com/user.png"
					bind:value={newAvatarUrl}
				/>
			</div>
			<div class="flex justify-end gap-2">
				<Button variant="outline" size="sm" onclick={() => (createOpen = false)}>Cancel</Button>
				<Button
					size="sm"
					disabled={!newUsername.trim() || creatingUser}
					onclick={createUser}
				>
					{creatingUser ? 'Creating...' : 'Create'}
				</Button>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>
