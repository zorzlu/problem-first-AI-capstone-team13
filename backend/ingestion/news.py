import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from backend.core.config import FINNHUB_API_KEY, CURRENTS_API_KEY, FRESHNESS_LOOKBACK_MINUTES
from backend.ingestion.scenarios import SCENARIOS

def normalize_iso_timestamp(ts: str) -> datetime:
    """Helper to convert various timestamp formats to timezone-aware datetime."""
    try:
        # Standard ISO format with 'Z'
        if ts.endswith('Z'):
            return datetime.fromisoformat(ts[:-1]).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        # Fallback to current time if parsing fails
        return datetime.now(timezone.utc)

def fetch_finnhub_direct_news(symbol: str, minutes_lookback: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches company-specific news from Finnhub.
    API: GET /company-news?symbol={symbol}&from={date}&to={date}
    """
    if not FINNHUB_API_KEY:
        print(f"Warning: Finnhub API Key not set. Direct news fetch for {symbol} skipped.")
        return []

    now = datetime.now(timezone.utc)
    # Finnhub requires YYYY-MM-DD
    today_str = now.strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": symbol,
        "from": today_str,
        "to": today_str,
        "token": FINNHUB_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Finnhub API error ({response.status_code}): {response.text}")
            return []
        
        articles = response.json()
        normalized = []
        for art in articles:
            # Finnhub timestamp is unix epoch in seconds
            published_dt = datetime.fromtimestamp(art.get("datetime", 0), timezone.utc)
            
            normalized.append({
                "articleId": f"finnhub_{art.get('id', '')}",
                "sourceApi": "finnhub",
                "sourceName": art.get("source", "Finnhub"),
                "url": art.get("url", ""),
                "headline": art.get("headline", ""),
                "summary": art.get("summary", ""),
                "publishedAt": published_dt.isoformat(),
                "relatedTickers": [symbol]
            })
        return normalized
    except Exception as e:
        print(f"Error fetching Finnhub news for {symbol}: {e}")
        return []

def _fetch_currents_search(
    keywords: List[str],
    *,
    source_api: str,
    related_tickers: Optional[List[str]] = None,
    query_label: str = "currents",
) -> List[Dict[str, Any]]:
    if not CURRENTS_API_KEY:
        print(f"Warning: Currents API Key not set. {query_label} fetch skipped.")
        return []

    if not keywords:
        return []

    keywords = [k for k in keywords if k]
    query_str = " OR ".join(keywords)
    print(f"Currents {query_label} query terms ({len(keywords)}): {keywords}")
    url = f"https://api.currentsapi.services/v1/search"
    params = {
        "keywords": query_str,
        "language": "en",
        "apiKey": CURRENTS_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Currents API error ({response.status_code}): {response.text}")
            return []
        
        data = response.json()
        articles = data.get("news", [])
        normalized = []
        for art in articles:
            # Currents uses standard ISO string for published
            normalized.append({
                "articleId": f"currents_{art.get('id', '')}",
                "sourceApi": source_api,
                "sourceName": art.get("author", "Currents"),
                "url": art.get("url", ""),
                "headline": art.get("title", ""),
                "summary": art.get("description", ""),
                "publishedAt": art.get("published", ""),
                "relatedTickers": related_tickers or [],
                "queryTerms": keywords,
            })
        return normalized
    except Exception as e:
        print(f"Error fetching Currents {query_label} news: {e}")
        return []


def fetch_currents_cross_impact_news(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Fetches broad external news from Currents API matching high-signal cross-impact terms.
    API: GET /search?keywords={query}&language=en
    """
    # Currents OR queries get noisy fast. The graph layer already ranks terms; keep this tight.
    return _fetch_currents_search(
        keywords[:25],
        source_api="currents",
        related_tickers=[],
        query_label="cross-impact",
    )


def _company_query_terms(symbol: str) -> List[str]:
    """Targeted Currents terms for one public company, separate from broad graph themes."""
    symbol = (symbol or "").upper()
    terms = [f"${symbol}"]
    try:
        from backend.graph.graph import get_graph
        nodes = get_graph().get("nodes", [])
    except Exception:
        nodes = []

    node = next((n for n in nodes if (n.get("ticker") or "").upper() == symbol), None)
    if node:
        candidates = [node.get("name", "")]
        candidates.extend(node.get("aliases", []))
        candidates.extend(node.get("queryTerms", []))
    else:
        candidates = [symbol]

    generic_aliases = {
        "ai", "ml", "app", "mac", "core", "arc", "power", "water", "coffee",
        "pizza", "taco", "hamburgers", "cafe", "chips", "gaming", "android",
        "iphone", "ipad", "airpods", "apple watch", "cloud computing",
        "cloud services", "data centers", "financial software", "fast food",
        "franchising", "advertising technology", "mobile marketing",
    }
    legal_markers = ("inc", "corp", "corporation", "technologies", "systems", "brands", "air lines", "semiconductor")
    for raw in candidates:
        term = re.sub(r"\s+", " ", str(raw or "").strip())
        if not term:
            continue
        lower = term.lower().strip(".,")
        if lower == symbol.lower() or lower in generic_aliases:
            continue
        if len(term) <= 2:
            continue
        # Keep legal/company names and a few distinctive brands; skip product/category aliases.
        if any(marker in lower for marker in legal_markers) or len(term.split()) <= 2:
            terms.append(term)

    deduped = []
    seen = set()
    for term in terms:
        key = term.lower()
        if key not in seen:
            deduped.append(term)
            seen.add(key)
    return deduped[:5]


def fetch_currents_company_news(symbols: List[str]) -> List[Dict[str, Any]]:
    """Run targeted Currents searches per company/ticker in parallel."""
    if not CURRENTS_API_KEY or not symbols:
        if not CURRENTS_API_KEY:
            print("Warning: Currents API Key not set. Company news fetch skipped.")
        return []

    ordered_symbols = []
    seen = set()
    for symbol in symbols:
        s = (symbol or "").upper()
        if s and s not in seen:
            ordered_symbols.append(s)
            seen.add(s)

    results = []
    max_workers = min(8, max(1, len(ordered_symbols)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _fetch_currents_search,
                _company_query_terms(symbol),
                source_api="currents_company",
                related_tickers=[symbol],
                query_label=f"company:{symbol}",
            ): symbol
            for symbol in ordered_symbols
        }
        for future in as_completed(futures):
            results.extend(future.result())
    return results


_BLOCKED_CURRENTS_DOMAINS = {
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "dev.to", "www.dev.to",
    "wikipedia.org", "en.wikipedia.org",
    "buzzfeed.com", "www.buzzfeed.com",
    "thefashionspot.com", "www.thefashionspot.com",
    "nocodefunctions.com", "shivekkhurana.com",
}

_CURRENTS_FILING_NOISE = (
    "form 13f", "13f filing", "holdings boosted", "stock holdings boosted",
    "lowers position", "lowers stock holdings", "decreases stock holdings",
    "sells shares", "sold by", "makes new investment", "acquires shares",
)

_CURRENTS_MARKET_CATALYST_TERMS = (
    "$", "%", "earnings", "guidance", "revenue", "profit", "margin",
    "contract", "government contract", "acquisition", "merger", "raises",
    "funding", "launches", "unveils", "benchmark", "outperforms",
    "data center", "ai model", "export controls", "tariff", "sanction",
    "antitrust", "lawsuit", "probe", "investigation", "federal reserve",
    "interest rates", "oil price", "jet fuel", "red sea", "suez",
    "bab el-mandeb", "shipping", "freight", "earthquake", "factory",
    "supply chain", "semiconductor", "foundry", "outage", "halts",
    "delay", "disruption",
    "stock", "shares", "analyst", "price target", "tailwind", "headwind",
    "bullish", "bearish", "upgrade", "downgrade", "investor", "market",
)

_CURRENTS_COMPANY_ATTENTION_TERMS = (
    "new", "reveals", "revealed", "launches", "launched", "unveils", "unveiled",
    "debut", "debuts", "prototype", "concept", "model", "product", "design",
    "redesign", "review", "reviews", "reaction", "reactions", "backlash",
    "criticism", "criticized", "disappointing", "disappoints", "disappointed",
    "expectations", "underwhelming", "praised", "hyped", "viral", "delay",
    "recall", "quality", "safety", "demand", "orders", "preorders",
)


def _domain_for_url(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _term_matches_article(term: str, text: str) -> bool:
    term = (term or "").strip().lower()
    if not term:
        return False
    if len(term.split()) == 1:
        return f" {term} " in f" {text} "
    return term in text


def is_relevant_live_article(art: Dict[str, Any], cross_impact_keywords: List[str]) -> bool:
    """Hard gate for live API noise before the extraction LLM sees the article."""
    if art.get("sourceApi") == "finnhub":
        return True

    headline = art.get("headline", "") or ""
    summary = art.get("summary", "") or ""
    text = f"{headline} {summary}".lower()
    url = art.get("url", "") or ""
    domain = _domain_for_url(url)
    source_name = (art.get("sourceName") or "").lower()

    if domain in _BLOCKED_CURRENTS_DOMAINS:
        return False
    if source_name.startswith("/u/"):
        return False
    if any(noise in text for noise in _CURRENTS_FILING_NOISE):
        return False

    if art.get("sourceApi") == "currents_company":
        query_hit = any(_term_matches_article(term, text) for term in art.get("queryTerms", []))
        ticker_hit = any(
            re.search(rf"\${re.escape(t)}\b|\bNASDAQ:{re.escape(t)}\b|\bNYSE:{re.escape(t)}\b", headline + " " + summary, re.IGNORECASE)
            for t in art.get("relatedTickers", [])
        )
        catalyst_hit = any(term in text for term in _CURRENTS_MARKET_CATALYST_TERMS)
        attention_hit = any(term in text for term in _CURRENTS_COMPANY_ATTENTION_TERMS)
        return (query_hit and (catalyst_hit or attention_hit)) or ticker_hit

    keyword_hit = any(_term_matches_article(term, text) for term in cross_impact_keywords)
    catalyst_hit = any(term in text for term in _CURRENTS_MARKET_CATALYST_TERMS)
    ticker_hit = bool(re.search(r"\$[A-Z]{1,5}\b|\bNASDAQ:|\bNYSE:", headline + " " + summary))

    return (keyword_hit and catalyst_hit) or ticker_hit

def get_news_payload(
    symbol_watchlist: List[str],
    cross_impact_keywords: List[str],
    scenario_id: str = "live",
    simulated_now_str: str = "2026-05-28T17:25:00Z",
    extra_tickers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Fetches news from either live APIs or scenario mock data.
    Applies the freshness window filter: articles published in the last N minutes 
    (where N is FRESHNESS_LOOKBACK_MINUTES).
    """
    all_articles = []
    
    if scenario_id != "live":
        # Load simulated scenario articles
        scenario = SCENARIOS.get(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found.")
        
        all_articles = list(scenario["articles"])
        # Use simulated 'now' for filtering
        reference_time = normalize_iso_timestamp(simulated_now_str)
        print(f"Replay Scenario Active: {scenario['name']}")
        print(f"Simulating time: {reference_time.isoformat()}")
    else:
        # Fetch Live
        tickers_to_query = list(symbol_watchlist)
        if extra_tickers:
            tickers_to_query.extend([t for t in extra_tickers if t not in tickers_to_query])
            
        print(f"Live Ingestion Active. Watchlist Tickers: {symbol_watchlist}. Extra Tickers: {extra_tickers}. Cross-impact Keywords: {cross_impact_keywords}")
        # Fetch Finnhub direct company-news for all target tickers
        for symbol in tickers_to_query:
            all_articles.extend(fetch_finnhub_direct_news(symbol))

        # Fetch targeted Currents company news in parallel as a second direct-news source.
        # This catches companies Finnhub misses and often surfaces richer finance/tech coverage.
        all_articles.extend(fetch_currents_company_news(tickers_to_query))
        
        # Fetch Currents cross-impact news
        if cross_impact_keywords:
            all_articles.extend(fetch_currents_cross_impact_news(cross_impact_keywords))
            
        reference_time = datetime.now(timezone.utc)

    # Apply freshness filter: last N minutes lookback buffer
    filtered_articles = []
    seen_urls = set()
    
    print(f"Filtering articles using FRESHNESS_LOOKBACK_MINUTES = {FRESHNESS_LOOKBACK_MINUTES} mins (relative to reference time: {reference_time.isoformat()})")
    for art in all_articles:
        url = art.get("url", "")
        if not url or url in seen_urls:
            continue
        
        pub_time = normalize_iso_timestamp(art.get("publishedAt", ""))
        time_diff_sec = (reference_time - pub_time).total_seconds()
        delta_mins = time_diff_sec / 60.0
        
        # Log each article details to show user time delta
        print(f"  - Article: '{art.get('headline')[:60]}...' | Published: {art.get('publishedAt')} | Delta: {delta_mins:.2f} mins")
        
        # Freshness filter:
        # - not in the future (relative to reference_time)
        # - published within the configured lookback window
        is_fresh = 0 <= time_diff_sec <= (FRESHNESS_LOOKBACK_MINUTES * 60)
        
        relevance_ok = scenario_id != "live" or is_relevant_live_article(art, cross_impact_keywords)
        if is_fresh and not relevance_ok:
            print("    skipped: failed live relevance gate")

        if (is_fresh and relevance_ok) or scenario_id != "live":
            filtered_articles.append(art)
            seen_urls.add(url)
            
    print(f"Ingested {len(all_articles)} articles, {len(filtered_articles)} passed freshness filter.")
    
    return {
        "articles": filtered_articles,
        "total_ingested": len(all_articles),
        "passed_freshness": len(filtered_articles)
    }
