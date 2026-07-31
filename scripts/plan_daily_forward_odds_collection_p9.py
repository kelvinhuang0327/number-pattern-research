"""
P9-D — Daily Forward Odds Collection Plan Script

只讀現有 TSL odds history timeline / P8 manifest。
不做任何網路呼叫。不修改 TSL crawler。
產出每日任務計畫（paper_only=true）。

Usage:
  python scripts/plan_daily_forward_odds_collection_p9.py \\
      --output data/paper_recommendations/p9_forward_collection_daily_schedule_20260525.json

paper_only=true。不呼叫外部 API。不修改 TSL crawler。不做 production write。
不代表任何實盤獲利能力。
"""

from __future__ import annotations

import json
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Constants ─────────────────────────────────────────────────────────────────

MIN_TIMESTAMP_COVERAGE_PCT: float = 95.0
MIN_PAIR_COVERAGE_PCT: float = 90.0
MIN_PAIRS_FOR_CLV: int = 200
CLOSING_WINDOW_SEC: int = 3600
PREGAME_MIN_SEC: int = 60

# Daily schedule windows
DAILY_SCHEDULE_WINDOWS = [
    {
        "label": "early",
        "hours_before_game_min": 24,
        "hours_before_game_max": 72,
        "priority": "NICE_TO_HAVE",
        "snapshot_type": "early",
        "notes": "早盤線收集，非必要但有助於 line movement 分析",
    },
    {
        "label": "pregame_d1",
        "hours_before_game_min": 6,
        "hours_before_game_max": 24,
        "priority": "HIGH",
        "snapshot_type": "pregame",
        "notes": "賽前一天開盤，建議在各時區開盤後 1 小時內抓取",
    },
    {
        "label": "pregame_d2",
        "hours_before_game_min": 2,
        "hours_before_game_max": 6,
        "priority": "CRITICAL",
        "snapshot_type": "pregame",
        "notes": "最重要的 pregame snapshot；CLV pair 的分子",
    },
    {
        "label": "decision",
        "hours_before_game_min": 0.5,
        "hours_before_game_max": 2,
        "priority": "CRITICAL",
        "snapshot_type": "decision",
        "notes": "先發投手確認後、賠率最終調整段；CLV 分析最關鍵的 window",
    },
    {
        "label": "closing_final",
        "hours_before_game_min": 0,
        "hours_before_game_max": 1,
        "priority": "CRITICAL",
        "snapshot_type": "closing",
        "notes": "closing_window_sec=3600；captured_at_utc 必須 < game_start_utc",
    },
]

# Target markets
TARGET_MARKETS = [
    {"market_code": "ML", "tsl_code": "MNL", "description": "讓分不讓分 (Moneyline)",
     "priority": "CRITICAL", "minimum_viable": True},
    {"market_code": "RL", "tsl_code": "HDP", "description": "讓分盤 (Run Line)",
     "priority": "MEDIUM", "minimum_viable": False},
    {"market_code": "OU", "tsl_code": "OU", "description": "大小分 (Over/Under)",
     "priority": "MEDIUM", "minimum_viable": False},
]

# ── Exceptions ────────────────────────────────────────────────────────────────


class ForwardCollectionPlanError(ValueError):
    """Raised when plan invariants are violated."""


# ── File naming convention ────────────────────────────────────────────────────


def build_snapshot_filename(
    match_id: str,
    market_code: str,
    window_label: str,
    captured_at_utc: str,
) -> str:
    """
    Deterministic snapshot filename.
    Format: tsl_{match_id}_{market_code}_{window_label}_{yyyymmddThhmmssZ}.json
    """
    ts = captured_at_utc.replace(":", "").replace("-", "").replace(" ", "T")
    if not ts.endswith("Z"):
        ts = ts[:15] + "Z"
    return f"tsl_{match_id}_{market_code}_{window_label}_{ts}.json"


# ── Timeline summary ──────────────────────────────────────────────────────────


def load_p8_manifest(manifest_path: Optional[Path] = None) -> dict:
    """
    Load the P8 forward collection manifest.
    Returns empty summary if file not found.
    """
    if manifest_path is None:
        manifest_path = Path(
            "data/paper_recommendations/p8_2026_forward_collection_manifest_20260524.json"
        )
    if not manifest_path.exists():
        return {
            "found": False,
            "total_records": 0,
            "unique_matches": 0,
            "pregame_closing_pairs": 0,
            "pair_coverage_pct": 0.0,
        }
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    summary = data.get("timeline_summary", {})
    return {
        "found": True,
        "total_records": summary.get("total_records", 0),
        "unique_matches": summary.get("unique_match_ids", 0),
        "pregame_closing_pairs": summary.get("pregame_closing_pairs", 0),
        "pair_coverage_pct": summary.get("pair_coverage_pct", 0.0),
        "date_range_start": summary.get("date_range_start", ""),
        "date_range_end": summary.get("date_range_end", ""),
    }


# ── Coverage check ────────────────────────────────────────────────────────────


