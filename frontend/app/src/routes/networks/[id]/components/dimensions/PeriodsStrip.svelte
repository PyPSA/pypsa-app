<script lang="ts">
	import type { PeriodsInfo } from '$lib/types.js';
	import CalendarRange from '@lucide/svelte/icons/calendar-range';

	interface Props {
		info: PeriodsInfo;
	}

	let { info }: Props = $props();

	let overlayLabel = $derived(`${info.count.toLocaleString()} period${info.count === 1 ? '' : 's'}`);

	let startLabel = $derived(info.values.length > 0 ? String(info.values[0]) : null);
	let endLabel = $derived(info.values.length > 0 ? String(info.values[info.values.length - 1]) : null);
	let showEndpoints = $derived(startLabel !== null && startLabel !== endLabel);
</script>

<div class="flex items-center gap-2 text-xs">
	<CalendarRange size={14} class="text-muted-foreground shrink-0" />
	<div class="flex min-w-0 flex-1 max-w-xs">
		{#if showEndpoints}
			<div class="flex w-full items-center gap-2 text-[10px] text-muted-foreground">
				<span class="shrink-0">{startLabel}</span>
				<div class="flex-1 border-t border-dashed border-muted-foreground/30"></div>
				<span class="font-medium text-foreground shrink-0 whitespace-nowrap">{overlayLabel}</span>
				<div class="flex-1 border-t border-dashed border-muted-foreground/30"></div>
				<span class="shrink-0">{endLabel}</span>
			</div>
		{:else}
			<div class="flex w-full items-center justify-center text-[10px] text-muted-foreground">
				<span class="font-medium text-foreground shrink-0 whitespace-nowrap">{overlayLabel}</span>
			</div>
		{/if}
	</div>
</div>
