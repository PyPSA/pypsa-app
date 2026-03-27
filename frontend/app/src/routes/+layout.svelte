<script lang="ts">
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { initFeatures } from '$lib/stores/features.svelte.js';
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
	import { ExternalLink, PanelRight, X } from 'lucide-svelte';
	import { version } from '$lib/api/client.js';
	import Badge from '$lib/components/ui/badge/badge.svelte';

	let { children, toolbar }: { children?: Snippet; toolbar?: Snippet } = $props();

	// Check if current path is an individual run detail page
	const isRunDetailPage = $derived(/^\/runs\/[^/]+$/.test($page.url.pathname));

	// Client-side auth guard
	$effect(() => {
		if (authStore.loading || authStore.authEnabled === null) return;
		if (authStore.authEnabled === false) return;

		const path = $page.url.pathname;

		if (path === '/login') {
			if (authStore.isAuthenticated && authStore.isApproved) {
				goto('/', { replaceState: true });
			}
		} else if (path === '/pending-approval') {
			if (!authStore.isAuthenticated) {
				goto('/login', { replaceState: true });
			} else if (authStore.isApproved) {
				goto('/', { replaceState: true });
			}
		} else if (/^\/runs\/[^/]+$/.test(path)) {
			// Individual run pages allow anonymous access for public runs
			// The page component handles auth-conditional rendering
			if (authStore.isAuthenticated && authStore.isPending) {
				goto('/pending-approval', { replaceState: true });
			}
		} else {
			if (!authStore.isAuthenticated) {
				goto('/login', { replaceState: true });
			} else if (authStore.isPending) {
				goto('/pending-approval', { replaceState: true });
			} else if (path.startsWith('/admin') && !authStore.isAdmin) {
				goto('/', { replaceState: true });
			}
		}
	});

	const pageInfo = $derived.by(() => {
		const path = $page.url.pathname;
		if (path === '/') return { name: 'Home', url: '/' };
		if (path === '/database' || path.startsWith('/database/')) return { name: 'Networks', url: '/database' };
		if (path === '/runs' || path.startsWith('/runs/')) return { name: 'Runs', url: '/runs' };
		if (path.startsWith('/admin')) return { name: 'Admin', url: '/admin' };
		if (path === '/login') return { name: 'Login', url: '/login' };
		return { name: 'Page', url: '/' };
	});
	const pageName = $derived(pageInfo.name);

	// Sidebar open state - uses shared store so pages can control it

	// Determine if we should show the sidebar
	const isPublicView = $derived(
		!authStore.loading && authStore.authEnabled !== false && !authStore.isAuthenticated && isRunDetailPage
	);
	const showSidebar = $derived(
		$page.url.pathname !== '/login' && $page.url.pathname !== '/pending-approval' && !isPublicView
	);

	// Determine if we should show the filters toggle button (only on network page)
	const showFiltersToggle = $derived($page.url.pathname.startsWith('/database/network'));

	// Version info for public header
	let publicVersion = $state<string | null>(null);

	function formatVersion(v: string | undefined) {
		if (!v) return v;
		return v.replace(/\.post\d+\./, '.').split('+')[0];
	}

	let bannerDismissed = $state(false);
	let bannerHeight = $state(0);

	function dismissBanner() {
		bannerDismissed = true;
		bannerHeight = 0;
		localStorage.setItem('dev-banner-dismissed', 'true');
	}

	onMount(async () => {
		bannerDismissed = localStorage.getItem('dev-banner-dismissed') === 'true';
		// Check if there's a saved sidebar state in cookie
		const cookies = document.cookie.split(';');
		const sidebarCookie = cookies.find(c => c.trim().startsWith('sidebar:state='));
		if (sidebarCookie) {
			const value = sidebarCookie.split('=')[1];
			sidebarStore.open = value === 'true';
		}

		// Initialize auth state and feature flags
		await Promise.all([authStore.init(), initFeatures()]);

		// Fetch version for public header
		try {
			const cached = localStorage.getItem('pypsa-version');
			if (cached) {
				const parsed = JSON.parse(cached);
				const cachedVersion = parsed.backend ?? parsed.pypsa;
				if (cachedVersion) publicVersion = formatVersion(cachedVersion) ?? null;
			}
			const data = await version.get();
			publicVersion = formatVersion(data.backend_version as string) ?? null;
		} catch {
			// Version display is optional
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<ModeWatcher />
<Toaster position="bottom-right" closeButton richColors duration={8000} />

<div class="flex h-svh flex-col overflow-hidden" style="--banner-height: {bannerDismissed ? 0 : bannerHeight}px">
	{#if !bannerDismissed && showSidebar}
		<div class="flex w-full items-center justify-center gap-2 bg-primary px-4 py-1.5 text-center text-sm font-medium text-primary-foreground"
			bind:clientHeight={bannerHeight}>
			<span>
				This app is in early development. Report bugs or suggest features by opening an
				<a href="https://github.com/PyPSA/pypsa-app/issues/new" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 font-semibold underline underline-offset-2">
					issue<ExternalLink class="h-3 w-3" /></a>.
			</span>
			<button onclick={() => dismissBanner()} class="ml-2 rounded p-0.5 hover:bg-white/20">
				<X class="h-3.5 w-3.5" />
			</button>
		</div>
	{/if}

	{#if authStore.loading}
		<div class="flex flex-1 items-center justify-center">
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-foreground"></div>
		</div>
	{:else if showSidebar}
		<Sidebar.Provider bind:open={sidebarStore.open} class="flex-1">
			<AppSidebar />
			<Sidebar.Inset class="overflow-auto">
				<header class="flex h-16 shrink-0 items-center gap-2 border-b border-border bg-background px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
					<div class="flex items-center gap-2">
						<Sidebar.Trigger />
						<div class="h-4 w-px bg-border"></div>
						<Breadcrumb.Root>
							<Breadcrumb.List>
								<Breadcrumb.Item>
									{#if breadcrumbStore.items.length > 0}
										<Breadcrumb.Link href={pageInfo.url}>
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
	{:else if isPublicView}
		<!-- Minimal public layout for unauthenticated run pages -->
		<div class="flex flex-col h-full">
			<header class="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background px-4">
				<a href="/login" class="flex items-center gap-2 hover:opacity-80 transition-opacity">
					<img src="/pypsa-logo.svg" alt="PyPSA App" class="h-6 w-6" />
					<span class="text-sm font-semibold">PyPSA App</span>
					{#if publicVersion}
						<Badge variant="default">v{publicVersion}</Badge>
					{/if}
				</a>
				<div class="ml-auto flex items-center gap-2">
					<DarkModeToggle />
					<Button variant="outline" size="sm" onclick={() => goto('/login')}>
						Sign in
					</Button>
				</div>
			</header>
			<div class="flex flex-1 flex-col gap-4 p-4 pt-0 overflow-auto">
				{@render children?.()}
			</div>
		</div>
	{:else}
		{@render children?.()}
	{/if}
</div>
