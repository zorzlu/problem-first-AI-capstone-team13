"""Windows MIME-type compatibility shim.

Root cause (outside this app): on some Windows machines a corrupted registry MIME entry
(a bogus ``Content Type`` value under ``HKEY_CLASSES_ROOT``) makes Python's ``mimetypes``
module return wrong content types. Starlette/Uvicorn read those types when serving
responses, so the bad registry value surfaces as broken responses.

Mitigation: re-initialize ``mimetypes`` from Python's built-in defaults
(``init(files=[])``) instead of the registry. There is no in-app "proper" fix because the
fault is in the OS registry, not our code — this is the standard, documented mitigation.

Design:
- Guarded to Windows only, so on macOS/Linux it is a clean no-op rather than a
  speculative ``try/except`` that silently does nothing.
- Imported once for its side effect from ``backend/config.py`` (which every entrypoint
  imports), so it runs exactly once with a single source of truth.
- The narrow ``except`` keeps a healthy system from ever failing startup over this; if the
  reinit itself errors we are no worse off than before calling it.
"""
import sys


def apply() -> None:
    if sys.platform != "win32":
        return
    import mimetypes
    try:
        mimetypes.init(files=[])
    except Exception:
        # A corrupted registry is exactly the failure mode we are working around; do not
        # let it crash startup.
        pass


apply()
