"""Write-safety harness for mutation tools.

Status changes go through :func:`guarded_status_change`; numeric bid/budget changes go through
:func:`guarded_value_change` (which adds a percent-change cap). Both enforce, in order:

  1. allowlist  — customer_id must be in ``GOOGLE_ADS_MUTATE_ALLOWLIST`` (empty = deny all).
  2. (value only) cap — the change vs the current value must be within the configured fraction.
  3. preview    — without ``confirm=True`` it runs ``validate_only``; no change is made.
  4. audit      — confirmed mutations are appended to an append-only JSONL audit log. If the
                  audit write fails *after* a mutation applied, the result is still reported as
                  ``applied: true`` with ``audit_logged: false`` + a warning (never mislabeled
                  as a failed mutation), and a CRITICAL line goes to stderr.

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

# Default per-change caps for value mutations (fraction of the current value).
DEFAULT_MAX_BID_CHANGE = 0.25
DEFAULT_MAX_BUDGET_CHANGE = 0.20


def _allowlist() -> set[str]:
    raw = os.environ.get("GOOGLE_ADS_MUTATE_ALLOWLIST", "")
    return {normalize_customer_id(part) for part in raw.split(",") if part.strip()}


def is_allowed(customer_id: str) -> bool:
    """True only if the (normalized) customer_id is explicitly allowlisted. Default deny."""
    return normalize_customer_id(customer_id) in _allowlist()


def max_change_fraction(env_name: str, default: float) -> float:
    """Read a configurable percent-change cap from an env var, falling back to ``default``."""
    raw = os.environ.get(env_name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def set_update_mask(client, operation, entity, field_name: str) -> None:
    """Populate operation.update_mask for ``field_name``.

    Uses the official ``protobuf_helpers.field_mask`` pattern (as in every Google Ads sample)
    against the real proto-plus message, and falls back to a direct paths assignment for test
    doubles (which have no ``_pb``). The live path is what the API actually receives.
    """
    pb = getattr(entity, "_pb", None)
    if pb is not None and hasattr(client, "copy_from"):
        from google.api_core import protobuf_helpers

        client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, pb))
    else:
        operation.update_mask.paths.append(field_name)


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


def _blocked(norm: str) -> dict:
    return {
        "success": False,
        "blocked": True,
        "applied": False,
        "error": (
            f"customer_id {norm} is not in the mutate allowlist "
            "(set GOOGLE_ADS_MUTATE_ALLOWLIST). No change made."
        ),
    }


def _apply_and_audit(*, norm, describe, extra: dict, executor) -> dict:
    """Run the confirmed executor, then audit; surface applied-but-unaudited honestly."""
    result = executor(validate_only=False)
    response = {"success": True, "applied": True, "audit_logged": True, "result": result, **extra}
    try:
        audit({"customer_id": norm, "action": describe, "result": result, **extra})
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


def guarded_status_change(
    *,
    customer_id: str,
    describe: str,
    target_status: str,
    confirm: bool,
    executor: Callable[..., dict],
) -> dict:
    """Run a status mutation behind allowlist + preview + audit gates.

    Status changes are idempotent: setting a status that already holds (e.g. pausing an
    already-paused entity) is a no-op on the Google Ads side. If the executor raises, the
    mutation is treated as failed and is NOT audited (the exception propagates to tool_handler).
    """
    norm = normalize_customer_id(customer_id)
    if not is_allowed(norm):
        return _blocked(norm)

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

    return _apply_and_audit(
        norm=norm, describe=describe, extra={"target_status": target_status}, executor=executor
    )


def guarded_value_change(
    *,
    customer_id: str,
    describe: str,
    field: str,
    current_value: int | None,
    new_value: int,
    max_change_fraction: float,
    confirm: bool,
    executor: Callable[..., dict],
) -> dict:
    """Run a numeric (bid/budget) mutation behind allowlist + cap + preview + audit gates.

    The cap is a fraction of the *current* value. If the current value is unknown or zero the
    cap cannot be computed, so the change is blocked (read the current value and adjust manually).
    """
    norm = normalize_customer_id(customer_id)
    if not is_allowed(norm):
        return _blocked(norm)

    # Negative current values are intentionally not blocked here: the cap math uses
    # abs(current_value) so it stays well-defined, and the Google Ads API rejects invalid
    # negative bids/budgets server-side. Only unknown/zero current can't be capped.
    if current_value is None or current_value == 0:
        return {
            "success": False,
            "blocked": True,
            "applied": False,
            "field": field,
            "current_value": current_value,
            "new_value": new_value,
            "error": (
                f"current {field} is {current_value!r}; cannot enforce the "
                f"{max_change_fraction:.0%} change cap. Read the current value and adjust manually."
            ),
        }

    change_fraction = (new_value - current_value) / abs(current_value)
    common = {
        "field": field,
        "current_value": current_value,
        "new_value": new_value,
        "change_fraction": round(change_fraction, 4),
    }

    if abs(change_fraction) > max_change_fraction:
        return {
            "success": False,
            "blocked": True,
            "applied": False,
            "cap": max_change_fraction,
            "error": (
                f"requested {field} change of {change_fraction:.1%} exceeds the cap of "
                f"{max_change_fraction:.0%}. Raise the cap env var or make a smaller change."
            ),
            **common,
        }

    if not confirm:
        preview = executor(validate_only=True)
        return {
            "success": True,
            "applied": False,
            "preview": True,
            "would": describe,
            "message": "Preview only (validate_only=true). Re-call with confirm=true to apply.",
            "preview_result": preview,
            **common,
        }

    return _apply_and_audit(
        norm=norm,
        describe=describe,
        extra={"field": field, "old_value": current_value, "new_value": new_value,
               "change_fraction": round(change_fraction, 4)},
        executor=executor,
    )


def guarded_create(
    *,
    customer_id: str,
    describe: str,
    entities: list,
    confirm: bool,
    executor: Callable[..., dict],
) -> dict:
    """Run an entity-creation behind allowlist + preview + audit gates."""
    norm = normalize_customer_id(customer_id)
    if not is_allowed(norm):
        return _blocked(norm)

    if not confirm:
        preview = executor(validate_only=True)
        return {
            "success": True,
            "applied": False,
            "preview": True,
            "would": describe,
            "entities": entities,
            "message": "Preview only (validate_only=true). Re-call with confirm=true to apply.",
            "preview_result": preview,
        }

    return _apply_and_audit(
        norm=norm, describe=describe, extra={"entities": entities}, executor=executor
    )
