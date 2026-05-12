<script lang="ts">
	import LogOut from '@lucide/svelte/icons/log-out';
	import User from '@lucide/svelte/icons/user';
	import ChevronsUpDown from '@lucide/svelte/icons/chevrons-up-down';
	import LogIn from '@lucide/svelte/icons/log-in';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { goto } from '$app/navigation';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import * as Sidebar from '$lib/components/ui/sidebar';

	const sidebar = Sidebar.useSidebar();

	// Get user initials for fallback
	function getInitials(name: string) {
		if (!name) return 'U';
		const parts = name.split(' ');
		if (parts.length >= 2) {
			return (parts[0][0] + parts[1][0]).toUpperCase();
		}
		return name.substring(0, 2).toUpperCase();
	}

	// Handle login
	function handleLogin() {
		goto('/login');
	}

	// Handle logout
	function handleLogout() {
		authStore.logout();
	}
</script>

<Sidebar.Menu>
	<Sidebar.MenuItem>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, unknown> })}
					{#if authStore.isAuthenticated}
						<Sidebar.MenuButton size="lg" class="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground" {...props}>
							<Avatar.Root class="h-8 w-8 rounded-lg">
								<Avatar.Image src={authStore.avatarUrl} alt={authStore.displayName} />
								<Avatar.Fallback class="rounded-lg">
									{getInitials(authStore.displayName)}
								</Avatar.Fallback>
							</Avatar.Root>
							<div class="grid flex-1 text-left text-sm leading-tight">
								<span class="truncate font-medium">{authStore.displayName}</span>
								<span class="truncate text-xs text-muted-foreground">{authStore.user?.email || ''}</span>
							</div>
							<ChevronsUpDown class="ml-auto size-4" />
						</Sidebar.MenuButton>
					{:else}
						<Sidebar.MenuButton size="lg" onclick={handleLogin}>
							<LogIn class="h-4 w-4" />
							<span class="truncate font-medium">Sign in</span>
						</Sidebar.MenuButton>
					{/if}
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content
				class="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
				side={sidebar.isMobile ? 'bottom' : 'right'}
				align="end"
				sideOffset={4}
			>
				<DropdownMenu.Label class="p-0 font-normal">
					<div class="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
						{#if authStore.isAuthenticated}
							<Avatar.Root class="h-8 w-8 rounded-lg">
								<Avatar.Image src={authStore.avatarUrl} alt={authStore.displayName} />
								<Avatar.Fallback class="rounded-lg">
									{getInitials(authStore.displayName)}
								</Avatar.Fallback>
							</Avatar.Root>
							<div class="grid flex-1 text-left text-sm leading-tight">
								<span class="truncate font-medium">{authStore.displayName}</span>
								<span class="truncate text-xs text-muted-foreground">{authStore.user?.email || ''}</span>
							</div>
						{/if}
					</div>
				</DropdownMenu.Label>
				<DropdownMenu.Separator />
				<DropdownMenu.Group>
					<DropdownMenu.Item disabled>
						<User class="mr-2 h-4 w-4" />
						<span>Profile</span>
					</DropdownMenu.Item>
				</DropdownMenu.Group>
				<DropdownMenu.Separator />
				<DropdownMenu.Item onclick={handleLogout}>
					<LogOut class="mr-2 h-4 w-4" />
					<span>Log out</span>
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</Sidebar.MenuItem>
</Sidebar.Menu>
