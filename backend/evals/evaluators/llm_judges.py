"""LLM-as-judge evaluators for quality evals requiring semantic understanding.

These evaluators use LLM calls to assess faithfulness, coherence, grounding, and
path consistency. Used for deep analysis (not in CI without API keys).
"""
from typing import Any, Dict, List, Tuple, Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


def evaluate_faithfulness(
    synthesis: Dict[str, Any],
    articles: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate whether synthesis claims are faithful to source articles.

    Args:
        synthesis: Per-ticker synthesis output.
        articles: Source articles that were used.

    Returns:
        (passed, metrics, errors)

    Note: Requires LLM API keys. Deferred to later implementation.
    """
    metrics: Dict[str, Any] = {}
    errors: List[str] = []

    # TODO: Implement with LLM judge
    logger.warning("Faithfulness evaluation not yet implemented")
    metrics["status"] = "not_implemented"

    return True, metrics, errors


def evaluate_coherence(
    synthesis: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate whether synthesis is coherent, well-structured, and readable.

    Args:
        synthesis: Per-ticker synthesis output.

    Returns:
        (passed, metrics, errors)

    Note: Requires LLM API keys. Deferred to later implementation.
    """
    metrics: Dict[str, Any] = {}
    errors: List[str] = []

    # TODO: Implement with LLM judge
    logger.warning("Coherence evaluation not yet implemented")
    metrics["status"] = "not_implemented"

    return True, metrics, errors


def evaluate_compliance(
    synthesis: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate compliance: no trading advice, proper disclaimers, no over-claims.

    Args:
        synthesis: Per-ticker synthesis output.

    Returns:
        (passed, metrics, errors)
    """
    metrics: Dict[str, Any] = {}
    errors: List[str] = []

    # Check for basic compliance red flags in the synthesis text.
    summary = synthesis.get("situationSummary", "").lower()
    headline = synthesis.get("summaryHeadline", "").lower()

    # Warn on trading-like language (non-exhaustive list).
    trading_phrases = [
        "buy", "sell", "hold", "short", "long", "recommend", "should invest",
        "bull market", "bear market", "profitable trade", "quick profit"
    ]

    found_trading = []
    for phrase in trading_phrases:
        if phrase in summary or phrase in headline:
            found_trading.append(phrase)

    if found_trading:
        errors.append(f"Possible trading advice detected: {found_trading}")

    # Check for disclaimer presence.
    disclaimer_phrases = ["market", "may not", "uncertain", "risk", "no guarantee"]
    found_disclaimers = sum(1 for phrase in disclaimer_phrases if phrase in summary)
    metrics["disclaimer_phrases"] = found_disclaimers

    passed = len(errors) == 0
    return passed, metrics, errors


def evaluate_path_consistency(
    synthesis: Dict[str, Any],
    impact_paths: List[List[str]],
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Evaluate that synthesis explanations stay within supplied impact paths.

    Args:
        synthesis: Per-ticker synthesis output.
        impact_paths: Valid impact paths for this ticker (e.g., [["AAPL", "supply_chain", "TSMC"]]).

    Returns:
        (passed, metrics, errors)

    Note: Requires semantic understanding. Deferred to LLM judge.
    """
    metrics: Dict[str, Any] = {}
    errors: List[str] = []

    # TODO: Implement with LLM judge to verify path mentions stay in bounds
    logger.warning("Path consistency evaluation not yet implemented")
    metrics["status"] = "not_implemented"

    return True, metrics, errors
