"""Account-discovery tools."""

from __future__ import annotations

from .. import config
from ..errors import tool_handler


def list_accessible_customers() -> dict:
    """List the Google Ads customer accounts the credentials can access.

    Returns digit-only customer ids to use as ``customer_id`` for other tools.
    """
    client = config.get_client()
    service = client.get_service("CustomerService")
    response = service.list_accessible_customers()
    ids = [name.split("/")[-1] for name in response.resource_names]
    return {"success": True, "customer_ids": ids, "count": len(ids)}


def register(mcp) -> None:
    mcp.tool(tool_handler(list_accessible_customers))
