"""Tests for the write-safety harness (mutate.py). No Google Ads SDK involved."""

import json

import pytest

from google_ads_mcp import mutate


def _recorder(seen):
    def executor(validate_only):
        seen.append(validate_only)
        return {"resource_names": ["customers/1234567890/campaigns/7"], "validate_only": validate_only}
    return executor


def test_default_deny_blocks_without_allowlist(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    seen = []
    out = mutate.guarded_status_change(
        customer_id="1234567890", describe="pause campaign 1", target_status="PAUSED",
        confirm=True, executor=_recorder(seen),
    )
    assert out["success"] is False
    assert out["blocked"] is True
    assert out["applied"] is False
    assert seen == []  # executor must never run when blocked


def test_preview_does_not_apply(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", "1234567890")
    seen = []
    out = mutate.guarded_status_change(
        customer_id="123-456-7890", describe="pause campaign 1", target_status="PAUSED",
        confirm=False, executor=_recorder(seen),
    )
    assert out["applied"] is False
    assert out["preview"] is True
    assert seen == [True]  # validate_only preview only


def test_confirm_applies_and_audits(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", "1234567890")
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(log))
    seen = []
    out = mutate.guarded_status_change(
        customer_id="1234567890", describe="pause campaign 7", target_status="PAUSED",
        confirm=True, executor=_recorder(seen),
    )
    assert out["applied"] is True
    assert out["audit_logged"] is True
    assert seen == [False]  # real mutate, not validate_only
    entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    assert len(entries) == 1
    assert entries[0]["customer_id"] == "1234567890"
    assert entries[0]["target_status"] == "PAUSED"
    assert "ts" in entries[0]


def test_preview_is_not_audited(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", "1234567890")
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(log))
    mutate.guarded_status_change(
        customer_id="1234567890", describe="pause", target_status="PAUSED",
        confirm=False, executor=lambda validate_only: {"ok": True},
    )
    assert not log.exists()  # nothing is logged for a preview


def test_audit_failure_keeps_applied_and_warns(monkeypatch, tmp_path):
    """If audit write fails after a mutation applies, report applied:true / audit_logged:false."""
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", "1234567890")
    # Point the audit log at a directory so the file open/write fails.
    monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(tmp_path))
    seen = []
    out = mutate.guarded_status_change(
        customer_id="1234567890", describe="pause campaign 1", target_status="PAUSED",
        confirm=True, executor=_recorder(seen),
    )
    assert out["applied"] is True  # not mislabeled as failed
    assert out["audit_logged"] is False
    assert "warning" in out
    assert seen == [False]


def test_executor_error_is_not_audited(monkeypatch, tmp_path):
    """A failed mutation (executor raises) must propagate and never be audited."""
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", "1234567890")
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("GOOGLE_ADS_AUDIT_LOG", str(log))

    def boom(validate_only):
        raise RuntimeError("api down")

    with pytest.raises(RuntimeError, match="api down"):
        mutate.guarded_status_change(
            customer_id="1234567890", describe="pause campaign 1", target_status="PAUSED",
            confirm=True, executor=boom,
        )
    assert not log.exists()


def test_is_allowed_normalizes_and_default_denies(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_MUTATE_ALLOWLIST", "111-222-3333, 4444444444")
    assert mutate.is_allowed("1112223333") is True
    assert mutate.is_allowed("444-444-4444") is True
    assert mutate.is_allowed("9999999999") is False
    monkeypatch.delenv("GOOGLE_ADS_MUTATE_ALLOWLIST", raising=False)
    assert mutate.is_allowed("1112223333") is False
