"""Serialization utilities for converting data structures to JSON"""

import math
from typing import Any

import numpy as np
import pandas as pd

# Use orjson for faster JSON serialization when available
try:
    import orjson

    def fast_json_dumps(obj: Any) -> str:
        """Serialize to JSON string using orjson (3-10x faster than stdlib)."""
        return orjson.dumps(
            obj, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS
        ).decode()

    def fast_json_loads(data: str | bytes) -> Any:
        """Deserialize JSON using orjson."""
        return orjson.loads(data)

    ORJSON_AVAILABLE = True
except ImportError:
    import json

    fast_json_dumps = json.dumps  # type: ignore[assignment]
    fast_json_loads = json.loads  # type: ignore[assignment]
    ORJSON_AVAILABLE = False


def serialize_df(data: pd.DataFrame | pd.Series) -> dict:
    """Convert pandas DataFrame or Series to JSON-serializable dict"""
    if isinstance(data, pd.DataFrame):
        result = data.to_dict(orient="split")
        # Convert tuple indices/columns to strings
        if result.get("index") and isinstance(
            result["index"][0] if result["index"] else None, tuple
        ):
            result["index"] = [str(idx) for idx in result["index"]]
        if result.get("columns") and isinstance(
            result["columns"][0] if result["columns"] else None, tuple
        ):
            result["columns"] = [str(col) for col in result["columns"]]
        # Replace NaN/Inf in data values for JSON compatibility
        if result.get("data"):
            result["data"] = _sanitize_nested_floats(result["data"])
        return result
    elif isinstance(data, pd.Series):
        return {str(k): _sanitize_float(v) for k, v in data.to_dict().items()}
    else:
        msg = f"Expected DataFrame or Series, got {type(data)}"
        raise TypeError(msg)


def _sanitize_float(v: Any) -> Any:
    """Sanitize a single float value."""
    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
        return None
    if isinstance(v, np.floating):
        v = float(v)
        if math.isinf(v) or math.isnan(v):
            return None
    return v


def _sanitize_nested_floats(data: Any) -> Any:
    """Recursively sanitize float values in nested lists (for DataFrame data)."""
    if isinstance(data, list):
        return [_sanitize_nested_floats(item) for item in data]
    return _sanitize_float(data)


def sanitize_metadata(data: Any) -> Any:
    """Recursively sanitize metadata to be JSON-compatible (removes inf/nan)"""
    if isinstance(data, dict):
        return {k: sanitize_metadata(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_metadata(item) for item in data]
    elif isinstance(data, float) and (math.isinf(data) or math.isnan(data)):
        return None
    return data
