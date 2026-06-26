"""Entity creation tools (Phase 4).

Four tools for creating campaigns, ad groups, keywords, and ads. All default to PAUSED status
(except keywords, which are ENABLED) and are gated by the same allowlist/preview/confirm/audit
harness as Phase 2/3 writes.
"""

from __future__ import annotations

from .. import config, gaql, mutate
from ..errors import tool_handler


def create_campaign(
    customer_id: str,
    name: str,
    budget_amount_micros: int,
    advertising_channel_type: str = "SEARCH",
    confirm: bool = False,
) -> dict:
    """Create a new campaign (paused by default).

    Args:
        customer_id: Customer account ID (digits, hyphens allowed).
        name: Campaign name (max 255 chars).
        budget_amount_micros: Daily budget in micros.
        advertising_channel_type: One of SEARCH, DISPLAY, SHOPPING, VIDEO, PERFORMANCE_MAX.
        confirm: If False (default), preview only. If True, apply the change.

    Returns a dict with campaign and budget resource names (if confirmed), or a preview.
    """
    gaql.require_customer_id(customer_id)
    if not name or len(name) > 255:
        raise ValueError(f"name must be 1-255 chars, got {len(name) if name else 0}")
    budget_amount_micros = int(budget_amount_micros)
    if budget_amount_micros <= 0:
        raise ValueError(f"budget_amount_micros must be > 0, got {budget_amount_micros}")
    channel_type = gaql.require_enum(
        "advertising_channel_type", advertising_channel_type,
        {"SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "PERFORMANCE_MAX"}
    )

    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()

    def executor(validate_only):
        service = client.get_service("GoogleAdsService")
        budget_op = client.get_type("MutateOperation")
        budget_op.campaign_budget_operation.create.name = name
        budget_op.campaign_budget_operation.create.amount_micros = budget_amount_micros
        budget_op.campaign_budget_operation.create.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget_op.campaign_budget_operation.create.explicitly_shared = False
        budget_op.campaign_budget_operation.create.resource_name = f"customers/{cid}/campaignBudgets/-1"

        campaign_op = client.get_type("MutateOperation")
        campaign_op.campaign_operation.create.name = name
        campaign_op.campaign_operation.create.status = client.enums.CampaignStatusEnum.PAUSED
        campaign_op.campaign_operation.create.campaign_budget = f"customers/{cid}/campaignBudgets/-1"
        campaign_op.campaign_operation.create.advertising_channel_type = getattr(
            client.enums.AdvertisingChannelTypeEnum, channel_type
        )
        campaign_op.campaign_operation.create.manual_cpc.enhanced_cpc_enabled = False
        campaign_op.campaign_operation.create.resource_name = f"customers/{cid}/campaigns/-2"

        response = service.mutate(
            customer_id=cid, mutate_operations=[budget_op, campaign_op], validate_only=validate_only
        )
        return {
            "budget_resource_name": response.mutate_operation_responses[0].campaign_budget_result.resource_name,
            "campaign_resource_name": response.mutate_operation_responses[1].campaign_result.resource_name,
            "validate_only": validate_only,
        }

    return mutate.guarded_create(
        customer_id=customer_id,
        describe=f"create campaign {name}",
        entities=[{"type": "campaign", "name": name}],
        confirm=confirm,
        executor=executor,
    )


def create_ad_group(
    customer_id: str,
    campaign_id: str,
    name: str,
    cpc_bid_micros: int | None = None,
    confirm: bool = False,
) -> dict:
    """Create a new ad group (paused by default).

    Args:
        customer_id: Customer account ID.
        campaign_id: Campaign ID to attach to.
        name: Ad group name.
        cpc_bid_micros: Optional default CPC bid.
        confirm: If False (default), preview only.

    Returns a dict with the created ad group resource name, or a preview.
    """
    gaql.require_customer_id(customer_id)
    gaql.require_id("campaign_id", campaign_id)
    if not name or len(name) > 255:
        raise ValueError(f"name must be 1-255 chars, got {len(name) if name else 0}")
    if cpc_bid_micros is not None:
        cpc_bid_micros = int(cpc_bid_micros)

    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()

    def executor(validate_only):
        service = client.get_service("AdGroupService")
        operation = client.get_type("AdGroupOperation")
        op = operation.ad_group_operation.create
        op.name = name
        op.campaign = f"customers/{cid}/campaigns/{campaign_id}"
        op.status = client.enums.AdGroupStatusEnum.PAUSED
        if cpc_bid_micros is not None:
            op.cpc_bid_micros = cpc_bid_micros
        operation.resource_name = f"customers/{cid}/adGroups/-1"

        response = service.mutate_ad_groups(
            customer_id=cid, operations=[operation], validate_only=validate_only
        )
        return {
            "resource_names": [r.resource_name for r in response.results],
            "validate_only": validate_only,
        }

    return mutate.guarded_create(
        customer_id=customer_id,
        describe=f"create ad group {name}",
        entities=[{"type": "ad_group", "name": name}],
        confirm=confirm,
        executor=executor,
    )


def create_keyword(
    customer_id: str,
    ad_group_id: str,
    keyword_text: str,
    match_type: str = "BROAD",
    cpc_bid_micros: int | None = None,
    confirm: bool = False,
) -> dict:
    """Create a new keyword (enabled by default).

    Args:
        customer_id: Customer account ID.
        ad_group_id: Ad group ID to attach to.
        keyword_text: Keyword text (max 80 chars).
        match_type: One of BROAD, PHRASE, EXACT (default: BROAD).
        cpc_bid_micros: Optional CPC bid override.
        confirm: If False (default), preview only.

    Returns a dict with the created keyword resource name, or a preview.
    """
    gaql.require_customer_id(customer_id)
    gaql.require_id("ad_group_id", ad_group_id)
    if not keyword_text or len(keyword_text) > 80:
        raise ValueError(f"keyword_text must be 1-80 chars, got {len(keyword_text) if keyword_text else 0}")
    match = gaql.require_enum("match_type", match_type, gaql.KEYWORD_MATCH_TYPES)
    if cpc_bid_micros is not None:
        cpc_bid_micros = int(cpc_bid_micros)

    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()

    def executor(validate_only):
        service = client.get_service("AdGroupCriterionService")
        operation = client.get_type("AdGroupCriterionOperation")
        op = operation.ad_group_criterion_operation.create
        op.ad_group = f"customers/{cid}/adGroups/{ad_group_id}"
        op.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        op.keyword.text = keyword_text
        op.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match)
        if cpc_bid_micros is not None:
            op.cpc_bid_micros = cpc_bid_micros
        operation.resource_name = f"customers/{cid}/adGroupCriteria/{ad_group_id}~-1"

        response = service.mutate_ad_group_criteria(
            customer_id=cid, operations=[operation], validate_only=validate_only
        )
        return {
            "resource_names": [r.resource_name for r in response.results],
            "validate_only": validate_only,
        }

    return mutate.guarded_create(
        customer_id=customer_id,
        describe=f"create keyword {keyword_text}",
        entities=[{"type": "keyword", "text": keyword_text, "match_type": match}],
        confirm=confirm,
        executor=executor,
    )


