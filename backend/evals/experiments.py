"""Phoenix experiments CLI runner for golden case evals.

This module runs golden cases through eval suites and generates Phoenix experiments.
Golden cases live in backend/evals/sets/golden_examples/{suite_name}/. Each case is
a JSON file conforming to the golden_schema.

Usage:
    uv run --project backend python -m backend.evals.experiments \
        --suite iter1_direct \
        --dataset-dir backend/evals/sets/golden_examples/iter1 \
        --experiment-name "smoke_test_run"
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from backend.core.logging import get_logger, configure_logging
from backend.evals.golden_schema import GoldenCase, EvalResult, EvalReport
from backend.evals.harness import run_golden_case
from backend.evals.evaluators.deterministic import (
    evaluate_iter1_direct,
    evaluate_iter2_memory,
    evaluate_iter3_cross_impact,
    evaluate_judge_calibration,
)

logger = get_logger(__name__)


def load_golden_cases(dataset_dir: Path) -> List[GoldenCase]:
    """Load all golden cases from a directory of JSON files."""
    cases = []
    json_files = sorted(dataset_dir.glob("*.json"))
    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)
            case = GoldenCase(**data)
            cases.append(case)
            logger.debug("Loaded golden case: %s", case.caseId)
        except Exception as e:
            logger.error("Failed to load %s: %s", json_file, e)
    return cases


def run_experiment(
    suite_name: str,
    cases: List[GoldenCase],
    experiment_name: str,
) -> EvalReport:
    """Run eval suite on golden cases.

    Args:
        suite_name: Suite name (iter1_direct, iter2_memory, iter3_cross_impact, judge_calibration).
        cases: List of golden cases to evaluate.
        experiment_name: Experiment name for logging/Phoenix.

    Returns:
        EvalReport with per-case results and summary.
    """
    logger.info("Starting experiment: %s (suite: %s, %d cases)", experiment_name, suite_name, len(cases))

    results: List[EvalResult] = []
    passed_count = 0

    # Select evaluator based on suite.
    if suite_name == "iter1_direct":
        evaluator = evaluate_iter1_direct
    elif suite_name == "iter2_memory":
        evaluator = evaluate_iter2_memory
    elif suite_name == "iter3_cross_impact":
        evaluator = evaluate_iter3_cross_impact
    elif suite_name == "judge_calibration":
        evaluator = evaluate_judge_calibration
    else:
        raise ValueError(f"Unknown suite: {suite_name}")

    # Run each case.
    for case in cases:
        try:
            logger.info("Running case: %s", case.caseId)
            final_state = run_golden_case(case)

            # Evaluate outputs.
            passed, metrics, errors = evaluator(case, final_state)

            if passed:
                passed_count += 1

            result = EvalResult(
                caseId=case.caseId,
                suite=suite_name,
                passed=passed,
                metrics=metrics,
                errors=errors,
            )
            results.append(result)

            status = "PASS" if passed else "FAIL"
            logger.info("%s: %s (errors: %d)", status, case.caseId, len(errors))
            for error in errors:
                logger.warning("  - %s", error)

        except Exception as e:
            logger.exception("Exception running case %s: %s", case.caseId, e)
            result = EvalResult(
                caseId=case.caseId,
                suite=suite_name,
                passed=False,
                metrics={},
                errors=[f"Exception: {str(e)}"],
            )
            results.append(result)

    # Generate report.
    report = EvalReport(
        suite=suite_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        totalCases=len(cases),
        passedCases=passed_count,
        failedCases=len(cases) - passed_count,
        results=results,
        notes=f"Experiment: {experiment_name}",
    )

    return report


def print_report(report: EvalReport) -> None:
    """Pretty-print eval report."""
    print()
    print("=" * 80)
    print(f"EVAL REPORT: {report.suite}")
    print("=" * 80)
    print(f"Timestamp: {report.timestamp}")
    print(f"Total cases: {report.totalCases}")
    print(f"Passed: {report.passedCases}/{report.totalCases}")
    print(f"Failed: {report.failedCases}/{report.totalCases}")
    print()

    for result in report.results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"{status}: {result.caseId}")
        if result.errors:
            for error in result.errors:
                print(f"  - {error}")
        if result.metrics:
            for key, value in result.metrics.items():
                print(f"  {key}: {value}")
    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Run golden case eval experiments")
    parser.add_argument("--suite", required=True, help="Suite name (iter1_direct, iter2_memory, etc.)")
    parser.add_argument("--dataset-dir", required=True, help="Directory with golden case JSON files")
    parser.add_argument("--experiment-name", default="default", help="Experiment name for logging")

    args = parser.parse_args()

    configure_logging()

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.exists():
        logger.error("Dataset directory not found: %s", dataset_dir)
        sys.exit(1)

    # Load and run.
    cases = load_golden_cases(dataset_dir)
    if not cases:
        logger.warning("No golden cases found in %s", dataset_dir)
        sys.exit(0)

    report = run_experiment(args.suite, cases, args.experiment_name)
    print_report(report)

    # Exit with non-zero if any cases failed (for CI gating).
    if report.failedCases > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
