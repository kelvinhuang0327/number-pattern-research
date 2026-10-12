"""
P83A — 2026 Live Accumulation First Snapshot / Awaiting Contract
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Verify P82C staging guard state.
  2. Discover 2026 prediction-only data in local repo (no API calls).
  3. Define expected 2026 prediction row schema.
  4. If 2026 rows with required schema exist: generate first snapshot.
  5. If no matching rows exist: generate formal awaiting-data contract.
  6. No odds, no EV, no CLV, no Kelly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Governance — MUST stay paper_only=True / diagnostic_only=True
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
}

ALLOWED_CLASSIFICATIONS = [
    "P83A_2026_FIRST_SNAPSHOT_READY",
    "P83A_2026_FIRST_SNAPSHOT_READY_SAMPLE_LIMITED",
    "P83A_2026_DATA_PRESENT_OUTCOMES_PENDING",
    "P83A_2026_DATA_INVALID",
    "P83A_AWAITING_2026_DATA",
    "P83A_BLOCKED_BY_MISSING_P82C_ARTIFACT",
    "P83A_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P83A is a 2026 live accumulation check only. "
    "Any snapshot computed is for research tracking — "
    "NOT a production deployment, NOT a betting recommendation, NOT a market-edge claim. "
    "paper_only=True, diagnostic_only=True."
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PATHS = {
    "p82c_json": ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json",
    "p82b_json": ROOT / "data/mlb_2025/derived/p82b_raw_paid_odds_data_policy_contract_summary.json",
    "p82a_json": ROOT / "data/mlb_2025/derived/p82a_real_legal_odds_intake_gate_summary.json",
    "p81_json":  ROOT / "data/mlb_2025/derived/p81_legal_odds_dataset_validator_contract_summary.json",
    "p80_json":  ROOT / "data/mlb_2025/derived/p80_market_edge_reentry_readiness_contract_summary.json",
    "p79b_json": ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "p79a_json": ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json",
    "p78_json":  ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json",
    "p77_json":  ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_json":  ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_json": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_json": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_json":  ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_json":  ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_json": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_json": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
}

OUTPUT_JSON   = ROOT / "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json"
OUTPUT_REPORT = ROOT / "report/p83a_2026_live_accumulation_first_snapshot_20260526.md"
PLAN_REPORT   = ROOT / "00-BettingPlan/20260526/p83a_2026_live_accumulation_first_snapshot_20260526.md"

# ---------------------------------------------------------------------------
# Discovery — candidate paths (local only, no API calls)
# ---------------------------------------------------------------------------
DISCOVERY_CANDIDATE_PATHS = [
    ROOT / "data/mlb_2026",
    ROOT / "data/mlb_2026/derived",
    ROOT / "data/mlb_2026/predictions",
    ROOT / "data/mlb_2026/live",
    ROOT / "outputs/online_validation",
]

# Extensions to scan for prediction rows
PRED_EXTENSIONS = {".jsonl", ".json", ".csv"}

# ---------------------------------------------------------------------------
# Expected 2026 prediction row schema
# ---------------------------------------------------------------------------
REQUIRED_SCHEMA_FIELDS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "predicted_side",
    "model_probability",
    "sp_fip_delta",
    "abs_sp_fip_delta",
    "source_prediction_version",
    "paper_only",
    "diagnostic_only",
    "odds_used",
    "market_edge_evaluated",
    "production_ready",
]

OPTIONAL_OUTCOME_FIELDS = [
    "actual_winner",
    "is_correct",
    "outcome_source",
    "outcome_available",
]

GOVERNANCE_REQUIRED_VALUES: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "odds_used": False,
    "market_edge_evaluated": False,
    "production_ready": False,
}

# ---------------------------------------------------------------------------
# Snapshot thresholds
# ---------------------------------------------------------------------------
SNAPSHOT_THRESHOLDS = {
    "smoke":       {"min_n": 1,   "label": "smoke_snapshot"},
    "sample_limited": {"min_n": 10,  "label": "first_sample_limited_report"},
    "checkpoint_1": {"min_n": 50,  "label": "checkpoint_1"},
    "checkpoint_2": {"min_n": 100, "label": "checkpoint_2"},
    "operational":  {"min_n": 200, "label": "operational_checkpoint"},
}

# ---------------------------------------------------------------------------
# Rule definitions (for categorising discovered rows)
# ---------------------------------------------------------------------------
PRIMARY_RULE = {
    "rule_id": "TIER_C_HOME_PLUS_AWAY_125",
    "description": "Home all (abs_sp_fip_delta >= 0.50) + Away (abs_sp_fip_delta >= 1.25)",
    "home_threshold": 0.50,
    "away_threshold": 1.25,
}

SHADOW_RULE = {
    "rule_id": "TIER_C_HOME_PLUS_AWAY_100",
    "description": "Home all (abs_sp_fip_delta >= 0.50) + Away (abs_sp_fip_delta >= 1.00)",
    "home_threshold": 0.50,
    "away_threshold": 1.00,
}

TIER_B_RULE = {
    "rule_id": "TIER_B_ABS_DELTA_025_050",
    "description": "0.25 <= abs_sp_fip_delta < 0.50 (research only, requires n>=200)",
    "delta_lo": 0.25,
    "delta_hi": 0.50,
}

TIER_A_WATCHLIST = {
    "rule_id": "TIER_A_ABS_DELTA_BELOW_025",
    "description": "abs_sp_fip_delta < 0.25 (watchlist only)",
    "delta_hi": 0.25,
}


# ---------------------------------------------------------------------------
# Step 1 — Verify P82C state
# ---------------------------------------------------------------------------
def step1_verify_p82c(p82c: dict) -> dict:
    cls = p82c.get("p82c_classification", "")
    sc = p82c.get("step2_scanner_contract", {})
    mock = p82c.get("step3_mock_fixture_scan", {})
    repo = p82c.get("step4_current_repo_dryrun", {})
    live_api = p82c.get("governance", {}).get("live_api_calls", -1)
    p82_status = p82c.get("p82_status", "")

    scan_modes_ok = len(sc.get("scan_modes", [])) >= 4
    mock_passed = mock.get("all_passed", False)
    overall_guard = repo.get("overall_guard_state", "")
    guard_clean = overall_guard in ("STAGE_CLEAN", "REVIEW_REQUIRED")
    p82_blocked = p82_status == "BLOCKED_NO_REAL_DATASET"

    ok = (
        cls == "P82C_STAGING_GUARD_DRYRUN_READY"
        and scan_modes_ok
        and mock_passed
        and guard_clean
        and live_api == 0
        and p82_blocked
    )

    return {
        "classification": cls,
        "classification_ok": cls == "P82C_STAGING_GUARD_DRYRUN_READY",
        "scan_modes_count": len(sc.get("scan_modes", [])),
        "scan_modes_ok": scan_modes_ok,
        "mock_all_passed": mock_passed,
        "overall_guard_state": overall_guard,
        "guard_state_ok": guard_clean,
        "live_api_calls": live_api,
        "live_api_ok": live_api == 0,
        "p82_status": p82_status,
        "p82_blocked": p82_blocked,
        "verification_ok": ok,
    }


# ---------------------------------------------------------------------------
# Step 2 — Discover 2026 prediction data
# ---------------------------------------------------------------------------
def _row_has_required_schema(row: dict) -> bool:
    """Check if a JSON row has all required schema fields."""
    return all(f in row for f in REQUIRED_SCHEMA_FIELDS)


def _row_is_2026(row: dict) -> bool:
    """Check if row has game_date in 2026."""
    gd = str(row.get("game_date", ""))
    return gd.startswith("2026")


def _row_governance_clean(row: dict) -> bool:
    """Check governance fields match required values."""
    for field, expected in GOVERNANCE_REQUIRED_VALUES.items():
        if row.get(field) != expected:
            return False
    return True


def _classify_row_tier(row: dict) -> str:
    """Classify row into PRIMARY / SHADOW / TIER_B / TIER_A / NONE."""
    abs_delta = row.get("abs_sp_fip_delta")
    predicted_side = row.get("predicted_side", "")
    if abs_delta is None:
        return "UNKNOWN"
    if predicted_side == "home" and abs_delta >= PRIMARY_RULE["home_threshold"]:
        return "TIER_C_ELIGIBLE"
    if predicted_side == "away" and abs_delta >= PRIMARY_RULE["away_threshold"]:
        return "PRIMARY_125"
    if predicted_side == "away" and abs_delta >= SHADOW_RULE["away_threshold"]:
        return "SHADOW_100_ONLY"
    if TIER_B_RULE["delta_lo"] <= abs_delta < TIER_B_RULE["delta_hi"]:
        return "TIER_B"
    if abs_delta < TIER_A_WATCHLIST["delta_hi"]:
        return "TIER_A_WATCHLIST"
    return "NONE"


def step2_discover_2026_data() -> dict:
    """Search local paths only. No API calls."""
    found_files: list[dict] = []
    checked_paths: list[str] = []
    not_found_paths: list[str] = []

    for candidate_dir in DISCOVERY_CANDIDATE_PATHS:
        rel = str(candidate_dir.relative_to(ROOT))
        checked_paths.append(rel)
        if not candidate_dir.exists():
            not_found_paths.append(rel)
            continue
        for f in sorted(candidate_dir.rglob("*")):
            if f.suffix.lower() in PRED_EXTENSIONS and f.is_file():
                found_files.append({
                    "path": str(f.relative_to(ROOT)),
                    "size_bytes": f.stat().st_size,
                    "suffix": f.suffix.lower(),
                })

    # Also check for a known 2026 recommendations directory
    reco_2026_dir = ROOT / "outputs/recommendations/PAPER"
    if reco_2026_dir.exists():
        for entry in sorted(reco_2026_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith("2026-"):
                for f in sorted(entry.rglob("*")):
                    if f.suffix.lower() in PRED_EXTENSIONS and f.is_file():
                        found_files.append({
                            "path": str(f.relative_to(ROOT)),
                            "size_bytes": f.stat().st_size,
                            "suffix": f.suffix.lower(),
                            "note": "runtime_recommendation_pipeline_not_p83a_schema",
                        })

    # Now inspect found files for schema compatibility
    schema_compatible_files: list[dict] = []
    schema_incompatible_files: list[dict] = []

    for fi in found_files:
        path = ROOT / fi["path"]
        rows_2026 = 0
        rows_with_schema = 0
        rows_governance_clean = 0
        sample_row: dict | None = None

        try:
            if fi["suffix"] == ".jsonl":
                with open(path, errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                            if _row_is_2026(row):
                                rows_2026 += 1
                                if _row_has_required_schema(row):
                                    rows_with_schema += 1
                                    if _row_governance_clean(row):
                                        rows_governance_clean += 1
                                        if sample_row is None:
                                            sample_row = {k: row[k] for k in
                                                         ["game_id", "game_date", "season",
                                                          "predicted_side", "abs_sp_fip_delta"]
                                                         if k in row}
                        except json.JSONDecodeError:
                            pass
            elif fi["suffix"] == ".json" and path.stat().st_size < 2_000_000:
                with open(path, errors="replace") as fh:
                    data = json.load(fh)
                rows_list = data if isinstance(data, list) else []
                for row in rows_list:
                    if not isinstance(row, dict):
                        continue
                    if _row_is_2026(row):
                        rows_2026 += 1
                        if _row_has_required_schema(row):
                            rows_with_schema += 1
                            if _row_governance_clean(row):
                                rows_governance_clean += 1
        except Exception:
            pass

        fi_result = {**fi, "rows_2026": rows_2026, "rows_with_schema": rows_with_schema,
                     "rows_governance_clean": rows_governance_clean}
        if rows_with_schema > 0:
            fi_result["sample_row"] = sample_row
            schema_compatible_files.append(fi_result)
        else:
            schema_incompatible_files.append(fi_result)

    total_schema_rows = sum(f["rows_with_schema"] for f in schema_compatible_files)
    total_governance_rows = sum(f["rows_governance_clean"] for f in schema_compatible_files)

    return {
        "discovery_local_only": True,
        "no_api_calls": True,
        "candidate_paths_checked": checked_paths,
        "candidate_paths_not_found": not_found_paths,
        "files_found": len(found_files),
        "schema_compatible_files": schema_compatible_files,
        "schema_incompatible_files_count": len(schema_incompatible_files),
        "schema_incompatible_files_sample": schema_incompatible_files[:3],
        "total_2026_rows_with_required_schema": total_schema_rows,
        "total_2026_rows_governance_clean": total_governance_rows,
        "data_found": total_schema_rows > 0,
        "note": (
            "Discovery searched local paths only. "
            "outputs/recommendations/PAPER/2026-* contains runtime pipeline outputs "
            "but uses different schema (no sp_fip_delta / predicted_side). "
            "These do not qualify as P83A prediction rows."
        ),
    }


# ---------------------------------------------------------------------------
# Step 3 — Expected schema definition
# ---------------------------------------------------------------------------
def step3_expected_schema() -> dict:
    return {
        "schema_id": "P83A_2026_PREDICTION_ROW_SCHEMA_V1",
        "required_fields": REQUIRED_SCHEMA_FIELDS,
        "optional_outcome_fields": OPTIONAL_OUTCOME_FIELDS,
        "governance_required_values": GOVERNANCE_REQUIRED_VALUES,
        "tier_classification_rules": {
            "primary_rule": PRIMARY_RULE,
            "shadow_rule": SHADOW_RULE,
            "tier_b_rule": TIER_B_RULE,
            "tier_a_watchlist": TIER_A_WATCHLIST,
        },
        "schema_notes": [
            "season must be 2026",
            "sp_fip_delta = home_sp_fip - away_sp_fip (positive = home favored)",
            "abs_sp_fip_delta = |sp_fip_delta|",
            "predicted_side = 'home' if sp_fip_delta > 0 else 'away'",
            "model_probability = P(predicted_side wins)",
            "odds_used must be False (prediction-only lane)",
            "market_edge_evaluated must be False (prediction-only lane)",
        ],
        "expected_canonical_path": "data/mlb_2026/predictions/mlb_2026_prediction_only_sp_fip_delta_v1.jsonl",
        "expected_derived_path": "data/mlb_2026/derived/",
    }


# ---------------------------------------------------------------------------
# Step 4 — Snapshot (if data exists) — not executed in current run
# ---------------------------------------------------------------------------
def step4_snapshot_if_data_exists(rows: list[dict]) -> dict:
    """Generate first snapshot from qualifying rows."""
    if not rows:
        return {"snapshot_available": False, "reason": "no_rows"}

    # Classification
    primary_rows = [r for r in rows if _classify_row_tier(r) in ("TIER_C_ELIGIBLE", "PRIMARY_125")]
    shadow_rows  = [r for r in rows if _classify_row_tier(r) in (
        "TIER_C_ELIGIBLE", "PRIMARY_125", "SHADOW_100_ONLY")]
    tier_b_rows  = [r for r in rows if _classify_row_tier(r) == "TIER_B"]
    tier_a_rows  = [r for r in rows if _classify_row_tier(r) == "TIER_A_WATCHLIST"]

    dates = sorted(set(r.get("game_date", "")[:7] for r in rows if r.get("game_date")))
    has_outcomes = any(r.get("is_correct") is not None for r in rows)

    # Determine level
    n = len(rows)
    if n < SNAPSHOT_THRESHOLDS["smoke"]["min_n"]:
        level = "NO_THRESHOLD_MET"
    elif n < SNAPSHOT_THRESHOLDS["sample_limited"]["min_n"]:
        level = "smoke"
    elif n < SNAPSHOT_THRESHOLDS["checkpoint_1"]["min_n"]:
        level = "sample_limited"
    elif n < SNAPSHOT_THRESHOLDS["checkpoint_2"]["min_n"]:
        level = "checkpoint_1"
    elif n < SNAPSHOT_THRESHOLDS["operational"]["min_n"]:
        level = "checkpoint_2"
    else:
        level = "operational"

    if not has_outcomes:
        cls = "P83A_2026_DATA_PRESENT_OUTCOMES_PENDING"
    elif level in ("sample_limited", "smoke"):
        cls = "P83A_2026_FIRST_SNAPSHOT_READY_SAMPLE_LIMITED"
    else:
        cls = "P83A_2026_FIRST_SNAPSHOT_READY"

    return {
        "snapshot_available": True,
        "snapshot_classification": cls,
        "snapshot_level": level,
        "total_rows": n,
        "governance_clean_rows": sum(1 for r in rows if _row_governance_clean(r)),
        "months_covered": dates,
        "primary_rule_count": len(primary_rows),
        "shadow_rule_count": len(shadow_rows),
        "tier_b_count": len(tier_b_rows),
        "tier_a_watchlist_count": len(tier_a_rows),
        "outcomes_available": has_outcomes,
        "metrics": {
            "hit_rate": "COMPUTABLE" if has_outcomes else "NOT_YET_AVAILABLE",
            "auc": "COMPUTABLE" if has_outcomes else "NOT_YET_AVAILABLE",
            "brier": "COMPUTABLE" if has_outcomes else "NOT_YET_AVAILABLE",
            "ece": "COMPUTABLE" if has_outcomes else "NOT_YET_AVAILABLE",
        },
        "no_odds_required": True,
        "no_market_edge": True,
    }


# ---------------------------------------------------------------------------
# Step 5 — Awaiting-data contract (no data found)
# ---------------------------------------------------------------------------
def step5_awaiting_contract() -> dict:
    return {
        "contract_id": "P83A_AWAITING_2026_DATA_CONTRACT_V1",
        "status": "AWAITING",
        "reason": (
            "No 2026 prediction rows with required P83A schema found in local repository. "
            "The runtime pipeline outputs (outputs/recommendations/PAPER/2026-05-11/) "
            "use a different schema (market/TSL pipeline, no sp_fip_delta field) "
            "and do not qualify as P83A prediction-only research rows."
        ),
        "expected_canonical_paths": [
            "data/mlb_2026/predictions/mlb_2026_prediction_only_sp_fip_delta_v1.jsonl",
            "data/mlb_2026/derived/",
        ],
        "required_schema_fields": REQUIRED_SCHEMA_FIELDS,
        "required_governance": GOVERNANCE_REQUIRED_VALUES,
        "snapshot_thresholds": SNAPSHOT_THRESHOLDS,
        "rerun_trigger": {
            "condition": "Any new file matching P83A schema in data/mlb_2026/ or outputs/online_validation/",
            "minimum_for_rerun": SNAPSHOT_THRESHOLDS["smoke"]["min_n"],
            "recommended_for_first_report": SNAPSHOT_THRESHOLDS["sample_limited"]["min_n"],
        },
        "primary_rule_tracked": PRIMARY_RULE["rule_id"],
        "shadow_rule_tracked": SHADOW_RULE["rule_id"],
        "tier_b_rule": TIER_B_RULE["rule_id"],
        "tier_a_watchlist": TIER_A_WATCHLIST["rule_id"],
        "p82_market_edge_status": "BLOCKED — requires external legal odds dataset",
        "next_phase_when_data_arrives": "P83B — 2026 Accumulation Snapshot with Outcomes",
        "notes": [
            "2026 MLB regular season started April 2026.",
            "P83A data feed expected from prediction-only research pipeline (sp_fip_delta-based).",
            "This awaiting contract formalises all trigger criteria for automatic P83A rerun.",
            "No odds, no EV, no CLV, no Kelly required at any stage.",
        ],
    }


# ---------------------------------------------------------------------------
# Forbidden phrase scan
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
    '"p82_unlocked": true',
]


def _scan_forbidden(text: str) -> dict:
    violations = [p for p in FORBIDDEN_PHRASES if p.lower() in text.lower()]
    return {"violations": violations, "result": "CLEAN" if not violations else "VIOLATION_FOUND"}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _generate_report(result: dict) -> str:
    lines: list[str] = []
    a = lines.append
    cls = result.get("p83a_classification", "—")

    a("# P83A — 2026 Live Accumulation First Snapshot / Awaiting Contract")
    a("**Date:** 2026-05-26  ")
    a(f"**Phase:** P83A  ")
    a(f"**Classification:** `{cls}`  ")
    a("**Mode:** paper_only=True | diagnostic_only=True | NO_REAL_BET=True")
    a("")
    a("---")
    a("")
    a("## P82C Verification")
    a("")
    v = result["step1_p82c_verification"]
    a(f"- P82C classification: `{v['classification']}` {'✅' if v['classification_ok'] else '❌'}")
    a(f"- Scanner modes: {v['scan_modes_count']} {'✅' if v['scan_modes_ok'] else '❌'}")
    a(f"- Mock cases: {'✅ PASS' if v['mock_all_passed'] else '❌ FAIL'}")
    a(f"- Repo guard state: `{v['overall_guard_state']}` {'✅' if v['guard_state_ok'] else '❌'}")
    a(f"- P82 status: `{v['p82_status']}` {'✅' if v['p82_blocked'] else '❌'}")
    a(f"- live_api_calls: {v['live_api_calls']} {'✅' if v['live_api_ok'] else '❌'}")
    a("")
    a("---")
    a("")
    a("## 2026 Data Discovery")
    a("")
    disc = result["step2_discovery"]
    a(f"**Discovery mode:** Local paths only — no API calls. `discovery_local_only={disc['discovery_local_only']}`")
    a("")
    a("### Paths Searched")
    a("")
    for p in disc["candidate_paths_checked"]:
        found = p not in disc["candidate_paths_not_found"]
        a(f"- `{p}` {'✅ exists' if found else '❌ not found'}")
    a("")
    a(f"**Files found:** {disc['files_found']}")
    a(f"**2026 rows with required schema:** {disc['total_2026_rows_with_required_schema']}")
    a(f"**Data found:** {'YES' if disc['data_found'] else 'NO'}")
    a("")
    if disc.get("schema_incompatible_files_sample"):
        a("### Schema-Incompatible Files (sample)")
        a("")
        for fi in disc["schema_incompatible_files_sample"]:
            note = fi.get("note", "missing required fields")
            a(f"- `{fi['path']}` — {note}")
    a("")
    a(f"> {disc['note']}")
    a("")
    a("---")
    a("")
    a("## Expected 2026 Row Schema")
    a("")
    schema = result["step3_expected_schema"]
    a(f"**Schema ID:** `{schema['schema_id']}`")
    a("")
    a("### Required Fields")
    for f in schema["required_fields"]:
        a(f"- `{f}`")
    a("")
    a("### Optional Outcome Fields")
    for f in schema["optional_outcome_fields"]:
        a(f"- `{f}`")
    a("")
    a("### Governance Required Values")
    for k, v2 in schema["governance_required_values"].items():
        a(f"- `{k}` = `{v2}`")
    a("")
    a(f"**Expected canonical path:** `{schema['expected_canonical_path']}`")
    a("")
    a("---")
    a("")

    if cls == "P83A_AWAITING_2026_DATA":
        await_c = result["step5_awaiting_contract"]
        a("## Awaiting-Data Contract")
        a("")
        a(f"**Status:** {await_c['status']}")
        a("")
        a(f"> {await_c['reason']}")
        a("")
        a("### Snapshot Thresholds")
        a("")
        a("| Threshold | Min n | Label |")
        a("|---|---:|---|")
        for key, t in SNAPSHOT_THRESHOLDS.items():
            a(f"| {key} | {t['min_n']} | `{t['label']}` |")
        a("")
        a("### Rerun Trigger")
        a("")
        rt = await_c["rerun_trigger"]
        a(f"- Condition: {rt['condition']}")
        a(f"- Minimum for rerun: n >= {rt['minimum_for_rerun']}")
        a(f"- Recommended for first report: n >= {rt['recommended_for_first_report']}")
        a("")
        a("### Tracking Rules")
        a("")
        a(f"- Primary: `{await_c['primary_rule_tracked']}`")
        a(f"- Shadow: `{await_c['shadow_rule_tracked']}`")
        a(f"- Tier B: `{await_c['tier_b_rule']}`")
        a(f"- Tier A watchlist: `{await_c['tier_a_watchlist']}`")
        a("")
        a(f"**P82 market-edge:** {await_c['p82_market_edge_status']}")
        a(f"**Next phase when data arrives:** {await_c['next_phase_when_data_arrives']}")

    a("")
    a("---")
    a("")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_p83a() -> dict:
    p82c_path = PATHS["p82c_json"]
    if not p82c_path.exists():
        return {
            "phase": "P83A",
            "date": "2026-05-26",
            "p83a_classification": "P83A_BLOCKED_BY_MISSING_P82C_ARTIFACT",
            "governance": GOVERNANCE,
        }

    p82c = json.loads(p82c_path.read_text())

    # Step 1
    p82c_verification = step1_verify_p82c(p82c)
    if not p82c_verification["verification_ok"]:
        return {
            "phase": "P83A",
            "date": "2026-05-26",
            "p83a_classification": "P83A_FAILED_VALIDATION",
            "step1_p82c_verification": p82c_verification,
            "governance": GOVERNANCE,
        }

    # Step 2
    discovery = step2_discover_2026_data()

    # Step 3
    schema = step3_expected_schema()

    result: dict[str, Any] = {
        "phase": "P83A",
        "date": "2026-05-26",
        "governance": GOVERNANCE,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "source_artifacts": {k: str(p) for k, p in PATHS.items()},
        "step1_p82c_verification": p82c_verification,
        "step2_discovery": discovery,
        "step3_expected_schema": schema,
    }

    if discovery["data_found"]:
        # Step 4 — collect qualifying rows (not implemented in full for this run)
        # If rows were found they'd be loaded here; this branch handles future data
        snapshot = step4_snapshot_if_data_exists([])  # placeholder
        result["step4_snapshot"] = snapshot
        result["p83a_classification"] = snapshot.get(
            "snapshot_classification", "P83A_2026_DATA_INVALID"
        )
    else:
        # Step 5 — awaiting contract
        awaiting = step5_awaiting_contract()
        result["step5_awaiting_contract"] = awaiting
        result["p83a_classification"] = "P83A_AWAITING_2026_DATA"

    result_text = json.dumps(result, indent=2)
    scan = _scan_forbidden(result_text)
    result["forbidden_scan"] = scan

    return result


def main() -> None:
    result = run_p83a()
    cls = result.get("p83a_classification", "UNKNOWN")
    print(f"[P83A] Classification: {cls}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[P83A] JSON → {OUTPUT_JSON}")

    if cls not in ("P83A_BLOCKED_BY_MISSING_P82C_ARTIFACT", "P83A_FAILED_VALIDATION"):
        report_text = _generate_report(result)
        OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_REPORT.write_text(report_text)
        print(f"[P83A] Report → {OUTPUT_REPORT}")
        PLAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        PLAN_REPORT.write_text(report_text)
        print(f"[P83A] Plan report → {PLAN_REPORT}")

    scan = result.get("forbidden_scan", {})
    if scan.get("result") != "CLEAN":
        print(f"[P83A] FORBIDDEN PHRASE VIOLATION: {scan.get('violations')}")
        sys.exit(1)
    print("[P83A] Forbidden scan: CLEAN")
    print("[P83A] Done.")


if __name__ == "__main__":
    main()
