<script>
	import * as Sheet from "$lib/components/ui/sheet/index.js";
	import { cn } from "$lib/utils.js";
	import { SIDEBAR_WIDTH_MOBILE } from "./constants.js";
	import { useSidebar } from "./context.svelte.js";

	let {
		ref = $bindable(null),
		side = "left",
		variant = "sidebar",
		collapsible = "offcanvas",
		class: className,
		children,
		...restProps
	} = $props();

	const sidebar = useSidebar();
</script>

{#if collapsible === "none"}
	<div
		class={cn(
			"bg-sidebar text-sidebar-foreground w-(--sidebar-width) flex h-full flex-col",
			className
		)}
		bind:this={ref}
		{...restProps}
	>
		{@render children?.()}
	</div>
{:else if sidebar.isMobile}
	<Sheet.Root
		bind:open={() => sidebar.openMobile, (v) => sidebar.setOpenMobile(v)}
		{...restProps}
	>
		<Sheet.Content
			data-sidebar="sidebar"
			data-slot="sidebar"
			data-mobile="true"
			class="bg-sidebar text-sidebar-foreground w-(--sidebar-width) p-0 [&>button]:hidden"
			style="--sidebar-width: {SIDEBAR_WIDTH_MOBILE};"
			{side}
		>
			<Sheet.Header class="sr-only">
				<Sheet.Title>Sidebar</Sheet.Title>
				<Sheet.Description>Displays the mobile sidebar.</Sheet.Description>
			</Sheet.Header>
			<div class="flex h-full w-full flex-col">
				{@render children?.()}
			</div>
		</Sheet.Content>
	</Sheet.Root>
{:else}
	<div
		bind:this={ref}
		class="text-sidebar-foreground group peer block"
		data-state={sidebar.state}
		data-collapsible={sidebar.state === "collapsed" ? collapsible : ""}
		data-variant={variant}
		data-side={side}
		data-slot="sidebar"
	>
		<!-- This is what handles the sidebar gap on desktop -->
		<div
			data-slot="sidebar-gap"
			style="width: {sidebar.state === 'collapsed' && collapsible === 'icon' ? 'var(--sidebar-width-icon)' : 'var(--sidebar-width)'};"
			class={cn(
				"relative bg-transparent transition-[width] duration-200 ease-linear",
				"group-data-[side=right]:rotate-180"
			)}
		></div>
		<div
			data-slot="sidebar-container"
			style={"width: " + (sidebar.state === 'collapsed' && collapsible === 'icon' ? 'var(--sidebar-width-icon)' : 'var(--sidebar-width)') + ";"}
			class={cn(
				"fixed inset-y-0 z-10 flex h-svh transition-[width] duration-200 ease-linear",
				side === "left"
					? "left-0"
					: "right-0",
				variant === "floating" || variant === "inset"
					? "p-2"
					: "",
				className
			)}
			{...restProps}
		>
			<div
				data-sidebar="sidebar"
				data-slot="sidebar-inner"
				class={cn(
					"bg-sidebar flex h-full w-full flex-col",
					variant === "floating"
						? "rounded-lg border border-sidebar-border shadow-sm"
						: variant !== "inset"
							? side === "left"
								? "border-r border-sidebar-border"
								: "border-l border-sidebar-border"
							: ""
				)}
			>
				{@render children?.()}
			</div>
		</div>
	</div>
{/if}
