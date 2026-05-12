<script lang="ts">
	let { network } = $props();
</script>

<div class="font-medium text-sm">{network.filename}</div>
{#if network.name}
	<div class="text-xs text-muted-foreground mt-0.5 max-w-64 truncate" title={network.name}>
		{network.name}
	</div>
{/if}
