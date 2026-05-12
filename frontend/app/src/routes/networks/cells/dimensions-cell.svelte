<script lang="ts">
	import Clock from '@lucide/svelte/icons/clock';
	import CalendarRange from '@lucide/svelte/icons/calendar-range';
	import Waypoints from '@lucide/svelte/icons/waypoints';

	let { network } = $props();
</script>

<div class="flex flex-col gap-1">
	{#if network.dimensions}
		{#if network.dimensions.timesteps?.count}
			<div class="inline-flex items-center gap-1.5 text-xs">
				<Clock size={14} class="text-muted-foreground" />
				<span class="font-semibold">{network.dimensions.timesteps.count.toLocaleString()}</span>
			</div>
		{/if}
		{#if network.dimensions.periods?.count}
			<div class="inline-flex items-center gap-1.5 text-xs">
				<CalendarRange size={14} class="text-muted-foreground" />
				<span class="font-semibold">{network.dimensions.periods.count.toLocaleString()}</span>
			</div>
		{/if}
		{#if network.dimensions.scenarios?.count}
			<div class="inline-flex items-center gap-1.5 text-xs">
				<Waypoints size={14} class="text-muted-foreground" />
				<span class="font-semibold">{network.dimensions.scenarios.count.toLocaleString()}</span>
			</div>
		{/if}
	{:else}
		<span class="text-xs text-muted-foreground">-</span>
	{/if}
</div>
