"""Operator remediation overrides for cross-impact routing.

Closes the feedback loop on routing quality: when the offline routing evals (or a human
reviewing live briefings) flag a false-butterfly route, an operator records an override here
instead of waiting for a code change. Overrides persist in ``backend/state/routing_overrides.json``
next to the exposure graph and are applied deterministically inside ``route_cross_impact``.

Override file shape::

    {
      "suppressedRoutes": [
        {"ticker": "MCD", "anchorName": "United States", "reason": "...", "addedAt": "..."}
      ],
      "extraBroadGeoNodes": ["region_Latin_America"],
      "notBroadGeoNodes": []
    }

- ``suppressedRoutes`` — never route ``ticker`` from a path anchored at ``anchorName``
  (matched case-insensitively against the first node of the impact path).
- ``extraBroadGeoNodes`` / ``notBroadGeoNodes`` — node ids to force in/out of the
  broad-geography anchor demotion in ``backend.graph.graph``.
"""
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List

_STATE_DIR = str(Path(__file__).resolve().parents[1] / "state")
_OVERRIDES_FILE = os.path.join(_STATE_DIR, "routing_overrides.json")

_DEFAULT_OVERRIDES: Dict[str, Any] = {
    "suppressedRoutes": [],
    "extraBroadGeoNodes": [],
    "notBroadGeoNodes": [],
}

_lock = RLock()
_cache: Dict[str, Any] = {}
_cache_mtime: float = -1.0


def _load_from_disk() -> Dict[str, Any]:
    try:
        with open(_OVERRIDES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(_DEFAULT_OVERRIDES)
    merged = copy.deepcopy(_DEFAULT_OVERRIDES)
    if isinstance(data, dict):
        for key in merged:
            if isinstance(data.get(key), list):
                merged[key] = data[key]
    return merged


def get_overrides() -> Dict[str, Any]:
    """Returns current overrides, reloading from disk only when the file changed."""
    global _cache, _cache_mtime
    with _lock:
        try:
            mtime = os.path.getmtime(_OVERRIDES_FILE)
        except OSError:
            mtime = -1.0
        if not _cache or mtime != _cache_mtime:
            _cache = _load_from_disk()
            _cache_mtime = mtime
        return copy.deepcopy(_cache)


def save_overrides(overrides: Dict[str, Any]) -> Dict[str, Any]:
    global _cache, _cache_mtime
    merged = copy.deepcopy(_DEFAULT_OVERRIDES)
    for key in merged:
        if isinstance(overrides.get(key), list):
            merged[key] = overrides[key]
    with _lock:
        os.makedirs(_STATE_DIR, exist_ok=True)
        with open(_OVERRIDES_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        _cache = copy.deepcopy(merged)
        try:
            _cache_mtime = os.path.getmtime(_OVERRIDES_FILE)
        except OSError:
            _cache_mtime = -1.0
    return merged


def add_suppressed_route(ticker: str, anchor_name: str, reason: str = "") -> Dict[str, Any]:
    """Records that ``ticker`` must never be routed from paths anchored at ``anchor_name``."""
    ticker = str(ticker).strip().upper()
    anchor_name = str(anchor_name).strip()
    if not ticker or not anchor_name:
        raise ValueError("ticker and anchor_name are required")
    with _lock:
        overrides = get_overrides()
        for entry in overrides["suppressedRoutes"]:
            if entry["ticker"].upper() == ticker and entry["anchorName"].lower() == anchor_name.lower():
                return overrides
        overrides["suppressedRoutes"].append({
            "ticker": ticker,
            "anchorName": anchor_name,
            "reason": reason,
            "addedAt": datetime.now(timezone.utc).isoformat(),
        })
        return save_overrides(overrides)


def is_route_suppressed(ticker: str, impact_path: List[str]) -> bool:
    if not impact_path:
        return False
    anchor = str(impact_path[0]).strip().lower()
    ticker = str(ticker).strip().upper()
    for entry in get_overrides().get("suppressedRoutes", []):
        if str(entry.get("ticker", "")).strip().upper() != ticker:
            continue
        if str(entry.get("anchorName", "")).strip().lower() == anchor:
            return True
    return False
