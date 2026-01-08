<script>
	import { User, Server } from 'lucide-svelte';
	import { MultiSelectFilter } from '$lib/components/ui/multi-select-filter';
	import { authStore } from '$lib/stores/auth.svelte.js';

	let {
		selected = new Set(),
		availableOwners = [],
		onChange
	} = $props();

	// Build owner options: System + current user (first) + other users
	const options = $derived.by(() => {
		const opts = [];

		// System networks (no owner)
		opts.push({ id: 'system', label: 'System', icon: Server });

		// Current user always first (if they have networks)
		const currentUserInOwners = availableOwners.find(o => o.id === authStore.user?.id);
		if (currentUserInOwners) {
			opts.push({
				id: currentUserInOwners.id,
				label: currentUserInOwners.username,
				avatarUrl: currentUserInOwners.avatar_url,
				icon: User
			});
		}

		// Other users from availableOwners
		for (const owner of availableOwners) {
			if (owner.id !== authStore.user?.id) {
				opts.push({
					id: owner.id,
					label: owner.username,
					avatarUrl: owner.avatar_url,
					icon: User
				});
			}
		}

		return opts;
	});
</script>

<MultiSelectFilter
	label="Owner"
	{options}
	{selected}
	{onChange}
/>
