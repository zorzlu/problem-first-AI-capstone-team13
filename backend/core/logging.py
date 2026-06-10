"""Backend logging setup.

All app modules log through here instead of print() so output carries levels and
timestamps, respects LOG_LEVEL, and plays nicely with uvicorn's own logging.
CLI tools (backend/scripts) and tests keep printing — their output IS the product.
"""
import logging
import os

_CONFIGURED = False


def configure_logging() -> None:
    """Set up backend logging once at startup (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    # basicConfig attaches a single root StreamHandler; backend.* loggers propagate to it.
    # Uvicorn keeps its own handlers on the "uvicorn" loggers, so lines are not doubled.
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module (pass __name__)."""
    return logging.getLogger(name)
