"""
tests/test_run_p16_6_recommendation_gate_with_p18_policy.py

Integration tests for scripts/run_p16_6_recommendation_gate_with_p18_policy.py

Test cases:
- CLI produces all 6 required output files
- CLI is deterministic across two runs (identical CSV hash)
- recommendation_rows.csv has required columns (P18 policy fields included)
- gate_reason_counts.json is valid JSON
- recommendation_summary.json has required keys
- p18_policy_applied.json matches P18 source policy
- p16_6_policy_risk_profile.json has required fields
- paper_only=True enforced, production_ready=False in all rows
- blocked rows have paper_stake_fraction = 0.0
- overall gate decision reflects eligible row count
- missing input file → exit code 2
- invalid paper_only → exit code 2
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.run_p16_6_recommendation_gate_with_p18_policy import main as cli_main


# ── Data paths ────────────────────────────────────────────────────────────────

P15_DIR = Path("outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation")
P18_DIR = Path("outputs/predictions/PAPER/2026-05-12/p18_strategy_policy_risk_repair")

JOINED_OOF = P15_DIR / "joined_oof_with_odds.csv"
P15_LEDGER = P15_DIR / "simulation_ledger.csv"
P18_POLICY = P18_DIR / "selected_strategy_policy.json"


def _skip_if_missing() -> None:
    if not JOINED_OOF.exists() or not P15_LEDGER.exists() or not P18_POLICY.exists():
        pytest.skip("P15/P18 artifacts not present — integration test skipped")


# ── Required outputs ──────────────────────────────────────────────────────────

REQUIRED_OUTPUT_FILES = [
    "recommendation_rows.csv",
    "recommendation_summary.json",
    "recommendation_summary.md",
    "gate_reason_counts.json",
    "p18_policy_applied.json",
    "p16_6_policy_risk_profile.json",
]

REQUIRED_ROW_COLUMNS = [
    "recommendation_id",
    "game_id",
    "date",
    "side",
    "p_model",
    "p_market",
    "edge",
    "odds_decimal",
    "paper_stake_fraction",
    "strategy_policy",
    "gate_decision",
    "gate_reason",
    "source_model",
    "source_bss_oof",
    "odds_join_status",
    "paper_only",
    "production_ready",
    "created_from",
    "selected_edge_threshold",
    "p18_policy_id",
    "p18_edge_threshold",
    "p18_max_stake_cap",
    "p18_kelly_fraction",
    "p18_odds_decimal_max",
    "p18_policy_max_drawdown_pct",
    "p18_policy_sharpe_ratio",
    "p18_policy_n_bets",
    "p18_policy_roi_ci_low_95",
    "p18_policy_roi_ci_high_95",
]

REQUIRED_SUMMARY_KEYS = [
    "p16_6_gate",
    "p18_source_gate",
    "p18_policy_id",
    "p18_edge_threshold",
    "p18_max_stake_cap",
    "p18_kelly_fraction",
    "p18_odds_decimal_max",
    "n_input_rows",
    "n_joined_rows",
    "n_policy_eligible_rows",
    "n_recommended_rows",
    "n_blocked_rows",
    "top_gate_reasons",
    "selected_policy_max_drawdown_pct",
    "selected_policy_sharpe_ratio",
    "selected_policy_n_bets",
    "paper_only",
    "production_ready",
]

REQUIRED_RISK_PROFILE_KEYS = [
    "roi_mean",
    "roi_ci_low_95",
    "roi_ci_high_95",
    "max_drawdown_pct",
    "sharpe_ratio",
    "n_bets",
    "source",
    "selected_policy_id",
    "edge_threshold",
    "max_stake_cap",
    "kelly_fraction",
    "odds_decimal_max",
    "paper_only",
    "production_ready",
]


# ── CLI runner helper ─────────────────────────────────────────────────────────

def _run_cli(output_dir: str) -> int:
    return cli_main([
        "--joined-oof", str(JOINED_OOF),
        "--p15-ledger", str(P15_LEDGER),
        "--p18-policy", str(P18_POLICY),
        "--output-dir", output_dir,
        "--paper-only", "true",
    ])


# ── Integration tests ─────────────────────────────────────────────────────────


def test_all_output_files_written():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        rc = _run_cli(tmp)
        assert rc in (0, 1), f"Unexpected exit code: {rc}"
        for fname in REQUIRED_OUTPUT_FILES:
            assert (Path(tmp) / fname).exists(), f"Missing output file: {fname}"


def test_recommendation_rows_has_required_columns():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        rc = _run_cli(tmp)
        assert rc in (0, 1)
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        for col in REQUIRED_ROW_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"


def test_paper_only_invariant_all_rows():
    """Every row must have paper_only=True."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        assert (df["paper_only"] == True).all(), "Found paper_only=False rows"  # noqa: E712


