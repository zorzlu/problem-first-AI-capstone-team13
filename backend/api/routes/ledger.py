from typing import Optional

from fastapi import APIRouter

from backend.memory import clear_ledger, get_ledger


router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("")
def get_active_ledger(iteration: int = 2):
    return get_ledger(iteration)


@router.post("/clear")
def reset_ledger(iteration: Optional[int] = None):
    clear_ledger(iteration)
    scope = iteration if iteration is not None else "all"
    return {"status": "success", "message": f"Catalyst Ledger for iteration {scope} has been cleared."}
