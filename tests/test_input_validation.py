"""Read tools reject malformed ids / dates / enums before building a GAQL string."""

import pytest

from google_ads_mcp.testing import FakeGoogleAdsClient
from google_ads_mcp.tools import adgroups, campaigns, changes, keywords


def _no_creds_needed(monkeypatch, mod):
    monkeypatch.setattr(mod.config, "get_client", lambda: FakeGoogleAdsClient(rows=[]))


def test_get_campaigns_rejects_injected_status(monkeypatch):
    _no_creds_needed(monkeypatch, campaigns)
    with pytest.raises(ValueError):
        campaigns.get_campaigns("1234567890", status_filter="ENABLED' OR '1'='1")


def test_get_campaign_performance_rejects_injected_date(monkeypatch):
    _no_creds_needed(monkeypatch, campaigns)
    with pytest.raises(ValueError):
        campaigns.get_campaign_performance("1234567890", "2024-01-01' OR '1'='1", "2024-01-31")


def test_get_ad_groups_rejects_injected_campaign_id(monkeypatch):
    _no_creds_needed(monkeypatch, adgroups)
    with pytest.raises(ValueError):
        adgroups.get_ad_groups("1234567890", campaign_id="1 OR campaign.id > 0")


def test_get_keywords_rejects_bad_match_type(monkeypatch):
    _no_creds_needed(monkeypatch, keywords)
    with pytest.raises(ValueError):
        keywords.get_keywords("1234567890", match_type_filter="BROAD; DROP")


def test_get_change_events_rejects_bad_date(monkeypatch):
    _no_creds_needed(monkeypatch, changes)
    with pytest.raises(ValueError):
        changes.get_change_events("1234567890", "not-a-date", "2024-01-31")


def test_valid_inputs_still_work(monkeypatch):
    _no_creds_needed(monkeypatch, campaigns)
    out = campaigns.get_campaigns("123-456-7890", status_filter="ENABLED")
    assert out["success"] is True
