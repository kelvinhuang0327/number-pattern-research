"""
scripts/run_phase56_inject_bullpen_to_phase52.py
================================================
Phase 56 — Inject Bullpen Features into Phase52 SP Context

讀取 Phase52 JSONL + Phase56 bullpen features JSONL，
將 bullpen_features 注入每場記錄，輸出 phase56_sp_bullpen_context_v1 JSONL。

執行方式：
    python scripts/run_phase56_inject_bullpen_to_phase52.py [--print] [--json]

輸出：
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
    DIAGNOSTIC_ONLY = True
    不可修改 home_win, market_home_prob_no_vig, game_id, game_date 等不變欄位
    不可修改原始 model_home_prob（context injection 不改機率）
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

# ── Constants ─────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase56_sp_bullpen_context_v1"

# ── Paths ─────────────────────────────────────────────────────────────────────
_PHASE52_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
)
_BULLPEN_FEATURES_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_bullpen_features_phase56.jsonl"
)
_OUTPUT_JSONL = (
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)

# 不可修改的欄位
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
    "prediction_time_utc",
    "odds_snapshot_time_utc",
    "source_backtest",
})


def _load_bullpen_features(path: Path) -> dict[str, dict]:
    """載入 bullpen features JSONL，建立 game_id → record 映射。"""
    result: dict[str, dict] = {}
    if not path.exists():
        logger.warning("Bullpen features JSONL 不存在：%s", path)
        return result
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            gid = row.get("game_id", "")
            if gid:
                result[gid] = row
    logger.info("Bullpen features 載入：%d 筆", len(result))
    return result


def _compute_context_audit_hash(
    game_id: str,
    bullpen_avail: bool,
    sp_fip_delta: float,
) -> str:
    payload = f"{game_id}|{bullpen_avail}|{sp_fip_delta:.4f}|{FEATURE_VERSION}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def inject_bullpen_to_phase52_row(
    phase52_row: dict,
    bullpen_record: dict | None,
) -> dict:
    """
    注入 bullpen features 至 phase52 record。

    規則：
    - 保留所有 p0_features（先發投手特徵）
    - 新增 bullpen_features 子字典
    - 更新 feature_version 為 phase56
    - 不修改任何 _IMMUTABLE_FIELDS
    - 不修改 model_home_prob（context injection 不改機率）
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    game_id = phase52_row.get("game_id", "")
    game_date = phase52_row.get("game_date", "")

    # Safety: validate no immutable field is being changed
    out = dict(phase52_row)

    if bullpen_record is not None:
        bullpen_avail = bullpen_record.get("bullpen_feature_available", False)
        bullpen_features_payload = {
            "home_bullpen_fatigue_3d": bullpen_record.get("home_bullpen_fatigue_3d", 0.0),
            "home_bullpen_fatigue_7d": bullpen_record.get("home_bullpen_fatigue_7d", 0.0),
            "home_reliever_b2b_count": bullpen_record.get("home_reliever_b2b_count", 0),
            "home_bullpen_recent_era_proxy": bullpen_record.get("home_bullpen_recent_era_proxy", 4.10),
            "home_late_game_leverage_usage_proxy": bullpen_record.get("home_late_game_leverage_usage_proxy", 0.0),
            "away_bullpen_fatigue_3d": bullpen_record.get("away_bullpen_fatigue_3d", 0.0),
            "away_bullpen_fatigue_7d": bullpen_record.get("away_bullpen_fatigue_7d", 0.0),
            "away_reliever_b2b_count": bullpen_record.get("away_reliever_b2b_count", 0),
            "away_bullpen_recent_era_proxy": bullpen_record.get("away_bullpen_recent_era_proxy", 4.10),
            "away_late_game_leverage_usage_proxy": bullpen_record.get("away_late_game_leverage_usage_proxy", 0.0),
            "bullpen_fatigue_delta_3d": bullpen_record.get("bullpen_fatigue_delta_3d", 0.0),
            "bullpen_fatigue_delta_7d": bullpen_record.get("bullpen_fatigue_delta_7d", 0.0),
            "bullpen_feature_available": bullpen_avail,
            "bullpen_feature_source": bullpen_record.get("bullpen_feature_source", "neutral_fallback"),
            "fallback_reason": bullpen_record.get("fallback_reason", "no_relief_pitcher_usage_data"),
            "point_in_time_safe": bullpen_record.get("point_in_time_safe", True),
            "audit_hash": bullpen_record.get("audit_hash", ""),
            "feature_version": bullpen_record.get("feature_version", "phase56_bullpen_v1"),
        }
        fallback_source = "bullpen_matched"
    else:
        bullpen_avail = False
        bullpen_features_payload = {
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "no_bullpen_record_for_game",
            "point_in_time_safe": True,
            "feature_version": "phase56_bullpen_v1",
        }
        fallback_source = "bullpen_not_found"

    out["bullpen_features"] = bullpen_features_payload

    # Extract SP FIP delta for audit hash
    p0 = out.get("p0_features", {})
    sp_fip_delta = float(p0.get("sp_fip_delta", 0.0)) if isinstance(p0, dict) else 0.0

    context_hash = _compute_context_audit_hash(game_id, bullpen_avail, sp_fip_delta)
    out["phase56_context_audit_hash"] = context_hash
    out["feature_version"] = FEATURE_VERSION
    out["bullpen_match_source"] = fallback_source
    out["candidate_patch_created"] = False
    out["production_modified"] = False
    out["diagnostic_only"] = True

    # Assert immutable fields not changed
    for immutable in _IMMUTABLE_FIELDS:
        if immutable in phase52_row and immutable in out:
            orig = phase52_row[immutable]
            curr = out[immutable]
            if orig != curr:
                logger.error(
                    "IMMUTABLE FIELD CHANGED: game_id=%s field=%s orig=%s curr=%s",
                    game_id, immutable, orig, curr,
                )

    return out


