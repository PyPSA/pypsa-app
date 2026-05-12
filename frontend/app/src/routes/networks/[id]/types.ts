import type { Network } from '$lib/types.js';

export interface NetworkWithFacets extends Omit<Network, 'components_count'> {
	components_count?: Record<string, number>;
	facets?: {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	};
}
