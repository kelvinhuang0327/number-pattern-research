#!/usr/bin/env python3
"""
Phase 6U — CLV Validation Record Generator
===========================================
Generates CLV validation records ONLY after all registry and data-quality
gates pass. Consumes exclusively from Phase 6T prediction registry rows.

This is the final stage of Phase 6.

Eligibility gates (all must pass):
  G1  clv_usable = True                        (from Phase 6S/6T)
  G2  odds_snapshot_ref present                 (required for audit)
  G3  odds_snapshot_time_utc <= prediction_time_utc  (no future leak)
  G4  expected_value present                    (EV computed in 6S)
  G5  execution_mode in ALLOWED_EXECUTION_MODES
  G6  live_bet_submitted = False                (no live exposure)
  G7  governance_status = "VALIDATED_ML_ONLY"   (Phase 6T gated)
  G8  no hard-fail timestamp_quality_flags
  G9  closing odds available OR mark PENDING_CLOSING

CLV status logic:
  COMPUTED        — closing odds found AND are strictly after prediction_time_utc
  PENDING_CLOSING — no valid closing odds yet (pre-game or game in future)
  BLOCKED         — a G1–G8 gate failed (no CLV record generated, logged)

CLV formula (when COMPUTED):
  clv_value = closing_implied_probability - implied_probability_at_prediction
  (positive = beat the closing line)

Closing odds priority:
  1) external_closing_home/away_ml  (OddsAPI / Pinnacle, T-0 to T-30 min)
  2) closing_home/away_ml           (TSL fallback)
  Closing ts must be STRICTLY AFTER prediction_time_utc to be valid.

Selection-aware lookup:
  selection = "home" → home ML fields
  selection = "away" → away ML fields

Idempotency:
  Dedup key = (prediction_id, odds_snapshot_ref, selection)
  Existing rows with same key are skipped.

Output:
  data/wbc_backend/reports/clv_validation_records_6u_YYYY-MM-DD.jsonl
  data/wbc_backend/reports/clv_validation_records_6u_summary_YYYY-MM-DD.json

Hard rules:
  - Do NOT generate CLV from raw model outputs (only from 6T registry)
  - Do NOT bypass Phase 6T registry
  - Do NOT use future odds or fake closing odds
  - Do NOT mark PENDING_CLOSING as COMPUTED
  - Do NOT touch live betting execution
  - Do NOT overwrite production reports
  - Do NOT modify historical rows
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────
CLV_SCHEMA_VERSION = "6u-1.0"
SOURCE_PHASE = "6U"

_ALLOWED_EXECUTION_MODES = frozenset({
    "RESEARCH_ONLY",
    "PAPER_ONLY",
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

_REQUIRED_GOVERNANCE_STATUS = "VALIDATED_ML_ONLY"

# Critical fields that must be present in every COMPUTED/PENDING CLV record
_REQUIRED_CLV_FIELDS = (
    "clv_record_id",
    "prediction_id",
    "canonical_match_id",
    "market_type",
    "selection",
    "predicted_probability",
    "implied_probability_at_prediction",
    "market_odds_at_prediction",
    "expected_value",
    "odds_snapshot_ref",
    "odds_snapshot_time_utc",
    "prediction_time_utc",
    "clv_status",
    "source_registry_file",
    "created_at_utc",
    "clv_schema_version",
)


# ── CLV status codes ──────────────────────────────────────────────────────────
class CLVStatus:
    COMPUTED        = "COMPUTED"
    PENDING_CLOSING = "PENDING_CLOSING"
    BLOCKED         = "BLOCKED"


# ── Rejection reasons (for summary) ──────────────────────────────────────────
class RejectionReason:
    CLV_UNUSABLE        = "clv_usable_false"
    NO_SNAP_REF         = "missing_odds_snapshot_ref"
    FUTURE_SNAP_LEAK    = "odds_snapshot_after_prediction_time"
    NO_EV               = "missing_expected_value"
    BAD_EXECUTION_MODE  = "execution_mode_not_allowed"
    LIVE_BET_SUBMITTED  = "live_bet_submitted_true"
    WRONG_GOVERNANCE    = "governance_status_not_validated_ml_only"
    HARD_FAIL_FLAG      = "hard_fail_timestamp_flag"
    DUPLICATE           = "duplicate_key"


# ── American odds → implied probability ──────────────────────────────────────
def _american_to_implied(ml: int | float | None) -> float | None:
    """Convert American moneyline to implied probability, rounded to 6dp."""
    if ml is None:
        return None
    ml = float(ml)
    if ml >= 100:
        return round(100.0 / (ml + 100.0), 6)
    if ml <= -100:
        return round(abs(ml) / (abs(ml) + 100.0), 6)
    return None


# ── Timestamp parsing ─────────────────────────────────────────────────────────
def _parse_ts(ts: str | None) -> datetime | None:
    """Parse ISO-8601 UTC timestamp string to aware datetime."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# ── JSONL loading ─────────────────────────────────────────────────────────────
