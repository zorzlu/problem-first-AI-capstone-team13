"""Ticker synthesis worker and fan-in.

The synthesis stage is split across:
  - synthesis_buckets.py     : build the per-ticker context buckets + Send dispatch
  - synthesis_scoring.py     : pure recency/scoring/annotation helpers
  - synthesis_postprocess.py : contract repair, significance floors, mock briefing
This module keeps the LangGraph worker (synthesize_one_ticker_node) and the fan-in
collector, and re-exports the public node API plus the helpers imported by tests.

Note: synthesize_one_ticker_node resolves get_synthesis_llm from THIS module's namespace,
so tests patch backend.iterations.synthesis.get_synthesis_llm. Keep that import here.
"""
import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from backend.iterations.contracts import SynthesisOut, WorkflowState
from backend.iterations.guardrails import build_degraded_synthesis, judge_synthesis_output
from backend.iterations.prompts import SYNTHESIS_SYSTEM_PROMPT
from backend.iterations.utils import classify_llm_failure, datetime_now, invoke_with_retry
from backend.core.llm import get_synthesis_llm, has_llm_for_step
from backend.core.logging import get_logger

from backend.iterations.synthesis_buckets import (
    build_ticker_buckets_for_synthesis,
    dispatch_ticker_synthesis,
)
from backend.iterations.synthesis_scoring import (
    _annotate_bucket_for_synthesis,
    _source_refs_for_bucket,
)
from backend.iterations.synthesis_postprocess import (
    _mock_synthesis_for_ticker,
    _normalize_synthesis_significance,
    _postprocess_synthesis,
)

logger = get_logger(__name__)

__all__ = [
    "build_ticker_buckets_for_synthesis",
    "dispatch_ticker_synthesis",
    "synthesize_one_ticker_node",
    "collect_ticker_syntheses",
]

