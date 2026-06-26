"""Planning and recommendations tools (Phase 5).

Five tools for querying recommendations, applying/dismissing them, generating keyword ideas,
and forecasting metrics. The read-only tools (get_recommendations, generate_keyword_ideas,
get_forecast_metrics) have no gates. The mutation tools (apply_recommendation, dismiss_recommendation)
go through the allowlist/preview/confirm/audit gate.
"""

from __future__ import annotations

import re
import sys

from .. import config, gaql, mutate
from ..errors import tool_handler

_REC_RESOURCE_RE = re.compile(r"^customers/\d+/recommendations/\d+$")


def _require_recommendation_resource(value: str) -> None:
    if not _REC_RESOURCE_RE.match(value):
        raise ValueError(
            f"recommendation_resource_name must match 'customers/CID/recommendations/ID',"
            f" got {value!r}"
        )


# --- read-only tools (no gates) -----------------------------------------------

def get_recommendations(customer_id: str, campaign_id: str | None = None, limit: int = 20) -> dict:
    """Fetch active recommendations for an account or campaign.

    Args:
        customer_id: Customer account ID.
        campaign_id: Optional campaign ID to filter recommendations.
        limit: Max recommendations to return (default 20).

    Returns recommendations with type, campaign, impact metrics, and resource name.
    """
    gaql.require_customer_id(customer_id)
    if campaign_id:
        gaql.require_id("campaign_id", campaign_id)

    client = config.get_client()
    cid = gaql.normalize_customer_id(customer_id)

    query = (
        "SELECT recommendation.type, recommendation.campaign, "
        "recommendation.resource_name "
        "FROM recommendation "
        "WHERE recommendation.dismissed = FALSE"
    )
    if campaign_id:
        query += f" AND recommendation.campaign = 'customers/{cid}/campaigns/{campaign_id}'"

    return gaql.run_search(client, customer_id, query, limit=limit)


def generate_keyword_ideas(
    customer_id: str,
    keywords: list[str] | None = None,
    url: str | None = None,
    language_id: str = "1014",
    location_ids: list[str] | None = None,
    limit: int = 50,
) -> dict:
    """Generate keyword ideas using Google's Keyword Planner.

    Args:
        customer_id: Customer account ID.
        keywords: List of seed keywords (optional if url provided).
        url: Website URL for idea generation (optional if keywords provided).
        language_id: Language constant ID (default 1014 = English).
        location_ids: List of location constant IDs (optional).
        limit: Max ideas to return (default 50, capped at 1000).

    Returns a list of keyword ideas with search volume, competition, and bid estimates.
    """
    gaql.require_customer_id(customer_id)
    if not keywords and not url:
        raise ValueError("provide at least one of keywords or url")

    client = config.get_client()
    cid = gaql.normalize_customer_id(customer_id)
    service = client.get_service("KeywordPlanIdeaService")
    request = client.get_type("GenerateKeywordIdeasRequest")

    gaql.require_id("language_id", language_id)
    if location_ids:
        for loc in location_ids:
            gaql.require_id("location_id", str(loc))

    request.customer_id = cid
    request.language = f"languageConstants/{language_id}"
    if location_ids:
        for loc in location_ids:
            request.geo_target_constants.append(f"geoTargetConstants/{loc}")
    request.include_adult_keywords = False
    request.page_size = min(limit, 1000)

    if keywords:
        request.keyword_seed.keywords.extend(keywords)
    if url:
        request.url_seed.url = url

    response = service.generate_keyword_ideas(request=request)
    ideas = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        ideas.append({
            "text": idea.text,
            "avg_monthly_searches": getattr(metrics, "avg_monthly_searches", None),
            "competition": str(getattr(metrics, "competition", "")),
            "low_top_of_page_bid_micros": getattr(metrics, "low_top_of_page_bid_micros", None),
            "high_top_of_page_bid_micros": getattr(metrics, "high_top_of_page_bid_micros", None),
        })
        if len(ideas) >= limit:
            break

    return {
        "success": True,
        "ideas": ideas,
        "idea_count": len(ideas),
    }


def get_forecast_metrics(customer_id: str, campaign_id: str, limit: int = 10) -> dict:
    """Fetch forecast metrics and bid simulations for a campaign.

    Args:
        customer_id: Customer account ID.
        campaign_id: Campaign ID.
        limit: Max rows to return.

    Returns raw ad_group_criterion_simulation rows (complex nested structure).
    """
    gaql.require_customer_id(customer_id)
    gaql.require_id("campaign_id", campaign_id)

    client = config.get_client()

    query = (
        "SELECT ad_group_criterion_simulation.ad_group_id, "
        "ad_group_criterion_simulation.criterion_id, "
        "ad_group_criterion_simulation.type "
        "FROM ad_group_criterion_simulation "
        f"WHERE campaign.id = {campaign_id} "
        "AND ad_group_criterion_simulation.type = 'CPC_BID'"
    )

    result = gaql.run_search(client, customer_id, query, limit=limit)
    result["note"] = (
        "Bid simulation data; points represent potential performance at different bid levels. "
        "Use these to forecast impact of bid changes."
    )
    return result


