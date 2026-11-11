"""
tests/test_run_p24_backfill_performance_stability_audit.py

CLI tests for scripts/run_p24_backfill_performance_stability_audit.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = str(REPO_ROOT / "scripts" / "run_p24_backfill_performance_stability_audit.py")
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")


def _run_cli(*args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [PYTHON, CLI] + list(args),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_p23_dir(tmp_path: Path, dates: list) -> Path:
    p23_dir = tmp_path / "p23"
    p23_dir.mkdir(parents=True, exist_ok=True)
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
    base = tmp_path / "PAPER"
    base.mkdir()
    for i, d in enumerate(dates):
        mat_dir = base / d / "p23_historical_replay" / "p15_materialized"
        mat_dir.mkdir(parents=True)
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
# TestCLIGuards
# ---------------------------------------------------------------------------


class TestCLIGuards:
    def test_paper_only_false_exits_2(self, tmp_path):
        dates = ["2026-05-01"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates)
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "false",
        )
        assert result.returncode == 2
        assert "paper-only" in result.stderr.lower() or "guard" in result.stderr.lower()

    def test_missing_p23_dir_exits_2(self, tmp_path):
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p23-dir", str(tmp_path / "nonexistent"),
            "--paper-base-dir", str(tmp_path / "PAPER"),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "true",
        )
        assert result.returncode == 2

    def test_missing_paper_base_exits_2(self, tmp_path):
        dates = ["2026-05-01"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(tmp_path / "NONEXISTENT"),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "true",
        )
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# TestCLIBlockedPath
# ---------------------------------------------------------------------------


class TestCLIBlockedPath:
    def test_duplicate_source_exits_1(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=True)
        out_dir = tmp_path / "out"
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        assert result.returncode == 1
        assert "P24_BLOCKED_DUPLICATE_SOURCE_REPLAY" in result.stdout

    def test_blocked_still_writes_6_files(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=True)
        out_dir = tmp_path / "out"
        _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        expected_files = [
            "stability_audit_summary.json",
            "stability_audit_summary.md",
            "source_integrity_audit.json",
            "performance_stability_audit.json",
            "duplicate_source_findings.json",
            "p24_gate_result.json",
        ]
        for fname in expected_files:
            assert (out_dir / fname).exists(), f"Missing: {fname}"

    def test_gate_json_not_ready(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=True)
        out_dir = tmp_path / "out"
        _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        with open(out_dir / "p24_gate_result.json") as f:
            data = json.load(f)
        assert data["p24_gate"] != "P24_BACKFILL_STABILITY_AUDIT_READY"
        assert data["paper_only"] is True
        assert data["production_ready"] is False


# ---------------------------------------------------------------------------
# TestCLIReadyPath
# ---------------------------------------------------------------------------


class TestCLIReadyPath:
    def test_independent_sources_exits_0(self, tmp_path):
        dates = [f"2026-05-{d:02d}" for d in range(1, 5)]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=False)
        out_dir = tmp_path / "out"
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-04",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        assert result.returncode == 0
        assert "P24_BACKFILL_STABILITY_AUDIT_READY" in result.stdout


# ---------------------------------------------------------------------------
# TestCLIDeterminism
# ---------------------------------------------------------------------------


class TestCLIDeterminism:
    def _run_and_load(self, tmp_path, dates, out_name, identical_source=True):
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=identical_source)
        out_dir = tmp_path / out_name
        _run_cli(
            "--date-start", dates[0],
            "--date-end", dates[-1],
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        return out_dir

    def test_gate_result_deterministic(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_a = _make_p23_dir(tmp_path / "a", dates)
        paper_a = _make_paper_base(tmp_path / "a", dates, identical_source=True)
        p23_b = _make_p23_dir(tmp_path / "b", dates)
        paper_b = _make_paper_base(tmp_path / "b", dates, identical_source=True)
        out_1 = tmp_path / "run1"
        out_2 = tmp_path / "run2"

        _run_cli(
            "--date-start", "2026-05-01", "--date-end", "2026-05-02",
            "--p23-dir", str(p23_a), "--paper-base-dir", str(paper_a),
            "--output-dir", str(out_1), "--paper-only", "true",
        )
        _run_cli(
            "--date-start", "2026-05-01", "--date-end", "2026-05-02",
            "--p23-dir", str(p23_b), "--paper-base-dir", str(paper_b),
            "--output-dir", str(out_2), "--paper-only", "true",
        )

        for fname in [
            "p24_gate_result.json",
            "source_integrity_audit.json",
            "performance_stability_audit.json",
            "duplicate_source_findings.json",
        ]:
            with open(out_1 / fname) as f1, open(out_2 / fname) as f2:
                d1 = json.load(f1)
                d2 = json.load(f2)
            # Remove generated_at before comparing
            d1.pop("generated_at", None)
            d2.pop("generated_at", None)
            assert d1 == d2, f"Non-deterministic: {fname}"

    def test_summary_csv_deterministic(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_a = _make_p23_dir(tmp_path / "a", dates)
        paper_a = _make_paper_base(tmp_path / "a", dates, identical_source=True)
        p23_b = _make_p23_dir(tmp_path / "b", dates)
        paper_b = _make_paper_base(tmp_path / "b", dates, identical_source=True)
        out_1 = tmp_path / "run1"
        out_2 = tmp_path / "run2"

        _run_cli(
            "--date-start", "2026-05-01", "--date-end", "2026-05-02",
            "--p23-dir", str(p23_a), "--paper-base-dir", str(paper_a),
            "--output-dir", str(out_1), "--paper-only", "true",
        )
        _run_cli(
            "--date-start", "2026-05-01", "--date-end", "2026-05-02",
            "--p23-dir", str(p23_b), "--paper-base-dir", str(paper_b),
            "--output-dir", str(out_2), "--paper-only", "true",
        )

        with open(out_1 / "stability_audit_summary.json") as f1:
            s1 = json.load(f1)
        with open(out_2 / "stability_audit_summary.json") as f2:
            s2 = json.load(f2)
        s1.pop("generated_at", None)
        s2.pop("generated_at", None)
        assert s1 == s2


# ---------------------------------------------------------------------------
# TestCLIPaperOnlyFlags
# ---------------------------------------------------------------------------


class TestCLIPaperOnlyFlags:
    def test_gate_and_summary_paper_only_true(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=True)
        out_dir = tmp_path / "out"
        _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        with open(out_dir / "p24_gate_result.json") as f:
            gate_data = json.load(f)
        with open(out_dir / "stability_audit_summary.json") as f:
            summary_data = json.load(f)
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False
        assert summary_data["paper_only"] is True
        assert summary_data["production_ready"] is False

    def test_stdout_contains_production_ready_false(self, tmp_path):
        dates = ["2026-05-01", "2026-05-02"]
        p23_dir = _make_p23_dir(tmp_path, dates)
        paper_base = _make_paper_base(tmp_path, dates, identical_source=True)
        out_dir = tmp_path / "out"
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--p23-dir", str(p23_dir),
            "--paper-base-dir", str(paper_base),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        assert "production_ready" in result.stdout
        assert "False" in result.stdout
