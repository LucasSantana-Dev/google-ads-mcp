"""Retry helper for transient Google Ads API quota errors.

Applies exponential back-off with full jitter on RESOURCE_TEMPORARILY_EXHAUSTED:
  wait = random(0, min(CAP, BASE * 2^attempt))

Configure via env vars:
  GOOGLE_ADS_MAX_RETRIES  — total retry attempts after first failure (default 3)
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")

_MAX_RETRIES = int(os.environ.get("GOOGLE_ADS_MAX_RETRIES", "3"))
_BASE_S = 1.0
_CAP_S = 30.0


def _is_quota_exhausted(exc: Exception) -> bool:
    """True when exc is a GoogleAdsException caused by quota exhaustion."""
    try:
        from google.ads.googleads.errors import GoogleAdsException

        if isinstance(exc, GoogleAdsException):
            return any(
                "RESOURCE_TEMPORARILY_EXHAUSTED" in str(e.error_code)
                for e in exc.failure.errors
            )
    except Exception:
        pass
    return False


def call_with_retry(fn: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Call fn(*args, **kwargs), retrying up to _MAX_RETRIES times on quota exhaustion.

    Non-quota exceptions propagate immediately. After _MAX_RETRIES retries, the last
    quota exception re-raises so the caller (tool_handler) surfaces it cleanly.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not _is_quota_exhausted(exc):
                raise
            last_exc = exc
            if attempt >= _MAX_RETRIES:
                break
            wait = random.uniform(0, min(_CAP_S, _BASE_S * (2**attempt)))
            time.sleep(wait)
    assert last_exc is not None  # loop always sets it before break
    raise last_exc
