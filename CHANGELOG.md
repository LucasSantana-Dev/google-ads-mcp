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
- **8 gated write tools (Phase 2 / v1.5):** `pause`/`enable` × `campaign`/`ad_group`/`keyword`/`ad`.
  Write-safety harness (`mutate.py`): default-deny allowlist (`GOOGLE_ADS_MUTATE_ALLOWLIST`) →
  `validate_only` preview → explicit `confirm` → append-only audit log (flock, 0600, size-capped).
  Applied-but-unaudited mutations are surfaced honestly (`audit_logged:false` + stderr CRITICAL),
  never mislabeled as failures. Status mutations use the official `field_mask` pattern.
- Hardened GAQL input validation across read + write tools (numeric ids, `YYYY-MM-DD` dates,
  enum allowlists) — defense-in-depth against query injection. Adversarial 3-lens review applied.
- **3 gated bid/budget write tools (Phase 3 / v2.0):** `update_keyword_bid`, `update_ad_group_bid`,
  `update_campaign_budget`. Same allowlist/preview/confirm/audit harness plus a **percent-change
  cap** (reads the current value, blocks a change beyond the cap; default bid 25% / budget 20%,
  via `GOOGLE_ADS_MAX_BID_CHANGE_PCT` / `GOOGLE_ADS_MAX_BUDGET_CHANGE_PCT`). Audit records old→new.
  `row_to_dict` now emits deterministic snake_case keys. Reviewed clean (API-correctness + cap-safety).
