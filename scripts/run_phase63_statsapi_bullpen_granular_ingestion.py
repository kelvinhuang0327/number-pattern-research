"""
scripts/run_phase63_statsapi_bullpen_granular_ingestion.py
==========================================================
Phase 63 — StatsAPI-based Bullpen Granular Ingestion Runner

目的：
  1. 從 Phase 62 fixture 解析 NormalizedReliefAppearance artifacts
  2. 為每個 (prediction_date, team) 組合計算 SSOT feature artifacts
  3. 輸出三份 diagnostic artifacts：
       reports/phase63_bullpen_relief_appearances_20260506.jsonl
       reports/phase63_bullpen_ssot_features_20260506.jsonl
       reports/phase63_statsapi_bullpen_granular_ingestion_20260506.json
  4. 不呼叫 live API；fixture-only 驗證

安全限制：
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED      = False
  - ALPHA_MODIFIED           = False
  - DIAGNOSTIC_ONLY          = True
  - Artifacts 寫入 reports/ (diagnostic 目錄)，不覆蓋 production dataset

使用方式：
  cd /path/to/Betting-pool
  python scripts/run_phase63_statsapi_bullpen_granular_ingestion.py

輸出：
  reports/phase63_bullpen_relief_appearances_20260506.jsonl
  reports/phase63_bullpen_ssot_features_20260506.jsonl
  reports/phase63_statsapi_bullpen_granular_ingestion_20260506.json
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path when run as a script
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.features.mlb_bullpen_granular_ingestion import (
    PHASE63_MODULE_VERSION,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    GATE_RESULT as PHASE62_GATE_RESULT,
    parse_fixture_to_phase63_ingestion,
    compute_ssot_feature_artifact,
    build_phase63_diagnostic_report,
    SSOTFeatureArtifact,
    NormalizedReliefAppearance,
)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "phase62_boxscore_fixtures.json"
REPORTS_DIR = _REPO_ROOT / "reports"
APPEARANCES_OUT = REPORTS_DIR / "phase63_bullpen_relief_appearances_20260506.jsonl"
FEATURES_OUT = REPORTS_DIR / "phase63_bullpen_ssot_features_20260506.jsonl"
REPORT_OUT = REPORTS_DIR / "phase63_statsapi_bullpen_granular_ingestion_20260506.json"

# Prediction configuration: compute SSOT features for these (prediction_date, team) pairs.
# Using fixture data from May 1–4 to predict for May 5.
PREDICTION_TARGETS: list[dict[str, str]] = [
    {
        "prediction_game_id": "MLB-20250505-PRED-NEW_YORK_YANKEES",
        "game_date": "2025-05-05",
        "team": "New York Yankees",
    },
    {
        "prediction_game_id": "MLB-20250505-PRED-BOSTON_RED_SOX",
        "game_date": "2025-05-05",
        "team": "Boston Red Sox",
    },
    {
        "prediction_game_id": "MLB-20250505-PRED-HOUSTON_ASTROS",
        "game_date": "2025-05-05",
        "team": "Houston Astros",
    },
    {
        "prediction_game_id": "MLB-20250505-PRED-TAMPA_BAY_RAYS",
        "game_date": "2025-05-05",
        "team": "Tampa Bay Rays",
    },
]


def _normalize_to_json(rec: NormalizedReliefAppearance) -> dict:
    """Serialize NormalizedReliefAppearance to JSON-safe dict."""
    return {
        "game_id": rec.game_id,
        "game_date": rec.game_date,
        "team": rec.team,
        "opponent": rec.opponent,
        "pitcher_id": rec.pitcher_id,
        "pitcher_name": rec.pitcher_name,
        "appeared_order": rec.appeared_order,
        "starter_flag": rec.starter_flag,
        "opener_flag": rec.opener_flag,
        "reliever_flag": rec.reliever_flag,
        "innings_pitched": round(rec.innings_pitched, 6),
        "outs_recorded": rec.outs_recorded,
        "pitches_thrown": rec.pitches_thrown,
        "source": rec.source,
        "source_game_id": rec.source_game_id,
        "audit_hash": rec.audit_hash,
    }


def _artifact_to_json(art: SSOTFeatureArtifact) -> dict:
    """Serialize SSOTFeatureArtifact to JSON-safe dict."""
    return {
        "prediction_game_id": art.prediction_game_id,
        "game_date": art.game_date,
        "team": art.team,
        "bullpen_usage_last_1d": art.bullpen_usage_last_1d,
        "bullpen_usage_last_3d": art.bullpen_usage_last_3d,
        "bullpen_usage_last_5d": art.bullpen_usage_last_5d,
        "reliever_back_to_back_count": art.reliever_back_to_back_count,
        "reliever_three_in_four_days_count": art.reliever_three_in_four_days_count,
        "closer_used_last_1d": art.closer_used_last_1d,
        "closer_used_last_2d": art.closer_used_last_2d,
        "high_leverage_reliever_used_last_1d": art.high_leverage_reliever_used_last_1d,
        "high_leverage_reliever_workload_last_3d": art.high_leverage_reliever_workload_last_3d,
        "availability_map": art.availability_map,
        "pit_window_map": art.pit_window_map,
        "audit_hash": art.audit_hash,
        "module_version": art.module_version,
        "diagnostic_only": art.diagnostic_only,
    }


def main() -> None:
    """Run Phase 63 ingestion pipeline; write diagnostic artifacts."""
    print(f"=== Phase 63 StatsAPI Bullpen Granular Ingestion Runner ===")
    print(f"Module: {PHASE63_MODULE_VERSION}")
    print(f"Phase62 Gate: {PHASE62_GATE_RESULT}")
    print(f"CANDIDATE_PATCH_CREATED = {CANDIDATE_PATCH_CREATED}")
    print(f"PRODUCTION_MODIFIED     = {PRODUCTION_MODIFIED}")
    print(f"ALPHA_MODIFIED          = {ALPHA_MODIFIED}")
    print()

    # ── Step 1: Parse fixture ──────────────────────────────────────────────
    print(f"[1/4] Parsing fixture: {FIXTURE_PATH}")
    if not FIXTURE_PATH.exists():
        print(f"ERROR: Fixture not found: {FIXTURE_PATH}")
        sys.exit(1)

    normalized, ingestion_result = parse_fixture_to_phase63_ingestion(FIXTURE_PATH)

    print(f"  Games parsed  : {ingestion_result.games_parsed}")
    print(f"  Games missing : {ingestion_result.games_missing}")
    print(f"  Appearances   : {len(normalized)}")
    print(f"  Errors        : {ingestion_result.errors or 'none'}")
    print()

    # ── Step 2: Write relief appearances JSONL ─────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[2/4] Writing relief appearances → {APPEARANCES_OUT.name}")
    with APPEARANCES_OUT.open("w", encoding="utf-8") as f:
        for rec in normalized:
            f.write(json.dumps(_normalize_to_json(rec), ensure_ascii=False) + "\n")
    print(f"  Written {len(normalized)} records")
    print()

    # ── Step 3: Compute SSOT feature artifacts ─────────────────────────────
    print(f"[3/4] Computing SSOT feature artifacts for {len(PREDICTION_TARGETS)} targets")
    ssot_artifacts: list[SSOTFeatureArtifact] = []
    for target in PREDICTION_TARGETS:
        art = compute_ssot_feature_artifact(
            ingestion_result.appearances,
            prediction_game_id=target["prediction_game_id"],
            game_date=target["game_date"],
            team=target["team"],
        )
        ssot_artifacts.append(art)
        print(f"  [{target['team']:25s}] "
              f"1d={str(art.bullpen_usage_last_1d):6s} "
              f"3d={str(art.bullpen_usage_last_3d):7s} "
              f"5d={str(art.bullpen_usage_last_5d):7s} "
              f"B2B={art.reliever_back_to_back_count} "
              f"3in4={art.reliever_three_in_four_days_count} "
              f"CL1d={'Y' if art.closer_used_last_1d else 'N'} "
              f"CL2d={'Y' if art.closer_used_last_2d else 'N'}")

    print()
    print(f"[3b/4] Writing SSOT feature artifacts → {FEATURES_OUT.name}")
    with FEATURES_OUT.open("w", encoding="utf-8") as f:
        for art in ssot_artifacts:
            f.write(json.dumps(_artifact_to_json(art), ensure_ascii=False) + "\n")
    print(f"  Written {len(ssot_artifacts)} artifacts")
    print()

    # ── Step 4: Build and write JSON diagnostic report ─────────────────────
    print(f"[4/4] Building Phase 63 diagnostic report → {REPORT_OUT.name}")
    report = build_phase63_diagnostic_report(normalized, ssot_artifacts, ingestion_result)

    with REPORT_OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Phase63 Gate : {report['phase63_gate']}")
    print(f"  Phase62 Gate : {report['phase62_gate']}")
    print(f"  Phase64 ready: {report['phase64_ready']}")
    print(f"  Audit hash   : {report['audit_hash']}")
    print()

    # ── Summary ────────────────────────────────────────────────────────────
    print("=== Summary ===")
    print(f"  relief_appearances JSONL  : {APPEARANCES_OUT}")
    print(f"  ssot_features JSONL       : {FEATURES_OUT}")
    print(f"  diagnostic report JSON    : {REPORT_OUT}")
    print()
    if report["phase63_gate"] == "GRANULAR_INGESTION_READY":
        print("PHASE_63_STATSAPI_BULLPEN_GRANULAR_INGESTION_VERIFIED")
    else:
        print(f"Gate: {report['phase63_gate']} — resolve before Phase 64.")


if __name__ == "__main__":
    main()
