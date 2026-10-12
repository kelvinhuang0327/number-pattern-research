"""
scripts/run_phase56_bullpen_backfill.py
=======================================
Phase 56 — Bullpen Feature Backfill Script

讀取 baseline JSONL，為每場 2025 MLB 比賽建立 bullpen 特徵記錄，
輸出至 mlb_2025_bullpen_features_phase56.jsonl。

執行方式：
    python scripts/run_phase56_bullpen_backfill.py [--print] [--json]

輸出：
    data/mlb_2025/derived/mlb_2025_bullpen_features_phase56.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True

注意：
    由於目前無 MLB 2025 牛棚實際使用資料，所有特徵均為中性回退值
    (bullpen_feature_available = False)。
    系統已設計為：當 context 包含實際資料時可無縫升級。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from wbc_backend.features.mlb_bullpen_feature_builder import build_bullpen_features
from wbc_backend.features.mlb_bullpen_pit_validator import (
    validate_bullpen_features,
    validate_bullpen_batch,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase56_bullpen_v1"

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
)
_OUTPUT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_bullpen_features_phase56.jsonl"
)


def _load_baseline(path: Path) -> list[dict]:
    """載入 baseline JSONL。"""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    logger.info("Baseline 載入：%d 筆", len(rows))
    return rows


def build_bullpen_row(base_row: dict) -> dict:
    """
    為單場比賽建立 bullpen 特徵記錄。

    由於沒有歷史牛棚使用資料，傳入 context=None，
    所有特徵使用中性回退值。
    """
    game_id = base_row.get("game_id", "")
    game_date = base_row.get("game_date", "")
    home_team = base_row.get("home_team", "")
    away_team = base_row.get("away_team", "")

    features = build_bullpen_features(base_row, context=None)

    # Validate PIT safety
    pit_result = validate_bullpen_features(features, game_date)
    if not pit_result.is_safe:
        logger.error(
            "game_id=%s PIT 驗證失敗: %s", game_id, pit_result.violations
        )

    return {
        "game_id": game_id,
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        # Home bullpen features
        "home_bullpen_fatigue_3d": features["home_bullpen_fatigue_3d"],
        "home_bullpen_fatigue_7d": features["home_bullpen_fatigue_7d"],
        "home_reliever_b2b_count": features["home_reliever_b2b_count"],
        "home_bullpen_recent_era_proxy": features["home_bullpen_recent_era_proxy"],
        "home_late_game_leverage_usage_proxy": features["home_late_game_leverage_usage_proxy"],
        # Away bullpen features
        "away_bullpen_fatigue_3d": features["away_bullpen_fatigue_3d"],
        "away_bullpen_fatigue_7d": features["away_bullpen_fatigue_7d"],
        "away_reliever_b2b_count": features["away_reliever_b2b_count"],
        "away_bullpen_recent_era_proxy": features["away_bullpen_recent_era_proxy"],
        "away_late_game_leverage_usage_proxy": features["away_late_game_leverage_usage_proxy"],
        # Delta features
        "bullpen_fatigue_delta_3d": features["bullpen_fatigue_delta_3d"],
        "bullpen_fatigue_delta_7d": features["bullpen_fatigue_delta_7d"],
        # Metadata
        "bullpen_feature_available": features["bullpen_feature_available"],
        "bullpen_feature_source": features["bullpen_feature_source"],
        "point_in_time_safe": features["point_in_time_safe"],
        "fallback_reason": features["fallback_reason"],
        "audit_hash": features["audit_hash"],
        "feature_version": features["feature_version"],
        "pit_validation_passed": pit_result.is_safe,
        # Hard rules
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }


def run_backfill(
    baseline_path: Path = _BASELINE_JSONL,
    output_path: Path = _OUTPUT_JSONL,
    dry_run: bool = False,
) -> dict:
    """
    執行完整 bullpen feature backfill。

    Returns:
        Summary dict with stats.
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    base_rows = _load_baseline(baseline_path)
    bullpen_rows: list[dict] = []

    for base_row in base_rows:
        row = build_bullpen_row(base_row)
        bullpen_rows.append(row)

    # Validate batch
    batch_result = validate_bullpen_batch(bullpen_rows)
    avail_count = batch_result["availability_count"]
    avail_rate = batch_result["availability_rate"]

    summary = {
        "total_rows": len(bullpen_rows),
        "pit_safe_count": batch_result["safe_count"],
        "pit_safe_rate": batch_result["pit_safe_rate"],
        "bullpen_feature_available_count": avail_count,
        "bullpen_feature_available_rate": avail_rate,
        "violation_count": batch_result["violation_count"],
        "sample_violations": batch_result["sample_violations"],
        "output_path": str(output_path),
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for row in bullpen_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info(
            "Backfill 完成：%d 筆寫入 %s (availability=%.1f%%)",
            len(bullpen_rows), output_path, avail_rate * 100,
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase56 Bullpen Feature Backfill")
    parser.add_argument("--print", action="store_true", help="印出摘要至 stdout")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出摘要")
    parser.add_argument("--output", type=Path, default=_OUTPUT_JSONL, help="輸出路徑")
    parser.add_argument("--dry-run", action="store_true", help="不寫入檔案（測試用）")
    args = parser.parse_args()

    summary = run_backfill(
        baseline_path=_BASELINE_JSONL,
        output_path=args.output,
        dry_run=args.dry_run,
    )

    if args.json or args.print:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"[Phase56 Backfill] 完成")
        print(f"  總筆數:              {summary['total_rows']}")
        print(f"  PIT safe rate:       {summary['pit_safe_rate']:.1%}")
        print(f"  Feature 可用率:      {summary['bullpen_feature_available_rate']:.1%}")
        print(f"  Violation 筆數:      {summary['violation_count']}")
        print(f"  輸出:                {summary['output_path']}")
        print(f"  CANDIDATE_PATCH:     {summary['candidate_patch_created']}")
        print(f"  PRODUCTION_MODIFIED: {summary['production_modified']}")


if __name__ == "__main__":
    main()
