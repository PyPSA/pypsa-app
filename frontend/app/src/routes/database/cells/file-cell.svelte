<script>
	let { network, dirPath } = $props();
</script>

<div class="font-medium text-sm">{network.filename}</div>
{#if network.name}
	<div class="text-xs text-muted-foreground mt-0.5 max-w-64 truncate" title={network.name}>
		{network.name}
	</div>
{/if}
{#if dirPath}
	<div class="text-xs text-muted-foreground mt-0.5 font-mono" title={network.file_path}>
		{dirPath}
	</div>
{/if}
