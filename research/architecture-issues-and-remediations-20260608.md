# Architecture Issues & Remediations — 2026-06-08

> Companion to `architecture-analysis-20260608.md`. Each issue has: severity (rated for
> **this** project — a single-user local demo graded on architecture), evidence (`file:line`),
> and a concrete remediation. Library claims were verified against **context7** on 2026-06-08;
> training data was not trusted. Findings prefixed **M-** were surfaced by the red-team pass.
>
> Severity legend: **High** = can break a live graded demo or leak/expose; **Med** = real
> architecture/quality defect worth fixing before submission; **Low** = polish / future-proofing.

---

## Implementation status — 2026-06-08

**Done & verified (Waves 1–2 + docs):**
- M-01 tunable timeout (300s default, env `PIPELINE_RUN_TIMEOUT_SECONDS`) + `AbortSignal`
  "Stop Waiting" control. *Verified: 504 + ledger rollback, request freed in ~1s.*
- I-04 `127.0.0.1` default · M-02 reload off (both env-overridable) · I-02 `lifespan` ·
  I-03 dead `.dict()` removed · M-04 retry no longer fires on schema/validation failures.
- I-01 three runtime-state JSONs git-ignored; app self-seeds from `seed_data.EXPOSURE_GRAPH`
  + `DEFAULT_WATCHLIST`. *(User must `git rm --cached` them once — see README.)*
- I-10 CI is now a 3-OS matrix (windows/macos/ubuntu) for backend+frontend; OS-agnostic
  dep check; `--locked`; pyright job (basic mode, non-blocking, scratch/tests excluded).
- I-12 Phoenix status probed (was hardcoded) · I-13 memory accessors (no more private
  reach-in) · I-14 mimetypes shim centralized + Windows-guarded · M-05 private symbols out
  of the facade `__all__` · I-07/M-03 runs serialized under `runs_lock`.
- `run_tests.py` split into per-suite `test_*.py` modules + discovery runner (26 tests green).
- I-11 stale research docs banner-marked historical; this file + the analysis are the references.

**Done & verified (Wave 3):**
- I-09 `App.tsx` **1375 → 210 lines** — extracted `useDashboardState`/`usePollingStatus` hooks
  + `DashboardHeader`/`ResultsView`/`TickerDetailPanel`/`GraphModal` components; `tsconfig`
  `strict: true` enabled with **zero** TS errors. *(13 frontend tests + build green.)*
- I-06 `synthesis.py` **846 → 293 lines** — split into `synthesis_scoring` / `synthesis_buckets`
  / `synthesis_postprocess`; worker kept in `synthesis.py` to preserve the `get_synthesis_llm`
  test patch target. *(26 backend tests green.)*
- I-08 **capability-oriented backend restructure** (chosen over the generic `domain/` bucket):
  `core/` (config, llm, mimetypes), `ingestion/` (news + scenarios), `memory/` (ledger),
  `graph/` (graph + expansion + seed). `seed_data.py` split by owner; `routing.py` → `graph/graph.py`
  fixing the misnomer. `memory`/`ingestion` packages re-export their public API so call sites were
  unchanged; the rest rewritten boundary-safe. `__file__`-relative paths fixed for the deeper files.
  *(26 backend tests green, app boots, pyright steady at 14.)*

**Deferred / stretch:**
- I-10 (stretch) make pyright a hard gate once the LangChain-stub findings are resolved.
- I-11 (stretch) full line-audit of `README.md` / `capstone-system-design.md`.

---

## Priority order (do these first)

1. **M-01** Add an invoke timeout (protects a live demo) — *High*
2. **I-04** Default bind to `127.0.0.1`, drop no-auth LAN exposure — *Med, cheap*
3. **I-01** Gitignore + seed runtime state files — *Med, cheap*
4. **M-04** Stop retrying schema/validation failures — *Med, cheap*
5. **I-02** FastAPI `lifespan` instead of `on_event` — *Low, cheap*
6. **I-11 / I-09** Refresh stale docs; finish `App.tsx` split — *Med, larger*

