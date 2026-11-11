"""
Phase 35 Tests — Daily CLV Operations Runbook & Alerting
=========================================================

Tests:
  1.  normal INSUFFICIENT accumulation → INFO alert
  2.  pending CLV older than 24h → WARN alert
  3.  threshold event unhandled → WARN alert
  4.  pending human review → WARN alert
  5.  planner external LLM attempt → CRITICAL alert
  6.  missing CLV file → CRITICAL alert (registry exists, no CLV file)
  7.  computed count decrease → CRITICAL alert
  8.  CLI writes JSON + Markdown artifacts
  9.  Decision Card renders Daily CLV Ops section
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.daily_clv_ops_summary import (
    SEV_CRITICAL,
    SEV_INFO,
    SEV_WARN,
    CODE_COMPUTED_COUNT_DECREASED,
    CODE_CLV_FILE_MISSING_OR_MALFORMED,
    CODE_EVIDENCE_APPROACHING,
    CODE_HUMAN_REVIEW_PENDING,
    CODE_NO_PENDING_REVIEWS,
    CODE_NO_UNEXPECTED_LLM,
    CODE_NORMAL_ACCUMULATION,
    CODE_PLANNER_LLM_ATTEMPT,
    CODE_PENDING_CLV_STALE,
    CODE_THRESHOLD_EVENT_UNHANDLED,
    _evaluate_alerts,
    get_daily_ops_summary,
    render_daily_ops_markdown,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _make_clv_file(
    reports: Path,
    date_str: str = "2026-04-30",
    computed: int = 0,
    pending: int = 0,
) -> Path:
    p = reports / f"clv_validation_records_6u_{date_str}.jsonl"
    rows: list[dict] = []
    for i in range(computed):
        rows.append({"prediction_id": f"c_{i}", "clv_status": "COMPUTED", "clv_value": 0.01 * i})
    for i in range(pending):
        rows.append({"prediction_id": f"p_{i}", "clv_status": "PENDING_CLOSING"})
    _write_jsonl(p, rows)
    return p


def _make_registry(reports: Path, date_str: str = "2026-04-30", n: int = 3) -> Path:
    p = reports / f"prediction_registry_6t_{date_str}.jsonl"
    _write_jsonl(p, [{"id": i, "game_date": date_str} for i in range(n)])
    return p


def _empty_batch_summary() -> dict:
    return {
        "available": True,
        "batches_seen": 0,
        "latest_batch_date": None,
        "total_computed": 0,
        "total_pending": 0,
        "batches_needing_clv_generation": 0,
        "batches_needing_closing_monitor": 0,
        "batches_needing_accumulation_update": 0,
        "batches": [],
    }


def _normal_accumulation() -> dict:
    return {
        "available": True,
        "evidence_state": "INSUFFICIENT",
        "computed_count": 14,
        "threshold": 50,
        "remaining_needed": 36,
        "patch_gate_recheck_allowed": False,
        "patch_candidate_allowed": False,
    }


def _empty_threshold() -> dict:
    return {
        "available": True,
        "pending_threshold_events": 0,
        "crossed_30": False,
        "crossed_50": False,
        "latest_event_type": None,
        "recommended_task_type": None,
    }


def _empty_hr() -> dict:
    return {
        "available": True,
        "pending_count": 0,
        "approved_count": 0,
        "rejected_count": 0,
        "pending_reviews": [],
        "approved_reviews": [],
        "rejected_reviews": [],
        "more_data_requested": [],
    }


def _empty_llm_audit() -> dict:
    return {
        "available": True,
        "total_events": 0,
        "attempts": 0,
        "results": 0,
        "blocked": 0,
        "by_role": {},
        "by_provider": {},
    }


def _normal_clv_counts(computed: int = 14, pending: int = 0, prev: int = 10) -> dict:
    return {
        "available": True,
        "clv_files_found": 1,
        "computed_total": computed,
        "pending_total": pending,
        "blocked_total": 0,
        "new_computed_today": max(0, computed - prev),
        "previous_computed_count": prev,
        "malformed_files": [],
    }


# ── Test 1: normal INSUFFICIENT accumulation → INFO ─────────────────────────

def test_normal_insufficient_produces_info_alert():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()

        alerts = _evaluate_alerts(
            batch_summary=_empty_batch_summary(),
            clv_counts=_normal_clv_counts(),
            accumulation=_normal_accumulation(),
            threshold=_empty_threshold(),
            human_review=_empty_hr(),
            llm_audit=_empty_llm_audit(),
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        severities = [a["severity"] for a in alerts]

        assert CODE_NORMAL_ACCUMULATION in codes
        assert SEV_CRITICAL not in severities
        assert any(a["severity"] == SEV_INFO for a in alerts)


# ── Test 2: pending CLV older than 24h → WARN ───────────────────────────────

def test_stale_pending_clv_produces_warn():
    old_date = "2026-04-28"  # > 24h ago from 2026-05-01
    batch_summary = {
        "available": True,
        "batches_seen": 1,
        "latest_batch_date": old_date,
        "total_computed": 5,
        "total_pending": 3,
        "batches_needing_clv_generation": 0,
        "batches_needing_closing_monitor": 1,
        "batches_needing_accumulation_update": 0,
        "batches": [{
            "batch_date": old_date,
            "computed_count": 5,
            "pending_count": 3,
            "needs_clv_generation": False,
            "needs_closing_monitor": True,
            "needs_accumulation_update": False,
        }],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()

        alerts = _evaluate_alerts(
            batch_summary=batch_summary,
            clv_counts=_normal_clv_counts(pending=3),
            accumulation=_normal_accumulation(),
            threshold=_empty_threshold(),
            human_review=_empty_hr(),
            llm_audit=_empty_llm_audit(),
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        assert CODE_PENDING_CLV_STALE in codes
        warn_alerts = [a for a in alerts if a["code"] == CODE_PENDING_CLV_STALE]
        assert all(a["severity"] == SEV_WARN for a in warn_alerts)


# ── Test 3: threshold event unhandled → WARN ────────────────────────────────

def test_unhandled_threshold_event_produces_warn():
    threshold = {
        "available": True,
        "pending_threshold_events": 1,
        "crossed_30": True,
        "crossed_50": False,
        "latest_event_type": "CROSSED_APPROACHING",
        "recommended_task_type": "production_clv_investigation",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()

        alerts = _evaluate_alerts(
            batch_summary=_empty_batch_summary(),
            clv_counts=_normal_clv_counts(),
            accumulation=_normal_accumulation(),
            threshold=threshold,
            human_review=_empty_hr(),
            llm_audit=_empty_llm_audit(),
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        assert CODE_THRESHOLD_EVENT_UNHANDLED in codes
        thr_alerts = [a for a in alerts if a["code"] == CODE_THRESHOLD_EVENT_UNHANDLED]
        assert all(a["severity"] == SEV_WARN for a in thr_alerts)


# ── Test 4: pending human review → WARN ─────────────────────────────────────

def test_pending_human_review_produces_warn():
    hr = {
        "available": True,
        "pending_count": 2,
        "approved_count": 0,
        "rejected_count": 0,
        "pending_reviews": [
            {"review_type": "LEARNING_RECHECK", "status": "PENDING"},
            {"review_type": "LEARNING_RECHECK", "status": "PENDING"},
        ],
        "approved_reviews": [],
        "rejected_reviews": [],
        "more_data_requested": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()

        alerts = _evaluate_alerts(
            batch_summary=_empty_batch_summary(),
            clv_counts=_normal_clv_counts(),
            accumulation=_normal_accumulation(),
            threshold=_empty_threshold(),
            human_review=hr,
            llm_audit=_empty_llm_audit(),
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        assert CODE_HUMAN_REVIEW_PENDING in codes
        hr_alerts = [a for a in alerts if a["code"] == CODE_HUMAN_REVIEW_PENDING]
        assert all(a["severity"] == SEV_WARN for a in hr_alerts)


# ── Test 5: planner external LLM attempt → CRITICAL ─────────────────────────

def test_planner_llm_attempt_produces_critical():
    llm_audit = {
        "available": True,
        "total_events": 2,
        "attempts": 2,
        "results": 1,
        "blocked": 0,
        "by_role": {
            "planner": {"attempts": 2, "results": 1, "blocked": 0, "succeeded": 1, "failed": 0}
        },
        "by_provider": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()

        alerts = _evaluate_alerts(
            batch_summary=_empty_batch_summary(),
            clv_counts=_normal_clv_counts(),
            accumulation=_normal_accumulation(),
            threshold=_empty_threshold(),
            human_review=_empty_hr(),
            llm_audit=llm_audit,
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        assert CODE_PLANNER_LLM_ATTEMPT in codes
        crit_alerts = [a for a in alerts if a["code"] == CODE_PLANNER_LLM_ATTEMPT]
        assert all(a["severity"] == SEV_CRITICAL for a in crit_alerts)


# ── Test 6: missing CLV file (registry exists, no CLV) → CRITICAL ────────────

def test_missing_clv_file_produces_critical():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        # Registry exists but no CLV file
        _make_registry(reports, "2026-04-30", n=3)

        # batch_summary will indicate batches_seen=1 via clv_counts having 0 files
        batch_summary = {
            "available": True,
            "batches_seen": 1,
            "latest_batch_date": "2026-04-30",
            "total_computed": 0,
            "total_pending": 0,
            "batches_needing_clv_generation": 1,
            "batches_needing_closing_monitor": 0,
            "batches_needing_accumulation_update": 0,
            "batches": [{
                "batch_date": "2026-04-30",
                "computed_count": 0,
                "pending_count": 0,
                "needs_clv_generation": True,
                "needs_closing_monitor": False,
                "needs_accumulation_update": False,
            }],
        }
        clv_counts = {
            "available": True,
            "clv_files_found": 0,   # <-- no CLV file
            "computed_total": 0,
            "pending_total": 0,
            "blocked_total": 0,
            "new_computed_today": 0,
            "previous_computed_count": 0,
            "malformed_files": [],
        }

        alerts = _evaluate_alerts(
            batch_summary=batch_summary,
            clv_counts=clv_counts,
            accumulation=_normal_accumulation(),
            threshold=_empty_threshold(),
            human_review=_empty_hr(),
            llm_audit=_empty_llm_audit(),
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        assert CODE_CLV_FILE_MISSING_OR_MALFORMED in codes
        crit_alerts = [a for a in alerts if a["code"] == CODE_CLV_FILE_MISSING_OR_MALFORMED]
        assert all(a["severity"] == SEV_CRITICAL for a in crit_alerts)


# ── Test 7: computed count decrease → CRITICAL ──────────────────────────────

def test_computed_count_decrease_produces_critical():
    # Previous count = 20, current = 14 → decrease
    clv_counts = _normal_clv_counts(computed=14, prev=20)

    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()

        alerts = _evaluate_alerts(
            batch_summary=_empty_batch_summary(),
            clv_counts=clv_counts,
            accumulation=_normal_accumulation(),
            threshold=_empty_threshold(),
            human_review=_empty_hr(),
            llm_audit=_empty_llm_audit(),
            reports_dir=reports,
        )

        codes = [a["code"] for a in alerts]
        assert CODE_COMPUTED_COUNT_DECREASED in codes
        crit_alerts = [a for a in alerts if a["code"] == CODE_COMPUTED_COUNT_DECREASED]
        assert all(a["severity"] == SEV_CRITICAL for a in crit_alerts)


# ── Test 8: CLI writes JSON + Markdown ──────────────────────────────────────

def test_cli_writes_json_and_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir    = Path(tmpdir) / "docs" / "orchestration"
        reports_dir = Path(tmpdir) / "data" / "wbc_backend" / "reports"
        reports_dir.mkdir(parents=True)
        docs_dir.mkdir(parents=True)

        # Patch path constants in the runner
        import scripts.run_daily_clv_ops_summary as runner_mod

        original_docs    = runner_mod._DOCS_DIR
        original_reports = runner_mod._REPORTS_DIR
        try:
            runner_mod._DOCS_DIR    = docs_dir
            runner_mod._REPORTS_DIR = reports_dir

            # Provide a CLV file so the summary has real data
            _make_clv_file(reports_dir.parent.parent  # go up to reach actual reports
                           if False else reports_dir,
                           "2026-04-30", computed=14)

            exit_code = runner_mod.main(["--date", "2026-04-30"])
        finally:
            runner_mod._DOCS_DIR    = original_docs
            runner_mod._REPORTS_DIR = original_reports

        assert exit_code == 0

        json_path = reports_dir / "daily_clv_ops_summary_2026-04-30.json"
        md_path   = docs_dir    / "daily_clv_ops_summary_2026-04-30.md"

        assert json_path.exists(), f"JSON artifact missing: {json_path}"
        assert md_path.exists(),   f"MD artifact missing: {md_path}"

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["date"] == "2026-04-30"
        assert "alerts" in data
        assert "operator_next_action" in data

        md_text = md_path.read_text(encoding="utf-8")
        assert "DAILY CLV OPS SUMMARY" in md_text
        assert "OPERATOR NEXT ACTION" in md_text


# ── Test 9: Decision Card renders Daily CLV Ops section ─────────────────────

def test_decision_card_renders_daily_clv_ops():
    from scripts.ops_decision_card import compute_daily_clv_ops_status, render_card

    status = compute_daily_clv_ops_status()
    assert isinstance(status, dict)
    assert "date" in status or "available" in status  # either real data or error dict

    # Use build_payload so render_card gets correctly shaped sub-dicts,
    # then inject our daily_clv_ops fixture on top.
    from scripts.ops_decision_card import build_payload
    full_payload = build_payload()
    full_payload["daily_clv_ops"] = {
        "date": "2026-05-01",
        "highest_severity": "INFO",
        "clv": {"computed_total": 14, "pending_total": 0, "blocked_total": 0},
        "accumulation": {
            "evidence_state": "INSUFFICIENT",
            "computed_count": 14,
            "threshold": 50,
        },
        "threshold": {"pending_threshold_events": 0},
        "human_review": {"pending_count": 0},
        "llm_audit": {"attempts": 0},
        "alerts": [],
        "operator_next_action": "Continue accumulation.",
    }

    card = render_card(full_payload)
    assert "DAILY CLV OPS" in card
    assert "2026-05-01" in card
    assert "OPERATOR NEXT ACTION" not in card  # ops section, not top bar
    assert "Continue accumulation." in card

    # Also verify the full build_payload includes the key
    from scripts.ops_decision_card import build_payload
    payload = build_payload()
    assert "daily_clv_ops" in payload
    assert isinstance(payload["daily_clv_ops"], dict)
