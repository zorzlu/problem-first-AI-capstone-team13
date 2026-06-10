"""Fetch/filter node shared by iteration workflows."""
from typing import Any, Dict

from backend.core.config import FRESHNESS_LOOKBACK_MINUTES
from backend.core.logging import get_logger
from backend.ingestion import get_news_payload
from backend.iterations.contracts import WorkflowState
from backend.graph.graph import get_cross_impact_queries

logger = get_logger(__name__)


def run_fetch_and_filter(state: WorkflowState, expand: bool) -> Dict[str, Any]:
    """Fetch news and apply the freshness window.

    ``expand=True`` widens the search using exposure-graph-derived cross-impact
    keywords and peer tickers; otherwise only the watchlist is queried.
    """
    logger.info("--- [Node 1: Fetching & Filtering News] (expand=%s) ---", expand)
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    watchlist = state.get("watchlist", [])
    scenario_id = state.get("scenario_id", "live")
    simulated_now = state.get("simulated_now", "2026-05-28T17:25:00Z")

    if span and span.is_recording():
        span.set_attribute("watchlist", watchlist)
        span.set_attribute("scenario_id", scenario_id)

    cross_impact_keywords = []
    extra_tickers = []
    if expand:
        cross_impact_keywords, extra_tickers = get_cross_impact_queries(watchlist)
        logger.info("Expanded search terms from exposure graph: %s", cross_impact_keywords)
        logger.info("Expanded peer tickers from exposure graph: %s", extra_tickers)

    payload = get_news_payload(
        symbol_watchlist=watchlist,
        cross_impact_keywords=cross_impact_keywords,
        scenario_id=scenario_id,
        simulated_now_str=simulated_now,
        extra_tickers=extra_tickers,
    )

    total_ingested = payload.get("total_ingested", 0)
    passed_freshness = payload.get("passed_freshness", 0)

    if span and span.is_recording():
        span.set_attribute("total_ingested", total_ingested)
        span.set_attribute("passed_freshness", passed_freshness)
        span.add_event("news_fetched", {
            "total_fetched_articles": total_ingested,
            "symbols_queried": watchlist + (extra_tickers or []),
        })
        span.add_event("freshness_filtering", {
            "passed_freshness": passed_freshness,
            "lookback_minutes": FRESHNESS_LOOKBACK_MINUTES,
        })

    return {
        "articles": payload["articles"],
        "ingestion_metadata": {
            "total_ingested": total_ingested,
            "passed_freshness": passed_freshness,
        },
        "expansion_keywords": cross_impact_keywords,
        "expansion_tickers": extra_tickers,
    }
