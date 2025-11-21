<script context="module">
	// Module-level cache that persists across component instances
	let cachedVersion = { pypsa: null, app: null };
</script>

<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { browser } from '$app/environment';
	import { version } from '$lib/api/client.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { LogOut, User } from 'lucide-svelte';

	// Use cached version immediately to prevent flicker
	let pypsaVersion = cachedVersion.pypsa;
	let appVersion = cachedVersion.app;

	// Format version for display (remove .post1. and git hash)
	function formatVersion(version) {
		if (!version) return version;
		return version.replace(/\.post\d+\./, '.').split('+')[0];
	}

	// Get the current page path to highlight active nav item
	const currentPath = $derived($page.url.pathname);

	// User menu state
	let showUserMenu = $state(false);
	let userMenuContainer = $state(null);

	function toggleUserMenu() {
		showUserMenu = !showUserMenu;
	}

	function handleLogout() {
		authStore.logout();
	}

	// Close dropdown when clicking outside or pressing Escape
	$effect(() => {
		if (!showUserMenu || !browser) return;

		function handleClickOutside(event) {
			if (userMenuContainer && !userMenuContainer.contains(event.target)) {
				showUserMenu = false;
			}
		}

		function handleEscape(event) {
			if (event.key === 'Escape') {
				showUserMenu = false;
			}
		}

		// Add event listeners
		document.addEventListener('click', handleClickOutside);
		document.addEventListener('keydown', handleEscape);

		// Cleanup on effect re-run or component unmount
		return () => {
			document.removeEventListener('click', handleClickOutside);
			document.removeEventListener('keydown', handleEscape);
		};
	});

	onMount(async () => {
		// Try to load from localStorage first
		try {
			const cached = localStorage.getItem('pypsa-version');
			if (cached) {
				const data = JSON.parse(cached);
				pypsaVersion = data.pypsa;
				appVersion = data.app;
				cachedVersion.pypsa = data.pypsa;
				cachedVersion.app = data.app;
			}
		} catch (e) {
			// Ignore cache errors
		}

		// Fetch fresh version
		try {
			const versionData = await version.get();
			pypsaVersion = versionData.pypsa_version;
			appVersion = versionData.app_version;
			cachedVersion.pypsa = versionData.pypsa_version;
			cachedVersion.app = versionData.app_version;

			// Cache for future navigations
			localStorage.setItem('pypsa-version', JSON.stringify({
				pypsa: versionData.pypsa_version,
				app: versionData.app_version
			}));
		} catch (err) {
			console.error('Failed to fetch version:', err);
		}
	});

	function isActive(path) {
		// For exact match on home and database paths
		if (path === '/' || path === '/networks') {
			return currentPath === path;
		}
		// For /network path, check exact match or with query params
		if (path === '/network') {
			return currentPath === '/network' || currentPath.startsWith('/network?');
		}
		// For other paths, check if current path starts with the link path
		return currentPath.startsWith(path);
	}
</script>

<header
	class="navbar-container fixed top-5 left-1/2 -translate-x-1/2 z-40 rounded-2xl flex items-center justify-between p-2 glass-morphism max-h-16"
>
	<!-- Left section -->
	<div class="flex items-center z-10">
		<a href="/database" class="font-bold text-lg flex items-center gap-2">
			<img
				src="https://raw.githubusercontent.com/PyPSA/PyPSA/master/docs/assets/logo/logo.svg"
				alt="PyPSA Logo"
				class="w-9 h-9"
			/>
			<span>PyPSA App</span>
			{#if appVersion}
				<span
					class="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded font-normal cursor-help"
					title="PyPSA Framework v{pypsaVersion}"
				>
					v{formatVersion(appVersion)}
				</span>
			{/if}
		</a>
	</div>

	<!-- Center section - absolutely positioned for true centering -->
	<div class="absolute left-1/2 transform -translate-x-1/2 flex items-center gap-1">
		<a
			href="/database"
			class="px-4 py-2 rounded-lg transition-colors duration-200 nav-link {isActive('/database') ? 'nav-link-active' : ''}"
		>
			Database
		</a>
		<a
			href="/network"
			class="px-4 py-2 rounded-lg transition-colors duration-200 nav-link {isActive('/network') ? 'nav-link-active' : ''}"
		>
			Network
		</a>
	</div>

	<!-- Right section - using ml-auto to push to the right -->
	<div class="flex items-center gap-1 ml-auto relative z-10">
		{#if authStore.isAuthenticated}
			<!-- User menu container -->
			<div class="relative" bind:this={userMenuContainer}>
				<!-- User menu button -->
				<button
					onclick={toggleUserMenu}
					class="user-menu-button flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors"
					title={authStore.displayName}
				>
					{#if authStore.avatarUrl}
						<img
							src={authStore.avatarUrl}
							alt={authStore.displayName}
							class="user-avatar"
						/>
					{:else}
						<User class="w-5 h-5 flex-shrink-0" />
					{/if}
					<span class="text-sm font-medium">{authStore.displayName}</span>
				</button>

				<!-- User dropdown menu -->
				{#if showUserMenu}
					<div class="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
						<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
							<p class="text-sm font-medium text-gray-900 dark:text-gray-100">
								{authStore.displayName}
							</p>
							{#if authStore.user?.email}
								<p class="text-xs text-gray-500 dark:text-gray-400">
									{authStore.user.email}
								</p>
							{/if}
						</div>
						<button
							onclick={handleLogout}
							class="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
						>
							<LogOut class="w-4 h-4" />
							Sign out
						</button>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</header>

<style>
	.navbar-container {
		width: 90%;
		max-width: 1280px;
	}

	@media (min-width: 768px) {
		.navbar-container {
			width: 70%;
		}
	}

	@media (min-width: 1024px) {
		.navbar-container {
			width: 75%;
		}
	}

	.glass-morphism {
		background: rgba(255, 255, 255, 0.25);
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
		border: 1px solid rgba(255, 255, 255, 0.18);
		box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
	}

	:global(.dark) .glass-morphism {
		background: rgba(0, 0, 0, 0.25);
		border: 1px solid rgba(255, 255, 255, 0.18);
		box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
	}

	.nav-link {
		position: relative;
		color: var(--color-foreground);
	}

	.nav-link:hover {
		background-color: var(--color-primary);
		color: var(--color-primary-foreground);
	}

	.nav-link-active {
		background-color: color-mix(in srgb, var(--color-primary) 15%, transparent);
		color: var(--color-primary);
		border: 1px solid color-mix(in srgb, var(--color-primary) 30%, transparent);
	}

	:global(.dark) .nav-link-active {
		background-color: color-mix(in srgb, var(--color-primary) 20%, transparent);
	}

	.user-avatar {
		width: 40px;
		height: 40px;
		min-width: 40px;
		min-height: 40px;
		max-width: 40px;
		max-height: 40px;
		border-radius: 50%;
		object-fit: cover;
		flex-shrink: 0;
		display: block;
	}

	.user-menu-button:hover {
		background-color: var(--color-primary);
		color: var(--color-primary-foreground);
	}
</style>