def create_ad(
    customer_id: str,
    ad_group_id: str,
    headlines: list,
    descriptions: list,
    final_urls: list,
    confirm: bool = False,
) -> dict:
    """Create a new responsive search ad (paused by default).

    Args:
        customer_id: Customer account ID.
        ad_group_id: Ad group ID to attach to.
        headlines: List of 3-15 headline strings (each max 30 chars).
        descriptions: List of 2-4 description strings (each max 90 chars).
        final_urls: List of 1+ destination URLs.
        confirm: If False (default), preview only.

    Returns a dict with the created ad resource name, or a preview.
    """
    gaql.require_customer_id(customer_id)
    gaql.require_id("ad_group_id", ad_group_id)

    if not headlines or len(headlines) < 3 or len(headlines) > 15:
        raise ValueError(f"headlines must be 3-15 items, got {len(headlines)}")
    for i, h in enumerate(headlines):
        if not h or len(h) > 30:
            raise ValueError(f"headline {i} must be 1-30 chars, got {len(h) if h else 0}")

    if not descriptions or len(descriptions) < 2 or len(descriptions) > 4:
        raise ValueError(f"descriptions must be 2-4 items, got {len(descriptions)}")
    for i, d in enumerate(descriptions):
        if not d or len(d) > 90:
            raise ValueError(f"description {i} must be 1-90 chars, got {len(d) if d else 0}")

    if not final_urls or len(final_urls) < 1:
        raise ValueError("final_urls must have at least 1 URL")

    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()

    def executor(validate_only):
        service = client.get_service("AdGroupAdService")
        operation = client.get_type("AdGroupAdOperation")
        op = operation.ad_group_ad_operation.create
        op.ad_group = f"customers/{cid}/adGroups/{ad_group_id}"
        op.status = client.enums.AdGroupAdStatusEnum.PAUSED

        rsa = op.ad.responsive_search_ad
        for h in headlines:
            asset = client.get_type("AdTextAsset")
            asset.text = h
            rsa.headlines.append(asset)
        for d in descriptions:
            asset = client.get_type("AdTextAsset")
            asset.text = d
            rsa.descriptions.append(asset)

        for url in final_urls:
            op.ad.final_urls.append(url)

        response = service.mutate_ad_group_ads(
            customer_id=cid, operations=[operation], validate_only=validate_only
        )
        return {
            "resource_names": [r.resource_name for r in response.results],
            "validate_only": validate_only,
        }

    return mutate.guarded_create(
        customer_id=customer_id,
        describe=f"create ad with {len(headlines)} headlines",
        entities=[{"type": "ad", "headlines": headlines, "descriptions": descriptions}],
        confirm=confirm,
        executor=executor,
    )


_TOOLS = [create_campaign, create_ad_group, create_keyword, create_ad]


def register(mcp) -> None:
    for fn in _TOOLS:
        mcp.tool(tool_handler(fn))
