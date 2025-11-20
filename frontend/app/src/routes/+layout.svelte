<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { filtersPanelCollapsed } from '$lib/stores/networkPageStore';
	import AppSidebar from '$lib/components/AppSidebar.svelte';
	import AppSidebarRight from '$lib/components/AppSidebarRight.svelte';
	import DarkModeToggle from '$lib/components/DarkModeToggle.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { ModeWatcher } from 'mode-watcher';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb';
	import { PanelRight } from 'lucide-svelte';

	let { children, toolbar } = $props();

	// Get current page name for breadcrumb
	const pageName = $derived.by(() => {
		const path = $page.url.pathname;
		if (path === '/') return 'Home';
		if (path === '/database') return 'Database';
		if (path === '/network' || path.startsWith('/network/')) return 'Network';
		if (path === '/login') return 'Login';
		return 'Page';
	});

	// Sidebar open state - initialize from cookie if available
	let sidebarOpen = $state(true);

	// Determine if we should show the sidebar (hide only on login page)
	const showSidebar = $derived($page.url.pathname !== '/login');

	// Determine if we should show the right sidebar (only on network page)
	// Disabled - will move filters into main content area instead
	const showRightSidebar = $derived(false);

	// Determine if we should show the filters toggle button (only on network page)
	const showFiltersToggle = $derived($page.url.pathname.startsWith('/network'));

	onMount(async () => {
		// Check if there's a saved sidebar state in cookie
		const cookies = document.cookie.split(';');
		const sidebarCookie = cookies.find(c => c.trim().startsWith('sidebar:state='));
		if (sidebarCookie) {
			const value = sidebarCookie.split('=')[1];
			sidebarOpen = value === 'true';
		}

		// Initialize auth state on app load
		await authStore.init();

		// If auth is enabled and user is not authenticated, redirect to login
		// (except if already on login page)
		// Note: The API client's automatic 401 redirect skips /auth/ endpoints
		// to prevent redirect loops, so we handle the redirect manually here
		const currentPath = $page.url.pathname;
		if (!authStore.loading && !authStore.isAuthenticated) {
			if (currentPath !== '/login') {
				goto('/login');
			}
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<ModeWatcher />

{#if showSidebar}
	<Sidebar.Provider bind:open={sidebarOpen}>
		<AppSidebar />
		{#if showRightSidebar}
			<AppSidebarRight />
		{/if}
		<Sidebar.Inset>
			<header class="flex h-16 shrink-0 items-center gap-2 border-b border-border bg-background px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
				<div class="flex items-center gap-2">
					<Sidebar.Trigger />
					<div class="h-4 w-px bg-border"></div>
					<Breadcrumb.Root>
						<Breadcrumb.List>
							<Breadcrumb.Item>
								<Breadcrumb.Page>{pageName}</Breadcrumb.Page>
							</Breadcrumb.Item>
						</Breadcrumb.List>
					</Breadcrumb.Root>
				</div>
				<div class="ml-auto flex items-center gap-2">
					{#if toolbar}
						{@render toolbar()}
					{/if}
					{#if showFiltersToggle}
						<Button
							variant="ghost"
							size="icon"
							class="h-7 w-7"
							onclick={() => $filtersPanelCollapsed = !$filtersPanelCollapsed}
							title={$filtersPanelCollapsed ? 'Show filters' : 'Hide filters'}
						>
							<PanelRight class="h-4 w-4" />
						</Button>
					{/if}
					<DarkModeToggle />
				</div>
			</header>
			<div class="flex flex-1 flex-col gap-4 p-4 pt-0">
				{@render children?.()}
			</div>
		</Sidebar.Inset>
	</Sidebar.Provider>
{:else}
	{@render children?.()}
{/if}
