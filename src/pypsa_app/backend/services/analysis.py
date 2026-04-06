"""Custom analysis pipelines for PyPSA networks.

Goes beyond PyPSA's built-in statistics — implements Script_MEE-style dashboard
analyses: dispatch profiles, line loading, price duration curves, and
cross-border flows.

All functions accept a loaded PyPSA network and return Plotly figure JSON dicts,
ready for caching and frontend rendering.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pypsa_app.backend.services.network import load_service
from pypsa_app.backend.utils.carrier_colors import (
    COUNTRY_COLORS,
    PLOTLY_TEMPLATE,
    get_carrier_color,
    sort_carriers_by_dispatch_order,
)

logger = logging.getLogger(__name__)

# Try polars for fast aggregations, fall back to pandas-only
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False


# ── Dispatch / Energy Balance ────────────────────────────────────────────────


def dispatch_area(
    file_paths: list[str],
    *,
    country: str | None = None,
    carrier_filter: list[str] | None = None,
    resample: str | None = None,
) -> dict[str, Any]:
    """Stacked area chart of generation dispatch by carrier over time.

    Mirrors Script_MEE's dispatch stacking with canonical carrier colors
    and dispatch order.
    """
    service = load_service(file_paths, use_cache=True)
    n = service.n

    # Get generator dispatch (p) — rows=snapshots, cols=generators
    gen_p = n.generators_t.p
    if gen_p.empty:
        return _empty_figure("No generator dispatch data available")

    # Map generators to carriers
    carrier_map = n.generators.carrier
    dispatch = gen_p.T.groupby(carrier_map).sum().T

    # Optional country filter
    if country:
        country_buses = n.buses.index[n.buses.get("country", "") == country]
        country_gens = n.generators.index[n.generators.bus.isin(country_buses)]
        gen_p_filtered = gen_p[gen_p.columns.intersection(country_gens)]
        carrier_map_filtered = n.generators.carrier.loc[gen_p_filtered.columns]
        dispatch = gen_p_filtered.T.groupby(carrier_map_filtered).sum().T

    # Optional carrier filter
    if carrier_filter:
        dispatch = dispatch[[c for c in carrier_filter if c in dispatch.columns]]

    # Optional resampling (e.g., "D" for daily, "W" for weekly)
    if resample and len(dispatch) > 1:
        dispatch = dispatch.resample(resample).mean()

    # Sort columns by dispatch order
    ordered_carriers = sort_carriers_by_dispatch_order(list(dispatch.columns))
    dispatch = dispatch[ordered_carriers]

    # Build stacked area plot
    fig = go.Figure()
    for carrier in ordered_carriers:
        fig.add_trace(
            go.Scatter(
                x=dispatch.index.astype(str),
                y=dispatch[carrier].values,
                name=carrier,
                mode="lines",
                stackgroup="dispatch",
                fillcolor=get_carrier_color(carrier),
                line={"width": 0.5, "color": get_carrier_color(carrier)},
            )
        )

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Generation Dispatch" + (f" — {country}" if country else ""),
        xaxis_title="Time",
        yaxis_title="Power (MW)",
        hovermode="x unified",
        legend={"traceorder": "normal"},
    )

    return json.loads(fig.to_json())


# ── Line Loading ─────────────────────────────────────────────────────────────


def line_loading_histogram(
    file_paths: list[str],
    *,
    security_margin_pct: float = 70.0,
    n1_limit_pct: float = 100.0,
    top_n: int = 20,
) -> dict[str, Any]:
    """Line loading distribution histogram + top-N congested lines bar chart.

    Two subplots:
    1. Histogram of max loading % across all lines
    2. Horizontal bar chart of top-N most loaded lines
    """
    service = load_service(file_paths, use_cache=True)
    n = service.n

    if not len(n.lines) or n.lines_t.p0.empty:
        return _empty_figure("No line loading data available")

    # Compute loading percentage: |p0| / s_nom
    s_nom = n.lines.s_nom
    s_nom_safe = s_nom.replace(0, np.nan)
    max_loading = (n.lines_t.p0.abs().max() / s_nom_safe * 100).dropna()

    if POLARS_AVAILABLE:
        # Vectorized with polars for speed on large networks
        df = pl.DataFrame(
            {
                "line": max_loading.index,
                "loading_pct": max_loading.values,
            }
        )
        top_lines = df.sort("loading_pct", descending=True).head(top_n)
        top_names = top_lines["line"].to_list()
        top_values = top_lines["loading_pct"].to_list()
        hist_values = df["loading_pct"].to_list()
    else:
        hist_values = max_loading.values
        top = max_loading.nlargest(top_n)
        top_names = top.index.tolist()
        top_values = top.values.tolist()

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["Loading Distribution", f"Top {top_n} Congested Lines"],
        column_widths=[0.5, 0.5],
    )

    # Histogram
    fig.add_trace(
        go.Histogram(
            x=hist_values,
            nbinsx=50,
            marker_color="steelblue",
            opacity=0.7,
            name="Lines",
        ),
        row=1,
        col=1,
    )

    # Threshold lines
    for pct, color, label in [
        (security_margin_pct, "orange", f"Security ({security_margin_pct:.0f}%)"),
        (n1_limit_pct, "red", f"N-1 Limit ({n1_limit_pct:.0f}%)"),
    ]:
        fig.add_vline(
            x=pct,
            line_dash="dash",
            line_color=color,
            annotation_text=label,
            row=1,
            col=1,
        )

    # Top-N bar chart with color coding
    bar_colors = [
        "red" if v > n1_limit_pct else "orange" if v > security_margin_pct else "green"
        for v in top_values
    ]
    fig.add_trace(
        go.Bar(
            y=top_names,
            x=top_values,
            orientation="h",
            marker_color=bar_colors,
            name="Max Loading %",
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Line Loading Analysis",
        showlegend=False,
        height=500,
    )
    fig.update_xaxes(title_text="Max Loading (%)", row=1, col=1)
    fig.update_xaxes(title_text="Max Loading (%)", row=1, col=2)

    return json.loads(fig.to_json())


def line_loading_timeseries(
    file_paths: list[str],
    *,
    line_names: list[str] | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Time series of line loading for selected or top-N lines."""
    service = load_service(file_paths, use_cache=True)
    n = service.n

    if not len(n.lines) or n.lines_t.p0.empty:
        return _empty_figure("No line loading data available")

    s_nom = n.lines.s_nom
    s_nom_safe = s_nom.replace(0, np.nan)
    loading_pct = n.lines_t.p0.abs().div(s_nom_safe) * 100

    # Select lines to plot
    if line_names:
        selected = [ln for ln in line_names if ln in loading_pct.columns]
    else:
        max_loading = loading_pct.max()
        selected = max_loading.nlargest(top_n).index.tolist()

    if not selected:
        return _empty_figure("No matching lines found")

    fig = go.Figure()
    for line_name in selected:
        fig.add_trace(
            go.Scatter(
                x=loading_pct.index.astype(str),
                y=loading_pct[line_name].values,
                name=line_name,
                mode="lines",
            )
        )

    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="red",
        annotation_text="N-1 Limit",
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Line Loading Time Series",
        xaxis_title="Time",
        yaxis_title="Loading (%)",
        hovermode="x unified",
    )

    return json.loads(fig.to_json())


