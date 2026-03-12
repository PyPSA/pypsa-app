import { getUser, requireAuth } from '$lib/server/auth.js';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const user = await getUser(cookies, fetch);
	return { user: requireAuth(user) };
};
