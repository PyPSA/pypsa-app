import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import TopologyCell from '../cells/topology-cell.svelte';
import FileCell from '../cells/file-cell.svelte';
import DimensionsCell from '../cells/dimensions-cell.svelte';
import ComponentsCell from '../cells/components-cell.svelte';
import TagsCell from '../cells/tags-cell.svelte';
import UpdateHistoryCell from '../cells/update-history-cell.svelte';
import ActionsCell from '../cells/actions-cell.svelte';
import VisibilityCell from '../cells/visibility-cell.svelte';
import OwnerCell from '../cells/owner-cell.svelte';

export const createColumns = (helpers) => {
	const {
		getDirectoryPath,
		getTagType,
		getTagColor,
		formatFileSize,
		formatDate,
		handleDelete,
		toggleComponentsExpanded,
		getExpandedComponents,
		handleVisibilityToggle,
		canEditVisibility,
		authEnabled,
		getDeletingId = () => null,
		getUpdatingVisibilityId = () => null
	} = helpers;

	return [
		{
			accessorKey: 'topology_svg',
			header: 'Topology',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				return renderComponent(TopologyCell, { network });
			}
		},
		{
			accessorKey: 'filename',
			header: 'File',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				const network = info.row.original;
				const dirPath = getDirectoryPath(network.file_path);
				return renderComponent(FileCell, { network, dirPath });
			},
			filterFn: (row, columnId, filterValue) => {
				const network = row.original;
				const searchStr = filterValue.toLowerCase();
				return (
					network.filename?.toLowerCase().includes(searchStr) ||
					network.name?.toLowerCase().includes(searchStr) ||
					network.file_path?.toLowerCase().includes(searchStr)
				);
			}
		},
		{
			accessorKey: 'dimensions_count',
			header: 'Dimensions',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				return renderComponent(DimensionsCell, { network });
			}
		},
		{
			accessorKey: 'components_count',
			header: 'Components',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				const isExpanded = getExpandedComponents().has(network.id);
				return renderComponent(ComponentsCell, {
					network,
					isExpanded,
					toggleComponentsExpanded
				});
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
			filterFn: (row, columnId, filterValue) => {
				const network = row.original;
				const searchStr = filterValue.toLowerCase();
				if (!network.tags || !Array.isArray(network.tags)) return false;
				return network.tags.some((tag) => {
					if (typeof tag === 'string') {
						return tag.toLowerCase().includes(searchStr);
					} else if (typeof tag === 'object' && tag.name) {
						return tag.name.toLowerCase().includes(searchStr);
					}
					return false;
				});
			}
		},
		// Auth-only columns
		...(authEnabled
			? [
					{
						accessorKey: 'visibility',
						header: 'Visibility',
						enableSorting: true,
						cell: (info) => {
							const network = info.row.original;
							return renderComponent(VisibilityCell, {
								network,
								canEdit: canEditVisibility(network),
								onToggle: handleVisibilityToggle
							});
						}
					},
					{
						accessorKey: 'owner',
						header: 'Owner',
						enableSorting: false,
						cell: (info) => {
							const network = info.row.original;
							return renderComponent(OwnerCell, { network });
						}
					}
				]
			: []),
		{
			accessorKey: 'file_size',
			header: 'Size',
			enableSorting: true,
			sortingFn: 'basic',
			cell: (info) => {
				return formatFileSize(info.getValue());
			}
		},
		{
			accessorKey: 'update_history',
			header: 'Last Updated',
			enableSorting: true,
			sortingFn: (rowA, rowB) => {
				const historyA = rowA.original.update_history;
				const historyB = rowB.original.update_history;

				// Get the most recent update for each row
				const latestA = historyA && historyA.length > 0
					? new Date(historyA[historyA.length - 1]).getTime()
					: 0;
				const latestB = historyB && historyB.length > 0
					? new Date(historyB[historyB.length - 1]).getTime()
					: 0;

				return latestA - latestB;
			},
			cell: (info) => {
				const network = info.row.original;
				return renderComponent(UpdateHistoryCell, { network, formatDate });
			}
		},
		{
			id: 'actions',
			header: 'Actions',
			enableSorting: false,
			cell: (info) => {
				const network = info.row.original;
				const canEdit = canEditVisibility(network);
				const isDeleting = getDeletingId() === network.id;
				const isUpdatingVisibility = getUpdatingVisibilityId() === network.id;
				return renderComponent(ActionsCell, {
					network,
					handleDelete,
					handleVisibilityToggle,
					canEdit,
					isDeleting,
					isUpdatingVisibility
				});
			}
		}
	];
};
