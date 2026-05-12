// Filter AST — single source of truth for table filters.
// Round-trips with the GitHub-style DSL (added in a later phase) and is
// evaluated server-side via a backend mirror of these types.

// Source byte range in the DSL string a node was parsed from. Optional because
// ASTs built programmatically (URL re-hydration) have no source — only the
// parser sets it. Used for chip rendering and error highlighting.
export interface SourceSpan {
	start: number;
	end: number;
}

export interface FilterIn {
	type: 'in';
	field: string;
	values: string[];
	span?: SourceSpan;
}

export interface FilterText {
	type: 'text';
	value: string;
	span?: SourceSpan;
}

export interface FilterAnd {
	type: 'and';
	children: FilterAst[];
	span?: SourceSpan;
}

export interface FilterOr {
	type: 'or';
	children: FilterAst[];
	span?: SourceSpan;
}

export interface FilterNot {
	type: 'not';
	child: FilterAst;
	span?: SourceSpan;
}

export type FilterAst = FilterIn | FilterText | FilterAnd | FilterOr | FilterNot;

export function emptyAnd(): FilterAnd {
	return { type: 'and', children: [] };
}

export function isEmpty(ast: FilterAst): boolean {
	if (ast.type === 'and' || ast.type === 'or') return ast.children.length === 0;
	if (ast.type === 'in') return ast.values.length === 0;
	if (ast.type === 'text') return ast.value.length === 0;
	return false;
}

// True iff the AST is representable as the per-category UI's flat shape: a
// single `in` leaf or `and(in, in, ...)`. The parser collapses singleton ANDs
// to a bare `in` so we accept both forms. Free-text leaves never qualify.
export function isFlatAndOfIn(ast: FilterAst): boolean {
	if (ast.type === 'in') return true;
	if (ast.type === 'and') return ast.children.every(c => c.type === 'in');
	return false;
}

// Flatten the top of the AST into its conjuncts so callers can work on each
// piece independently. `and(a, b, c)` → `[a, b, c]`; a bare leaf → `[leaf]`;
// OR/NOT stay opaque (returned as a single child).
export function topLevelConjuncts(ast: FilterAst): FilterAst[] {
	if (ast.type === 'and') return [...ast.children];
	return [ast];
}

// Combine top-level conjuncts back into a single AST, collapsing singletons.
export function fromConjuncts(children: FilterAst[]): FilterAst {
	if (children.length === 0) return { type: 'and', children: [] };
	if (children.length === 1) return children[0];
	return { type: 'and', children };
}

export function walk(ast: FilterAst, fn: (node: FilterAst) => void): void {
	fn(ast);
	if (ast.type === 'and' || ast.type === 'or') {
		for (const c of ast.children) walk(c, fn);
	} else if (ast.type === 'not') {
		walk(ast.child, fn);
	}
}

export function equals(a: FilterAst, b: FilterAst): boolean {
	if (a.type !== b.type) return false;
	if (a.type === 'in' && b.type === 'in') {
		if (a.field !== b.field) return false;
		if (a.values.length !== b.values.length) return false;
		for (let i = 0; i < a.values.length; i++) {
			if (a.values[i] !== b.values[i]) return false;
		}
		return true;
	}
	if (a.type === 'text' && b.type === 'text') return a.value === b.value;
	if ((a.type === 'and' && b.type === 'and') || (a.type === 'or' && b.type === 'or')) {
		if (a.children.length !== b.children.length) return false;
		for (let i = 0; i < a.children.length; i++) {
			if (!equals(a.children[i], b.children[i])) return false;
		}
		return true;
	}
	if (a.type === 'not' && b.type === 'not') return equals(a.child, b.child);
	return false;
}
