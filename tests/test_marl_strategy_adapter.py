"""
Tests for wbc_backend/recommendation/marl_strategy_adapter.py
P6_MARL_OPTIMIZER_INTEGRATION — 13+ tests
"""
from __future__ import annotations

import json
import pytest
from wbc_backend.recommendation.marl_strategy_adapter import (
    MARLRecord,
    MARLState,
    MARLAction,
    MARLReward,
    p5_row_to_marl_record,
    calculate_cumulative_drawdown,
    calculate_risk_adjusted_score,
    aggregate_strategy_stats,
)

# ── 測試用 P5 row ─────────────────────────────────────────────────────────────

BASE_ROW = {
    "game_id": "MLB2025_0001",
    "game_date": "2025-03-18",
    "home_team": "Cubs",
    "away_team": "Dodgers",
    "market": "ML",
    "side": "home",
    "bet_side": "HOME",
    "model_prob": 0.5503,
    "implied_prob": 0.4255,
    "edge": 0.0503,
    "kelly_fraction": 0.0565,
    "stake_unit": 0.0141,
    "ev": 0.0706,
    "home_ml_odds": 135.0,
    "away_ml_odds": -155.0,
    "odds_quality_tier": "POST_GAME_PROXY",
    "paper_only": True,
    "walk_forward_fold": 1,
    "ece": 0.035,
    "blowout_propensity": 0.1358,
    "brier_score": None,
    "home_elo": 1490.0,
    "away_elo": 1546.8,
    "home_win_ci_95": [0.3609, 0.5908],
    "source_trace": "Elo_logistic: home_elo=1490.0",
    "actual_home_win": 1,
}

BASE_POLICY = {
    "edge_threshold": 0.01,
    "kelly_fraction_multiplier": 0.25,
    "drawdown_penalty_weight": 0.1,
    "calibration_penalty_weight": 0.05,
}


# ── Test 1: p5_row_to_marl_record 正確轉換 ────────────────────────────────────

def test_p5_row_to_marl_record_basic():
    rec = p5_row_to_marl_record(BASE_ROW, BASE_POLICY)
    assert rec is not None
    assert rec.state.game_id == "MLB2025_0001"
    assert rec.state.edge == pytest.approx(0.0503)
    assert rec.state.walk_forward_fold == 1


# ── Test 2: paper_only 永遠 True ──────────────────────────────────────────────

def test_paper_only_always_true():
    row = dict(BASE_ROW)
    row["paper_only"] = False  # 嘗試設 False
    rec = p5_row_to_marl_record(row, BASE_POLICY)
    assert rec.paper_only is True
    d = rec.to_dict()
    assert d["paper_only"] is True


# ── Test 3: missing actual_home_win → reward=0, invalid_for_reward=True ───────

def test_missing_actual_home_win():
    row = dict(BASE_ROW)
    del row["actual_home_win"]
    rec = p5_row_to_marl_record(row, BASE_POLICY)
    assert rec.invalid_for_reward is True
    assert rec.reward.proxy_profit_loss == 0.0
    assert rec.reward.roi == 0.0


# ── Test 4: reward 不可使用未來 rows（actual_home_win=None 時 reward=0）────────

def test_reward_no_future_leakage():
    """實作上 reward 只從當前 row 的 actual_home_win 計算，不參考其他 rows"""
    row = {**BASE_ROW, "actual_home_win": None}
    rec = p5_row_to_marl_record(row, BASE_POLICY)
    # 無 actual_home_win → reward=0，不可 look-ahead
    assert rec.reward.proxy_profit_loss == 0.0
    assert rec.invalid_for_reward is True


# ── Test 5: edge_threshold policy 正確過濾 ───────────────────────────────────

def test_edge_threshold_filtering():
    # edge=0.0503 > 0.10 時不下注
    policy_high = {**BASE_POLICY, "edge_threshold": 0.10}
    rec = p5_row_to_marl_record(BASE_ROW, policy_high)
    # edge 0.0503 < 0.10 → 不下注
    assert rec.action.bet is False

    # edge=0.0503 > 0.01 時下注
    policy_low = {**BASE_POLICY, "edge_threshold": 0.01}
    rec2 = p5_row_to_marl_record(BASE_ROW, policy_low)
    assert rec2.action.bet is True


# ── Test 6: kelly multiplier policy 正確縮放 ─────────────────────────────────

def test_kelly_multiplier_scaling():
    policy_50 = {**BASE_POLICY, "kelly_fraction_multiplier": 0.50}
    policy_25 = {**BASE_POLICY, "kelly_fraction_multiplier": 0.25}
    rec50 = p5_row_to_marl_record(BASE_ROW, policy_50)
    rec25 = p5_row_to_marl_record(BASE_ROW, policy_25)
    assert rec50.action.kelly_fraction_multiplier == pytest.approx(0.50)
    assert rec25.action.kelly_fraction_multiplier == pytest.approx(0.25)
    # 50% kelly PnL 應大於 25%（同勝情況）
    if rec50.action.bet and rec25.action.bet:
        assert abs(rec50.reward.proxy_profit_loss) > abs(rec25.reward.proxy_profit_loss)


# ── Test 7: drawdown penalty 計算正確（peak-to-trough）───────────────────────

