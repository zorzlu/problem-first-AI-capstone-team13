# Senior Review and Remediation Plan

> ⚠️ **Historical progress journal.** This records an earlier remediation pass and mixes
> planned / done / deferred items. The current-state reference is
> [`architecture-analysis-20260608.md`](./architecture-analysis-20260608.md); the live
> issue list and its status is [`architecture-issues-and-remediations-20260608.md`](./architecture-issues-and-remediations-20260608.md).

## Executive Summary

The system is a strong capstone prototype: the product concept is coherent, the three LangGraph iterations are easy to demo, and the guardrail loop is much better than a plain "LLM generates a summary" architecture. The main weakness is that prototype pressure has compressed too many responsibilities into a few files. The app now needs a pass that turns the demo into a maintainable product surface: smaller modules, explicit runtime settings, repeatable eval sets, stronger dependency/version discipline, and safer production defaults.

## Highest-Risk Issues

1. `backend/iterations/common.py` has been reduced to a compatibility facade. The remaining backend long-file pressure is now `backend/iterations/synthesis.py`, which contains the active bucket construction, worker synthesis, and post-processing path.
2. `frontend/src/App.tsx` is still large, although types, API calls, graph rendering, run controls, watchlist sidebar, and modals have been extracted. The remaining issue is mostly dashboard orchestration and result-detail rendering.
3. `backend/main.py` has been reduced to app creation/startup/router registration. Endpoint ownership now lives under `backend/api/routes/`, and pipeline execution/ledger rollback lives under services.
4. Backend dependencies are now owned by `backend/pyproject.toml` and locked with `backend/uv.lock`; CI syncs them with `uv`. Frontend dependencies are pinned through `package-lock.json`.
5. Phoenix was only used as tracing/observability. A repeatable eval-set runner now exists, but eval maturity and comparison workflows are intentionally deferred to a separate conversation.
6. CORS currently allows all origins. That is acceptable for a local classroom demo but unsafe as a deployed default.
7. Runtime state is split across in-memory objects and JSON files. Watchlist, graph, settings, and run results persist; ledger and graph expansion status do not. The JSON files do not have schema versions or migrations, so persisted state can silently break after shape changes.
8. Configuration was environment-only. API keys should stay there, but provider/model routing is a reasonable non-secret setting for the tool itself.
9. CI now runs backend tests, frontend interaction tests, frontend build, dependency consistency, and a high-severity frontend audit gate. Eval smoke runs are intentionally deferred.
10. API graph mutation endpoints now use typed Pydantic request schemas.
11. Background graph-expansion and manual graph writes now use explicit in-process locking. This is acceptable for one local Uvicorn process; multi-process deployment would still need an external store/queue.
12. Frontend interaction tests now cover the settings modal, add-ticker modal, API client request/error behavior, extracted run controls, and the extracted watchlist sidebar. Broader App-level coverage is still useful for graph rebuild/manual expand and result rendering.
13. The stale frontend `lint` script has been removed because there is no ESLint configuration/dependency in the frontend folder.
14. The Vite major-version migration has been applied and `npm audit` now reports zero vulnerabilities.

## Configuration Decision

Expose these in the app settings UI:

- LLM provider and model per semantic step: extraction, synthesis, judge, graph expansion.

Keep these out of the settings UI for now:

- API keys and base URLs. They remain in `.env` or deployment secrets.
- Eval execution and eval-set selection. These belong in CI/operator tooling and Phoenix/Arize workflows, not the analyst product UI.
- Dedup thresholds and freshness windows. These affect product validity and should move only after we add stronger eval coverage and clear presets.
- CORS and host/port settings. These are deployment concerns, not analyst workflow settings.

## Prioritized Plan

### P0: Stabilize the Product Loop

- Add non-secret runtime settings and wire model-route resolution through them.
- Add a replay eval-set runner that writes eval results and emits Phoenix-friendly spans.
- Add stateful path-set evals before changing memory, vector, routing, or graph-status behavior.
- Bound Python and frontend dependency versions.
- Add CI that runs backend tests and frontend typecheck/build. Eval smoke runs are deferred.
- Add a Python dependency lock path for deterministic backend installs.
- Document the distinction between unit tests, eval sets, and Phoenix traces.

### P1: Split Backend by Responsibility

- Move workflow schemas to `backend/iterations/contracts.py`.
- Move prompts to `backend/iterations/prompts.py`.
- Move mock replay extraction data to `backend/iterations/mock_data.py`.
- Move extraction focus/ticker alias helpers to `backend/iterations/extraction_focus.py`.
- Move fetch/filter node logic to `backend/iterations/fetching.py`.
- Move synthesis and safety judging to `backend/iterations/synthesis.py`.
- Move canonical extraction to `backend/iterations/extraction.py`.
- Move ledger-node helpers to `backend/iterations/memory_nodes.py`.
- Move routing-node helpers to `backend/iterations/routing_nodes.py`.
- Move result serialization and ledger rollback out of `main.py` into `backend/services/pipeline.py`.
- Add a public ledger snapshot/restore API in `backend/memory.py` and remove direct `_ledger_store` access from `main.py`.
- Split FastAPI endpoints into route modules under `backend/api/routes/`.

