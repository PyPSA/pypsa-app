import type { ColumnDef } from '@tanstack/table-core';

type RowData = Record<string, unknown>;

const NUMERIC_DTYPES = new Set(['int64', 'float64', 'int32', 'float32', 'int', 'float']);

export function buildColumns(
	responseColumns: string[],
	dtypes: Record<string, string>
): ColumnDef<RowData, unknown>[] {
	const indexCol: ColumnDef<RowData, unknown> = {
		accessorKey: '__index__',
		header: 'Name',
		enableSorting: true,
	};

	const dataCols: ColumnDef<RowData, unknown>[] = responseColumns.map((col) => {
		const isNumeric = NUMERIC_DTYPES.has(dtypes[col] ?? '');
		return {
			accessorKey: col,
			header: col,
			enableSorting: true,
			meta: { align: isNumeric ? 'right' : 'left' },
		};
	});

	return [indexCol, ...dataCols];
}
