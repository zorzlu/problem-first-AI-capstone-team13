"""Replay scenario article datasets used in no-key / demo mode."""

SCENARIOS = {
    "direct_news": {
        "name": "Scenario 1: Direct Company Announcements",
        "description": "Simulates standard, direct company-level catalyst news tagged with ticker symbols.",
        "articles": [
            {
                "articleId": "finnhub_direct_001",
                "sourceApi": "finnhub",
                "sourceName": "Finnhub Financial News",
                "url": "https://finnhub.io/news/aapl/m5-announcement",
                "headline": "Apple Inc. (AAPL) Unveils Next-Gen M5 Chip Architecture Engineered with 2nm Tech for On-Device AI",
                "summary": "Today Apple officially announced its M5 chip family, which will power upcoming MacBooks and iPads. The processor leverages TSMC's 2nm lithography to deliver 40% faster local LLM processing and improved thermal efficiency.",
                "publishedAt": "2026-05-28T17:20:00Z",
                "relatedTickers": ["AAPL"]
            },
            {
                "articleId": "finnhub_direct_002",
                "sourceApi": "finnhub",
                "sourceName": "Tech Market Dispatch",
                "url": "https://finnhub.io/news/msft/copilot-revenue",
                "headline": "Microsoft (MSFT) Exceeds Guidance as Copilot Subscriptions Drive 28% Cloud Revenue Expansion",
                "summary": "Microsoft Corp announced its latest financial metrics, showing cloud services grew 28% year over year, heavily boosted by corporate adoption of Microsoft 365 Copilot integrations.",
                "publishedAt": "2026-05-28T17:21:00Z",
                "relatedTickers": ["MSFT"]
            }
        ]
    },
    "duplicate_news": {
        "name": "Scenario 2: Duplicate Spam & Story Updates",
        "description": "Simulates repetitive reports and subsequent story updates to test catalyst ledger deduplication.",
        "articles": [
            {
                "articleId": "finnhub_dup_001",
                "sourceApi": "finnhub",
                "sourceName": "Global Wire News",
                "url": "https://finnhub.io/news/aapl/foxconn-fire",
                "headline": "Fire Reported at Major Electronics Plant in Zhengzhou Assembly Zone; iPhone Lines Affected",
                "summary": "Local emergency services were called to an industrial facility in Zhengzhou. Unconfirmed reports state a small fire broke out in a component warehouse. Authorities say no casualties are reported.",
                "publishedAt": "2026-05-28T17:20:00Z",
                "relatedTickers": ["AAPL"]
            },
            {
                "articleId": "finnhub_dup_002",
                "sourceApi": "finnhub",
                "sourceName": "Syndicated Press Association",
                "url": "https://finnhub.io/news/aapl/zhengzhou-factory-incident",
                "headline": "Factory Incident in Zhengzhou Electronics Zone Challenges Smartphone Supply Chains",
                "summary": "Emergency units responded to a fire in a Zhengzhou electronics manufacturing plant. The incident took place near assembly warehouses. Investigators are examining potential damage to hardware supplies.",
                "publishedAt": "2026-05-28T17:21:30Z",
                "relatedTickers": ["AAPL"]
            },
            {
                "articleId": "finnhub_dup_003",
                "sourceApi": "finnhub",
                "sourceName": "Market Intel Weekly",
                "url": "https://finnhub.io/news/aapl/foxconn-halt",
                "headline": "Update: Foxconn Confirms Zhengzhou Fire Halted Apple iPhone Production Lines; 2M Units Impacted",
                "summary": "Foxconn issued a statement confirming a fire in Zhengzhou factory warehouse, leading to a complete shutdown of advanced assembly lines. Analysts estimate the halt will delay shipment of 2 million iPhone units, representing a high material hit.",
                "publishedAt": "2026-05-28T17:24:00Z",
                "relatedTickers": ["AAPL"]
            }
        ]
    },
    "cross_impact": {
        "name": "Scenario 3: Geopolitical, Tech, & Supply-Chain Cross-Impact",
        "description": "Simulates broad, untickered external events. Checks if the system correctly routes them through the exposure graph.",
        "articles": [
            {
                "articleId": "currents_cross_001",
                "sourceApi": "currents",
                "sourceName": "Taipei Daily Tribune",
                "url": "https://currentsapi.services/news/taiwan-earthquake",
                "headline": "Major 7.2 Magnitude Earthquake Strikes Eastern Taiwan; High-Tech Foundries Evacuate Fabs",
                "summary": "A powerful 7.2 magnitude earthquake shook eastern Taiwan today. High-tech manufacturing facilities in Hsinchu Science Park, including advanced semiconductor silicon fabs, evacuated staff. Initial reports indicate possible precision calibration damage to high-end lithography equipment.",
                "publishedAt": "2026-05-28T17:20:00Z",
                "relatedTickers": []  # Untickered external event!
            },
            {
                "articleId": "currents_cross_002",
                "sourceApi": "currents",
                "sourceName": "AI Innovation Monitor",
                "url": "https://currentsapi.services/news/anthropic-claude",
                "headline": "Anthropic Launches Claude 3.7 Sonnet, Redefining LLM Benchmarks for Complex Reasoning",
                "summary": "Anthropic PBC has officially launched Claude 3.7 Sonnet. The model achieves state-of-the-art results on software engineering, mathematical proofing, and chemical synthesis benchmarks, outperforming comparable open and closed model platforms.",
                "publishedAt": "2026-05-28T17:21:00Z",
                "relatedTickers": []  # Untickered external event!
            },
            {
                "articleId": "currents_cross_003",
                "sourceApi": "currents",
                "sourceName": "Middle East Shipping Journal",
                "url": "https://currentsapi.services/news/red-sea-disruption",
                "headline": "Drone Attacks Force Global Freight Carriers to Abandon Red Sea Routing, Skyrocketing Rates",
                "summary": "Two large cargo ships were targeted by drone strikes near the Bab el-Mandeb strait. In response, major maritime shipping alliances announced a complete suspension of Red Sea and Suez Canal routes, directing vessels around the Cape of Good Hope. Spot container rates surged 30% along with oil logistics surcharges.",
                "publishedAt": "2026-05-28T17:22:00Z",
                "relatedTickers": []  # Untickered external event!
            }
        ]
    }
}
