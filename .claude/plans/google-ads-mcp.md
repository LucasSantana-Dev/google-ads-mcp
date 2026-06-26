# Plan: Google Ads MCP Server

**Status:** active · **Created:** 2026-06-25 · **Owner:** Lucas Santana
**Stack decisions (locked):** Python · Full management + planning (destination) · Local stdio transport

---

## Goal

Build an MCP (Model Context Protocol) server that wraps the **Google Ads API** so an LLM
(Claude Desktop / Claude Code) can read account data, run reports, and — eventually —
manage campaigns, bids, budgets, and planning operations, with safety guardrails on every write.

The end-state scope is **full management + planning**. To avoid a big-bang build, the
roadmap is staged into independently-shippable versions; each version is usable on its own
and read-only value lands first.

## Success criteria

- v1.0: From Claude, ask "show my campaigns / performance / search terms" and get correct,
  paginated structured data via the MCP server running over stdio.
- Every write tool (v1.5+) is gated by `validate_only` preview + explicit `confirm`, an
  account allowlist, and an append-only audit log. No mutation can fire on a single
  un-previewed call.
- ≥80% unit coverage on tool input/output contracts using mocked `GoogleAdsClient`
  (no live-credential tests in CI).

---

## Verified facts (research, June 2026)

| Thing | Value | Source |
|---|---|---|
| Google Ads API version | **v24.2** (2026-06-24); 3 versions supported concurrently (v22–v24) | developers.google.com/google-ads/api/docs/release-notes |
| Official Python client | **`google-ads>=31.1.0`** — gRPC/protobuf internal, auto-paging, GAQL, OAuth2+service-account | pypi.org/project/google-ads |
| No official JS/TS lib | Opteo `google-ads-api` v11 (2022) abandoned → Python chosen | github.com/Opteo/google-ads-api |
| MCP framework | **FastMCP 3.4.2** (decorator tools, Pydantic schema, ~70% of MCP servers) | pypi.org/project/fastmcp |
| MCP spec | **2025-11-25** stable; 2026-07-28 RC (stateless HTTP) on horizon | modelcontextprotocol.io |
| Auth | developer token + OAuth2 (client id/secret/refresh token) + optional `login-customer-id` (no hyphens) | .../docs/oauth/overview |
| 2SV update | New refresh tokens require 2-step verification (April 2026); **service account bypasses 2SV** | .../docs/oauth/overview |
| Dev-token tiers | Test 15k ops/day (test accts only) · Explorer 2,880 prod/day (auto) · Basic 15k (5-day review) · Standard unlimited (10-day) | .../docs/api-policy/access-levels |
| GAQL | SQL-like; `search` vs `search_stream` (both = 1 op); `IN` ≤20,000; results cap 10,000 rows; dates `YYYY-MM-DD` | .../docs/query/overview |
| Mutations | `validate_only` dry-run, `partial_failure`, temp resource names, atomic default | .../docs/mutating/best-practices |
| Rate limit | Token-bucket, dynamic QPS; `RESOURCE_TEMPORARILY_EXHAUSTED` → backoff+jitter | .../docs/productionize/rate-limits |

Prior art surveyed: official `googleads/google-ads-mcp` (read-only, 3 tools, 673★),
`cohnen/mcp-google-ads` (Python, 644★), `FGRibreau/mcp-google-ads` (Rust, two-step
confirm + budget/bid caps + audit log = **write-safety reference**).

---

## In scope

- Python `src/` package, FastMCP server over stdio, `GoogleAdsClient` from env vars.
- Read/reporting tools, then gated write tools, then bid/budget, then create/build, then planning.
- Claude Desktop / Claude Code config + README + tests.

## Out of scope (for now)

- Remote HTTP/SSE multi-tenant hosting (revisit if sharing is needed — see Replanning triggers).
- Web UI / dashboard. Natural-language→GAQL generation beyond metadata-validated raw GAQL.
- Non-Google ad platforms.

---

## Phased roadmap

> Each phase has a validation gate. Do not start the next phase until the gate passes.
> v1.0 = read-only is the first shippable milestone.

### Phase 0 — Project setup & auth (scaffolded this session)
- `git init`; `src/google_ads_mcp/` package; `pyproject.toml` (py≥3.10, google-ads≥31.1, fastmcp≥3.4.2, pydantic≥2).
- `config.py`: env loading + `GoogleAdsClient` factory pinned to `version="v24"` + clear missing-cred error.
- `.env.example`, `.gitignore`, `README.md` credential guide, `tests/` skeleton.
- One-time OAuth helper to mint a refresh token (`scripts/get_refresh_token.py`, Phase 0b).
- **Gate:** `uv sync` installs; `pytest` green (no-network smoke tests); `python -m google_ads_mcp.server` starts and exposes tools.

