export { default as FilterDialog } from './filter-dialog.svelte';

export interface FilterOption {
	id: string;
	label: string;
	avatarUrl?: string;
}

export interface FilterCategory {
	key: string;
	label: string;
	options: FilterOption[];
	condition?: boolean | null;
}

export type FilterState = Record<string, Set<string>>;
