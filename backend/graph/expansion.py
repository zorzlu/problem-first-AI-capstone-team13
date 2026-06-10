"""
Exposure-graph expansion.

When a ticker is added to the watchlist, the add itself is NOT blocked: the LLM-driven
expansion runs afterwards as a background task. It discovers the causal exposure
surrounding the ticker (suppliers, customers, competitors, partners, regions, technology
themes, macro/commodity risk factors, shipping routes) and merges the resulting nodes
and edges into the live exposure graph. Per-ticker progress is tracked in an in-memory
status store so the UI can show a pending/ready/failed state and offer a manual re-run.
It is NOT re-run on pipeline refreshes.
"""
import json
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, Any, List, Literal, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.llm import get_graph_expansion_llm, has_llm_for_step
from backend.core.logging import get_logger
from backend.iterations.common import invoke_with_retry
from backend.graph.graph import get_graph, add_graph_node, add_graph_edge, graph_lock
from backend.storage.persistence import save_graph

logger = get_logger(__name__)


# Node/edge vocabulary mirrors backend/seed_data.py so generated graph elements are
# interchangeable with the manually seeded ones.
VALID_NODE_TYPES = {
    "ticker",
    "private_company",
    "country",
    "region",
    "policy_area",
    "government_agency",
    "technology_theme",
    "shipping_route",
    "risk_factor",
    "sector",
    "commodity",
}

VALID_EDGE_TYPES = {
    "supplier_of",
    "customer_of",
    "competitor_of",
    "partner_of",
    "technology_exposure",
    "regional_exposure",
    "shipping_exposure",
    "macro_sensitivity",
    "policy_exposure",
    "defense_exposure",
    "trade_exposure",
    "sector_exposure",
    "commodity_exposure",
}


class GraphExpansionError(Exception):
    """Raised when a configured LLM fails to produce a usable expansion."""


# Structured-output schemas (constrained decoding). Binding these via
# `.with_structured_output(...)` guarantees the model emits schema-valid JSON, so a
# missing delimiter can never sink an expansion. The referential-integrity checks
# below (edges must point at known nodeIds) still run — structured outputs enforces
# SHAPE, not whether a generated nodeId actually exists in the graph.
NodeTypeLiteral = Literal[
    "ticker", "private_company", "country", "region", "policy_area",
    "government_agency", "technology_theme", "shipping_route", "risk_factor",
    "sector", "commodity",
]
EdgeTypeLiteral = Literal[
    "supplier_of", "customer_of", "competitor_of", "partner_of",
    "technology_exposure", "regional_exposure", "shipping_exposure",
    "macro_sensitivity", "policy_exposure", "defense_exposure",
    "trade_exposure", "sector_exposure", "commodity_exposure",
]


class ExpansionNode(BaseModel):
    nodeId: str
    nodeType: NodeTypeLiteral
    name: str
    ticker: Optional[str] = None
    aliases: List[str]
    queryTerms: List[str]


class ExpansionEdge(BaseModel):
    fromNodeId: str
    toNodeId: str
    edgeType: EdgeTypeLiteral
    strength: Literal["high", "medium", "low"]
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str


class GraphExpansionResult(BaseModel):
    nodes: List[ExpansionNode]
    edges: List[ExpansionEdge]


# ---------------------------------------------------------------------------
# Per-ticker expansion status store (in-memory; drives the UI pending indicator)
# ---------------------------------------------------------------------------
# status: "pending" (queued) | "running" | "done" | "skipped" | "failed"
_expansion_status: Dict[str, Dict[str, Any]] = {}
_status_lock = RLock()
_expansion_lock = RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_status(ticker: str, status: str, **extra: Any) -> None:
    entry = {"ticker": ticker, "status": status, "updatedAt": _now_iso()}
    entry.update(extra)
    with _status_lock:
        _expansion_status[ticker] = entry


def get_expansion_status() -> Dict[str, Dict[str, Any]]:
    """Returns the full per-ticker expansion status map."""
    with _status_lock:
        return {ticker: dict(status) for ticker, status in _expansion_status.items()}


