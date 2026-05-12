<script lang="ts">
	import type { ExploreCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import ExploreCard from './ExploreCard.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import Button from '$lib/components/ui/button/button.svelte';
	import Switch from '$lib/components/ui/switch/switch.svelte';
	import { parseCountriesFromQuery, buildCountryQuery } from '$lib/reports/filterHelpers.js';

	interface NetworkFacets {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	}

	interface Props {
		open: boolean;
		networkId: string;
		facets: NetworkFacets;
		initialCard?: ExploreCardDefinition | null;
		onsave: (card: ExploreCardDefinition) => void;
		onclose: () => void;
	}

	let { open = $bindable(), networkId, facets, initialCard = null, onsave, onclose }: Props =
		$props();

	const BRANCH_COMPONENTS = [
		{ value: 'Line', label: 'Lines' },
		{ value: 'Link', label: 'Links' },
		{ value: 'Transformer', label: 'Transformers' },
	];

	let name = $state('');
	let selectedCarriers = $state<Set<string>>(new Set());
	let selectedCountries = $state<Set<string>>(new Set());
	let selectedBranches = $state<Set<string>>(new Set(['Line', 'Link', 'Transformer']));
	let geometry = $state(false);

	$effect(() => {
		if (open) {
			name = initialCard?.name ?? '';
			selectedCarriers = new Set(
				(initialCard?.bus_carrier ?? Object.keys(facets.carriers ?? {})).filter(
					(c) => c && c !== 'none',
				),
			);
			selectedCountries = parseCountriesFromQuery(initialCard?.query, facets.countries);
			selectedBranches = new Set(
				initialCard?.branch_components ?? ['Line', 'Link', 'Transformer'],
			);
			geometry = initialCard?.geometry ?? false;
		}
	});

	let carriers = $derived(
		facets.carriers
			? Object.entries(facets.carriers)
					.filter(([name]) => name && name !== 'none')
					.map(([name, data]) => ({
						name,
						niceName: data.nice_name || name,
					}))
			: [],
	);
	let countries = $derived((facets.countries ?? []).filter((c) => c && c !== 'none'));

	function buildQuery(): string | undefined {
		return buildCountryQuery(selectedCountries, facets.countries);
	}

	function buildBusCarrier(): string[] | undefined {
		if (selectedCarriers.size > 0 && selectedCarriers.size < Object.keys(facets.carriers ?? {}).filter((c) => c && c !== 'none').length) {
			return Array.from(selectedCarriers);
		}
		return undefined;
	}

	function buildBranchComponents(): string[] | undefined {
		if (selectedBranches.size < BRANCH_COMPONENTS.length) {
			return Array.from(selectedBranches);
		}
		return undefined;
	}

	let previewCard = $derived<ExploreCardDefinition>({
		id: initialCard?.id ?? 'preview',
		type: 'explore',
		name: name.trim() || undefined,
		bus_carrier: buildBusCarrier(),
		query: buildQuery(),
		branch_components: buildBranchComponents(),
		geometry,
		x: 0,
		y: 0,
		w: 8,
		h: 8,
	});

	function handleSave() {
		const result: ExploreCardDefinition = {
			id: initialCard?.id ?? crypto.randomUUID(),
			type: 'explore',
			name: name.trim() || undefined,
			bus_carrier: buildBusCarrier(),
			query: buildQuery(),
			branch_components: buildBranchComponents(),
			geometry,
			x: initialCard?.x ?? 0,
			y: initialCard?.y ?? 0,
			w: initialCard?.w ?? 8,
			h: initialCard?.h ?? 8,
		};
		onsave(result);
	}

	function toggleCarrier(name: string) {
		const next = new Set(selectedCarriers);
		if (next.has(name)) next.delete(name);
		else next.add(name);
		selectedCarriers = next;
	}

	function toggleCountry(name: string) {
		const next = new Set(selectedCountries);
		if (next.has(name)) next.delete(name);
		else next.add(name);
		selectedCountries = next;
	}

	function toggleBranch(name: string) {
		const next = new Set(selectedBranches);
		if (next.has(name)) next.delete(name);
		else next.add(name);
		selectedBranches = next;
	}
</script>

<Dialog.Root bind:open onOpenChange={(v) => { if (!v) onclose(); }}>
	<Dialog.Content class="sm:max-w-7xl max-h-[90vh] overflow-hidden flex flex-col" onOpenAutoFocus={(e) => e.preventDefault()}>
		<Dialog.Header>
			<Dialog.Title>{initialCard ? 'Edit Explore Map' : 'Add Explore Map'}</Dialog.Title>
		</Dialog.Header>

		<div class="flex gap-6 flex-1 min-h-0 overflow-hidden">
			<!-- Left: Settings -->
			<div class="w-1/3 flex flex-col gap-4 overflow-y-auto pr-2">
				<!-- Name -->
				<div>
					<label class="text-sm font-medium mb-1.5 block">
						Name
						<input
							type="text"
							class="w-full text-sm border border-border rounded-md px-3 py-1.5 bg-background text-foreground placeholder:text-muted-foreground mt-1.5"
							placeholder="Explore"
							bind:value={name}
						/>
					</label>
				</div>

				<!-- Branch Components -->
				<div>
					<span class="text-sm font-medium mb-1.5 block">Branch Components</span>
					<div class="flex flex-col gap-1.5">
						{#each BRANCH_COMPONENTS as bc}
							<label class="flex items-center gap-2 cursor-pointer">
								<Checkbox
									checked={selectedBranches.has(bc.value)}
									onCheckedChange={() => toggleBranch(bc.value)}
								/>
								<span class="text-sm">{bc.label}</span>
							</label>
						{/each}
					</div>
				</div>

				<!-- Geometry -->
				<div>
					<label class="flex items-center justify-between">
						<span class="text-sm font-medium">Use line geometries</span>
						<Switch checked={geometry} onCheckedChange={(v) => (geometry = v)} />
					</label>
					<p class="text-xs text-muted-foreground mt-1">Show actual line paths instead of straight lines</p>
				</div>

				<!-- Carriers -->
				{#if carriers.length > 0}
					<div>
						<span class="text-sm font-medium mb-1.5 block">Carriers</span>
						<div class="flex flex-col gap-1.5 max-h-40 overflow-y-auto">
							{#each carriers as carrier}
								<label class="flex items-center gap-2 cursor-pointer">
									<Checkbox
										checked={selectedCarriers.has(carrier.name)}
										onCheckedChange={() => toggleCarrier(carrier.name)}
									/>
									<span class="text-sm">{carrier.niceName}</span>
								</label>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Countries -->
				{#if countries.length > 0}
					<div>
						<span class="text-sm font-medium mb-1.5 block">Countries</span>
						<div class="flex flex-col gap-1.5 max-h-40 overflow-y-auto">
							{#each countries as country}
								<label class="flex items-center gap-2 cursor-pointer">
									<Checkbox
										checked={selectedCountries.has(country)}
										onCheckedChange={() => toggleCountry(country)}
									/>
									<span class="text-sm">{country}</span>
								</label>
							{/each}
						</div>
					</div>
				{/if}
			</div>

			<!-- Right: Preview -->
			<div class="w-2/3 flex flex-col min-h-0">
				<span class="text-sm font-medium mb-1.5 block">Preview</span>
				<div class="flex-1 min-h-0">
					{#key JSON.stringify([previewCard.bus_carrier, previewCard.query, previewCard.branch_components, previewCard.geometry])}
						<ExploreCard
							card={previewCard}
							{networkId}
							onedit={() => {}}
							onremove={() => {}}
						/>
					{/key}
				</div>
			</div>
		</div>

		<Dialog.Footer>
			<Button variant="outline" onclick={onclose}>Cancel</Button>
			<Button onclick={handleSave}>Save</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
