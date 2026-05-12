import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import DateTime from '$lib/components/DateTime.svelte';
import BadgeCell from '$lib/components/cells/BadgeCell.svelte';
import type { ColumnDef } from '@tanstack/table-core';
import { byDate } from '$lib/utils.js';
import type { ApiKey } from '$lib/types.js';

interface ApiKeyColumnsHelpers {
	isExpired: (key: ApiKey) => boolean;
}

export const createColumns = (helpers: ApiKeyColumnsHelpers): ColumnDef<ApiKey, unknown>[] => {
	const { isExpired } = helpers;

	return [
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
};
