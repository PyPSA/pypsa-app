<script lang="ts">
	import { onMount } from 'svelte';
	import { version } from '$lib/api/client.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import NavMain from './sidebar/NavMain.svelte';
	import NavAdmin from './sidebar/NavAdmin.svelte';
	import NavUser from './sidebar/NavUser.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import Badge from '$lib/components/ui/badge/badge.svelte';

	// Version info
	interface VersionData {
		app: string;
		pypsa: string;
	}
	const VERSION_CACHE_KEY = 'pypsa-version-v3';
	let versionData = $state<VersionData | null>(null);

	// Format version for display (remove .post1. and git hash)
	function formatVersion(version: string | undefined) {
		if (!version) return version;
		return version.replace(/\.post\d+\./, '.').split('+')[0];
	}

	onMount(async () => {
		// Try to load from localStorage first for instant display
		try {
			const cached = localStorage.getItem(VERSION_CACHE_KEY);
			if (cached) {
				versionData = JSON.parse(cached);
			}
		} catch (e) {
			// Ignore cache errors
		}

		// Fetch fresh version
		try {
			const data = await version.get();
			versionData = {
				app: data.version as string,
				pypsa: data.pypsa_version as string
			};

			// Cache for future use
			localStorage.setItem(VERSION_CACHE_KEY, JSON.stringify(versionData));
		} catch (err) {
			console.error('Failed to fetch version:', err);
		}
	});
</script>

<Sidebar.Root collapsible="icon">
	<Sidebar.Header>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton size="lg">
					{#snippet child({ props }: { props: Record<string, unknown> })}
						<a href="/networks" class="flex items-center gap-2" {...props}>
							<img src="/pypsa-logo.svg" alt="PyPSA Logo" class="h-8 w-8 shrink-0 object-contain" />
							<div class="flex flex-1 items-center gap-2 text-left text-sm leading-tight">
								<span class="truncate font-semibold">PyPSA App</span>
								{#if versionData?.app}
									<Tooltip.Root>
										<Tooltip.Trigger>
											<Badge variant="default">
												v{formatVersion(versionData.app)}
											</Badge>
										</Tooltip.Trigger>
										<Tooltip.Content side="bottom">
											<div class="grid grid-cols-[auto_auto] gap-x-3 gap-y-1 text-xs">
												<span class="text-muted-foreground">PyPSA App</span>
												<span class="font-mono">{versionData.app}</span>
												<span class="text-muted-foreground">PyPSA</span>
												<span class="font-mono">{versionData.pypsa}</span>
											</div>
										</Tooltip.Content>
									</Tooltip.Root>
								{/if}
							</div>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>

	<Sidebar.Content class="flex flex-col overflow-hidden">
		<NavMain />
		<NavAdmin />
	</Sidebar.Content>

	{#if !authStore.loading && authStore.isAuthenticated}
		<Sidebar.Footer>
			<NavUser />
		</Sidebar.Footer>
	{/if}

	<Sidebar.Rail />
</Sidebar.Root>
