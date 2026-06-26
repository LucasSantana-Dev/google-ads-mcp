"""Change event tracking tool."""

from __future__ import annotations

from .. import config, gaql
from ..errors import tool_handler


def get_change_events(
    customer_id: str,
    date_start: str,
    date_end: str,
    limit: int = 100,
) -> dict:
    """Retrieve change events for a customer account within a date range.

    The change_event resource requires a date filter, an ORDER BY clause, and a LIMIT
    (hard-capped at 10,000 rows by the API). The Google Ads API typically supports a
    ~30-day lookback window for change events; queries beyond that range may return
    empty results.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        date_start: start date in 'YYYY-MM-DD' format (inclusive).
        date_end: end date in 'YYYY-MM-DD' format (inclusive).
        limit: max rows returned to the caller (hard-capped at 10,000 by the API).

    Returns ``{success, rows, row_count, is_truncated}``.
    """
    gaql.require_customer_id(customer_id)
    gaql.require_date("date_start", date_start)
    gaql.require_date("date_end", date_end)
    limit = int(limit)
    client = config.get_client()
    query = gaql.TEMPLATES["change_events"]
    query += f" WHERE change_event.change_date_time BETWEEN '{date_start}' AND '{date_end}'"
    query += " ORDER BY change_event.change_date_time DESC"
    query += f" LIMIT {min(limit, 10000)}"
    return gaql.run_search(client, customer_id, query, limit)


def register(mcp) -> None:
    mcp.tool(tool_handler(get_change_events))
