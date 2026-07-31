#!/usr/bin/env python3
"""
P5 驗證腳本：p5_validate_ha40_platt.py
計算 P5 ha40+platt artifact 的 Brier / ECE / accuracy / MARL gate。
與 P3 baseline / P4 warm_start 對照。
"""
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

ARTIFACT_PATH = BASE_DIR / "data/paper_recommendations/strategy_sim_v2_ha40_platt_20260518.jsonl"
ODDS_CSV_CANDIDATES = [
    BASE_DIR / "data/mlb_2025/mlb_odds_2025_real.csv",
    BASE_DIR / "data/mlb_odds_2025_real.csv",
    Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv"),
]
OUTPUT_PATH = BASE_DIR / "data/paper_recommendations/p5_ha40_platt_validation_20260518.json"

from wbc_backend.recommendation.strategy_sim_validation import (
    validate_marl_gate,
    build_brier_ece_result,
    summarize_by_walk_forward_fold,
    compare_edge_thresholds,
)


def _find_odds_csv() -> Path:
    for p in ODDS_CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(f"找不到 mlb_odds_2025_real.csv，已搜尋：{ODDS_CSV_CANDIDATES}")


def _normalize_team(name: str) -> str:
    return name.strip().lower()


def _load_odds_lookup(csv_path: Path) -> dict:
    lookup = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Status", "").strip().lower() != "final":
                continue
            date = row.get("Date", "").strip()
            home = _normalize_team(row.get("Home", ""))
            away = _normalize_team(row.get("Away", ""))
            try:
                hs = int(row.get("Home Score", 0))
                aws = int(row.get("Away Score", 0))
            except (ValueError, TypeError):
                continue
            lookup[(date, home, away)] = {
                "home_win": 1 if hs > aws else 0,
                "home_score": hs,
                "away_score": aws,
            }
    return lookup


def _load_artifact(path: Path) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _calc_ece(probs: list, outcomes: list, n_bins: int = 10) -> float:
    """計算 ECE（Expected Calibration Error）。"""
    if not probs:
        return float("nan")
    bins = defaultdict(list)
    for p, o in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b].append((p, o))
    ece = 0.0
    n = len(probs)
    for b, items in bins.items():
        avg_p = sum(x[0] for x in items) / len(items)
        avg_o = sum(x[1] for x in items) / len(items)
        ece += len(items) / n * abs(avg_p - avg_o)
    return ece


def main():
    print("=" * 60)
    print("P5 驗證腳本啟動 (ha40 + Platt Scaling)")
    print("=" * 60)

    # 讀取 artifact
    if not ARTIFACT_PATH.exists():
        print(f"[ERROR] artifact 不存在：{ARTIFACT_PATH}")
        sys.exit(1)
    rows = _load_artifact(ARTIFACT_PATH)
    total_rows = len(rows)
    print(f"[INFO] artifact 讀取完成：{total_rows} 筆")

    # 讀取 odds CSV
    odds_csv_path = _find_odds_csv()
    odds_lookup = _load_odds_lookup(odds_csv_path)
    print(f"[INFO] odds lookup：{len(odds_lookup)} 筆")

    # Join
    joined = []
    n_joined = 0
    n_missing = 0
    for row in rows:
        date = row.get("game_date", "")
        home = _normalize_team(row.get("home_team", ""))
        away = _normalize_team(row.get("away_team", ""))
        key = (date, home, away)
        od = odds_lookup.get(key)
        enriched = dict(row)
        if od is not None:
            enriched["actual_home_win"] = od["home_win"]
            n_joined += 1
        else:
            enriched["actual_home_win"] = None
            n_missing += 1
        joined.append(enriched)

    join_rate = n_joined / total_rows if total_rows > 0 else 0.0
    print(f"[INFO] join 率：{join_rate:.2%} ({n_joined}/{total_rows})")

    # 計算指標
    rows_with_outcome = [r for r in joined if r.get("actual_home_win") is not None]
    probs = [r["model_prob"] for r in rows_with_outcome]
    outcomes = [r["actual_home_win"] for r in rows_with_outcome]

    brier = sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs) if probs else float("nan")
    ece = _calc_ece(probs, outcomes)
    accuracy = sum(1 for p, o in zip(probs, outcomes) if (p > 0.5) == (o == 1)) / len(probs) if probs else float("nan")

    # MARL gate
    gate = validate_marl_gate(brier=brier, ece=ece)
    gate_status = gate["gate_status"]
    # P5 額外：accuracy > 50%
    if accuracy <= 0.50:
        gate_status = "FAIL"
        gate.setdefault("reasons", []).append(f"Accuracy {accuracy:.4f} <= 0.50")

    print(f"[RESULT] Brier={brier:.4f}, ECE={ece:.4f}, Accuracy={accuracy:.4f}, gate={gate_status}")

    # Fold-level breakdown
    fold_summary = summarize_by_walk_forward_fold(joined)

    # Edge threshold comparison
    edge_comparison = compare_edge_thresholds(joined, thresholds=[0.01, 0.03, 0.05])

    # 讀取 P3 baseline 與 P4 結果作對照
    p3_path = BASE_DIR / "data/paper_recommendations/p3_brier_ece_validation_20260518.json"
    p4_path = BASE_DIR / "data/paper_recommendations/p4_elo_repair_validation_20260518.json"
    p3_summary = None
    p4_summary = None
    try:
        p3_summary = json.loads(p3_path.read_text())["summary"]
    except Exception:
        pass
    try:
        p4_summary = json.loads(p4_path.read_text())["summary"]
    except Exception:
        pass

    # 決定 P5 classification
    if join_rate < 0.50:
        classification = "P5_PARTIAL_CALIBRATION_DATA_BLOCKED"
    elif accuracy > 0.50 and brier < 0.25 and ece < 0.12:
        classification = "P5_HOME_ADVANTAGE_CALIBRATION_AND_MARL_GATE_PASS"
    elif accuracy > 0.50:
        classification = "P5_DIRECTION_REPAIRED_CALIBRATION_STILL_FAIL"
    else:
        classification = "P5_FAIL_PURE_ELO_DIRECTION_UNRESOLVED"

    print(f"[RESULT] Classification: {classification}")

    # 輸出 JSON
    output_data = {
        "classification": classification,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "artifact_path": str(ARTIFACT_PATH),
        "odds_csv_path": str(odds_csv_path),
        "summary": {
            "total_rows": total_rows,
            "joined_rows": n_joined,
            "missing_result_rows": n_missing,
            "brier_score": round(brier, 6) if not math.isnan(brier) else None,
            "ece": round(ece, 6) if not math.isnan(ece) else None,
            "accuracy": round(accuracy, 6) if not math.isnan(accuracy) else None,
            "coverage_rate": round(join_rate, 4),
            "gate_status": gate_status,
            "reasons": gate.get("reasons", []),
        },
        "comparison": {
            "p3_baseline": p3_summary,
            "p4_warm_start": p4_summary,
            "p5_ha40_platt": {
                "brier_score": round(brier, 6) if not math.isnan(brier) else None,
                "ece": round(ece, 6) if not math.isnan(ece) else None,
                "accuracy": round(accuracy, 6) if not math.isnan(accuracy) else None,
                "gate_status": gate_status,
            },
        },
        "fold_summary": fold_summary,
        "edge_threshold_comparison": edge_comparison,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x),
        encoding="utf-8"
    )
    print(f"[OUTPUT] 儲存至：{OUTPUT_PATH}")
    print("=" * 60)
    print(f"Final Classification：{classification}")
    print("=" * 60)


if __name__ == "__main__":
    main()