def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ── Odds timeline index ───────────────────────────────────────────────────────
def _load_odds_timeline_index(timeline_path: Path) -> dict[str, dict]:
    """
    Load odds timeline into a dict indexed by game_id.
    If multiple rows exist for the same game_id, prefer the one with
    external_closing_home_ml, then the one with closing_home_ml.
    """
    rows = _load_jsonl(timeline_path)
    index: dict[str, dict] = {}
    for row in rows:
        gid = row.get("game_id")
        if not gid:
            continue
        existing = index.get(gid)
        if existing is None:
            index[gid] = row
        else:
            # Prefer external closing > TSL closing > whatever
            if row.get("external_closing_home_ml") is not None:
                index[gid] = row
            elif (existing.get("external_closing_home_ml") is None
                  and row.get("closing_home_ml") is not None):
                index[gid] = row
    return index


# ── Closing odds lookup ───────────────────────────────────────────────────────
def _find_closing_odds(
    reg_row: dict,
    timeline_index: dict[str, dict],
) -> tuple[int | float | None, str | None, str | None]:
    """
    Look up valid closing odds for a registry row.

    Returns (closing_ml, closing_ts_str, source) where:
      - closing_ml  is the moneyline for the correct side (home/away)
      - closing_ts  is the timestamp string of the closing odds
      - source      is one of "external", "tsl", or None

    Returns (None, None, None) when no valid closing odds are available.

    Validity requirement: closing_ts must be STRICTLY AFTER prediction_time_utc.
    This prevents the pre-game snapshot (same as the odds_snapshot) from being
    used as a "closing line".
    """
    game_id = reg_row.get("game_id")
    selection = reg_row.get("selection", "").lower()
    prediction_time_str = reg_row.get("prediction_time_utc")

    if not game_id or not prediction_time_str:
        return None, None, None

    prediction_dt = _parse_ts(prediction_time_str)
    if prediction_dt is None:
        return None, None, None

    timeline_row = timeline_index.get(game_id)
    if timeline_row is None:
        return None, None, None

    # Priority 1: external closing (OddsAPI / Pinnacle)
    ext_home_ml = timeline_row.get("external_closing_home_ml")
    ext_away_ml = timeline_row.get("external_closing_away_ml")
    ext_ts_str = timeline_row.get("external_closing_ts")
    ext_dt = _parse_ts(ext_ts_str)

    if ext_dt is not None and ext_dt > prediction_dt:
        if selection == "home" and ext_home_ml is not None:
            return ext_home_ml, ext_ts_str, "external"
        if selection == "away" and ext_away_ml is not None:
            return ext_away_ml, ext_ts_str, "external"

    # Priority 2: TSL closing
    tsl_home_ml = timeline_row.get("closing_home_ml")
    tsl_away_ml = timeline_row.get("closing_away_ml")
    tsl_ts_str = timeline_row.get("closing_ts")
    tsl_dt = _parse_ts(tsl_ts_str)

    if tsl_dt is not None and tsl_dt > prediction_dt:
        if selection == "home" and tsl_home_ml is not None:
            return tsl_home_ml, tsl_ts_str, "tsl"
        if selection == "away" and tsl_away_ml is not None:
            return tsl_away_ml, tsl_ts_str, "tsl"

    return None, None, None


