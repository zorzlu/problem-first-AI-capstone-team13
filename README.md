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

Each run executes one of three compiled LangGraph workflows in `backend/iterations/`, all built from shared helpers in `backend/iterations/common.py`:

```text
Iteration 1
Fetch & Filter News
        ↓
Canonical Event Extraction  (LLM: gpt-4.1-nano / gemini-2.5-flash)
        ↓
Route Events to Tickers     (direct tag routing)
        ↓
Assign Catalyst IDs         (no ledger in Iteration 1)
        ↓
Per-Ticker Synthesis        (LLM: gpt-4o-mini / gemini-2.5-flash)
        ↓
Output Safety Judge         (LLM: grounding + no-advice + path check)
        ↓
Compliance Gate             (regex scrub of buy/sell language)

Iteration 2
Fetch & Filter News
        ↓
Canonical Event Extraction  (LLM: gpt-4.1-nano / gemini-2.5-flash)
        ↓
Route Events to Tickers     (direct tag routing)
        ↓
Ledger Memory Check         (local embeddings / lexical fallback)
        ↓
Per-Ticker Synthesis        (LLM: gpt-4o-mini / gemini-2.5-flash)
        ↓
Output Safety Judge         (LLM: grounding + no-advice + path check)
        ↓
Compliance Gate             (regex scrub of buy/sell language)

Iteration 3
Fetch & Filter News + Graph Query Expansion
        ↓
Canonical Event Extraction  (LLM: gpt-4.1-nano / gemini-2.5-flash)
        ↓
Route Events to Tickers     (direct tag + exposure graph traversal)
        ↓
Ledger Memory Check         (local embeddings / lexical fallback)
        ↓
Per-Ticker Synthesis        (LLM: gpt-4o-mini / gemini-2.5-flash)
        ↓
Output Safety Judge         (LLM: grounding + no-advice + path check)
        ↓
Compliance Gate             (regex scrub of buy/sell language)
```

**No API keys?** The app runs in no-key mode using pre-baked mock events and rules-based synthesis. All three replay scenarios work fully offline; non-empty mock syntheses mark the LLM judge as skipped in `guardrailMetadata`.

### Output guardrails

Every non-empty LLM synthesis is checked by a structured output safety judge before the regex compliance gate. The judge verifies that claims are grounded in the ticker bucket, that the briefing contains no trading advice/action language, and that indirect catalyst explanations stay inside the routed `impactPath` and `reasonForRouting`. If the judge fails, the backend regenerates that ticker's synthesis once with the defects named; if the regenerated output still fails or the judge errors, the briefing is degraded to **Briefing suppressed pending verification** with no main catalysts. The API response includes `guardrailMetadata`, and the ticker detail view shows a badge such as `Verified`, `Regenerated after guardrail`, or `Suppressed pending verification`.

### Exposure-graph expansion (separate from the run pipeline)

When you **add a ticker** to the watchlist, a background task maps that ticker's causal exposure (suppliers, customers, competitors, partners, regions, technology themes, commodities, macro/shipping risks) and merges the resulting nodes and edges into the exposure graph. It pulls known stock peers from Finnhub, then calls the LLM (`get_llm` — `gpt-4o-mini` / `gemini-2.5-flash`) to generate the surrounding graph. Exposure and sensitivity edges are directional from the cause/source node to the affected company or ticker. This runs **once per ticker on add** (not on every pipeline run), and can be re-triggered manually per ticker or rebuilt for the whole watchlist. With no LLM keys, only the bare ticker node is added. Per-ticker progress (`pending → running → done/skipped/failed`) is shown in the UI.

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Python | 3.11 | Earlier versions are untested |
| Node.js | 18.x | 20.x or later also works |
| npm | 9.x | Comes with Node.js |

Check your versions:

```bash
python --version
node --version
npm --version
```

---

## API Keys

The application uses up to four external API keys. **All are optional** — see the table below for what each one unlocks.

### Which keys do you actually need?

| Scenario | Keys required |
|----------|--------------|
| Run the three built-in replay scenarios with real LLM synthesis | One of: `GEMINI_API_KEY` **or** `OPENAI_API_KEY` |
| Run the three replay scenarios without any LLM (rules-based mock output) | None |
| Pull live company news from Finnhub | `FINNHUB_API_KEY` |
| Pull live cross-impact / geopolitical news from Currents | `CURRENTS_API_KEY` |

---

### `GEMINI_API_KEY` — Google Gemini (default LLM)

