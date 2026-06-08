import mimetypes
try:
    mimetypes.init(files=[])
except Exception:
    pass

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")

from backend.iterations import get_workflow
from backend.ingestion.scenarios import SCENARIOS

def main():
    print("Building workflow graph...")
    workflow = get_workflow(3)

    initial_state = {
        "iteration": 3,
        "watchlist": ["AAPL", "MSFT", "NVDA", "TSM", "DAL"],
        "scenario_id": "cross_impact",
        "simulated_now": "2026-05-28T17:25:00Z",
        "articles": [],
        "canonical_events": [],
        "routed_candidates": [],
        "ticker_buckets": {},
        "ticker_syntheses": {},
        "duplicate_counts": {},
        "ingestion_metadata": {}
    }
    
    print("Invoking workflow...")
    final_state = workflow.invoke(initial_state)
    
    print("\n--- CANONICAL EVENTS EXTRACTED ---")
    for event in final_state.get("canonical_events", []):
        print(f"\nEvent ID: {event.get('eventId')}")
        print(f"Summary: {event.get('eventSummary')}")
        print(f"Entities: {event.get('entities')}")
        print(f"Tags: {event.get('eventTags')}")
        print(f"Regions: {event.get('regions')}")
        print(f"Themes: {event.get('technologyThemes')}")
        
    print("\n--- ROUTED CANDIDATES ---")
    for cand in final_state.get("routed_candidates", []):
        if "evt_currents_cross_002" in cand.get("eventId"):
            print(f"\nCandidate for: {cand.get('ticker')}")
            print(f"Relationship: {cand.get('relationshipType')}")
            print(f"Path: {cand.get('impactPath')}")
            print(f"Confidence: {cand.get('pathConfidence')}")
            print(f"Reason: {cand.get('reasonForRouting')}")

if __name__ == "__main__":
    main()