# ── Eligibility gates G1–G8 ───────────────────────────────────────────────────
def _check_eligibility(row: dict) -> str | None:
    """
    Run gates G1–G8. Returns rejection reason on first failure, None if eligible.
    """
    # G1: clv_usable must be True
    if not row.get("clv_usable"):
        return RejectionReason.CLV_UNUSABLE

    # G2: odds_snapshot_ref must be present
    snap_ref = row.get("odds_snapshot_ref")
    if not snap_ref:
        return RejectionReason.NO_SNAP_REF

    # G3: odds_snapshot_time_utc must not be after prediction_time_utc
    snap_ts = _parse_ts(row.get("odds_snapshot_time_utc"))
    pred_ts = _parse_ts(row.get("prediction_time_utc"))
    if snap_ts is not None and pred_ts is not None:
        if snap_ts > pred_ts:
            return RejectionReason.FUTURE_SNAP_LEAK

    # G4: expected_value must be present
    if row.get("expected_value") is None:
        return RejectionReason.NO_EV

    # G5: execution_mode must be allowed
    exec_mode = row.get("execution_mode", "")
    if exec_mode not in _ALLOWED_EXECUTION_MODES:
        return RejectionReason.BAD_EXECUTION_MODE

    # G6: live_bet_submitted must be False (never allow live exposure)
    if row.get("live_bet_submitted") is not False:
        return RejectionReason.LIVE_BET_SUBMITTED

    # G7: governance_status must be VALIDATED_ML_ONLY
    if row.get("governance_status") != _REQUIRED_GOVERNANCE_STATUS:
        return RejectionReason.WRONG_GOVERNANCE

    # G8: no hard-fail timestamp_quality_flags
    flags = row.get("timestamp_quality_flags") or []
    if isinstance(flags, str):
        flags = [f.strip() for f in flags.split(",") if f.strip()]
    hard_fails = _HARD_FAIL_TIMESTAMP_FLAGS & set(flags)
    if hard_fails:
        return f"{RejectionReason.HARD_FAIL_FLAG}:{','.join(sorted(hard_fails))}"

    return None


# ── Idempotency key ───────────────────────────────────────────────────────────
def _dedup_key(row: dict) -> tuple[str, str, str]:
    """3-tuple dedup key for CLV records."""
    return (
        str(row.get("prediction_id", "")),
        str(row.get("odds_snapshot_ref", "")),
        str(row.get("selection", "")),
    )


