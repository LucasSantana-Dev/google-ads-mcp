"""Tests for metadata discovery tools."""

from __future__ import annotations

from types import SimpleNamespace


from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import metadata as mod


def test_get_segments_metadata(monkeypatch):
    """Test retrieval of GAQL segments metadata."""
    fields = [
        SimpleNamespace(
            name="segments.date",
            category="SEGMENT",
            data_type="DATE",
            selectable=True,
            filterable=True,
            sortable=True,
        ),
        SimpleNamespace(
            name="segments.device",
            category="SEGMENT",
            data_type="ENUM",
            selectable=True,
            filterable=True,
            sortable=False,
        ),
    ]
    fake_client = FakeGoogleAdsClient(fields=fields)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_segments_metadata()

    assert result["success"] is True
    assert result["count"] == 2
    assert len(result["fields"]) == 2
    assert result["fields"][0]["name"] == "segments.date"
    assert result["fields"][0]["category"] == "SEGMENT"
    assert result["fields"][1]["name"] == "segments.device"
    assert result["fields"][1]["sortable"] is False


def test_get_metrics_metadata(monkeypatch):
    """Test retrieval of GAQL metrics metadata."""
    fields = [
        SimpleNamespace(
            name="metrics.impressions",
            category="METRIC",
            data_type="INT64",
            selectable=True,
            filterable=True,
            sortable=True,
        ),
        SimpleNamespace(
            name="metrics.clicks",
            category="METRIC",
            data_type="INT64",
            selectable=True,
            filterable=True,
            sortable=True,
        ),
    ]
    fake_client = FakeGoogleAdsClient(fields=fields)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_metrics_metadata()

    assert result["success"] is True
    assert result["count"] == 2
    assert len(result["fields"]) == 2
    assert result["fields"][0]["name"] == "metrics.impressions"
    assert result["fields"][0]["category"] == "METRIC"


def test_get_resource_metadata(monkeypatch):
    """Test retrieval of fields for a specific resource."""
    fields = [
        SimpleNamespace(
            name="campaign.id",
            category="ATTRIBUTE",
            data_type="INT64",
            selectable=True,
            filterable=True,
            sortable=True,
        ),
        SimpleNamespace(
            name="campaign.name",
            category="ATTRIBUTE",
            data_type="STRING",
            selectable=True,
            filterable=True,
            sortable=True,
        ),
        SimpleNamespace(
            name="campaign.status",
            category="ATTRIBUTE",
            data_type="ENUM",
            selectable=True,
            filterable=True,
            sortable=False,
        ),
    ]
    fake_client = FakeGoogleAdsClient(fields=fields)
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_resource_metadata("campaign")

    assert result["success"] is True
    assert result["count"] == 3
    assert len(result["fields"]) == 3
    assert all(f["name"].startswith("campaign.") for f in result["fields"])
    assert result["fields"][2]["sortable"] is False


def test_get_resource_metadata_empty(monkeypatch):
    """Test retrieval when no fields match the resource name."""
    fake_client = FakeGoogleAdsClient(fields=[])
    monkeypatch.setattr(mod.config, "get_client", lambda: fake_client)

    result = mod.get_resource_metadata("nonexistent_resource")

    assert result["success"] is True
    assert result["count"] == 0
    assert result["fields"] == []
