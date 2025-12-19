import { getUser, requireAuth } from '$lib/server/auth.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies, fetch }) {
	const user = await getUser(cookies, fetch);
	return { user: requireAuth(user) };
}
