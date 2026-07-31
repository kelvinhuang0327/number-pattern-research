"""
tests/test_p227c_star_box_play_dryrun_scan.py
=============================================
P227C — Targeted validation tests for the dry-run scan script.

Tests cover:
  - pure statistical helpers (no DB required)
  - pre-registration constants
  - feature functions (no DB required)
  - artifact JSON structure
  - DB-unchanged assertion (requires DB)

Run with:
    pytest tests/test_p227c_star_box_play_dryrun_scan.py -v
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Lazy import of scan module (avoids running main at import time)
_SCAN_PATH = ROOT / "scripts" / "p227c_star_box_play_dryrun_scan.py"
_spec = importlib.util.spec_from_file_location("p227c_scan", _SCAN_PATH)
_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scan)

from lottery_api.models.star_box_play import (
    STAR_CONFIG,
    star_box_exact_match,
)


# ---------------------------------------------------------------------------
# 1. Statistical helpers
# ---------------------------------------------------------------------------


def test_binomial_p_above_baseline():
    """When k >> n*p0, p-value should be small."""
    p = _scan.binomial_one_sided_p(k=15, n=1000, p0=0.00833)
    assert p < 0.05


def test_binomial_p_at_baseline():
    """When k ≈ n*p0, p-value should be ≈ 0.5."""
    p = _scan.binomial_one_sided_p(k=9, n=1000, p0=0.00833)
    assert 0.2 < p < 0.9


def test_binomial_p_zero_n():
    assert _scan.binomial_one_sided_p(0, 0, 0.01) == 1.0


def test_wilson_ci_contains_true_p():
    """95% Wilson CI should contain true p for reasonable n."""
    lo, hi = _scan.wilson_ci(k=9, n=1000)
    assert lo <= 0.009 <= hi


def test_wilson_ci_zero_n():
    lo, hi = _scan.wilson_ci(0, 0)
    assert lo == 0.0 and hi == 1.0


def test_bh_fdr_rejects_small_p():
    p_vals = [0.001, 0.02, 0.5, 0.9]
    rejects = _scan.bh_fdr(p_vals, alpha=0.05)
    assert rejects[0] is True   # 0.001 should be rejected
    assert rejects[3] is False  # 0.9 should not be rejected


def test_bh_fdr_empty():
    assert _scan.bh_fdr([], 0.05) == []


def test_block_stability_counts():
    hits = [1] * 300 + [0] * 300   # 600 total, 2 blocks of 150
    result = _scan.block_stability(hits, block_size=150)
    assert result["n_blocks"] == 4
    assert result["blocks_above_baseline"] >= 2


def test_block_stability_empty():
    result = _scan.block_stability([], block_size=150)
    assert result["n_blocks"] == 0


# ---------------------------------------------------------------------------
# 2. Pre-registration constants
# ---------------------------------------------------------------------------


def test_n_hypotheses_consistent():
    """Total hypothesis count must equal N_LOTTERIES * N_FEATURES * N_WINDOWS."""
    assert _scan.N_HYPOTHESES == _scan.N_LOTTERIES * _scan.N_FEATURES * _scan.N_WINDOWS


def test_bonferroni_threshold_formula():
    expected = 0.05 / _scan.N_HYPOTHESES
    assert abs(_scan.BONFERRONI_THRESHOLD - expected) < 1e-12


def test_power_min_draws_present():
    assert "3_STAR" in _scan.POWER_MIN_DRAWS
    assert "4_STAR" in _scan.POWER_MIN_DRAWS
    # 4_STAR has lower baseline (1/210) so needs MORE draws than 3_STAR (1/120)
    assert _scan.POWER_MIN_DRAWS["4_STAR"] > _scan.POWER_MIN_DRAWS["3_STAR"]


def test_windows_frozen():
    assert _scan.WINDOWS_SHORT == [100, 125, 150]
    assert _scan.WINDOWS_MID == [500, 750, 1000]


# ---------------------------------------------------------------------------
# 3. Feature functions (synthetic data, no DB)
# ---------------------------------------------------------------------------


def _make_draws(n: int, pick_count: int = 3) -> list:
    """Generate synthetic draws cycling through [0,1,2,...,9]."""
    import random
    random.seed(42)
    draws = []
    for i in range(n):
        nums = sorted(random.sample(range(10), pick_count))
        draws.append({"draw": str(i), "date": "2020-01-01", "numbers": nums})
    return draws


def test_predict_hot_returns_pick_count():
    draws = _make_draws(200, pick_count=3)
    pred = _scan._predict_hot(draws[:100], 100, 3)
    assert len(pred) == 3
    assert all(0 <= d <= 9 for d in pred)


def test_predict_cold_returns_pick_count():
    draws = _make_draws(200, pick_count=3)
    pred = _scan._predict_cold(draws[:100], 100, 3)
    assert len(pred) == 3


def test_predict_overdue_returns_pick_count():
    draws = _make_draws(200, pick_count=3)
    pred = _scan._predict_overdue(draws[:100], 3)
    assert len(pred) == 3


def test_predict_consensus_returns_pick_count():
    draws = _make_draws(200, pick_count=3)
    pred = _scan._predict_consensus(draws[:100], 100, 3)
    assert len(pred) == 3


def test_evaluate_feature_returns_correct_keys():
    draws = _make_draws(300, pick_count=3)
    baseline = 1 / 120
    result = _scan.evaluate_feature(
        draws,
        lambda h: _scan._predict_hot(h, 100, 3),
        baseline,
        oos_start_pct=0.5,
    )
    for key in ["n_oos", "n_hits", "hit_rate", "baseline", "lift", "p_value",
                "ci_low", "ci_high", "block_stability", "power_status"]:
        assert key in result, f"Missing key: {key}"


def test_evaluate_feature_power_underpowered():
    """Synthetic data with < 10000 OOS draws must be UNDERPOWERED."""
    draws = _make_draws(300, pick_count=3)
    # Add lottery_type for power gate
    draws = [dict(d, lottery_type="3_STAR") for d in draws]
    baseline = 1 / 120
    result = _scan.evaluate_feature(
        draws,
        lambda h: _scan._predict_hot(h, 100, 3),
        baseline,
    )
    assert result["power_status"] == "UNDERPOWERED"


def test_no_db_write_in_scan_module():
    """Verify scan module never calls INSERT or execute with INSERT."""
    import inspect
    source = inspect.getsource(_scan)
    # No INSERT INTO strategy_prediction_replays
    assert "INSERT INTO strategy_prediction_replays" not in source


def test_scan_does_not_use_calculate_match_score():
    """Scan must not call calculate_match_score."""
    import ast
    import inspect
    source = inspect.getsource(_scan)
    tree = ast.parse(source)
    bad_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(getattr(n, "func", None), ast.Name)
        and n.func.id == "calculate_match_score"
    ]
    assert bad_calls == []


# ---------------------------------------------------------------------------
# 4. Artifact JSON validation (requires prior scan execution)
# ---------------------------------------------------------------------------

ARTIFACT_PATH = (
    ROOT / "outputs" / "research" / "p227c_star_box_play_dryrun_scan_20260603.json"
)


@pytest.mark.skipif(
    not ARTIFACT_PATH.exists(),
    reason="Run scripts/p227c_star_box_play_dryrun_scan.py first"
)
def test_artifact_parses():
    d = json.loads(ARTIFACT_PATH.read_text())
    assert d["task"] == "P227C_STAR_BOX_PLAY_DRYRUN_SCAN_COMPLETE"
    assert d["db_writes"] == 0
    assert d["replay_rows_written"] == 0


@pytest.mark.skipif(
    not ARTIFACT_PATH.exists(),
    reason="Run scripts/p227c_star_box_play_dryrun_scan.py first"
)
def test_artifact_db_unchanged():
    d = json.loads(ARTIFACT_PATH.read_text())
    assert d["total_replay_rows_unchanged"] == 94924
    assert d["star_replay_rows_unchanged"] == 0


@pytest.mark.skipif(
    not ARTIFACT_PATH.exists(),
    reason="Run scripts/p227c_star_box_play_dryrun_scan.py first"
)
def test_artifact_classification_underpowered():
    """Given current draw counts, expect UNDERPOWERED classification."""
    d = json.loads(ARTIFACT_PATH.read_text())
    for lt in ["3_STAR", "4_STAR"]:
        overall = d["scan_results"][lt]["overall_classification"]
        # Either UNDERPOWERED_NO_SIGNAL or CANDIDATES_NEED_MORE_OOS — both are OK.
        # But NOT something claiming deployable signal.
        assert "DEPLOY" not in overall
        assert "PROMOTE" not in overall
        assert "PRODUCTION" not in overall


@pytest.mark.skipif(
    not ARTIFACT_PATH.exists(),
    reason="Run scripts/p227c_star_box_play_dryrun_scan.py first"
)
def test_artifact_bonferroni_threshold_correct():
    d = json.loads(ARTIFACT_PATH.read_text())
    # 2 lotteries × 10 features × 6 windows = 120 total hypotheses
    # Bonferroni = 0.05 / 120
    expected = 0.05 / 120
    assert abs(d["bonferroni_threshold"] - expected) < 1e-7


@pytest.mark.skipif(
    not ARTIFACT_PATH.exists(),
    reason="Run scripts/p227c_star_box_play_dryrun_scan.py first"
)
def test_artifact_no_bonferroni_pass():
    """No result should pass Bonferroni — sample size is too small."""
    d = json.loads(ARTIFACT_PATH.read_text())
    for lt in ["3_STAR", "4_STAR"]:
        n_bonf = d["scan_results"][lt]["n_bonferroni_pass"]
        # With ~4000 draws Bonferroni should be 0; fail loudly if it somehow passes
        assert n_bonf == 0, f"{lt}: unexpected Bonferroni pass ({n_bonf})"


@pytest.mark.skipif(
    not ARTIFACT_PATH.exists(),
    reason="Run scripts/p227c_star_box_play_dryrun_scan.py first"
)
def test_artifact_straight_play_blocked_present():
    d = json.loads(ARTIFACT_PATH.read_text())
    assert "straight_play_blocked" in d
    assert "positional" in d["straight_play_blocked"].lower()
