"""LLM provider registry and per-workflow model selection.

LangGraph nodes should depend on semantic model roles (extraction, synthesis, judge,
graph expansion), not on vendor-specific constructors or environment variables. This
module owns that boundary.
"""
import os
from dataclasses import dataclass
from typing import Literal, Optional

from backend.core.config import (
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    LOCAL_LLM_API_KEY,
    LOCAL_LLM_BASE_URL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_COMPATIBLE_API_KEY,
    OPENAI_COMPATIBLE_BASE_URL,
)
from backend.services.runtime_settings import get_runtime_llm_override

Provider = Literal["openai", "gemini", "anthropic", "openai_compatible", "local"]


@dataclass(frozen=True)
class ModelSpec:
    provider: Provider
    model_id: str


@dataclass(frozen=True)
class StepModelRoute:
    primary: ModelSpec
    fallback: Optional[ModelSpec] = None


@dataclass(frozen=True)
class ProviderRuntime:
    provider: Provider
    label: str
    configured: bool
    base_url: str = ""
    notes: str = ""


LLM_STEPS = ("extraction", "synthesis", "judge", "graph_expansion")

# Defaults are intentionally stable model ids, not "latest" aliases. Override any step
# with e.g. EXTRACTION_LLM_PROVIDER=anthropic and EXTRACTION_LLM_MODEL=claude-sonnet-4-20250514.
STEP_MODELS: dict[str, StepModelRoute] = {
    "extraction": StepModelRoute(
        primary=ModelSpec("openai", "gpt-5-mini"),
        fallback=ModelSpec("gemini", "gemini-2.5-flash-lite"),
    ),
    "synthesis": StepModelRoute(
        primary=ModelSpec("openai", "gpt-5-nano"),
        fallback=ModelSpec("gemini", "gemini-2.5-flash-lite"),
    ),
    "judge": StepModelRoute(
        primary=ModelSpec("gemini", "gemini-3.1-flash-lite"),
        fallback=ModelSpec("openai", "gpt-4o-mini"),
    ),
    "graph_expansion": StepModelRoute(
        primary=ModelSpec("openai", "gpt-5-mini"),
        fallback=ModelSpec("gemini", "gemini-2.5-flash-lite"),
    ),
}

PROVIDER_DEFAULT_MODELS: dict[Provider, dict[str, str]] = {
    "openai": {
        "extraction": "gpt-4.1-nano",
        "synthesis": "gpt-4o-mini",
        "judge": "gpt-4o-mini",
        "graph_expansion": "gpt-5-mini",
    },
    "gemini": {
        "extraction": "gemini-2.5-flash-lite",
        "synthesis": "gemini-2.5-flash-lite",
        "judge": "gemini-2.5-flash-lite",
        "graph_expansion": "gemini-2.5-flash-lite",
    },
    "anthropic": {
        "extraction": "claude-3-5-haiku-20241022",
        "synthesis": "claude-sonnet-4-20250514",
        "judge": "claude-sonnet-4-20250514",
        "graph_expansion": "claude-sonnet-4-20250514",
    },
    "openai_compatible": {
        "extraction": os.getenv("OPENAI_COMPATIBLE_MODEL", ""),
        "synthesis": os.getenv("OPENAI_COMPATIBLE_MODEL", ""),
        "judge": os.getenv("OPENAI_COMPATIBLE_MODEL", ""),
        "graph_expansion": os.getenv("OPENAI_COMPATIBLE_MODEL", ""),
    },
    "local": {
        "extraction": os.getenv("LOCAL_LLM_MODEL", ""),
        "synthesis": os.getenv("LOCAL_LLM_MODEL", ""),
        "judge": os.getenv("LOCAL_LLM_MODEL", ""),
        "graph_expansion": os.getenv("LOCAL_LLM_MODEL", ""),
    },
}


def _provider_runtime(provider: Provider) -> ProviderRuntime:
    if provider == "openai":
        return ProviderRuntime(provider, "OpenAI", bool(OPENAI_API_KEY))
    if provider == "gemini":
        return ProviderRuntime(provider, "Google Gemini", bool(GEMINI_API_KEY))
    if provider == "anthropic":
        return ProviderRuntime(provider, "Anthropic Claude", bool(ANTHROPIC_API_KEY))
    if provider == "openai_compatible":
        return ProviderRuntime(
            provider,
            "OpenAI-compatible endpoint",
            bool(OPENAI_COMPATIBLE_BASE_URL),
            base_url=OPENAI_COMPATIBLE_BASE_URL,
            notes="Uses ChatOpenAI with a custom base URL for hosted gateways.",
        )
    if provider == "local":
        return ProviderRuntime(
            provider,
            "Local OpenAI-compatible endpoint",
            bool(LOCAL_LLM_BASE_URL),
            base_url=LOCAL_LLM_BASE_URL,
            notes="Set LOCAL_LLM_BASE_URL to an OpenAI-compatible local server such as Ollama /v1, LM Studio, or vLLM.",
        )
    raise ValueError(f"Unknown provider '{provider}'.")


def provider_statuses() -> dict[str, dict[str, str | bool]]:
    statuses = {}
    for provider in ("openai", "gemini", "anthropic", "openai_compatible", "local"):
        runtime = _provider_runtime(provider)  # type: ignore[arg-type]
        statuses[provider] = {
            "label": runtime.label,
            "configured": runtime.configured,
            "baseUrl": runtime.base_url,
            "notes": runtime.notes,
        }
    return statuses


def _candidate_specs(route: StepModelRoute) -> list[ModelSpec]:
    candidates = [route.primary]
    if route.fallback and route.fallback != route.primary:
        candidates.append(route.fallback)
    return candidates


