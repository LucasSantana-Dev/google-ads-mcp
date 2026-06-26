"""No-network foundation tests for Phase 1. Tools are tested against FakeGoogleAdsClient."""

import asyncio

import pytest

from google_ads_mcp import config, gaql
from google_ads_mcp.testing import FakeGoogleAdsClient


# --- config ---------------------------------------------------------------

def test_missing_env_is_reported(monkeypatch):
    for name in config.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    assert set(config.missing_env()) == set(config.REQUIRED_ENV)


def test_get_client_raises_clear_error_when_unconfigured(monkeypatch):
    for name in config.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    config.get_client.cache_clear()
    with pytest.raises(RuntimeError, match="Missing required Google Ads credentials"):
        config.get_client()


# --- gaql helpers ---------------------------------------------------------

def test_normalize_customer_id_strips_hyphens():
    assert gaql.normalize_customer_id("123-456-7890") == "1234567890"


def test_row_to_dict_passes_dicts_through():
    assert gaql.row_to_dict({"a": 1}) == {"a": 1}


def test_quote_list():
    assert gaql.quote_list(["ENABLED", "PAUSED"]) == "('ENABLED', 'PAUSED')"


def test_run_search_truncates_at_limit():
    rows = [{"i": i} for i in range(5)]
    out = gaql.run_search(FakeGoogleAdsClient(rows=rows), "123", "SELECT x FROM y", limit=3)
    assert out["row_count"] == 3
    assert out["is_truncated"] is True


def test_run_search_under_limit_not_truncated():
    rows = [{"i": i} for i in range(2)]
    out = gaql.run_search(FakeGoogleAdsClient(rows=rows, batch_size=1), "123", "q", limit=100)
    assert out["row_count"] == 2
    assert out["is_truncated"] is False


# --- registration & tools -------------------------------------------------

def _registered_tool_names() -> set[str]:
    import google_ads_mcp.server as server

    return {tool.name for tool in asyncio.run(server.mcp.list_tools())}


def test_core_tools_registered():
    assert {"list_accessible_customers", "run_gaql_query"} <= _registered_tool_names()


def test_list_accessible_customers(monkeypatch):
    from google_ads_mcp.tools import accounts

    monkeypatch.setattr(
        accounts.config, "get_client",
        lambda: FakeGoogleAdsClient(customers=["customers/1234567890", "customers/9999"]),
    )
    out = accounts.list_accessible_customers()
    assert out["success"] is True
    assert out["count"] == 2
    assert "1234567890" in out["customer_ids"]


def test_run_gaql_query(monkeypatch):
    from google_ads_mcp.tools import query

    rows = [{"campaign": {"name": "A"}}, {"campaign": {"name": "B"}}]
    monkeypatch.setattr(query.config, "get_client", lambda: FakeGoogleAdsClient(rows=rows))
    out = query.run_gaql_query("123-456", "SELECT campaign.name FROM campaign", limit=10)
    assert out["success"] is True
    assert out["row_count"] == 2
    assert out["is_truncated"] is False
