#!/usr/bin/env python3
"""
P3：驗證 strategy_sim_v2 的 Brier/ECE，決定 MARL gate。

join 策略：Date + Home_team + Away_team（因 game_id 格式與 CSV 無直接對應）
資料來源：
  - P2 artifact: data/paper_recommendations/strategy_sim_v2_20260518.jsonl
  - MLB odds:    data/mlb_2025/mlb_odds_2025_real.csv（主 repo 路徑）
若 join 失敗超過 50%，輸出 PARTIAL。
"""
import csv
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# 路徑設定
BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = BASE_DIR / "data/paper_recommendations/strategy_sim_v2_20260518.jsonl"
ODDS_CSV_CANDIDATES = [
    BASE_DIR / "data/mlb_odds_2025_real.csv",
    BASE_DIR / "data/mlb_2025/mlb_odds_2025_real.csv",
    Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv"),
]
OUTPUT_PATH = BASE_DIR / "data/paper_recommendations/p3_brier_ece_validation_20260518.json"
REPORT_PATH = BASE_DIR / "report/p3_brier_ece_validation_20260518.md"

# 加入 sys.path 以 import 模組
sys.path.insert(0, str(BASE_DIR))
from wbc_backend.recommendation.strategy_sim_validation import (
    build_brier_ece_result,
    calculate_brier_score,
    calculate_ece,
    compare_edge_thresholds,
    summarize_by_walk_forward_fold,
    validate_marl_gate,
)


def _find_odds_csv() -> Path:
    for p in ODDS_CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"找不到 mlb_odds_2025_real.csv，已搜尋：{ODDS_CSV_CANDIDATES}"
    )


def _normalize_team(name: str) -> str:
    return name.strip().lower()


def load_odds_lookup(csv_path: Path) -> dict:
    """
    讀取 MLB odds CSV，建立 (date, home_team_norm, away_team_norm) → {home_score, away_score, home_win}。
    """
    lookup = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get("Date", "").strip()
            home = _normalize_team(row.get("Home", ""))
            away = _normalize_team(row.get("Away", ""))
            status = row.get("Status", "").strip()
            if status.lower() != "final":
                continue
            try:
                home_score = int(row.get("Home Score", 0))
                away_score = int(row.get("Away Score", 0))
            except (ValueError, TypeError):
                continue
            home_win = 1 if home_score > away_score else 0
            key = (date, home, away)
            lookup[key] = {
                "home_score": home_score,
                "away_score": away_score,
                "home_win": home_win,
                "home_ml": row.get("Home ML", ""),
                "away_ml": row.get("Away ML", ""),
            }
    return lookup


def join_artifact_with_odds(
    artifact_rows: list, odds_lookup: dict
) -> tuple[list, int, int]:
    """
    join P2 artifact 與 odds 資料。
    回傳 (joined_rows, n_joined, n_missing)
    """
    joined = []
    n_joined = 0
    n_missing = 0

    for row in artifact_rows:
        date = row.get("game_date", "")
        home = _normalize_team(row.get("home_team", ""))
        away = _normalize_team(row.get("away_team", ""))
        key = (date, home, away)
        odds_data = odds_lookup.get(key)
        enriched = dict(row)
        if odds_data is not None:
            enriched["actual_home_win"] = odds_data["home_win"]
            enriched["actual_home_score"] = odds_data["home_score"]
            enriched["actual_away_score"] = odds_data["away_score"]
            n_joined += 1
        else:
            enriched["actual_home_win"] = None
            n_missing += 1
        joined.append(enriched)

    return joined, n_joined, n_missing


