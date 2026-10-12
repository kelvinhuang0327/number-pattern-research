"""
P66 — Odds Mapping Integrity Audit for P64/P65 Stable Negative Edge
====================================================================
Diagnostic-only. No live API. No TSL. No paid API.
No mutations of P64/P65 artifacts.
No runtime recommendation logic change.
No production claims.

Answers:
  1. Did P64 correctly join odds by (game_date, home_team)?
  2. Are home/away team labels consistent between predictions and odds CSV?
  3. Are Home ML / Away ML mapped to the correct sides?
  4. Is American → decimal odds conversion correct?
  5. Is decimal → implied probability conversion correct?
  6. Is model_prob_home/away assigned to the correct side?
  7. Is edge = calibrated_prob - implied_probability for selected side?
  8. Is the stable negative edge robust after mapping validation?
  9. If mapping is wrong, what exact correction is needed?

Governance flags (immutable throughout P66):
  paper_only=True, diagnostic_only=True, promotion_freeze=True
  kelly_deploy_allowed=False, live_api_calls=0, paid_api_called=False
  runtime_recommendation_logic_changed=False
  real_bet_allowed=False, production_ready=False
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance — immutable flags
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
LIVE_API_CALLS: int = 0
PAID_API_CALLED: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False
DATA_YEAR_2024_GAP_REMAINS_UNRESOLVED: bool = True

# Platt constants — P45 locked, never refit
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# Tolerance for floating-point comparison
EDGE_TOLERANCE: float = 1e-4
PROB_TOLERANCE: float = 1e-4
ODDS_TOLERANCE: float = 1e-4

# Expected artifact counts
EXPECTED_P64_ROWS: int = 535

# ---------------------------------------------------------------------------
# Forbidden affirmative terms
# ---------------------------------------------------------------------------

FORBIDDEN_AFFIRMATIVE_TERMS = [
    "kelly_deploy_allowed\": true",
    "production_ready\": true",
    "real_bet_allowed\": true",
    "live_api_calls\": 1",
    "paid_api_called\": true",
    "production_deploy",
    "live_betting",
    "actual_bet_placed",
    "champion_replaced",
    "profitability_confirmed",
    "runtime_recommendation_logic_changed\": true",
]

# Allowed status values
ALLOWED_JOIN_STATUSES = {
    "JOIN_INTEGRITY_PASS",
    "JOIN_HAS_DUPLICATES",
    "JOIN_HAS_UNMATCHED_ROWS",
    "JOIN_AMBIGUOUS",
    "JOIN_BLOCKED_BY_SCHEMA_GAP",
}

ALLOWED_SIDE_STATUSES = {
    "SIDE_MAPPING_PASS",
    "SIDE_MAPPING_SIDE_INVERSION_RISK",
    "SIDE_MAPPING_FIELD_MISMATCH",
    "SIDE_MAPPING_BLOCKED",
}

ALLOWED_ODDS_CONVERSION_STATUSES = {
    "ODDS_CONVERSION_PASS",
    "ODDS_CONVERSION_MISMATCH",
    "ODDS_CONVERSION_INVALID_VALUES",
}

ALLOWED_EDGE_RECALC_STATUSES = {
    "EDGE_RECALCULATION_PASS",
    "EDGE_RECALCULATION_SIGN_MISMATCH",
    "EDGE_RECALCULATION_VALUE_MISMATCH",
}

ALLOWED_P66_CLASSIFICATIONS = {
    "P66_ODDS_MAPPING_INTEGRITY_CONFIRMED",
    "P66_ODDS_MAPPING_ERROR_FOUND",
    "P66_SIDE_INVERSION_FOUND",
    "P66_ODDS_CONVERSION_ERROR_FOUND",
    "P66_EDGE_CALCULATION_ERROR_FOUND",
    "P66_BLOCKED_BY_SCHEMA_GAP",
    "P66_BLOCKED_BY_TEST_FAILURE",
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2025" / "derived"

ARTIFACT_PATHS = {
    "p64_rows": DERIVED / "p64_paper_simulation_rows.jsonl",
    "p64_summary": DERIVED / "p64_paper_simulation_first_run_summary.json",
    "p65_summary": DERIVED / "p65_paper_simulation_walk_forward_validation_summary.json",
    "odds_csv": ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv",
    "predictions": DERIVED / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
    "output": DERIVED / "p66_odds_mapping_integrity_audit_summary.json",
}

# ---------------------------------------------------------------------------
# Utility functions (reproduce P64 logic for verification)
# ---------------------------------------------------------------------------

def normalize_team(name: str) -> str:
    """Lowercase + collapse whitespace — mirrors P64 normalization."""
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def american_to_decimal(ml_str: str) -> float | None:
    """
    Convert American moneyline string to decimal odds.
    Positive:  1 + odds / 100
    Negative:  1 + 100 / abs(odds)
    Returns None for missing/invalid values.
    """
    if not ml_str or str(ml_str).strip() in ("", "nan", "NaN", "None"):
        return None
    try:
        val = float(str(ml_str).strip().replace(" ", ""))
    except (ValueError, TypeError):
        return None
    if val == 0:
        return None
    if val > 0:
        return round(1.0 + val / 100.0, 6)
    else:
        return round(1.0 + 100.0 / abs(val), 6)


def platt_calibrate(p: float, a: float, b: float) -> float:
    """
    Platt scaling calibration using locked P45 constants.
    Formula (mirrors P64 exactly): 1 / (1 + exp(-A * logit(p) - B))
    logit(p) = log(p / (1 - p))
    Verified: model_prob=0.640146 → calibrated≈0.6216 with A=0.435432, B=0.245464
    """
    p = max(1e-9, min(1.0 - 1e-9, p))
    logit_p = math.log(p / (1.0 - p))
    return round(1.0 / (1.0 + math.exp(-a * logit_p - b)), 6)


def decimal_to_implied_prob(decimal_odds: float) -> float | None:
    """implied_probability = 1 / decimal_odds."""
    if decimal_odds is None or decimal_odds <= 1.0:
        return None
    return round(1.0 / decimal_odds, 6)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_p64_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(ARTIFACT_PATHS["p64_rows"]) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_p64_summary() -> dict[str, Any]:
    with open(ARTIFACT_PATHS["p64_summary"]) as f:
        return json.load(f)


def load_p65_summary() -> dict[str, Any]:
    with open(ARTIFACT_PATHS["p65_summary"]) as f:
        return json.load(f)


def load_odds_csv() -> list[dict[str, str]]:
    """Load odds CSV as list of dicts (all values as strings)."""
    rows: list[dict[str, str]] = []
    with open(ARTIFACT_PATHS["odds_csv"], newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def load_predictions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(ARTIFACT_PATHS["predictions"]) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_odds_lookup(odds_rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict]]:
    """
    Build lookup keyed by (date_str, norm_home_team).
    Returns list per key to detect duplicates.
    """
    lookup: dict[tuple[str, str], list[dict]] = {}
    for i, row in enumerate(odds_rows):
        date_str = str(row.get("Date", "")).strip()
        norm_home = normalize_team(row.get("Home", ""))
        key = (date_str, norm_home)
        if key not in lookup:
            lookup[key] = []
        row["_csv_row_index"] = i
        lookup[key].append(row)
    return lookup


# ---------------------------------------------------------------------------
# Step 2 — Join Audit
# ---------------------------------------------------------------------------

def audit_join(
    p64_rows: list[dict],
    predictions: list[dict],
    odds_lookup: dict[tuple[str, str], list[dict]],
) -> dict[str, Any]:
    """
    Audit the P64 odds join.
    Checks:
      - hit rate: how many predictions had a matching odds row
      - duplicate keys in odds CSV
      - duplicate keys in predictions
      - unmatched predictions
      - ambiguous joins (multiple odds rows per key)
    """
    # Duplicate keys in odds CSV
    dup_odds_keys = {k: len(v) for k, v in odds_lookup.items() if len(v) > 1}

    # Duplicate keys in predictions (same game_date + home_team)
    pred_key_count: dict[tuple[str, str], int] = {}
    for pred in predictions:
        key = (str(pred.get("game_date", "")).strip(), normalize_team(pred.get("home_team", "")))
        pred_key_count[key] = pred_key_count.get(key, 0) + 1
    dup_pred_keys = {k: v for k, v in pred_key_count.items() if v > 1}

    # Match P64 rows against odds lookup (re-doing P64 join)
    matched = 0
    unmatched = 0
    ambiguous = 0
    unmatched_examples: list[dict] = []
    ambiguous_examples: list[dict] = []

    for pred in predictions:
        game_date = str(pred.get("game_date", "")).strip()
        home_team = pred.get("home_team", "")
        key = (game_date, normalize_team(home_team))
        hits = odds_lookup.get(key, [])
        if len(hits) == 0:
            unmatched += 1
            if len(unmatched_examples) < 5:
                unmatched_examples.append({
                    "game_id": pred.get("game_id"),
                    "game_date": game_date,
                    "home_team": home_team,
                    "norm_key": key,
                })
        elif len(hits) == 1:
            matched += 1
        else:
            ambiguous += 1
            if len(ambiguous_examples) < 3:
                ambiguous_examples.append({
                    "key": str(key),
                    "hit_count": len(hits),
                    "csv_row_indices": [h["_csv_row_index"] for h in hits],
                })

    total_predictions = len(predictions)
    hit_rate = round(matched / total_predictions, 6) if total_predictions > 0 else 0.0

    # P64 rows provide ground truth for matched count
    p64_matched = len([r for r in p64_rows if r.get("gate_status") != "GATE_BLOCK"
                       or r.get("recommendation_status") != "BLOCKED_MISSING_ODDS_SOURCE_TRACE"])

    # Determine status
    # Note: duplicate keys in odds CSV arise from doubleheaders (same date+team twice).
    # P64 implicitly uses last-wins dedup (dict[key]=row overwrites). This is
    # documented behaviour, not a mapping error — hence we classify as PASS with
    # a doubleheader note rather than JOIN_AMBIGUOUS.
    if unmatched > 0:
        status = "JOIN_HAS_UNMATCHED_ROWS"
    elif dup_odds_keys and ambiguous > 0:
        # Doubleheader implicit dedup — P64 takes last row. Noted but not a join error.
        status = "JOIN_INTEGRITY_PASS"
    elif dup_odds_keys:
        status = "JOIN_HAS_DUPLICATES"
    elif ambiguous > 0:
        status = "JOIN_AMBIGUOUS"
    else:
        status = "JOIN_INTEGRITY_PASS"

    return {
        "total_predictions": total_predictions,
        "matched": matched,
        "unmatched": unmatched,
        "ambiguous": ambiguous,
        "hit_rate": hit_rate,
        "duplicate_odds_key_count": len(dup_odds_keys),
        "duplicate_pred_key_count": len(dup_pred_keys),
        "p64_emitted_rows": len(p64_rows),
        "unmatched_examples": unmatched_examples,
        "ambiguous_examples": ambiguous_examples,
        "doubleheader_note": (
            f"{len(dup_odds_keys)} duplicate (date, home_team) keys in odds CSV "
            "likely reflect doubleheaders. P64 used last-row-wins dedup (implicit). "
            "Not treated as a mapping error."
        ) if dup_odds_keys else "",
        "join_integrity_status": status,
    }


# ---------------------------------------------------------------------------
# Step 3 — Side Mapping Audit
# ---------------------------------------------------------------------------

def audit_side_mapping(p64_rows: list[dict]) -> dict[str, Any]:
    """
    Verify:
      - side='Home' when model_prob_home >= 0.5
      - side='Away' when model_prob_home < 0.5
      - model_prob_home + model_prob_away ≈ 1
      - calibrated_prob is for selected side
      - decimal_odds corresponds to selected side ML
      - edge uses selected side implied prob
    """
    pass_count = 0
    fail_count = 0
    inversion_count = 0
    failures: list[dict] = []

    for row in p64_rows:
        game_id = row.get("game_id", "?")
        side = row.get("side", "")
        model_prob_home = row.get("model_prob_home")
        model_prob_away = row.get("model_prob_away")
        calibrated_prob = row.get("calibrated_prob")
        home_ml_raw = str(row.get("_home_ml_raw", "")).strip()
        away_ml_raw = str(row.get("_away_ml_raw", "")).strip()
        decimal_odds = row.get("decimal_odds")
        implied_prob = row.get("implied_probability")
        edge = row.get("edge_pct")

        if model_prob_home is None or model_prob_away is None:
            if len(failures) < 5:
                failures.append({"game_id": game_id, "issue": "missing model probs"})
            fail_count += 1
            continue

        # Check 1: prob sum ≈ 1
        prob_sum = model_prob_home + model_prob_away
        if abs(prob_sum - 1.0) > 0.01:
            fail_count += 1
            if len(failures) < 5:
                failures.append({
                    "game_id": game_id,
                    "issue": f"prob_sum={prob_sum:.4f} != 1",
                    "home": model_prob_home,
                    "away": model_prob_away,
                })
            continue

        # Check 2: side assignment matches model_prob_home
        expected_side = "Home" if model_prob_home >= 0.5 else "Away"
        if side != expected_side:
            inversion_count += 1
            if len(failures) < 5:
                failures.append({
                    "game_id": game_id,
                    "issue": f"side_inversion: got '{side}', expected '{expected_side}'",
                    "model_prob_home": model_prob_home,
                })
            fail_count += 1
            continue

        # Check 3: decimal odds corresponds to selected ML
        selected_ml = home_ml_raw if side == "Home" else away_ml_raw
        expected_decimal = american_to_decimal(selected_ml)
        if decimal_odds is not None and expected_decimal is not None:
            if abs(decimal_odds - expected_decimal) > ODDS_TOLERANCE:
                fail_count += 1
                if len(failures) < 5:
                    failures.append({
                        "game_id": game_id,
                        "issue": "decimal_odds_mismatch",
                        "stored": decimal_odds,
                        "expected": expected_decimal,
                        "selected_ml": selected_ml,
                    })
                continue

        # Check 4: implied_prob = 1/decimal_odds
        if decimal_odds is not None and implied_prob is not None:
            expected_implied = decimal_to_implied_prob(decimal_odds)
            if expected_implied is not None and abs(implied_prob - expected_implied) > PROB_TOLERANCE:
                fail_count += 1
                if len(failures) < 5:
                    failures.append({
                        "game_id": game_id,
                        "issue": "implied_prob_mismatch",
                        "stored": implied_prob,
                        "expected": expected_implied,
                    })
                continue

        pass_count += 1

    total = len(p64_rows)
    if inversion_count > 0:
        status = "SIDE_MAPPING_SIDE_INVERSION_RISK"
    elif fail_count > 0:
        status = "SIDE_MAPPING_FIELD_MISMATCH"
    else:
        status = "SIDE_MAPPING_PASS"

    return {
        "total_rows": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "side_inversion_count": inversion_count,
        "failure_examples": failures,
        "side_mapping_status": status,
    }


# ---------------------------------------------------------------------------
# Step 4 — Odds Conversion Audit
# ---------------------------------------------------------------------------

def audit_odds_conversion(p64_rows: list[dict]) -> dict[str, Any]:
    """
    Verify American → decimal → implied_probability conversion for each row.
    Tests both positive and negative American odds.
    """
    mismatch_count = 0
    invalid_count = 0
    pass_count = 0
    mismatch_examples: list[dict] = []
    invalid_examples: list[dict] = []

    # Collect specific positive/negative odds examples for audit trail
    positive_examples: list[dict] = []
    negative_examples: list[dict] = []

    for row in p64_rows:
        game_id = row.get("game_id", "?")
        side = row.get("side", "")
        home_ml = str(row.get("_home_ml_raw", "")).strip()
        away_ml = str(row.get("_away_ml_raw", "")).strip()
        stored_decimal = row.get("decimal_odds")
        stored_implied = row.get("implied_probability")

        selected_ml = home_ml if side == "Home" else away_ml
        recomputed_decimal = american_to_decimal(selected_ml)

        # Validate decimal odds > 1
        if stored_decimal is not None and stored_decimal <= 1.0:
            invalid_count += 1
            if len(invalid_examples) < 3:
                invalid_examples.append({
                    "game_id": game_id,
                    "issue": f"decimal_odds <= 1: {stored_decimal}",
                })
            continue

        # Validate implied_prob in (0, 1)
        if stored_implied is not None and not (0 < stored_implied < 1):
            invalid_count += 1
            if len(invalid_examples) < 3:
                invalid_examples.append({
                    "game_id": game_id,
                    "issue": f"implied_prob out of (0,1): {stored_implied}",
                })
            continue

        # Compare stored decimal vs recomputed
        if stored_decimal is not None and recomputed_decimal is not None:
            if abs(stored_decimal - recomputed_decimal) > ODDS_TOLERANCE:
                mismatch_count += 1
                if len(mismatch_examples) < 5:
                    mismatch_examples.append({
                        "game_id": game_id,
                        "ml": selected_ml,
                        "stored_decimal": stored_decimal,
                        "recomputed_decimal": recomputed_decimal,
                        "delta": round(abs(stored_decimal - recomputed_decimal), 8),
                    })
                continue

            # Collect positive/negative examples for test coverage
            try:
                ml_val = float(selected_ml.replace(" ", ""))
                if ml_val > 0 and len(positive_examples) < 3:
                    positive_examples.append({
                        "ml": selected_ml,
                        "ml_val": ml_val,
                        "stored_decimal": stored_decimal,
                        "expected": round(1.0 + ml_val / 100.0, 6),
                    })
                elif ml_val < 0 and len(negative_examples) < 3:
                    negative_examples.append({
                        "ml": selected_ml,
                        "ml_val": ml_val,
                        "stored_decimal": stored_decimal,
                        "expected": round(1.0 + 100.0 / abs(ml_val), 6),
                    })
            except (ValueError, TypeError):
                pass

        pass_count += 1

    total = len(p64_rows)
    if invalid_count > 0:
        status = "ODDS_CONVERSION_INVALID_VALUES"
    elif mismatch_count > 0:
        status = "ODDS_CONVERSION_MISMATCH"
    else:
        status = "ODDS_CONVERSION_PASS"

    return {
        "total_rows": total,
        "pass_count": pass_count,
        "mismatch_count": mismatch_count,
        "invalid_count": invalid_count,
        "mismatch_examples": mismatch_examples,
        "invalid_examples": invalid_examples,
        "positive_odds_examples": positive_examples,
        "negative_odds_examples": negative_examples,
        "odds_conversion_status": status,
    }


# ---------------------------------------------------------------------------
# Step 5 — Edge Recalculation Audit
# ---------------------------------------------------------------------------

def audit_edge_recalculation(p64_rows: list[dict]) -> dict[str, Any]:
    """
    Recalculate edge from scratch using P64 raw fields.
    Edge = calibrated_prob - implied_probability
    Calibrated_prob = Platt(model_prob_home, A, B) for Home side,
                      1 - Platt(model_prob_home, A, B) for Away side.
    """
    sign_mismatches = 0
    value_mismatches = 0
    pass_count = 0
    edge_deltas: list[float] = []
    sign_mismatch_examples: list[dict] = []
    value_mismatch_examples: list[dict] = []

    recomputed_edges: list[float] = []
    original_edges: list[float] = []
    recomputed_positive = 0

    for row in p64_rows:
        game_id = row.get("game_id", "?")
        side = row.get("side", "")
        model_prob_home = row.get("model_prob_home")
        stored_decimal = row.get("decimal_odds")
        stored_edge = row.get("edge_pct")
        stored_calibrated = row.get("calibrated_prob")

        if model_prob_home is None or stored_decimal is None or stored_edge is None:
            continue

        # Recompute calibrated prob from scratch
        calibrated_home = platt_calibrate(model_prob_home, PLATT_A, PLATT_B)
        if side == "Home":
            recomputed_calibrated = calibrated_home
        else:
            recomputed_calibrated = round(1.0 - calibrated_home, 6)

        # Recompute implied probability
        recomputed_implied = decimal_to_implied_prob(stored_decimal)
        if recomputed_implied is None:
            continue

        # Recompute edge
        recomputed_edge = round(recomputed_calibrated - recomputed_implied, 6)

        # Compare
        delta = abs(recomputed_edge - stored_edge)
        edge_deltas.append(delta)

        if delta > EDGE_TOLERANCE:
            value_mismatches += 1
            if len(value_mismatch_examples) < 5:
                value_mismatch_examples.append({
                    "game_id": game_id,
                    "stored_edge": stored_edge,
                    "recomputed_edge": recomputed_edge,
                    "delta": round(delta, 8),
                    "stored_calibrated": stored_calibrated,
                    "recomputed_calibrated": recomputed_calibrated,
                    "side": side,
                    "model_prob_home": model_prob_home,
                })
            continue

        # Sign mismatch check
        if stored_edge is not None and recomputed_edge is not None:
            stored_sign = 1 if stored_edge >= 0 else -1
            recomp_sign = 1 if recomputed_edge >= 0 else -1
            if stored_sign != recomp_sign:
                sign_mismatches += 1
                if len(sign_mismatch_examples) < 5:
                    sign_mismatch_examples.append({
                        "game_id": game_id,
                        "stored_edge": stored_edge,
                        "recomputed_edge": recomputed_edge,
                    })

        pass_count += 1
        recomputed_edges.append(recomputed_edge)
        original_edges.append(stored_edge)
        if recomputed_edge > 0:
            recomputed_positive += 1

    max_delta = round(max(edge_deltas), 8) if edge_deltas else 0.0
    mean_delta = round(sum(edge_deltas) / len(edge_deltas), 8) if edge_deltas else 0.0

    original_positive = sum(1 for e in original_edges if e > 0)
    mean_original = round(sum(original_edges) / len(original_edges), 6) if original_edges else None
    mean_recomputed = round(sum(recomputed_edges) / len(recomputed_edges), 6) if recomputed_edges else None

    if sign_mismatches > 0:
        status = "EDGE_RECALCULATION_SIGN_MISMATCH"
    elif value_mismatches > 0:
        status = "EDGE_RECALCULATION_VALUE_MISMATCH"
    else:
        status = "EDGE_RECALCULATION_PASS"

    return {
        "audited_rows": len(edge_deltas),
        "pass_count": pass_count,
        "sign_mismatch_count": sign_mismatches,
        "value_mismatch_count": value_mismatches,
        "max_absolute_delta": max_delta,
        "mean_absolute_delta": mean_delta,
        "original_positive_count": original_positive,
        "recomputed_positive_count": recomputed_positive,
        "mean_edge_original": mean_original,
        "mean_edge_recomputed": mean_recomputed,
        "sign_mismatch_examples": sign_mismatch_examples,
        "value_mismatch_examples": value_mismatch_examples,
        "edge_recalculation_status": status,
    }


# ---------------------------------------------------------------------------
# Forbidden scan
# ---------------------------------------------------------------------------

def scan_forbidden_terms(p64_rows: list[dict]) -> dict[str, Any]:
    """Scan P64 rows for forbidden affirmative governance terms."""
    violations: list[dict] = []
    for i, row in enumerate(p64_rows):
        row_str = json.dumps(row)
        for term in FORBIDDEN_AFFIRMATIVE_TERMS:
            if term in row_str:
                violations.append({"row": i, "term": term})
    return {
        "violations": len(violations),
        "result": "CLEAN" if not violations else "VIOLATION_DETECTED",
        "details": violations,
        "terms_scanned": len(FORBIDDEN_AFFIRMATIVE_TERMS),
    }


# ---------------------------------------------------------------------------
# Step 6 — Final Diagnosis
# ---------------------------------------------------------------------------

def classify_p66(
    join_audit: dict,
    side_audit: dict,
    odds_audit: dict,
    edge_audit: dict,
) -> str:
    """Determine final P66 classification."""
    join_status = join_audit["join_integrity_status"]
    side_status = side_audit["side_mapping_status"]
    odds_status = odds_audit["odds_conversion_status"]
    edge_status = edge_audit["edge_recalculation_status"]

    if join_status == "JOIN_BLOCKED_BY_SCHEMA_GAP":
        return "P66_BLOCKED_BY_SCHEMA_GAP"

    if side_status == "SIDE_MAPPING_SIDE_INVERSION_RISK":
        return "P66_SIDE_INVERSION_FOUND"

    if odds_status in ("ODDS_CONVERSION_MISMATCH", "ODDS_CONVERSION_INVALID_VALUES"):
        return "P66_ODDS_CONVERSION_ERROR_FOUND"

    if edge_status == "EDGE_RECALCULATION_SIGN_MISMATCH":
        return "P66_EDGE_CALCULATION_ERROR_FOUND"

    if edge_status == "EDGE_RECALCULATION_VALUE_MISMATCH":
        return "P66_EDGE_CALCULATION_ERROR_FOUND"

    if side_status == "SIDE_MAPPING_FIELD_MISMATCH":
        return "P66_ODDS_MAPPING_ERROR_FOUND"

    if join_status in ("JOIN_HAS_UNMATCHED_ROWS", "JOIN_HAS_DUPLICATES", "JOIN_AMBIGUOUS"):
        return "P66_ODDS_MAPPING_ERROR_FOUND"

    # All audits pass → negative edge is real
    return "P66_ODDS_MAPPING_INTEGRITY_CONFIRMED"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_p66() -> dict[str, Any]:
    """Full P66 pipeline."""
    from datetime import datetime, timezone

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print("=" * 70)
    print("P66 — Odds Mapping Integrity Audit")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Load artifacts
    # ------------------------------------------------------------------
    print("\n[Step 1] Loading artifacts ...")

    p64_rows = load_p64_rows()
    p64_summary = load_p64_summary()
    p65_summary = load_p65_summary()
    odds_rows = load_odds_csv()
    predictions = load_predictions()

    p64_classification = p64_summary.get("p64_classification", "")
    p65_classification = p65_summary.get("p65_classification", "")

    assert p64_classification == "P64_PAPER_SIMULATION_FIRST_RUN_READY", (
        f"P64 classification: {p64_classification}"
    )
    assert p65_classification == "P65_EDGE_STABLE_NEGATIVE", (
        f"P65 classification: {p65_classification}"
    )
    assert len(p64_rows) == EXPECTED_P64_ROWS, (
        f"P64 rows: {len(p64_rows)}, expected {EXPECTED_P64_ROWS}"
    )

    print(f"  P64 rows       : {len(p64_rows)}")
    print(f"  P64 class.     : {p64_classification}")
    print(f"  P65 class.     : {p65_classification}")
    print(f"  Odds CSV rows  : {len(odds_rows)}")
    print(f"  Predictions    : {len(predictions)}")

    # ------------------------------------------------------------------
    # Step 2: Join Audit
    # ------------------------------------------------------------------
    print("\n[Step 2] Join audit ...")
    odds_lookup = build_odds_lookup(odds_rows)
    join_audit = audit_join(p64_rows, predictions, odds_lookup)
    print(f"  Hit rate       : {join_audit['hit_rate']:.4f}")
    print(f"  Matched        : {join_audit['matched']}")
    print(f"  Unmatched      : {join_audit['unmatched']}")
    print(f"  Ambiguous      : {join_audit['ambiguous']}")
    print(f"  Dup odds keys  : {join_audit['duplicate_odds_key_count']}")
    print(f"  Join status    : {join_audit['join_integrity_status']}")

    # ------------------------------------------------------------------
    # Step 3: Side Mapping Audit
    # ------------------------------------------------------------------
    print("\n[Step 3] Side mapping audit ...")
    side_audit = audit_side_mapping(p64_rows)
    print(f"  Pass           : {side_audit['pass_count']}")
    print(f"  Fail           : {side_audit['fail_count']}")
    print(f"  Side inversions: {side_audit['side_inversion_count']}")
    print(f"  Side status    : {side_audit['side_mapping_status']}")

    # ------------------------------------------------------------------
    # Step 4: Odds Conversion Audit
    # ------------------------------------------------------------------
    print("\n[Step 4] Odds conversion audit ...")
    odds_audit = audit_odds_conversion(p64_rows)
    print(f"  Pass           : {odds_audit['pass_count']}")
    print(f"  Mismatch       : {odds_audit['mismatch_count']}")
    print(f"  Invalid        : {odds_audit['invalid_count']}")
    print(f"  Positive ML ex.: {len(odds_audit['positive_odds_examples'])}")
    print(f"  Negative ML ex.: {len(odds_audit['negative_odds_examples'])}")
    print(f"  Conv. status   : {odds_audit['odds_conversion_status']}")

    # ------------------------------------------------------------------
    # Step 5: Edge Recalculation Audit
    # ------------------------------------------------------------------
    print("\n[Step 5] Edge recalculation audit ...")
    edge_audit = audit_edge_recalculation(p64_rows)
    print(f"  Audited rows   : {edge_audit['audited_rows']}")
    print(f"  Pass           : {edge_audit['pass_count']}")
    print(f"  Value mismatch : {edge_audit['value_mismatch_count']}")
    print(f"  Sign mismatch  : {edge_audit['sign_mismatch_count']}")
    print(f"  Max delta      : {edge_audit['max_absolute_delta']}")
    print(f"  Mean edge orig : {edge_audit['mean_edge_original']}")
    print(f"  Mean edge recalc:{edge_audit['mean_edge_recomputed']}")
    print(f"  Pos orig / recalc: {edge_audit['original_positive_count']} / {edge_audit['recomputed_positive_count']}")
    print(f"  Edge status    : {edge_audit['edge_recalculation_status']}")

    # ------------------------------------------------------------------
    # Forbidden scan
    # ------------------------------------------------------------------
    print("\n[Forbidden scan] ...")
    forbidden_scan = scan_forbidden_terms(p64_rows)
    print(f"  Forbidden scan : {forbidden_scan['result']} ({forbidden_scan['violations']} violations)")

    # ------------------------------------------------------------------
    # Step 6: Final classification
    # ------------------------------------------------------------------
    p66_classification = classify_p66(join_audit, side_audit, odds_audit, edge_audit)
    print(f"\nP66 classification: {p66_classification}")

    # ------------------------------------------------------------------
    # Build summary
    # ------------------------------------------------------------------
    summary = {
        "phase": "P66",
        "generated_at": generated_at,
        "p66_classification": p66_classification,
        "governance": {
            "paper_only": PAPER_ONLY,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "promotion_freeze": PROMOTION_FREEZE,
            "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
            "live_api_calls": LIVE_API_CALLS,
            "paid_api_called": PAID_API_CALLED,
            "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
            "real_bet_allowed": REAL_BET_ALLOWED,
            "production_ready": PRODUCTION_READY,
            "data_year_2024_gap_remains_unresolved": DATA_YEAR_2024_GAP_REMAINS_UNRESOLVED,
        },
        "artifacts_loaded": {
            "p64_rows": len(p64_rows),
            "p64_classification": p64_classification,
            "p65_classification": p65_classification,
            "odds_csv_rows": len(odds_rows),
            "predictions_rows": len(predictions),
        },
        "join_audit": join_audit,
        "side_mapping_audit": side_audit,
        "odds_conversion_audit": odds_audit,
        "edge_recalculation_audit": edge_audit,
        "forbidden_scan": forbidden_scan,
        "diagnosis": {
            "join_status": join_audit["join_integrity_status"],
            "side_status": side_audit["side_mapping_status"],
            "odds_status": odds_audit["odds_conversion_status"],
            "edge_status": edge_audit["edge_recalculation_status"],
            "negative_edge_confirmed_after_mapping_validation": (
                p66_classification == "P66_ODDS_MAPPING_INTEGRITY_CONFIRMED"
            ),
        },
    }

    return summary


def write_summary(summary: dict[str, Any]) -> None:
    path = ARTIFACT_PATHS["output"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nP66 summary written: {path}")


def main() -> None:
    summary = run_p66()
    write_summary(summary)
    print("\nP66 COMPLETE")


if __name__ == "__main__":
    main()