---

## High severity

### M-01 — No timeout on LLM workflow invocation --> remember that agents might take een 3 minutes to process everythign. put the timeout in a place where it could be tuned. i dont know whats the senior approach? maybe have a stop button or smth like that? idk. the max time shall be bigger than 4 minutes
**Evidence:** `backend/services/pipeline.py:105` `get_workflow(req.iteration).invoke(initial_state)`
has no timeout; `backend/iterations/utils.py:30-41` `invoke_with_retry` also has none.
**Impact:** A hung/slow provider call parks the sync threadpool worker indefinitely and blocks
all subsequent `/api/run` requests until Uvicorn is restarted — a single-point failure during a
*live* demo.
**Remediation:** Wrap the invoke in a bounded executor, e.g.
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout
with ThreadPoolExecutor(max_workers=1) as ex:
    try:
        final_state = ex.submit(get_workflow(req.iteration).invoke, initial_state).result(timeout=120)
    except FTimeout:
        restore_ledger_store(ledger_snapshot)
        raise HTTPException(504, "Pipeline timed out")
```
Make the timeout an env/config knob. (`signal.alarm` is unavailable on Windows + threadpool, so
prefer the executor approach.)

---

## Medium severity

### I-01 — Runtime state files committed to git --> seed should just be the companies stacl and i guess we ould provide the first exposure graph for them. so that people can easily run the 3 iterations before doing other things. 
**Evidence:** `git ls-files` tracks `backend/state/graph.json`, `backend/state/run_results.json`
(300KB+), `backend/state/watchlist.json`. `.gitignore` excludes `state/settings.json`,
`state/*.log`, `state/eval_runs/`, `state/fastembed_cache/` but **not** these three.
**Impact:** Every run dirties the working tree and produces noisy diffs/merge conflicts; the repo
ships one dev machine's run as canonical state.
**Remediation:** Add `backend/state/graph.json`, `backend/state/run_results.json`,
`backend/state/watchlist.json` to `.gitignore`; `git rm --cached` them. Seed `graph`/`watchlist`
from `seed_data.py` / `DEFAULT_WATCHLIST` on first run (already the load-default path), and let
`run_results` regenerate. Optionally commit a tiny `*.example.json` if a seed graph must ship.

### I-04 — `0.0.0.0` bind + no auth exposes the API to the LAN
**Evidence:** `backend/main.py:76` `uvicorn.run(..., host="0.0.0.0", reload=True)`;
`.vscode/launch.json` passes `--host 0.0.0.0`. No endpoint has auth.
**Impact:** Anyone on the same network can drive the pipeline, mutate the graph/watchlist, and
burn the developer's LLM quota.
**Remediation:** Default `host="127.0.0.1"` in both `main.py` and `launch.json`; make the bind an
env var for the rare case a real LAN demo is needed. If LAN access is ever required, add a shared
bearer token check via a single FastAPI dependency.

### M-04 — `invoke_with_retry` retries content/validation failures
**Evidence:** `backend/iterations/utils.py:39` catches bare `Exception` and retries once;
`classify_llm_failure` (same file, 15-28) already distinguishes a `ValidationError`/schema
failure from a transient availability failure but is **not** consulted here.
**Impact:** A malformed-but-returned LLM response (schema failure) triggers a second full paid
call + round-trip before failing identically — a cost/latency multiplier on bad output, which
matters on a quota-constrained student account.
**Remediation:** Only retry transient failures:
```python
except Exception as e:
    if isinstance(e, (ValidationError, ValueError)) or "OutputParser" in type(e).__name__:
        raise  # schema/content failure — retrying won't help
    return runnable.invoke(messages)
```

### I-10 — CI has no Python static-analysis gate; windows-only matrix
**Evidence:** `.github/workflows/ci.yml` runs tests/build/audit but no `ruff`/`mypy`/`pyright`,
even though root `pyproject.toml` configures `[tool.pyright]`. Jobs run only on `windows-latest`.
**Impact:** Type/lint regressions land silently; the configured pyright is never enforced.
**Remediation:** Add a `uv run pyright` (or `ruff check`) step to the backend job. Consider a
`ubuntu-latest` leg if portability matters (the app targets Windows, so this is optional). --> app targets windows macos and linux. ..> THIS IS IMPORTANT AF.

### I-11 — Documentation is stale / misleading
**Evidence:** `research/codebase-research.md` cites `common.py:1-1429` and `main.py:1-223`; actual
sizes are 69 and 76 lines. `senior-review-*.md` and `remaining-remediation-roadmap.md` are
progress journals, not current spec. `README.md` / `capstone-system-design.md` predate the
route/service/storage split.
**Remediation:** Treat `architecture-analysis-20260608.md` as the current reference. Fix or remove
the wrong line anchors in `codebase-research.md`; re-audit README and `capstone-system-design.md`
against the current module layout before submission.

### I-09 / Frontend — `App.tsx` monolith + non-strict TS
**Evidence:** `frontend/src/App.tsx` is 1375 lines (~25 `useState`, polling effects, retry state
machine, all result rendering). `frontend/tsconfig.json:10` `"strict": false`; ~26 `any` in
`App.tsx`.
**Remediation:** Split into `DashboardHeader`, `TickerDetailPanel`, `ResultsView` and hooks
`useDashboardState` / `usePollingStatus` (split by workflow, not visual chunk). Turn on
`"strict": true` and fix the resulting `any`s incrementally (start by typing `client.ts` returns).

---

## Low severity

### I-02 — Deprecated FastAPI `on_event`
**Evidence:** `backend/main.py:65-67` `@app.on_event("startup")`. context7: deprecated in favor of
`lifespan`.
**Remediation:**
```python
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    hydrate_app_state(); yield
app = FastAPI(title=..., lifespan=lifespan)
```

### I-03 — Dead **and** silently-broken `.dict()` fallback
**Evidence:** `backend/api/routes/settings.py:28-33`. With `pydantic>=2,<3` pinned, `.model_dump()`
always exists so the `except AttributeError: .dict()` branch is dead — and if it ever ran, `.dict()`
(deprecated proxy) would not raise `AttributeError`, so the intended guard is illusory.
**Remediation:** Call `save_runtime_settings(req.model_dump())` directly; keep only the
`except Exception -> HTTP 400` for validation errors.

### M-03 — Unlocked `run_results` write race
**Evidence:** `backend/services/pipeline.py:112-113` mutates `app_state.run_results` then writes the
300KB+ JSON with no lock/atomic guard beyond the `tmp`+`replace` in persistence.
**Impact:** Two concurrent same-iteration runs last-write-wins in memory and on disk. Theoretical
for one user; documented as the multi-user boundary.
**Remediation:** Guard ledger snapshot/restore **and** run_results update under a single
`runs_lock` (RLock) if concurrent runs ever become possible.

### I-07 — Unlocked ledger global
**Evidence:** `backend/memory.py:_ledger_store` mutated in-place during the sync `POST /api/run`
(threadpool); snapshot/restore in `pipeline.py:100,109,117` is non-atomic. Graph writes *are*
locked; ledger writes are not.
**Remediation:** Same `runs_lock` as M-03, or serialize `/api/run` execution. Single-user: no action
needed beyond a code comment stating the assumption.

### M-02 — `reload=True` resets all in-memory state
**Evidence:** `backend/main.py:76` `reload=True` in the `__main__` path. On any file save Uvicorn
respawns the worker, resetting `_ledger_store`, `_embedding_model`, and the RLocks; in-flight runs
are orphaned and accumulated ledger data is lost.
**Remediation:** Don't ship `reload=True` as the default entrypoint; document that dev reload wipes
process memory. The documented run command (`setup.sh`) already omits `--reload` — make `main.py`
match it (default off, opt-in via env).

### M-05 / I-08 — Facade re-exports private symbols; flat domain layout
**Evidence:** `backend/iterations/common.py.__all__` lists `_normalize_synthesis_significance`,
`_postprocess_synthesis`, `_relax_language_only_judge_failure`. Domain modules (`memory`, `routing`,
`graph_expansion`, `ingestion`, `seed_data`) sit at `backend/` root while everything else is a
package.
**Remediation:** Drop private names from `__all__` (import them directly where genuinely needed).
Plan a `backend/domain/` package move *after* the `synthesis.py` split, since it touches many imports.

### I-06 — Residual large files
**Evidence:** `synthesis.py` 846, `graph_expansion.py` 594, `seed_data.py` 545, `routing.py` 504,
`tests/run_tests.py` 1254.
**Remediation:** Split `synthesis.py` into `synthesis_buckets` / `synthesis_worker` /
`synthesis_postprocess`; split `run_tests.py` into a `tests/` package mirroring the suites. The
others are acceptable (mostly data/seed).

### I-12 — Phoenix status is hardcoded
**Evidence:** `backend/api/routes/status.py:14` returns `"running": True` unconditionally.
**Impact:** UI shows a healthy Phoenix even when the collector is down.
**Remediation:** Probe the collector (TCP connect to the OTLP/UI port, or check the registered
provider) and report the real state.

### I-13 — Leaky encapsulation into `memory.py` privates
**Evidence:** `status.py:39-43,51-52` reads `memory_module._ledger_store`, `_EMBEDDING_MODEL_NAME`,
`_EMBEDDING_CACHE_DIR`.
**Remediation:** Promote the read-only constants to public names (`EMBEDDING_MODEL_NAME`) and add a
public `ledger_counts()` accessor; route status through those.

### I-14 — Duplicated `mimetypes.init(files=[])` Windows hack
**Evidence:** identical bare `try/except Exception: pass` in `main.py:1-6` and `config.py:1-5`
(runs twice; swallows all errors; no comment).
**Remediation:** Move to one helper (e.g. `backend/_win_mimetypes.py`) with a one-line comment
explaining the Windows registry MIME-type workaround; import it once.

---

## Library currency notes (verified, context7 — 2026-06-08)

These are **not** issues to fix now, but the verified posture behind the analysis:

- **LangGraph** pin `>=0.2,<2.0` is fine; current stable is **1.0.x**. Import `Send` from
  `langgraph.types`. Consider raising the floor to `>=1.0` to avoid resolving the 0.2 line.
- **React 18.2.0** is supported but two steps behind (18.3 bridge, 19.x GA). Optional: bump to
  18.3 to surface deprecation warnings before any future 19 migration.
- **Vite 8 / Vitest 4** pins are current. Embedded Vitest config is valid; a separate
  `vitest.config.ts` via `mergeConfig` is the mildly-preferred current pattern.
- **uv**: in CI, `uv sync --locked` is slightly safer than `--frozen` (it fails on a stale lock).
- **CORS**: with explicit origins the wildcard methods/headers + credentials combo is functionally
  safe but doc-discouraged; enumerate methods/headers to be compliant.

---

## Suggested execution waves

- **Wave 1 (hours, protects the demo):** M-01, I-04, I-01, M-04, I-02, I-03, M-02.
- **Wave 2 (a day, quality):** I-10 (pyright in CI), I-12, I-13, I-14, M-05 `__all__` cleanup,
  split `run_tests.py`.
- **Wave 3 (larger, maintainability):** `App.tsx` split + `strict: true` (I-09), `synthesis.py`
  split (I-06), `backend/domain/` move (I-08), doc refresh (I-11).