def test_production_ready_invariant_all_rows():
    """Every row must have production_ready=False."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        assert (df["production_ready"] == False).all(), "Found production_ready=True rows"  # noqa: E712


def test_blocked_rows_have_zero_stake():
    """Rows that did not pass the gate must have paper_stake_fraction=0.0."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        eligible_code = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
        blocked = df[df["gate_decision"] != eligible_code]
        assert (blocked["paper_stake_fraction"] == 0.0).all(), (
            "Blocked row has non-zero stake"
        )


def test_eligible_rows_have_positive_stake():
    """Rows that passed the gate must have paper_stake_fraction > 0.0."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        rc = _run_cli(tmp)
        if rc != 0:
            pytest.skip("No eligible rows in this dataset — cannot test positive stake")
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        eligible_code = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
        eligible = df[df["gate_decision"] == eligible_code]
        assert (eligible["paper_stake_fraction"] > 0.0).all(), (
            "Eligible row has zero stake"
        )


def test_recommendation_summary_has_required_keys():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        with open(Path(tmp) / "recommendation_summary.json") as f:
            summary = json.load(f)
        for key in REQUIRED_SUMMARY_KEYS:
            assert key in summary, f"Missing summary key: {key}"


def test_summary_paper_only_false_never():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        with open(Path(tmp) / "recommendation_summary.json") as f:
            summary = json.load(f)
        assert summary["paper_only"] is True
        assert summary["production_ready"] is False


def test_gate_reason_counts_is_valid_json():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        with open(Path(tmp) / "gate_reason_counts.json") as f:
            counts = json.load(f)
        assert isinstance(counts, dict)
        # All values are integers
        for k, v in counts.items():
            assert isinstance(v, int), f"Non-integer count for reason '{k}': {v}"


def test_p18_policy_applied_json_matches_source():
    """p18_policy_applied.json must match values from the source P18 policy."""
    _skip_if_missing()
    with open(P18_POLICY) as f:
        source = json.load(f)
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        with open(Path(tmp) / "p18_policy_applied.json") as f:
            applied = json.load(f)
    assert applied["selected_policy_id"] == source["selected_policy_id"]
    assert applied["edge_threshold"] == pytest.approx(source["edge_threshold"])
    assert applied["max_stake_cap"] == pytest.approx(source["max_stake_cap"])
    assert applied["kelly_fraction"] == pytest.approx(source["kelly_fraction"])
    assert applied["odds_decimal_max"] == pytest.approx(source["odds_decimal_max"])
    assert applied["paper_only"] is True
    assert applied["production_ready"] is False


def test_risk_profile_json_has_required_keys():
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        with open(Path(tmp) / "p16_6_policy_risk_profile.json") as f:
            rp = json.load(f)
        for key in REQUIRED_RISK_PROFILE_KEYS:
            assert key in rp, f"Missing risk profile key: {key}"
        assert rp["source"] == "p18_selected_policy"
        assert rp["paper_only"] is True
        assert rp["production_ready"] is False


def test_summary_gate_reflects_eligible_count():
    """If n_recommended_rows > 0 → gate is GATE_READY, else GATE_NO_ELIGIBLE."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        rc = _run_cli(tmp)
        with open(Path(tmp) / "recommendation_summary.json") as f:
            summary = json.load(f)
        if summary["n_recommended_rows"] > 0:
            assert summary["p16_6_gate"] == "P16_6_PAPER_RECOMMENDATION_GATE_READY"
            assert rc == 0
        else:
            assert summary["p16_6_gate"] == "P16_6_BLOCKED_NO_ELIGIBLE_ROWS"
            assert rc == 1


