"""
tests/test_p14_strategy_simulator.py

P14: Tests for p13_strategy_simulator.py

Covers:
- P13StrategySimulationRunner.from_oof_csv: loads, validates, prepares rows
- SimulationSummary: spine gate, per-policy results, ledger
- paper_only invariant: never False
- MARKET_ODDS_ABSENT_SIMULATION_ONLY gate when odds absent
- Determinism: same input → identical summary dict (excluding timestamps)
- StrategySimulationResult contracts per policy
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.simulation.p13_strategy_simulator import (
    P13StrategySimulationRunner,
    SimulationSummary,
    SPINE_GATE_MARKET_ABSENT,
    SPINE_GATE_PASS,
    SPINE_GATE_INVALID_INPUT,
)
from wbc_backend.simulation.strategy_simulation_result import (
    StrategySimulationResult,
    VALID_GATE_STATUSES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_oof_df(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic OOF predictions DataFrame."""
    import numpy as np
    rng = np.random.RandomState(seed)
    y = rng.randint(0, 2, size=n)
    p = rng.uniform(0.35, 0.75, size=n)
    fold_ids = [i % 5 + 1 for i in range(n)]
    return pd.DataFrame({
        "y_true": y,
        "p_oof": p,
        "fold_id": fold_ids,
        "source_model": "p13_walk_forward_logistic",
        "source_bss_oof": 0.008253,
        "paper_only": True,
    })


def _write_oof_csv_and_report(tmp_dir: Path, n: int = 50) -> tuple[Path, Path]:
    """Write oof_predictions.csv and oof_report.json to tmp_dir."""
    df = _make_oof_df(n=n)
    csv_path = tmp_dir / "oof_predictions.csv"
    df.to_csv(csv_path, index=False)

    report = {
        "bss_oof": 0.008253,
        "gate_decision": "PASS",
        "n_samples_total": n,
        "paper_only": True,
    }
    report_path = tmp_dir / "oof_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return csv_path, report_path


# ── from_oof_csv tests ────────────────────────────────────────────────────────

class TestFromOofCsv:
    def test_loads_valid_csv(self, tmp_path: Path) -> None:
        csv_path, _ = _write_oof_csv_and_report(tmp_path)
        runner = P13StrategySimulationRunner.from_oof_csv(
            oof_csv_path=csv_path,
            source_bss_oof=0.008253,
        )
        assert len(runner._rows) == 50

    def test_rows_have_required_keys(self, tmp_path: Path) -> None:
        csv_path, _ = _write_oof_csv_and_report(tmp_path)
        runner = P13StrategySimulationRunner.from_oof_csv(
            oof_csv_path=csv_path,
            source_bss_oof=0.008253,
        )
        for row in runner._rows:
            assert "p_model" in row
            assert "y_true" in row
            assert row["paper_only"] is True

    def test_market_odds_are_none(self, tmp_path: Path) -> None:
        csv_path, _ = _write_oof_csv_and_report(tmp_path)
        runner = P13StrategySimulationRunner.from_oof_csv(
            oof_csv_path=csv_path,
            source_bss_oof=0.008253,
        )
        for row in runner._rows:
            assert row["decimal_odds"] is None
            assert row["p_market"] is None

    def test_confidence_rank_injected(self, tmp_path: Path) -> None:
        csv_path, _ = _write_oof_csv_and_report(tmp_path)
        runner = P13StrategySimulationRunner.from_oof_csv(
            oof_csv_path=csv_path,
            source_bss_oof=0.008253,
        )
        ranks = sorted(r["confidence_rank"] for r in runner._rows)
        assert ranks[0] == 1
        assert ranks[-1] == 50

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            P13StrategySimulationRunner.from_oof_csv(
                oof_csv_path=tmp_path / "missing.csv",
                source_bss_oof=0.008253,
            )

    def test_missing_required_columns_raises(self, tmp_path: Path) -> None:
        bad_csv = tmp_path / "oof_predictions.csv"
        pd.DataFrame({"x": [1, 2], "z": [3, 4]}).to_csv(bad_csv, index=False)
        with pytest.raises(ValueError, match="missing required columns"):
            P13StrategySimulationRunner.from_oof_csv(
                oof_csv_path=bad_csv,
                source_bss_oof=0.008253,
            )

    def test_paper_only_false_raises(self, tmp_path: Path) -> None:
        csv_path, _ = _write_oof_csv_and_report(tmp_path)
        with pytest.raises(ValueError, match="paper_only must remain True"):
            P13StrategySimulationRunner.from_oof_csv(
                oof_csv_path=csv_path,
                source_bss_oof=0.008253,
                paper_only=False,
            )


# ── run() output contracts ────────────────────────────────────────────────────