### Phase 1 — Read-only reporting (v1.0, first ship)
Tools: `list_accessible_customers`, `get_segments_metadata`, `get_metrics_metadata`,
`get_resource_metadata`, `run_gaql_query`, `get_campaigns`, `get_campaign_performance`,
`get_ad_groups`, `get_keywords`, `get_search_terms`, `get_change_events`.
- GAQL field validation via metadata allow-list before `run_gaql_query` (anti-hallucination).
- Pagination (default 100, return `has_more` + `next_page_token`); `search_stream` for big sets; cap 10k rows + `is_truncated`.
- Errors returned in tool result (`{success:false,error:{code,message}}`), never as protocol errors.
- **Gate:** mocked unit tests per tool; live manual test in Claude Desktop ("show my campaigns" works); responses <2s typical; tag `v1.0.0`.

### Phase 2 — Safe status writes (v1.5)
Tools: `pause_campaign`, `pause_ad_group`, `pause_keyword`, `pause_ad` (+ enable variants).
- Write-safety core: `validate_only` preview → `confirm:true` to execute; **customer-id allowlist**; append-only audit log (JSONL/SQLite-WAL).
- `partial_failure:true` on batches.
- **Gate:** preview path causes zero side effects in tests; confirm path writes + logs; allowlist blocks non-listed accounts.

### Phase 3 — Bid & budget writes (v2.0)
Tools: `update_keyword_bid`, `update_campaign_budget`, `update_bidding_strategy`.
- Configurable caps (default: block single bid change >25%, budget >20%); over-spend pre-check; old/new values logged.
- **Gate:** caps enforced in tests; impact preview returned before commit.

### Phase 4 — Creation & build (v2.5)
Tools: `create_campaign`, `create_ad_group`, `create_keyword`, `create_ad` (temp-id atomic pattern).
- New campaigns/ads default to **PAUSED**.
- **Gate:** atomic multi-entity create via temp ids; rollback on partial failure.

### Phase 5 — Planning & recommendations (v3.0 — completes "full management + planning")
Tools: `get_recommendations`, `apply_recommendation` (gated), `generate_keyword_ideas` (Keyword Planner), `get_forecast_metrics`.
- **Gate:** recommendations are evidence-backed (show GAQL data + % change before suggesting); apply is confirm-gated.

---

## Cross-cutting requirements (all phases)

- **Rate limiting:** client-side token bucket + exponential backoff w/ jitter on `RESOURCE_TEMPORARILY_EXHAUSTED`; surface backoff to caller.
- **Mandatory input filters** (customer_id + date range) to prevent unbounded calls / context overflow.
- **Logging to stderr only** (stdout is the JSON-RPC channel — any stray stdout write crashes stdio transport).
- **Version pinning** to `v24`; quarterly review for v25 + sunset dates.
- **Secrets** only via env vars / `.env` (gitignored); never in config files or code.

---

## Key risks → mitigations

1. **Dev-token tier** caps throughput → start Test/Explorer for dev; document Basic/Standard upgrade; surface quota warnings.
2. **OAuth 2SV (Apr 2026)** breaks headless refresh → offer **service-account** path for unattended use.
3. **GAQL hallucination** → require metadata lookup; reject unknown fields with the valid-field list.
4. **Accidental mass mutation** → validate_only + confirm + allowlist + audit, paused-by-default creates.
5. **Large result sets** → enforce filters, paginate, cap 10k + `is_truncated`, prefer `search_stream`.
6. **Wrong-account writes under MCC** → `list_accessible_customers` scoping; surface hierarchy before any write.

---

## Open micro-decisions (sensible defaults chosen; override anytime)

- **Dev-token tier:** default *Test/Explorer for dev → upgrade for prod*. 
- **Auth method:** default *OAuth refresh token for local stdio*; add *service account* in Phase 2+ for unattended runs.
- **Bid/budget caps (Phase 3):** default *balanced* (bid +25%, budget +20%, configurable).
- **Public MCP registry submission:** default *submit v1.0 read-only* after Phase 1.

## Replanning triggers

- Need to share the server with other users / machines → add remote HTTP transport (re-scope Phase 1.5).
- google-ads releases v25 with breaking changes → version-migration spike before continuing.
- Prototype of Phase 1 exposes >3 friction points or >2 shims → escalate to `/research-and-decide` before Phase 2.

## Execution method

- Build with `mcp-builder` patterns; drive each phase TDD-style under `xp` (red→green→refactor).
- Phases are sequential (gates); within a phase, independent tools can be parallelized across agents (worktrees) per repo rules.
