from fastapi import APIRouter

from backend.services.app_state import app_state


router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("")
def get_latest_results():
    """Return cached run results for all iterations."""
    return app_state.run_results
