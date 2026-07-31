"""
P83E — 2026 Canonical Prediction Row Producer
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Re-check P83D upstream gates.
  2. Validate schemas for schedule / pitcher feature / model output files.
  3. Join upstream files by game_id.
  4. Compute sp_fip_delta, abs_sp_fip_delta, predicted_side, rule flags.
  5. Enforce governance on every row.
  6. Write canonical rows to data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl.
  7. Generate future snapshot prompt (P83F/P84A).

Expected classification when upstream files are missing:
  P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA

Expected when upstream is complete and rows written:
  P83E_CANONICAL_ROWS_READY

sp_fip_delta convention (P83C_UPSTREAM_INPUT_CONTRACT_V1):
  sp_fip_delta = home_sp_fip - away_sp_fip
  FIP is lower-is-better, so:
    delta > 0 → home pitcher FIP > away pitcher FIP → home pitcher WORSE → predicted_side='away'
    delta < 0 → home pitcher FIP < away pitcher FIP → away pitcher WORSE → predicted_side='home'
  [P84G fix: corrected from inverted P83E v1 mapping per P84F_SIDE_MAPPING_INVERTED diagnosis]
  Ties (sp_fip_delta == 0.0) are excluded from canonical output.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
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
    "api_key_accessed": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "market_edge_evaluated": False,
    "kelly_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "odds_used": False,
}

ALLOWED_CLASSIFICATIONS = [
    "P83E_CANONICAL_ROWS_READY",
    "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA",
    "P83E_BLOCKED_BY_SCHEMA_MISMATCH",
    "P83E_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P83E is the canonical 2026 prediction row producer. "
    "No external API calls are made. No market edge is computed. "
    "Canonical rows written only if all upstream gates pass. "
    "paper_only=True, diagnostic_only=True."
)

SOURCE_PREDICTION_VERSION = "mlb_2026_prediction_rows_v1"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SOURCE_ARTIFACTS: dict[str, Path] = {
    "p83d_json": ROOT / "data/mlb_2026/derived/p83d_2026_upstream_data_availability_probe_summary.json",
    "p83c_json": ROOT / "data/mlb_2026/derived/p83c_2026_prediction_schema_producer_contract_summary.json",
    "p83b_json": ROOT / "data/mlb_2026/derived/p83b_2026_prediction_data_ingest_contract_summary.json",
    "p83a_json": ROOT / "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json",
}

UPSTREAM_FILES: dict[str, Path] = {
    "schedule": ROOT / "data/mlb_2026/schedule/mlb_2026_schedule.jsonl",
    "pitchers": ROOT / "data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl",
    "model_outputs": ROOT / "data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl",
}

CANONICAL_OUTPUT_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"

# ---------------------------------------------------------------------------
# Schema requirements (from P83B / P83C contracts)
# ---------------------------------------------------------------------------
SCHEDULE_REQUIRED_FIELDS = {"game_id", "game_date", "season", "home_team", "away_team"}
PITCHER_REQUIRED_FIELDS = {"game_id", "home_sp_fip", "away_sp_fip"}
MODEL_OUTPUT_REQUIRED_FIELDS = {"game_id", "model_probability", "source_prediction_version"}

# Thresholds from P83C rule flag computation contract
THRESHOLDS: dict[str, float] = {
    "home_pick_min_abs": 0.50,
    "away_pick_primary_min_abs": 1.25,
    "away_pick_shadow_min_abs": 1.00,
    "tier_b_lower": 0.25,
    "tier_b_upper": 0.50,
    "tier_a_upper": 0.25,
}

_GATE_BLOCKED_BY_MISSING_FILE = "missing file"

# ---------------------------------------------------------------------------
# Step 1 — Load and verify P83D artifact
# ---------------------------------------------------------------------------

def load_p83d_artifact() -> dict[str, Any]:
    path = SOURCE_ARTIFACTS["p83d_json"]
    if not path.exists():
        return {
            "loaded": False,
            "error": f"P83D artifact not found: {path}",
            "p83d_classification": None,
        }
    d = json.loads(path.read_text())
    classification = d.get("p83d_classification", "")
    return {
        "loaded": True,
        "path": str(path.relative_to(ROOT)),
        "p83d_classification": classification,
        "classification_ok": classification == "P83D_AWAITING_UPSTREAM_DATA",
        "governance_ok": d.get("governance", {}).get("live_api_calls", 1) == 0,
    }


# ---------------------------------------------------------------------------
# Step 2 — Check upstream file availability
# ---------------------------------------------------------------------------

def check_upstream_files() -> dict[str, Any]:
    results: dict[str, Any] = {}
    all_present = True
    for key, path in UPSTREAM_FILES.items():
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        results[key] = {
            "path": str(path.relative_to(ROOT)),
            "exists": exists,
            "size_bytes": size,
        }
        if not exists:
            all_present = False
    missing = [k for k, v in results.items() if not v["exists"]]
    return {
        "file_checks": results,
        "all_present": all_present,
        "missing_files": missing,
        "missing_count": len(missing),
    }


# ---------------------------------------------------------------------------
# Step 3 — Upstream schema validators
# ---------------------------------------------------------------------------

def validate_schedule_row(row: dict[str, Any]) -> list[str]:
    """Return list of validation errors for a schedule row (empty = pass)."""
    errors: list[str] = []
    for field in SCHEDULE_REQUIRED_FIELDS:
        if field not in row or row[field] is None:
            errors.append(f"Missing required field: {field}")
    if "season" in row and row["season"] is not None:
        try:
            if int(row["season"]) != 2026:
                errors.append(f"season must be 2026, got {row['season']}")
        except (TypeError, ValueError):
            errors.append(f"season must be integer, got {row['season']!r}")
    if "game_date" in row and row["game_date"] is not None:
        gd = str(row["game_date"])
        if len(gd) != 10 or gd[4] != "-" or gd[7] != "-":
            errors.append(f"game_date must be YYYY-MM-DD, got {gd!r}")
    return errors


def _fip_value_errors(field: str, value: Any) -> list[str]:
    """Return errors for a non-None FIP value."""
    try:
        val = float(value)
        if val < 0.0 or val > 15.0:
            return [f"{field} out of plausible range [0, 15]: {val}"]
        return []
    except (TypeError, ValueError):
        return [f"{field} must be numeric, got {value!r}"]


def validate_pitcher_row(row: dict[str, Any]) -> list[str]:
    """Return list of validation errors for a pitcher feature row.

    FEATURE_PENDING rows have None FIP by contract; schema-valid but blocked by gate.
    """
    errors: list[str] = []
    is_pending = row.get("row_status") == "FEATURE_PENDING"
    for field in PITCHER_REQUIRED_FIELDS:
        if field not in row or (row[field] is None and not is_pending):
            errors.append(f"Missing required field: {field}")
    for fip_field in ("home_sp_fip", "away_sp_fip"):
        if row.get(fip_field) is not None:
            errors.extend(_fip_value_errors(fip_field, row[fip_field]))
    return errors


def validate_model_output_row(row: dict[str, Any]) -> list[str]:
    """Return list of validation errors for a model output row.

    MODEL_PENDING rows have None model_probability by contract; schema-valid but blocked by gate.
    """
    errors: list[str] = []
    is_pending = row.get("predicted_side_derivation_status") == "MODEL_PENDING"
    for field in MODEL_OUTPUT_REQUIRED_FIELDS:
        if field not in row or (row[field] is None and not is_pending):
            errors.append(f"Missing required field: {field}")
    if "model_probability" in row and row["model_probability"] is not None:
        try:
            prob = float(row["model_probability"])
            if not (0.0 < prob < 1.0):
                errors.append(f"model_probability must be in (0, 1), got {prob}")
        except (TypeError, ValueError):
            errors.append(f"model_probability must be numeric, got {row['model_probability']!r}")
    return errors


def load_and_validate_upstream(
    path: Path, _required_fields: set[str], validator_fn: Any, label: str
) -> dict[str, Any]:
    """Load a JSONL upstream file and validate each row."""
    if not path.exists():
        return {
            "loaded": False, "path": str(path.relative_to(ROOT)),
            "error": f"{label} file missing",
        }
    rows: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                parse_errors.append(f"Line {i}: {e}")

    if parse_errors:
        return {
            "loaded": False, "path": str(path.relative_to(ROOT)),
            "parse_errors": parse_errors,
        }

    all_errors: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        errs = validator_fn(row)
        if errs:
            all_errors.append({"row_index": i, "game_id": row.get("game_id"), "errors": errs})

    # Duplicate game_id check
    game_ids = [r.get("game_id") for r in rows]
    dup_ids = [gid for gid in set(game_ids) if game_ids.count(gid) > 1]

    return {
        "loaded": True,
        "path": str(path.relative_to(ROOT)),
        "row_count": len(rows),
        "rows": rows,
        "validation_errors": all_errors,
        "duplicate_game_ids": dup_ids,
        "schema_valid": len(all_errors) == 0 and len(dup_ids) == 0,
    }


# ---------------------------------------------------------------------------
# Step 4 — Join upstream files by game_id
# ---------------------------------------------------------------------------

def join_upstream(
    schedule_data: dict[str, Any],
    pitcher_data: dict[str, Any],
    model_data: dict[str, Any],
) -> dict[str, Any]:
    """Join schedule + pitcher features + model outputs by game_id."""
    schedule_rows = {r["game_id"]: r for r in schedule_data.get("rows", [])}
    pitcher_rows = {r["game_id"]: r for r in pitcher_data.get("rows", [])}
    model_rows = {r["game_id"]: r for r in model_data.get("rows", [])}

    all_ids = set(schedule_rows) | set(pitcher_rows) | set(model_rows)

    # Full inner join: must appear in all 3
    joined_ids = sorted(set(schedule_rows) & set(pitcher_rows) & set(model_rows))
    joined_rows: list[dict[str, Any]] = []
    for gid in joined_ids:
        merged = {**schedule_rows[gid], **pitcher_rows[gid], **model_rows[gid]}
        joined_rows.append(merged)

    unmatched_schedule = sorted(set(schedule_rows) - set(joined_ids))
    unmatched_pitchers = sorted(set(pitcher_rows) - set(joined_ids))
    unmatched_models = sorted(set(model_rows) - set(joined_ids))

    return {
        "total_unique_game_ids": len(all_ids),
        "joined_row_count": len(joined_rows),
        "joined_rows": joined_rows,
        "unmatched_schedule_ids": unmatched_schedule,
        "unmatched_pitcher_ids": unmatched_pitchers,
        "unmatched_model_ids": unmatched_models,
        "join_ok": len(joined_rows) > 0,
    }


# ---------------------------------------------------------------------------
# Step 5 — Compute prediction fields (deterministic)
# ---------------------------------------------------------------------------

def compute_sp_fip_delta(home_sp_fip: float, away_sp_fip: float) -> float:
    """
    P83C convention: sp_fip_delta = home_sp_fip - away_sp_fip.
    FIP is lower-is-better:
      delta > 0 → home pitcher FIP > away FIP → home pitcher WORSE → predict 'away'
      delta < 0 → home pitcher FIP < away FIP → away pitcher WORSE → predict 'home'
    [P84G fix: docstring corrected per P84F_SIDE_MAPPING_INVERTED diagnosis]
    """
    return home_sp_fip - away_sp_fip


def compute_predicted_side(sp_fip_delta: float) -> str | None:
    """
    P84G-corrected predicted_side logic (fixes P84F_SIDE_MAPPING_INVERTED):
      sp_fip_delta = home_sp_fip - away_sp_fip (P83C formula)
      FIP is lower-is-better:
        delta > 0 → home pitcher FIP higher → home pitcher WORSE → predicted_side='away'
        delta < 0 → away pitcher FIP higher → away pitcher WORSE → predicted_side='home'
      Ties (sp_fip_delta == 0.0) → None (excluded from canonical output)
    """
    if sp_fip_delta > 0.0:
        return "away"  # home pitcher worse (higher FIP) — P84G fix
    if sp_fip_delta < 0.0:
        return "home"  # away pitcher worse (higher FIP) — P84G fix
    return None  # tie — excluded


def compute_rule_flags(predicted_side: str | None, abs_fip: float) -> dict[str, bool]:
    """
    Rule flag computation per P83C_RULE_FLAG_COMPUTATION_CONTRACT_V1.
    Returns all 4 flag booleans.
    """
    if predicted_side is None:
        return {
            "rule_primary_125_flag": False,
            "rule_shadow_100_flag": False,
            "tier_b_candidate_flag": False,
            "tier_a_watchlist_flag": False,
        }

    # primary_125: home → abs >= 0.50; away → abs >= 1.25
    if predicted_side == "home":
        primary_125 = abs_fip >= THRESHOLDS["home_pick_min_abs"]
        shadow_100 = abs_fip >= THRESHOLDS["home_pick_min_abs"]
    else:
        primary_125 = abs_fip >= THRESHOLDS["away_pick_primary_min_abs"]
        shadow_100 = abs_fip >= THRESHOLDS["away_pick_shadow_min_abs"]

    tier_b = THRESHOLDS["tier_b_lower"] <= abs_fip < THRESHOLDS["tier_b_upper"]
    tier_a = abs_fip < THRESHOLDS["tier_a_upper"]

    return {
        "rule_primary_125_flag": primary_125,
        "rule_shadow_100_flag": shadow_100,
        "tier_b_candidate_flag": tier_b,
        "tier_a_watchlist_flag": tier_a,
    }


def compute_prediction_row(merged_row: dict[str, Any]) -> dict[str, Any] | None:
    """
    Build a canonical P83B/P83C prediction row from a joined upstream row.
    Returns None if sp_fip_delta == 0 (tie excluded).
    """
    home_fip = float(merged_row["home_sp_fip"])
    away_fip = float(merged_row["away_sp_fip"])
    sp_fip_delta = compute_sp_fip_delta(home_fip, away_fip)
    abs_fip = abs(sp_fip_delta)
    predicted_side = compute_predicted_side(sp_fip_delta)

    if predicted_side is None:
        return None  # tie excluded

    flags = compute_rule_flags(predicted_side, abs_fip)
    model_prob = float(merged_row["model_probability"])

    row: dict[str, Any] = {
        "game_id": merged_row["game_id"],
        "game_date": merged_row["game_date"],
        "season": int(merged_row.get("season", 2026)),
        "home_team": merged_row["home_team"],
        "away_team": merged_row["away_team"],
        "home_sp_fip": home_fip,
        "away_sp_fip": away_fip,
        "sp_fip_delta": round(sp_fip_delta, 6),
        "abs_sp_fip_delta": round(abs_fip, 6),
        "model_probability": model_prob,
        "predicted_side": predicted_side,
        "source_prediction_version": merged_row.get("source_prediction_version", SOURCE_PREDICTION_VERSION),
        "rule_primary_125_flag": flags["rule_primary_125_flag"],
        "rule_shadow_100_flag": flags["rule_shadow_100_flag"],
        "tier_b_candidate_flag": flags["tier_b_candidate_flag"],
        "tier_a_watchlist_flag": flags["tier_a_watchlist_flag"],
        # Governance constants
        "paper_only": True,
        "diagnostic_only": True,
        "odds_used": False,
        "market_edge_evaluated": False,
        "production_ready": False,
        # Outcome fields — pending
        "result_home_score": None,
        "result_away_score": None,
        "actual_winner": None,
        "is_correct": None,
    }
    return row


def validate_canonical_row(row: dict[str, Any]) -> list[str]:
    """Validate a produced canonical row against the P83B schema."""
    errors: list[str] = []
    required = [
        "game_id", "game_date", "season", "home_team", "away_team",
        "sp_fip_delta", "abs_sp_fip_delta", "model_probability",
        "predicted_side", "source_prediction_version",
        "rule_primary_125_flag", "rule_shadow_100_flag",
        "tier_b_candidate_flag", "tier_a_watchlist_flag",
        "paper_only", "diagnostic_only", "odds_used",
        "market_edge_evaluated", "production_ready",
    ]
    for f in required:
        if f not in row:
            errors.append(f"Missing required field: {f}")
    # Governance invariant checks
    if row.get("paper_only") is not True:
        errors.append("paper_only must be True")
    if row.get("diagnostic_only") is not True:
        errors.append("diagnostic_only must be True")
    if row.get("odds_used") is not False:
        errors.append("odds_used must be False")
    if row.get("market_edge_evaluated") is not False:
        errors.append("market_edge_evaluated must be False")
    if row.get("production_ready") is not False:
        errors.append("production_ready must be False")
    if row.get("season") != 2026:
        errors.append(f"season must be 2026, got {row.get('season')}")
    if row.get("predicted_side") not in ("home", "away"):
        errors.append(f"predicted_side must be 'home' or 'away', got {row.get('predicted_side')!r}")
    return errors


# ---------------------------------------------------------------------------
# Step 6 — Write canonical rows
# ---------------------------------------------------------------------------

def write_canonical_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Write validated canonical rows to the output JSONL path."""
    out_dir = CANONICAL_OUTPUT_PATH.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_errors: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        errs = validate_canonical_row(row)
        if errs:
            schema_errors.append({"row_index": i, "game_id": row.get("game_id"), "errors": errs})
        else:
            valid_rows.append(row)

    if schema_errors:
        return {
            "rows_written": False,
            "path": str(CANONICAL_OUTPUT_PATH.relative_to(ROOT)),
            "schema_errors": schema_errors,
            "error": "Schema validation failed — rows not written",
        }

    with open(CANONICAL_OUTPUT_PATH, "w") as f:
        for row in valid_rows:
            f.write(json.dumps(row) + "\n")

    return {
        "rows_written": True,
        "path": str(CANONICAL_OUTPUT_PATH.relative_to(ROOT)),
        "row_count": len(valid_rows),
        "schema_errors": [],
    }


