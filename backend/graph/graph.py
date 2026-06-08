from typing import List, Dict, Any, Set, Optional
import copy
import re
from contextlib import contextmanager
from threading import RLock
from backend.graph.seed import EXPOSURE_GRAPH

def _is_match(event_term: str, node_text: str) -> bool:
    event_term = event_term.strip().lower()
    node_text = node_text.strip().lower()
    
    if not event_term or not node_text:
        return False
        
    # Exact match
    if event_term == node_text:
        return True
        
    # Word boundary match (highly robust and avoids substring issues like "ai" in "taiwan" or "hon hai")
    pattern = r'\b' + re.escape(event_term) + r'\b'
    if re.search(pattern, node_text):
        return True
        
    # Plural/Singular stem matching for terms of length >= 4
    if len(event_term) >= 4:
        # Check if one is a plural/singular variation of the other
        if event_term.endswith('s') and event_term[:-1] == node_text:
            return True
        if node_text.endswith('s') and node_text[:-1] == event_term:
            return True
            
    return False


# In-memory storage for exposure graph, initialized with seed data
_graph_store = copy.deepcopy(EXPOSURE_GRAPH)
_graph_lock = RLock()


@contextmanager
def graph_lock():
    """Serialize graph reads/writes that must be observed atomically."""
    with _graph_lock:
        yield


def _infer_ticker_from_node(node: Dict[str, Any]) -> str:
    ticker = node.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()

    node_id = node.get("nodeId", "")
    if node_id.startswith("ticker_"):
        suffix = node_id.replace("ticker_", "", 1).strip().upper()
        if suffix and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", suffix):
            return suffix

    return ""


def _merge_unique(*lists):
    merged = []
    seen = set()
    for values in lists:
        for value in values or []:
            if value is None:
                continue
            key = str(value).strip()
            if not key or key.lower() in seen:
                continue
            merged.append(key)
            seen.add(key.lower())
    return merged


def normalize_graph(graph: Dict[str, Any], watchlist: Optional[List[str]] = None) -> Dict[str, Any]:
    """Normalize graph shape after load/LLM/manual edits.

    Public companies with tickers are first-class ticker nodes. Private/non-public actors
    such as OpenAI, Mistral, Claude, Anthropic, and Reflection AI stay private_company
    nodes. Region/country/policy nodes are kept as macro nodes for directional traversal.
    """
    watch = {t.strip().upper() for t in watchlist or [] if isinstance(t, str)}
    normalized = copy.deepcopy(graph or {"nodes": [], "edges": []})
    nodes = []

    for node in normalized.get("nodes", []):
        node = dict(node)
        node_type = node.get("nodeType")
        ticker = _infer_ticker_from_node(node)

        if ticker and (node_type in {"ticker", "private_company"} or ticker in watch):
            node["nodeType"] = "ticker"
            node["ticker"] = ticker
            node["aliases"] = _merge_unique(node.get("aliases", []), [ticker])
            node["queryTerms"] = _merge_unique(node.get("queryTerms", []), [ticker])
            if node.get("name") == ticker and len(node.get("aliases", [])) > 1:
                node["name"] = next((a for a in node["aliases"] if a.upper() != ticker), node["name"])
        elif node_type == "ticker":
            # A ticker node without a ticker is unusable as a query/routing root; demote only
            # if no symbol can be inferred.
            node["nodeType"] = "private_company"

        nodes.append(node)

    normalized["nodes"] = nodes
    return normalized

def get_graph() -> Dict[str, Any]:
    """Returns the current state of the exposure graph."""
    with _graph_lock:
        return _graph_store

def add_graph_node(node: Dict[str, Any]):
    """Adds or updates a node in the exposure graph."""
    with _graph_lock:
        node = normalize_graph({"nodes": [node], "edges": []})["nodes"][0]
        node_id = node.get("nodeId")
        if not node_id:
            raise ValueError("nodeId is required")

        _graph_store["nodes"] = [n for n in _graph_store["nodes"] if n["nodeId"] != node_id]
        _graph_store["nodes"].append(node)

