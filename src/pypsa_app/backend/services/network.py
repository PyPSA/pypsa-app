from __future__ import annotations

import hashlib
import logging
import math
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pypsa

from pypsa_app.backend.models import Network, Permission, User
from pypsa_app.backend.permissions import has_permission
from pypsa_app.backend.settings import settings
from pypsa_app.backend.utils.path_validation import validate_path
from pypsa_app.backend.utils.serializers import sanitize_metadata

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NetworkCache:
    """Thread-safe LRU cache for loaded PyPSA networks with TTL"""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 10) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.cache = OrderedDict()
        self.hits = self.misses = 0
        self._lock = threading.Lock()

    def get(self, file_path: Path) -> pypsa.Network | None:
        """Get network from cache if not expired (thread-safe)"""
        key = str(file_path)

        with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None

            network, timestamp = self.cache[key]
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None

            self.cache.move_to_end(key)
            self.hits += 1
            return network

    def put(self, file_path: Path, network: pypsa.Network) -> None:
        """Add network to cache with LRU eviction (thread-safe)"""
        key = str(file_path)

        with self._lock:
            # Evict oldest if at capacity
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                logger.debug(
                    "Evicted oldest network from cache (LRU)",
                    extra={
                        "evicted_network": oldest,
                        "cache_size": len(self.cache),
                        "max_size": self.max_size,
                    },
                )

            self.cache[key] = (network, time.time())
            self.cache.move_to_end(key)
            logger.debug(
                "Cached network",
                extra={
                    "file_path": str(file_path),
                    "cache_size": len(self.cache),
                },
            )

    def clear(self) -> None:
        """Clear all cached networks (thread-safe)"""
        with self._lock:
            cached_count = len(self.cache)
            self.cache.clear()
            self.hits = self.misses = 0
            logger.info(
                "Network cache cleared",
                extra={
                    "cleared_count": cached_count,
                    "cache_type": "in_memory",
                },
            )

    def stats(self) -> dict:
        """Get cache statistics (thread-safe)"""
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_percent": round((self.hits / total * 100) if total else 0, 2),
                "cached_networks": [
                    {"file_path": k, "cached_at": time.ctime(t)}
                    for k, (_, t) in self.cache.items()
                ],
            }


_network_cache = NetworkCache(ttl_seconds=settings.network_cache_ttl)


class NetworkService:
    """Service for PyPSA network operations (handles single networks)"""

    def __init__(
        self, network: pypsa.Network | Path | str, use_cache: bool = True
    ) -> None:
        """Initialize service with a network object or file path"""
        if isinstance(network, (Path, str)):
            self.file_path = validate_path(Path(network), must_exist=True)

            # Try to get from cache first
            if use_cache and (cached_network := _network_cache.get(self.file_path)):
                self.n = cached_network
            else:
                self.n = pypsa.Network(self.file_path)
                logger.debug(
                    "Successfully loaded network from file",
                    extra={
                        "file_path": str(self.file_path),
                        "use_cache": use_cache,
                    },
                )

                if use_cache:
                    _network_cache.put(self.file_path, self.n)
        elif isinstance(network, pypsa.Network):
            self.n = network
            self.file_path = None
        else:
            msg = "Invalid network type"
            raise TypeError(msg)

    def extract_database_info(self) -> dict:
        """Extract network metadata for database storage.

        Mirrors Network model field order.
        """
        info = {}

        info["name"] = self.n.name

        info["dimensions_count"] = {
            "timesteps": len(self.n.snapshots),
            "periods": len(self.n.investment_periods),
            "scenarios": len(self.n.scenarios),
        }

        info["components_count"] = {
            c.name: int(len(c))
            for c in self.n.components
            if not c.name.endswith("Type")
        }

        info["meta"] = (
            sanitize_metadata(dict(self.n.meta))
            if hasattr(self.n, "meta") and self.n.meta
            else {}
        )

        facets = {}
        if carriers := self._extract_carriers(self.n):
            facets["carriers"] = carriers
        if countries := self._extract_countries(self.n):
            facets["countries"] = countries
        info["facets"] = facets or None

        return info

    @staticmethod
    def _extract_carriers(network: pypsa.Network) -> dict[str, dict]:
        """Extract bus carrier information from the network"""
        carriers = {}
        for carrier_name in network.buses.carrier.unique():
            carrier_info = {}
            if carrier_name in network.carriers.index:
                carrier_info = {
                    k: v
                    for k, v in network.carriers.loc[carrier_name].to_dict().items()
                    if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
                }
            carriers[carrier_name] = carrier_info

        return carriers

    @staticmethod
    def _extract_countries(network: pypsa.Network) -> list[str]:
        """Extract unique countries from the network buses"""
        if not len(network.buses) or "country" not in network.buses.columns:
            return []

        countries = network.buses["country"].dropna().unique()
        return sorted(countries)

    def calculate_file_hash(self) -> str:
        """Calculate SHA256 hash of the network file"""
        if self.file_path is None:
            msg = "Cannot calculate hash for network without file_path"
            raise ValueError(msg)

        sha256_hash = hashlib.sha256()
        with self.file_path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_file_size(self) -> int:
        """Get file size in bytes"""
        if self.file_path is None:
            msg = "Cannot get file size for network without file_path"
            raise ValueError(msg)
        return self.file_path.stat().st_size


