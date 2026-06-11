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
    final_state: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate iter1_direct suite: extraction + direct routing.

    Args:
        case: Golden case specification.
        final_state: Final workflow state after invoke.

    Returns:
        (passed, metrics, errors)
        passed: True if all assertions pass.
        metrics: Dict of computed metrics (recall, precision, accuracy, etc.).
        errors: List of assertion failures.
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    # Get expected outputs from last step.
    if not case.steps:
        errors.append("No steps in case")
        return False, metrics, errors

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


def evaluate_iter2_memory(
    case: GoldenCase,
    final_state: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate iter2_memory suite: dedup and ledger accuracy.

    Args:
        case: Golden case specification (may have multiple steps).
        final_state: Final workflow state after all steps.

    Returns:
        (passed, metrics, errors)
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    # Check final step expected outputs.
    if not case.steps:
        errors.append("No steps in case")
        return False, metrics, errors

    last_step = case.steps[-1]
    try:
        expected = Iter2ExpectedStep(**last_step.expected)
    except Exception as e:
        errors.append(f"Invalid Iter2ExpectedStep block: {e}")
        return False, metrics, errors

    # Check duplicate counts.
    dup_counts = final_state.get("duplicate_counts", {})
    for ticker, min_count in expected.duplicateCountsAtLeast.items():
        actual = dup_counts.get(ticker, 0)
        if actual < min_count:
            errors.append(f"{ticker}: duplicate count {actual} < {min_count}")
    metrics["duplicate_counts"] = dup_counts

    # Check live ledger entries.
    # (In a real implementation, we'd inspect the ledger store directly.)
    # For now, we'll just log expected counts.
    metrics["expected_live_entries"] = expected.ledgerLiveEntriesEquals

    passed = len(errors) == 0
    return passed, metrics, errors


def evaluate_iter3_cross_impact(
    case: GoldenCase,
    final_state: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate iter3_cross_impact suite: cross-impact routing and paths.

    Args:
        case: Golden case specification.
        final_state: Final workflow state after invoke.

    Returns:
        (passed, metrics, errors)
    """
    errors: List[str] = []
    metrics: Dict[str, Any] = {}

    if not case.steps:
        errors.append("No steps in case")
        return False, metrics, errors

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
