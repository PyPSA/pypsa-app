<script lang="ts">
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { filtersPanelCollapsed } from '$lib/stores/networkPageStore';
	import { breadcrumbStore } from '$lib/stores/breadcrumb.svelte.js';
	import { sidebarStore } from '$lib/stores/sidebar.svelte.js';
	import AppSidebar from '$lib/components/AppSidebar.svelte';
	import DarkModeToggle from '$lib/components/DarkModeToggle.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from 'svelte-sonner';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import * as Breadcrumb from '$lib/components/ui/breadcrumb';
	import { PanelRight } from 'lucide-svelte';

	let { children, toolbar }: { children?: Snippet; toolbar?: Snippet } = $props();

	// Get current page name for breadcrumb
	const pageName = $derived.by(() => {
		const path = $page.url.pathname;
		if (path === '/') return 'Home';
		if (path === '/database') return 'Database';
		if (path === '/network' || path.startsWith('/network/')) return 'Network';
		if (path === '/runs' || path.startsWith('/runs/')) return 'Runs';
		if (path.startsWith('/admin')) return 'Admin';
		if (path === '/login') return 'Login';
		return 'Page';
	});

	// Sidebar open state - uses shared store so pages can control it

	// Determine if we should show the sidebar
	const showSidebar = $derived(
		$page.url.pathname !== '/login' && $page.url.pathname !== '/pending-approval'
	);

	// Determine if we should show the filters toggle button (only on network page)
	const showFiltersToggle = $derived($page.url.pathname.startsWith('/network'));

	onMount(async () => {
		// Check if there's a saved sidebar state in cookie
		const cookies = document.cookie.split(';');
		const sidebarCookie = cookies.find(c => c.trim().startsWith('sidebar:state='));
		if (sidebarCookie) {
			const value = sidebarCookie.split('=')[1];
			sidebarStore.open = value === 'true';
		}

		// Initialize auth state for better client-side UI
		await authStore.init();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<ModeWatcher />
<Toaster position="bottom-right" closeButton richColors duration={8000} />

{#if showSidebar}
	<Sidebar.Provider bind:open={sidebarStore.open}>
		<AppSidebar />
		<Sidebar.Inset>
			<header class="flex h-16 shrink-0 items-center gap-2 border-b border-border bg-background px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
				<div class="flex items-center gap-2">
					<Sidebar.Trigger />
					<div class="h-4 w-px bg-border"></div>
					<Breadcrumb.Root>
						<Breadcrumb.List>
							<Breadcrumb.Item>
								{#if breadcrumbStore.items.length > 0}
									<Breadcrumb.Link href={'/' + pageName.toLowerCase()}>
										{pageName}
									</Breadcrumb.Link>
								{:else}
									<Breadcrumb.Page>{pageName}</Breadcrumb.Page>
								{/if}
							</Breadcrumb.Item>
							{#each breadcrumbStore.items as item}
								<Breadcrumb.Separator />
								<Breadcrumb.Item>
									{#if item.href}
										<Breadcrumb.Link href={item.href}>{item.label}</Breadcrumb.Link>
									{:else}
										<Breadcrumb.Page>{item.label}</Breadcrumb.Page>
									{/if}
								</Breadcrumb.Item>
							{/each}
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
