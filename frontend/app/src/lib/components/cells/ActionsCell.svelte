<script lang="ts">
	import type { Component } from 'svelte';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import MoreVertical from '@lucide/svelte/icons/more-vertical';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	interface Action {
		icon: any;
		label?: string;
		loadingLabel?: string;
		loading?: boolean;
		onclick?: () => void;
		variant?: 'default' | 'destructive';
	}

	let { actions = [] }: { actions: Action[] } = $props();

	const isLoading = $derived(actions.some((a) => a.loading));
</script>

{#if actions.length > 0}
	<div onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()} role="button" tabindex="-1">
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, unknown> })}
					<Button variant="ghost" size="sm" {...props} class="h-8 w-8 p-0" disabled={isLoading}>
						{#if isLoading}
							<Loader2 class="h-4 w-4 animate-spin" />
						{:else}
							<MoreVertical class="h-4 w-4" />
						{/if}
						<span class="sr-only">Open menu</span>
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				{#each actions as action, i}
					{#if i > 0 && action.variant === 'destructive'}
						<DropdownMenu.Separator />
					{/if}
					<DropdownMenu.Item
						onclick={action.onclick}
						class={action.variant === 'destructive' ? 'text-destructive focus:text-destructive' : ''}
						disabled={isLoading}
					>
						{#if action.loading}
							<Loader2 class="h-4 w-4 mr-2 animate-spin" />
							{action.loadingLabel || 'Loading...'}
						{:else}
							<action.icon class="h-4 w-4 mr-2" />
							{action.label}
						{/if}
					</DropdownMenu.Item>
				{/each}
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>
{/if}
