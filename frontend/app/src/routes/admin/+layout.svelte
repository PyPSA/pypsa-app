<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children?: Snippet } = $props();
</script>

<div class="max-w-[80rem] mx-auto w-full py-8">
	{@render children?.()}
</div>
