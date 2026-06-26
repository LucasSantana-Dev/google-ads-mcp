"""Tests for the status write tools — gating, preview/confirm, path building, audit."""

import asyncio
import json

from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import writes_status as w

ALLOW = "1234567890"


def _wire(monkeypatch, fake, *, allow=ALLOW, audit=None):
    monkeypatch.setattr(w.config, "get_client", lambda: fake)
    if allow is None:
        monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", allow)
    if audit is not None:
        monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(audit))


def test_pause_campaign_preview_uses_validate_only(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = w.pause_campaign(ALLOW, "111", confirm=False)
    assert out["preview"] is True and out["applied"] is False
    assert fake.mutations[-1]["method"] == "mutate_campaigns"
    assert fake.mutations[-1]["validate_only"] is True


def test_pause_campaign_confirm_applies_and_audits(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = w.pause_campaign(ALLOW, "111", confirm=True)
    assert out["applied"] is True
    assert fake.mutations[-1]["validate_only"] is False
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["action"] == "pause campaign 111"
    assert entry["target_status"] == "PAUSED"


def test_blocked_when_not_allowlisted_never_calls_api(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake, allow=None)
    out = w.pause_campaign(ALLOW, "111", confirm=True)
    assert out["blocked"] is True
    assert fake.mutations == []  # API must never be touched when blocked


def test_keyword_path_uses_ad_group_and_criterion_ids(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = w.enable_keyword(ALLOW, "222", "333", confirm=True)
    resource_name = out["result"]["resource_names"][0]
    assert "222" in resource_name and "333" in resource_name


def test_all_eight_write_tools_registered():
    import google_ads_mcp.server as server

    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    expected = {
        "pause_campaign", "enable_campaign", "pause_ad_group", "enable_ad_group",
        "pause_keyword", "enable_keyword", "pause_ad", "enable_ad",
    }
    assert expected <= names
