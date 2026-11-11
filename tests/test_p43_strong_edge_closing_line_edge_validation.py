from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import _p43_strong_edge_closing_line_edge_validation as p43


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "data/mlb_2025/derived/p43_strong_edge_closing_line_edge_summary.json"


@pytest.fixture(scope="module")
def summary() -> dict:
    data = p43.build_summary()
    p43.write_outputs(data)
    return data


def test_01_data_load_shape_match(summary: dict) -> None:
    inv = summary["data_inventory"]
    total = inv["rows_unified_total"]
    c2024 = inv["rows_2024"]["holdout_quality_rows"]
    c2025 = inv["rows_2025"]["phase56_joined_rows"]
    # Unified includes all 2024 quality + all 2025 joined records
    assert total == c2024 + c2025


def test_02_delta_filter_correct(summary: dict) -> None:
    c_n = summary["tier_metrics"]["C"]["n"]
    b_n = summary["tier_metrics"]["B"]["n"]
    a_n = summary["tier_metrics"]["A"]["n"]
    assert c_n >= b_n >= a_n


def test_03_edge_computation_correctness() -> None:
    # Home-favored case
    e1, s1 = p43.edge_for_model_side(model_home_prob=0.63, market_home_prob=0.58)
    assert s1 == "home"
    assert e1 == pytest.approx(0.05)

    # Away-favored case: use away-side probabilities
    # model_away=0.57, market_away=0.51 => +0.06
    e2, s2 = p43.edge_for_model_side(model_home_prob=0.43, market_home_prob=0.49)
    assert s2 == "away"
    assert e2 == pytest.approx(0.06)


def test_04_bootstrap_ci_deterministic_seed() -> None:
    values = [0.01, -0.02, 0.03, 0.04, -0.01, 0.02]
    a = p43.bootstrap_mean_ci(values, n_boot=500, seed=7)
    b = p43.bootstrap_mean_ci(values, n_boot=500, seed=7)
    assert a == b


def test_05_tier_breakdown_counts_match_expected(summary: dict) -> None:
    c = summary["tier_metrics"]["C"]["n"]
    y = summary["year_metrics"]["2024"]["C"]["n"] + summary["year_metrics"]["2025"]["C"]["n"]
    assert c == y


def test_06_year_split_correctness(summary: dict) -> None:
    assert set(summary["year_metrics"].keys()) == {"2024", "2025", "combined"}
    for tier in ("A", "B", "C"):
        assert summary["year_metrics"]["combined"][tier]["n"] == (
            summary["year_metrics"]["2024"][tier]["n"]
            + summary["year_metrics"]["2025"][tier]["n"]
        )


def test_07_classification_logic() -> None:
    assert p43.classify_edge(mean_edge=0.01, ci_low=0.001, ci_high=0.02, n=100) == "EDGE_CONFIRMED"
    assert p43.classify_edge(mean_edge=0.002, ci_low=-0.003, ci_high=0.01, n=100) == "WEAK_STABLE"
    assert p43.classify_edge(mean_edge=-0.01, ci_low=-0.02, ci_high=-0.001, n=100) == "NEGATIVE"
    assert p43.classify_edge(mean_edge=0.0, ci_low=-0.01, ci_high=0.01, n=100) == "INCONCLUSIVE"
    assert p43.classify_edge(mean_edge=0.03, ci_low=0.01, ci_high=0.05, n=10) == "SAMPLE_LIMITED"


def test_08_flags_and_framing_note_in_json(summary: dict) -> None:
    assert SUMMARY_PATH.exists(), f"Missing summary file: {SUMMARY_PATH}"
    loaded = json.loads(SUMMARY_PATH.read_text())

    gov = loaded["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert loaded["framing_note"]
    assert "not strict CLV" in loaded["framing_note"]


def test_09_2024_data_gap_flag(summary: dict) -> None:
    inv = summary["data_inventory"]
    assert inv["rows_with_market_prob_2024"] == 0
    assert inv["data_gap_2024_market_prob_missing"] is True
    assert summary["classification"]["final_classification"] == "P43_BLOCKED_BY_DATA_GAP"