### P2: Split Frontend

- Move API calls to `frontend/src/api/client.ts`.
- Move shared types to `frontend/src/types.ts`.
- Move graph layout/rendering to `frontend/src/components/GraphView.tsx`.
- Move engine/settings modals to `frontend/src/components/`.
- Keep `App.tsx` as route/layout orchestration only.

### P3: Production Hardening

- Replace permissive CORS with configured origins.
- Add request validation for graph node/edge mutations instead of accepting raw `Dict[str, Any]`.
- Add persisted or database-backed ledger storage if story memory must survive restarts.
- Add schema versions/migrations for JSON-backed state files (`watchlist`, `graph`, `settings`, `run_results`) or move them behind a real store.
- Add an explicit concurrency policy for background graph expansion and graph/status writes.
- Add API error response conventions so frontend failures are consistent and debuggable.
- Add CI commands for backend tests, frontend interaction tests, frontend typecheck/build, frontend high-severity audit, and dependency lock verification.
- Add or remove the frontend lint gate: either configure ESLint properly or delete the misleading script.
- Complete the Vite major-version migration needed to clear remaining dev-server audit findings.

### P4: Eval Maturity (Deferred)

- Version eval datasets and expected assertions so changes to memory/routing behavior are intentional.
- Keep eval execution outside the analyst UI, but make eval outputs easy to compare across branches/runs.
- Add separate eval suites for direct extraction, duplicate/update memory behavior, cross-impact routing, graph expansion quality, synthesis grounding, and guardrail degradation.
- Capture cost/latency/token metrics per semantic LLM step so model-route changes can be judged on quality and runtime, not only pass/fail.
- Add eval isolation rules: clean ledger, clean graph/status, and optionally separate vector/index state per run.

## Work Completed in This Pass

- Added persisted non-secret runtime settings in `backend/services/runtime_settings.py`.
- Added `/api/settings` read/update endpoints and a frontend Runtime Settings modal.
- Added `backend/evals/runner.py` plus `backend/evals/sets/replay_scenarios.json` as operator/CI tooling that can emit Phoenix spans.
- Added a small schema module so API request models are no longer embedded in `main.py`.
- Bounded backend dependency versions and pinned frontend package versions.
- Split FastAPI route modules out of `backend/main.py` and moved mutable process state to `backend/services/app_state.py`.
- Moved LangGraph workflow state and structured-output schemas to `backend/iterations/contracts.py`.
- Moved extraction, synthesis, and judge prompt templates to `backend/iterations/prompts.py`.
- Moved no-key mock extraction fixtures to `backend/iterations/mock_data.py`.
- Moved extraction focus/ticker alias helpers to `backend/iterations/extraction_focus.py`.
- Moved fetch/filter node logic to `backend/iterations/fetching.py`.
- Moved extraction, routing, memory, synthesis, guardrail, and utility workflow nodes out of `backend/iterations/common.py`.
- Converted `backend/iterations/common.py` into a compatibility facade for existing iteration imports.
- Fixed a latent `_empty_state_summary` dependency issue by importing `FRESHNESS_LOOKBACK_MINUTES` through the new synthesis module.
- Added configured CORS origins via `CORS_ORIGINS`.
- Added versioned JSON state wrappers with legacy-read compatibility for watchlist, graph, run results, and runtime settings.
- Added typed Pydantic graph node/edge mutation request schemas.
- Added in-process graph/status locks around graph expansion and graph mutation persistence.
- Added `.github/workflows/ci.yml` for backend tests, frontend interaction tests, frontend build, dependency consistency, and high-severity frontend audit.
- Added `backend/pyproject.toml` and `backend/uv.lock` for reproducible backend installs.
- Removed the old `backend/requirements.txt` / `backend/requirements.lock` dual-source dependency path.
- Updated CI and VS Code backend install/test tasks to use `uv`.
- Removed the stale frontend `lint` script.
- Added Vitest and Testing Library component interaction tests for the settings and add-ticker modals.
- Added frontend API client tests for env prefixing, request serialization, and backend error-envelope parsing.
- Extracted frontend run controls to `frontend/src/components/RunControls.tsx` and added interaction tests.
- Extracted frontend watchlist/sidebar composition to `frontend/src/components/WatchlistSidebar.tsx` and added interaction tests.
- Migrated Vite to `8.0.16` and cleared the frontend audit report.

## Still Missing From Implementation

- App-level interaction coverage for graph rebuild/manual expand and result rendering.
- Optional further split of `backend/iterations/synthesis.py` into bucket, worker, and postprocess modules.
- Further split of `frontend/src/App.tsx` into dashboard header shell, ticker detail, and results view modules.
- Eval isolation and comparison tooling for memory/vector/graph-status experiments. Deferred by request.
- Multi-process-safe graph expansion/state coordination if the backend is deployed with more than one worker.