def add_graph_edge(edge: Dict[str, Any]):
    """Adds or updates an edge in the exposure graph."""
    with _graph_lock:
        from_id = edge.get("fromNodeId")
        to_id = edge.get("toNodeId")
        if not from_id or not to_id:
            raise ValueError("fromNodeId and toNodeId are required")

        _graph_store["edges"] = [
            e for e in _graph_store["edges"]
            if not (e["fromNodeId"] == from_id and e["toNodeId"] == to_id)
        ]
        _graph_store["edges"].append(edge)

def set_graph(graph: Dict[str, Any]):
    global _graph_store
    with _graph_lock:
        _graph_store = normalize_graph(graph)

def reset_graph() -> Dict[str, Any]:
    """Restores the exposure graph to the curated seed, discarding all runtime additions."""
    global _graph_store
    with _graph_lock:
        _graph_store = normalize_graph(copy.deepcopy(EXPOSURE_GRAPH))
        return _graph_store

from typing import Tuple

_FETCH_NOISE_TERMS = {
    "ai", "ml", "us", "usa", "eu", "ce", "prc", "app", "mac", "core", "arc",
    "power", "water", "energy", "coffee", "pizza", "taco", "hamburgers",
    "cafe", "chips", "silicon", "electronics", "gaming", "esports",
    "video games", "wearables", "android", "iphone", "ipad", "airpods",
    "apple", "google", "amazon", "microsoft", "nvidia", "delta",
    "united states", "europe", "china", "taiwan", "consumer spending",
    "consumer demand", "cloud computing", "cloud services", "data centers",
    "data center", "artificial intelligence", "semiconductor",
}

_HIGH_SIGNAL_ONE_WORD_TERMS = {
    "openai", "anthropic", "mistral", "chatgpt", "claude", "blackwell",
}

_HIGH_SIGNAL_PHRASES = (
    "export control", "chip export", "tariff", "sanction", "antitrust",
    "regulation", "regulatory", "lawsuit", "probe", "investigation",
    "defense spending", "pentagon", "department of defense", "dod",
    "red sea", "suez", "bab el-mandeb", "freight rates", "shipping cost",
    "jet fuel", "oil price", "interest rates", "federal reserve",
    "ai model", "large language model", "frontier ai", "ai data center",
    "ai infrastructure", "gpu cluster", "benchmark", "claude model",
    "gpt-5", "sora", "nvidia-backed", "reflection ai",
    "taiwan strait", "earthquake", "foundry evacuation",
)


def _clean_fetch_term(term: str) -> str:
    return re.sub(r"\s+", " ", str(term or "").strip())


def _is_fetchable_cross_impact_term(term: str, node: Dict[str, Any], watchlist: Set[str]) -> bool:
    term = _clean_fetch_term(term)
    if not term:
        return False

    lower = term.lower()
    if lower in _FETCH_NOISE_TERMS:
        return False
    if term.upper() in watchlist:
        return False
    if re.fullmatch(r"[A-Z]{1,5}", term):
        return False

    node_type = node.get("nodeType")
    if node_type == "ticker":
        # Ticker/company direct news comes from Finnhub, not broad Currents search.
        return False

    words = re.findall(r"[A-Za-z0-9$.-]+", term)
    if len(words) <= 1:
        return lower in _HIGH_SIGNAL_ONE_WORD_TERMS

    if len(term) > 70:
        return False

    if any(phrase in lower for phrase in _HIGH_SIGNAL_PHRASES):
        return True

    # Keep named private actors and specific policy/technology phrases, drop broad nouns.
    if node_type in {"private_company", "government_agency"} and len(words) <= 4:
        return True
    if node_type in {"policy_area", "shipping_route", "technology_theme", "commodity"} and len(words) >= 2:
        return True

    return False


