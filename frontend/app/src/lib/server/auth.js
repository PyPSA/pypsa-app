/**
 * Server-side auth helpers for route protection
 */

import { redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

const backendUrl = env.BACKEND_URL || 'http://localhost:8000';

/**
 * Get current user from session cookie
 * @param {import('@sveltejs/kit').Cookies} cookies
 * @param {typeof fetch} fetch
 * @returns {Promise<object|null>}
 */
export async function getUser(cookies, fetch) {
	const session = cookies.get('pypsa_session');
	if (!session) return null;

	try {
		const res = await fetch(`${backendUrl}/api/v1/auth/me`, {
			headers: { Cookie: `pypsa_session=${session}` }
		});
		if (!res.ok) {
			console.error(`Auth check failed: ${res.status} ${res.statusText}`);
			return null;
		}
		return await res.json();
	} catch (error) {
		console.error('Failed to verify authentication:', error.message, {
			backendUrl,
			errorType: error.name
		});
		return null;
	}
}

function isPending(user) {
	return !user.permissions || user.permissions.length === 0;
}

function isAdmin(user) {
	return user.permissions?.includes('users:manage');
}

/**
 * Require authenticated user (not pending)
 * Redirects to /login if not authenticated, /pending-approval if pending
 */
export function requireAuth(user) {
	if (!user) throw redirect(302, '/login');
	if (isPending(user)) throw redirect(302, '/pending-approval');
	return user;
}

/**
 * Require admin user
 * Redirects to / if not admin
 */
export function requireAdmin(user) {
	requireAuth(user);
	if (!isAdmin(user)) throw redirect(302, '/');
	return user;
}