class NetworkCollectionService:
    """Service for PyPSA network collection operations (handles multiple networks)"""

    def __init__(
        self, file_paths: list[Path] | list[str], use_cache: bool = True
    ) -> None:
        """Initialize service by loading networks and creating a collection"""
        file_paths = [Path(p) for p in file_paths]
        names = self._generate_unique_names_from_paths(file_paths)

        networks = {}
        for file_path, name in zip(file_paths, names, strict=True):
            validated = validate_path(file_path, must_exist=True)

            # Try cache first
            if use_cache and (cached := _network_cache.get(validated)):
                networks[name] = cached
            else:
                # Load network directly
                network = pypsa.Network(validated)
                if use_cache:
                    _network_cache.put(validated, network)
                networks[name] = network

        self.n = pypsa.NetworkCollection(
            list(networks.values()), index=list(networks.keys())
        )

    def get_summary(self) -> dict:
        """Get summary information about the collection"""
        info = {}
        info["collection_size"] = len(self.n.networks)
        info["network_indices"] = list(self.n.index)

        return info

    @staticmethod
    def _generate_unique_names_from_paths(file_paths: list[Path]) -> list[str]:
        """Generate unique names for networks based on file paths"""
        names = []
        for path in file_paths:
            # Use filename without extension as name
            name = path.stem
            # Handle duplicates by appending parent directory
            if name in names:
                name = f"{path.parent.name}_{name}"
            names.append(name)
        return names


def _calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def import_network_file(
    file_path: Path,
    original_filename: str,
    user_id: uuid.UUID,
    db: Session,
    source_run_id: uuid.UUID | None = None,
) -> Network:
    """Import a network file.

    Hash, move to storage, extract metadata and create DB record.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not has_permission(user, Permission.NETWORKS_MODIFY):
        msg = "User does not have permission to import networks"
        raise PermissionError(msg)

    file_hash = _calculate_file_hash(file_path)

    # Check for duplicate file content
    existing = (
        db.query(Network)
        .filter(Network.user_id == user_id, Network.file_hash == file_hash)
        .first()
    )
    if existing:
        file_path.unlink(missing_ok=True)
        return existing

    # Generate ID upfront so file is stored as {user_id}/{network_id}.nc
    network_id = uuid.uuid4()
    user_dir = settings.networks_path / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{network_id}.nc"

    shutil.move(str(file_path), str(dest))

    # Reload from final path and extract metadata
    service = NetworkService(dest, use_cache=False)
    info = service.extract_database_info()

    network = Network(
        id=network_id,
        user_id=user_id,
        source_run_id=source_run_id,
        filename=original_filename,
        file_path=str(dest),
        file_hash=file_hash,
        file_size=service.get_file_size(),
        name=info["name"],
        dimensions_count=info["dimensions_count"],
        components_count=info["components_count"],
        meta=info["meta"],
        facets=info["facets"],
        update_history=[datetime.now(UTC).isoformat()],
    )
    db.add(network)
    db.flush()
    return network


def load_service(
    file_paths: list[str] | list[Path], use_cache: bool = True
) -> NetworkService | NetworkCollectionService:
    """Load one or more networks, returning appropriate service.

    Args:
        file_paths: Single file path or list of file paths
        use_cache: Whether to use the network cache

    Returns:
        NetworkService if single file, NetworkCollectionService if multiple files

    """
    if len(file_paths) == 1:
        return NetworkService(file_paths[0], use_cache=use_cache)
    else:
        return NetworkCollectionService(file_paths, use_cache=use_cache)
