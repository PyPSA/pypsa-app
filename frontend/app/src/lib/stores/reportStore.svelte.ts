import yaml from 'js-yaml';
import overviewYaml from '$lib/reports/overview.yaml?raw';
import { networks } from '$lib/api/client.js';
import { features } from '$lib/stores/features.svelte.js';

interface CardBase {
	id: string;
	name?: string;
	x: number;
	y: number;
	w: number;
	h: number;
}

export interface PlotCardDefinition extends CardBase {
	type: 'plot';
	statistic: string;
	plotType: string;
	parameters: {
		bus_carrier?: string[];
		query?: string;
	};
	expandBy?: 'bus_carrier' | 'country';
}

export interface MarkdownCardDefinition extends CardBase {
	type: 'markdown';
	content: string;
}

export interface ExploreCardDefinition extends CardBase {
	type: 'explore';
	bus_carrier?: string[];
	query?: string;
	branch_components?: string[];
	geometry?: boolean;
}

/** @deprecated Use ExploreCardDefinition */
export interface MapCardDefinition extends CardBase {
	type: 'map';
	parameters: Record<string, unknown>;
}

export interface OverviewCardDefinition extends CardBase {
	type: 'overview';
}

export interface ComponentTableCardDefinition extends CardBase {
	type: 'component_table';
	component: string;
}

export type CardDefinition =
	| PlotCardDefinition
	| MarkdownCardDefinition
	| ExploreCardDefinition
	| MapCardDefinition
	| OverviewCardDefinition
	| ComponentTableCardDefinition;

/** @deprecated Use PlotCardDefinition */
export type PlotDefinition = PlotCardDefinition;

export interface Report {
	id: string;
	name: string;
	cards: CardDefinition[];
	isDefault: boolean;
}

// Mirror of backend ALLOWED_STATISTICS with human-readable labels
export const STATISTICS: { value: string; label: string }[] = [
	{ value: 'energy_balance', label: 'Energy Balance' },
	{ value: 'installed_capacity', label: 'Installed Capacity' },
	{ value: 'optimal_capacity', label: 'Optimal Capacity' },
	{ value: 'expanded_capacity', label: 'Expanded Capacity' },
	{ value: 'capex', label: 'CAPEX' },
	{ value: 'installed_capex', label: 'Installed CAPEX' },
	{ value: 'expanded_capex', label: 'Expanded CAPEX' },
	{ value: 'opex', label: 'OPEX' },
	{ value: 'system_cost', label: 'System Cost' },
	{ value: 'revenue', label: 'Revenue' },
	{ value: 'market_value', label: 'Market Value' },
	{ value: 'supply', label: 'Supply' },
	{ value: 'withdrawal', label: 'Withdrawal' },
	{ value: 'curtailment', label: 'Curtailment' },
	{ value: 'capacity_factor', label: 'Capacity Factor' },
	{ value: 'transmission', label: 'Transmission' },
	{ value: 'prices', label: 'Prices' },
];

export const CHART_TYPES: { value: string; label: string }[] = [
	{ value: 'area', label: 'Area' },
	{ value: 'bar', label: 'Bar' },
	{ value: 'line', label: 'Line' },
];

function uid(): string {
	return crypto.randomUUID();
}

function loadDefaultReport(): Report {
	const raw = yaml.load(overviewYaml) as { name: string; cards: Omit<CardDefinition, 'id'>[] };
	return {
		id: 'default-overview',
		name: raw.name,
		isDefault: true,
		cards: raw.cards.map((c) => ({ ...c, id: uid() }) as CardDefinition),
	};
}

export interface ReportState {
	reports: Report[];
	activeReportId: string;
}

function defaultState(): ReportState {
	return { reports: [loadDefaultReport()], activeReportId: 'default-overview' };
}

