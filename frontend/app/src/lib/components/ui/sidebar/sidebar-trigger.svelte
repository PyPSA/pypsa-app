<script>
	import { Button } from "$lib/components/ui/button/index.js";
	import { cn } from "$lib/utils.js";
	import PanelLeftIcon from "@lucide/svelte/icons/panel-left";
	import { useSidebar } from "./context.svelte.js";

	let {
		ref = $bindable(null),
		class: className,
		onclick,
		...restProps
	} = $props();

	const sidebar = useSidebar();

	function handleClick(e) {
		onclick?.(e);
		sidebar?.toggle();
	}
</script>

<Button
	bind:ref
	data-sidebar="trigger"
	data-slot="sidebar-trigger"
	variant="ghost"
	size="icon-lg"
	class={cn(className)}
	type="button"
	onclick={handleClick}
	{...restProps}
>
	<PanelLeftIcon />
</Button>
