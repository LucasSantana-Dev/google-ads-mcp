# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Phase 0 scaffold: Python `src/` package, `pyproject.toml`, FastMCP stdio server.
- `config.get_client()` — env-based GoogleAdsClient factory pinned to API `v24` with a
  clear missing-credential error.
- `tools/` package with auto-registration; shared `gaql.py` (run_search, TEMPLATES,
  quote_list), `errors.py` (tool_handler), `testing.py` (FakeGoogleAdsClient).
- **11 read-only tools (v1.0):** `list_accessible_customers`, `run_gaql_query`,
  `get_segments_metadata`, `get_metrics_metadata`, `get_resource_metadata`,
  `get_campaigns`, `get_campaign_performance`, `get_ad_groups`, `get_keywords`,
  `get_search_terms`, `get_change_events`.
- `get_resource_metadata` validates `resource_name` against GAQL injection.
- `scripts/get_refresh_token.py` — one-time OAuth refresh-token helper.
- 38 no-network unit tests (mocked GoogleAdsClient); README setup + tool reference.
- Roadmap plan at `.claude/plans/google-ads-mcp.md` (staged read-only → writes → planning).
