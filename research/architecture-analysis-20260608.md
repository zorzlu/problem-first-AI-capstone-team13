# Architecture Analysis — 2026-06-08

> Senior architecture review of **Intraday Cross-Impact Catalyst Briefings**.
> Scope: solution architecture only — backend, frontend, scripts, setup, security,
> modularization, file length, tests, CI, docs. **Not** in scope: AI/prompt quality,
> eval methodology (covered separately).
>
> Method: primary review by a senior engineer, with two delegated Sonnet subagents —
> one verifying library/version facts against **context7** (training data explicitly
> distrusted), one red-teaming the findings. See [Appendix A](#appendix-a--how-this-review-was-run-agent-plan).
> Library facts below are as the current docs report them on 2026-06-08, not from memory.

---

## 1. System at a glance

A single-user, single-process full-stack demo:

```
React + Vite SPA  ──/api/*──▶  FastAPI (one Uvicorn process)
  frontend/src/App.tsx                 backend/main.py
                                         │
                          ┌──────────────┼───────────────────────────┐
                          ▼              ▼                           ▼
                  api/routes/*      services/*                  iterations/*
                  (HTTP surface)  (pipeline, app_state,     (3 cached LangGraph
                                   runtime_settings)          apps: iter1/2/3)
                          │              │                           │
                          └──────────────┴───────────────┬──────────┘
                                                          ▼
                          domain (flat): memory.py · routing.py ·
                          graph_expansion.py · ingestion.py · seed_data.py
                                                          │
                                          storage/persistence.py → backend/state/*.json
```

- **Three iterations** are three independently-compiled LangGraph apps built from shared
  node modules and cached once per process (`iterations/__init__.py:get_workflow`).
- **LLM access** is abstracted behind *semantic steps* (extraction / synthesis / judge /
  graph_expansion), each with a provider+model route, env/runtime overrides, and a
  configured fallback (`backend/llm.py`).
- **Dedup memory** uses local `fastembed` (BAAI/bge-small-en-v1.5, 384d, ONNX/CPU) with a
  deterministic lexical fallback — no remote embedding cost (`backend/memory.py`).
- **State** is in-memory + JSON files under `backend/state/` (watchlist, graph, run
  results, settings persist; ledger and expansion-status are process-only).
- **Observability**: Arize Phoenix / OpenInference spans around runs and graph expansion.

This is a coherent, well-layered prototype. The decomposition that previous passes
introduced (routes → services → storage, iteration node split, typed schemas, versioned
state wrappers, CI, uv lock) is real and good. The remaining weaknesses are mostly
**deployment-default and single-process-assumption** issues plus a few residual monoliths.

---

## 2. Backend

### 2.1 Layering — strong
- `main.py` (76 lines) is now a thin composition root: middleware, exception handlers,
  router registration, startup hydration. Good.
- HTTP surface is split into seven route modules under `api/routes/` with a typed Pydantic
  schema module (`api/schemas.py`) — graph node/edge mutations are properly validated with
  `Literal` vocabularies and field validators.
- Business logic lives in `services/` (`pipeline.py`, `app_state.py`, `runtime_settings.py`)
  and `storage/persistence.py`. Routes stay declarative and delegate. This is the right shape.
- `llm.py` is the standout module: nodes depend on a semantic role, not a vendor SDK.
  Provider resolution has a clear precedence chain (env step-override → runtime setting →
  legacy global → default route) with a configured-provider check and fallback. Status
  reporting (`model_statuses`, `provider_statuses`) backs the settings UI cleanly.

### 2.2 Iteration / workflow modularization — mostly good
- The old `iterations/common.py` monolith has been split into focused node modules
  (`extraction`, `routing_nodes`, `memory_nodes`, `synthesis`, `guardrails`, `fetching`,
  `extraction_focus`, `contracts`, `prompts`, `mock_data`, `utils`). `common.py` is now a
  69-line re-export facade.
- **Residual debt:** `synthesis.py` is still 846 lines (bucket build + worker + post-process
  + mock in one file). The facade re-exports three *private* symbols
  (`_normalize_synthesis_significance`, `_postprocess_synthesis`,
  `_relax_language_only_judge_failure`) through `__all__` — a Python anti-pattern.

### 2.3 Domain modules — flat, inconsistent
`memory.py`, `routing.py`, `graph_expansion.py`, `ingestion.py`, `seed_data.py` sit at
`backend/` root while everything else is a package. Cosmetic, but it breaks the otherwise
consistent layering. A `backend/domain/` (or similar) package would finish the structure.

### 2.4 Concurrency model — correct only under the single-process assumption
- Graph reads/writes **are** serialized: `routing.graph_lock()` (RLock) +
  `graph_expansion._expansion_lock`, held around expand-and-persist.
- The **ledger** (`memory._ledger_store`, a module global) is **not** locked. It is mutated
  in-place during the *sync* `POST /api/run` handler, which FastAPI runs in a threadpool, so
  two overlapping runs can interleave. `services/pipeline.py` snapshots and restores the
  ledger around a run **non-atomically** — a concurrent run finishing mid-window can be
  silently rolled back.
- `app_state.run_results` + its 300KB+ JSON write are likewise unprotected (last-write-wins).
- For one local user this is theoretical. It is documented here as the exact boundary that
  breaks under a second user or a second worker. (See Issues I-07, M-03.)

### 2.5 Resilience gaps
- **No timeout** anywhere on `get_workflow(...).invoke()` or inside `invoke_with_retry`.
  A hung provider call parks a threadpool worker indefinitely and blocks subsequent runs
  until restart — a single-point failure for a *live* demo. (Issue M-01.)
- `invoke_with_retry` retries on **any** `Exception`, including pydantic `ValidationError`
  (a schema/content failure, not a transient one), doubling latency and API cost on bad
  output even though `classify_llm_failure` already knows the difference. (Issue M-04.)

### 2.6 Verified library posture (context7, 2026-06-08)
| Library | Pin | Current | Verdict |
|---|---|---|---|
| FastAPI | `>=0.115,<1.0` | startup uses **deprecated** `@app.on_event` → use `lifespan` | fix |
| Pydantic | `>=2,<3` | v2; `.dict()` fallback is dead **and** silently broken | fix |
| LangGraph | `>=0.2,<2.0` | current stable **1.0.x**; `Send` still supported (import from `langgraph.types`) | pin OK; consider `>=1.0` |
| uv | — | `uv sync --frozen` + committed lock + `package=false` is idiomatic; CI could use `--locked` | OK |
| fastembed | `>=0.5,<1.0` | `TextEmbedding` + `bge-small-en-v1.5` are current defaults | OK |

---

## 3. Frontend

- **Good extraction:** API client (`api/client.ts`), shared `types.ts`, `GraphView`,
  `RunControls`, `WatchlistSidebar`, `SettingsModal`, `AddTickerModal`,
  `EngineStatusPopover` are all separate, and most have Vitest interaction tests.
- **Residual monolith:** `App.tsx` is still **1375 lines** holding ~25 `useState`,
  polling effects, connection/retry state machine, and all result-detail rendering. This is
  the single largest structural item on the frontend. Natural next splits: `DashboardHeader`,
  `TickerDetailPanel`, `ResultsView`, and hooks `useDashboardState` / `usePollingStatus`.
- **Type safety is weakened:** `tsconfig.json` has `"strict": false`; `App.tsx`/`client.ts`
  use `any` heavily (~26 occurrences in App.tsx). Build does run `tsc`, so there *is* a
  type-check gate, but it is permissive.
- **Build/config posture (context7):** Vite 8.x and Vitest 4.x pins are current. The Vitest
  config is embedded in `vite.config.ts`; current docs mildly prefer a separate
  `vitest.config.ts` via `mergeConfig`, but the embedded form is valid. React is pinned at
  **18.2.0** — React 19 is GA and 18.3 is the deprecation-warning bridge; 18.2 is supported
  but two steps behind.

---

## 4. Setup, scripts, CI

- **Setup** is clean: `scripts/setup.sh` / `setup.ps1` check for `uv`/`node`/`npm`, sync the
  backend via the lock, `npm ci` the frontend, and seed `.env` from `.env.example`. Clear
  next-step output.
- **Dependency ownership** is now correct: `backend/pyproject.toml` + `backend/uv.lock` are
  the single source of truth; the old `requirements.txt`/`.lock` dual path is gone; root
  `pyproject.toml` is a thin workspace shell (and *does* configure `[tool.pyright]`).
- **Scripts** are tidied under `backend/scripts/` (Phoenix runner, embedding prewarm, scratch
  inspectors).
- **CI** (`.github/workflows/ci.yml`) runs backend tests, frontend tests, frontend build,
  `uv pip check`, and `npm audit --audit-level=high`. Solid baseline. Gaps: **windows-only**
  matrix, and **no Python static analysis step** despite pyright being configured (no
  `ruff`/`mypy`/`pyright` invocation in CI).

---

## 5. Security posture

This is a localhost classroom demo with no auth by design, so the bar is "safe defaults,"
not "production hardening." Against that bar:

- **Good:** `.env` is gitignored; secrets stay in env, never in the settings UI or state
  files; CORS origins are explicitly configured (not `*`); state writes are atomic
  (`tmp` + `os.replace`).
- **Weak default — network exposure:** `main.py` and `.vscode/launch.json` bind
  `host="0.0.0.0"` with **no auth on any endpoint**. On shared Wi-Fi, anyone on the LAN can
  drive the pipeline and burn the developer's LLM quota. Default should be `127.0.0.1`.
- **CORS nuance (context7):** with explicit origins the current `allow_methods=["*"]` /
  `allow_headers=["*"]` + `allow_credentials=True` combo is *functionally* safe (Starlette
  resolves the wildcards to concrete values when credentials are on), but the FastAPI docs
  explicitly advise against `*` with credentials — enumerate methods/headers to be
  doc-compliant.
- **Committed runtime state:** `backend/state/graph.json`, `run_results.json` (300KB+),
  `watchlist.json` are tracked in git. Not a secret leak, but it ships one dev machine's run
  as repo "truth" and dirties the tree on every run.

---

## 6. Tests

- **Backend:** `backend/tests/run_tests.py` — 26 `unittest` methods across
  `TestWorkflow`, `TestGuardrails`, `TestModelSelection`, `TestGraphExpansion`,
  `TestPersistenceAndApiSchemas`. Good coverage of the workflow, guardrail
  pass/regenerate/degrade path, model-route resolution, graph expansion, and schema/
  persistence. **One 1254-line file** — should be split per concern into a `tests/` package.
- **Frontend:** 5 test files (client, AddTickerModal, RunControls, SettingsModal,
  WatchlistSidebar). Missing: App-level flows (run loading/error, result rendering, graph
  rebuild/manual-expand).
- No coverage threshold is enforced in CI.

---

## 7. Documentation accuracy

The `.md` docs are **partly stale** and should not be trusted as current spec:

- `research/codebase-research.md` cites `backend/iterations/common.py:1-1429` and
  `backend/main.py:1-223` — those files are now **69** and **76** lines. Its line anchors are
  wrong post-refactor, though its prose narrative is still broadly correct.
- `research/senior-review-and-remediation-plan.md` and `remaining-remediation-roadmap.md`
  read as **progress journals** ("Done via…"), not a current-state architecture description.
  Useful history, but they conflate "planned," "done," and "deferred."
- `README.md` (649 lines), `capstone-system-design.md` (453), `guardrails-and-evaluation.md`
  (225) were not line-audited here; they should be re-checked against the current module
  layout before submission (they predate the route/service/storage split).

**This document (`architecture-analysis-20260608.md`) is intended to be the current-state
reference; the issues/remediation companion lists the fixes.**

---

## 8. Overall assessment

| Dimension | Grade | Note |
|---|---|---|
| Backend layering | A− | clean routes/services/storage; flat domain modules the only smell |
| Workflow modularity | B+ | good split; `synthesis.py` + facade `__all__` residue |
| Frontend modularity | B | good extraction; `App.tsx` still a 1375-line monolith |
| Setup / deps / CI | A− | uv lock + CI solid; no static-analysis gate, windows-only |
| Security defaults | B− | secrets handled well; `0.0.0.0` + no-auth + committed state |
| Resilience | C+ | no invoke timeout; over-broad retry; unlocked ledger |
| Tests | B | real backend coverage; giant test file; thin App tests |
| Docs accuracy | C | stale line anchors; journals masquerading as spec |

**Bottom line:** architecturally sound prototype with the bones of a maintainable product.
The highest-value work is *not* more decomposition — it is **resilience and safe defaults**
(invoke timeout, retry classification, `127.0.0.1`, gitignore state) which are cheap and
protect a live graded demo, followed by finishing the `App.tsx` split and refreshing docs.

See **`architecture-issues-and-remediations-20260608.md`** for the prioritized fix list.

---

## Appendix A — How this review was run (agent plan)

The task explicitly required a senior-led review that **delegates verification to less
powerful agents** and **does not trust training data**. The plan used, and recommended for
re-runs:

**Principle:** the senior (main) agent holds context and judgment; subagents are cheap,
parallel, single-purpose, and must cite sources. Never let a subagent's conclusion land
unverified on a high-severity claim.

1. **Senior pass (main, this agent).** Build the full file map, read every architectural
   seam (routes, services, storage, llm, iterations facade, memory/graph concurrency,
   frontend entry points, CI, setup, docs). Produce a *draft* findings list with severity.

2. **Fact-verification subagent (Sonnet + context7).** Hand it a numbered list of concrete,
   falsifiable library claims (FastAPI lifespan, Pydantic `.dict()`, LangGraph `Send`/version,
   Vite/Vitest/React versions, uv workflow, fastembed API, CORS-with-credentials). It must use
   `mcp__context7` and report TRUE/FALSE/NUANCED + the current recommended approach + a source
   note. This is where "don't trust training data" is enforced.

3. **Red-team subagent (Sonnet).** Hand it the draft findings + the project's real context
   (single-user local demo) and require it to read the actual files and rate each finding
   VALID / OVERSTATED / WRONG / MISSING-CONTEXT with `file:line`, plus surface up to 5 missed
   issues. This caught the missing invoke-timeout (High), the `reload=True` state reset, the
   `run_results` race, the retry-cost multiplier, and the private-symbol `__all__` leak.

4. **Senior reconciliation (main).** Re-verify any subagent claim that changes a severity or
   that the subagent itself got partially wrong (e.g. the red-teamer missed that *root*
   `pyproject.toml` configures pyright). Only verified findings enter the deliverables.

**Why weaker models for steps 2–3:** the work is bounded lookup and adversarial reading, not
synthesis — Sonnet/Haiku are sufficient and run in parallel, keeping the senior's context
free for judgment and the final write-up.

**For a fuller sweep**, add parallel single-purpose subagents: (a) a frontend-only reader to
audit `App.tsx` state/effects for stale-closure and polling-leak bugs; (b) a test-coverage
reader to map asserted-vs-unasserted behavior; (c) a docs-vs-code reconciler to line-audit
README/`capstone-system-design.md` against the current module layout. Fan them out, then
reconcile centrally.
