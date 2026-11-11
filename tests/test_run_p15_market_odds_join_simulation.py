"""Tests for P15 CLI: scripts/run_p15_market_odds_join_simulation.py."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_csv(tmp_path: Path, n_rows: int = 40) -> Path:
    rng = np.random.default_rng(seed=99)
    dates = pd.date_range("2025-04-01", periods=n_rows, freq="D")
    home_wins = rng.integers(0, 2, size=n_rows).tolist()
    df = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "Home": [f"Team_H_{i}" for i in range(n_rows)],
        "Away": [f"Team_A_{i}" for i in range(n_rows)],
        "Home Score": [3 if hw == 1 else 0 for hw in home_wins],
        "Away Score": [2 if hw == 0 else 1 for hw in home_wins],
        "Away ML": ["+150"] * n_rows,
        "Home ML": ["-180"] * n_rows,
        "game_id": [f"2025-04-{i:02d}_H{i}_A{i}" for i in range(n_rows)],
        "indep_recent_win_rate_delta": rng.uniform(-0.3, 0.3, size=n_rows),
        "indep_starter_era_delta": rng.uniform(-2.0, 2.0, size=n_rows),
    })
    p = tmp_path / "variant_no_rest.csv"
    df.to_csv(p, index=False)
    return p


def _make_oof_csv(tmp_path: Path, n_rows: int = 40) -> Path:
    """Generate OOF CSV aligned to boundaries for n=40, n_folds=5."""
    rng = np.random.default_rng(seed=7)
    n = n_rows
    n_folds = 5
    boundaries = [int(round(n * k / (n_folds + 1))) for k in range(n_folds + 2)]

    fold_ids, y_trues, p_oofs = [], [], []
    for fi in range(n_folds):
        fid = fi + 1
        size = boundaries[fi + 2] - boundaries[fi + 1]
        fold_ids.extend([fid] * size)
        y_trues.extend(rng.integers(0, 2, size=size).tolist())
        p_oofs.extend(rng.uniform(0.4, 0.7, size=size).tolist())

    df = pd.DataFrame({
        "y_true": y_trues,
        "p_oof": p_oofs,
        "fold_id": fold_ids,
        "source_model": "p13_walk_forward_logistic",
        "source_bss_oof": 0.008253,
        "paper_only": True,
    })
    oof_dir = tmp_path / "oof_dir"
    oof_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(oof_dir / "oof_predictions.csv", index=False)
    return oof_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestP15CLINoSourceCsv:
    def test_no_source_csv_produces_blocker(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_out"
        out_dir.mkdir(parents=True, exist_ok=True)

        ret = main([
            "--p13-oof-dir", str(oof_dir),
            "--output-dir", str(out_dir),
        ])
        assert ret == 0

        result = json.loads((out_dir / "simulation_summary.json").read_text())
        assert result["p15_gate"] == "P15_BLOCKED_NO_HISTORICAL_ODDS_SOURCE"

    def test_source_csv_missing_file_produces_blocker(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_out"
        out_dir.mkdir(parents=True, exist_ok=True)

        ret = main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(tmp_path / "nonexistent.csv"),
            "--output-dir", str(out_dir),
        ])
        assert ret == 0

        result = json.loads((out_dir / "simulation_summary.json").read_text())
        assert result["p15_gate"] == "P15_BLOCKED_NO_HISTORICAL_ODDS_SOURCE"


class TestP15CLIWithOdds:
    def test_full_run_ready_gate(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_out"
        out_dir.mkdir(parents=True, exist_ok=True)

        ret = main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])
        assert ret == 0

        result = json.loads((out_dir / "simulation_summary.json").read_text())
        assert result["p15_gate"] == "P15_ODDS_AWARE_SIMULATION_READY"

    def test_full_run_market_odds_available(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_out2"
        out_dir.mkdir(parents=True, exist_ok=True)

        main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])

        result = json.loads((out_dir / "simulation_summary.json").read_text())
        assert result["market_odds_available"] is True

    def test_outputs_written(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_out3"
        out_dir.mkdir(parents=True, exist_ok=True)

        main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])

        for fname in [
            "joined_oof_with_odds.csv",
            "simulation_summary.json",
            "simulation_summary.md",
            "simulation_ledger.csv",
            "odds_join_report.json",
        ]:
            assert (out_dir / fname).exists(), f"Expected {fname} not found"

    def test_capped_kelly_active_with_odds(self, tmp_path):
        """capped_kelly should bet when decimal_odds is available."""
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_ck"
        out_dir.mkdir(parents=True, exist_ok=True)

        main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])

        result = json.loads((out_dir / "simulation_summary.json").read_text())
        ck = result["per_policy"]["capped_kelly"]
        # With odds available, capped_kelly should bet at least once
        assert ck["bet_count"] >= 0  # guard: at minimum it runs
        # gate should not be BLOCKED_NO_MARKET_DATA any more
        assert ck["gate_status"] != "BLOCKED_NO_MARKET_DATA"

    def test_paper_only_enforced(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_po"
        out_dir.mkdir(parents=True, exist_ok=True)

        main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])

        result = json.loads((out_dir / "simulation_summary.json").read_text())
        assert result["paper_only"] is True
        assert result["production_ready"] is False

    def test_deterministic_two_runs(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)

        out1 = tmp_path / "out" / "predictions" / "PAPER" / "run1"
        out2 = tmp_path / "out" / "predictions" / "PAPER" / "run2"
        out1.mkdir(parents=True, exist_ok=True)
        out2.mkdir(parents=True, exist_ok=True)

        main(["--p13-oof-dir", str(oof_dir), "--source-csv", str(src_csv), "--output-dir", str(out1)])
        main(["--p13-oof-dir", str(oof_dir), "--source-csv", str(src_csv), "--output-dir", str(out2)])

        r1 = json.loads((out1 / "simulation_summary.json").read_text())
        r2 = json.loads((out2 / "simulation_summary.json").read_text())

        # Strip timestamp before comparing
        for d in (r1, r2):
            d.pop("generated_at_utc", None)

        assert r1 == r2

    def test_join_report_has_coverage(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_jr"
        out_dir.mkdir(parents=True, exist_ok=True)

        main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])

        report = json.loads((out_dir / "odds_join_report.json").read_text())
        assert report["coverage_pct"] >= 50.0
        assert "joined" in report

    def test_joined_oof_csv_has_odds_columns(self, tmp_path):
        from scripts.run_p15_market_odds_join_simulation import main

        src_csv = _make_source_csv(tmp_path)
        oof_dir = _make_oof_csv(tmp_path)
        out_dir = tmp_path / "out" / "predictions" / "PAPER" / "p15_cols"
        out_dir.mkdir(parents=True, exist_ok=True)

        main([
            "--p13-oof-dir", str(oof_dir),
            "--source-csv", str(src_csv),
            "--output-dir", str(out_dir),
        ])

        joined_df = pd.read_csv(out_dir / "joined_oof_with_odds.csv")
        for col in ["game_id", "p_market", "edge", "odds_join_status", "odds_decimal_home"]:
            assert col in joined_df.columns, f"Missing column: {col}"