def mark_pending(ticker: str) -> None:
    """Marks a ticker as queued for expansion (called before scheduling the task)."""
    _set_status(ticker.strip().upper(), "pending")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_finnhub_peers(symbol: str) -> List[str]:
    """Queries Finnhub for the peers of a given stock symbol."""
    from backend.core.config import FINNHUB_API_KEY
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set. Cannot fetch peers for %s.", symbol)
        return []
    
    url = "https://finnhub.io/api/v1/stock/peers"
    params = {
        "symbol": symbol,
        "token": FINNHUB_API_KEY
    }
    try:
        import requests
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            peers = response.json()
            if isinstance(peers, list):
                # Filter out the symbol itself or invalid entries
                return [p for p in peers if p and p != symbol]
        else:
            logger.error("Finnhub Peers API error (%s): %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Error fetching peers for %s: %s", symbol, e)
    return []


SYSTEM_PROMPT = """You are a financial exposure-graph architect. A new stock ticker has just been added to an intraday trading watchlist.
Your job is to map the causal exposure surrounding this ticker COMPREHENSIVELY, so a news system can route INDIRECT news \
(supply-chain disruptions, geopolitics, technology themes, macro shocks, commodities, competitors, key partners) to this ticker.

You will be given:
- The new ticker symbol.
- A list of known stock peers/competitors of this ticker (from Finnhub API).
- The nodes ALREADY in the exposure graph (each with nodeId, name, nodeType, and optionally ticker and aliases).

Return a single JSON object with two keys: "nodes" and "edges".

"nodes": a list of NEW nodes to add. Do NOT duplicate nodes that already exist — reference those by their existing nodeId inside "edges" instead.
You MUST include exactly one node for the ticker itself:
{
  "nodeId": "ticker_<SYMBOL>",
  "nodeType": "ticker",
  "name": "<Full Company Name, e.g., Apple Inc. or Microsoft Corp.>",
  "ticker": "<SYMBOL>",
  "aliases": ["common company names, e.g. Google, Alphabet"],
  "queryTerms": ["search keywords: company name, ticker, flagship products/brands"]
}
For each relevant exposure entity that is NOT already in the graph, add a node. 
For companies (suppliers, customers, competitors, partners), write their full name in "name".
If a company is public and has a stock ticker, use nodeType "ticker" and include ticker.
Use nodeType "private_company" ONLY for non-public/private actors such as OpenAI,
Mistral AI, Anthropic, Claude, Reflection AI, or government-owned/non-listed entities.
{
  "nodeId": "<type>_<ShortName>",   e.g. supplier_Foxconn, region_Taiwan, theme_semiconductors, risk_oil_price, commodity_lithium, route_Red_Sea, sector_cloud
  "nodeType": "ticker" | "private_company" | "country" | "region" | "policy_area" | "government_agency" | "technology_theme" | "shipping_route" | "risk_factor" | "sector" | "commodity",
  "name": "Human readable full name of the company or entity (e.g. Hon Hai Precision Industry or Advanced Micro Devices)",
  "ticker": "Stock ticker symbol if public, otherwise null or omit",
  "aliases": ["alternative names/tickers"],
  "queryTerms": ["news search keywords for this entity"]
}

"edges": a list of directed exposure edges. Point each edge FROM the cause/source node TO the affected node (usually the ticker).
Create competitor_of edges using the provided known stock peers!
{
  "fromNodeId": "<source nodeId — a new node OR an existing nodeId from the provided list>",
  "toNodeId": "ticker_<SYMBOL>  (or another node when modelling an intermediate hop)",
  "edgeType": "supplier_of" | "customer_of" | "competitor_of" | "partner_of" | "technology_exposure" | "regional_exposure" | "shipping_exposure" | "macro_sensitivity" | "policy_exposure" | "defense_exposure" | "trade_exposure" | "sector_exposure" | "commodity_exposure",
  "strength": "high" | "medium" | "low",
  "confidence": 0.0-1.0,
  "notes": "one sentence explaining the causal relationship"
}

Rules:
1. REUSE existing nodes: if an exposure entity already exists in the provided node list (e.g. theme_semiconductors, region_Taiwan, ticker_TSM), reference its EXACT existing nodeId in edges — do NOT create a duplicate node.
2. Avoid duplicates by comparing aliases and tickers. If the company exists under a different name (e.g. TSM exists as ticker_TSM), do not create supplier_TSMC.
3. Be COMPREHENSIVE, not conservative. Produce roughly 8-15 exposure links covering the full surface: key SUPPLIERS, major CUSTOMERS, direct COMPETITORS (use the known stock peers provided), strategic PARTNERS, regions/countries of operation or revenue concentration, policy areas (US politics, EU regulation, export controls, defense spending), relevant technology themes, input COMMODITIES, macro/rate/fuel sensitivities, and shipping/logistics routes where they genuinely apply. Include both strong and plausible-but-secondary links (use confidence to grade them) — a sparse graph misses cross-impact news.
4. CONNECT TO OTHER WATCHLIST TICKERS when a real relationship exists: if an existing ticker_* node is a supplier, customer, or competitor of the new ticker, add that edge (e.g. competitor_of between two chipmakers, supplier_of from a foundry ticker to a fabless ticker).
5. Use only REAL, well-known entities. Do NOT invent companies.
6. confidence reflects how directly the source moves this ticker intraday (0.9+ = near-certain causal link, 0.6 = relevant, 0.45 = plausible/marginal). Do not omit a real link just because it is secondary — grade it with a lower confidence instead.
7. Every edge's fromNodeId and toNodeId must be either the new ticker node, one of your new nodes, or an existing nodeId from the provided list.
8. EDGE DIRECTION: Point each edge FROM the cause/source node TO the affected node. For exposure/sensitivity edges (regional_exposure, technology_exposure, shipping_exposure, macro_sensitivity, policy_exposure, defense_exposure, trade_exposure, sector_exposure, commodity_exposure), the country/region/policy/agency/theme/route/risk_factor/sector/commodity is the CAUSE (fromNodeId) and the company/ticker is the AFFECTED node (toNodeId). Do NOT reverse this (e.g., fromNodeId="country_United_States", toNodeId="ticker_MCD" is correct; fromNodeId="ticker_MCD", toNodeId="country_United_States" is incorrect).
9. Model government and policy catalysts explicitly when relevant. Examples:
   - United States / US politics / US federal procurement / Department of Defense spending can affect Microsoft through Azure Government, defense cloud, cybersecurity, and public-sector software demand.
   - US export controls, tariffs, antitrust, or immigration policy can affect US companies and non-US exporters selling into the US.
   - EU regulation can affect US platforms and EU exporters through compliance, privacy, competition, and trade channels.
"""


