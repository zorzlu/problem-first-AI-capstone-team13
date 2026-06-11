from fastapi import APIRouter, BackgroundTasks

from backend.api.schemas import WatchlistRequest
from backend.graph.expansion import get_expansion_status, mark_pending, process_ticker_expansion, should_schedule
from backend.services.app_state import app_state
from backend.storage.persistence import save_watchlist


router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist():
    return {"tickers": app_state.watchlist}


@router.post("")
def update_watchlist(req: WatchlistRequest, background_tasks: BackgroundTasks):
    previous_watchlist = list(app_state.watchlist)

    # Newly added tickers trigger a one-time exposure-graph expansion. The add itself
    # is not blocked by the LLM; expansion runs in the background.
    new_tickers = [ticker for ticker in req.tickers if ticker not in previous_watchlist]

    app_state.watchlist = req.tickers
    save_watchlist(app_state.watchlist)

    for ticker in new_tickers:
        if not should_schedule(ticker):
            continue
        mark_pending(ticker)
        background_tasks.add_task(process_ticker_expansion, ticker, False)

    return {"tickers": app_state.watchlist, "expansionStatus": get_expansion_status()}
