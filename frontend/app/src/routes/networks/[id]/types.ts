import type { Network } from '$lib/types.js';

export interface NetworkWithFacets extends Network {
	facets?: {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	};
}
