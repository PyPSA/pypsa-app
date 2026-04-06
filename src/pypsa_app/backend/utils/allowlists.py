"""Security allowlists for PyPSA API inputs to prevent arbitrary code execution"""

from typing import Final

ALLOWED_STATISTICS: Final[frozenset[str]] = frozenset(
    {
        "capex",
        "installed_capex",
        "expanded_capex",
        "opex",
        "system_cost",
        "revenue",
        "market_value",
        "installed_capacity",
        "expanded_capacity",
        "optimal_capacity",
        "supply",
        "withdrawal",
        "curtailment",
        "capacity_factor",
        "transmission",
        "energy_balance",
        "prices",
    }
)

ALLOWED_CHART_TYPES: Final[frozenset[str]] = frozenset(
    {
        "area",
        "bar",
        "map",
        "scatter",
        "line",
        "box",
        "violin",
        "histogram",
    }
)

ALLOWED_ANALYSIS_TYPES: Final[frozenset[str]] = frozenset(
    {
        "dispatch_area",
        "line_loading_histogram",
        "line_loading_timeseries",
        "price_duration_curve",
        "price_timeseries",
        "cross_border_flows",
        "capacity_mix",
    }
)

__all__ = ["ALLOWED_STATISTICS", "ALLOWED_CHART_TYPES", "ALLOWED_ANALYSIS_TYPES"]
