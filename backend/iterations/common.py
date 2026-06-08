"""Compatibility exports for iteration workflow building blocks.

The actual node implementations live in focused modules in this package. Iteration
wiring imports from this facade so callers can migrate gradually without recreating
cross-module dependency churn.
"""
from backend.iterations.contracts import (
    ExtractionResult,
    OutputSafetyJudgeOut,
    SynthesisOut,
    WorkflowState,
)
from backend.iterations.extraction import run_extraction
from backend.iterations.extraction_focus import cross_impact_focus, direct_focus
from backend.iterations.fetching import run_fetch_and_filter
from backend.iterations.guardrails import (
    build_degraded_synthesis,
    judge_synthesis_output,
    run_compliance_gate,
)
from backend.iterations.memory_nodes import assign_new_catalysts, run_ledger_dedup
from backend.iterations.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from backend.iterations.routing_nodes import route_events
from backend.iterations.synthesis import (
    build_ticker_buckets_for_synthesis,
    collect_ticker_syntheses,
    dispatch_ticker_synthesis,
    synthesize_one_ticker_node,
)
from backend.iterations.utils import clean_json_string, classify_llm_failure, copy_dict, datetime_now, invoke_with_retry

__all__ = [
    "ExtractionResult",
    "OutputSafetyJudgeOut",
    "SynthesisOut",
    "WorkflowState",
    "EXTRACTION_SYSTEM_PROMPT",
    "JUDGE_SYSTEM_PROMPT",
    "SYNTHESIS_SYSTEM_PROMPT",
    "cross_impact_focus",
    "direct_focus",
    "run_fetch_and_filter",
    "run_extraction",
    "route_events",
    "assign_new_catalysts",
    "run_ledger_dedup",
    "build_ticker_buckets_for_synthesis",
    "dispatch_ticker_synthesis",
    "synthesize_one_ticker_node",
    "collect_ticker_syntheses",
    "judge_synthesis_output",
    "build_degraded_synthesis",
    "run_compliance_gate",
    "clean_json_string",
    "classify_llm_failure",
    "copy_dict",
    "datetime_now",
    "invoke_with_retry",
]
