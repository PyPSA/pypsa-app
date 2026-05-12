<script lang="ts">
	import type { ScenariosInfo } from '$lib/types.js';
	import Waypoints from '@lucide/svelte/icons/waypoints';

	interface Props {
		info: ScenariosInfo;
	}

	let { info }: Props = $props();

	let overlayLabel = $derived(`${info.count.toLocaleString()} scenario${info.count === 1 ? '' : 's'}`);

	let startLabel = $derived(info.names.length > 0 ? info.names[0] : null);
	let endLabel = $derived(info.names.length > 1 ? info.names[info.names.length - 1] : null);
	let showEndpoints = $derived(
		info.names.length >= 2 && startLabel !== null && endLabel !== null && startLabel !== endLabel
	);
</script>

<div class="flex items-center gap-2 text-xs">
	<Waypoints size={14} class="text-muted-foreground shrink-0" />
	<div class="flex min-w-0 flex-1 max-w-xs">
		{#if showEndpoints}
			<div class="flex w-full items-center gap-2 text-[10px] text-muted-foreground">
				<span class="shrink-0 truncate max-w-[30%]">{startLabel}</span>
				<div class="flex-1 border-t border-dashed border-muted-foreground/30"></div>
				<span class="font-medium text-foreground shrink-0 whitespace-nowrap">{overlayLabel}</span>
				<div class="flex-1 border-t border-dashed border-muted-foreground/30"></div>
				<span class="shrink-0 truncate max-w-[30%]">{endLabel}</span>
			</div>
		{:else}
			<div class="flex w-full items-center justify-center text-[10px] text-muted-foreground">
				<span class="font-medium text-foreground shrink-0 whitespace-nowrap">{overlayLabel}</span>
			</div>
		{/if}
	</div>
</div>
