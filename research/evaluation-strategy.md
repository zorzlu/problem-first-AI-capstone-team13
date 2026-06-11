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

### Deterministic (No API Keys, CI-Safe)

- `backend/evals/runner.py`: Deterministic eval runner using pre-baked event extraction and mock LLMs. Runs in CI without API keys or Phoenix.
  - `--eval-set replay_scenarios`: independent smoke evals for the three replay scenarios.
  - `--eval-set memory_and_routing_paths`: sequenced path-set evals for ledger-free Iteration 1, Iteration 2 story-memory progression, and Iteration 3 indirect routing.
  - `--eval-set routing_quality`: golden routing cases measuring false-butterfly rates and indirect routing recall.

Run with:

```bash
python -m backend.evals.runner --eval-set memory_and_routing_paths --no-phoenix
```

### Phoenix Golden Case Framework (Optional, Requires API Keys)

New eval infrastructure built on golden cases for deeper quality assessment:

**Golden Cases** (`backend/evals/sets/golden_examples/{suite}/`):
- JSON files conforming to `golden_schema.py` (schemaVersion=1).
- Per-suite structure: `iter1_direct/`, `iter2_memory/`, `iter3_cross_impact/`, `judge_calibration/`.
- Each case specifies: articles, watchlist, graph fixture, and suite-specific expected outputs.
- Smoke cases included for basic validation (no golden dataset repo yet).

**Eval Harness** (`backend/evals/harness.py`):
- `run_golden_case()` injects articles, optionally swaps graph fixtures, invokes workflow, collects results.
- Returns final state for evaluator assertions.
- Automatically handles ledger/graph cleanup.

**Deterministic Evaluators** (`backend/evals/evaluators/deterministic.py`):
- `evaluate_iter1_direct()`: extraction accuracy, direct-route precision/recall, forbidden-route violations.
- `evaluate_iter2_memory()`: dedup decision accuracy, duplicate counts, live ledger entries.
- `evaluate_iter3_cross_impact()`: indirect-route precision/recall, false-butterfly detection, path validity.
- `evaluate_judge_calibration()`: judge accuracy per dimension (grounding, advice, path).

**LLM Judges** (`backend/evals/evaluators/llm_judges.py`):
- Placeholder implementations for faithfulness, coherence, compliance, path consistency.
- Deferred until golden dataset repo is available and human labels are provided.

**Suite Configurations** (`backend/evals/suites/`):
- Per-suite pass criteria and metric definitions.
- Example: iter3_cross_impact requires recall ≥ 0.85, precision ≥ 0.85, false-butterfly ≤ 0.05.

**Experiment Runner** (`backend/evals/experiments.py`):
- CLI: `python -m backend.evals.experiments --suite iter1_direct --dataset-dir backend/evals/sets/golden_examples/iter1 --experiment-name smoke_test`
- Loads golden cases, runs evaluators, generates EvalReport.
- Exit code non-zero if any case fails (suitable for CI gating).

**Phoenix Dataset Sync** (`backend/evals/datasets.py`):
- `sync_to_phoenix_dataset()`: Uploads golden cases to Phoenix datasets (placeholder, deferred).
- `create_experiment_name()`: Standardized naming for experiment comparison.
- Placeholder implementation; full sync requires golden dataset repo + Phoenix server.

**Running Golden Cases**:

```bash
# Run iter1 smoke test
python -m backend.evals.experiments --suite iter1_direct --dataset-dir backend/evals/sets/golden_examples/iter1 --experiment-name smoke

# Run all smoke tests
for suite in iter1_direct iter2_memory iter3_cross_impact; do
  python -m backend.evals.experiments --suite $suite --dataset-dir backend/evals/sets/golden_examples/$suite --experiment-name smoke
done
```

**Golden Case Schema**:

Each case specifies:
- `schemaVersion`: 1
- `caseId`: unique ID
- `suite`: one of `iter1_direct`, `iter2_memory`, `iter3_cross_impact`, `judge_calibration`
- `iteration`: 1, 2, or 3
- `watchlist`: tickers to monitor
- `simulatedNow`: timestamp for reproducibility
- `graphFixture`: "seed" or custom {nodes, edges} dict
- `steps`: ordered list with articles + suite-specific expected blocks
- `labels`: metadata (annotator, labeledAt, notes)

Expected blocks vary by suite (see `golden_schema.py` for full definitions).

**Next Steps**:

1. Import golden dataset repo (separate repository with real/synthetic article samples + human labels).
2. Implement LLM judge evaluators with prompt templates.
3. Wire `datasets.py` sync to Phoenix (requires server + client).
4. Set up nightly CI job to run full eval suites with API keys + Phoenix.
5. Document pass thresholds and review process for eval failures.