# ── Price Analysis ───────────────────────────────────────────────────────────


def price_duration_curve(
    file_paths: list[str],
    *,
    country: str | None = None,
    bus_names: list[str] | None = None,
) -> dict[str, Any]:
    """Price duration curve — sorted marginal prices from high to low.

    Shows the full-year price profile in a single view, essential for
    understanding price volatility and baseload/peak economics.
    """
    service = load_service(file_paths, use_cache=True)
    n = service.n

    if not hasattr(n, "buses_t") or n.buses_t.marginal_price.empty:
        return _empty_figure("No marginal price data available")

    prices = n.buses_t.marginal_price

    if bus_names:
        cols = [b for b in bus_names if b in prices.columns]
        if not cols:
            return _empty_figure("No matching buses found")
        prices = prices[cols]
    elif country:
        country_buses = n.buses.index[n.buses.get("country", "") == country]
        matching = prices.columns.intersection(country_buses)
        if matching.empty:
            return _empty_figure(f"No buses found for country {country}")
        prices = prices[matching]

    fig = go.Figure()

    max_individual_curves = 10
    if prices.shape[1] <= max_individual_curves:
        # Plot individual bus duration curves
        for col in prices.columns:
            sorted_vals = np.sort(prices[col].dropna().values)[::-1]
            hours = np.arange(1, len(sorted_vals) + 1)
            fig.add_trace(go.Scatter(x=hours, y=sorted_vals, name=col, mode="lines"))
    else:
        # Aggregate: mean price across all selected buses
        mean_prices = prices.mean(axis=1)
        sorted_vals = np.sort(mean_prices.dropna().values)[::-1]
        hours = np.arange(1, len(sorted_vals) + 1)
        label = country or "Average"
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=sorted_vals,
                name=label,
                mode="lines",
                line={"color": COUNTRY_COLORS.get(country, "#2563eb")},
            )
        )

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Price Duration Curve" + (f" — {country}" if country else ""),
        xaxis_title="Hours (sorted)",
        yaxis_title="Marginal Price (EUR/MWh)",
        hovermode="x unified",
    )

    return json.loads(fig.to_json())


