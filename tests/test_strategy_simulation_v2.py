"""
tests/test_strategy_simulation_v2.py — P2 SimulationRecommendationV2 合約測試

至少 12 個測試，覆蓋：
  - dataclass 建構與 __post_init__ 約束
  - model_source 禁止 PROXY_DERIVED
  - paper_only 永遠 True
  - to_dict / to_json 序列化
  - MARL 下游欄位
  - 腳本輸出 artifact 基本驗證
"""
from __future__ import annotations

import json
import os
import pytest

# 確保 worktree root 在 sys.path
import sys
_WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WT_ROOT not in sys.path:
    sys.path.insert(0, _WT_ROOT)

from wbc_backend.recommendation.simulation_recommendation_v2 import (
    SimulationRecommendationV2,
)


# ─── 輔助函數 ────────────────────────────────────────────────────────────────

def _minimal_rec(**kwargs) -> SimulationRecommendationV2:
    """建立最小合法 SimulationRecommendationV2。"""
    defaults = dict(
        game_id="TEST_0001",
        game_date="2025-04-01",
        model_prob=0.55,
        implied_prob=0.50,
        edge=0.05,
        model_source="SimplifiedElo_v1",
        odds_quality_tier="POST_GAME_PROXY",
    )
    defaults.update(kwargs)
    return SimulationRecommendationV2(**defaults)


# ─── T01：合法建構 ───────────────────────────────────────────────────────────

def test_t01_valid_construction():
    rec = _minimal_rec()
    assert rec.game_id == "TEST_0001"
    assert rec.model_prob == 0.55
    assert rec.paper_only is True


# ─── T02：paper_only 永遠 True ───────────────────────────────────────────────

def test_t02_paper_only_must_be_true():
    with pytest.raises(AssertionError, match="paper_only"):
        SimulationRecommendationV2(
            game_id="TEST_0002",
            game_date="2025-04-01",
            model_prob=0.55,
            model_source="SimplifiedElo_v1",
            odds_quality_tier="POST_GAME_PROXY",
            paper_only=False,  # 非法
        )


# ─── T03：model_source 不得含 PROXY_DERIVED ─────────────────────────────────

def test_t03_proxy_derived_model_source_forbidden():
    with pytest.raises(ValueError, match="PROXY_DERIVED"):
        _minimal_rec(model_source="PROXY_DERIVED_odds_inverse")


# ─── T04：model_source 不得為空 ─────────────────────────────────────────────

def test_t04_empty_model_source_forbidden():
    with pytest.raises(AssertionError, match="model_source"):
        _minimal_rec(model_source="")


# ─── T05：odds_quality_tier 不得為空 ────────────────────────────────────────

def test_t05_empty_odds_quality_tier_forbidden():
    with pytest.raises(AssertionError, match="odds_quality_tier"):
        _minimal_rec(odds_quality_tier="")


# ─── T06：to_dict 序列化正確 ─────────────────────────────────────────────────

def test_t06_to_dict_contains_required_keys():
    rec = _minimal_rec(
        side="home",
        bet_side="HOME",
        kelly_fraction=0.025,
        stake_unit=0.025,
        walk_forward_fold=3,
    )
    d = rec.to_dict()
    required_keys = [
        "game_id", "game_date", "model_prob", "implied_prob", "edge",
        "model_source", "odds_quality_tier", "paper_only",
        "kelly_fraction", "stake_unit", "walk_forward_fold",
        "generated_at_utc", "source_trace",
        "home_win_ci_95", "world_model_score_dist", "marl_strategy_weight",
        "gates_passed", "rejected_reason",
    ]
    for key in required_keys:
        assert key in d, f"Missing key: {key}"


# ─── T07：to_json 可解析 ─────────────────────────────────────────────────────

def test_t07_to_json_parseable():
    rec = _minimal_rec()
    raw = rec.to_json()
    parsed = json.loads(raw)
    assert parsed["model_prob"] == pytest.approx(0.55, abs=1e-4)
    assert parsed["paper_only"] is True


# ─── T08：MARL 下游欄位 ──────────────────────────────────────────────────────