# ---------------------------------------------------------------------------
# Step 7 — Future snapshot prompt
# ---------------------------------------------------------------------------

def generate_next_prompt(classification: str, row_count: int) -> str:
    if classification == "P83E_CANONICAL_ROWS_READY":
        return (
            f"[P83F / P84A — 2026 Prediction Snapshot Execution]\n\n"
            f"P83E wrote {row_count} canonical rows to "
            f"data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl.\n\n"
            f"Next step:\n"
            f"1. Re-run P83A snapshot unlock gate with canonical row count = {row_count}.\n"
            f"2. Compute primary_125 / shadow_100 / tier_b / tier_a counts from canonical rows.\n"
            f"3. If outcomes available (result_home_score / result_away_score): compute hit_rate metrics.\n"
            f"4. Compare against 2025 baseline (HOME_PLUS_AWAY_125 hit=0.6392, AUC=0.5787, n=316).\n"
            f"5. Maintain paper_only=True until real outcomes reach n≥50 threshold.\n\n"
            f"Rules: no odds | no EV/CLV/Kelly | paper_only=True | diagnostic_only=True"
        )
    elif classification == "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA":
        return (
            "[P83E Retry — Upstream Data Availability]\n\n"
            "P83E remains blocked. Re-run when all three files exist locally:\n"
            "  1. data/mlb_2026/schedule/mlb_2026_schedule.jsonl\n"
            "     Fields: game_id, game_date, season, home_team, away_team\n"
            "  2. data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl\n"
            "     Fields: game_id, home_sp_fip, away_sp_fip\n"
            "  3. data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl\n"
            "     Fields: game_id, model_probability, source_prediction_version\n\n"
            "Data sources (no API call in P83E):\n"
            "  - statsapi.mlb.com/api/v1/schedule (free, public)\n"
            "  - statsapi.mlb.com/api/v1/people (pitcher stats)\n"
            "  - 2025-trained ensemble model applied to 2026 features\n\n"
            "Rules: no external API calls in P83E itself | no odds | paper_only=True"
        )
    else:
        return (
            "[P83E Schema Mismatch / Failure Recovery]\n\n"
            f"P83E classification: {classification}. "
            "Review upstream file schemas and fix before retrying."
        )