def price_timeseries(
    file_paths: list[str],
    *,
    country: str | None = None,
    resample: str | None = None,
) -> dict[str, Any]:
    """Price time series — marginal prices over time."""
    service = load_service(file_paths, use_cache=True)
    n = service.n

    if not hasattr(n, "buses_t") or n.buses_t.marginal_price.empty:
        return _empty_figure("No marginal price data available")

    prices = n.buses_t.marginal_price

    if country:
        country_buses = n.buses.index[n.buses.get("country", "") == country]
        matching = prices.columns.intersection(country_buses)
        if matching.empty:
            return _empty_figure(f"No buses found for country {country}")
        prices = prices[matching].mean(axis=1).to_frame(name=country)
    else:
        prices = prices.mean(axis=1).to_frame(name="Average")

    if resample and len(prices) > 1:
        prices = prices.resample(resample).mean()

    fig = go.Figure()
    for col in prices.columns:
        color = COUNTRY_COLORS.get(col, "#2563eb")
        fig.add_trace(
            go.Scatter(
                x=prices.index.astype(str),
                y=prices[col].values,
                name=col,
                mode="lines",
                line={"color": color},
            )
        )

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Marginal Prices" + (f" — {country}" if country else ""),
        xaxis_title="Time",
        yaxis_title="Price (EUR/MWh)",
        hovermode="x unified",
    )

    return json.loads(fig.to_json())


# ── Cross-Border Flows ───────────────────────────────────────────────────────


