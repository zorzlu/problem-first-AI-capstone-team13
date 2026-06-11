"""Deterministic evaluators for golden case assertions.

These evaluators check structural invariants (routing precision/recall, event counts,
path validity, compliance regex) without LLM calls. Used as gates in CI and for
debugging evaluation failures.
"""
from typing import Any, Dict, List, Tuple
from backend.evals.golden_schema import GoldenCase, Iter1Expected, Iter2ExpectedStep, Iter3Expected
from backend.core.logging import get_logger

logger = get_logger(__name__)


def evaluate_iter1_direct(
    case: GoldenCase,
    step_states: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate iter1_direct suite: extraction + direct routing.

    Args:
        case: Golden case specification.
        step_states: Per-step final workflow states (iter1 cases have one step).

    Returns:
        (passed, metrics, errors)
        passed: True if all assertions pass.
        metrics: Dict of computed metrics (recall, precision, accuracy, etc.).
        errors: List of assertion failures.
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    # Get expected outputs from last step.
    if not case.steps or not step_states:
        errors.append("No steps in case")
        return False, metrics, errors

    final_state = step_states[-1]
    last_step = case.steps[-1]
    try:
        expected = Iter1Expected(**last_step.expected)
    except Exception as e:
        errors.append(f"Invalid Iter1Expected block: {e}")
        return False, metrics, errors

    # Extract direct routes from routed_candidates.
    routed = final_state.get("routed_candidates", [])
    direct_routes = [r["ticker"] for r in routed if r.get("relationshipType") == "direct"]
    direct_routes = list(set(direct_routes))  # unique
    metrics["direct_routes"] = direct_routes

    # Check recall: all expected routes should be present.
    expected_set = set(expected.directRoutes)
    routed_set = set(direct_routes)
    recall = len(expected_set & routed_set) / len(expected_set) if expected_set else 1.0
    metrics["recall"] = recall
    if recall < 1.0:
        missing = expected_set - routed_set
        errors.append(f"Recall < 1.0: missing routes {missing}")

    # Check precision: no forbidden routes should be routed.
    forbidden_set = set(expected.forbiddenRoutes)
    forbidden_routed = forbidden_set & routed_set
    if forbidden_routed:
        errors.append(f"False positives (forbidden routes routed): {forbidden_routed}")
    metrics["forbidden_routed"] = list(forbidden_routed)

    # Check synthesis count.
    syntheses = final_state.get("ticker_syntheses", {})
    for ticker in expected.requiredSyntheses:
        if ticker not in syntheses:
            errors.append(f"Missing synthesis for {ticker}")
    metrics["syntheses_count"] = len(syntheses)

    passed = len(errors) == 0
    return passed, metrics, errors


def _article_decisions(state: Dict[str, Any]) -> Dict[str, List[str]]:
    """Map articleId -> ledger decisions of its surviving routed candidates.

    The ledger node drops duplicate candidates from routed_candidates, so an article
    whose only candidates were duplicates maps to an empty list here; duplicates are
    instead visible in duplicate_counts.
    """
    # Mock extraction stamps sourceArticleIds=[id]; LLM extraction stamps articleId.
    event_article = {}
    for e in state.get("canonical_events", []):
        article_id = e.get("articleId") or (e.get("sourceArticleIds") or [None])[0]
        event_article[e.get("eventId")] = article_id
    decisions: Dict[str, List[str]] = {}
    for cand in state.get("routed_candidates", []):
        article_id = event_article.get(cand.get("eventId"))
        if article_id is None:
            continue
        decisions.setdefault(article_id, []).append(cand.get("ledgerDecision"))
    return decisions


def evaluate_iter2_memory(
    case: GoldenCase,
    step_states: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate iter2_memory suite: dedup and ledger accuracy, asserted per step.

    Each step's expected block is checked against that step's final state:
    - ledgerDecisions: "new"/"update" require a surviving routed candidate with that
      decision for the article; "duplicate" requires the article's candidates to have
      been dropped AND the step to record at least one duplicate.
    - duplicateCountsAtLeast: per-ticker minimum duplicate counts for the step.

    Args:
        case: Golden case specification (may have multiple steps).
        step_states: Per-step final workflow states from the harness.

    Returns:
        (passed, metrics, errors)
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    if not case.steps:
        errors.append("No steps in case")
        return False, metrics, errors
    if len(step_states) != len(case.steps):
        errors.append(f"Expected {len(case.steps)} step states, got {len(step_states)}")
        return False, metrics, errors

    for step, state in zip(case.steps, step_states):
        try:
            expected = Iter2ExpectedStep(**step.expected)
        except Exception as e:
            errors.append(f"[{step.stepId}] Invalid Iter2ExpectedStep block: {e}")
            continue

        dup_counts = state.get("duplicate_counts", {})
        decisions_by_article = _article_decisions(state)
        metrics[f"{step.stepId}.duplicate_counts"] = dup_counts
        metrics[f"{step.stepId}.decisions"] = decisions_by_article

        # Per-article ledger decision assertions.
        for article_id, expected_decision in expected.ledgerDecisions.items():
            actual = decisions_by_article.get(article_id, [])
            if expected_decision == "duplicate":
                if actual:
                    errors.append(
                        f"[{step.stepId}] {article_id}: expected duplicate (dropped), "
                        f"but survived with decisions {actual}"
                    )
                elif sum(dup_counts.values()) < 1:
                    errors.append(
                        f"[{step.stepId}] {article_id}: expected duplicate, but no "
                        f"duplicates were recorded this step (article may not have routed at all)"
                    )
            else:
                if expected_decision not in actual:
                    errors.append(
                        f"[{step.stepId}] {article_id}: expected decision "
                        f"'{expected_decision}', got {actual or 'none (not routed or dropped)'}"
                    )

        # Per-ticker duplicate count floors.
        for ticker, min_count in expected.duplicateCountsAtLeast.items():
            actual_count = dup_counts.get(ticker, 0)
            if actual_count < min_count:
                errors.append(f"[{step.stepId}] {ticker}: duplicate count {actual_count} < {min_count}")

    passed = len(errors) == 0
    return passed, metrics, errors


def evaluate_iter3_cross_impact(
    case: GoldenCase,
    step_states: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate iter3_cross_impact suite: cross-impact routing and paths.

    Args:
        case: Golden case specification.
        step_states: Per-step final workflow states (iter3 cases have one step).

    Returns:
        (passed, metrics, errors)
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    if not case.steps or not step_states:
        errors.append("No steps in case")
        return False, metrics, errors

    final_state = step_states[-1]
    last_step = case.steps[-1]
    try:
        expected = Iter3Expected(**last_step.expected)
    except Exception as e:
        errors.append(f"Invalid Iter3Expected block: {e}")
        return False, metrics, errors

    routed = final_state.get("routed_candidates", [])

    # Check expected indirect routes.
    for route_exp in expected.indirectRoutes:
        ticker = route_exp.ticker
        ticker_routes = [r for r in routed if r.get("ticker") == ticker and r.get("relationshipType") == "indirect"]
        if not ticker_routes:
            errors.append(f"No indirect routes for {ticker}")
            continue

        # Check path requirements.
        for route in ticker_routes:
            path = route.get("impactPath", [])
            if route_exp.pathMustIncludeAnyOf:
                if not any(node in path for node in route_exp.pathMustIncludeAnyOf):
                    errors.append(f"{ticker} path missing required nodes {route_exp.pathMustIncludeAnyOf}: {path}")
            if route_exp.minPathConfidence > 0:
                confidence = route.get("pathConfidence", 0)
                if confidence < route_exp.minPathConfidence:
                    errors.append(f"{ticker} path confidence {confidence} < {route_exp.minPathConfidence}")

    # Check forbidden routes.
    indirect_tickers = set(r.get("ticker") for r in routed if r.get("relationshipType") == "indirect")
    for forbidden in expected.forbiddenIndirectRoutes:
        ticker = forbidden.get("ticker")
        if ticker in indirect_tickers:
            errors.append(f"Forbidden indirect route to {ticker}: {forbidden.get('reason', 'no reason given')}")

    metrics["total_indirect_routes"] = len([r for r in routed if r.get("relationshipType") == "indirect"])
    metrics["unique_indirect_tickers"] = len(indirect_tickers)

    passed = len(errors) == 0
    return passed, metrics, errors


def evaluate_judge_calibration(
    case: GoldenCase,
    judge_verdict: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate judge_calibration suite: judge accuracy.

    Args:
        case: Golden case specification with judge labels.
        judge_verdict: Judge output (passes, groundingPassed, advicePassed, pathPassed).

    Returns:
        (passed, metrics, errors)
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    if not case.steps or not case.labels:
        errors.append("Judge calibration case must have steps and labels")
        return False, metrics, errors

    # Labels should contain expected judge verdict.
    try:
        from backend.evals.golden_schema import JudgeCalibrationExpected
        expected = JudgeCalibrationExpected(**case.steps[0].expected)
        labels = expected.labels
    except Exception as e:
        errors.append(f"Invalid JudgeCalibrationExpected: {e}")
        return False, metrics, errors

    # Compare verdict fields.
    if judge_verdict.get("passes") != labels.passes:
        errors.append(f"Judge passes mismatch: {judge_verdict.get('passes')} != {labels.passes}")
    if judge_verdict.get("groundingPassed") != labels.groundingPassed:
        errors.append(f"Grounding mismatch: {judge_verdict.get('groundingPassed')} != {labels.groundingPassed}")
    if judge_verdict.get("advicePassed") != labels.advicePassed:
        errors.append(f"Advice mismatch: {judge_verdict.get('advicePassed')} != {labels.advicePassed}")
    if judge_verdict.get("pathPassed") != labels.pathPassed:
        errors.append(f"Path mismatch: {judge_verdict.get('pathPassed')} != {labels.pathPassed}")

    metrics["judge_accuracy"] = 1.0 if len(errors) == 0 else 0.0

    passed = len(errors) == 0
    return passed, metrics, errors
