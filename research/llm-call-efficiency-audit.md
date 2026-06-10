# LLM Call Efficiency Audit & Optimization Roadmap

**Status**: Research document for future optimization (deferred until correctness baseline established)  
**Date**: 2026-06-10  
**Scope**: Audit the 4 LLM call sites for potential input structure optimization (GUID-based references, fact indices, etc.)

---

## Current State: Full-Text Payloads

### Call Site 1: Extraction (`backend/iterations/extraction.py`)

**Current structure**:
- **Input**: Full article list → `articles[].headline`, `articles[].summary`, `articles[].articleId`, `articles[].sourceRelatedTickers`, `articles[].url`, `articles[].publishedAt`
- **Processing**: LLM reads full text per article, extracts canonical events
- **Output**: `CanonicalEventOut[]` with `eventSummary`, `hardFacts[]`, `entities[]`, etc.

**Current size**: ~30 KB per typical news batch (10–20 articles × 1–2 KB each)

**Optimization potential**: **LOW** (worth revisiting post-baseline)
- Articles are the *input* not the intermediate; shortening them breaks the source-of-truth principle
- Headline + summary capture 90%+ of decision logic
- Could trim: remove `url` if not needed in output; cap summary length (current: unbounded)
- **Deferred**: No gains here until we see what factors drive extraction quality

---

### Call Site 2: Synthesis (`backend/iterations/synthesis.py:95–96`)

**Current structure**:
- **Input**: Full `annotated_bucket` (JSON-serialized):
  ```json
  {
    "directEvents": [{
      "eventId": "evt_123",
      "eventSummary": "...",
      "hardFacts": ["fact 1", "fact 2", ...],
      "entities": [...],
      "eventTags": [...],
      "possibleDirectionalPressure": "positive",
      "minutesAgo": 15,
      "impactPath": ["direct"],
      ...
    }, ...],
    "crossImpactEvents": [...]
  }
  ```
- **Processing**: LLM reads full bucket, writes per-ticker briefing
- **Output**: `SynthesisOut` with `summaryHeadline`, `situationSummary`, `mainCatalysts[]`, `overallPossibleInfluence`, etc.

**Current size**: ~5–20 KB per ticker (varies by bucket fullness; typically 3–8 events × 500–1000 bytes each)

**Optimization opportunity**: **MEDIUM** (good gains likely)

Proposed lightweight structure (future):
```json
{
  "directEvents": [
    {
      "eventId": "evt_123",
      "summaryId": "sum_123",  // Reference, not full text
      "directionalPressure": "positive",
      "confidence": "high",
      "minutesAgo": 15,
      "impactPath": ["direct"],
      "significance": 7,
      "sourceNames": ["Reuters", "Bloomberg"]
    },
    ...
  ],
  "crossImpactEvents": [...]
}
```

Separately, expose an **event summary index** (computed pre-synthesis):
```
{
  "sum_123": {
    "summary": "...",
    "hardFacts": ["...", "..."],
    "entities": [...]
  },
  ...
}
```

**Rationale**: 
- LLM only needs the *decision factors* (directional pressure, recency, significance, source attribution) for weighting, not full fact lists
- Fact reference allows LLM to request deep detail if needed (e.g., "What are the hardFacts for event evt_123?") — 2-shot pattern
- Reduces per-call token cost ~40–50%
- Requires careful prompt tuning to ensure LLM doesn't skip deep-dive when necessary

---

### Call Site 3: Judge (`backend/iterations/guardrails.py`)

**Current structure**:
- **Input**: `ticker`, full `bucket` (same as synthesis), full `synthesis` output
- **Processing**: LLM validates grounding, advice rules, path validity
- **Output**: `OutputSafetyJudgeOut` with `passes`, `groundingPassed`, `advicePassed`, `pathPassed`, `defects[]`

**Current size**: ~15–30 KB (bucket + synthesis combined)

**Optimization opportunity**: **MEDIUM** (similar to synthesis)

