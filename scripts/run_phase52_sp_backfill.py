"""
Phase 52 — Starting Pitcher Feature Backfill Script
====================================================
讀取 baseline JSONL + asplayed CSV，建立每場先發投手的
point-in-time safe FIP 特徵記錄，輸出至 JSONL。

執行方式：
    python scripts/run_phase52_sp_backfill.py [--print] [--json] [--output PATH]

輸出：
    data/mlb_2025/derived/mlb_2025_starting_pitcher_features_phase52.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from data.mlb_sp_data_loader import (
    build_starter_match_records,
    load_asplayed_starters,
    load_baseline_rows,
)
from wbc_backend.features.mlb_sp_stat_snapshot import (
    build_pitcher_snapshot,
    compute_sp_fip_delta,
)
from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"
_ASPLAYED_CSV   = _ROOT / "data" / "mlb_2025" / "mlb-2025-asplayed.csv"
_OUTPUT_JSONL   = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_starting_pitcher_features_phase52.jsonl"

CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
FEATURE_VERSION: str = "phase52_sp_features_v1"


def _compute_row_audit_hash(game_id: str, home_fip: float, away_fip: float, stat_source_h: str, stat_source_a: str) -> str:
    payload = f"{game_id}|{home_fip:.3f}|{away_fip:.3f}|{stat_source_h}|{stat_source_a}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def build_sp_feature_row(
    game_id: str,
    game_date: str,
    home_team: str,
    away_team: str,
    home_pitcher_name: str,
    away_pitcher_name: str,
    matched: bool,
    fallback_reason: str | None,
) -> dict:
    """為單場比賽建立完整的 SP feature 記錄。"""
    home_snap = build_pitcher_snapshot(home_pitcher_name, game_date)
    away_snap = build_pitcher_snapshot(away_pitcher_name, game_date)

    sp_fip_delta, sp_fip_delta_available = compute_sp_fip_delta(home_snap, away_snap)

    # Point-in-time validation（使用 home snap 代表，兩者 snapshot_date 相同）
    pit_result = validate_point_in_time_snapshot(home_snap, game_date)

    audit_hash = _compute_row_audit_hash(
        game_id, home_snap.fip, away_snap.fip,
        home_snap.stat_source, away_snap.stat_source,
    )

    return {
        "game_id": game_id,
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_probable_pitcher_name": home_pitcher_name,
        "away_probable_pitcher_name": away_pitcher_name,

        # FIP 數據
        "home_sp_fip": home_snap.fip,
        "away_sp_fip": away_snap.fip,
        "sp_fip_delta": sp_fip_delta,
        "sp_fip_delta_available": sp_fip_delta_available,

        # K9 / BB9 / HR9
        "home_sp_k9": home_snap.k9,
        "away_sp_k9": away_snap.k9,
        "home_sp_bb9": home_snap.bb9,
        "away_sp_bb9": away_snap.bb9,
        "home_sp_hr9": home_snap.hr9,
        "away_sp_hr9": away_snap.hr9,

        # 元數據
        "snapshot_date": home_snap.snapshot_date,   # = game_date - 1
        "point_in_time_safe": pit_result.is_safe,
        "stat_source_home": home_snap.stat_source,
        "stat_source_away": away_snap.stat_source,
        "stat_source": (
            home_snap.stat_source
            if home_snap.stat_source == away_snap.stat_source
            else "mixed"
        ),
        "estimated": True,

        # Match 元數據
        "matched": matched,
        "fallback_reason": fallback_reason,

        # 稽核
        "feature_version": FEATURE_VERSION,
        "audit_hash": audit_hash,
        "pit_violations": pit_result.violations,
        "candidate_patch_created": False,
        "production_modified": False,
    }


def run(
    baseline_path: Path = _BASELINE_JSONL,
    asplayed_path: Path = _ASPLAYED_CSV,
    output_path: Path = _OUTPUT_JSONL,
) -> dict:
    """
    執行 Phase 52 SP backfill pipeline。

    Returns:
        summary dict
    """
    logger.info("Phase 52 SP Backfill 開始")
    logger.info("  baseline: %s", baseline_path)
    logger.info("  asplayed: %s", asplayed_path)
    logger.info("  output:   %s", output_path)

    # 1. 載入資料
    baseline_rows = load_baseline_rows(baseline_path)
    asplayed_map = load_asplayed_starters(asplayed_path)
    match_records = build_starter_match_records(
        baseline_rows=baseline_rows,
        asplayed_map=asplayed_map,
    )

    # 2. 建立 SP feature rows
    output_rows: list[dict] = []
    stats = {
        "matched": 0,
        "unmatched": 0,
        "home_known": 0,
        "away_known": 0,
        "both_known": 0,
        "none_known": 0,
        "sp_fip_available": 0,
        "pit_safe": 0,
        "pit_unsafe": 0,
        "stat_source_historical": 0,
        "stat_source_fallback": 0,
        "stat_source_mixed": 0,
    }

    from wbc_backend.features.mlb_sp_stat_snapshot import _PITCHER_FIP_TABLE

    for rec in match_records:
        # 反查 baseline row 以取得 game_id
        row_dict = build_sp_feature_row(
            game_id=rec.game_id,
            game_date=rec.game_date,
            home_team=rec.home_team,
            away_team=rec.away_team,
            home_pitcher_name=rec.home_probable_pitcher_name,
            away_pitcher_name=rec.away_probable_pitcher_name,
            matched=rec.matched,
            fallback_reason=rec.fallback_reason,
        )
        output_rows.append(row_dict)

        # 統計
        if rec.matched:
            stats["matched"] += 1
        else:
            stats["unmatched"] += 1

        h_known = rec.home_probable_pitcher_name in _PITCHER_FIP_TABLE
        a_known = rec.away_probable_pitcher_name in _PITCHER_FIP_TABLE
        if h_known: stats["home_known"] += 1
        if a_known: stats["away_known"] += 1
        if h_known and a_known: stats["both_known"] += 1
        if not h_known and not a_known: stats["none_known"] += 1

        if row_dict["sp_fip_delta_available"]: stats["sp_fip_available"] += 1
        if row_dict["point_in_time_safe"]: stats["pit_safe"] += 1
        else: stats["pit_unsafe"] += 1

        src = row_dict["stat_source"]
        if src == "historical_proxy": stats["stat_source_historical"] += 1
        elif src == "league_average_fallback": stats["stat_source_fallback"] += 1
        else: stats["stat_source_mixed"] += 1

    total = len(output_rows)

    # 3. 寫出 JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info("寫出 %d 行至 %s", total, output_path)

    # 4. 計算 summary
    sp_avail_rate = stats["sp_fip_available"] / max(total, 1)
    match_rate = stats["matched"] / max(total, 1)
    pit_safe_rate = stats["pit_safe"] / max(total, 1)

    summary = {
        "rows_total": total,
        "rows_matched": stats["matched"],
        "rows_unmatched": stats["unmatched"],
        "match_rate": round(match_rate, 4),
        "sp_fip_delta_available": stats["sp_fip_available"],
        "sp_fip_delta_availability_rate": round(sp_avail_rate, 4),
        "home_pitcher_known": stats["home_known"],
        "away_pitcher_known": stats["away_known"],
        "both_pitchers_known": stats["both_known"],
        "neither_pitcher_known": stats["none_known"],
        "point_in_time_safe_count": stats["pit_safe"],
        "point_in_time_safe_rate": round(pit_safe_rate, 4),
        "stat_source_historical": stats["stat_source_historical"],
        "stat_source_fallback": stats["stat_source_fallback"],
        "stat_source_mixed": stats["stat_source_mixed"],
        "output_path": str(output_path),
        "feature_version": FEATURE_VERSION,
        "candidate_patch_created": False,
        "production_modified": False,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    logger.info("=== Phase 52 SP Backfill 完成 ===")
    logger.info("  rows_total:              %d", total)
    logger.info("  match_rate:              %.1f%%", match_rate * 100)
    logger.info("  sp_fip_availability:     %.1f%%", sp_avail_rate * 100)
    logger.info("  point_in_time_safe_rate: %.1f%%", pit_safe_rate * 100)
    logger.info("  both_pitchers_known:     %d / %d", stats["both_known"], total)
    logger.info("  neither_pitcher_known:   %d / %d", stats["none_known"], total)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 52 SP Backfill")
    parser.add_argument("--baseline", type=Path, default=_BASELINE_JSONL)
    parser.add_argument("--asplayed", type=Path, default=_ASPLAYED_CSV)
    parser.add_argument("--output", type=Path, default=_OUTPUT_JSONL)
    parser.add_argument("--print", action="store_true", dest="print_summary")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    summary = run(
        baseline_path=args.baseline,
        asplayed_path=args.asplayed,
        output_path=args.output,
    )

    if args.print_summary or args.json_output:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
