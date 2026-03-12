import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import { formatDate, formatDuration } from '$lib/utils.js';
import StatusCell from '../cells/status-cell.svelte';
import TextWithTitleCell from '../cells/text-with-title-cell.svelte';
import WorkflowCell from '../cells/workflow-cell.svelte';
import JobsCell from '../cells/jobs-cell.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import { X, Trash2, RotateCw } from 'lucide-svelte';
import OwnerCell from '$lib/components/OwnerCell.svelte';
import type { ColumnDef } from '@tanstack/table-core';
import { RUN_SETTLED_STATUSES } from '$lib/types.js';
import type { RunSummary } from '$lib/types.js';

interface RunsColumnsHelpers {
	formatRelativeTime: (dateString: string | null | undefined) => string;
	handleCancel: (id: string) => void;
	handleRemove: (id: string) => void;
	handleRerun: (run: RunSummary) => void;
	authEnabled: boolean;
	getCancellingId?: () => string | null;
	getRemovingId?: () => string | null;
	getTick?: () => number;
}

export const createColumns = (helpers: RunsColumnsHelpers): ColumnDef<RunSummary, unknown>[] => {
	const {
		formatRelativeTime,
		handleCancel,
		handleRemove,
		handleRerun,
		authEnabled,
		getCancellingId = () => null,
		getRemovingId = () => null,
		getTick = () => 0
	} = helpers;

	return [
		{
			accessorKey: 'status',
			header: 'Status',
			enableSorting: true,
			cell: (info) => {
				const run = info.row.original;
				return renderComponent(StatusCell, { run });
			}
		},
		{
			accessorKey: 'workflow',
			header: 'Workflow',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				const run = info.row.original;
				return renderComponent(WorkflowCell, { run });
			}
		},
		{
			accessorKey: 'configfile',
			header: 'Config',
			enableSorting: true,
			sortingFn: 'alphanumeric',
			cell: (info) => {
				return (info.getValue() as string) || '\u2014';
			}
		},
		{
			id: 'duration',
			header: 'Duration',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				// Read tick to force re-render every second while run is active
				if (!run.completed_at) getTick();
				const text = formatDuration(run.started_at, run.completed_at) ?? '\u2014';
				const title = run.completed_at ? formatDate(run.completed_at) : '';
				return renderComponent(TextWithTitleCell, { text, title });
			}
		},
		{
			id: 'jobs',
			header: 'Jobs',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				return renderComponent(JobsCell, { run });
			}
		},
		{
			accessorKey: 'created_at',
			header: 'Created',
			enableSorting: true,
			sortingFn: (rowA, rowB) => {
				const a = new Date(rowA.original.created_at).getTime();
				const b = new Date(rowB.original.created_at).getTime();
				return a - b;
			},
			cell: (info) => {
				const val = info.getValue() as string;
				// Read tick to force re-render every second while run is active
				if (!info.row.original.completed_at) getTick();
				return renderComponent(TextWithTitleCell, {
					text: formatRelativeTime(val),
					title: formatDate(val)
				});
			}
		},
		{
			id: 'backend',
			header: 'Backend',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				return run.backend.name || '\u2014';
			}
		},
		// Only shown when auth is enabled
		...(authEnabled
			? [
					{
						accessorKey: 'owner',
						header: 'Owner',
						enableSorting: false,
						cell: (info: { row: { original: RunSummary } }) => {
							const run = info.row.original;
							return renderComponent(OwnerCell, { item: run });
						}
					}
				] as ColumnDef<RunSummary, unknown>[]
			: []),
		{
			id: 'actions',
			header: '',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				const isSettled = RUN_SETTLED_STATUSES.has(run.status);
				const isCancelling = getCancellingId() === run.id;
				const isRemoving = getRemovingId() === run.id;
				const actions = [];
				if (!isSettled) {
					actions.push({
						icon: X,
						label: 'Cancel',
						onclick: () => handleCancel(run.id),
						loading: isCancelling
					});
				}
				if (isSettled) {
					actions.push({
						icon: RotateCw,
						label: 'Rerun',
						onclick: () => handleRerun(run)
					});
				}
				actions.push({
					icon: Trash2,
					label: 'Remove',
					onclick: () => handleRemove(run.id),
					loading: isRemoving,
					variant: 'destructive' as const
				});
				return renderComponent(ActionsCell, { actions });
			}
		}
	] as ColumnDef<RunSummary, unknown>[];
};
