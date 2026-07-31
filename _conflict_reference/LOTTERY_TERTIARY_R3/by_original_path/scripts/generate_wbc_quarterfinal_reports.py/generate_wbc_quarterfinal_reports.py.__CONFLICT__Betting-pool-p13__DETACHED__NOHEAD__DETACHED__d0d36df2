#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
SCORES_PATH = ROOT / "data/wbc_2026_live_scores.json"
ARTIFACTS_PATH = ROOT / "data/wbc_backend/model_artifacts.json"
REPORTS_DIR = ROOT / "data/wbc_backend/reports"

MATCHUPS = [
    {
        "date_tpe": "2026-03-14",
        "team_a_code": "KOR",
        "team_b_code": "DOM",
        "team_a_name": "Korea",
        "team_b_name": "Dominican Republic",
    },
    {
        "date_tpe": "2026-03-14",
        "team_a_code": "USA",
        "team_b_code": "CAN",
        "team_a_name": "United States",
        "team_b_name": "Canada",
    },
    {
        "date_tpe": "2026-03-15",
        "team_a_code": "PUR",
        "team_b_code": "ITA",
        "team_a_name": "Puerto Rico",
        "team_b_name": "Italy",
    },
    {
        "date_tpe": "2026-03-15",
        "team_a_code": "VEN",
        "team_b_code": "JPN",
        "team_a_name": "Venezuela",
        "team_b_name": "Japan",
    },
]


def load_scores() -> dict:
    return json.loads(SCORES_PATH.read_text(encoding="utf-8"))


def team_rates(scores_obj: dict, team_name: str) -> dict[str, float]:
    games = runs_scored = runs_allowed = 0
    wins = losses = 0

    for game in scores_obj["games"]:
        if game.get("status") not in ("Final", "Completed Early"):
            continue

        away, home = game["away"], game["home"]
        away_score, home_score = game["away_score"], game["home_score"]

        if away == team_name:
            games += 1
            runs_scored += away_score
            runs_allowed += home_score
            if away_score > home_score:
                wins += 1
            else:
                losses += 1
        elif home == team_name:
            games += 1
            runs_scored += home_score
            runs_allowed += away_score
            if home_score > away_score:
                wins += 1
            else:
                losses += 1

    if games == 0:
        raise ValueError(f"No verified games found for team: {team_name}")

    return {
        "games": games,
        "wins": wins,
        "losses": losses,
        "runs_scored_per_game": runs_scored / games,
        "runs_allowed_per_game": runs_allowed / games,
        "run_diff_per_game": (runs_scored - runs_allowed) / games,
    }


def poisson_probability(runs: int, lam: float) -> float:
    return math.exp(-lam) * (lam**runs) / math.factorial(runs)


def build_probability_matrix(lambda_a: float, lambda_b: float, max_runs: int = 12) -> np.ndarray:
    matrix = np.zeros((max_runs + 1, max_runs + 1))
    for a_runs in range(max_runs + 1):
        prob_a = poisson_probability(a_runs, lambda_a)
        for b_runs in range(max_runs + 1):
            matrix[a_runs, b_runs] = prob_a * poisson_probability(b_runs, lambda_b)

    total_mass = float(matrix.sum())
    return matrix / total_mass


def build_ascii_heatmap(matrix: np.ndarray, team_a_code: str) -> str:
    levels = " .:-=+*#%@"
    sub = matrix[:11, :11]
    max_value = sub.max() if sub.size else 0.0
    lines = ["       + 01234567890"]

    for row_idx in range(sub.shape[0] - 1, -1, -1):
        chars = []
        for col_idx in range(sub.shape[1]):
            scaled = sub[row_idx, col_idx] / max_value if max_value > 0 else 0.0
            level_idx = min(int(scaled * (len(levels) - 1)), len(levels) - 1)
            chars.append(levels[level_idx])
        lines.append(f"{team_a_code} {row_idx:2d} | {''.join(chars)}")

    return "\n".join(lines)


