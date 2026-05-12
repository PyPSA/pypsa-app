<script lang="ts">
	import type { OverviewCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import type { NetworkWithFacets } from '../types.js';
	import {
		formatFileSize,
		getTagColor,
		getTagType,
	} from '$lib/utils.js';
	import DateTime from '$lib/components/DateTime.svelte';
	import Calendar from '@lucide/svelte/icons/calendar';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import HardDrive from '@lucide/svelte/icons/hard-drive';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Button from '$lib/components/ui/button/button.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import TimestepsStrip from './dimensions/TimestepsStrip.svelte';
	import PeriodsStrip from './dimensions/PeriodsStrip.svelte';
	import ScenariosStrip from './dimensions/ScenariosStrip.svelte';

	interface Props {
		card: OverviewCardDefinition;
		network: NetworkWithFacets;
		onremove?: () => void;
	}

	let { network, onremove }: Props = $props();
</script>

<div class="group/card bg-card rounded-lg border border-border overflow-hidden flex flex-col h-full relative">
	<!-- Header bar (drag handle) -->
	<div class="card-drag-handle flex items-center justify-between px-3 py-1 border-b border-border/50 shrink-0 cursor-grab">
		<span class="text-xs font-medium text-muted-foreground truncate">Overview</span>
		<div class="flex items-center gap-0.5">
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

	<!-- Content -->
	<div class="flex-1 min-h-0 p-4 overflow-auto flex flex-col gap-3">
		<!-- Section 1: Title + tags -->
		<div class="flex items-start gap-3">
			<div class="min-w-0 flex-1">
				{#if network.name && network.name !== network.filename}
					<h1 class="text-lg font-semibold truncate">{network.name}</h1>
					<div class="text-xs text-muted-foreground min-w-0">
						<span class="font-mono truncate">{network.filename}</span>
					</div>
				{:else}
					<h1 class="text-lg font-semibold font-mono truncate">{network.filename}</h1>
				{/if}
			</div>
			{#if network.tags && Array.isArray(network.tags) && network.tags.length > 0}
				<div class="flex flex-wrap justify-end gap-1 shrink-0">
					{#each network.tags as tag}
						{@const tagType = getTagType(tag)}
						{@const colorClasses = getTagColor(tagType)}
						{#if typeof tag === 'object' && tag.name && tag.url}
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
							<span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full {colorClasses}">
								{tag}
							</span>
						{/if}
					{/each}
				</div>
			{/if}
		</div>

		<!-- Section 2: Dimension strips -->
		{#if network.dimensions}
			<div class="flex flex-col gap-1.5">
				{#if network.dimensions.timesteps.count > 0}
					<TimestepsStrip info={network.dimensions.timesteps} />
				{/if}
				{#if network.dimensions.periods.count > 0}
					<PeriodsStrip info={network.dimensions.periods} />
				{/if}
				{#if network.dimensions.scenarios.count > 1}
					<ScenariosStrip info={network.dimensions.scenarios} />
				{/if}
			</div>
		{/if}

		<!-- Section 3: Meta footer -->
		<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground mt-auto">
			{#if network.owner}
				<div class="flex items-center gap-1.5">
					{#if network.owner.avatar_url}
						<img
							src={network.owner.avatar_url}
							alt={network.owner.username}
							class="h-4 w-4 rounded-full"
						/>
					{/if}
					<span>{network.owner.username}</span>
				</div>
				<span class="opacity-50">•</span>
			{/if}
			<div class="flex items-center gap-1.5">
				<Calendar class="h-3.5 w-3.5" />
				<DateTime value={network.created_at} />
			</div>
			{#if network.file_size}
				<span class="opacity-50">•</span>
				<div class="flex items-center gap-1.5" title={`${network.file_size.toLocaleString()} bytes`}>
					<HardDrive class="h-3.5 w-3.5" />
					<span>{formatFileSize(network.file_size)}</span>
				</div>
			{/if}
			{#if network.source_run_id}
				<span class="opacity-50">•</span>
				<a
					href={`/runs/${network.source_run_id}`}
					class="inline-flex items-center gap-1 hover:text-foreground transition-colors"
					onclick={(e) => e.stopPropagation()}
				>
					<ExternalLink class="h-3.5 w-3.5" />
					<span>source run</span>
				</a>
			{/if}
		</div>
	</div>
</div>
