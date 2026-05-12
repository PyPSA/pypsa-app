import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import DateTime from '$lib/components/DateTime.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import Trash2 from '@lucide/svelte/icons/trash-2';
import type { ColumnDef } from '@tanstack/table-core';
import { byDate } from '$lib/utils.js';
import type { ApiKey } from '$lib/types.js';

interface ApiKeyColumnsHelpers {
	onDelete: (key: ApiKey) => void;
}

export const createColumns = (helpers: ApiKeyColumnsHelpers): ColumnDef<ApiKey, unknown>[] => {
	const { onDelete } = helpers;

	return [
		{
			accessorKey: 'name',
			header: 'Name',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				return info.getValue() as string;
			}
		},
		{
			accessorKey: 'key_prefix',
			header: 'Prefix',
			enableSorting: false,
			cell: (info) => {
				return `${info.getValue() as string}...`;
			}
		},
		{
			id: 'owner',
			header: 'Bot User',
			enableSorting: true,
			cell: (info) => {
				return info.row.original.owner.username;
			}
		},
		{
			accessorKey: 'created_at',
			header: 'Created',
			enableSorting: true,
			sortingFn: byDate<ApiKey>((r) => r.created_at),
			cell: (info) => {
				return renderComponent(DateTime, { value: info.getValue() as string });
			}
		},
		{
			accessorKey: 'last_used_at',
			header: 'Last Used',
			enableSorting: true,
			sortingFn: byDate<ApiKey>((r) => r.last_used_at),
			cell: (info) => {
				return renderComponent(DateTime, { value: info.getValue() as string });
			}
		},
		{
			accessorKey: 'expires_at',
			header: 'Expires',
			enableSorting: true,
			sortingFn: byDate<ApiKey>((r) => r.expires_at),
			cell: (info) => {
				return renderComponent(DateTime, { value: info.getValue() as string });
			}
		},
		{
			id: 'actions',
			header: '',
			enableSorting: false,
			cell: (info) => {
				const key = info.row.original;
				return renderComponent(ActionsCell, {
					actions: [
						{
							icon: Trash2,
							label: 'Delete',
							onclick: () => onDelete(key),
							variant: 'destructive' as const
						}
					]
				});
			}
		}
	];
};
