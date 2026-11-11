"""
tests/test_run_p17_paper_recommendation_ledger.py

Integration tests for scripts/run_p17_paper_recommendation_ledger.py CLI.

Tests:
  - CLI emits all 6 required output files
  - Gate decision written to ledger_gate_result.json
  - CLI deterministic across two runs (excluding generated_at)
  - paper_only=false → exit 2
  - Missing input → exit 2
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

ELIGIBLE_GATE = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
BLOCKED_GATE = "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"

BASE_ROW = dict(
    game_id="2025-05-08_MIN_BAL",
    date="2025-05-08",
    side="HOME",
    p_model=0.60,
    p_market=0.55,
    edge=0.0535,
    odds_decimal=1.80,
    paper_stake_fraction=0.0025,
    strategy_policy="capped_kelly_p18",
    gate_reason="eligible",
    source_model="test_model",
    source_bss_oof=0.05,
    odds_join_status="JOINED",
    paper_only=True,
    production_ready=False,
    created_from="P16_6_RECOMMENDATION_GATE_RERUN_WITH_P18_POLICY",
    selected_edge_threshold=0.05,
    p18_policy_id="e0p0500_s0p0025_k0p10_o2p50",
    p18_edge_threshold=0.05,
    p18_max_stake_cap=0.0025,
    p18_kelly_fraction=0.10,
    p18_odds_decimal_max=2.5,
    p18_policy_max_drawdown_pct=1.847,
    p18_policy_sharpe_ratio=0.1016,
    p18_policy_n_bets=324,
    p18_policy_roi_ci_low_95=-0.99,
    p18_policy_roi_ci_high_95=20.78,
)

REC_SUMMARY = {
    "p16_6_gate": "P16_6_PAPER_RECOMMENDATION_GATE_READY",
    "p18_source_gate": "P18_STRATEGY_POLICY_RISK_REPAIRED",
    "p18_policy_id": "e0p0500_s0p0025_k0p10_o2p50",
    "n_recommended_rows": 1,
    "paper_only": True,
    "production_ready": False,
}

P15_ROW = dict(
    row_idx=0,
    fold_id=0,
    y_true=1.0,
    p_model=0.60,
    p_market=0.55,
    decimal_odds=1.80,
    confidence_rank=1,
    policy="capped_kelly",
    should_bet=True,
    stake_fraction=0.0025,
    reason="ELIGIBLE",
    paper_only=True,
)


def _make_rec_rows_csv(tmp_path: Path, rows: list[dict] | None = None) -> Path:
    if rows is None:
        rows = [{**BASE_ROW, "recommendation_id": "R-001",
                 "gate_decision": ELIGIBLE_GATE}]
    df = pd.DataFrame(rows)
    path = tmp_path / "recommendation_rows.csv"
    df.to_csv(path, index=False)
    return path


def _make_rec_summary_json(tmp_path: Path) -> Path:
    path = tmp_path / "recommendation_summary.json"
    path.write_text(json.dumps(REC_SUMMARY))
    return path


def _make_p15_ledger_csv(tmp_path: Path) -> Path:
    df = pd.DataFrame([P15_ROW])
    path = tmp_path / "simulation_ledger.csv"
    df.to_csv(path, index=False)
    return path


def _run_cli(
    tmp_path: Path,
    rec_rows: Path,
    rec_summary: Path,
    p15_ledger: Path,
    output_dir: Path,
    bankroll: float = 100.0,
    paper_only: str = "true",
) -> subprocess.CompletedProcess:
    script = (
        Path(__file__).resolve().parent.parent / "scripts" / "run_p17_paper_recommendation_ledger.py"
    )
    cmd = [
        sys.executable, str(script),
        "--recommendation-rows", str(rec_rows),
        "--recommendation-summary", str(rec_summary),
        "--p15-ledger", str(p15_ledger),
        "--output-dir", str(output_dir),
        "--bankroll-units", str(bankroll),
        "--paper-only", paper_only,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestCLIOutputFiles:
    def test_all_six_output_files_emitted(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"

        result = _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        assert result.returncode in (0, 1), (
            f"unexpected returncode={result.returncode}\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        expected_files = [
            "paper_recommendation_ledger.csv",
            "paper_recommendation_ledger_summary.json",
            "paper_recommendation_ledger_summary.md",
            "settlement_join_audit.json",
            "settlement_join_audit.md",
            "ledger_gate_result.json",
        ]
        for fname in expected_files:
            assert (output_dir / fname).is_file(), f"Missing output file: {fname}"

    def test_gate_decision_in_ledger_gate_result(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        gate_data = json.loads((output_dir / "ledger_gate_result.json").read_text())
        assert "gate_decision" in gate_data
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False

    def test_summary_json_has_required_fields(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        summary = json.loads((output_dir / "paper_recommendation_ledger_summary.json").read_text())
        for field in ["p17_gate", "n_recommendation_rows", "n_active_paper_entries",
                      "paper_only", "production_ready", "generated_at"]:
            assert field in summary, f"Missing field: {field}"

    def test_ledger_csv_has_settlement_columns(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        ledger_df = pd.read_csv(output_dir / "paper_recommendation_ledger.csv")
        for col in ["ledger_id", "settlement_status", "pnl_units", "roi",
                    "is_win", "is_loss", "paper_only", "production_ready"]:
            assert col in ledger_df.columns, f"Missing ledger column: {col}"

    def test_audit_json_has_join_quality(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        audit = json.loads((output_dir / "settlement_join_audit.json").read_text())
        assert "join_quality" in audit
        assert "join_coverage" in audit
        assert "risk_notes" in audit


class TestCLIDeterminism:
    def _hash_file_excluding_generated_at(self, path: Path) -> str:
        """SHA-256 of JSON file content with generated_at removed."""
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            data.pop("generated_at", None)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _hash_csv(self, path: Path) -> str:
        """SHA-256 of CSV content."""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_deterministic_across_two_runs(self, tmp_path):
        """Second run must produce bit-identical outputs (excluding generated_at)."""
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, out1)
        _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, out2)

        for fname in [
            "paper_recommendation_ledger.csv",
        ]:
            h1 = self._hash_csv(out1 / fname)
            h2 = self._hash_csv(out2 / fname)
            assert h1 == h2, f"Non-deterministic output: {fname}"

        for fname in [
            "paper_recommendation_ledger_summary.json",
            "settlement_join_audit.json",
            "ledger_gate_result.json",
        ]:
            h1 = self._hash_file_excluding_generated_at(out1 / fname)
            h2 = self._hash_file_excluding_generated_at(out2 / fname)
            assert h1 == h2, f"Non-deterministic JSON (excluding generated_at): {fname}"


class TestCLISafetyGuards:
    def test_paper_only_false_exits_2(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        result = _run_cli(
            tmp_path, rec_rows, rec_summary, p15_ledger, output_dir,
            paper_only="false",
        )
        assert result.returncode == 2

    def test_missing_rec_rows_exits_2(self, tmp_path):
        rec_rows = tmp_path / "nonexistent.csv"
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        result = _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        assert result.returncode == 2

    def test_missing_p15_ledger_exits_2(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = tmp_path / "nonexistent_ledger.csv"
        output_dir = tmp_path / "p17_out"
        result = _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        assert result.returncode == 2

    def test_missing_rec_summary_exits_2(self, tmp_path):
        rec_rows = _make_rec_rows_csv(tmp_path)
        rec_summary = tmp_path / "nonexistent_summary.json"
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        result = _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        assert result.returncode == 2


class TestCLIBlockedRows:
    def test_all_blocked_rows_emits_gate_blocked(self, tmp_path):
        rows = [{**BASE_ROW, "recommendation_id": "R-001",
                 "gate_decision": "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"}]
        rec_rows = _make_rec_rows_csv(tmp_path, rows=rows)
        rec_summary = _make_rec_summary_json(tmp_path)
        p15_ledger = _make_p15_ledger_csv(tmp_path)
        output_dir = tmp_path / "p17_out"
        result = _run_cli(tmp_path, rec_rows, rec_summary, p15_ledger, output_dir)
        # Should exit 1 (blocked)
        assert result.returncode == 1
        gate_data = json.loads((output_dir / "ledger_gate_result.json").read_text())
        assert "BLOCKED" in gate_data["gate_decision"]
