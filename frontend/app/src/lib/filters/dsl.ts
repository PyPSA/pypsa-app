// GitHub-style filter DSL — parse + serialize.
// Grammar (informal):
//   expr     := or
//   or       := and ('OR' and)*
//   and      := term (('AND')? term)*       // implicit AND between adjacent terms
//   term     := '(' expr ')' | ('NOT' | '-') term | leaf
//   leaf     := IDENT ':' value (',' value)* | value     // bare value = free text
//   value    := unquoted | '"' quoted '"'
// AND/OR/NOT are uppercase keywords; '-' is shorthand for NOT on a single leaf.
// Bare tokens (no `field:`) become free-text leaves; multiple bare tokens
// implicitly AND together.

import type { FilterAst } from '$lib/filters/ast';
import { emptyAnd } from '$lib/filters/ast';

export interface ParseError {
	message: string;
	range: [number, number];
}

export interface ParseResult {
	ast: FilterAst;
	errors: ParseError[];
}

const IDENT_HEAD = /[a-zA-Z_]/;
const IDENT_TAIL = /[a-zA-Z0-9_]/;
const VALUE_CHAR = /[^\s,()"]/;

class Parser {
	pos = 0;
	errors: ParseError[] = [];

	constructor(public input: string) {}

	parse(): ParseResult {
		this.skipWs();
		if (this.eof()) return { ast: emptyAnd(), errors: this.errors };
		const ast = this.parseOr();
		this.skipWs();
		if (!this.eof()) {
			this.error('Invalid query', this.pos, this.input.length);
		}
		return { ast, errors: this.errors };
	}

	private parseOr(): FilterAst {
		const start = this.pos;
		let left = this.parseAnd();
		while (true) {
			this.skipWs();
			if (!this.consumeKeyword('OR')) break;
			const right = this.parseAnd();
			if (left.type === 'or') {
				left.children.push(right);
				left.span = { start, end: this.pos };
			} else {
				left = { type: 'or', children: [left, right], span: { start, end: this.pos } };
			}
		}
		return left;
	}

	private parseAnd(): FilterAst {
		const start = this.pos;
		const children: FilterAst[] = [this.parseTerm()];
		while (true) {
			this.skipWs();
			if (this.eof()) break;
			if (this.peekKeyword('OR')) break;
			if (this.peek() === ')') break;
			// Optional explicit AND keyword between terms.
			this.consumeKeyword('AND');
			this.skipWs();
			if (this.eof()) break;
			if (this.peek() === ')') break;
			children.push(this.parseTerm());
		}
		if (children.length === 1) return children[0];
		return { type: 'and', children, span: { start, end: this.pos } };
	}

	private parseTerm(): FilterAst {
		this.skipWs();
		if (this.peek() === '(') {
			const parenStart = this.pos;
			this.pos++;
			const inner = this.parseOr();
			this.skipWs();
			if (this.peek() === ')') this.pos++;
			else this.error("Expected ')'", this.pos, this.pos + 1);
			// Extend the inner node's span to swallow wrapping parens so chip
			// slicing removes them too — otherwise removing `(status:done)` would
			// leave dangling `()` in the draft.
			inner.span = { start: parenStart, end: this.pos };
			return inner;
		}
		if (this.peekKeyword('NOT')) {
			const notStart = this.pos;
			this.consumeKeyword('NOT');
			const child = this.parseTerm();
			return { type: 'not', child, span: { start: notStart, end: this.pos } };
		}
		if (this.peek() === '-') {
			const notStart = this.pos;
			this.pos++;
			const child = this.parseLeaf();
			return { type: 'not', child, span: { start: notStart, end: this.pos } };
		}
		return this.parseLeaf();
	}

	private parseLeaf(): FilterAst {
		// Peek ahead: an IDENT immediately followed by ':' = field leaf.
		// Otherwise we consume one value as a free-text leaf.
		if (this.looksLikeFieldLeaf()) {
			const spanStart = this.pos;
			const field = this.parseIdent().toLowerCase();
			this.pos++; // consume ':' (looksLikeFieldLeaf already verified it)
			const values = this.parseValueList();
			return { type: 'in', field, values, span: { start: spanStart, end: this.pos } };
		}
		// Reserved keywords appearing where a term is expected = syntax error.
		// (NOT is intercepted earlier in parseTerm; AND/OR landing here means
		// the user wrote a dangling operator.)
		for (const kw of ['AND', 'OR', 'NOT']) {
			if (this.peekKeyword(kw)) {
				this.error(`Unexpected keyword '${kw}'`, this.pos, this.pos + kw.length);
				const start = this.pos;
				this.pos += kw.length;
				return { type: 'text', value: '', span: { start, end: this.pos } };
			}
		}
		const start = this.pos;
		const value = this.parseValue();
		if (value === null) {
			this.error('Expected value', start, this.pos + 1);
			return { type: 'text', value: '', span: { start, end: this.pos } };
		}
		return { type: 'text', value, span: { start, end: this.pos } };
	}

	private looksLikeFieldLeaf(): boolean {
		// Can't be a field leaf if it starts with a quote — that's free text.
		if (this.peek() === '"') return false;
		const save = this.pos;
		const ident = this.parseIdent();
		const isField = ident.length > 0 && this.peek() === ':';
		this.pos = save;
		return isField;
	}

	private parseValueList(): string[] {
		const values: string[] = [];
		const first = this.parseValue();
		if (first === null) {
			this.error('Expected value', this.pos, this.pos + 1);
		} else {
			values.push(first);
		}
		while (this.peek() === ',') {
			this.pos++;
			const next = this.parseValue();
			if (next === null) {
				this.error('Expected value after comma', this.pos, this.pos + 1);
				break;
			}
			values.push(next);
		}
		return values;
	}

	private parseValue(): string | null {
		if (this.peek() === '"') return this.parseQuoted();
		const start = this.pos;
		while (!this.eof() && VALUE_CHAR.test(this.peek())) this.pos++;
		if (this.pos === start) return null;
		return this.input.slice(start, this.pos);
	}

	private parseQuoted(): string {
		const start = this.pos;
		this.pos++; // opening quote
		let out = '';
		while (!this.eof() && this.peek() !== '"') {
			if (this.peek() === '\\' && this.pos + 1 < this.input.length) {
				out += this.input[this.pos + 1];
				this.pos += 2;
			} else {
				out += this.input[this.pos];
				this.pos++;
			}
		}
		if (this.peek() === '"') this.pos++;
		else this.error('Unterminated quoted string', start, this.pos);
		return out;
	}

	private parseIdent(): string {
		const start = this.pos;
		if (this.eof() || !IDENT_HEAD.test(this.peek())) return '';
		while (!this.eof() && IDENT_TAIL.test(this.peek())) this.pos++;
		return this.input.slice(start, this.pos);
	}

	private consumeKeyword(kw: string): boolean {
		if (!this.peekKeyword(kw)) return false;
		this.pos += kw.length;
		return true;
	}

	private peekKeyword(kw: string): boolean {
		const slice = this.input.substr(this.pos, kw.length);
		if (slice.toUpperCase() !== kw) return false;
		const after = this.input[this.pos + kw.length];
		return !after || !IDENT_TAIL.test(after);
	}

	private skipWs(): void {
		while (!this.eof() && /\s/.test(this.peek())) this.pos++;
	}

	private peek(): string {
		return this.input[this.pos] ?? '';
	}

	private eof(): boolean {
		return this.pos >= this.input.length;
	}

	private error(message: string, start: number, end: number): void {
		this.errors.push({ message, range: [start, end] });
	}
}

export function parse(input: string): ParseResult {
	return new Parser(input).parse();
}

const PREC_OR = 1;
const PREC_AND = 2;
const PREC_NOT = 3;

const SAFE_VALUE = /^[a-zA-Z0-9_\-./@:][a-zA-Z0-9_\-./@:]*$/;

function quoteValue(v: string): string {
	if (v.length > 0 && SAFE_VALUE.test(v)) return v;
	return `"${v.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

// Bare-text leaves can't use the field-value safe charset because `:` would
// be reparsed as a field separator and a leading `-` as NOT.
function quoteText(v: string): string {
	if (v.length === 0) return '""';
	const needsQuote = /[\s:(),"]/.test(v) || v.startsWith('-');
	if (!needsQuote) return v;
	return `"${v.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

function serializeNode(ast: FilterAst, parentPrec: number): string {
	if (ast.type === 'in') {
		if (ast.values.length === 0) return `${ast.field}:`;
		return `${ast.field}:${ast.values.map(quoteValue).join(',')}`;
	}
	if (ast.type === 'text') return quoteText(ast.value);
	if (ast.type === 'not') {
		// `-leaf` shorthand for in/text leaves; otherwise `NOT (...)`.
		if (ast.child.type === 'in' || ast.child.type === 'text') {
			return `-${serializeNode(ast.child, PREC_NOT)}`;
		}
		return `NOT ${serializeNode(ast.child, PREC_NOT)}`;
	}
	if (ast.type === 'and') {
		if (ast.children.length === 0) return '';
		const body = ast.children.map(c => serializeNode(c, PREC_AND)).join(' ');
		return parentPrec > PREC_AND ? `(${body})` : body;
	}
	// or
	if (ast.children.length === 0) return '';
	const body = ast.children.map(c => serializeNode(c, PREC_OR)).join(' OR ');
	return parentPrec > PREC_OR ? `(${body})` : body;
}

export function serialize(ast: FilterAst): string {
	return serializeNode(ast, 0);
}
