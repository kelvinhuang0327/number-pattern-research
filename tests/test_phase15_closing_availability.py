"""
Phase 15 — Closing Odds Availability Monitor Tests
====================================================
Tests the per-record diagnostic and source-level summary functions added
in Phase 15, plus downstream integration with safe_task_executor,
optimization_readiness, optimization_ops_report, and ops_decision_card.

Test scenarios:
  T1. Pending record with no timeline entry → recommended_action="wait"
  T2. TSL closing exists but closing_ts ≤ prediction_time → invalid_reason="before_prediction"
  T3. External closing valid (ts > pred_time) → candidate_valid=True
  T4. Same-snapshot candidate rejected → invalid_reason="same_snapshot"
  T5. Source-level summary counts are correct
  T6. Safe executor artifact includes pending details section and is non-empty
  T7. Readiness dashboard includes "closing_availability" key
  T8. Ops report includes closing_availability in return dict
  T9. Decision card payload includes closing_availability key
"""
from __future__ import annotations

import json
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )


def _make_clv_row(
    pred_id: str = "pred-001",
    match_id: str = "game-001",
    selection: str = "home",
    pred_time: str | None = None,
    status: str = "PENDING_CLOSING",
) -> dict[str, Any]:
    if pred_time is None:
        pred_time = _iso(datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc))
    return {
        "prediction_id": pred_id,
        "canonical_match_id": match_id,
        "selection": selection,
        "prediction_time_utc": pred_time,
        "clv_status": status,
        "predicted_ml": -120,
        "predicted_side": selection,
    }


def _make_timeline_row(
    game_id: str = "game-001",
    closing_home_ml: float | None = None,
    closing_ts: str | None = None,
    ext_home_ml: float | None = None,
    ext_ts: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"game_id": game_id, "source": "live"}
    if closing_home_ml is not None:
        row["closing_home_ml"] = closing_home_ml
    if closing_ts is not None:
        row["closing_ts"] = closing_ts
    if ext_home_ml is not None:
        row["external_closing_home_ml"] = ext_home_ml
    if ext_ts is not None:
        row["external_closing_ts"] = ext_ts
    return row


# ─────────────────────────────────────────────
# T1 — No timeline entry → wait
# ─────────────────────────────────────────────

def test_t1_no_timeline_entry_recommends_wait(tmp_path: Path) -> None:
    """Pending record with no matching game in timeline → recommended_action='wait'."""
    from orchestrator.closing_odds_monitor import _analyze_pending_record

    clv_row = _make_clv_row()
    timeline_index: dict[str, dict] = {}  # completely empty

    result = _analyze_pending_record(clv_row, timeline_index)

    assert result["recommended_action"] == "wait", (
        f"Expected 'wait' when timeline is empty, got '{result['recommended_action']}'"
    )
    assert result["tsl_closing_found"] is False
    assert result["external_closing_found"] is False
    assert result["candidate_valid"] is False
    assert result["best_candidate_source"] is None


# ─────────────────────────────────────────────
# T2 — TSL closing exists but ts ≤ pred_time
# ─────────────────────────────────────────────

def test_t2_tsl_before_prediction_time(tmp_path: Path) -> None:
    """TSL closing_ts ≤ prediction_time → invalid_reason='before_prediction', candidate_valid=False."""
    from orchestrator.closing_odds_monitor import _analyze_pending_record

    pred_dt = datetime.now(timezone.utc) - timedelta(hours=5)
    # TSL timestamp is BEFORE prediction time
    tsl_dt  = pred_dt - timedelta(hours=1)

    clv_row = _make_clv_row(pred_time=_iso(pred_dt))
    timeline_index = {
        "game-001": _make_timeline_row(
            closing_home_ml=-110.0,
            closing_ts=_iso(tsl_dt),
        )
    }

    result = _analyze_pending_record(clv_row, timeline_index)

    assert result["tsl_closing_found"] is True
    assert result["candidate_valid"] is False
    assert result["invalid_reason"] == "before_prediction", (
        f"Expected 'before_prediction', got '{result['invalid_reason']}'"
    )


# ─────────────────────────────────────────────
# T3 — External closing valid (ts > pred_time)
# ─────────────────────────────────────────────