def evaluate_coverage(manifest_summary: dict) -> dict:
    """Evaluate coverage against P8/P9 thresholds."""
    pairs = manifest_summary.get("pregame_closing_pairs", 0)
    pct = manifest_summary.get("pair_coverage_pct", 0.0)
    return {
        "current_pairs": pairs,
        "min_pairs_for_clv": MIN_PAIRS_FOR_CLV,
        "pairs_threshold_met": pairs >= MIN_PAIRS_FOR_CLV,
        "current_pair_coverage_pct": pct,
        "min_pair_coverage_pct": MIN_PAIR_COVERAGE_PCT,
        "coverage_threshold_met": pct >= MIN_PAIR_COVERAGE_PCT,
        "clv_gate_passed": pairs >= MIN_PAIRS_FOR_CLV and pct >= MIN_PAIR_COVERAGE_PCT,
    }


# ── Daily schedule builder ────────────────────────────────────────────────────


def build_daily_schedule(
    manifest_summary: dict,
    paper_only: bool = True,
) -> dict:
    """
    Build the daily forward odds collection schedule.
    paper_only must be True — raises ForwardCollectionPlanError otherwise.
    """
    if not paper_only:
        raise ForwardCollectionPlanError(
            "paper_only must be True for P9-D forward collection plan."
        )

    coverage = evaluate_coverage(manifest_summary)

    return {
        "task": "P9-D",
        "title": "Daily Forward Odds Collection Plan",
        "plan_date": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "network_call": False,
        "crawler_modified": False,
        "production_write": False,
        "thresholds": {
            "min_timestamp_coverage_pct": MIN_TIMESTAMP_COVERAGE_PCT,
            "min_pair_coverage_pct": MIN_PAIR_COVERAGE_PCT,
            "min_pairs_for_clv": MIN_PAIRS_FOR_CLV,
            "closing_window_sec": CLOSING_WINDOW_SEC,
            "pregame_min_sec": PREGAME_MIN_SEC,
        },
        "schedule_windows": DAILY_SCHEDULE_WINDOWS,
        "target_markets": TARGET_MARKETS,
        "minimum_viable_pair": {
            "description": "最小可行 CLV 配對",
            "pregame_window": "pregame_d2 OR decision",
            "closing_window": "closing_final",
            "market": "ML (Moneyline)",
            "constraint": "captured_at_utc(closing) < game_start_utc",
        },
        "file_naming": {
            "convention": "tsl_{match_id}_{market_code}_{window_label}_{yyyymmddThhmmssZ}.json",
            "example": "tsl_G2026031501_ML_closing_final_20260315T203000Z.json",
            "deterministic": True,
            "replay_safe": True,
            "duplicate_rule": (
                "若同一 match_id + market_code + window_label + 同分鐘 timestamp 已存在，"
                "SKIP 而非覆蓋。比對 captured_at_utc truncate to minute。"
            ),
        },
        "failure_handling": [
            {
                "scenario": "Crawler 抓取失敗",
                "action": "SKIP 記錄此 window；下一個 cron cycle 重試",
            },
            {
                "scenario": "缺少 snapshot_type",
                "action": "從 captured_at_utc vs game_start_utc 推斷 classify_source_type()",
            },
            {
                "scenario": "API timeout",
                "action": "3 次重試 + 指數退避 (1s, 4s, 16s)；超限後標記 FAILED_SNAPSHOT",
            },
            {
                "scenario": "paper_only 違規",
                "action": "觸發 PaperOnlyViolationError；終止該批次",
            },
        ],
        "replay_safety": {
            "append_rule": "只 append，不 overwrite 現有 JSONL 記錄",
            "idempotency": "以 match_id + window_label + minute 為 dedup key",
        },
        "coverage_metrics": coverage,
        "manifest_source": manifest_summary,
        "annotation": (
            "paper_only=true。TSL crawler 未修改。不做 production write。"
            "不代表任何實盤獲利能力。策略推廣凍結直到 CLV gate 通過。"
        ),
    }


# ── Main runner ───────────────────────────────────────────────────────────────


def run_daily_schedule_plan(
    output_path: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
) -> dict:
    """Main entrypoint: load manifest, build schedule, write output."""
    manifest_summary = load_p8_manifest(manifest_path)
    schedule = build_daily_schedule(manifest_summary, paper_only=True)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, indent=2, ensure_ascii=False)
        print(f"Written: {output_path}")

    return schedule


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P9-D Daily Forward Odds Collection Plan — no network, no crawler mod."
    )
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON path.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="P8 forward collection manifest path (optional).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    schedule = run_daily_schedule_plan(
        output_path=args.output,
        manifest_path=args.manifest,
    )
    coverage = schedule["coverage_metrics"]
    print(f"paper_only: {schedule['paper_only']}")
    print(f"crawler_modified: {schedule['crawler_modified']}")
    print(f"network_call: {schedule['network_call']}")
    print(f"current_pairs: {coverage['current_pairs']} / clv_gate_passed: {coverage['clv_gate_passed']}")


if __name__ == "__main__":
    main()