def render_report(
    *,
    matchup: dict,
    team_a: dict[str, float],
    team_b: dict[str, float],
    lambda_a: float,
    lambda_b: float,
    p_a_win_9: float,
    p_b_win_9: float,
    p_tie_9: float,
    p_a_full: float,
    p_b_full: float,
    matrix_csv_path: Path,
    summary_json_path: Path,
    ascii_heatmap: str,
) -> str:
    delta_rsg = team_b["runs_scored_per_game"] - team_a["runs_scored_per_game"]
    delta_rag = team_b["runs_allowed_per_game"] - team_a["runs_allowed_per_game"]
    delta_rdg = team_b["run_diff_per_game"] - team_a["run_diff_per_game"]
    stronger_code = matchup["team_b_code"] if p_b_full > p_a_full else matchup["team_a_code"]

    return f"""# 2026 WBC 深度對決分析：{matchup['team_a_name']} ({matchup['team_a_code']}) vs {matchup['team_b_name']} ({matchup['team_b_code']})

## 📊 核心實力指標 (Left vs Right)

| 指標 | {matchup['team_a_name']} ({matchup['team_a_code']}) | {matchup['team_b_name']} ({matchup['team_b_code']}) | 差異 |
|---|---:|---:|---:|
| 台灣比賽日期 | {matchup['date_tpe']} | {matchup['date_tpe']} | 同日 |
| 預賽戰績 | {team_a['wins']}-{team_a['losses']} | {team_b['wins']}-{team_b['losses']} | {stronger_code} 優勢 |
| 場均得分 (RS/G) | {team_a['runs_scored_per_game']:.2f} | {team_b['runs_scored_per_game']:.2f} | {matchup['team_b_code']} {delta_rsg:+.2f} |
| 場均失分 (RA/G) | {team_a['runs_allowed_per_game']:.2f} | {team_b['runs_allowed_per_game']:.2f} | {matchup['team_b_code']} {delta_rag:+.2f} |
| 得失分差/場 (RD/G) | {team_a['run_diff_per_game']:+.2f} | {team_b['run_diff_per_game']:+.2f} | {matchup['team_b_code']} {delta_rdg:+.2f} |
| OPS+ | 無資料 | 無資料 | 無資料 |
| FIP- | 無資料 | 無資料 | 無資料 |
| K-BB% | 無資料 | 無資料 | 無資料 |
| DER | 無資料 | 無資料 | 無資料 |
| Elo | 無資料 | 無資料 | 無資料 |

## 🧢 關鍵投打對決模擬 (Matchup Depth)

| 項目 | {matchup['team_a_name']} ({matchup['team_a_code']}) | {matchup['team_b_name']} ({matchup['team_b_code']}) |
|---|---|---|
| 台灣比賽日期 | {matchup['date_tpe']} | {matchup['date_tpe']} |
| 先發投手預估 | 無資料 | 無資料 |
| 先發投手球種/球速可驗證資料 | 無資料 | 無資料 |
| 牛棚深度可驗證資料 | 無資料 | 無資料 |
| 專項對戰加權資料 | 無資料 | 無資料 |

## 🎯 比分機率分佈 (Poisson 回歸)

資料來源：
- 官方完賽資料：`{SCORES_PATH}`
- 模型設定：`{ARTIFACTS_PATH}`

回歸參數：
- `lambda_{matchup['team_a_code']} = {lambda_a:.2f}`
- `lambda_{matchup['team_b_code']} = {lambda_b:.2f}`
- 特定對戰加權：`無資料`（無可驗證拆分資料）

機率結果：
- {matchup['team_a_code']} 9 局勝率：`{p_a_win_9:.4f}`
- {matchup['team_b_code']} 9 局勝率：`{p_b_win_9:.4f}`
- 9 局平手率：`{p_tie_9:.4f}`
- 全場 {matchup['team_a_code']} 勝率（平手 50/50）：`{p_a_full:.4f}`
- 全場 {matchup['team_b_code']} 勝率（平手 50/50）：`{p_b_full:.4f}`

## 🗺️ 得分機率矩陣圖

- 矩陣 CSV：`{matrix_csv_path}`
- 矩陣摘要：`{summary_json_path}`

ASCII 熱度圖（{matchup['team_a_code']} 為列，{matchup['team_b_code']} 為欄）：

```text
{ascii_heatmap}
```

## 💰 台灣運彩 EV 檢查

- 台灣運彩目前賠率：`無資料`
- EV：`無資料`
- 結論：`無資料`

## ⚠️ 風險提醒

- `model_artifacts.json` 未提供各隊權重欄位，該部分為 `無資料`。
- 先發與牛棚若臨場異動，lambda 與勝率會快速變化。
- 若盤口補齊，可立即改算 EV 與 Kelly 倉位。
"""


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    scores_obj = load_scores()

    for matchup in MATCHUPS:
        team_a = team_rates(scores_obj, matchup["team_a_name"])
        team_b = team_rates(scores_obj, matchup["team_b_name"])

        lambda_a = (team_a["runs_scored_per_game"] + team_b["runs_allowed_per_game"]) / 2.0
        lambda_b = (team_b["runs_scored_per_game"] + team_a["runs_allowed_per_game"]) / 2.0
        matrix = build_probability_matrix(lambda_a, lambda_b)

        p_a_win_9 = float(np.tril(matrix, -1).sum())
        p_b_win_9 = float(np.triu(matrix, 1).sum())
        p_tie_9 = float(np.trace(matrix))
        p_a_full = p_a_win_9 + 0.5 * p_tie_9
        p_b_full = p_b_win_9 + 0.5 * p_tie_9

        date_prefix = matchup["date_tpe"]
        slug = f"{matchup['team_a_code']}_{matchup['team_b_code']}"
        report_path = REPORTS_DIR / f"{date_prefix}_WBC_{slug}_Deep_Report.md"
        matrix_csv_path = REPORTS_DIR / f"{date_prefix}_{slug}_poisson_matrix.csv"
        summary_json_path = REPORTS_DIR / f"{date_prefix}_{slug}_poisson_summary.json"

        pd.DataFrame(
            matrix,
            index=[f"{matchup['team_a_code']}_{i}" for i in range(matrix.shape[0])],
            columns=[f"{matchup['team_b_code']}_{i}" for i in range(matrix.shape[1])],
        ).to_csv(matrix_csv_path, encoding="utf-8")

        summary = {
            "date_tpe": matchup["date_tpe"],
            "lambda_a": lambda_a,
            "lambda_b": lambda_b,
            "a_win_9": p_a_win_9,
            "b_win_9": p_b_win_9,
            "tie_9": p_tie_9,
            "a_full": p_a_full,
            "b_full": p_b_full,
            "special_matchup_weight": "無資料",
            "odds": "無資料",
            "model_artifacts_has_team_weights": False,
            "matrix_csv": str(matrix_csv_path),
        }
        summary_json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        report = render_report(
            matchup=matchup,
            team_a=team_a,
            team_b=team_b,
            lambda_a=lambda_a,
            lambda_b=lambda_b,
            p_a_win_9=p_a_win_9,
            p_b_win_9=p_b_win_9,
            p_tie_9=p_tie_9,
            p_a_full=p_a_full,
            p_b_full=p_b_full,
            matrix_csv_path=matrix_csv_path,
            summary_json_path=summary_json_path,
            ascii_heatmap=build_ascii_heatmap(matrix, matchup["team_a_code"]),
        )
        report_path.write_text(report, encoding="utf-8")
        print(report_path)


if __name__ == "__main__":
    main()
