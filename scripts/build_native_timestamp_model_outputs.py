#!/usr/bin/env python3
"""
Phase 6Q — Native Timestamp Model Output Stub
==============================================
Generates model output rows with full Phase 6O native timestamp capture.
All timestamps are real system-clock values captured at inference runtime.

In --dry-run mode: emits 30 synthetic future-game rows (all dry_run=true)
that satisfy all 31 Phase 6J contract fields AND all 7 Phase 6O native
timestamp fields, designed to pass the Phase 6P extended validator (M1–M13).

Timestamp source mapping (Phase 6O → Phase 6Q):
  "system_clock"     → prediction_time_source = "MODEL_INFERENCE_RUNTIME"
  "odds_snapshot"    → prediction_time_source = "MODEL_OUTPUT_EMISSION_RUNTIME"
  feature load time  → feature_cutoff_source  = "MLB_SCHEDULE_LOAD_TIME"

HARD RULES enforced:
  - Timestamps are real datetime.now(timezone.utc) values (not fabricated)
  - prediction_time_utc is always < match_time_utc (pre-game invariant)
  - Historical model output rows are NOT modified
  - Post-game / settlement data is NOT used
  - External APIs are NOT called
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "6q-dry-run-1.0"
TIMESTAMP_CAPTURE_VERSION = "6q-1.0"
PHASE = "6Q"

# Must be in Phase 6P validator's ALLOWED_PREDICTION_TIME_SOURCES.
# "system_clock" maps to this canonical value per Phase 6O specification.
PREDICTION_TIME_SOURCE = "MODEL_INFERENCE_RUNTIME"

# Must not be "UNKNOWN" — descriptive source for schedule-based feature loading.
FEATURE_CUTOFF_SOURCE = "MLB_SCHEDULE_LOAD_TIME"

# ── Synthetic game templates ──────────────────────────────────────────────────
# 5 hypothetical future MLB matchups — home, away, league
_SYNTHETIC_GAMES: list[tuple[str, str, str]] = [
    ("NYY", "BOS", "mlb"),
    ("LAD", "SFN", "mlb"),
    ("HOU", "TEX", "mlb"),
    ("CHN", "STL", "mlb"),
    ("ATL", "PHI", "mlb"),
]

# 3 market types × 2 sides = 6 rows per game × 5 games = 30 rows total
_MARKET_TEMPLATES: list[dict] = [
    {
        "market_type": "ML",
        "market_line": None,
        "sides": [
            {"selection": "home", "selection_key": "ml_home"},
            {"selection": "away", "selection_key": "ml_away"},
        ],
    },
    {
        "market_type": "RL",
        "market_line": -1.5,
        "sides": [
            {"selection": "home", "selection_key": "rl_home_-1.5"},
            {"selection": "away", "selection_key": "rl_away_+1.5"},
        ],
        "dq_flag": "MODEL_CAPABILITY_GAP_RL_LINE_SPECIFIC_PROBABILITY",
    },
    {
        "market_type": "OU",
        "market_line": 8.5,
        "sides": [
            {"selection": "over", "selection_key": "ou_over_8.5"},
            {"selection": "under", "selection_key": "ou_under_8.5"},
        ],
        "dq_flag": "MODEL_CAPABILITY_GAP_OU_TOTAL_DISTRIBUTION",
    },
]


# ── Argument parsing ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = argparse.ArgumentParser(
        description=(
            "Phase 6Q: Generate model output rows with Phase 6O native "
            "timestamp capture. Use --dry-run to emit synthetic rows."
        )
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Emit 30 synthetic dry-run rows with native timestamps. "
            "All rows have dry_run=true and predicted_probability=null."
        ),
    )
    p.add_argument(
        "--output",
        default=f"data/derived/model_outputs_6q_dry_run_{today}.jsonl",
        help="Output JSONL file path",
    )
    p.add_argument(
        "--match-offset-hours",
        type=float,
        default=4.0,
        metavar="HOURS",
        help=(
            "Hours from script runtime to set synthetic match_time_utc. "
            "Must be > 0 to satisfy pre-game timing invariant (M6)."
        ),
    )
    return p.parse_args()


# ── Timestamp helpers ────────────────────────────────────────────────────────

def _fmt_utc(dt: datetime) -> str:
    """Format a UTC datetime as ISO8601 string."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Row builder ──────────────────────────────────────────────────────────────

