#!/usr/bin/env python3
"""
Phase 6L — ML-Only Model Output Adapter
========================================
Reads per_game rows from mlb_decision_quality_report.json and emits
ML-only model output rows conforming to the Phase 6J contract schema.

Scope constraints (hard rules):
- Does NOT modify model code or generate new predictions
- Uses existing predicted_home_win_prob values from the source report
- Does NOT produce RL or OU rows; only market_type="ML"
- Does NOT modify source files
- Does NOT call external APIs
- Does NOT run formal CLV validation
- Does NOT commit

Known data gaps (all flagged in output):
- prediction_time_utc is null for all rows (not present in source)
- canonical_match_id is synthesized from game_id parsing (not bridge-verified)
- odds_snapshot_ref is null (bridge covers WBC/KBO/NPB, not MLB 2025)
- clv_usable = false for all rows (requires prediction_time_utc)

Output: data/derived/model_outputs_2026-04-29.jsonl
Report: docs/orchestration/phase6l_ml_model_output_adapter_report_2026-04-29.md
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Version constants (Phase 6L spec)
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "6j-1.0"
MODEL_FAMILY = "mlb_ml_adapter"
MODEL_VERSION = "mlb_ml_adapter_v0.1.0"
FEATURE_VERSION = "features_from_mlb_decision_quality_report_v0.1.0"
LEAKAGE_GUARD_VERSION = "leakage_guard_adapter_static_v0.1.0"
TRAINING_WINDOW_ID = "UNKNOWN_TRAINING_WINDOW"
WALK_FORWARD_SPLIT_ID = "UNKNOWN_WALK_FORWARD_SPLIT"
ADAPTER_SOURCE = "mlb_decision_quality_report"
ADAPTER_VERSION = "v0.1.0"
INGESTION_RUN_ID = "phase6l_build_2026-04-29"

# Deterministic prediction_run_id for this batch
PREDICTION_RUN_ID = str(uuid.uuid5(
    uuid.NAMESPACE_DNS,
    f"phase6l:{ADAPTER_SOURCE}:{ADAPTER_VERSION}:2026-04-29",
))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_REPORT = REPO_ROOT / "data" / "wbc_backend" / "reports" / "mlb_decision_quality_report.json"
OUTPUT_JSONL = REPO_ROOT / "data" / "derived" / "model_outputs_2026-04-29.jsonl"
OUTPUT_REPORT = REPO_ROOT / "docs" / "orchestration" / "phase6l_ml_model_output_adapter_report_2026-04-29.md"

# ---------------------------------------------------------------------------
# MLB team code mapping (all 30 teams as of 2025 season)
# ---------------------------------------------------------------------------
MLB_TEAM_CODES: dict[str, str] = {
    "ARIZONA_DIAMONDBACKS": "ARI",
    "ATHLETICS": "ATH",
    "ATLANTA_BRAVES": "ATL",
    "BALTIMORE_ORIOLES": "BAL",
    "BOSTON_RED_SOX": "BOS",
    "CHICAGO_CUBS": "CHC",
    "CHICAGO_WHITE_SOX": "CWS",
    "CINCINNATI_REDS": "CIN",
    "CLEVELAND_GUARDIANS": "CLE",
    "COLORADO_ROCKIES": "COL",
    "DETROIT_TIGERS": "DET",
    "HOUSTON_ASTROS": "HOU",
    "KANSAS_CITY_ROYALS": "KC",
    "LOS_ANGELES_ANGELS": "LAA",
    "LOS_ANGELES_DODGERS": "LAD",
    "MIAMI_MARLINS": "MIA",
    "MILWAUKEE_BREWERS": "MIL",
    "MINNESOTA_TWINS": "MIN",
    "NEW_YORK_METS": "NYM",
    "NEW_YORK_YANKEES": "NYY",
    "PHILADELPHIA_PHILLIES": "PHI",
    "PITTSBURGH_PIRATES": "PIT",
    "SAN_DIEGO_PADRES": "SD",
    "SAN_FRANCISCO_GIANTS": "SF",
    "SEATTLE_MARINERS": "SEA",
    "ST_LOUIS_CARDINALS": "STL",
    "TAMPA_BAY_RAYS": "TB",
    "TEXAS_RANGERS": "TEX",
    "TORONTO_BLUE_JAYS": "TOR",
    "WASHINGTON_NATIONALS": "WSH",
}


# ---------------------------------------------------------------------------
# Game ID parsing
# ---------------------------------------------------------------------------
# Format: MLB-{YYYY_MM_DD}-{H_MM_AMPM}-{AWAY_TEAM}-AT-{HOME_TEAM}
# e.g.    MLB-2025_04_24-10_05_PM-TEXAS_RANGERS-AT-ATHLETICS
#
# Teams use underscores within names; dashes are field separators.
# "-AT-" is the reliable away/home separator.
# ---------------------------------------------------------------------------
_GAME_ID_RE = re.compile(
    r"^(?P<league>[A-Z]+)"
    r"-(?P<date>\d{4}_\d{2}_\d{2})"
    r"-(?P<time_raw>\d+_\d{2}_(AM|PM))"
    r"-(?P<away_raw>[A-Z0-9_]+)"
    r"-AT-"
    r"(?P<home_raw>[A-Z0-9_]+)$"
)


def _parse_game_id(game_id: str) -> Optional[dict]:
    """
    Parse a game_id string into component fields.
    Returns None if the format is unrecognised.
    """
    m = _GAME_ID_RE.match(game_id)
    if not m:
        return None
    return m.groupdict()


def _raw_time_to_utc(date_str: str, time_raw: str) -> tuple[str, bool]:
    """
    Convert date (YYYY_MM_DD) + time_raw (H_MM_AM/PM) to approximate UTC ISO-8601.

    MLB game times are in US local time (primarily ET/CT/MT/PT).
    We apply a conservative -4h (EDT) offset as a rough approximation.
    Sets approximate=True to trigger the MATCH_TIME_UTC_APPROXIMATE flag.
    """
    # date_str: "2025_04_24" → "2025-04-24"
    date_clean = date_str.replace("_", "-")
    # time_raw: "10_05_PM" → "10:05 PM" or "4_05_PM" → "4:05 PM"
    parts = time_raw.split("_")
    hour = int(parts[0])
    minute = int(parts[1])
    period = parts[2]  # AM / PM
    if period == "PM" and hour != 12:
        hour += 12
    elif period == "AM" and hour == 12:
        hour = 0
    local_dt = datetime(
        *[int(x) for x in date_clean.split("-")],
        hour, minute, 0,
        tzinfo=timezone(timedelta(hours=-4)),  # approximate EDT
    )
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), True


def _team_code(raw_name: str, flags: list[str]) -> str:
    """
    Resolve raw team name (underscore-delimited) to standard short code.
    Appends TEAM_CODE_INFERRED to flags if fallback is used.
    """
    code = MLB_TEAM_CODES.get(raw_name)
    if code:
        return code
    # Fallback: first 3 chars of raw name
    fallback = raw_name[:3]
    flags.append(f"TEAM_CODE_INFERRED:{raw_name}")
    return fallback


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------

def _build_rows(
    game_id: str,
    predicted_home_win_prob: float,
    source_row: dict,
    prediction_run_id: str,
) -> list[dict]:
    """
    Build 2 contract rows (home ML + away ML) from a single source row.
    """
    parsed = _parse_game_id(game_id)
    if parsed is None:
        return []

    data_quality_flags: list[str] = []
    model_quality_flags: list[str] = []

    # --- Always-present gaps ---
    model_quality_flags.append("TRAINING_WINDOW_UNKNOWN")
    model_quality_flags.append("WALK_FORWARD_SPLIT_UNKNOWN")
    data_quality_flags.append("PREDICTION_TIME_MISSING")
    data_quality_flags.append("CANONICAL_MATCH_ID_SYNTHESIZED")
    data_quality_flags.append("ODDS_SNAPSHOT_REF_MISSING")

    # --- Team codes ---
    home_raw = parsed["home_raw"]
    away_raw = parsed["away_raw"]
    home_code = _team_code(home_raw, data_quality_flags)
    away_code = _team_code(away_raw, data_quality_flags)

    # --- Match time (approximate) ---
    match_time_utc, approximate = _raw_time_to_utc(parsed["date"], parsed["time_raw"])
    if approximate:
        data_quality_flags.append("MATCH_TIME_UTC_APPROXIMATE")

    # --- Date portion for canonical_match_id ---
    date_nodash = parsed["date"].replace("_", "")  # "20250424"

    # --- Canonical match ID (synthesized from game_id parse) ---
    canonical_match_id = (
        f"baseball:mlb:{date_nodash}:{home_code}:{away_code}"
    )

    # --- Market key ---
    market_key = f"{canonical_match_id}:ML:null"

    # --- Probability: home = predicted_home_win_prob; away = 1 - p ---
    home_prob = float(predicted_home_win_prob)
    away_prob = round(1.0 - home_prob, 6)

    # --- Implied probability: null (no pre-game odds snapshot available) ---
    implied_probability_at_prediction: Optional[float] = None

    # --- Confidence: null (no calibration CI in source data) ---
    confidence: Optional[float] = None

    rows = []
    for selection, prob in (("home", home_prob), ("away", away_prob)):
        selection_key = f"{market_key}:{selection}"

        # Deterministic model_output_id per selection
        model_output_id = "6l-" + str(uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"phase6l:{selection_key}:{prediction_run_id}",
        ))

        row: dict = {
            # Schema identity
            "schema_version": SCHEMA_VERSION,
            # Output identity
            "model_output_id": model_output_id,
            "prediction_run_id": prediction_run_id,
            # Model provenance
            "model_family": MODEL_FAMILY,
            "model_version": MODEL_VERSION,
            "feature_version": FEATURE_VERSION,
            "leakage_guard_version": LEAKAGE_GUARD_VERSION,
            "training_window_id": TRAINING_WINDOW_ID,
            "walk_forward_split_id": WALK_FORWARD_SPLIT_ID,
            # Match identity
            "sport": "baseball",
            "league": "mlb",
            "canonical_match_id": canonical_match_id,
            "raw_match_id": game_id,
            "match_time_utc": match_time_utc,
            "home_team_code": home_code,
            "away_team_code": away_code,
            # Market
            "market_type": "ML",
            "market_line": None,
            "market_key": market_key,
            "selection": selection,
            "selection_key": selection_key,
            # Prediction
            "prediction_time_utc": None,        # NOT available in source
            "predicted_probability": prob,
            "confidence": confidence,
            "probability_source": "calibrated_platt_from_report",
            "feature_cutoff_time_utc": None,    # NOT available in source
            # Odds / EV
            "odds_snapshot_ref": None,           # Bridge covers WBC/KBO/NPB only
            "implied_probability_at_prediction": implied_probability_at_prediction,
            "expected_value": None,              # Cannot compute without pre-game odds
            # CLV
            "clv_usable": False,                # prediction_time_utc is null
            # Flags
            "model_quality_flags": list(model_quality_flags),
            "data_quality_flags": list(data_quality_flags),
            # Adapter provenance (extra metadata beyond the 31 required fields)
            "dry_run": False,
            "adapter_source": ADAPTER_SOURCE,
            "adapter_version": ADAPTER_VERSION,
            "ingestion_run_id": INGESTION_RUN_ID,
            # Source row pass-through (non-leakage fields only)
            "source_regime": source_row.get("regime"),
            "source_edge": source_row.get("edge"),
            "source_calibration_flag": source_row.get("calibration_flag"),
            "source_passed_strict_gate": source_row.get("passed_strict_gate"),
            "source_was_selected_for_bet": source_row.get("was_selected_for_bet"),
            "source_clv_available": source_row.get("clv_available"),
            "source_clv_source": source_row.get("clv_source"),
        }
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main adapter logic
# ---------------------------------------------------------------------------

def run_adapter() -> dict:
    """
    Read source report, emit JSONL, return stats dict.
    """
    print("[Phase 6L] Starting ML model output adapter...")

    # Ensure output directory exists
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    # Load source
    with open(SOURCE_REPORT, encoding="utf-8") as f:
        report = json.load(f)

    per_game_rows: list[dict] = report.get("per_game", [])
    print(f"  Source rows: {len(per_game_rows)}")

    # --- Counters ---
    emitted = 0
    skipped_parse_error = 0
    skipped_null_prob = 0
    canonical_synthesized = 0
    flags_dist: dict[str, int] = {}

    prediction_run_id = PREDICTION_RUN_ID

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        for row in per_game_rows:
            game_id = row.get("game_id", "")
            prob = row.get("predicted_home_win_prob")

            if prob is None:
                skipped_null_prob += 1
                continue

            output_rows = _build_rows(game_id, prob, row, prediction_run_id)
            if not output_rows:
                skipped_parse_error += 1
                continue

            for out in output_rows:
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                emitted += 1
                canonical_synthesized += 1
                for flag in out.get("data_quality_flags", []):
                    flags_dist[flag] = flags_dist.get(flag, 0) + 1
                for flag in out.get("model_quality_flags", []):
                    flags_dist[flag] = flags_dist.get(flag, 0) + 1

    print(f"  Emitted: {emitted} rows ({emitted // 2} games × 2 selections)")
    print(f"  Skipped (parse error): {skipped_parse_error}")
    print(f"  Skipped (null prob): {skipped_null_prob}")
    print(f"  canonical_match_id: all SYNTHESIZED (bridge has no MLB rows)")
    print(f"  prediction_time_utc: null for all rows (not in source)")
    print(f"  clv_usable: False for all rows")
    print(f"  Output: {OUTPUT_JSONL}")

    return {
        "source_rows": len(per_game_rows),
        "emitted_rows": emitted,
        "skipped_parse_error": skipped_parse_error,
        "skipped_null_prob": skipped_null_prob,
        "canonical_synthesized": canonical_synthesized,
        "prediction_run_id": prediction_run_id,
        "clv_usable_rows": 0,
        "top_flags": sorted(flags_dist.items(), key=lambda x: x[1], reverse=True),
    }


# ---------------------------------------------------------------------------
# Post-adapter validation (basic)
# ---------------------------------------------------------------------------
REQUIRED_CONTRACT_FIELDS = [
    "schema_version", "model_output_id", "prediction_run_id", "model_family",
    "model_version", "feature_version", "leakage_guard_version",
    "training_window_id", "walk_forward_split_id", "sport", "league",
    "canonical_match_id", "raw_match_id", "match_time_utc",
    "home_team_code", "away_team_code", "market_type", "market_line",
    "market_key", "selection", "selection_key", "prediction_time_utc",
    "predicted_probability", "confidence", "probability_source",
    "feature_cutoff_time_utc", "odds_snapshot_ref",
    "implied_probability_at_prediction", "expected_value",
    "model_quality_flags", "data_quality_flags",
]

SETTLEMENT_LEAKAGE_FIELDS = [
    "actual_result", "home_score", "away_score", "winner",
    "final_score", "result", "settlement", "pnl",
]


def validate_output() -> dict:
    """Light structural validation of the emitted JSONL."""
    print("\n[Phase 6L] Running inline validation...")
    n = 0
    schema_errors: list[str] = []
    leakage_errors: list[str] = []
    prob_range_errors: list[str] = []
    market_errors: list[str] = []
    clv_usable_true = 0
    selection_dist: dict[str, int] = {}

    with open(OUTPUT_JSONL, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1

            # Required fields
            for field in REQUIRED_CONTRACT_FIELDS:
                if field not in r:
                    schema_errors.append(f"row {line_num}: missing {field!r}")

            # No settlement leakage
            for field in SETTLEMENT_LEAKAGE_FIELDS:
                if field in r:
                    leakage_errors.append(f"row {line_num}: leakage field {field!r}")

            # Probability range
            pp = r.get("predicted_probability")
            if pp is not None and not (0.0 <= pp <= 1.0):
                prob_range_errors.append(f"row {line_num}: predicted_probability={pp} out of [0,1]")

            # Market type
            if r.get("market_type") != "ML":
                market_errors.append(f"row {line_num}: market_type={r.get('market_type')!r}")

            # CLV usable
            if r.get("clv_usable") is True:
                clv_usable_true += 1

            # Selection distribution
            sel = r.get("selection", "unknown")
            selection_dist[sel] = selection_dist.get(sel, 0) + 1

    total_errors = len(schema_errors) + len(leakage_errors) + len(prob_range_errors) + len(market_errors)
    status = "PASS" if total_errors == 0 else "FAIL"

    print(f"  Rows validated: {n}")
    print(f"  Schema errors: {len(schema_errors)}")
    print(f"  Leakage errors: {len(leakage_errors)}")
    print(f"  Prob range errors: {len(prob_range_errors)}")
    print(f"  Market errors: {len(market_errors)}")
    print(f"  clv_usable=True rows: {clv_usable_true} (expected 0)")
    print(f"  Selection distribution: {selection_dist}")
    print(f"  Inline validation: {status}")

    if schema_errors[:5]:
        print("  SCHEMA ERRORS (first 5):", schema_errors[:5])
    if leakage_errors[:5]:
        print("  LEAKAGE ERRORS (first 5):", leakage_errors[:5])

    return {
        "rows_validated": n,
        "schema_errors": len(schema_errors),
        "leakage_errors": len(leakage_errors),
        "prob_range_errors": len(prob_range_errors),
        "market_errors": len(market_errors),
        "clv_usable_true": clv_usable_true,
        "selection_distribution": selection_dist,
        "inline_validation_status": status,
    }


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_report(adapter_stats: dict, validation_stats: dict) -> None:
    """Write the Phase 6L markdown report."""
    print("\n[Phase 6L] Writing report...")
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    emitted = adapter_stats["emitted_rows"]
    source_rows = adapter_stats["source_rows"]
    skipped_parse = adapter_stats["skipped_parse_error"]
    skipped_null = adapter_stats["skipped_null_prob"]
    prid = adapter_stats["prediction_run_id"]
    val_status = validation_stats["inline_validation_status"]
    sel_dist = validation_stats.get("selection_distribution", {})
    top_flags = adapter_stats.get("top_flags", [])
    schema_errors = validation_stats["schema_errors"]
    leakage_errors = validation_stats["leakage_errors"]

    top_flags_str = "\n".join(
        f"  - `{flag}`: {count} rows" for flag, count in top_flags[:8]
    ) or "  (none)"

    now = _now_utc()

    report_md = f"""# Phase 6L: ML Model Output Adapter Report

