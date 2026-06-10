"""Catalyst memory and ledger nodes for iteration workflows."""
from typing import Any, Dict

from backend.core.logging import get_logger
from backend.iterations.contracts import WorkflowState
from backend.memory import check_ledger_decision

logger = get_logger(__name__)

def assign_new_catalysts(state: WorkflowState) -> Dict[str, Any]:
    """Iteration 1 has no catalyst memory: every routed candidate becomes a fresh briefing.

    Assigns catalyst ids / new-fact lists so downstream synthesis & display work, without
    consulting or writing to the ledger store.
    """
    logger.info("--- [Node 4: Catalyst Assignment (Iteration 1, no memory)] ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    routed_candidates = state.get("routed_candidates", [])
    canonical_events = {e["eventId"]: e for e in state.get("canonical_events", [])}

    for cand in routed_candidates:
        ticker = cand["ticker"]
        event_id = cand["eventId"]
        event = canonical_events[event_id]
        cand["ledgerDecision"] = "new"
        cand["newFacts"] = event.get("hardFacts", [])
        cand["catalystId"] = f"cat_{ticker}_{event_id[:8]}"
        if span and span.is_recording():
            span.add_event("ledger_decision", {
                "ticker": ticker,
                "event_id": event_id,
                "decision": "new",
                "catalyst_id": cand["catalystId"],
            })

    return {"routed_candidates": routed_candidates, "duplicate_counts": {}}

def run_ledger_dedup(state: WorkflowState) -> Dict[str, Any]:
    logger.info("--- [Node 4: Ledger Memory Check] ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    routed_candidates = state.get("routed_candidates", [])
    canonical_events = {e["eventId"]: e for e in state.get("canonical_events", [])}

    if span and span.is_recording():
        span.set_attribute("candidates_count", len(routed_candidates))

    filtered_candidates = []
    duplicate_counts = {}

    accepted_count = 0
    duplicate_count = 0
    update_count = 0
    iteration = state.get("iteration", 2)

    for cand in routed_candidates:
        ticker = cand["ticker"]
        event_id = cand["eventId"]
        event = canonical_events[event_id]

        # Catalyst Memory dedup (used by iterations 2 and 3)
        decision, cat_id, new_facts = check_ledger_decision(ticker, event, iteration=iteration)
        cand["ledgerDecision"] = decision
        cand["newFacts"] = new_facts
        cand["catalystId"] = cat_id
        
        if decision == "duplicate":
            duplicate_counts[ticker] = duplicate_counts.get(ticker, 0) + 1
            duplicate_count += 1
            logger.warning("Memory: Suppressing duplicate event for %s. (Catalyst: %s)", ticker, cat_id)
        else:
            if decision == "new":
                accepted_count += 1
            elif decision == "update":
                update_count += 1
            filtered_candidates.append(cand)
            logger.info("Memory: Accepted event for %s as %s. (Catalyst: %s)", ticker, decision.upper(), cat_id)
            
        if span and span.is_recording():
            span.add_event("ledger_decision", {
                "ticker": ticker,
                "event_id": event_id,
                "decision": decision,
                "catalyst_id": cat_id,
                "new_facts_count": len(new_facts)
            })
            
    if span and span.is_recording():
        span.set_attribute("accepted_count", accepted_count)
        span.set_attribute("duplicate_count", duplicate_count)
        span.set_attribute("update_count", update_count)
        
    return {"routed_candidates": filtered_candidates, "duplicate_counts": duplicate_counts}
