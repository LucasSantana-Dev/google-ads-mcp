"""Raw GAQL query tool."""

from __future__ import annotations

from .. import config, gaql
from ..errors import tool_handler


def run_gaql_query(customer_id: str, query: str, limit: int = 1000) -> dict:
    """Run a read-only GAQL query against a customer account.

    This is the explicit raw-query escape hatch: the ``query`` is passed through as-is, so the
    caller is responsible for valid GAQL. Use ``get_segments_metadata`` / ``get_metrics_metadata``
    / ``get_resource_metadata`` first to discover valid field names. ``customer_id`` is validated.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        query: a GAQL query (SELECT ... FROM ... [WHERE ...] [LIMIT ...]).
        limit: max rows returned to the caller (hard-capped at 10,000 by the API).

    Returns ``{success, rows, row_count, is_truncated}``.
    """
    gaql.require_customer_id(customer_id)
    client = config.get_client()
    return gaql.run_search(client, customer_id, query, int(limit))


def register(mcp) -> None:
    mcp.tool(tool_handler(run_gaql_query))
