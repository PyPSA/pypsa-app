import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import DateTime from '$lib/components/DateTime.svelte';
import BadgeCell from '$lib/components/cells/BadgeCell.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import Users from '@lucide/svelte/icons/users';
import type { ColumnDef } from '@tanstack/table-core';
import { byDate } from '$lib/utils.js';
import type { Backend } from '$lib/types.js';

interface BackendColumnsHelpers {
	onManageUsers: (backend: Backend) => void;
}

export const createColumns = (helpers: BackendColumnsHelpers): ColumnDef<Backend, unknown>[] => {
	const { onManageUsers } = helpers;

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
			accessorKey: 'url',
			header: 'URL',
			enableSorting: false,
			cell: (info) => {
				return info.getValue() as string;
			}
		},
		{
			id: 'status',
			header: 'Status',
			enableSorting: true,
			cell: (info) => {
				const backend = info.row.original;
				return renderComponent(BadgeCell, {
					label: backend.is_active ? 'active' : 'inactive',
					variant: backend.is_active ? 'default' : 'outline'
				});
			}
		},
		{
			accessorKey: 'created_at',
			header: 'Created',
			enableSorting: true,
			sortingFn: byDate<Backend>((r) => r.created_at),
			cell: (info) => {
				return renderComponent(DateTime, { value: info.getValue() as string });
			}
		},
		{
			id: 'actions',
			header: '',
			enableSorting: false,
			cell: (info) => {
				const backend = info.row.original;
				return renderComponent(ActionsCell, {
					actions: [
						{
							icon: Users,
							label: 'Manage Users',
							onclick: () => onManageUsers(backend)
						}
					]
				});
			}
		}
	];
};