def _bare_ticker_node(ticker: str) -> Dict[str, Any]:
    return {
        "nodeId": f"ticker_{ticker}",
        "nodeType": "ticker",
        "name": ticker,
        "ticker": ticker,
        "aliases": [ticker],
        "queryTerms": [ticker],
    }


def find_matching_node(new_node: Dict[str, Any], existing_nodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Helper to check if a new node matches an existing node in the graph by ticker, name, or aliases."""
    new_type = new_node.get("nodeType")
    new_name = new_node.get("name", "").strip().lower()
    new_ticker = new_node.get("ticker")
    new_ticker_clean = new_ticker.strip().upper() if new_ticker else ""
    new_aliases = [a.strip().lower() for a in new_node.get("aliases", []) if a]

    is_new_company = new_type in ("ticker", "private_company")

    for e in existing_nodes:
        e_type = e.get("nodeType")
        is_e_company = e_type in ("ticker", "private_company")
        new_type_cmp = "region" if new_type == "country" else new_type
        e_type_cmp = "region" if e_type == "country" else e_type
        
        # If one is a company and the other is not, they don't match
        if is_new_company != is_e_company:
            if new_type_cmp != e_type_cmp:
                continue
        elif not is_new_company:
            # For non-companies, type must match exactly
            if new_type_cmp != e_type_cmp:
                continue

        # 1. Match by ticker if both have tickers
        e_ticker = e.get("ticker")
        e_ticker_clean = e_ticker.strip().upper() if e_ticker else ""
        if new_ticker_clean and e_ticker_clean:
            if new_ticker_clean == e_ticker_clean:
                return e

        # 2. Match by exact name
        e_name = e.get("name", "").strip().lower()
        if new_name == e_name:
            return e

        # 3. Match by name vs aliases or vice versa
        e_aliases = [a.strip().lower() for a in e.get("aliases", []) if a]
        if new_name in e_aliases:
            return e
        if e_name in new_aliases:
            return e
            
        # Check if any alias matches
        if set(new_aliases) & set(e_aliases):
            return e

        # 4. Fallback: match ticker to name / aliases or vice versa
        if is_new_company:
            if new_ticker_clean and new_ticker_clean.lower() == e_name:
                return e
            if e_ticker_clean and e_ticker_clean.lower() == new_name:
                return e
            if new_ticker_clean and new_ticker_clean.lower() in e_aliases:
                return e
            if e_ticker_clean and e_ticker_clean.lower() in new_aliases:
                return e

    return None


def expand_graph_for_ticker(ticker: str, force: bool = False) -> Dict[str, Any]:
    """
    Discovers and merges exposure-graph nodes/edges for a ticker.

    Behaviour:
      - If the ticker node already exists and ``force`` is False, this is a no-op
        (automatic expansion runs once per ticker).
      - With ``force=True`` (manual re-run), it re-queries the LLM and merges again,
        enriching the existing subgraph (merges are idempotent by nodeId / edge pair).
      - With no LLM keys configured (demo/mock mode), adds only the bare ticker node.
      - Raises GraphExpansionError if a configured LLM call fails or returns unusable output.

    Returns a summary dict. Does NOT persist or update status — see process_ticker_expansion.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise GraphExpansionError("Empty ticker symbol.")

    ticker_node_id = f"ticker_{ticker}"
    existing_nodes = get_graph()["nodes"]
    already_present = any(n.get("nodeType") == "ticker" and n.get("ticker") == ticker for n in existing_nodes)

    # Automatic expansion is once-per-ticker. A manual re-run (force=True) bypasses this.
    if already_present and not force:
        logger.info("%s already in graph — skipping expansion.", ticker)
        return {"ticker": ticker, "addedNodes": 0, "addedEdges": 0, "usedLLM": False, "skipped": True}

    # Demo/mock mode: no LLM available. Register the bare ticker node so cross-impact
    # routing has a valid target; richer links require API keys.
    if not has_llm_for_step("graph_expansion"):
        bare_node = _bare_ticker_node(ticker)
        matched_node = find_matching_node(bare_node, existing_nodes)
        added_nodes = 1
        if matched_node:
            matched_node["nodeType"] = "ticker"
            add_graph_node(matched_node)
            added_nodes = 0
            logger.warning("No LLM keys configured — upgraded existing node to ticker for %s.", ticker)
        else:
            add_graph_node(bare_node)
            logger.warning("No LLM keys configured — added bare node for %s only.", ticker)
        return {"ticker": ticker, "addedNodes": added_nodes, "addedEdges": 0, "usedLLM": False}

    # --- LLM-driven expansion ---
    existing_context = []
    for n in existing_nodes:
        ctx = {"nodeId": n["nodeId"], "name": n["name"], "nodeType": n["nodeType"]}
        if n.get("ticker"):
            ctx["ticker"] = n["ticker"]
        if n.get("aliases"):
            ctx["aliases"] = n["aliases"]
        existing_context.append(ctx)

    peers = fetch_finnhub_peers(ticker)
    peers_str = ", ".join(peers) if peers else "None detected"

    user_prompt = (
        f"NEW TICKER: {ticker}\n"
        f"KNOWN STOCK PEERS/COMPETITORS FROM FINNHUB: {peers_str}\n\n"
        f"EXISTING GRAPH NODES (reuse these nodeIds in edges where relevant):\n"
        f"{json.dumps(existing_context, indent=2)}\n\n"
        f"Map the causal exposure for {ticker} and return the JSON object."
    )

    try:
        from opentelemetry import trace as otel_trace
        tracer = otel_trace.get_tracer("cross-impact-catalysts")
        try:
            from openinference.semconv.trace import SpanAttributes
            OPENINFERENCE_SPAN_KIND = SpanAttributes.OPENINFERENCE_SPAN_KIND
            INPUT_VALUE = SpanAttributes.INPUT_VALUE
            OUTPUT_VALUE = SpanAttributes.OUTPUT_VALUE
        except ImportError:
            OPENINFERENCE_SPAN_KIND = "openinference.span.kind"
            INPUT_VALUE = "input.value"
            OUTPUT_VALUE = "output.value"
    except Exception:
        tracer = None

    try:
        if tracer:
            span_name = f"Graph Expansion LLM Call ({ticker})"
            with tracer.start_as_current_span(span_name) as llm_span:
                llm_span.set_attribute("ticker", ticker)
                llm_span.set_attribute(OPENINFERENCE_SPAN_KIND, "LLM")
                
                # Tag with the LLM model name if available
                base_llm = get_graph_expansion_llm()
                model_name = getattr(base_llm, "model_name", getattr(base_llm, "model", "unknown"))
                llm_span.set_attribute("llm.model_name", model_name)
                
                llm_span.set_attribute(INPUT_VALUE, user_prompt)
                
                llm = base_llm.with_structured_output(GraphExpansionResult)
                result: GraphExpansionResult = invoke_with_retry(
                    llm,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)],
                    label=f"graph expansion for {ticker}",
                )
                payload = result.model_dump()
                llm_span.set_attribute(OUTPUT_VALUE, json.dumps(payload))
        else:
            llm = get_graph_expansion_llm().with_structured_output(GraphExpansionResult)
            result: GraphExpansionResult = invoke_with_retry(
                llm,
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)],
                label=f"graph expansion for {ticker}",
            )
            payload = result.model_dump()
    except Exception as e:
        raise GraphExpansionError(f"LLM expansion failed for {ticker}: {e}") from e

    raw_nodes = payload["nodes"]
    raw_edges = payload["edges"]

    # --- Validate, deduplicate & collect new nodes ---
    clean_nodes: List[Dict[str, Any]] = []
    seen_node_ids = set()
    resolved_node_ids = {}
    reference_nodes = list(existing_nodes)

    for n in raw_nodes:
        if not isinstance(n, dict):
            continue
        node_id = n.get("nodeId")
        node_type = n.get("nodeType")
        name = n.get("name")
        if not node_id or not name or node_type not in VALID_NODE_TYPES:
            logger.warning("Dropping invalid node: %s", n)
            continue

        # Check if node matches any reference node
        matched_node = find_matching_node(n, reference_nodes)
        if matched_node:
            logger.info(
                "Resolving duplicate node: %s (%s) -> %s (%s)",
                node_id, name, matched_node["nodeId"], matched_node["name"],
            )
            resolved_node_ids[node_id] = matched_node["nodeId"]
            
            # Enrich existing node in-place
            matched_node["aliases"] = list(set(matched_node.get("aliases", []) + n.get("aliases", [])))
            matched_node["queryTerms"] = list(set(matched_node.get("queryTerms", []) + n.get("queryTerms", [])))
            if n.get("ticker") and not matched_node.get("ticker"):
                matched_node["ticker"] = n.get("ticker")
            if n.get("nodeType") == "ticker":
                matched_node["nodeType"] = "ticker"
                
            # Save updated node
            add_graph_node(matched_node)
            continue

        if node_id in seen_node_ids:
            continue

        seen_node_ids.add(node_id)
        new_node_dict = {
            "nodeId": node_id,
            "nodeType": node_type,
            "name": name,
            "ticker": n.get("ticker"),
            "aliases": n.get("aliases", []) or [],
            "queryTerms": n.get("queryTerms", []) or [],
        }
        clean_nodes.append(new_node_dict)
        reference_nodes.append(new_node_dict)

    # Guarantee the ticker node exists even if the LLM omitted it.
    if not any(n.get("nodeType") == "ticker" and n.get("ticker") == ticker for n in reference_nodes):
        bare_node = _bare_ticker_node(ticker)
        matched_node = find_matching_node(bare_node, reference_nodes)
        if matched_node:
            resolved_node_ids[ticker_node_id] = matched_node["nodeId"]
            matched_node["nodeType"] = "ticker"
            add_graph_node(matched_node)
        else:
            clean_nodes.append(bare_node)
            seen_node_ids.add(ticker_node_id)

    # Valid edge endpoints = existing graph nodes + the new nodes we just accepted.
    valid_ids = {n["nodeId"] for n in existing_nodes} | seen_node_ids

    today = _today()
    clean_edges: List[Dict[str, Any]] = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        from_id = e.get("fromNodeId")
        to_id = e.get("toNodeId")
        edge_type = e.get("edgeType")

        # Resolve duplicate endpoints
        if from_id in resolved_node_ids:
            from_id = resolved_node_ids[from_id]
        if to_id in resolved_node_ids:
            to_id = resolved_node_ids[to_id]

        if not from_id or not to_id or from_id == to_id:
            continue

        if from_id not in valid_ids or to_id not in valid_ids:
            logger.warning("Dropping edge with unknown/unresolved endpoint: %s -> %s", from_id, to_id)
            continue
        if edge_type not in VALID_EDGE_TYPES:
            logger.warning("Dropping edge with invalid edgeType '%s': %s -> %s", edge_type, from_id, to_id)
            continue
        try:
            confidence = float(e.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))
        clean_edges.append({
            "fromNodeId": from_id,
            "toNodeId": to_id,
            "edgeType": edge_type,
            "strength": e.get("strength", "medium"),
            "confidence": round(confidence, 2),
            "sourceType": "llm_generated",
            "notes": e.get("notes", ""),
            "lastReviewedAt": today,
        })

    # --- Merge into the live graph ---
    for n in clean_nodes:
        add_graph_node(n)
    for e in clean_edges:
        add_graph_edge(e)

    logger.info("%s: merged %d nodes, %d edges via LLM.", ticker, len(clean_nodes), len(clean_edges))
    return {
        "ticker": ticker,
        "addedNodes": len(clean_nodes),
        "addedEdges": len(clean_edges),
        "usedLLM": True,
    }


