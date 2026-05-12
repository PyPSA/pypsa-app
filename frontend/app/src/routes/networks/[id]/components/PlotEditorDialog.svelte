<script lang="ts">
	import { STATISTICS, CHART_TYPES, type PlotCardDefinition } from '$lib/stores/reportStore.svelte.js';
	import { plotTitle } from './plotRenderer.js';
	import PlotCard from './PlotCard.svelte';
	import PlotGroup from './PlotGroup.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import Button from '$lib/components/ui/button/button.svelte';
	import { parseCountriesFromQuery } from '$lib/reports/filterHelpers.js';

	interface NetworkFacets {
		carriers?: Record<string, { nice_name?: string; color?: string }>;
		countries?: string[];
	}

	interface Props {
		open: boolean;
		networkId: string;
		facets: NetworkFacets;
		initialPlot?: PlotCardDefinition | null;
		onsave: (plot: PlotCardDefinition) => void;
		onclose: () => void;
	}

	let { open = $bindable(), networkId, facets, initialPlot = null, onsave, onclose }: Props =
		$props();

	// Form state
	let name = $state('');
	let statistic = $state('energy_balance');
	let plotType = $state('bar');
	let expandBy = $state<'bus_carrier' | 'country' | ''>('');
	let selectedCarriers = $state<Set<string>>(new Set());
	let selectedCountries = $state<Set<string>>(new Set());

	// Reset form when dialog opens
	$effect(() => {
		if (open) {
			name = initialPlot?.name ?? '';
			statistic = initialPlot?.statistic ?? 'energy_balance';
			plotType = initialPlot?.plotType ?? 'bar';
			expandBy = initialPlot?.expandBy ?? '';
			selectedCarriers = new Set(
				(initialPlot?.parameters?.bus_carrier ?? Object.keys(facets.carriers ?? {})).filter(
					(c) => c && c !== 'none',
				),
			);
			selectedCountries = parseCountriesFromQuery(initialPlot?.parameters?.query, facets.countries);
		}
	});

	let title = $derived(plotTitle(statistic, plotType));

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

	let unavailableCarriers = $derived(
		[...selectedCarriers].filter((c) => !Object.keys(facets.carriers ?? {}).includes(c)),
	);
	let unavailableCountries = $derived(
		[...selectedCountries].filter((c) => !(facets.countries ?? []).includes(c)),
	);

	function clearUnavailableCarriers() {
		const available = new Set(Object.keys(facets.carriers ?? {}));
		selectedCarriers = new Set([...selectedCarriers].filter((c) => available.has(c)));
	}

	function clearUnavailableCountries() {
		const available = new Set(facets.countries ?? []);
		selectedCountries = new Set([...selectedCountries].filter((c) => available.has(c)));
	}

	function buildParameters(): PlotCardDefinition['parameters'] {
		const params: PlotCardDefinition['parameters'] = {};
		if (selectedCarriers.size > 0) {
			params.bus_carrier = Array.from(selectedCarriers);
		}
		// Only pass country query when a subset is selected (passing all is same as not filtering)
		const validCountries = Array.from(selectedCountries).filter(Boolean);
		if (validCountries.length > 0 && validCountries.length < countries.filter(Boolean).length) {
			const formatted = validCountries.map((c) => `'${c}'`).join(', ');
			params.query = `country in [${formatted}]`;
		}
		return params;
	}

	// Build a live PlotCardDefinition from current form state for preview
	let previewPlot = $derived<PlotCardDefinition>({
		id: initialPlot?.id ?? 'preview',
		type: 'plot',
		name: name.trim() || undefined,
		statistic,
		plotType,
		parameters: buildParameters(),
		x: 0,
		y: 0,
		w: 8,
		h: 5,
		expandBy: expandBy || undefined,
	});

	interface GroupItem {
		plot: PlotCardDefinition;
		label: string;
	}

	let previewGroupItems = $derived.by((): GroupItem[] | null => {
		if (!previewPlot.expandBy) return null;

		let items: GroupItem[] = [];
		if (previewPlot.expandBy === 'bus_carrier' && facets.carriers) {
			const carrierKeys = previewPlot.parameters.bus_carrier?.length
				? previewPlot.parameters.bus_carrier
				: Object.keys(facets.carriers);
			items = carrierKeys
				.filter((n) => n && n !== 'none' && n in facets.carriers!)
				.map((n) => ({
					label: facets.carriers![n].nice_name || n,
					plot: { ...previewPlot, parameters: { ...previewPlot.parameters, bus_carrier: [n] }, expandBy: undefined },
				}));
		} else if (previewPlot.expandBy === 'country' && facets.countries) {
			const match = previewPlot.parameters.query?.match(/country in \[(.+)]/);
			const selected = match
				? match[1].split(',').map((c) => c.trim().replace(/'/g, '')).filter(Boolean)
				: facets.countries.filter((c) => c && c !== 'none');
			items = selected
				.filter((c) => c && c !== 'none' && facets.countries!.includes(c))
				.map((c) => ({
					label: c,
					plot: { ...previewPlot, parameters: { ...previewPlot.parameters, query: `country in ['${c}']` }, expandBy: undefined },
				}));
		}

		return items.length > 0 ? items : null;
	});

	function handleSave() {
		const result: PlotCardDefinition = {
			id: initialPlot?.id ?? crypto.randomUUID(),
			type: 'plot',
			name: name.trim() || undefined,
			statistic,
			plotType,
			parameters: buildParameters(),
			x: initialPlot?.x ?? 0,
			y: initialPlot?.y ?? 0,
			w: initialPlot?.w ?? 8,
			h: initialPlot?.h ?? 5,
			expandBy: expandBy || undefined,
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

</script>

<Dialog.Root bind:open onOpenChange={(v) => { if (!v) onclose(); }}>
	<Dialog.Content class="sm:max-w-7xl max-h-[90vh] overflow-hidden flex flex-col" onOpenAutoFocus={(e) => e.preventDefault()}>
		<Dialog.Header>
			<Dialog.Title>{initialPlot ? 'Edit Plot' : 'Add Plot'}</Dialog.Title>
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
							placeholder={title}
							bind:value={name}
						/>
					</label>
				</div>

				<!-- Statistic -->
				<div>
					<span class="text-sm font-medium mb-1.5 block">Statistic</span>
					<Select.Root
						type="single"
						value={statistic}
						onValueChange={(v) => {
							statistic = v;
						}}
					>
						<Select.Trigger class="w-full">
							{STATISTICS.find((s) => s.value === statistic)?.label ?? statistic}
						</Select.Trigger>
						<Select.Content>
							{#each STATISTICS as stat}
								<Select.Item value={stat.value}>{stat.label}</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
				</div>

				<!-- Plot Type -->
				<div>
					<span class="text-sm font-medium mb-1.5 block">Plot Type</span>
					<div class="flex flex-wrap gap-1.5">
						{#each CHART_TYPES as ct}
							<button
								class="px-3 py-1.5 text-xs rounded-md border transition-colors {plotType ===
								ct.value
									? 'bg-primary text-primary-foreground border-primary'
									: 'bg-background border-border hover:bg-accent'}"
								onclick={() => (plotType = ct.value)}
							>
								{ct.label}
							</button>
						{/each}
					</div>
				</div>

				<!-- Expand by -->
				<div>
					<span class="text-sm font-medium mb-1.5 block">Expand by</span>
					<div class="flex flex-wrap gap-1.5">
						{#each [{ value: '', label: 'None' }, { value: 'bus_carrier', label: 'Per Carrier' }, { value: 'country', label: 'Per Country' }] as opt}
							<button
								class="px-3 py-1.5 text-xs rounded-md border transition-colors {expandBy ===
								opt.value
									? 'bg-primary text-primary-foreground border-primary'
									: 'bg-background border-border hover:bg-accent'}"
								onclick={() => (expandBy = opt.value as typeof expandBy)}
							>
								{opt.label}
							</button>
						{/each}
					</div>
					{#if expandBy}
						<p class="text-xs text-muted-foreground mt-1">
							One plot per {expandBy === 'bus_carrier' ? 'carrier' : 'country'} — select specific ones below or leave empty for all
						</p>
					{/if}
				</div>

				<!-- Carriers -->
				{#if carriers.length > 0 || unavailableCarriers.length > 0}
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
							{#if unavailableCarriers.length > 0}
								<div class="flex items-center gap-2 mt-1">
									<hr class="flex-1 border-border" />
									<span class="text-xs text-muted-foreground">Not on this network</span>
									<hr class="flex-1 border-border" />
								</div>
								{#each unavailableCarriers as carrier}
									<label class="flex items-center gap-2 opacity-50 cursor-default">
										<Checkbox checked={true} disabled />
										<span class="text-sm">{carrier}</span>
									</label>
								{/each}
								<button
									class="text-xs text-muted-foreground hover:text-foreground mt-0.5 text-left"
									onclick={clearUnavailableCarriers}
								>
									Clear unavailable
								</button>
							{/if}
						</div>
					</div>
				{/if}

				<!-- Countries -->
				{#if countries.length > 0 || unavailableCountries.length > 0}
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
							{#if unavailableCountries.length > 0}
								<div class="flex items-center gap-2 mt-1">
									<hr class="flex-1 border-border" />
									<span class="text-xs text-muted-foreground">Not on this network</span>
									<hr class="flex-1 border-border" />
								</div>
								{#each unavailableCountries as country}
									<label class="flex items-center gap-2 opacity-50 cursor-default">
										<Checkbox checked={true} disabled />
										<span class="text-sm">{country}</span>
									</label>
								{/each}
								<button
									class="text-xs text-muted-foreground hover:text-foreground mt-0.5 text-left"
									onclick={clearUnavailableCountries}
								>
									Clear unavailable
								</button>
							{/if}
						</div>
					</div>
				{/if}
			</div>

			<!-- Right: Preview -->
			<div class="w-2/3 flex flex-col min-h-0">
				<span class="text-sm font-medium mb-1.5 block">Preview</span>
				<div class="flex-1 min-h-0">
					{#key `${previewPlot.expandBy}`}
						{#if previewGroupItems}
							<PlotGroup
								items={previewGroupItems}
								{networkId}
								{facets}
								parentPlot={previewPlot}
								onedit={() => {}}
								onremove={() => {}}
								showActions={false}
							/>
						{:else}
							<PlotCard
								plot={previewPlot}
								{networkId}
								{facets}
								showActions={false}
							/>
						{/if}
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
