"""Tests that build real google-ads protos (offline) so wrong field names or call shapes fail here.

The loose fakes in ``testing.py`` accept any keyword argument, which hid the fact that the real
``mutate_*`` methods only take ``customer_id`` and ``operations`` as keywords (``validate_only``
has to be sent inside the request message).
"""

from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials

from google_ads_mcp import GOOGLE_ADS_API_VERSION, mutate
from google_ads_mcp.tools import creates, writes_status, writes_value

ALLOW = "1234567890"


class _Svc:
    """Mirrors the real services: mutate_* takes request= only."""

    def __init__(self, calls):
        self._calls = calls

    def __getattr__(self, name):
        if name.endswith("_path"):
            collection = {"campaign_path": "campaigns", "ad_group_path": "adGroups",
                          "ad_group_criterion_path": "adGroupCriteria",
                          "ad_group_ad_path": "adGroupAds",
                          "campaign_budget_path": "campaignBudgets"}[name]
            return lambda cid, *ids: f"customers/{cid}/{collection}/" + "~".join(map(str, ids))
        if name.startswith("mutate_"):
            def _call(request=None):
                self._calls.append((name, request))
                return SimpleNamespace(
                    results=[SimpleNamespace(resource_name=f"r/{i}")
                             for i, _ in enumerate(request.operations)])
            return _call
        raise AttributeError(name)


class RealClient:
    def __init__(self):
        self.calls = []
        self._real = GoogleAdsClient(
            credentials=AnonymousCredentials(), version=GOOGLE_ADS_API_VERSION,
            use_proto_plus=True)
        self.enums = self._real.enums

    def get_type(self, name):
        return self._real.get_type(name)

    def copy_from(self, destination, source):
        return self._real.copy_from(destination, source)

    def get_service(self, name):
        return _Svc(self.calls)


@pytest.fixture
def client(monkeypatch, tmp_path):
    c = RealClient()
    for module in (writes_status, writes_value, creates):
        monkeypatch.setattr(module.config, "get_client", lambda c=c: c)
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", ALLOW)
    monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    return c


def test_request_type_name():
    assert mutate.request_type_name("mutate_ad_groups") == "MutateAdGroupsRequest"
    assert mutate.request_type_name("mutate_ad_group_criteria") == "MutateAdGroupCriteriaRequest"


def test_pause_ad_group_sends_real_request(client):
    out = writes_status.pause_ad_group(ALLOW, "222", confirm=True)
    assert out["applied"] is True
    name, request = client.calls[-1]
    assert name == "mutate_ad_groups" and request.validate_only is False
    op = request.operations[0]
    assert op.update.resource_name == f"customers/{ALLOW}/adGroups/222"
    assert op.update.status == client.enums.AdGroupStatusEnum.PAUSED
    assert "status" in op.update_mask.paths


def test_pause_ad_group_preview_is_validate_only(client):
    out = writes_status.pause_ad_group(ALLOW, "222")
    assert out["preview"] is True
    assert client.calls[-1][1].validate_only is True


def test_create_keyword_uses_real_operation_shape(client):
    out = creates.create_keyword(ALLOW, "222", "lip blush braga", "PHRASE", confirm=True)
    assert out["applied"] is True
    crit = client.calls[-1][1].operations[0].create
    assert crit.ad_group == f"customers/{ALLOW}/adGroups/222"
    assert crit.keyword.text == "lip blush braga"
    assert crit.keyword.match_type == client.enums.KeywordMatchTypeEnum.PHRASE


def test_budget_update_uses_request_message(client, monkeypatch):
    monkeypatch.setattr(
        writes_value, "_read_one",
        lambda *a, **k: {"campaign_budget": {"id": "9", "amount_micros": 5_000_000}})
    out = writes_value.update_campaign_budget(ALLOW, "111", 6_000_000, confirm=True)
    assert out.get("applied") is True, out
    assert client.calls[-1][1].validate_only is False
