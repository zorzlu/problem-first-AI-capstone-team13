"""Mutable application state and startup hydration.

The demo runs as a single FastAPI process, so a lightweight in-memory state object is
enough. Keeping it here prevents route modules from reaching into ``main.py`` globals.
"""
from typing import Any, Dict, List

from backend.core.config import init_phoenix
from backend.graph.graph import get_graph, set_graph
from backend.storage.persistence import (
    load_graph,
    load_run_results,
    load_watchlist,
    save_graph,
)


DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSM", "DAL"]


class AppState:
    def __init__(self) -> None:
        self.watchlist: List[str] = list(DEFAULT_WATCHLIST)
        self.run_results: Dict[int, Dict[str, Any]] = {}


app_state = AppState()


def hydrate_app_state() -> None:
    """Load persisted state used by request handlers."""
    init_phoenix()
    app_state.watchlist = load_watchlist(default=app_state.watchlist)
    set_graph(load_graph(default=get_graph()))
    save_graph(get_graph())

    # JSON object keys are strings; the API historically exposes integer iteration
    # keys, so normalize them at startup.
    app_state.run_results = {}
    for key, value in load_run_results().items():
        try:
            app_state.run_results[int(key)] = value
        except Exception:
            pass
