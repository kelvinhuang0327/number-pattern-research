"""
P4 — Optimizer Fitness Contract & Champion Gate
================================================
提供 risk-adjusted fitness 計算與 champion gate 邏輯。

核心原則：
- fitness_score 主體使用 bootstrap lower_bound_score（ci_low），不得是 raw ROI
- 樣本 <30 → status='insufficient_sample'，fitness_score=-999
- champion gate：只有在 challenger 顯著勝出時才升級
- paper_only=false 記錄直接 raise ValueError

禁止：
- EV-proxy 欄位進入 fitness 計算
- raw ROI 作為 fitness_score 主體
- paper_only=false 記錄
"""
from __future__ import annotations

import math
import random
import statistics
from typing import List, Optional

MIN_SAMPLE = 30
_PROHIBITED_EV_PROXY_PREFIXES = ("ev_proxy_",)


def _check_no_ev_proxy(records: list) -> None:
    """若任何 record 含 ev_proxy_* 欄位，raise ValueError。"""
    for r in records:
        for key in r:
            for prefix in _PROHIBITED_EV_PROXY_PREFIXES:
                if key.startswith(prefix):
                    raise ValueError(
                        f"[P4 Fitness] Prohibited EV-proxy field '{key}' "
                        "detected in fitness input records."
                    )


def _check_paper_only(records: list) -> None:
    """若任何 record 的 paper_only=false，raise ValueError。"""
    for r in records:
        if r.get("paper_only") is False:
            raise ValueError(
                "[P4 Fitness] paper_only=false record is forbidden in fitness computation."
            )


def _record_pnl(r: dict) -> Optional[float]:
    """
    從 record 中計算單筆真實 PnL（基於 actual_home_win + artifact odds）。
    若缺少必要欄位，回傳 None（由 caller 排除）。
    """
    if r.get("ambiguous_doubleheader") is True:
        return None
    actual_home_win = r.get("actual_home_win")
    if actual_home_win is None:
        return None
    bet_side = (r.get("bet_side") or "").upper()
    if bet_side not in ("HOME", "AWAY"):
        return None
    stake = float(r.get("stake_unit") or 0.0)
    if stake <= 0:
        return None

    # 從 artifact 欄位讀取 odds（禁止 hard-coded fallback）
    if bet_side == "HOME":
        ml = r.get("home_ml_odds")
    else:
        ml = r.get("away_ml_odds")

    pad = r.get("payout_assumption_decimal")
    if pad is not None:
        decimal_odds = float(pad)
    elif ml is not None:
        ml = float(ml)
        if ml >= 0:
            decimal_odds = 1.0 + ml / 100.0
        else:
            decimal_odds = 1.0 + 100.0 / abs(ml)
    else:
        return None  # missing_odds

    actual_home_win = int(actual_home_win)
    if bet_side == "HOME":
        win = (actual_home_win == 1)
    else:
        win = (actual_home_win == 0)

    if win:
        return round(stake * (decimal_odds - 1.0), 8)
    else:
        return round(-stake, 8)


def _max_drawdown_from_pnls(pnls: list[float]) -> float:
    """Peak-to-trough 最大連虧（以 stake_unit 為單位）。"""
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 6)


