from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import graph, ledger, pipeline, results, settings, status, watchlist
from backend.core.config import BACKEND_HOST, BACKEND_PORT, BACKEND_RELOAD, CORS_ORIGINS
from backend.services.app_state import hydrate_app_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load persisted state and initialize tracing. (Replaces the deprecated
    # @app.on_event("startup") hook.)
    hydrate_app_state()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Intraday Cross-Impact Catalyst Briefings API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error": {
                    "code": "http_error",
                    "message": str(exc.detail),
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                },
            },
        )

    app.include_router(watchlist.router)
    app.include_router(graph.router)
    app.include_router(ledger.router)
    app.include_router(results.router)
    app.include_router(settings.router)
    app.include_router(pipeline.router)
    app.include_router(status.router)

    return app


app = create_app()


if __name__ == "__main__":
    # Defaults to loopback with reload off; override via BACKEND_HOST / BACKEND_PORT /
    # BACKEND_RELOAD. See backend/config.py and .env.example for the security note.
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=BACKEND_RELOAD)
