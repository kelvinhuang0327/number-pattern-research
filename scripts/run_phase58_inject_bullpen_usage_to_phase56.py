"""
scripts/run_phase58_inject_bullpen_usage_to_phase56.py
======================================================
Phase 58 — 注入 Phase58 Bullpen Usage 到 Phase56/52 Context

功能：
  將 phase58 bullpen usage snapshot 注入到 phase56 或 phase52 context JSONL，
  更新 bullpen_features 欄位，產生 phase58 context JSONL。

執行方式：
    python scripts/run_phase58_inject_bullpen_usage_to_phase56.py [--dry-run] [--print]

輸入：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
    （若不存在則使用 phase52 context）
    data/mlb_2025/derived/mlb_2025_bullpen_usage_phase58.jsonl

輸出：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase58_bullpen_context_v1.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True
    - 不可改 home_win
    - 不可改 market odds
    - 不可改 game metadata
    - 保留 p0_features / SP features
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase58_bullpen_context_v1"

# ─── Paths ────────────────────────────────────────────────────────────────────
_PHASE56_CONTEXT = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_PHASE52_CONTEXT = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
)
_BULLPEN_USAGE_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_bullpen_usage_phase58.jsonl"
)
_OUTPUT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase58_bullpen_context_v1.jsonl"
)

# ─── Fields NOT to overwrite ──────────────────────────────────────────────────
_IMMUTABLE_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "model_home_prob",
    "market_home_prob_no_vig",
    "market_away_prob_no_vig",
    "home_ml",
    "away_ml",
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "season",
    "schema_version",
})


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _build_bullpen_index(usage_rows: list[dict]) -> dict[str, dict]:
    """
    建立 game_id → bullpen_usage 的索引。
    """
    index: dict[str, dict] = {}
    for row in usage_rows:
        gid = row.get("game_id", "")
        if gid:
            index[gid] = row
    return index


def _inject_bullpen_to_row(
    context_row: dict,
    bullpen_usage: dict,
) -> dict:
    """
    將 bullpen usage 欄位注入 context row。

    規則：
    - 不覆蓋 _IMMUTABLE_FIELDS 中的欄位
    - 保留所有 SP features (sp_features_*)
    - 保留所有 p0 features (p0_features_*)
    - 更新 bullpen_features 命名空間欄位
    - 更新 feature_version 為 phase58
    """
    result = dict(context_row)

    # 注入 bullpen usage 欄位
    bullpen_keys = [
        "home_bullpen_outs_1d", "away_bullpen_outs_1d",
        "home_bullpen_outs_3d", "away_bullpen_outs_3d",
        "home_bullpen_outs_7d", "away_bullpen_outs_7d",
        "home_bullpen_outs_1d_available", "away_bullpen_outs_1d_available",
        "home_bullpen_outs_3d_available", "away_bullpen_outs_3d_available",
        "home_bullpen_outs_7d_available", "away_bullpen_outs_7d_available",
        "home_reliever_b2b_count", "away_reliever_b2b_count",
        "home_reliever_3in4_count", "away_reliever_3in4_count",
        "home_b2b_available", "away_b2b_available",
        "home_3in4_available", "away_3in4_available",
        "home_bullpen_recent_era_proxy", "away_bullpen_recent_era_proxy",
        "home_bullpen_recent_fip_proxy", "away_bullpen_recent_fip_proxy",
        "home_era_available", "away_era_available",
        "home_fip_available", "away_fip_available",
        "home_late_game_leverage_usage_proxy", "away_late_game_leverage_usage_proxy",
        "home_high_leverage_reliever_usage_3d", "away_high_leverage_reliever_usage_3d",
        "home_leverage_available", "away_leverage_available",
        "bullpen_fatigue_delta_3d", "bullpen_fatigue_delta_7d",
        "reliever_b2b_delta", "bullpen_recent_era_delta",
        "bullpen_recent_fip_delta", "leverage_usage_delta",
        "bullpen_feature_available", "workload_available",
        "leverage_available", "performance_proxy_available",
        "estimated", "availability_components", "fallback_reason",
        "snapshot_date", "source", "point_in_time_safe",
    ]

    for key in bullpen_keys:
        if key in bullpen_usage:
            result[key] = bullpen_usage[key]

    # 更新 audit 欄位
    result["bullpen_usage_source"] = bullpen_usage.get("source", "unknown")
    result["bullpen_usage_audit_hash"] = bullpen_usage.get("audit_hash", "")
    result["bullpen_usage_feature_version"] = bullpen_usage.get("feature_version", "")
    result["bullpen_usage_snapshot_date"] = bullpen_usage.get("snapshot_date", "")

    # 更新 feature_version
    result["phase58_feature_version"] = FEATURE_VERSION

    # Hard rules
    result["candidate_patch_created"] = False
    result["production_modified"] = False
    result["diagnostic_only"] = True

    return result


def run_injection(
    context_path: Path = _PHASE56_CONTEXT,
    bullpen_usage_path: Path = _BULLPEN_USAGE_JSONL,
    output_path: Path = _OUTPUT_JSONL,
    dry_run: bool = False,
) -> dict:
    """
    執行 Phase58 bullpen usage context injection。

    Returns:
        Summary dict
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    # 若 phase56 context 不存在，退回使用 phase52
    if not context_path.exists():
        logger.warning(
            "Phase56 context 不存在: %s，使用 phase52 context", context_path
        )
        context_path = _PHASE52_CONTEXT

    if not context_path.exists():
        raise FileNotFoundError(f"Context JSONL 不存在: {context_path}")
    if not bullpen_usage_path.exists():
        raise FileNotFoundError(f"Bullpen usage JSONL 不存在: {bullpen_usage_path}")

    logger.info("Context source: %s", context_path)
    logger.info("Bullpen usage: %s", bullpen_usage_path)
    logger.info("Output: %s", output_path)

    context_rows = _load_jsonl(context_path)
    bullpen_rows = _load_jsonl(bullpen_usage_path)

    logger.info("Context rows: %d", len(context_rows))
    logger.info("Bullpen usage rows: %d", len(bullpen_rows))

    bullpen_index = _build_bullpen_index(bullpen_rows)
    logger.info("Bullpen index: %d entries", len(bullpen_index))

    injected_rows: list[dict] = []
    match_count = 0
    no_match_count = 0

    for row in context_rows:
        gid = row.get("game_id", "")
        if gid in bullpen_index:
            injected = _inject_bullpen_to_row(row, bullpen_index[gid])
            match_count += 1
        else:
            # No match — preserve existing row with Phase58 metadata
            injected = dict(row)
            injected["phase58_feature_version"] = FEATURE_VERSION
            injected["bullpen_usage_source"] = "no_match"
            injected["bullpen_usage_audit_hash"] = ""
            injected["candidate_patch_created"] = False
            injected["production_modified"] = False
            injected["diagnostic_only"] = True
            no_match_count += 1
        injected_rows.append(injected)

    timestamp = datetime.now(timezone.utc).isoformat()

    summary = {
        "phase": "phase58_bullpen_usage_injection",
        "feature_version": FEATURE_VERSION,
        "context_source": str(context_path),
        "bullpen_usage_source": str(bullpen_usage_path),
        "output_path": str(output_path),
        "context_row_count": len(context_rows),
        "bullpen_index_count": len(bullpen_index),
        "match_count": match_count,
        "no_match_count": no_match_count,
        "match_rate": round(match_count / max(1, len(context_rows)), 4),
        "output_row_count": len(injected_rows),
        "dry_run": dry_run,
        "timestamp": timestamp,
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for row in injected_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("已寫入 %d 筆到 %s", len(injected_rows), output_path)
    else:
        logger.info("DRY RUN: 不寫入 %s", output_path)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase58 Bullpen Usage Context Injection"
    )
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--print", action="store_true", dest="print_summary")
    parser.add_argument("--json", action="store_true", dest="print_json")
    args = parser.parse_args()

    summary = run_injection(dry_run=args.dry_run)

    if args.print_summary:
        print("\n" + "="*60)
        print("Phase 58 — Bullpen Context Injection Summary")
        print("="*60)
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("="*60)

    if args.print_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
