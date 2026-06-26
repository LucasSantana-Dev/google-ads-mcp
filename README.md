# google-ads-mcp

An [MCP](https://modelcontextprotocol.io) server that wraps the **Google Ads API** so an
LLM client (Claude Desktop / Claude Code) can query accounts, run reports, and — in later
versions — manage campaigns under safety gates.

- **Stack:** Python ≥3.10 · `google-ads` ≥31.1.0 (official) · FastMCP ≥3.4.2 · stdio transport
- **Pinned API version:** Google Ads `v24`
- **Status:** Phase 0 scaffold + first read-only tools. See [`.claude/plans/google-ads-mcp.md`](.claude/plans/google-ads-mcp.md) for the full roadmap.

> Read-only first. Write tools (pause / bid / budget / create / recommendations) arrive in
> later phases, each behind `validate_only` preview + explicit `confirm` + account allowlist
> + an append-only audit log.

## Setup

### 1. Install

```bash
uv sync --extra dev        # or: pip install -e ".[dev]"
```

### 2. Get credentials

You need four values (see `.env.example`):

1. **Developer token** — https://ads.google.com/aw/apicenter → Settings → Developer Token (22 chars).
   Test/Explorer tier is fine for development.
2. **OAuth client id + secret** — https://console.cloud.google.com → enable *Google Ads API* →
   create an **OAuth 2.0 Desktop App** credential.
3. **Refresh token** — run the one-time helper (Phase 0b): `python scripts/get_refresh_token.py`
   (opens a browser, grants access, prints the refresh token). Note: new tokens require 2-step
   verification (Google Ads policy, April 2026). For unattended use, a service account avoids 2SV.

Copy `.env.example` → `.env` and fill them in (`.env` is gitignored).

### 3. Run

```bash
google-ads-mcp            # console script, stdio transport
# or
python -m google_ads_mcp.server
```

### 4. Register in Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "google-ads-mcp",
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "...",
        "GOOGLE_ADS_CLIENT_ID": "...",
        "GOOGLE_ADS_CLIENT_SECRET": "...",
        "GOOGLE_ADS_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

## Tools (v1.0 — read-only)

**Discovery**
| Tool | Purpose |
|---|---|
| `list_accessible_customers` | List customer accounts the credentials can access |
| `get_segments_metadata` | List selectable GAQL segments (dimensions) |
| `get_metrics_metadata` | List selectable GAQL metrics |
| `get_resource_metadata` | List fields for a resource (e.g. `campaign`) — validated against injection |

**Reporting**
| Tool | Purpose |
|---|---|
| `run_gaql_query` | Run an arbitrary read-only GAQL query (capped at 10,000 rows) |
| `get_campaigns` | List campaigns, optional status filter |
| `get_campaign_performance` | Campaign metrics over a date range |
| `get_ad_groups` | List ad groups, optional campaign/status filter |
| `get_keywords` | List keywords, optional ad-group/match-type filter |
| `get_search_terms` | Search terms over a date range, min-impressions filter |
| `get_change_events` | Account change history over a date range |

Write tools (pause / bid / budget / create / recommendations) arrive in later phases — see
[`.claude/plans/google-ads-mcp.md`](.claude/plans/google-ads-mcp.md).

## Develop

```bash
pytest        # no-network smoke + (later) mocked unit tests
ruff check .
```
