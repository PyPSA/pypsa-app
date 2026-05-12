<script lang="ts">
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { formatDate, formatRelativeTime, formatRelativeTimeDetailed, parseUTCDate } from '$lib/utils.js';

	type Props = {
		value: string | null | undefined;
		variant?: 'absolute' | 'relative';
		class?: string;
	};

	let { value, variant = 'relative', class: className = '' }: Props = $props();

	const trigger = $derived(
		variant === 'relative' ? formatRelativeTime(value) : formatDate(value)
	);
	const detailedRelative = $derived(formatRelativeTimeDetailed(value));
	const absolute = $derived(formatDate(value));
	// Normalize to ISO 8601 with explicit timezone so the <time datetime=> attribute
	// is unambiguous for assistive tech and microformat parsers.
	const isoDatetime = $derived(value ? parseUTCDate(value).toISOString() : undefined);
</script>

{#if !value}
	<span class={className}>—</span>
{:else}
	<Tooltip.Root>
		<Tooltip.Trigger class={className}>
			<time datetime={isoDatetime}>{trigger}</time>
		</Tooltip.Trigger>
		<Tooltip.Content>
			<p>{detailedRelative}</p>
			<p>{absolute}</p>
		</Tooltip.Content>
	</Tooltip.Root>
{/if}
