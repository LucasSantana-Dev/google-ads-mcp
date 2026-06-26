"""FastMCP server exposing Google Ads tools over stdio.

Tools live in ``google_ads_mcp.tools.*`` and self-register via ``register_all``.

IMPORTANT: stdout is the JSON-RPC transport channel — never print() to stdout here.
All logging goes to stderr.
"""

from __future__ import annotations

import sys

from fastmcp import FastMCP

from . import __version__
from .tools import register_all

mcp = FastMCP("Google Ads")
REGISTERED_MODULES = register_all(mcp)


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main() -> None:
    """Entry point for the ``google-ads-mcp`` console script (stdio transport)."""
    _log(
        f"google-ads-mcp v{__version__} starting (stdio); "
        f"tool modules: {', '.join(REGISTERED_MODULES)}"
    )
    mcp.run()


if __name__ == "__main__":
    main()
