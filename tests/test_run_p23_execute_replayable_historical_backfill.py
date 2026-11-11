"""
tests/test_run_p23_execute_replayable_historical_backfill.py

Subprocess-based tests for the P23 CLI.

Tests confirm:
- Exits 2 when --paper-only false
- Exits 2 when --p22-5-dir missing
- Exits 1 when P22.5 plan has no dates ready (all blocked)
- Emits all 6 required output files on success path
- gate_result.json has paper_only=true, production_ready=false
- Deterministic: two runs on same input produce identical gate/summary
  (excluding generated_at timestamp)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
CLI = str(REPO_ROOT / "scripts" / "run_p23_execute_replayable_historical_backfill.py")
ENV = {
    "PYTHONPATH": str(REPO_ROOT),
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _run(args: list[str], *, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, CLI] + args,
        capture_output=True,
        text=True,
        env=ENV,
        cwd=cwd or str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Helpers — minimal mock P22.5 dir with NO ready dates
# ---------------------------------------------------------------------------

def _make_empty_p22_5_dir(base: Path) -> Path:
    """A P22.5 dir with a valid readiness plan but zero dates ready."""
    p22_5_dir = base / "p22_5_out"
    p22_5_dir.mkdir(parents=True, exist_ok=True)

    plan = {
        "schema_version": "P22_5_v1",
        "generated_at": "2026-05-12T00:00:00+00:00",
        "paper_only": True,
        "production_ready": False,
        "date_start": "2026-05-01",
        "date_end": "2026-05-12",
        "dates_ready_to_build_p15_inputs": [],
        "dates_blocked": [
            {"date": "2026-05-01", "reason": "TEST_MOCK"},
        ],
        "readiness_gate": "P22_5_BLOCKED_NO_SOURCES",
        "source_artifact_path": str(p22_5_dir / "no_source.csv"),
        "recommended_next_action": "Fix source",
    }
    (p22_5_dir / "p15_readiness_plan.json").write_text(json.dumps(plan))

    # source_candidate_inventory.json — empty, no usable candidates
    inventory = {
        "candidates": [],
        "usable_candidates": [],
    }
    (p22_5_dir / "source_candidate_inventory.json").write_text(json.dumps(inventory))

    return p22_5_dir


def _make_single_date_p22_5_dir(base: Path, run_date: str) -> Path:
    """
    A P22.5 dir declaring one date ready with a minimal joined_oof_with_odds.csv
    that has all required columns.
    """
    p22_5_dir = base / "p22_5_out"
    p22_5_dir.mkdir(parents=True, exist_ok=True)

    # Write minimal source CSV (needs all REQUIRED_MATERIALIZED_COLUMNS)
    src_csv = p22_5_dir / "joined_oof_with_odds.csv"
    rows = [
        "y_true,p_oof,game_id,game_date,odds_decimal_home,odds_decimal_away,p_market,edge,run_date",
        "1,0.55,G001,2026-05-12,1.90,2.10,0.5263,0.0237,2026-05-12",
        "0,0.45,G002,2026-05-12,2.10,1.90,0.4762,-0.0262,2026-05-12",
    ]
    src_csv.write_text("\n".join(rows))

    plan = {
        "schema_version": "P22_5_v1",
        "generated_at": "2026-05-12T00:00:00+00:00",
        "paper_only": True,
        "production_ready": False,
        "date_start": run_date,
        "date_end": run_date,
        "dates_ready_to_build_p15_inputs": [run_date],
        "dates_blocked": [],
        "readiness_gate": "P22_5_HISTORICAL_SOURCE_ARTIFACT_BUILDER_READY",
        "source_artifact_path": str(src_csv),
        "recommended_next_action": "Proceed to P23",
    }
    (p22_5_dir / "p15_readiness_plan.json").write_text(json.dumps(plan))

    inventory = {
        "candidates": [
            {
                "candidate_id": "CAND_001",
                "candidate_status": "SOURCE_CANDIDATE_USABLE",
                "source_type": "HISTORICAL_P15_JOINED_INPUT",
                "file_path": str(src_csv),
                "n_rows": 2,
            }
        ],
        "usable_candidates": [
            {
                "candidate_id": "CAND_001",
                "candidate_status": "SOURCE_CANDIDATE_USABLE",
                "source_type": "HISTORICAL_P15_JOINED_INPUT",
                "file_path": str(src_csv),
                "n_rows": 2,
            }
        ],
    }
    (p22_5_dir / "source_candidate_inventory.json").write_text(json.dumps(inventory))

    return p22_5_dir


# ---------------------------------------------------------------------------
# Guard tests (paper-only, missing dir)
# ---------------------------------------------------------------------------

class TestCLIGuards:
    def test_exits_2_when_paper_only_false(self, tmp_path):
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        result = _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "false",
        ])
        assert result.returncode == 2, (
            f"Expected 2, got {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_exits_2_when_p22_5_dir_missing(self, tmp_path):
        result = _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(tmp_path / "nonexistent_dir"),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "true",
        ])
        assert result.returncode == 2, (
            f"Expected 2, got {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_exits_2_when_plan_missing(self, tmp_path):
        # Dir exists but no plan file inside
        missing_plan_dir = tmp_path / "no_plan"
        missing_plan_dir.mkdir()
        result = _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(missing_plan_dir),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "true",
        ])
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# Blocked path (no ready dates)
# ---------------------------------------------------------------------------

class TestCLIBlockedPath:
    def test_exits_1_when_all_dates_blocked(self, tmp_path):
        """
        With a P22.5 plan that has zero ready dates, the CLI should complete
        with exit code 1 (BLOCKED) and produce output files.
        """
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        out_dir = tmp_path / "out"

        result = _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        ])
        assert result.returncode == 1, (
            f"Expected 1, got {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_blocked_output_has_correct_gate(self, tmp_path):
        """p23_gate_result.json must exist even in the blocked path."""
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        out_dir = tmp_path / "out"

        result = _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        ])
        gate_path = out_dir / "p23_gate_result.json"
        assert gate_path.exists(), (
            f"Gate file missing. returncode={result.returncode}\nstdout={result.stdout}"
        )
        gate_data = json.loads(gate_path.read_text())
        # All dates blocked → gate is not READY
        from wbc_backend.recommendation.p23_historical_replay_contract import (
            P23_HISTORICAL_REPLAY_BACKFILL_READY,
        )
        assert gate_data["p23_gate"] != P23_HISTORICAL_REPLAY_BACKFILL_READY
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False

    def test_blocked_output_produces_6_files(self, tmp_path):
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        out_dir = tmp_path / "out"

        _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        ])

        required_files = [
            "historical_replay_summary.json",
            "historical_replay_summary.md",
            "date_replay_results.csv",
            "blocked_dates.json",
            "artifact_manifest.json",
            "p23_gate_result.json",
        ]
        for fname in required_files:
            assert (out_dir / fname).exists(), f"Missing output file: {fname}"


# ---------------------------------------------------------------------------
# Determinism check (blocked path — no subprocess pipelines invoked)
# ---------------------------------------------------------------------------

class TestCLIDeterminism:
    def test_deterministic_on_blocked_path(self, tmp_path):
        """
        Two sequential runs with identical inputs should produce identical
        p23_gate_result.json contents, excluding the 'generated_at' field.
        """
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        common_args = [
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--paper-only", "true",
        ]
        _run(common_args + ["--output-dir", str(out1)])
        _run(common_args + ["--output-dir", str(out2)])

        gate1 = json.loads((out1 / "p23_gate_result.json").read_text())
        gate2 = json.loads((out2 / "p23_gate_result.json").read_text())

        # Remove volatile field before comparing
        for d in (gate1, gate2):
            d.pop("generated_at", None)

        assert gate1 == gate2, (
            f"Non-deterministic gate result.\nRun1: {gate1}\nRun2: {gate2}"
        )

    def test_summary_deterministic_on_blocked_path(self, tmp_path):
        """historical_replay_summary.json should also be deterministic (excl. generated_at)."""
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        common_args = [
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--paper-only", "true",
        ]
        _run(common_args + ["--output-dir", str(out1)])
        _run(common_args + ["--output-dir", str(out2)])

        sum1 = json.loads((out1 / "historical_replay_summary.json").read_text())
        sum2 = json.loads((out2 / "historical_replay_summary.json").read_text())

        for d in (sum1, sum2):
            d.pop("generated_at", None)

        assert sum1 == sum2

    def test_csv_deterministic_on_blocked_path(self, tmp_path):
        """date_replay_results.csv should be byte-identical across runs."""
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        common_args = [
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--paper-only", "true",
        ]
        _run(common_args + ["--output-dir", str(out1)])
        _run(common_args + ["--output-dir", str(out2)])

        csv1 = (out1 / "date_replay_results.csv").read_text()
        csv2 = (out2 / "date_replay_results.csv").read_text()
        assert csv1 == csv2


# ---------------------------------------------------------------------------
# paper_only / production_ready guards in output
# ---------------------------------------------------------------------------

class TestCLIPaperOnlyFlags:
    def test_gate_result_paper_only_true(self, tmp_path):
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        out_dir = tmp_path / "out"

        _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        ])

        gate_data = json.loads((out_dir / "p23_gate_result.json").read_text())
        assert gate_data["paper_only"] is True

    def test_gate_result_production_ready_false(self, tmp_path):
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        out_dir = tmp_path / "out"

        _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        ])

        gate_data = json.loads((out_dir / "p23_gate_result.json").read_text())
        assert gate_data["production_ready"] is False

    def test_summary_paper_only_true(self, tmp_path):
        p22_5_dir = _make_empty_p22_5_dir(tmp_path)
        out_dir = tmp_path / "out"

        _run([
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--p22-5-dir", str(p22_5_dir),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        ])

        data = json.loads((out_dir / "historical_replay_summary.json").read_text())
        assert data["paper_only"] is True
        assert data["production_ready"] is False
