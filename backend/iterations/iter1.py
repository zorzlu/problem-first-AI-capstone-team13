"""Iteration 1 pipeline: naive direct-news briefings with NO memory.

fetch -> extract(direct focus) -> route(direct only) -> assign new catalysts -> synthesize -> compliance
Every routed candidate is treated as a fresh catalyst; the ledger is never read or written,
so nothing from prior runs bleeds in.
"""
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from backend.iterations.common import (
    WorkflowState,
    EXTRACTION_SYSTEM_PROMPT,
    direct_focus,
    run_fetch_and_filter,
    run_extraction,
    route_events,
    assign_new_catalysts,
    build_ticker_buckets_for_synthesis,
    dispatch_ticker_synthesis,
    synthesize_one_ticker_node,
    collect_ticker_syntheses,
    run_compliance_gate,
)


def fetch_node(state: WorkflowState) -> Dict[str, Any]:
    return run_fetch_and_filter(state, expand=False)


def extract_node(state: WorkflowState) -> Dict[str, Any]:
    focus = direct_focus(state.get("watchlist", []))
    return run_extraction(state, EXTRACTION_SYSTEM_PROMPT, focus)


def route_node(state: WorkflowState) -> Dict[str, Any]:
    return route_events(state, cross_impact=False)


# NOTE: iteration 1 has NO memory. This stage is pure ID assignment — it does not touch
# the catalyst ledger; it only stamps a catalystId on each candidate so synthesis/UI can
# render the cards. The ledger is never read or written in this iteration.
def assign_catalysts_node(state: WorkflowState) -> Dict[str, Any]:
    return assign_new_catalysts(state)


def build_buckets_node(state: WorkflowState) -> Dict[str, Any]:
    return build_ticker_buckets_for_synthesis(state, restore_ledger=False, restore_indirect=False)


def synthesize_ticker_node(state: WorkflowState) -> Dict[str, Any]:
    return synthesize_one_ticker_node(state)


def collect_syntheses_node(state: WorkflowState) -> Dict[str, Any]:
    return collect_ticker_syntheses(state)


def compliance_node(state: WorkflowState) -> Dict[str, Any]:
    return run_compliance_gate(state)


def build_graph():
    wf = StateGraph(WorkflowState)
    wf.add_node("fetch_and_filter", fetch_node)
    wf.add_node("extract_events", extract_node)
    wf.add_node("route_events", route_node)
    wf.add_node("assign_catalysts", assign_catalysts_node)
    wf.add_node("build_ticker_buckets", build_buckets_node)
    wf.add_node("synthesize_one_ticker", synthesize_ticker_node)
    wf.add_node("collect_ticker_syntheses", collect_syntheses_node)
    wf.add_node("compliance_gate", compliance_node)

    wf.set_entry_point("fetch_and_filter")
    wf.add_edge("fetch_and_filter", "extract_events")
    wf.add_edge("extract_events", "route_events")
    wf.add_edge("route_events", "assign_catalysts")
    wf.add_edge("assign_catalysts", "build_ticker_buckets")
    wf.add_conditional_edges("build_ticker_buckets", dispatch_ticker_synthesis)
    wf.add_edge("synthesize_one_ticker", "collect_ticker_syntheses")
    wf.add_edge("collect_ticker_syntheses", "compliance_gate")
    wf.add_edge("compliance_gate", END)
    return wf.compile()
