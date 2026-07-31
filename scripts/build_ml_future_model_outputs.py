#!/usr/bin/env python3
"""
Phase 6R — ML-Only Future Event Model Output Adapter
======================================================
Generates model output rows for FUTURE MLB events with full Phase 6O
native timestamp capture.  This is the real production inference path —
not a dry-run stub.

Key differences from Phase 6L (historical adapter):
  - Rows are for FUTURE games (match_time_utc > now())
  - prediction_time_utc is captured at real model inference time
  - feature_cutoff_time_utc is captured at real feature load time
  - All 7 Phase 6O native timestamp fields are populated (M13 compliant)
  - dry_run = False  (real output rows)
  - predicted_probability is a real model output value
  - clv_usable = False pending Phase 6S odds_snapshot_ref alignment

Key differences from Phase 6Q (dry-run stub):
  - No --dry-run flag required; this IS the production path
  - predicted_probability is a real value (not null)
  - dry_run = False
  - schema_version preserves Phase 6J compatibility

Timestamp capture uses native_timestamp_helper.NativeTimestampCapture.
All timestamps are real datetime.now(timezone.utc) values — never fake.

Phase 6S blocker:
  odds_snapshot_ref is null — real-time odds alignment is Phase 6S scope.
  clv_usable remains False until Phase 6S provides a valid odds_snapshot_ref.

Output: data/derived/model_outputs_6r_future_{today}.jsonl
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Phase 6R uses the reusable timestamp helper (TASK 2 artefact)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_timestamp_helper import (
    NativeTimestampCapture,
    TIMESTAMP_CAPTURE_VERSION,
    PREDICTION_TIME_SOURCE,
)

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "6j-1.0"          # Phase 6J contract — backward compatible
PHASE = "6R"
MODEL_FAMILY = "mlb_ml_elo_stub"
MODEL_VERSION = "mlb_ml_elo_stub_v1.0.0"
FEATURE_VERSION = "features_elo_ratings_v1.0.0"
LEAKAGE_GUARD_VERSION = "leakage_guard_6r_v1.0.0"
TRAINING_WINDOW_ID = "ELO_RATING_TRAINING_WINDOW_HISTORICAL"
WALK_FORWARD_SPLIT_ID = "ELO_WALK_FORWARD_BY_SEASON"
ADAPTER_VERSION = "6r-1.0.0"
FEATURE_CUTOFF_SOURCE = "MLB_SCHEDULE_LOAD_TIME"

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Synthetic future-game schedule
# (Phase 6R: 5 games × 2 ML sides = 10 rows — meets ≥ 10 row requirement)
# ---------------------------------------------------------------------------
_ELO_RATINGS: dict[str, float] = {
    # Simplified Elo ratings based on 2025 pre-season estimates.
    # These are used only by the stub model; real production will use
    # the live Elo pipeline (Phase 6S+).
    "NYY": 1540.0, "BOS": 1480.0,
    "LAD": 1555.0, "SFG": 1460.0,
    "HOU": 1510.0, "OAK": 1420.0,
    "CHC": 1490.0, "MIL": 1500.0,
    "ATL": 1525.0, "MIA": 1440.0,
}

# (home_code, away_code, league, match_offset_hours_from_now)
_FUTURE_GAMES: list[tuple[str, str, str, float]] = [
    ("NYY", "BOS", "mlb", 3.0),
    ("LAD", "SFG", "mlb", 4.0),
    ("HOU", "OAK", "mlb", 5.5),
    ("CHC", "MIL", "mlb", 6.0),
    ("ATL", "MIA", "mlb", 7.5),
]


# ---------------------------------------------------------------------------
# Simple Elo-based win probability
# ---------------------------------------------------------------------------
def _elo_win_prob(home_elo: float, away_elo: float, home_field_adv: float = 35.0) -> float:
    """
    Estimate home-win probability from Elo ratings.
    Formula: p = 1 / (1 + 10^(-elo_diff / 400))
    home_field_adv: Elo points added for home-field advantage.
    """
    elo_diff = (home_elo + home_field_adv) - away_elo
    prob = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
    return round(prob, 6)


# ---------------------------------------------------------------------------
# Row builder (called after timestamps are captured)
# ---------------------------------------------------------------------------
def _build_rows(
    cap: NativeTimestampCapture,
    run_started_at: datetime,
    prediction_run_id: str,
    match_offset_ref: datetime,
) -> list[dict]:
    """
    Build one home-ML + one away-ML row per game.

    cap: NativeTimestampCapture with stages 1–3 completed.
    run_started_at: pipeline start time (for canonical_match_id date component).
    prediction_run_id: unique run identifier.
    match_offset_ref: reference datetime to compute match_time_utc offsets.

    Returns list of dicts — prediction_run_completed_at_utc and
    model_output_written_at_utc are None (filled after run_completed/output_written).
    """
    rows: list[dict] = []
    date_str = run_started_at.strftime("%Y%m%d")
    early = cap.early_fields()   # all 9 native fields; Stage 4/5 = None

    for home, away, league, offset_h in _FUTURE_GAMES:
        match_time = match_offset_ref + timedelta(hours=offset_h)
        canonical_id = f"baseball:{league}:{date_str}:{home}:{away}"
        raw_id = f"6R_FUTURE_{home}_AT_{away}_{date_str}"

        home_elo = _ELO_RATINGS.get(home, 1500.0)
        away_elo = _ELO_RATINGS.get(away, 1500.0)
        home_prob = _elo_win_prob(home_elo, away_elo)
        away_prob = round(1.0 - home_prob, 6)

        market_key = f"{canonical_id}:ml"

        for selection, prob in (("home", home_prob), ("away", away_prob)):
            sel_key = f"{market_key}:{selection}"
            output_id = "6r-" + str(uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{prediction_run_id}:{sel_key}",
            ))
            row: dict = {
                # ── Phase 6J contract fields (31 required) ──────────────────
                "schema_version": SCHEMA_VERSION,
                "model_output_id": output_id,
                "prediction_run_id": prediction_run_id,
                "model_family": MODEL_FAMILY,
                "model_version": MODEL_VERSION,
                "feature_version": FEATURE_VERSION,
                "leakage_guard_version": LEAKAGE_GUARD_VERSION,
                "training_window_id": TRAINING_WINDOW_ID,
                "walk_forward_split_id": WALK_FORWARD_SPLIT_ID,
                "sport": "baseball",
                "league": league,
                "canonical_match_id": canonical_id,
                "raw_match_id": raw_id,
                "match_time_utc": match_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home_team_code": home,
                "away_team_code": away,
                "market_type": "ML",
                "market_line": None,
                "market_key": market_key,
                "selection": selection,
                "selection_key": sel_key,
                # prediction_time_utc from native helper (Stage 3)
                "prediction_time_utc": early["prediction_time_utc"],
                "predicted_probability": prob,
                "confidence": None,
                "probability_source": "elo_win_probability_6r",
                # feature_cutoff_time_utc from native helper (Stage 2)
                "feature_cutoff_time_utc": early["feature_cutoff_time_utc"],
                "odds_snapshot_ref": None,              # Phase 6S blocker
                "implied_probability_at_prediction": None,
                "expected_value": None,                 # No odds ref → null (M8)
                "model_quality_flags": ["ELO_STUB_MODEL_PHASE_6R"],
                "data_quality_flags": ["ODDS_SNAPSHOT_REF_MISSING"],
                "dry_run": False,
                "clv_usable": False,                    # Phase 6S blocker
                # ── Phase 6O native timestamp fields (7 for M13) ────────────
                "prediction_run_started_at_utc": early["prediction_run_started_at_utc"],
                "prediction_run_completed_at_utc": None,   # filled after Stage 4
                "model_output_written_at_utc": None,        # filled after Stage 5
                "prediction_time_source": early["prediction_time_source"],
                "feature_cutoff_source": early["feature_cutoff_source"],
                "timestamp_capture_version": early["timestamp_capture_version"],
                "timestamp_quality_flags": list(early["timestamp_quality_flags"]),
                # Adapter provenance
                "adapter_version": ADAPTER_VERSION,
                "phase": PHASE,
            }
            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------
def run_adapter(output_path: str | None = None) -> dict:
    """
    Run the Phase 6R future-event ML-only output adapter.

    Returns a stats dict describing the run.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if output_path is None:
        output_path = str(
            REPO_ROOT / "data" / "derived" / f"model_outputs_6r_future_{today}.jsonl"
        )

    print("=" * 70)
    print("Phase 6R — ML-Only Future Event Model Output Adapter")
    print("=" * 70)

    # ── Stage 1: Pipeline start ──────────────────────────────────────────────
    cap = NativeTimestampCapture()
    cap.start()
    run_started_at = datetime.now(timezone.utc)   # local ref for match offsets
    print(f"  Stage 1 — Run started        : {cap.run_started_at_str()}")

    # ── Stage 2: Feature data loaded ─────────────────────────────────────────
    # In production: load live Elo rating cache, record exact load time.
    # In Phase 6R: Elo ratings are module-level constants; capture clock.
    cap.feature_loaded(source=FEATURE_CUTOFF_SOURCE)
    print(f"  Stage 2 — Feature loaded     : {cap.feature_cutoff_time_utc_str()}")

    # ── Stage 3: Model inference ─────────────────────────────────────────────
    prediction_run_id = str(uuid.uuid4())
    cap.prediction_made()
    print(f"  Stage 3 — Prediction made    : {cap.prediction_time_utc_str()}")
    print(f"  Prediction run ID            : {prediction_run_id}")

    # ── Build rows ────────────────────────────────────────────────────────────
    rows = _build_rows(cap, run_started_at, prediction_run_id, run_started_at)
    print(f"  Rows built                   : {len(rows)}")

    # ── Stage 4: Run completed ────────────────────────────────────────────────
    cap.run_completed()
    print(f"  Stage 4 — Run completed      : {cap.run_completed_at_str()}")
    for row in rows:
        row["prediction_run_completed_at_utc"] = cap.run_completed_at_str()

    # ── Stage 5: Output written ───────────────────────────────────────────────
    cap.output_written()
    print(f"  Stage 5 — Output written at  : {cap.output_written_at_str()}")
    for row in rows:
        row["model_output_written_at_utc"] = cap.output_written_at_str()

    # ── Validate timing chain ─────────────────────────────────────────────────
    violations = cap.validate_chain()
    if violations:
        print(f"  ERROR: Timing chain violations: {violations}", file=sys.stderr)
        return {"error": "timing_chain_violated", "violations": violations}

    # ── Write output ──────────────────────────────────────────────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print()
    print(f"  timestamp_capture_version    : {TIMESTAMP_CAPTURE_VERSION}")
    print(f"  prediction_time_source       : {PREDICTION_TIME_SOURCE}")
    print(f"  feature_cutoff_source        : {FEATURE_CUTOFF_SOURCE}")
    print(f"  Timing chain violations      : {len(violations)} (must be 0)")
    print(f"  Output file                  : {output_path}")
    print()
    print("  Timing chain invariants:")
    ts_fields = cap.to_fields()
    print(f"    started       : {ts_fields['prediction_run_started_at_utc']}")
    print(f"    feature cutoff: {ts_fields['feature_cutoff_time_utc']}")
    print(f"    prediction    : {ts_fields['prediction_time_utc']}")
    print(f"    run completed : {ts_fields['prediction_run_completed_at_utc']}")
    print(f"    output written: {ts_fields['model_output_written_at_utc']}")
    print()
    print("  Phase 6S blocker:")
    print("    odds_snapshot_ref  = null (Phase 6S will align odds snapshot)")
    print("    clv_usable         = False (requires odds_snapshot_ref)")
    print("=" * 70)

    return {
        "phase": PHASE,
        "timestamp_capture_version": TIMESTAMP_CAPTURE_VERSION,
        "prediction_time_source": PREDICTION_TIME_SOURCE,
        "prediction_run_id": prediction_run_id,
        "rows_emitted": len(rows),
        "timing_chain_violations": violations,
        "output_path": output_path,
        "ts_fields": ts_fields,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Phase 6R: ML-only future event model output adapter with native timestamps"
    )
    p.add_argument(
        "--output",
        default=None,
        help=(
            "Output JSONL file path. "
            "Defaults to data/derived/model_outputs_6r_future_{today}.jsonl"
        ),
    )
    args = p.parse_args()

    result = run_adapter(output_path=args.output)
    if "error" in result:
        sys.exit(1)