function migrateState(state: ReportState): ReportState {
	for (const report of state.reports) {
		// Migrate old row-based format to flat cards
		if ('rows' in report && !('cards' in report) && !('plots' in report)) {
			const rows = (report as any).rows as { id: string; plots: any[] }[];
			let y = 0;
			const cards: CardDefinition[] = [];
			for (const row of rows) {
				const w = Math.floor(24 / row.plots.length);
				const h = Math.max(3, Math.round((row.plots[0]?.height ?? 400) / 80));
				for (let i = 0; i < row.plots.length; i++) {
					const p = row.plots[i];
					cards.push({
						id: p.id,
						type: 'plot',
						statistic: p.statistic,
						plotType: p.plotType,
						parameters: p.parameters,
						x: i * w,
						y,
						w,
						h,
					});
				}
				y += h;
			}
			(report as any).cards = cards;
			delete (report as any).rows;
		}

		// Migrate plots → cards
		if ('plots' in report && !('cards' in report)) {
			(report as any).cards = ((report as any).plots as any[]).map((p: any) => ({
				...p,
				type: p.type ?? 'plot',
			}));
			delete (report as any).plots;
		}
	}

	// Clean empty/none values from plot card parameters
	for (const report of state.reports) {
		if (!('cards' in report)) continue;
		for (const card of report.cards) {
			if (card.type !== 'plot' && (card as any).type !== undefined && (card as any).statistic === undefined) continue;
			// Ensure type field exists on old data
			if (!card.type) (card as any).type = 'plot';
			if (card.type !== 'plot') continue;
			const plot = card as PlotCardDefinition;
			if (plot.parameters?.bus_carrier) {
				plot.parameters.bus_carrier = plot.parameters.bus_carrier.filter(
					(c: string) => c && c !== 'none',
				);
				if (plot.parameters.bus_carrier.length === 0) delete plot.parameters.bus_carrier;
			}
			if (plot.parameters?.query) {
				const match = plot.parameters.query.match(/country in \[(.+)]/);
				if (match) {
					const raw = match[1]
						.split(',')
						.map((c: string) => c.trim().replace(/'/g, ''));
					const cleaned = raw.filter((c: string) => c && c !== 'none');
					if (cleaned.length < raw.length) {
						delete plot.parameters.query;
					}
				}
			}
		}
	}

	// Migrate map cards → explore cards
	for (const report of state.reports) {
		if (!('cards' in report) || !Array.isArray(report.cards)) continue;
		report.cards = report.cards.map((c) => {
			if (c.type === 'map') {
				return { ...c, type: 'explore' } as unknown as CardDefinition;
			}
			return c;
		});
	}

	// Prepend overview card to default report if missing (migrates pre-overview-card state)
	for (const report of state.reports) {
		if (!report.isDefault && report.id !== 'default-overview') continue;
		if (!('cards' in report) || !Array.isArray(report.cards)) continue;

		const existing = report.cards.find((c) => c.type === 'overview');
		if (!existing) {
			const overviewCard: OverviewCardDefinition = {
				id: uid(),
				type: 'overview',
				x: 0,
				y: 0,
				w: 5,
				h: 4,
			};
			const shifted = report.cards.map((c) => ({ ...c, y: c.y + 4 }));
			report.cards = [overviewCard, ...shifted];
		} else if (existing.h <= 2) {
			const delta = 4 - existing.h;
			existing.h = 4;
			for (const c of report.cards) {
				if (c.id !== existing.id && c.y >= existing.y + 2) c.y += delta;
			}
		}
	}

	return state;
}

function createReportStore() {
	let state = $state<ReportState>(defaultState());
	let currentNetworkId = $state<string | null>(null);
	let loading = $state(false);

	const DEBOUNCE_MS = 1500;
	let pendingTimer: ReturnType<typeof setTimeout> | undefined;
	let pendingNetworkId: string | undefined;
	let pendingPayload: ReportState | undefined;
	let initialized = false;

	function saveForNetwork(networkId: string, payload: ReportState) {
		fetch(`/api/v1/networks/${networkId}/reports`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload),
			keepalive: true,
			credentials: 'include',
		}).catch((e) => console.error('Failed to save reports:', e));
	}

	function flush() {
		if (pendingTimer !== undefined) clearTimeout(pendingTimer);
		pendingTimer = undefined;
		if (pendingNetworkId && pendingPayload) {
			saveForNetwork(pendingNetworkId, pendingPayload);
			pendingPayload = undefined;
			pendingNetworkId = undefined;
		}
	}

	function schedule(networkId: string, payload: ReportState) {
		if (features.demoMode) return;
		if (!initialized) { initialized = true; return; }
		pendingNetworkId = networkId;
		pendingPayload = payload;
		if (pendingTimer !== undefined) clearTimeout(pendingTimer);
		pendingTimer = setTimeout(flush, DEBOUNCE_MS);
	}

	if (typeof window !== 'undefined') {
		$effect.root(() => {
			$effect(() => {
				const snapshot = $state.snapshot(state);
				if (!currentNetworkId) return;
				schedule(currentNetworkId, snapshot);
			});
		});

		window.addEventListener('beforeunload', flush);
		document.addEventListener('visibilitychange', () => {
			if (document.visibilityState === 'hidden') flush();
		});
	}

	return {
		get reports() {
			return state.reports;
		},
		get activeReport(): Report {
			return state.reports.find((r) => r.id === state.activeReportId) ?? state.reports[0];
		},
		get activeReportId() {
			return state.activeReportId;
		},
		get loading() {
			return loading;
		},
		get currentNetworkId() {
			return currentNetworkId;
		},

		async loadForNetwork(networkId: string) {
			flush();

			currentNetworkId = networkId;
			loading = true;
			initialized = false;

			try {
				const saved = await networks.getReports(networkId);
				if (currentNetworkId !== networkId) return;

				if (saved) {
					state = migrateState(saved);
				} else {
					state = defaultState();
				}
			} catch {
				if (currentNetworkId !== networkId) return;
				state = defaultState();
			} finally {
				if (currentNetworkId === networkId) {
					loading = false;
				}
			}
		},

		setActiveReport(id: string) {
			state.activeReportId = id;
		},
		addReport(name: string, cards?: Omit<CardDefinition, 'id'>[]): Report {
			const report: Report = {
				id: uid(),
				name,
				isDefault: false,
				cards: cards ? cards.map((c) => ({ ...c, id: uid() }) as CardDefinition) : [],
			};
			state.reports = [...state.reports, report];
			state.activeReportId = report.id;
			return report;
		},
		removeReport(id: string) {
			state.reports = state.reports.filter((r) => r.id !== id);
			if (state.activeReportId === id) {
				state.activeReportId = state.reports[0]?.id ?? '';
			}
		},
		updateCard(reportId: string, cardId: string, updates: Partial<PlotCardDefinition> | Partial<MarkdownCardDefinition> | Partial<ExploreCardDefinition> | Partial<ComponentTableCardDefinition>) {
			state.reports = state.reports.map((r) => {
				if (r.id !== reportId) return r;
				return {
					...r,
					cards: r.cards.map((c) => (c.id === cardId ? { ...c, ...updates } as CardDefinition : c)),
				};
			});
		},
		addCard(reportId: string, card: CardDefinition) {
			state.reports = state.reports.map((r) => {
				if (r.id !== reportId) return r;
				return { ...r, cards: [...r.cards, card] };
			});
		},
		removeCard(reportId: string, cardId: string) {
			state.reports = state.reports.map((r) => {
				if (r.id !== reportId) return r;
				return { ...r, cards: r.cards.filter((c) => c.id !== cardId) };
			});
		},
		updateLayout(reportId: string, items: { id: string; x: number; y: number; w: number; h: number }[]) {
			state.reports = state.reports.map((r) => {
				if (r.id !== reportId) return r;
				return {
					...r,
					cards: r.cards.map((c) => {
						const item = items.find((i) => i.id === c.id);
						return item ? { ...c, x: item.x, y: item.y, w: item.w, h: item.h } : c;
					}),
				};
			});
		},
		renameReport(id: string, name: string) {
			state.reports = state.reports.map((r) =>
				r.id === id ? { ...r, name } : r,
			);
		},
		resetToDefaults() {
			state = defaultState();
		},
	};
}

export const reportStore = createReportStore();
