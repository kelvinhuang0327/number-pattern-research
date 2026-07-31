"""
Phase 52 — Inject SP Features into Phase48 P0 Context
======================================================
讀取 Phase48 JSONL + Phase52 SP features JSONL，
更新 p0_features.sp_fip_delta 與 sp_fip_delta_available，
輸出 phase52_sp_context_v1 JSONL。

執行方式：
    python scripts/run_phase52_inject_sp_to_phase48.py [--print] [--json]

輸出：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    不可改 home_win
    不可改 market_home_prob_no_vig
    不可改原始 game metadata
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_PHASE48_JSONL  = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase48_p0_v1.jsonl"
_SP_FEATURES    = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_starting_pitcher_features_phase52.jsonl"
_OUTPUT_JSONL   = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"

CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
FEATURE_VERSION: str = "phase52_sp_context_v1"

# 不可修改的欄位（leakage guard + production safety）
_IMMUTABLE_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "market_home_prob_no_vig",
    "market_away_prob_no_vig",
    "home_ml",
    "away_ml",
    "schema_version",
    "season",
    "game_id",
    "game_date",
    "dedupe_key",
    "home_team",
    "away_team",
    "model_home_prob",
    "model_version",
    "split_id",
    "train_window_start",
    "train_window_end",
    "test_window_start",
    "test_window_end",
    "prediction_time_utc",
    "odds_snapshot_time_utc",
    "source_backtest",
})


def _load_sp_features(path: Path) -> dict[str, dict]:
    """載入 SP features JSONL，建立 game_id → record 映射。"""
    result: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            gid = row.get("game_id", "")
            if gid:
                result[gid] = row
    logger.info("SP features 載入：%d 筆", len(result))
    return result


def _compute_sp_context_audit_hash(
    game_id: str,
    sp_fip_delta: float,
    sp_fip_delta_available: bool,
    stat_source: str,
) -> str:
    payload = f"{game_id}|{sp_fip_delta:.4f}|{sp_fip_delta_available}|{stat_source}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def inject_sp_to_phase48_row(phase48_row: dict, sp_record: dict | None) -> dict:
    """
    將 SP feature 注入 Phase48 row 的 p0_features。

    規則：
    - 更新 p0_features.sp_fip_delta
    - 更新 p0_features.sp_fip_delta_available
    - 保留 park_run_factor / season_game_index（不修改）
    - 新增 sp_context_source / sp_context_audit_hash
    - 不修改任何 _IMMUTABLE_FIELDS
    """
    import copy
    row = copy.deepcopy(phase48_row)

    # Validate: 不修改 immutable fields
    game_id = row.get("game_id", "")
    p0 = dict(row.get("p0_features", {}))

    if sp_record:
        new_fip_delta = sp_record.get("sp_fip_delta", 0.0)
        new_available = sp_record.get("sp_fip_delta_available", False)
        stat_source = sp_record.get("stat_source", "unknown")
        sp_home_name = sp_record.get("home_probable_pitcher_name", "")
        sp_away_name = sp_record.get("away_probable_pitcher_name", "")
        sp_context_audit_hash = _compute_sp_context_audit_hash(
            game_id, new_fip_delta, new_available, stat_source
        )
    else:
        new_fip_delta = 0.0
        new_available = False
        stat_source = "no_sp_record"
        sp_home_name = ""
        sp_away_name = ""
        sp_context_audit_hash = ""

    # 更新 p0_features（只改 SP 相關欄位）
    p0["sp_fip_delta"] = new_fip_delta
    p0["sp_fip_delta_available"] = new_available

    # 新增 SP context 欄位
    p0["sp_home_pitcher"] = sp_home_name
    p0["sp_away_pitcher"] = sp_away_name
    p0["sp_context_source"] = stat_source
    p0["sp_context_audit_hash"] = sp_context_audit_hash

    # 更新 feature_version
    p0["feature_version"] = FEATURE_VERSION

    # 重新計算 feature_audit_hash
    audit_payload = f"{game_id}|{p0.get('sp_fip_delta', 0.0):.4f}|{p0.get('park_run_factor', 0.0):.4f}|{p0.get('season_game_index', 0.0):.6f}"
    p0["feature_audit_hash"] = hashlib.sha256(audit_payload.encode()).hexdigest()

    row["p0_features"] = p0
    row["feature_audit_hash"] = p0["feature_audit_hash"]

    return row


def run(
    phase48_path: Path = _PHASE48_JSONL,
    sp_features_path: Path = _SP_FEATURES,
    output_path: Path = _OUTPUT_JSONL,
) -> dict:
    """
    執行 SP → Phase48 注入 pipeline。

    Returns:
        summary dict
    """
    logger.info("Phase 52 SP Context Injection 開始")
    logger.info("  phase48:     %s", phase48_path)
    logger.info("  sp_features: %s", sp_features_path)
    logger.info("  output:      %s", output_path)

    # 1. 載入資料
    sp_map = _load_sp_features(sp_features_path)
    output_rows: list[dict] = []
    stats = {
        "rows_total": 0,
        "sp_injected": 0,
        "sp_missing": 0,
        "sp_fip_available": 0,
        "sp_fip_unavailable": 0,
        "fip_delta_nonzero": 0,
    }

    with open(phase48_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p48_row = json.loads(line)
            game_id = p48_row.get("game_id", "")

            sp_record = sp_map.get(game_id)
            injected_row = inject_sp_to_phase48_row(p48_row, sp_record)
            output_rows.append(injected_row)

            stats["rows_total"] += 1
            if sp_record:
                stats["sp_injected"] += 1
            else:
                stats["sp_missing"] += 1

            p0 = injected_row.get("p0_features", {})
            if p0.get("sp_fip_delta_available"):
                stats["sp_fip_available"] += 1
            else:
                stats["sp_fip_unavailable"] += 1

            if abs(p0.get("sp_fip_delta", 0.0)) > 0.0001:
                stats["fip_delta_nonzero"] += 1

    total = stats["rows_total"]

    # 2. 寫出 JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info("寫出 %d 行至 %s", total, output_path)

    sp_avail_rate = stats["sp_fip_available"] / max(total, 1)
    inject_rate = stats["sp_injected"] / max(total, 1)
    nonzero_rate = stats["fip_delta_nonzero"] / max(total, 1)

    summary = {
        "rows_total": total,
        "sp_injected": stats["sp_injected"],
        "sp_missing": stats["sp_missing"],
        "inject_rate": round(inject_rate, 4),
        "sp_fip_delta_available": stats["sp_fip_available"],
        "sp_fip_delta_availability_rate": round(sp_avail_rate, 4),
        "fip_delta_nonzero": stats["fip_delta_nonzero"],
        "fip_delta_nonzero_rate": round(nonzero_rate, 4),
        "feature_version": FEATURE_VERSION,
        "output_path": str(output_path),
        "candidate_patch_created": False,
        "production_modified": False,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    logger.info("=== Phase 52 SP Context Injection 完成 ===")
    logger.info("  inject_rate:            %.1f%%", inject_rate * 100)
    logger.info("  sp_fip_availability:    %.1f%%", sp_avail_rate * 100)
    logger.info("  fip_delta_nonzero_rate: %.1f%%", nonzero_rate * 100)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 52 SP → Phase48 Injection")
    parser.add_argument("--phase48",     type=Path, default=_PHASE48_JSONL)
    parser.add_argument("--sp-features", type=Path, default=_SP_FEATURES)
    parser.add_argument("--output",      type=Path, default=_OUTPUT_JSONL)
    parser.add_argument("--print", action="store_true", dest="print_summary")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    summary = run(
        phase48_path=args.phase48,
        sp_features_path=args.sp_features,
        output_path=args.output,
    )

    if args.print_summary or args.json_output:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
