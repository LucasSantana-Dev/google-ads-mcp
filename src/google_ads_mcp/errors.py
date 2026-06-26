"""Shared error handling for tools.

MCP best practice: surface failures inside the tool result (``{success: false, error: ...}``)
so the LLM can react, instead of raising protocol-level errors. Every tool is wrapped with
``tool_handler`` at registration time.
"""

from __future__ import annotations

import functools
from typing import Any, Callable


def tool_handler(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Wrap a tool function so any exception becomes a structured error result."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - deliberately broad; reported to caller
            return {"success": False, "error": format_error(exc)}

    return wrapper


def format_error(exc: Exception) -> dict:
    """Readable error dict, with Google Ads API failure detail when present."""
    try:
        from google.ads.googleads.errors import GoogleAdsException

        if isinstance(exc, GoogleAdsException):
            return {
                "type": "GoogleAdsException",
                "request_id": exc.request_id,
                "errors": [
                    {"message": e.message, "code": str(e.error_code).strip()}
                    for e in exc.failure.errors
                ],
            }
    except Exception:  # pragma: no cover - never let error formatting mask the original
        pass
    return {"type": type(exc).__name__, "message": str(exc)}
