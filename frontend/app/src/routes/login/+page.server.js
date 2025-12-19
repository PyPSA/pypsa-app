import { redirect } from '@sveltejs/kit';
import { getUser } from '$lib/server/auth.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies, fetch }) {
	const user = await getUser(cookies, fetch);
	// Redirect approved users to home
	if (user && user.permissions?.length > 0) {
		throw redirect(302, '/');
	}
	return {};
}
