"""
scripts/run_phase58_bullpen_feature_injection.py
================================================
Phase 58 — Bullpen Feature Injection

功能：
  將 Phase58 bullpen context 轉換為調整後機率，
  重用 mlb_bullpen_feature_injection.py。

執行方式：
    python scripts/run_phase58_bullpen_feature_injection.py [--dry-run] [--print] [--json]

輸入：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase58_bullpen_context_v1.jsonl

輸出：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase58_bullpen_injected_v1.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True
    max_adjustment <= 0.015
    若 bullpen_feature_available = False → adjustment = 0
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

from wbc_backend.features.mlb_bullpen_feature_injection import (
    apply_bullpen_adjustment,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    _MAX_TOTAL_ADJUSTMENT as MAX_TOTAL_ADJUSTMENT,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
FEATURE_VERSION: str = "phase58_bullpen_injected_v1"

# ─── Paths ────────────────────────────────────────────────────────────────────
_CONTEXT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase58_bullpen_context_v1.jsonl"
)
_OUTPUT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase58_bullpen_injected_v1.jsonl"
)


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _extract_bullpen_features(context_row: dict) -> dict:
    """
    從 context row 中提取 bullpen features dict，
    格式與 mlb_bullpen_feature_builder.py 輸出相容。
    """
    return {
        # Phase56 格式的 fatigue/era/leverage 欄位
        "home_bullpen_fatigue_3d": (
            context_row.get("home_bullpen_outs_3d", 0.0) / 27.0
            if context_row.get("workload_available", False)
            else 0.0
        ),
        "home_bullpen_fatigue_7d": (
            context_row.get("home_bullpen_outs_7d", 0.0) / 63.0
            if context_row.get("workload_available", False)
            else 0.0
        ),
        "home_reliever_b2b_count": context_row.get("home_reliever_b2b_count", 0),
        "home_bullpen_recent_era_proxy": context_row.get(
            "home_bullpen_recent_era_proxy", 4.10
        ),
        "home_late_game_leverage_usage_proxy": context_row.get(
            "home_late_game_leverage_usage_proxy", 0.0
        ),
        "away_bullpen_fatigue_3d": (
            context_row.get("away_bullpen_outs_3d", 0.0) / 27.0
            if context_row.get("workload_available", False)
            else 0.0
        ),
        "away_bullpen_fatigue_7d": (
            context_row.get("away_bullpen_outs_7d", 0.0) / 63.0
            if context_row.get("workload_available", False)
            else 0.0
        ),
        "away_reliever_b2b_count": context_row.get("away_reliever_b2b_count", 0),
        "away_bullpen_recent_era_proxy": context_row.get(
            "away_bullpen_recent_era_proxy", 4.10
        ),
        "away_late_game_leverage_usage_proxy": context_row.get(
            "away_late_game_leverage_usage_proxy", 0.0
        ),
        "bullpen_fatigue_delta_3d": context_row.get("bullpen_fatigue_delta_3d", 0.0),
        "bullpen_fatigue_delta_7d": context_row.get("bullpen_fatigue_delta_7d", 0.0),
        "bullpen_feature_available": context_row.get("bullpen_feature_available", False),
        "bullpen_feature_source": context_row.get("source", "phase58_proxy"),
        "point_in_time_safe": context_row.get("point_in_time_safe", True),
        "fallback_reason": context_row.get("fallback_reason", ""),
        "feature_version": FEATURE_VERSION,
        "audit_hash": context_row.get("bullpen_usage_audit_hash", ""),
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }


def run_injection(
    context_path: Path = _CONTEXT_JSONL,
    output_path: Path = _OUTPUT_JSONL,
    dry_run: bool = False,
) -> dict:
    """
    執行 Phase58 bullpen feature injection。

    Returns:
        Summary dict
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    logger.info("Phase58 Bullpen Feature Injection 開始")
    logger.info("Context: %s", context_path)
    logger.info("Output: %s", output_path)

    if not context_path.exists():
        raise FileNotFoundError(f"Context JSONL 不存在: {context_path}")

    context_rows = _load_jsonl(context_path)
    logger.info("Context rows: %d", len(context_rows))

    injected_rows: list[dict] = []
    rows_adjusted = 0
    total_abs_adjustment = 0.0
    max_abs_adjustment = 0.0
    adjustment_values: list[float] = []

    for row in context_rows:
        base_prob = row.get("model_home_prob", 0.5)
        bullpen_features = _extract_bullpen_features(row)

        result = apply_bullpen_adjustment(base_prob, bullpen_features)

        injected = dict(row)
        injected["phase58_model_home_prob"] = result.adjusted_model_home_prob
        injected["phase58_bullpen_adjustment"] = result.bullpen_adjustment
        injected["phase58_adjustment_components"] = result.adjustment_components
        injected["phase58_bullpen_feature_available"] = result.bullpen_feature_available
        injected["phase58_feature_effect_mode"] = result.feature_effect_mode
        injected["phase58_adjustment_capped"] = result.adjustment_capped
        injected["phase58_feature_version"] = FEATURE_VERSION
        injected["candidate_patch_created"] = False
        injected["production_modified"] = False
        injected["diagnostic_only"] = True

        if abs(result.bullpen_adjustment) > 1e-9:
            rows_adjusted += 1
            abs_adj = abs(result.bullpen_adjustment)
            total_abs_adjustment += abs_adj
            max_abs_adjustment = max(max_abs_adjustment, abs_adj)
            adjustment_values.append(result.bullpen_adjustment)

        injected_rows.append(injected)

    rows_total = len(injected_rows)
    adjusted_rate = round(rows_adjusted / max(1, rows_total), 4)
    mean_abs_adjustment = (
        total_abs_adjustment / rows_adjusted if rows_adjusted > 0 else 0.0
    )

    feature_effect_mode = "MODEL_AFFECTING" if rows_adjusted > 0 else "REPORT_ONLY"

    summary = {
        "phase": "phase58_bullpen_feature_injection",
        "feature_version": FEATURE_VERSION,
        "rows_total": rows_total,
        "rows_adjusted": rows_adjusted,
        "adjusted_rate": adjusted_rate,
        "mean_abs_adjustment": round(mean_abs_adjustment, 6),
        "max_abs_adjustment": round(max_abs_adjustment, 6),
        "feature_effect_mode": feature_effect_mode,
        "max_allowed_adjustment": MAX_TOTAL_ADJUSTMENT,
        "adjustment_within_limit": max_abs_adjustment <= MAX_TOTAL_ADJUSTMENT,
        "output_path": str(output_path),
        "dry_run": dry_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for row in injected_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("已寫入 %d 筆到 %s", rows_total, output_path)
    else:
        logger.info("DRY RUN: 不寫入 %s", output_path)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase58 Bullpen Feature Injection")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--print", action="store_true", dest="print_summary")
    parser.add_argument("--json", action="store_true", dest="print_json")
    args = parser.parse_args()

    summary = run_injection(dry_run=args.dry_run)

    if args.print_summary:
        print("\n" + "="*60)
        print("Phase 58 — Bullpen Feature Injection Summary")
        print("="*60)
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("="*60)

    if args.print_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
