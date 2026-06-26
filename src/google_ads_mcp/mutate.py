"""Write-safety harness for mutation tools.

Every write goes through :func:`guarded_status_change`, which enforces, in order:

  1. allowlist  — customer_id must be in ``GOOGLE_ADS_MUTATE_ALLOWLIST`` (empty = deny all).
  2. preview    — without ``confirm=True`` it runs ``validate_only`` and returns a preview;
                  no change is made.
  3. audit      — confirmed mutations are appended to an append-only JSONL audit log. If the
                  audit write fails *after* a mutation was applied, the result is still
                  reported as ``applied: true`` with ``audit_logged: false`` + a warning (never
                  mislabeled as a failed mutation), and a CRITICAL line goes to stderr.

The actual API call is supplied as an ``executor(validate_only: bool) -> dict`` callable, so
the gate logic is fully testable without the Google Ads SDK.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Callable

from .gaql import normalize_customer_id

# Cap an oversized result payload in an audit record to avoid unbounded log growth.
MAX_AUDIT_RESULT_BYTES = 16_000


def _allowlist() -> set[str]:
    raw = os.environ.get("GOOGLE_ADS_MUTATE_ALLOWLIST", "")
    return {normalize_customer_id(part) for part in raw.split(",") if part.strip()}


def is_allowed(customer_id: str) -> bool:
    """True only if the (normalized) customer_id is explicitly allowlisted. Default deny."""
    return normalize_customer_id(customer_id) in _allowlist()


def audit_log_path() -> str:
    return os.environ.get("GOOGLE_ADS_AUDIT_LOG", "audit-log.jsonl")


def audit(entry: dict) -> None:
    """Append one timestamped record to the append-only JSONL audit log.

    Hardening: caps an oversized result payload, ensures the parent dir, locks the file during
    the write (flock where available), and restricts perms to 0600. Raises if the write itself
    fails so the caller can surface an applied-but-unaudited mutation.
    """
    path = audit_log_path()
    record = {"ts": datetime.datetime.now(datetime.UTC).isoformat(), **entry}
    blob = json.dumps(record)
    if len(blob) > MAX_AUDIT_RESULT_BYTES:
        record["result"] = {"_truncated": True, "bytes": len(blob)}
        blob = json.dumps(record)

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "a", encoding="utf-8") as fh:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # locking is best-effort; not available on every platform
        fh.write(blob + "\n")

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def guarded_status_change(
    *,
    customer_id: str,
    describe: str,
    target_status: str,
    confirm: bool,
    executor: Callable[..., dict],
) -> dict:
    """Run a status mutation behind allowlist + preview + audit gates.

    Args:
        customer_id: target account (digits or hyphenated; normalized internally).
        describe: human-readable description of the change (e.g. "pause campaign 123").
        target_status: the status being set (e.g. "PAUSED", "ENABLED").
        confirm: must be True to actually apply; otherwise only a validate_only preview runs.
        executor: ``executor(validate_only: bool) -> dict`` performs the real API call.

    Status changes are idempotent: setting a status that already holds (e.g. pausing an
    already-paused entity) is a no-op on the Google Ads side. If the executor raises, the
    mutation is treated as failed and is NOT audited (the exception propagates to tool_handler).
    """
    norm = normalize_customer_id(customer_id)

    if not is_allowed(norm):
        return {
            "success": False,
            "blocked": True,
            "applied": False,
            "error": (
                f"customer_id {norm} is not in the mutate allowlist "
                "(set GOOGLE_ADS_MUTATE_ALLOWLIST). No change made."
            ),
        }

    if not confirm:
        preview = executor(validate_only=True)
        return {
            "success": True,
            "applied": False,
            "preview": True,
            "would": describe,
            "target_status": target_status,
            "message": "Preview only (validate_only=true). Re-call with confirm=true to apply.",
            "preview_result": preview,
        }

    # Apply first; a failure to AUDIT must not be reported as a failed MUTATION.
    result = executor(validate_only=False)
    response = {
        "success": True,
        "applied": True,
        "audit_logged": True,
        "action": describe,
        "target_status": target_status,
        "result": result,
    }
    try:
        audit(
            {
                "customer_id": norm,
                "action": describe,
                "target_status": target_status,
                "result": result,
            }
        )
    except Exception as exc:  # noqa: BLE001 - mutation already applied; surface, don't mask
        response["audit_logged"] = False
        response["warning"] = (
            f"Mutation was APPLIED but could not be written to the audit log: {exc}"
        )
        print(
            f"CRITICAL: mutation applied for customer {norm} ({describe}) "
            f"but audit log write failed: {exc}",
            file=sys.stderr,
            flush=True,
        )
    return response
