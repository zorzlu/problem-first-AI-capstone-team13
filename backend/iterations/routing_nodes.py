"""Candidate routing nodes for iteration workflows."""
from typing import Any, Dict

from backend.iterations.contracts import WorkflowState
from backend.graph.graph import route_cross_impact

def route_events(state: WorkflowState, cross_impact: bool) -> Dict[str, Any]:
    """Route canonical events to watchlist tickers.

    Direct routing (source pre-tagged with a watchlist ticker) always runs.
    ``cross_impact=True`` (iteration 3) additionally routes untickered events through the
    exposure graph.
    """
    print(f"--- [Node 3: Candidate Routing] (cross_impact={cross_impact}) ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    watchlist = state.get("watchlist", [])
    canonical_events = state.get("canonical_events", [])
    
    if span and span.is_recording():
        span.set_attribute("events_count", len(canonical_events))
        
    routed_candidates = []
    
    for event in canonical_events:
        # A. Direct Routing (Applies to all iterations)
        # Check if the source article was pre-tagged with a watchlist ticker, or if the
        # extraction model mapped an explicit article mention to a watched public ticker.
        source_tickers = {t.upper() for t in event.get("relatedTickers", [])}
        mentioned_tickers = {t.upper() for t in event.get("mentionedTickers", [])}
        for ticker in watchlist:
            ticker_upper = ticker.upper()
            if ticker_upper in source_tickers or ticker_upper in mentioned_tickers:
                reason = (
                    f"Directly tagged in news source for ticker {ticker}."
                    if ticker_upper in source_tickers
                    else f"Article text explicitly mentions or maps to watched ticker {ticker}."
                )
                candidate = {
                    "candidateId": f"cand_{ticker}_{event['eventId'][:8]}",
                    "ticker": ticker,
                    "relationshipType": "direct",
                    "eventId": event["eventId"],
                    "impactPath": [ticker],
                    "pathConfidence": 1.0,
                    "reasonForRouting": reason
                }
                routed_candidates.append(candidate)
                print(f"Direct Route: {event['eventSummary']} -> {ticker}")
                
                if span and span.is_recording():
                    span.add_event("event_routing", {
                        "event_id": event["eventId"],
                        "ticker": ticker,
                        "relationship_type": "direct",
                        "path_confidence": 1.0,
                        "impact_path": [ticker]
                    })
                    
        # B. Cross-Impact Graph Routing (only when cross_impact=True / iteration 3)
        if cross_impact:
            indirect_candidates = route_cross_impact(event, watchlist)
            for ic in indirect_candidates:
                # Avoid duplicates with direct routing
                is_dup = any(c["ticker"] == ic["ticker"] and c["eventId"] == ic["eventId"] for c in routed_candidates)
                if not is_dup:
                    routed_candidates.append(ic)
                    print(f"Cross-Impact Route: {event['eventSummary']} -> {ic['ticker']} via {ic['impactPath']} (Conf: {ic['pathConfidence']})")
                    
                    if span and span.is_recording():
                        span.add_event("event_routing", {
                            "event_id": ic["eventId"],
                            "ticker": ic["ticker"],
                            "relationship_type": "indirect",
                            "path_confidence": ic["pathConfidence"],
                            "impact_path": ic["impactPath"]
                        })
                        
    if span and span.is_recording():
        span.set_attribute("routed_candidates_count", len(routed_candidates))
        
    return {"routed_candidates": routed_candidates}
