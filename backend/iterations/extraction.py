"""Canonical event extraction node for iteration workflows."""
from typing import Any, Dict
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from backend.iterations.contracts import ExtractionResult, WorkflowState
from backend.iterations.extraction_focus import (
    UNTRUSTED_NEWS_BATCH_WRAPPER,
    _ticker_alias_focus_block,
)
from backend.iterations.mock_data import MOCK_EVENTS
from backend.iterations.utils import classify_llm_failure, copy_dict, datetime_now, invoke_with_retry
from backend.core.llm import get_extraction_llm, has_llm_for_step
from backend.core.logging import get_logger

logger = get_logger(__name__)

def run_extraction(state: WorkflowState, system_prompt: str, focus_block: str) -> Dict[str, Any]:
    """Extract canonical events from the fetched articles using the given prompt + focus block."""
    logger.info("--- [Node 2: Canonical Event Extraction] ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    articles = state.get("articles", [])
    canonical_events = []
    
    if span and span.is_recording():
        span.set_attribute("articles_count", len(articles))
        
    if not articles:
        logger.info("No articles fetched to extract events from.")
        return {"canonical_events": []}
        
    use_mock = not has_llm_for_step("extraction")
    
    if use_mock:
        logger.warning("No LLM API keys found. Falling back to pre-baked canonical event extraction.")
        for art in articles:
            art_id = art["articleId"]
            
            if art_id in MOCK_EVENTS:
                event = copy_dict(MOCK_EVENTS[art_id])
            else:
                event = {
                    "eventType": "other",
                    "eventSummary": art["headline"],
                    "hardFacts": [art.get("summary") or art["headline"]],
                    "entities": art.get("relatedTickers", []),
                    "eventTags": ["general"],
                    "regions": [],
                    "sectors": [],
                    "commodities": [],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "unclear",
                    "uncertaintyNotes": ["Source data completeness"],
                    "evidence": [art["headline"]]
                }
            
            # Map identifiers and source urls
            event["eventId"] = f"evt_{art_id}"
            event["sourceArticleIds"] = [art_id]
            event["relatedTickers"] = art.get("relatedTickers", [])
            event["sourceUrl"] = art.get("url")
            event["sourceName"] = art.get("sourceName")
            event["sourceHeadline"] = art.get("headline")
            event["publishedAt"] = art.get("publishedAt")
            
            canonical_events.append(event)
            logger.info("Mock Extracted Event: %s (Type: %s)", event["eventSummary"], event["eventType"])
            
        if span and span.is_recording():
            span.add_event("events_extracted", {
                "extracted_count": len(canonical_events),
                "use_mock": True
            })
        return {"canonical_events": canonical_events}

    llm = get_extraction_llm()

    # Reference time for computing article age
    ref_time = datetime_now()

    def clean_summary(headline: str, summary: str) -> str:
        """Strips Finnhub-style trailing headline repetition from the summary field."""
        if not summary:
            return ""
        stripped = summary.strip()
        if stripped.lower().endswith(headline.strip().lower()):
            stripped = stripped[: -len(headline.strip())].rstrip(" .,;")
        return stripped

    # Build the input message containing all articles
    ticker_alias_block = _ticker_alias_focus_block(
        state.get("watchlist", []),
        state.get("expansion_tickers", []),
    )
    user_content = focus_block + ticker_alias_block + UNTRUSTED_NEWS_BATCH_WRAPPER + "\n\nAnalyze the following news articles and return a JSON list of event objects:\n\n"
    for i, art in enumerate(articles):
        headline = art['headline']
        raw_summary = art.get('summary', '')
        summary = clean_summary(headline, raw_summary)
        try:
            pub_dt = datetime.fromisoformat(art['publishedAt'].replace('Z', '+00:00')).astimezone(timezone.utc)
            minutes_ago = int((ref_time - pub_dt).total_seconds() / 60)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            # Expected for missing/malformed publishedAt; anything else should propagate.
            logger.debug("Could not parse publishedAt for article %s: %s", art.get('articleId'), exc)
            minutes_ago = -1
        age_label = f"{minutes_ago} mins ago" if minutes_ago >= 0 else "unknown age"
        user_content += f"""--- ARTICLE {i+1} ---
ARTICLE ID: {art['articleId']}
SOURCE: {art['sourceName']}
PUBLISHED: {art['publishedAt']} ({age_label})
URL: {art['url']}
HEADLINE: {headline}
SUMMARY: {summary}
RELATED TICKERS IN SOURCE: {', '.join(art.get('relatedTickers', []))}
\n"""

    try:
        logger.info("Calling LLM to extract events from %d articles in one batch...", len(articles))
        structured_llm = llm.with_structured_output(ExtractionResult)
        result: ExtractionResult = invoke_with_retry(
            structured_llm,
            [SystemMessage(content=system_prompt), HumanMessage(content=user_content)],
            label="batch event extraction",
        )
        extracted_events = [ev.model_dump() for ev in result.events]

        # Create map of articles by ID for easy lookup
        art_map = {art["articleId"]: art for art in articles}
        
        for event in extracted_events:
            art_id = event.get("articleId")
            if not art_id and len(articles) == 1:
                art_id = articles[0]["articleId"]
                
            art = art_map.get(art_id)
            if art:
                event["eventId"] = f"evt_{art['articleId']}"
                event["sourceArticleIds"] = [art["articleId"]]
                event["relatedTickers"] = art.get("relatedTickers", [])
                event["sourceUrl"] = art.get("url")
                event["sourceName"] = art.get("sourceName")
                event["sourceHeadline"] = art.get("headline")
                event["publishedAt"] = art.get("publishedAt")
                canonical_events.append(event)
                logger.info("Extracted Event: %s (Type: %s)", event["eventSummary"], event["eventType"])
            else:
                logger.warning("Extracted event references unknown articleId: %s", art_id)
                
        if span and span.is_recording():
            span.add_event("events_extracted", {
                "extracted_count": len(canonical_events),
                "use_mock": False
            })
            
    except Exception as e:
        reason = classify_llm_failure(e, "news-analysis model")
        logger.exception("Node 2 event extraction failed: %s", e)
        logger.error("Setting llm_failed=True to halt downstream LLM steps.")
        if span and span.is_recording():
            span.set_attribute("llm_failed", True)
            span.set_attribute("failure_reason", reason)
        return {
            "canonical_events": [],
            "llm_failed": True,
            "failure_reason": reason,
        }

    return {"canonical_events": canonical_events, "llm_failed": False, "failure_reason": ""}
