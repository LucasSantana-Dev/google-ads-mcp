"""Tests for the negative keyword tools.

The add tools are exercised against the real google-ads proto types (not the loose fakes), so a
wrong field name on an operation fails here instead of against the live API.
"""

import importlib
import json
from types import SimpleNamespace

import pytest

from google_ads_mcp import GOOGLE_ADS_API_VERSION
from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import negatives as n

ALLOW = "1234567890"


def _proto(module: str, name: str):
    return getattr(importlib.import_module(f"google.ads.googleads.{GOOGLE_ADS_API_VERSION}.{module}"), name)


class _Service:
    """Mirrors the real client: mutate_* takes a request message (no validate_only keyword)."""

    def __init__(self, calls):
        self._calls = calls

    def _mutate(self, method, request):
        self._calls.append(SimpleNamespace(
            method=method, customer_id=request.customer_id,
            operations=list(request.operations), validate_only=request.validate_only,
        ))
        return SimpleNamespace(
            results=[SimpleNamespace(resource_name=f"customers/{request.customer_id}/criteria/{i}")
                     for i, _ in enumerate(request.operations)]
        )

    def mutate_campaign_criteria(self, request=None):
        return self._mutate("mutate_campaign_criteria", request)

    def mutate_ad_group_criteria(self, request=None):
        return self._mutate("mutate_ad_group_criteria", request)


class RealTypeClient:
    """Real operation protos and enums, recording service that captures what would be sent."""

    def __init__(self):
        self.calls = []
        match_enum = _proto("enums.types.keyword_match_type", "KeywordMatchTypeEnum")
        self.enums = SimpleNamespace(KeywordMatchTypeEnum=match_enum.KeywordMatchType)
        self._ops = {
            "CampaignCriterionOperation": _proto(
                "services.types.campaign_criterion_service", "CampaignCriterionOperation"),
            "AdGroupCriterionOperation": _proto(
                "services.types.ad_group_criterion_service", "AdGroupCriterionOperation"),
            "MutateCampaignCriteriaRequest": _proto(
                "services.types.campaign_criterion_service", "MutateCampaignCriteriaRequest"),
            "MutateAdGroupCriteriaRequest": _proto(
                "services.types.ad_group_criterion_service", "MutateAdGroupCriteriaRequest"),
        }

    def get_service(self, name):
        return _Service(self.calls)

    def get_type(self, name):
        return self._ops[name]()


def _wire(monkeypatch, client, *, allow=ALLOW, audit=None):
    monkeypatch.setattr(n.config, "get_client", lambda: client)
    if allow is None:
        monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", allow)
    if audit is not None:
        monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(audit))


# --- clean_keywords -------------------------------------------------------

def test_clean_keywords_trims_and_dedupes_case_insensitively():
    assert n.clean_keywords([" Beauty  Salon ", "beauty salon", "facials"]) == [
        "Beauty Salon", "facials"]


@pytest.mark.parametrize("bad", ['"quoted"', "[exact]", "50% off", "a, b", "x" * 81,
                                 " ".join(["w"] * 11), ""])
def test_clean_keywords_rejects_invalid(bad):
    with pytest.raises(ValueError):
        n.clean_keywords([bad])


def test_clean_keywords_rejects_empty_list_and_too_many():
    with pytest.raises(ValueError):
        n.clean_keywords([])
    with pytest.raises(ValueError, match="at most"):
        n.clean_keywords([f"kw{i}" for i in range(n.MAX_NEGATIVES_PER_CALL + 1)])


# --- add tools ------------------------------------------------------------

def test_campaign_preview_sends_validate_only_with_real_protos(monkeypatch):
    client = RealTypeClient()
    _wire(monkeypatch, client)
    out = n.add_campaign_negative_keywords(ALLOW, "111", ["beauty salons", "facials"])
    assert out["preview"] is True and out["applied"] is False
    call = client.calls[-1]
    assert call.method == "mutate_campaign_criteria" and call.validate_only is True
    crit = call.operations[0].create
    assert crit.campaign == f"customers/{ALLOW}/campaigns/111"
    assert crit.negative is True
    assert crit.keyword.text == "beauty salons"
    assert crit.keyword.match_type == client.enums.KeywordMatchTypeEnum.PHRASE
    assert [op.create.keyword.text for op in call.operations] == ["beauty salons", "facials"]


def test_campaign_confirm_applies_and_audits(monkeypatch, tmp_path):
    client = RealTypeClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, client, audit=log)
    out = n.add_campaign_negative_keywords(ALLOW, "111", ["facials"], match_type="EXACT",
                                           confirm=True)
    assert out["applied"] is True and client.calls[-1].validate_only is False
    assert client.calls[-1].operations[0].create.keyword.match_type == \
        client.enums.KeywordMatchTypeEnum.EXACT
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["action"] == "add 1 EXACT negative keyword(s) to campaign 111"


def test_ad_group_uses_ad_group_criterion_service(monkeypatch):
    client = RealTypeClient()
    _wire(monkeypatch, client)
    n.add_ad_group_negative_keywords(ALLOW, "222", ["curso"])
    call = client.calls[-1]
    assert call.method == "mutate_ad_group_criteria"
    crit = call.operations[0].create
    assert crit.ad_group == f"customers/{ALLOW}/adGroups/222"
    assert crit.negative is True and crit.keyword.text == "curso"


def test_blocked_when_not_allowlisted(monkeypatch):
    client = RealTypeClient()
    _wire(monkeypatch, client, allow=None)
    out = n.add_campaign_negative_keywords(ALLOW, "111", ["facials"], confirm=True)
    assert out["blocked"] is True and client.calls == []


def test_invalid_inputs_raise_before_any_call(monkeypatch):
    client = RealTypeClient()
    _wire(monkeypatch, client)
    with pytest.raises(ValueError):
        n.add_campaign_negative_keywords(ALLOW, "abc", ["facials"])
    with pytest.raises(ValueError):
        n.add_campaign_negative_keywords(ALLOW, "111", ["facials"], match_type="LOOSE")
    assert client.calls == []


# --- list tool ------------------------------------------------------------

def _capture_query(monkeypatch):
    seen = {}

    def fake_run_search(client, customer_id, query, limit):
        seen["query"] = query
        return {"success": True, "rows": [], "row_count": 0, "is_truncated": False}

    monkeypatch.setattr(n.gaql, "run_search", fake_run_search)
    monkeypatch.setattr(n.config, "get_client", lambda: FakeGoogleAdsClient())
    return seen


def test_list_campaign_level_query(monkeypatch):
    seen = _capture_query(monkeypatch)
    n.list_negative_keywords(ALLOW, campaign_id="111")
    q = seen["query"]
    assert "FROM campaign_criterion" in q and "negative = TRUE" in q and "campaign.id = 111" in q


def test_list_ad_group_level_query(monkeypatch):
    seen = _capture_query(monkeypatch)
    n.list_negative_keywords(ALLOW, ad_group_id="222")
    q = seen["query"]
    assert "FROM ad_group_criterion" in q and "ad_group.id = 222" in q


def test_list_rejects_non_numeric_ids(monkeypatch):
    _capture_query(monkeypatch)
    with pytest.raises(ValueError):
        n.list_negative_keywords(ALLOW, campaign_id="1 OR 1=1")
