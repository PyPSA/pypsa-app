<script>
	import { page } from '$app/stores';
	import { Search, X } from 'lucide-svelte';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';

	// Props
	let {
		selectedTags = $bindable(new Set()),
		tagSearchQuery = $bindable(''),
		allTags = [],
		onClearFilters = () => {}
	} = $props();

	// Only show filters on /networks page
	const showFilters = $derived($page.url.pathname === '/networks');

	// Filter tags based on search query
	const filteredTags = $derived(allTags.filter(tag =>
		tag.toLowerCase().includes(tagSearchQuery.toLowerCase())
	));

	function toggleTag(tagName) {
		if (selectedTags.has(tagName)) {
			selectedTags.delete(tagName);
		} else {
			selectedTags.add(tagName);
		}
		selectedTags = selectedTags; // Trigger reactivity
	}

	function getTagType(tag) {
		const name = tag.toLowerCase();

		// Check for config type
		if (name.includes('config') || name.endsWith('.yaml') || name.endsWith('.yml')) {
			return 'config';
		}

		// Check for version type (commit hash or version-like)
		if (/^[a-f0-9]{7,}$/.test(name) || name === 'master' || name === 'main') {
			return 'version';
		}

		// Otherwise, assume it's a model/project
		return 'model';
	}

	function getTagColor(type) {
		switch (type) {
			case 'model':
				return 'tag-model';
			case 'version':
				return 'tag-version';
			case 'config':
				return 'tag-config';
			default:
				return 'tag-default';
		}
	}
</script>

{#if showFilters}
	<Sidebar.Group>
		<Sidebar.GroupLabel>Filters</Sidebar.GroupLabel>
		<Sidebar.GroupContent class="space-y-3">
			<!-- Search input -->
			<div class="relative">
				<Search class="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
				<Input
					type="text"
					placeholder="Search tags..."
					bind:value={tagSearchQuery}
					class="pl-8 h-8"
				/>
			</div>

			<!-- Clear filters button -->
			{#if selectedTags.size > 0}
				<Button
					variant="outline"
					size="sm"
					class="w-full h-8"
					on:click={onClearFilters}
				>
					<X class="mr-2 h-4 w-4" />
					Clear ({selectedTags.size})
				</Button>
			{/if}

			<!-- Tags list -->
			{#if filteredTags.length > 0}
				<div class="space-y-1 max-h-[300px] overflow-y-auto">
					{#each filteredTags as tag}
						{@const isSelected = selectedTags.has(tag)}
						{@const tagType = getTagType(tag)}
						{@const tagColorClass = getTagColor(tagType)}
						<button
							class="w-full text-left px-2 py-1.5 rounded-md text-sm transition-colors hover:bg-accent flex items-center gap-2 {isSelected ? 'bg-accent' : ''}"
							on:click={() => toggleTag(tag)}
						>
							<div class="flex-1 flex items-center gap-2">
								<span class="inline-block w-2 h-2 rounded-full {tagColorClass}"></span>
								<span class="truncate">{tag}</span>
							</div>
							{#if isSelected}
								<Badge variant="secondary" class="h-5 px-1.5 text-xs">✓</Badge>
							{/if}
						</button>
					{/each}
				</div>
			{:else if tagSearchQuery}
				<p class="text-sm text-muted-foreground text-center py-4">
					No tags found
				</p>
			{/if}
		</Sidebar.GroupContent>
	</Sidebar.Group>
{/if}
