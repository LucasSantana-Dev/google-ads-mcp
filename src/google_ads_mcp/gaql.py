"""GAQL helpers shared by all reporting tools.

The core entry point is :func:`run_search`, which executes a GAQL query via
``GoogleAdsService.search_stream`` and returns paginated, capped, serialized rows.
Reporting tools build a GAQL string (often with :data:`TEMPLATES`) and call ``run_search``.

The ``require_*`` validators are defense-in-depth: tools that interpolate ids / dates / enum
values into a GAQL string must validate them first so a caller cannot inject query logic.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .retry import call_with_retry

# Google Ads caps a single query result at 10,000 rows.
MAX_ROWS = 10_000


def normalize_customer_id(customer_id: str) -> str:
    """Customer ids are digits only; strip hyphens a user may have pasted."""
    return customer_id.replace("-", "").strip()


# --- input validation -----------------------------------------------------
_ID_RE = re.compile(r"^\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CAMPAIGN_STATUSES = {"ENABLED", "PAUSED", "REMOVED"}
AD_GROUP_STATUSES = {"ENABLED", "PAUSED", "REMOVED"}
KEYWORD_MATCH_TYPES = {"BROAD", "PHRASE", "EXACT"}


def require_customer_id(value: str) -> str:
    """Normalize then validate that a customer id is digits only. Raises ValueError otherwise."""
    norm = normalize_customer_id(value)
    if not _ID_RE.match(norm):
        raise ValueError(f"customer_id must be digits (hyphens allowed), got {value!r}")
    return norm


def require_id(name: str, value: str) -> str:
    """Validate a numeric resource id (digits only). Raises ValueError otherwise."""
    text = str(value).strip()
    if not _ID_RE.match(text):
        raise ValueError(f"{name} must be digits only, got {value!r}")
    return text


def require_date(name: str, value: str) -> str:
    """Validate a YYYY-MM-DD date string. Raises ValueError otherwise."""
    text = str(value).strip()
    if not _DATE_RE.match(text):
        raise ValueError(f"{name} must be in YYYY-MM-DD format, got {value!r}")
    return text


def require_enum(name: str, value: str, allowed: set[str]) -> str:
    """Validate that value is in the allowed set. Raises ValueError otherwise."""
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got {value!r}")
    return value


# --- query execution ------------------------------------------------------

def row_to_dict(row: Any) -> dict:
    """Serialize a GoogleAdsRow (proto-plus) to a plain dict with snake_case keys.

    Passes through dicts unchanged so test doubles can yield plain dicts as rows. Keys are
    snake_case (``preserving_proto_field_name=True``) so they match the GAQL field names the
    caller wrote (e.g. ``cpc_bid_micros``) rather than protobuf camelCase.
    """
    if isinstance(row, dict):
        return row
    to_dict = getattr(type(row), "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict(row, preserving_proto_field_name=True)
        except TypeError:
            return to_dict(row)
    pb = getattr(row, "_pb", row)
    from google.protobuf.json_format import MessageToDict

    return MessageToDict(pb, preserving_proto_field_name=True)


def run_search(client: Any, customer_id: str, query: str, limit: int = 1000) -> dict:
    """Execute a GAQL query and return up to ``limit`` rows (hard-capped at MAX_ROWS).

    Returns ``{success, rows, row_count, is_truncated}``. ``is_truncated`` is True when the
    cap was hit (more rows may exist; narrow the query or raise the limit).

    Retries automatically on RESOURCE_TEMPORARILY_EXHAUSTED with exponential backoff + jitter
    (see :mod:`retry`). Partial result sets are discarded on retry so rows are never duplicated.
    """
    cap = max(1, min(limit, MAX_ROWS))
    cid = normalize_customer_id(customer_id)
    service = client.get_service("GoogleAdsService")

    def _execute() -> list[dict]:
        rows: list[dict] = []
        for batch in service.search_stream(customer_id=cid, query=query):
            for row in batch.results:
                rows.append(row_to_dict(row))
                if len(rows) >= cap:
                    break
            if len(rows) >= cap:
                break
        return rows

    rows = call_with_retry(_execute)
    return {
        "success": True,
        "rows": rows,
        "row_count": len(rows),
        "is_truncated": len(rows) >= cap,
    }


def quote_list(values: Iterable[Any]) -> str:
    """Render values as a GAQL ``IN`` clause group, e.g. ('ENABLED', 'PAUSED')."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


# Ready-made GAQL templates (resource + metric selections). Tools format date / id filters
# and may append ORDER BY / LIMIT. Field names verified against Google Ads API v24.
TEMPLATES = {
    "campaigns": (
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign.advertising_channel_type FROM campaign"
    ),
    "campaign_performance": (
        "SELECT campaign.id, campaign.name, metrics.clicks, metrics.impressions, "
        "metrics.cost_micros, metrics.conversions, metrics.ctr, metrics.average_cpc "
        "FROM campaign"
    ),
    "ad_groups": (
        "SELECT ad_group.id, ad_group.name, ad_group.status, campaign.id "
        "FROM ad_group"
    ),
    "keywords": (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type, ad_group_criterion.status, ad_group.id "
        "FROM keyword_view"
    ),
    "search_terms": (
        "SELECT search_term_view.search_term, metrics.clicks, metrics.impressions, "
        "metrics.conversions, metrics.cost_micros FROM search_term_view"
    ),
    "change_events": (
        "SELECT change_event.change_date_time, change_event.change_resource_type, "
        "change_event.resource_change_operation, change_event.user_email "
        "FROM change_event"
    ),
}
