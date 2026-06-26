"""One-time helper: mint a Google Ads OAuth2 refresh token.

Prereqs: an OAuth 2.0 *Desktop App* credential (client id + secret) from Google Cloud Console.

Usage:
    GOOGLE_ADS_CLIENT_ID=... GOOGLE_ADS_CLIENT_SECRET=... \
        uv run python scripts/get_refresh_token.py

Opens a browser for consent, then prints the refresh token. Paste it into .env as
GOOGLE_ADS_REFRESH_TOKEN. (New tokens require 2-step verification per Google Ads policy,
April 2026. For unattended use, prefer a service account instead.)
"""

from __future__ import annotations

import os
import sys

# Google Ads API OAuth scope.
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main() -> None:
    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit(
            "Set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET first (see .env.example)."
        )

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit("Missing dependency. Run: uv add google-auth-oauthlib")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    print("\n" + "=" * 60)
    print("Add this to your .env file:")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
