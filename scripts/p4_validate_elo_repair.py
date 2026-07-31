#!/usr/bin/env python3
"""
P4：驗證 elo_repair 版 strategy_sim_v2 的 Brier/ECE，決定 MARL gate。
對 data/paper_recommendations/strategy_sim_v2_elo_repair_20260518.jsonl 跑驗證。
"""
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = BASE_DIR / "data/paper_recommendations/strategy_sim_v2_elo_repair_20260518.jsonl"
BASELINE_ARTIFACT = BASE_DIR / "data/paper_recommendations/strategy_sim_v2_20260518.jsonl"
ODDS_CSV_CANDIDATES = [
    BASE_DIR / "data/mlb_2025/mlb_odds_2025_real.csv",
    Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv"),
]
OUTPUT_PATH = BASE_DIR / "data/paper_recommendations/p4_elo_repair_validation_20260518.json"

sys.path.insert(0, str(BASE_DIR))
from wbc_backend.recommendation.strategy_sim_validation import (
    build_brier_ece_result,
    compare_edge_thresholds,
    summarize_by_walk_forward_fold,
)


def _find_odds_csv() -> Path:
    for p in ODDS_CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(f"找不到 mlb_odds_2025_real.csv，已搜尋：{ODDS_CSV_CANDIDATES}")


def _normalize_team(name: str) -> str:
    return name.strip().lower()


def load_odds_lookup(csv_path: Path) -> dict:
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
            lookup[(date, home, away)] = {"home_win": home_win}
    return lookup


def join_rows(artifact_rows, odds_lookup):
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
            n_joined += 1
        else:
            enriched["actual_home_win"] = None
            n_missing += 1
        joined.append(enriched)
    return joined, n_joined, n_missing


def run(artifact_path=None, output_path=None):
    art_path = Path(artifact_path) if artifact_path else ARTIFACT_PATH
    out_path = Path(output_path) if output_path else OUTPUT_PATH

    print("=" * 60)
    print("P4 Elo Repair 驗證腳本啟動")
    print(f"  artifact：{art_path}")
    print("=" * 60)

    if not art_path.exists():
        print(f"[ERROR] 找不到 artifact：{art_path}")
        sys.exit(1)

    artifact_rows = []
    with open(art_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                artifact_rows.append(json.loads(line))
    total_rows = len(artifact_rows)
    print(f"[INFO] artifact 讀取：{total_rows} 筆")

    odds_csv_path = _find_odds_csv()
    odds_lookup = load_odds_lookup(odds_csv_path)
    print(f"[INFO] odds 查詢表：{len(odds_lookup)} 筆 Final 場次")

    joined_rows, n_joined, n_missing = join_rows(artifact_rows, odds_lookup)
    join_rate = n_joined / total_rows if total_rows > 0 else 0.0
    print(f"[INFO] join：joined={n_joined}, missing={n_missing}, rate={join_rate:.2%}")

    rows_with_actual = [r for r in joined_rows if r.get("actual_home_win") is not None]
    result = build_brier_ece_result(
        rows_with_actual=rows_with_actual,
        total_rows=total_rows,
        joined_rows=n_joined,
        missing_result_rows=n_missing,
    )

    if result.gate_status == "PASS":
        classification = "P4_ELO_REPAIR_AND_MARL_GATE_PASS"
    elif result.accuracy is not None and result.accuracy > 0.5:
        classification = "P4_ELO_REPAIR_PARTIAL_DIRECTION_IMPROVED"
    else:
        classification = "P4_ELO_REPAIR_FAIL_MODEL_DIRECTION_UNRESOLVED"

    fold_summary = summarize_by_walk_forward_fold(joined_rows)
    edge_comparison = compare_edge_thresholds(joined_rows, thresholds=[0.01, 0.03, 0.05])

    # ── 讀取 baseline P3 結果進行比較 ──────────────────────────────────────────
    baseline_summary = None
    if BASELINE_ARTIFACT.exists():
        baseline_rows_raw = []
        with open(BASELINE_ARTIFACT, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    baseline_rows_raw.append(json.loads(line))
        baseline_joined, bn_joined, bn_missing = join_rows(baseline_rows_raw, odds_lookup)
        baseline_with_actual = [r for r in baseline_joined if r.get("actual_home_win") is not None]
        if baseline_with_actual:
            b_result = build_brier_ece_result(
                rows_with_actual=baseline_with_actual,
                total_rows=len(baseline_rows_raw),
                joined_rows=bn_joined,
                missing_result_rows=bn_missing,
            )
            baseline_summary = b_result.to_dict()
            baseline_summary["n_games"] = len(baseline_rows_raw)

    output_data = {
        "classification": classification,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "artifact_path": str(art_path),
        "odds_csv_path": str(odds_csv_path),
        "summary": result.to_dict(),
        "baseline_summary": baseline_summary,
        "fold_summary": fold_summary,
        "edge_threshold_comparison": edge_comparison,
    }

    output_json = json.dumps(
        output_data, ensure_ascii=False, indent=2,
        default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else x
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output_json, encoding="utf-8")
    print(f"[OUTPUT] 儲存至：{out_path}")

    print("=" * 60)
    print(f"  Brier：{result.brier_score:.4f}  ECE：{result.ece:.4f}  Accuracy：{result.accuracy:.4f}")
    print(f"  gate_status：{result.gate_status}")
    if baseline_summary:
        print(f"  Baseline Brier：{baseline_summary.get('brier_score', 'N/A')}  Accuracy：{baseline_summary.get('accuracy', 'N/A')}")
    print(f"Final Classification：{classification}")
    print("=" * 60)
    return output_data


if __name__ == "__main__":
    run()
