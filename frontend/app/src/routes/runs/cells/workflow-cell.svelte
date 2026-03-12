<script lang="ts">
	import type { RunSummary } from '$lib/types.js';

	let { run }: { run: RunSummary } = $props();

	let source = $derived.by(() => {
		let s = run.workflow || '';
		if (s.startsWith('https://github.com/')) {
			s = s.replace('https://github.com/', '');
		} else if (s.startsWith('https://')) {
			s = s.replace('https://', '');
		} else if (s.startsWith('http://')) {
			s = s.replace('http://', '');
		}
		return s.replace(/\.git$/, '');
	});

	let ref = $derived.by(() => {
		const gitRef = run.git_ref;
		const sha = run.git_sha ? run.git_sha.slice(0, 8) : null;
		if (gitRef && sha) return `${gitRef}@${sha}`;
		if (sha) return `@${sha}`;
		if (gitRef) return gitRef;
		return null;
	});
</script>

{#if ref}
	<div class="flex flex-col gap-0.5">
		<span>{ref}</span>
		<span class="text-xs text-muted-foreground">{source}</span>
	</div>
{:else}
	<span>{source}</span>
{/if}
