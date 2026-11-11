"""
P3 — MARL Reward Contract Tests
================================
驗證 compute_true_outcome_reward 函式的正確性與禁止條件。

硬性約束（所有測試）：
- paper_only 永遠 True
- reward 不得來自 EV-proxy
- 不得有 hard-coded -110 / -1.1 literal
"""
from __future__ import annotations

import ast
import inspect
import pytest

from wbc_backend.recommendation.marl_strategy_adapter import (
    compute_true_outcome_reward,
    american_to_decimal_odds,
)


# ── 基礎 fixture ──────────────────────────────────────────────────────────────

def _base_record(**kwargs) -> dict:
    """回傳一筆最小合法 paper_only=True 記錄。"""
    base = {
        "game_id": "TEST_001",
        "game_date": "2026-05-20",
        "bet_side": "HOME",
        "home_ml_odds": 110.0,   # decimal = 2.1
        "away_ml_odds": -130.0,
        "stake_unit": 1.0,
        "actual_home_win": 1,
        "ambiguous_doubleheader": False,
        "paper_only": True,
    }
    base.update(kwargs)
    return base


# ── Test 1: WIN case reward 計算正確 ─────────────────────────────────────────

def test_true_outcome_reward_win_case():
    """
    HOME 下注，home 贏 → reward = stake * (decimal - 1)
    home_ml_odds=110 → decimal=2.1 → reward = 1.0 * (2.1 - 1) = 1.1
    """
    rec = _base_record(home_ml_odds=110.0, stake_unit=1.0, actual_home_win=1)
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "ok"
    assert result["reward_source"] == "TRUE_OUTCOME"
    assert result["paper_only"] is True
    assert result["selected_side_win"] == 1
    expected = 1.0 * (american_to_decimal_odds(110.0) - 1.0)
    assert abs(result["reward"] - expected) < 1e-5


# ── Test 2: LOSS case reward 計算正確 ────────────────────────────────────────

def test_true_outcome_reward_loss_case():
    """
    HOME 下注，home 輸 → reward = -stake
    """
    rec = _base_record(home_ml_odds=110.0, stake_unit=2.5, actual_home_win=0)
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "ok"
    assert result["reward"] == pytest.approx(-2.5, abs=1e-5)
    assert result["selected_side_win"] == 0
    assert result["paper_only"] is True


# ── Test 3: AWAY 下注，side 與 actual_outcome 不一致 → skip side_mismatch ────

def test_skip_when_bet_side_is_no_bet():
    """
    bet_side='NO_BET' 不可計算 reward → skip with reason 'side_mismatch'
    """
    rec = _base_record(bet_side="NO_BET", actual_home_win=1)
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "skip"
    assert result["skip_reason"] == "side_mismatch"
    assert result["reward"] is None


# ── Test 4: ambiguous_doubleheader=true → 排除 ───────────────────────────────

def test_ambiguous_doubleheader_excluded():
    """
    ambiguous_doubleheader=true → skip 'ambiguous_doubleheader'
    """
    rec = _base_record(ambiguous_doubleheader=True)
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "skip"
    assert result["skip_reason"] == "ambiguous_doubleheader"
    assert result["reward"] is None


# ── Test 5: paper_only=false → raise ValueError ────────────────────────────

def test_paper_only_false_raises():
    """
    paper_only=false 記錄不得進入 reward 計算 → ValueError
    """
    rec = _base_record(paper_only=False)
    with pytest.raises(ValueError, match="paper_only=false"):
        compute_true_outcome_reward(rec)


# ── Test 6: missing odds → skip 'missing_odds' ───────────────────────────────

def test_missing_odds_skip():
    """
    home_ml_odds=None 且無 payout_assumption_decimal → skip 'missing_odds'
    """
    rec = _base_record(home_ml_odds=None, actual_home_win=1)
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "skip"
    assert result["skip_reason"] == "missing_odds"
    assert result["reward"] is None


# ── Test 7: missing outcome → skip 'missing_outcome' ────────────────────────

def test_missing_outcome_skip():
    """
    actual_home_win=None → skip 'missing_outcome'
    """
    rec = _base_record(actual_home_win=None)
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "skip"
    assert result["skip_reason"] == "missing_outcome"
    assert result["reward"] is None


# ── Test 8: ev_proxy_* 欄位 → raise ValueError ──────────────────────────────

def test_ev_proxy_field_raises():
    """
    record 含 ev_proxy_roi 欄位 → 立即 raise ValueError（禁止 EV-proxy 污染）
    """
    rec = _base_record(ev_proxy_roi=0.05)
    with pytest.raises(ValueError, match="ev_proxy"):
        compute_true_outcome_reward(rec)


# ── Test 9: 禁止 hard-coded -110 / 110 / 1.1 literal 出現在函式原始碼 ────────

def test_no_hardcoded_110_in_reward_function():
    """
    static analysis：compute_true_outcome_reward 函式原始碼不得含有
    hard-coded 110 / -110 / 1.1 / -1.1 payout literal。
    """
    source = inspect.getsource(compute_true_outcome_reward)
    # 透過 AST 確認無 Constant(110) / Constant(-110) / Constant(1.1) / Constant(-1.1)
    tree = ast.parse(source)
    forbidden = {110, -110, 1.1, -1.1}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if node.value in forbidden:
                found.append(node.value)
    assert found == [], (
        f"Hard-coded payout literals found in compute_true_outcome_reward: {found}. "
        "Odds must come from artifact fields only."
    )


# ── Test 10: AWAY 贏 case reward 正確 ────────────────────────────────────────

def test_away_win_reward_correct():
    """
    AWAY 下注，home 輸（actual_home_win=0）→ away 贏 → reward = stake*(dec-1)
    away_ml_odds=-130 → decimal = 1 + 100/130 ≈ 1.7692
    """
    rec = _base_record(
        bet_side="AWAY",
        away_ml_odds=-130.0,
        home_ml_odds=110.0,
        stake_unit=1.0,
        actual_home_win=0,  # away 贏
    )
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "ok"
    assert result["selected_side_win"] == 1
    expected = 1.0 * (american_to_decimal_odds(-130.0) - 1.0)
    assert abs(result["reward"] - expected) < 1e-5


# ── Test 11: payout_assumption_decimal 優先於 ml_odds ────────────────────────

def test_payout_assumption_decimal_takes_priority():
    """
    payout_assumption_decimal 存在時，應優先使用此 artifact 欄位，
    不得改用 home_ml_odds 計算。
    """
    rec = _base_record(
        home_ml_odds=100.0,              # decimal=2.0 if used
        payout_assumption_decimal=1.95,  # 優先：decimal=1.95
        stake_unit=1.0,
        actual_home_win=1,
    )
    result = compute_true_outcome_reward(rec)
    assert result["status"] == "ok"
    assert result["decimal_odds"] == pytest.approx(1.95, abs=1e-5)
    assert result["reward"] == pytest.approx(1.0 * (1.95 - 1.0), abs=1e-5)
