"""Tests for the keywords reporting tools."""

from __future__ import annotations


from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import keywords


def test_get_keywords_no_filters(monkeypatch):
    """Test retrieving all keywords for a customer."""
    rows = [
        {
            "ad_group_criterion": {
                "criterion_id": "101",
                "keyword": {"text": "python programming", "match_type": "BROAD"},
                "status": "ENABLED",
            },
            "ad_group": {"id": "111"},
        },
        {
            "ad_group_criterion": {
                "criterion_id": "102",
                "keyword": {"text": "python tutorial", "match_type": "PHRASE"},
                "status": "ENABLED",
            },
            "ad_group": {"id": "111"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_keywords("1234567890")
    assert out["success"] is True
    assert out["row_count"] == 2
    assert out["is_truncated"] is False


def test_get_keywords_with_ad_group_filter(monkeypatch):
    """Test retrieving keywords filtered by ad group id."""
    rows = [
        {
            "ad_group_criterion": {
                "criterion_id": "101",
                "keyword": {"text": "python", "match_type": "EXACT"},
                "status": "ENABLED",
            },
            "ad_group": {"id": "222"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_keywords("1234567890", ad_group_id="222")
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_keywords_with_both_filters(monkeypatch):
    """Test retrieving keywords with both ad_group_id and match_type filters."""
    rows = [
        {
            "ad_group_criterion": {
                "criterion_id": "101",
                "keyword": {"text": "python", "match_type": "EXACT"},
                "status": "ENABLED",
            },
            "ad_group": {"id": "222"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_keywords("1234567890", ad_group_id="222", match_type_filter="EXACT")
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_keywords_custom_limit(monkeypatch):
    """Test that get_keywords respects the limit parameter."""
    rows = [
        {
            "ad_group_criterion": {
                "criterion_id": str(i),
                "keyword": {"text": f"keyword{i}", "match_type": "BROAD"},
                "status": "ENABLED",
            },
            "ad_group": {"id": "111"},
        }
        for i in range(50)
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_keywords("1234567890", limit=25)
    assert out["success"] is True
    assert out["row_count"] == 25
    assert out["is_truncated"] is True


def test_get_search_terms_date_range_only(monkeypatch):
    """Test retrieving search terms for a date range."""
    rows = [
        {
            "search_term_view": {"search_term": "best python tutorial"},
            "metrics": {"clicks": 42, "impressions": 500, "conversions": 5, "cost_micros": 1500000},
            "segments": {"date": "2025-06-15"},
        },
        {
            "search_term_view": {"search_term": "python tips"},
            "metrics": {"clicks": 15, "impressions": 200, "conversions": 2, "cost_micros": 600000},
            "segments": {"date": "2025-06-20"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_search_terms("1234567890", "2025-06-01", "2025-06-30")
    assert out["success"] is True
    assert out["row_count"] == 2
    assert out["is_truncated"] is False


def test_get_search_terms_with_campaign_filter(monkeypatch):
    """Test retrieving search terms filtered by campaign id."""
    rows = [
        {
            "search_term_view": {"search_term": "python tutorial"},
            "metrics": {"clicks": 20, "impressions": 200, "conversions": 3, "cost_micros": 800000},
            "segments": {"date": "2025-06-15"},
            "campaign": {"id": "333"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_search_terms("1234567890", "2025-06-01", "2025-06-30", campaign_id="333")
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_search_terms_with_min_impressions(monkeypatch):
    """Test retrieving search terms filtered by minimum impressions."""
    rows = [
        {
            "search_term_view": {"search_term": "popular search"},
            "metrics": {"clicks": 50, "impressions": 1000, "conversions": 10, "cost_micros": 3000000},
            "segments": {"date": "2025-06-20"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_search_terms("1234567890", "2025-06-01", "2025-06-30", min_impressions=500)
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_search_terms_with_multiple_filters(monkeypatch):
    """Test retrieving search terms with campaign and impressions filters."""
    rows = [
        {
            "search_term_view": {"search_term": "high value search"},
            "metrics": {"clicks": 35, "impressions": 600, "conversions": 8, "cost_micros": 2000000},
            "segments": {"date": "2025-06-25"},
            "campaign": {"id": "444"},
        },
    ]
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=rows),
    )
    out = keywords.get_search_terms(
        "1234567890", "2025-06-01", "2025-06-30", campaign_id="444", min_impressions=300
    )
    assert out["success"] is True
    assert out["row_count"] == 1


def test_get_search_terms_no_results(monkeypatch):
    """Test get_search_terms with no matching results."""
    monkeypatch.setattr(
        keywords.config,
        "get_client",
        lambda: FakeGoogleAdsClient(rows=[]),
    )
    out = keywords.get_search_terms("1234567890", "2025-06-01", "2025-06-30")
    assert out["success"] is True
    assert out["row_count"] == 0
    assert out["rows"] == []
    assert out["is_truncated"] is False
