import mimetypes
try:
    mimetypes.init(files=[])
except Exception:
    pass

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.config import init_phoenix, PHOENIX_PORT
from backend.routing import get_graph, add_graph_node, add_graph_edge, set_graph, reset_graph
from backend.memory import get_ledger, clear_ledger
import backend.memory as _memory_module
from backend.llm import model_statuses, provider_statuses
from backend.iterations import get_workflow
from backend.persistence import load_watchlist, save_watchlist, load_graph, save_graph, load_run_results, save_run_results
from backend.graph_expansion import (
    process_ticker_expansion,
    mark_pending,
    get_expansion_status,
)

app = FastAPI(title="Intraday Cross-Impact Catalyst Briefings API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For localhost demo, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Watchlist configuration
_watchlist = ["AAPL", "MSFT", "NVDA", "TSM", "DAL"]
_run_results: Dict[int, Dict[str, Any]] = {}

class RunRequest(BaseModel):
    iteration: int # 1, 2, or 3
    scenario_id: str # "live", "direct_news", "duplicate_news", "cross_impact"
    simulated_now: Optional[str] = "2026-05-28T17:25:00Z"

class WatchlistRequest(BaseModel):
    tickers: List[str]

class ExpandRequest(BaseModel):
    ticker: str
    force: bool = True  # manual triggers default to re-running even if the node exists

class RebuildRequest(BaseModel):
    reset: bool = True  # True = reset to curated seed first; False = additive refresh on top

@app.on_event("startup")
def startup_event():
    global _watchlist, _run_results
    init_phoenix()
    _watchlist = load_watchlist(default=_watchlist)
    set_graph(load_graph(default=get_graph()))
    save_graph(get_graph())
    # Load run results and convert string keys from JSON back to integers
    loaded = load_run_results()
    _run_results = {}
    for k, v in loaded.items():
        try:
            _run_results[int(k)] = v
        except Exception:
            pass

@app.get("/api/watchlist")
def get_watchlist():
    return {"tickers": _watchlist}

@app.post("/api/watchlist")
def update_watchlist(req: WatchlistRequest, background_tasks: BackgroundTasks):
    global _watchlist
    previous_watchlist = list(_watchlist)

    # Newly added tickers trigger a ONE-TIME exposure-graph expansion. The add itself
    # is NOT blocked by the LLM: we commit the watchlist immediately and run expansion
    # as a background task. Removals are left in the graph so knowledge accumulates.
    new_tickers = [t for t in req.tickers if t not in previous_watchlist]

    _watchlist = req.tickers
    save_watchlist(_watchlist)

    # Queue expansion for each new ticker. mark_pending() flips the status before the
    # task runs so the UI shows "pending" the instant the add returns.
    for ticker in new_tickers:
        mark_pending(ticker)
        background_tasks.add_task(process_ticker_expansion, ticker, False)

    return {"tickers": _watchlist, "expansionStatus": get_expansion_status()}

@app.get("/api/graph/status")
def graph_expansion_status():
    """Per-ticker exposure-graph expansion status (pending/running/done/skipped/failed)."""
    return {"status": get_expansion_status()}

@app.post("/api/graph/expand")
def trigger_graph_expansion(req: ExpandRequest, background_tasks: BackgroundTasks):
    """Manually (re-)run the exposure-graph expansion for a ticker, in the background."""
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    mark_pending(ticker)
    background_tasks.add_task(process_ticker_expansion, ticker, req.force)
    return {"status": "scheduled", "ticker": ticker, "expansionStatus": get_expansion_status()}

@app.post("/api/graph/rebuild")
def rebuild_graph_endpoint(req: RebuildRequest, background_tasks: BackgroundTasks):
    """
    Rebuild the exposure graph for the ENTIRE watchlist in the background.
      - reset=True  : restore the curated seed graph (drop accumulated LLM additions), then re-expand every ticker.
      - reset=False : keep the current graph and force a fresh expansion for every ticker on top of it.
    """
    if req.reset:
        reset_graph()
        save_graph(get_graph())
    for ticker in _watchlist:
        mark_pending(ticker)
        background_tasks.add_task(process_ticker_expansion, ticker, True)
    return {
        "status": "scheduled",
        "reset": req.reset,
        "tickers": _watchlist,
        "expansionStatus": get_expansion_status(),
    }

@app.get("/api/graph")
def get_exposure_graph():
    return get_graph()

@app.post("/api/graph/node")
def add_node(node: Dict[str, Any]):
    try:
        add_graph_node(node)
        save_graph(get_graph())
        return {"status": "success", "graph": get_graph()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/graph/edge")
def add_edge(edge: Dict[str, Any]):
    try:
        add_graph_edge(edge)
        save_graph(get_graph())
        return {"status": "success", "graph": get_graph()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/ledger")
def get_active_ledger(iteration: int = 2):
    return get_ledger(iteration)

@app.post("/api/ledger/clear")
def reset_ledger(iteration: Optional[int] = None):
    clear_ledger(iteration)
    return {"status": "success", "message": f"Catalyst Ledger for iteration {iteration if iteration is not None else 'all'} has been cleared."}

@app.get("/api/results")
def get_latest_results():
    """Returns the cached run results for all iterations."""
    return _run_results

@app.post("/api/run")
def trigger_pipeline(req: RunRequest):
    """Triggers the LangGraph pipeline run for the specified iteration and scenario."""
    if req.iteration not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Iteration must be 1, 2, or 3.")
        
    try:
        from opentelemetry import trace as otel_trace
        tracer = otel_trace.get_tracer("cross-impact-catalysts")
        try:
            from openinference.semconv.trace import SpanAttributes
            OPENINFERENCE_SPAN_KIND = SpanAttributes.OPENINFERENCE_SPAN_KIND
            INPUT_VALUE = SpanAttributes.INPUT_VALUE
            OUTPUT_VALUE = SpanAttributes.OUTPUT_VALUE
        except ImportError:
            OPENINFERENCE_SPAN_KIND = "openinference.span.kind"
            INPUT_VALUE = "input.value"
            OUTPUT_VALUE = "output.value"
    except Exception:
        tracer = None

    initial_state = {
        "iteration": req.iteration,
        "watchlist": _watchlist,
        "scenario_id": req.scenario_id,
        "simulated_now": req.simulated_now,
        "articles": [],
        "canonical_events": [],
        "routed_candidates": [],
        "ticker_buckets": {},
        "ticker_syntheses": {},
        "duplicate_counts": {},
        "ingestion_metadata": {},
        "llm_failed": False
    }

    # Snapshot ledger before run so we can roll back if the pipeline fails
    ledger_snapshot = {k: list(v) for k, v in _memory_module._ledger_store.items()}

    def _run_with_ledger():
        try:
            print(f"Executing LangGraph workflow for Iteration {req.iteration} (Scenario: {req.scenario_id})...")
            final_state = get_workflow(req.iteration).invoke(initial_state)

            # If LLM failed, roll back any ledger writes made during this run so
            # re-running won't treat those articles as already-seen duplicates.
            if final_state.get("llm_failed", False):
                print("Pipeline had LLM failure — rolling back ledger to pre-run snapshot.")
                _memory_module._ledger_store.clear()
                _memory_module._ledger_store.update(ledger_snapshot)

            # Clean final state for client consumption
            response_data = {
                "runId": f"run_{req.scenario_id}_{int(datetime_now().timestamp())}",
                "iteration": final_state["iteration"],
                "watchlist": final_state["watchlist"],
                "articlesCount": len(final_state.get("articles", [])),
                "eventsCount": len(final_state.get("canonical_events", [])),
                "routedCount": len(final_state.get("routed_candidates", [])),
                "duplicateCounts": final_state.get("duplicate_counts", {}),
                "tickerSyntheses": final_state.get("ticker_syntheses", {}),
                "llmFailed": final_state.get("llm_failed", False),
                # Debug structures
                "rawArticles": final_state.get("articles", []),
                "canonicalEvents": final_state.get("canonical_events", []),
                "routedCandidates": final_state.get("routed_candidates", []),
                "tickerBuckets": final_state.get("ticker_buckets", {})
            }
            # Cache run result per iteration
            global _run_results
            _run_results[req.iteration] = response_data
            save_run_results(_run_results)
            return response_data
        except Exception as e:
            # Also roll back ledger on unexpected crash
            print(f"Error running pipeline: {e} — rolling back ledger.")
            _memory_module._ledger_store.clear()
            _memory_module._ledger_store.update(ledger_snapshot)
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")

    if tracer:
        import json
        if req.iteration == 1:
            span_name = "Iteration 1: Naive News Briefing"
        elif req.iteration == 2:
            span_name = "Iteration 2: News Briefing with Memory"
        else:
            span_name = "Iteration 3: Cross-Impact Briefing"

        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("iteration", req.iteration)
            span.set_attribute("scenario_id", req.scenario_id)
            span.set_attribute(OPENINFERENCE_SPAN_KIND, "CHAIN")
            
            input_summary = {
                "iteration": req.iteration,
                "scenario_id": req.scenario_id,
                "simulated_now": req.simulated_now,
                "watchlist": _watchlist
            }
            span.set_attribute(INPUT_VALUE, json.dumps(input_summary))

            res = _run_with_ledger()
            
            span.set_attribute("articles_count", res.get("articlesCount", 0))
            span.set_attribute("events_count", res.get("eventsCount", 0))
            span.set_attribute("routed_count", res.get("routedCount", 0))
            
            output_summary = {
                "runId": res.get("runId"),
                "articlesCount": res.get("articlesCount"),
                "eventsCount": res.get("eventsCount"),
                "routedCount": res.get("routedCount"),
                "llmFailed": res.get("llmFailed")
            }
            span.set_attribute(OUTPUT_VALUE, json.dumps(output_summary))
            return res
    else:
        return _run_with_ledger()


@app.get("/api/phoenix-status")
def get_phoenix_status():
    return {
        "running": True,
        "dashboardUrl": f"http://127.0.0.1:{PHOENIX_PORT}",
        "projectName": "cross-impact-catalysts"
    }

@app.get("/api/memory-status")
def get_memory_status():
    """Returns the current status of the catalyst dedup engine and memory module."""
    # The dedup engine runs LOCALLY at $0/call — no remote embedding API.
    # Primary: local fastembed neural embeddings. Fallback: lexical token cosine.
    embedding_active = _memory_module.is_embedding_active()
    if embedding_active:
        dedup_provider = "Local embeddings"
        dedup_model = f"{_memory_module._EMBEDDING_MODEL_NAME} (384d)"
        dedup_method = "neural_cosine"
    else:
        dedup_provider = "Local (lexical fallback)"
        dedup_model = "tf-cosine + jaccard"
        dedup_method = "lexical_cosine"

    llm_steps = model_statuses()
    llm_extraction = llm_steps["extraction"]
    llm_synthesis = llm_steps["synthesis"]
    llm_judge = llm_steps["judge"]
    llm_graph_expansion = llm_steps["graph_expansion"]

    total_entries = sum(len(entries) for entries in _memory_module._ledger_store.values())
    live_entries = []
    for iteration_entries in _memory_module._ledger_store.values():
        live_entries.extend([e for e in iteration_entries if e.get("status") == "live"])
    embedded_entries = [e for e in live_entries if e.get("embedding_vec")]

    return {
        "dedupProvider": dedup_provider,
        "dedupModel": dedup_model,
        "dedupMethod": dedup_method,
        "embeddingProvider": "local_fastembed" if embedding_active else "local_lexical",
        "embeddingRuntime": "local_cpu" if embedding_active else "local_python",
        "embeddingModel": _memory_module._EMBEDDING_MODEL_NAME if embedding_active else "tf-cosine + jaccard",
        "embeddingCacheDir": _memory_module._EMBEDDING_CACHE_DIR,
        "embeddingLocation": "localhost",
        # isFallbackActive=True means the lexical fallback is in use (embedding model unavailable).
        "isFallbackActive": not embedding_active,
        "similarityThreshold": 0.75,
        "jaccardFactThreshold": 0.6,
        "ledgerTotalEntries": total_entries,
        "ledgerLiveEntries": len(live_entries),
        "ledgerEmbeddedEntries": len(embedded_entries),
        "llmExtractionProvider": llm_extraction["provider"],
        "llmExtractionModel": llm_extraction["model"],
        "llmSynthesisProvider": llm_synthesis["provider"],
        "llmSynthesisModel": llm_synthesis["model"],
        "llmJudgeProvider": llm_judge["provider"],
        "llmJudgeModel": llm_judge["model"],
        "llmGraphExpansionProvider": llm_graph_expansion["provider"],
        "llmGraphExpansionModel": llm_graph_expansion["model"],
        "llmSteps": llm_steps,
        "llmProviders": provider_statuses(),
    }

def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
