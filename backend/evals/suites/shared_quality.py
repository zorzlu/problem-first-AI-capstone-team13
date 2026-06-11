"""Shared quality checks across all suites (compliance, faithfulness, coherence)."""
from dataclasses import dataclass


@dataclass
class SharedQualitySuiteConfig:
    """Configuration for shared_quality eval suite."""
    suite_name: str = "shared_quality"
    description: str = "Output Safety & Quality"
    task: str = "Test compliance (no trading advice), faithfulness (grounded in sources), coherence (well-written), path bounds"

    # Pass criteria.
    compliance_required: bool = True  # Must pass compliance regex gate
    min_faithfulness: float = 0.9  # Claims grounded in source text
    min_coherence: float = 0.85  # Well-structured synthesis
    path_bounds_required: bool = True  # Indirect explanations stay in supplied paths

    # Evaluators.
    deterministic_evaluators: list = None  # compliance_check
    llm_judges: list = None  # faithfulness, coherence, path_consistency

    metric_keys: list = None

    def __post_init__(self):
        if self.deterministic_evaluators is None:
            self.deterministic_evaluators = ["compliance_gate"]
        if self.llm_judges is None:
            self.llm_judges = ["faithfulness", "coherence", "path_consistency"]
        if self.metric_keys is None:
            self.metric_keys = ["compliance_passed", "disclaimer_phrases", "trading_phrases_found"]


config = SharedQualitySuiteConfig()
