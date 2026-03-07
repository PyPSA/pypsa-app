import { renderComponent } from '$lib/components/ui/data-table/render-helpers.js';
import { formatDate, formatDuration } from '$lib/utils.js';
import StatusCell from '../cells/status-cell.svelte';
import TextWithTitleCell from '../cells/text-with-title-cell.svelte';
import ActionsCell from '$lib/components/cells/ActionsCell.svelte';
import { X, Trash2, RotateCw } from 'lucide-svelte';
import OwnerCell from '$lib/components/OwnerCell.svelte';
import type { ColumnDef } from '@tanstack/table-core';
import { RUN_SETTLED_STATUSES } from '$lib/types.js';
import type { Run } from '$lib/types.js';

interface RunsColumnsHelpers {
	formatRelativeTime: (dateString: string | null | undefined) => string;
	handleCancel: (id: string) => void;
	handleRemove: (id: string) => void;
	handleRerun: (run: Run) => void;
	authEnabled: boolean;
	getCancellingId?: () => string | null;
	getRemovingId?: () => string | null;
	getTick?: () => number;
}

export const createColumns = (helpers: RunsColumnsHelpers): ColumnDef<Run, unknown>[] => {
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
				let source = run.workflow || '';

				// Strip URL prefixes
				if (source.startsWith('https://github.com/')) {
					source = source.replace('https://github.com/', '');
				} else if (source.startsWith('https://')) {
					source = source.replace('https://', '');
				} else if (source.startsWith('http://')) {
					source = source.replace('http://', '');
				}
				// Strip trailing .git
				source = source.replace(/\.git$/, '');

				// Append git ref/sha
				const ref = run.git_ref;
				const sha = run.git_sha ? run.git_sha.slice(0, 8) : null;
				if (ref && sha) {
					source += ` ${ref}@${sha}`;
				} else if (sha) {
					source += ` @${sha}`;
				} else if (ref) {
					source += ` ${ref}`;
				}

				return source;
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
				// Reference tick to force re-render for running jobs
				if (!run.completed_at) getTick();
				const text = formatDuration(run.started_at, run.completed_at) ?? '\u2014';
				const title = run.completed_at ? formatDate(run.completed_at) : '';
				return renderComponent(TextWithTitleCell, { text, title });
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
				return renderComponent(TextWithTitleCell, {
					text: formatRelativeTime(val),
					title: formatDate(val)
				});
			}
		},
		// Only shown when auth is enabled
		...(authEnabled
			? [
					{
						accessorKey: 'owner',
						header: 'Owner',
						enableSorting: false,
						cell: (info: { row: { original: Run } }) => {
							const run = info.row.original;
							return renderComponent(OwnerCell, { item: run });
						}
					}
				] as ColumnDef<Run, unknown>[]
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
	] as ColumnDef<Run, unknown>[];
};
