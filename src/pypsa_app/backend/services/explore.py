"""Interactive explore map generation via n.plot.explore()"""

import json
import logging
from typing import Any

from pypsa_app.backend.services.network import NetworkService

logger = logging.getLogger(__name__)


def fix_carrier_colors(network: Any) -> None:
    """Replace matplotlib single-char color shorthands that Plotly.js doesn't accept."""
    if hasattr(network, "carriers") and "color" in network.carriers.columns:
        network.carriers["color"] = network.carriers["color"].replace(
            {
                "b": "blue",
                "g": "green",
                "r": "red",
                "c": "cyan",
                "m": "magenta",
                "y": "yellow",
                "k": "black",
                "w": "white",
            }
        )


def _build_explore_defaults(n: Any) -> dict[str, Any]:
    """Build rich explore() defaults when optimization results are available."""
    defaults: dict[str, Any] = {"auto_scale": True}

    has_results = any(
        len(n.c[c].dynamic.get("p0", [])) > 0 for c in n.branch_components
    )
    if not has_results:
        return defaults

    try:
        eb = (
            n.statistics.energy_balance(
                groupby=["bus", "carrier"],
                components=["Generator", "Load", "StorageUnit"],
                nice_names=False,
            )
            .groupby(["bus", "carrier"])
            .sum()
        )
        if len(eb) > 0:
            defaults["bus_size"] = eb
            defaults["bus_split_circle"] = True
            defaults["bus_size_max"] = 7000
    except Exception:
        logger.warning(
            "Could not compute energy balance for explore defaults",
            exc_info=True,
        )

    try:
        # TODO: re-add "Process" once PyPSA PydeckPlotter supports process_* kwargs
        supported_branches = {"Line", "Link", "Transformer"}
        for c in n.branch_components:
            if c not in supported_branches:
                continue
            p0 = n.c[c].dynamic.get("p0")
            if p0 is not None and len(p0) > 0:
                flow = p0.sum(axis=0)
                key = c.lower()
                defaults[f"{key}_width"] = flow
                defaults[f"{key}_flow"] = flow
        if any(k.endswith("_flow") for k in defaults):
            defaults["branch_width_max"] = 16
            defaults["arrow_size_factor"] = 2
    except Exception:
        logger.warning(
            "Could not compute branch flows for explore defaults",
            exc_info=True,
        )

    return defaults


def get_explore(
    file_paths: list[str],
    parameters: dict | None = None,
) -> dict:
    """Generate interactive map from a single network using n.plot.explore()."""
    n = NetworkService(file_paths[0], use_cache=True).n
    n.c.carriers.add_missing_carriers()
    n.c.carriers.assign_colors()
    fix_carrier_colors(n)

    explore_kwargs = _build_explore_defaults(n)
    explore_kwargs.update(parameters or {})

    deck = n.plot.explore(**explore_kwargs)
    return json.loads(deck.to_json())
