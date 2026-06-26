"""Tests for campaign-reporting tools."""

from __future__ import annotations


from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import campaigns as mod


def test_get_campaigns_no_filter(monkeypatch):
    """Test get_campaigns returns all campaigns without status filter."""
    rows = [
        {"campaign": {"id": "1", "name": "Campaign 1", "status": "ENABLED"}},
        {"campaign": {"id": "2", "name": "Campaign 2", "status": "PAUSED"}},
    ]
    fake_client = FakeGoogleAdsClient(rows=rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_campaigns("123456789")
    assert result["success"] is True
    assert result["row_count"] == 2
    assert len(result["rows"]) == 2


def test_get_campaigns_with_status_filter(monkeypatch):
    """Test get_campaigns filters by status."""
    rows = [
        {"campaign": {"id": "1", "name": "Campaign 1", "status": "ENABLED"}},
    ]
    fake_client = FakeGoogleAdsClient(rows=rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_campaigns("123456789", status_filter="ENABLED")
    assert result["success"] is True
    assert result["row_count"] == 1
    assert result["rows"][0]["campaign"]["id"] == "1"


def test_get_campaigns_respects_limit(monkeypatch):
    """Test get_campaigns respects the limit parameter and reports truncation."""
    rows = [
        {"campaign": {"id": str(i), "name": f"Campaign {i}", "status": "ENABLED"}}
        for i in range(10)
    ]
    fake_client = FakeGoogleAdsClient(rows=rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_campaigns("123456789", limit=5)
    assert result["success"] is True
    assert result["row_count"] == 5
    assert result["is_truncated"] is True


def test_get_campaign_performance(monkeypatch):
    """Test get_campaign_performance returns performance data."""
    rows = [
        {
            "campaign": {"id": "1", "name": "Campaign 1"},
            "segments": {"date": "2024-01-01"},
            "metrics": {"cost_micros": 5000000, "clicks": 100, "impressions": 500},
        },
        {
            "campaign": {"id": "2", "name": "Campaign 2"},
            "segments": {"date": "2024-01-01"},
            "metrics": {"cost_micros": 3000000, "clicks": 50, "impressions": 300},
        },
    ]
    fake_client = FakeGoogleAdsClient(rows=rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_campaign_performance("123456789", "2024-01-01", "2024-01-31")
    assert result["success"] is True
    assert result["row_count"] == 2
    assert result["is_truncated"] is False


def test_get_campaign_performance_with_limit(monkeypatch):
    """Test get_campaign_performance respects limit parameter."""
    rows = [
        {
            "campaign": {"id": str(i), "name": f"Campaign {i}"},
            "segments": {"date": "2024-01-15"},
            "metrics": {"cost_micros": 1000000 * (i + 1), "clicks": 10 * (i + 1), "impressions": 100 * (i + 1)},
        }
        for i in range(10)
    ]
    fake_client = FakeGoogleAdsClient(rows=rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_campaign_performance("123456789", "2024-01-01", "2024-01-31", limit=5)
    assert result["success"] is True
    assert result["row_count"] == 5
    assert result["is_truncated"] is True