def _rank_fetch_term(term: str) -> Tuple[int, int, str]:
    lower = term.lower()
    score = 0
    if any(phrase in lower for phrase in _HIGH_SIGNAL_PHRASES):
        score += 20
    if any(token in lower for token in ("export", "antitrust", "tariff", "lawsuit", "probe", "red sea", "federal reserve", "pentagon", "benchmark", "data center")):
        score += 10
    word_count = len(term.split())
    if 2 <= word_count <= 4:
        score += 5
    return (-score, len(term), term.lower())


def get_cross_impact_queries(watchlist: List[str]) -> Tuple[List[str], List[str]]:
    """
    Finds keywords and query terms from nearby nodes connected to watchlist tickers in the exposure graph.
    Traverses the graph in reverse (from tickers outwards up to 2 hops) to find relevant search terms.
    Returns a tuple: (cross_impact_keywords, extra_tickers)
    """
    nodes = {n["nodeId"]: n for n in _graph_store["nodes"]}
    edges = _graph_store["edges"]
    
    # Find start nodes corresponding to the watchlist tickers
    watchlist_node_ids = set()
    for node_id, node in nodes.items():
        if node["nodeType"] == "ticker" and node.get("ticker") in watchlist:
            watchlist_node_ids.add(node_id)
            
    if not watchlist_node_ids:
        return [], []
        
    # Collect query terms from these nodes and their 1-hop and 2-hop neighbors
    relevant_nodes = set(watchlist_node_ids)
    
    # 1st Hop
    neighbors_1 = set()
    for edge in edges:
        f, t = edge["fromNodeId"], edge["toNodeId"]
        if f in relevant_nodes:
            neighbors_1.add(t)
        if t in relevant_nodes:
            neighbors_1.add(f)
            
    relevant_nodes.update(neighbors_1)
    
    # 2nd Hop
    neighbors_2 = set()
    for edge in edges:
        f, t = edge["fromNodeId"], edge["toNodeId"]
        if f in neighbors_1:
            neighbors_2.add(t)
        if t in neighbors_1:
            neighbors_2.add(f)
            
    relevant_nodes.update(neighbors_2)
    
    # Collect query terms and extra tickers. Broad graph aliases are useful for routing, but
    # terrible as live-news search terms; keep Currents focused on specific catalysts.
    keywords = set()
    extra_tickers = set()
    watchlist_symbols = {t.upper() for t in watchlist}
    for node_id in relevant_nodes:
        node = nodes[node_id]
        terms = list(node.get("queryTerms", []))
        if node.get("nodeType") in {"private_company", "government_agency", "policy_area", "shipping_route", "technology_theme", "commodity"}:
            terms.append(node.get("name", ""))
            terms.extend(node.get("aliases", []))
        for term in terms:
            cleaned = _clean_fetch_term(term)
            if _is_fetchable_cross_impact_term(cleaned, node, watchlist_symbols):
                keywords.add(cleaned)
        
        # If this node represents a company with a ticker and is not on the watchlist,
        # collect its ticker to query Finnhub
        node_ticker = node.get("ticker")
        if node_ticker and node_ticker not in watchlist:
            extra_tickers.add(node_ticker)
            
    return sorted(keywords, key=_rank_fetch_term)[:35], sorted(extra_tickers)


def get_cross_impact_keywords(watchlist: List[str]) -> List[str]:
    """Finds keywords and query terms from nearby nodes. Maintained for backward compatibility."""
    keywords, _ = get_cross_impact_queries(watchlist)
    return keywords

