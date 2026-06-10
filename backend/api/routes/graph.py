from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.api.schemas import (
    ExpandRequest,
    GraphEdgeRequest,
    GraphNodeRequest,
    RebuildRequest,
    RoutingOverridesRequest,
    SuppressRouteRequest,
)
from backend.graph.expansion import get_expansion_status, mark_pending, process_ticker_expansion
from backend.graph.graph import add_graph_edge, add_graph_node, get_graph, graph_lock, reset_graph
from backend.graph.overrides import add_suppressed_route, get_overrides, save_overrides
from backend.services.app_state import app_state
from backend.storage.persistence import save_graph


router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/status")
def graph_expansion_status():
    """Per-ticker exposure-graph expansion status."""
    return {"status": get_expansion_status()}


@router.post("/expand")
def trigger_graph_expansion(req: ExpandRequest, background_tasks: BackgroundTasks):
    """Manually re-run exposure-graph expansion for a ticker."""
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    mark_pending(ticker)
    background_tasks.add_task(process_ticker_expansion, ticker, req.force)
    return {"status": "scheduled", "ticker": ticker, "expansionStatus": get_expansion_status()}


@router.post("/rebuild")
def rebuild_graph_endpoint(req: RebuildRequest, background_tasks: BackgroundTasks):
    """Rebuild the exposure graph for the entire watchlist in the background."""
    if req.reset:
        with graph_lock():
            reset_graph()
            save_graph(get_graph())
    for ticker in app_state.watchlist:
        mark_pending(ticker)
        background_tasks.add_task(process_ticker_expansion, ticker, True)
    return {
        "status": "scheduled",
        "reset": req.reset,
        "tickers": app_state.watchlist,
        "expansionStatus": get_expansion_status(),
    }


@router.get("")
def get_exposure_graph():
    return get_graph()


@router.post("/node")
def add_node(node: GraphNodeRequest):
    try:
        with graph_lock():
            add_graph_node(node.model_dump(exclude_none=True))
            save_graph(get_graph())
            graph = get_graph()
        return {"status": "success", "graph": graph}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/routing-overrides")
def get_routing_overrides():
    """Operator remediation overrides applied inside cross-impact routing."""
    return get_overrides()


@router.post("/routing-overrides")
def replace_routing_overrides(req: RoutingOverridesRequest):
    try:
        return {"status": "success", "overrides": save_overrides(req.model_dump())}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/routing-overrides/suppress")
def suppress_route(req: SuppressRouteRequest):
    """Remediation feedback loop: flag a false-butterfly route so it is never produced again."""
    try:
        overrides = add_suppressed_route(ticker=req.ticker, anchor_name=req.anchorName, reason=req.reason)
        return {"status": "success", "overrides": overrides}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/edge")
def add_edge(edge: GraphEdgeRequest):
    try:
        with graph_lock():
            add_graph_edge(edge.model_dump())
            save_graph(get_graph())
            graph = get_graph()
        return {"status": "success", "graph": graph}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
