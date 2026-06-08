import socket

from fastapi import APIRouter

import backend.memory as memory_module
from backend.core.config import PHOENIX_PORT
from backend.core.llm import model_statuses, provider_statuses


router = APIRouter(prefix="/api", tags=["status"])


def _phoenix_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.25) -> bool:
    """Best-effort check that something is accepting connections on the Phoenix port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@router.get("/phoenix-status")
def get_phoenix_status():
    running = _phoenix_listening(PHOENIX_PORT)
    return {
        "running": running,
        "dashboardUrl": f"http://127.0.0.1:{PHOENIX_PORT}",
        "projectName": "cross-impact-catalysts",
    }


@router.get("/memory-status")
def get_memory_status():
    """Return the current status of the catalyst dedup engine and memory module."""
    embedding_active = memory_module.is_embedding_active()
    if embedding_active:
        dedup_provider = "Local embeddings"
        dedup_model = f"{memory_module.EMBEDDING_MODEL_NAME} (384d)"
        dedup_method = "neural_cosine"
    else:
        dedup_provider = "Local (lexical fallback)"
        dedup_model = "tf-cosine + jaccard"
        dedup_method = "lexical_cosine"

    llm_steps = model_statuses()
    llm_extraction = llm_steps["extraction"]
    llm_synthesis = llm_steps["synthesis"]
    llm_judge = llm_steps["judge"]
    llm_graph_expansion = llm_steps["graph_expansion"]

    counts = memory_module.ledger_counts()

    return {
        "dedupProvider": dedup_provider,
        "dedupModel": dedup_model,
        "dedupMethod": dedup_method,
        "embeddingProvider": "local_fastembed" if embedding_active else "local_lexical",
        "embeddingRuntime": "local_cpu" if embedding_active else "local_python",
        "embeddingModel": memory_module.EMBEDDING_MODEL_NAME if embedding_active else "tf-cosine + jaccard",
        "embeddingCacheDir": memory_module.EMBEDDING_CACHE_DIR,
        "embeddingLocation": "localhost",
        "isFallbackActive": not embedding_active,
        "similarityThreshold": 0.75,
        "jaccardFactThreshold": 0.6,
        "ledgerTotalEntries": counts["total"],
        "ledgerLiveEntries": counts["live"],
        "ledgerEmbeddedEntries": counts["embedded"],
        "llmExtractionProvider": llm_extraction["provider"],
        "llmExtractionModel": llm_extraction["model"],
        "llmSynthesisProvider": llm_synthesis["provider"],
        "llmSynthesisModel": llm_synthesis["model"],
        "llmJudgeProvider": llm_judge["provider"],
        "llmJudgeModel": llm_judge["model"],
        "llmGraphExpansionProvider": llm_graph_expansion["provider"],
        "llmGraphExpansionModel": llm_graph_expansion["model"],
        "llmSteps": llm_steps,
        "llmProviders": provider_statuses(),
    }
