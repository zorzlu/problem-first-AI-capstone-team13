"""Offline routing-quality eval gate for cross-impact routing.

Complements ``backend.evals.runner`` (end-to-end scenario replay): this gate replays the
golden case set in ``sets/routing_quality.json`` directly against ``route_cross_impact``
and reports the two headline metrics from guardrails-and-evaluation.md §D.3 —
expected-target recall and false-butterfly rate. Exits non-zero on any failure so it can
gate CI/releases. It is deterministic and needs no API keys, Phoenix, or LLM calls.

Usage::

    uv run --project backend --frozen python -m backend.evals.routing_quality
    ... --graph path/to/graph.json   # explicit graph snapshot (default: state/graph.json, else seed)
    ... --json                       # machine-readable output
    ... --suggest-overrides          # remediation hints for failures
"""
import argparse
import copy
import json
import os
import sys
from typing import Any, Dict, List

from backend.graph import graph as graph_module
from backend.graph.seed import EXPOSURE_GRAPH

_HERE = os.path.dirname(__file__)
_DEFAULT_CASES = os.path.join(_HERE, "sets", "routing_quality.json")
_DEFAULT_GRAPH = os.path.join(os.path.dirname(_HERE), "state", "graph.json")

_STRENGTH_RANK = {"weak": 0, "strong": 1}


def _load_graph(graph_path: str) -> Dict[str, Any]:
    if os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        # storage.persistence wraps state as {"schemaVersion", "kind", "data"}; accept both.
        if isinstance(payload, dict) and "data" in payload and "nodes" not in payload:
            payload = payload["data"]
        return payload
    return copy.deepcopy(EXPOSURE_GRAPH)


def evaluate_case(case: Dict[str, Any], watchlist: List[str]) -> Dict[str, Any]:
    candidates = graph_module.route_cross_impact(case["event"], watchlist)
    by_ticker = {c["ticker"]: c for c in candidates}

    failures = []
    false_butterflies = []

    expected = case.get("expectedTickers", [])
    for ticker in expected:
        if ticker not in by_ticker:
            failures.append(f"expected {ticker} was not routed")

    for ticker in case.get("forbiddenTickers", []):
        if ticker in by_ticker:
            cand = by_ticker[ticker]
            failures.append(
                f"forbidden {ticker} was routed [{cand['pathStrength']}] via {' -> '.join(cand['impactPath'])}"
            )
            false_butterflies.append(cand)

    for ticker, max_strength in (case.get("maxStrength") or {}).items():
        cand = by_ticker.get(ticker)
        if cand and _STRENGTH_RANK.get(cand["pathStrength"], 1) > _STRENGTH_RANK.get(max_strength, 1):
            failures.append(
                f"{ticker} exceeded max strength '{max_strength}': "
                f"[{cand['pathStrength']}] via {' -> '.join(cand['impactPath'])}"
            )
            false_butterflies.append(cand)

    for ticker, required in (case.get("requireStrength") or {}).items():
        cand = by_ticker.get(ticker)
        if not cand:
            failures.append(f"{ticker} required [{required}] but was not routed")
        elif _STRENGTH_RANK.get(cand["pathStrength"], 0) < _STRENGTH_RANK.get(required, 0):
            failures.append(f"{ticker} required [{required}] but got [{cand['pathStrength']}]")

    return {
        "caseId": case["caseId"],
        "passed": not failures,
        "failures": failures,
        "expectedFound": len([t for t in expected if t in by_ticker]),
        "expectedTotal": len(expected),
        "falseButterflies": false_butterflies,
        "routed": [
            {
                "ticker": c["ticker"],
                "pathStrength": c["pathStrength"],
                "pathConfidence": c["pathConfidence"],
                "impactPath": c["impactPath"],
            }
            for c in sorted(candidates, key=lambda c: -c["pathConfidence"])
        ],
    }


def run_evals(cases_path: str = _DEFAULT_CASES, graph_path: str = _DEFAULT_GRAPH) -> Dict[str, Any]:
    with open(cases_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    with graph_module.graph_lock():
        previous_graph = copy.deepcopy(graph_module.get_graph())
    graph_module.set_graph(_load_graph(graph_path))
    try:
        watchlist = eval_set.get("watchlist", [])
        results = [evaluate_case(case, watchlist) for case in eval_set.get("cases", [])]
    finally:
        graph_module.set_graph(previous_graph)

    expected_total = sum(r["expectedTotal"] for r in results)
    expected_found = sum(r["expectedFound"] for r in results)
    butterfly_count = sum(len(r["falseButterflies"]) for r in results)

    return {
        "graphPath": graph_path if os.path.exists(graph_path) else "<seed>",
        "casesPassed": sum(1 for r in results if r["passed"]),
        "casesTotal": len(results),
        "expectedTargetRecall": (expected_found / expected_total) if expected_total else 1.0,
        "falseButterflyCount": butterfly_count,
        "results": results,
    }


def _print_report(report: Dict[str, Any], suggest_overrides: bool) -> None:
    print(f"Routing-quality eval — graph: {report['graphPath']}")
    print("=" * 72)
    for r in report["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['caseId']}")
        for c in r["routed"]:
            print(f"        {c['ticker']:6s} {c['pathConfidence']:.2f} [{c['pathStrength']}] {' -> '.join(c['impactPath'])}")
        for failure in r["failures"]:
            print(f"    !!  {failure}")
    print("=" * 72)
    print(f"Cases: {report['casesPassed']}/{report['casesTotal']} passed")
    print(f"Expected-target recall: {report['expectedTargetRecall']:.0%}")
    print(f"False butterflies: {report['falseButterflyCount']}")

    if suggest_overrides:
        suggestions = {
            (b["ticker"], b["impactPath"][0])
            for r in report["results"]
            for b in r["falseButterflies"]
            if b.get("impactPath")
        }
        if suggestions:
            print("\nRemediation suggestions (POST /api/graph/routing-overrides/suppress):")
            for ticker, anchor in sorted(suggestions):
                print(f'  {{"ticker": "{ticker}", "anchorName": "{anchor}", "reason": "flagged by routing eval"}}')


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline cross-impact routing-quality gate.")
    parser.add_argument("--cases", default=_DEFAULT_CASES, help="Path to the golden case set JSON.")
    parser.add_argument("--graph", default=_DEFAULT_GRAPH, help="Path to the exposure graph JSON (falls back to seed).")
    parser.add_argument("--json", action="store_true", help="Emit the full report as JSON.")
    parser.add_argument("--suggest-overrides", action="store_true", help="Print remediation override suggestions for failures.")
    args = parser.parse_args()

    report = run_evals(cases_path=args.cases, graph_path=args.graph)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report, suggest_overrides=args.suggest_overrides)
    return 0 if report["casesPassed"] == report["casesTotal"] else 1


if __name__ == "__main__":
    sys.exit(main())
