import os

# Import-time side effect: harden mimetypes on Windows exactly once. config.py is imported
# by every entrypoint, so this is the single place the workaround needs to live.
import backend.core._win_mimetypes  # noqa: F401

from dotenv import load_dotenv

# Load environment variables (supports root and backend folder)
load_dotenv()
backend_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(backend_env_path):
    load_dotenv(backend_env_path, override=True)

# API Keys & Configurations
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_COMPATIBLE_API_KEY = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
OPENAI_COMPATIBLE_BASE_URL = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "")
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "")
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")

PHOENIX_PORT = int(os.getenv("PHOENIX_PORT", "6006"))
PHOENIX_PROJECT_NAME = os.getenv("PHOENIX_PROJECT_NAME", "cross-impact-catalysts")
FRESHNESS_LOOKBACK_MINUTES = int(os.getenv("FRESHNESS_LOOKBACK_MINUTES", "10"))

# Server bind defaults. 127.0.0.1 keeps the unauthenticated API off the LAN; override
# BACKEND_HOST=0.0.0.0 only for an intentional, trusted local-network demo.
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
# Dev autoreload respawns the worker and wipes in-memory ledger/graph state, so it is
# opt-in (BACKEND_RELOAD=1) rather than the default.
BACKEND_RELOAD = os.getenv("BACKEND_RELOAD", "0") == "1"

# Hard ceiling on a single pipeline run. A full multi-agent iteration can legitimately
# take a few minutes, so the default is generous (5 min) and tunable. When exceeded, the
# request is freed with a 504 and the ledger is rolled back; see services/pipeline.py.
PIPELINE_RUN_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_RUN_TIMEOUT_SECONDS", "300"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

# Global variables to track Phoenix session
phoenix_session = None

def init_phoenix():
    """Initializes Arize Phoenix tracing by registering the OTel provider."""
    try:
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor

        # Register the tracing collector (sends to localhost:4317 by default)
        print("Registering Arize Phoenix OpenTelemetry tracing provider...")
        register(project_name=PHOENIX_PROJECT_NAME)
        
        # Instrument LangChain & LangGraph
        LangChainInstrumentor().instrument()
        print("Arize Phoenix OpenTelemetry tracing provider registered successfully.")
    except Exception as e:
        print(f"Warning: Failed to initialize Arize Phoenix OpenTelemetry provider: {e}")
        print("Traces will not be captured.")
