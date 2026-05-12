/**
 * Helpers for parsing/building `country in ['XX', ...]` pandas-query fragments
 * used by plot and explore card parameters. Shared by PlotEditorDialog and
 * ExploreEditorDialog to keep the wire format in one place.
 */

const COUNTRY_RE = /country in \[(.+)]/;

export function parseCountriesFromQuery(
	query: string | undefined,
	availableCountries: string[] | undefined,
): Set<string> {
	if (!query) return new Set((availableCountries ?? []).filter(Boolean));
	const match = query.match(COUNTRY_RE);
	if (match) {
		return new Set(
			match[1]
				.split(',')
				.map((c) => c.trim().replace(/'/g, ''))
				.filter(Boolean),
		);
	}
	return new Set(availableCountries ?? []);
}

/**
 * Build a `country in ['XX', ...]` fragment, or undefined when the selection
 * is empty or covers every country (no filter needed).
 */
export function buildCountryQuery(
	selected: Iterable<string>,
	availableCountries: string[] | undefined,
): string | undefined {
	const validSelected = Array.from(selected).filter(Boolean);
	const validAvailable = (availableCountries ?? []).filter(Boolean);
	if (validSelected.length > 0 && validSelected.length < validAvailable.length) {
		const formatted = validSelected.map((c) => `'${c}'`).join(', ');
		return `country in [${formatted}]`;
	}
	return undefined;
}
