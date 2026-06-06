import mimetypes
try:
    mimetypes.init(files=[])
except Exception:
    pass

import os
from dotenv import load_dotenv

# Load environment variables (supports root and backend folder)
load_dotenv()
backend_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
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
