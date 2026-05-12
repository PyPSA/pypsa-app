<script lang="ts">
	import { page } from '$app/stores';
	import { Collapsible } from 'bits-ui';
	import Shield from '@lucide/svelte/icons/shield';
	import Users from '@lucide/svelte/icons/users';
	import Server from '@lucide/svelte/icons/server';
	import Key from '@lucide/svelte/icons/key';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import * as Sidebar from '$lib/components/ui/sidebar';

	const navItems = [
		{ title: 'Users', url: '/admin/users', icon: Users },
		{ title: 'Backends', url: '/admin/backends', icon: Server },
		{ title: 'API Keys', url: '/admin/api-keys', icon: Key }
	];

	const currentPath = $derived($page.url.pathname);
	const isAdminRoute = $derived(currentPath.startsWith('/admin'));

	let open = $state(false);
	$effect(() => {
		if (isAdminRoute) open = true;
	});
</script>

{#if authStore.isAdmin}
	<Sidebar.Group>
		<Sidebar.Menu>
			<Collapsible.Root bind:open class="group/collapsible">
				<Sidebar.MenuItem>
					<Collapsible.Trigger>
						{#snippet child({ props })}
							<Sidebar.MenuButton
								{...props}
								tooltipContent="Administration"
								isActive={isAdminRoute}
							>
								<Shield />
								<span>Administration</span>
								<ChevronRight
									class="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90"
								/>
							</Sidebar.MenuButton>
						{/snippet}
					</Collapsible.Trigger>
					<Collapsible.Content>
						<Sidebar.MenuSub>
							{#each navItems as item}
								<Sidebar.MenuSubItem>
									<Sidebar.MenuSubButton
										isActive={currentPath === item.url ||
											currentPath.startsWith(item.url + '/')}
									>
										{#snippet child({ props }: { props: Record<string, unknown> })}
											<a href={item.url} {...props}>
												<item.icon />
												<span>{item.title}</span>
											</a>
										{/snippet}
									</Sidebar.MenuSubButton>
								</Sidebar.MenuSubItem>
							{/each}
						</Sidebar.MenuSub>
					</Collapsible.Content>
				</Sidebar.MenuItem>
			</Collapsible.Root>
		</Sidebar.Menu>
	</Sidebar.Group>
{/if}