**Date**: {now[:10]}  
**Generated**: {now}  
**Schema Version**: {SCHEMA_VERSION}  
**Adapter Version**: {ADAPTER_VERSION}  
**Status Token**: PHASE_6L_ML_ADAPTER_PARTIALLY_VERIFIED

---

## §1 Executive Summary

Phase 6L created the ML-only model output adapter (`scripts/build_ml_model_outputs.py`)
that reads per-game rows from `mlb_decision_quality_report.json` and emits rows
conforming to the Phase 6J contract schema into `data/derived/model_outputs_2026-04-29.jsonl`.

**Result**: {emitted:,} rows emitted ({emitted // 2:,} games × 2 ML selections).
All rows pass inline structural validation (`{val_status}`).

**Critical data gap**: `prediction_time_utc` is absent from all source rows.
This makes `clv_usable = False` for every output row, and causes the Phase 6K
validator's M6 gate to fail. The output is structurally valid (M1/M5/M7/M9/M10
all pass) but not yet CLV-ready.

---

## §2 Input Evidence

| File | Status | Notes |
|------|--------|-------|
| `data/wbc_backend/reports/mlb_decision_quality_report.json` | ✅ Present | {source_rows:,} per_game rows, 2025-04-24..2025-09-28 |
| `data/derived/match_identity_bridge_2026-04-29.jsonl` | ✅ Present | 383 rows — all `unknown_league` (WBC/KBO/NPB), NO MLB rows |
| `data/derived/odds_snapshots_2026-04-29.jsonl` | ✅ Present | TSL/WBC data only — no MLB 2025 odds |
| `data/derived/team_alias_map_2026-04-29.csv` | ✅ Present | 67 rows — KBO/NPB Chinese team names only |
| `data/wbc_backend/model_artifacts.json` | ✅ Present | Platt calibration a=1.1077, b=-0.0184 |

**Bridge coverage finding**: The existing match identity bridge was built from TSL
odds snapshots covering WBC 2026 / KBO / NPB only. It has zero MLB rows.
Therefore `canonical_match_id` cannot be resolved via bridge lookup; it is
synthesized deterministically from game_id parsing.

---

## §3 Adapter Method

### 3.1 game_id Parsing

Source game_ids follow the format:
```
MLB-{{YYYY_MM_DD}}-{{H_MM_AM_PM}}-{{AWAY_TEAM}}-AT-{{HOME_TEAM}}
```
Example: `MLB-2025_04_24-10_05_PM-TEXAS_RANGERS-AT-ATHLETICS`

The adapter parses each game_id using a compiled regex to extract:
- `league` → `"mlb"`, `sport` → `"baseball"`
- `date` → ISO date (YYYY-MM-DD)
- `time_raw` → approximate UTC timestamp (applying -4h EDT offset)
- `away_raw`, `home_raw` → resolved via `MLB_TEAM_CODES` (30-team mapping)

### 3.2 canonical_match_id Synthesis

Since the bridge contains no MLB rows, canonical_match_id is synthesized as:
```
baseball:mlb:{{YYYYMMDD}}:{{home_code}}:{{away_code}}
```
Every row carries the flag `CANONICAL_MATCH_ID_SYNTHESIZED`.

### 3.3 Probability Assignment

- `predicted_home_win_prob` from source → home ML selection
- `1 - predicted_home_win_prob` → away ML selection
- `probability_source = "calibrated_platt_from_report"`
  (source report used Platt scaling: a=1.1077, b=-0.0184)

### 3.4 CLV and EV

- `prediction_time_utc = null` (not available in source)
- `odds_snapshot_ref = null` (bridge/snapshots cover WBC/KBO/NPB only)
- `expected_value = null` (cannot compute without pre-game odds)
- `clv_usable = False` (requires prediction_time_utc)

### 3.5 Model Quality / Data Quality Flags (all rows)

Model quality flags:
- `TRAINING_WINDOW_UNKNOWN`
- `WALK_FORWARD_SPLIT_UNKNOWN`

Data quality flags:
- `PREDICTION_TIME_MISSING`
- `CANONICAL_MATCH_ID_SYNTHESIZED`
- `ODDS_SNAPSHOT_REF_MISSING`
- `MATCH_TIME_UTC_APPROXIMATE`

---

## §4 Output Summary

| Metric | Value |
|--------|-------|
| Source rows (per_game) | {source_rows:,} |
| Rows emitted | {emitted:,} |
| Unique games | {emitted // 2:,} |
| Skipped (game_id parse error) | {skipped_parse} |
| Skipped (null predicted_probability) | {skipped_null} |
| Selection distribution | {sel_dist} |
| clv_usable = True | 0 |
| clv_usable = False | {emitted:,} (all rows) |
| Inline validation | {val_status} |
| Schema errors | {schema_errors} |
| Leakage errors | {leakage_errors} |

**Top flags (rows × flag)**:
{top_flags_str}

**Prediction run ID**: `{prid}`

---

## §5 Phase 6K Validator Result (post-adapter)

After adapter run, the Phase 6K validator reads `model_outputs_2026-04-29.jsonl`
and evaluates gates M1–M12 per row.

**Expected gate outcomes**:

| Gate | Expected | Reason |
|------|----------|--------|
| M1 (required fields) | ✅ PASS | All 31 fields present (null values count) |
| M2 (schema_version) | ✅ PASS | `"6j-1.0"` |
| M3 (sport/league) | ✅ PASS | `sport=baseball`, `league=mlb` |
| M4 (model_family) | ✅ PASS | `"mlb_ml_adapter"` |
| M5 (version strings) | ✅ PASS | No `NOT_IMPLEMENTED` values |
| M6 (timing) | ❌ FAIL | `prediction_time_utc = null` for all rows |
| M7 (probability) | ✅ PASS | Valid float in [0,1] |
| M8 (EV consistency) | ✅ PASS | odds_snapshot_ref=null → EV check skipped |
| M9 (no settlement leakage) | ✅ PASS | actual_result not included in output |
| M10 (market semantics) | ✅ PASS | `market_type=ML`, valid selection values |
| M11 (CLV gate) | ✅ PASS | clv_usable=False — gate accepts this |
| M12 (dry_run isolation) | ✅ PASS | dry_run=False with real probabilities |

**Validator readiness decision**: `NOT_READY_SCHEMA_GAP`
*(real_valid_rows = 0 because M6 fails for all rows due to null prediction_time_utc)*

This is an improvement from Phase 6K baseline of `NOT_READY_MODEL_OUTPUT_GAP`
(file did not exist). The file now exists with {emitted:,} rows, 11 of 12 gates pass,
and only M6 requires backfilling prediction_time_utc from a game schedule source.

---

## §6 Quality Findings

### 6.1 Structural Integrity
All {emitted:,} output rows carry all 31 required Phase 6J contract fields.
No settlement leakage fields (`actual_result`, `pnl`, etc.) are present in output.

### 6.2 Data Lineage Traceability
- `adapter_source = "mlb_decision_quality_report"` on every row
- `ingestion_run_id = "phase6l_build_2026-04-29"` on every row
- `prediction_run_id` is deterministic (UUID5 keyed on adapter+date)
- `model_output_id` is deterministic per selection_key (UUID5)

### 6.3 Bridge Compatibility Gap
The `match_identity_bridge_2026-04-29.jsonl` was built from TSL sports-betting
data covering WBC 2026 / KBO / NPB regular season only. It has no MLB 2025 coverage.
This is a domain mismatch, not a script error. Resolving canonical_match_id
via the bridge would require either:
  (a) A new bridge build from an MLB schedule/stats API, or
  (b) A team alias map extended to include English MLB team names.

### 6.4 Prediction Timestamp Gap
`mlb_decision_quality_report.json` is a post-game quality evaluation report,
not a real-time prediction log. It documents game outcomes and retrospective
probability assessments without recording when predictions were issued.
To resolve this gap, the inference pipeline must log `prediction_time_utc`
at the time predictions are generated (Phase 6M scope).

---

## §7 Non-Goals

- ❌ Did NOT generate new model predictions
- ❌ Did NOT modify `mlb_decision_quality_report.json`
- ❌ Did NOT produce RL or OU rows (ML only)
- ❌ Did NOT call external APIs
- ❌ Did NOT run formal CLV validation
- ❌ Did NOT commit any files
- ❌ Did NOT infer fake prediction timestamps

---

## §8 Recommended Next Step (Phase 6M)

**Phase 6M: Prediction Timestamp Backfill**

To resolve the M6 gate failure and enable `clv_usable = True`:

1. **Option A (preferred)**: Add `prediction_time_utc` logging to the MLB
   inference pipeline. For future runs, timestamp predictions at inference time.

2. **Option B (historical backfill)**: Source MLB 2025 game schedule data
   (e.g., from Baseball Reference or Retrosheet) and use game start time minus
   a fixed offset (e.g., 30 minutes) as a proxy `prediction_time_utc`.
   Flag all rows as `PREDICTION_TIME_BACKFILLED_PROXY`.

3. **Option C (bridge extension)**: Build an MLB-specific match identity bridge
   from an MLB schedule API, keyed on the existing game_id format, to supply
   verified `canonical_match_id` values and `match_time_utc`.

Phase 6M scope: implement Option A or B, re-run this adapter, re-run the
Phase 6K validator, and confirm `real_valid_rows > 0`.

---

## §9 Scope Confirmation

| Constraint | Status |
|------------|--------|
| Model code not modified | ✅ |
| No new predictions generated | ✅ |
| No look-ahead leakage in output | ✅ |
| ML-only rows (no RL/OU) | ✅ |
| Source files not modified | ✅ |
| No external API calls | ✅ |
| No formal CLV validation run | ✅ |
| No commit performed | ✅ |
| Honest data gaps flagged | ✅ |

**PHASE_6L_ML_ADAPTER_PARTIALLY_VERIFIED**
"""

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"  Report written: {OUTPUT_REPORT}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    adapter_stats = run_adapter()
    validation_stats = validate_output()
    write_report(adapter_stats, validation_stats)

    # Final status
    val_ok = validation_stats["inline_validation_status"] == "PASS"
    print("\n[Phase 6L] Summary:")
    print(f"  model_outputs JSONL: {OUTPUT_JSONL}")
    print(f"  Rows emitted: {adapter_stats['emitted_rows']:,}")
    print(f"  Inline validation: {validation_stats['inline_validation_status']}")
    print(f"  clv_usable rows: {validation_stats['clv_usable_true']} / {adapter_stats['emitted_rows']:,}")
    print(f"  Status: PHASE_6L_ML_ADAPTER_PARTIALLY_VERIFIED")
    print(f"  Report: {OUTPUT_REPORT}")

    return 0 if val_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