def run_injection(
    phase52_path: Path = _PHASE52_JSONL,
    bullpen_path: Path = _BULLPEN_FEATURES_JSONL,
    output_path: Path = _OUTPUT_JSONL,
    dry_run: bool = False,
) -> dict:
    """
    執行完整 bullpen → phase52 注入流程。

    Returns:
        Summary dict.
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    # Load phase52 rows
    phase52_rows: list[dict] = []
    with open(phase52_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            phase52_rows.append(json.loads(line))
    logger.info("Phase52 rows 載入：%d 筆", len(phase52_rows))

    # Load bullpen features
    bullpen_map = _load_bullpen_features(bullpen_path)

    output_rows: list[dict] = []
    matched = 0
    not_matched = 0

    for row in phase52_rows:
        gid = row.get("game_id", "")
        bullpen_rec = bullpen_map.get(gid)
        if bullpen_rec is not None:
            matched += 1
        else:
            not_matched += 1

        out_row = inject_bullpen_to_phase52_row(row, bullpen_rec)
        output_rows.append(out_row)

    available_count = sum(
        1 for r in output_rows
        if r.get("bullpen_features", {}).get("bullpen_feature_available", False)
    )

    summary = {
        "total_rows": len(output_rows),
        "matched_from_bullpen": matched,
        "not_matched_from_bullpen": not_matched,
        "match_rate": round(matched / max(1, len(output_rows)), 4),
        "bullpen_available_count": available_count,
        "bullpen_available_rate": round(available_count / max(1, len(output_rows)), 4),
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
            "注入完成：%d 筆寫入 %s (matched=%d, not_matched=%d)",
            len(output_rows), output_path, matched, not_matched,
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase56 Bullpen → Phase52 Context Injection"
    )
    parser.add_argument("--print", action="store_true", help="印出摘要至 stdout")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出摘要")
    parser.add_argument("--dry-run", action="store_true", help="不寫入檔案（測試用）")
    args = parser.parse_args()

    summary = run_injection(dry_run=args.dry_run)

    if args.json or args.print:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("[Phase56 Context Injection] 完成")
        print(f"  總筆數:              {summary['total_rows']}")
        print(f"  Bullpen 匹配率:      {summary['match_rate']:.1%}")
        print(f"  Bullpen 可用率:      {summary['bullpen_available_rate']:.1%}")
        print(f"  輸出:                {summary['output_path']}")
        print(f"  CANDIDATE_PATCH:     {summary['candidate_patch_created']}")
        print(f"  PRODUCTION_MODIFIED: {summary['production_modified']}")


if __name__ == "__main__":
    main()
