"""Canonical carrier colors and dispatch order for energy system visualizations.

Ported from PSA_MEE analysis.dashboard_utils — single source of truth for all
plot styling in pypsa-app.
"""

from typing import Final

# Technology-specific colors for energy dispatch charts
CARRIER_COLORS: Final[dict[str, str]] = {
    "Nuclear": "#d62728",
    "Gas": "#8c564b",
    "CHP": "#006400",
    "Coal": "#2c2c2c",
    "Lignite": "#654321",
    "Wind": "#1f77b4",
    "Wind_Onshore": "#1f77b4",
    "Wind_Offshore": "#00008b",
    "Solar": "#ffdd44",
    "Hydro": "#87CEEB",
    "Biomass": "#98df8a",
    "Waste": "#bc5090",
    "Oil": "#e377c2",
    "Other": "#aaa5a0",
    "Slack": "#d62728",
    "Battery": "#800080",
    "PHS": "#7f7f7f",
    "DemandResponse": "#bcbd22",
    "Load": "#708090",
    "HVDC_Losses": "#e74c3c",
}

# Dispatch stacking order: baseload at bottom, variable renewables on top
DISPATCH_ORDER: Final[list[str]] = [
    "Nuclear",
    "Hydro",
    "Coal",
    "Lignite",
    "Biomass",
    "Waste",
    "CHP",
    "Gas",
    "Oil",
    "Other",
    "DemandResponse",
    "Battery",
    "PHS",
    "Wind_Offshore",
    "Wind_Onshore",
    "Wind",
    "Solar",
    "Slack",
]

# Country/zone colors for cross-border and price visualizations
COUNTRY_COLORS: Final[dict[str, str]] = {
    "NL": "#FF6B00",
    "DE": "#000000",
    "BE": "#FFD700",
    "FR": "#002395",
    "GB": "#00247D",
    "DK": "#C8102E",
    "NO": "#003DA5",
    "LU": "#00A3E0",
}

PLOTLY_TEMPLATE: Final[str] = "simple_white"


def get_carrier_color(carrier: str) -> str:
    """Get color for a carrier, falling back to grey for unknown carriers."""
    return CARRIER_COLORS.get(carrier, "#aaa5a0")


def sort_carriers_by_dispatch_order(carriers: list[str]) -> list[str]:
    """Sort carriers according to canonical dispatch stacking order."""
    order_map = {name: i for i, name in enumerate(DISPATCH_ORDER)}
    return sorted(carriers, key=lambda c: order_map.get(c, len(DISPATCH_ORDER)))
