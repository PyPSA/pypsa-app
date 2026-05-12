<script lang="ts">
	import AlertTriangle from '@lucide/svelte/icons/alert-triangle';

	let { network } = $props();
</script>

<div class="flex items-center gap-1.5">
	{#if network.file_missing}
		<AlertTriangle
			class="size-3.5 shrink-0 text-amber-600"
			aria-label="File missing"
		/>
	{/if}
	<div
		class="font-medium text-sm {network.file_missing ? 'text-muted-foreground line-through' : ''}"
		title={network.file_missing && network.file_path
			? `File no longer exists at ${network.file_path}`
			: undefined}
	>
		{network.filename}
	</div>
</div>
{#if network.name}
	<div class="text-xs text-muted-foreground mt-0.5 max-w-64 truncate" title={network.name}>
		{network.name}
	</div>
{/if}
