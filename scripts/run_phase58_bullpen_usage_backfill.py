"""
scripts/run_phase58_bullpen_usage_backfill.py
=============================================
Phase 58 — Bullpen Usage Backfill Script

功能：
  為 MLB 2025 的 2,025 場比賽建立 bullpen usage snapshot，
  使用 schedule proxy fallback（D-1 PIT-safe）。

執行方式：
    python scripts/run_phase58_bullpen_usage_backfill.py [--print] [--json]

輸出：
    data/mlb_2025/derived/mlb_2025_bullpen_usage_phase58.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True

資料策略：
    本 Phase 使用 schedule proxy fallback（無真實 boxscore data）：
    - 每場已完成比賽估計 9 個 bullpen outs（聯盟平均）
    - B2B 根據賽程連續性估計
    - ERA/FIP proxy 使用聯盟平均（4.10 / 4.05）
    - Leverage proxy = 0.0（需 Statcast，Phase 59 實作）
    - 所有記錄標記：estimated=True, source="schedule_proxy_fallback"
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import sys
sys.path.insert(0, str(_ROOT / "data"))

from data.mlb_bullpen_usage_loader import (
    load_bullpen_usage_inputs,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
)
from wbc_backend.features.mlb_bullpen_usage_snapshot import (
    build_bullpen_snapshots_batch,
    FEATURE_VERSION,
)
from wbc_backend.features.mlb_bullpen_pit_validator import (
    validate_bullpen_snapshot_batch,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions.jsonl"
)
_ASPLAYED_CSV = _ROOT / "data" / "mlb_2025" / "mlb-2025-asplayed.csv"
_OUTPUT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_bullpen_usage_phase58.jsonl"
)

# ── Expected row count ────────────────────────────────────────────────────────
_EXPECTED_ROW_COUNT: int = 2025


def run_backfill(
    baseline_path: Path = _BASELINE_JSONL,
    asplayed_path: Path = _ASPLAYED_CSV,
    output_path: Path = _OUTPUT_JSONL,
    dry_run: bool = False,
) -> dict:
    """
    執行 Phase58 bullpen usage backfill。

    Returns:
        Summary dict
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    logger.info("Phase58 Bullpen Usage Backfill 開始")
    logger.info("Baseline: %s", baseline_path)
    logger.info("Asplayed: %s", asplayed_path)
    logger.info("Output: %s", output_path)
    if dry_run:
        logger.info("DRY RUN — 不寫入 output 檔案")

    # ── Step 1: 載入資料 ────────────────────────────────────────────────────
    bundle = load_bullpen_usage_inputs(
        baseline_path=baseline_path,
        asplayed_path=asplayed_path,
    )
    baseline_rows = bundle.baseline_rows
    team_game_history = bundle.team_game_history

    # ── Step 2: 建立牛棚快照 ─────────────────────────────────────────────────
    logger.info("為 %d 場比賽建立 bullpen snapshots...", len(baseline_rows))
    timestamp = datetime.now(timezone.utc).isoformat()
    snapshots = build_bullpen_snapshots_batch(baseline_rows, team_game_history)

    # Inject data_timestamp
    for snap in snapshots:
        snap["data_timestamp"] = timestamp

    # ── Step 3: PIT 驗證 ─────────────────────────────────────────────────────
    logger.info("執行 PIT validation...")
    val_result = validate_bullpen_snapshot_batch(snapshots)

    if val_result["violation_count"] > 0:
        logger.error(
            "PIT validation 失敗：%d 筆違規",
            val_result["violation_count"],
        )
        for v in val_result["sample_violations"]:
            logger.error("  VIOLATION: %s", v)
        if val_result["violation_count"] / max(1, val_result["total"]) > 0.01:
            raise RuntimeError(
                f"PIT validation: {val_result['violation_count']} violations"
                " (>1% failure rate). Aborting backfill."
            )

    # ── Step 4: 統計摘要 ─────────────────────────────────────────────────────
    row_count = len(snapshots)
    available_count = val_result["availability_count"]
    available_rate = val_result["availability_rate"]

    workload_avail_count = sum(
        1 for s in snapshots if s.get("workload_available", False)
    )
    leverage_avail_count = sum(
        1 for s in snapshots if s.get("leverage_available", False)
    )
    perf_proxy_avail_count = sum(
        1 for s in snapshots if s.get("performance_proxy_available", False)
    )
    estimated_count = sum(1 for s in snapshots if s.get("estimated", True))
    fallback_count = sum(1 for s in snapshots if not s.get("bullpen_feature_available", False))

    # Source breakdown
    source_counts: dict[str, int] = {}
    for s in snapshots:
        src = s.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    summary = {
        "phase": "phase58_bullpen_usage_backfill",
        "feature_version": FEATURE_VERSION,
        "row_count": row_count,
        "expected_row_count": _EXPECTED_ROW_COUNT,
        "row_count_matches_expected": row_count == _EXPECTED_ROW_COUNT,
        "bullpen_feature_available_count": available_count,
        "bullpen_feature_available_rate": available_rate,
        "workload_available_count": workload_avail_count,
        "workload_available_rate": round(workload_avail_count / max(1, row_count), 4),
        "leverage_available_count": leverage_avail_count,
        "leverage_available_rate": round(leverage_avail_count / max(1, row_count), 4),
        "performance_proxy_available_count": perf_proxy_avail_count,
        "performance_proxy_available_rate": round(perf_proxy_avail_count / max(1, row_count), 4),
        "estimated_count": estimated_count,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / max(1, row_count), 4),
        "point_in_time_safe_count": val_result["safe_count"],
        "point_in_time_safe_rate": val_result["pit_safe_rate"],
        "audit_hash_present_count": val_result["audit_hash_present_count"],
        "audit_hash_present_rate": val_result["audit_hash_present_rate"],
        "forbidden_leakage_count": val_result["violation_count"],
        "source_breakdown": source_counts,
        "output_path": str(output_path),
        "dry_run": dry_run,
        "bundle_audit_hash": bundle.audit_hash,
        "timestamp": timestamp,
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }

    # ── Step 5: 寫入 output ───────────────────────────────────────────────────
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for snap in snapshots:
                f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        logger.info("已寫入 %d 筆到 %s", row_count, output_path)
    else:
        logger.info("DRY RUN: 不寫入 %s", output_path)

    # ── Gate check ───────────────────────────────────────────────────────────
    if available_rate < 0.80:
        summary["gate"] = "DATA_GAP_REMAINS"
        logger.warning(
            "Gate = DATA_GAP_REMAINS (available_rate=%.1f%% < 80%%)",
            available_rate * 100,
        )
    else:
        summary["gate"] = "PROCEED_TO_EVALUATION"
        logger.info(
            "Gate = PROCEED_TO_EVALUATION (available_rate=%.1f%%)",
            available_rate * 100,
        )

    return summary