def find_paths_to_watchlist(start_node_id: str, watchlist_node_ids: Set[str], max_hops: int = 3) -> List[List[Dict[str, Any]]]:
    """
    Finds all paths of length <= max_hops from start_node_id to any node in watchlist_node_ids.
    Returns a list of paths, where each path is a list of edge dicts.
    """
    nodes = {n["nodeId"]: n for n in _graph_store["nodes"]}
    edges = _graph_store["edges"]
    company_types = {"ticker", "private_company"}
    
    # Simple BFS/DFS pathfinding
    paths = []
    
    def is_allowed_transition(current_id: str, neighbor_id: str, edge: Dict[str, Any]) -> bool:
        c_node = nodes.get(current_id)
        n_node = nodes.get(neighbor_id)
        if not c_node or not n_node:
            return False
            
        c_type = c_node.get("nodeType")
        n_type = n_node.get("nodeType")
        
        # If it is an exposure/sensitivity edge:
        if edge.get("edgeType") in {
            "regional_exposure", "technology_exposure", "shipping_exposure", 
            "macro_sensitivity", "policy_exposure", "defense_exposure",
            "trade_exposure", "sector_exposure", "commodity_exposure"
        }:
            is_c_company = c_type in company_types
            is_n_company = n_type in company_types
            
            if is_c_company and not is_n_company:
                # Company -> Macro transition is NOT allowed for exposure edges (exposure flows macro -> company)
                return False
                
            if not is_c_company and is_n_company:
                # Macro -> Company transition IS allowed
                return True
                
            if not is_c_company and not is_n_company:
                # Both are macro nodes. Follow the edge's original direction.
                # Traverse only if current_id is the original fromNodeId and neighbor_id is the original toNodeId
                return edge.get("fromNodeId") == current_id and edge.get("toNodeId") == neighbor_id
                
        # For company-to-company edges (supplier_of, customer_of, competitor_of, partner_of), bi-directional is fine.
        return True
    
    def dfs(current_id: str, current_path: List[Dict[str, Any]], visited: Set[str]):
        if len(current_path) > max_hops:
            return
            
        if current_id in watchlist_node_ids:
            paths.append(list(current_path))
            # Keep searching in case there are other paths
            
        # Find neighbors (can traverse edges in both directions or directed.
        # Since exposures can represent causal influence, they can flow both ways in terms of correlation, 
        # but typically we traverse from Event Node -> Ticker.
        # Let's check both directions, representing general connection.
        for edge in edges:
            f, t = edge["fromNodeId"], edge["toNodeId"]
            if f == current_id and t not in visited:
                if is_allowed_transition(current_id, t, edge):
                    dfs(t, current_path + [edge], visited | {t})
            elif t == current_id and f not in visited:
                # Reverse edge traversal is valid since relationship is bi-directional exposure
                # We create a reversed version of the edge for path building
                if is_allowed_transition(current_id, f, edge):
                    rev_edge = copy.deepcopy(edge)
                    rev_edge["fromNodeId"], rev_edge["toNodeId"] = t, f
                    dfs(f, current_path + [rev_edge], visited | {f})
                
    dfs(start_node_id, [], {start_node_id})
    return paths

