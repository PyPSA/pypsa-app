// Adapters between the legacy per-category FilterState and the AST.
// Only handles the flat and-of-in shape — non-flat ASTs (or, not, nesting)
// produced by Query mode collapse to an empty FilterState here.

import type { FilterState } from '$lib/components/widgets/filter-dialog';
import type { FilterAst, FilterAnd, FilterIn } from '$lib/filters/ast';

export function astFromFilterState(state: FilterState): FilterAnd {
	const children: FilterIn[] = [];
	for (const [field, values] of Object.entries(state)) {
		if (!values || values.size === 0) continue;
		children.push({ type: 'in', field, values: [...values] });
	}
	return { type: 'and', children };
}

export function filterStateFromAst(ast: FilterAst, categoryKeys: string[]): FilterState {
	const result: FilterState = {};
	for (const k of categoryKeys) result[k] = new Set<string>();
	if (ast.type !== 'and') return result;
	for (const c of ast.children) {
		if (c.type !== 'in') continue;
		const set = result[c.field] ?? new Set<string>();
		for (const v of c.values) set.add(v);
		result[c.field] = set;
	}
	return result;
}
