# Intraday Cross-Impact Catalyst Briefings

A full-stack demo that monitors a stock watchlist for breaking news, deduplicates duplicate story threads, routes untickered geopolitical events through a causal exposure graph, and synthesizes per-ticker briefings via an LLM pipeline.

Built with **LangGraph** (pipeline orchestration), **FastAPI** (backend API), **React + Vite** (dashboard), and **Arize Phoenix** (LLM tracing).

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [API Keys](#api-keys)
4. [Local Setup](#local-setup)
5. [Running the Application](#running-the-application)
6. [Running with VS Code](#running-with-vs-code)
7. [Running Tests](#running-tests)
8. [The Three Pipeline Iterations](#the-three-pipeline-iterations)
9. [Environment Variable Reference](#environment-variable-reference)
10. [Repository Structure](#repository-structure)
11. [Troubleshooting](#troubleshooting)

---

## How It Works

Each run executes one of three compiled LangGraph workflows in `backend/iterations/`. The iteration files wire focused extraction, routing, memory, synthesis, guardrail, fetching, and prompt modules:

```text
Iteration 1
Fetch & Filter News
        ↓
Canonical Event Extraction  (LLM: gpt-4.1-nano / gemini-2.5-flash-lite)
        ↓
Route Events to Tickers     (direct tag routing)
        ↓
Assign Catalyst IDs         (no ledger in Iteration 1)
        ↓
Build Ticker Buckets
        ↓
Parallel Per-Ticker Workers (LangGraph Send: synthesis LLM + output safety judge)
        ↓
Collect Ticker Syntheses
        ↓
Compliance Gate             (regex scrub of buy/sell language)

Iteration 2
Fetch & Filter News
        ↓
Canonical Event Extraction  (LLM: gpt-4.1-nano / gemini-2.5-flash-lite)
        ↓
Route Events to Tickers     (direct tag routing)
        ↓
Ledger Memory Check         (local embeddings / lexical fallback)
        ↓
Build Ticker Buckets
        ↓
Parallel Per-Ticker Workers (LangGraph Send: synthesis LLM + output safety judge)
        ↓
Collect Ticker Syntheses
        ↓
Compliance Gate             (regex scrub of buy/sell language)

Iteration 3
Fetch & Filter News + Graph Query Expansion
        ↓
Canonical Event Extraction  (LLM: gpt-4.1-nano / gemini-2.5-flash-lite)
        ↓
Route Events to Tickers     (direct tag + exposure graph traversal)
        ↓
Ledger Memory Check         (local embeddings / lexical fallback)
        ↓
Build Ticker Buckets
        ↓
Parallel Per-Ticker Workers (LangGraph Send: synthesis LLM + output safety judge)
        ↓
Collect Ticker Syntheses
        ↓
Compliance Gate             (regex scrub of buy/sell language)
```

**No API keys?** The app runs in no-key mode using pre-baked mock events and rules-based synthesis. All three replay scenarios work fully offline; non-empty mock syntheses mark the LLM judge as skipped in `guardrailMetadata`.

### Output guardrails

Every non-empty LLM synthesis is checked by a structured output safety judge before the regex compliance gate. The synthesis and judge run inside a per-ticker LangGraph worker branch dispatched with `Send(...)`, so different tickers can be synthesized and judged independently before the collector node merges the results. The judge verifies that claims are grounded in the ticker bucket, that the briefing contains no trading advice/action language, and that indirect catalyst explanations stay inside the routed `impactPath` and `reasonForRouting`. If the judge fails, the backend regenerates that ticker's synthesis once with the defects named; if the regenerated output still fails or the judge errors, the briefing is degraded to **Briefing suppressed pending verification** with no main catalysts. The API response includes `guardrailMetadata`, and the ticker detail view shows a badge such as `Verified`, `Regenerated after guardrail`, or `Suppressed pending verification`.

### Exposure-graph expansion (separate from the run pipeline)

When you **add a ticker** to the watchlist, a background task maps that ticker's causal exposure (suppliers, customers, competitors, partners, regions, technology themes, commodities, macro/shipping risks) and merges the resulting nodes and edges into the exposure graph. It pulls known stock peers from Finnhub, then calls the graph-expansion model route from `backend/llm.py` to generate the surrounding graph. Exposure and sensitivity edges are directional from the cause/source node to the affected company or ticker. This runs **once per ticker on add** (not on every pipeline run), and can be re-triggered manually per ticker or rebuilt for the whole watchlist. With no configured graph-expansion LLM, only the bare ticker node is added. Per-ticker progress (`pending -> running -> done/skipped/failed`) is shown in the UI.

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Python | 3.11.8 | Encoded in `.python-version`, `backend/.python-version`, `runtime.txt`, and `backend/pyproject.toml` |
| Node.js | 18.x | 20.x or later also works |
| npm | 9.x | Comes with Node.js |
| uv | 0.11.x | Backend Python dependency locking/sync |

Check your versions:

```bash
python --version
node --version
npm --version
uv --version
```

The backend is intended to run from the isolated environment at `backend/.venv`. Tools that understand `.python-version` or `pyproject.toml` should select Python 3.11 automatically; otherwise create the venv with Python 3.11 explicitly.

---

## API Keys

The application can use several optional service credentials. **All are optional** — see the table below for what each one unlocks.

### Which keys do you actually need?

| Scenario | Keys required |
|----------|--------------|
| Run the three built-in replay scenarios with real LLM synthesis | One configured chat provider route: Gemini, OpenAI, Anthropic, OpenAI-compatible, or local |
| Run the three replay scenarios without any LLM (rules-based mock output) | None |
| Pull live company news from Finnhub | `FINNHUB_API_KEY` |
| Pull live cross-impact / geopolitical news from Currents | `CURRENTS_API_KEY` |

---

### LLM provider routing

Model/provider selection is centralized in `backend/llm.py`. LangGraph nodes request semantic roles (`extraction`, `synthesis`, `judge`, `graph_expansion`); they do not construct vendor clients directly.

Default routes:
- Extraction, synthesis, judge: Gemini primary, OpenAI fallback.
- Graph expansion: OpenAI primary, Gemini fallback.

Supported providers:
- `openai`
- `gemini`
- `anthropic`
- `openai_compatible`
- `local`

Override any step with:

```env
SYNTHESIS_LLM_PROVIDER=anthropic
SYNTHESIS_LLM_MODEL=claude-sonnet-4-20250514

GRAPH_EXPANSION_LLM_PROVIDER=local
GRAPH_EXPANSION_LLM_MODEL=llama3.1
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
```

The legacy `LLM_PROVIDER` variable still works as a global provider override, but new configs should prefer explicit per-step variables. The deduplication ledger does **not** use remote LLM keys; it embeds locally (see [Catalyst dedup embeddings](#catalyst-dedup-embeddings-local-no-api-key) below).

---

### `GEMINI_API_KEY` — Google Gemini

**How to get it:**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with a Google account.
3. Click **Create API key** and copy the value.

The free tier is sufficient for all replay scenarios.

---

### `OPENAI_API_KEY` — OpenAI

**How to get it:**
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
2. Sign in and click **Create new secret key**.
3. Copy the value — it is only shown once.

You need a funded account (pay-as-you-go). Running all three replay scenarios costs well under $0.10.

---

### `ANTHROPIC_API_KEY` — Anthropic Claude

Use this when a step is configured with `*_LLM_PROVIDER=anthropic`.

**How to get it:**
1. Go to [console.anthropic.com](https://console.anthropic.com/).
2. Create an API key.
3. Set `ANTHROPIC_API_KEY` in `backend/.env`.

---

### Catalyst dedup embeddings (local, no API key)

The catalyst-memory ledger decides whether a fresh event is a duplicate, an update, or a new story. This is done with a **local embedding model** — there is no embedding API key and no per-call cost.

- **Primary:** [`fastembed`](https://github.com/qdrant/fastembed) running `BAAI/bge-small-en-v1.5` (384 dimensions, ONNX, CPU). The model downloads once (~50 MB) into `backend/state/fastembed_cache` by default, then runs fully offline. Override with the `EMBEDDING_MODEL` and `EMBEDDING_CACHE_DIR` env vars.
- **Fallback:** if the model cannot be loaded, the system automatically uses a deterministic lexical token-frequency cosine matcher (no extra dependencies). Recall on heavily paraphrased duplicates is lower, but it is fully deterministic. The UI memory panel shows which engine is active.

This replaced the earlier remote embedding API (`models/embedding-001` / `text-embedding-3-small`), which charged per call and was the main recurring cost in the dedup path.

---

### `FINNHUB_API_KEY` — Finnhub (live direct company news)

Used for: fetching real-time company-specific news in **Live Feeds** mode. Not needed for replay scenarios.

**How to get it:**
1. Go to [finnhub.io](https://finnhub.io) and click **Get free API key**.
2. Create a free account.
3. Your key appears on the dashboard immediately.

The free tier allows 60 API calls/minute, which is more than enough for this demo.

---

### `CURRENTS_API_KEY` — Currents API (live cross-impact news)

Used for: fetching broad geopolitical, macro, and technology news in **Live Feeds** mode with Iteration 3. Not needed for replay scenarios.

**How to get it:**
1. Go to [currentsapi.services](https://currentsapi.services/en/register).
2. Register a free account.
3. Your API key appears on the dashboard after email verification.

---

## Local Setup

Run all commands from the **repository root** unless noted otherwise.

### Step 1 — Clone the repository

```bash
git clone <repo-url>
cd problem-first-AI-capstone-team13
```

### Step 2 — Set up the local environment

Run the setup script once after cloning or after pulling dependency changes:

```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

```bash
# macOS / Linux
bash scripts/setup.sh
```

The setup script:

- syncs the backend Python environment from `backend/pyproject.toml` and `backend/uv.lock`;
- installs frontend dependencies with `npm ci`;
- creates `backend/.env` from `backend/.env.example` if it does not already exist;
- creates `frontend/.env` from `frontend/.env.example` if it does not already exist.

It never overwrites existing `.env` files.

You can also run the same action from VS Code: `Tasks: Run Task` -> `Setup Local Environment`.

### Manual Backend Setup

**Install Python dependencies with uv:**

```bash
uv sync --project backend --frozen --link-mode=copy
```

This creates/syncs `backend/.venv` from `backend/pyproject.toml` and
`backend/uv.lock`. The backend dependency source of truth is:

- `backend/pyproject.toml`: human-maintained dependency ranges and Python version.
- `backend/uv.lock`: committed resolved lock for deterministic installs.

Run backend commands from the repository root through uv:

```bash
uv run --project backend --frozen python -m backend.tests.run_tests
uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`--link-mode=copy` avoids Windows cross-filesystem hardlink/clone issues when the
uv cache and the venv live on different drives.

**Create your `.env` file:**

```bash
# Windows
copy backend\.env.example backend\.env

# macOS / Linux
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in the keys you want to use:

```env
# Add one LLM provider credential if you want real hosted synthesis.
# Local/OpenAI-compatible routes can be configured with the provider variables below.
# Leave blank to run in no-key / mock mode.
GEMINI_API_KEY=your_key_here

# Only needed for the Live Feeds scenario
FINNHUB_API_KEY=your_key_here
CURRENTS_API_KEY=your_key_here
```

### Manual Frontend Setup

```bash
cd frontend
npm install
cd ..
```

Optional frontend env overrides live in `frontend/.env`:

```bash
cd frontend
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Local development normally uses relative `/api` calls and the Vite dev-server proxy.
Use `VITE_API_PROXY_TARGET` to change the local proxy backend. Use
`VITE_API_BASE_URL` only when a built frontend is served from a different origin than
the backend API.

---

## Running the Application

The canonical way to run the app is from a terminal at the **repository root** using the isolated Python environment in `backend/.venv`. VS Code launch configs are convenience wrappers around these commands; they are not required.

You need **two terminals** open from the repository root.

**Terminal 1 — Backend:**

```bash
uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The backend starts at `http://localhost:8000`.  
Arize Phoenix tracing dashboard starts at `http://localhost:6006`.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open your browser to `http://localhost:5173`.

> The Vite dev server proxies all `/api/*` requests to `http://localhost:8000`, so both processes must be running.

**Without activating the venv**, use the interpreter directly:

```powershell
uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
# macOS / Linux
uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

---

## Running with VS Code

The `.vscode/launch.json` includes pre-configured debug/run configurations:

| Configuration | What it does |
|---|---|
| `Backend: FastAPI Server` | Starts Uvicorn with the FastAPI app |
| `Frontend: Vite React Server` | Runs `npm run dev` in `frontend/` |
| `Tracing: Arize Phoenix Server` | Starts the Phoenix collector separately |
| `Backend: Run Unit Tests` | Runs `backend/tests/run_tests.py` |
| **`Full Application (Backend + Frontend + Tracing)`** | Launches all three servers at once |

**To start everything:**
1. Open the **Run and Debug** panel (`Ctrl+Shift+D` / `Cmd+Shift+D`).
2. Select **`Full Application (Backend + Frontend + Tracing)`** from the dropdown.
3. Click the green play button.

**Install dependencies first (one-time):**
- Open the Command Palette (`Ctrl+Shift+P`) → `Tasks: Run Task`.
- Run `Install Backend Requirements` then `Install Frontend Dependencies`.

---

## Running Tests

The test suite verifies the three LangGraph workflows end-to-end, plus the implemented guardrail paths: direct routing, duplicate suppression, cross-impact graph traversal, prompt-injection framing, judge pass, judge-regeneration, judge-degrade, and judge-error degradation.

```bash
uv run --project backend --frozen python -m backend.tests.run_tests
```

Or via the VS Code launch config `Backend: Run Unit Tests`.

Frontend interaction tests run with Vitest and Testing Library:

```bash
cd frontend
npm run test
```

**What the tests cover:**

| Test | Scenario | Validates |
|------|----------|-----------|
| `test_iteration_1_direct_news` | `direct_news`, Iteration 1 | AAPL and MSFT are directly routed; syntheses are generated |
| `test_iteration_2_ledger_duplicates` | `duplicate_news`, Iteration 2 | Exactly 1 duplicate is suppressed for AAPL across 3 articles |
| `test_iteration_3_cross_impact_routing` | `cross_impact`, Iteration 3 | Taiwan earthquake → AAPL/NVDA/TSM; Anthropic launch → MSFT/NVDA; Red Sea → DAL |
| `TestGuardrails` | Guardrail unit scenarios | Prompt-injection wrapper, judge pass, regeneration, double-fail degradation, and judge exception degradation |

Tests run with mocked LLM responses and do not require any API keys.

## Running Eval Sets

Unit tests verify implementation behavior with mocked model calls. Eval sets exercise
the compiled product workflows end-to-end and grade scenario-level expectations. They
also emit Phoenix-friendly spans when Phoenix tracing is enabled, so eval runs can be
inspected beside normal traces.

```bash
# From the repository root, with the venv active
uv run --project backend --frozen python -m backend.evals.runner --eval-set replay_scenarios

# Stateful memory/routing path-set evals
uv run --project backend --frozen python -m backend.evals.runner --eval-set memory_and_routing_paths

# Run locally without initializing Phoenix tracing
uv run --project backend --frozen python -m backend.evals.runner --eval-set replay_scenarios --no-phoenix
```

Eval run JSON is written under `backend/state/eval_runs/`. Eval execution is kept out
of the analyst UI; run it from CI, a terminal, or a Phoenix/Arize-oriented operator
workflow.

## Runtime Settings

The app includes a **Settings** button in the header for non-secret runtime knobs. It
can route each semantic LLM step (`extraction`, `synthesis`, `judge`,
`graph_expansion`) to a configured provider/model. API keys, base URLs, eval
execution, CORS, and deployment-level settings remain outside the analyst UI.

---

## The Three Pipeline Iterations

Select the iteration and scenario from the header dropdowns, then click **Fetch Catalysts**.

### Iteration 1 — Direct News Synthesis
- Uses `backend/iterations/iter1.py`.
- Fetches news articles tagged with watchlist ticker symbols.
- Extracts structured canonical events via LLM (or mock).
- Builds ticker buckets, then dispatches one LangGraph worker branch per ticker for synthesis and output-safety judging when LLM keys are configured.
- No deduplication, no cross-impact routing.

**Recommended scenario:** `Replay Scenario 1: Direct Announcements`  
(AAPL M5 chip announcement + MSFT Copilot cloud earnings)

---

### Iteration 2 — Catalyst Memory Deduplication
- Uses `backend/iterations/iter2.py`.
- Everything from Iteration 1, plus:
- An in-memory vector ledger checks each incoming event against previously seen catalysts using cosine similarity (threshold ≥ 0.75) and Jaccard fact overlap (threshold ≥ 0.60).
- **Duplicate:** same story, no new facts → suppressed, counted.
- **Update:** same story, new facts added → emitted with only the new facts.
- **New:** unrelated story → emitted normally.

**Recommended scenario:** `Replay Scenario 2: Duplicate Articles`  
(Three reports of the same Zhengzhou factory fire; the second is a duplicate, the third is an update with new facts about production halts and 2M delayed iPhones.)

> Use **Reset Cache** between runs to clear the ledger and observe the deduplication behavior from a clean state.

---

### Iteration 3 — Graph Cross-Impact Routing
- Uses `backend/iterations/iter3.py`.
- Everything from Iteration 2, plus:
- The exposure graph is used to expand search keywords by traversing up to 2 hops from watched tickers.
- Untickered external events (no `relatedTickers`) are matched to graph nodes by entity/tag/region/theme and routed to watchlist tickers via graph path traversal (max 3 hops).
- Path score = `event_severity × avg_edge_confidence × path_shortness_bonus`. Routes with score ≥ 0.45 are included.
- Hover over an indirect catalyst card to highlight its path through the Exposure Graph SVG on the right.

**Recommended scenario:** `Replay Scenario 3: Untickered Geopolitical/Tech`  
(Taiwan earthquake → TSMC/AAPL/NVDA; Anthropic model launch → NVDA/MSFT via Frontier AI; Red Sea drone strikes → DAL via Logistics Cost Risk)

---

## Environment Variable Reference

All variables go in `backend/.env`. Copy `backend/.env.example` as a starting point.

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GEMINI_API_KEY` | _(empty)_ | No | Google Gemini API key. Default primary route for extraction, synthesis, and judge. |
| `OPENAI_API_KEY` | _(empty)_ | No | OpenAI API key. Default primary route for graph expansion and fallback route for extraction, synthesis, and judge. |
| `ANTHROPIC_API_KEY` | _(empty)_ | No | Anthropic Claude API key. Activate per step with `*_LLM_PROVIDER=anthropic`. |
| `OPENAI_COMPATIBLE_BASE_URL` / `OPENAI_COMPATIBLE_API_KEY` / `OPENAI_COMPATIBLE_MODEL` | _(empty)_ | No | Hosted OpenAI-compatible chat endpoint. Activate per step with `*_LLM_PROVIDER=openai_compatible`. |
| `LOCAL_LLM_BASE_URL` / `LOCAL_LLM_API_KEY` / `LOCAL_LLM_MODEL` | _(empty)_ | No | Local OpenAI-compatible chat endpoint such as Ollama `/v1`, LM Studio, or vLLM. Activate per step with `*_LLM_PROVIDER=local`. |
| `EXTRACTION_LLM_PROVIDER`, `SYNTHESIS_LLM_PROVIDER`, `JUDGE_LLM_PROVIDER`, `GRAPH_EXPANSION_LLM_PROVIDER` | route defaults | No | Per-step provider override. Supported values: `openai`, `gemini`, `anthropic`, `openai_compatible`, `local`. |
| `EXTRACTION_LLM_MODEL`, `SYNTHESIS_LLM_MODEL`, `JUDGE_LLM_MODEL`, `GRAPH_EXPANSION_LLM_MODEL` | provider defaults | No | Per-step model override. Required for `local` or `openai_compatible` unless the corresponding default model env var is set. |
| `LLM_PROVIDER` | _(empty)_ | No | Optional legacy global provider override. New configs should prefer the per-step route map in `backend/llm.py`. |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | No | Local fastembed model used for catalyst dedup. Runs offline on CPU at $0/call; downloads once (~50 MB). Lexical cosine fallback if it cannot load. |
| `EMBEDDING_CACHE_DIR` | `backend/state/fastembed_cache` | No | Local cache directory for the fastembed ONNX model. Ignored by git. |
| `FINNHUB_API_KEY` | _(empty)_ | No | Finnhub key for live company-specific news. Only used with `scenario_id=live`. |
| `CURRENTS_API_KEY` | _(empty)_ | No | Currents API key for live cross-impact news. Only used with `scenario_id=live` and Iteration 3. |
| `PHOENIX_PORT` | `6006` | No | Port for the Arize Phoenix tracing dashboard. |
| `PHOENIX_PROJECT_NAME` | `cross-impact-catalysts` | No | Project label shown in the Phoenix dashboard. |
| `FRESHNESS_LOOKBACK_MINUTES` | `10` | No | How many minutes back from "now" to accept articles in live mode. Replay scenarios bypass this filter. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | No | Comma-separated browser origins allowed to call the backend API. |
| `BACKEND_HOST` | `127.0.0.1` | No | Uvicorn bind host. Loopback by default. The API has **no auth**, so `0.0.0.0` exposes full pipeline control to the LAN — only set it for a trusted local-network demo. |
| `BACKEND_PORT` | `8000` | No | Uvicorn bind port. |
| `BACKEND_RELOAD` | `0` | No | Set `1` to enable dev autoreload. Reload respawns the worker and wipes the in-memory catalyst ledger and graph-expansion status. |
| `PIPELINE_RUN_TIMEOUT_SECONDS` | `300` | No | Hard ceiling for a single `/api/run`. On timeout the request returns 504 and the ledger is rolled back. Raise it for slow providers. |

### State and seeding

`backend/state/watchlist.json`, `graph.json`, and `run_results.json` are **mutable runtime
state and are git-ignored**. On first boot the app self-seeds from `backend/seed_data.py`
(`EXPOSURE_GRAPH`) and the `DEFAULT_WATCHLIST` (AAPL, MSFT, NVDA, TSM, DAL), so all three
iterations work immediately on a clean clone — no committed state required.

> If these files were tracked in an earlier checkout, untrack them once so the ignore rule
> takes effect (this keeps the files on disk):
> ```bash
> git rm --cached backend/state/graph.json backend/state/run_results.json backend/state/watchlist.json
> ```

To prewarm or verify the local embedding engine before a demo:

```bash
uv run --project backend --frozen python -m backend.scripts.prewarm_embeddings
```

If the model is not cached yet, FastEmbed may download it on first use. If loading
fails, the app falls back to deterministic lexical matching and reports that fallback
through `/api/memory-status`.

---

## Repository Structure

```
problem-first-AI-capstone-team13/
├── backend/
│   ├── main.py               # FastAPI app factory, CORS, lifespan startup, router registration
│   ├── core/                 # Cross-cutting infrastructure
│   │   ├── config.py         # Env vars and Phoenix init
│   │   ├── llm.py            # Provider registry and per-step LLM route resolution
│   │   └── _win_mimetypes.py # Windows MIME-type compatibility shim
│   ├── api/                  # API schemas and route modules
│   │   └── routes/           # Watchlist, graph, ledger, settings, pipeline, status endpoints
│   ├── services/             # App state, pipeline orchestration, runtime settings
│   ├── storage/              # JSON file persistence helpers
│   ├── evals/                # Eval runner and eval-set definitions
│   ├── tests/                # Backend unit/integration-style tests (one module per suite)
│   ├── scripts/              # Manual utilities and local server helpers
│   │   └── prewarm_embeddings.py # Local embedding model check/prewarm helper
│   ├── ingestion/            # News ingestion domain
│   │   ├── news.py           # Finnhub/Currents API clients + scenario replay
│   │   └── scenarios.py      # Replay scenario article datasets
│   ├── memory/               # Catalyst memory domain
│   │   └── ledger.py         # In-memory catalyst ledger + local embedding/lexical dedup engine
│   ├── graph/                # Exposure graph domain
│   │   ├── graph.py          # Exposure graph state + path traversal + scoring
│   │   ├── expansion.py      # LLM-driven exposure-graph expansion (runs on ticker-add)
│   │   └── seed.py           # Seeded starter exposure graph (default watchlist)
│   ├── iterations/
│   │   ├── __init__.py       # Iteration selector/cacher for compiled LangGraph apps
│   │   ├── contracts.py      # LangGraph state and structured-output schemas
│   │   ├── extraction_focus.py # Extraction focus and ticker-alias context helpers
│   │   ├── fetching.py       # Shared fetch/filter node
│   │   ├── extraction.py     # Canonical event extraction node
│   │   ├── routing_nodes.py  # Candidate routing node
│   │   ├── memory_nodes.py   # Catalyst assignment and ledger dedup nodes
│   │   ├── synthesis.py      # Synthesis worker + fan-in (with synthesis_buckets/scoring/postprocess)
│   │   ├── guardrails.py     # Safety judge and compliance gate
│   │   ├── utils.py          # Small shared iteration helpers
│   │   ├── mock_data.py      # Mock extraction fixtures for no-key mode
│   │   ├── prompts.py        # Extraction, synthesis, and judge prompt templates
│   │   ├── common.py         # Compatibility exports for iteration wiring
│   │   ├── iter1.py          # Direct-news workflow
│   │   ├── iter2.py          # Direct-news + catalyst memory workflow
│   │   └── iter3.py          # Cross-impact workflow with graph expansion inputs
│   ├── state/                # Persisted state (watchlist.json, graph.json) — git-ignored, self-seeds on first boot
│   ├── pyproject.toml        # Backend Python dependency ranges and Python version
│   ├── uv.lock               # Reproducible backend dependency lock used by CI
│   ├── .env.example          # Environment variable template
│   └── .venv/                # Local Python virtual environment (not committed)
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Dashboard orchestration and page state
│   │   ├── api/              # Frontend API client
│   │   ├── components/       # Graph view, settings modal, status popover, ticker modal
│   │   ├── test/             # Vitest/Testing Library setup
│   │   ├── types.ts          # Shared frontend types and defaults
│   │   ├── main.tsx          # React DOM mount point
│   │   └── index.css         # Dark-theme CSS variables and component styles
│   ├── index.html
│   ├── .env.example          # Optional frontend env overrides
│   ├── package.json
│   └── vite.config.ts        # Vite config — dev server port 5173, /api proxy to 8000
├── .vscode/
│   ├── launch.json           # Debug/run configurations
│   └── tasks.json            # Install dependency tasks
├── research/
│   └── codebase-research.md  # Full codebase research document
├── README.md
└── implementation_plan.md
```

---

## Troubleshooting

### The backend starts but synthesis output says "LLM unavailable"
The configured model route has no usable provider credentials, or the provider is exhausted/rate-limited. Check `backend/.env` and `/api/memory-status`; the response includes `llmSteps`, `llmProviders`, and the active local embedding engine. The app will still run and use mock synthesis when no synthesis LLM is configured.

### PowerShell blocks the venv activation script
Run this once to allow local scripts:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### `uv sync` reports access denied for a `.pyd` file on Windows
Stop any running backend, Phoenix, or Python processes that are using `backend/.venv`,
then rerun:
```powershell
uv sync --project backend --frozen --link-mode=copy
```
This can happen when converting an older pip-managed venv to the uv-locked backend
environment and Windows keeps a compiled extension loaded.

### `ModuleNotFoundError: No module named 'backend'`
Run the backend as a module from the **repository root**, not from inside the `backend/` directory:
```bash
# Correct — from the repo root
uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Wrong
cd backend && python main.py
```

### Arize Phoenix dashboard shows no traces
Phoenix must be running as a separate collector process for the dashboard at `http://localhost:6006` to display data. Use the `Full Application (Backend + Frontend + Tracing)` VS Code compound config, or start it manually:
```bash
uv run --project backend --frozen python -m phoenix.server.main serve
```
The backend instruments LangGraph via OpenTelemetry on startup and sends traces to `localhost:4317`.

### Frontend shows "Pipeline execution error"
Check the backend terminal for the Python traceback. Common causes:
- Backend is not running (`http://localhost:8000` unreachable).
- An LLM API key is set but invalid or rate-limited — the pipeline sets `llm_failed=True` and rolls back the ledger.

### Live mode returns 0 articles
- The freshness filter only accepts articles published within the last `FRESHNESS_LOOKBACK_MINUTES` (default 10) minutes. Live news APIs may return articles older than this window.
- Verify your `FINNHUB_API_KEY` and `CURRENTS_API_KEY` are set correctly. Check the backend terminal for API error messages.

### Watchlist or exposure graph state
The watchlist and the exposure graph are persisted to versioned JSON files in `backend/state/` (`watchlist.json` and `graph.json`) and reloaded on startup, so they survive backend restarts. Legacy unwrapped state files still load. The catalyst ledger is **not** persisted — it lives in memory only, expires after 1 day, and can be cleared from the UI (**Reset Cache**) or via `POST /api/ledger/clear`. To start the graph from a clean curated seed, use the graph **Rebuild (reset)** action (`POST /api/graph/rebuild` with `reset=true`), which restores the seed and re-expands every watchlist ticker.