def route_cross_impact(canonical_event: Dict[str, Any], watchlist: List[str]) -> List[Dict[str, Any]]:
    """
    Routes an untickered canonical event to watchlist tickers using exposure graph path traversal.
    """
    nodes = {n["nodeId"]: n for n in _graph_store["nodes"]}
    watchlist_node_ids = set()
    ticker_to_node = {}
    
    for node_id, node in nodes.items():
        if node["nodeType"] == "ticker" and node.get("ticker") in watchlist:
            watchlist_node_ids.add(node_id)
            ticker_to_node[node.get("ticker")] = node_id
            
    if not watchlist_node_ids:
        return []
        
    # Match event entities and tags to graph nodes
    matched_node_ids = set()
    
    # Search fields in canonical event
    event_entities = [e.lower() for e in canonical_event.get("entities", [])]
    event_tickers = [t.lower() for t in canonical_event.get("mentionedTickers", [])]
    event_tags = [t.lower() for t in canonical_event.get("eventTags", [])]
    event_regions = [r.lower() for r in canonical_event.get("regions", []) or []]
    event_themes = [t.lower() for t in canonical_event.get("technologyThemes", []) or []]
    
    event_terms = set(event_tickers + event_entities + event_tags + event_regions + event_themes)
    
    # Check node match using word-boundary and stem matching
    for node_id, node in nodes.items():
        node_name_lower = node["name"].lower()
        node_aliases_lower = [a.lower() for a in node.get("aliases", [])]
        node_terms = [node_name_lower] + node_aliases_lower
        if node.get("ticker"):
            node_terms.append(node["ticker"].lower())
        
        matched = False
        for term in node_terms:
            for et in event_terms:
                if _is_match(et, term):
                    matched_node_ids.add(node_id)
                    matched = True
                    break
            if matched:
                break
                
    candidates = []
    
    # Traverse paths from each matched node to watchlist tickers
    for start_node_id in matched_node_ids:
        paths = find_paths_to_watchlist(start_node_id, watchlist_node_ids, max_hops=3)
        
        for path in paths:
            if not path:
                continue
                
            # Path node list for visualization
            path_nodes = [start_node_id]
            for edge in path:
                path_nodes.append(edge["toNodeId"])
                
            final_node_id = path_nodes[-1]
            target_ticker = nodes[final_node_id].get("ticker") or nodes[final_node_id]["name"]
            
            # Calculate path score
            # path_score = event_severity * average_edge_confidence * path_shortness_bonus
            # Severity mapping from possibleDirectionalPressure
            severity_str = canonical_event.get("possibleDirectionalPressure", "unclear")
            if severity_str in ["positive", "negative"]:
                event_severity = 1.0
            elif severity_str == "mixed":
                event_severity = 0.8
            else:
                event_severity = 0.5
                
            edge_confidences = [edge.get("confidence", 0.8) for edge in path]
            average_edge_confidence = sum(edge_confidences) / len(edge_confidences)
            
            # Path shortness bonus: 1 hop = 1.0, 2 hops = 0.9, 3 hops = 0.75
            hops = len(path)
            if hops == 1:
                path_shortness_bonus = 1.0
            elif hops == 2:
                path_shortness_bonus = 0.9
            else:
                path_shortness_bonus = 0.75
                
            path_score = event_severity * average_edge_confidence * path_shortness_bonus
 
            # Route if path score >= 0.45; tag "strong" (>=0.70) vs "weak" (0.45-0.69)
            # so the synthesis LLM can treat marginal paths as watch items, not primary catalysts
            if path_score >= 0.45:
                # Construct path details/explanation
                explanations = []
                for edge in path:
                    notes = edge.get("notes", "")
                    from_name = nodes[edge["fromNodeId"]]["name"]
                    to_name = nodes[edge["toNodeId"]]["name"]
                    rel_type = edge["edgeType"]
                    explanations.append(f"{from_name} ({rel_type}) -> {to_name}. {notes}")
 
                reason_for_routing = "; ".join(explanations)
                path_strength = "strong" if path_score >= 0.70 else "weak"
 
                candidates.append({
                    "candidateId": f"cand_{target_ticker}_{canonical_event.get('eventId', '')[:8]}",
                    "ticker": target_ticker,
                    "relationshipType": "indirect",
                    "eventId": canonical_event.get("eventId"),
                    "impactPath": [nodes[nid]["name"] for nid in path_nodes],
                    "pathConfidence": round(path_score, 2),
                    "pathStrength": path_strength,
                    "reasonForRouting": reason_for_routing
                })
                
    # Deduplicate candidate connections (take highest score path for a ticker-event pair)
    best_candidates = {}
    for cand in candidates:
        key = (cand["ticker"], cand["eventId"])
        if key not in best_candidates or cand["pathConfidence"] > best_candidates[key]["pathConfidence"]:
            best_candidates[key] = cand
            
    return list(best_candidates.values())
