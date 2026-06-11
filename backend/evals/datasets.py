"""Phoenix dataset management for golden case eval suite.

This module syncs golden cases from JSON files to Phoenix datasets,
enabling side-by-side experiment comparison in the Phoenix UI.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.logging import get_logger

logger = get_logger(__name__)


def load_golden_cases_as_dicts(dataset_dir: Path) -> List[Dict[str, Any]]:
    """Load golden cases from directory as plain dicts (for Phoenix dataset creation)."""
    cases = []
    json_files = sorted(dataset_dir.glob("*.json"))
    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)
            cases.append(data)
            logger.debug("Loaded golden case: %s", data.get("caseId"))
        except Exception as e:
            logger.error("Failed to load %s: %s", json_file, e)
    return cases


def sync_to_phoenix_dataset(
    dataset_name: str,
    cases: List[Dict[str, Any]],
    phoenix_client: Optional[Any] = None,
) -> Optional[str]:
    """Sync golden cases to Phoenix dataset.

    Args:
        dataset_name: Phoenix dataset name (e.g., "iter1_direct_golden").
        cases: List of golden cases (dicts).
        phoenix_client: Phoenix client instance (if None, Phoenix unavailable).

    Returns:
        Dataset ID if successful, None if Phoenix unavailable or error.

    Note: Requires Phoenix server running and arize-phoenix-client installed.
          Deferred implementation until golden dataset repo is available.
    """
    if not phoenix_client:
        logger.info("Phoenix unavailable; skipping dataset sync for %s", dataset_name)
        return None

    try:
        # TODO: Implement Phoenix dataset creation/sync
        # dataset = phoenix_client.datasets.create_dataset(
        #     name=dataset_name,
        #     examples=[
        #         {
        #             "input": case.get("steps", [{}])[0].get("articles", []),
        #             "expected_output": case.get("steps", [{}])[0].get("expected", {}),
        #             "metadata": {"caseId": case.get("caseId"), "suite": case.get("suite")},
        #         }
        #         for case in cases
        #     ],
        # )
        # logger.info("Synced %d cases to Phoenix dataset: %s (ID: %s)", len(cases), dataset_name, dataset.id)
        # return dataset.id
        logger.warning("Phoenix dataset sync not yet implemented")
        return None
    except Exception as e:
        logger.error("Failed to sync dataset %s to Phoenix: %s", dataset_name, e)
        return None


def create_experiment_name(iteration: int, variant: str, git_sha: Optional[str] = None) -> str:
    """Create standardized Phoenix experiment name.

    Args:
        iteration: Iteration number (1, 2, or 3).
        variant: Model/prompt variant (e.g., "gpt4_v1", "claude_baseline").
        git_sha: Git commit SHA for traceability.

    Returns:
        Experiment name suitable for Phoenix.
    """
    base = f"iter{iteration}_{variant}"
    if git_sha:
        return f"{base}_{git_sha[:8]}"
    return base


def should_upload_to_phoenix() -> bool:
    """Check if Phoenix is available and should be used for this run.

    Returns:
        True if Phoenix server is reachable and client is installed.
    """
    try:
        import socket
        from backend.core.config import PHOENIX_PORT

        with socket.create_connection(("127.0.0.1", PHOENIX_PORT), timeout=0.25):
            return True
    except OSError:
        return False
