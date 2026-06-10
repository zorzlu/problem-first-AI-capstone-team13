"""Pipeline execution service.

The FastAPI layer should validate requests and expose endpoints. The details of
LangGraph invocation, ledger rollback, response shaping, and Phoenix span metadata
belong here so `main.py` stays readable.
"""
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, List

from fastapi import HTTPException

from backend.core.config import PIPELINE_RUN_TIMEOUT_SECONDS
from backend.core.logging import get_logger
from backend.iterations import get_workflow
from backend.memory import restore_ledger_store, snapshot_ledger_store
from backend.api.schemas import RunRequest

logger = get_logger(__name__)


RunResultsStore = Dict[int, Dict[str, Any]]
SaveRunResults = Callable[[RunResultsStore], None]

# Serializes pipeline runs within this process. The ledger snapshot/restore and the
# run_results update are not individually atomic, so two overlapping runs could roll back
# each other's ledger writes or interleave the results write. FastAPI executes the sync
# /api/run handler in a threadpool, so this is reachable with concurrent callers. One
# local Uvicorn process only — multi-worker deployments would need an external store.
runs_lock = RLock()


def _datetime_now() -> datetime:
    return datetime.now(timezone.utc)


def _initial_state(req: RunRequest, watchlist: List[str]) -> Dict[str, Any]:
    return {
        "iteration": req.iteration,
        "watchlist": watchlist,
        "scenario_id": req.scenario_id,
        "simulated_now": req.simulated_now,
        "articles": [],
        "canonical_events": [],
        "routed_candidates": [],
        "ticker_buckets": {},
        "ticker_syntheses": {},
        "duplicate_counts": {},
        "ingestion_metadata": {},
        "llm_failed": False,
    }


def _response_from_state(req: RunRequest, final_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "runId": f"run_{req.scenario_id}_{int(_datetime_now().timestamp())}",
        "iteration": final_state["iteration"],
        "watchlist": final_state["watchlist"],
        "articlesCount": len(final_state.get("articles", [])),
        "eventsCount": len(final_state.get("canonical_events", [])),
        "routedCount": len(final_state.get("routed_candidates", [])),
        "duplicateCounts": final_state.get("duplicate_counts", {}),
        "tickerSyntheses": final_state.get("ticker_syntheses", {}),
        "llmFailed": final_state.get("llm_failed", False),
        "rawArticles": final_state.get("articles", []),
        "canonicalEvents": final_state.get("canonical_events", []),
        "routedCandidates": final_state.get("routed_candidates", []),
        "tickerBuckets": final_state.get("ticker_buckets", {}),
    }


def _span_name(iteration: int) -> str:
    if iteration == 1:
        return "Iteration 1: Naive News Briefing"
    if iteration == 2:
        return "Iteration 2: News Briefing with Memory"
    return "Iteration 3: Cross-Impact Briefing"


def _trace_metadata():
    try:
        from opentelemetry import trace as otel_trace

        tracer = otel_trace.get_tracer("cross-impact-catalysts")
        try:
            from openinference.semconv.trace import SpanAttributes

            return (
                tracer,
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                SpanAttributes.INPUT_VALUE,
                SpanAttributes.OUTPUT_VALUE,
            )
        except ImportError:
            return tracer, "openinference.span.kind", "input.value", "output.value"
    except Exception:
        return None, "", "", ""


def _invoke_with_timeout(iteration: int, initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the compiled workflow with a hard wall-clock ceiling.

    A hung or very slow provider call must not park the request indefinitely. We run the
    blocking ``.invoke`` in a single-worker executor and wait at most
    ``PIPELINE_RUN_TIMEOUT_SECONDS``. On timeout the caller frees the request (504) and
    rolls back the ledger.

    Honest limitation: Python cannot force-kill the worker thread, so the orphaned run
    keeps executing to completion in the background and is simply ignored. This keeps the
    API responsive without a cooperative cancel token threaded through every node, which
    would be a much larger change.

    Note: we deliberately do NOT use ``with ThreadPoolExecutor(...)`` — its ``__exit__``
    calls ``shutdown(wait=True)`` and would block until the runaway worker finishes,
    re-introducing the very hang we are guarding against. We shut down with ``wait=False``
    so the request is freed at the timeout.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline-run")
    future = executor.submit(get_workflow(iteration).invoke, initial_state)
    try:
        return future.result(timeout=PIPELINE_RUN_TIMEOUT_SECONDS)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def execute_pipeline_run(
    req: RunRequest,
    watchlist: List[str],
    run_results: RunResultsStore,
    save_run_results: SaveRunResults,
) -> Dict[str, Any]:
    if req.iteration not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Iteration must be 1, 2, or 3.")

    # Hold runs_lock for the whole run so the ledger snapshot/restore and the run_results
    # write are observed atomically with respect to any other concurrent /api/run.
    runs_lock.acquire()
    try:
        return _execute_locked_run(req, watchlist, run_results, save_run_results)
    finally:
        runs_lock.release()


def _execute_locked_run(
    req: RunRequest,
    watchlist: List[str],
    run_results: RunResultsStore,
    save_run_results: SaveRunResults,
) -> Dict[str, Any]:
    initial_state = _initial_state(req, watchlist)
    ledger_snapshot = snapshot_ledger_store()

    def run_with_ledger() -> Dict[str, Any]:
        try:
            logger.info("Executing LangGraph workflow for Iteration %s (Scenario: %s)...", req.iteration, req.scenario_id)
            final_state = _invoke_with_timeout(req.iteration, initial_state)

            if final_state.get("llm_failed", False):
                logger.error("Pipeline had LLM failure - rolling back ledger to pre-run snapshot.")
                restore_ledger_store(ledger_snapshot)

            response_data = _response_from_state(req, final_state)
            run_results[req.iteration] = response_data
            save_run_results(run_results)
            return response_data
        except FuturesTimeoutError:
            logger.error(
                "Pipeline run exceeded %ss - rolling back ledger and "
                "freeing the request (background thread is abandoned).",
                PIPELINE_RUN_TIMEOUT_SECONDS,
            )
            restore_ledger_store(ledger_snapshot)
            raise HTTPException(
                status_code=504,
                detail=(
                    f"Pipeline timed out after {PIPELINE_RUN_TIMEOUT_SECONDS}s. "
                    "Increase PIPELINE_RUN_TIMEOUT_SECONDS or retry."
                ),
            )
        except Exception as e:
            logger.exception("Error running pipeline: %s - rolling back ledger.", e)
            restore_ledger_store(ledger_snapshot)
            raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")

    tracer, span_kind_attr, input_attr, output_attr = _trace_metadata()
    if not tracer:
        return run_with_ledger()

    with tracer.start_as_current_span(_span_name(req.iteration)) as span:
        span.set_attribute("iteration", req.iteration)
        span.set_attribute("scenario_id", req.scenario_id)
        span.set_attribute(span_kind_attr, "CHAIN")
        span.set_attribute(input_attr, json.dumps({
            "iteration": req.iteration,
            "scenario_id": req.scenario_id,
            "simulated_now": req.simulated_now,
            "watchlist": watchlist,
        }))

        res = run_with_ledger()

        span.set_attribute("articles_count", res.get("articlesCount", 0))
        span.set_attribute("events_count", res.get("eventsCount", 0))
        span.set_attribute("routed_count", res.get("routedCount", 0))
        span.set_attribute(output_attr, json.dumps({
            "runId": res.get("runId"),
            "articlesCount": res.get("articlesCount"),
            "eventsCount": res.get("eventsCount"),
            "routedCount": res.get("routedCount"),
            "llmFailed": res.get("llmFailed"),
        }))
        return res
