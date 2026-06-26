"""Status-change write tools (pause / enable) for campaigns, ad groups, keywords, ads.

Every tool is gated by the mutate safety harness: without ``confirm=True`` it only previews
(validate_only), and the customer must be in ``GOOGLE_ADS_MUTATE_ALLOWLIST`` or the call is
blocked. Confirmed changes are written to the append-only audit log. Status changes are
idempotent (setting a status an entity already has is a no-op on the Google Ads side).
"""

from __future__ import annotations

from .. import config, gaql, mutate
from ..errors import tool_handler

# Per-entity Google Ads API wiring (service / operation type / mutate method / path / status enum).
ENTITIES = {
    "campaign": {
        "service": "CampaignService", "op": "CampaignOperation",
        "mutate": "mutate_campaigns", "path": "campaign_path", "enum": "CampaignStatusEnum",
    },
    "ad_group": {
        "service": "AdGroupService", "op": "AdGroupOperation",
        "mutate": "mutate_ad_groups", "path": "ad_group_path", "enum": "AdGroupStatusEnum",
    },
    "keyword": {
        "service": "AdGroupCriterionService", "op": "AdGroupCriterionOperation",
        "mutate": "mutate_ad_group_criteria", "path": "ad_group_criterion_path",
        "enum": "AdGroupCriterionStatusEnum",
    },
    "ad": {
        "service": "AdGroupAdService", "op": "AdGroupAdOperation",
        "mutate": "mutate_ad_group_ads", "path": "ad_group_ad_path", "enum": "AdGroupAdStatusEnum",
    },
}


def _set_status_update_mask(client, operation, entity) -> None:
    """Populate the operation's update_mask for the 'status' field.

    Uses the official ``protobuf_helpers.field_mask`` pattern (as in every Google Ads sample)
    against the real proto-plus message, and falls back to a direct paths assignment for test
    doubles (which have no ``_pb``). The live path is what the API actually receives.
    """
    pb = getattr(entity, "_pb", None)
    if pb is not None and hasattr(client, "copy_from"):
        from google.api_core import protobuf_helpers

        client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, pb))
    else:
        operation.update_mask.paths.append("status")


def _apply_status(client, entity_key, customer_id, path_ids, target_status, validate_only):
    """Build and send a single status-update operation. The actual Google Ads API call."""
    cfg = ENTITIES[entity_key]
    cid = gaql.normalize_customer_id(customer_id)
    service = client.get_service(cfg["service"])
    operation = client.get_type(cfg["op"])
    entity = operation.update
    entity.resource_name = getattr(service, cfg["path"])(cid, *path_ids)
    entity.status = getattr(getattr(client.enums, cfg["enum"]), target_status)
    _set_status_update_mask(client, operation, entity)
    response = getattr(service, cfg["mutate"])(
        customer_id=cid, operations=[operation], validate_only=validate_only
    )
    return {
        "resource_names": [r.resource_name for r in response.results],
        "validate_only": validate_only,
    }


def _status_tool(entity_key, customer_id, path_ids, target_status, confirm, describe):
    gaql.require_customer_id(customer_id)
    for raw_id in path_ids:
        gaql.require_id("resource id", raw_id)

    def executor(validate_only):
        client = config.get_client()
        return _apply_status(client, entity_key, customer_id, path_ids, target_status, validate_only)

    return mutate.guarded_status_change(
        customer_id=customer_id, describe=describe, target_status=target_status,
        confirm=confirm, executor=executor,
    )


# --- campaign -------------------------------------------------------------
def pause_campaign(customer_id: str, campaign_id: str, confirm: bool = False) -> dict:
    """Pause a campaign. Previews unless confirm=true; customer must be allowlisted."""
    return _status_tool("campaign", customer_id, [campaign_id], "PAUSED", confirm,
                        f"pause campaign {campaign_id}")


def enable_campaign(customer_id: str, campaign_id: str, confirm: bool = False) -> dict:
    """Enable (resume) a campaign. Previews unless confirm=true."""
    return _status_tool("campaign", customer_id, [campaign_id], "ENABLED", confirm,
                        f"enable campaign {campaign_id}")


# --- ad group -------------------------------------------------------------
def pause_ad_group(customer_id: str, ad_group_id: str, confirm: bool = False) -> dict:
    """Pause an ad group. Previews unless confirm=true."""
    return _status_tool("ad_group", customer_id, [ad_group_id], "PAUSED", confirm,
                        f"pause ad_group {ad_group_id}")


def enable_ad_group(customer_id: str, ad_group_id: str, confirm: bool = False) -> dict:
    """Enable an ad group. Previews unless confirm=true."""
    return _status_tool("ad_group", customer_id, [ad_group_id], "ENABLED", confirm,
                        f"enable ad_group {ad_group_id}")


# --- keyword (ad group criterion) -----------------------------------------
def pause_keyword(customer_id: str, ad_group_id: str, criterion_id: str,
                  confirm: bool = False) -> dict:
    """Pause a keyword (ad group criterion). Previews unless confirm=true."""
    return _status_tool("keyword", customer_id, [ad_group_id, criterion_id], "PAUSED", confirm,
                        f"pause keyword {ad_group_id}~{criterion_id}")


def enable_keyword(customer_id: str, ad_group_id: str, criterion_id: str,
                   confirm: bool = False) -> dict:
    """Enable a keyword (ad group criterion). Previews unless confirm=true."""
    return _status_tool("keyword", customer_id, [ad_group_id, criterion_id], "ENABLED", confirm,
                        f"enable keyword {ad_group_id}~{criterion_id}")


# --- ad (ad group ad) -----------------------------------------------------
def pause_ad(customer_id: str, ad_group_id: str, ad_id: str, confirm: bool = False) -> dict:
    """Pause an ad (ad group ad). Previews unless confirm=true."""
    return _status_tool("ad", customer_id, [ad_group_id, ad_id], "PAUSED", confirm,
                        f"pause ad {ad_group_id}~{ad_id}")


def enable_ad(customer_id: str, ad_group_id: str, ad_id: str, confirm: bool = False) -> dict:
    """Enable an ad (ad group ad). Previews unless confirm=true."""
    return _status_tool("ad", customer_id, [ad_group_id, ad_id], "ENABLED", confirm,
                        f"enable ad {ad_group_id}~{ad_id}")


_TOOLS = [
    pause_campaign, enable_campaign,
    pause_ad_group, enable_ad_group,
    pause_keyword, enable_keyword,
    pause_ad, enable_ad,
]


def register(mcp) -> None:
    for fn in _TOOLS:
        mcp.tool(tool_handler(fn))
