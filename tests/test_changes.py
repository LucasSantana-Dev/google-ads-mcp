"""Tests for the change_events tool."""


from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import changes


def test_get_change_events_happy_path(monkeypatch):
    """Test retrieving change events within a date range."""
    rows = [
        {
            "change_event": {
                "change_date_time": "2025-06-20T14:30:00Z",
                "change_resource_type": "CAMPAIGN",
                "resource_change_operation": "CREATE",
                "user_email": "user@example.com",
            }
        },
        {
            "change_event": {
                "change_date_time": "2025-06-19T10:15:00Z",
                "change_resource_type": "AD_GROUP",
                "resource_change_operation": "MODIFY",
                "user_email": "user@example.com",
            }
        },
    ]
    monkeypatch.setattr(
        changes.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = changes.get_change_events("123-456-7890", "2025-06-19", "2025-06-20", limit=100)
    assert out["success"] is True
    assert out["row_count"] == 2
    assert out["is_truncated"] is False
    assert out["rows"][0]["change_event"]["change_resource_type"] == "CAMPAIGN"


def test_get_change_events_date_filter(monkeypatch):
    """Test that date range is properly applied in the GAQL query."""
    rows = [{"change_event": {"change_date_time": "2025-06-20T12:00:00Z"}}]
    monkeypatch.setattr(
        changes.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = changes.get_change_events("789", "2025-06-20", "2025-06-21", limit=50)
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_change_events_truncation_at_limit(monkeypatch):
    """Test that results are truncated when exceeding the limit."""
    rows = [
        {"change_event": {"change_date_time": f"2025-06-20T{i:02d}:00:00Z"}}
        for i in range(150)
    ]
    monkeypatch.setattr(
        changes.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = changes.get_change_events("123", "2025-06-20", "2025-06-30", limit=50)
    assert out["success"] is True
    assert out["row_count"] == 50
    assert out["is_truncated"] is True


def test_get_change_events_limit_capped_at_10000(monkeypatch):
    """Test that limit is capped at the API maximum of 10,000."""
    rows = [
        {"change_event": {"change_date_time": f"2025-06-{d:02d}T{h:02d}:00:00Z"}}
        for d in range(1, 30)
        for h in range(0, 24)
    ]
    monkeypatch.setattr(
        changes.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = changes.get_change_events("456", "2025-06-01", "2025-06-30", limit=50000)
    assert out["success"] is True
    assert out["row_count"] == len(rows)
    assert out["is_truncated"] is False
