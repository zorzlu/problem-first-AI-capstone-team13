"""Split from the former monolithic run_tests.py. Run the whole suite with:
    python -m backend.tests.run_tests
which discovers every test_*.py module in this package.
"""
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from backend.iterations import get_workflow
from backend.iterations.contracts import (
    ExtractionResult,
    SynthesisOut,
    OutputSafetyJudgeOut,
)
# Internal helpers are imported directly from their owning modules rather than through the
# common facade, which only re-exports the public node API.
from backend.iterations.synthesis import (
    _normalize_synthesis_significance,
    _postprocess_synthesis,
)
from backend.iterations.guardrails import _relax_language_only_judge_failure
from backend.ingestion.scenarios import SCENARIOS
from backend.graph.seed import EXPOSURE_GRAPH
from backend.memory import clear_ledger


class TestModelSelection(unittest.TestCase):
    def test_gemini_step_falls_back_to_openai_with_openai_model(self):
        from backend.core import llm

        with patch.dict("os.environ", {}, clear=True), \
             patch("backend.core.llm.GEMINI_API_KEY", ""), \
             patch("backend.core.llm.OPENAI_API_KEY", "sk-test"), \
             patch("backend.core.llm.ANTHROPIC_API_KEY", ""), \
             patch("backend.core.llm.OPENAI_COMPATIBLE_BASE_URL", ""), \
             patch("backend.core.llm.LOCAL_LLM_BASE_URL", ""):
            spec = llm.resolve_model_spec("extraction")

        self.assertEqual(spec.provider, "openai")
        self.assertEqual(spec.model_id, "gpt-4.1-nano")

    def test_graph_expansion_falls_back_to_gemini_with_gemini_model(self):
        from backend.core import llm

        with patch.dict("os.environ", {}, clear=True), \
             patch("backend.core.llm.GEMINI_API_KEY", "gemini-key"), \
             patch("backend.core.llm.OPENAI_API_KEY", ""), \
             patch("backend.core.llm.ANTHROPIC_API_KEY", ""), \
             patch("backend.core.llm.OPENAI_COMPATIBLE_BASE_URL", ""), \
             patch("backend.core.llm.LOCAL_LLM_BASE_URL", ""):
            spec = llm.resolve_model_spec("graph_expansion")

        self.assertEqual(spec.provider, "gemini")
        self.assertEqual(spec.model_id, "gemini-2.5-flash-lite")

    def test_step_override_supports_claude(self):
        from backend.core import llm

        with patch.dict("os.environ", {
            "SYNTHESIS_LLM_PROVIDER": "anthropic",
            "SYNTHESIS_LLM_MODEL": "claude-sonnet-4-20250514",
        }, clear=True), \
             patch("backend.core.llm.ANTHROPIC_API_KEY", "anthropic-key"):
            spec = llm.resolve_model_spec("synthesis")

        self.assertEqual(spec.provider, "anthropic")
        self.assertEqual(spec.model_id, "claude-sonnet-4-20250514")

    def test_step_override_supports_local_openai_compatible_endpoint(self):
        from backend.core import llm

        with patch.dict("os.environ", {
            "GRAPH_EXPANSION_LLM_PROVIDER": "local",
            "GRAPH_EXPANSION_LLM_MODEL": "llama3.1",
        }, clear=True), \
             patch("backend.core.llm.LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"):
            spec = llm.resolve_model_spec("graph_expansion")

        self.assertEqual(spec.provider, "local")
        self.assertEqual(spec.model_id, "llama3.1")

    def test_legacy_llm_provider_still_works_as_global_override(self):
        from backend.core import llm

        with patch.dict("os.environ", {}, clear=True), \
             patch("backend.core.llm.LLM_PROVIDER", "openai"), \
             patch("backend.core.llm.OPENAI_API_KEY", "sk-test"), \
             patch("backend.core.llm.GEMINI_API_KEY", ""):
            spec = llm.resolve_model_spec("synthesis")

        self.assertEqual(spec.provider, "openai")
        self.assertEqual(spec.model_id, "gpt-4o-mini")
