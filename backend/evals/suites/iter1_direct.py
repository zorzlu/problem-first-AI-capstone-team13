"""Eval suite definition for iter1_direct (extraction + direct routing)."""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Iter1SuiteConfig:
    """Configuration for iter1_direct eval suite."""
    suite_name: str = "iter1_direct"
    description: str = "Extraction + Direct Routing"
    task: str = "Test LLM extraction of canonical events and direct routing to mentioned tickers"

    # Pass criteria (thresholds for success).
    min_recall: float = 1.0  # Must route all expected tickers
    min_precision: float = 0.95  # Allow very few false positives
    min_accuracy: float = 0.85  # Event type accuracy

    # Evaluators used.
    deterministic_evaluators: list = None  # evaluate_iter1_direct
    llm_judges: list = None  # faithfulness, coherence

    # Metrics reported.
    metric_keys: list = None

    def __post_init__(self):
        if self.deterministic_evaluators is None:
            self.deterministic_evaluators = ["extract_and_route_accuracy"]
        if self.llm_judges is None:
            self.llm_judges = ["event_faithfulness", "summary_coherence"]
        if self.metric_keys is None:
            self.metric_keys = ["recall", "precision", "forbidden_routed", "syntheses_count"]


config = Iter1SuiteConfig()
