import { version } from '$lib/api/client.js';

export const features = $state({ runsEnabled: false, localMode: false, demoMode: false });

export async function initFeatures(): Promise<void> {
	const response = await version.get();
	features.runsEnabled = Boolean(response.runs_enabled);
	features.localMode = Boolean(response.local_mode);
	features.demoMode = Boolean(response.demo_mode);
}
