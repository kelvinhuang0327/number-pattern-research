"""
P3 測試套件：strategy_sim_validation.py
至少 12 個測試，涵蓋 Brier/ECE/MARL gate/fold-level/edge threshold 等。
"""
import json
import math
import pytest

from wbc_backend.recommendation.strategy_sim_validation import (
    BrierECEResult,
    assign_probability_bin,
    build_brier_ece_result,
    calculate_brier_score,
    calculate_ece,
    compare_edge_thresholds,
    summarize_by_walk_forward_fold,
    validate_marl_gate,
)


# ── 1. Brier Score 計算正確 ──────────────────────────────────────────────
class TestBrierScore:
    def test_perfect_prediction(self):
        probs = [1.0, 0.0, 1.0]
        outcomes = [1, 0, 1]
        assert calculate_brier_score(probs, outcomes) == pytest.approx(0.0)

    def test_worst_prediction(self):
        probs = [0.0, 1.0]
        outcomes = [1, 0]
        assert calculate_brier_score(probs, outcomes) == pytest.approx(1.0)

    def test_known_value(self):
        # (0.7-1)^2 + (0.3-0)^2 = 0.09 + 0.09 = 0.18 / 2 = 0.09
        probs = [0.7, 0.3]
        outcomes = [1, 0]
        assert calculate_brier_score(probs, outcomes) == pytest.approx(0.09)

    def test_empty_returns_nan(self):
        result = calculate_brier_score([], [])
        assert math.isnan(result)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            calculate_brier_score([0.5, 0.5], [1])


# ── 2. ECE binning ──────────────────────────────────────────────────────
class TestECE:
    def test_boundary_zero(self):
        assert assign_probability_bin(0.0, 10) == 0

    def test_boundary_one(self):
        assert assign_probability_bin(1.0, 10) == 9  # max bin

    def test_boundary_mid(self):
        # 0.55 -> bin 5
        assert assign_probability_bin(0.55, 10) == 5

    def test_perfect_calibration_ece_zero(self):
        # 所有預測 0.5，結果各半 → perfect calibration
        probs = [0.5] * 100
        outcomes = [1] * 50 + [0] * 50
        ece = calculate_ece(probs, outcomes)
        assert ece == pytest.approx(0.0, abs=1e-10)

    def test_ece_empty_returns_nan(self):
        assert math.isnan(calculate_ece([], []))

    def test_ece_miscalibrated(self):
        # always predict 0.9 but only 50% win → large ECE
        probs = [0.9] * 100
        outcomes = [1] * 50 + [0] * 50
        ece = calculate_ece(probs, outcomes)
        assert ece > 0.3


# ── 3. MARL Gate ─────────────────────────────────────────────────────────
class TestMarlGate:
    def test_ece_fail(self):
        result = validate_marl_gate(brier=0.22, ece=0.15)
        assert result["gate_status"] == "FAIL"
        assert any("ECE" in r for r in result["reasons"])

    def test_brier_fail(self):
        result = validate_marl_gate(brier=0.30, ece=0.10)
        assert result["gate_status"] == "FAIL"
        assert any("Brier" in r for r in result["reasons"])

    def test_both_pass(self):
        result = validate_marl_gate(brier=0.24, ece=0.10)
        assert result["gate_status"] == "PASS"
        assert result["reasons"] == []

    def test_reasons_list_returned(self):
        result = validate_marl_gate(brier=0.30, ece=0.15)
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) == 2  # 兩個都 FAIL

    def test_nan_brier_fails(self):
        result = validate_marl_gate(brier=float("nan"), ece=0.10)
        assert result["gate_status"] == "FAIL"


# ── 4. Missing actual_home_win 不得靜默忽略 ─────────────────────────────
class TestMissingActual:
    def test_missing_counted_in_result(self):
        rows = [
            {"model_prob": 0.6, "bet_side": "HOME", "actual_home_win": 1, "walk_forward_fold": 1},
            {"model_prob": 0.6, "bet_side": "HOME", "actual_home_win": None, "walk_forward_fold": 1},
            {"model_prob": 0.6, "bet_side": "HOME", "actual_home_win": None, "walk_forward_fold": 1},
        ]
        result = build_brier_ece_result(
            rows_with_actual=[r for r in rows if r["actual_home_win"] is not None],
            total_rows=3,
            joined_rows=1,
            missing_result_rows=2,
        )
        assert result.missing_result_rows == 2
        assert result.joined_rows == 1


# ── 5. Fold-level summary ────────────────────────────────────────────────
class TestFoldSummary:
    def _make_rows(self):
        rows = []
        for fold in [1, 2, 3]:
            for i in range(10):
                rows.append({
                    "walk_forward_fold": fold,
                    "model_prob": 0.6,
                    "bet_side": "HOME",
                    "actual_home_win": 1 if i % 2 == 0 else 0,
                    "edge": 0.05,
                    "kelly_fraction": 0.1,
                })
        return rows

    def test_all_folds_present(self):
        rows = self._make_rows()
        summary = summarize_by_walk_forward_fold(rows)
        folds = [s["fold"] for s in summary]
        assert set(folds) == {1, 2, 3}

    def test_fold_games_count(self):
        rows = self._make_rows()
        summary = summarize_by_walk_forward_fold(rows)
        for s in summary:
            assert s["games"] == 10


# ── 6. Edge threshold comparison ─────────────────────────────────────────
class TestEdgeThreshold:
    def _make_rows(self):
        rows = []
        for edge in [0.005, 0.02, 0.04, 0.06]:
            rows.extend([{"edge": edge, "kelly_fraction": edge * 2}] * 5)
        return rows  # 20 rows: 5@0.005, 5@0.02, 5@0.04, 5@0.06

    def test_different_n_recommended(self):
        rows = self._make_rows()
        comparisons = compare_edge_thresholds(rows, thresholds=[0.01, 0.03, 0.05])
        counts = [c["n_recommended"] for c in comparisons]
        assert counts[0] > counts[1] > counts[2]

    def test_thresholds_three_rows(self):
        rows = self._make_rows()
        comparisons = compare_edge_thresholds(rows, thresholds=[0.01, 0.03, 0.05])
        assert len(comparisons) == 3


# ── 7. BrierECEResult JSON serialize ────────────────────────────────────
class TestBrierECEResultSerialize:
    def test_json_serializable(self):
        result = BrierECEResult(
            total_rows=100,
            joined_rows=80,
            missing_result_rows=20,
            brier_score=0.22,
            ece=0.08,
            accuracy=0.55,
            coverage_rate=0.8,
            gate_status="PASS",
            reasons=[],
        )
        serialized = json.dumps(result.to_dict())
        parsed = json.loads(serialized)
        assert parsed["gate_status"] == "PASS"
        assert parsed["brier_score"] == pytest.approx(0.22)


# ── 8. paper_only 欄位不被覆寫 ──────────────────────────────────────────
class TestPaperOnly:
    def test_paper_only_preserved(self):
        row = {
            "model_prob": 0.6,
            "bet_side": "HOME",
            "actual_home_win": 1,
            "walk_forward_fold": 1,
            "paper_only": True,
            "edge": 0.05,
            "kelly_fraction": 0.1,
        }
        # summarize_by_walk_forward_fold 不應修改原始 row
        rows = [row]
        summarize_by_walk_forward_fold(rows)
        assert rows[0]["paper_only"] is True
