<script lang="ts">
	import { Filter, Search } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Avatar from '$lib/components/ui/avatar';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import type { FilterCategory, FilterState } from './index.js';

	interface FilterDialogProps {
		categories: FilterCategory[];
		filters: FilterState;
		onFilterChange: (filters: FilterState) => void;
		title?: string;
	}

	let {
		categories,
		filters,
		onFilterChange,
		title = 'Filters'
	}: FilterDialogProps = $props();

	const visibleCategories = $derived(
		categories.filter(c => (c.condition === undefined || c.condition) && c.options.length > 0)
	);

	const activeFilterCount = $derived(
		Object.values(filters).reduce((sum, s) => sum + s.size, 0)
	);

	let filterOpen = $state(false);
	let draftFilters = $state<FilterState>({});
	let activeTab = $state('');
	let searchQueries = $state<Record<string, string>>({});

	const activeCategory = $derived(
		visibleCategories.find(c => c.key === activeTab)
	);

	function cloneFilters(f: FilterState): FilterState {
		const result: FilterState = {};
		for (const cat of categories) {
			result[cat.key] = new Set(f[cat.key] ?? []);
		}
		return result;
	}

	function handleOpenChange(open: boolean) {
		if (open) {
			draftFilters = cloneFilters(filters);
			// Auto-select first category with active filters, or first visible
			const withFilters = visibleCategories.find(c => (filters[c.key]?.size ?? 0) > 0);
			activeTab = withFilters?.key ?? visibleCategories[0]?.key ?? '';
			searchQueries = {};
		}
		filterOpen = open;
	}

	function getFilteredOptions(category: FilterCategory) {
		const query = (searchQueries[category.key] ?? '').toLowerCase();
		if (!query) return category.options;
		return category.options.filter(o => o.label.toLowerCase().includes(query));
	}

	function toggleDraftFilter(key: string, id: string, checked: boolean) {
		const updated = new Set(draftFilters[key] ?? []);
		if (checked) updated.add(id);
		else updated.delete(id);
		draftFilters = { ...draftFilters, [key]: updated };
	}

	function selectAllInCategory(key: string, options: { id: string; label: string }[]) {
		const updated = new Set(draftFilters[key] ?? []);
		for (const opt of options) updated.add(opt.id);
		draftFilters = { ...draftFilters, [key]: updated };
	}

	function clearCategory(key: string) {
		draftFilters = { ...draftFilters, [key]: new Set<string>() };
	}

	function applyFilters() {
		onFilterChange(cloneFilters(draftFilters));
		filterOpen = false;
	}

	function clearAll() {
		const empty: FilterState = {};
		for (const cat of categories) {
			empty[cat.key] = new Set();
		}
		onFilterChange(empty);
		filterOpen = false;
	}

	const draftActiveCount = $derived(
		Object.values(draftFilters).reduce((sum, s) => sum + s.size, 0)
	);
</script>

{#if visibleCategories.length > 0}
	<Dialog.Root open={filterOpen} onOpenChange={handleOpenChange}>
		<Dialog.Trigger>
			{#snippet child({ props }: { props: Record<string, unknown> })}
				<Button variant="ghost" size="icon" class="h-8 w-8 relative" {...props}>
					<Filter class="h-4 w-4" />
					{#if activeFilterCount > 0}
						<span class="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
							{activeFilterCount}
						</span>
					{/if}
				</Button>
			{/snippet}
		</Dialog.Trigger>
		<Dialog.Content class="sm:max-w-2xl">
			<Dialog.Header>
				<Dialog.Title>{title}</Dialog.Title>
			</Dialog.Header>
			<div class="flex h-[60vh] max-h-[400px]">
				<!-- Left: category tabs -->
				<div class="flex w-28 shrink-0 flex-col gap-0.5 overflow-y-auto border-r pr-2">
					{#each visibleCategories as category}
						{@const catKey = category.key}
						{@const draftCount = (draftFilters[catKey]?.size ?? 0)}
						<button
							type="button"
							class="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm font-medium hover:bg-accent {activeTab === catKey ? 'bg-accent' : ''}"
							onclick={() => { activeTab = catKey; }}
						>
							<span class="truncate">{category.label}</span>
							{#if draftCount > 0}
								<span class="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-medium text-primary-foreground">
									{draftCount}
								</span>
							{/if}
						</button>
					{/each}
				</div>
				<!-- Right: active category options -->
				<div class="flex flex-1 flex-col gap-1 pl-3">
					{#if activeCategory}
						{@const catKey = activeCategory.key}
						{@const draftCount = (draftFilters[catKey]?.size ?? 0)}
						{@const filteredOptions = getFilteredOptions(activeCategory)}
						<div class="relative">
							<Search class="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
							<input
								type="text"
								class="w-full rounded-md border bg-transparent pl-7 pr-2 py-1 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
								placeholder="Search..."
								value={searchQueries[catKey] ?? ''}
								oninput={(e: Event) => { searchQueries[catKey] = (e.target as HTMLInputElement).value; }}
							/>
						</div>
						<div class="flex-1 overflow-y-auto grid grid-cols-1 gap-0.5 content-start">
							{#each filteredOptions as option}
								{@const isChecked = draftFilters[catKey]?.has(option.id) ?? false}
								<label class="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-accent cursor-pointer">
									<Checkbox
										checked={isChecked}
										onCheckedChange={(checked: boolean) => toggleDraftFilter(catKey, option.id, checked)}
									/>
									{#if option.avatarUrl}
										<Avatar.Root class="h-5 w-5">
											<Avatar.Image src={option.avatarUrl} alt={option.label} />
											<Avatar.Fallback class="text-[10px]">{option.label.slice(0, 2).toUpperCase()}</Avatar.Fallback>
										</Avatar.Root>
									{/if}
									<span class="truncate">{option.label}</span>
								</label>
							{/each}
							{#if filteredOptions.length === 0}
								<span class="px-2 py-1 text-sm text-muted-foreground">No matches</span>
							{/if}
						</div>
						<div class="flex items-center gap-2 pt-1">
							<Button variant="ghost" size="sm" class="h-6 px-2 text-xs" onclick={() => selectAllInCategory(catKey, activeCategory.options)}>
								All
							</Button>
							<Button variant="ghost" size="sm" class="h-6 px-2 text-xs" onclick={() => clearCategory(catKey)} disabled={draftCount === 0}>
								Clear
							</Button>
						</div>
					{/if}
				</div>
			</div>
			<Dialog.Footer>
				<Button variant="ghost" size="sm" onclick={clearAll} disabled={draftActiveCount === 0}>
					Clear all
				</Button>
				<Button size="sm" onclick={applyFilters}>Apply</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>
{/if}