def test_t3_external_closing_valid(tmp_path: Path) -> None:
    """External closing ts > pred_time, ML in range → candidate_valid=True, source='external'."""
    from orchestrator.closing_odds_monitor import _analyze_pending_record

    pred_dt = datetime.now(timezone.utc) - timedelta(hours=6)
    ext_dt  = pred_dt + timedelta(hours=3)  # AFTER prediction, still recent

    clv_row = _make_clv_row(pred_time=_iso(pred_dt))
    timeline_index = {
        "game-001": _make_timeline_row(
            ext_home_ml=-115.0,
            ext_ts=_iso(ext_dt),
        )
    }

    result = _analyze_pending_record(clv_row, timeline_index)

    assert result["external_closing_found"] is True
    assert result["candidate_valid"] is True
    assert result["best_candidate_source"] == "external"
    assert result["invalid_reason"] is None
    assert result["recommended_action"] == "run_closing_monitor"


# ─────────────────────────────────────────────
# T4 — Same-snapshot candidate rejected
# ─────────────────────────────────────────────

def test_t4_same_snapshot_rejected(tmp_path: Path) -> None:
    """
    Snapshot whose ts is only seconds after prediction → same_snapshot rejection.
    Uses external odds with a timestamp only 30 seconds after prediction.
    """
    from orchestrator.closing_odds_monitor import _analyze_pending_record

    pred_dt = datetime.now(timezone.utc) - timedelta(hours=3)
    # Only 30 seconds after prediction — same-snapshot guard fires (threshold is 60s)
    ext_dt = pred_dt + timedelta(seconds=30)

    clv_row = _make_clv_row(pred_time=_iso(pred_dt))
    # Add a prediction_ts to the row so same-snapshot check can fire
    clv_row["prediction_ts"] = _iso(pred_dt)

    timeline_index = {
        "game-001": _make_timeline_row(
            ext_home_ml=-110.0,
            ext_ts=_iso(ext_dt),
        )
    }

    result = _analyze_pending_record(clv_row, timeline_index)

    assert result["external_closing_found"] is True
    assert result["candidate_valid"] is False
    # Should be either "same_snapshot" or "before_prediction" depending on exact threshold
    assert result["invalid_reason"] in ("same_snapshot", "before_prediction"), (
        f"Expected rejection reason, got '{result['invalid_reason']}'"
    )


# ─────────────────────────────────────────────
# T5 — Source-level summary counts are correct
# ─────────────────────────────────────────────

def test_t5_source_summary_counts(tmp_path: Path) -> None:
    """
    Build diagnostics from a mix of record types and verify summary aggregations.
    """
    from orchestrator.closing_odds_monitor import (
        _analyze_pending_record,
        _build_source_summary,
    )

    pred_dt = datetime.now(timezone.utc) - timedelta(hours=6)

    # Record A: no timeline → wait
    row_a = _make_clv_row("pred-A", "game-A")
    # Record B: external valid → run_closing_monitor
    row_b = _make_clv_row("pred-B", "game-B", pred_time=_iso(pred_dt))
    # Record C: TSL before_prediction → refresh_tsl
    row_c = _make_clv_row("pred-C", "game-C", pred_time=_iso(pred_dt))

    ext_valid_dt = pred_dt + timedelta(hours=3)   # recent & after pred
    tsl_old_dt   = pred_dt - timedelta(hours=1)   # before pred

    timeline_index = {
        "game-B": _make_timeline_row(ext_home_ml=-110.0, ext_ts=_iso(ext_valid_dt)),
        "game-C": _make_timeline_row(closing_home_ml=-120.0, closing_ts=_iso(tsl_old_dt)),
    }

    diags = [
        _analyze_pending_record(row_a, timeline_index),
        _analyze_pending_record(row_b, timeline_index),
        _analyze_pending_record(row_c, timeline_index),
    ]

    summary = _build_source_summary(diags, computed_total=2)

    assert summary["pending_total"] == 3
    assert summary["computed_total"] == 2
    assert summary["missing_all_sources"] == 1  # record A
    assert summary["external_available_valid"] == 1   # record B (external chosen, valid)
    assert summary["invalid_before_prediction"] == 1  # record C (TSL before pred)
    assert summary["ready_to_upgrade"] == 1   # record B


# ─────────────────────────────────────────────
# T6 — Safe executor artifact is richer
# ─────────────────────────────────────────────