def test_drawdown_calculation():
    # 序列：+1, +1, -3, +1  →  peak=2, trough=2-(-1)=3 ← peak-to-trough
    def make_rec(pnl: float) -> MARLRecord:
        state = MARLState("g1", "2025-01-01", 0.55, 0.45, 0.10, 0.10, 1.0, 1, "POST_GAME_PROXY")
        action = MARLAction(bet=True)
        reward = MARLReward(proxy_profit_loss=pnl)
        return MARLRecord(state=state, action=action, reward=reward, actual_home_win=1)

    records = [make_rec(1.0), make_rec(1.0), make_rec(-3.0), make_rec(1.0)]
    dd = calculate_cumulative_drawdown(records)
    # peak=2.0, trough point=-1.0 → drawdown=3.0
    assert dd == pytest.approx(3.0, abs=1e-5)


# ── Test 8: calibration penalty 邏輯正確 ─────────────────────────────────────

def test_calibration_penalty():
    # ECE=0.035（基準值）→ penalty=0
    row_base = {**BASE_ROW, "ece": 0.035}
    rec_base = p5_row_to_marl_record(row_base, BASE_POLICY)
    assert rec_base.reward.calibration_penalty == pytest.approx(0.0, abs=1e-8)

    # ECE=0.12 > 0.035 → penalty > 0
    row_high = {**BASE_ROW, "ece": 0.12}
    rec_high = p5_row_to_marl_record(row_high, BASE_POLICY)
    assert rec_high.reward.calibration_penalty > 0.0


# ── Test 9: fold-level aggregation 正確 ──────────────────────────────────────

def test_fold_level_aggregation():
    def make_rec(fold: int, pnl: float, bet: bool = True) -> MARLRecord:
        state = MARLState("g1", "2025-01-01", 0.55, 0.45, 0.10, 0.10, 1.0,
                          fold, "POST_GAME_PROXY")
        action = MARLAction(bet=bet)
        reward = MARLReward(proxy_profit_loss=pnl)
        return MARLRecord(state=state, action=action, reward=reward, actual_home_win=1)

    records = [
        make_rec(1, 1.0), make_rec(1, -0.5),
        make_rec(2, 2.0), make_rec(2, -1.0),
    ]
    stats = aggregate_strategy_stats(records, "test_strategy")
    assert "fold_1" in stats["fold_level"]
    assert "fold_2" in stats["fold_level"]
    assert stats["fold_level"]["fold_1"]["bets"] == 2
    assert stats["fold_level"]["fold_2"]["bets"] == 2


# ── Test 10: MARLRecord 可 JSON serialize ─────────────────────────────────────

def test_marl_record_json_serializable():
    rec = p5_row_to_marl_record(BASE_ROW, BASE_POLICY)
    d = rec.to_dict()
    json_str = json.dumps(d)  # 不應 raise
    parsed = json.loads(json_str)
    assert parsed["paper_only"] is True
    assert "proxy_roi_disclaimer" in parsed


# ── Test 11: odds_quality_tier 必須保留 ──────────────────────────────────────

def test_odds_quality_tier_preserved():
    row = {**BASE_ROW, "odds_quality_tier": "POST_GAME_PROXY"}
    rec = p5_row_to_marl_record(row, BASE_POLICY)
    assert rec.state.odds_quality_tier == "POST_GAME_PROXY"


# ── Test 12: proxy ROI 標記非真實 CLV ────────────────────────────────────────

def test_proxy_roi_disclaimer_present():
    def make_rec(pnl: float) -> MARLRecord:
        state = MARLState("g1", "2025-01-01", 0.55, 0.45, 0.10, 0.10, 1.0, 1, "POST_GAME_PROXY")
        action = MARLAction(bet=True)
        reward = MARLReward(proxy_profit_loss=pnl)
        return MARLRecord(state=state, action=action, reward=reward, actual_home_win=1)

    records = [make_rec(0.5), make_rec(-0.3)]
    stats = aggregate_strategy_stats(records, "test")
    assert "proxy_roi_disclaimer" in stats
    assert "NOT real CLV" in stats["proxy_roi_disclaimer"]

    # to_dict 也必須有 disclaimer
    rec = p5_row_to_marl_record(BASE_ROW, BASE_POLICY)
    d = rec.to_dict()
    assert "NOT real CLV" in d.get("proxy_roi_disclaimer", "")


# ── Test 13: production channel 不得寫入 ─────────────────────────────────────

def test_production_channel_not_written():
    """production channel 寫入守衛：aggregate_strategy_stats 輸出 paper_only=True"""
    def make_rec() -> MARLRecord:
        state = MARLState("g1", "2025-01-01", 0.55, 0.45, 0.10, 0.10, 1.0, 1, "POST_GAME_PROXY")
        action = MARLAction(bet=True)
        reward = MARLReward(proxy_profit_loss=1.0)
        return MARLRecord(state=state, action=action, reward=reward, actual_home_win=1)

    stats = aggregate_strategy_stats([make_rec()], "test")
    assert stats["paper_only"] is True


# ── Test 14: risk_adjusted_score 公式正確 ────────────────────────────────────

def test_risk_adjusted_score_formula():
    score = calculate_risk_adjusted_score(roi=0.1, drawdown=0.05, volatility=0.02,
                                           roi_weight=0.6, drawdown_weight=0.3,
                                           volatility_weight=0.1)
    expected = 0.6 * 0.1 - 0.3 * 0.05 - 0.1 * 0.02
    assert score == pytest.approx(expected, abs=1e-8)


# ── Test 15: NO_BET row 不下注 ───────────────────────────────────────────────

def test_no_bet_row_action_false():
    row = {**BASE_ROW, "bet_side": "NO_BET", "edge": 0.001}
    rec = p5_row_to_marl_record(row, BASE_POLICY)
    assert rec.action.bet is False
