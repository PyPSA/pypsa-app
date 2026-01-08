<script>
	let { network, getTagType, getTagColor } = $props();
</script>

<div class="flex flex-wrap gap-1">
	{#if network.tags && Array.isArray(network.tags) && network.tags.length > 0}
		{#each network.tags as tag}
			{@const tagType = getTagType(tag)}
			{@const colorClasses = getTagColor(tagType)}
			{#if typeof tag === 'object' && tag.name && tag.url}
				<!-- Tag is an object with name and url -->
				<a
					href={tag.url}
					target="_blank"
					rel="noopener noreferrer"
					class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full transition-colors {colorClasses}"
					title={tag.url}
					onclick={(e) => e.stopPropagation()}
				>
					{tag.name}
					<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="opacity-70">
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
						<polyline points="15 3 21 3 21 9"></polyline>
						<line x1="10" y1="14" x2="21" y2="3"></line>
					</svg>
				</a>
			{:else if typeof tag === 'string'}
				<!-- Tag is a plain string -->
				<span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full {colorClasses}">
					{tag}
				</span>
			{/if}
		{/each}
	{/if}
</div>