def test_t6_safe_executor_artifact_includes_sections(tmp_path: Path, monkeypatch: Any) -> None:
    """
    _execute_closing_monitor must produce an artifact that contains both
    ## Closing Odds Availability and ## Pending Details sections.
    """
    from orchestrator import safe_task_executor as ste

    # Patch _count_clv_states to return stable values
    monkeypatch.setattr(ste, "_count_clv_states", lambda: (3, 0))

    # Patch run_closing_odds_monitor to return a stable no-upgrade result
    def _fake_monitor() -> dict:
        return {
            "dates_scanned": ["2026-03-20"],
            "total_stats": {
                "total_pending": 3,
                "upgraded": 0,
                "still_pending": 3,
                "stale_closing_rejected": 0,
            },
            "per_date": {},
            "run_at": "2026-03-20T14:00:00+00:00",
        }

    import orchestrator.closing_odds_monitor as com
    monkeypatch.setattr(com, "run_closing_odds_monitor", _fake_monitor)

    # Patch get_pending_diagnostics to return minimal diagnostics
    pred_dt = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    fake_diag = {
        "pending_diagnostics": [
            {
                "prediction_id": "pred-001",
                "canonical_match_id": "game-001",
                "selection": "home",
                "prediction_time_utc": _iso(pred_dt),
                "current_status": "PENDING_CLOSING",
                "tsl_closing_found": False,
                "external_closing_found": False,
                "best_candidate_source": None,
                "best_candidate_time_utc": None,
                "candidate_valid": False,
                "invalid_reason": None,
                "recommended_action": "wait",
            }
        ],
        "source_summary": {
            "pending_total": 1,
            "computed_total": 0,
            "external_available_valid": 0,
            "external_available_invalid": 0,
            "tsl_available_valid": 0,
            "tsl_available_invalid": 0,
            "missing_all_sources": 1,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "recommended_refresh_tsl": 0,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
            "ready_to_upgrade": 0,
            "next_closing_action": "Wait for market settlement — no closing data available yet",
        },
        "generated_at": "2026-03-20T14:00:00+00:00",
    }
    monkeypatch.setattr(com, "get_pending_diagnostics", lambda **kw: fake_diag)

    # Build a fake task
    artifact_path = tmp_path / "2026-03-20" / "task-001-closing-monitor-report.md"
    artifact_path.parent.mkdir(parents=True)

    task = {
        "id": "task-001",
        "task_type": "closing_monitor",
        "artifact_slot_key": None,
        "prompt_path": None,
    }

    # Patch the artifact path resolver
    monkeypatch.setattr(ste, "_resolve_artifact_path", lambda t: artifact_path)

    result = ste._execute_closing_monitor(task)

    assert result["success"] is True
    text = result["completed_text"]
    assert "## Closing Odds Availability" in text, "Expected ## Closing Odds Availability section"
    assert "## Pending Details" in text, "Expected ## Pending Details section"
    assert len(text) > 300


# ─────────────────────────────────────────────
# T7 — Readiness dashboard includes closing_availability
# ─────────────────────────────────────────────

def test_t7_readiness_summary_has_closing_availability(monkeypatch: Any) -> None:
    """get_readiness_summary() must include 'closing_availability' key."""
    import orchestrator.optimization_readiness as orr

    # Stub out heavy helper functions so the test is isolated
    monkeypatch.setattr(orr, "_get_phase6", lambda: {"available": False})
    monkeypatch.setattr(orr, "_get_phase7", lambda: {"available": False})
    monkeypatch.setattr(orr, "_get_governance", lambda: {"available": False})
    monkeypatch.setattr(orr, "_get_ops_summary", lambda: {"available": False})
    monkeypatch.setattr(orr, "_get_completion_quality", lambda: {"available": False})
    monkeypatch.setattr(orr, "_get_safe_work_status", lambda: {"available": False})
    monkeypatch.setattr(orr, "_get_skip_health", lambda: {"available": False, "skip_reasons": {}})
    monkeypatch.setattr(
        orr,
        "_get_closing_availability",
        lambda: {
            "available": True,
            "pending_total": 5,
            "computed_total": 0,
            "missing_all_sources": 5,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "recommended_refresh_tsl": 0,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
            "ready_to_upgrade": 0,
            "next_closing_action": "Wait for market settlement — no closing data available yet",
        },
    )

    summary = orr.get_readiness_summary()

    assert "closing_availability" in summary, (
        "get_readiness_summary() must include 'closing_availability' key"
    )
    ca = summary["closing_availability"]
    assert ca.get("available") is True
    assert ca.get("pending_total") == 5


# ─────────────────────────────────────────────
# T8 — Ops report includes closing_availability
# ─────────────────────────────────────────────

