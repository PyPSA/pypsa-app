<script lang="ts">
	import Copy from '@lucide/svelte/icons/copy';
	import Button from '$lib/components/ui/button/button.svelte';
	import { copyToClipboard } from '$lib/utils.js';

	interface Props {
		token: string;
		onDone: () => void;
	}

	let { token, onDone }: Props = $props();
</script>

<div class="space-y-4">
	<div class="rounded-md border border-green-500/30 bg-green-500/10 p-3">
		<p class="mb-2 text-sm font-medium">API key created!</p>
		<p class="mb-2 text-xs text-muted-foreground">Copy now. You won't see it again.</p>
		<div class="flex items-center gap-2">
			<code class="flex-1 break-all rounded bg-muted px-2 py-1 text-xs">{token}</code>
			<Button
				variant="outline"
				size="icon"
				class="size-8 shrink-0"
				onclick={() => copyToClipboard(token)}
				title="Copy"
			>
				<Copy class="size-4" />
			</Button>
		</div>
	</div>
	<div class="flex justify-end">
		<Button size="sm" onclick={onDone}>Done</Button>
	</div>
</div>