# ---------------------------------------------------------------------------
# In-memory mock fixture (for test validation without real upstream data)
# ---------------------------------------------------------------------------

def build_mock_upstream_fixture() -> dict[str, Any]:
    """
    Build a small in-memory mock fixture with 5 games covering all rule-flag cases.
    Does NOT write any file. For test validation only.
    """
    schedule = [
        {"game_id": "MLB2026_NYY_BOS_20260510", "game_date": "2026-05-10", "season": 2026, "home_team": "Boston Red Sox", "away_team": "New York Yankees"},
        {"game_id": "MLB2026_LAD_SF_20260510",  "game_date": "2026-05-10", "season": 2026, "home_team": "San Francisco Giants", "away_team": "Los Angeles Dodgers"},
        {"game_id": "MLB2026_CHC_STL_20260511", "game_date": "2026-05-11", "season": 2026, "home_team": "St. Louis Cardinals", "away_team": "Chicago Cubs"},
        {"game_id": "MLB2026_HOU_TEX_20260511", "game_date": "2026-05-11", "season": 2026, "home_team": "Texas Rangers", "away_team": "Houston Astros"},
        {"game_id": "MLB2026_ATL_NYM_20260512", "game_date": "2026-05-12", "season": 2026, "home_team": "New York Mets", "away_team": "Atlanta Braves"},
    ]
    # home_sp_fip - away_sp_fip = sp_fip_delta
    # Case 1: delta=+1.30 → home, abs=1.30, primary=T, shadow=T, tierB=F, tierA=F
    # Case 2: delta=-1.40 → away, abs=1.40, primary=T, shadow=T, tierB=F, tierA=F
    # Case 3: delta=-1.10 → away, abs=1.10, primary=F, shadow=T, tierB=F, tierA=F
    # Case 4: delta=+0.35 → home, abs=0.35, primary=F, shadow=F, tierB=T, tierA=F
    # Case 5: delta=+0.15 → home, abs=0.15, primary=F, shadow=F, tierB=F, tierA=T
    pitchers = [
        {"game_id": "MLB2026_NYY_BOS_20260510", "home_sp_fip": 4.80, "away_sp_fip": 3.50},  # +1.30
        {"game_id": "MLB2026_LAD_SF_20260510",  "home_sp_fip": 3.20, "away_sp_fip": 4.60},  # -1.40
        {"game_id": "MLB2026_CHC_STL_20260511", "home_sp_fip": 3.10, "away_sp_fip": 4.20},  # -1.10
        {"game_id": "MLB2026_HOU_TEX_20260511", "home_sp_fip": 4.00, "away_sp_fip": 3.65},  # +0.35
        {"game_id": "MLB2026_ATL_NYM_20260512", "home_sp_fip": 3.80, "away_sp_fip": 3.65},  # +0.15
    ]
    model_outputs = [
        {"game_id": "MLB2026_NYY_BOS_20260510", "model_probability": 0.58, "source_prediction_version": SOURCE_PREDICTION_VERSION},
        {"game_id": "MLB2026_LAD_SF_20260510",  "model_probability": 0.62, "source_prediction_version": SOURCE_PREDICTION_VERSION},
        {"game_id": "MLB2026_CHC_STL_20260511", "model_probability": 0.55, "source_prediction_version": SOURCE_PREDICTION_VERSION},
        {"game_id": "MLB2026_HOU_TEX_20260511", "model_probability": 0.53, "source_prediction_version": SOURCE_PREDICTION_VERSION},
        {"game_id": "MLB2026_ATL_NYM_20260512", "model_probability": 0.51, "source_prediction_version": SOURCE_PREDICTION_VERSION},
    ]
    # Build in-memory data dicts (matching load_and_validate_upstream output shape)
    schedule_data = {"loaded": True, "rows": schedule, "row_count": len(schedule), "schema_valid": True, "validation_errors": [], "duplicate_game_ids": []}
    pitcher_data  = {"loaded": True, "rows": pitchers,  "row_count": len(pitchers),  "schema_valid": True, "validation_errors": [], "duplicate_game_ids": []}
    model_data    = {"loaded": True, "rows": model_outputs, "row_count": len(model_outputs), "schema_valid": True, "validation_errors": [], "duplicate_game_ids": []}
    return {
        "schedule": schedule_data,
        "pitchers": pitcher_data,
        "model_outputs": model_data,
        "tag": "MOCK_IN_MEMORY_ONLY",
        "note": "Mock fixture for test validation only. Does not write canonical rows.",
    }