# ── Build one CLV record ──────────────────────────────────────────────────────
def _build_clv_record(
    reg_row: dict,
    closing_ml: int | float | None,
    closing_ts: str | None,
    closing_source: str | None,
    source_registry_file: str,
    now_utc: str,
) -> dict:
    """
    Construct a CLV validation record from a registry row plus closing odds.
    Status is set by the caller based on closing_ml availability.
    """
    pred_id = reg_row.get("prediction_id", "")
    selection = reg_row.get("selection", "")
    implied_at_prediction = reg_row.get("implied_probability_at_prediction")

    # CLV computation
    if closing_ml is not None and implied_at_prediction is not None:
        closing_prob = _american_to_implied(closing_ml)
        clv_value = (
            round(closing_prob - implied_at_prediction, 6)
            if closing_prob is not None
            else None
        )
        clv_status = CLVStatus.COMPUTED
        block_reason = None
    else:
        closing_prob = None
        clv_value = None
        clv_status = CLVStatus.PENDING_CLOSING
        block_reason = None

    # Deterministic record ID: uuid5 over (prediction_id, snap_ref, selection)
    snap_ref = reg_row.get("odds_snapshot_ref", "")
    clv_record_id = "6u-" + str(
        uuid.uuid5(uuid.NAMESPACE_DNS, f"6u:{pred_id}:{snap_ref}:{selection}")
    )

    return {
        "clv_record_id": clv_record_id,
        "prediction_id": pred_id,
        "canonical_match_id": reg_row.get("canonical_match_id"),
        "game_id": reg_row.get("game_id"),
        "league": reg_row.get("league"),
        "market_type": reg_row.get("market_type"),
        "selection": selection,
        # Prediction-time context
        "predicted_probability": reg_row.get("predicted_probability"),
        "implied_probability_at_prediction": implied_at_prediction,
        "market_odds_at_prediction": reg_row.get("market_odds_at_prediction"),
        "expected_value": reg_row.get("expected_value"),
        "odds_snapshot_ref": snap_ref,
        "odds_snapshot_time_utc": reg_row.get("odds_snapshot_time_utc"),
        "prediction_time_utc": reg_row.get("prediction_time_utc"),
        "event_start_time_utc": reg_row.get("event_start_time_utc"),
        # Closing odds
        "closing_odds": closing_ml,
        "closing_implied_probability": closing_prob,
        "closing_odds_time_utc": closing_ts,
        "closing_odds_source": closing_source,
        # CLV result
        "clv_value": clv_value,
        "clv_status": clv_status,
        "block_reason": block_reason,
        # Governance + provenance
        "execution_mode": reg_row.get("execution_mode"),
        "governance_status": reg_row.get("governance_status"),
        "source_model": reg_row.get("source_model"),
        "signal_state_type": reg_row.get("signal_state_type"),
        "source_registry_file": source_registry_file,
        "clv_schema_version": CLV_SCHEMA_VERSION,
        "source_phase": SOURCE_PHASE,
        "created_at_utc": now_utc,
        # Timestamp chain passthrough
        "prediction_time_source": reg_row.get("prediction_time_source"),
        "timestamp_capture_version": reg_row.get("timestamp_capture_version"),
        "timestamp_quality_flags": reg_row.get("timestamp_quality_flags"),
    }


# ── Inline validator ──────────────────────────────────────────────────────────
def validate_clv_record(record: dict) -> list[str]:
    """
    Validate a CLV record for internal consistency.
    Returns list of error strings (empty = OK).
    """
    errors: list[str] = []

    # Required fields must be present
    for field in _REQUIRED_CLV_FIELDS:
        if record.get(field) is None:
            errors.append(f"missing_required_field:{field}")

    status = record.get("clv_status")
    if status not in (CLVStatus.COMPUTED, CLVStatus.PENDING_CLOSING, CLVStatus.BLOCKED):
        errors.append(f"invalid_clv_status:{status}")

    # COMPUTED records must have all closing fields
    if status == CLVStatus.COMPUTED:
        for f in ("closing_odds", "closing_implied_probability", "closing_odds_time_utc",
                  "closing_odds_source", "clv_value"):
            if record.get(f) is None:
                errors.append(f"computed_missing:{f}")

    # PENDING records must NOT have clv_value
    if status == CLVStatus.PENDING_CLOSING and record.get("clv_value") is not None:
        errors.append("pending_has_clv_value")

    # BLOCKED records must have block_reason
    if status == CLVStatus.BLOCKED and not record.get("block_reason"):
        errors.append("blocked_missing_block_reason")

    # No future closing odds leakage
    pred_ts = _parse_ts(record.get("prediction_time_utc"))
    closing_ts = _parse_ts(record.get("closing_odds_time_utc"))
    if pred_ts is not None and closing_ts is not None:
        if closing_ts <= pred_ts:
            errors.append("closing_odds_not_after_prediction_time")

    # EV must be present
    if record.get("expected_value") is None:
        errors.append("missing_expected_value")

    # live_bet_submitted must never appear in CLV records
    if "live_bet_submitted" in record:
        errors.append("unexpected_live_bet_field")

    return errors


