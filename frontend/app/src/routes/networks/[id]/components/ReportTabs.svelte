<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { reportStore } from '$lib/stores/reportStore.svelte.js';
	import { slugify } from '$lib/utils.js';
	import * as Dialog from '$lib/components/ui/dialog';
	import Plus from '@lucide/svelte/icons/plus';
	import FilePlus from '@lucide/svelte/icons/file-plus';
	import X from '@lucide/svelte/icons/x';

	interface Props {
		networkId: string;
	}

	let { networkId }: Props = $props();

	let dialogOpen = $state(false);
	let editingId = $state<string | null>(null);
	let editName = $state('');

	let currentSlug = $derived($page.params.slug || '');

	function addBlankReport() {
		const name = `Report ${reportStore.reports.length + 1}`;
		const report = reportStore.addReport(name);
		dialogOpen = false;
		goto(`/networks/${networkId}/report/${slugify(report.name)}`);
	}

	function startRename(report: { id: string; name: string; isDefault: boolean }) {
		if (report.isDefault) return;
		editingId = report.id;
		editName = report.name;
	}

	function commitRename() {
		if (editingId && editName.trim()) {
			reportStore.renameReport(editingId, editName.trim());
			const isActive = slugify(reportStore.reports.find(r => r.id === editingId)?.name || '') === currentSlug
				|| reportStore.activeReportId === editingId;
			if (isActive) {
				goto(`/networks/${networkId}/report/${slugify(editName.trim())}`, { replaceState: true });
			}
		}
		editingId = null;
	}

	function cancelRename() {
		editingId = null;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			commitRename();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			cancelRename();
		}
	}

	function handleRemove(e: MouseEvent, reportId: string) {
		e.preventDefault();
		e.stopPropagation();
		const wasActive = reportStore.activeReportId === reportId;
		reportStore.removeReport(reportId);
		if (wasActive) {
			const fallback = slugify(reportStore.reports[0]?.name) || 'overview';
			goto(`/networks/${networkId}/report/${fallback}`);
		}
	}
</script>

<div>
	<div class="flex items-center">
		<div class="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
			{#each reportStore.reports as report (report.id)}
				{@const reportSlug = slugify(report.name)}
				{@const isActive = reportSlug === currentSlug}
				<a
					href="/networks/{networkId}/report/{reportSlug}"
					class="inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
					class:bg-background={isActive}
					class:text-foreground={isActive}
					class:shadow={isActive}
					data-state={isActive ? 'active' : 'inactive'}
				>
					{#if editingId === report.id}
						<!-- svelte-ignore a11y_autofocus -->
						<input
							class="bg-transparent border-b border-foreground outline-none text-sm w-24"
							bind:value={editName}
							onblur={commitRename}
							onkeydown={handleKeydown}
							autofocus
							onclick={(e) => e.stopPropagation()}
						/>
					{:else}
						<span ondblclick={() => startRename(report)}>{report.name}</span>
					{/if}
					{#if !report.isDefault}
						<button
							class="ml-1.5 rounded-sm opacity-50 hover:opacity-100"
							onclick={(e) => handleRemove(e, report.id)}
						>
							<X class="h-3 w-3" />
						</button>
					{/if}
				</a>
			{/each}
		</div>
		<button
			class="ml-1 h-8 w-8 inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
			onclick={() => (dialogOpen = true)}
			title="Add Report"
		>
			<Plus class="h-4 w-4" />
		</button>
	</div>
</div>

<Dialog.Root bind:open={dialogOpen}>
	<Dialog.Content class="sm:max-w-7xl max-h-[90vh] overflow-hidden flex flex-col" onOpenAutoFocus={(e) => e.preventDefault()}>
		<Dialog.Header>
			<Dialog.Title>New Report</Dialog.Title>
		</Dialog.Header>
		<div class="grid grid-cols-3 gap-3 py-4">
			<button
				class="flex flex-col items-center gap-2 rounded-lg border border-border p-4 hover:bg-accent hover:border-foreground/20 transition-colors cursor-pointer"
				onclick={addBlankReport}
			>
				<FilePlus class="h-8 w-8 text-muted-foreground" />
				<span class="text-sm font-medium">Blank Report</span>
			</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
