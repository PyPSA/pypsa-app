<script lang="ts">
	import type { TimestepsInfo } from '$lib/types.js';
	import { formatStripDateFull, formatPandasFreq } from '$lib/utils.js';
	import Clock from '@lucide/svelte/icons/clock';

	interface Props {
		info: TimestepsInfo;
	}

	let { info }: Props = $props();

	let freqLabel = $derived(formatPandasFreq(info.freq));
	let countLabel = $derived(info.count.toLocaleString());
	let overlayLabel = $derived(freqLabel ? `${countLabel} × ${freqLabel}` : countLabel);

	let startLabel = $derived(info.start ? formatStripDateFull(info.start) : null);
	let endLabel = $derived(info.end ? formatStripDateFull(info.end) : null);
	let showEndpoints = $derived(startLabel !== null && endLabel !== null);
</script>

<div class="flex items-center gap-2 text-xs">
	<Clock size={14} class="text-muted-foreground shrink-0" />
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
