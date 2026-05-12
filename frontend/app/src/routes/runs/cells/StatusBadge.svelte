<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	type BadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline';

	let { status }: { status: string } = $props();

	const statusConfig = $derived.by((): { variant: BadgeVariant; label: string; class?: string; active?: boolean } => {
		switch (status) {
			case 'RUNNING':
				return { variant: 'secondary', label: 'Running', class: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 border-transparent', active: true };
			case 'UPLOADING':
				return { variant: 'secondary', label: 'Uploading', class: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 border-transparent', active: true };
			case 'COMPLETED':
				return { variant: 'default', label: 'Completed' };
			case 'FAILED':
				return { variant: 'destructive', label: 'Failed' };
			case 'ERROR':
				return { variant: 'destructive', label: 'Error', class: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 border-transparent' };
			case 'CANCELLED':
				return { variant: 'outline', label: 'Cancelled' };
			case 'SETUP':
				return { variant: 'secondary', label: 'Setup', active: true };
			case 'PENDING':
			default:
				return { variant: 'secondary', label: 'Pending', active: true };
		}
	});
</script>

<Badge variant={statusConfig.variant} class={statusConfig.class || ''}>
	{#if statusConfig.active}
		<LoaderCircle class="h-3.5 w-3.5 mr-1 animate-spin" />
	{/if}
	{statusConfig.label}
</Badge>