def test_t08_marl_downstream_fields():
    rec = _minimal_rec(
        home_win_ci_95=(0.48, 0.62),
        world_model_score_dist={"mean_home": 4.2, "mean_away": 3.8},
        marl_strategy_weight=0.40,
    )
    d = rec.to_dict()
    assert d["home_win_ci_95"] == [0.48, 0.62]
    assert d["world_model_score_dist"]["mean_home"] == pytest.approx(4.2)
    assert d["marl_strategy_weight"] == pytest.approx(0.40)


# ─── T09：generated_at_utc 自動填充 ─────────────────────────────────────────

def test_t09_generated_at_utc_auto_filled():
    rec = _minimal_rec()
    assert rec.generated_at_utc != ""
    # 應為 ISO 格式
    assert "T" in rec.generated_at_utc


# ─── T10：model_prob 來自 Elo 不含 odds 的合法案例 ───────────────────────────

def test_t10_elo_based_model_prob_is_valid():
    """SimplifiedElo_v1 的 model_prob 不依賴 odds，合法"""
    elo_home, elo_away = 1520.0, 1480.0
    elo_d = 400.0
    p_home = 1.0 / (1.0 + 10 ** ((elo_away - elo_home) / elo_d))
    rec = _minimal_rec(
        model_prob=p_home,
        model_source="SimplifiedElo_v1",
        home_elo=elo_home,
        away_elo=elo_away,
        source_trace=f"Elo_logistic: home={elo_home}, away={elo_away}",
    )
    assert rec.model_prob == pytest.approx(p_home, abs=1e-4)
    assert "PROXY" not in rec.model_source


# ─── T11：rejected_reason 在 NO_BET 時正確記錄 ──────────────────────────────

def test_t11_no_bet_with_rejected_reason():
    rec = _minimal_rec(
        side="",
        bet_side="NO_BET",
        edge=-0.02,
        rejected_reason="edge_gate: edge=-0.02 < 0.01",
        gates_passed=["ece_pass"],
    )
    d = rec.to_dict()
    assert d["rejected_reason"] is not None
    assert "edge_gate" in d["rejected_reason"]
    assert "ece_pass" in d["gates_passed"]


# ─── T12：artifact JSONL 存在且格式正確 ─────────────────────────────────────

def test_t12_artifact_exists_and_parseable():
    """確認腳本輸出的 artifact 存在且每行可解析。"""
    artifact_path = os.path.join(
        _WT_ROOT,
        "data", "paper_recommendations", "strategy_sim_v2_20260518.jsonl"
    )
    if not os.path.exists(artifact_path):
        pytest.skip("strategy_sim_v2_20260518.jsonl 尚未產出，跳過（請先執行 run_strategy_simulation_v2.py）")

    with open(artifact_path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    assert len(lines) > 0, "Artifact 不得為空"
    for i, line in enumerate(lines[:5]):
        row = json.loads(line)
        assert "game_id" in row, f"第 {i} 行缺少 game_id"
        assert "model_prob" in row, f"第 {i} 行缺少 model_prob"
        assert row["paper_only"] is True, f"第 {i} 行 paper_only != True"
        assert "PROXY_DERIVED" not in row.get("model_source", ""), (
            f"第 {i} 行 model_source 含 PROXY_DERIVED"
        )


# ─── T13：walk_forward_fold 數值合法 ────────────────────────────────────────

def test_t13_walk_forward_fold_nonnegative():
    rec = _minimal_rec(walk_forward_fold=5)
    assert rec.walk_forward_fold >= 0

    rec2 = _minimal_rec(walk_forward_fold=0)
    assert rec2.walk_forward_fold == 0


# ─── T14：Elo 差距 => 機率單調性 ────────────────────────────────────────────

def test_t14_elo_prob_monotone():
    """Elo 差距越大，勝率越高（單調性驗證）。"""
    def elo_prob(home_elo: float, away_elo: float) -> float:
        return 1.0 / (1.0 + 10 ** ((away_elo - home_elo) / 400.0))

    p_equal = elo_prob(1500, 1500)
    p_slight = elo_prob(1520, 1480)
    p_strong = elo_prob(1600, 1400)

    assert abs(p_equal - 0.5) < 1e-6
    assert p_slight > p_equal
    assert p_strong > p_slight