def cross_border_flows(
    file_paths: list[str],
    *,
    country: str = "NL",
    resample: str | None = "D",
) -> dict[str, Any]:
    """Cross-border flow analysis for a given country.

    Shows net imports/exports per interconnection over time.
    """
    service = load_service(file_paths, use_cache=True)
    n = service.n

    if n.links_t.p0.empty and n.lines_t.p0.empty:
        return _empty_figure("No flow data available")

    country_buses = set(n.buses.index[n.buses.get("country", "") == country])
    if not country_buses:
        return _empty_figure(f"No buses found for country {country}")

    flows = {}

    # Check links (HVDC interconnectors)
    for link_name in n.links.index:
        bus0 = n.links.at[link_name, "bus0"]
        bus1 = n.links.at[link_name, "bus1"]
        bus0_country = n.buses.get("country", "").get(bus0, "")
        bus1_country = n.buses.get("country", "").get(bus1, "")

        if bus0 in country_buses and bus1 not in country_buses:
            # Export from country
            label = f"{country} → {bus1_country}"
            if link_name in n.links_t.p0.columns:
                flows.setdefault(label, []).append(n.links_t.p0[link_name])
        elif bus1 in country_buses and bus0 not in country_buses:
            # Import to country
            label = f"{bus0_country} → {country}"
            if link_name in n.links_t.p0.columns:
                flows.setdefault(label, []).append(-n.links_t.p0[link_name])

    if not flows:
        return _empty_figure(f"No cross-border links found for {country}")

    fig = go.Figure()
    for label, series_list in flows.items():
        combined = pd.concat(series_list, axis=1).sum(axis=1)
        if resample and len(combined) > 1:
            combined = combined.resample(resample).mean()

        # Color by partner country
        partner = label.replace(f"{country} → ", "").replace(f" → {country}", "")
        color = COUNTRY_COLORS.get(partner, "#888888")

        fig.add_trace(
            go.Scatter(
                x=combined.index.astype(str),
                y=combined.values,
                name=label,
                mode="lines",
                line={"color": color},
            )
        )

    fig.add_hline(y=0, line_dash="dot", line_color="grey")
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Cross-Border Flows — {country}",
        xaxis_title="Time",
        yaxis_title="Flow (MW, positive = export)",
        hovermode="x unified",
    )

    return json.loads(fig.to_json())


# ── Capacity Mix ─────────────────────────────────────────────────────────────


def capacity_mix(
    file_paths: list[str],
    *,
    country: str | None = None,
) -> dict[str, Any]:
    """Installed capacity bar chart by carrier."""
    service = load_service(file_paths, use_cache=True)
    n = service.n

    gens = n.generators.copy()
    if country:
        country_buses = n.buses.index[n.buses.get("country", "") == country]
        gens = gens[gens.bus.isin(country_buses)]

    if gens.empty:
        return _empty_figure("No generator data available")

    capacity = gens.groupby("carrier")["p_nom"].sum()
    ordered = sort_carriers_by_dispatch_order(list(capacity.index))
    capacity = capacity.reindex(ordered)
    colors = [get_carrier_color(c) for c in ordered]

    fig = go.Figure(
        go.Bar(
            x=ordered,
            y=capacity.values,
            marker_color=colors,
        )
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Installed Capacity" + (f" — {country}" if country else ""),
        xaxis_title="Carrier",
        yaxis_title="Capacity (MW)",
    )

    return json.loads(fig.to_json())


# ── Helpers ──────────────────────────────────────────────────────────────────


def _empty_figure(message: str) -> dict[str, Any]:
    """Return an empty Plotly figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 16, "color": "grey"},
    )
    fig.update_layout(template=PLOTLY_TEMPLATE)
    return json.loads(fig.to_json())


# ── Public dispatch table ────────────────────────────────────────────────────

ANALYSIS_TYPES: dict[str, callable] = {
    "dispatch_area": dispatch_area,
    "line_loading_histogram": line_loading_histogram,
    "line_loading_timeseries": line_loading_timeseries,
    "price_duration_curve": price_duration_curve,
    "price_timeseries": price_timeseries,
    "cross_border_flows": cross_border_flows,
    "capacity_mix": capacity_mix,
}


def run_analysis(
    file_paths: list[str],
    analysis_type: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Run a named analysis pipeline and return Plotly figure JSON."""
    if analysis_type not in ANALYSIS_TYPES:
        msg = (
            f"Unknown analysis type '{analysis_type}'. "
            f"Available: {sorted(ANALYSIS_TYPES)}"
        )
        raise ValueError(msg)

    func = ANALYSIS_TYPES[analysis_type]
    logger.debug(
        "Running analysis",
        extra={
            "analysis_type": analysis_type,
            "num_networks": len(file_paths),
            "parameters": parameters,
        },
    )
    return func(file_paths, **parameters)
