"""Regression tests for false-butterfly cross-impact routing (e.g. TSMC story -> McDonald's).

Uses a self-contained fixture graph reproducing the runtime topology that caused the bug:
a broad "United States" region wired to every US company, a geopolitical risk node with a
"Taiwan Strait tensions" alias, and competitor edges that previously amplified macro
exposure to rivals.
"""
import copy
import os
import tempfile
import unittest


class TestCrossImpactRoutingQuality(unittest.TestCase):
    FIXTURE_GRAPH = {
        "nodes": [
            {"nodeId": "ticker_TSM", "nodeType": "ticker", "name": "TSMC", "ticker": "TSM",
             "aliases": ["Taiwan Semiconductor Manufacturing"], "queryTerms": ["TSMC"]},
            {"nodeId": "ticker_AAPL", "nodeType": "ticker", "name": "Apple Inc.", "ticker": "AAPL",
             "aliases": ["Apple"], "queryTerms": ["Apple"]},
            {"nodeId": "ticker_NVDA", "nodeType": "ticker", "name": "Nvidia Corp.", "ticker": "NVDA",
             "aliases": ["Nvidia"], "queryTerms": ["Nvidia"]},
            {"nodeId": "ticker_MCD", "nodeType": "ticker", "name": "McDonald's Corporation", "ticker": "MCD",
             "aliases": ["McDonald's"], "queryTerms": ["McDonald's"]},
            {"nodeId": "ticker_SBUX", "nodeType": "ticker", "name": "Starbucks Corporation", "ticker": "SBUX",
             "aliases": ["Starbucks"], "queryTerms": ["Starbucks"]},
            {"nodeId": "region_Taiwan", "nodeType": "region", "name": "Taiwan",
             "aliases": [], "queryTerms": ["Taiwan"]},
            {"nodeId": "region_United_States", "nodeType": "region", "name": "United States",
             "aliases": ["US", "USA"], "queryTerms": ["United States"]},
            {"nodeId": "risk_consumer_spending", "nodeType": "risk_factor", "name": "Consumer Spending",
             "aliases": [], "queryTerms": ["consumer spending"]},
            {"nodeId": "risk_geo_china", "nodeType": "risk_factor", "name": "Geopolitical Tensions (China)",
             "aliases": ["Taiwan Strait tensions", "US-China trade war"], "queryTerms": []},
        ],
        "edges": [
            {"fromNodeId": "region_Taiwan", "toNodeId": "ticker_TSM", "edgeType": "regional_exposure", "confidence": 0.99},
            {"fromNodeId": "ticker_TSM", "toNodeId": "ticker_AAPL", "edgeType": "supplier_of", "confidence": 0.95},
            {"fromNodeId": "ticker_TSM", "toNodeId": "ticker_NVDA", "edgeType": "supplier_of", "confidence": 0.95},
            {"fromNodeId": "region_United_States", "toNodeId": "ticker_AAPL", "edgeType": "regional_exposure", "confidence": 0.9},
            {"fromNodeId": "region_United_States", "toNodeId": "ticker_MCD", "edgeType": "regional_exposure", "confidence": 0.9},
            {"fromNodeId": "region_United_States", "toNodeId": "ticker_SBUX", "edgeType": "regional_exposure", "confidence": 0.9},
            {"fromNodeId": "risk_consumer_spending", "toNodeId": "ticker_MCD", "edgeType": "macro_sensitivity", "confidence": 0.85},
            {"fromNodeId": "risk_geo_china", "toNodeId": "ticker_MCD", "edgeType": "macro_sensitivity", "confidence": 0.6},
            {"fromNodeId": "ticker_MCD", "toNodeId": "ticker_SBUX", "edgeType": "competitor_of", "confidence": 0.9},
        ],
    }

    WATCHLIST = ["AAPL", "NVDA", "TSM", "MCD", "SBUX"]

    def setUp(self):
        from backend.graph.graph import set_graph
        set_graph(copy.deepcopy(self.FIXTURE_GRAPH))

    def tearDown(self):
        from backend.graph.graph import reset_graph
        reset_graph()

    def _route(self, **event_fields):
        from backend.graph.graph import route_cross_impact
        event = {
            "eventId": "evt_routing_quality_test",
            "entities": [], "mentionedTickers": [], "eventTags": [],
            "regions": [], "technologyThemes": [],
            "possibleDirectionalPressure": "negative",
        }
        event.update(event_fields)
        return {c["ticker"]: c for c in route_cross_impact(event, self.WATCHLIST)}

    def test_chip_story_with_us_region_tag_does_not_route_to_consumer_brands(self):
        # The original false butterfly: TSMC story datelined "United States" routed to MCD/SBUX.
        routed = self._route(
            entities=["TSMC"],
            eventTags=["semiconductor", "export controls"],
            regions=["Taiwan", "United States"],
        )
        self.assertIn("TSM", routed)
        self.assertIn("AAPL", routed)
        self.assertIn("NVDA", routed)
        self.assertNotIn("MCD", routed)
        self.assertNotIn("SBUX", routed)

    def test_pure_us_macro_story_routes_weak_only(self):
        routed = self._route(entities=["US government"], eventTags=["government shutdown"], regions=["United States"])
        self.assertTrue(routed, "country-level macro story should still produce watch items")
        for ticker, cand in routed.items():
            self.assertEqual(cand["pathStrength"], "weak", f"{ticker} must not be a strong catalyst")

    def test_narrow_geography_still_routes_strong(self):
        routed = self._route(entities=["Taiwan"], eventTags=["earthquake"], regions=["Taiwan"])
        self.assertEqual(routed["TSM"]["pathStrength"], "strong")
        self.assertIn("AAPL", routed)
        self.assertNotIn("MCD", routed)

    def test_topical_macro_factor_still_routes_strong(self):
        # Broad-geo demotion must not swallow genuinely topical macro factors.
        routed = self._route(eventTags=["consumer spending"], regions=["United States"])
        self.assertIn("MCD", routed)
        self.assertEqual(routed["MCD"]["pathStrength"], "strong")

    def test_generic_region_word_does_not_anchor_multiword_risk_alias(self):
        # "taiwan" alone must not anchor "Taiwan Strait tensions"; the quake story must not
        # reach MCD through the geopolitical risk node.
        routed = self._route(entities=["Taiwan"], eventTags=["earthquake"], regions=["Taiwan"])
        self.assertNotIn("MCD", routed)
        # A genuine tension story (distinctive sub-phrase) still anchors the risk node.
        routed = self._route(eventTags=["trade war", "tariff"], regions=["China", "United States"])
        self.assertIn("MCD", routed)
        self.assertEqual(routed["MCD"]["pathStrength"], "weak")

    def test_competitor_hop_does_not_amplify_macro_exposure(self):
        # Geo Tensions -> MCD -> SBUX (competitor_of) must be blocked...
        routed = self._route(eventTags=["trade war"], regions=["China"])
        self.assertIn("MCD", routed)
        self.assertNotIn("SBUX", routed)
        # ...but an event AT a company still reaches its direct competitor.
        routed = self._route(entities=["McDonald's"], eventTags=["food safety recall"])
        self.assertIn("SBUX", routed)

    def test_operator_override_suppresses_flagged_route(self):
        from backend.graph import overrides as overrides_module

        original_file = overrides_module._OVERRIDES_FILE
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        os.unlink(tmp.name)
        overrides_module._OVERRIDES_FILE = tmp.name
        overrides_module._cache = {}
        overrides_module._cache_mtime = -1.0
        try:
            routed = self._route(eventTags=["consumer spending"], regions=["United States"])
            self.assertIn("MCD", routed)

            overrides_module.add_suppressed_route("MCD", "Consumer Spending", reason="test")
            routed = self._route(eventTags=["consumer spending"], regions=["United States"])
            self.assertNotIn("MCD", routed)
        finally:
            overrides_module._OVERRIDES_FILE = original_file
            overrides_module._cache = {}
            overrides_module._cache_mtime = -1.0
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def test_routing_eval_gate_passes_on_current_graph(self):
        from backend.evals.routing_quality import run_evals
        report = run_evals()
        failing = [r["caseId"] for r in report["results"] if not r["passed"]]
        self.assertEqual(report["casesPassed"], report["casesTotal"], f"failing eval cases: {failing}")
        self.assertEqual(report["falseButterflyCount"], 0)


if __name__ == "__main__":
    unittest.main()