def _build_rows(
    run_started_at: datetime,
    feature_loaded_at: datetime,
    prediction_time: datetime,
    match_offset_hours: float,
    prediction_run_id: str,
) -> list[dict]:
    """
    Build synthetic model output rows.

    All Phase 6J (31 fields) + Phase 6O (7 native timestamp fields) are present.
    prediction_run_completed_at_utc and model_output_written_at_utc are set to
    None here and filled in by main() after the run completes.

    Timing invariants guaranteed at construction:
      feature_loaded_at <= prediction_time  (T2, M6)
      run_started_at    <= prediction_time  (T4, M6)
      match_time        >  prediction_time  (T1, M6)
    """
    rows: list[dict] = []
    date_str = run_started_at.strftime("%Y%m%d")

    for home, away, league in _SYNTHETIC_GAMES:
        match_time = run_started_at + timedelta(hours=match_offset_hours)
        canonical_id = f"baseball:{league}:{date_str}:{home}:{away}"
        raw_id = f"6Q_SYNTHETIC_{home}_AT_{away}_{date_str}"

        for market_tmpl in _MARKET_TEMPLATES:
            mt = market_tmpl["market_type"]
            line = market_tmpl["market_line"]
            line_str = f"_{line}" if line is not None else ""
            market_key = f"{canonical_id}:{mt.lower()}{line_str}"
            dq_flags: list[str] = (
                [market_tmpl["dq_flag"]] if "dq_flag" in market_tmpl else []
            )

            for side in market_tmpl["sides"]:
                output_id = str(uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{prediction_run_id}:{market_key}:{side['selection_key']}",
                ))
                rows.append({
                    # ── Phase 6J contract fields (31 required) ────────────────
                    "schema_version": SCHEMA_VERSION,
                    "model_output_id": output_id,
                    "prediction_run_id": prediction_run_id,
                    "model_family": "native_ts_stub",
                    "model_version": "native_ts_stub_v0.1.0",
                    "feature_version": "features_native_ts_stub_v0.1.0",
                    "leakage_guard_version": "leakage_guard_native_ts_v0.1.0",
                    "training_window_id": "NATIVE_TS_STUB_NO_TRAINING_WINDOW",
                    "walk_forward_split_id": "NATIVE_TS_STUB_NO_WALK_FORWARD",
                    "sport": "baseball",
                    "league": league,
                    "canonical_match_id": canonical_id,
                    "raw_match_id": raw_id,
                    "match_time_utc": _fmt_utc(match_time),
                    "home_team_code": home,
                    "away_team_code": away,
                    "market_type": mt,
                    "market_line": line,
                    "market_key": market_key,
                    "selection": side["selection"],
                    "selection_key": side["selection_key"],
                    "prediction_time_utc": _fmt_utc(prediction_time),
                    "predicted_probability": None,       # dry_run=true → null required (M7)
                    "confidence": None,
                    "probability_source": "NATIVE_TS_STUB_DRY_RUN",
                    "feature_cutoff_time_utc": _fmt_utc(feature_loaded_at),
                    "odds_snapshot_ref": None,           # no odds fetch in stub (M8 ok)
                    "implied_probability_at_prediction": None,
                    "expected_value": None,              # no odds_snapshot_ref → null (M8)
                    "model_quality_flags": ["NATIVE_TIMESTAMP_STUB"],
                    "data_quality_flags": dq_flags,
                    "dry_run": True,
                    "clv_usable": False,                 # dry_run rows are never CLV-usable
                    # ── Phase 6O native timestamp fields (7 required for M13) ─
                    "prediction_run_started_at_utc": _fmt_utc(run_started_at),
                    "prediction_run_completed_at_utc": None,  # filled after run
                    "model_output_written_at_utc": None,      # filled before write
                    "prediction_time_source": PREDICTION_TIME_SOURCE,
                    "feature_cutoff_source": FEATURE_CUTOFF_SOURCE,
                    "timestamp_capture_version": TIMESTAMP_CAPTURE_VERSION,
                    "timestamp_quality_flags": [],            # no flags — clean run
                    "odds_snapshot_time_utc": None,           # no odds fetch in stub
                })

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()

    if not args.dry_run:
        print(
            "ERROR: Phase 6Q stub requires --dry-run. "
            "Production inference pipeline is not yet implemented.",
            file=sys.stderr,
        )
        print(
            "  Usage: python3 scripts/build_native_timestamp_model_outputs.py --dry-run",
            file=sys.stderr,
        )
        return 1

    if args.match_offset_hours <= 0:
        print(
            f"ERROR: --match-offset-hours must be > 0 (got {args.match_offset_hours}). "
            "prediction_time_utc must be before match_time_utc.",
            file=sys.stderr,
        )
        return 1

    # ── Stage 1: Run started ─────────────────────────────────────────────────
    run_started_at = datetime.now(timezone.utc)

    # ── Stage 2: Feature data loaded ─────────────────────────────────────────
    # In production: load feature store, record exact load time.
    # In dry-run: capture system clock at the moment feature loading would occur.
    feature_loaded_at = datetime.now(timezone.utc)

    # ── Stage 3: Model inference ─────────────────────────────────────────────
    # In production: run model.predict(), record inference start time.
    # In dry-run: capture system clock as the "inference runtime" timestamp.
    prediction_run_id = str(uuid.uuid4())
    prediction_time = datetime.now(timezone.utc)

    rows = _build_rows(
        run_started_at,
        feature_loaded_at,
        prediction_time,
        args.match_offset_hours,
        prediction_run_id,
    )

    # ── Stage 4: Run completed ───────────────────────────────────────────────
    run_completed_at = datetime.now(timezone.utc)
    for row in rows:
        row["prediction_run_completed_at_utc"] = _fmt_utc(run_completed_at)

    # ── Stage 5: Write output ────────────────────────────────────────────────
    output_written_at = datetime.now(timezone.utc)
    for row in rows:
        row["model_output_written_at_utc"] = _fmt_utc(output_written_at)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ── Console summary ──────────────────────────────────────────────────────
    print("=" * 70)
    print("Phase 6Q — Native Timestamp Model Output Stub")
    print("=" * 70)
    print(f"  Run started          : {_fmt_utc(run_started_at)}")
    print(f"  Feature loaded at    : {_fmt_utc(feature_loaded_at)}")
    print(f"  Prediction time      : {_fmt_utc(prediction_time)}")
    print(f"  Run completed        : {_fmt_utc(run_completed_at)}")
    print(f"  Output written at    : {_fmt_utc(output_written_at)}")
    print(f"  Prediction run ID    : {prediction_run_id}")
    print(f"  Rows generated       : {len(rows)}")
    print(f"  Output file          : {args.output}")
    print()
    print(f"  prediction_time_source    : {PREDICTION_TIME_SOURCE}")
    print(f"  feature_cutoff_source     : {FEATURE_CUTOFF_SOURCE}")
    print(f"  timestamp_capture_version : {TIMESTAMP_CAPTURE_VERSION}")
    print()
    print("  Timestamp chain invariants (all must hold for M6 to pass):")
    print(f"    started  <= prediction : {_fmt_utc(run_started_at)} <= {_fmt_utc(prediction_time)} → {run_started_at <= prediction_time}")
    print(f"    feature  <= prediction : {_fmt_utc(feature_loaded_at)} <= {_fmt_utc(prediction_time)} → {feature_loaded_at <= prediction_time}")
    match_example = run_started_at + timedelta(hours=args.match_offset_hours)
    print(f"    prediction < match     : {_fmt_utc(prediction_time)} < {_fmt_utc(match_example)} → {prediction_time < match_example}")
    print(f"    completed >= prediction: {_fmt_utc(run_completed_at)} >= {_fmt_utc(prediction_time)} → {run_completed_at >= prediction_time}")
    print(f"    written   >= prediction: {_fmt_utc(output_written_at)} >= {_fmt_utc(prediction_time)} → {output_written_at >= prediction_time}")
    print()
    print("  To validate (Phase 6P extended validator):")
    print(f"    python3 scripts/validate_model_output_contract.py \\")
    print(f"        --candidate {args.output} \\")
    print(f"        --report docs/orchestration/phase6q_validator_run_report_{_fmt_utc(run_started_at)[:10]}.md \\")
    print(f"        --summary data/derived/model_output_contract_validation_summary_6q_{_fmt_utc(run_started_at)[:10]}.json")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
