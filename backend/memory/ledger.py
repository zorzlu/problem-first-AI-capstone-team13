import math
import os
import re
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone, timedelta

import numpy as np

from backend.core.logging import get_logger

logger = get_logger(__name__)

# In-memory storage for the Catalyst Ledger entries partitioned by iteration
_ledger_store: Dict[int, List[Dict[str, Any]]] = {
    1: [],
    2: [],
    3: []
}

# ----------------------------------------------------------------------------
# Catalyst near-duplicate detection engine
# ----------------------------------------------------------------------------
# Previously every candidate event triggered a paid/quota'd REMOTE embedding API
# call (Gemini embedding-001 / OpenAI text-embedding-3-small). That was the main
# recurring cost in the dedup path. It is replaced by a LOCAL engine with $0/call:
#
#   Primary  : local ONNX embedding model via `fastembed` (BAAI/bge-small-en-v1.5,
#              384 dims). Downloaded once (~50 MB), then runs offline on CPU with no
#              network call and no per-call cost. Preserves the semantic dedup quality
#              of the old API path — it catches paraphrased duplicates of the same
#              catalyst that a purely lexical match would miss.
#   Fallback : deterministic lexical token-frequency cosine (`calculate_text_similarity`).
#              Zero extra dependencies. Used automatically if the embedding model cannot
#              be loaded (e.g. offline first-run with no cached model). Lower recall on
#              heavy paraphrases but fully deterministic and auditable.
#
# Either way there is no remote embedding API and no ongoing embedding cost.

# Embedding model/cache location (overridable via env for experimentation).
_EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
_DEFAULT_EMBEDDING_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "fastembed_cache")
_EMBEDDING_CACHE_DIR = os.getenv("EMBEDDING_CACHE_DIR", _DEFAULT_EMBEDDING_CACHE_DIR)

# Lazily-initialised singleton + availability flag.
_embedding_model = None
_embedding_unavailable = False
_embedding_unavailable_reason: Optional[str] = None

# Small English stopword set so common filler words don't inflate similarity scores.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was",
    "were", "will", "with",
})


def _tokenize(text: str) -> List[str]:
    """Lowercase, alphanumeric tokenization with stopword removal."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _get_embedding_model():
    """Lazily load the local fastembed model. Returns None if unavailable."""
    global _embedding_model, _embedding_unavailable, _embedding_unavailable_reason
    if _embedding_unavailable:
        return None
    if _embedding_model is None:
        try:
            from fastembed import TextEmbedding
            _embedding_model = TextEmbedding(model_name=_EMBEDDING_MODEL_NAME, cache_dir=_EMBEDDING_CACHE_DIR)
        except Exception as e:
            reason = f"{type(e).__name__}: {str(e)}"
            logger.warning("Local embedding model unavailable (%s). Falling back to lexical similarity.", reason)
            _embedding_unavailable = True
            _embedding_unavailable_reason = reason
            return None
    return _embedding_model


def is_embedding_active() -> bool:
    """Whether the local neural embedding engine is loaded and in use (vs lexical fallback)."""
    return _get_embedding_model() is not None


def get_embedding_unavailable_reason() -> Optional[str]:
    """Return the reason embedding is unavailable, or None if embedding is active or not yet attempted."""
    # Trigger lazy load if not yet attempted, so the reason is populated
    _get_embedding_model()
    return _embedding_unavailable_reason


# Public, read-only views of the embedding config so callers (e.g. the status route) do
# not reach into the underscore-prefixed module internals.
EMBEDDING_MODEL_NAME = _EMBEDDING_MODEL_NAME
EMBEDDING_CACHE_DIR = _EMBEDDING_CACHE_DIR


def ledger_counts() -> Dict[str, int]:
    """Summary counts across all iteration ledgers, for status reporting."""
    total = 0
    live = 0
    embedded = 0
    for entries in _ledger_store.values():
        for entry in entries:
            total += 1
            if entry.get("status") == "live":
                live += 1
                if entry.get("embedding_vec"):
                    embedded += 1
    return {"total": total, "live": live, "embedded": embedded}


def get_text_embedding(text: str) -> Optional[List[float]]:
    """
    Returns a local embedding vector for `text`, or None if the embedding model is
    unavailable (in which case callers fall back to lexical similarity).
    """
    model = _get_embedding_model()
    if model is None:
        return None

    # fastembed returns a generator of numpy arrays
    vec = next(iter(model.embed([text])))
    return [float(x) for x in vec]


def get_text_embeddings(texts: List[str]) -> Optional[List[List[float]]]:
    """
    Batch variant of get_text_embedding: returns one embedding vector per input text in
    order, or None if the embedding model is unavailable (callers fall back to lexical).

    A single batched model.embed([...]) call is far cheaper than N per-fact calls when
    comparing whole fact lists (see check_for_new_facts).
    """
    if not texts:
        return []
    model = _get_embedding_model()
    if model is None:
        return None
    return [[float(x) for x in vec] for vec in model.embed(list(texts))]


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Cosine similarity between two embedding vectors."""
    v1 = np.asarray(vec1, dtype=float)
    v2 = np.asarray(vec2, dtype=float)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


