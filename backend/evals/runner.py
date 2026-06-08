"""Run replay eval sets and emit Phoenix trace-friendly spans.

This is intentionally separate from unit tests: unit tests mock model calls and check
implementation details, while eval sets exercise the compiled workflows end-to-end and
grade product-level expectations. Start Phoenix first if you want these runs visible
in the dashboard, then run:

    uv run --project backend --frozen python -m backend.evals.runner --eval-set replay_scenarios
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from backend.core.config import init_phoenix
from backend.iterations import get_workflow
from backend.memory import clear_ledger, get_ledger, is_embedding_active


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EVAL_SET_DIR = BACKEND_ROOT / "evals" / "sets"
EVAL_RUN_DIR = BACKEND_ROOT / "state" / "eval_runs"


def _load_eval_set(name: str) -> Dict[str, Any]:
    path = EVAL_SET_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Eval set not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _initial_state(step: Dict[str, Any], watchlist: List[str]) -> Dict[str, Any]:
    return {
        "iteration": step["iteration"],
        "watchlist": watchlist,
        "scenario_id": step["scenario_id"],
        "simulated_now": step.get("simulated_now", "2026-05-28T17:25:00Z"),
        "articles": [],
        "canonical_events": [],
        "routed_candidates": [],
        "ticker_buckets": {},
        "ticker_syntheses": {},
        "duplicate_counts": {},
        "ingestion_metadata": {},
        "llm_failed": False,
    }


def _ledger_metrics(iteration: int) -> Dict[str, Any]:
    ledger = get_ledger(iteration)
    by_ticker: Dict[str, int] = {}
    embedded = 0
    for entry in ledger:
        ticker = entry.get("ticker", "UNKNOWN")
        by_ticker[ticker] = by_ticker.get(ticker, 0) + 1
        if entry.get("embedding_vec"):
            embedded += 1
    return {
        "ledgerLiveEntries": len(ledger),
        "ledgerEntriesByTicker": by_ticker,
        "ledgerEmbeddedEntries": embedded,
        "embeddingProvider": "local_fastembed" if is_embedding_active() else "local_lexical",
    }


def _grade(step: Dict[str, Any], final_state: Dict[str, Any]) -> Dict[str, Any]:
    assertions = step.get("assertions", {})
    failures: List[str] = []
    routed = final_state.get("routed_candidates", [])
    syntheses = final_state.get("ticker_syntheses", {})
    duplicate_counts = final_state.get("duplicate_counts", {})
    ledger = _ledger_metrics(step["iteration"])

    min_events = assertions.get("minCanonicalEvents")
    if min_events is not None and len(final_state.get("canonical_events", [])) < min_events:
        failures.append(f"expected at least {min_events} canonical events")

    for ticker in assertions.get("requiredTickerSyntheses", []):
        if ticker not in syntheses:
            failures.append(f"missing synthesis for {ticker}")

    for ticker in assertions.get("requiredDirectRoutes", []):
        if not any(r.get("ticker") == ticker and r.get("relationshipType") == "direct" for r in routed):
            failures.append(f"missing direct route for {ticker}")

    for ticker in assertions.get("requiredIndirectRoutes", []):
        if not any(r.get("ticker") == ticker and r.get("relationshipType") == "indirect" for r in routed):
            failures.append(f"missing indirect route for {ticker}")

    for ticker, minimum in assertions.get("duplicateCountsAtLeast", {}).items():
        if duplicate_counts.get(ticker, 0) < minimum:
            failures.append(f"expected duplicate count for {ticker} >= {minimum}")

    ledger_total_equals = assertions.get("ledgerLiveTotalEquals")
    if ledger_total_equals is not None and ledger["ledgerLiveEntries"] != ledger_total_equals:
        failures.append(f"expected live ledger total == {ledger_total_equals}")

    for ticker, minimum in assertions.get("ledgerLiveEntriesAtLeast", {}).items():
        if ledger["ledgerEntriesByTicker"].get(ticker, 0) < minimum:
            failures.append(f"expected live ledger entries for {ticker} >= {minimum}")

    for ticker, expected in assertions.get("ledgerLiveEntriesEquals", {}).items():
        if ledger["ledgerEntriesByTicker"].get(ticker, 0) != expected:
            failures.append(f"expected live ledger entries for {ticker} == {expected}")

    if final_state.get("llm_failed"):
        failures.append(f"workflow reported llm_failed: {final_state.get('failure_reason', 'unknown')}")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "articles": len(final_state.get("articles", [])),
            "canonicalEvents": len(final_state.get("canonical_events", [])),
            "routedCandidates": len(routed),
            "tickerSyntheses": len(syntheses),
            "duplicateCounts": duplicate_counts,
            **ledger,
        },
    }


def _case_steps(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "steps" in case:
        return case["steps"]
    return [{
        "id": case["id"],
        "iteration": case["iteration"],
        "scenario_id": case["scenario_id"],
        "simulated_now": case.get("simulated_now", "2026-05-28T17:25:00Z"),
        "assertions": case.get("assertions", {}),
    }]


def run_eval_set(name: str, trace_to_phoenix: bool) -> Dict[str, Any]:
    if trace_to_phoenix:
        init_phoenix()

    tracer = None
    if trace_to_phoenix:
        try:
            from opentelemetry import trace as otel_trace
            tracer = otel_trace.get_tracer("cross-impact-catalysts-evals")
        except Exception:
            tracer = None

    eval_set = _load_eval_set(name)
    watchlist = eval_set.get("watchlist", ["AAPL", "MSFT", "NVDA", "TSM", "DAL"])
    case_results = []

    for case in eval_set.get("cases", []):
        if case.get("clearLedgerBeforeCase", True):
            clear_ledger()

        def _run_case() -> Dict[str, Any]:
            step_results = []
            for step in _case_steps(case):
                initial_state = _initial_state(step, watchlist)
                final_state = get_workflow(step["iteration"]).invoke(initial_state)
                grade = _grade(step, final_state)
                step_results.append({
                    "id": step["id"],
                    "iteration": step["iteration"],
                    "scenarioId": step["scenario_id"],
                    **grade,
                })
            failures = [
                f"{step_result['id']}: {failure}"
                for step_result in step_results
                for failure in step_result["failures"]
            ]
            return {
                "id": case["id"],
                "passed": not failures,
                "failures": failures,
                "steps": step_results,
            }

        if tracer:
            with tracer.start_as_current_span(f"eval:{name}:{case['id']}") as span:
                span.set_attribute("eval.set", name)
                span.set_attribute("eval.case_id", case["id"])
                result = _run_case()
                span.set_attribute("eval.passed", result["passed"])
                span.set_attribute("eval.failures", json.dumps(result["failures"]))
                span.set_attribute("eval.steps", json.dumps(result["steps"]))
        else:
            result = _run_case()

        case_results.append(result)

    summary = {
        "evalSet": name,
        "ranAt": datetime.now(timezone.utc).isoformat(),
        "passed": all(r["passed"] for r in case_results),
        "cases": case_results,
    }
    EVAL_RUN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVAL_RUN_DIR / f"{name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["outputPath"] = str(out_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a configured workflow eval set.")
    parser.add_argument("--eval-set", default="replay_scenarios")
    parser.add_argument("--no-phoenix", action="store_true", help="Do not initialize Phoenix tracing for the eval run.")
    args = parser.parse_args()

    summary = run_eval_set(args.eval_set, trace_to_phoenix=not args.no_phoenix)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