# ── Main generator ────────────────────────────────────────────────────────────
def generate_clv_records_from_registry(
    registry_rows: list[dict],
    timeline_index: dict[str, dict],
    source_registry_file: str = "",
    existing_keys: set[tuple[str, str, str]] | None = None,
) -> tuple[list[dict], dict]:
    """
    Generate CLV validation records from Phase 6T registry rows.

    Args:
        registry_rows:       Rows from prediction_registry_6t_YYYY-MM-DD.jsonl
        timeline_index:      Indexed odds timeline (game_id → timeline row)
        source_registry_file: Path string for provenance tracking
        existing_keys:       Already-seen dedup keys (for idempotency across runs)

    Returns:
        (clv_records, stats_dict)
    """
    if existing_keys is None:
        existing_keys = set()

    now_utc = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    clv_records: list[dict] = []

    stats: dict[str, Any] = {
        "total_registry_rows": len(registry_rows),
        "eligible": 0,
        "blocked": 0,
        "skipped_duplicate": 0,
        "computed": 0,
        "pending_closing": 0,
        "validation_errors": 0,
        "rejection_reasons": {},
        "validation_error_details": [],
    }

    for reg_row in registry_rows:
        # Gate G1–G8
        rejection = _check_eligibility(reg_row)
        if rejection:
            stats["blocked"] += 1
            stats["rejection_reasons"][rejection] = (
                stats["rejection_reasons"].get(rejection, 0) + 1
            )
            continue

        stats["eligible"] += 1

        # Idempotency
        key = _dedup_key(reg_row)
        if key in existing_keys:
            stats["skipped_duplicate"] += 1
            continue
        existing_keys.add(key)

        # G9: Find closing odds (PENDING_CLOSING if not available)
        closing_ml, closing_ts, closing_source = _find_closing_odds(
            reg_row, timeline_index
        )

        # Build record
        record = _build_clv_record(
            reg_row=reg_row,
            closing_ml=closing_ml,
            closing_ts=closing_ts,
            closing_source=closing_source,
            source_registry_file=source_registry_file,
            now_utc=now_utc,
        )

        # Track status
        if record["clv_status"] == CLVStatus.COMPUTED:
            stats["computed"] += 1
        else:
            stats["pending_closing"] += 1

        # Inline validation
        errors = validate_clv_record(record)
        if errors:
            stats["validation_errors"] += 1
            stats["validation_error_details"].append(
                {"prediction_id": reg_row.get("prediction_id"), "errors": errors}
            )

        clv_records.append(record)

    return clv_records, stats