def synthesize_one_ticker_node(state: WorkflowState) -> Dict[str, Any]:
    """LangGraph worker node: synthesize and judge exactly one ticker branch."""
    ticker = state["active_synthesis_ticker"]
    bucket = state["active_synthesis_bucket"]
    logger.info("--- [Node 5b: Per-Ticker Synthesis Worker] (%s) ---", ticker)
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    counts = {"judge_fail": 0, "regeneration": 0, "degrade": 0}

    use_mock = not has_llm_for_step("synthesis")

    if use_mock:
        synthesis = _mock_synthesis_for_ticker(ticker, bucket, state)
        if span and span.is_recording():
            span.add_event("ticker_synthesis", {
                "ticker": ticker,
                "status": "success",
                "has_catalysts": bool(bucket["directEvents"] or bucket["crossImpactEvents"]),
                "mode": "mock",
            })
        return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis, "l3Counts": counts}]}

    if not bucket["directEvents"] and not bucket["crossImpactEvents"]:
        synthesis = _mock_synthesis_for_ticker(ticker, bucket, state)
        synthesis["guardrailMetadata"]["judgeStatus"] = "skipped_empty"
        if span and span.is_recording():
            span.add_event("ticker_synthesis", {
                "ticker": ticker,
                "status": "success",
                "has_catalysts": False,
                "mode": "llm",
            })
        return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis, "l3Counts": counts}]}

    annotated_bucket = _annotate_bucket_for_synthesis(bucket)
    for event in bucket["crossImpactEvents"]:
        if span and span.is_recording():
            span.add_event("path_filtering", {
                "ticker": ticker,
                "event_id": event["eventId"],
                "path_score": event.get("pathConfidence", 0.0),
                "path_strength": event.get("pathStrength") or "weak",
                "status": "included" if event.get("pathStrength") == "strong" else "filtered_out",
            })

    logger.info("Synthesizing catalyst briefing for ticker: %s", ticker)
    context_str = json.dumps(annotated_bucket, indent=2)
    user_prompt = f"TICKER CONFIG: {ticker}\nCONTEXT BUCKET:\n{context_str}"
    src_ids, src_urls = _source_refs_for_bucket(bucket)

    try:
        llm = get_synthesis_llm()
        structured_llm = llm.with_structured_output(SynthesisOut)
        result: SynthesisOut = invoke_with_retry(
            structured_llm,
            [SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT), HumanMessage(content=user_prompt)],
            label=f"synthesis for {ticker}",
        )
        synthesis = _postprocess_synthesis(result.model_dump(), annotated_bucket, ticker)
        synthesis["summaryId"] = f"sum_{ticker}_{int(datetime_now().timestamp())}"
        synthesis["ticker"] = ticker
        synthesis["sourceEventIds"] = src_ids
        synthesis["sourceArticleUrls"] = src_urls
        synthesis["notFinancialAdvice"] = True
        synthesis["complianceDisclaimer"] = "This is an informational briefing, not financial advice. The net impact assessment is tentative and may be incomplete; market data and official sources can change the read."

        try:
            judge_res = judge_synthesis_output(ticker, annotated_bucket, synthesis)
            if span and span.is_recording():
                span.add_event("l3_output_judge", {
                    "ticker": ticker,
                    "passes": judge_res.passes,
                    "groundingPassed": judge_res.groundingPassed,
                    "advicePassed": judge_res.advicePassed,
                    "pathPassed": judge_res.pathPassed,
                    "defects": judge_res.defects,
                })

            if judge_res.passes:
                synthesis["guardrailMetadata"] = {
                    "judgeStatus": "passed",
                    "judgeAttempts": 1,
                    "judgeDefects": [],
                    "regenerated": False,
                    "degraded": False,
                }
                if span and span.is_recording():
                    span.add_event("ticker_synthesis", {
                        "ticker": ticker,
                        "status": "success",
                        "has_catalysts": True,
                        "mode": "llm",
                    })
                return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis, "l3Counts": counts}]}

            logger.warning("  [guardrail] Judge failed for %s. Defects: %s", ticker, judge_res.defects)
            counts["judge_fail"] += 1
            counts["regeneration"] += 1
            if span and span.is_recording():
                span.add_event("l3_regeneration", {
                    "ticker": ticker,
                    "defects": judge_res.defects,
                    "regeneration_instruction": judge_res.regenerationInstruction,
                })

            regen_system_prompt = SYNTHESIS_SYSTEM_PROMPT + f"\n\nCRITICAL CORRECTION REQUIRED:\nYour previous output was evaluated by a safety guardrail and failed due to the following defects: {', '.join(judge_res.defects)}.\n\nCorrection instructions:\n{judge_res.regenerationInstruction}\n\nStrictly address these defects, ensuring the output is perfectly grounded in the context data and indirect paths match the routing exactly."
            logger.warning("  [guardrail] Attempting regeneration for %s...", ticker)
            result_regen: SynthesisOut = invoke_with_retry(
                structured_llm,
                [SystemMessage(content=regen_system_prompt), HumanMessage(content=user_prompt)],
                label=f"regeneration for {ticker}",
            )
            synthesis_regen = _postprocess_synthesis(result_regen.model_dump(), annotated_bucket, ticker)
            synthesis_regen["summaryId"] = f"sum_{ticker}_{int(datetime_now().timestamp())}"
            synthesis_regen["ticker"] = ticker
            synthesis_regen["sourceEventIds"] = src_ids
            synthesis_regen["sourceArticleUrls"] = src_urls
            synthesis_regen["notFinancialAdvice"] = True
            synthesis_regen["complianceDisclaimer"] = "This is an informational briefing, not financial advice. The net impact assessment is tentative and may be incomplete; market data and official sources can change the read."

            judge_res_2 = judge_synthesis_output(ticker, annotated_bucket, synthesis_regen)
            if span and span.is_recording():
                span.add_event("l3_output_judge", {
                    "ticker": ticker,
                    "passes": judge_res_2.passes,
                    "groundingPassed": judge_res_2.groundingPassed,
                    "advicePassed": judge_res_2.advicePassed,
                    "pathPassed": judge_res_2.pathPassed,
                    "defects": judge_res_2.defects,
                })

            if judge_res_2.passes:
                logger.info("  [guardrail] Regenerated output passed for %s!", ticker)
                synthesis_regen["guardrailMetadata"] = {
                    "judgeStatus": "regenerated_passed",
                    "judgeAttempts": 2,
                    "judgeDefects": [],
                    "regenerated": True,
                    "degraded": False,
                }
                if span and span.is_recording():
                    span.add_event("ticker_synthesis", {
                        "ticker": ticker,
                        "status": "success",
                        "has_catalysts": True,
                        "mode": "llm",
                    })
                return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis_regen, "l3Counts": counts}]}

            logger.warning("  [guardrail] Regenerated output failed for %s again. Degrading briefing.", ticker)
            counts["degrade"] += 1
            if span and span.is_recording():
                span.add_event("l3_degraded", {
                    "ticker": ticker,
                    "reason": f"Regeneration failed: {', '.join(judge_res_2.defects)}",
                })
            synthesis = build_degraded_synthesis(
                ticker,
                f"Regeneration failed: {', '.join(judge_res_2.defects)}",
                src_ids,
                src_urls,
            )
            return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis, "l3Counts": counts}]}

        except Exception as judge_exc:
            logger.exception("  [guardrail] Judge execution error for %s: %s. Degrading briefing.", ticker, judge_exc)
            counts["degrade"] += 1
            if span and span.is_recording():
                span.add_event("l3_degraded", {
                    "ticker": ticker,
                    "reason": f"Judge error: {str(judge_exc)}",
                })
            synthesis = build_degraded_synthesis(
                ticker,
                f"Judge error: {str(judge_exc)}",
                src_ids,
                src_urls,
            )
            return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis, "l3Counts": counts}]}

    except Exception as e:
        reason = classify_llm_failure(e, "synthesis model")
        logger.exception("Error synthesizing briefing for %s: %s", ticker, e)
        synthesis = {
            "summaryId": f"sum_error_{ticker}",
            "ticker": ticker,
            "summaryHeadline": "Error in catalyst synthesis",
            "situationSummary": f"No briefing was produced for {ticker}. {reason}",
            "mainCatalysts": [],
            "overallPossibleInfluence": "unclear",
            "confidence": "low",
            "uncertainties": ["System processing error."],
            "watchItems": [],
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
            span.add_event("ticker_synthesis", {
                "ticker": ticker,
                "status": "failed",
                "mode": "llm",
                "error": str(e),
            })
        return {"ticker_synthesis_results": [{"ticker": ticker, "synthesis": synthesis, "l3Counts": counts}]}

def collect_ticker_syntheses(state: WorkflowState) -> Dict[str, Any]:
    """Fan-in node: reduce branch results into the existing ticker_syntheses API shape."""
    logger.info("--- [Node 5c: Collect Ticker Syntheses] ---")
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
    except Exception:
        span = None

    results = state.get("ticker_synthesis_results", [])
    if not results:
        return {"ticker_syntheses": state.get("ticker_syntheses", {})}

    by_ticker = {r["ticker"]: r["synthesis"] for r in results}
    ticker_syntheses = {
        ticker: by_ticker[ticker]
        for ticker in state.get("watchlist", [])
        if ticker in by_ticker
    }
    for ticker, synthesis in by_ticker.items():
        ticker_syntheses.setdefault(ticker, synthesis)

    l3_judge_fail_count = sum(r.get("l3Counts", {}).get("judge_fail", 0) for r in results)
    l3_regeneration_count = sum(r.get("l3Counts", {}).get("regeneration", 0) for r in results)
    l3_degrade_count = sum(r.get("l3Counts", {}).get("degrade", 0) for r in results)

    if span and span.is_recording():
        span.set_attribute("l3_judge_fail_count", l3_judge_fail_count)
        span.set_attribute("l3_regeneration_count", l3_regeneration_count)
        span.set_attribute("l3_degrade_count", l3_degrade_count)

    return {"ticker_syntheses": ticker_syntheses}
