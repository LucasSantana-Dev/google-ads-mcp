"""Keyword and search term reporting tools."""

from __future__ import annotations

from .. import config, gaql
from ..errors import tool_handler


def get_keywords(
    customer_id: str,
    ad_group_id: str | None = None,
    match_type_filter: str | None = None,
    limit: int = 100,
) -> dict:
    """Retrieve keywords from an ad group, optionally filtered by match type.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        ad_group_id: Optional ad group id to filter keywords to a specific ad group.
        match_type_filter: Optional match type filter (BROAD, PHRASE, or EXACT).
        limit: max rows returned to the caller (hard-capped at 10,000 by the API).

    Returns:
        ``{success, rows, row_count, is_truncated}``.
    """
    client = config.get_client()
    query = gaql.TEMPLATES["keywords"]
    
    # Build WHERE conditions
    conditions = []
    if ad_group_id is not None:
        conditions.append(f"ad_group.id = {ad_group_id}")
    if match_type_filter is not None:
        conditions.append(f"ad_group_criterion.keyword.match_type = '{match_type_filter}'")
    
    # Append WHERE clause if conditions exist
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += f" LIMIT {limit}"
    return gaql.run_search(client, customer_id, query, limit)


def get_search_terms(
    customer_id: str,
    date_start: str,
    date_end: str,
    campaign_id: str | None = None,
    min_impressions: int = 0,
    limit: int = 100,
) -> dict:
    """Retrieve search terms that matched keywords, filtered by date and optional criteria.

    Search terms are ordered by clicks (descending) to prioritize high-engagement terms.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        date_start: start date in 'YYYY-MM-DD' format (inclusive).
        date_end: end date in 'YYYY-MM-DD' format (inclusive).
        campaign_id: Optional campaign id to filter search terms to a specific campaign.
        min_impressions: Optional minimum impressions threshold (default 0 = no filter).
        limit: max rows returned to the caller (hard-capped at 10,000 by the API).

    Returns:
        ``{success, rows, row_count, is_truncated}``.
    """
    client = config.get_client()
    query = gaql.TEMPLATES["search_terms"]
    
    # Build WHERE conditions
    conditions = [f"segments.date BETWEEN '{date_start}' AND '{date_end}'"]
    if campaign_id is not None:
        conditions.append(f"campaign.id = {campaign_id}")
    if min_impressions > 0:
        conditions.append(f"metrics.impressions >= {min_impressions}")
    
    # Append WHERE, ORDER BY, and LIMIT
    query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY metrics.clicks DESC"
    query += f" LIMIT {limit}"
    
    return gaql.run_search(client, customer_id, query, limit)


def register(mcp) -> None:
    mcp.tool(tool_handler(get_keywords))
    mcp.tool(tool_handler(get_search_terms))
