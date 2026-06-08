"""Pure recency/scoring/annotation helpers for ticker synthesis.

Small, side-effect-free functions shared by the bucket, post-processing, and worker
stages. Kept separate so each stage module stays focused.
"""
from typing import Any, Dict, List, Tuple

from backend.iterations.utils import datetime_now

def _minutes_ago(iso_ts: str, ref_time) -> int:
    """Whole minutes between an ISO timestamp and ref_time; -1 if missing/unparseable."""
    from datetime import datetime, timezone
    if not iso_ts:
        return -1
    try:
        dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00')).astimezone(timezone.utc)
        return int((ref_time - dt).total_seconds() / 60)
    except Exception:
        return -1

def _coerce_minutes_ago(event: Dict[str, Any]) -> int:
    try:
        return int(event.get("minutesAgo", -1))
    except Exception:
        return -1

def _recency_label(event: Dict[str, Any]) -> str:
    minutes_ago = _coerce_minutes_ago(event)
    if 0 <= minutes_ago < 30:
        return "breaking"
    if 0 <= minutes_ago <= 90:
        return "recent"
    return "background"

def _event_text_for_scoring(event: Dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in [
            event.get("headline", ""),
            event.get("eventSummary", ""),
            " ".join(str(f.get("fact", f)) if isinstance(f, dict) else str(f) for f in event.get("hardFacts", [])),
            " ".join(event.get("eventTags", [])),
            " ".join(event.get("technologyThemes", [])),
        ]
    ).lower()

def _source_tagged_to_different_mentioned_company(event: Dict[str, Any], ticker: str) -> bool:
    source_related = {t.upper() for t in event.get("sourceRelatedTickers", [])}
    mentioned = {t.upper() for t in event.get("mentionedTickers", [])}
    ticker_upper = ticker.upper()
    return ticker_upper in source_related and bool(mentioned) and ticker_upper not in mentioned

def _infer_intraday_pressure(event: Dict[str, Any], ticker: str, current: str = "unclear") -> str:
    """Preserve the model's ticker-level directional read without keyword forcing."""
    if current in {"positive", "negative", "mixed"}:
        return current

    event_pressure = event.get("possibleDirectionalPressure", "unclear")
    if event_pressure in {"positive", "negative", "mixed"}:
        return event_pressure

    return "unclear"

def _source_refs_for_bucket(bucket: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    src_ids = []
    src_urls = []
    for event in bucket.get("directEvents", []) + bucket.get("crossImpactEvents", []):
        src_ids.append(event["eventId"])
        if event.get("sourceUrl"):
            src_urls.append(event["sourceUrl"])
    return src_ids, list(set(src_urls))

def _annotate_bucket_for_synthesis(bucket: Dict[str, Any]) -> Dict[str, Any]:
    ref_time = datetime_now()

    def annotate_event_recency(event: Dict[str, Any]) -> Dict[str, Any]:
        event["minutesAgo"] = _minutes_ago(
            event.get("publishedAt", "") or event.get("lastUpdatedAt", "") or event.get("firstSeenAt", ""),
            ref_time,
        )
        timed = event.get("hardFactsTimed")
        if timed:
            event["hardFacts"] = [
                {"fact": f.get("fact", ""), "minutesAgo": _minutes_ago(f.get("publishedAt", ""), ref_time)}
                for f in timed
            ]
        event.pop("hardFactsTimed", None)
        return event

    annotated_bucket = dict(bucket)
    annotated_bucket["directEvents"] = [annotate_event_recency(dict(e)) for e in bucket.get("directEvents", [])]
    annotated_bucket["crossImpactEvents"] = [annotate_event_recency(dict(e)) for e in bucket.get("crossImpactEvents", [])]
    return annotated_bucket
