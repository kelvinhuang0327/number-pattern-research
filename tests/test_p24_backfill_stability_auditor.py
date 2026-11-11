"""
tests/test_p24_backfill_stability_auditor.py

Integration tests for p24_backfill_stability_auditor.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    P24_BACKFILL_STABILITY_AUDIT_READY,
    P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
    P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES,
    STABILITY_ACCEPTABLE,
    STABILITY_SOURCE_INTEGRITY_BLOCKED,
)
from wbc_backend.recommendation.p24_backfill_stability_auditor import (
    _date_range,
    determine_p24_gate,
    run_backfill_stability_audit,
    write_p24_outputs,
)
from wbc_backend.recommendation.p24_backfill_stability_contract import (
    P24StabilityAuditSummary,
    P24StabilityGateResult,
)
from wbc_backend.recommendation.p24_source_integrity_auditor import (
    summarize_source_integrity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_P23_CSV_COLUMNS = [
    "run_date",
    "source_ready",
    "p15_preview_ready",
    "p16_6_gate",
    "p19_gate",
    "p17_replay_gate",
    "p20_gate",
    "date_gate",
    "n_recommended_rows",
    "n_active_paper_entries",
    "n_settled_win",
    "n_settled_loss",
    "n_unsettled",
    "total_stake_units",
    "total_pnl_units",
    "roi_units",
    "hit_rate",
    "game_id_coverage",
    "settlement_join_method",
    "blocker_reason",
    "paper_only",
    "production_ready",
]


def _make_p23_dir(tmp_path: Path, dates: list, identical_source: bool = True) -> Path:
    """Build a minimal P23 aggregate output directory."""
    p23_dir = tmp_path / "p23"
    p23_dir.mkdir()

    rows = []
    for d in dates:
        rows.append(
            {
                "run_date": d,
                "source_ready": True,
                "p15_preview_ready": True,
                "p16_6_gate": "P16_6_PAPER_RECOMMENDATION_GATE_READY",
                "p19_gate": "P19_IDENTITY_JOIN_REPAIR_READY",
                "p17_replay_gate": "P17_PAPER_LEDGER_READY",
                "p20_gate": "P20_DAILY_PAPER_ORCHESTRATOR_READY",
                "date_gate": "P23_DATE_REPLAY_READY",
                "n_recommended_rows": 100,
                "n_active_paper_entries": 100,
                "n_settled_win": 55,
                "n_settled_loss": 45,
                "n_unsettled": 0,
                "total_stake_units": 25.0,
                "total_pnl_units": 2.5,
                "roi_units": 0.10,
                "hit_rate": 0.55,
                "game_id_coverage": 1.0,
                "settlement_join_method": "JOIN_BY_GAME_ID",
                "blocker_reason": "",
                "paper_only": True,
                "production_ready": False,
            }
        )
    pd.DataFrame(rows).to_csv(p23_dir / "date_replay_results.csv", index=False)
    return p23_dir


def _make_paper_base(
    tmp_path: Path, dates: list, identical_source: bool = True
) -> Path:
    """Build materialized P15 input files under paper_base_dir."""
    base = tmp_path / "PAPER"
    base.mkdir()

    for i, d in enumerate(dates):
        mat_dir = base / d / "p23_historical_replay" / "p15_materialized"
        mat_dir.mkdir(parents=True)
        # All dates use the same game_ids if identical_source=True
        game_ids = (
            [f"2025-05-08_T{j:03d}" for j in range(20)]
            if identical_source
            else [f"{d}_T{j:03d}" for j in range(20 + i)]
        )
        game_date = "2025-05-08" if identical_source else d
        df = pd.DataFrame(
            {
                "run_date": [d] * len(game_ids),
                "game_id": game_ids,
                "game_date": [game_date] * len(game_ids),
                "y_true": [1] * len(game_ids),
                "p_oof": [0.55] * len(game_ids),
                "edge": [0.05] * len(game_ids),
            }
        )
        df.to_csv(mat_dir / "joined_oof_with_odds.csv", index=False)

    return base


# ---------------------------------------------------------------------------
# _date_range
# ---------------------------------------------------------------------------


def test_date_range_inclusive():
    r = _date_range("2026-05-01", "2026-05-03")
    assert r == ["2026-05-01", "2026-05-02", "2026-05-03"]


def test_date_range_single():
    r = _date_range("2026-05-01", "2026-05-01")
    assert r == ["2026-05-01"]


# ---------------------------------------------------------------------------
# run_backfill_stability_audit — duplicate source path
# ---------------------------------------------------------------------------


def test_audit_blocks_duplicate_source_replay(tmp_path):
    dates = [f"2026-05-{d:02d}" for d in range(1, 4)]
    p23_dir = _make_p23_dir(tmp_path, dates, identical_source=True)
    paper_base = _make_paper_base(tmp_path, dates, identical_source=True)

    summary, gate_result, raw = run_backfill_stability_audit(
        date_start="2026-05-01",
        date_end="2026-05-03",
        p23_dir=str(p23_dir),
        paper_base_dir=str(paper_base),
    )
    assert gate_result.p24_gate == P24_BLOCKED_DUPLICATE_SOURCE_REPLAY
    assert gate_result.n_duplicate_source_groups >= 1
    assert gate_result.production_ready is False
    assert gate_result.paper_only is True


def test_audit_ready_for_independent_sources(tmp_path):
    dates = [f"2026-05-{d:02d}" for d in range(1, 5)]
    p23_dir = _make_p23_dir(tmp_path, dates, identical_source=False)
    paper_base = _make_paper_base(tmp_path, dates, identical_source=False)

    summary, gate_result, raw = run_backfill_stability_audit(
        date_start="2026-05-01",
        date_end="2026-05-04",
        p23_dir=str(p23_dir),
        paper_base_dir=str(paper_base),
    )
    assert gate_result.p24_gate == P24_BACKFILL_STABILITY_AUDIT_READY
    assert gate_result.n_duplicate_source_groups == 0
    assert gate_result.n_independent_source_dates >= 2


def test_audit_fails_on_missing_p23_csv(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_backfill_stability_audit(
            date_start="2026-05-01",
            date_end="2026-05-02",
            p23_dir=str(tmp_path / "nonexistent"),
            paper_base_dir=str(tmp_path / "PAPER"),
        )


# ---------------------------------------------------------------------------
# determine_p24_gate
# ---------------------------------------------------------------------------


def _make_source_profile_blocked():
    from wbc_backend.recommendation.p24_backfill_stability_contract import (
        P24SourceIntegrityProfile,
    )
    return P24SourceIntegrityProfile(
        n_dates_audited=12,
        n_independent_source_dates=0,
        n_duplicate_source_groups=1,
        source_hash_unique_count=1,
        source_hash_duplicate_count=11,
        game_id_set_unique_count=1,
        all_dates_date_mismatch=True,
        any_date_date_mismatch=True,
        duplicate_findings=(),
        audit_status=STABILITY_SOURCE_INTEGRITY_BLOCKED,
        blocker_reason="all dates duplicate",
    )


def _make_source_profile_ok():
    from wbc_backend.recommendation.p24_backfill_stability_contract import (
        P24SourceIntegrityProfile,
    )
    return P24SourceIntegrityProfile(
        n_dates_audited=5,
        n_independent_source_dates=5,
        n_duplicate_source_groups=0,
        source_hash_unique_count=5,
        source_hash_duplicate_count=0,
        game_id_set_unique_count=5,
        all_dates_date_mismatch=False,
        any_date_date_mismatch=False,
        duplicate_findings=(),
        audit_status=STABILITY_ACCEPTABLE,
        blocker_reason="",
    )


def _make_aggregate():
    return {
        "aggregate_roi_units": 0.10,
        "aggregate_hit_rate": 0.55,
        "total_stake_units": 100.0,
        "total_pnl_units": 10.0,
    }


def _make_variance():
    return {
        "roi_std_by_date": 0.0,
        "roi_min_by_date": 0.10,
        "roi_max_by_date": 0.10,
        "hit_rate_std_by_date": 0.0,
        "hit_rate_min_by_date": 0.55,
        "hit_rate_max_by_date": 0.55,
        "active_entry_std_by_date": 0.0,
        "active_entry_min_by_date": 100,
        "active_entry_max_by_date": 100,
    }


def test_gate_blocked_duplicate_source():
    gate_result, summary = determine_p24_gate(
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_dates=12,
        source_profile=_make_source_profile_blocked(),
        aggregate=_make_aggregate(),
        variance=_make_variance(),
        is_perf_suspicious=True,
        perf_reason="identical ROI",
    )
    assert gate_result.p24_gate == P24_BLOCKED_DUPLICATE_SOURCE_REPLAY
    assert summary.paper_only is True
    assert summary.production_ready is False


def test_gate_ready_for_independent():
    gate_result, summary = determine_p24_gate(
        date_start="2026-05-01",
        date_end="2026-05-05",
        n_dates=5,
        source_profile=_make_source_profile_ok(),
        aggregate=_make_aggregate(),
        variance=_make_variance(),
        is_perf_suspicious=False,
        perf_reason="",
    )
    assert gate_result.p24_gate == P24_BACKFILL_STABILITY_AUDIT_READY


# ---------------------------------------------------------------------------
# write_p24_outputs — 6 files produced
# ---------------------------------------------------------------------------


def test_writes_all_6_output_files(tmp_path):
    dates = ["2026-05-01", "2026-05-02"]
    p23_dir = _make_p23_dir(tmp_path, dates)
    paper_base = _make_paper_base(tmp_path, dates, identical_source=True)

    summary, gate_result, raw = run_backfill_stability_audit(
        date_start="2026-05-01",
        date_end="2026-05-02",
        p23_dir=str(p23_dir),
        paper_base_dir=str(paper_base),
    )
    out_dir = tmp_path / "p24_out"
    files = write_p24_outputs(str(out_dir), summary, gate_result, raw)

    expected = {
        "stability_audit_summary.json",
        "stability_audit_summary.md",
        "source_integrity_audit.json",
        "performance_stability_audit.json",
        "duplicate_source_findings.json",
        "p24_gate_result.json",
    }
    assert set(files.keys()) == expected
    for name, path in files.items():
        assert Path(path).exists(), f"Missing output file: {name}"


def test_gate_result_json_has_correct_gate(tmp_path):
    dates = ["2026-05-01", "2026-05-02"]
    p23_dir = _make_p23_dir(tmp_path, dates)
    paper_base = _make_paper_base(tmp_path, dates, identical_source=True)

    summary, gate_result, raw = run_backfill_stability_audit(
        date_start="2026-05-01",
        date_end="2026-05-02",
        p23_dir=str(p23_dir),
        paper_base_dir=str(paper_base),
    )
    out_dir = tmp_path / "p24_out"
    write_p24_outputs(str(out_dir), summary, gate_result, raw)

    with open(out_dir / "p24_gate_result.json") as f:
        data = json.load(f)
    assert data["p24_gate"] == P24_BLOCKED_DUPLICATE_SOURCE_REPLAY
    assert data["paper_only"] is True
    assert data["production_ready"] is False


def test_summary_json_paper_only_true(tmp_path):
    dates = ["2026-05-01"]
    p23_dir = _make_p23_dir(tmp_path, dates)
    paper_base = _make_paper_base(tmp_path, dates, identical_source=True)

    summary, gate_result, raw = run_backfill_stability_audit(
        date_start="2026-05-01",
        date_end="2026-05-01",
        p23_dir=str(p23_dir),
        paper_base_dir=str(paper_base),
    )
    out_dir = tmp_path / "p24_out"
    write_p24_outputs(str(out_dir), summary, gate_result, raw)

    with open(out_dir / "stability_audit_summary.json") as f:
        data = json.load(f)
    assert data["paper_only"] is True
    assert data["production_ready"] is False


def test_duplicate_source_findings_json_nonempty(tmp_path):
    dates = ["2026-05-01", "2026-05-02"]
    p23_dir = _make_p23_dir(tmp_path, dates)
    paper_base = _make_paper_base(tmp_path, dates, identical_source=True)

    summary, gate_result, raw = run_backfill_stability_audit(
        date_start="2026-05-01",
        date_end="2026-05-02",
        p23_dir=str(p23_dir),
        paper_base_dir=str(paper_base),
    )
    out_dir = tmp_path / "p24_out"
    write_p24_outputs(str(out_dir), summary, gate_result, raw)

    with open(out_dir / "duplicate_source_findings.json") as f:
        data = json.load(f)
    assert data["n_duplicate_source_groups"] >= 1
    assert len(data["findings"]) >= 1
