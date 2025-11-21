<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { version } from '$lib/api/client.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import NavMain from './sidebar/NavMain.svelte';
	import NavUser from './sidebar/NavUser.svelte';
	import NavNetworksList from './sidebar/NavNetworksList.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import Badge from '$lib/components/ui/badge/badge.svelte';

	// Check if we're on the network detail page
	const isNetworkPage = $derived($page.url.pathname === '/network');

	// Version info
	let versionData = $state(null);

	// Format version for display (remove .post1. and git hash)
	function formatVersion(version) {
		if (!version) return version;
		return version.replace(/\.post\d+\./, '.').split('+')[0];
	}

	onMount(async () => {
		// Try to load from localStorage first for instant display
		try {
			const cached = localStorage.getItem('pypsa-version');
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
				backend: data.backend_version,
				frontendApp: data.frontend_app_version,
				frontendMap: data.frontend_map_version,
				pypsa: data.pypsa_version
			};

			// Cache for future use
			localStorage.setItem('pypsa-version', JSON.stringify(versionData));
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
					{#snippet child({ props })}
						<a href="/database" class="flex items-center gap-2" {...props}>
							<img src="/pypsa-logo.svg" alt="PyPSA Logo" class="h-8 w-8 shrink-0 object-contain" />
							<div class="flex flex-1 items-center gap-2 text-left text-sm leading-tight">
								<span class="truncate font-semibold">PyPSA App</span>
								{#if versionData?.backend}
									<Tooltip.Root>
										<Tooltip.Trigger>
											<Badge variant="default">
												v{formatVersion(versionData.backend)}
											</Badge>
										</Tooltip.Trigger>
										<Tooltip.Content side="bottom" class="bg-popover text-popover-foreground">
											<div class="space-y-1 text-xs">
												<div><strong>Backend:</strong> {versionData.backend}</div>
												<div><strong>Frontend App:</strong> {versionData.frontendApp}</div>
												<div><strong>Frontend Map:</strong> {versionData.frontendMap}</div>
												<div><strong>PyPSA:</strong> {versionData.pypsa}</div>
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
		{#if isNetworkPage}
			<NavNetworksList />
		{/if}
	</Sidebar.Content>

	{#if !authStore.loading && authStore.isAuthenticated}
		<Sidebar.Footer>
			<NavUser />
		</Sidebar.Footer>
	{/if}

	<Sidebar.Rail />
</Sidebar.Root>
