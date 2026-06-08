# Evaluation Strategy for Flow Evolution

## Principle

The system should not evolve by intuition alone. Every meaningful change to extraction, routing, memory, graph expansion, synthesis, or guardrails should be judged against path sets that exercise the state transitions we care about.

Phoenix/Arize should be the analysis surface for traces and experiment comparison. The product UI should not run evals. CI or an operator command should run eval sets and emit spans/results that Phoenix can inspect.

## State Boundaries to Evaluate Separately

- Run result state: what one pipeline execution returns to the analyst.
- Catalyst ledger memory: story threads, duplicate/update decisions, fact progression, and TTL behavior.
- Vector/embedding state: whether semantic dedup is using local fastembed or lexical fallback, and whether vector-backed matching changes decisions.
- Exposure graph state: durable graph nodes/edges and one-time ticker expansion.
- Expansion status state: pending/running/done/skipped/failed metadata for background graph work.
- Settings state: non-secret LLM route overrides only.

These should not be collapsed into a single "memory" concept. A bug in graph expansion status should not look like a catalyst ledger bug, and a vector fallback should not silently alter story-thread behavior without an eval signal.

## Required Path Sets

### P0: Direct News Baseline

Purpose: detect regressions in basic extraction, direct ticker routing, and synthesis.

Checks:
- Required tickers receive direct routes.
- Required tickers receive syntheses.
- Iteration 1 does not write to the catalyst ledger.
- Guardrail metadata exists for non-empty LLM synthesis.

### P0: Story Memory Progression

Purpose: decide whether ledger changes improve duplicate/update handling.

Checks:
- First duplicate scenario creates one live AAPL story thread.
- Same-story duplicate is suppressed.
- Same-story update extends the existing thread rather than creating a new thread.
- Re-running the same feed does not create another live AAPL story thread.
- New hard facts are retained; old facts remain available as context.

### P0: Cross-Impact Routing

Purpose: protect the core Iteration 3 promise.

Checks:
- Untickered external events route through graph paths to exposed watchlist tickers.
- Required indirect routes exist for AAPL, MSFT, NVDA, TSM, and DAL in the replay scenario.
- Returned candidates carry impact paths and routing reasons.
- Ledger writes for indirect candidates remain ticker-specific.

### P1: Vector DB / Fallback Behavior

Purpose: understand whether vector-backed dedup changes memory quality.

Checks:
- Run the same memory path set with local fastembed active.
- Run it again with forced lexical fallback.
- Compare duplicate/update decisions, live thread counts, and new-fact detection.
- Treat differences as review items, not automatic failures, until thresholds are calibrated.

### P1: Graph Expansion Status Isolation

Purpose: keep background graph work from polluting run/memory state.

Checks:
- Adding a ticker marks expansion pending/running/done without creating catalyst ledger entries.
- Graph rebuild changes graph state, not previous run-result state.
- Failed expansion does not block watchlist persistence.

### P1: Settings Route Safety

Purpose: ensure non-secret settings are useful without becoming a footgun.

Checks:
- Provider/model override changes selected model status.
- Missing credentials reports unconfigured instead of failing silently.
- Blank route returns to backend defaults.
- API keys never appear in settings responses.

## Implemented Eval Sets

- `backend/evals/sets/replay_scenarios.json`: independent smoke evals for the three replay scenarios.
- `backend/evals/sets/memory_and_routing_paths.json`: sequenced path-set evals for ledger-free Iteration 1, Iteration 2 story-memory progression, and Iteration 3 indirect routing.

Run with:

```bash
python -m backend.evals.runner --eval-set memory_and_routing_paths
```

Use `--no-phoenix` for local debugging without trace emission.