def process_ticker_expansion(ticker: str, force: bool = False) -> Dict[str, Any]:
    """
    Background-task entrypoint. Runs the expansion, persists the graph on success, and
    records the outcome in the status store. Never raises — failures are surfaced via
    the status entry so the UI can offer a manual re-run.
    """
    try:
        from opentelemetry import trace as otel_trace
        tracer = otel_trace.get_tracer("cross-impact-catalysts")
        try:
            from openinference.semconv.trace import SpanAttributes
            OPENINFERENCE_SPAN_KIND = SpanAttributes.OPENINFERENCE_SPAN_KIND
            INPUT_VALUE = SpanAttributes.INPUT_VALUE
            OUTPUT_VALUE = SpanAttributes.OUTPUT_VALUE
        except ImportError:
            OPENINFERENCE_SPAN_KIND = "openinference.span.kind"
            INPUT_VALUE = "input.value"
            OUTPUT_VALUE = "output.value"
    except Exception:
        tracer = None

    def _run():
        tk = ticker.strip().upper()
        _set_status(tk, "running")
        try:
            with _expansion_lock:
                with graph_lock():
                    summary = expand_graph_for_ticker(tk, force=force)
                    save_graph(get_graph())
            final_status = "skipped" if summary.get("skipped") else "done"
            _set_status(
                tk,
                final_status,
                addedNodes=summary.get("addedNodes", 0),
                addedEdges=summary.get("addedEdges", 0),
                usedLLM=summary.get("usedLLM", False),
            )
            return summary
        except Exception as e:
            logger.exception("Background expansion failed for %s: %s", tk, e)
            _set_status(tk, "failed", error=str(e))
            return {"ticker": tk, "status": "failed", "error": str(e)}

    if tracer:
        span_name = "Graph Building: Entity Cross-Relationships"
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("ticker", ticker)
            span.set_attribute("force", force)
            span.set_attribute(OPENINFERENCE_SPAN_KIND, "CHAIN")
            span.set_attribute(INPUT_VALUE, json.dumps({"ticker": ticker, "force": force}))
            
            res = _run()
            
            span.set_attribute("status", res.get("status", "done"))
            span.set_attribute("added_nodes", res.get("addedNodes", 0))
            span.set_attribute("added_edges", res.get("addedEdges", 0))
            span.set_attribute(OUTPUT_VALUE, json.dumps(res))
            return res
    else:
        return _run()
