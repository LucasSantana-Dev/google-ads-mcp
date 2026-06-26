"""Ad group retrieval tools."""

from __future__ import annotations

from .. import config, gaql
from ..errors import tool_handler


def get_ad_groups(
    customer_id: str,
    campaign_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 100,
) -> dict:
    """Get ad groups for a customer, with optional filtering by campaign and status.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        campaign_id: optional campaign id to filter ad groups.
        status_filter: optional ad group status filter (ENABLED, PAUSED, or REMOVED).
        limit: max rows returned to the caller (hard-capped at 10,000 by the API).

    Returns ``{success, rows, row_count, is_truncated}``.
    """
    gaql.require_customer_id(customer_id)
    if campaign_id is not None:
        gaql.require_id("campaign_id", campaign_id)
    if status_filter is not None:
        gaql.require_enum("status_filter", status_filter, gaql.AD_GROUP_STATUSES)
    limit = int(limit)
    client = config.get_client()
    query = gaql.TEMPLATES["ad_groups"]

    conditions = []
    if campaign_id is not None:
        conditions.append(f"campaign.id = {campaign_id}")
    if status_filter is not None:
        conditions.append(f"ad_group.status = '{status_filter}'")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" LIMIT {limit}"

    return gaql.run_search(client, customer_id, query, limit)


def register(mcp) -> None:
    mcp.tool(tool_handler(get_ad_groups))
