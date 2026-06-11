"""Eval suite definition for iter3_cross_impact (cross-impact routing + paths)."""
from dataclasses import dataclass


@dataclass
class Iter3SuiteConfig:
    """Configuration for iter3_cross_impact eval suite."""
    suite_name: str = "iter3_cross_impact"
    description: str = "Cross-Impact Routing & Path Validity"
    task: str = "Test multi-hop exposure-graph routing and path validity"

    # Pass criteria.
    min_indirect_recall: float = 0.85  # Must find indirect routes for target tickers
    min_indirect_precision: float = 0.85  # Avoid false-butterfly routes
    max_false_butterfly_rate: float = 0.05  # Hard gate: very few multi-hop false positives
    path_validity_required: bool = True  # All paths must be valid graph structures

    # Evaluators.
    deterministic_evaluators: list = None  # indirect_routing_accuracy, path_validity, false_butterfly_detection
    llm_judges: list = None  # path_explanation_consistency, route_relevance

    metric_keys: list = None

    def __post_init__(self):
        if self.deterministic_evaluators is None:
            self.deterministic_evaluators = ["indirect_routing_accuracy", "path_validity"]
        if self.llm_judges is None:
            self.llm_judges = ["path_consistency", "route_relevance"]
        if self.metric_keys is None:
            self.metric_keys = ["total_indirect_routes", "unique_indirect_tickers", "false_butterfly_count"]


config = Iter3SuiteConfig()