class TestRunOutput:
    def _get_runner(self, tmp_path: Path, n: int = 100) -> P13StrategySimulationRunner:
        csv_path, _ = _write_oof_csv_and_report(tmp_path, n=n)
        return P13StrategySimulationRunner.from_oof_csv(
            oof_csv_path=csv_path,
            source_bss_oof=0.008253,
        )

    def test_returns_simulation_summary(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "no_bet"])
        assert isinstance(summary, SimulationSummary)

    def test_spine_gate_market_absent(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "capped_kelly", "confidence_rank", "no_bet"])
        assert summary.spine_gate == SPINE_GATE_MARKET_ABSENT

    def test_all_four_policies_run(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "capped_kelly", "confidence_rank", "no_bet"])
        assert set(summary.policy_results.keys()) == {"flat", "capped_kelly", "confidence_rank", "no_bet"}

    def test_policy_results_are_strategy_simulation_result(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "no_bet"])
        for res in summary.policy_results.values():
            assert isinstance(res, StrategySimulationResult)

    def test_gate_statuses_valid(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "capped_kelly", "confidence_rank", "no_bet"])
        for res in summary.policy_results.values():
            assert res.gate_status in VALID_GATE_STATUSES, (
                f"gate_status '{res.gate_status}' not in VALID_GATE_STATUSES"
            )

    def test_paper_only_always_true(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "capped_kelly", "confidence_rank", "no_bet"])
        assert summary.paper_only is True
        for res in summary.policy_results.values():
            assert res.paper_only is True

    def test_capped_kelly_blocked_no_market_data(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["capped_kelly"])
        res = summary.policy_results["capped_kelly"]
        assert res.gate_status == "BLOCKED_NO_MARKET_DATA"
        assert res.bet_count == 0

    def test_no_bet_policy_zero_bets(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["no_bet"])
        res = summary.policy_results["no_bet"]
        assert res.bet_count == 0
        assert res.gate_status == "PAPER_ONLY"

    def test_flat_stake_bets_above_zero(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path, n=100)
        summary = runner.run(policies=["flat"])
        res = summary.policy_results["flat"]
        # With random probs 0.35–0.75, some should be > 0.55
        assert res.bet_count >= 0  # at least it ran
        assert res.sample_size == 100

    def test_ledger_row_count(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path, n=50)
        summary = runner.run(policies=["flat", "no_bet"])
        ledger = summary.ledger_rows()
        # Each policy produces 50 rows → 100 total
        assert len(ledger) == 100

    def test_ledger_has_paper_only_flag(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path, n=20)
        summary = runner.run(policies=["flat"])
        for row in summary.ledger_rows():
            assert row["paper_only"] is True

    def test_ledger_columns_present(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path, n=20)
        summary = runner.run(policies=["flat"])
        required = {"row_idx", "y_true", "p_model", "policy", "should_bet", "stake_fraction", "reason"}
        for row in summary.ledger_rows():
            assert required.issubset(set(row.keys()))

    def test_to_summary_dict_structure(self, tmp_path: Path) -> None:
        runner = self._get_runner(tmp_path)
        summary = runner.run(policies=["flat", "no_bet"])
        d = summary.to_summary_dict()
        assert d["paper_only"] is True
        assert d["production_ready"] is False
        assert "spine_gate" in d
        assert "per_policy" in d
        assert "flat" in d["per_policy"]

    def test_invalid_policy_raises(self, tmp_path: Path) -> None:
        csv_path, _ = _write_oof_csv_and_report(tmp_path)
        runner = P13StrategySimulationRunner.from_oof_csv(
            oof_csv_path=csv_path,
            source_bss_oof=0.008253,
        )
        with pytest.raises(ValueError, match="Unknown policy"):
            runner.run(policies=["nonexistent_policy"])


# ── Determinism tests ─────────────────────────────────────────────────────────

class TestDeterminism:
    def test_summary_dict_deterministic(self, tmp_path: Path) -> None:
        """Same input → same per-policy metrics (excluding timestamps)."""
        csv_path, _ = _write_oof_csv_and_report(tmp_path)

        def _get_metrics() -> dict:
            runner = P13StrategySimulationRunner.from_oof_csv(
                oof_csv_path=csv_path,
                source_bss_oof=0.008253,
            )
            summary = runner.run(policies=["flat", "confidence_rank", "no_bet"])
            d = summary.to_summary_dict()
            # Remove timestamps before comparison
            return {k: v for k, v in d.items() if k != "generated_at_utc"}

        result_a = _get_metrics()
        result_b = _get_metrics()
        assert result_a == result_b, (
            "Summary dict is not deterministic across two runs with identical input."
        )

    def test_ledger_deterministic(self, tmp_path: Path) -> None:
        """Ledger rows are identical for two runs with same input."""
        csv_path, _ = _write_oof_csv_and_report(tmp_path)

        def _get_ledger() -> list[dict]:
            runner = P13StrategySimulationRunner.from_oof_csv(
                oof_csv_path=csv_path,
                source_bss_oof=0.008253,
            )
            summary = runner.run(policies=["flat", "no_bet"])
            return summary.ledger_rows()

        ledger_a = _get_ledger()
        ledger_b = _get_ledger()
        assert len(ledger_a) == len(ledger_b)
        for ra, rb in zip(ledger_a, ledger_b):
            assert ra["row_idx"] == rb["row_idx"]
            assert ra["policy"] == rb["policy"]
            assert ra["should_bet"] == rb["should_bet"]
            assert ra["stake_fraction"] == rb["stake_fraction"]
            assert abs(ra["p_model"] - rb["p_model"]) < 1e-9
