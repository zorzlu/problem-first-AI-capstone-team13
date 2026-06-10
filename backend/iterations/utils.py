"""Small shared helpers for iteration workflow nodes."""
import os
import time
from datetime import datetime, timezone

from backend.core.logging import get_logger

logger = get_logger(__name__)

def clean_json_string(text: str) -> str:
    """Cleans markdown JSON code blocks from LLM output if present."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def classify_llm_failure(e: Exception, model_label: str) -> str:
    """Turn an LLM-node exception into an accurate, user-facing failure reason.

    Distinguishes a genuine availability problem (the call never produced a valid
    response — rate limit, quota, auth, connectivity) from a content problem (the
    model responded but its output did not satisfy the required schema). Conflating
    these is exactly the bug that made a parse error read as 'rate-limited'.
    """
    from pydantic import ValidationError
    name = type(e).__name__
    if isinstance(e, (ValidationError, ValueError)) or "OutputParser" in name:
        return f"The {model_label} returned output that did not match the required schema: {e}"
    return (f"The {model_label} could not be reached "
            f"(possible rate limit, quota, or connectivity issue): {e}")

def invoke_with_retry(runnable, messages, label="LLM call"):
    """Invoke a runnable, retrying exactly once on a *transient* failure.

    The expensive nodes make a single batched call by design (efficiency). A retry
    covers a transient hiccup (rate-limit blip, timeout) without un-batching. A schema /
    content failure (the model responded but its output did not match the required
    schema) will not be fixed by retrying — re-issuing the same call just doubles latency
    and API cost — so we re-raise those immediately. Mirrors classify_llm_failure().

    The single retry is intentionally unguarded: if the second attempt also fails, the
    exception propagates to the caller's fail-classify path. A short backoff
    (RETRY_BACKOFF_SECONDS, default 2s) precedes the retry — rate-limit errors are
    transient, and an immediate retry within the same second hits the same limit again.
    """
    from pydantic import ValidationError
    try:
        return runnable.invoke(messages)
    except Exception as e:
        if isinstance(e, (ValidationError, ValueError)) or "OutputParser" in type(e).__name__:
            raise
        backoff = float(os.getenv("RETRY_BACKOFF_SECONDS", "2"))
        logger.warning("%s failed (%s); retrying once in %.1fs...", label, e, backoff)
        if backoff > 0:
            time.sleep(backoff)
        return runnable.invoke(messages)

def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

def copy_dict(d):
    # Shallow copy for simplicity
    return {k: v for k, v in d.items()}
