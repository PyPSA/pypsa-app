<script>
	import { page } from '$app/stores';
	import { Users, Network } from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import * as Sidebar from '$lib/components/ui/sidebar';

	const navItems = [
		{
			title: 'User Management',
			url: '/admin/users',
			icon: Users
		},
		{
			title: 'Network Management',
			url: '/admin/networks',
			icon: Network
		}
	];

	const currentPath = $derived($page.url.pathname);
</script>

{#if authStore.isAdmin}
	<Sidebar.Group>
		<Sidebar.GroupLabel>Administration</Sidebar.GroupLabel>
		<Sidebar.GroupContent>
			<Sidebar.Menu>
				{#each navItems as item}
					<Sidebar.MenuItem>
						<Sidebar.MenuButton tooltipContent={item.title} isActive={currentPath === item.url}>
							{#snippet child({ props })}
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
{/if}
