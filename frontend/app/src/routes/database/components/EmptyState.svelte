<script>
	import { Network, FolderOpen } from 'lucide-svelte';
	import * as Empty from '$lib/components/ui/empty';

	let { type = 'empty' } = $props();

	const config = $derived(type === 'empty'
		? { icon: Network, title: 'No Networks', description: 'Get started by uploading or scanning for networks.' }
		: { icon: FolderOpen, title: 'No Results', description: 'No networks match your current filters.' }
	);
</script>

<Empty.Root>
	<Empty.Header>
		<Empty.Media variant="icon">
			<config.icon />
		</Empty.Media>
		<Empty.Title>{config.title}</Empty.Title>
		<Empty.Description>{config.description}</Empty.Description>
	</Empty.Header>
</Empty.Root>
