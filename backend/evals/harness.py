"""Test harness for running golden cases through eval workflows.

The harness injects articles, optionally swaps graph fixtures, invokes the workflow,
and collects results for eval assertions.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.core.logging import get_logger
from backend.iterations import get_workflow
from backend.memory import clear_ledger, snapshot_ledger_store, restore_ledger_store
from backend.graph.graph import set_graph, reset_graph
from backend.evals.golden_schema import GoldenCase, GoldenStep

logger = get_logger(__name__)


def run_golden_case(
    case: GoldenCase,
    simulated_now_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a golden test case and return the final workflow state.

    Args:
        case: Golden case specification with articles, watchlist, and expected outputs.
        simulated_now_override: Override the case's simulatedNow timestamp (for testing).

    Returns:
        Final workflow state from invoke(). Caller can check state against expected values.
    """
    logger.info("Running golden case %s (suite: %s)", case.caseId, case.suite)

    # Save current ledger and graph state for rollback.
    ledger_snapshot = snapshot_ledger_store()
    original_graph_state = None

    try:
        # Set up graph fixture.
        if case.graphFixture == "seed":
            reset_graph()
        elif isinstance(case.graphFixture, dict):
            # Custom subgraph for this case (e.g., for iter3 false-butterfly negatives).
            original_graph_state = None  # Track original state if we save it
            set_graph(case.graphFixture.get("nodes", []), case.graphFixture.get("edges", []))
        else:
            reset_graph()

        # Clear ledger for fresh case.
        clear_ledger()

        # Run steps in order (usually 1 for iter1/iter3, N for iter2 memory progression).
        final_state = None
        for step in case.steps:
            logger.debug("Running step %s of case %s", step.stepId, case.caseId)

            # Build initial state for this step.
            initial_state = {
                "iteration": case.iteration,
                "watchlist": case.watchlist,
                "scenario_id": case.caseId,
                "simulated_now": simulated_now_override or case.simulatedNow,
                "articles": _articles_to_dicts(step.articles),
                "canonical_events": [],
                "routed_candidates": [],
                "ticker_buckets": {},
                "ticker_syntheses": {},
                "duplicate_counts": {},
                "ingestion_metadata": {},
                "llm_failed": False,
            }

            # Invoke workflow.
            workflow = get_workflow(case.iteration)
            final_state = workflow.invoke(initial_state)

            if final_state.get("llm_failed"):
                logger.warning("LLM failure in step %s", step.stepId)

        return final_state or {}

    finally:
        # Always restore ledger and graph on exit.
        restore_ledger_store(ledger_snapshot)
        reset_graph()
        logger.debug("Restored ledger and graph for case %s", case.caseId)


def _articles_to_dicts(articles: List[Any]) -> List[Dict[str, Any]]:
    """Convert GoldenArticle Pydantic models to plain dicts for workflow injection."""
    result = []
    for article in articles:
        if hasattr(article, "model_dump"):
            # Pydantic v2
            result.append(article.model_dump(exclude_none=True))
        elif hasattr(article, "dict"):
            # Pydantic v1
            result.append(article.dict(exclude_none=True))
        else:
            # Already a dict
            result.append(article)
    return result