# --- gated mutation tools (allowlist + preview + confirm + audit) -----------

def apply_recommendation(
    customer_id: str,
    recommendation_resource_name: str,
    confirm: bool = False,
) -> dict:
    """Apply a recommendation (e.g. add a keyword, raise a bid).

    Args:
        customer_id: Customer account ID (must be in allowlist).
        recommendation_resource_name: Full resource name from get_recommendations.
        confirm: If False, preview only. If True, apply.

    Returns success, applied status, audit log entry (if applied).
    """
    gaql.require_customer_id(customer_id)
    if not recommendation_resource_name:
        raise ValueError("recommendation_resource_name required")
    _require_recommendation_resource(recommendation_resource_name)

    cid = gaql.normalize_customer_id(customer_id)
    client = config.get_client()

    def executor(validate_only):
        service = client.get_service("RecommendationService")
        op = client.get_type("ApplyRecommendationOperation")
        op.resource_name = recommendation_resource_name
        response = service.apply_recommendations(
            customer_id=cid, operations=[op], validate_only=validate_only
        )
        return {
            "resource_names": [r.resource_name for r in response.results],
            "validate_only": validate_only,
        }

    return mutate.guarded_create(
        customer_id=customer_id,
        describe=f"apply recommendation {recommendation_resource_name}",
        entities=[{"resource_name": recommendation_resource_name}],
        confirm=confirm,
        executor=executor,
    )


def dismiss_recommendation(
    customer_id: str,
    recommendation_resource_name: str,
    confirm: bool = False,
) -> dict:
    """Dismiss a recommendation (mark as not applicable).

    Note: The Google Ads API does not support validate_only for dismiss, so preview
    returns the intent without calling the API.

    Args:
        customer_id: Customer account ID (must be in allowlist).
        recommendation_resource_name: Full resource name from get_recommendations.
        confirm: If False, preview only. If True, dismiss.

    Returns success, applied status, audit log entry (if applied).
    """
    gaql.require_customer_id(customer_id)
    if not recommendation_resource_name:
        raise ValueError("recommendation_resource_name required")
    _require_recommendation_resource(recommendation_resource_name)

    norm = gaql.normalize_customer_id(customer_id)
    if not mutate.is_allowed(norm):
        return {
            "success": False,
            "blocked": True,
            "applied": False,
            "error": (
                f"customer_id {norm} is not in the mutate allowlist "
                "(set GOOGLE_ADS_MUTATE_ALLOWLIST). No change made."
            ),
        }

    if not confirm:
        return {
            "success": True,
            "applied": False,
            "preview": True,
            "would": f"dismiss recommendation {recommendation_resource_name}",
            "entities": [{"resource_name": recommendation_resource_name}],
            "message": "Preview only. Re-call with confirm=true to dismiss.",
        }

    client = config.get_client()
    service = client.get_service("RecommendationService")
    request = client.get_type("DismissRecommendationRequest")
    request.customer_id = norm
    op = client.get_type("DismissRecommendationOperation")
    op.resource_name = recommendation_resource_name
    request.operations.append(op)

    result = service.dismiss_recommendations(request=request)
    dismissed = getattr(result, "results", None)
    if not dismissed:
        raise ValueError(
            "dismiss_recommendations returned no results — recommendation may not have been dismissed"
        )
    response = {
        "success": True,
        "applied": True,
        "audit_logged": True,
        "result": {
            "resource_names": [r.resource_name for r in dismissed],
        },
    }

    try:
        mutate.audit({
            "customer_id": norm,
            "action": f"dismiss recommendation {recommendation_resource_name}",
            "result": response.get("result", {}),
            "entities": [{"resource_name": recommendation_resource_name}],
        })
    except Exception as exc:
        response["audit_logged"] = False
        response["warning"] = f"Dismiss was APPLIED but audit log write failed: {exc}"
        print(
            f"CRITICAL: dismiss applied for customer {norm} "
            f"but audit log write failed: {exc}",
            file=sys.stderr,
            flush=True,
        )

    return response


_TOOLS = [
    get_recommendations,
    apply_recommendation,
    generate_keyword_ideas,
    get_forecast_metrics,
    dismiss_recommendation,
]


def register(mcp) -> None:
    for fn in _TOOLS:
        mcp.tool(tool_handler(fn))
