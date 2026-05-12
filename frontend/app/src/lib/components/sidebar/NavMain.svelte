<script lang="ts">
	import { page } from '$app/stores';
	import Database from '@lucide/svelte/icons/database';
	import Play from '@lucide/svelte/icons/play';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import { features } from '$lib/stores/features.svelte.js';

	const allNavItems = [
		{
			title: 'Networks',
			url: '/networks',
			icon: Database
		},
		{
			title: 'Runs',
			url: '/runs',
			icon: Play
		}
	];

	const navItems = $derived(
		allNavItems.filter((item) => item.title !== 'Runs' || features.runsEnabled)
	);

	// Reactive variable to check current path
	const currentPath = $derived($page.url.pathname);
</script>

<Sidebar.Group>
	<Sidebar.GroupLabel>Navigation</Sidebar.GroupLabel>
	<Sidebar.GroupContent>
		<Sidebar.Menu>
			{#each navItems as item}
				<Sidebar.MenuItem>
					<Sidebar.MenuButton tooltipContent={item.title} isActive={currentPath === item.url || (item.url !== '/' && currentPath.startsWith(item.url + '/'))}>
						{#snippet child({ props }: { props: Record<string, unknown> })}
							<a href={item.url} {...props}>
								<item.icon />
								<span>{item.title}</span>
							</a>
						{/snippet}
					</Sidebar.MenuButton>
				</Sidebar.MenuItem>
			{/each}
		</Sidebar.Menu>
	</Sidebar.GroupContent>
</Sidebar.Group>
