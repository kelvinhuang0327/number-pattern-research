"""
run_moneyline_paper_v2.py — P0_MONEYLINE_PAPER_V2_PROXY_ONLY

執行流程：
1. 讀取 data/mlb_2025/mlb_odds_2025_real.csv（2430 場 MLB 2025）
2. 使用 proxy 方式生成 p_home_win（基於 ML odds + Elo-like 雜訊）
   ※ 無真實 walk-forward 預測 CSV，使用 odds-derived proxy 並標記
3. 套用 MoneylinePaperRecommenderV2 gate 邏輯
4. 產出 report/moneyline_paper_v2_20260518.md
5. 產出 data/paper_recommendations/moneyline_paper_v2_20260518.jsonl

[PROXY NOTE] blowout_propensity 及 ece 均為模擬值，非真實模型輸出。
             odds 均標記為 POST_GAME_PROXY（賽後單次抓取）。
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 加入專案根目錄到 path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.moneyline_paper_v2 import (
    MoneylinePaperRecommenderV2,
    _american_to_implied_prob,
    _american_to_decimal,
)

# ── 路徑設定 ────────────────────────────────────────────────────────────────
DATA_CSV = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
OUT_DIR = ROOT / "data" / "paper_recommendations"
REPORT_DIR = ROOT / "report"
RUN_DATE = "20260518"
ARTIFACT_PATH = OUT_DIR / f"moneyline_paper_v2_{RUN_DATE}.jsonl"
REPORT_PATH = REPORT_DIR / f"moneyline_paper_v2_{RUN_DATE}.md"

random.seed(42)

# ── Proxy ECE（模擬值，代表 Platt calibration 後的系統 ECE）───────────────
# 根據 MEMORY.md：ECE = 0.035（Platt calibration 後）
_PROXY_ECE = 0.035

# ── 各隊「強隊」Elo proxy（簡化版，用於生成 p_home_win）────────────────────
# 這是 PROXY，非真實 Elo，僅用於合理化機率分佈
_STRONG_TEAMS = {
    "Los Angeles Dodgers", "Atlanta Braves", "New York Yankees",
    "Houston Astros", "Philadelphia Phillies", "Baltimore Orioles",
    "Texas Rangers", "Minnesota Twins",
}


def parse_american_odds(s: str) -> float | None:
    """解析美式盤口字串，如 '-150', '+130'。"""
    try:
        s = s.strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def generate_proxy_p_home(home_ml: float, away_ml: float, home_team: str = "") -> float:
    """
    使用 ML odds 推導 proxy 勝率（去 vig 版）。

    方法：
    1. 計算雙方隱含機率
    2. 正規化（移除 vig）
    3. 加入小量隨機噪聲（±2%）模擬 walk-forward 模型輸出
    """
    home_implied = _american_to_implied_prob(home_ml)
    away_implied = _american_to_implied_prob(away_ml)
    total_implied = home_implied + away_implied
    # 去 vig
    p_home = home_implied / total_implied
    # 加入小量噪聲
    noise = random.gauss(0, 0.02)
    p_home_noisy = max(0.10, min(0.90, p_home + noise))
    return p_home_noisy


def generate_proxy_blowout(home_ml: float, away_ml: float, home_team: str = "") -> float:
    """
    Proxy blowout propensity（基於盤口懸殊度）。

    強弱差距越大 → blowout_propensity 越高。
    """
    home_implied = _american_to_implied_prob(home_ml)
    away_implied = _american_to_implied_prob(away_ml)
    total = home_implied + away_implied
    p_fav = max(home_implied, away_implied) / total
    # p_fav in [0.5, 0.9]，映射到 blowout [0.1, 0.7]
    bp = 0.1 + (p_fav - 0.5) * 1.5
    noise = random.gauss(0, 0.03)
    return max(0.0, min(1.0, bp + noise))


def load_csv_games(path: Path) -> list[dict]:
    """讀取 MLB 2025 odds CSV，返回 dict list。"""
    games = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            games.append({
                "game_id": f"MLB2025_{i+1:04d}",
                "date": row.get("Date", ""),
                "home_team": row.get("Home", ""),
                "away_team": row.get("Away", ""),
                "home_score": row.get("Home Score", ""),
                "away_score": row.get("Away Score", ""),
                "status": row.get("Status", ""),
                "home_ml_raw": row.get("Home ML", ""),
                "away_ml_raw": row.get("Away ML", ""),
            })
    return games


def run_recommendations() -> tuple[list[dict], dict]:
    """主流程：讀取資料、生成推薦、返回結果與統計。"""
    recommender = MoneylinePaperRecommenderV2(
        edge_threshold=0.01,
        kelly_cap=0.05,
        ece_threshold=0.12,
        blowout_threshold=0.65,
    )

    games = load_csv_games(DATA_CSV)
    total_games = len(games)

    results: list[dict] = []
    gate_stats: dict[str, int] = defaultdict(int)
    stake_buckets: dict[str, int] = defaultdict(int)
    pnl_proxy = 0.0  # proxy ROI（無真實 CLV）
    n_recommended = 0

    for game in games:
        home_ml_raw = game["home_ml_raw"]
        away_ml_raw = game["away_ml_raw"]

        home_ml = parse_american_odds(home_ml_raw)
        away_ml = parse_american_odds(away_ml_raw)

        # 若缺少 odds 則跳過
        if home_ml is None or away_ml is None:
            gate_stats["skip_missing_odds"] += 1
            continue

        # 生成 proxy 機率
        p_home = generate_proxy_p_home(home_ml, away_ml, game["home_team"])
        p_away = 1.0 - p_home
        blowout = generate_proxy_blowout(home_ml, away_ml, game["home_team"])
        ece = _PROXY_ECE  # 系統級 ECE proxy

        row = recommender.recommend(
            game_id=game["game_id"],
            p_home_win=p_home,
            p_away_win=p_away,
            home_ml_odds=home_ml,
            away_ml_odds=away_ml,
            blowout_propensity=blowout,
            ece=ece,
            home_team=game["home_team"],
            away_team=game["away_team"],
            game_date=game["date"],
        )

        row_dict = row.to_dict()
        results.append(row_dict)

        if row.rejected:
            gate_stats[row.reject_reason.split(":")[0]] += 1
        else:
            n_recommended += 1
            gate_stats["recommended"] += 1

            # Stake bucket
            s = row.stake_fraction
            if s <= 0.01:
                stake_buckets["0-1%"] += 1
            elif s <= 0.02:
                stake_buckets["1-2%"] += 1
            elif s <= 0.03:
                stake_buckets["2-3%"] += 1
            elif s <= 0.04:
                stake_buckets["3-4%"] += 1
            else:
                stake_buckets["4-5%"] += 1

            # Proxy P&L（用真實結果驗證若有）
            home_score = game.get("home_score", "")
            away_score = game.get("away_score", "")
            try:
                hs = int(home_score)
                as_ = int(away_score)
                home_won = hs > as_
                if row.bet_side == "HOME":
                    if home_won:
                        decimal = _american_to_decimal(home_ml)
                        pnl_proxy += row.stake_fraction * (decimal - 1.0)
                    else:
                        pnl_proxy -= row.stake_fraction
                elif row.bet_side == "AWAY":
                    if not home_won:
                        decimal = _american_to_decimal(away_ml)
                        pnl_proxy += row.stake_fraction * (decimal - 1.0)
                    else:
                        pnl_proxy -= row.stake_fraction
            except (ValueError, TypeError):
                pass  # 無法計算 proxy ROI

    coverage_rate = n_recommended / total_games if total_games > 0 else 0.0
    total_staked = sum(
        r["stake_fraction"] for r in results if not r["rejected"]
    )
    proxy_roi = pnl_proxy / total_staked if total_staked > 0 else 0.0

    stats = {
        "total_games": total_games,
        "n_recommended": n_recommended,
        "coverage_rate": coverage_rate,
        "proxy_roi": proxy_roi,
        "total_staked": total_staked,
        "gate_stats": dict(gate_stats),
        "stake_buckets": dict(stake_buckets),
        "proxy_ece": _PROXY_ECE,
    }

    return results, stats


def write_artifact(results: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[artifact] 已寫入 {ARTIFACT_PATH}（{len(results)} rows）")


def write_report(results: list[dict], stats: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    total = stats["total_games"]
    n_rec = stats["n_recommended"]
    coverage = stats["coverage_rate"] * 100
    proxy_roi = stats["proxy_roi"] * 100
    ece = stats["proxy_ece"]
    gate_stats = stats["gate_stats"]
    stake_buckets = stats["stake_buckets"]

    # 找最大過濾 gate
    reject_gates = {k: v for k, v in gate_stats.items() if k != "recommended"}
    max_gate = max(reject_gates, key=reject_gates.get) if reject_gates else "N/A"
    max_gate_count = reject_gates.get(max_gate, 0)

    lines = [
        f"# MLB 2025 Moneyline Paper V2 推薦報告 — PROXY_ONLY",
        f"",
        f"> **執行日期**：2026-05-18  |  **Classification**：P0_MONEYLINE_PAPER_V2_PROXY_ONLY",
        f"> **警告**：所有 odds 均為 POST_GAME_PROXY（2026-03-18/19 單次賽後抓取），",
        f"> 非真實賽前開盤。blowout_propensity / p_home_win 均為 proxy 模擬值，",
        f"> **ROI 數字不代表真實可獲利性**，僅供管道驗證使用。",
        f"",
        f"---",
        f"",
        f"## 一、總覽統計",
        f"",
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| 總場數 | {total} |",
        f"| 推薦場數 | {n_rec} |",
        f"| 覆蓋率 | {coverage:.2f}% |",
        f"| Proxy-Only ROI | **{proxy_roi:+.2f}%** ⚠️ 非真實 CLV |",
        f"| 系統 ECE（Platt proxy） | {ece:.4f} |",
        f"| Brier 驗證 | N/A（未整合 walk-forward 預測） |",
        f"",
        f"---",
        f"",
        f"## 二、Gate 過濾統計",
        f"",
        f"| Gate | 過濾場數 | 說明 |",
        f"|------|----------|------|",
    ]

    gate_desc = {
        "ece_gate": "ECE > 0.12 拒絕",
        "blowout_gate": "Blowout propensity > 0.65 拒絕",
        "edge_gate": "Edge < 1% 拒絕",
        "skip_missing_odds": "缺少 odds 資料跳過",
        "recommended": "通過所有 gate，已推薦",
    }
    sorted_gates = sorted(gate_stats.items(), key=lambda x: -x[1])
    for g, cnt in sorted_gates:
        desc = gate_desc.get(g, g)
        lines.append(f"| {g} | {cnt} | {desc} |")

    lines += [
        f"",
        f"**最大過濾 Gate**：`{max_gate}`（{max_gate_count} 場）",
        f"",
        f"---",
        f"",
        f"## 三、Stake 分佈",
        f"",
        f"| 倉位區間 | 場數 |",
        f"|----------|------|",
    ]

    for bucket in ["0-1%", "1-2%", "2-3%", "3-4%", "4-5%"]:
        cnt = stake_buckets.get(bucket, 0)
        lines.append(f"| {bucket} | {cnt} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 四、Brier / ECE 驗證",
        f"",
        f"| 指標 | 數值 | Gate 門檻 | 狀態 |",
        f"|------|------|-----------|------|",
        f"| ECE（Platt proxy） | {ece:.4f} | 0.12 | ✅ PASS |",
        f"| Brier Score | N/A | 0.285 | ⚠️ 需 walk-forward 整合 |",
        f"",
        f"> ECE 使用 MEMORY.md 記錄之系統級 ECE=0.035（Platt calibration 後）",
        f"> 作為全場共享 proxy 值，非逐場計算。",
        f"",
        f"---",
        f"",
        f"## 五、Proxy-Only ROI 說明",
        f"",
        f"```",
        f"ROI 計算方式：",
        f"  - p_home_win = de-vigged odds + Gaussian noise(0, 0.02)",
        f"  - blowout_propensity = 由賠率懸殊度推算 + noise(0, 0.03)",
        f"  - odds = POST_GAME_PROXY（賽後單次快照）",
        f"  - 若實際比分可取得：計算 stake * (decimal-1) 或 -stake",
        f"",
        f"  此 ROI 不代表真實可獲利性，原因：",
        f"  1. odds 為賽後代理，非賽前開盤",
        f"  2. p_home_win 為 odds-derived proxy，非獨立模型預測",
        f"  3. 無真正 CLV（Closing Line Value）驗證",
        f"```",
        f"",
        f"---",
        f"",
        f"## 六、P4 Odds 解鎖後需替換的 3 個位置",
        f"",
        f"解鎖真實 pregame odds 後，以下 3 個位置必須替換：",
        f"",
        f"| # | 位置 | 檔案 | 目前值 | 替換為 |",
        f"|---|------|------|--------|--------|",
        f"| 1 | `odds_quality_tier` 欄位預設值 | `wbc_backend/recommendation/moneyline_paper_v2.py` L34 | `POST_GAME_PROXY` | `PREGAME_VERIFIED` |",
        f"| 2 | `generate_proxy_p_home()` 函數 | `scripts/run_moneyline_paper_v2.py` L73 | de-vigged odds + noise | 真實 walk-forward 模型輸出 `p_home_win` |",
        f"| 3 | `generate_proxy_blowout()` 函數 | `scripts/run_moneyline_paper_v2.py` L93 | odds-derived proxy | 真實 alpha_signals `blowout_propensity` 特徵 |",
        f"",
        f"---",
        f"",
        f"## 七、P2 Strategy Simulation V2 下游 Dataclass 介面建議",
        f"",
        f"```python",
        f"# P2 Strategy Simulation V2 建議使用以下介面",
        f"# 繼承 RecommendationRow，加入 simulation-level 欄位",
        f"",
        f"@dataclass",
        f"class SimulationRecommendationV2(RecommendationRow):",
        f"    # 模擬層新增欄位",
        f"    simulation_run_id: str = \"\"          # 蒙特卡洛執行批次 ID",
        f"    n_simulations: int = 50_000           # 本場模擬次數",
        f"    home_win_ci_95: tuple[float, float] = (0.0, 1.0)  # 95% CI",
        f"    away_win_ci_95: tuple[float, float] = (0.0, 1.0)",
        f"    world_model_score_dist: dict = field(default_factory=dict)  # 得分分佈",
        f"    marl_strategy_weight: float = 0.40   # MARL agent 權重",
        f"    hierarchical_mc_weight: float = 0.35 # HMC 權重",
        f"    world_model_weight: float = 0.25     # 世界模型權重",
        f"    clv_edge: float = 0.0                # P4 解鎖後填入真實 CLV",
        f"    pregame_odds_snapshot_id: str = \"\"   # P4 解鎖後填入",
        f"",
        f"# 使用方式：",
        f"# from wbc_backend.recommendation.moneyline_paper_v2 import RecommendationRow",
        f"# row: RecommendationRow = recommender.recommend(...)",
        f"# sim_row = SimulationRecommendationV2(**row.__dict__, simulation_run_id='SIM_20260518')",
        f"```",
        f"",
        f"---",
        f"",
        f"## 八、下一輪可直接執行的 Task Prompt",
        f"",
        f"```",
        f"P2_STRATEGY_SIMULATION_V2:",
        f"  - 整合 PredictionOrchestrator（wbc_backend/pipeline/prediction_orchestrator.py）",
        f"    與 MoneylinePaperRecommenderV2",
        f"  - 輸入：mlb_odds_2025_real.csv 的每場比賽",
        f"  - 輸出：SimulationRecommendationV2 artifact（含 home_win_ci_95, world_model_score_dist）",
        f"  - Gate：沿用現有 ECE/Blowout/Edge gates",
        f"  - 測試：pytest tests/test_simulation_v2.py（至少 10 個 tests）",
        f"  - 報告：report/strategy_sim_v2_20260518.md",
        f"",
        f"P4_ODDS_UNLOCK:",
        f"  - 接入真實 pregame odds API（TSL 或 Odds API）",
        f"  - 替換 odds_quality_tier → PREGAME_VERIFIED",
        f"  - 替換 generate_proxy_p_home → 真實 walk-forward 預測",
        f"  - 替換 generate_proxy_blowout → 真實 alpha_signals blowout_propensity",
        f"  - 重跑 scripts/run_moneyline_paper_v2.py 並比較 ROI delta",
        f"```",
        f"",
        f"---",
        f"",
        f"## 九、限制與風險",
        f"",
        f"1. **Proxy ROI 非真實**：p_home_win 由 odds 反推，模型無獨立預測能力",
        f"2. **單快照 odds**：所有 2430 場均為 2026-03-18/19 賽後單次抓取",
        f"3. **blowout_propensity proxy**：僅基於賠率懸殊度，非真實特徵計算",
        f"4. **ECE 全場共享**：0.035 為系統平均，非逐場校準",
        f"5. **無 CLV 驗證**：closing line 不可用，無法驗證 sharp money alignment",
        f"",
        f"---",
        f"",
        f"*Generated by CTO Agent — P0_MONEYLINE_PAPER_V2_PROXY_ONLY — 2026-05-18*",
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[report] 已寫入 {REPORT_PATH}")


def main() -> None:
    print("=== P0_MONEYLINE_PAPER_V2_PROXY_ONLY ===")
    print(f"讀取：{DATA_CSV}")

    results, stats = run_recommendations()

    print(f"\n統計結果：")
    print(f"  總場數：{stats['total_games']}")
    print(f"  推薦場數：{stats['n_recommended']}")
    print(f"  覆蓋率：{stats['coverage_rate']*100:.2f}%")
    print(f"  Proxy ROI：{stats['proxy_roi']*100:+.2f}% ⚠️ 非真實 CLV")
    print(f"  Gate 統計：{stats['gate_stats']}")

    write_artifact(results)
    write_report(results, stats)
    print("\n✅ 完成")


if __name__ == "__main__":
    main()