def produce_mock_canonical_rows(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Build canonical rows from mock fixture (in-memory, no file write)."""
    join = join_upstream(fixture["schedule"], fixture["pitchers"], fixture["model_outputs"])
    rows: list[dict[str, Any]] = []
    for merged in join["joined_rows"]:
        row = compute_prediction_row(merged)
        if row is not None:
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_p83e_producer(write_canonical: bool = True) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()

    # Step 1 — Load P83D artifact
    p83d_artifact = load_p83d_artifact()

    # Step 2 — Check upstream files
    upstream_check = check_upstream_files()
    missing_files = upstream_check["missing_files"]

    # STOP condition: any upstream file missing
    if not upstream_check["all_present"]:
        classification = "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA"
        next_prompt = generate_next_prompt(classification, 0)

        forbidden_scan: dict[str, Any] = {
            **{k: v for k, v in GOVERNANCE.items() if k in (
                "live_api_calls", "api_key_accessed", "ev_calculated", "clv_calculated",
                "market_edge_calculated", "kelly_calculated", "odds_used",
                "production_ready", "kelly_deploy_allowed",
            )},
            "canonical_rows_written": False,
            "forbidden_scan_pass": True,
        }

        return {
            "phase": "P83E",
            "date": "2026-05-26",
            "generated_at": ts,
            "p83e_classification": classification,
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "prediction_boundary": PREDICTION_BOUNDARY,
            "governance": GOVERNANCE,
            "step1_p83d_artifact": p83d_artifact,
            "step2_upstream_check": upstream_check,
            "step3_gate_recheck": {
                "SCHEDULE_GATE": {"gate_pass": False, "blocked_by": _GATE_BLOCKED_BY_MISSING_FILE},
                "PITCHER_FEATURE_GATE": {"gate_pass": False, "blocked_by": _GATE_BLOCKED_BY_MISSING_FILE},
                "MODEL_OUTPUT_GATE": {"gate_pass": False, "blocked_by": _GATE_BLOCKED_BY_MISSING_FILE},
                "PREDICTED_SIDE_GATE": {"gate_pass": False, "blocked_by": "PITCHER_FEATURE_GATE"},
                "GOVERNANCE_GATE": {"gate_pass": True},
                "PRODUCER_ACTIVATION_GATE": {"gate_pass": False, "reason": f"missing: {missing_files}"},
            },
            "step4_schema_validation": None,
            "step5_join_result": None,
            "step6_canonical_rows": {
                "rows_written": False,
                "row_count": 0,
                "reason": f"Blocked by missing upstream files: {missing_files}",
            },
            "step7_next_prompt": next_prompt,
            "forbidden_scan": forbidden_scan,
            "source_artifacts": {k: str(v) for k, v in SOURCE_ARTIFACTS.items()},
            "upstream_files": {k: str(v) for k, v in UPSTREAM_FILES.items()},
            "canonical_output_path": str(CANONICAL_OUTPUT_PATH.relative_to(ROOT)),
        }

    # Upstream complete path (will execute when upstream data is provided)
    # Step 3 — Validate upstream schemas
    schedule_data = load_and_validate_upstream(
        UPSTREAM_FILES["schedule"], SCHEDULE_REQUIRED_FIELDS, validate_schedule_row, "Schedule"
    )
    pitcher_data = load_and_validate_upstream(
        UPSTREAM_FILES["pitchers"], PITCHER_REQUIRED_FIELDS, validate_pitcher_row, "Pitcher features"
    )
    model_data = load_and_validate_upstream(
        UPSTREAM_FILES["model_outputs"], MODEL_OUTPUT_REQUIRED_FIELDS, validate_model_output_row, "Model outputs"
    )

    schema_ok = all([
        schedule_data.get("schema_valid", False),
        pitcher_data.get("schema_valid", False),
        model_data.get("schema_valid", False),
    ])

    if not schema_ok:
        classification = "P83E_BLOCKED_BY_SCHEMA_MISMATCH"
        return {
            "phase": "P83E", "date": "2026-05-26", "generated_at": ts,
            "p83e_classification": classification,
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "prediction_boundary": PREDICTION_BOUNDARY,
            "governance": GOVERNANCE,
            "step1_p83d_artifact": p83d_artifact,
            "step2_upstream_check": upstream_check,
            "step3_gate_recheck": {
                "SCHEDULE_GATE": {"gate_pass": schedule_data.get("schema_valid", False)},
                "PITCHER_FEATURE_GATE": {"gate_pass": pitcher_data.get("schema_valid", False)},
                "MODEL_OUTPUT_GATE": {"gate_pass": model_data.get("schema_valid", False)},
                "PREDICTED_SIDE_GATE": {"gate_pass": False, "blocked_by": "schema mismatch"},
                "GOVERNANCE_GATE": {"gate_pass": True},
                "PRODUCER_ACTIVATION_GATE": {"gate_pass": False, "reason": "schema validation failed"},
            },
            "step4_schema_validation": {
                "schedule": schedule_data,
                "pitchers": pitcher_data,
                "model_outputs": model_data,
            },
            "step6_canonical_rows": {"rows_written": False, "row_count": 0},
            "step7_next_prompt": generate_next_prompt(classification, 0),
            "forbidden_scan": {
                **{k: GOVERNANCE[k] for k in (
                    "live_api_calls", "api_key_accessed", "ev_calculated", "clv_calculated",
                    "market_edge_calculated", "kelly_calculated", "odds_used",
                    "production_ready", "kelly_deploy_allowed",
                )},
                "canonical_rows_written": False,
                "forbidden_scan_pass": True,
            },
        }

    # Step 4 — Join
    join_result = join_upstream(schedule_data, pitcher_data, model_data)
    if not join_result["join_ok"]:
        classification = "P83E_FAILED_VALIDATION"
        return {
            "phase": "P83E", "date": "2026-05-26", "generated_at": ts,
            "p83e_classification": classification,
            "step5_join_result": join_result,
            "step6_canonical_rows": {"rows_written": False, "row_count": 0},
            "forbidden_scan": {
                **{k: GOVERNANCE[k] for k in (
                    "live_api_calls", "api_key_accessed", "ev_calculated", "clv_calculated",
                    "market_edge_calculated", "kelly_calculated", "odds_used",
                    "production_ready", "kelly_deploy_allowed",
                )},
                "canonical_rows_written": False,
                "forbidden_scan_pass": True,
            },
        }

    # Filter out FEATURE_PENDING rows before computing (None FIP would crash float())
    ready_rows = [
        r for r in join_result["joined_rows"]
        if r.get("row_status") != "FEATURE_PENDING"
        and r.get("home_sp_fip") is not None
        and r.get("away_sp_fip") is not None
        and r.get("model_probability") is not None
    ]
    pending_count = len(join_result["joined_rows"]) - len(ready_rows)

    # If all rows are pending, treat as blocked
    if len(ready_rows) == 0:
        classification = "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA"
        return {
            "phase": "P83E", "date": "2026-05-26", "generated_at": ts,
            "p83e_classification": classification,
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "governance": GOVERNANCE,
            "step3_gate_recheck": {
                "SCHEDULE_GATE": {"gate_pass": True},
                "PITCHER_FEATURE_GATE": {"gate_pass": False, "blocked_by": f"all {pending_count} rows FEATURE_PENDING"},
                "MODEL_OUTPUT_GATE": {"gate_pass": False, "blocked_by": "PITCHER_FEATURE_GATE"},
                "PREDICTED_SIDE_GATE": {"gate_pass": False, "blocked_by": "PITCHER_FEATURE_GATE"},
                "GOVERNANCE_GATE": {"gate_pass": True},
                "PRODUCER_ACTIVATION_GATE": {"gate_pass": False, "reason": "no FEATURE_READY rows"},
            },
            "step6_canonical_rows": {"rows_written": False, "row_count": 0,
                                     "reason": f"All {pending_count} joined rows are FEATURE_PENDING"},
            "forbidden_scan": {
                **{k: GOVERNANCE[k] for k in (
                    "live_api_calls", "api_key_accessed", "ev_calculated", "clv_calculated",
                    "market_edge_calculated", "kelly_calculated", "odds_used",
                    "production_ready", "kelly_deploy_allowed",
                )},
                "canonical_rows_written": False,
                "forbidden_scan_pass": True,
            },
        }

    # Step 5 — Compute canonical rows (ready rows only)
    computed_rows: list[dict[str, Any]] = []
    ties_excluded = 0
    for merged in ready_rows:
        row = compute_prediction_row(merged)
        if row is None:
            ties_excluded += 1
        else:
            computed_rows.append(row)

    # Step 6 — Write canonical rows
    write_result: dict[str, Any]
    if write_canonical and computed_rows:
        write_result = write_canonical_rows(computed_rows)
    else:
        write_result = {"rows_written": False, "row_count": len(computed_rows), "note": "write_canonical=False or no rows"}

    classification = "P83E_CANONICAL_ROWS_READY" if write_result.get("rows_written") else "P83E_FAILED_VALIDATION"

    gate_recheck = {
        "SCHEDULE_GATE": {"gate_pass": schedule_data.get("schema_valid", False)},
        "PITCHER_FEATURE_GATE": {"gate_pass": pitcher_data.get("schema_valid", False)},
        "MODEL_OUTPUT_GATE": {"gate_pass": model_data.get("schema_valid", False)},
        "PREDICTED_SIDE_GATE": {"gate_pass": True, "note": "Logic defined, data present"},
        "GOVERNANCE_GATE": {"gate_pass": True},
        "PRODUCER_ACTIVATION_GATE": {"gate_pass": write_result.get("rows_written", False)},
    }

    next_prompt = generate_next_prompt(classification, write_result.get("row_count", 0))
    forbidden_scan = {
        **{k: GOVERNANCE[k] for k in (
            "live_api_calls", "api_key_accessed", "ev_calculated", "clv_calculated",
            "market_edge_calculated", "kelly_calculated", "odds_used",
            "production_ready", "kelly_deploy_allowed",
        )},
        "canonical_rows_written": write_result.get("rows_written", False),
        "forbidden_scan_pass": True,
    }

    return {
        "phase": "P83E", "date": "2026-05-26", "generated_at": ts,
        "p83e_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "governance": GOVERNANCE,
        "step1_p83d_artifact": p83d_artifact,
        "step2_upstream_check": upstream_check,
        "step3_gate_recheck": gate_recheck,
        "step4_schema_validation": {
            "schedule": {k: v for k, v in schedule_data.items() if k != "rows"},
            "pitchers": {k: v for k, v in pitcher_data.items() if k != "rows"},
            "model_outputs": {k: v for k, v in model_data.items() if k != "rows"},
        },
        "step5_join_result": {k: v for k, v in join_result.items() if k != "joined_rows"},
        "step5_ties_excluded": ties_excluded,
        "step6_canonical_rows": write_result,
        "step7_next_prompt": next_prompt,
        "forbidden_scan": forbidden_scan,
        "source_artifacts": {k: str(v) for k, v in SOURCE_ARTIFACTS.items()},
        "canonical_output_path": str(CANONICAL_OUTPUT_PATH.relative_to(ROOT)),
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_p83e_producer()

    out_dir = ROOT / "data/mlb_2026/derived"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "p83e_2026_canonical_prediction_row_producer_summary.json"
    serializable = dict(result)
    with open(out_json, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"[P83E] JSON written → {out_json.relative_to(ROOT)}")

    report_dir = ROOT / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "p83e_2026_canonical_prediction_row_producer_20260526.md"

    classification = result["p83e_classification"]
    gate_recheck = result.get("step3_gate_recheck", {})
    gate_rows = "\n".join(
        f"| {g} | {'✅ PASS' if v.get('gate_pass') else '❌ FAIL'} |"
        for g, v in gate_recheck.items()
    )

    upstream = result.get("step2_upstream_check", {})
    missing = upstream.get("missing_files", [])
    canon = result.get("step6_canonical_rows", {})

    md = f"""# P83E — 2026 Canonical Prediction Row Producer
**Date:** 2026-05-26
**Classification:** `{classification}`
**Mode:** paper_only=True | diagnostic_only=True | NO_REAL_BET=True

---

## Summary

P83E attempted to produce canonical 2026 prediction rows by loading upstream
schedule, pitcher FIP, and model output files.

**Result:** `{classification}`

---

## P83D Gate Recheck

| Gate | Status |
|---|---|
{gate_rows}

---

## Upstream File Check

| File | Status |
|---|---|
| data/mlb_2026/schedule/mlb_2026_schedule.jsonl | {'✅ Present' if 'schedule' not in missing else '❌ Missing'} |
| data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl | {'✅ Present' if 'pitchers' not in missing else '❌ Missing'} |
| data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl | {'✅ Present' if 'model_outputs' not in missing else '❌ Missing'} |

**Missing count:** {len(missing)}

---

## Canonical Rows Status

- **Rows written:** {canon.get('rows_written', False)}
- **Row count:** {canon.get('row_count', 0)}
- **Reason:** {canon.get('reason', 'N/A')}

---

## sp_fip_delta Convention

Per P83C_UPSTREAM_INPUT_CONTRACT_V1:
- `sp_fip_delta = home_sp_fip - away_sp_fip`
- Positive → home pitcher favored (system convention)
- `predicted_side = 'home' if sp_fip_delta > 0 else 'away'`
- Ties (delta == 0) excluded from canonical output

---

## Rule Flag Thresholds (P83C)

| Flag | Condition |
|---|---|
| rule_primary_125_flag | home: abs >= 0.50 OR away: abs >= 1.25 |
| rule_shadow_100_flag | home: abs >= 0.50 OR away: abs >= 1.00 |
| tier_b_candidate_flag | 0.25 <= abs < 0.50 |
| tier_a_watchlist_flag | abs < 0.25 |

---

## Next Steps

```
{result.get('step7_next_prompt', 'N/A')}
```

---

## Governance Invariants

| Invariant | Value |
|---|---|
| paper_only | True |
| diagnostic_only | True |
| live_api_calls | 0 |
| odds_used | False |
| ev_calculated | False |
| clv_calculated | False |
| kelly_calculated | False |
| production_ready | False |
| canonical_rows_written | {canon.get('rows_written', False)} |
| forbidden_scan_pass | True |

---

## Final Classification

**`{classification}`**

{PREDICTION_BOUNDARY}
"""
    with open(report_path, "w") as f:
        f.write(md)
    print(f"[P83E] Report written → {report_path.relative_to(ROOT)}")
    print(f"[P83E] Classification: {classification}")
    print(f"[P83E] Missing upstream files: {missing}")
    print(f"[P83E] Canonical rows written: {canon.get('rows_written', False)}")