def _env_prefix(step: str) -> str:
    return step.upper()


def _provider_from_env(value: str) -> Provider:
    provider = value.strip().lower()
    if provider == "openai-compatible":
        provider = "openai_compatible"
    if provider not in {"openai", "gemini", "anthropic", "openai_compatible", "local"}:
        raise ValueError(
            f"Unsupported LLM provider '{value}'. Use openai, gemini, anthropic, "
            "openai_compatible, or local."
        )
    return provider  # type: ignore[return-value]


def _step_override(step: str) -> Optional[ModelSpec]:
    prefix = _env_prefix(step)
    provider_raw = os.getenv(f"{prefix}_LLM_PROVIDER", "")
    model_id = os.getenv(f"{prefix}_LLM_MODEL", "")
    if not provider_raw and not model_id:
        return None

    provider = _provider_from_env(provider_raw) if provider_raw else STEP_MODELS[step].primary.provider
    model_id = model_id or PROVIDER_DEFAULT_MODELS[provider].get(step, "")
    if not model_id:
        raise ValueError(
            f"{prefix}_LLM_MODEL is required when {prefix}_LLM_PROVIDER={provider}."
        )
    return ModelSpec(provider, model_id)


def _runtime_settings_override(step: str) -> Optional[ModelSpec]:
    override = get_runtime_llm_override(step)
    if not override:
        return None
    provider_raw, model_id = override
    provider = _provider_from_env(provider_raw)
    model_id = model_id or PROVIDER_DEFAULT_MODELS[provider].get(step, "")
    if not model_id:
        raise ValueError(
            f"A model is required for runtime setting {step}.llmRoutes when provider={provider}."
        )
    return ModelSpec(provider, model_id)


def _legacy_provider_override(step: str) -> Optional[ModelSpec]:
    if not LLM_PROVIDER:
        return None
    provider = _provider_from_env(LLM_PROVIDER)
    model_id = PROVIDER_DEFAULT_MODELS[provider].get(step, "")
    if not model_id:
        raise ValueError(
            f"{provider} has no default model for step '{step}'. Set {step.upper()}_LLM_MODEL."
        )
    return ModelSpec(provider, model_id)


def _is_provider_configured(provider: Provider) -> bool:
    return _provider_runtime(provider).configured


def _resolved_candidates(step: str) -> list[ModelSpec]:
    if step not in STEP_MODELS:
        raise ValueError(f"Unknown LLM step '{step}'. Valid steps: {', '.join(sorted(STEP_MODELS))}.")
    override = _step_override(step)
    if override:
        return [override]
    runtime_override = _runtime_settings_override(step)
    if runtime_override:
        return [runtime_override]
    legacy_override = _legacy_provider_override(step)
    if legacy_override:
        route = STEP_MODELS[step]
        candidates = [legacy_override]
        if route.fallback and route.fallback.provider != legacy_override.provider:
            candidates.append(route.fallback)
        return candidates
    return _candidate_specs(STEP_MODELS[step])


def resolve_model_spec(step: str) -> ModelSpec:
    """Return the provider/model pair that should be used for this semantic step."""
    candidates = _resolved_candidates(step)
    for spec in candidates:
        if _is_provider_configured(spec.provider):
            if len(candidates) > 1 and spec != candidates[0]:
                print(
                    f"Warning: {candidates[0].provider} is not configured for step '{step}'. "
                    f"Falling back to {spec.provider}:{spec.model_id}."
                )
            return spec

    tried = ", ".join(f"{spec.provider}:{spec.model_id}" for spec in candidates)
    raise ValueError(f"No configured LLM provider is available for step '{step}'. Tried {tried}.")


def has_llm_for_step(step: str) -> bool:
    try:
        resolve_model_spec(step)
        return True
    except ValueError:
        return False


def has_any_llm() -> bool:
    return any(has_llm_for_step(step) for step in LLM_STEPS)


def get_model_status(step: str) -> dict[str, str | bool]:
    route = STEP_MODELS[step]
    try:
        selected = resolve_model_spec(step)
        return {
            "configured": True,
            "provider": selected.provider,
            "model": selected.model_id,
            "primaryProvider": route.primary.provider,
            "primaryModel": route.primary.model_id,
        }
    except ValueError as e:
        return {
            "configured": False,
            "provider": "N/A",
            "model": "N/A",
            "primaryProvider": route.primary.provider,
            "primaryModel": route.primary.model_id,
            "error": str(e),
        }


def model_statuses() -> dict[str, dict[str, str | bool]]:
    return {step: get_model_status(step) for step in LLM_STEPS}


def _build_llm(step: str):
    spec = resolve_model_spec(step)

    if spec.provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=OPENAI_API_KEY, model=spec.model_id, temperature=0.0)

    if spec.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(google_api_key=GEMINI_API_KEY, model=spec.model_id, temperature=0.0)

    if spec.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=ANTHROPIC_API_KEY, model=spec.model_id, temperature=0.0)

    if spec.provider == "openai_compatible":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=OPENAI_COMPATIBLE_API_KEY or "not-required",
            base_url=OPENAI_COMPATIBLE_BASE_URL,
            model=spec.model_id,
            temperature=0.0,
        )

    if spec.provider == "local":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=LOCAL_LLM_API_KEY or "not-required",
            base_url=LOCAL_LLM_BASE_URL,
            model=spec.model_id,
            temperature=0.0,
        )

    raise ValueError(f"Unknown provider '{spec.provider}' for step '{step}'.")


def get_extraction_llm():
    return _build_llm("extraction")


def get_synthesis_llm():
    return _build_llm("synthesis")


def get_judge_llm():
    return _build_llm("judge")


def get_graph_expansion_llm():
    return _build_llm("graph_expansion")
