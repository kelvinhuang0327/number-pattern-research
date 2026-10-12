"""
P6 MARL Strategy Simulation v2
================================
8 策略比較分析，基於 P5 artifact strategy_sim_v2_ha40_platt_20260518.jsonl。

硬性約束：
- paper_only 永遠 True
- proxy ROI 非真實 CLV
- 不呼叫 live odds API
- 不 merge PR
- 不偽造任何指標
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# 確保可以 import wbc_backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.recommendation.marl_strategy_adapter import (
    p5_row_to_marl_record,
    aggregate_strategy_stats,
    calculate_risk_adjusted_score,
)

# ── 輸入 / 輸出路徑 ────────────────────────────────────────────────────────────

WORKTREE = Path(__file__).resolve().parent.parent
_DEFAULT_ARTIFACT = WORKTREE / "data/paper_recommendations/strategy_sim_v2_ha40_platt_20260518.jsonl"
_WITH_OUTCOMES_ARTIFACT = WORKTREE / "data/paper_recommendations/strategy_sim_v2_ha40_platt_with_outcomes_20260518.jsonl"
ARTIFACT_PATH = _DEFAULT_ARTIFACT  # 向下相容
OUTPUT_PATH = WORKTREE / "data/paper_recommendations/p6_marl_strategy_simulation_20260518.json"

# ── 8 個策略定義 ───────────────────────────────────────────────────────────────

STRATEGIES = [
    {
        "name": "fixed_edge_1pct",
        "edge_threshold": 0.01,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "fixed_edge_3pct",
        "edge_threshold": 0.03,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "fixed_edge_5pct",
        "edge_threshold": 0.05,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "fractional_kelly_25",
        "edge_threshold": 0.01,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "fractional_kelly_50",
        "edge_threshold": 0.01,
        "kelly_fraction_multiplier": 0.50,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "fractional_kelly_100",
        "edge_threshold": 0.01,
        "kelly_fraction_multiplier": 1.0,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "conservative_drawdown",
        "edge_threshold": 0.03,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.3,
        "calibration_penalty_weight": 0.05,
    },
    {
        "name": "calibration_penalty",
        "edge_threshold": 0.03,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.1,
    },
]


def load_p5_rows(artifact_path: Path = None) -> list[dict]:
    path = artifact_path or ARTIFACT_PATH
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"[P6/P7] 載入 artifact：{len(rows)} rows from {path.name}")
    return rows


def run_strategy(rows: list[dict], strategy: dict) -> dict:
    policy = {
        "edge_threshold": strategy["edge_threshold"],
        "kelly_fraction_multiplier": strategy["kelly_fraction_multiplier"],
        "drawdown_penalty_weight": strategy.get("drawdown_penalty_weight", 0.1),
        "calibration_penalty_weight": strategy.get("calibration_penalty_weight", 0.05),
    }

    records = []
    for row in rows:
        rec = p5_row_to_marl_record(row, policy)
        if rec is not None:
            records.append(rec)

    stats = aggregate_strategy_stats(records, strategy["name"])
    stats["policy"] = policy

    # ── EV-proxy 分析（actual_home_win 全缺失時替代指標）────────────────────
    edge_thresh = strategy["edge_threshold"]
    kelly_mult = strategy["kelly_fraction_multiplier"]
    bet_rows = [r for r in rows if
                r.get("edge", 0.0) >= edge_thresh and
                r.get("bet_side", "NO_BET") != "NO_BET"]

    total_ev = sum(r.get("ev", 0.0) * r.get("stake_unit", 0.0) * kelly_mult / 0.25
                   for r in bet_rows)
    total_staked_ev = sum(r.get("stake_unit", 0.0) * kelly_mult / 0.25
                          for r in bet_rows)
    ev_roi = total_ev / max(total_staked_ev, 1e-8)
    avg_edge = sum(r.get("edge", 0.0) for r in bet_rows) / max(len(bet_rows), 1)
    avg_ev = sum(r.get("ev", 0.0) for r in bet_rows) / max(len(bet_rows), 1)
    avg_stake = sum(r.get("stake_unit", 0.0) for r in bet_rows) / max(len(bet_rows), 1)

    # 模型機率分布
    model_probs = [r.get("model_prob", 0.5) for r in bet_rows]
    avg_model_prob = sum(model_probs) / max(len(model_probs), 1)

    # fold-level EV 分析
    fold_ev: dict = {}
    for r in bet_rows:
        fold = r.get("walk_forward_fold", 0)
        if fold not in fold_ev:
            fold_ev[fold] = {"bets": 0, "total_ev": 0.0, "total_staked": 0.0, "total_edge": 0.0}
        fold_ev[fold]["bets"] += 1
        fold_ev[fold]["total_ev"] += r.get("ev", 0.0) * r.get("stake_unit", 0.0) * kelly_mult / 0.25
        fold_ev[fold]["total_staked"] += r.get("stake_unit", 0.0) * kelly_mult / 0.25
        fold_ev[fold]["total_edge"] += r.get("edge", 0.0)

    fold_ev_stats = {}
    for fold, fv in sorted(fold_ev.items()):
        fold_ev_stats[f"fold_{fold}"] = {
            "bets": fv["bets"],
            "ev_roi": round(fv["total_ev"] / max(fv["total_staked"], 1e-8), 4),
            "avg_edge": round(fv["total_edge"] / max(fv["bets"], 1), 4),
        }

    stats["ev_analysis"] = {
        "note": "actual_home_win=None 全部缺失，以 EV-proxy（model_prob × stake）替代 PnL 分析",
        "ev_proxy_roi": round(ev_roi, 6),
        "total_ev": round(total_ev, 6),
        "total_staked_ev": round(total_staked_ev, 6),
        "average_edge": round(avg_edge, 6),
        "average_ev": round(avg_ev, 6),
        "average_stake": round(avg_stake, 6),
        "average_model_prob": round(avg_model_prob, 4),
        "fold_ev_level": fold_ev_stats,
    }

    # 更新 stats 核心欄位為 EV-proxy 版本
    stats["proxy_roi"] = round(ev_roi, 6)
    stats["average_edge"] = round(avg_edge, 6)
    stats["average_stake"] = round(avg_stake, 6)
    # risk_adjusted_score 基於 EV-proxy ROI（無 actual 時 drawdown=0, vol=0）
    stats["risk_adjusted_score"] = round(ev_roi * 0.6, 6)
    stats["ev_proxy_note"] = "ROI/risk_adjusted 均為 EV-proxy，非實際損益。actual_home_win 全部缺失。"

    return stats


def _parse_args():
    parser = argparse.ArgumentParser(description="P6/P7 MARL Strategy Simulation v2")
    parser.add_argument(
        "--input",
        default=None,
        help="artifact 路徑（預設 ev_proxy: ha40_platt; true_outcome: with_outcomes）",
    )
    parser.add_argument(
        "--reward-source",
        choices=["ev_proxy", "true_outcome"],
        default="ev_proxy",
        dest="reward_source",
        help="ev_proxy=使用 EV 代理; true_outcome=使用實際比賽結果",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="輸出路徑（預設自動依 reward-source 決定）",
    )
    return parser.parse_args()


def _compute_true_roi(records, strategy: dict) -> dict:
    """使用 true_profit_loss 計算真實 ROI"""
    kelly_mult = strategy["kelly_fraction_multiplier"]
    bet_records = [r for r in records if r.action.bet and not r.invalid_for_reward]
    true_pnl_records = [r for r in bet_records if r.true_profit_loss is not None]

    total_true_pnl = sum(r.true_profit_loss for r in true_pnl_records)
    total_staked = sum(
        r.state.stake_unit * kelly_mult / 0.25
        for r in true_pnl_records
    )
    true_roi = total_true_pnl / max(total_staked, 1e-8)
    wins = [r for r in true_pnl_records if (r.true_profit_loss or 0.0) > 0]
    hit_rate = len(wins) / max(len(true_pnl_records), 1)

    # fold-level
    fold_stats: dict = {}
    for rec in true_pnl_records:
        fold = rec.state.walk_forward_fold
        if fold not in fold_stats:
            fold_stats[fold] = {"bets": 0, "pnl": 0.0, "staked": 0.0, "wins": 0}
        fold_stats[fold]["bets"] += 1
        fold_stats[fold]["pnl"] += rec.true_profit_loss
        fold_stats[fold]["staked"] += rec.state.stake_unit * kelly_mult / 0.25
        if rec.true_profit_loss > 0:
            fold_stats[fold]["wins"] += 1

    fold_level = {}
    for fold, fs in sorted(fold_stats.items()):
        froi = fs["pnl"] / max(fs["staked"], 1e-8)
        fhr = fs["wins"] / max(fs["bets"], 1)
        fold_level[f"fold_{fold}"] = {
            "bets": fs["bets"],
            "hit_rate": round(fhr, 4),
            "true_roi": round(froi, 4),
            "true_pnl": round(fs["pnl"], 4),
        }

    return {
        "true_roi": round(true_roi, 6),
        "total_true_pnl": round(total_true_pnl, 6),
        "total_staked": round(total_staked, 6),
        "true_hit_rate": round(hit_rate, 4),
        "true_outcome_bets": len(true_pnl_records),
        "fold_level_true": fold_level,
        "reward_source": "TRUE_OUTCOME",
    }


def main():
    args = _parse_args()
    reward_source = args.reward_source

    # 決定 artifact 路徑
    if args.input:
        artifact_path = Path(args.input)
        if not artifact_path.is_absolute():
            artifact_path = WORKTREE / args.input
    elif reward_source == "true_outcome":
        artifact_path = _WITH_OUTCOMES_ARTIFACT
    else:
        artifact_path = _DEFAULT_ARTIFACT

    # 決定輸出路徑
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = WORKTREE / args.output
    elif reward_source == "true_outcome":
        output_path = WORKTREE / "data/paper_recommendations/p7_true_pnl_marl_strategy_simulation_20260518.json"
    else:
        output_path = OUTPUT_PATH

    print(f"[P6/P7] MARL Strategy Simulation v2 開始（reward_source={reward_source}）")
    rows = load_p5_rows(artifact_path)

    results = []
    for strategy in STRATEGIES:
        print(f"  → 策略: {strategy['name']} (edge>={strategy['edge_threshold']}, kelly={strategy['kelly_fraction_multiplier']})")
        stats = run_strategy(rows, strategy)

        # P7 true ROI
        if reward_source == "true_outcome":
            policy = {
                "edge_threshold": strategy["edge_threshold"],
                "kelly_fraction_multiplier": strategy["kelly_fraction_multiplier"],
                "drawdown_penalty_weight": strategy.get("drawdown_penalty_weight", 0.1),
                "calibration_penalty_weight": strategy.get("calibration_penalty_weight", 0.05),
            }
            records = [r for r in [p5_row_to_marl_record(row, policy) for row in rows] if r is not None]
            true_roi_stats = _compute_true_roi(records, strategy)
            stats["true_pnl_analysis"] = true_roi_stats
            # 顯示 true ROI
            print(f"     bets={stats['total_bets']}, true_roi={true_roi_stats['true_roi']:.4f}, "
                  f"true_hit_rate={true_roi_stats['true_hit_rate']:.3f}")
        else:
            print(f"     bets={stats['total_bets']}, coverage={stats['coverage']:.1%}, "
                  f"proxy_roi={stats['proxy_roi']:.4f}, hit_rate={stats['hit_rate']:.3f}, "
                  f"risk_adj={stats['risk_adjusted_score']:.4f}")

        results.append(stats)

    # 排序：by proxy_roi, by risk_adjusted_score
    best_by_roi = max(results, key=lambda x: x["proxy_roi"])
    best_by_risk_adj = max(results, key=lambda x: x["risk_adjusted_score"])
    conservative = next(
        (r for r in results if r["strategy_name"] == "conservative_drawdown"),
        results[0]
    )

    run_id = "P7_TRUE_PNL_MARL_STRATEGY_SIM_20260518" if reward_source == "true_outcome" else "P6_MARL_STRATEGY_SIM_20260518"

    output = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifact": str(artifact_path.name),
        "reward_source": reward_source,
        "total_rows": len(rows),
        "n_strategies": len(STRATEGIES),
        "proxy_roi_disclaimer": "All ROI figures are proxy estimates — NOT real CLV. Based on POST_GAME_PROXY odds only.",
        "paper_only": True,
        "strategies": results,
        "summary": {
            "best_by_proxy_roi": {
                "name": best_by_roi["strategy_name"],
                "proxy_roi": best_by_roi["proxy_roi"],
                "total_bets": best_by_roi["total_bets"],
                "risk_adjusted_score": best_by_roi["risk_adjusted_score"],
            },
            "best_by_risk_adjusted": {
                "name": best_by_risk_adj["strategy_name"],
                "proxy_roi": best_by_risk_adj["proxy_roi"],
                "total_bets": best_by_risk_adj["total_bets"],
                "risk_adjusted_score": best_by_risk_adj["risk_adjusted_score"],
            },
            "conservative_candidate": {
                "name": conservative["strategy_name"],
                "proxy_roi": conservative["proxy_roi"],
                "total_bets": conservative["total_bets"],
                "max_drawdown": conservative["max_drawdown"],
            },
        },
    }

    # 若 true_outcome 模式，加入真實 ROI 最佳策略
    if reward_source == "true_outcome":
        true_rois = [
            (r["strategy_name"], r.get("true_pnl_analysis", {}).get("true_roi", 0.0))
            for r in results
        ]
        best_true = max(true_rois, key=lambda x: x[1])
        output["summary"]["best_by_true_roi"] = {
            "name": best_true[0],
            "true_roi": best_true[1],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[P6/P7] 輸出：{output_path}")
    print(f"[P6/P7] 最佳 proxy ROI：{best_by_roi['strategy_name']} ({best_by_roi['proxy_roi']:.4f})")
    print(f"[P6/P7] 最佳風險調整：{best_by_risk_adj['strategy_name']} ({best_by_risk_adj['risk_adjusted_score']:.4f})")
    print("[P6/P7] 完成 ✓")
    return output


if __name__ == "__main__":
    main()
