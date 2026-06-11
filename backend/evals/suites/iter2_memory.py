"""Eval suite definition for iter2_memory (dedup + ledger)."""
from dataclasses import dataclass


@dataclass
class Iter2SuiteConfig:
    """Configuration for iter2_memory eval suite."""
    suite_name: str = "iter2_memory"
    description: str = "Catalyst Dedup & Ledger Management"
    task: str = "Test dedup (new/update/duplicate detection) and catalyst ledger accuracy across multi-step runs"

    # Pass criteria.
    min_dedup_accuracy: float = 0.9  # Decision accuracy (new/update/dup)
    max_missed_update_rate: float = 0.1  # Actual updates marked as dup
    max_over_merge_rate: float = 0.0  # No over-merging allowed
    max_under_merge_rate: float = 0.1  # Some false-new is acceptable

    # Evaluators.
    deterministic_evaluators: list = None  # ledger_dedup_accuracy, duplicate_counts
    llm_judges: list = None  # update_summary_quality

    metric_keys: list = None

    def __post_init__(self):
        if self.deterministic_evaluators is None:
            self.deterministic_evaluators = ["ledger_dedup_accuracy", "duplicate_counts"]
        if self.llm_judges is None:
            self.llm_judges = ["update_quality"]
        if self.metric_keys is None:
            self.metric_keys = ["duplicate_counts", "expected_live_entries"]


config = Iter2SuiteConfig()