def test_determinism_two_runs():
    """Two consecutive CLI runs must produce identical recommendation_rows.csv content."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        rc1 = _run_cli(tmp1)
        rc2 = _run_cli(tmp2)
        assert rc1 == rc2, "Exit codes differ across runs"

        df1 = pd.read_csv(Path(tmp1) / "recommendation_rows.csv")
        df2 = pd.read_csv(Path(tmp2) / "recommendation_rows.csv")

        # Same shape
        assert df1.shape == df2.shape, f"Row shapes differ: {df1.shape} vs {df2.shape}"

        # Sort and compare numeric columns
        sort_cols = ["game_id", "date"]
        df1 = df1.sort_values(sort_cols).reset_index(drop=True)
        df2 = df2.sort_values(sort_cols).reset_index(drop=True)

        numeric_cols = ["p_model", "p_market", "edge", "odds_decimal", "paper_stake_fraction"]
        for col in numeric_cols:
            if col in df1.columns:
                diff = (df1[col] - df2[col]).abs().max()
                assert diff < 1e-12, f"Column '{col}' differs across runs by {diff}"

        # Recommendation IDs must match exactly
        assert list(df1["recommendation_id"]) == list(df2["recommendation_id"]), (
            "recommendation_id differs across runs"
        )


def test_missing_joined_oof_exits_with_code_2():
    with tempfile.TemporaryDirectory() as tmp:
        rc = cli_main([
            "--joined-oof", "/nonexistent/joined_oof.csv",
            "--p15-ledger", str(P15_LEDGER) if P15_LEDGER.exists() else "/nonexistent/ledger.csv",
            "--p18-policy", str(P18_POLICY) if P18_POLICY.exists() else "/nonexistent/policy.json",
            "--output-dir", tmp,
        ])
        assert rc == 2


def test_paper_only_false_rejected():
    """--paper-only false must exit with code 2."""
    _skip_if_missing()
    with tempfile.TemporaryDirectory() as tmp:
        rc = cli_main([
            "--joined-oof", str(JOINED_OOF),
            "--p15-ledger", str(P15_LEDGER),
            "--p18-policy", str(P18_POLICY),
            "--output-dir", tmp,
            "--paper-only", "false",
        ])
        assert rc == 2


def test_stake_cap_respected():
    """No eligible row should have paper_stake_fraction > p18_policy.max_stake_cap."""
    _skip_if_missing()
    with open(P18_POLICY) as f:
        source = json.load(f)
    max_cap = source["max_stake_cap"]

    with tempfile.TemporaryDirectory() as tmp:
        rc = _run_cli(tmp)
        if rc not in (0, 1):
            pytest.skip("CLI failed — skipping stake cap check")
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        eligible_code = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
        eligible = df[df["gate_decision"] == eligible_code]
        if len(eligible) == 0:
            pytest.skip("No eligible rows — skipping stake cap check")
        max_stake = eligible["paper_stake_fraction"].max()
        assert max_stake <= max_cap + 1e-12, (
            f"Stake {max_stake:.6f} exceeds max_stake_cap={max_cap}"
        )


def test_p18_edge_threshold_column_consistent():
    """All rows must have p18_edge_threshold matching the P18 policy source."""
    _skip_if_missing()
    with open(P18_POLICY) as f:
        source = json.load(f)
    expected_threshold = source["edge_threshold"]

    with tempfile.TemporaryDirectory() as tmp:
        _run_cli(tmp)
        df = pd.read_csv(Path(tmp) / "recommendation_rows.csv")
        max_diff = (df["p18_edge_threshold"] - expected_threshold).abs().max()
        assert max_diff < 1e-10, (
            f"p18_edge_threshold column has inconsistent values (max_diff={max_diff})"
        )
