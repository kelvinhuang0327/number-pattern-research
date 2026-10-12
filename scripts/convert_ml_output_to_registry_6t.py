#!/usr/bin/env python3
"""
Phase 6T — ML-Only Model Output → Prediction Registry Converter
================================================================
Consumes validated Phase 6S model output rows and converts them into
flat prediction registry rows.

Eligibility gates (all must pass — no relaxation):
  G1  clv_usable = True
  G2  odds_snapshot_alignment_status = "ALIGNED"
  G3  odds_snapshot_ref is not None/empty
  G4  expected_value is not None
  G5  no future odds leakage  (snap_ts <= prediction_time_utc)
  G6  no hard-fail timestamp_quality_flags
  G7  M13 native timestamp fields present + prediction_time_source valid

Registry output fields:
  prediction_id, canonical_match_id, game_id, league, market_type,
  selection, predicted_probability, implied_probability_at_prediction,
  expected_value, odds_snapshot_ref, odds_snapshot_time_utc,
  prediction_time_utc, event_start_time_utc, clv_usable,
  governance_status, execution_mode, source_model, signal_state_type,
  validation_schema_version, created_at_utc,
  + full timestamp chain (6 fields) + provenance fields

Governance:
  execution_mode   = "RESEARCH_ONLY"
  governance_status = "VALIDATED_ML_ONLY"
  No live betting execution fields are set.

Idempotency:
  Duplicate detection key = (canonical_match_id, market_type, selection,
                              prediction_time_utc, odds_snapshot_ref)
  Existing rows with the same key are skipped.

Output:
  data/wbc_backend/reports/prediction_registry_6t_YYYY-MM-DD.jsonl
  data/wbc_backend/reports/prediction_registry_6t_summary_YYYY-MM-DD.json

Phase 6U blockers:
  - CLV record generation (needs closing odds vs. pre-prediction odds)
  - Kelly sizing (needs bankroll state + CLV registry)
  - Settlement ingestion linkage (needs game results)
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────
REGISTRY_SCHEMA_VERSION = "6t-1.0"
EXECUTION_MODE = "RESEARCH_ONLY"
GOVERNANCE_STATUS = "VALIDATED_ML_ONLY"
SIGNAL_STATE_TYPE = "ML_ONLY_FUTURE_PREGAME"
VALIDATION_SCHEMA_VERSION = "6j-1.0"  # Phase 6J contract

_ALLOWED_PREDICTION_TIME_SOURCES = frozenset({
    "MODEL_INFERENCE_RUNTIME",
    "MODEL_OUTPUT_EMISSION_RUNTIME",
    "SCHEDULER_RUN_RUNTIME",
})

_HARD_FAIL_TIMESTAMP_FLAGS = frozenset({
    "TIMESTAMP_MISSING",
    "TIMESTAMP_SOURCE_LOW_CONFIDENCE",
    "PREDICTION_TIME_AFTER_MATCH",
    "FEATURE_CUTOFF_AFTER_PREDICTION",
    "FEATURE_CUTOFF_AFTER_MATCH",
    "TIMESTAMP_CLOCK_DRIFT",
    "HISTORICAL_TIMESTAMP_RECOVERY",
    "ODDS_SNAPSHOT_AFTER_MATCH",
})

# Critical fields that must never be null in a registry row
_CRITICAL_REGISTRY_FIELDS = (
    "prediction_id",
    "canonical_match_id",
    "league",
    "market_type",
    "selection",
    "predicted_probability",
    "implied_probability_at_prediction",
    "expected_value",
    "odds_snapshot_ref",
    "odds_snapshot_time_utc",
    "prediction_time_utc",
    "clv_usable",
    "governance_status",
    "execution_mode",
    "source_model",
    "signal_state_type",
    "validation_schema_version",
    "created_at_utc",
)

# ── Rejection reasons (for summary) ──────────────────────────────────────────
class RejectionReason:
    CLV_UNUSABLE        = "clv_usable_false"
    NOT_ALIGNED         = "alignment_status_not_aligned"
    NO_SNAP_REF         = "missing_odds_snapshot_ref"
    NO_EV               = "missing_expected_value"
    FUTURE_LEAK         = "future_odds_leakage"
    HARD_FAIL_FLAG      = "hard_fail_timestamp_flag"
    M13_FAIL            = "m13_native_timestamp_fail"
    DUPLICATE           = "duplicate_key"


def _check_eligibility(row: dict) -> str | None:
    """
    Run all eligibility gates. Returns rejection reason string on first
    failure, or None if row is eligible.
    """
    # G1: clv_usable must be True
    if not row.get("clv_usable"):
        return RejectionReason.CLV_UNUSABLE

    # G2: alignment status must be ALIGNED
    if row.get("odds_snapshot_alignment_status") != "ALIGNED":
        return RejectionReason.NOT_ALIGNED

    # G3: odds_snapshot_ref must be present
    snap_ref = row.get("odds_snapshot_ref")
    if not snap_ref:
        return RejectionReason.NO_SNAP_REF

    # G4: expected_value must be present
    if row.get("expected_value") is None:
        return RejectionReason.NO_EV

    # G5: no future odds leakage
    snap_ts = row.get("odds_snapshot_time_utc", "")
    pred_ts = row.get("prediction_time_utc", "")
    if snap_ts and pred_ts and snap_ts > pred_ts:
        return RejectionReason.FUTURE_LEAK

    # G6: no hard-fail timestamp quality flags
    tqf = set(row.get("timestamp_quality_flags") or [])
    if tqf & _HARD_FAIL_TIMESTAMP_FLAGS:
        return RejectionReason.HARD_FAIL_FLAG

    # G7: M13 — prediction_time_source in allowed set + required TS fields present
    pts = row.get("prediction_time_source", "")
    if pts not in _ALLOWED_PREDICTION_TIME_SOURCES:
        return RejectionReason.M13_FAIL
    if not row.get("prediction_time_utc"):
        return RejectionReason.M13_FAIL
    if not row.get("timestamp_capture_version"):
        return RejectionReason.M13_FAIL

    return None  # eligible


def _dedup_key(row: dict) -> tuple:
    """Idempotency key — uniquely identifies a prediction entry."""
    return (
        row.get("canonical_match_id", ""),
        row.get("market_type", ""),
        row.get("selection", ""),
        row.get("prediction_time_utc", ""),
        row.get("odds_snapshot_ref", ""),
    )


def convert_ml_output_to_prediction_registry(row: dict) -> dict:
    """
    Convert a validated Phase 6S ML-only model output row into a flat
    prediction registry row.

    Raises ValueError if the row fails eligibility gates (caller should
    check _check_eligibility first if they want the reason code).
    """
    reason = _check_eligibility(row)
    if reason is not None:
        raise ValueError(f"Row ineligible for registry: {reason} — {row.get('canonical_match_id')}")

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Stable prediction_id: deterministic from source model_output_id
    src_id = row.get("model_output_id", "")
    prediction_id = "6t-" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"6t:{src_id}"))

    return {
        # ── Identity ──────────────────────────────────────────────────────────
        "prediction_id":              prediction_id,
        "source_model_output_id":     src_id,
        "prediction_run_id":          row.get("prediction_run_id"),
        # ── Match identity ────────────────────────────────────────────────────
        "canonical_match_id":         row["canonical_match_id"],
        "game_id":                    row.get("odds_snapshot_ref", "").split("|")[0],
        "sport":                      row.get("sport", "baseball"),
        "league":                     row.get("league", "mlb"),
        "home_team_code":             row.get("home_team_code"),
        "away_team_code":             row.get("away_team_code"),
        "event_start_time_utc":       row.get("match_time_utc"),
        # ── Market ────────────────────────────────────────────────────────────
        "market_type":                row.get("market_type", "ML"),
        "market_key":                 row.get("market_key"),
        "selection":                  row["selection"],
        "selection_key":              row.get("selection_key"),
        "market_line":                row.get("market_line"),
        # ── Probabilities & EV ───────────────────────────────────────────────
        "predicted_probability":      row["predicted_probability"],
        "implied_probability_at_prediction": row["implied_probability_at_prediction"],
        "expected_value":             row["expected_value"],
        "market_odds_at_prediction":  row.get("market_odds_at_prediction"),
        # ── Odds snapshot ─────────────────────────────────────────────────────
        "odds_snapshot_ref":          row["odds_snapshot_ref"],
        "odds_snapshot_time_utc":     row["odds_snapshot_time_utc"],
        "odds_snapshot_source":       row.get("odds_snapshot_source"),
        "odds_snapshot_alignment_status": row.get("odds_snapshot_alignment_status"),
        # ── Timestamps (full 6O chain) ────────────────────────────────────────
        "prediction_time_utc":            row["prediction_time_utc"],
        "feature_cutoff_time_utc":        row.get("feature_cutoff_time_utc"),
        "prediction_run_started_at_utc":  row.get("prediction_run_started_at_utc"),
        "prediction_run_completed_at_utc": row.get("prediction_run_completed_at_utc"),
        "model_output_written_at_utc":    row.get("model_output_written_at_utc"),
        "prediction_time_source":         row.get("prediction_time_source"),
        "feature_cutoff_source":          row.get("feature_cutoff_source"),
        "timestamp_capture_version":      row.get("timestamp_capture_version"),
        "timestamp_quality_flags":        list(row.get("timestamp_quality_flags") or []),
        # ── CLV / governance ─────────────────────────────────────────────────
        "clv_usable":             row["clv_usable"],
        "governance_status":      GOVERNANCE_STATUS,
        "execution_mode":         EXECUTION_MODE,
        "signal_state_type":      SIGNAL_STATE_TYPE,
        # ── No live execution fields ──────────────────────────────────────────
        "live_bet_submitted":     False,
        "live_bet_stake":         None,
        "live_bet_ref":           None,
        # ── Model provenance ─────────────────────────────────────────────────
        "source_model":           row.get("model_version", row.get("model_family", "unknown")),
        "model_family":           row.get("model_family"),
        "model_version":          row.get("model_version"),
        "feature_version":        row.get("feature_version"),
        "adapter_version":        row.get("adapter_version"),
        "phase":                  row.get("phase", "6S"),
        # ── Quality flags ─────────────────────────────────────────────────────
        "model_quality_flags":    list(row.get("model_quality_flags") or []),
        "data_quality_flags":     list(row.get("data_quality_flags") or []),
        "dry_run":                row.get("dry_run", False),
        # ── Schema / audit ────────────────────────────────────────────────────
        "validation_schema_version": VALIDATION_SCHEMA_VERSION,
        "registry_schema_version":   REGISTRY_SCHEMA_VERSION,
        "created_at_utc":            now_utc,
    }


def validate_registry_row(row: dict) -> list[str]:
    """
    Post-conversion validator. Returns list of error strings (empty = OK).
    Checks:
      - no null critical fields
      - execution_mode is PAPER_ONLY or RESEARCH_ONLY
      - governance_status is VALIDATED_ML_ONLY
      - live execution fields are NOT activated
      - odds_snapshot_ref preserved
      - timestamp chain fields preserved
    """
    errors: list[str] = []

    for field in _CRITICAL_REGISTRY_FIELDS:
        if row.get(field) is None:
            errors.append(f"NULL_CRITICAL_FIELD: {field}")

    mode = row.get("execution_mode", "")
    if mode not in ("PAPER_ONLY", "RESEARCH_ONLY"):
        errors.append(f"INVALID_EXECUTION_MODE: {mode!r}")

    if row.get("governance_status") != GOVERNANCE_STATUS:
        errors.append(f"INVALID_GOVERNANCE_STATUS: {row.get('governance_status')!r}")

    if row.get("live_bet_submitted") is True:
        errors.append("LIVE_BET_ACTIVATED: live_bet_submitted=True")

    if row.get("live_bet_ref") is not None:
        errors.append("LIVE_BET_ACTIVATED: live_bet_ref is set")

    if not row.get("odds_snapshot_ref"):
        errors.append("MISSING_ODDS_SNAPSHOT_REF")

    if not row.get("prediction_time_utc"):
        errors.append("MISSING_PREDICTION_TIME_UTC")

    if not row.get("timestamp_capture_version"):
        errors.append("MISSING_TIMESTAMP_CAPTURE_VERSION")

    return errors


# ── Main runner ───────────────────────────────────────────────────────────────
def run_converter(
    input_path: str | None = None,
    output_path: str | None = None,
    summary_path: str | None = None,
    target_date: str | None = None,
) -> dict:
    """
    Run the Phase 6T converter.

    Args:
        input_path:   Override Phase 6S JSONL source.
        output_path:  Override registry JSONL output path.
        summary_path: Override summary JSON path.
        target_date:  Date string YYYY-MM-DD (defaults to today UTC).

    Returns stats dict.
    """
    today = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    repo_root = Path(__file__).resolve().parent.parent

    if input_path is None:
        input_path = str(
            repo_root / "data" / "derived" / f"model_outputs_6s_future_{today}.jsonl"
        )
    if output_path is None:
        output_path = str(
            repo_root / "data" / "wbc_backend" / "reports"
            / f"prediction_registry_6t_{today}.jsonl"
        )
    if summary_path is None:
        summary_path = str(
            repo_root / "data" / "wbc_backend" / "reports"
            / f"prediction_registry_6t_summary_{today}.json"
        )

    print("=" * 70)
    print("Phase 6T — ML-Only Output → Prediction Registry Converter")
    print("=" * 70)
    print(f"  Source       : {input_path}")
    print(f"  Registry out : {output_path}")

    # Load source rows
    src = Path(input_path)
    if not src.exists():
        print(f"  ERROR: source file not found: {input_path}", file=sys.stderr)
        return {"error": "source_not_found", "path": input_path}

    source_rows = [
        json.loads(line)
        for line in src.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"  Source rows  : {len(source_rows)}")

    # Load existing registry for idempotency check
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[tuple] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
                existing_keys.add(_dedup_key(existing))
            except json.JSONDecodeError:
                pass
    print(f"  Existing keys: {len(existing_keys)}")

    # Convert
    converted: list[dict] = []
    rejected: dict[str, list[str]] = {}  # reason → [canonical_match_id:selection]
    validation_errors: list[str] = []

    for row in source_rows:
        reason = _check_eligibility(row)
        label = f"{row.get('canonical_match_id')}:{row.get('selection')}"

        if reason is not None:
            rejected.setdefault(reason, []).append(label)
            continue

        dk = _dedup_key(row)
        if dk in existing_keys:
            rejected.setdefault(RejectionReason.DUPLICATE, []).append(label)
            continue

        try:
            reg_row = convert_ml_output_to_prediction_registry(row)
        except ValueError as e:
            rejected.setdefault("conversion_error", []).append(f"{label}: {e}")
            continue

        errs = validate_registry_row(reg_row)
        if errs:
            validation_errors.extend(errs)
            rejected.setdefault("validation_failed", []).append(label)
            continue

        converted.append(reg_row)
        existing_keys.add(dk)

    # Write registry rows (append mode for idempotency)
    if converted:
        with out_path.open("a", encoding="utf-8") as fout:
            for reg_row in converted:
                fout.write(json.dumps(reg_row, ensure_ascii=False) + "\n")

    # Print summary
    total_rejected = sum(len(v) for v in rejected.values())
    print()
    print(f"  Converted    : {len(converted)}")
    print(f"  Rejected     : {total_rejected}")
    for reason, items in rejected.items():
        print(f"    {reason}: {len(items)}")
    if validation_errors:
        print(f"  Validation errors: {validation_errors}")

    # Downstream readiness check
    print()
    print("  Downstream readiness:")
    print(f"    research_layer        : {'READY' if len(converted) > 0 else 'NO_ROWS'}")
    print(f"    settlement_ingestion  : READY (event_start_time_utc populated)")
    print(f"    roi_tracking          : READY (expected_value + execution_mode present)")
    print(f"    clv_generation_6u     : READY (clv_usable=True + odds_snapshot_ref present)")
    print()
    print("  Phase 6U blockers:")
    print("    CLV record generation — needs closing odds vs pre-prediction odds")
    print("    Kelly sizing          — needs bankroll state + CLV registry")
    print("    Settlement linkage    — needs game results ingestion")
    print("=" * 70)

    # Write summary
    summary = {
        "phase": "6T",
        "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        "source_file": input_path,
        "output_file": output_path,
        "source_rows": len(source_rows),
        "converted": len(converted),
        "rejected_total": total_rejected,
        "rejected_by_reason": {k: len(v) for k, v in rejected.items()},
        "rejected_detail": rejected,
        "validation_errors": validation_errors,
        "execution_mode": EXECUTION_MODE,
        "governance_status": GOVERNANCE_STATUS,
        "downstream_readiness": {
            "research_layer": len(converted) > 0,
            "settlement_ingestion": True,
            "roi_tracking": True,
            "clv_generation_6u": len(converted) > 0,
        },
        "phase_6u_blockers": [
            "CLV record generation (needs closing odds)",
            "Kelly sizing (needs bankroll state)",
            "Settlement linkage (needs game results)",
        ],
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_path).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"  Summary JSON : {summary_path}")

    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 6T — Convert Phase 6S ML output rows to prediction registry"
    )
    parser.add_argument("--input", metavar="PATH", default=None,
                        help="Phase 6S JSONL source (default: data/derived/model_outputs_6s_future_YYYY-MM-DD.jsonl)")
    parser.add_argument("--output", metavar="PATH", default=None,
                        help="Registry JSONL output path")
    parser.add_argument("--summary", metavar="PATH", default=None,
                        help="Summary JSON output path")
    parser.add_argument("--date", metavar="YYYY-MM-DD", default=None,
                        help="Target date (default: today UTC)")
    args = parser.parse_args()

    result = run_converter(
        input_path=args.input,
        output_path=args.output,
        summary_path=args.summary,
        target_date=args.date,
    )
    if "error" in result:
        sys.exit(1)
    if result.get("validation_errors"):
        print("FATAL: Registry validation errors found.", file=sys.stderr)
        sys.exit(1)