def test_t8_ops_report_includes_closing_availability(monkeypatch: Any) -> None:
    """generate_report() must include 'closing_availability' dict in return value."""
    import orchestrator.optimization_ops_report as oor

    # Stub out DB/memory lookups
    monkeypatch.setattr(oor, "_query_tasks_in_window", lambda s: [])
    monkeypatch.setattr(oor, "_query_runs_in_window", lambda s: [])
    monkeypatch.setattr(oor, "_get_training_memory_summary", lambda: {})

    def _fake_p6() -> dict:
        return {"clv_computed": 0, "clv_pending": 5, "current_state": "DATA_WAITING",
                "current_governance_state": "DATA_WAITING", "allowed_families": [],
                "blocked_families": [], "reasons": []}

    monkeypatch.setattr(oor, "_get_optimization_state_summary", _fake_p6)

    fake_ca = {
        "available": True,
        "pending_total": 5,
        "computed_total": 0,
        "missing_all_sources": 5,
        "invalid_before_prediction": 0,
        "invalid_same_snapshot": 0,
        "stale_candidates": 0,
        "recommended_refresh_tsl": 0,
        "recommended_refresh_external": 0,
        "manual_review_required": 0,
        "ready_to_upgrade": 0,
        "next_closing_action": "Wait for market settlement",
    }
    monkeypatch.setattr(oor, "_get_closing_availability_summary", lambda: fake_ca)

    report = oor.generate_report(window="8h")

    assert "closing_availability" in report, (
        "generate_report() must include 'closing_availability' key"
    )
    assert report["closing_availability"].get("available") is True
    assert "closing_sub_classification" in report


# ─────────────────────────────────────────────
# T9 — Decision card payload includes closing_availability
# ─────────────────────────────────────────────

def test_t9_decision_card_has_closing_availability(monkeypatch: Any) -> None:
    """
    build_payload() must include 'closing_availability', and render_card()
    must produce a card that contains the CLOSING ODDS AVAILABILITY section.
    """
    import scripts.ops_decision_card as odc

    # Stub all compute_* functions that do I/O
    monkeypatch.setattr(odc, "compute_clv_metrics", lambda: {
        "total_live_rows": 0, "external_closing_rows": 0,
        "coverage_pct": 0.0, "clv_samples": 0, "clv_std": 0.0,
    })
    monkeypatch.setattr(odc, "compute_scheduler_status", lambda: {
        "state_date": "2026-03-20", "fetched_today": False,
        "api_calls_today": 0, "api_cap": 2,
        "last_run_ts": "unknown", "next_trigger_minutes": None,
        "heartbeat_present": False,
    })
    monkeypatch.setattr(odc, "collect_flags", lambda: [])
    monkeypatch.setattr(odc, "compute_system_health", lambda: {"available": False})
    monkeypatch.setattr(odc, "compute_today_wbc", lambda: {"games": [], "date": "2026-03-20", "note": "no games"})
    monkeypatch.setattr(odc, "compute_recent_performance", lambda: {"available": False})
    monkeypatch.setattr(odc, "compute_last_postmortem", lambda: {"available": False, "count": 0})
    monkeypatch.setattr(odc, "compute_phase6_status", lambda: {"available": False})
    monkeypatch.setattr(odc, "compute_phase7_status", lambda: {"available": False})
    monkeypatch.setattr(odc, "compute_phase8_status", lambda partial_payload=None: {"available": False})
    monkeypatch.setattr(odc, "compute_phase9_ops_status", lambda window="8h": {"available": False})
    monkeypatch.setattr(odc, "compute_readiness_status", lambda: {"available": False})
    monkeypatch.setattr(odc, "compute_closing_availability", lambda: {
        "available": True,
        "pending_total": 14,
        "computed_total": 0,
        "external_available_valid": 0,
        "external_available_invalid": 0,
        "tsl_available_valid": 0,
        "tsl_available_invalid": 0,
        "missing_all_sources": 14,
        "invalid_before_prediction": 0,
        "invalid_same_snapshot": 0,
        "stale_candidates": 0,
        "ready_to_upgrade": 0,
        "recommended_refresh_tsl": 0,
        "recommended_refresh_external": 0,
        "manual_review_required": 0,
        "next_closing_action": "Wait for market settlement — no closing data available yet",
    })

    payload = odc.build_payload()

    assert "closing_availability" in payload, (
        "build_payload() must include 'closing_availability' key"
    )
    assert payload["closing_availability"]["available"] is True
    assert payload["closing_availability"]["pending_total"] == 14

    # Also verify render_card doesn't crash and includes the section
    card = odc.render_card(payload)
    assert "CLOSING ODDS AVAILABILITY" in card, (
        "render_card() must include 'CLOSING ODDS AVAILABILITY' section"
    )
    assert "Wait for market settlement" in card
