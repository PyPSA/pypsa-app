"""Functions for generating PyPSA statistics and plots"""

import json
import logging

from pypsa_app.backend.services.explore import fix_carrier_colors
from pypsa_app.backend.services.network import (
    NetworkCollectionService,
    load_service,
)
from pypsa_app.backend.utils.serializers import serialize_df

logger = logging.getLogger(__name__)


def get_statistics(file_paths: list[str], statistic: str, parameters: dict) -> dict:
    """Get statistics from network files (handles single or multiple networks)."""
    service = load_service(file_paths, use_cache=True)
    stats_data = getattr(service.n.statistics, statistic)(**parameters)

    logger.debug(
        "Retrieved statistics",
        extra={
            "statistic": statistic,
            "parameters": parameters,
            "num_networks": len(file_paths),
        },
    )

    return serialize_df(stats_data)


def get_plot(
    file_paths: list[str], statistic: str, plot_type: str, parameters: dict
) -> dict:
    """Generate plot from network files (handles single or multiple networks)"""
    service = load_service(file_paths, use_cache=True)

    # Sanitize carriers and fix matplotlib color shorthands
    if isinstance(service, NetworkCollectionService):
        for network in service.n.networks:
            network.c.carriers.add_missing_carriers()
            network.c.carriers.assign_colors()
            fix_carrier_colors(network)
    else:
        service.n.c.carriers.add_missing_carriers()
        service.n.c.carriers.assign_colors()
        fix_carrier_colors(service.n)
    # TODO-framework should be moved to obj.sanitize

    # Generate plot
    plot_method = getattr(service.n.statistics, statistic).iplot
    fig = getattr(plot_method, plot_type)(**parameters)

    logger.debug(
        "Generated plot",
        extra={
            "statistic": statistic,
            "plot_type": plot_type,
            "num_networks": len(file_paths),
            "parameters": parameters,
        },
    )
    return json.loads(fig.to_json())
