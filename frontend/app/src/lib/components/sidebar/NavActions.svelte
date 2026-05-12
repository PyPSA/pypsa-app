<script lang="ts">
	import ScanSearch from '@lucide/svelte/icons/scan-search';
	import Upload from '@lucide/svelte/icons/upload';
	import {
		SidebarGroup,
		SidebarGroupLabel,
		SidebarMenu,
		SidebarMenuButton,
		SidebarMenuItem
	} from '$lib/components/ui/sidebar';

	// Props for event handlers
	let { onScanNetworks = () => {} }: { onScanNetworks?: () => void } = $props();
</script>

<SidebarGroup>
	<SidebarGroupLabel>Quick Actions</SidebarGroupLabel>
	<SidebarMenu>
		<SidebarMenuItem>
			<SidebarMenuButton onclick={onScanNetworks}>
				<ScanSearch />
				<span>Scan Networks</span>
			</SidebarMenuButton>
		</SidebarMenuItem>
		<SidebarMenuItem>
			<SidebarMenuButton aria-disabled="true">
				<Upload />
				<span>Upload Network</span>
			</SidebarMenuButton>
		</SidebarMenuItem>
	</SidebarMenu>
</SidebarGroup>
