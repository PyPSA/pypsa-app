<script lang="ts">
	import { onMount } from 'svelte';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	import type { MarkdownCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Check from '@lucide/svelte/icons/check';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';

	interface Props {
		card: MarkdownCardDefinition;
		onupdate: (content: string) => void;
		onremove?: () => void;
		onfullscreen?: () => void;
	}

	let { card, onupdate, onremove, onfullscreen }: Props = $props();

	let editing = $state(false);
	let draft = $state('');
	let renderedHtml = $state('');

	// Start in edit mode if content is empty
	onMount(() => {
		if (!card.content) {
			editing = true;
			draft = '';
		}
	});

	$effect(() => {
		if (!editing) {
			const rawHtml = marked.parse(card.content || '*Click edit to add content*', {
				async: false,
			}) as string;
			renderedHtml = DOMPurify.sanitize(rawHtml);
		}
	});

	function startEdit() {
		draft = card.content;
		editing = true;
	}

	function save() {
		onupdate(draft);
		editing = false;
	}
</script>

<div class="group/card bg-card rounded-lg border border-border overflow-hidden flex flex-col h-full relative">
	<!-- Header / drag handle -->
	<div class="card-drag-handle flex items-center justify-between px-3 py-1 border-b border-border/50 shrink-0 cursor-grab">
		{#if onfullscreen}
			<button class="text-xs font-medium text-muted-foreground truncate hover:text-foreground transition-colors cursor-pointer" onclick={onfullscreen}>{card.name ?? 'Notes'}</button>
		{:else}
			<span class="text-xs font-medium text-muted-foreground truncate">{card.name ?? 'Notes'}</span>
		{/if}
		<div class="flex items-center gap-0.5">
		{#if editing}
			<Button variant="ghost" size="icon" class="h-6 w-6" onclick={save}>
				<Check class="h-3 w-3" />
			</Button>
		{:else}
			<Button variant="ghost" size="icon" class="h-6 w-6" onclick={startEdit}>
				<Pencil class="h-3 w-3" />
			</Button>
		{/if}
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props })}
					<Button variant="ghost" size="icon" class="h-6 w-6" {...props}>
						<Ellipsis class="h-3 w-3" />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end" class="w-36">
				<DropdownMenu.Item onclick={onremove}>
					<Trash2 class="h-3.5 w-3.5 mr-2" />
					Remove
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
		</div>
	</div>

	<!-- Content area -->
	<div class="flex-1 min-h-0 overflow-auto">
		{#if editing}
			<textarea
				class="w-full h-full p-3 text-sm bg-background text-foreground resize-none focus:outline-none font-mono"
				bind:value={draft}
				placeholder="Write markdown here..."
			></textarea>
		{:else}
			<div class="prose prose-sm dark:prose-invert p-3 max-w-none">
				{@html renderedHtml}
			</div>
		{/if}
	</div>
</div>