def compute_risk_adjusted_fitness(
    records: list[dict],
    n_boot: int = 5000,
    ci: float = 0.95,
    lambda_std: float = 1.0,
    min_samples: int = 30,
) -> dict:
    """
    計算 risk-adjusted fitness。

    回傳：
    {
      'roi': float,
      'ci_low': float,
      'ci_high': float,
      'p_value': float,
      'lower_bound_score': float,     # ci_low（主要 fitness）
      'std_penalised_roi': float,     # mean_roi - lambda_std * std_roi
      'positive_fold_ratio': float,
      'max_drawdown': float,
      'fitness_score': float,         # 主要排序用：lower_bound_score
      'significant_at_5pct': bool,
      'sample_size': int,
      'status': 'ok' | 'insufficient_sample',
      'paper_only': True,
    }

    禁止：
    - ev_proxy_* 欄位 → raise ValueError
    - paper_only=false 記錄 → raise ValueError
    - fitness_score 不得是 raw ROI（使用 lower_bound_score）
    """
    # ── 安全守衛 ──────────────────────────────────────────────────────────
    _check_no_ev_proxy(records)
    _check_paper_only(records)

    # ── 計算各筆 PnL ──────────────────────────────────────────────────────
    pnl_pairs: list[tuple[float, float]] = []  # (pnl, stake)
    fold_pnls: dict[int, list[float]] = {}
    fold_stakes: dict[int, float] = {}

    for r in records:
        pnl = _record_pnl(r)
        if pnl is None:
            continue
        stake = float(r.get("stake_unit") or 0.0)
        pnl_pairs.append((pnl, stake))
        fold = int(r.get("walk_forward_fold") or 0)
        fold_pnls.setdefault(fold, []).append(pnl)
        fold_stakes[fold] = fold_stakes.get(fold, 0.0) + stake

    n = len(pnl_pairs)

    # ── 樣本不足 ──────────────────────────────────────────────────────────
    if n < min_samples:
        return {
            "roi": 0.0,
            "ci_low": -999.0,
            "ci_high": 999.0,
            "p_value": 1.0,
            "lower_bound_score": -999.0,
            "std_penalised_roi": -999.0,
            "positive_fold_ratio": 0.0,
            "max_drawdown": 0.0,
            "fitness_score": -999.0,
            "significant_at_5pct": False,
            "sample_size": n,
            "status": "insufficient_sample",
            "paper_only": True,
        }

    pnls = [p for p, _ in pnl_pairs]
    stakes = [s for _, s in pnl_pairs]
    total_pnl = sum(pnls)
    total_stake = sum(stakes)
    roi = total_pnl / max(total_stake, 1e-8)

    # ── Bootstrap CI ──────────────────────────────────────────────────────
    rng = random.Random(42)
    boot_rois: list[float] = []
    for _ in range(n_boot):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        boot_pnl = sum(pnls[i] for i in idx)
        boot_stake = sum(stakes[i] for i in idx)
        boot_rois.append(boot_pnl / max(boot_stake, 1e-8))

    boot_rois.sort()
    alpha = 1.0 - ci
    lo_idx = int(math.floor(alpha / 2 * n_boot))
    hi_idx = int(math.ceil((1 - alpha / 2) * n_boot)) - 1
    ci_low = boot_rois[max(0, lo_idx)]
    ci_high = boot_rois[min(n_boot - 1, hi_idx)]

    # ── p-value（H0: roi = 0）────────────────────────────────────────────
    p_value = sum(1 for br in boot_rois if br <= 0.0) / n_boot
    if roi < 0:
        p_value = 1.0 - p_value  # two-sided 守護

    # ── std_penalised_roi ─────────────────────────────────────────────────
    roi_std = statistics.stdev(boot_rois) if len(boot_rois) >= 2 else 0.0
    std_penalised_roi = roi - lambda_std * roi_std

    # ── Fold stability ────────────────────────────────────────────────────
    fold_rois: list[float] = []
    for fold, fpnls in fold_pnls.items():
        fstake = fold_stakes[fold]
        if fstake > 0:
            fold_rois.append(sum(fpnls) / fstake)
    positive_fold_ratio = (
        sum(1 for fr in fold_rois if fr > 0) / len(fold_rois) if fold_rois else 0.0
    )

    # ── Max drawdown ──────────────────────────────────────────────────────
    max_drawdown = _max_drawdown_from_pnls(pnls)

    # ── Fitness score：使用 lower_bound_score（不得是 raw ROI）───────────
    lower_bound_score = ci_low
    fitness_score = lower_bound_score  # 主要排序依據

    significant_at_5pct = (p_value < 0.05) and (ci_low > 0.0)

    return {
        "roi": round(roi, 6),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "p_value": round(p_value, 6),
        "lower_bound_score": round(lower_bound_score, 6),
        "std_penalised_roi": round(std_penalised_roi, 6),
        "positive_fold_ratio": round(positive_fold_ratio, 4),
        "max_drawdown": round(max_drawdown, 6),
        "fitness_score": round(fitness_score, 6),
        "significant_at_5pct": significant_at_5pct,
        "sample_size": n,
        "status": "ok",
        "paper_only": True,
    }


