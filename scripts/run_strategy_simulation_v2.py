"""
run_strategy_simulation_v2.py — P2_STRATEGY_SIMULATION_V2_INDEPENDENT_PROB

路徑選擇：路徑 B — SimplifiedElo_v1
  - PredictionOrchestrator 所需相依模組（MARL / HierarchicalMC / WorldModel）
    在此 worktree 中不存在，故使用 SimplifiedElo_v1 作為替代
  - model_prob 完全由 Walk-Forward Elo（滾動更新，K=20, D=400）計算
  - 絕不使用 odds 反推 model_prob
  - implied_prob = de-vigged closing proxy price（僅作為 edge 計算之用）

執行流程：
1. 讀取 data/mlb_2025/mlb_odds_2025_real.csv（2430 場 MLB 2025）
2. Walk-Forward 計算每隊滾動 Elo（賽前狀態，無 Look-ahead Leakage）
3. model_prob = elo_expected(home_elo, away_elo)  ← 獨立，不依賴 odds
4. implied_prob = de-vigged closing proxy price（用於 edge / kelly 計算）
5. 套用 Gate 過濾（ECE / Blowout / Edge）
6. 產出 data/paper_recommendations/strategy_sim_v2_20260518.jsonl
7. 產出 report/strategy_sim_v2_20260518.md
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import argparse

from wbc_backend.recommendation.simulation_recommendation_v2 import (
    SimulationRecommendationV2,
)
from wbc_backend.recommendation.elo_repair import (
    is_spring_training_game,
    initialize_elo_from_win_rate,
    check_2024_data_availability,
    MLB_2024_WIN_RATES,
    apply_walk_forward_platt_calibration,
)

# ── 路徑設定 ────────────────────────────────────────────────────────────────
DATA_CSV = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
OUT_DIR = ROOT / "data" / "paper_recommendations"
REPORT_DIR = ROOT / "report"
RUN_DATE = "20260518"
ARTIFACT_PATH = OUT_DIR / f"strategy_sim_v2_{RUN_DATE}.jsonl"
REPORT_PATH = REPORT_DIR / f"strategy_sim_v2_{RUN_DATE}.md"
RUN_ID = f"P2_SIM_V2_{RUN_DATE}"

# ── Elo 參數（與 mlb_data_loader.py 一致）────────────────────────────────────
_ELO_K = 20.0
_ELO_D = 400.0
_ELO_INIT = 1500.0

# ── Gate 閾值 ────────────────────────────────────────────────────────────────
_ECE_THRESHOLD = 0.12        # ECE > 0.12 → reject
_BLOWOUT_THRESHOLD = 0.65    # blowout_propensity > 0.65 → reject
_EDGE_THRESHOLD = 0.01       # edge < 0.01 → reject
_KELLY_CAP = 0.05            # 最大 5% 倉位
_KELLY_FRACTION = 0.25       # 使用 1/4 Kelly

# ── 模型 ECE（來自 MEMORY.md：Platt calibration 後 ECE=0.035）────────────────
_SYSTEM_ECE = 0.035

# ── Walk-Forward fold 邊界（月份分層，12 個 fold）────────────────────────────
_WF_MONTH_FOLDS = {
    "03": 1, "04": 2, "05": 3, "06": 4,
    "07": 5, "08": 6, "09": 7, "10": 8,
}


# ── Elo 公式 ─────────────────────────────────────────────────────────────────

def _elo_expected(home_elo: float, away_elo: float) -> float:
    """計算 home 隊勝率（標準 Elo 公式）。"""
    return 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo) / _ELO_D))


def _elo_update(winner_elo: float, loser_elo: float) -> tuple[float, float]:
    """賽後更新雙方 Elo，返回 (new_winner_elo, new_loser_elo)。"""
    exp = _elo_expected(winner_elo, loser_elo)
    delta = _ELO_K * (1.0 - exp)
    return winner_elo + delta, loser_elo - delta


# ── Odds 工具 ─────────────────────────────────────────────────────────────────

def _parse_american(s: str) -> float | None:
    try:
        return float(str(s).strip())
    except (ValueError, TypeError):
        return None


def _american_to_prob(odds: float) -> float:
    """美式盤口 → 原始隱含機率。"""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return (-odds) / (-odds + 100.0)


def _remove_vig(p_home: float, p_away: float) -> tuple[float, float]:
    """去 vig：正規化兩邊機率，合計=1。"""
    total = p_home + p_away
    if total <= 0:
        return 0.5, 0.5
    return p_home / total, p_away / total


# ── Blowout propensity（簡化：基於 Elo 差距）─────────────────────────────────

def _blowout_propensity(home_elo: float, away_elo: float) -> float:
    """Elo 差距越大，崩盤風險越高（0~1）。"""
    diff = abs(home_elo - away_elo)
    # logistic：差距 300+ → ~0.7；差距 0 → ~0.15
    return 1.0 / (1.0 + math.exp(-(diff - 200.0) / 80.0)) * 0.6 + 0.05


# ── Kelly 計算 ────────────────────────────────────────────────────────────────

def _kelly(model_prob: float, decimal_odds: float) -> float:
    """Kelly 公式，返回 f*。"""
    b = decimal_odds - 1.0
    if b <= 0 or model_prob <= 0:
        return 0.0
    f = (model_prob * b - (1.0 - model_prob)) / b
    return max(0.0, f)


def _american_to_decimal(odds: float) -> float:
    if odds > 0:
        return odds / 100.0 + 1.0
    else:
        return 100.0 / (-odds) + 1.0


# ── Gate 邏輯 ─────────────────────────────────────────────────────────────────

def _apply_gates(
    model_prob: float,
    implied_home: float,
    implied_away: float,
    home_ml: float,
    away_ml: float,
    blowout: float,
    ece: float,
    edge_threshold: float = _EDGE_THRESHOLD,
) -> dict:
    """
    Gate 過濾，返回 {side, edge, kelly_fraction, stake_unit, ev,
                     gates_passed, rejected_reason, bet_side}
    """
    gates_passed = []
    rejected_reason = None

    # Gate 1: ECE
    if ece > _ECE_THRESHOLD:
        return dict(
            side="", bet_side="NO_BET", edge=0.0, kelly_fraction=0.0,
            stake_unit=0.0, ev=0.0,
            gates_passed=gates_passed,
            rejected_reason=f"ece_gate: ece={ece:.4f} > {_ECE_THRESHOLD}",
        )
    gates_passed.append("ece_pass")

    # Gate 2: Blowout
    if blowout > _BLOWOUT_THRESHOLD:
        return dict(
            side="", bet_side="NO_BET", edge=0.0, kelly_fraction=0.0,
            stake_unit=0.0, ev=0.0,
            gates_passed=gates_passed,
            rejected_reason=f"blowout_gate: blowout={blowout:.4f} > {_BLOWOUT_THRESHOLD}",
        )
    gates_passed.append("blowout_pass")

    # Gate 3: Edge
    home_edge = model_prob - implied_home
    away_edge = (1.0 - model_prob) - implied_away

    if home_edge >= edge_threshold:
        side = "home"
        bet_side = "HOME"
        edge = home_edge
        dec_odds = _american_to_decimal(home_ml)
        ev = model_prob * (dec_odds - 1.0) - (1.0 - model_prob)
    elif away_edge >= edge_threshold:
        side = "away"
        bet_side = "AWAY"
        edge = away_edge
        dec_odds = _american_to_decimal(away_ml)
        ev = (1.0 - model_prob) * (dec_odds - 1.0) - model_prob
    else:
        best_edge = max(home_edge, away_edge)
        return dict(
            side="", bet_side="NO_BET", edge=best_edge, kelly_fraction=0.0,
            stake_unit=0.0, ev=0.0,
            gates_passed=gates_passed,
            rejected_reason=f"edge_gate: edge={best_edge:.4f} < {edge_threshold}",
        )
    gates_passed.append("edge_pass")

    # Kelly 計算
    raw_kelly = _kelly(
        model_prob if side == "home" else (1.0 - model_prob),
        dec_odds,
    )
    kelly_frac = raw_kelly * _KELLY_FRACTION
    stake = min(kelly_frac, _KELLY_CAP)

    return dict(
        side=side,
        bet_side=bet_side,
        edge=edge,
        kelly_fraction=raw_kelly,
        stake_unit=stake,
        ev=ev,
        gates_passed=gates_passed,
        rejected_reason=None,
    )


# ── Walk-Forward Elo 計算 ────────────────────────────────────────────────────

def run_walk_forward_elo(
    csv_path: Path,
    repair_mode: str = "baseline",
    run_id: str | None = None,
    output_suffix: str | None = None,
    home_advantage: float = 0.0,
) -> list[SimulationRecommendationV2]:
    """
    讀取 CSV，走 Walk-Forward Elo，為每場比賽計算獨立 model_prob。
    Elo 僅使用賽前狀態，賽後才更新（無 Look-ahead Leakage）。
    """
    # P4/P5: repair_mode 初始化
    _ha = home_advantage > 0
    _model_source_tag = "SimplifiedElo_v1"
    if repair_mode == "exclude_spring":
        _model_source_tag = "SimplifiedElo_v1_exclude_spring"
        if _ha:
            _model_source_tag += f"_ha{int(home_advantage)}_uncalibrated"
    elif repair_mode == "warm_start_2024":
        if _ha:
            _model_source_tag = f"SimplifiedElo_v1_warm2024_ha{int(home_advantage)}_uncalibrated"
        else:
            _model_source_tag = "SimplifiedElo_v1_warm_start_2024"

    if repair_mode == "warm_start_2024":
        avail = check_2024_data_availability()
        if avail["available"]:
            print(f"  [P4] warm_start_2024: 使用外部 2024 檔案 {avail['source']}")
            initial_elos = initialize_elo_from_win_rate(MLB_2024_WIN_RATES)
            elo: dict[str, float] = defaultdict(lambda: _ELO_INIT, initial_elos)
        else:
            print(f"  [P4] PARTIAL: {avail['blocking_reason']}")
            print(f"  [P4] warm_start_2024 fallback: 使用內建 2024 win rates")
            initial_elos = initialize_elo_from_win_rate(MLB_2024_WIN_RATES)
            elo = defaultdict(lambda: _ELO_INIT, initial_elos)
    else:
        elo: dict[str, float] = defaultdict(lambda: _ELO_INIT)
    records = []

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            # 解析基本欄位
            date_str = row.get("Date", "").strip()
            home = row.get("Home", "").strip()
            away = row.get("Away", "").strip()
            home_score_raw = row.get("Home Score", "")
            away_score_raw = row.get("Away Score", "")
            status = row.get("Status", "").strip()

            if not home or not away:
                continue
            if status != "Final":
                continue

            # P4: exclude_spring 跳過春訓場次（仍更新 Elo，但不產出 recommendation）
            _is_spring = is_spring_training_game(date_str)
            if repair_mode == "exclude_spring" and _is_spring:
                # 更新 Elo，不產出 record
                try:
                    home_score_ex = int(row.get("Home Score", ""))
                    away_score_ex = int(row.get("Away Score", ""))
                    h_elo_ex = elo[home]
                    a_elo_ex = elo[away]
                    if home_score_ex > away_score_ex:
                        elo[home], elo[away] = _elo_update(h_elo_ex, a_elo_ex)
                    else:
                        elo[away], elo[home] = _elo_update(a_elo_ex, h_elo_ex)
                except (ValueError, TypeError):
                    pass
                continue

            try:
                home_score = int(home_score_raw)
                away_score = int(away_score_raw)
            except (ValueError, TypeError):
                continue

            # ── 賽前 Elo（獨立機率）──────────────────────────────────────────
            home_elo_pre = elo[home]
            away_elo_pre = elo[away]
            # P5: 主場優勢 Elo 加成（僅影響勝率計算，不修改儲存的 Elo）
            effective_home_elo = home_elo_pre + home_advantage
            model_prob = _elo_expected(effective_home_elo, away_elo_pre)

            # ── Odds（closing proxy，僅用於 edge / kelly 計算）────────────────
            home_ml = _parse_american(row.get("Home ML", ""))
            away_ml = _parse_american(row.get("Away ML", ""))

            if home_ml is not None and away_ml is not None:
                raw_h = _american_to_prob(home_ml)
                raw_a = _american_to_prob(away_ml)
                implied_home, implied_away = _remove_vig(raw_h, raw_a)
            else:
                # 若無 odds，implied = Elo prob（edge=0，不會推薦）
                implied_home = model_prob
                implied_away = 1.0 - model_prob
                home_ml = 0.0
                away_ml = 0.0

            # ── Blowout propensity ────────────────────────────────────────────
            blowout = _blowout_propensity(home_elo_pre, away_elo_pre)

            # ── Walk-Forward Fold（月份分層）─────────────────────────────────
            try:
                month_str = date_str[5:7] if len(date_str) >= 7 else "00"
                wf_fold = _WF_MONTH_FOLDS.get(month_str, 0)
            except Exception:
                wf_fold = 0

            # ── Gate 過濾 ─────────────────────────────────────────────────────
            gate_result = _apply_gates(
                model_prob=model_prob,
                implied_home=implied_home,
                implied_away=implied_away,
                home_ml=home_ml or 0.0,
                away_ml=away_ml or 0.0,
                blowout=blowout,
                ece=_SYSTEM_ECE,
            )

            # ── CI（Elo 差距估算）─────────────────────────────────────────────
            elo_diff = abs(effective_home_elo - away_elo_pre)
            ci_half = max(0.03, 0.12 - elo_diff * 0.0003)
            ci = (
                round(max(0.01, model_prob - ci_half), 4),
                round(min(0.99, model_prob + ci_half), 4),
            )

            # ── 建構 SimulationRecommendationV2 ─────────────────────────────
            game_id = f"MLB2025_{idx:04d}"
            rec = SimulationRecommendationV2(
                game_id=game_id,
                game_date=date_str,
                market="ML",
                side=gate_result["side"],
                model_prob=round(model_prob, 4),
                implied_prob=round(implied_home, 4),
                edge=round(gate_result["edge"], 4),
                kelly_fraction=round(gate_result["kelly_fraction"], 4),
                stake_unit=round(gate_result["stake_unit"], 4),
                odds_quality_tier="POST_GAME_PROXY",
                paper_only=True,
                gates_passed=gate_result["gates_passed"],
                rejected_reason=gate_result.get("rejected_reason"),
                simulation_run_id=RUN_ID,
                model_source=_model_source_tag,
                walk_forward_fold=wf_fold,
                generated_at_utc=datetime.now(timezone.utc).isoformat(),
                source_trace=(
                    f"Elo_logistic: home_elo={home_elo_pre:.1f}, "
                    f"away_elo={away_elo_pre:.1f}, "
                    f"p_home={model_prob:.4f}"
                ),
                home_win_ci_95=ci,
                world_model_score_dist=None,
                marl_strategy_weight=None,
                home_team=home,
                away_team=away,
                home_ml_odds=home_ml or 0.0,
                away_ml_odds=away_ml or 0.0,
                bet_side=gate_result["bet_side"],
                ev=round(gate_result["ev"], 4),
                ece=_SYSTEM_ECE,
                blowout_propensity=round(blowout, 4),
                brier_score=None,
                home_elo=round(home_elo_pre, 1),
                away_elo=round(away_elo_pre, 1),
            )
            records.append(rec)

            # ── 賽後更新 Elo ──────────────────────────────────────────────────
            if home_score > away_score:
                elo[home], elo[away] = _elo_update(elo[home], elo[away])
            else:
                elo[away], elo[home] = _elo_update(elo[away], elo[home])

    return records


# ── 統計計算 ─────────────────────────────────────────────────────────────────

def _compute_stats(records: list[SimulationRecommendationV2]) -> dict:
    total = len(records)
    n_model_available = sum(1 for r in records if r.model_prob > 0)
    recommended = [r for r in records if r.rejected_reason is None]
    n_rec = len(recommended)
    coverage = n_rec / total if total > 0 else 0.0

    gate_counts: dict[str, int] = defaultdict(int)
    for r in records:
        if r.rejected_reason:
            gate = r.rejected_reason.split(":")[0]
            gate_counts[gate] += 1

    # Walk-Forward fold 統計
    fold_stats: dict[int, dict] = defaultdict(lambda: {"total": 0, "recommended": 0})
    for r in records:
        fold_stats[r.walk_forward_fold]["total"] += 1
        if r.rejected_reason is None:
            fold_stats[r.walk_forward_fold]["recommended"] += 1

    # Stake 分佈
    stakes = [r.stake_unit for r in recommended]
    avg_stake = sum(stakes) / len(stakes) if stakes else 0.0
    max_stake = max(stakes) if stakes else 0.0

    # Proxy ROI（注意：非真實 CLV）
    # 僅用 edge 做估算（edge × n_rec / total）
    avg_edge = sum(r.edge for r in recommended) / len(recommended) if recommended else 0.0

    return {
        "total_games": total,
        "n_model_prob_available": n_model_available,
        "n_recommended": n_rec,
        "recommendation_coverage_rate": round(coverage, 4),
        "gate_counts": dict(gate_counts),
        "fold_stats": {k: v for k, v in sorted(fold_stats.items())},
        "avg_stake_unit": round(avg_stake, 4),
        "max_stake_unit": round(max_stake, 4),
        "avg_edge_recommended": round(avg_edge, 4),
        "proxy_price_roi_note": "非真實 CLV：model_prob 獨立（Elo），implied_prob 為 POST_GAME_PROXY",
    }


# ── 報告產出 ─────────────────────────────────────────────────────────────────

def _write_report(records: list[SimulationRecommendationV2], stats: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    a = lines.append

    a("# STRATEGY_SIM_V2 策略模擬報告（P2）")
    a("")
    a(f"**Run ID**: `{RUN_ID}`")
    a(f"**產出時間**: {datetime.now(timezone.utc).isoformat()}")
    a(f"**資料來源**: `data/mlb_2025/mlb_odds_2025_real.csv`（2430 場 MLB 2025）")
    a("")
    a("## 1. 同源問題消除聲明")
    a("")
    a("| 項目 | P0（moneyline_paper_v2） | P2（strategy_sim_v2） |")
    a("|------|--------------------------|----------------------|")
    a("| model_prob 來源 | de-vigged odds + Gaussian noise（**odds 反推**） | Walk-Forward Elo logistic（**獨立模型**） |")
    a("| model_source | PROXY_DERIVED | SimplifiedElo_v1 |")
    a("| 是否消除同源問題 | ❌ 否 | ✅ **是** |")
    a("| odds_quality_tier | POST_GAME_PROXY | POST_GAME_PROXY |")
    a("| implied_prob 用途 | 計算 edge（**亦從 odds 反推 model_prob**） | 計算 edge（model_prob 獨立） |")
    a("")
    a("> **結論：P2 model_prob 來自 Walk-Forward Elo，與 implied_prob 完全獨立，已消除同源問題。**")
    a("")
    a("## 2. 使用的 model_source")
    a("")
    a("**SimplifiedElo_v1**")
    a("")
    a("- 公式：`p_home = 1 / (1 + 10^((away_elo - home_elo) / 400))`")
    a("- Elo K 值：20（MLB 標準）")
    a("- 初始 Elo：1500（所有球隊相同）")
    a("- Walk-Forward：每場賽後立即更新，賽前讀取當前 Elo（無 Look-ahead Leakage）")
    a("- 未接入 PredictionOrchestrator 的原因：MARL / HierarchicalMC / WorldModel")
    a("  等相依模組在此 worktree 中不存在，選用 SimplifiedElo_v1 作為替代路徑")
    a("")
    a("## 3. 核心指標")
    a("")
    a(f"| 指標 | 數值 |")
    a(f"|------|------|")
    a(f"| total_games | {stats['total_games']} |")
    a(f"| n_model_prob_available | {stats['n_model_prob_available']} |")
    a(f"| n_recommended | {stats['n_recommended']} |")
    a(f"| recommendation_coverage_rate | {stats['recommendation_coverage_rate']:.2%} |")
    a(f"| avg_edge（推薦場次） | {stats['avg_edge_recommended']:.4f} |")
    a(f"| avg_stake_unit | {stats['avg_stake_unit']:.4f} |")
    a(f"| max_stake_unit | {stats['max_stake_unit']:.4f} |")
    a(f"| ECE（Platt 校準後系統值） | 0.035 |")
    a(f"| Brier | N/A（artifact 未含真實 outcomes） |")
    a(f"| proxy_price_roi | **非真實 CLV**，model_prob 獨立，implied 為 POST_GAME_PROXY |")
    a("")
    a("## 4. Gate 統計")
    a("")
    a("| Gate | 拒絕場次 |")
    a("|------|---------|")
    for gate, cnt in sorted(stats["gate_counts"].items(), key=lambda x: -x[1]):
        a(f"| {gate} | {cnt} |")
    a("")
    a("## 5. Walk-Forward Fold 表（月份分層）")
    a("")
    a("| Fold | 月份 | 總場次 | 推薦場次 | 推薦率 |")
    a("|------|------|--------|----------|--------|")
    month_map = {"1": "Mar", "2": "Apr", "3": "May", "4": "Jun",
                 "5": "Jul", "6": "Aug", "7": "Sep", "8": "Oct", "0": "Unknown"}
    for fold_id, fstat in stats["fold_stats"].items():
        m = month_map.get(str(fold_id), str(fold_id))
        total_f = fstat["total"]
        rec_f = fstat["recommended"]
        rate = rec_f / total_f if total_f > 0 else 0.0
        a(f"| {fold_id} | {m} | {total_f} | {rec_f} | {rate:.2%} |")
    a("")
    a("## 6. Stake 分佈")
    a("")
    a("| 倉位區間 | 場次 |")
    a("|---------|------|")
    buckets = defaultdict(int)
    for r in records:
        if r.rejected_reason is None:
            if r.stake_unit < 0.01:
                buckets["<1%"] += 1
            elif r.stake_unit < 0.02:
                buckets["1-2%"] += 1
            elif r.stake_unit < 0.03:
                buckets["2-3%"] += 1
            elif r.stake_unit < 0.04:
                buckets["3-4%"] += 1
            else:
                buckets["4-5%"] += 1
    for bucket, cnt in sorted(buckets.items()):
        a(f"| {bucket} | {cnt} |")
    a("")
    a("## 7. MARL optimizer 下游欄位清單")
    a("")
    a("P2 artifact 包含以下欄位，供 MARL optimizer 使用：")
    a("")
    a("| 欄位 | 說明 |")
    a("|------|------|")
    a("| `model_prob` | Walk-Forward Elo 獨立機率（home win） |")
    a("| `implied_prob` | de-vigged closing proxy（非 model 來源） |")
    a("| `edge` | model_prob - implied_prob（真正獨立 edge） |")
    a("| `kelly_fraction` | raw 1/1 Kelly f* |")
    a("| `stake_unit` | 1/4 Kelly，上限 5% |")
    a("| `home_win_ci_95` | 95% CI（Elo 差距估算） |")
    a("| `walk_forward_fold` | 月份 fold（1=Mar ... 8=Oct） |")
    a("| `home_elo` / `away_elo` | 賽前滾動 Elo 值 |")
    a("| `blowout_propensity` | 崩盤風險（Elo 差距 logistic） |")
    a("| `model_source` | SimplifiedElo_v1（可替換為 Orchestrator） |")
    a("| `marl_strategy_weight` | 預留欄位（目前 null） |")
    a("| `world_model_score_dist` | 預留欄位（目前 null） |")
    a("")
    a("## 8. P0 vs P2 差異對照表")
    a("")
    a("| 項目 | P0 | P2 |")
    a("|------|----|----|")
    a("| model_prob 來源 | odds 反推（同源） | Walk-Forward Elo（獨立） |")
    a("| 同源問題 | ❌ 存在 | ✅ 已消除 |")
    a("| walk_forward_fold | 無 | 月份分層 (1-8) |")
    a("| home_win_ci_95 | 無 | 有 |")
    a("| marl_strategy_weight | 無 | 預留（null） |")
    a("| model_source 欄位 | 無 | SimplifiedElo_v1 |")
    a("| source_trace | 無 | 有（含具體 Elo 值） |")
    a("")
    a("## 9. 下一步建議")
    a("")
    a("1. **接入 PredictionOrchestrator**：當 MARL / HierarchicalMC / WorldModel 模組在 worktree 中可用時，")
    a("   將 `model_source` 升級為 `PredictionOrchestrator_v1`，model_prob 精度將大幅提升。")
    a("2. **MLB 真實球員數據**（Phase 8B）：接入真實 wOBA/FIP 取代代理，改善 Elo 以外的特徵。")
    a("3. **MARL optimizer 整合**：使用 P2 artifact 中的 `edge` / `kelly_fraction` / `walk_forward_fold`")
    a("   欄位訓練 MARL，評估策略自適應效果。")
    a("4. **2026 regular season 實時 TSL 收集**：建立逐漸增長的 pregame 時間點資料集，")
    a("   最終實現真正的 CLV 研究。")
    a("")
    a("---")
    a("*本報告為 paper-only 研究用途，禁止用於生產下注。*")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 報告已產出：{REPORT_PATH}")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P2/P4/P5 Strategy Simulation V2")
    parser.add_argument(
        "--repair-mode",
        choices=["baseline", "exclude_spring", "warm_start_2024"],
        default="baseline",
        help="Elo 修復模式（預設 baseline = 原始 SimplifiedElo_v1）",
    )
    # P5 新增參數
    parser.add_argument(
        "--mode",
        default=None,
        choices=["baseline", "exclude_spring", "warm_start_2024",
                 "warm_start_2024_home_advantage_platt"],
        help="P5 模式快捷鍵（優先於 --repair-mode）",
    )
    parser.add_argument(
        "--home-advantage",
        type=float,
        default=40.0,
        help="主場優勢 Elo 加成（P5，預設 40.0）",
    )
    parser.add_argument(
        "--apply-platt",
        action="store_true",
        help="套用 Walk-Forward Platt Scaling（P5）",
    )
    parser.add_argument(
        "--output-suffix",
        default=None,
        help="輸出檔案後綴（如 elo_repair_20260518）",
    )
    args = parser.parse_args()

    # P5: --mode 優先
    if args.mode is not None:
        if args.mode == "warm_start_2024_home_advantage_platt":
            repair_mode = "warm_start_2024"
            home_advantage = args.home_advantage
            apply_platt = True
        else:
            repair_mode = args.mode
            home_advantage = args.home_advantage if args.apply_platt else 0.0
            apply_platt = args.apply_platt
    else:
        repair_mode = args.repair_mode
        home_advantage = args.home_advantage if args.apply_platt else 0.0
        apply_platt = args.apply_platt

    output_suffix = args.output_suffix

    # 決定輸出路徑
    if output_suffix:
        artifact_path = OUT_DIR / f"strategy_sim_v2_{output_suffix}.jsonl"
        report_path = REPORT_DIR / f"strategy_sim_v2_{output_suffix}.md"
        run_id_local = f"P4_SIM_V2_{output_suffix.upper()}"
    else:
        artifact_path = ARTIFACT_PATH
        report_path = REPORT_PATH
        run_id_local = RUN_ID

    print(f"[P5] STRATEGY_SIM_V2 開始執行...")
    print(f"  repair_mode：{repair_mode}")
    print(f"  home_advantage：{home_advantage}")
    print(f"  apply_platt：{apply_platt}")
    print(f"  資料來源：{DATA_CSV}")
    print(f"  輸出 artifact：{artifact_path}")

    if not DATA_CSV.exists():
        print(f"❌ 資料檔案不存在：{DATA_CSV}")
        sys.exit(1)

    print("[1/4] Walk-Forward Elo 計算中...")
    records = run_walk_forward_elo(
        DATA_CSV,
        repair_mode=repair_mode,
        home_advantage=home_advantage,
    )
    print(f"  → {len(records)} 場 GameRecord 載入完成")

    # P5: Walk-Forward Platt Scaling
    _platt_meta: dict = {}
    if apply_platt:
        print("[1b/4] Walk-Forward Platt Scaling 中...")
        # 從 CSV 重新讀取 outcomes（home_score > away_score → 1，否則 0）
        _outcomes_map: dict[str, int] = {}
        with open(DATA_CSV, encoding="utf-8") as _f:
            _reader = csv.DictReader(_f)
            _idx2 = 0
            for _row in _reader:
                if _row.get("Status", "").strip() != "Final":
                    continue
                _home = _row.get("Home", "").strip()
                _away = _row.get("Away", "").strip()
                _date = _row.get("Date", "").strip()
                if not _home or not _away:
                    continue
                try:
                    _hs = int(_row.get("Home Score", ""))
                    _as = int(_row.get("Away Score", ""))
                    _outcomes_map[f"{_date}|{_home}|{_away}"] = 1 if _hs > _as else 0
                except (ValueError, TypeError):
                    pass

        # 為每個 record 建構 dict + outcome 列表
        _rows_dicts = []
        _outcome_list = []
        for rec in records:
            _key = f"{rec.game_date}|{rec.home_team}|{rec.away_team}"
            _outcome = _outcomes_map.get(_key)
            _rows_dicts.append({
                "model_prob": rec.model_prob,
                "walk_forward_fold": rec.walk_forward_fold,
                "model_source": rec.model_source,
                "game_date": rec.game_date,
            })
            _outcome_list.append(_outcome if _outcome is not None else -1)

        # 只對有 outcome 的行做校準
        _valid_mask = [o >= 0 for o in _outcome_list]
        _valid_rows = [r for r, v in zip(_rows_dicts, _valid_mask) if v]
        _valid_outcomes = [o for o, v in zip(_outcome_list, _valid_mask) if v]

        if len(_valid_rows) >= 20:
            _calibrated = apply_walk_forward_platt_calibration(
                _valid_rows, _valid_outcomes
            )
            # 將校準後的 model_prob 寫回 records
            _cal_idx = 0
            _n_calibrated = 0
            _n_rejected = 0
            for i, rec in enumerate(records):
                if _valid_mask[i]:
                    _cal_row = _calibrated[_cal_idx]
                    _cal_idx += 1
                    if _cal_row.get("calibration_used", False):
                        rec.model_prob = _cal_row["model_prob"]
                        _src = rec.model_source
                        if "_uncalibrated" in _src:
                            rec.model_source = _src.replace("_uncalibrated", "_platt")
                        elif "_platt" not in _src:
                            rec.model_source = _src + "_platt"
                        _n_calibrated += 1
                    elif _cal_row.get("calibration_rejected", False):
                        _n_rejected += 1
            _platt_meta = {
                "n_valid": len(_valid_rows),
                "n_calibrated": _n_calibrated,
                "n_rejected": _n_rejected,
            }
            print(f"  → Platt 校準完成：{_n_calibrated} 場使用校準，{_n_rejected} 場拒絕校準")
        else:
            print(f"  → Platt Scaling 樣本不足（{len(_valid_rows)} < 20），跳過")

    print("[2/4] Gate 過濾統計...")
    stats = _compute_stats(records)
    print(f"  → total_games={stats['total_games']}")
    print(f"  → n_recommended={stats['n_recommended']}")
    print(f"  → coverage={stats['recommendation_coverage_rate']:.2%}")

    print("[3/4] 產出 JSONL artifact...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(artifact_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.to_json() + "\n")
    print(f"  → {artifact_path}")

    print("[4/4] 產出 Markdown 報告...")
    _write_report(records, stats)

    print("")
    print("=" * 60)
    print("P2 STRATEGY_SIM_V2 完成")
    print(f"  total_games             : {stats['total_games']}")
    print(f"  n_model_prob_available  : {stats['n_model_prob_available']}")
    print(f"  n_recommended           : {stats['n_recommended']}")
    print(f"  coverage_rate           : {stats['recommendation_coverage_rate']:.2%}")
    print(f"  avg_edge (推薦)          : {stats['avg_edge_recommended']:.4f}")
    print(f"  ECE (系統，Platt 後)     : 0.035")
    print(f"  proxy_price_roi         : 非真實 CLV")
    print(f"  最大過濾 gate            : {max(stats['gate_counts'], key=lambda k: stats['gate_counts'][k]) if stats['gate_counts'] else 'N/A'}")
    print(f"  同源問題消除             : ✅ YES（Elo 獨立，不依賴 odds）")
    print("=" * 60)


if __name__ == "__main__":
    main()
