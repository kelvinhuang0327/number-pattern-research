"""
Phase 32 Tests — CLV Accumulation & Monitoring Policy
=======================================================
12 tests covering:
  1.  computed_count=14 → INSUFFICIENT
  2.  computed_count=30 → APPROACHING
  3.  computed_count=50 → SUFFICIENT
  4.  learning_cycle_allowed=True when count >= 1
  5.  patch_gate_recheck_allowed=False when count < 50
  6.  patch_gate_recheck_allowed=True when count >= 50
  7.  priority_segments loaded from Phase 31 training_memory
  8.  readiness summary includes clv_accumulation key
  9.  ops report includes clv_accumulation key
 10.  decision card build_payload includes clv_accumulation key (renders section)
 11.  no patch task generated while INSUFFICIENT
 12.  report file generated on --apply
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.clv_accumulation_policy import (
    EVIDENCE_APPROACHING,
    EVIDENCE_INSUFFICIENT,
    EVIDENCE_SUFFICIENT,
    EVIDENCE_THRESHOLD_APPROACHING,
    EVIDENCE_THRESHOLD_SUFFICIENT,
    evaluate_clv_accumulation,
    evaluate_clv_accumulation_from_count,
    get_clv_accumulation_summary,
)
from scripts.run_phase32_clv_accumulation_monitor import (
    EXIT_TOKEN,
    EXECUTION_MODE,
    LIVE_BET_SUBMITTED,
    PRODUCTION_MUTATION,
    SOURCE_MARKER,
    build_report_markdown,
    load_computed_clv_records,
    run_monitor,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _make_records(n: int) -> list[dict]:
    """Return n minimal COMPUTED CLV record dicts."""
    return [{"prediction_id": f"pred_{i:04d}", "clv_status": "COMPUTED", "clv_value": 0.01 * i} for i in range(n)]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def _make_clv_file(tmpdir: Path, n: int = 14) -> Path:
    """Create a minimal CLV validation JSONL file with n COMPUTED records."""
    reports = tmpdir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    clv_file = reports / "clv_validation_records_6u_2026-04-30.jsonl"
    rows = _make_records(n)
    _write_jsonl(clv_file, rows)
    return reports


def _make_memory_with_investigation(tmpdir: Path) -> Path:
    """Create a minimal training_memory.json with a Phase 31 investigation entry."""
    mem_dir = tmpdir / "runtime" / "agent_orchestrator"
    mem_dir.mkdir(parents=True, exist_ok=True)
    mem_path = mem_dir / "training_memory.json"

    investigation = {
        "task_id": "phase31_inv_test",
        "investigation_type": "production_clv_segment_analysis",
        "weak_segments": [
            {
                "segment_type": "selection",
                "segment_value": "YES",
                "reliability": "RELIABILITY_NEGATIVE",
                "mean_clv": -0.012,
                "positive_rate": 0.30,
                "count": 8,
            }
        ],
        "promising_segments": [
            {
                "segment_type": "ev_bucket",
                "segment_value": "negative_ev",
                "reliability": "RELIABILITY_POSITIVE",
                "mean_clv": 0.025,
                "positive_rate": 0.67,
                "count": 6,
            }
        ],
    }

    mem_data = {
        "learning_cycles": [],
        "gate_decisions": [],
        "clv_investigations": [investigation],
    }
    mem_path.write_text(json.dumps(mem_data, indent=2), encoding="utf-8")
    return mem_path


# ── Test 1: evidence state INSUFFICIENT for n=14 ───────────────────────────

def test_evidence_state_insufficient_at_14():
    records = _make_records(14)
    result = evaluate_clv_accumulation(records=records)
    assert result["evidence_state"] == EVIDENCE_INSUFFICIENT
    assert result["computed_count"] == 14
    assert result["threshold"] == EVIDENCE_THRESHOLD_SUFFICIENT
    assert result["remaining_needed"] == 36
    assert result["progress_pct"] == pytest.approx(28.0, abs=0.1)


# ── Test 2: evidence state APPROACHING for n=30 ────────────────────────────

def test_evidence_state_approaching_at_30():
    records = _make_records(30)
    result = evaluate_clv_accumulation(records=records)
    assert result["evidence_state"] == EVIDENCE_APPROACHING
    assert result["computed_count"] == 30
    assert result["remaining_needed"] == 20


# ── Test 3: evidence state SUFFICIENT for n=50 ─────────────────────────────

def test_evidence_state_sufficient_at_50():
    records = _make_records(50)
    result = evaluate_clv_accumulation(records=records)
    assert result["evidence_state"] == EVIDENCE_SUFFICIENT
    assert result["computed_count"] == 50
    assert result["remaining_needed"] == 0
    assert result["progress_pct"] == pytest.approx(100.0, abs=0.1)


# ── Test 4: learning_cycle_allowed is True when count >= 1 ─────────────────

def test_learning_cycle_allowed_when_count_gte_1():
    result = evaluate_clv_accumulation(records=_make_records(1))
    assert result["learning_cycle_allowed"] is True

    # Zero records → not allowed
    result_zero = evaluate_clv_accumulation(records=[])
    assert result_zero["learning_cycle_allowed"] is False


# ── Test 5: patch_gate_recheck_allowed is False when count < 50 ────────────

def test_patch_gate_recheck_blocked_below_threshold():
    for n in [0, 1, 14, 29, 30, 49]:
        result = evaluate_clv_accumulation(records=_make_records(n))
        assert result["patch_gate_recheck_allowed"] is False, (
            f"Expected patch_gate_recheck_allowed=False for n={n}, got True"
        )


# ── Test 6: patch_gate_recheck_allowed is True when count >= 50 ────────────

def test_patch_gate_recheck_allowed_at_threshold():
    for n in [50, 51, 100]:
        result = evaluate_clv_accumulation(records=_make_records(n))
        assert result["patch_gate_recheck_allowed"] is True, (
            f"Expected patch_gate_recheck_allowed=True for n={n}, got False"
        )


# ── Test 7: priority_segments loaded from Phase 31 memory ─────────────────

def test_priority_segments_loaded_from_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        mem_path = _make_memory_with_investigation(Path(tmpdir))
        result = evaluate_clv_accumulation(
            records=_make_records(14),
            memory_path=mem_path,
        )
        segs = result["priority_segments"]
        assert len(segs) == 2, f"Expected 2 priority segments, got {len(segs)}"
        # All segments must be marked observation-only
        for seg in segs:
            assert seg["observation_only_until_threshold"] is True
        # Classifications present
        classifications = {s["classification"] for s in segs}
        assert "weak" in classifications
        assert "promising" in classifications


# ── Test 8: readiness summary includes clv_accumulation ───────────────────

def test_readiness_summary_includes_clv_accumulation():
    """get_readiness_summary() must include the clv_accumulation key."""
    from orchestrator.optimization_readiness import get_readiness_summary

    summary = get_readiness_summary()
    assert "clv_accumulation" in summary, (
        "get_readiness_summary() must include 'clv_accumulation' key"
    )
    # Should be a dict (may be empty if files are unavailable in test env)
    assert isinstance(summary["clv_accumulation"], dict)


# ── Test 9: ops report includes clv_accumulation ──────────────────────────

def test_ops_report_includes_clv_accumulation():
    """optimization_ops_report.generate_report() must include clv_accumulation key."""
    from orchestrator.optimization_ops_report import generate_report

    report = generate_report(window="8h")
    assert "clv_accumulation" in report, (
        "generate_report() must include 'clv_accumulation' key"
    )
    assert isinstance(report["clv_accumulation"], dict)


# ── Test 10: decision card payload includes clv_accumulation ──────────────

def test_decision_card_renders_accumulation_state():
    """build_payload() must include clv_accumulation; render_card() must output section."""
    from scripts.ops_decision_card import build_payload, render_card

    payload = build_payload()
    assert "clv_accumulation" in payload, (
        "build_payload() must include 'clv_accumulation' key"
    )
    assert isinstance(payload["clv_accumulation"], dict)

    # render_card should output at least the section header
    card = render_card(payload)
    assert "CLV ACCUMULATION" in card or "clv_accumulation" in card.lower(), (
        "render_card() should render a CLV accumulation section"
    )


# ── Test 11: no patch task generated while INSUFFICIENT ───────────────────

def test_no_patch_task_while_insufficient():
    """Accumulation policy must hard-block patch candidates when INSUFFICIENT."""
    records = _make_records(14)  # INSUFFICIENT
    result = evaluate_clv_accumulation(records=records)

    assert result["evidence_state"] == EVIDENCE_INSUFFICIENT
    # patch_candidate_allowed must always be False
    assert result["patch_candidate_allowed"] is False
    # patch gate recheck must be blocked
    assert result["patch_gate_recheck_allowed"] is False
    # Scheduler recommendations must NOT include patch tasks
    sched_recs = result.get("scheduler_recommendations", [])
    patch_recs = [r for r in sched_recs if "PATCH" in r.upper() and "NO_PATCH" not in r.upper()]
    assert len(patch_recs) == 0, (
        f"No patch-type recommendations should appear when INSUFFICIENT; got {patch_recs}"
    )
    # Verify the NO_PATCH signal is explicitly present
    assert "NO_PATCH_TASKS" in sched_recs


# ── Test 12: report file generated on apply ───────────────────────────────

def test_report_generated_on_apply():
    """run_monitor(apply=True) must write a markdown report to docs/orchestration/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        reports_dir = _make_clv_file(tmppath, n=14)
        docs_dir = tmppath / "docs" / "orchestration"
        mem_path = _make_memory_with_investigation(tmppath)

        result = run_monitor(
            clv_dir=reports_dir,
            docs_dir=docs_dir,
            memory_path=mem_path,
            apply=True,
            task_id="test_phase32_report",
        )

        assert result["applied"] is True
        assert result["exit_token"] == EXIT_TOKEN

        report_path = Path(result["report_path"])
        assert report_path.exists(), f"Report file not found: {report_path}"

        content = report_path.read_text(encoding="utf-8")
        assert "Phase 32" in content
        assert "CLV Accumulation" in content
        assert EXIT_TOKEN in content

        # Verify hard rules compliance section
        assert "No patch candidate generated" in content
        assert "No live bet submitted" in content


# ── Hard rule constants ────────────────────────────────────────────────────

def test_hard_rule_constants():
    """Verify script constants enforce paper-only mode."""
    assert EXECUTION_MODE == "PAPER_ONLY"
    assert PRODUCTION_MUTATION is False
    assert LIVE_BET_SUBMITTED is False
    assert SOURCE_MARKER == "production/paper"
    assert EXIT_TOKEN == "PHASE_32_CLV_ACCUMULATION_POLICY_VERIFIED"