def champion_gate(
    champion: dict,
    challenger: dict,
) -> dict:
    """
    Champion Gate：只有在 challenger 顯著勝出時才升級。

    升級條件（全部滿足）：
    1. challenger.status == 'ok'
    2. challenger CI 不跨 0（ci_low > 0）
    3. challenger.p_value < 0.05
    4. challenger.ci_low > champion.ci_low
    5. challenger.positive_fold_ratio > 0.5（多數 fold 為正）
    6. challenger 樣本充足（sample_size >= 30）

    封鎖條件（任一觸發 → 不升級）：
    - challenger CI 跨 0（ci_low <= 0）
    - challenger 樣本不足（status='insufficient_sample'）
    - challenger raw ROI 高但 ci_low <= champion ci_low
    - p_value >= 0.05
    - fold stability 負多數（positive_fold_ratio <= 0.5）

    回傳：{ 'upgrade': bool, 'reason': str }
    """
    # ── 封鎖條件判斷 ──────────────────────────────────────────────────────
    if challenger.get("status") == "insufficient_sample":
        return {
            "upgrade": False,
            "reason": "blocked: challenger 樣本不足（insufficient_sample）",
        }

    if challenger.get("sample_size", 0) < MIN_SAMPLE:
        return {
            "upgrade": False,
            "reason": f"blocked: challenger 樣本數 {challenger.get('sample_size')} < {MIN_SAMPLE}",
        }

    chall_ci_low = challenger.get("ci_low", -999.0)
    if chall_ci_low <= 0.0:
        return {
            "upgrade": False,
            "reason": f"blocked: challenger CI 跨 0（ci_low={chall_ci_low:.4f} <= 0）",
        }

    p_val = challenger.get("p_value", 1.0)
    if p_val >= 0.05:
        return {
            "upgrade": False,
            "reason": f"blocked: challenger p_value={p_val:.4f} >= 0.05，不顯著",
        }

    champ_ci_low = champion.get("ci_low", -999.0)
    if chall_ci_low <= champ_ci_low:
        chall_roi = challenger.get("roi", 0.0)
        champ_roi = champion.get("roi", 0.0)
        if chall_roi > champ_roi:
            return {
                "upgrade": False,
                "reason": (
                    f"blocked: challenger raw ROI={chall_roi:.4f} 較高，"
                    f"但 ci_low={chall_ci_low:.4f} <= champion ci_low={champ_ci_low:.4f}"
                ),
            }
        return {
            "upgrade": False,
            "reason": f"blocked: challenger ci_low={chall_ci_low:.4f} <= champion ci_low={champ_ci_low:.4f}",
        }

    pos_fold = challenger.get("positive_fold_ratio", 0.0)
    if pos_fold <= 0.5:
        return {
            "upgrade": False,
            "reason": f"blocked: challenger fold stability 負多數（positive_fold_ratio={pos_fold:.2f} <= 0.5）",
        }

    # ── 升級 ─────────────────────────────────────────────────────────────
    return {
        "upgrade": True,
        "reason": (
            f"upgrade approved: p={p_val:.4f} < 0.05, "
            f"ci_low={chall_ci_low:.4f} > champion_ci_low={champ_ci_low:.4f}, "
            f"fold_stability={pos_fold:.2f} > 0.5"
        ),
    }
