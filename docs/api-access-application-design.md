<!-- Genericized template. This is the design-document structure submitted with a
Google Ads API Basic-access application, with client-identifying values replaced by
placeholders. Kept public as documentation of the approach; the real, filled-in
version lives in the client's private repository. -->

# Google Ads API Tool — Design Document

**Tool name:** Google Ads MCP Server
**Applicant:** The advertiser (an independent Google Ads developer)
**Manager account (MCC):** XXX-XXX-XXXX
**Contact:** <api-contact-email>
**Intended use:** Internal tool to report on and manage the advertiser's own Google Ads campaigns.

## 1. Overview

The Google Ads MCP Server is an internal automation tool that connects the
Google Ads API to an AI assistant through the Model Context Protocol (MCP). It lets our
team query account performance and make routine campaign-management changes through a
controlled, auditable interface, instead of clicking through the Google Ads UI manually.

The tool is built in Python using the official `google-ads` client library and runs
locally over the MCP stdio transport (no public web service). It is used only by
the advertiser's staff, only against the advertiser's own accounts under manager account
XXX-XXX-XXXX. It does not manage third-party advertiser accounts and is not resold.

## 2. Company and how we use Google Ads

The advertiser runs its own Google Ads search and display campaigns to promote its products
and services and to acquire customers. We manage these campaigns daily: monitoring
spend and performance, reviewing search terms, pausing underperforming campaigns/ad
groups/keywords, and adjusting bids and budgets. This tool exists to make that recurring
work faster and less error-prone for our own account.

## 3. Users and access

- Access is internal only — the advertiser's own operator(s).
- The tool runs on a local workstation; it is not exposed to the public internet and has
  no multi-tenant or client-facing access.
- Credentials are supplied through environment variables and are never shared.

## 4. Authentication

- OAuth 2.0 with a Desktop-app client (client id + secret) and a user refresh token.
- A single developer token, tied to manager account XXX-XXX-XXXX.
- Optional `login-customer-id` set to the manager account when accessing sub-accounts.
- Credentials are stored only in local environment variables / a local `.env` file that
  is excluded from version control. No credentials are transmitted to any third party.

## 5. Google Ads API features used

Reporting and read operations (via GoogleAdsService.SearchStream and GoogleAdsFieldService):

- List accessible customers (CustomerService.ListAccessibleCustomers).
- Run read-only GAQL queries.
- List campaigns and campaign performance metrics (impressions, clicks, cost, conversions).
- List ad groups, keywords, and search terms.
- Read account change history (change_event).
- Discover available fields/segments/metrics for query building (GoogleAdsFieldService).

Management and write operations (each behind explicit confirmation — see Section 9):

- Pause / enable campaigns (CampaignService).
- Pause / enable ad groups (AdGroupService).
- Pause / enable keywords (AdGroupCriterionService).
- Pause / enable ads (AdGroupAdService).
- Update keyword and ad-group CPC bids (AdGroupCriterionService / AdGroupService).
- Update campaign daily budget (CampaignBudgetService).

We do NOT use the token for App Conversion Tracking or Remarketing, and we do NOT create
accounts or manage billing through the API.

## 6. Architecture and data flow

1. The operator asks the AI assistant (MCP client) a question or for an action.
2. The MCP client calls a tool exposed by this server over local stdio.
3. The server authenticates with the Google Ads API using the stored OAuth credentials.
4. For reads, it issues a GAQL query and returns structured results to the assistant.
5. For writes, it first runs a validate-only preview; only after explicit confirmation
   does it submit the mutation, and it records the change to a local audit log.

No data is stored beyond the local audit log of write operations; query results are
returned to the local assistant and not persisted or sent anywhere else.

## 7. Rate limiting and quota management

- Operations are interactive and low-volume (one operator, occasional queries/changes).
- The server surfaces Google Ads API errors (including RESOURCE_TEMPORARILY_EXHAUSTED) to
  the caller and retries transient failures with exponential backoff and jitter.
- Reporting uses SearchStream for large result sets and caps returned rows to avoid
  oversized responses.

## 8. Data handling and storage

- No end-user or personal data is collected or stored.
- Query results are transient and returned only to the local operator's assistant.
- The only persisted data is a local append-only audit log of write operations (timestamp,
  account id, action, old/new value), kept on the operator's machine for accountability.
- No data is shared with third parties.

## 9. Safety controls for write operations

Every mutation passes through a safety gate before it can change the account:

- Account allowlist: writes are blocked unless the target customer id is explicitly
  allowlisted; the default is deny-all.
- Preview first: by default a change runs in validate-only mode and returns a preview
  with no effect; it is applied only when the operator passes an explicit confirmation.
- Change caps: bid and budget changes beyond a configurable percentage of the current
  value (default 25% for bids, 20% for budgets) are blocked.
- Audit log: every applied change is recorded to an append-only local log.
- New entities default to paused.

## 10. Acknowledgement

All information in this document and in the application form is accurate. The tool is for
the advertiser's internal use on its own Google Ads accounts under manager account
XXX-XXX-XXXX, in compliance with the Google Ads API Terms and Conditions and the
Required Minimum Functionality and policy requirements.
