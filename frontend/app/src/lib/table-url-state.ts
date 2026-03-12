import type { VisibilityState } from '@tanstack/table-core';
import { loadTablePrefs } from './utils.js';

const VALID_PAGE_SIZES = [10, 25, 50, 100];

type FilterKeys = readonly string[];

/**
 * Read pagination + filters from URL search params + localStorage.
 */
export function restoreTableState(
	searchParams: URLSearchParams,
	prefix: string,
	filterKeys: FilterKeys
): {
	page: number;
	pageSize: number;
	columnVisibility: VisibilityState | null;
	filters: Record<string, Set<string>>;
} {
	const prefs = loadTablePrefs(prefix);

	let page = 1;
	let pageSize = (prefs.pageSize && VALID_PAGE_SIZES.includes(prefs.pageSize)) ? prefs.pageSize : 25;

	const urlPage = searchParams.get('page');
	if (urlPage) {
		const parsed = parseInt(urlPage);
		if (!isNaN(parsed) && parsed > 0) page = parsed;
	}

	const urlSize = searchParams.get('size');
	if (urlSize) {
		const parsed = parseInt(urlSize);
		if (!isNaN(parsed) && VALID_PAGE_SIZES.includes(parsed)) pageSize = parsed;
	}

	const filters: Record<string, Set<string>> = {};
	for (const key of filterKeys) {
		const values = searchParams.getAll(key);
		filters[key] = values.length > 0 ? new Set(values) : new Set();
	}

	return { page, pageSize, columnVisibility: prefs.columnVisibility, filters };
}

/**
 * Build a URL with current pagination + filters.
 */
export function buildTableURL(
	currentURL: URL,
	page: number,
	pageSize: number,
	filters: Record<string, Set<string>>,
	filterKeys: FilterKeys
): URL {
	const url = new URL(currentURL.href);
	url.searchParams.set('page', page.toString());
	url.searchParams.set('size', pageSize.toString());
	for (const key of filterKeys) {
		url.searchParams.delete(key);
		const values = filters[key];
		if (values) {
			for (const v of values) {
				url.searchParams.append(key, v);
			}
		}
	}
	return url;
}

/**
 * Convert Set-based filters to plain arrays for API calls.
 * Only includes keys with non-empty sets.
 */
export function filtersToAPI<T extends Record<string, string[]>>(
	filters: Record<string, Set<string>>,
	filterKeys: FilterKeys
): Partial<T> {
	const result: Record<string, string[]> = {};
	for (const key of filterKeys) {
		const values = filters[key];
		if (values && values.size > 0) {
			result[key] = Array.from(values);
		}
	}
	return result as Partial<T>;
}

/**
 * Correct page if it exceeds total pages; returns null if no change needed.
 */
export function clampPage(page: number, pageSize: number, total: number): number | null {
	const totalPages = Math.ceil(total / pageSize);
	if (page > totalPages && totalPages > 0) {
		return totalPages;
	}
	return null;
}
