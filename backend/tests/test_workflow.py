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


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        clear_ledger()
        self.watchlist = ["AAPL", "MSFT", "NVDA", "TSM", "DAL"]

    def mock_structured(self, schema):
        """Stand-in for `llm.with_structured_output(schema)`.

        Returns a runner whose .invoke() produces a validated instance of `schema`,
        mirroring how the real structured-output path now behaves. Dispatch is keyed
        on the schema type rather than fragile prompt substrings.
        """
        runner = MagicMock()
        def _invoke(messages):
            kind, payload = self.mock_llm_invoke(messages)
            if schema is ExtractionResult:
                return ExtractionResult(events=payload)
            if schema is SynthesisOut:
                return SynthesisOut(**payload)
            if schema is OutputSafetyJudgeOut:
                return OutputSafetyJudgeOut(**payload)
            raise ValueError(f"Mock got unexpected structured-output schema: {schema}")
        runner.invoke = _invoke
        return runner

    def mock_llm_invoke(self, messages):
        """Builds the raw payload for a node; returns (kind, payload)."""
        system_msg = messages[0].content
        user_msg = messages[1].content

        # A. Canonical Extraction Mocking
        if "canonical structured event" in system_msg:
            extracted = []
            
            # Helper to check article properties and map them
            if "m5-announcement" in user_msg or "M5 Chip" in user_msg or "finnhub_direct_001" in user_msg:
                event = {
                    "articleId": "finnhub_direct_001",
                    "eventType": "supply_chain",
                    "eventSummary": "Apple unveils M5 chip utilizing TSMC 2nm technology.",
                    "hardFacts": ["Apple announced M5 chip family", "Uses TSMC 2nm lithography", "40% faster local LLM processing"],
                    "entities": ["Apple", "AAPL", "TSMC"],
                    "eventTags": ["M5", "semiconductor", "2nm"],
                    "regions": ["Taiwan"],
                    "sectors": ["technology"],
                    "commodities": ["microchips"],
                    "technologyThemes": ["semiconductors"],
                    "possibleDirectionalPressure": "positive",
                    "uncertaintyNotes": ["yield rates of 2nm nodes"],
                    "evidence": ["announced its M5 chip family", "leverages TSMC's 2nm lithography"]
                }
                extracted.append(event)
                
            if "copilot-revenue" in user_msg or "Copilot Subscriptions" in user_msg or "finnhub_direct_002" in user_msg:
                event = {
                    "articleId": "finnhub_direct_002",
                    "eventType": "earnings",
                    "eventSummary": "Microsoft exceeds guidance fueled by 28% cloud growth from Copilot.",
                    "hardFacts": ["Cloud revenue expanded 28%", "Boosted by Microsoft 365 Copilot adoption"],
                    "entities": ["Microsoft", "MSFT"],
                    "eventTags": ["cloud", "Copilot", "earnings"],
                    "regions": [],
                    "sectors": ["technology"],
                    "commodities": [],
                    "technologyThemes": ["frontier AI"],
                    "possibleDirectionalPressure": "positive",
                    "uncertaintyNotes": ["sustainability of Copilot subscription growth"],
                    "evidence": ["cloud services grew 28%", "boosted by corporate adoption of Microsoft 365 Copilot"]
                }
                extracted.append(event)

            if "dell-msft-contract" in user_msg or "Dell Technologies" in user_msg:
                event = {
                    "articleId": "dell_msft_contract_001",
                    "eventType": "other",
                    "eventSummary": "Dell Technologies wins a $10 billion government contract and hits an all-time high.",
                    "hardFacts": ["Dell Technologies won a $10 billion government contract", "Dell hit an all-time high"],
                    "entities": ["Dell Technologies", "DELL"],
                    "eventTags": ["government contract", "all-time high"],
                    "regions": ["United States"],
                    "sectors": ["technology"],
                    "commodities": [],
                    "technologyThemes": ["enterprise infrastructure"],
                    "possibleDirectionalPressure": "positive",
                    "uncertaintyNotes": ["The source tag links the item to Microsoft, but the article summary does not explain the exact mechanism."],
                    "evidence": ["wins $10B govt contract", "hits all-time high"]
                }
                extracted.append(event)

            if "nvidia-ai-data-center" in user_msg or "currents_8532d38f-c8bd-55c3-ac51-dd3860f1a287" in user_msg:
                event = {
                    "articleId": "currents_8532d38f-c8bd-55c3-ac51-dd3860f1a287",
                    "eventType": "private_company_technology",
                    "eventSummary": "TechRepublic reports Nvidia-backed Reflection AI plans a multibillion-dollar AI data center in South Korea.",
                    "hardFacts": ["TechRepublic reports Reflection AI is Nvidia-backed", "Reflection AI plans a multibillion-dollar AI data center in South Korea"],
                    "mentionedTickers": ["NVDA"],
                    "entities": ["Nvidia", "Reflection AI"],
                    "eventTags": ["AI infrastructure", "data center", "open AI infrastructure"],
                    "regions": ["South Korea"],
                    "sectors": ["technology", "AI"],
                    "commodities": [],
                    "technologyThemes": ["AI infrastructure", "frontier AI"],
                    "possibleDirectionalPressure": "positive",
                    "uncertaintyNotes": ["Reflection AI is private; the article does not quantify Nvidia's direct financial exposure"],
                    "evidence": ["Nvidia-backed Reflection AI plans a multibillion-dollar data center in South Korea"]
                }
                extracted.append(event)
                
            if "foxconn-fire" in user_msg or "Zhengzhou Assembly Zone" in user_msg or "finnhub_dup_001" in user_msg:
                event = {
                    "articleId": "finnhub_dup_001",
                    "eventType": "supply_chain",
                    "eventSummary": "Fire reported at electronics manufacturing zone in Zhengzhou.",
                    "hardFacts": ["fire in component warehouse", "Zhengzhou assembly zone", "no casualties"],
                    "entities": ["Foxconn", "AAPL"],
                    "eventTags": ["Zhengzhou", "fire", "factory"],
                    "regions": ["China"],
                    "sectors": ["technology"],
                    "commodities": [],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "negative",
                    "uncertaintyNotes": ["damage scale to inventory"],
                    "evidence": ["Zhengzhou assembly zone", "fire broke out in a component warehouse"]
                }
                extracted.append(event)
                
            if "factory-incident" in user_msg or "Zhengzhou Electronics Zone" in user_msg or "finnhub_dup_002" in user_msg:
                event = {
                    "articleId": "finnhub_dup_002",
                    "eventType": "supply_chain",
                    "eventSummary": "Fire reported at electronics manufacturing zone in Zhengzhou.",
                    "hardFacts": ["fire in component warehouse", "Zhengzhou assembly zone"],
                    "entities": ["Foxconn", "AAPL"],
                    "eventTags": ["Zhengzhou", "fire", "factory"],
                    "regions": ["China"],
                    "sectors": ["technology"],
                    "commodities": [],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "negative",
                    "uncertaintyNotes": ["production impact"],
                    "evidence": ["fire in a Zhengzhou electronics manufacturing plant", "examining potential damage"]
                }
                extracted.append(event)
                
            if "foxconn-halt" in user_msg or "Zhengzhou Fire Halted" in user_msg or "finnhub_dup_003" in user_msg:
                event = {
                    "articleId": "finnhub_dup_003",
                    "eventType": "supply_chain",
                    "eventSummary": "Fire reported at electronics manufacturing zone in Zhengzhou halts lines.",
                    "hardFacts": ["fire in component warehouse", "Zhengzhou assembly zone", "assembly lines halted", "2 million iPhones delayed"],
                    "entities": ["Foxconn", "AAPL", "Apple"],
                    "eventTags": ["Zhengzhou", "fire", "halt", "iPhone"],
                    "regions": ["China"],
                    "sectors": ["technology"],
                    "commodities": [],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "negative",
                    "uncertaintyNotes": ["duration of shutdown"],
                    "evidence": ["fire in Zhengzhou factory warehouse", "complete shutdown of advanced assembly lines", "delay shipment of 2 million iPhone units"]
                }
                extracted.append(event)
                
            if "taiwan-earthquake" in user_msg or "currents_cross_001" in user_msg:
                event = {
                    "articleId": "currents_cross_001",
                    "eventType": "natural_disaster",
                    "eventSummary": "7.2 magnitude earthquake in Taiwan prompts foundry evacuations.",
                    "hardFacts": ["7.2 magnitude earthquake struck eastern Taiwan", "Semiconductor fabs in Hsinchu evacuated", "Possible calibration damage to lithography tools"],
                    "entities": ["Taiwan", "TSMC"],
                    "eventTags": ["Taiwan", "earthquake", "lithography", "semiconductor"],
                    "regions": ["Taiwan"],
                    "sectors": ["technology"],
                    "commodities": ["silicon", "microchips"],
                    "technologyThemes": ["semiconductors"],
                    "possibleDirectionalPressure": "negative",
                    "uncertaintyNotes": ["calibration recovery time"],
                    "evidence": ["7.2 magnitude earthquake shook eastern Taiwan", "evacuated staff", "calibration damage to high-end lithography equipment"]
                }
                extracted.append(event)
                
            if "anthropic-claude" in user_msg or "currents_cross_002" in user_msg:
                event = {
                    "articleId": "currents_cross_002",
                    "eventType": "private_company_technology",
                    "eventSummary": "Anthropic launches Claude 3.7 Sonnet setting coding benchmarks.",
                    "hardFacts": ["Anthropic launched Claude 3.7 Sonnet", "Outperforms platforms in coding, math, chemistry"],
                    "entities": ["Anthropic", "Claude"],
                    "eventTags": ["Anthropic", "Claude", "model release"],
                    "regions": [],
                    "sectors": ["technology"],
                    "commodities": [],
                    "technologyThemes": ["frontier AI"],
                    "possibleDirectionalPressure": "positive",
                    "uncertaintyNotes": ["pricing structures", "competitor response timeline"],
                    "evidence": ["launched Claude 3.7 Sonnet", "achieves state-of-the-art results"]
                }
                extracted.append(event)
                
            if "red-sea-disruption" in user_msg or "currents_cross_003" in user_msg:
                event = {
                    "articleId": "currents_cross_003",
                    "eventType": "geopolitical",
                    "eventSummary": "Drone strikes near Bab el-Mandeb reroute Red Sea shipping.",
                    "hardFacts": ["Cargo ships targeted by drone strikes in Bab el-Mandeb", "Red Sea route suspended", "Container rates surge 30%"],
                    "entities": ["Red Sea", "Bab el-Mandeb"],
                    "eventTags": ["Red Sea", "drone strikes", "shipping", "freight rates"],
                    "regions": ["Red Sea", "Middle East"],
                    "sectors": ["shipping", "airlines"],
                    "commodities": ["oil"],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "negative",
                    "uncertaintyNotes": ["duration of rerouting", "naval security intervention"],
                    "evidence": ["targeted by drone strikes near the Bab el-Mandeb", "suspension of Red Sea", "rates surged 30%"]
                }
                extracted.append(event)
                
            return ("extraction", extracted)

        # B. Safety Judge Mocking
        elif "independent safety, compliance, and grounding judge" in system_msg:
            passes = getattr(self, "mock_judge_passes", True)
            if hasattr(self, "mock_judge_attempts_decisions"):
                attempts = getattr(self, "mock_judge_attempts_made", 0)
                decisions = self.mock_judge_attempts_decisions
                if attempts < len(decisions):
                    passes = decisions[attempts]
                    self.mock_judge_attempts_made = attempts + 1
            
            groundingPassed = getattr(self, "mock_judge_grounding", passes)
            advicePassed = getattr(self, "mock_judge_advice", passes)
            pathPassed = getattr(self, "mock_judge_path", passes)
            defects = getattr(self, "mock_judge_defects", [] if passes else ["mocked defect"])
            regenerationInstruction = getattr(self, "mock_judge_regen_instr", "" if passes else "Fix the issues.")
            
            if getattr(self, "mock_judge_exception", False):
                raise ValueError("Mock judge error")
                
            return ("judge", {
                "passes": passes,
                "groundingPassed": groundingPassed,
                "advicePassed": advicePassed,
                "pathPassed": pathPassed,
                "defects": defects,
                "regenerationInstruction": regenerationInstruction
            })

        # C. Synthesis Mocking
        elif "review the direct and indirect catalyst events" in system_msg:
            # Parse input to find ticker
            ticker = "UNKNOWN"
            for line in user_msg.split('\n'):
                if "TICKER CONFIG:" in line:
                    ticker = line.replace("TICKER CONFIG:", "").strip()

            is_regen = "CRITICAL CORRECTION REQUIRED" in system_msg
            summaryHeadline = f"Catalysts analyzed for {ticker} (Regenerated)" if is_regen else f"Catalysts analyzed for {ticker}"

            return ("synthesis", {
                "summaryHeadline": summaryHeadline,
                "situationSummary": f"Analyzed latest direct and indirect events affecting {ticker}.",
                "mainCatalysts": [
                    {
                        "eventId": "evt_test_001",
                        "label": "Test Catalyst",
                        "relationshipType": "direct",
                        "eventType": "supply_chain",
                        "possibleInfluence": "positive",
                        "confidence": "high",
                        "recency": "breaking",
                        "impactPath": [ticker],
                        "significance": 8
                    }
                ],
                "overallPossibleInfluence": "positive",
                "confidence": "medium",
                "uncertainties": ["Market volatility."],
                "watchItems": ["Volume indicators."]
            })

        raise ValueError(f"Mock got unexpected message patterns: {messages}")

    @patch('backend.iterations.extraction.get_extraction_llm')
    @patch('backend.iterations.guardrails.get_judge_llm')
    @patch('backend.iterations.synthesis.get_synthesis_llm')
    def test_iteration_1_direct_news(self, mock_synthesis_llm, mock_judge_llm, mock_extraction_llm):
        """Test Iteration 1 direct company news path without duplicates."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output = self.mock_structured
        mock_synthesis_llm.return_value = mock_llm
        mock_judge_llm.return_value = mock_llm
        mock_extraction_llm.return_value = mock_llm

        initial_state = {
            "iteration": 1,
            "watchlist": self.watchlist,
            "scenario_id": "direct_news",
            "simulated_now": "2026-05-28T17:25:00Z",
            "articles": [],
            "canonical_events": [],
            "routed_candidates": [],
            "ticker_buckets": {},
            "ticker_syntheses": {},
            "duplicate_counts": {},
            "ingestion_metadata": {}
        }
        
        final_state = get_workflow(initial_state["iteration"]).invoke(initial_state)
        
        # Assertions
        self.assertEqual(len(final_state["articles"]), 2)
        self.assertEqual(len(final_state["canonical_events"]), 2)
        # Check direct routing
        routed = final_state["routed_candidates"]
        self.assertTrue(any(r["ticker"] == "AAPL" and r["relationshipType"] == "direct" for r in routed))
        self.assertTrue(any(r["ticker"] == "MSFT" and r["relationshipType"] == "direct" for r in routed))
        
        # Check syntheses are present for watchlist
        self.assertIn("AAPL", final_state["ticker_syntheses"])
        self.assertIn("MSFT", final_state["ticker_syntheses"])

        msft_direct = final_state["ticker_buckets"]["MSFT"]["directEvents"][0]
        self.assertIn("MSFT", msft_direct["sourceRelatedTickers"])
        self.assertEqual(msft_direct["impactPath"], ["MSFT"])
        self.assertIn("Directly tagged", msft_direct["reasonForRouting"])

    @patch('backend.iterations.extraction.get_extraction_llm')
    @patch('backend.iterations.guardrails.get_judge_llm')
    @patch('backend.iterations.synthesis.get_synthesis_llm')
    def test_iteration_1_preserves_direct_source_tag_for_non_named_company(self, mock_synthesis_llm, mock_judge_llm, mock_extraction_llm):
        """Source ticker tags are routing evidence even when the headline names another company."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output = self.mock_structured
        mock_synthesis_llm.return_value = mock_llm
        mock_judge_llm.return_value = mock_llm
        mock_extraction_llm.return_value = mock_llm

        article = {
            "articleId": "dell_msft_contract_001",
            "headline": "Dell Technologies (DELL) Wins $10B Govt Contract, Hits All-Time High",
            "summary": "Dell Technologies wins a $10 billion government contract and hits an all-time high.",
            "sourceName": "Finnhub",
            "sourceApi": "finnhub",
            "publishedAt": "2026-05-28T17:20:00Z",
            "url": "http://example.com/dell-msft-contract",
            "relatedTickers": ["MSFT"],
        }
        initial_state = {
            "iteration": 1,
            "watchlist": self.watchlist,
            "scenario_id": "live",
            "simulated_now": "2026-05-28T17:25:00Z",
            "articles": [],
            "canonical_events": [],
            "routed_candidates": [],
            "ticker_buckets": {},
            "ticker_syntheses": {},
            "duplicate_counts": {},
            "ingestion_metadata": {}
        }

        with patch('backend.iterations.fetching.get_news_payload') as mock_payload:
            mock_payload.return_value = {
                "total_ingested": 1,
                "passed_freshness": 1,
                "articles": [article],
            }
            final_state = get_workflow(1).invoke(initial_state)

        self.assertEqual(len(final_state["canonical_events"]), 1)
        self.assertTrue(any(r["ticker"] == "MSFT" and r["relationshipType"] == "direct" for r in final_state["routed_candidates"]))
        msft_events = final_state["ticker_buckets"]["MSFT"]["directEvents"]
        self.assertEqual(len(msft_events), 1)
        self.assertEqual(msft_events[0]["sourceRelatedTickers"], ["MSFT"])
        self.assertEqual(msft_events[0]["impactPath"], ["MSFT"])
        self.assertIn("Directly tagged", msft_events[0]["reasonForRouting"])

    @patch('backend.core.llm.OPENAI_API_KEY', 'sk-test')
    @patch('backend.iterations.extraction.get_extraction_llm')
    @patch('backend.iterations.guardrails.get_judge_llm')
    @patch('backend.iterations.synthesis.get_synthesis_llm')
    def test_iteration_3_routes_untagged_article_by_mentioned_ticker(self, mock_synthesis_llm, mock_judge_llm, mock_extraction_llm):
        """Currents stories with no source ticker should still route when extraction maps a watched ticker."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output = self.mock_structured
        mock_synthesis_llm.return_value = mock_llm
        mock_judge_llm.return_value = mock_llm
        mock_extraction_llm.return_value = mock_llm

        article = {
            "articleId": "currents_8532d38f-c8bd-55c3-ac51-dd3860f1a287",
            "sourceApi": "currents",
            "sourceName": "TechRepublic",
            "url": "https://www.techrepublic.com/article/news-nvidia-ai-data-center-south-korea-china-open-source/",
            "headline": "Nvidia-Backed Startup Plans Billion-Dollar AI Fortress in South Korea",
            "summary": "Nvidia-backed Reflection AI plans a multibillion-dollar data center in South Korea as the US pushes open AI infrastructure to counter Chinese rivals.",
            "publishedAt": "2026-05-28T17:21:00Z",
            "relatedTickers": [],
        }
        initial_state = {
            "iteration": 3,
            "watchlist": self.watchlist,
            "scenario_id": "live",
            "simulated_now": "2026-05-28T17:25:00Z",
            "articles": [],
            "canonical_events": [],
            "routed_candidates": [],
            "ticker_buckets": {},
            "ticker_syntheses": {},
            "duplicate_counts": {},
            "ingestion_metadata": {}
        }

        with patch('backend.iterations.fetching.get_news_payload') as mock_payload:
            mock_payload.return_value = {
                "total_ingested": 1,
                "passed_freshness": 1,
                "articles": [article],
            }
            final_state = get_workflow(3).invoke(initial_state)

        event = final_state["canonical_events"][0]
        self.assertEqual(event["mentionedTickers"], ["NVDA"])
        self.assertTrue(any(r["ticker"] == "NVDA" and r["relationshipType"] == "direct" for r in final_state["routed_candidates"]))
        nvda_events = final_state["ticker_buckets"]["NVDA"]["directEvents"]
        self.assertEqual(len(nvda_events), 1)
        self.assertEqual(nvda_events[0]["mentionedTickers"], ["NVDA"])
        self.assertEqual(nvda_events[0]["entities"], ["Nvidia", "Reflection AI"])
        self.assertEqual(nvda_events[0]["sourceName"], "TechRepublic")

    @patch('backend.iterations.extraction.get_extraction_llm')
    @patch('backend.iterations.guardrails.get_judge_llm')
    @patch('backend.iterations.synthesis.get_synthesis_llm')
    def test_iteration_2_ledger_duplicates(self, mock_synthesis_llm, mock_judge_llm, mock_extraction_llm):
        """Test Iteration 2 catalyst memory deduplication and update detection."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output = self.mock_structured
        mock_synthesis_llm.return_value = mock_llm
        mock_judge_llm.return_value = mock_llm
        mock_extraction_llm.return_value = mock_llm

        initial_state = {
            "iteration": 2,
            "watchlist": self.watchlist,
            "scenario_id": "duplicate_news",
            "simulated_now": "2026-05-28T17:25:00Z",
            "articles": [],
            "canonical_events": [],
            "routed_candidates": [],
            "ticker_buckets": {},
            "ticker_syntheses": {},
            "duplicate_counts": {},
            "ingestion_metadata": {}
        }
        
        final_state = get_workflow(initial_state["iteration"]).invoke(initial_state)
        
        # In duplicate_news scenario:
        # Article 1: Zhengzhou Fire (evt_finnhub_dup_001) -> new
        # Article 2: Zhengzhou fire incident (evt_finnhub_dup_002) -> duplicate
        # Article 3: Zhengzhou fire halts line (evt_finnhub_dup_003) -> update
        
        self.assertEqual(len(final_state["articles"]), 3)
        self.assertEqual(len(final_state["canonical_events"]), 3)
        
        # Duplicate count for AAPL should be 1
        self.assertEqual(final_state["duplicate_counts"].get("AAPL", 0), 1)
        self.assertTrue(final_state["ticker_buckets"]["AAPL"]["directEvents"])
        self.assertIn("sourceRelatedTickers", final_state["ticker_buckets"]["AAPL"]["directEvents"][0])

    @patch('backend.iterations.extraction.get_extraction_llm')
    @patch('backend.iterations.guardrails.get_judge_llm')
    @patch('backend.iterations.synthesis.get_synthesis_llm')
    def test_iteration_3_cross_impact_routing(self, mock_synthesis_llm, mock_judge_llm, mock_extraction_llm):
        """Test Iteration 3 cross impact graph routing for untickered events."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output = self.mock_structured
        mock_synthesis_llm.return_value = mock_llm
        mock_judge_llm.return_value = mock_llm
        mock_extraction_llm.return_value = mock_llm

        initial_state = {
            "iteration": 3,
            "watchlist": self.watchlist,
            "scenario_id": "cross_impact",
            "simulated_now": "2026-05-28T17:25:00Z",
            "articles": [],
            "canonical_events": [],
            "routed_candidates": [],
            "ticker_buckets": {},
            "ticker_syntheses": {},
            "duplicate_counts": {},
            "ingestion_metadata": {}
        }
        
        final_state = get_workflow(initial_state["iteration"]).invoke(initial_state)
        
        self.assertEqual(len(final_state["articles"]), 3)
        
        # Verify cross impact candidate paths
        routed = final_state["routed_candidates"]
        
        # 1. Taiwan Earthquake should route to AAPL, NVDA, and TSM via semiconductor chain (eventId: evt_currents_cross_001)
        earthquake_routes = [r for r in routed if "evt_currents_cross_001" in r["eventId"]]
        self.assertTrue(any(r["ticker"] == "AAPL" for r in earthquake_routes))
        self.assertTrue(any(r["ticker"] == "NVDA" for r in earthquake_routes))
        self.assertTrue(any(r["ticker"] == "TSM" for r in earthquake_routes))
        
        # 2. Anthropic model launch should route to MSFT and NVDA via Frontier AI theme (eventId: evt_currents_cross_002)
        anthropic_routes = [r for r in routed if "evt_currents_cross_002" in r["eventId"]]
        self.assertTrue(any(r["ticker"] == "MSFT" for r in anthropic_routes))
        self.assertTrue(any(r["ticker"] == "NVDA" for r in anthropic_routes))
        
        # 3. Red Sea Disruption should route to DAL via Logistics Cost Risk -> Airline sensitivities (eventId: evt_currents_cross_003)
        redsea_routes = [r for r in routed if "evt_currents_cross_003" in r["eventId"]]
        self.assertTrue(any(r["ticker"] == "DAL" for r in redsea_routes))
        self.assertTrue(final_state["ticker_buckets"]["DAL"]["crossImpactEvents"])
        self.assertIn("reasonForRouting", final_state["ticker_buckets"]["DAL"]["crossImpactEvents"][0])

    def test_intraday_significance_floor_for_fresh_direct_contract(self):
        synthesis = {
            "mainCatalysts": [
                {
                    "eventId": "evt_dell_msft_contract_001",
                    "label": "Dell contract",
                    "relationshipType": "direct",
                    "eventType": "other",
                    "possibleInfluence": "positive",
                    "confidence": "medium",
                    "recency": "breaking",
                    "impactPath": ["MSFT"],
                    "significance": 3,
                }
            ]
        }
        bucket = {
            "directEvents": [
                {
                    "eventId": "evt_dell_msft_contract_001",
                    "relationshipType": "direct",
                    "headline": "Dell Technologies wins $10B government contract, hits all-time high",
                    "eventSummary": "Dell Technologies wins a $10 billion government contract and hits an all-time high.",
                    "hardFacts": [{"fact": "Dell Technologies won a $10 billion government contract", "minutesAgo": 13}],
                    "eventTags": ["government contract", "all-time high"],
                    "technologyThemes": ["enterprise infrastructure"],
                    "possibleDirectionalPressure": "positive",
                    "minutesAgo": 13,
                }
            ],
            "crossImpactEvents": [],
        }

        normalized = _normalize_synthesis_significance(synthesis, bucket)
        self.assertGreaterEqual(normalized["mainCatalysts"][0]["significance"], 7)

    def test_synthesis_postprocess_restores_direct_and_filters_weak_indirect(self):
        synthesis = {
            "summaryHeadline": "Macro pressure dominates MSFT",
            "situationSummary": "Weak macro paths were selected by the model.",
            "mainCatalysts": [
                {
                    "eventId": "evt_weak_macro",
                    "label": "U.S. voters coping with higher prices",
                    "relationshipType": "indirect",
                    "eventType": "other",
                    "possibleInfluence": "unclear",
                    "confidence": "tentative",
                    "recency": "breaking",
                    "impactPath": ["United States", "MSFT"],
                    "significance": 4,
                }
            ],
            "overallPossibleInfluence": "mixed",
            "confidence": "medium",
            "uncertainties": [],
            "watchItems": [],
        }
        bucket = {
            "directEvents": [
                {
                    "eventId": "evt_agentic_ai_msft",
                    "relationshipType": "direct",
                    "headline": "Could Agentic AI Be Apple's Next Big Tailwind?",
                    "eventSummary": "Yahoo article argues that Agentic AI could be Apple's next big tailwind.",
                    "hardFacts": [{"fact": "Published on 2026-05-30T07:50:00+00:00", "minutesAgo": 99}],
                    "mentionedTickers": ["AAPL"],
                    "entities": ["Apple"],
                    "eventTags": ["AI development"],
                    "technologyThemes": ["AI models"],
                    "possibleDirectionalPressure": "unclear",
                    "sourceRelatedTickers": ["MSFT"],
                    "impactPath": ["MSFT"],
                    "minutesAgo": 99,
                }
            ],
            "crossImpactEvents": [
                {
                    "eventId": "evt_weak_macro",
                    "relationshipType": "indirect",
                    "headline": "9 U.S. Voters Tell Us How They're Coping With Higher Prices",
                    "eventSummary": "U.S. voters are coping with higher prices.",
                    "hardFacts": [{"fact": "Published recently", "minutesAgo": 27}],
                    "eventTags": ["economic"],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "unclear",
                    "impactPath": ["United States", "MSFT"],
                    "pathStrength": "weak",
                    "pathConfidence": 0.45,
                    "minutesAgo": 27,
                }
            ],
        }

        repaired = _postprocess_synthesis(synthesis, bucket, "MSFT")
        self.assertEqual([c["eventId"] for c in repaired["mainCatalysts"]], ["evt_agentic_ai_msft"])
        self.assertTrue(any("evt_weak_macro" not in c["eventId"] for c in repaired["mainCatalysts"]))
        self.assertTrue(repaired["watchItems"])

    def test_judge_relaxes_watch_item_language_failure_without_trade_instruction(self):
        judge_result = OutputSafetyJudgeOut(
            passes=False,
            groundingPassed=True,
            advicePassed=False,
            pathPassed=True,
            defects=["Contains implicit trading recommendations in the watchItems section."],
            regenerationInstruction="Remove watchItems.",
        )
        synthesis = {
            "watchItems": [
                "Monitor whether AI political activity becomes relevant to MSFT via Frontier AI."
            ]
        }

        relaxed = _relax_language_only_judge_failure(judge_result, synthesis)
        self.assertTrue(relaxed.passes)
        self.assertTrue(relaxed.advicePassed)

    def test_synthesis_directional_read_can_override_unclear_extraction_hint(self):
        synthesis = {
            "summaryHeadline": "MSFT read-through improves",
            "situationSummary": "The model takes a tentative positive intraday read from the direct event.",
            "mainCatalysts": [
                {
                    "eventId": "evt_direct_msft",
                    "label": "Direct MSFT catalyst",
                    "relationshipType": "direct",
                    "eventType": "market_attention",
                    "possibleInfluence": "positive",
                    "confidence": "tentative",
                    "recency": "recent",
                    "impactPath": ["MSFT"],
                    "significance": 5,
                }
            ],
            "overallPossibleInfluence": "unclear",
            "confidence": "medium",
            "uncertainties": [],
            "watchItems": [],
        }
        bucket = {
            "directEvents": [
                {
                    "eventId": "evt_direct_msft",
                    "relationshipType": "direct",
                    "headline": "Source-tagged MSFT catalyst",
                    "eventSummary": "A source-tagged MSFT article creates a plausible positive intraday read.",
                    "hardFacts": [],
                    "eventTags": [],
                    "technologyThemes": [],
                    "possibleDirectionalPressure": "unclear",
                    "sourceRelatedTickers": ["MSFT"],
                    "impactPath": ["MSFT"],
                    "minutesAgo": 20,
                }
            ],
            "crossImpactEvents": [],
        }

        repaired = _postprocess_synthesis(synthesis, bucket, "MSFT")
        self.assertEqual(repaired["mainCatalysts"][0]["possibleInfluence"], "positive")
        self.assertEqual(repaired["overallPossibleInfluence"], "positive")
