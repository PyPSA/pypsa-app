<script lang="ts">
	import { goto } from '$app/navigation';
	import { networks } from '$lib/api/client.js';
	import type { ComponentDataResponse } from '$lib/types.js';
	import type { ComponentTableCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { reportStore } from '$lib/stores/reportStore.svelte.js';
	import DataTable from '$lib/components/DataTable.svelte';
	import type { ColumnDef } from '@tanstack/svelte-table';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import type { NetworkWithFacets } from '../types.js';

	interface Props {
		card: ComponentTableCardDefinition;
		networkId: string;
		network: NetworkWithFacets;
		reportId: string;
		onremove?: () => void;
		onfullscreen?: () => void;
	}

	let { card, networkId, network, reportId, onremove, onfullscreen }: Props = $props();

	let loading = $state(true);
	let error = $state<string | null>(null);
	let response = $state<ComponentDataResponse | null>(null);
	let currentPage = $state(1);
	let pageSize = $state(50);

	const componentNames = $derived(
		network.components_count ? Object.keys(network.components_count).sort() : []
	);

	type RowData = Record<string, unknown>;

	const columns = $derived.by((): ColumnDef<RowData, unknown>[] => {
		if (!response) return [];
		const indexCol: ColumnDef<RowData, unknown> = {
			accessorKey: '__index__',
			header: 'Name',
			enableSorting: true,
		};
		const dataCols: ColumnDef<RowData, unknown>[] = response.columns.map((col) => ({
			accessorKey: col,
			header: col,
			enableSorting: true,
		}));
		return [indexCol, ...dataCols];
	});

	const tableData = $derived.by((): RowData[] => {
		if (!response) return [];
		return response.data.map((row, i) => {
			const obj: RowData = { __index__: response!.index[i] };
			response!.columns.forEach((col, j) => {
				obj[col] = row[j];
			});
			return obj;
		});
	});

	async function fetchData() {
		loading = true;
		error = null;
		try {
			const offset = (currentPage - 1) * pageSize;
			response = await networks.getComponentData(networkId, card.component, {
				offset,
				limit: pageSize,
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load component data';
		} finally {
			loading = false;
		}
	}

	function handleComponentChange(e: Event) {
		const select = e.target as HTMLSelectElement;
		reportStore.updateCard(reportId, card.id, { component: select.value });
		currentPage = 1;
	}

	let prevKey = '';
	$effect(() => {
		const key = `${networkId}-${card.component}-${currentPage}-${pageSize}`;
		if (key !== prevKey) {
			prevKey = key;
			fetchData();
		}
	});
</script>

<div class="group/card bg-card rounded-lg border border-border overflow-hidden flex flex-col h-full relative">
	<div class="card-drag-handle flex items-center justify-between px-3 py-1 border-b border-border/50 shrink-0 cursor-grab">
		<div class="flex items-center gap-2 min-w-0">
			{#if onfullscreen}
				<button class="text-xs font-medium text-muted-foreground truncate hover:text-foreground transition-colors cursor-pointer" onclick={onfullscreen}>
					{card.name ?? 'Component Table'}
				</button>
			{:else}
				<span class="text-xs font-medium text-muted-foreground truncate">{card.name ?? 'Component Table'}</span>
			{/if}
			<select
				class="text-xs bg-transparent border border-border/50 rounded px-1.5 py-0.5 text-foreground cursor-pointer hover:border-border"
				value={card.component}
				onchange={handleComponentChange}
				onclick={(e) => e.stopPropagation()}
			>
				{#each componentNames as name}
					<option value={name}>{name} ({network.components_count?.[name] ?? 0})</option>
				{/each}
			</select>
		</div>
		<div class="flex items-center gap-0.5">
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props })}
						<Button variant="ghost" size="icon" class="h-6 w-6" {...props}>
							<Ellipsis class="h-3 w-3" />
						</Button>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end" class="w-36">
					<DropdownMenu.Item onclick={() => goto(`/networks/${networkId}/data/${card.component}`)}>
						<ExternalLink class="h-3.5 w-3.5 mr-2" />
						Full view
					</DropdownMenu.Item>
					<DropdownMenu.Item onclick={onremove}>
						<Trash2 class="h-3.5 w-3.5 mr-2" />
						Remove
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</div>
	</div>

	<div class="flex-1 min-h-0 overflow-auto p-2">
		{#if loading && !response}
			<div class="flex items-center justify-center h-full text-sm text-muted-foreground">
				Loading…
			</div>
		{:else if error}
			<div class="flex items-center justify-center h-full text-sm text-destructive p-4">
				{error}
			</div>
		{:else if response}
			<DataTable
				data={tableData}
				columns={columns as any}
				{pageSize}
				totalItems={response.total}
				{currentPage}
				onPageChange={(page) => { currentPage = page; }}
				onPageSizeChange={(size) => { pageSize = size; currentPage = 1; }}
			/>
		{/if}
	</div>
</div>