def _print_summary(summary: dict) -> None:
    """Print human-readable summary."""
    print("\n" + "="*60)
    print("Phase 58 — Bullpen Usage Backfill Summary")
    print("="*60)
    print(f"Feature Version : {summary['feature_version']}")
    print(f"Row Count       : {summary['row_count']} (expected {summary['expected_row_count']})")
    print(f"Count Match     : {'✓' if summary['row_count_matches_expected'] else '✗'}")
    print(f"Avail Rate      : {summary['bullpen_feature_available_rate']:.1%}")
    print(f"Workload Avail  : {summary['workload_available_rate']:.1%}")
    print(f"Leverage Avail  : {summary['leverage_available_rate']:.1%}")
    print(f"Perf Proxy Avail: {summary['performance_proxy_available_rate']:.1%}")
    print(f"Fallback Rate   : {summary['fallback_rate']:.1%}")
    print(f"PIT Safe Rate   : {summary['point_in_time_safe_rate']:.1%}")
    print(f"Audit Hash Rate : {summary['audit_hash_present_rate']:.1%}")
    print(f"Leakage Count   : {summary['forbidden_leakage_count']}")
    print(f"Gate            : {summary['gate']}")
    print(f"Candidate Patch : {summary['candidate_patch_created']}")
    print(f"Prod Modified   : {summary['production_modified']}")
    print("Source Breakdown:")
    for src, cnt in summary["source_breakdown"].items():
        print(f"  {src}: {cnt}")
    print("="*60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase58 Bullpen Usage Backfill")
    parser.add_argument("--print", action="store_true", dest="print_summary",
                        help="Print human-readable summary")
    parser.add_argument("--json", action="store_true", dest="print_json",
                        help="Print JSON summary to stdout")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Dry run (do not write output file)")
    args = parser.parse_args()

    summary = run_backfill(dry_run=args.dry_run)

    if args.print_summary:
        _print_summary(summary)

    if args.print_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
