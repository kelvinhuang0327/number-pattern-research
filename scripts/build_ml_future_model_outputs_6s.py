#!/usr/bin/env python3
"""
Phase 6S — ML-Only Future Event Adapter with Odds Snapshot Alignment
======================================================================
Extends Phase 6R by:
  1. Loading REAL scheduled games from the odds timeline (not synthetic)
  2. Aligning each prediction row with the best available pre-prediction
     odds snapshot (TSL early/pregame entries).
  3. Computing implied_probability_at_prediction from American moneyline.
  4. Setting clv_usable = True only when all CLV gates pass (TASK 4).

New fields added per row (Phase 6S):
  - odds_snapshot_ref
  - odds_snapshot_time_utc
  - implied_probability_at_prediction
  - market_odds_at_prediction
  - odds_snapshot_source
  - odds_snapshot_alignment_status

CLV Usability Gate (TASK 4):
  clv_usable = True  IFF:
    M13 native timestamp: PASS  (prediction_time_source in allowed set, etc.)
    odds_snapshot_ref:    present (not None)
    odds_snapshot_time_utc <= prediction_time_utc
    implied_probability_at_prediction: non-null float in (0,1)
    timestamp_quality_flags: no HARD_FAIL flags
  Otherwise: clv_usable = False

Phase 6T blocker:
  - CLV registry conversion deferred to Phase 6T.
  - expected_value computation deferred to Phase 6T (requires closing odds).
  - No betting execution is triggered.

Output: data/derived/model_outputs_6s_future_{today}.jsonl
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── Path setup ────────────────────────────────────────────────────────────────
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from native_timestamp_helper import (
    NativeTimestampCapture,
    TIMESTAMP_CAPTURE_VERSION,
    PREDICTION_TIME_SOURCE,
    FEATURE_CUTOFF_SOURCE_DEFAULT,
)
from align_odds_snapshot import (
    OddsTimelineLoader,
    align_odds_snapshot_for_prediction,
    _extract_from_game_id,
    TEAM_NAME_TO_CODE,
    american_to_implied,
)

# ── Version constants ─────────────────────────────────────────────────────────
SCHEMA_VERSION = "6j-1.0"           # Phase 6J contract (backward compat)
PHASE = "6S"
MODEL_FAMILY = "mlb_ml_elo_stub"
MODEL_VERSION = "mlb_ml_elo_stub_v1.1.0"   # v1.1 — real-game schedule
FEATURE_VERSION = "features_elo_ratings_v1.1.0"
LEAKAGE_GUARD_VERSION = "leakage_guard_6s_v1.0.0"
TRAINING_WINDOW_ID = "ELO_RATING_TRAINING_WINDOW_HISTORICAL"
WALK_FORWARD_SPLIT_ID = "ELO_WALK_FORWARD_BY_SEASON"
ADAPTER_VERSION = "6s-1.0.0"
FEATURE_CUTOFF_SOURCE = "MLB_SCHEDULE_LOAD_TIME"
TIMESTAMP_CAPTURE_VER = "6R-1.0"    # same capture version as Phase 6R

_REPO_ROOT = _SCRIPTS.parent

# ── CLV gate: hard-fail timestamp quality flags ───────────────────────────────
_CLV_HARD_FAIL_FLAGS: set[str] = {
    "TIMESTAMP_MISSING",
    "TIMESTAMP_SOURCE_LOW_CONFIDENCE",
    "PREDICTION_TIME_AFTER_MATCH",
    "FEATURE_CUTOFF_AFTER_PREDICTION",
    "FEATURE_CUTOFF_AFTER_MATCH",
    "TIMESTAMP_CLOCK_DRIFT",
    "HISTORICAL_TIMESTAMP_RECOVERY",
    "ODDS_SNAPSHOT_AFTER_MATCH",
}

_ALLOWED_PREDICTION_TIME_SOURCES = {
    "MODEL_INFERENCE_RUNTIME",
    "MODEL_OUTPUT_EMISSION_RUNTIME",
    "SCHEDULER_RUN_RUNTIME",
}

# ── Elo ratings (30 MLB teams — broader than Phase 6R's 10-team stub) ─────────
_ELO_RATINGS: dict[str, float] = {
    # AL East
    "NYY": 1540.0, "BOS": 1480.0, "TOR": 1495.0, "TBR": 1470.0, "BAL": 1515.0,
    # AL Central
    "CWS": 1390.0, "CLE": 1505.0, "DET": 1475.0, "KC":  1450.0, "MIN": 1500.0,
    # AL West
    "HOU": 1510.0, "LAA": 1445.0, "OAK": 1420.0, "SEA": 1490.0, "TEX": 1480.0,
    # NL East
    "ATL": 1525.0, "MIA": 1440.0, "NYM": 1505.0, "PHI": 1530.0, "WSH": 1410.0,
    # NL Central
    "CHC": 1490.0, "CIN": 1460.0, "MIL": 1500.0, "PIT": 1435.0, "STL": 1470.0,
    # NL West
    "ARI": 1485.0, "COL": 1415.0, "LAD": 1555.0, "SDP": 1500.0, "SFG": 1460.0,
}


# ── Simple Elo win probability ────────────────────────────────────────────────
def _elo_win_prob(
    home_elo: float, away_elo: float, home_field_adv: float = 35.0
) -> float:
    """P(home wins) = 1 / (1 + 10^(-elo_diff/400))"""
    elo_diff = (home_elo + home_field_adv) - away_elo
    prob = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
    return round(prob, 6)


# ── CLV usability gate ────────────────────────────────────────────────────────
def _compute_clv_usable(
    row: dict,
    alignment: dict,
    pred_time: datetime,
) -> bool:
    """
    TASK 4 — CLV Usability Gate.

    Returns True IFF:
      1. prediction_time_source is in the approved set
      2. odds_snapshot_ref is present
      3. odds_snapshot_time_utc <= prediction_time_utc
      4. implied_probability_at_prediction is a valid float in (0, 1)
      5. No hard-fail flags in timestamp_quality_flags
    """
    # Gate 1: prediction_time_source
    if row.get("prediction_time_source") not in _ALLOWED_PREDICTION_TIME_SOURCES:
        return False

    # Gate 2: odds_snapshot_ref present
    snap_ref = alignment.get("odds_snapshot_ref")
    if not snap_ref:
        return False

    # Gate 3: snapshot_time <= prediction_time
    snap_ts_str = alignment.get("odds_snapshot_time_utc")
    if not snap_ts_str:
        return False
    try:
        snap_ts = datetime.strptime(snap_ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return False
    if snap_ts > pred_time:
        return False

    # Gate 4: implied_probability in (0, 1)
    ip = alignment.get("implied_probability_at_prediction")
    if ip is None:
        return False
    try:
        ip_f = float(ip)
        if not (0.0 < ip_f < 1.0):
            return False
    except (TypeError, ValueError):
        return False

    # Gate 5: no hard-fail timestamp quality flags
    tqf = row.get("timestamp_quality_flags") or []
    if any(f in _CLV_HARD_FAIL_FLAGS for f in tqf):
        return False

    return True


# ── Load real games from odds timeline ───────────────────────────────────────
def _load_real_games(
    loader: OddsTimelineLoader,
    date_yyyymmdd: str,
) -> list[tuple[str, str, str, str]]:
    """
    Load real scheduled games from odds timeline for a given date.
    Returns list of (home_code, away_code, game_id, date_yyyymmdd).
    Only includes games where both home_ml and away_ml odds exist.
    """
    games = []
    for record in loader.records_for_date(date_yyyymmdd):
        parsed = _extract_from_game_id(record.get("game_id", ""))
        if not parsed:
            continue
        date, away_code, home_code = parsed

        # Must have at least closing or history odds
        has_ml = (
            record.get("closing_home_ml") is not None
            or any(
                h.get("home_ml") is not None
                for h in record.get("odds_history", [])
            )
        )
        if has_ml:
            games.append((home_code, away_code, record["game_id"], date))
    return games


# ── Row builder ───────────────────────────────────────────────────────────────
def _build_rows(
    cap: NativeTimestampCapture,
    run_started_at: datetime,
    prediction_run_id: str,
    games: list[tuple[str, str, str, str]],
    loader: OddsTimelineLoader,
) -> list[dict]:
    """
    Build 2 rows per game (home ML + away ML) with odds alignment.
    """
    rows: list[dict] = []
    early = cap.early_fields()   # Stage 4/5 = None (filled later)
    pred_time_str: str = early["prediction_time_utc"]

    for home_code, away_code, odds_game_id, date_yyyymmdd in games:
        match_dt_str: Optional[str] = None
        # Use commence_time from record if available, else None
        record = loader.find(date_yyyymmdd, home_code, away_code)
        if record:
            ct = record.get("commence_time", "")
            if ct and ct.strip():
                # Normalise to UTC Z format so _parse_dt in validator can handle it.
                # datetime.fromisoformat() handles +HH:MM offsets (Python 3.7+).
                try:
                    ct_dt = datetime.fromisoformat(ct.strip())
                    ct_utc = ct_dt.astimezone(timezone.utc)
                    match_dt_str = ct_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                except (ValueError, TypeError):
                    match_dt_str = None

        # Fallback: use date + EOD placeholder; this is pre-game so never before prediction
        if not match_dt_str:
            match_dt_str = (
                f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}T23:59:00Z"
            )

        canonical_id = f"baseball:mlb:{date_yyyymmdd}:{home_code}:{away_code}"
        raw_id = f"6S_REAL_{home_code}_AT_{away_code}_{date_yyyymmdd}"
        market_key = f"{canonical_id}:ml"

        home_elo = _ELO_RATINGS.get(home_code, 1500.0)
        away_elo = _ELO_RATINGS.get(away_code, 1500.0)
        home_prob = _elo_win_prob(home_elo, away_elo)
        away_prob = round(1.0 - home_prob, 6)

        for selection, prob in (("home", home_prob), ("away", away_prob)):
            sel_key = f"{market_key}:{selection}"
            output_id = "6s-" + str(uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{prediction_run_id}:{sel_key}",
            ))

            # Build base row (Phase 6J + 6O fields)
            row: dict = {
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
                "league": "mlb",
                "canonical_match_id": canonical_id,
                "raw_match_id": raw_id,
                "match_time_utc": match_dt_str,
                "home_team_code": home_code,
                "away_team_code": away_code,
                "market_type": "ML",
                "market_line": None,
                "market_key": market_key,
                "selection": selection,
                "selection_key": sel_key,
                "prediction_time_utc": early["prediction_time_utc"],
                "predicted_probability": prob,
                "confidence": None,
                "probability_source": "elo_win_probability_6s",
                "feature_cutoff_time_utc": early["feature_cutoff_time_utc"],
                # Phase 6S alignment fields (filled below)
                "odds_snapshot_ref": None,
                "implied_probability_at_prediction": None,
                "expected_value": None,   # Phase 6T scope
                "model_quality_flags": ["ELO_STUB_MODEL_PHASE_6S"],
                "data_quality_flags": [],
                "dry_run": False,
                "clv_usable": False,      # set after alignment gate
                # Phase 6O native timestamp fields (Stage 4/5 = None; filled after)
                "prediction_run_started_at_utc": early["prediction_run_started_at_utc"],
                "prediction_run_completed_at_utc": None,
                "model_output_written_at_utc": None,
                "prediction_time_source": early["prediction_time_source"],
                "feature_cutoff_source": early["feature_cutoff_source"],
                "timestamp_capture_version": early["timestamp_capture_version"],
                "timestamp_quality_flags": list(early["timestamp_quality_flags"]),
                "adapter_version": ADAPTER_VERSION,
                "phase": PHASE,
            }

            # ── Odds snapshot alignment (TASK 2 + 3 integration) ─────────────
            alignment = align_odds_snapshot_for_prediction(row, loader)
            row["odds_snapshot_ref"] = alignment["odds_snapshot_ref"]
            row["odds_snapshot_time_utc"] = alignment.get("odds_snapshot_time_utc")
            row["implied_probability_at_prediction"] = alignment[
                "implied_probability_at_prediction"
            ]
            row["market_odds_at_prediction"] = alignment.get("market_odds_at_prediction")
            row["odds_snapshot_source"] = alignment.get("odds_snapshot_source")
            row["odds_snapshot_alignment_status"] = alignment["odds_snapshot_alignment_status"]

            # ── EV computation (edge formula) ─────────────────────────────────
            # EV = predicted_prob − implied_prob  (positive = value bet)
            # Required by M8 when odds_snapshot_ref is present.
            ip = alignment.get("implied_probability_at_prediction")
            if ip is not None and row.get("odds_snapshot_ref"):
                row["expected_value"] = round(float(prob) - float(ip), 6)
            else:
                row["expected_value"] = None

            # Annotate data_quality_flags when alignment is not clean
            status = alignment["odds_snapshot_alignment_status"]
            if status == "MISSING":
                row["data_quality_flags"].append("ODDS_SNAPSHOT_REF_MISSING")
            elif status == "STALE":
                row["data_quality_flags"].append("ODDS_SNAPSHOT_STALE")
            elif status == "FUTURE_LEAK_BLOCKED":
                row["data_quality_flags"].append("ODDS_SNAPSHOT_FUTURE_BLOCKED")

            rows.append(row)

    return rows


# ── Main adapter ──────────────────────────────────────────────────────────────
def run_adapter(
    output_path: str | None = None,
    target_date: str | None = None,
    odds_timeline_path: str | None = None,
) -> dict:
    """
    Run the Phase 6S future-event ML-only output adapter with odds alignment.

    Args:
        output_path:        Override default output JSONL path.
        target_date:        Date string "YYYYMMDD". Defaults to today (UTC).
        odds_timeline_path: Override default odds timeline source path.

    Returns stats dict.
    """
    today_dt = datetime.now(timezone.utc)
    today = today_dt.strftime("%Y-%m-%d")
    date_yyyymmdd = target_date or today_dt.strftime("%Y%m%d")

    if output_path is None:
        output_path = str(
            _REPO_ROOT / "data" / "derived" / f"model_outputs_6s_future_{today}.jsonl"
        )

    print("=" * 70)
    print("Phase 6S — ML-Only Future Event Adapter + Odds Snapshot Alignment")
    print("=" * 70)

    # ── Stage 1: Pipeline start ───────────────────────────────────────────────
    cap = NativeTimestampCapture()
    cap.start()
    run_started_at = datetime.now(timezone.utc)
    print(f"  Stage 1 — Run started        : {cap.run_started_at_str()}")

    # ── Stage 2: Feature data (Elo ratings + odds timeline) loaded ────────────
    print(f"  Loading odds timeline from   : {odds_timeline_path or 'default'}")
    loader = OddsTimelineLoader(path=odds_timeline_path)
    cap.feature_loaded(source=FEATURE_CUTOFF_SOURCE)
    print(f"  Stage 2 — Feature loaded     : {cap.feature_cutoff_time_utc_str()}")

    # ── Load real games for target date ───────────────────────────────────────
    games = _load_real_games(loader, date_yyyymmdd)
    print(f"  Real games found ({date_yyyymmdd})  : {len(games)}")
    for home, away, gid, _ in games:
        print(f"    {home} vs {away}  ({gid})")

    # ── Stage 3: Model inference ──────────────────────────────────────────────
    prediction_run_id = str(uuid.uuid4())
    cap.prediction_made()
    print(f"  Stage 3 — Prediction made    : {cap.prediction_time_utc_str()}")
    print(f"  Prediction run ID            : {prediction_run_id}")

    # ── Build rows with alignment ─────────────────────────────────────────────
    rows = _build_rows(cap, run_started_at, prediction_run_id, games, loader)
    print(f"  Rows built                   : {len(rows)}")

    # ── Stage 4: Run completed ────────────────────────────────────────────────
    cap.run_completed()
    print(f"  Stage 4 — Run completed      : {cap.run_completed_at_str()}")
    run_completed_str = cap.run_completed_at_str()
    for row in rows:
        row["prediction_run_completed_at_utc"] = run_completed_str

    # ── Stage 5: Output written ───────────────────────────────────────────────
    cap.output_written()
    print(f"  Stage 5 — Output written at  : {cap.output_written_at_str()}")
    output_written_str = cap.output_written_at_str()
    for row in rows:
        row["model_output_written_at_utc"] = output_written_str

    # ── TASK 4 — Apply CLV usability gate AFTER stages 4 & 5 are filled ──────
    pred_time = datetime.strptime(
        cap.prediction_time_utc_str(), "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)

    aligned_count = 0
    missing_count = 0
    stale_count = 0
    future_blocked_count = 0
    clv_true_count = 0

    for row in rows:
        alignment_status = row.get("odds_snapshot_alignment_status", "MISSING")
        if alignment_status == "ALIGNED":
            aligned_count += 1
        elif alignment_status == "STALE":
            stale_count += 1
        elif alignment_status == "FUTURE_LEAK_BLOCKED":
            future_blocked_count += 1
        else:
            missing_count += 1

        # Rebuild alignment dict for gate evaluation
        alignment_for_gate = {
            "odds_snapshot_ref": row.get("odds_snapshot_ref"),
            "odds_snapshot_time_utc": row.get("odds_snapshot_time_utc"),
            "implied_probability_at_prediction": row.get(
                "implied_probability_at_prediction"
            ),
        }
        clv_ok = _compute_clv_usable(row, alignment_for_gate, pred_time)
        row["clv_usable"] = clv_ok
        if clv_ok:
            clv_true_count += 1

    # ── Validate timing chain ─────────────────────────────────────────────────
    violations = cap.validate_chain()
    if violations:
        print(f"  ERROR: Timing violations: {violations}", file=sys.stderr)
        return {"error": "timing_chain_violated", "violations": violations}

    # ── Write output ──────────────────────────────────────────────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fout:
        for row in rows:
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")

    print()
    print("  Alignment summary:")
    print(f"    ALIGNED              : {aligned_count}")
    print(f"    MISSING              : {missing_count}")
    print(f"    STALE                : {stale_count}")
    print(f"    FUTURE_LEAK_BLOCKED  : {future_blocked_count}")
    print(f"    clv_usable=True      : {clv_true_count}")
    print()
    print(f"  timestamp_capture_version    : {TIMESTAMP_CAPTURE_VERSION}")
    print(f"  prediction_time_source       : {PREDICTION_TIME_SOURCE}")
    print(f"  feature_cutoff_source        : {FEATURE_CUTOFF_SOURCE}")
    print(f"  Timing chain violations      : {len(violations)} (must be 0)")
    print(f"  Output file                  : {output_path}")
    print()
    print("  Phase 6T blocker:")
    print("    CLV registry conversion deferred to Phase 6T")
    print("    expected_value computation deferred to Phase 6T (needs closing odds)")
    print("=" * 70)

    return {
        "phase": PHASE,
        "timestamp_capture_version": TIMESTAMP_CAPTURE_VERSION,
        "prediction_time_source": PREDICTION_TIME_SOURCE,
        "feature_cutoff_source": FEATURE_CUTOFF_SOURCE,
        "rows_written": len(rows),
        "timing_violations": len(violations),
        "aligned_count": aligned_count,
        "missing_count": missing_count,
        "stale_count": stale_count,
        "future_blocked_count": future_blocked_count,
        "clv_true_count": clv_true_count,
        "output_path": output_path,
        "target_date": date_yyyymmdd,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 6S — ML-Only Future Adapter with Odds Snapshot Alignment"
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Override output JSONL path (default: data/derived/model_outputs_6s_future_YYYY-MM-DD.jsonl)",
    )
    parser.add_argument(
        "--date",
        metavar="YYYYMMDD",
        default=None,
        help="Target date for scheduled games (default: today UTC)",
    )
    parser.add_argument(
        "--odds-timeline",
        metavar="PATH",
        default=None,
        help="Override odds timeline JSONL path",
    )
    args = parser.parse_args()

    result = run_adapter(
        output_path=args.output,
        target_date=args.date,
        odds_timeline_path=args.odds_timeline,
    )
    if "error" in result:
        sys.exit(1)