# ── Runner ────────────────────────────────────────────────────────────────────
def run_generator(
    input_path: Path,
    output_path: Path,
    summary_path: Path,
    timeline_path: Path,
    target_date: str,
) -> dict:
    """
    End-to-end Phase 6U generator run.

    Args:
        input_path:    Phase 6T registry JSONL (e.g. prediction_registry_6t_2026-04-30.jsonl)
        output_path:   CLV records output JSONL
        summary_path:  Summary JSON
        timeline_path: Odds timeline JSONL
        target_date:   YYYY-MM-DD for logging

    Returns:
        Stats dict
    """
    print(f"[Phase 6U] Loading 6T registry: {input_path}")
    registry_rows = _load_jsonl(input_path)
    print(f"[Phase 6U] Loaded {len(registry_rows)} registry rows")

    print(f"[Phase 6U] Loading odds timeline: {timeline_path}")
    timeline_index = _load_odds_timeline_index(timeline_path)
    print(f"[Phase 6U] Timeline index: {len(timeline_index)} game entries")

    # Load existing CLV records for idempotency
    existing_keys: set[tuple[str, str, str]] = set()
    if output_path.exists():
        existing = _load_jsonl(output_path)
        for rec in existing:
            k = (
                str(rec.get("prediction_id", "")),
                str(rec.get("odds_snapshot_ref", "")),
                str(rec.get("selection", "")),
            )
            existing_keys.add(k)
        print(f"[Phase 6U] Loaded {len(existing_keys)} existing CLV record keys")

    clv_records, stats = generate_clv_records_from_registry(
        registry_rows=registry_rows,
        timeline_index=timeline_index,
        source_registry_file=str(input_path),
        existing_keys=existing_keys,
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as fh:
        for rec in clv_records:
            fh.write(json.dumps(rec, default=str) + "\n")

    # Write summary
    summary = {
        "target_date": target_date,
        "source_registry": str(input_path),
        "output_path": str(output_path),
        "timeline_path": str(timeline_path),
        "clv_schema_version": CLV_SCHEMA_VERSION,
        "source_phase": SOURCE_PHASE,
        "stats": stats,
        "generated_at_utc": datetime.now(tz=timezone.utc)
            .isoformat().replace("+00:00", "Z"),
    }
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    # Print report
    print(f"\n[Phase 6U] Results for {target_date}:")
    print(f"  Total registry rows    : {stats['total_registry_rows']}")
    print(f"  Eligible (G1–G8 pass)  : {stats['eligible']}")
    print(f"  Blocked (gate fail)    : {stats['blocked']}")
    print(f"  Skipped (duplicate)    : {stats['skipped_duplicate']}")
    print(f"  CLV records written    : {len(clv_records)}")
    print(f"    → COMPUTED           : {stats['computed']}")
    print(f"    → PENDING_CLOSING    : {stats['pending_closing']}")
    print(f"  Validation errors      : {stats['validation_errors']}")
    if stats["rejection_reasons"]:
        print(f"  Rejection reasons:")
        for reason, count in stats["rejection_reasons"].items():
            print(f"    {reason}: {count}")
    if stats["validation_errors"]:
        print(f"  Validation error details:")
        for detail in stats["validation_error_details"]:
            print(f"    {detail}")

    print(f"\n[Phase 6U] Output: {output_path}")
    print(f"[Phase 6U] Summary: {summary_path}")

    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 6U — Generate CLV validation records from 6T registry"
    )
    parser.add_argument(
        "--date",
        default="2026-04-30",
        help="Target date (YYYY-MM-DD) for registry input file",
    )
    parser.add_argument(
        "--input",
        help="Override input registry path",
    )
    parser.add_argument(
        "--output",
        help="Override output CLV records path",
    )
    parser.add_argument(
        "--summary",
        help="Override output summary path",
    )
    parser.add_argument(
        "--timeline",
        default="data/mlb_context/odds_timeline.jsonl",
        help="Odds timeline JSONL path",
    )
    args = parser.parse_args()

    target_date = args.date
    base = Path("data/wbc_backend/reports")

    input_path = Path(args.input) if args.input else (
        base / f"prediction_registry_6t_{target_date}.jsonl"
    )
    output_path = Path(args.output) if args.output else (
        base / f"clv_validation_records_6u_{target_date}.jsonl"
    )
    summary_path = Path(args.summary) if args.summary else (
        base / f"clv_validation_records_6u_summary_{target_date}.json"
    )
    timeline_path = Path(args.timeline)

    if not input_path.exists():
        print(f"[Phase 6U] ERROR: input registry not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if not timeline_path.exists():
        print(f"[Phase 6U] ERROR: odds timeline not found: {timeline_path}", file=sys.stderr)
        sys.exit(1)

    stats = run_generator(
        input_path=input_path,
        output_path=output_path,
        summary_path=summary_path,
        timeline_path=timeline_path,
        target_date=target_date,
    )

    if stats.get("validation_errors", 0) > 0:
        print("[Phase 6U] WARNING: validation errors found — review output.", file=sys.stderr)
        sys.exit(2)

    print("[Phase 6U] Complete.")


if __name__ == "__main__":
    main()
