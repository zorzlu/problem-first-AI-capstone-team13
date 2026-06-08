from fastapi import APIRouter, HTTPException

from backend.api.schemas import RuntimeSettingsRequest
from backend.core.llm import model_statuses, provider_statuses
from backend.services.runtime_settings import (
    ALLOWED_LLM_PROVIDERS,
    LLM_STEPS,
    get_runtime_settings,
    save_runtime_settings,
)


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    """Non-secret runtime settings plus option metadata for the local settings UI."""
    return {
        "settings": get_runtime_settings(),
        "allowedLlmProviders": [provider for provider in ALLOWED_LLM_PROVIDERS if provider],
        "llmSteps": list(LLM_STEPS),
    }


@router.put("")
def update_settings(req: RuntimeSettingsRequest):
    try:
        settings = save_runtime_settings(req.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "settings": settings,
        "llmSteps": model_statuses(),
        "llmProviders": provider_statuses(),
    }
