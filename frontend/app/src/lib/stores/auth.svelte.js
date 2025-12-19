/**
 * Authentication store using Svelte 5 runes
 * Manages user session state and provides auth methods
 */

import { auth } from '$lib/api/client.js';

class AuthStore {
	user = $state(null);
	loading = $state(true);
	error = $state(null);
	authEnabled = $state(null); // null = unknown, true = enabled, false = disabled

	/** Call on app startup to initialize auth state */
	async init() {
		this.loading = true;
		this.error = null;

		try {
			const response = await auth.me();
			this.user = response;
			this.authEnabled = true; // Auth is enabled and user is logged in
		} catch (err) {
			// Check if auth is disabled (400 error)
			if (err.status === 400) {
				// Auth is disabled - no login required
				this.authEnabled = false;
				this.user = null;
				this.error = null;
			} else if (err.status === 401) {
				// Auth is enabled but user is not logged in
				this.authEnabled = true;
				this.user = null;
				this.error = null;
			} else {
				// Other error
				console.error('Failed to fetch user:', err);
				this.error = err.message;
			}
		} finally {
			this.loading = false;
		}
	}

	login() {
		auth.login();
	}

	async logout() {
		this.loading = true;
		try {
			// Call logout endpoint (will redirect to login page)
			auth.logout();
		} catch (err) {
			console.error('Logout failed:', err);
			this.error = err.message;
			this.loading = false;
		}
	}

	get isAuthenticated() {
		return this.user !== null;
	}

	get displayName() {
		return this.user?.username || 'User';
	}

	get avatarUrl() {
		return this.user?.avatar_url || null;
	}

	get permissions() {
		return this.user?.permissions || [];
	}

	hasPermission(permission) {
		return this.permissions.includes(permission);
	}

	get isAdmin() {
		return this.hasPermission('admin');
	}

	get isApproved() {
		return this.permissions.length > 0;
	}

	get isPending() {
		return this.user !== null && this.permissions.length === 0;
	}

	get canManageNetworks() {
		return this.hasPermission('delete_networks');
	}

	get canViewNetworks() {
		return this.hasPermission('view_networks');
	}
}

export const authStore = new AuthStore();