# ----------------------------------------------------------------------------
# Hard-fact representation
# ----------------------------------------------------------------------------
# Each entry in a ledger entry's `hardFactsSeen` is a dict {"fact": str, "publishedAt": iso}
# so the synthesis LLM can age individual facts within an evolving catalyst thread (a fact
# whose news broke 2 minutes ago is a breaking sub-development; one from 3 hours ago is context).
# `publishedAt` is the SOURCE NEWS publication time (when the news actually spread), not when we
# fetched/processed it — the article may have been published before we ingested it. We fall back
# to processing time only when the source carries no publication timestamp.
# Legacy plain-string facts and legacy `firstSeenAt`-keyed facts are tolerated on read for safety.

def _fact_text(fact: Any) -> str:
    """Extracts the fact text from either a {'fact','firstSeenAt'} dict or a plain string."""
    if isinstance(fact, dict):
        return fact.get("fact", "")
    return fact


def _fact_texts(facts: List[Any]) -> List[str]:
    """Maps a list of timestamped-or-plain facts to their text values."""
    return [_fact_text(f) for f in facts]


def get_ledger(iteration: int = 2) -> List[Dict[str, Any]]:
    """Returns all active ledger entries for a given iteration."""
    if iteration not in _ledger_store:
        _ledger_store[iteration] = []
    # Clean up expired items first
    now = datetime.now(timezone.utc)
    for entry in _ledger_store[iteration]:
        exp_time = datetime.fromisoformat(entry["expiresAt"])
        if now > exp_time:
            entry["status"] = "expired"
    return [entry for entry in _ledger_store[iteration] if entry["status"] == "live"]

def clear_ledger(iteration: Optional[int] = None):
    """Clears the ledger store (for a specific iteration or all)."""
    global _ledger_store
    if iteration is not None:
        _ledger_store[iteration] = []
    else:
        for k in list(_ledger_store.keys()):
            _ledger_store[k] = []


def snapshot_ledger_store() -> Dict[int, List[Dict[str, Any]]]:
    """Return a shallow snapshot of the in-memory ledger partitions."""
    return {k: list(v) for k, v in _ledger_store.items()}


