import { auth, type AuthProviderInfo } from '$lib/api/client.js';
import type { User, ApiError, Permission } from '$lib/types.js';

class AuthStore {
	user: User | null = $state(null);
	loading: boolean = $state(true);
	error: string | null = $state(null);
	authEnabled: boolean | null = $state(null);
	providers: AuthProviderInfo[] = $state([]);

	async init(): Promise<void> {
		this.loading = true;
		this.error = null;

		try {
			const { providers } = await auth.providers();
			this.providers = providers;
			this.authEnabled = providers.length > 0;

			if (this.authEnabled) {
				try {
					const response = await auth.me();
					this.user = response;
				} catch (err) {
					const apiErr = err as ApiError;
					if (apiErr.status === 400 || apiErr.status === 401) {
						this.user = null;
					} else {
						console.error('Failed to fetch user:', err);
						this.error = apiErr.message;
					}
				}
			}
		} catch (err) {
			console.error('Failed to fetch auth providers:', err);
			this.authEnabled = false;
			this.error = (err as Error).message;
		} finally {
			this.loading = false;
		}
	}

	async refreshUser(): Promise<void> {
		try {
			this.user = await auth.me();
		} catch (err) {
			const apiErr = err as ApiError;
			if (apiErr.status === 400 || apiErr.status === 401) {
				this.user = null;
			} else {
				console.error('Failed to refresh user:', err);
			}
		}
	}

	async logout(): Promise<void> {
		this.loading = true;
		try {
			auth.logout();
		} catch (err) {
			console.error('Logout failed:', err);
			this.error = (err as Error).message;
			this.loading = false;
		}
	}

	get isAuthenticated(): boolean {
		return this.user !== null;
	}

	get displayName(): string {
		return this.user?.username || 'User';
	}

	get avatarUrl(): string | null {
		return this.user?.avatar_url || null;
	}

	get permissions(): string[] {
		return this.user?.permissions || [];
	}

	hasPermission(permission: Permission): boolean {
		return this.permissions.includes(permission);
	}

	get isAdmin(): boolean {
		return this.hasPermission('users:manage');
	}

	get isApproved(): boolean {
		return this.permissions.length > 0;
	}

	get isPending(): boolean {
		return this.isAuthenticated && !this.isApproved;
	}
}

export const authStore = new AuthStore();
