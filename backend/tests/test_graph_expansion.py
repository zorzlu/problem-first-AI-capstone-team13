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


class TestGraphExpansion(unittest.TestCase):
    def setUp(self):
        from backend.graph.graph import reset_graph
        reset_graph()

    @patch('backend.graph.expansion.has_llm_for_step', return_value=False)
    def test_expand_new_ticker_no_llm(self, _mock_has_llm):
        from backend.graph.expansion import expand_graph_for_ticker
        from backend.graph.graph import get_graph, add_graph_node

        # Add GOOGL as a private_company first (not in seed graph, so we test normalization)
        add_graph_node({
            "nodeId": "private_company_GOOGL",
            "nodeType": "private_company",
            "name": "Alphabet Inc.",
            "ticker": "GOOGL",
            "aliases": ["Google", "Alphabet"],
            "queryTerms": ["Google", "Alphabet", "GOOGL"]
        })

        # Public companies with tickers are normalized at insertion time.
        nodes = get_graph()["nodes"]
        googl_nodes = [n for n in nodes if n.get("ticker") == "GOOGL"]
        self.assertEqual(len(googl_nodes), 1)
        self.assertEqual(googl_nodes[0]["nodeType"], "ticker")

        # Run expansion for GOOGL. Since it is now a clean ticker root, automatic
        # expansion without force can skip it.
        res = expand_graph_for_ticker("GOOGL", force=False)
        self.assertEqual(res["ticker"], "GOOGL")
        self.assertTrue(res.get("skipped", False))
        
    def test_normalize_graph_repairs_ticker_roots_and_public_company_nodes(self):
        from backend.graph.graph import normalize_graph

        graph = {
            "nodes": [
                {"nodeId": "ticker_NVDA", "nodeType": "ticker", "name": "NVDA", "aliases": [], "queryTerms": ["NVDA"]},
                {"nodeId": "private_company_SBUX", "nodeType": "private_company", "name": "Starbucks Corporation", "ticker": "SBUX", "aliases": ["Starbucks"], "queryTerms": ["coffee"]},
                {"nodeId": "country_United_States", "nodeType": "country", "name": "United States", "aliases": ["US"], "queryTerms": ["US politics"]},
                {"nodeId": "company_OpenAI", "nodeType": "private_company", "name": "OpenAI", "aliases": ["ChatGPT"], "queryTerms": ["OpenAI"]},
            ],
            "edges": [],
        }

        normalized = normalize_graph(graph, watchlist=["NVDA", "SBUX"])
        by_id = {n["nodeId"]: n for n in normalized["nodes"]}

        self.assertEqual(by_id["ticker_NVDA"]["ticker"], "NVDA")
        self.assertEqual(by_id["private_company_SBUX"]["nodeType"], "ticker")
        self.assertEqual(by_id["private_company_SBUX"]["ticker"], "SBUX")
        self.assertEqual(by_id["country_United_States"]["nodeType"], "country")
        self.assertEqual(by_id["company_OpenAI"]["nodeType"], "private_company")

    def test_cross_impact_queries_drop_broad_noise_terms(self):
        from backend.graph.graph import set_graph, get_cross_impact_queries

        graph = {
            "nodes": [
                {"nodeId": "ticker_AAPL", "nodeType": "ticker", "name": "Apple Inc.", "ticker": "AAPL", "aliases": ["Apple", "iPhone"], "queryTerms": ["Apple", "iPhone", "Mac"]},
                {"nodeId": "policy_export", "nodeType": "policy_area", "name": "US Export Controls", "aliases": ["US"], "queryTerms": ["US", "AI", "US export controls", "chip export restrictions"]},
                {"nodeId": "theme_ai", "nodeType": "technology_theme", "name": "Frontier AI", "aliases": ["AI"], "queryTerms": ["AI", "large language model", "AI data center"]},
                {"nodeId": "company_openai", "nodeType": "private_company", "name": "OpenAI", "aliases": ["ChatGPT"], "queryTerms": ["OpenAI", "ChatGPT"]},
            ],
            "edges": [
                {"fromNodeId": "policy_export", "toNodeId": "ticker_AAPL", "edgeType": "policy_exposure", "rationale": "test", "confidence": 0.8},
                {"fromNodeId": "theme_ai", "toNodeId": "ticker_AAPL", "edgeType": "technology_exposure", "rationale": "test", "confidence": 0.8},
                {"fromNodeId": "company_openai", "toNodeId": "theme_ai", "edgeType": "technology_exposure", "rationale": "test", "confidence": 0.8},
            ],
        }
        set_graph(graph)
        keywords, extra_tickers = get_cross_impact_queries(["AAPL"])
        lower = {k.lower() for k in keywords}

        self.assertIn("us export controls", lower)
        self.assertIn("ai data center", lower)
        self.assertNotIn("us", lower)
        self.assertNotIn("ai", lower)
        self.assertNotIn("iphone", lower)
        self.assertNotIn("mac", lower)
        self.assertEqual(extra_tickers, [])

    def test_live_relevance_gate_rejects_currents_noise(self):
        from backend.ingestion import is_relevant_live_article

        keywords = ["US export controls", "AI data center", "Red Sea Shipping"]
        reddit_iphone = {
            "sourceApi": "currents",
            "sourceName": "/u/tryn_asidyy",
            "url": "https://www.reddit.com/r/iphone/comments/1trva7u/is_this_real_iphone/",
            "headline": "Is this real iphone ?",
            "summary": "Please help me to figure out, this is real or fake one",
        }
        ai_datacenter = {
            "sourceApi": "currents",
            "sourceName": "TechRepublic",
            "url": "https://www.techrepublic.com/article/news-nvidia-ai-data-center-south-korea-china-open-source/",
            "headline": "Nvidia-Backed Startup Plans Billion-Dollar AI Fortress in South Korea",
            "summary": "Reflection AI plans a multibillion-dollar AI data center in South Korea.",
        }
        marketbeat_filing = {
            "sourceApi": "currents",
            "sourceName": "MarketBeat",
            "url": "https://www.marketbeat.com/instant-alerts/filing-king-luther-capital-management-corp-sells-7962-shares-of-yum-brands-inc-yum-2026-05-30/",
            "headline": "King Luther Capital Management Corp Sells 7,962 Shares of Yum! Brands, Inc. $YUM",
            "summary": "Form 13F filing.",
        }

        self.assertFalse(is_relevant_live_article(reddit_iphone, keywords))
        self.assertTrue(is_relevant_live_article(ai_datacenter, keywords))
        self.assertFalse(is_relevant_live_article(marketbeat_filing, keywords))

    def test_currents_company_news_can_pass_as_direct_source(self):
        from backend.ingestion import is_relevant_live_article

        company_article = {
            "sourceApi": "currents_company",
            "sourceName": "Yahoo",
            "url": "https://finance.yahoo.com/news/could-agentic-ai-be-apples-next-big-tailwind",
            "headline": "Could Agentic AI Be Apple's Next Big Tailwind?",
            "summary": "Discussion of agentic AI as a potential tailwind for Apple shares.",
            "relatedTickers": ["AAPL"],
            "queryTerms": ["$AAPL", "Apple", "Apple Inc."],
        }
        product_reception_article = {
            "sourceApi": "currents_company",
            "sourceName": "Autocar",
            "url": "https://www.autocar.example/news/ferrari-luce-design-reaction",
            "headline": "New Ferrari Luce disappoints expectations with divisive design",
            "summary": "Early reactions to Ferrari's new Luce model criticize the design direction.",
            "relatedTickers": ["RACE"],
            "queryTerms": ["$RACE", "Ferrari", "Ferrari N.V."],
        }
        reddit_article = {
            "sourceApi": "currents_company",
            "sourceName": "/u/tryn_asidyy",
            "url": "https://www.reddit.com/r/iphone/comments/1trva7u/is_this_real_iphone/",
            "headline": "Is this real iphone ?",
            "summary": "Please help me figure out if this is real.",
            "relatedTickers": ["AAPL"],
            "queryTerms": ["$AAPL", "Apple", "Apple Inc."],
        }

        self.assertTrue(is_relevant_live_article(company_article, []))
        self.assertTrue(is_relevant_live_article(product_reception_article, []))
        self.assertFalse(is_relevant_live_article(reddit_article, []))
