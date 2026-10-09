"""Negative keyword tools: list, and add at campaign or ad-group level.

Adds go through the same allowlist / preview / confirm / audit harness as the other creation
tools. A single call is capped at ``MAX_NEGATIVES_PER_CALL`` keywords so one bad prompt cannot
block a large share of traffic.
"""

from __future__ import annotations

import re

from .. import config, gaql, mutate
from ..errors import tool_handler

MAX_NEGATIVES_PER_CALL = 50
MAX_KEYWORD_CHARS = 80
MAX_KEYWORD_WORDS = 10

# Characters the API rejects in keyword text; match type is set separately, so brackets and
# quotes are not accepted either.
_INVALID_CHARS = re.compile(r'[!@%^()={};~`<>?\\|,"\[\]]')


def clean_keywords(keywords: list[str]) -> list[str]:
    """Trim, validate and de-duplicate (case-insensitive) negative keyword texts."""
    if not isinstance(keywords, list) or not keywords:
        raise ValueError("keywords must be a non-empty list of strings")

    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in keywords:
        text = " ".join(str(raw).split())
        if not text:
            raise ValueError("keywords must not contain empty strings")
        if len(text) > MAX_KEYWORD_CHARS:
            raise ValueError(f"keyword exceeds {MAX_KEYWORD_CHARS} chars: {text!r}")
        if len(text.split()) > MAX_KEYWORD_WORDS:
            raise ValueError(f"keyword exceeds {MAX_KEYWORD_WORDS} words: {text!r}")
        if _INVALID_CHARS.search(text):
            raise ValueError(
                f"keyword contains characters Google Ads rejects (set match_type instead of "
                f"quotes/brackets): {text!r}"
            )
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            cleaned.append(text)

    if len(cleaned) > MAX_NEGATIVES_PER_CALL:
        raise ValueError(
            f"at most {MAX_NEGATIVES_PER_CALL} negative keywords per call, got {len(cleaned)}"
        )
    return cleaned


def list_negative_keywords(
    customer_id: str,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    limit: int = 1000,
) -> dict:
    """List negative keywords at campaign level, or at ad-group level when ad_group_id is set.

    Args:
        customer_id: Google Ads customer id (digits only; hyphens are stripped).
        campaign_id: Optional campaign id to filter campaign-level negatives.
        ad_group_id: If set, list that ad group's negatives instead of campaign-level ones.
        limit: max rows returned (hard-capped at 10,000 by the API).

    Returns ``{success, rows, row_count, is_truncated}``.
    """
    gaql.require_customer_id(customer_id)
    limit = int(limit)
    client = config.get_client()

    if ad_group_id is not None:
        gaql.require_id("ad_group_id", ad_group_id)
        query = (
            "SELECT ad_group.id, ad_group.name, ad_group_criterion.criterion_id, "
            "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type "
            "FROM ad_group_criterion "
            "WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = TRUE "
            f"AND ad_group.id = {ad_group_id}"
        )
    else:
        query = (
            "SELECT campaign.id, campaign.name, campaign_criterion.criterion_id, "
            "campaign_criterion.keyword.text, campaign_criterion.keyword.match_type "
            "FROM campaign_criterion "
            "WHERE campaign_criterion.type = 'KEYWORD' AND campaign_criterion.negative = TRUE"
        )
        if campaign_id is not None:
            gaql.require_id("campaign_id", campaign_id)
            query += f" AND campaign.id = {campaign_id}"
    query += f" LIMIT {limit}"

    return gaql.run_search(client, customer_id, query, limit)


def _add_negatives(*, level, customer_id, parent_id, keywords, match_type, confirm) -> dict:
    gaql.require_customer_id(customer_id)
    gaql.require_id(f"{level}_id", parent_id)
    texts = clean_keywords(keywords)
    match = gaql.require_enum("match_type", match_type, gaql.KEYWORD_MATCH_TYPES)

    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()

    if level == "campaign":
        service_name, op_name = "CampaignCriterionService", "CampaignCriterionOperation"
        mutate_method, parent_field = "mutate_campaign_criteria", "campaign"
        parent_resource = f"customers/{cid}/campaigns/{parent_id}"
    else:
        service_name, op_name = "AdGroupCriterionService", "AdGroupCriterionOperation"
        mutate_method, parent_field = "mutate_ad_group_criteria", "ad_group"
        parent_resource = f"customers/{cid}/adGroups/{parent_id}"

    def executor(validate_only):
        service = client.get_service(service_name)
        operations = []
        for text in texts:
            operation = client.get_type(op_name)
            criterion = operation.create
            setattr(criterion, parent_field, parent_resource)
            criterion.negative = True
            criterion.keyword.text = text
            criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match)
            operations.append(operation)

        response = mutate.send_mutate(
            client, service, mutate_method, cid, operations, validate_only
        )
        return {
            "resource_names": [r.resource_name for r in response.results],
            "validate_only": validate_only,
        }

    return mutate.guarded_create(
        customer_id=customer_id,
        describe=f"add {len(texts)} {match} negative keyword(s) to {level} {parent_id}",
        entities=[{"type": f"{level}_negative_keyword", "text": t, "match_type": match}
                  for t in texts],
        confirm=confirm,
        executor=executor,
    )


def add_campaign_negative_keywords(
    customer_id: str,
    campaign_id: str,
    keywords: list[str],
    match_type: str = "PHRASE",
    confirm: bool = False,
) -> dict:
    """Add negative keywords to a campaign. Previews unless confirm=true; customer must be allowlisted.

    Args:
        customer_id: Customer account ID (digits, hyphens allowed).
        campaign_id: Campaign to add the negatives to.
        keywords: Plain keyword texts (no quotes or brackets); up to 50 per call.
        match_type: One of BROAD, PHRASE, EXACT (default PHRASE).
        confirm: If False (default), validate only. If True, apply and write the audit log.
    """
    return _add_negatives(level="campaign", customer_id=customer_id, parent_id=campaign_id,
                          keywords=keywords, match_type=match_type, confirm=confirm)


def add_ad_group_negative_keywords(
    customer_id: str,
    ad_group_id: str,
    keywords: list[str],
    match_type: str = "PHRASE",
    confirm: bool = False,
) -> dict:
    """Add negative keywords to an ad group. Previews unless confirm=true; customer must be allowlisted.

    Args:
        customer_id: Customer account ID (digits, hyphens allowed).
        ad_group_id: Ad group to add the negatives to.
        keywords: Plain keyword texts (no quotes or brackets); up to 50 per call.
        match_type: One of BROAD, PHRASE, EXACT (default PHRASE).
        confirm: If False (default), validate only. If True, apply and write the audit log.
    """
    return _add_negatives(level="ad_group", customer_id=customer_id, parent_id=ad_group_id,
                          keywords=keywords, match_type=match_type, confirm=confirm)


_TOOLS = [list_negative_keywords, add_campaign_negative_keywords, add_ad_group_negative_keywords]


def register(mcp) -> None:
    for fn in _TOOLS:
        mcp.tool(tool_handler(fn))