Used for: canonical event extraction (`gemini-2.5-flash`), per-ticker synthesis (`gemini-2.5-flash`), graph expansion, and the output safety judge. The deduplication ledger does **not** use this key — it embeds locally (see [Catalyst dedup embeddings](#catalyst-dedup-embeddings-local-no-api-key) below).

**How to get it:**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with a Google account.
3. Click **Create API key** and copy the value.

The free tier is sufficient for all replay scenarios.

---

### `OPENAI_API_KEY` — OpenAI (alternative LLM)

Used for: canonical event extraction (`gpt-4.1-nano`), per-ticker synthesis (`gpt-4o-mini`), graph expansion, and the output safety judge. The deduplication ledger does **not** use this key — it embeds locally (see [Catalyst dedup embeddings](#catalyst-dedup-embeddings-local-no-api-key) below).

Set `LLM_PROVIDER=openai` in your `.env` to activate this path. If both keys are set, `LLM_PROVIDER` controls which one is used. If `GEMINI_API_KEY` is absent but `OPENAI_API_KEY` is present, the app automatically falls back to OpenAI regardless of `LLM_PROVIDER`.

**How to get it:**
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
2. Sign in and click **Create new secret key**.
3. Copy the value — it is only shown once.

You need a funded account (pay-as-you-go). Running all three replay scenarios costs well under $0.10.

---

### Catalyst dedup embeddings (local, no API key)

The catalyst-memory ledger decides whether a fresh event is a duplicate, an update, or a new story. This is done with a **local embedding model** — there is no embedding API key and no per-call cost.

- **Primary:** [`fastembed`](https://github.com/qdrant/fastembed) running `BAAI/bge-small-en-v1.5` (384 dimensions, ONNX, CPU). The model downloads once (~50 MB) on first run, then runs fully offline. Override with the `EMBEDDING_MODEL` env var.
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

### Step 2 — Set up the Python backend

**Create and activate a virtual environment:**

```bash
# Create
python -m venv backend/.venv

# Activate — Windows PowerShell
.\backend\.venv\Scripts\Activate.ps1

# Activate — Windows CMD
backend\.venv\Scripts\activate.bat

# Activate — macOS / Linux
source backend/.venv/bin/activate
```

**Install Python dependencies:**

```bash
pip install -r backend/requirements.txt
```

**Create your `.env` file:**

```bash
# Windows
copy backend\.env.example backend\.env

# macOS / Linux
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in the keys you want to use:

```env
# At minimum, add one LLM key if you want real synthesis.
# Leave blank to run in no-key / mock mode.
GEMINI_API_KEY=your_key_here

# Only needed for the Live Feeds scenario
FINNHUB_API_KEY=your_key_here
CURRENTS_API_KEY=your_key_here
```

### Step 3 — Set up the React frontend

```bash
cd frontend
npm install
cd ..
```

---

## Running the Application

You need **two terminals** open from the repository root.

**Terminal 1 — Backend:**

```bash
# Activate the venv first if not already active (see Step 2 above)
python -m backend.main
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

---

## Running with VS Code

The `.vscode/launch.json` includes pre-configured debug/run configurations:

| Configuration | What it does |
|---|---|
| `Backend: FastAPI Server` | Starts Uvicorn with the FastAPI app |
| `Frontend: Vite React Server` | Runs `npm run dev` in `frontend/` |
| `Tracing: Arize Phoenix Server` | Starts the Phoenix collector separately |
| `Backend: Run Unit Tests` | Runs `backend/run_tests.py` |
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
# From the repository root, with the venv active
python -m unittest backend/run_tests.py
```

Or via the VS Code launch config `Backend: Run Unit Tests`.

**What the tests cover:**

| Test | Scenario | Validates |
|------|----------|-----------|
| `test_iteration_1_direct_news` | `direct_news`, Iteration 1 | AAPL and MSFT are directly routed; syntheses are generated |
| `test_iteration_2_ledger_duplicates` | `duplicate_news`, Iteration 2 | Exactly 1 duplicate is suppressed for AAPL across 3 articles |
| `test_iteration_3_cross_impact_routing` | `cross_impact`, Iteration 3 | Taiwan earthquake → AAPL/NVDA/TSM; Anthropic launch → MSFT/NVDA; Red Sea → DAL |
| `TestGuardrails` | Guardrail unit scenarios | Prompt-injection wrapper, judge pass, regeneration, double-fail degradation, and judge exception degradation |

Tests run with mocked LLM responses and do not require any API keys.

---

## The Three Pipeline Iterations

Select the iteration and scenario from the header dropdowns, then click **Fetch Catalysts**.

### Iteration 1 — Direct News Synthesis
- Uses `backend/iterations/iter1.py`.
- Fetches news articles tagged with watchlist ticker symbols.
- Extracts structured canonical events via LLM (or mock).
- Synthesizes a briefing for each ticker that has direct news, then verifies it with the output safety judge when LLM keys are configured.
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
| `GEMINI_API_KEY` | _(empty)_ | No | Google Gemini API key. Used for LLM extraction and synthesis (not embeddings — dedup embeds locally). Either this or `OPENAI_API_KEY` needed for real LLM output. |
| `OPENAI_API_KEY` | _(empty)_ | No | OpenAI API key. Alternative to Gemini. Set `LLM_PROVIDER=openai` to activate. |
| `LLM_PROVIDER` | `gemini` | No | `"gemini"` or `"openai"`. Selects which provider's models are used when both keys are set. |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | No | Local fastembed model used for catalyst dedup. Runs offline on CPU at $0/call; downloads once (~50 MB). Lexical cosine fallback if it cannot load. |
| `FINNHUB_API_KEY` | _(empty)_ | No | Finnhub key for live company-specific news. Only used with `scenario_id=live`. |
| `CURRENTS_API_KEY` | _(empty)_ | No | Currents API key for live cross-impact news. Only used with `scenario_id=live` and Iteration 3. |
| `PHOENIX_PORT` | `6006` | No | Port for the Arize Phoenix tracing dashboard. |
| `PHOENIX_PROJECT_NAME` | `cross-impact-catalysts` | No | Project label shown in the Phoenix dashboard. |
| `FRESHNESS_LOOKBACK_MINUTES` | `10` | No | How many minutes back from "now" to accept articles in live mode. Replay scenarios bypass this filter. |

---

## Repository Structure

```
problem-first-AI-capstone-team13/
├── backend/
│   ├── main.py               # FastAPI app — routes and pipeline invocation
│   ├── config.py             # Env vars, LLM factory functions, Phoenix init
│   ├── graph_expansion.py    # LLM-driven exposure-graph expansion (runs on ticker-add)
│   ├── ingestion.py          # Finnhub/Currents API clients + scenario replay
│   ├── routing.py            # Exposure graph state + path traversal + scoring
│   ├── memory.py             # In-memory catalyst ledger + local embedding/lexical dedup engine
│   ├── seed_data.py          # Seeded exposure graph and replay scenario articles
│   ├── persistence.py        # JSON file persistence for watchlist + graph + run results
│   ├── iterations/
│   │   ├── __init__.py       # Iteration selector/cacher for compiled LangGraph apps
│   │   ├── common.py         # Shared schemas, prompts, step helpers, and output safety judge
│   │   ├── iter1.py          # Direct-news workflow
│   │   ├── iter2.py          # Direct-news + catalyst memory workflow
│   │   └── iter3.py          # Cross-impact workflow with graph expansion inputs
│   ├── state/                # Persisted state (watchlist.json, graph.json) — survives restarts
│   ├── run_tests.py          # Unit test suite (3 end-to-end workflow tests)
│   ├── requirements.txt      # Python dependencies (unpinned)
│   ├── .env.example          # Environment variable template
│   └── .venv/                # Local Python virtual environment (not committed)
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # All dashboard logic, state, and rendering
│   │   ├── main.tsx          # React DOM mount point
│   │   └── index.css         # Dark-theme CSS variables and component styles
│   ├── index.html
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
The LLM API key is either missing or exhausted. Check that `backend/.env` exists and contains a valid `GEMINI_API_KEY` or `OPENAI_API_KEY`. The app will still run and use mock synthesis in this case — the `Embeddings Memory Engine` panel in the UI will show which provider is active.

### PowerShell blocks the venv activation script
Run this once to allow local scripts:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### `ModuleNotFoundError: No module named 'backend'`
Run the backend as a module from the **repository root**, not from inside the `backend/` directory:
```bash
# Correct — from the repo root
python -m backend.main

# Wrong
cd backend && python main.py
```

### Arize Phoenix dashboard shows no traces
Phoenix must be running as a separate collector process for the dashboard at `http://localhost:6006` to display data. Use the `Full Application (Backend + Frontend + Tracing)` VS Code compound config, or start it manually:
```bash
python -m phoenix.server.main serve
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
The watchlist and the exposure graph are persisted to JSON files in `backend/state/` (`watchlist.json` and `graph.json`) and reloaded on startup, so they survive backend restarts. The catalyst ledger is **not** persisted — it lives in memory only, expires after 1 day, and can be cleared from the UI (**Reset Cache**) or via `POST /api/ledger/clear`. To start the graph from a clean curated seed, use the graph **Rebuild (reset)** action (`POST /api/graph/rebuild` with `reset=true`), which restores the seed and re-expands every watchlist ticker.
