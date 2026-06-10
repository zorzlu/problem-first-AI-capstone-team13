"""
Lightweight JSON file persistence for watchlist and exposure graph state.
Files are stored in backend/state/ and survive backend restarts.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from backend.core.logging import get_logger

logger = get_logger(__name__)

# State directory sits at backend/state/. This module lives in backend/storage/.
_STATE_DIR = str(Path(__file__).resolve().parents[1] / "state")
_WATCHLIST_FILE = os.path.join(_STATE_DIR, "watchlist.json")
_GRAPH_FILE = os.path.join(_STATE_DIR, "graph.json")
_STATE_SCHEMA_VERSION = 1


def _ensure_state_dir():
    os.makedirs(_STATE_DIR, exist_ok=True)


def _wrap_state(kind: str, data: Any) -> Dict[str, Any]:
    return {
        "schemaVersion": _STATE_SCHEMA_VERSION,
        "kind": kind,
        "data": data,
    }


def _unwrap_state(raw: Any, kind: str) -> Any:
    """Read versioned state while accepting legacy unwrapped JSON files."""
    if isinstance(raw, dict) and raw.get("kind") == kind and "data" in raw:
        version = raw.get("schemaVersion", 0)
        if version > _STATE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported {kind} state schemaVersion={version}")
        return raw["data"]
    return raw


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Watchlist persistence
# ---------------------------------------------------------------------------

def load_watchlist(default: List[str]) -> List[str]:
    """Loads the persisted watchlist, or returns the default if none exists."""
    _ensure_state_dir()
    if not os.path.exists(_WATCHLIST_FILE):
        return list(default)
    try:
        with open(_WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = _unwrap_state(json.load(f), "watchlist")
        tickers = data.get("tickers", default)
        logger.info("Loaded watchlist from disk: %s", tickers)
        return tickers
    except Exception as e:
        logger.warning("Failed to load watchlist, using default: %s", e)
        return list(default)


def save_watchlist(tickers: List[str]):
    """Persists the current watchlist to disk."""
    _ensure_state_dir()
    try:
        _write_json(_WATCHLIST_FILE, _wrap_state("watchlist", {"tickers": tickers}))
    except Exception as e:
        logger.error("Failed to save watchlist: %s", e)


# ---------------------------------------------------------------------------
# Exposure graph persistence
# ---------------------------------------------------------------------------

def load_graph(default: Dict[str, Any]) -> Dict[str, Any]:
    """Loads the persisted exposure graph, or returns the seed default if none exists."""
    _ensure_state_dir()
    if not os.path.exists(_GRAPH_FILE):
        return default
    try:
        with open(_GRAPH_FILE, "r", encoding="utf-8") as f:
            data = _unwrap_state(json.load(f), "graph")
        node_count = len(data.get("nodes", []))
        edge_count = len(data.get("edges", []))
        logger.info("Loaded graph from disk: %d nodes, %d edges", node_count, edge_count)
        return data
    except Exception as e:
        logger.warning("Failed to load graph, using seed default: %s", e)
        return default


def save_graph(graph: Dict[str, Any]):
    """Persists the current exposure graph state to disk."""
    _ensure_state_dir()
    try:
        _write_json(_GRAPH_FILE, _wrap_state("graph", graph))
    except Exception as e:
        logger.error("Failed to save graph: %s", e)


# ---------------------------------------------------------------------------
# Per-iteration run results persistence
# ---------------------------------------------------------------------------

_RUN_RESULTS_FILE = os.path.join(_STATE_DIR, "run_results.json")


def load_run_results() -> Dict[str, Any]:
    """Loads the persisted run results dict, or returns empty dict if none exists."""
    _ensure_state_dir()
    if not os.path.exists(_RUN_RESULTS_FILE):
        return {}
    try:
        with open(_RUN_RESULTS_FILE, "r", encoding="utf-8") as f:
            data = _unwrap_state(json.load(f), "run_results")
        logger.info("Loaded latest run results from disk")
        return data
    except Exception as e:
        logger.warning("Failed to load run results: %s", e)
        return {}


def save_run_results(results: Dict[str, Any]):
    """Persists the run results dict to disk."""
    _ensure_state_dir()
    try:
        _write_json(_RUN_RESULTS_FILE, _wrap_state("run_results", results))
    except Exception as e:
        logger.error("Failed to save run results: %s", e)
