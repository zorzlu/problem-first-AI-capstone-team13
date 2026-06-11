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


class TestPersistenceAndApiSchemas(unittest.TestCase):
    def test_persistence_loads_legacy_and_saves_versioned_watchlist(self):
        from backend.storage import persistence

        with tempfile.TemporaryDirectory() as tmp:
            old_dir = persistence._STATE_DIR
            old_file = persistence._WATCHLIST_FILE
            try:
                persistence._STATE_DIR = tmp
                persistence._WATCHLIST_FILE = f"{tmp}/watchlist.json"
                with open(persistence._WATCHLIST_FILE, "w", encoding="utf-8") as f:
                    json.dump({"tickers": ["AAPL"]}, f)

                self.assertEqual(persistence.load_watchlist(default=["MSFT"]), ["AAPL"])

                persistence.save_watchlist(["NVDA"])
                with open(persistence._WATCHLIST_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)

                self.assertEqual(saved["schemaVersion"], 1)
                self.assertEqual(saved["kind"], "watchlist")
                self.assertEqual(saved["data"]["tickers"], ["NVDA"])
            finally:
                persistence._STATE_DIR = old_dir
                persistence._WATCHLIST_FILE = old_file

    def test_persistence_future_schema_version_falls_back_to_default(self):
        # A state file written by a NEWER app version must not be silently misread:
        # _unwrap_state raises, and the loader degrades to the default with a warning.
        from backend.storage import persistence

        with tempfile.TemporaryDirectory() as tmp:
            old_dir = persistence._STATE_DIR
            old_file = persistence._WATCHLIST_FILE
            try:
                persistence._STATE_DIR = tmp
                persistence._WATCHLIST_FILE = f"{tmp}/watchlist.json"
                with open(persistence._WATCHLIST_FILE, "w", encoding="utf-8") as f:
                    json.dump(
                        {"schemaVersion": 99, "kind": "watchlist", "data": {"tickers": ["AAPL"]}},
                        f,
                    )

                with self.assertRaises(ValueError):
                    persistence._unwrap_state(
                        {"schemaVersion": 99, "kind": "watchlist", "data": {}}, "watchlist"
                    )
                self.assertEqual(persistence.load_watchlist(default=["MSFT"]), ["MSFT"])
            finally:
                persistence._STATE_DIR = old_dir
                persistence._WATCHLIST_FILE = old_file

    def test_graph_mutation_schema_rejects_invalid_edge(self):
        from pydantic import ValidationError

        from backend.api.schemas import GraphEdgeRequest

        with self.assertRaises(ValidationError):
            GraphEdgeRequest(
                fromNodeId="ticker_AAPL",
                toNodeId="ticker_MSFT",
                edgeType="invented_edge_type",
                confidence=2.0,
            )
