import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import { formatDate, formatDuration, byDate } from '$lib/utils.js';
import DateTime from '$lib/components/DateTime.svelte';
import StatusCell from '../cells/status-cell.svelte';
import TextWithTitleCell from '../cells/text-with-title-cell.svelte';
import WorkflowCell from '../cells/workflow-cell.svelte';
import JobsCell from '../cells/jobs-cell.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import VisibilityCell from '$lib/components/cells/VisibilityCell.svelte';
import X from '@lucide/svelte/icons/x';
import Trash2 from '@lucide/svelte/icons/trash-2';
import RotateCw from '@lucide/svelte/icons/rotate-cw';
import LockKeyhole from '@lucide/svelte/icons/lock-keyhole';
import Globe from '@lucide/svelte/icons/globe';
import OwnerCell from '$lib/components/cells/OwnerCell.svelte';
import type { ColumnDef } from '@tanstack/table-core';
import { RUN_SETTLED_STATUSES } from '$lib/types.js';
import type { RunSummary, Visibility } from '$lib/types.js';

interface RunsColumnsHelpers {
	handleCancel: (id: string) => void;
	handleRemove: (id: string) => void;
	handleRerun: (run: RunSummary) => void;
	handleVisibilityToggle: (id: string, visibility: Visibility) => void;
	canEditRun: (run: RunSummary) => boolean;
	authEnabled: boolean;
	getCancellingId?: () => string | null;
	getRemovingId?: () => string | null;
	getUpdatingVisibilityId?: () => string | null;
	getTick?: () => number;
}

export const createColumns = (helpers: RunsColumnsHelpers): ColumnDef<RunSummary, unknown>[] => {
	const {
		handleCancel,
		handleRemove,
		handleRerun,
		handleVisibilityToggle,
		canEditRun,
		authEnabled,
		getCancellingId = () => null,
		getRemovingId = () => null,
		getUpdatingVisibilityId = () => null,
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
			sortingFn: byDate<RunSummary>((r) => r.created_at),
			cell: (info) => {
				const val = info.getValue() as string;
				// Read tick to force re-render every second while run is active
				if (!info.row.original.completed_at) getTick();
				return renderComponent(DateTime, { value: val });
			}
		},
		{
			id: 'backend',
			header: 'Backend',
			enableSorting: false,
			cell: (info) => {
				const run = info.row.original;
				return run.backend?.name || '\u2014';
			}
		},
		// Only shown when auth is enabled
		...(authEnabled
			? [
					{
						accessorKey: 'visibility',
						header: 'Visibility',
						enableSorting: true,
						cell: (info: { row: { original: RunSummary } }) => {
							const run = info.row.original;
							return renderComponent(VisibilityCell, {
								item: run,
								canEdit: canEditRun(run),
								onToggle: handleVisibilityToggle
							});
						}
					},
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
				const isUpdatingVisibility = getUpdatingVisibilityId() === run.id;
				const isPublic = run.visibility === 'public';
				const canEdit = canEditRun(run);
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
				if (authEnabled && canEdit) {
					actions.push({
						icon: isPublic ? LockKeyhole : Globe,
						label: isPublic ? 'Make private' : 'Make public',
						onclick: () => handleVisibilityToggle(run.id, isPublic ? 'private' : 'public'),
						loading: isUpdatingVisibility,
						loadingLabel: 'Updating...'
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