def generate_report(
    result,
    fold_summary: list,
    edge_comparison: list,
    classification: str,
    odds_csv_path: Path,
) -> str:
    """產出繁體中文 Markdown 報告。"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    gate_emoji = "✅" if result.gate_status == "PASS" else "❌"

    brier_str = f"{result.brier_score:.4f}" if not math.isnan(result.brier_score) else "N/A"
    ece_str = f"{result.ece:.4f}" if not math.isnan(result.ece) else "N/A"
    acc_str = f"{result.accuracy:.4f}" if not math.isnan(result.accuracy) else "N/A"

    lines = [
        f"# P3 驗證報告：P3_BRIER_ECE_VALIDATION_AND_MARL_GATE（PROXY_ONLY）",
        "",
        f"**產出時間**：{now}",
        f"**Classification**：{classification}",
        f"**資料來源**：`{odds_csv_path.name}`（{odds_csv_path}）",
        "",
        "本報告驗證 P2 SimplifiedElo_v1 model_prob 的校準能力。",
        "由於 MLB odds CSV 僅包含單次 post-game 快照，所有賽果為 PROXY_ONLY。",
        "",
        "---",
        "",
        "## 一、指標摘要",
        "",
        "| 指標 | 數值 |",
        "|------|------|",
        f"| total_rows | {result.total_rows} |",
        f"| joined_rows | {result.joined_rows} |",
        f"| missing_result_rows | {result.missing_result_rows} |",
        f"| Brier Score | {brier_str} |",
        f"| ECE | {ece_str} |",
        f"| Accuracy | {acc_str} |",
        f"| coverage_rate | {result.coverage_rate:.4f} |",
        f"| MARL gate_status | {gate_emoji} {result.gate_status} |",
        "",
        "---",
        "",
        "## 二、MARL Gate 決策",
        "",
        f"**決策：{gate_emoji} {result.gate_status}**",
        "",
    ]

    if result.gate_status == "PASS":
        lines.append("Brier Score < 0.25 且 ECE < 0.12，符合進入 MARL optimizer 條件。")
    else:
        lines.append("未通過 MARL gate，原因如下：")
        for reason in result.reasons:
            lines.append(f"- {reason}")

    lines += [
        "",
        "---",
        "",
        "## 三、Walk-Forward Fold 分層統計",
        "",
        "| Fold | Games | Recommendations | Coverage | Accuracy | Brier | ECE |",
        "|------|-------|----------------|----------|----------|-------|-----|",
    ]

    for f in fold_summary:
        acc = f"{f['accuracy']:.4f}" if f["accuracy"] is not None else "N/A"
        brier = f"{f['brier']:.4f}" if f["brier"] is not None else "N/A"
        ece = f"{f['ece']:.4f}" if f["ece"] is not None else "N/A"
        lines.append(
            f"| {f['fold']} | {f['games']} | {f['recommendations']} "
            f"| {f['coverage']:.4f} | {acc} | {brier} | {ece} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 四、Edge Threshold Comparison",
        "",
        "| Threshold | n_recommended | coverage_rate | avg_edge | avg_kelly_fraction |",
        "|-----------|--------------|---------------|----------|--------------------|",
    ]

    for ec in edge_comparison:
        avg_edge = f"{ec['average_edge']:.4f}" if ec["average_edge"] is not None else "N/A"
        avg_kelly = f"{ec['average_kelly_fraction']:.4f}" if ec["average_kelly_fraction"] is not None else "N/A"
        lines.append(
            f"| {ec['threshold']} | {ec['n_recommended']} | {ec['coverage_rate']:.4f} "
            f"| {avg_edge} | {avg_kelly} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 五、結論與下一步",
        "",
    ]

    if classification == "P3_BRIER_ECE_VALIDATION_AND_MARL_GATE_PASS":
        lines += [
            "SimplifiedElo_v1 model_prob 通過 Brier/ECE gate，可進入 MARL optimizer（P4）。",
            "",
            "### 建議下一步",
            "- **P4**：MARL 策略優化器整合（marl_optimizer.py），使用本次 brier/ece 結果作為 baseline",
            "- **P5**：接入 Platt Scaling 進行機率後校準（probability_calibrator.py）",
            "- **P6**：開始累積 2026 regular season 實時 TSL 資料，建立真實 pregame odds 時間線",
        ]
    elif classification == "P3_BRIER_ECE_VALIDATION_AND_MARL_GATE_FAIL":
        lines += [
            "SimplifiedElo_v1 model_prob 未通過 Brier/ECE gate，不得進入 MARL optimizer。",
            "",
            "### 建議下一步",
            "- 執行 Platt Scaling / Temperature Scaling 後重驗（probability_calibrator.py）",
            "- 審查特徵工程是否有 look-ahead leakage",
            "- 考慮增加回測數據量或調整 Elo K 值",
        ]
    else:
        lines += [
            "join 成功率不足 50%，無法得出可靠結論（PARTIAL）。",
            "",
            "### 建議下一步",
            "- 確認 mlb_odds_2025_real.csv 的球隊名稱格式是否與 P2 artifact 一致",
            "- 補充 game_id 對應關係，或修正 date+team join key",
        ]

    lines += [
        "",
        "---",
        "",
        f"> 本報告由 CTO agent 自動產出，驗證標準：Brier < 0.25，ECE < 0.12",
        f"> 資料品質：PROXY_ONLY（MLB 2025 賽季，post-game 單次快照）",
    ]

    return "\n".join(lines) + "\n"


def main():
    print("=" * 60)
    print("P3 Brier/ECE 驗證腳本啟動")
    print("=" * 60)

    # 1. 讀取 P2 artifact
    if not ARTIFACT_PATH.exists():
        print(f"[ERROR] 找不到 artifact：{ARTIFACT_PATH}")
        sys.exit(1)

    artifact_rows = []
    with open(ARTIFACT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                artifact_rows.append(json.loads(line))
    total_rows = len(artifact_rows)
    print(f"[INFO] P2 artifact 讀取完成：{total_rows} 筆")

    # 2. 讀取 odds CSV
    try:
        odds_csv_path = _find_odds_csv()
        print(f"[INFO] 使用 odds CSV：{odds_csv_path}")
        odds_lookup = load_odds_lookup(odds_csv_path)
        print(f"[INFO] odds 查詢表建立完成：{len(odds_lookup)} 筆 Final 場次")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # 3. Join
    joined_rows, n_joined, n_missing = join_artifact_with_odds(artifact_rows, odds_lookup)
    join_rate = n_joined / total_rows if total_rows > 0 else 0.0
    print(f"[INFO] join 結果：joined={n_joined}, missing={n_missing}, rate={join_rate:.2%}")

    # 4. 決定 classification
    if join_rate < 0.50:
        classification = "P3_BRIER_ECE_VALIDATION_PARTIAL"
        print(f"[WARN] join 率 {join_rate:.2%} < 50%，輸出 PARTIAL")
    else:
        # 計算指標
        rows_with_actual = [r for r in joined_rows if r.get("actual_home_win") is not None]
        result = build_brier_ece_result(
            rows_with_actual=rows_with_actual,
            total_rows=total_rows,
            joined_rows=n_joined,
            missing_result_rows=n_missing,
        )
        if result.gate_status == "PASS":
            classification = "P3_BRIER_ECE_VALIDATION_AND_MARL_GATE_PASS"
        else:
            classification = "P3_BRIER_ECE_VALIDATION_AND_MARL_GATE_FAIL"

    if join_rate >= 0.50:
        rows_with_actual = [r for r in joined_rows if r.get("actual_home_win") is not None]
        result = build_brier_ece_result(
            rows_with_actual=rows_with_actual,
            total_rows=total_rows,
            joined_rows=n_joined,
            missing_result_rows=n_missing,
        )
    else:
        # PARTIAL：建立假 result
        from wbc_backend.recommendation.strategy_sim_validation import BrierECEResult
        result = BrierECEResult(
            total_rows=total_rows,
            joined_rows=n_joined,
            missing_result_rows=n_missing,
            brier_score=float("nan"),
            ece=float("nan"),
            accuracy=float("nan"),
            coverage_rate=join_rate,
            gate_status="FAIL",
            reasons=[f"join 率 {join_rate:.2%} < 50%，資料不足"],
        )

    brier_str = f"{result.brier_score:.4f}" if not math.isnan(result.brier_score) else "NaN"
    ece_str = f"{result.ece:.4f}" if not math.isnan(result.ece) else "NaN"
    print(f"[RESULT] Brier={brier_str}, ECE={ece_str}, gate={result.gate_status}")
    print(f"[RESULT] Classification: {classification}")

    # 5. Fold-level summary
    fold_summary = summarize_by_walk_forward_fold(joined_rows)

    # 6. Edge threshold comparison
    edge_comparison = compare_edge_thresholds(joined_rows, thresholds=[0.01, 0.03, 0.05])

    # 7. 輸出 validation JSON
    output_data = {
        "classification": classification,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "artifact_path": str(ARTIFACT_PATH),
        "odds_csv_path": str(odds_csv_path),
        "summary": result.to_dict(),
        "fold_summary": fold_summary,
        "edge_threshold_comparison": edge_comparison,
    }
    # 處理 nan
    output_json = json.dumps(output_data, ensure_ascii=False, indent=2, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else x)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(output_json, encoding="utf-8")
    print(f"[OUTPUT] JSON 儲存至：{OUTPUT_PATH}")

    # 8. 產出 Markdown 報告
    report_text = generate_report(result, fold_summary, edge_comparison, classification, odds_csv_path)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"[OUTPUT] 報告儲存至：{REPORT_PATH}")

    print("=" * 60)
    print(f"Final Classification：{classification}")
    print("=" * 60)


if __name__ == "__main__":
    main()