def restore_ledger_store(snapshot: Dict[int, List[Dict[str, Any]]]) -> None:
    """Restore the in-memory ledger partitions from a prior snapshot."""
    _ledger_store.clear()
    _ledger_store.update({k: list(v) for k, v in snapshot.items()})

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Deterministic lexical similarity between two short texts using token-frequency
    (term-frequency) cosine similarity.

    This is the FALLBACK matcher, used when the local neural embedding model is not
    available. There are no fixed-size vectors and no hashing, so there are no
    collisions: each text is represented as a sparse Counter of its (stopword-filtered)
    tokens, and cosine is computed over the shared vocabulary. Returns a value in
    [0.0, 1.0].
    """
    c1 = Counter(_tokenize(text1))
    c2 = Counter(_tokenize(text2))
    if not c1 or not c2:
        return 0.0
    common = set(c1) & set(c2)
    dot = sum(c1[t] * c2[t] for t in common)
    if dot == 0:
        return 0.0
    norm1 = math.sqrt(sum(v * v for v in c1.values()))
    norm2 = math.sqrt(sum(v * v for v in c2.values()))
    return dot / (norm1 * norm2)


def get_containment_score(str1: str, str2: str) -> float:
    """Checks what fraction of the words in the shorter string are present in the longer string."""
    words1 = set(str1.lower().split())
    words2 = set(str2.lower().split())
    if not words1 or not words2:
        return 0.0
    shorter = words1 if len(words1) < len(words2) else words2
    longer = words2 if len(words1) < len(words2) else words1
    intersection = shorter.intersection(longer)
    return len(intersection) / len(shorter)

def get_jaccard_similarity(str1: str, str2: str) -> float:
    """Calculates word-level Jaccard similarity between two strings."""
    set1 = set(str1.lower().split())
    set2 = set(str2.lower().split())
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union)

# A fact counts as already-seen when its embedding cosine to any seen fact is >= this.
# Empirically (BAAI/bge-small-en-v1.5) there is a wide margin between genuinely distinct
# facts (cosine <= ~0.61) and paraphrased/numeric restatements of the same fact (>= ~0.79,
# e.g. "2 million" vs "2000000" ~ 0.87). 0.75 sits in that gap: it suppresses paraphrases
# (the bug this fixes) without collapsing distinct facts. Tunable in the 0.72-0.82 range.
FACT_SIMILARITY_THRESHOLD = 0.75


def _check_for_new_facts_lexical(event_facts: List[str], ledger_facts: List[str]) -> Tuple[bool, List[str]]:
    """
    Lexical fallback for check_for_new_facts (used when the embedding model is unavailable).
    A fact is 'new' if its word-level Jaccard similarity is < 0.6 AND its word containment
    score is < 0.8 relative to ALL existing facts in the ledger entry.
    """
    new_facts = []
    has_new_facts = False

    for ef in event_facts:
        is_duplicate = False
        for lf in ledger_facts:
            sim = get_jaccard_similarity(ef, lf)
            cont = get_containment_score(ef, lf)
            if sim >= 0.6 or cont >= 0.8:
                is_duplicate = True
                break
        if not is_duplicate:
            new_facts.append(ef)
            has_new_facts = True

    return has_new_facts, new_facts


def check_for_new_facts(event_facts: List[str], ledger_facts: List[str]) -> Tuple[bool, List[str]]:
    """
    Compares event facts against already-seen facts in the ledger entry.
    Returns (has_new_facts, list_of_new_facts).

    Primary path: semantic. Each incoming fact is 'new' if its MAX embedding cosine to any
    already-seen fact is below FACT_SIMILARITY_THRESHOLD. This collapses paraphrased restatements
    (e.g. "delays 2 million iPhone units" vs "shipment of 2M phones pushed back") that a purely
    lexical word-overlap test would mistake for novel facts. It also treats numeric restatements
    like "2 million" and "2000000" as the same fact.

    Fallback path: if the embedding model is unavailable, defer to the deterministic lexical
    Jaccard/containment matcher. This mirrors the primary/fallback design of the thread-level
    matcher in check_ledger_decision.
    """
    if not event_facts:
        return False, []
    if not ledger_facts:
        # Nothing seen yet — every incoming fact is new.
        return True, list(event_facts)

    event_embeddings = get_text_embeddings(event_facts)
    ledger_embeddings = get_text_embeddings(ledger_facts) if event_embeddings is not None else None

    # Embedding model unavailable -> deterministic lexical fallback.
    if event_embeddings is None or ledger_embeddings is None:
        return _check_for_new_facts_lexical(event_facts, ledger_facts)

    new_facts = []
    has_new_facts = False
    for ef, ef_emb in zip(event_facts, event_embeddings):
        max_sim = max(
            (calculate_cosine_similarity(ef_emb, lf_emb) for lf_emb in ledger_embeddings),
            default=0.0,
        )
        if max_sim < FACT_SIMILARITY_THRESHOLD:
            new_facts.append(ef)
            has_new_facts = True

    return has_new_facts, new_facts

def check_ledger_decision(ticker: str, canonical_event: Dict[str, Any], similarity_threshold: float = 0.75, iteration: int = 2) -> Tuple[str, str, List[str]]:
    """
    Checks the incoming event against the active catalyst ledger.
    Returns a tuple: (decision, catalyst_id, list_of_new_facts)
    decision can be: "new" | "update" | "duplicate"
    """
    event_summary = canonical_event.get("eventSummary", "")
    event_type = canonical_event.get("eventType", "")
    event_facts = canonical_event.get("hardFacts", [])
    
    # Ingesting articles can have related article IDs
    article_ids = canonical_event.get("sourceArticleIds", [])
    
    # 1. Fetch active ledger entries for this specific ticker & event_type
    if iteration not in _ledger_store:
        _ledger_store[iteration] = []
    active_entries = [
        entry for entry in _ledger_store[iteration]
        if entry["ticker"] == ticker and entry["eventType"] == event_type and entry["status"] == "live"
    ]
    
    # Compute the local embedding of the incoming summary once (None if model unavailable).
    event_embedding = get_text_embedding(event_summary)

    best_entry = None
    highest_sim = 0.0

    for entry in active_entries:
        entry_summary = entry.get("canonicalSummary", "")
        if not entry_summary:
            continue
        entry_emb = entry.get("embedding_vec")
        if event_embedding is not None and entry_emb:
            # Primary path: semantic cosine over local embedding vectors.
            sim = calculate_cosine_similarity(event_embedding, entry_emb)
        else:
            # Fallback path: deterministic lexical cosine over summaries.
            sim = calculate_text_similarity(event_summary, entry_summary)
        if sim > highest_sim:
            highest_sim = sim
            best_entry = entry

    # If similarity is above the threshold, it is the same catalyst thread
    if best_entry and highest_sim >= similarity_threshold:
        catalyst_id = best_entry["catalystId"]
        
        # A. Early exit if this exact article ID has already been seen in this story thread
        already_seen_article = any(aid in best_entry["memberArticleIds"] for aid in article_ids)
        if already_seen_article:
            return "duplicate", catalyst_id, []

        # B. Check if there are new hard facts (compare against the seen facts' text)
        has_new_facts, new_facts = check_for_new_facts(event_facts, _fact_texts(best_entry["hardFactsSeen"]))

        if has_new_facts:
            # Update ledger entry. Stamp the newly-arrived facts with THIS update's time so
            # synthesis can age them independently of older facts in the same thread.
            update_time = datetime.now(timezone.utc).isoformat()
            best_entry["lastUpdatedAt"] = update_time
            # Stamp new facts with the SOURCE NEWS publication time so they age by when the news
            # broke, not when we fetched it; fall back to processing time if the source omits it.
            fact_published = canonical_event.get("publishedAt") or update_time
            best_entry["memberArticleIds"] = list(set(best_entry["memberArticleIds"] + article_ids))
            best_entry["hardFactsSeen"] = best_entry["hardFactsSeen"] + [
                {"fact": f, "publishedAt": fact_published} for f in new_facts
            ]
            
            # Check if this update summary is already contained to avoid infinitely appending updates
            if event_summary.strip().lower() not in best_entry["canonicalSummary"].strip().lower():
                best_entry["canonicalSummary"] = f"{best_entry['canonicalSummary']} Update: {event_summary}"
                # Refresh the stored embedding to reflect the updated summary (no-op under lexical fallback).
                updated_emb = get_text_embedding(best_entry["canonicalSummary"])
                if updated_emb is not None:
                    best_entry["embedding_vec"] = updated_emb

            # Merge other synthesis metadata
            best_entry["uncertaintyNotes"] = list(set(best_entry.get("uncertaintyNotes", []) + canonical_event.get("uncertaintyNotes", [])))
            if canonical_event.get("sourceUrl"):
                best_entry["sourceUrl"] = canonical_event["sourceUrl"]
            if canonical_event.get("sourceHeadline"):
                best_entry["sourceHeadline"] = canonical_event["sourceHeadline"]
            if canonical_event.get("possibleDirectionalPressure"):
                best_entry["possibleDirectionalPressure"] = canonical_event["possibleDirectionalPressure"]

            return "update", catalyst_id, new_facts
        else:
            # Suppress as duplicate, but log the article reference
            best_entry["memberArticleIds"] = list(set(best_entry["memberArticleIds"] + article_ids))
            return "duplicate", catalyst_id, []
            
    # If similarity is below threshold, create a new catalyst entry
    catalyst_id = f"cat_{ticker}_{int(datetime.now().timestamp())}_{len(_ledger_store[iteration])}"
    now_str = datetime.now(timezone.utc).isoformat()
    expires_str = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat() # 1 day TTL
    # Per-fact stamp = source news publication time (fall back to now if the source omits it).
    fact_published = canonical_event.get("publishedAt") or now_str
    
    new_entry = {
        "catalystId": catalyst_id,
        "ticker": ticker,
        "eventType": event_type,
        "relationshipType": "direct" if len(canonical_event.get("relatedTickers", [])) > 0 else "indirect",
        "canonicalSummary": event_summary,
        "embedding_vec": event_embedding,
        "firstSeenAt": now_str,
        "lastUpdatedAt": now_str,
        "expiresAt": expires_str,
        "memberArticleIds": article_ids,
        "hardFactsSeen": [{"fact": f, "publishedAt": fact_published} for f in event_facts],
        "status": "live",
        "possibleDirectionalPressure": canonical_event.get("possibleDirectionalPressure", "unclear"),
        "sourceUrl": canonical_event.get("sourceUrl", ""),
        "sourceHeadline": canonical_event.get("sourceHeadline", ""),
        "uncertaintyNotes": canonical_event.get("uncertaintyNotes", [])
    }
    _ledger_store[iteration].append(new_entry)
    
    return "new", catalyst_id, event_facts
