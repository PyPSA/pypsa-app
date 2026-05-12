import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import FileCell from '../cells/file-cell.svelte';
import DimensionsCell from '../cells/dimensions-cell.svelte';
import TagsCell from '../cells/tags-cell.svelte';
import DateTime from '$lib/components/DateTime.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import VisibilityCell from '$lib/components/cells/VisibilityCell.svelte';
import Lock from '@lucide/svelte/icons/lock';
import Globe from '@lucide/svelte/icons/globe';
import Trash2 from '@lucide/svelte/icons/trash-2';
import UserRoundCog from '@lucide/svelte/icons/user-round-cog';
import OwnerCell from '$lib/components/OwnerCell.svelte';
import type { ColumnDef } from '@tanstack/table-core';
import { byDate } from '$lib/utils.js';
import type { Network, NetworkTag, TagType, TagColor, Visibility } from '$lib/types.js';

interface DatabaseColumnsHelpers {
	getTagType: (tag: string | NetworkTag) => TagType;
	getTagColor: (type: TagType) => TagColor;
	formatFileSize: (bytes: number | null | undefined) => string;
	handleDelete: (id: string) => void;
	handleVisibilityToggle: (id: string, visibility: Visibility) => void;
	canEditNetwork: (network: Network) => boolean;
	authEnabled: boolean;
	handleOwnerChange?: (network: Network) => void;
	getDeletingId?: () => string | null;
	getUpdatingVisibilityId?: () => string | null;
}

export const createColumns = (helpers: DatabaseColumnsHelpers): ColumnDef<Network, unknown>[] => {
	const {
		getTagType,
		getTagColor,
		formatFileSize,
		handleDelete,
		handleVisibilityToggle,
		canEditNetwork,
		authEnabled,
		handleOwnerChange,
		getDeletingId = () => null,
		getUpdatingVisibilityId = () => null
	} = helpers;

	return [
		{
			accessorKey: 'filename',
			header: 'File',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				const network = info.row.original;
				return renderComponent(FileCell, { network });
			},
		},
		{
			accessorKey: 'dimensions',
			header: 'Dimensions',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				return renderComponent(DimensionsCell, { network });
			}
		},
		{
			accessorKey: 'tags',
			header: 'Tags',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				return renderComponent(TagsCell, {
					network,
					getTagType,
					getTagColor
				});
			},
		},
		// Auth-only columns
		...(authEnabled
			? [
					{
						accessorKey: 'visibility',
						header: 'Visibility',
						enableSorting: true,
						cell: (info: { row: { original: Network } }) => {
							const network = info.row.original;
							return renderComponent(VisibilityCell, {
								item: network,
								canEdit: canEditNetwork(network),
								onToggle: handleVisibilityToggle
							});
						}
					},
					{
						accessorKey: 'owner',
						header: 'Owner',
						enableSorting: false,
						cell: (info: { row: { original: Network } }) => {
							const network = info.row.original;
							return renderComponent(OwnerCell, { item: network });
						}
					}
				] as ColumnDef<Network, unknown>[]
			: []),
		{
			accessorKey: 'file_size',
			header: 'Size',
			enableSorting: true,
			sortingFn: 'basic',
			cell: (info) => {
				return formatFileSize(info.getValue() as number);
			}
		},
		{
			accessorKey: 'created_at',
			header: 'Created',
			enableSorting: true,
			sortingFn: byDate<Network>((r) => r.created_at),
			cell: (info) => {
				const val = info.getValue() as string | undefined;
				return renderComponent(DateTime, { value: val });
			}
		},
		{
			id: 'actions',
			header: 'Actions',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				const canEdit = canEditNetwork(network);
				const isPublic = network.visibility === 'public';
				const isDeleting = getDeletingId() === network.id;
				const isUpdatingVisibility = getUpdatingVisibilityId() === network.id;
				const actions = [];
				if (canEdit) {
					if (handleOwnerChange) {
						actions.push({
							icon: UserRoundCog,
							label: 'Change owner',
							onclick: () => handleOwnerChange(network)
						});
					}
					actions.push({
						icon: isPublic ? Lock : Globe,
						label: isPublic ? 'Make private' : 'Make public',
						onclick: () => handleVisibilityToggle(network.id, isPublic ? 'private' : 'public'),
						loading: isUpdatingVisibility,
						loadingLabel: 'Updating...'
					});
					actions.push({
						icon: Trash2,
						label: 'Delete',
						onclick: () => handleDelete(network.id),
						loading: isDeleting,
						loadingLabel: 'Deleting...',
						variant: 'destructive' as const
					});
				}
				return renderComponent(ActionsCell, { actions });
			}
		}
	] as ColumnDef<Network, unknown>[];
};
