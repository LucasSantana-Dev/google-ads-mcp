"""Tests for the ad groups tool."""


from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import adgroups as mod


def test_get_ad_groups_no_filters(monkeypatch):
    """Test get_ad_groups with no filters returns all ad groups."""
    fake_rows = [
        {"ad_group.id": "111", "ad_group.name": "AG1", "ad_group.status": "ENABLED", "campaign.id": "999"},
        {"ad_group.id": "222", "ad_group.name": "AG2", "ad_group.status": "PAUSED", "campaign.id": "999"},
        {"ad_group.id": "333", "ad_group.name": "AG3", "ad_group.status": "ENABLED", "campaign.id": "888"},
    ]
    client = FakeGoogleAdsClient(rows=fake_rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: client)

    out = mod.get_ad_groups("123")

    assert out["success"] is True
    assert out["row_count"] == 3
    assert len(out["rows"]) == 3
    assert out["is_truncated"] is False
    assert out["rows"][0]["ad_group.id"] == "111"


def test_get_ad_groups_with_campaign_filter(monkeypatch):
    """Test get_ad_groups filtered by campaign ID."""
    fake_rows = [
        {"ad_group.id": "111", "campaign.id": "999", "ad_group.status": "ENABLED"},
        {"ad_group.id": "222", "campaign.id": "999", "ad_group.status": "PAUSED"},
    ]
    client = FakeGoogleAdsClient(rows=fake_rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: client)

    out = mod.get_ad_groups("123", campaign_id="999")

    assert out["success"] is True
    assert out["row_count"] == 2
    assert out["is_truncated"] is False


def test_get_ad_groups_with_status_filter(monkeypatch):
    """Test get_ad_groups filtered by status."""
    fake_rows = [
        {"ad_group.id": "111", "ad_group.status": "ENABLED", "campaign.id": "999"},
        {"ad_group.id": "222", "ad_group.status": "ENABLED", "campaign.id": "888"},
    ]
    client = FakeGoogleAdsClient(rows=fake_rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: client)

    out = mod.get_ad_groups("123", status_filter="ENABLED")

    assert out["success"] is True
    assert out["row_count"] == 2
    assert out["is_truncated"] is False


def test_get_ad_groups_with_both_filters(monkeypatch):
    """Test get_ad_groups with both campaign and status filters."""
    fake_rows = [
        {"ad_group.id": "111", "campaign.id": "999", "ad_group.status": "ENABLED"},
    ]
    client = FakeGoogleAdsClient(rows=fake_rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: client)

    out = mod.get_ad_groups("123", campaign_id="999", status_filter="ENABLED")

    assert out["success"] is True
    assert out["row_count"] == 1
    assert out["is_truncated"] is False
    assert out["rows"][0]["ad_group.id"] == "111"


def test_get_ad_groups_respects_limit(monkeypatch):
    """Test get_ad_groups respects limit parameter and truncation."""
    fake_rows = [
        {"ad_group.id": str(i), "ad_group.status": "ENABLED", "campaign.id": "999"}
        for i in range(20)
    ]
    client = FakeGoogleAdsClient(rows=fake_rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: client)

    out = mod.get_ad_groups("123", limit=5)

    assert out["success"] is True
    assert out["row_count"] == 5
    assert out["is_truncated"] is True
    assert len(out["rows"]) == 5


def test_get_ad_groups_default_limit(monkeypatch):
    """Test get_ad_groups uses default limit of 100."""
    fake_rows = [
        {"ad_group.id": str(i), "ad_group.status": "ENABLED"}
        for i in range(50)
    ]
    client = FakeGoogleAdsClient(rows=fake_rows)
    monkeypatch.setattr(mod.config, "get_client", lambda: client)

    out = mod.get_ad_groups("123")

    assert out["success"] is True
    assert out["row_count"] == 50
    assert out["is_truncated"] is False
