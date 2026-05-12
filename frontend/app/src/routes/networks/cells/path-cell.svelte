<script lang="ts">
	import Copy from '@lucide/svelte/icons/copy';
	import { Button } from '$lib/components/ui/button';
	import { copyToClipboard } from '$lib/utils.js';

	let { network } = $props();

	const fullPath = $derived<string>(
		network.is_external && network.file_path ? network.file_path : ''
	);

	const display = $derived<string>(collapse(fullPath));

	function collapse(p: string): string {
		if (!p) return '';
		const m = p.match(/^(\/(?:home|Users)\/[^/]+)(\/.*)?$/);
		if (m) return '~' + (m[2] ?? '');
		return p;
	}

	function handleCopy(e: MouseEvent) {
		e.stopPropagation();
		if (fullPath) copyToClipboard(fullPath);
	}
</script>

{#if fullPath}
	<div class="group flex items-center gap-1 max-w-[20rem]">
		<button
			type="button"
			dir="rtl"
			class="font-mono text-xs truncate text-left cursor-pointer hover:text-foreground"
			title={fullPath}
			onclick={handleCopy}
		>
			<bdi>{display}</bdi>
		</button>
		<Button
			variant="ghost"
			size="icon"
			class="size-6 shrink-0 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity"
			title="Copy path"
			onclick={handleCopy}
		>
			<Copy class="size-3.5" />
		</Button>
	</div>
{/if}
