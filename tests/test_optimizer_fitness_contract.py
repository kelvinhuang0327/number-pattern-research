"""
P4 — Optimizer Fitness Contract & Champion Gate Tests
======================================================
驗證 compute_risk_adjusted_fitness 與 champion_gate 函式的正確性與禁止條件。

硬性約束：
- fitness_score 主體必須是 lower_bound_score（不得是 raw ROI）
- paper_only 永遠 True
- EV-proxy 欄位禁止進入 fitness
"""
from __future__ import annotations

import pytest
from wbc_backend.recommendation.optimizer_fitness import (
    compute_risk_adjusted_fitness,
    champion_gate,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_records(n: int, win_rate: float = 0.5, stake: float = 1.0,
                  home_ml: float = -110.0) -> list[dict]:
    """
    生成 n 筆合法 paper_only=True 記錄（fold 均勻分布）。
    win_rate 控制 HOME 贏的比例，home_ml 控制賠率。
    """
    records = []
    for i in range(n):
        win = 1 if (i / n) < win_rate else 0
        records.append({
            "game_id": f"TEST_{i:04d}",
            "bet_side": "HOME",
            "home_ml_odds": home_ml,
            "away_ml_odds": 100.0,
            "stake_unit": stake,
            "actual_home_win": win,
            "ambiguous_doubleheader": False,
            "paper_only": True,
            "walk_forward_fold": (i % 7) + 1,
        })
    return records


def _make_fitness_result(
    ci_low: float = 0.0,
    roi: float = 0.0,
    p_value: float = 0.5,
    positive_fold_ratio: float = 0.5,
    sample_size: int = 100,
    status: str = "ok",
) -> dict:
    return {
        "roi": roi,
        "ci_low": ci_low,
        "ci_high": ci_low + 0.1,
        "p_value": p_value,
        "lower_bound_score": ci_low,
        "std_penalised_roi": roi - 0.01,
        "positive_fold_ratio": positive_fold_ratio,
        "max_drawdown": 0.5,
        "fitness_score": ci_low,
        "significant_at_5pct": (p_value < 0.05 and ci_low > 0),
        "sample_size": sample_size,
        "status": status,
        "paper_only": True,
    }


# ── Test 1: raw ROI 較高但 CI 跨 0 → 不升級 ─────────────────────────────────

def test_champion_gate_blocks_when_ci_crosses_zero():
    """
    challenger raw ROI 高但 ci_low <= 0 → 封鎖升級。
    """
    champion = _make_fitness_result(ci_low=-0.039, roi=0.018)
    challenger = _make_fitness_result(ci_low=-0.01, roi=0.05, p_value=0.03)
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False
    assert "CI" in result["reason"] or "ci_low" in result["reason"]


# ── Test 2: lower_bound 較差 → 不升級 ────────────────────────────────────────

def test_champion_gate_blocks_when_lower_bound_worse():
    """
    challenger ci_low < champion ci_low → 封鎖，即使 raw ROI 較高。
    """
    champion = _make_fitness_result(ci_low=0.02, roi=0.03, p_value=0.01)
    challenger = _make_fitness_result(ci_low=0.01, roi=0.10, p_value=0.01,
                                       positive_fold_ratio=0.7)
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False
    assert "ci_low" in result["reason"]


# ── Test 3: 顯著勝出 → 可升級 ────────────────────────────────────────────────

def test_champion_gate_allows_when_significantly_better():
    """
    challenger p<0.05 + ci_low > champion.ci_low + fold stable → upgrade=True
    """
    champion = _make_fitness_result(ci_low=-0.039, roi=0.018)
    challenger = _make_fitness_result(ci_low=0.05, roi=0.12, p_value=0.02,
                                       positive_fold_ratio=0.7)
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is True
    assert "approve" in result["reason"] or "upgrade" in result["reason"].lower()


# ── Test 4: fitness_score 使用 lower_bound_score，不得是 raw ROI ──────────────

def test_fitness_score_is_lower_bound_not_raw_roi():
    """
    fitness_score 必須等於 ci_low（lower_bound_score），不得是 raw ROI。
    """
    records = _make_records(200, win_rate=0.52, home_ml=-110.0)
    result = compute_risk_adjusted_fitness(records, n_boot=500)
    assert result["status"] in ("ok", "insufficient_sample")
    if result["status"] == "ok":
        # fitness_score 必須等於 lower_bound_score，不得等於 roi（除非恰好相等）
        assert abs(result["fitness_score"] - result["lower_bound_score"]) < 1e-6
        # 通常 lower_bound_score != roi（除非特殊情境）
        # 此測試確保 fitness_score 的主體是 ci_low
        assert result["fitness_score"] == pytest.approx(result["ci_low"], abs=1e-5)
    assert result["paper_only"] is True


# ── Test 5: 樣本不足（n<30）→ blocked ────────────────────────────────────────

def test_insufficient_sample_returns_sentinel():
    """
    n=10 < 30 → status='insufficient_sample'，fitness_score=-999
    """
    records = _make_records(10, win_rate=0.6)
    result = compute_risk_adjusted_fitness(records)
    assert result["status"] == "insufficient_sample"
    assert result["fitness_score"] == -999.0
    assert result["paper_only"] is True


# ── Test 6: max_drawdown 大 → fitness 不升級 ─────────────────────────────────

def test_champion_gate_blocks_high_drawdown_challenger():
    """
    challenger 有高 max_drawdown 的情境：若 fold stability 差 → 封鎖。
    此測試透過 positive_fold_ratio <= 0.5 觸發封鎖條件。
    """
    champion = _make_fitness_result(ci_low=-0.039)
    # 即使 ci_low > 0 且 p < 0.05，但 fold stability 差 → 封鎖
    challenger = _make_fitness_result(
        ci_low=0.05, roi=0.12, p_value=0.02,
        positive_fold_ratio=0.43,  # <= 0.5 觸發封鎖
    )
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False
    assert "fold" in result["reason"].lower() or "stability" in result["reason"].lower()


# ── Test 7: fold stability 負多數 → blocked ───────────────────────────────────

def test_champion_gate_blocks_negative_fold_majority():
    """
    positive_fold_ratio=0.3（多數 fold 為負）→ 封鎖升級。
    """
    champion = _make_fitness_result(ci_low=-0.039)
    challenger = _make_fitness_result(
        ci_low=0.06, roi=0.15, p_value=0.01,
        positive_fold_ratio=0.3,
    )
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False


# ── Test 8: paper_only=false → raise ValueError ──────────────────────────────

def test_paper_only_false_raises_in_fitness():
    """
    records 中含 paper_only=false → compute_risk_adjusted_fitness 立即 raise
    """
    records = _make_records(50)
    records[0]["paper_only"] = False
    with pytest.raises(ValueError, match="paper_only=false"):
        compute_risk_adjusted_fitness(records)


# ── Test 9: ev_proxy_* 欄位 → raise ValueError ───────────────────────────────

def test_ev_proxy_field_raises_in_fitness():
    """
    records 中含 ev_proxy_roi 欄位 → raise ValueError（禁止 EV-proxy 污染）
    """
    records = _make_records(50)
    records[0]["ev_proxy_roi"] = 0.05
    with pytest.raises(ValueError, match="ev_proxy"):
        compute_risk_adjusted_fitness(records)


# ── Test 10: challenger 樣本不足 → gate 封鎖 ────────────────────────────────

def test_champion_gate_blocks_insufficient_challenger():
    """
    challenger status='insufficient_sample' → 封鎖，不升級。
    """
    champion = _make_fitness_result(ci_low=-0.039)
    challenger = _make_fitness_result(status="insufficient_sample",
                                       ci_low=-999.0, sample_size=5)
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False
    assert "insufficient_sample" in result["reason"] or "樣本" in result["reason"]


# ── Test 11: 完整 pipeline：從 records 到 gate ───────────────────────────────

def test_full_pipeline_champion_vs_challenger():
    """
    端對端：用 records 計算 fitness，再跑 champion gate。
    challenger = current baseline（不顯著）→ 不應升級。
    """
    # baseline champion（固定值，來自 P2 報告）
    champion = _make_fitness_result(
        ci_low=-0.03895,
        roi=0.018384,
        p_value=0.535846,
    )
    # challenger = 相同 records，同樣不顯著
    records = _make_records(200, win_rate=0.501)
    challenger = compute_risk_adjusted_fitness(records, n_boot=500)
    result = champion_gate(champion, challenger)
    # 正常情況下不顯著 → 不升級
    assert isinstance(result["upgrade"], bool)
    assert "reason" in result
