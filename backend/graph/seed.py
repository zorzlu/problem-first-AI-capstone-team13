"""Seed exposure graph for the default watchlist (the starter 5-company stack)."""

EXPOSURE_GRAPH = {
    "nodes": [
        # Watched Ticker Nodes
        {
            "nodeId": "ticker_AAPL",
            "nodeType": "ticker",
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "aliases": ["Apple", "Apple Inc."],
            "queryTerms": ["Apple", "AAPL", "iPhone"]
        },
        {
            "nodeId": "ticker_MSFT",
            "nodeType": "ticker",
            "name": "Microsoft Corp.",
            "ticker": "MSFT",
            "aliases": ["Microsoft", "Microsoft Corp."],
            "queryTerms": ["Microsoft", "MSFT", "Azure"]
        },
        {
            "nodeId": "ticker_NVDA",
            "nodeType": "ticker",
            "name": "Nvidia Corp.",
            "ticker": "NVDA",
            "aliases": ["Nvidia", "Nvidia Corp."],
            "queryTerms": ["Nvidia", "NVDA", "GeForce", "H100", "Blackwell"]
        },
        {
            "nodeId": "ticker_TSM",
            "nodeType": "ticker",
            "name": "TSMC",
            "ticker": "TSM",
            "aliases": ["TSMC", "Taiwan Semiconductor Manufacturing"],
            "queryTerms": ["TSMC", "TSM", "Taiwan Semiconductor"]
        },
        {
            "nodeId": "ticker_DAL",
            "nodeType": "ticker",
            "name": "Delta Air Lines",
            "ticker": "DAL",
            "aliases": ["Delta Air Lines", "Delta"],
            "queryTerms": ["Delta Air Lines", "DAL"]
        },
        # Supply Chain / Partner Nodes
        {
            "nodeId": "supplier_Foxconn",
            "nodeType": "private_company",
            "name": "Foxconn",
            "ticker": "HNHPF",
            "aliases": ["Hon Hai Precision Industry"],
            "queryTerms": ["Foxconn", "Hon Hai"]
        },
        # Region Nodes
        {
            "nodeId": "region_Taiwan",
            "nodeType": "region",
            "name": "Taiwan",
            "aliases": ["Formosa"],
            "queryTerms": ["Taiwan", "Hsinchu", "Taipei"]
        },
        {
            "nodeId": "country_United_States",
            "nodeType": "country",
            "name": "United States",
            "aliases": ["US", "USA", "America"],
            "queryTerms": ["United States", "US politics", "US government", "US economy", "Washington policy"]
        },
        {
            "nodeId": "region_Europe",
            "nodeType": "region",
            "name": "Europe",
            "aliases": ["European Union", "EU"],
            "queryTerms": ["Europe", "European Union", "EU regulation", "EU economy", "European market"]
        },
        {
            "nodeId": "policy_US_politics",
            "nodeType": "policy_area",
            "name": "US Politics",
            "aliases": ["Washington politics", "US administration", "US federal policy"],
            "queryTerms": ["US politics", "White House policy", "Congress", "US administration", "federal policy"]
        },
        {
            "nodeId": "policy_US_defense_spending",
            "nodeType": "policy_area",
            "name": "US Defense Spending",
            "aliases": ["Pentagon procurement", "US defense budget", "Department of Defense spending"],
            "queryTerms": ["US defense spending", "Pentagon procurement", "DoD cloud contract", "defense budget", "defense cloud"]
        },
        {
            "nodeId": "policy_US_export_controls",
            "nodeType": "policy_area",
            "name": "US Export Controls",
            "aliases": ["US chip export controls", "technology export restrictions"],
            "queryTerms": ["US export controls", "chip export restrictions", "technology export controls", "China export ban"]
        },
        {
            "nodeId": "policy_EU_regulation",
            "nodeType": "policy_area",
            "name": "EU Regulation",
            "aliases": ["European regulation", "EU antitrust", "EU digital rules"],
            "queryTerms": ["EU regulation", "European antitrust", "Digital Markets Act", "AI Act", "GDPR"]
        },
        {
            "nodeId": "agency_US_DoD",
            "nodeType": "government_agency",
            "name": "US Department of Defense",
            "aliases": ["Pentagon", "DoD"],
            "queryTerms": ["Department of Defense", "Pentagon", "DoD contracts", "US military cloud"]
        },
        # Theme Nodes
        {
            "nodeId": "theme_frontier_ai",
            "nodeType": "technology_theme",
            "name": "Frontier AI",
            "aliases": ["AI models", "foundation models", "LLMs", "Generative AI"],
            "queryTerms": ["frontier AI", "AI model", "large language model", "LLM", "GPT", "Claude", "Gemini"]
        },
        {
            "nodeId": "theme_semiconductors",
            "nodeType": "technology_theme",
            "name": "Semiconductors",
            "aliases": ["chips", "silicon", "foundry"],
            "queryTerms": ["semiconductor", "microchips", "foundry", "fab"]
        },
        {
            "nodeId": "theme_ai_infrastructure",
            "nodeType": "technology_theme",
            "name": "AI Infrastructure",
            "aliases": ["AI factories", "AI data centers", "GPU clusters", "open AI infrastructure"],
            "queryTerms": ["AI infrastructure", "AI factory", "AI data center", "GPU cluster", "AI compute"]
        },
        {
            "nodeId": "technology_data_centers",
            "nodeType": "technology_theme",
            "name": "Data Centers",
            "aliases": ["Data Center Infrastructure", "Hyperscale Data Centers"],
            "queryTerms": ["data center", "hyperscale", "server infrastructure", "cloud infrastructure"]
        },
        # Geopolitical / Risk Nodes
        {
            "nodeId": "route_Red_Sea",
            "nodeType": "shipping_route",
            "name": "Red Sea Shipping",
            "aliases": ["Suez Canal", "Bab el-Mandeb"],
            "queryTerms": ["Red Sea", "Suez Canal", "Bab el-Mandeb", "shipping lane", "maritime transport"]
        },
        {
            "nodeId": "risk_logistics_cost",
            "nodeType": "risk_factor",
            "name": "Logistics Cost Risk",
            "aliases": ["freight rates", "shipping costs", "fuel surcharge"],
            "queryTerms": ["freight rates", "shipping cost", "jet fuel", "oil price"]
        },
        # Tech Companies
        {
            "nodeId": "company_Anthropic",
            "nodeType": "private_company",
            "name": "Anthropic",
            "aliases": ["Claude AI"],
            "queryTerms": ["Anthropic", "Claude model", "Claude 3"]
        },
        {
            "nodeId": "company_OpenAI",
            "nodeType": "private_company",
            "name": "OpenAI",
            "aliases": ["ChatGPT", "Sora"],
            "queryTerms": ["OpenAI", "ChatGPT", "GPT-5", "Sora"]
        },
        {
            "nodeId": "company_Mistral",
            "nodeType": "private_company",
            "name": "Mistral AI",
            "aliases": ["Mistral"],
            "queryTerms": ["Mistral AI", "Mistral model", "Le Chat"]
        },
        {
            "nodeId": "company_Reflection_AI",
            "nodeType": "private_company",
            "name": "Reflection AI",
            "aliases": ["Reflection"],
            "queryTerms": ["Reflection AI", "Reflection AI data center", "Nvidia-backed Reflection AI"]
        }
    ],
    "edges": [
        # AAPL relationships
        {
            "fromNodeId": "ticker_TSM",
            "toNodeId": "ticker_AAPL",
            "edgeType": "supplier_of",
            "strength": "high",
            "confidence": 0.95,
            "sourceType": "manual_seed",
            "notes": "TSMC is the exclusive manufacturing partner for Apple silicon (A-series and M-series chips).",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "supplier_Foxconn",
            "toNodeId": "ticker_AAPL",
            "edgeType": "supplier_of",
            "strength": "high",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "Foxconn is Apple's largest assembly partner for iPhones.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "theme_semiconductors",
            "toNodeId": "ticker_AAPL",
            "edgeType": "technology_exposure",
            "strength": "medium",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "Apple depends heavily on semiconductor supply chains for all hardware products.",
            "lastReviewedAt": "2026-05-28"
        },
        # TSM relationships
        {
            "fromNodeId": "region_Taiwan",
            "toNodeId": "ticker_TSM",
            "edgeType": "regional_exposure",
            "strength": "high",
            "confidence": 0.99,
            "sourceType": "manual_seed",
            "notes": "TSMC operates its advanced semiconductor fabrication facilities (fabs) primarily in Taiwan.",
            "lastReviewedAt": "2026-05-28"
        },
        # NVDA relationships
        {
            "fromNodeId": "ticker_TSM",
            "toNodeId": "ticker_NVDA",
            "edgeType": "supplier_of",
            "strength": "high",
            "confidence": 0.95,
            "sourceType": "manual_seed",
            "notes": "Nvidia relies on TSMC to fabricate its cutting-edge AI and gaming GPUs.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "theme_semiconductors",
            "toNodeId": "ticker_NVDA",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.99,
            "sourceType": "manual_seed",
            "notes": "Nvidia is a pure-play fabless chip company; semiconductor cycles and tech directly define its revenue.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "theme_frontier_ai",
            "toNodeId": "ticker_NVDA",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "Nvidia is the dominant hardware supplier (GPUs) for training and deploying frontier AI models.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "theme_ai_infrastructure",
            "toNodeId": "ticker_NVDA",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.95,
            "sourceType": "manual_seed",
            "notes": "Nvidia GPU demand is tightly linked to AI infrastructure, AI factories, and data-center buildouts.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "technology_data_centers",
            "toNodeId": "ticker_NVDA",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "Hyperscale data-center expansion is a direct demand driver for Nvidia accelerators and networking.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "policy_US_export_controls",
            "toNodeId": "ticker_NVDA",
            "edgeType": "trade_exposure",
            "strength": "high",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "US chip export controls can directly affect Nvidia's ability to sell advanced AI accelerators into China and other restricted markets.",
            "lastReviewedAt": "2026-05-30"
        },
        # MSFT relationships
        {
            "fromNodeId": "theme_frontier_ai",
            "toNodeId": "ticker_MSFT",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "Microsoft is heavily exposed to Frontier AI through its Azure AI services, Copilot, and alliance with OpenAI.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "theme_ai_infrastructure",
            "toNodeId": "ticker_MSFT",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.85,
            "sourceType": "manual_seed",
            "notes": "Microsoft Azure and Copilot demand are tied to AI infrastructure and data-center capacity.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "technology_data_centers",
            "toNodeId": "ticker_MSFT",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.85,
            "sourceType": "manual_seed",
            "notes": "Microsoft's cloud business is sensitive to data-center expansion, power availability, and AI compute demand.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "policy_US_defense_spending",
            "toNodeId": "ticker_MSFT",
            "edgeType": "defense_exposure",
            "strength": "medium",
            "confidence": 0.75,
            "sourceType": "manual_seed",
            "notes": "US defense and federal procurement can affect Microsoft through Azure Government, cybersecurity, productivity software, and cloud contracts.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "agency_US_DoD",
            "toNodeId": "policy_US_defense_spending",
            "edgeType": "defense_exposure",
            "strength": "high",
            "confidence": 0.90,
            "sourceType": "manual_seed",
            "notes": "The Department of Defense is a core driver of US defense procurement and cloud/cybersecurity contracts.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "policy_US_politics",
            "toNodeId": "ticker_MSFT",
            "edgeType": "policy_exposure",
            "strength": "medium",
            "confidence": 0.65,
            "sourceType": "manual_seed",
            "notes": "US politics can influence Microsoft through antitrust, AI regulation, federal procurement, cybersecurity policy, and immigration rules for skilled labor.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "policy_EU_regulation",
            "toNodeId": "ticker_MSFT",
            "edgeType": "policy_exposure",
            "strength": "medium",
            "confidence": 0.70,
            "sourceType": "manual_seed",
            "notes": "EU digital, AI, privacy, and competition regulation can affect Microsoft cloud, software, and platform operations.",
            "lastReviewedAt": "2026-05-30"
        },
        # Private AI companies to Frontier AI theme
        {
            "fromNodeId": "company_Anthropic",
            "toNodeId": "theme_frontier_ai",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.95,
            "sourceType": "manual_seed",
            "notes": "Anthropic develops Claude, a leading frontier LLM family, competing directly with OpenAI and Microsoft partners.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "company_OpenAI",
            "toNodeId": "theme_frontier_ai",
            "edgeType": "technology_exposure",
            "strength": "high",
            "confidence": 0.95,
            "sourceType": "manual_seed",
            "notes": "OpenAI is the developer of ChatGPT and GPT models, driving frontier AI themes.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "company_Mistral",
            "toNodeId": "theme_frontier_ai",
            "edgeType": "technology_exposure",
            "strength": "medium",
            "confidence": 0.80,
            "sourceType": "manual_seed",
            "notes": "Mistral AI is a frontier/open-weight AI model developer whose launches and funding can affect the competitive AI landscape.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "company_Reflection_AI",
            "toNodeId": "theme_ai_infrastructure",
            "edgeType": "technology_exposure",
            "strength": "medium",
            "confidence": 0.75,
            "sourceType": "manual_seed",
            "notes": "Reflection AI infrastructure buildouts can signal AI compute demand and GPU/data-center capacity expansion.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "theme_ai_infrastructure",
            "toNodeId": "theme_frontier_ai",
            "edgeType": "technology_exposure",
            "strength": "medium",
            "confidence": 0.80,
            "sourceType": "manual_seed",
            "notes": "Frontier AI progress depends on available AI infrastructure, data-center capacity, and accelerator supply.",
            "lastReviewedAt": "2026-05-30"
        },
        {
            "fromNodeId": "country_United_States",
            "toNodeId": "policy_US_politics",
            "edgeType": "policy_exposure",
            "strength": "high",
            "confidence": 0.95,
            "sourceType": "manual_seed",
            "notes": "US politics and federal policy originate from United States government institutions.",
            "lastReviewedAt": "2026-05-30"
        },
        # DAL relationships (Logistics/Route)
        {
            "fromNodeId": "route_Red_Sea",
            "toNodeId": "risk_logistics_cost",
            "edgeType": "shipping_exposure",
            "strength": "medium",
            "confidence": 0.85,
            "sourceType": "manual_seed",
            "notes": "Red Sea maritime route disruptions force freight rerouting, driving up global oil, transport, and general logistics costs.",
            "lastReviewedAt": "2026-05-28"
        },
        {
            "fromNodeId": "risk_logistics_cost",
            "toNodeId": "ticker_DAL",
            "edgeType": "macro_sensitivity",
            "strength": "medium",
            "confidence": 0.80,
            "sourceType": "manual_seed",
            "notes": "Delta Air Lines is sensitive to global oil shocks and rising jet fuel costs resulting from logistics and supply chain strains.",
            "lastReviewedAt": "2026-05-28"
        }
    ]
}