Proposed lightweight structure (future):
```json
{
  "ticker": "AAPL",
  "synthesis": {
    "summaryHeadline": "...",
    "situationSummary": "...",
    "mainCatalysts": [
      {
        "eventId": "evt_123",
        "label": "...",
        "possibleInfluence": "positive",
        "significance": 7
      },
      ...
    ],
    "overallPossibleInfluence": "positive"
  },
  "bucketEventSummary": [
    {
      "eventId": "evt_123",
      "hardFacts": ["fact 1", "fact 2"],
      "entities": [...],
      "sourceNames": ["Reuters"]
    },
    ...
  ]
}
```

**Rationale**:
- Judge only needs grounding checks (facts vs bucket), advice scrub (synthesis text), and path validation (eventId references)
- Full bucket not needed; summarized events + synthesis text suffices
- ~30–40% token reduction possible

---

### Call Site 4: Graph Expansion (`backend/graph/expansion.py`)

**Current structure**:
- **Input**: `ticker` symbol, Finnhub `peers[]`, existing graph nodes/edges, expansion `SYSTEM_PROMPT`
- **Processing**: LLM generates suppliers, customers, competitors, regions, tech themes, macro risks
- **Output**: `GraphExpansionResult` with `nodes[]`, `edges[]`

**Current size**: ~3–8 KB (ticker + ~20 peer nodes + system prompt)

**Optimization opportunity**: **LOW** (already lean)
- Peers are essential context; ticker symbol is minimal
- Prompt is static and necessary for quality
- No efficiency gains without losing quality

---

## Summary Table: Estimated Impact

| LLM Call | Current Size | Optimization Type | Estimated Savings | Effort | Priority |
|----------|--------------|-------------------|--------------------|--------|----------|
| **Extraction** | ~30 KB | Trim article length, cap summaries | ~10% | Low | P3 (low ROI) |
| **Synthesis** | ~5–20 KB | Event summary index + fact refs | ~40–50% | Medium | P2 (good ROI, post-baseline) |
| **Judge** | ~15–30 KB | Lightweight event summaries | ~30–40% | Medium | P2 (good ROI, post-baseline) |
| **Graph Expansion** | ~3–8 KB | None (already lean) | ~0% | — | P4 (skip) |

---

## Recommendation

**Phase 1 (now)**: Establish correctness baseline with current full-text structures.  
- Run golden evals, confirm quality metrics, refine prompts
- Cost is secondary; focus on output quality and routing accuracy

**Phase 2 (post-baseline)**: Optimize synthesis + judge with summary index approach
- Once evals confirm output quality, introduce event-summary references
- Measure token savings + latency improvements; re-baseline quality
- Update prompts/judges if needed; document any quality drift

**Phase 3 (optional)**: Further refinements
- Fact-level indexing if per-fact grounding becomes a bottleneck
- Dynamic summary generation (compute summaries per-bucket, not globally) if multi-ticker scales

---

## Design Decision for Future Implementation

When synthesis/judge optimization begins:
1. Create `backend/iterations/event_summary_builder.py` — function to compute per-bucket summary index from canonical events
2. Expose via new contract `BucketWithSummaryIndex` in `contracts.py`
3. Update synthesis + judge prompts to reference `eventId` → index lookup pattern
4. Test 2-shot fallback: if LLM asks "what are the hardFacts for evt_123?", provide them (requires second LLM call or in-context retrieval)
5. A/B test: baseline (full text) vs. lightweight (summaries); measure token usage + quality metrics

---

## Open Questions

- **Fact-level granularity**: Should individual facts be indexed with GUIDs (eventId:factIndex), or is per-event summary sufficient?
- **LLM capability**: Can Claude/GPT/Gemini reliably follow "reference eventId, don't hallucinate summaries" pattern, or do we need more in-context examples?
- **Fallback cost**: If LLM requests deep-dive via eventId, is the overhead of a second call worth the savings?

Addressed post-baseline with real eval data.
