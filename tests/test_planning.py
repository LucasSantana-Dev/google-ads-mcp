"""Tests for planning and recommendations tools — read-only and gated mutation tools."""

import json
from types import SimpleNamespace

from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import planning as p

ALLOW = "1234567890"


def _wire(monkeypatch, fake, *, allow=ALLOW, audit=None):
    monkeypatch.setattr(p.config, "get_client", lambda: fake)
    if allow is None:
        monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", allow)
    if audit is not None:
        monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(audit))


def test_get_recommendations_returns_rows(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[
        {"recommendation": {"type": "KEYWORD", "campaign": "c1", "resource_name": "rec1"}},
    ])
    _wire(monkeypatch, fake)
    out = p.get_recommendations(ALLOW)
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_recommendations_filters_by_campaign(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[
        {"recommendation": {"type": "KEYWORD", "campaign": "c1", "resource_name": "rec1"}},
    ])
    _wire(monkeypatch, fake)
    out = p.get_recommendations(ALLOW, campaign_id="999")
    assert out["success"] is True


def test_generate_keyword_ideas_with_keywords(monkeypatch):
    ideas = [
        SimpleNamespace(
            text="python tutorial",
            keyword_idea_metrics=SimpleNamespace(
                avg_monthly_searches=1000,
                competition="HIGH",
                low_top_of_page_bid_micros=150000,
                high_top_of_page_bid_micros=250000,
            ),
        ),
    ]
    fake = FakeGoogleAdsClient(ideas=ideas)
    _wire(monkeypatch, fake)
    out = p.generate_keyword_ideas(ALLOW, keywords=["python"])
    assert out["success"] is True
    assert out["idea_count"] == 1
    assert out["ideas"][0]["text"] == "python tutorial"


def test_generate_keyword_ideas_with_url(monkeypatch):
    ideas = [
        SimpleNamespace(
            text="learn coding",
            keyword_idea_metrics=SimpleNamespace(
                avg_monthly_searches=500,
                competition="MEDIUM",
                low_top_of_page_bid_micros=100000,
                high_top_of_page_bid_micros=200000,
            ),
        ),
    ]
    fake = FakeGoogleAdsClient(ideas=ideas)
    _wire(monkeypatch, fake)
    out = p.generate_keyword_ideas(ALLOW, url="https://example.com")
    assert out["success"] is True
    assert out["idea_count"] == 1


def test_generate_keyword_ideas_requires_seed(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    try:
        p.generate_keyword_ideas(ALLOW)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "at least one of keywords or url" in str(e)


def test_get_forecast_metrics_returns_rows(monkeypatch):
    fake = FakeGoogleAdsClient(rows=[
        {"ad_group_criterion_simulation": {"ad_group_id": "123", "criterion_id": "456", "type": "CPC_BID"}},
    ])
    _wire(monkeypatch, fake)
    out = p.get_forecast_metrics(ALLOW, "999")
    assert out["success"] is True
    assert out["row_count"] == 1
    assert "note" in out


def test_apply_recommendation_preview(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = p.apply_recommendation(ALLOW, "customers/123/recommendations/456", confirm=False)
    assert out["preview"] is True
    assert out["applied"] is False
    assert fake.mutations[-1]["method"] == "apply_recommendations"
    assert fake.mutations[-1]["validate_only"] is True


def test_apply_recommendation_confirm_audits(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = p.apply_recommendation(ALLOW, "customers/123/recommendations/456", confirm=True)
    assert out["applied"] is True
    assert fake.mutations[-1]["validate_only"] is False
    entry = json.loads(log.read_text().splitlines()[0])
    assert "apply recommendation" in entry["action"]


def test_apply_recommendation_blocked(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake, allow=None)
    out = p.apply_recommendation(ALLOW, "customers/123/recommendations/456", confirm=True)
    assert out["blocked"] is True
    assert fake.mutations == []


def test_dismiss_recommendation_preview_no_api_call(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake)
    out = p.dismiss_recommendation(ALLOW, "customers/123/recommendations/456", confirm=False)
    assert out["preview"] is True
    assert out["applied"] is False
    # No API call made for preview (dismiss doesn't support validate_only)
    assert len([m for m in fake.mutations if m.get("method") == "dismiss_recommendations"]) == 0


def test_dismiss_recommendation_confirm_audits(monkeypatch, tmp_path):
    fake = FakeGoogleAdsClient()
    log = tmp_path / "audit.jsonl"
    _wire(monkeypatch, fake, audit=log)
    out = p.dismiss_recommendation(ALLOW, "customers/123/recommendations/456", confirm=True)
    assert out["applied"] is True
    entry = json.loads(log.read_text().splitlines()[0])
    assert "dismiss recommendation" in entry["action"]


def test_dismiss_recommendation_blocked(monkeypatch):
    fake = FakeGoogleAdsClient()
    _wire(monkeypatch, fake, allow=None)
    out = p.dismiss_recommendation(ALLOW, "customers/123/recommendations/456", confirm=True)
    assert out["blocked"] is True


def test_all_planning_tools_registered():
    import asyncio
    import google_ads_mcp.server as server

    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    expected = {
        "get_recommendations",
        "apply_recommendation",
        "generate_keyword_ideas",
        "get_forecast_metrics",
        "dismiss_recommendation",
    }
    assert expected <= names
