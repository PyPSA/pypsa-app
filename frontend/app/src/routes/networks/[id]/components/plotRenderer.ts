import type { PlotData } from '$lib/types.js';

let PlotlyModule: any = null;

export async function loadPlotly(): Promise<any> {
	if (!PlotlyModule) {
		PlotlyModule = await import('plotly.js-dist');
	}
	return PlotlyModule;
}

export function renderPlot(
	element: HTMLElement,
	plotData: PlotData,
	Plotly: any,
	height?: number,
): void {
	// Purge existing plot
	if ((element as any)._plotly) {
		try {
			Plotly.purge(element);
		} catch {
			// Ignore purge errors
		}
	}

	const layout = {
		...(plotData.layout as Record<string, unknown>),
		autosize: true,
		width: undefined,
		height: height || undefined,
		margin: { l: 60, r: 30, t: 30, b: 60 },
	};

	Plotly.newPlot(element, plotData.data, layout, {
		responsive: true,
		displayModeBar: true,
		displaylogo: false,
	});
}

export function purgePlot(element: HTMLElement, Plotly: any): void {
	try {
		Plotly.purge(element);
	} catch {
		// Ignore
	}
}

export function resizePlot(element: HTMLElement, Plotly: any): void {
	if (element && document.body.contains(element)) {
		try {
			Plotly.Plots.resize(element);
		} catch {
			// Ignore resize errors
		}
	}
}

export function humanizeStatistic(statistic: string): string {
	return statistic
		.split('_')
		.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
		.join(' ');
}

export function humanizePlotType(plotType: string): string {
	return plotType.charAt(0).toUpperCase() + plotType.slice(1);
}

export function plotTitle(statistic: string, plotType: string): string {
	return `${humanizeStatistic(statistic)} ${humanizePlotType(plotType)}`;
}
