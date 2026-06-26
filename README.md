# Google Ads MCP

> Manage Google Ads campaigns through an AI assistant — safely, with every write gated behind a preview and an audit log.

[![CI](https://github.com/LucasSantana-Dev/google-ads-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/LucasSantana-Dev/google-ads-mcp/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes Google Ads API v24 operations as tools for Claude (or any MCP client). Read campaign metrics, search terms, and recommendations; make controlled changes to bids, budgets, statuses, and creative — all from a single conversation.

---

## Features

31 tools across five capability layers:

### Read-only reporting
| Tool | What it does |
|------|-------------|
| `list_accessible_customers` | List all accounts under the MCC |
| `get_campaigns` | List campaigns with status and channel type |
| `get_campaign_performance` | Clicks, impressions, cost, conversions, CTR |
| `get_ad_groups` | List ad groups with status |
| `get_keywords` | Keywords with match type and status |
| `get_search_terms` | Actual search queries with performance metrics |
| `get_change_events` | Account change history |
| `run_gaql_query` | Execute any read-only GAQL query (up to 10k rows) |
| `get_segments_metadata` | Available GAQL segments |
| `get_metrics_metadata` | Available GAQL metrics |
| `get_resource_metadata` | Fields for any GAQL resource |

### Recommendations & planning
| Tool | What it does |
|------|-------------|
| `get_recommendations` | Active Google Ads recommendations for an account or campaign |
| `generate_keyword_ideas` | Keyword ideas from seed keywords or a URL |
| `get_forecast_metrics` | Bid simulations and forecast data |
| `apply_recommendation` | Apply a recommendation (gated) |
| `dismiss_recommendation` | Dismiss a recommendation (gated) |

### Status writes (gated)
| Tool | What it does |
|------|-------------|
| `pause_campaign` / `enable_campaign` | Toggle campaign status |
| `pause_ad_group` / `enable_ad_group` | Toggle ad group status |
| `pause_keyword` / `enable_keyword` | Toggle keyword status |
| `pause_ad` / `enable_ad` | Toggle ad status |

### Bid & budget writes (gated + capped)
| Tool | What it does |
|------|-------------|
| `update_keyword_bid` | Set keyword max CPC — capped at ±25% by default |
| `update_ad_group_bid` | Set ad group default CPC — capped |
| `update_campaign_budget` | Set daily budget — capped at ±20% by default |

### Entity creation (gated)
| Tool | What it does |
|------|-------------|
| `create_campaign` | Create campaign + shared budget atomically (starts paused) |
| `create_ad_group` | Create ad group under a campaign |
| `create_keyword` | Add keyword to an ad group |
| `create_ad` | Create a responsive search ad (starts paused) |

---

## Safety model

Every write passes through four sequential gates:

```
1. Allowlist  — customer_id must be in GOOGLE_ADS_MUTATE_ALLOWLIST (default: deny all)
2. Cap        — bid/budget changes exceeding the configured % are blocked outright
3. Preview    — confirm=False (default) runs validate_only; nothing changes in the account
4. Audit      — confirmed mutations are appended to an append-only JSONL log (chmod 0600)
```

New entities (campaigns, ad groups, keywords, ads) always start **paused**.

Transient quota errors (`RESOURCE_TEMPORARILY_EXHAUSTED`) are retried automatically with exponential back-off and jitter (configurable via `GOOGLE_ADS_MAX_RETRIES`, default 3).

---

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Google Ads developer token and manager account (MCC)

### Install

```bash
git clone https://github.com/LucasSantana-Dev/google-ads-mcp
cd google-ads-mcp
uv sync --extra dev
```

### Credentials

```bash
cp .env.example .env
```

| Variable | Description |
|----------|-------------|
| `GOOGLE_ADS_CLIENT_ID` | OAuth 2.0 Desktop App client ID |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth 2.0 Desktop App client secret |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Your Google Ads developer token |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | MCC account ID (digits only, no hyphens) |
| `GOOGLE_ADS_REFRESH_TOKEN` | Long-lived OAuth refresh token (see below) |
| `GOOGLE_ADS_MUTATE_ALLOWLIST` | Comma-separated customer IDs that may receive writes |
| `GOOGLE_ADS_AUDIT_LOG` | Audit log path (default: `audit-log.jsonl`) |
| `GOOGLE_ADS_MAX_BID_CHANGE_PCT` | Max bid change fraction (default: `0.25`) |
| `GOOGLE_ADS_MAX_BUDGET_CHANGE_PCT` | Max budget change fraction (default: `0.20`) |
| `GOOGLE_ADS_MAX_RETRIES` | Quota retry attempts (default: `3`) |

#### Mint a refresh token

```bash
GOOGLE_ADS_CLIENT_ID=... GOOGLE_ADS_CLIENT_SECRET=... \
  uv run python scripts/get_refresh_token.py
```

A browser opens for OAuth consent. Copy the printed refresh token into `.env`.

---

## Claude Desktop integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/Users/<you>/.local/bin/uv",
      "args": [
        "run",
        "--directory", "/path/to/google-ads-mcp",
        "--env-file", "/path/to/google-ads-mcp/.env",
        "python", "-m", "google_ads_mcp.server"
      ]
    }
  }
}
```

Restart Claude Desktop. The 31 tools appear automatically.

---

## Example conversations

```
# Reporting
"Show me all campaigns for account 123-456-7890 with spend > $100 this week"
"What search terms triggered our branded keywords in the last 7 days?"
"Any keyword ideas for 'project management software'?"
"What recommendations does Google have for my account?"

# Writes — always previews first; apply with confirm=true
"Pause campaign 9876543, it's burning budget"
"Set the CPC bid for keyword 111 in ad group 222 to $1.50"
"Create a new Search campaign 'Brand Q3' with a $20/day budget"
"Apply the 'add keyword' recommendation for campaign 555"
```

---

## Development

```bash
uv run pytest                          # 102 tests, 89% coverage
uv run ruff check src/ tests/          # lint
uv run mypy src/                       # type check
```

CI runs on every push and pull request.

---

## Architecture

```
src/google_ads_mcp/
├── server.py          # FastMCP entrypoint, tool registration
├── config.py          # GoogleAdsClient factory (reads .env)
├── gaql.py            # GAQL execution, validators, row serialization, retry
├── mutate.py          # Write-safety harness (allowlist → cap → preview → audit)
├── retry.py           # Exponential back-off for quota errors
├── errors.py          # tool_handler wrapper → {success, error} for any exception
├── testing.py         # FakeGoogleAdsClient — unit tests without network or credentials
└── tools/
    ├── accounts.py        # list_accessible_customers
    ├── campaigns.py       # get_campaigns, get_campaign_performance
    ├── adgroups.py        # get_ad_groups
    ├── keywords.py        # get_keywords, get_search_terms
    ├── changes.py         # get_change_events
    ├── query.py           # run_gaql_query
    ├── metadata.py        # get_*_metadata (3 tools)
    ├── writes_status.py   # pause/enable campaign/ad_group/keyword/ad (8 tools)
    ├── writes_value.py    # update keyword bid, ad group bid, campaign budget (3 tools)
    ├── creates.py         # create campaign, ad group, keyword, ad (4 tools)
    └── planning.py        # recommendations, keyword ideas, forecast (5 tools)
```

**Transport:** stdio only — no HTTP port, no public exposure.  
**Auth:** OAuth 2.0 Desktop App + refresh token. Credentials stay on the local machine.

---

## License

MIT
