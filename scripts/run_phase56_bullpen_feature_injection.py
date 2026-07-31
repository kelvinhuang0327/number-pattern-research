"""
scripts/run_phase56_bullpen_feature_injection.py
================================================
Phase 56 — Bullpen Feature Adjustment Injection Script

讀取 phase56_sp_bullpen_context JSONL，
套用 bullpen adjustment (apply_bullpen_adjustment)，
輸出 phase56_sp_bullpen_injected JSONL。

執行方式：
    python scripts/run_phase56_bullpen_feature_injection.py [--print] [--json]

輸出：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_injected_v1.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True
    最大調整幅度 ±0.015
    adjusted_prob clamp [0.01, 0.99]
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

from wbc_backend.features.mlb_bullpen_feature_injection import (
    apply_bullpen_adjustment,
    BullpenAdjustmentResult,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase56_sp_bullpen_injected_v1"

# ── Paths ─────────────────────────────────────────────────────────────────────
_CONTEXT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_OUTPUT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_injected_v1.jsonl"
)


def inject_bullpen_adjustment_to_row(context_row: dict) -> dict:
    """
    套用 bullpen adjustment 至單場記錄。

    - 讀取 model_home_prob 作為 base_model_prob
    - 讀取 bullpen_features 子字典
    - 呼叫 apply_bullpen_adjustment
    - 將 adjusted_model_home_prob 寫入 model_home_prob
    - 保留 original_model_home_prob
    - 添加 bullpen_adjustment + adjustment_components
    - feature_effect_mode = MODEL_AFFECTING | REPORT_ONLY
    - diagnostic_only = True
    - candidate_patch_created = False
    - production_modified = False
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    out = dict(context_row)

    base_prob = float(context_row.get("model_home_prob", 0.5))
    bullpen_features = context_row.get("bullpen_features", {})

    adj_result: BullpenAdjustmentResult = apply_bullpen_adjustment(
        base_model_prob=base_prob,
        bullpen_features=bullpen_features,
    )

    # Write adjustment fields
    out["original_model_home_prob"] = adj_result.original_model_home_prob
    out["model_home_prob"] = adj_result.adjusted_model_home_prob
    out["bullpen_adjustment"] = adj_result.bullpen_adjustment
    out["bullpen_adjustment_components"] = adj_result.adjustment_components
    out["feature_effect_mode"] = adj_result.feature_effect_mode
    out["bullpen_adjustment_capped"] = adj_result.adjustment_capped
    out["bullpen_fallback_applied"] = adj_result.fallback_applied
    out["bullpen_injection_audit_hash"] = adj_result.audit_hash

    # Hard rule flags
    out["diagnostic_only"] = True
    out["candidate_patch_created"] = False
    out["production_modified"] = False
    out["feature_version"] = FEATURE_VERSION

    return out


def run_injection(
    context_path: Path = _CONTEXT_JSONL,
    output_path: Path = _OUTPUT_JSONL,
    dry_run: bool = False,
) -> dict:
    """
    執行完整 bullpen adjustment injection。

    Returns:
        Summary dict.
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    context_rows: list[dict] = []
    with open(context_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            context_rows.append(json.loads(line))
    logger.info("Context rows 載入：%d 筆", len(context_rows))

    output_rows: list[dict] = []
    model_affecting_count = 0
    fallback_count = 0
    total_adjustment = 0.0
    capped_count = 0

    for row in context_rows:
        out_row = inject_bullpen_adjustment_to_row(row)
        output_rows.append(out_row)

        if out_row.get("feature_effect_mode") == "MODEL_AFFECTING":
            model_affecting_count += 1
        if out_row.get("bullpen_fallback_applied", True):
            fallback_count += 1
        total_adjustment += abs(out_row.get("bullpen_adjustment", 0.0))
        if out_row.get("bullpen_adjustment_capped", False):
            capped_count += 1

    n = len(output_rows)
    summary = {
        "total_rows": n,
        "model_affecting_count": model_affecting_count,
        "model_affecting_rate": round(model_affecting_count / max(1, n), 4),
        "fallback_applied_count": fallback_count,
        "fallback_applied_rate": round(fallback_count / max(1, n), 4),
        "avg_abs_adjustment": round(total_adjustment / max(1, n), 6),
        "capped_count": capped_count,
        "output_path": str(output_path),
        "feature_version": FEATURE_VERSION,
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for row in output_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info(
            "注入完成：%d 筆寫入 %s (MODEL_AFFECTING=%d)",
            n, output_path, model_affecting_count,
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase56 Bullpen Feature Adjustment Injection"
    )
    parser.add_argument("--print", action="store_true", help="印出摘要至 stdout")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出摘要")
    parser.add_argument("--dry-run", action="store_true", help="不寫入檔案（測試用）")
    args = parser.parse_args()

    summary = run_injection(dry_run=args.dry_run)

    if args.json or args.print:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("[Phase56 Bullpen Injection] 完成")
        print(f"  總筆數:              {summary['total_rows']}")
        print(f"  Model Affecting 率:  {summary['model_affecting_rate']:.1%}")
        print(f"  Fallback 率:         {summary['fallback_applied_rate']:.1%}")
        print(f"  平均調整幅度:         {summary['avg_abs_adjustment']:.6f}")
        print(f"  Capped 筆數:         {summary['capped_count']}")
        print(f"  輸出:                {summary['output_path']}")
        print(f"  CANDIDATE_PATCH:     {summary['candidate_patch_created']}")
        print(f"  PRODUCTION_MODIFIED: {summary['production_modified']}")


if __name__ == "__main__":
    main()
