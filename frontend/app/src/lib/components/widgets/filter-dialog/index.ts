export { default as TokenSearchInput } from './token-search-input.svelte';
export type { FilterAst } from '$lib/filters/ast';

export interface FilterOption {
	id: string;
	label: string;
	avatarUrl?: string;
}

export interface FilterCategory {
	key: string;
	label: string;
	description?: string;
	options: FilterOption[];
	condition?: boolean | null;
	hideChipPrefix?: boolean;
}

export type FilterState = Record<string, Set<string>>;
