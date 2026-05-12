<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { admin } from '$lib/api/client.js';
	import Server from '@lucide/svelte/icons/server';
	import DataTable from '$lib/components/DataTable.svelte';
	import type { FilterCategory } from '$lib/components/ui/filter-dialog';
	import type { FilterAst } from '$lib/filters/ast';
	import { emptyAnd } from '$lib/filters/ast';
	import { filterStateFromAst } from '$lib/filters/legacy';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { TableSkeleton } from '$lib/components/skeletons';
	import { createColumns } from '../components/backend-columns.js';
	import { toast } from 'svelte-sonner';
	import type { Backend } from '$lib/types.js';
	import type { SortingState } from '@tanstack/table-core';

	let allBackends = $state<Backend[]>([]);
	let filter = $state<FilterAst>(emptyAnd());

	const filterCategories: FilterCategory[] = [
		{
			key: 'status',
			label: 'Status',
			options: [
				{ id: 'active', label: 'Active' },
				{ id: 'inactive', label: 'Inactive' }
			]
		}
	];

	const filterStatus = $derived(filterStateFromAst(filter, ['status']).status ?? new Set<string>());
	let backends = $derived(
		filterStatus.size
			? allBackends.filter((b) => filterStatus.has(b.is_active ? 'active' : 'inactive'))
			: allBackends
	);
	let loading = $state(true);
	let sorting = $state<SortingState>([]);

	const columns = $derived(
		createColumns({
			onManageUsers: (backend) => goto(`/admin/backends/${backend.id}`)
		})
	);

	onMount(loadBackends);

	$effect(() => {
		breadcrumbStore.set([{ label: 'Backends' }]);
	});

	onDestroy(() => {
		breadcrumbStore.clear();
	});

	async function loadBackends() {
		loading = true;
		try {
			allBackends = await admin.listBackends();
		} catch (err) {
			toast.error((err as Error).message);
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Admin - Backends - PyPSA App</title>
</svelte:head>

{#if loading}
	<TableSkeleton rows={3} columns={5} />
{:else if backends.length === 0}
	<div class="rounded-md border p-6 text-center text-muted-foreground">
		<Server class="mx-auto mb-2 size-8" />
		<p>No backends configured.</p>
		<p class="mt-1 text-xs">
			Set <code>SNAKEDISPATCH_BACKENDS</code> to register backends.
		</p>
	</div>
{:else}
	<DataTable
		data={backends}
		columns={columns as any}
		bind:sorting
		{filterCategories}
		{filter}
		onFilterAstChange={(ast) => (filter = ast)}
		onRowClick={(backend: Backend) => goto(`/admin/backends/${backend.id}`)}
	/>
{/if}
