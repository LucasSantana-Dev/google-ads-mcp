"""Bid and budget write tools (Phase 3).

Same gated pattern as the status writes, plus a percent-change cap: a single change exceeding
the configured fraction of the current value is blocked. Defaults: bid 25%, budget 20%,
overridable via GOOGLE_ADS_MAX_BID_CHANGE_PCT / GOOGLE_ADS_MAX_BUDGET_CHANGE_PCT.

Amounts are in micros (1 currency unit = 1,000,000 micros), matching the Google Ads API.
"""

from __future__ import annotations

from .. import config, gaql, mutate
from ..errors import tool_handler

BID_CAP_ENV = "GOOGLE_ADS_MAX_BID_CHANGE_PCT"
BUDGET_CAP_ENV = "GOOGLE_ADS_MAX_BUDGET_CHANGE_PCT"


def _read_one(client, customer_id: str, query: str) -> dict | None:
    """Run a single-row read and return the first row dict (or None)."""
    result = gaql.run_search(client, customer_id, query, limit=1)
    rows = result.get("rows") or []
    return rows[0] if rows else None


def _dig(row, *paths):
    """Return the first value reachable by one of the key paths.

    Tries multiple key paths so it tolerates either snake_case or camelCase response keys:
    ``row_to_dict`` forces snake_case, but the camelCase paths are belt-and-suspenders insurance
    against a serialization difference across Google Ads API/proto-plus versions.
    """
    if not isinstance(row, dict):
        return None
    for path in paths:
        cur = row
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                cur = None
                break
        if cur is not None:
            return cur
    return None


def _apply_value(client, cid, service_name, op_type, mutate_method, path_method, path_ids,
                 field, value, validate_only):
    """Build and send a single value-update operation. The actual Google Ads API call."""
    service = client.get_service(service_name)
    operation = client.get_type(op_type)
    entity = operation.update
    entity.resource_name = getattr(service, path_method)(cid, *path_ids)
    setattr(entity, field, value)
    mutate.set_update_mask(client, operation, entity, field)
    response = getattr(service, mutate_method)(
        customer_id=cid, operations=[operation], validate_only=validate_only
    )
    return {
        "resource_names": [r.resource_name for r in response.results],
        "validate_only": validate_only,
    }


def update_keyword_bid(customer_id: str, ad_group_id: str, criterion_id: str,
                       cpc_bid_micros: int, confirm: bool = False) -> dict:
    """Set a keyword's max CPC bid (micros). Previews unless confirm=true; change is capped."""
    gaql.require_customer_id(customer_id)
    gaql.require_id("ad_group_id", ad_group_id)
    gaql.require_id("criterion_id", criterion_id)
    new_value = int(cpc_bid_micros)
    cap = mutate.max_change_fraction(BID_CAP_ENV, mutate.DEFAULT_MAX_BID_CHANGE)
    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()
    row = _read_one(
        client, customer_id,
        f"SELECT ad_group_criterion.cpc_bid_micros FROM ad_group_criterion "
        f"WHERE ad_group.id = {ad_group_id} AND ad_group_criterion.criterion_id = {criterion_id}",
    )
    current = _dig(row, ("ad_group_criterion", "cpc_bid_micros"), ("adGroupCriterion", "cpcBidMicros"))
    current = int(current) if current is not None else None

    def executor(validate_only):
        return _apply_value(
            client, cid, "AdGroupCriterionService", "AdGroupCriterionOperation",
            "mutate_ad_group_criteria", "ad_group_criterion_path", [ad_group_id, criterion_id],
            "cpc_bid_micros", new_value, validate_only,
        )

    return mutate.guarded_value_change(
        customer_id=customer_id,
        describe=f"set keyword {ad_group_id}~{criterion_id} cpc_bid to {new_value} micros",
        field="cpc_bid_micros", current_value=current, new_value=new_value,
        max_change_fraction=cap, confirm=confirm, executor=executor,
    )


def update_ad_group_bid(customer_id: str, ad_group_id: str, cpc_bid_micros: int,
                        confirm: bool = False) -> dict:
    """Set an ad group's default max CPC bid (micros). Previews unless confirm=true; capped."""
    gaql.require_customer_id(customer_id)
    gaql.require_id("ad_group_id", ad_group_id)
    new_value = int(cpc_bid_micros)
    cap = mutate.max_change_fraction(BID_CAP_ENV, mutate.DEFAULT_MAX_BID_CHANGE)
    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()
    row = _read_one(
        client, customer_id,
        f"SELECT ad_group.cpc_bid_micros FROM ad_group WHERE ad_group.id = {ad_group_id}",
    )
    current = _dig(row, ("ad_group", "cpc_bid_micros"), ("adGroup", "cpcBidMicros"))
    current = int(current) if current is not None else None

    def executor(validate_only):
        return _apply_value(
            client, cid, "AdGroupService", "AdGroupOperation", "mutate_ad_groups",
            "ad_group_path", [ad_group_id], "cpc_bid_micros", new_value, validate_only,
        )

    return mutate.guarded_value_change(
        customer_id=customer_id,
        describe=f"set ad_group {ad_group_id} cpc_bid to {new_value} micros",
        field="cpc_bid_micros", current_value=current, new_value=new_value,
        max_change_fraction=cap, confirm=confirm, executor=executor,
    )


def update_campaign_budget(customer_id: str, campaign_id: str, amount_micros: int,
                           confirm: bool = False) -> dict:
    """Set a campaign's daily budget (micros). Previews unless confirm=true; change is capped.

    Resolves the campaign's shared budget resource first, then mutates it.
    """
    gaql.require_customer_id(customer_id)
    gaql.require_id("campaign_id", campaign_id)
    new_value = int(amount_micros)
    cap = mutate.max_change_fraction(BUDGET_CAP_ENV, mutate.DEFAULT_MAX_BUDGET_CHANGE)
    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()
    row = _read_one(
        client, customer_id,
        f"SELECT campaign_budget.id, campaign_budget.amount_micros "
        f"FROM campaign WHERE campaign.id = {campaign_id}",
    )
    budget_id = _dig(row, ("campaign_budget", "id"), ("campaignBudget", "id"))
    current = _dig(row, ("campaign_budget", "amount_micros"), ("campaignBudget", "amountMicros"))
    current = int(current) if current is not None else None
    if budget_id is None:
        return {"success": False, "applied": False,
                "error": f"no campaign_budget found for campaign {campaign_id}"}

    def executor(validate_only):
        return _apply_value(
            client, cid, "CampaignBudgetService", "CampaignBudgetOperation",
            "mutate_campaign_budgets", "campaign_budget_path", [budget_id],
            "amount_micros", new_value, validate_only,
        )

    return mutate.guarded_value_change(
        customer_id=customer_id,
        describe=f"set campaign {campaign_id} budget to {new_value} micros (budget {budget_id})",
        field="amount_micros", current_value=current, new_value=new_value,
        max_change_fraction=cap, confirm=confirm, executor=executor,
    )


_TOOLS = [update_keyword_bid, update_ad_group_bid, update_campaign_budget]


def register(mcp) -> None:
    for fn in _TOOLS:
        mcp.tool(tool_handler(fn))
