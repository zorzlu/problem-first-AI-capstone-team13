"""Eval suite for judge calibration (judge accuracy measurement)."""
from dataclasses import dataclass


@dataclass
class JudgeCalibrationSuiteConfig:
    """Configuration for judge_calibration eval suite."""
    suite_name: str = "judge_calibration"
    description: str = "Judge Model Calibration"
    task: str = "Measure L3 judge accuracy on dimensions: grounding, advice, path validity; compare to human labels"

    # Pass criteria per dimension.
    max_grounding_fnr: float = 0.05  # False negative rate (incorrectly pass ungrounded claims)
    max_grounding_fpr: float = 0.15  # False positive rate (incorrectly fail grounded claims)
    max_advice_fnr: float = 0.05  # Fail to catch trading advice
    max_advice_fpr: float = 0.15  # Over-flag innocent language as advice
    max_path_fnr: float = 0.05  # Fail to catch out-of-bounds paths
    max_path_fpr: float = 0.15  # Over-flag valid paths

    # Evaluators.
    deterministic_evaluators: list = None  # judge_accuracy (per dimension)
    llm_judges: list = None  # none; judge IS the system

    metric_keys: list = None

    def __post_init__(self):
        if self.deterministic_evaluators is None:
            self.deterministic_evaluators = ["judge_accuracy"]
        if self.llm_judges is None:
            self.llm_judges = []  # Judge is the system being evaluated
        if self.metric_keys is None:
            self.metric_keys = ["judge_accuracy", "fnr_grounding", "fpr_grounding", "fnr_advice", "fpr_advice"]


config = JudgeCalibrationSuiteConfig()
