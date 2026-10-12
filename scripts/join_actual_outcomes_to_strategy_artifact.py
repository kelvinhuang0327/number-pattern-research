#!/usr/bin/env python3
"""
P7: join actual outcomes from mlb_odds_2025_real.csv to P5 artifact
====================================================================
從 mlb_odds_2025_real.csv 取得 home_score / away_score，
填入 P5 artifact 每一列，產出含 actual_home_win 的 enriched artifact。

硬性約束：
- 不偽造 actual_home_win
- paper_only 永遠 True
- 不呼叫 live odds API
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.recommendation.actual_outcome_join import join_outcomes_to_artifact

WORKTREE = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = WORKTREE / "data/paper_recommendations/strategy_sim_v2_ha40_platt_20260518.jsonl"
ODDS_CSV_PATH = WORKTREE / "data/mlb_2025/mlb_odds_2025_real.csv"
OUTPUT_PATH = WORKTREE / "data/paper_recommendations/strategy_sim_v2_ha40_platt_with_outcomes_20260518.jsonl"
SUMMARY_PATH = WORKTREE / "data/paper_recommendations/p7_actual_outcome_join_summary_20260518.json"


def load_artifact(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_odds_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def main():
    print("[P7] 載入 P5 artifact...")
    artifact_rows = load_artifact(ARTIFACT_PATH)
    print(f"  → {len(artifact_rows)} rows")

    print("[P7] 載入 MLB odds CSV...")
    odds_rows = load_odds_csv(ODDS_CSV_PATH)
    print(f"  → {len(odds_rows)} rows")

    print("[P7] 執行 outcome join...")
    enriched_rows, summary = join_outcomes_to_artifact(artifact_rows, odds_rows)

    print(f"  → 總計: {summary['total_rows']}")
    print(f"  → Joined: {summary['joined_rows']}")
    print(f"  → No Match: {summary['no_match_rows']}")
    print(f"  → Missing Score: {summary['missing_outcome_rows']}")
    print(f"  → Duplicate Key: {summary['duplicate_key_rows']}")
    print(f"  → Invalid Score: {summary['invalid_score_rows']}")
    print(f"  → Coverage Rate: {summary['join_coverage_rate']:.1%}")

    # 寫出 enriched artifact
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for row in enriched_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[P7] Enriched artifact → {OUTPUT_PATH}")

    # 寫出 summary JSON
    full_summary = {
        "run_id": "P7_ACTUAL_OUTCOME_JOIN_20260518",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_source": str(ARTIFACT_PATH.name),
        "odds_csv_source": str(ODDS_CSV_PATH.name),
        "output_artifact": str(OUTPUT_PATH.name),
        "paper_only": True,
        **summary,
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(full_summary, f, ensure_ascii=False, indent=2)
    print(f"[P7] Summary → {SUMMARY_PATH}")
    print("[P7] 完成 ✓")
    return full_summary


if __name__ == "__main__":
    main()
