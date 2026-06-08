"""Per-ticker synthesis bucket construction and LangGraph fan-out dispatch."""
from typing import Any, Dict, List

from langgraph.types import Send

from backend.iterations.contracts import WorkflowState

def _normalize_timed_facts(facts: List[Any], fallback_ts: str = "") -> List[Dict[str, Any]]:
    """
    Coerce a hardFactsSeen list into [{'fact','publishedAt'}], where publishedAt is the source
    news publication time. Accepts the current dict shape, the legacy `firstSeenAt`-keyed dict
    shape, and legacy plain strings, applying fallback_ts when a per-fact timestamp is missing.
    """
    normalized = []
    for f in facts or []:
        if isinstance(f, dict):
            ts = f.get("publishedAt") or f.get("firstSeenAt") or fallback_ts
            normalized.append({"fact": f.get("fact", ""), "publishedAt": ts})
        else:
            normalized.append({"fact": f, "publishedAt": fallback_ts})
    return normalized

def build_ticker_buckets_for_synthesis(state: WorkflowState, restore_ledger: bool, restore_indirect: bool) -> Dict[str, Any]:
    """Build per-ticker synthesis buckets before LangGraph fans out ticker workers."""
    print(f"--- [Node 5a: Build Ticker Buckets] (restore_ledger={restore_ledger}, restore_indirect={restore_indirect}) ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    if state.get("llm_failed", False):
        print("Skipping synthesis fan-out: upstream LLM failure detected (llm_failed=True).")
        watchlist = state.get("watchlist", [])
        reason = state.get("failure_reason") or "The model could not be reached during event extraction."
        halted_syntheses = {}
        for ticker in watchlist:
            halted_syntheses[ticker] = {
                "summaryId": f"sum_halted_{ticker}",
                "ticker": ticker,
                "summaryHeadline": "Pipeline halted — event extraction failed",
                "situationSummary": f"No synthesis was produced. {reason}",
                "mainCatalysts": [],
                "overallPossibleInfluence": "unclear",
                "confidence": "low",
                "uncertainties": [reason],
                "watchItems": ["Re-run the pipeline; if the failure persists, check the backend logs for the underlying cause."],
                "sourceEventIds": [],
                "sourceArticleUrls": [],
                "notFinancialAdvice": True,
                "guardrailMetadata": {
                    "judgeStatus": "not_run_synthesis_failed",
                    "judgeAttempts": 0,
                    "judgeDefects": [reason],
                    "regenerated": False,
                    "degraded": True,
                },
            }
        if span and span.is_recording():
            span.set_attribute("llm_failed", True)
            span.set_attribute("failure_reason", reason)
        return {"ticker_buckets": {}, "ticker_syntheses": halted_syntheses, "ticker_synthesis_results": []}

    watchlist = state.get("watchlist", [])
    routed_candidates = state.get("routed_candidates", [])
    duplicate_counts = state.get("duplicate_counts", {})
    canonical_events = {e["eventId"]: e for e in state.get("canonical_events", [])}

    if span and span.is_recording():
        span.set_attribute("watchlist", watchlist)
        span.set_attribute("llm_failed", False)

    ticker_buckets = {
        ticker: {
            "ticker": ticker,
            "directEvents": [],
            "crossImpactEvents": [],
            "suppressedDuplicateCount": duplicate_counts.get(ticker, 0),
        }
        for ticker in watchlist
    }

    from backend.memory import get_ledger
    iteration = state.get("iteration", 2)
    active_ledger = get_ledger(iteration) if restore_ledger else []
    ledger_by_catalyst = {e["catalystId"]: e for e in active_ledger}

    for cand in routed_candidates:
        ticker = cand["ticker"]
        event_id = cand["eventId"]
        event = canonical_events[event_id]

        ledger_entry = ledger_by_catalyst.get(cand.get("catalystId"))
        if ledger_entry and ledger_entry.get("hardFactsSeen"):
            facts_timed = _normalize_timed_facts(ledger_entry["hardFactsSeen"], event.get("publishedAt", ""))
        else:
            facts_timed = _normalize_timed_facts(event.get("hardFacts", []), event.get("publishedAt", ""))

        event_entry = {
            "eventId": event_id,
            "catalystId": cand.get("catalystId"),
            "eventType": event["eventType"],
            "relationshipType": cand["relationshipType"],
            "headline": event.get("sourceHeadline", ""),
            "sourceName": event.get("sourceName", ""),
            "eventSummary": event["eventSummary"],
            "hardFacts": [f["fact"] for f in facts_timed],
            "hardFactsTimed": facts_timed,
            "mentionedTickers": event.get("mentionedTickers", []),
            "entities": event.get("entities", []),
            "eventTags": event.get("eventTags", []),
            "regions": event.get("regions", []),
            "sectors": event.get("sectors", []),
            "commodities": event.get("commodities", []),
            "technologyThemes": event.get("technologyThemes", []),
            "possibleDirectionalPressure": event["possibleDirectionalPressure"],
            "sourceArticleIds": event["sourceArticleIds"],
            "sourceRelatedTickers": event.get("relatedTickers", []),
            "sourceUrl": event.get("sourceUrl", ""),
            "uncertaintyNotes": event.get("uncertaintyNotes", []),
            "publishedAt": event.get("publishedAt", ""),
            "impactPath": cand.get("impactPath", [ticker]),
            "reasonForRouting": cand.get("reasonForRouting", f"Directly tagged in news source for ticker {ticker}."),
        }

        if cand["relationshipType"] == "direct":
            ticker_buckets[ticker]["directEvents"].append(event_entry)
        else:
            event_entry["pathConfidence"] = cand["pathConfidence"]
            event_entry["pathStrength"] = cand.get("pathStrength", "strong")
            ticker_buckets[ticker]["crossImpactEvents"].append(event_entry)

    for ticker in watchlist:
        ticker_ledger_entries = [entry for entry in active_ledger if entry["ticker"] == ticker]

        seen_catalyst_ids = {
            e["catalystId"]
            for e in ticker_buckets[ticker]["directEvents"] + ticker_buckets[ticker]["crossImpactEvents"]
            if e.get("catalystId")
        }

        for entry in ticker_ledger_entries:
            cat_id = entry["catalystId"]
            if cat_id in seen_catalyst_ids:
                continue

            rel_type = entry.get("relationshipType", "direct")
            if not restore_indirect and rel_type != "direct":
                continue

            entry_fallback_ts = entry.get("lastUpdatedAt") or entry.get("firstSeenAt") or ""
            recon_facts_timed = _normalize_timed_facts(entry.get("hardFactsSeen", []), entry_fallback_ts)
            fact_times = [f["publishedAt"] for f in recon_facts_timed if f.get("publishedAt")]
            recon_published = max(fact_times) if fact_times else entry_fallback_ts

            reconstructed_entry = {
                "eventId": f"evt_{cat_id}",
                "catalystId": cat_id,
                "eventType": entry["eventType"],
                "relationshipType": rel_type,
                "headline": entry.get("sourceHeadline", ""),
                "sourceName": entry.get("sourceName", ""),
                "eventSummary": entry["canonicalSummary"],
                "hardFacts": [f["fact"] for f in recon_facts_timed],
                "hardFactsTimed": recon_facts_timed,
                "mentionedTickers": [ticker],
                "entities": [],
                "eventTags": [],
                "regions": [],
                "sectors": [],
                "commodities": [],
                "technologyThemes": [],
                "possibleDirectionalPressure": entry.get("possibleDirectionalPressure", "unclear"),
                "sourceArticleIds": entry.get("memberArticleIds", []),
                "sourceRelatedTickers": [ticker],
                "sourceUrl": entry.get("sourceUrl", ""),
                "uncertaintyNotes": entry.get("uncertaintyNotes", []),
                "publishedAt": recon_published,
                "impactPath": [ticker] if rel_type == "direct" else [entry["eventType"], ticker],
                "reasonForRouting": (
                    f"Restored direct catalyst memory for ticker {ticker}."
                    if rel_type == "direct"
                    else "Restored from exposure graph memory."
                ),
            }

            if rel_type == "direct":
                ticker_buckets[ticker]["directEvents"].append(reconstructed_entry)
            else:
                reconstructed_entry["pathConfidence"] = 1.0
                reconstructed_entry["pathStrength"] = "strong"
                ticker_buckets[ticker]["crossImpactEvents"].append(reconstructed_entry)

        if span and span.is_recording():
            span.add_event("bucket_created", {
                "ticker": ticker,
                "direct_events_count": len(ticker_buckets[ticker]["directEvents"]),
                "cross_impact_events_count": len(ticker_buckets[ticker]["crossImpactEvents"]),
            })

    return {"ticker_buckets": ticker_buckets, "ticker_synthesis_results": []}

def dispatch_ticker_synthesis(state: WorkflowState):
    """Fan out one LangGraph branch per ticker bucket using the Send API."""
    buckets = state.get("ticker_buckets", {})
    if not buckets:
        return "collect_ticker_syntheses"
    return [
        Send(
            "synthesize_one_ticker",
            {
                **state,
                "active_synthesis_ticker": ticker,
                "active_synthesis_bucket": bucket,
            },
        )
        for ticker, bucket in buckets.items()
    ]
