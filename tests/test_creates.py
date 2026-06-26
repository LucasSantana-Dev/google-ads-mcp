"""Tests for the create tools — gating, preview/confirm, input validation, audit."""

import asyncio
import json

from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import creates as c

ALLOW = "1234567890"


def _wire(monkeypatch, fake, *, allow=ALLOW, audit=None):
    monkeypatch.setattr(c.config, "get_client", lambda: fake)
    if allow is None:
        monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", allow)
    if audit is not None:
        monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(audit))


def test_create_campaign_preview_no_apply(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = c.create_campaign(ALLOW, "Test Campaign", 1000000, confirm=False)
    assert out["preview"] is True
    assert out["applied"] is False
    assert fake.mutations[-1]["method"] == "mutate"
    assert fake.mutations[-1]["validate_only"] is True


def test_create_campaign_confirm_applies_and_audits(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = c.create_campaign(ALLOW, "Test Campaign", 1000000, confirm=True)
    assert out["applied"] is True
    assert fake.mutations[-1]["validate_only"] is False
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["action"] == "create campaign Test Campaign"


def test_create_campaign_blocked_when_not_allowlisted(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake, allow=None)
    out = c.create_campaign(ALLOW, "Test Campaign", 1000000, confirm=True)
    assert out["blocked"] is True
    assert fake.mutations == []


def test_create_campaign_invalid_name(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_campaign(ALLOW, "", 1000000, confirm=False)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "name" in str(e).lower()


def test_create_campaign_invalid_budget(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_campaign(ALLOW, "Test", 0, confirm=False)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "budget" in str(e).lower()


def test_create_campaign_invalid_channel_type(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_campaign(ALLOW, "Test", 1000000, advertising_channel_type="INVALID", confirm=False)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "advertising_channel_type" in str(e).lower()


def test_create_ad_group_preview(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = c.create_ad_group(ALLOW, "123", "Test AG", confirm=False)
    assert out["preview"] is True
    assert out["applied"] is False


def test_create_ad_group_confirm(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = c.create_ad_group(ALLOW, "123", "Test AG", confirm=True)
    assert out["applied"] is True
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["action"] == "create ad group Test AG"


def test_create_keyword_preview(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = c.create_keyword(ALLOW, "456", "test keyword", confirm=False)
    assert out["preview"] is True
    assert out["applied"] is False


def test_create_keyword_confirm(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = c.create_keyword(ALLOW, "456", "test keyword", match_type="PHRASE", confirm=True)
    assert out["applied"] is True
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["action"] == "create keyword test keyword"


def test_create_keyword_invalid_match_type(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_keyword(ALLOW, "456", "test", match_type="INVALID", confirm=False)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "match_type" in str(e).lower()


def test_create_keyword_invalid_text(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_keyword(ALLOW, "456", "", confirm=False)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "keyword_text" in str(e).lower()


def test_create_ad_preview(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = c.create_ad(
        ALLOW, "789",
        ["Headline 1", "Headline 2", "Headline 3"],
        ["Description 1", "Description 2"],
        ["https://example.com"],
        confirm=False,
    )
    assert out["preview"] is True
    assert out["applied"] is False


def test_create_ad_confirm(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = c.create_ad(
        ALLOW, "789",
        ["Headline 1", "Headline 2", "Headline 3"],
        ["Description 1", "Description 2"],
        ["https://example.com"],
        confirm=True,
    )
    assert out["applied"] is True
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["action"] == "create ad with 3 headlines"


def test_create_ad_too_few_headlines(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_ad(
            ALLOW, "789",
            ["Headline 1", "Headline 2"],
            ["Description 1", "Description 2"],
            ["https://example.com"],
            confirm=False,
        )
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "headlines" in str(e).lower()


def test_create_ad_too_many_descriptions(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_ad(
            ALLOW, "789",
            ["Headline 1", "Headline 2", "Headline 3"],
            ["Desc 1", "Desc 2", "Desc 3", "Desc 4", "Desc 5"],
            ["https://example.com"],
            confirm=False,
        )
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "descriptions" in str(e).lower()


def test_create_ad_no_urls(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_ad(
            ALLOW, "789",
            ["Headline 1", "Headline 2", "Headline 3"],
            ["Description 1", "Description 2"],
            [],
            confirm=False,
        )
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "final_urls" in str(e).lower()


def test_create_ad_group_blocked_when_not_allowlisted(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake, allow=None)
    out = c.create_ad_group(ALLOW, "123", "Test AG", confirm=True)
    assert out["blocked"] is True
    assert fake.mutations == []


def test_create_ad_blocked_when_not_allowlisted(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake, allow=None)
    out = c.create_ad(
        ALLOW, "789",
        ["Headline 1", "Headline 2", "Headline 3"],
        ["Description 1", "Description 2"],
        ["https://example.com"],
        confirm=True,
    )
    assert out["blocked"] is True
    assert fake.mutations == []


def test_create_ad_headline_too_long(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_ad(
            ALLOW, "789",
            ["Headline 1", "Headline 2", "H" * 31],  # 31 chars — over limit
            ["Description 1", "Description 2"],
            ["https://example.com"],
            confirm=False,
        )
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "headline" in str(e).lower()


def test_create_ad_description_too_long(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_ad(
            ALLOW, "789",
            ["Headline 1", "Headline 2", "Headline 3"],
            ["Description 1", "D" * 91],  # 91 chars — over limit
            ["https://example.com"],
            confirm=False,
        )
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "description" in str(e).lower()


def test_create_ad_invalid_url(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        c.create_ad(
            ALLOW, "789",
            ["Headline 1", "Headline 2", "Headline 3"],
            ["Description 1", "Description 2"],
            [""],  # empty URL
            confirm=False,
        )
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "final_url" in str(e).lower()


def test_all_create_tools_registered():
    import google_ads_mcp.server as server

    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    expected = {"create_campaign", "create_ad_group", "create_keyword", "create_ad"}
    assert expected <= names
