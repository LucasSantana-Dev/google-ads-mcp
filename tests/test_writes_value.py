"""Tests for the bid/budget write tools — percent-change cap, preview/confirm, budget resolution."""

import asyncio
import json

from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import writes_value as wv

ALLOW = "1234567890"


def _wire(monkeypatch, fake, *, allow=ALLOW, audit=None):
    monkeypatch.setattr(wv.config, "get_client", lambda: fake)
    if allow is None:
        monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", allow)
    for env in ("GOOGLE_ADS_MAX_BID_CHANGE_PCT", "GOOGLE_ADS_MAX_BUDGET_CHANGE_PCT"):
        monkeypatch.delenv(env, raising=False)
    if audit is not None:
        monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(audit))


def test_bid_change_within_cap_previews(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[{"ad_group_criterion": {"cpc_bid_micros": 1_000_000}}])
    _wire(monkeypatch, fake)
    out = wv.update_keyword_bid(ALLOW, "11", "22", 1_200_000, confirm=False)  # +20% < 25%
    assert out["preview"] is True and out["applied"] is False
    assert out["change_fraction"] == 0.2
    assert fake.mutations[-1]["validate_only"] is True


def test_bid_change_over_cap_blocked_no_api_write(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[{"ad_group_criterion": {"cpc_bid_micros": 1_000_000}}])
    _wire(monkeypatch, fake)
    out = wv.update_keyword_bid(ALLOW, "11", "22", 2_000_000, confirm=True)  # +100% > 25%
    assert out["blocked"] is True and out["applied"] is False
    assert out["cap"] == 0.25
    assert fake.mutations == []  # cap must block before any mutate call


def test_bid_change_confirm_applies_and_audits_old_new(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient(rows=[{"ad_group_criterion": {"cpc_bid_micros": 1_000_000}}])
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = wv.update_keyword_bid(ALLOW, "11", "22", 1_100_000, confirm=True)  # +10%
    assert out["applied"] is True
    assert fake.mutations[-1]["validate_only"] is False
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["old_value"] == 1_000_000 and entry["new_value"] == 1_100_000
    assert entry["field"] == "cpc_bid_micros"


def test_change_blocked_when_current_value_unknown(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[])  # nothing to read -> current is None
    _wire(monkeypatch, fake)
    out = wv.update_keyword_bid(ALLOW, "11", "22", 500_000, confirm=True)
    assert out["blocked"] is True
    assert fake.mutations == []


def test_blocked_when_not_allowlisted(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[{"ad_group_criterion": {"cpc_bid_micros": 1_000_000}}])
    _wire(monkeypatch, fake, allow=None)
    out = wv.update_keyword_bid(ALLOW, "11", "22", 1_050_000, confirm=True)
    assert out["blocked"] is True
    assert fake.mutations == []


def test_update_campaign_budget_resolves_budget_and_applies(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient(
        rows=[{"campaign_budget": {"id": "555", "amount_micros": 1_000_000}}]
    )
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = wv.update_campaign_budget(ALLOW, "99", 1_100_000, confirm=True)  # +10% < 20%
    assert out["applied"] is True
    assert "555" in out["result"]["resource_names"][0]  # campaign_budget_path used budget id 555


def test_value_tools_registered():
    import google_ads_mcp.server as server

    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert {"update_keyword_bid", "update_ad_group_bid", "update_campaign_budget"} <= names
