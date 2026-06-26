"""Campaign-reporting tools."""

from __future__ import annotations

from .. import config, gaql
from ..errors import tool_handler


def get_campaigns(customer_id: str, status_filter: str | None = None, limit: int = 100) -> dict:
    """Get campaigns for a customer, optionally filtered by status.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        status_filter: optional campaign status filter (ENABLED, PAUSED, or REMOVED).
        limit: max campaigns returned to the caller (hard-capped at 10,000 by the API).

    Returns ``{success, rows, row_count, is_truncated}``.
    """
    client = config.get_client()
    query = gaql.TEMPLATES["campaigns"]
    if status_filter:
        query += f" WHERE campaign.status = '{status_filter}'"
    query += f" LIMIT {limit}"
    return gaql.run_search(client, customer_id, query, limit)


def get_campaign_performance(
    customer_id: str, date_start: str, date_end: str, limit: int = 100
) -> dict:
    """Get campaign performance metrics for a date range, ordered by cost descending.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        date_start: start date for performance metrics (YYYY-MM-DD format).
        date_end: end date for performance metrics (YYYY-MM-DD format).
        limit: max campaigns returned to the caller (hard-capped at 10,000 by the API).

    Returns ``{success, rows, row_count, is_truncated}``.
    """
    client = config.get_client()
    query = gaql.TEMPLATES["campaign_performance"]
    query += f" WHERE segments.date BETWEEN '{date_start}' AND '{date_end}' ORDER BY metrics.cost_micros DESC"
    query += f" LIMIT {limit}"
    return gaql.run_search(client, customer_id, query, limit)


def register(mcp) -> None:
    mcp.tool(tool_handler(get_campaigns))
    mcp.tool(tool_handler(get_campaign_performance))