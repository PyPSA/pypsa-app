<script lang="ts">
	import {
		GitBranch, FolderArchive, Terminal, Settings2, ChevronRight
	} from 'lucide-svelte';
	let {
		showWorkflow = false,
		showFiles = false,
		signInHref = '/login'
	}: {
		showWorkflow?: boolean;
		showFiles?: boolean;
		signInHref?: string;
	} = $props();

	const sections = $derived([
		...(showWorkflow ? [{ icon: GitBranch, label: 'Workflow' }] : []),
		...(showFiles ? [{ icon: FolderArchive, label: 'Files' }] : []),
		{ icon: Terminal, label: 'Logs' },
		{ icon: Settings2, label: 'Configuration' },
	]);
</script>

<!-- Locked section placeholders — mirrors the real collapsible sections -->
<div class="space-y-4 opacity-50 pointer-events-none select-none" aria-hidden="true">
	{#each sections as section}
		<div class="bg-card rounded-lg border border-border overflow-hidden">
			<div class="flex items-center gap-2 px-4 py-3">
				<section.icon class="h-4 w-4 text-muted-foreground" />
				<span class="text-sm font-medium">{section.label}</span>
				<ChevronRight class="h-4 w-4 text-muted-foreground ml-auto" />
			</div>
		</div>
	{/each}
</div>

<!-- Sign-in prompt -->
<p class="text-sm text-muted-foreground text-center pt-4 pb-4"><a href={signInHref} class="underline hover:text-foreground transition-colors">Sign in</a> to see details.</p>
<p class="text-xs text-muted-foreground text-center">PyPSA App is <a href="https://github.com/PyPSA/pypsa-app" class="underline hover:text-foreground transition-colors">open source</a>.</p>
<p class="text-xs text-muted-foreground text-center">Deploy your own instance or use the local app.</p>
