"""Metadata discovery tools for GAQL schema exploration."""

from __future__ import annotations

import re

from .. import config
from ..errors import tool_handler


def _validate_resource_name(resource_name: str) -> tuple[bool, str | None]:
    """Validate that resource_name matches valid GAQL resource identifier pattern.
    
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not resource_name:
        return False, "resource_name cannot be empty"
    
    # GAQL resource names are alphanumeric + underscores, must start with letter/underscore
    if not re.match(r'^[a-z_][a-z0-9_]*$', resource_name, re.IGNORECASE):
        return False, f"Invalid resource name format: {resource_name}"
    
    return True, None


def get_segments_metadata() -> dict:
    """List all available GAQL segments with metadata.

    Returns a list of segment field objects with name, category, data_type,
    selectable, filterable, and sortable attributes.
    """
    client = config.get_client()
    service = client.get_service("GoogleAdsFieldService")
    query = "SELECT name, category, data_type, selectable, filterable, sortable WHERE name LIKE 'segments.%'"
    results = service.search_google_ads_fields(query=query)

    fields = []
    for field in results:
        fields.append({
            "name": getattr(field, "name", None),
            "category": getattr(field, "category", None),
            "data_type": getattr(field, "data_type", None),
            "selectable": getattr(field, "selectable", None),
            "filterable": getattr(field, "filterable", None),
            "sortable": getattr(field, "sortable", None),
        })

    return {"success": True, "fields": fields, "count": len(fields)}


def get_metrics_metadata() -> dict:
    """List all available GAQL metrics with metadata.

    Returns a list of metric field objects with name, category, data_type,
    selectable, filterable, and sortable attributes.
    """
    client = config.get_client()
    service = client.get_service("GoogleAdsFieldService")
    query = "SELECT name, category, data_type, selectable, filterable, sortable WHERE name LIKE 'metrics.%'"
    results = service.search_google_ads_fields(query=query)

    fields = []
    for field in results:
        fields.append({
            "name": getattr(field, "name", None),
            "category": getattr(field, "category", None),
            "data_type": getattr(field, "data_type", None),
            "selectable": getattr(field, "selectable", None),
            "filterable": getattr(field, "filterable", None),
            "sortable": getattr(field, "sortable", None),
        })

    return {"success": True, "fields": fields, "count": len(fields)}


def get_resource_metadata(resource_name: str) -> dict:
    """Get all available fields for a specific resource.

    Args:
        resource_name: The resource name to query fields for (e.g., 'campaign', 'ad_group').

    Returns a list of field objects for the specified resource with name, category,
    data_type, selectable, filterable, and sortable attributes.
    """
    # Validate resource_name to prevent GAQL query injection
    is_valid, error_msg = _validate_resource_name(resource_name)
    if not is_valid:
        return {"success": False, "error": error_msg, "fields": [], "count": 0}
    
    client = config.get_client()
    service = client.get_service("GoogleAdsFieldService")
    query = f"SELECT name, category, data_type, selectable, filterable, sortable WHERE name LIKE '{resource_name}.%'"
    results = service.search_google_ads_fields(query=query)

    fields = []
    for field in results:
        fields.append({
            "name": getattr(field, "name", None),
            "category": getattr(field, "category", None),
            "data_type": getattr(field, "data_type", None),
            "selectable": getattr(field, "selectable", None),
            "filterable": getattr(field, "filterable", None),
            "sortable": getattr(field, "sortable", None),
        })

    return {"success": True, "fields": fields, "count": len(fields)}


def register(mcp) -> None:
    mcp.tool(tool_handler(get_segments_metadata))
    mcp.tool(tool_handler(get_metrics_metadata))
    mcp.tool(tool_handler(get_resource_metadata))