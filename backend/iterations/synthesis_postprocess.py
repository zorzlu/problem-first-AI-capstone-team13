"""Deterministic synthesis shaping: contract repair, significance floors, and the
no-key mock briefing. Applied to LLM output (or used directly in mock mode) before the
guardrail judge sees a briefing.
"""
from typing import Any, Dict

from backend.core.config import FRESHNESS_LOOKBACK_MINUTES
from backend.iterations.contracts import WorkflowState
from backend.iterations.utils import datetime_now
from backend.iterations.synthesis_scoring import (
    _coerce_minutes_ago,
    _event_text_for_scoring,
    _infer_intraday_pressure,
    _recency_label,
    _source_refs_for_bucket,
    _source_tagged_to_different_mentioned_company,
)

def _empty_state_summary(ticker: str, state: WorkflowState) -> str:
    """Accurate 'no catalysts' copy that distinguishes the real cause.

    The old wording always blamed the freshness window even when articles had cleared it
    and were merely deduplicated or routed elsewhere. This separates the three causes.
    """
    metadata = state.get("ingestion_metadata", {})
    total = metadata.get("total_ingested", 0)
    passed = metadata.get("passed_freshness", 0)
    dup = state.get("duplicate_counts", {}).get(ticker, 0)
    if total == 0:
        return "No news articles were ingested in this refresh."
    if passed == 0:
        return (f"Ingested {total} articles, but none passed the freshness filter "
                f"(nothing published within the last {FRESHNESS_LOOKBACK_MINUTES} minutes). "
                f"They were filtered out as older news.")
    if dup > 0:
        return "Known story threads only — no new developments since the last refresh."
    return f"No catalysts routed to {ticker} in this refresh."

