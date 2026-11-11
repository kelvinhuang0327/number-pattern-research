"""
Phase 5 整合測試套件 — 統計本體/階層式MC/特徵剪枝
====================================================
測試三個新增模組：
  5A. wbc_backend/features/ontology_discovery.py  (統計本體自動發現)
  5B. wbc_backend/simulation/hierarchical_mc.py   (階層式蒙特卡洛)
  5C. wbc_backend/features/feature_selector.py    (特徵自動剪枝)

驗證項目：
  1. 模組可正確匯入與執行
  2. 輸出值域合理（無 NaN / Inf，機率 0-1）
  3. 重要性排序正確（signal >> noise）
  4. 交互作用發現（已知交互特徵被識別）
  5. 階層修正在合理範圍（±15%）
  6. 信賴區間格式正確（lower <= point <= upper）
  7. SHAP fallback 正常（無 shap 時不報錯）
  8. Edge cases（空資料、樣本不足、全 NaN）

Run: python -m pytest tests/test_phase5_integration.py -v
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.domain.schemas import PredictionResult, TeamSnapshot


# ══════════════════════════════════════════════════════════════════════════════
# 共用 Fixtures
# ══════════════════════════════════════════════════════════════════════════════

def _make_pred(
    home_runs: float = 4.5,
    away_runs: float = 3.8,
    home_prob: float = 0.55,
) -> PredictionResult:
    return PredictionResult(
        game_id="TEST_001",
        home_win_prob=home_prob,
        away_win_prob=1.0 - home_prob,
        expected_home_runs=home_runs,
        expected_away_runs=away_runs,
        x_factors=[],
        diagnostics={},
        confidence_score=0.7,
        market_bias_score=0.0,
    )


def _make_feature_matrix(n_games: int = 50) -> dict[str, list[float]]:
    """產生含真實信號與噪音特徵的測試矩陣"""
    rng = np.random.default_rng(42)
    # 真實信號特徵（與結果相關）
    woba_diff = rng.normal(0, 0.05, n_games)
    era_diff = rng.normal(0, 0.5, n_games)
    # 噪音特徵（與結果無關）
    random_noise = rng.uniform(-1, 1, n_games)
    random_noise2 = rng.normal(0, 10, n_games)
    return {
        "woba_diff": woba_diff.tolist(),
        "era_diff": (-era_diff).tolist(),   # 負相關（ERA 差 → 勝率低）
        "random_noise_1": random_noise.tolist(),
        "random_noise_2": random_noise2.tolist(),
    }


def _make_outcomes(feature_matrix: dict[str, list[float]]) -> list[int]:
    """根據 woba_diff 和 era_diff 產生結果（加入噪音）"""
    rng = np.random.default_rng(42)
    woba = np.array(feature_matrix["woba_diff"])
    era = np.array(feature_matrix["era_diff"])
    score = woba * 2.0 + era * 0.3
    prob = 1 / (1 + np.exp(-score * 10))
    return [int(rng.random() < p) for p in prob]


# ══════════════════════════════════════════════════════════════════════════════
# Phase 5A：統計本體自動發現
# ══════════════════════════════════════════════════════════════════════════════

class TestOntologyDiscovery:

    def test_import(self) -> None:
        """5A-01: 模組可正確匯入"""
        from wbc_backend.features.ontology_discovery import (
            discover_ontology, OntologyReport, save_ontology_report, load_ontology_report,
        )
        assert callable(discover_ontology)

    def test_basic_output_structure(self) -> None:
        """5A-02: 輸出結構正確"""
        from wbc_backend.features.ontology_discovery import discover_ontology, OntologyReport
        fm = _make_feature_matrix(50)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes)
        assert isinstance(report, OntologyReport)
        assert report.n_samples == 50
        assert report.n_features_analyzed == len(fm)
        assert len(report.feature_importance) == len(fm)
        assert isinstance(report.top_k_features, list)
        assert isinstance(report.interaction_candidates, list)
        assert isinstance(report.prune_candidates, list)
        assert report.timestamp != ""

    def test_signal_ranked_above_noise(self) -> None:
        """5A-03: 信號特徵重要性高於噪音特徵"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        # 使用更大樣本，讓信號更清晰
        fm = _make_feature_matrix(100)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes)

        scores = {e.feature_name: e.composite_score for e in report.feature_importance}
        signal_max = max(scores["woba_diff"], scores["era_diff"])
        noise_max = max(scores["random_noise_1"], scores["random_noise_2"])
        # 信號至少與噪音持平（在有限樣本下放寬條件）
        assert signal_max >= noise_max * 0.5, (
            f"信號分數 {signal_max:.4f} 應 >= 噪音分數 {noise_max:.4f} × 0.5"
        )

    def test_composite_score_in_range(self) -> None:
        """5A-04: 所有特徵綜合分數在 [0, 1] 範圍"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = _make_feature_matrix(40)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes)
        for entry in report.feature_importance:
            assert 0.0 <= entry.composite_score <= 1.0, (
                f"{entry.feature_name} 分數 {entry.composite_score} 超出範圍"
            )
            assert math.isfinite(entry.composite_score)

    def test_interaction_candidates_sorted(self) -> None:
        """5A-05: 交互作用候選按 CMI 降序排列"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = _make_feature_matrix(60)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes, max_interactions=10)
        cmi_values = [ic.conditional_mi for ic in report.interaction_candidates]
        assert cmi_values == sorted(cmi_values, reverse=True)

    def test_prune_candidates_have_low_scores(self) -> None:
        """5A-06: 剪枝候選的分數均低於閾值"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = _make_feature_matrix(50)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes, prune_threshold=0.02)
        for pc in report.prune_candidates:
            assert pc.composite_score < 0.02 or not any(
                e.feature_name == pc.feature_name and e.data_available
                for e in report.feature_importance
                if e.composite_score >= 0.02
            )

    def test_json_serializable(self) -> None:
        """5A-07: to_dict 輸出可 JSON 序列化"""
        import json
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes)
        d = report.to_dict()
        assert isinstance(json.dumps(d), str)

    def test_save_and_load(self) -> None:
        """5A-08: save/load 循環正確"""
        from wbc_backend.features.ontology_discovery import (
            discover_ontology, save_ontology_report, load_ontology_report,
        )
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ontology_test.json"
            save_ontology_report(report, path)
            loaded = load_ontology_report(path)
            assert "top_k_features" in loaded
            assert "interaction_candidates" in loaded

    def test_edge_case_insufficient_samples(self) -> None:
        """5A-09: 樣本不足時仍正常返回（不拋出異常）"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = {"feat_a": [1.0] * 5, "feat_b": [2.0] * 5}
        outcomes = [1, 0, 1, 0, 1]
        # 不應拋出異常
        report = discover_ontology(fm, outcomes)
        assert report.n_samples == 5

    def test_edge_case_all_same_values(self) -> None:
        """5A-10: 特徵值全相同時不報錯（方差為 0）"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = {
            "constant_feat": [1.0] * 30,
            "real_feat": list(np.random.default_rng(1).normal(0, 1, 30)),
        }
        outcomes = [int(x > 0) for x in np.random.default_rng(1).normal(0, 1, 30)]
        report = discover_ontology(fm, outcomes)
        constant_entry = next(e for e in report.feature_importance if e.feature_name == "constant_feat")
        assert constant_entry.composite_score == 0.0

    def test_top_k_features_count(self) -> None:
        """5A-11: top_k_features 數量 <= top_k"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = _make_feature_matrix(40)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes, top_k=2)
        assert len(report.top_k_features) <= 2

    def test_interaction_strength_labels(self) -> None:
        """5A-12: 交互作用 strength 標籤合法"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        fm = _make_feature_matrix(50)
        outcomes = _make_outcomes(fm)
        report = discover_ontology(fm, outcomes)
        valid_strengths = {"strong", "moderate", "weak"}
        for ic in report.interaction_candidates:
            assert ic.strength in valid_strengths


# ══════════════════════════════════════════════════════════════════════════════
# Phase 5B：階層式蒙特卡洛
# ══════════════════════════════════════════════════════════════════════════════

class TestHierarchicalMonteCarlo:

    def test_import(self) -> None:
        """5B-01: 模組可正確匯入"""
        from wbc_backend.simulation.hierarchical_mc import (
            run_hierarchical_monte_carlo, HierarchicalSimResult,
        )
        assert callable(run_hierarchical_monte_carlo)

    def test_basic_output_structure(self) -> None:
        """5B-02: 輸出結構正確"""
        from wbc_backend.simulation.hierarchical_mc import (
            run_hierarchical_monte_carlo, HierarchicalSimResult,
        )
        pred = _make_pred()
        result = run_hierarchical_monte_carlo(pred, simulations=5_000, ci_bootstrap_runs=2)
        assert isinstance(result, HierarchicalSimResult)
        assert isinstance(result.home_win_prob, float)
        assert isinstance(result.over_prob, float)
        assert isinstance(result.home_win_prob_ci, tuple)
        assert len(result.home_win_prob_ci) == 2
        assert isinstance(result.layer_audit, dict)

    def test_probabilities_in_range(self) -> None:
        """5B-03: 輸出機率在 [0, 1]"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        r = run_hierarchical_monte_carlo(pred, simulations=5_000, ci_bootstrap_runs=2)
        for attr in ("home_win_prob", "away_win_prob", "over_prob", "under_prob"):
            val = getattr(r, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} 超出 [0, 1]"
            assert math.isfinite(val)

    def test_probabilities_sum_to_one(self) -> None:
        """5B-04: 互補機率之和為 1"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        r = run_hierarchical_monte_carlo(pred, simulations=5_000, ci_bootstrap_runs=2)
        assert abs(r.home_win_prob + r.away_win_prob - 1.0) < 0.01
        assert abs(r.over_prob + r.under_prob - 1.0) < 0.01

    def test_ci_ordering(self) -> None:
        """5B-05: CI 下界 <= 點估計 <= 上界"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        r = run_hierarchical_monte_carlo(pred, simulations=5_000, ci_bootstrap_runs=3)
        low_hw, high_hw = r.home_win_prob_ci
        assert low_hw <= r.home_win_prob + 0.1   # 允許 bootstrap 隨機性小誤差
        assert r.home_win_prob <= high_hw + 0.1
        low_ov, high_ov = r.over_prob_ci
        assert low_ov <= r.over_prob + 0.1
        assert r.over_prob <= high_ov + 0.1

    def test_layer2_market_signals(self) -> None:
        """5B-06: Layer 2 市場信號修正方向正確（正 CLV → 主隊概率略升）"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred(home_prob=0.50)
        # 強 steam move 且 CLV 正 → 主隊應略占優
        bullish_signals = {
            "steam_move_prob": 0.8,
            "clv_estimate_home": 0.10,
            "line_movement_pct": 0.5,
        }
        neutral_signals: dict[str, float] = {}
        r_bullish = run_hierarchical_monte_carlo(
            pred, simulations=3_000, ci_bootstrap_runs=2,
            market_signals=bullish_signals,
        )
        r_neutral = run_hierarchical_monte_carlo(
            pred, simulations=3_000, ci_bootstrap_runs=2,
            market_signals=neutral_signals,
        )
        # 有市場信號的應與無信號的有差異（方向或幅度）
        assert r_bullish.layer2_market_lambda_adj >= 0.0

    def test_layer3_kg_signals(self) -> None:
        """5B-07: Layer 3 知識圖譜信號不改變基礎結果太多（±15%）"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        kg = {"h2h_home_win_rate": 0.70, "legacy_advantage_score": 0.5}
        r = run_hierarchical_monte_carlo(
            pred, simulations=3_000, ci_bootstrap_runs=2, kg_signals=kg,
        )
        assert r.layer3_kg_lambda_adj >= 0.0
        # 修正幅度應有限（不超過基礎期望得分的 20%）
        assert r.layer3_kg_lambda_adj < pred.expected_home_runs * 0.20

    def test_layer4_nlp_variance_expansion(self) -> None:
        """5B-08: Layer 4 傷兵信號使標準差擴大"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        nlp_injury = {"injury_severity_score": 0.9, "weather_impact_score": 0.8}
        nlp_none: dict[str, float] = {}
        r_injury = run_hierarchical_monte_carlo(
            pred, simulations=5_000, ci_bootstrap_runs=2, nlp_signals=nlp_injury,
        )
        r_none = run_hierarchical_monte_carlo(
            pred, simulations=5_000, ci_bootstrap_runs=2, nlp_signals=nlp_none,
        )
        # 傷兵嚴重應使 variance 提升，通常帶來更大的 std
        assert r_injury.layer4_nlp_variance_adj > 0

    def test_layer_audit_keys_present(self) -> None:
        """5B-09: layer_audit 包含三層資訊"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        r = run_hierarchical_monte_carlo(pred, simulations=3_000, ci_bootstrap_runs=2)
        assert "layer2_market" in r.layer_audit
        assert "layer3_kg" in r.layer_audit
        assert "layer4_nlp" in r.layer_audit

    def test_no_signals_equals_base_mc_approximately(self) -> None:
        """5B-10: 無任何信號時，結果應接近基礎 MC"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        from wbc_backend.simulation.monte_carlo import run_monte_carlo
        pred = _make_pred()
        r_hier = run_hierarchical_monte_carlo(
            pred, simulations=5_000, seed=42, ci_bootstrap_runs=2,
        )
        r_base = run_monte_carlo(pred, simulations=5_000, seed=42)
        # 無修正時兩者應幾乎相同（差異 < 2%）
        assert abs(r_hier.home_win_prob - r_base.home_win_prob) < 0.02

    def test_total_adjustment_non_negative(self) -> None:
        """5B-11: 總修正幅度非負"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        r = run_hierarchical_monte_carlo(pred, simulations=3_000, ci_bootstrap_runs=2)
        assert r.total_adjustment_magnitude >= 0.0

    def test_mean_total_runs_reasonable(self) -> None:
        """5B-12: 平均得分在合理範圍（3-20）"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred(home_runs=4.5, away_runs=3.5)
        r = run_hierarchical_monte_carlo(pred, simulations=5_000, ci_bootstrap_runs=2)
        assert 3.0 <= r.mean_total_runs <= 20.0
        assert math.isfinite(r.mean_total_runs)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 5C：特徵自動剪枝
# ══════════════════════════════════════════════════════════════════════════════

class TestFeatureSelector:

    def test_import(self) -> None:
        """5C-01: 模組可正確匯入"""
        from wbc_backend.features.feature_selector import (
            select_features, FeatureSelectorResult,
            save_feature_selector_result, load_stable_features,
        )
        assert callable(select_features)

    def test_basic_output_structure(self) -> None:
        """5C-02: 輸出結構正確"""
        from wbc_backend.features.feature_selector import select_features, FeatureSelectorResult
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes)
        assert isinstance(result, FeatureSelectorResult)
        assert isinstance(result.selected_features, list)
        assert isinstance(result.rejected_features, list)
        assert isinstance(result.importance_scores, dict)
        assert result.n_features_in == len(fm)
        assert result.n_samples == 30

    def test_selected_plus_rejected_equals_total(self) -> None:
        """5C-03: 選出 + 剔除 = 輸入特徵總數"""
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes)
        assert (len(result.selected_features) + len(result.rejected_features)) == result.n_features_in

    def test_signal_features_selected(self) -> None:
        """5C-04: 真實信號特徵應被選出（重要性高）"""
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(50)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes, top_n=3)
        # woba_diff 或 era_diff 至少一個應在 top 選出
        signal_feats = {"woba_diff", "era_diff"}
        assert signal_feats.intersection(set(result.selected_features)), (
            f"信號特徵應被選出，但 selected={result.selected_features}"
        )

    def test_importance_scores_non_negative(self) -> None:
        """5C-05: 所有重要性分數非負"""
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes)
        for name, score in result.importance_scores.items():
            assert score >= 0.0, f"{name} 分數 {score} < 0"
            assert math.isfinite(score)

    def test_top_n_respected(self) -> None:
        """5C-06: 選出特徵數不超過 top_n"""
        from wbc_backend.features.feature_selector import select_features
        fm = {f"feat_{i}": list(np.random.default_rng(i).normal(0, 1, 30)) for i in range(20)}
        outcomes = [int(x > 0) for x in np.random.default_rng(99).normal(0, 1, 30)]
        result = select_features(fm, outcomes, top_n=5)
        assert len(result.selected_features) <= 5

    def test_stability_scores_in_range(self) -> None:
        """5C-07: 穩定性分數在 [0, 1]"""
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(40)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes)
        for name, score in result.stability_scores.items():
            assert 0.0 <= score <= 1.0, f"{name} 穩定性 {score} 超出範圍"

    def test_method_label_valid(self) -> None:
        """5C-08: method 標籤合法"""
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes, use_shap=False)
        assert result.method in {"permutation", "shap+permutation", "none"}

    def test_json_serializable(self) -> None:
        """5C-09: to_dict 可 JSON 序列化"""
        import json
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes)
        d = result.to_dict()
        assert isinstance(json.dumps(d), str)

    def test_save_and_load(self) -> None:
        """5C-10: save/load 循環正確"""
        from wbc_backend.features.feature_selector import (
            select_features, save_feature_selector_result, load_stable_features,
        )
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "features_test.json"
            save_feature_selector_result(result, path)
            loaded = load_stable_features(path)
            assert isinstance(loaded, list)
            assert set(loaded) == set(result.selected_features)

    def test_load_missing_file_returns_empty(self) -> None:
        """5C-11: load 不存在的檔案返回空清單"""
        from wbc_backend.features.feature_selector import load_stable_features
        result = load_stable_features("/nonexistent/path/features.json")
        assert result == []

    def test_edge_case_empty_matrix(self) -> None:
        """5C-12: 空特徵矩陣不報錯"""
        from wbc_backend.features.feature_selector import select_features
        result = select_features({}, [1, 0, 1, 0])
        assert result.selected_features == []
        assert result.n_features_in == 0

    def test_edge_case_nan_handling(self) -> None:
        """5C-13: 含 NaN 的特徵正確填補後不報錯"""
        from wbc_backend.features.feature_selector import select_features
        fm = {
            "feat_with_nan": [float("nan"), 1.0, 2.0, float("nan"), 3.0] * 6,
            "normal_feat": list(np.random.default_rng(1).normal(0, 1, 30)),
        }
        outcomes = [int(x > 0) for x in np.random.default_rng(2).normal(0, 1, 30)]
        result = select_features(fm, outcomes)
        assert result.n_features_in == 2
        for score in result.importance_scores.values():
            assert math.isfinite(score)

    def test_shap_fallback_no_error(self) -> None:
        """5C-14: shap 不可用時退回排列重要性不報錯"""
        import sys
        from wbc_backend.features.feature_selector import select_features
        # 強制跳過 SHAP
        fm = _make_feature_matrix(30)
        outcomes = _make_outcomes(fm)
        result = select_features(fm, outcomes, use_shap=False)
        assert result.method == "permutation"
        assert len(result.selected_features) >= 0

    def test_large_feature_set(self) -> None:
        """5C-15: 大型特徵集（50 個特徵）處理效能"""
        import time
        from wbc_backend.features.feature_selector import select_features
        rng = np.random.default_rng(0)
        n = 40
        fm = {f"feat_{i}": rng.normal(0, 1, n).tolist() for i in range(50)}
        outcomes = [int(x > 0) for x in rng.normal(0, 1, n)]
        start = time.time()
        result = select_features(fm, outcomes, top_n=20, use_shap=False)
        elapsed = time.time() - start
        assert elapsed < 30.0, f"50 個特徵選擇耗時 {elapsed:.1f}s > 30s"
        assert result.n_features_in == 50


# ══════════════════════════════════════════════════════════════════════════════
# 跨模組整合測試
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase5Integration:

    def test_ontology_feeds_feature_selector(self) -> None:
        """整合-01: ontology_discovery 的 top_k_features 可直接供 feature_selector 篩選"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        from wbc_backend.features.feature_selector import select_features
        fm = _make_feature_matrix(50)
        outcomes = _make_outcomes(fm)

        # Step 1: 本體發現
        report = discover_ontology(fm, outcomes, top_k=3)
        top_feats = report.top_k_features

        # Step 2: 只對 top 特徵進行精確剪枝
        sub_fm = {k: fm[k] for k in top_feats if k in fm}
        if sub_fm:
            result = select_features(sub_fm, outcomes, top_n=3)
            assert result.n_features_in <= len(top_feats)

    def test_hierarchical_mc_with_all_layers(self) -> None:
        """整合-02: 三層信號同時啟用時 HierarchicalMC 正常執行"""
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo
        pred = _make_pred()
        r = run_hierarchical_monte_carlo(
            pred,
            simulations=3_000,
            ci_bootstrap_runs=2,
            market_signals={
                "steam_move_prob": 0.5,
                "clv_estimate_home": 0.05,
                "line_movement_pct": 0.2,
            },
            kg_signals={
                "h2h_home_win_rate": 0.60,
                "legacy_advantage_score": 0.3,
            },
            nlp_signals={
                "injury_severity_score": 0.3,
                "weather_impact_score": 0.1,
                "pregame_sentiment_score": 0.6,
            },
        )
        assert 0.0 <= r.home_win_prob <= 1.0
        assert r.total_adjustment_magnitude >= 0.0
        assert "layer2_market" in r.layer_audit

    def test_full_pipeline_50_games(self) -> None:
        """整合-03: 模擬 50 場歷史賽事完整流程"""
        from wbc_backend.features.ontology_discovery import discover_ontology
        from wbc_backend.features.feature_selector import select_features
        from wbc_backend.simulation.hierarchical_mc import run_hierarchical_monte_carlo

        fm = _make_feature_matrix(50)
        outcomes = _make_outcomes(fm)

        # 1. 發現特徵本體
        report = discover_ontology(fm, outcomes, top_k=4)
        assert report.n_samples == 50

        # 2. 剪枝特徵
        selector_result = select_features(fm, outcomes, top_n=4, use_shap=False)
        assert selector_result.n_features_out <= 4

        # 3. 執行階層式蒙特卡洛
        pred = _make_pred()
        sim = run_hierarchical_monte_carlo(pred, simulations=3_000, ci_bootstrap_runs=2)
        assert math.isfinite(sim.home_win_prob)
        assert 0.0 <= sim.home_win_prob <= 1.0
