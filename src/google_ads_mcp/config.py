"""Credential loading and GoogleAdsClient construction.

Credentials come from environment variables (see .env.example). We never read
credentials from a checked-in file. The client is cached so we build it once per process.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from . import GOOGLE_ADS_API_VERSION

if TYPE_CHECKING:  # avoid importing the heavy google-ads package at module import time
    from google.ads.googleads.client import GoogleAdsClient

REQUIRED_ENV = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)


def missing_env() -> list[str]:
    """Return the names of required env vars that are unset or empty."""
    return [name for name in REQUIRED_ENV if not os.environ.get(name)]


@lru_cache(maxsize=1)
def get_client() -> "GoogleAdsClient":
    """Build (and cache) a GoogleAdsClient from environment variables.

    Raises RuntimeError with an actionable message if any required credential is missing,
    so the failure is clear in the MCP client instead of a deep google-ads stack trace.
    """
    missing = missing_env()
    if missing:
        raise RuntimeError(
            "Missing required Google Ads credentials: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in (see README.md)."
        )

    # google-ads reads its config from GOOGLE_ADS_* env vars via load_from_env.
    os.environ.setdefault("GOOGLE_ADS_USE_PROTO_PLUS", "True")

    from google.ads.googleads.client import GoogleAdsClient

    return GoogleAdsClient.load_from_env(version=GOOGLE_ADS_API_VERSION)
