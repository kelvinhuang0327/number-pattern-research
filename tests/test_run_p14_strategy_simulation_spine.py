"""
tests/test_run_p14_strategy_simulation_spine.py

P14: Tests for scripts/run_p14_strategy_simulation_spine.py

Covers:
- CLI argument parsing
- Refusals: missing OOF dir, non-PASS gate, non-PAPER output prefix
- Successful run: creates simulation_summary.json, simulation_summary.md, simulation_ledger.csv
- JSON outputs: paper_only=True, production_ready=False, spine_gate present
- Ledger CSV: at least 1 row, paper_only column present
- Determinism: two runs produce identical JSON metrics (excluding generated_at_utc)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

# Add project root to path so the CLI can be imported
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.run_p14_strategy_simulation_spine import main as cli_main


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _write_p13_artifacts(tmp_dir: Path, n: int = 60, gate: str = "PASS", bss: float = 0.008253) -> Path:
    """Write oof_predictions.csv and oof_report.json to tmp_dir."""
    import numpy as np
    rng = np.random.RandomState(0)
    y = rng.randint(0, 2, size=n)
    p = rng.uniform(0.35, 0.75, size=n)
    fold_ids = [i % 5 + 1 for i in range(n)]
    df = pd.DataFrame({
        "y_true": y,
        "p_oof": p,
        "fold_id": fold_ids,
        "source_model": "p13_walk_forward_logistic",
        "source_bss_oof": bss,
        "paper_only": True,
    })
    df.to_csv(tmp_dir / "oof_predictions.csv", index=False)

    report = {
        "bss_oof": bss,
        "gate_decision": gate,
        "n_samples_total": n,
        "paper_only": True,
    }
    (tmp_dir / "oof_report.json").write_text(json.dumps(report), encoding="utf-8")
    return tmp_dir


def _make_output_dir(base: Path) -> Path:
    """Create an output dir under outputs/predictions/PAPER for test isolation."""
    out = base / "outputs" / "predictions" / "PAPER" / "p14_test"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ── Refusal tests ─────────────────────────────────────────────────────────────

class TestRefusals:
    def test_refuses_missing_p13_dir(self, tmp_path: Path) -> None:
        out = _make_output_dir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cli_main([
                "--p13-oof-dir", str(tmp_path / "nonexistent"),
                "--output-dir", str(out),
            ])
        assert exc.value.code == 2

    def test_refuses_non_pass_gate(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13_fail"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, gate="FAIL")
        out = _make_output_dir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cli_main([
                "--p13-oof-dir", str(p13_dir),
                "--output-dir", str(out),
            ])
        assert exc.value.code == 2

    def test_refuses_output_outside_paper_zone(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13_ok"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, gate="PASS")
        bad_out = tmp_path / "not_paper" / "output"
        bad_out.mkdir(parents=True)
        with pytest.raises(SystemExit) as exc:
            cli_main([
                "--p13-oof-dir", str(p13_dir),
                "--output-dir", str(bad_out),
            ])
        assert exc.value.code == 2

    def test_refuses_invalid_policy_name(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13_ok"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, gate="PASS")
        out = _make_output_dir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cli_main([
                "--p13-oof-dir", str(p13_dir),
                "--output-dir", str(out),
                "--policies", "flat,INVALID_POLICY",
            ])
        assert exc.value.code == 2


# ── Successful run tests ──────────────────────────────────────────────────────

class TestSuccessfulRun:
    def _run_cli(self, p13_dir: Path, out_dir: Path) -> None:
        cli_main([
            "--p13-oof-dir", str(p13_dir),
            "--output-dir", str(out_dir),
            "--policies", "flat,capped_kelly,confidence_rank,no_bet",
            "--paper-only",
        ])

    def test_creates_output_files(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        assert (out / "simulation_summary.json").exists()
        assert (out / "simulation_summary.md").exists()
        assert (out / "simulation_ledger.csv").exists()

    def test_json_paper_only_true(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        data = json.loads((out / "simulation_summary.json").read_text())
        assert data["paper_only"] is True

    def test_json_production_ready_false(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        data = json.loads((out / "simulation_summary.json").read_text())
        assert data["production_ready"] is False

    def test_json_spine_gate_present(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        data = json.loads((out / "simulation_summary.json").read_text())
        assert "spine_gate" in data
        assert data["spine_gate"] in {
            "PASS_SIMULATION_SPINE_READY",
            "MARKET_ODDS_ABSENT_SIMULATION_ONLY",
            "FAIL_INVALID_INPUT",
            "FAIL_NON_DETERMINISTIC",
        }

    def test_json_source_bss_matches(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, bss=0.008253)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        data = json.loads((out / "simulation_summary.json").read_text())
        assert abs(data["source_bss_oof"] - 0.008253) < 1e-6

    def test_ledger_csv_has_rows(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, n=60)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        with (out / "simulation_ledger.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0

    def test_ledger_csv_paper_only_column(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, n=40)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        with (out / "simulation_ledger.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            assert "paper_only" in row

    def test_md_contains_spine_gate_marker(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        md = (out / "simulation_summary.md").read_text()
        assert "P14_STRATEGY_SIMULATION_SPINE_READY" in md

    def test_per_policy_in_json(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir)
        out = _make_output_dir(tmp_path)
        self._run_cli(p13_dir, out)
        data = json.loads((out / "simulation_summary.json").read_text())
        assert "per_policy" in data
        for policy in ["flat", "capped_kelly", "confidence_rank", "no_bet"]:
            assert policy in data["per_policy"]


# ── Determinism tests ─────────────────────────────────────────────────────────

class TestCLIDeterminism:
    def test_two_runs_produce_identical_metrics(self, tmp_path: Path) -> None:
        p13_dir = tmp_path / "p13_det"
        p13_dir.mkdir()
        _write_p13_artifacts(p13_dir, n=80)

        out_a = tmp_path / "outputs" / "predictions" / "PAPER" / "run_a"
        out_b = tmp_path / "outputs" / "predictions" / "PAPER" / "run_b"
        out_a.mkdir(parents=True)
        out_b.mkdir(parents=True)

        cli_main([
            "--p13-oof-dir", str(p13_dir),
            "--output-dir", str(out_a),
            "--policies", "flat,confidence_rank,no_bet",
        ])
        cli_main([
            "--p13-oof-dir", str(p13_dir),
            "--output-dir", str(out_b),
            "--policies", "flat,confidence_rank,no_bet",
        ])

        def _load_core(p: Path) -> dict:
            data = json.loads((p / "simulation_summary.json").read_text())
            # Remove timestamps before comparison
            data.pop("generated_at_utc", None)
            for policy_data in data.get("per_policy", {}).values():
                policy_data.pop("generated_at_utc", None)
            return data

        data_a = _load_core(out_a)
        data_b = _load_core(out_b)
        assert data_a == data_b, (
            "CLI produces different summary JSON on two runs with identical input."
        )
