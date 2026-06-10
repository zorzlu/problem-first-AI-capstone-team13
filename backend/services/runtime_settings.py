"""Persisted non-secret runtime settings.

API keys stay in environment variables. This module stores only behavior knobs that
are safe to expose in the local UI, such as which configured provider/model should
serve each semantic LLM step.
"""
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from backend.core.logging import get_logger

logger = get_logger(__name__)


STATE_DIR = str(Path(__file__).resolve().parents[1] / "state")
SETTINGS_FILE = os.path.join(STATE_DIR, "settings.json")
SETTINGS_SCHEMA_VERSION = 1

LLM_STEPS = ("extraction", "synthesis", "judge", "graph_expansion")
ALLOWED_LLM_PROVIDERS = ("", "openai", "gemini", "anthropic", "openai_compatible", "local")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "llmRoutes": {
        step: {"provider": "", "model": ""}
        for step in LLM_STEPS
    }
}


def _ensure_state_dir() -> None:
    os.makedirs(STATE_DIR, exist_ok=True)


def _wrap_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schemaVersion": SETTINGS_SCHEMA_VERSION,
        "kind": "runtime_settings",
        "data": settings,
    }


def _unwrap_settings(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict) and raw.get("kind") == "runtime_settings" and "data" in raw:
        version = raw.get("schemaVersion", 0)
        if version > SETTINGS_SCHEMA_VERSION:
            raise ValueError(f"Unsupported runtime settings schemaVersion={version}")
        return raw["data"]
    return raw if isinstance(raw, dict) else {}


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("-", "_")
    if normalized not in ALLOWED_LLM_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider '{provider}'. Use openai, gemini, anthropic, "
            "openai_compatible, local, or blank for default."
        )
    return normalized


def _sanitize_settings(raw: Dict[str, Any]) -> Dict[str, Any]:
    settings = deepcopy(DEFAULT_SETTINGS)

    raw_routes = raw.get("llmRoutes", {}) if isinstance(raw, dict) else {}
    if isinstance(raw_routes, dict):
        for step in LLM_STEPS:
            route = raw_routes.get(step, {})
            if not isinstance(route, dict):
                continue
            provider = _normalize_provider(str(route.get("provider", "") or ""))
            model = str(route.get("model", "") or "").strip()
            if not provider and model:
                raise ValueError(f"{step}.provider is required when {step}.model is set.")
            settings["llmRoutes"][step] = {"provider": provider, "model": model}

    return settings


def get_runtime_settings() -> Dict[str, Any]:
    _ensure_state_dir()
    if not os.path.exists(SETTINGS_FILE):
        return deepcopy(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return _sanitize_settings(_unwrap_settings(json.load(f)))
    except Exception as e:
        logger.warning("Failed to load runtime settings, using defaults: %s", e)
        return deepcopy(DEFAULT_SETTINGS)


def save_runtime_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = _sanitize_settings(settings)
    _ensure_state_dir()
    tmp_path = f"{SETTINGS_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(_wrap_settings(sanitized), f, indent=2)
    os.replace(tmp_path, SETTINGS_FILE)
    return sanitized


def get_runtime_llm_override(step: str) -> Optional[Tuple[str, str]]:
    settings = get_runtime_settings()
    route = settings["llmRoutes"].get(step, {})
    provider = route.get("provider", "")
    model = route.get("model", "")
    if not provider and not model:
        return None
    return provider, model
