from fastapi import APIRouter

from backend.api.schemas import RunRequest
from backend.services.app_state import app_state
from backend.services.pipeline import execute_pipeline_run
from backend.storage.persistence import save_run_results


router = APIRouter(prefix="/api/run", tags=["pipeline"])


@router.post("")
def trigger_pipeline(req: RunRequest):
    """Trigger the LangGraph pipeline run for the specified iteration and scenario."""
    return execute_pipeline_run(req, app_state.watchlist, app_state.run_results, save_run_results)