def _default_catalyst_from_event(event: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    relationship = event.get("relationshipType", "direct")
    pressure = _infer_intraday_pressure(event, ticker)
    text = _event_text_for_scoring(event)
    high_impact = any(term in text for term in (
        "contract", "government", "award", "wins", "billion", "million", "$",
        "earnings", "guidance", "regulatory", "lawsuit", "launch", "benchmark",
        "model", "paper", "supply", "halt", "delay", "disruption",
    ))
    minutes_ago = _coerce_minutes_ago(event)

    if relationship == "direct":
        significance = 5 if pressure == "unclear" else 6
        if _source_tagged_to_different_mentioned_company(event, ticker) and pressure == "unclear":
            significance = 4
        if high_impact or (0 <= minutes_ago < 30):
            significance = max(significance, 7 if pressure != "unclear" else 5)
        confidence = "medium" if pressure != "unclear" else "tentative"
    else:
        significance = 5 if pressure != "unclear" else 3
        confidence = "tentative"

    return {
        "eventId": event["eventId"],
        "label": event.get("headline") or event.get("eventSummary", "Catalyst event"),
        "relationshipType": relationship,
        "eventType": event.get("eventType", "other"),
        "possibleInfluence": pressure,
        "confidence": confidence,
        "recency": _recency_label(event),
        "impactPath": event.get("impactPath") or ([ticker] if relationship == "direct" else []),
        "significance": significance,
    }

def _repair_synthesis_structure(synthesis: Dict[str, Any], bucket: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """Make deterministic contract repairs before the LLM judge sees the briefing."""
    events_by_id = {
        e.get("eventId"): e
        for e in bucket.get("directEvents", []) + bucket.get("crossImpactEvents", [])
    }

    repaired_main = []
    seen_event_ids = set()
    weak_watch_items = []
    for catalyst in synthesis.get("mainCatalysts", []) or []:
        event_id = catalyst.get("eventId")
        event = events_by_id.get(event_id)
        if not event:
            continue
        if event.get("relationshipType") == "indirect" and event.get("pathStrength") != "strong":
            path = " -> ".join(event.get("impactPath", []))
            weak_watch_items.append(
                f"Monitor whether '{event.get('headline') or event.get('eventSummary')}' becomes relevant to {ticker} via {path}."
            )
            continue

        catalyst["relationshipType"] = event.get("relationshipType", catalyst.get("relationshipType"))
        catalyst["eventType"] = event.get("eventType", catalyst.get("eventType"))
        catalyst["impactPath"] = event.get("impactPath") or catalyst.get("impactPath", [])
        catalyst["possibleInfluence"] = _infer_intraday_pressure(
            event,
            ticker,
            catalyst.get("possibleInfluence", event.get("possibleDirectionalPressure", "unclear")),
        )
        catalyst["recency"] = catalyst.get("recency") or _recency_label(event)
        repaired_main.append(catalyst)
        seen_event_ids.add(event_id)

    # Source-tagged / mentioned-ticker direct events are the highest-trust input bucket.
    # If the model omitted them while discussing weak macro graph paths, put them back.
    missing_direct = [
        e for e in bucket.get("directEvents", [])
        if e.get("eventId") not in seen_event_ids
    ]
    missing_direct.sort(key=lambda e: (_coerce_minutes_ago(e) if _coerce_minutes_ago(e) >= 0 else 10_000))
    for event in reversed(missing_direct[:3]):
        repaired_main.insert(0, _default_catalyst_from_event(event, ticker))
        seen_event_ids.add(event.get("eventId"))

    synthesis["mainCatalysts"] = repaired_main

    watch_items = list(synthesis.get("watchItems", []) or [])
    for item in weak_watch_items:
        if item not in watch_items:
            watch_items.append(item)
    synthesis["watchItems"] = watch_items[:6]

    influences = [c.get("possibleInfluence") for c in repaired_main]
    directional = {p for p in influences if p in {"positive", "negative", "mixed"}}
    if "mixed" in directional or ("positive" in directional and "negative" in directional):
        synthesis["overallPossibleInfluence"] = "mixed"
    elif "positive" in directional:
        synthesis["overallPossibleInfluence"] = "positive"
    elif "negative" in directional:
        synthesis["overallPossibleInfluence"] = "negative"
    elif repaired_main:
        synthesis["overallPossibleInfluence"] = "unclear"

    if repaired_main and synthesis.get("confidence") == "low":
        synthesis["confidence"] = "medium"

    return synthesis

def _normalize_synthesis_significance(synthesis: Dict[str, Any], bucket: Dict[str, Any]) -> Dict[str, Any]:
    """Apply conservative intraday materiality floors to LLM significance scores.

    The model still chooses the score, but this prevents obviously material, fresh,
    source-tagged direct catalysts from being mislabeled as near-noise.
    """
    events_by_id = {
        e.get("eventId"): e
        for e in bucket.get("directEvents", []) + bucket.get("crossImpactEvents", [])
    }
    high_impact_terms = (
        "contract", "government", "award", "wins", "billion", "million", "$",
        "earnings", "guidance", "revenue", "profit", "margin", "all-time high",
        "record high", "stock hits", "price target", "sec", "regulatory", "lawsuit",
        "launch", "unveils", "benchmark", "outperforms", "model", "paper",
        "supply", "halt", "delay", "disruption",
    )

    for catalyst in synthesis.get("mainCatalysts", []) or []:
        event = events_by_id.get(catalyst.get("eventId"))
        if not event:
            continue

        text = _event_text_for_scoring(event)
        pressure = catalyst.get("possibleInfluence") or event.get("possibleDirectionalPressure")
        relationship = catalyst.get("relationshipType") or event.get("relationshipType")
        minutes_ago = event.get("minutesAgo", -1)
        has_direction = pressure in {"positive", "negative", "mixed"}
        has_high_impact_term = any(term in text for term in high_impact_terms)

        floor = 1
        if relationship == "direct" and has_direction:
            floor = max(floor, 6)
            if has_high_impact_term or (isinstance(minutes_ago, int) and 0 <= minutes_ago < 30):
                floor = max(floor, 7)
        elif relationship == "indirect" and has_direction:
            if event.get("pathStrength") == "strong":
                floor = max(floor, 5)
            if event.get("pathStrength") == "strong" and has_high_impact_term:
                floor = max(floor, 6)

        try:
            current = int(catalyst.get("significance", 1))
        except Exception:
            current = 1
        catalyst["significance"] = max(1, min(10, max(current, floor)))

    return synthesis

def _postprocess_synthesis(synthesis: Dict[str, Any], bucket: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    repaired = _repair_synthesis_structure(synthesis, bucket, ticker)
    return _normalize_synthesis_significance(repaired, bucket)

def _mock_synthesis_for_ticker(ticker: str, bucket: Dict[str, Any], state: WorkflowState) -> Dict[str, Any]:
    if not bucket["directEvents"] and not bucket["crossImpactEvents"]:
        return {
            "summaryId": f"sum_{ticker}_{int(datetime_now().timestamp())}",
            "ticker": ticker,
            "summaryHeadline": "No new catalysts detected",
            "situationSummary": _empty_state_summary(ticker, state),
            "mainCatalysts": [],
            "overallPossibleInfluence": "unclear",
            "confidence": "low",
            "uncertainties": ["No active events to assess."],
            "watchItems": ["Continue monitoring watchlist."],
            "sourceEventIds": [],
            "sourceArticleUrls": [],
            "notFinancialAdvice": True,
            "guardrailMetadata": {
                "judgeStatus": "skipped_empty",
                "judgeAttempts": 0,
                "judgeDefects": [],
                "regenerated": False,
                "degraded": False,
            },
        }

    all_events = bucket["directEvents"] + bucket["crossImpactEvents"]
    pressures = [e["possibleDirectionalPressure"] for e in all_events]
    if "negative" in pressures and "positive" in pressures:
        overall_influence = "mixed"
    elif "negative" in pressures:
        overall_influence = "negative"
    elif "positive" in pressures:
        overall_influence = "positive"
    else:
        overall_influence = "mixed"

    direct_summaries = [e["eventSummary"] for e in bucket["directEvents"]]
    cross_summaries = [f"{e['eventSummary']} (routed via {' -> '.join(e['impactPath'])})" for e in bucket["crossImpactEvents"]]

    headline = f"Catalyst update for {ticker}: "
    if direct_summaries and cross_summaries:
        headline += "Direct corporate and indirect exposure events active"
    elif direct_summaries:
        headline += "Direct announcements detected"
    else:
        headline += "Indirect cross-impact exposure pathways detected"

    situation_summary = f"In the latest monitoring window, {ticker} has active catalysts. "
    if direct_summaries:
        situation_summary += f"Direct corporate events: {'. '.join(direct_summaries)}. "
    if cross_summaries:
        situation_summary += f"Indirect cross-impact events routed through the exposure graph: {'. '.join(cross_summaries)}."

    main_catalysts = []
    for de in bucket["directEvents"]:
        main_catalysts.append({
            "eventId": de["eventId"],
            "label": de["eventSummary"],
            "relationshipType": "direct",
            "eventType": de["eventType"],
            "possibleInfluence": de["possibleDirectionalPressure"],
            "confidence": "high",
            "recency": "breaking",
            "impactPath": [ticker],
            "significance": 8 if de["possibleDirectionalPressure"] in ["positive", "negative"] else 4,
        })
    for ce in bucket["crossImpactEvents"]:
        main_catalysts.append({
            "eventId": ce["eventId"],
            "label": ce["eventSummary"],
            "relationshipType": "indirect",
            "eventType": ce["eventType"],
            "possibleInfluence": ce["possibleDirectionalPressure"],
            "confidence": "tentative",
            "recency": "recent",
            "impactPath": ce["impactPath"],
            "significance": 6 if ce["possibleDirectionalPressure"] in ["positive", "negative"] else 3,
        })

    uncertainties = []
    for event in all_events:
        uncertainties.extend(event.get("uncertaintyNotes", []))
    uncertainties = list(set(uncertainties)) if uncertainties else ["General macroeconomic conditions and market volatility."]
    src_ids, src_urls = _source_refs_for_bucket(bucket)

    return {
        "summaryId": f"sum_{ticker}_{int(datetime_now().timestamp())}",
        "ticker": ticker,
        "summaryHeadline": headline,
        "situationSummary": situation_summary,
        "mainCatalysts": main_catalysts,
        "overallPossibleInfluence": overall_influence,
        "confidence": "tentative",
        "uncertainties": uncertainties[:4],
        "watchItems": [
            f"{ticker} price and volume action",
            "Follow-up updates from related entities and supply partners",
        ],
        "sourceEventIds": src_ids,
        "sourceArticleUrls": src_urls,
        "notFinancialAdvice": True,
        "complianceDisclaimer": "This is an informational briefing, not financial advice. The impact assessment is tentative and may be incomplete; market data and official sources can change the read.",
        "guardrailMetadata": {
            "judgeStatus": "skipped_no_llm_mock_mode",
            "judgeAttempts": 0,
            "judgeDefects": [],
            "regenerated": False,
            "degraded": False,
        },
    }
