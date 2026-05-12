export type SuggestMode =
	| { kind: 'none' }
	| { kind: 'key'; prefix: string; tokenStart: number; tokenEnd: number }
	| {
			kind: 'value';
			key: string;
			partial: string;
			tokenStart: number;
			valueStart: number;
			tokenEnd: number;
		};

const IDENT = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

export function suggestMode(draft: string, cursor: number): SuggestMode {
	const before = draft.slice(0, cursor);
	let tokenStart = before.length;
	while (tokenStart > 0 && !/\s/.test(before[tokenStart - 1])) tokenStart--;
	const fragment = before.slice(tokenStart);

	let fullTokenEnd = cursor;
	while (fullTokenEnd < draft.length && !/\s/.test(draft[fullTokenEnd])) fullTokenEnd++;
	if (fragment.length === 0) {
		const prevEnd = tokenStart;
		let prevStart = prevEnd;
		while (prevStart > 0 && !/\s/.test(before[prevStart - 1])) prevStart--;
		const prevToken = before.slice(prevStart, prevEnd);
		const prevColon = prevToken.indexOf(':');
		if (prevColon !== -1) {
			const prevKey = prevToken.slice(0, prevColon);
			if (IDENT.test(prevKey) && prevToken.indexOf(':', prevColon + 1) === -1) {
				const valueStart = prevStart + prevColon + 1;
				return {
					kind: 'value',
					key: prevKey.toLowerCase(),
					partial: '',
					tokenStart: prevStart,
					valueStart,
					tokenEnd: fullTokenEnd
				};
			}
		}
		return { kind: 'none' };
	}

	const colonIdx = fragment.indexOf(':');
	if (colonIdx === -1) {
		if (!IDENT.test(fragment)) return { kind: 'none' };
		return { kind: 'key', prefix: fragment, tokenStart, tokenEnd: fullTokenEnd };
	}
	const key = fragment.slice(0, colonIdx);
	if (!IDENT.test(key)) return { kind: 'none' };
	const valuesPart = fragment.slice(colonIdx + 1);
	const lastComma = valuesPart.lastIndexOf(',');
	const partial = lastComma === -1 ? valuesPart : valuesPart.slice(lastComma + 1);
	const valueStart = tokenStart + colonIdx + 1 + (lastComma === -1 ? 0 : lastComma + 1);
	return {
		kind: 'value',
		key: key.toLowerCase(),
		partial,
		tokenStart,
		valueStart,
		tokenEnd: fullTokenEnd
	};
}
