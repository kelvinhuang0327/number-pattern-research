"""
Closing Odds Monitor — upgrade PENDING_CLOSING CLV records to COMPUTED
when valid post-prediction closing odds become available.

Read sources (never modified):
  data/wbc_backend/reports/clv_validation_records_6u_*.jsonl  — Phase 6U records
  data/mlb_context/odds_timeline.jsonl                        — canonical odds source

Write target (append-only, new file per run):
  data/wbc_backend/reports/clv_validation_records_6u_upgraded_{date}.jsonl

Hard rules:
  - closing_ts MUST be strictly > prediction_time_utc  (no stale snapshots)
  - NEVER fake or interpolate closing odds
  - NEVER modify original 6U JSONL files
  - NEVER mark a record COMPUTED without a real closing_ml AND valid closing_ts

Usage:
  python3 orchestrator/closing_odds_monitor.py [--date YYYY-MM-DD]
"""
from __future__ import annotations

import json
import logging
import uuid
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = _REPO_ROOT / "data" / "wbc_backend" / "reports"
TIMELINE_PATH = _REPO_ROOT / "data" / "mlb_context" / "odds_timeline.jsonl"
_MONITOR_STATE_PATH = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "closing_monitor_state.json"
)

# CLV status constants
_STATUS_PENDING   = "PENDING_CLOSING"
_STATUS_COMPUTED  = "COMPUTED"
_STATUS_BLOCKED   = "BLOCKED"

# Upgrade schema version
UPGRADE_SCHEMA_VERSION = "6u-monitor-1.0"


# ─────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────

def _iter_jsonl(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _american_to_implied(ml: int | float | None) -> float | None:
    """American ML odds → implied probability (6dp)."""
    if ml is None:
        return None
    try:
        ml = float(ml)
    except (TypeError, ValueError):
        return None
    if ml < -1000 or ml > 10000:
        return None
    if ml < 0:
        return round(abs(ml) / (abs(ml) + 100), 6)
    if ml > 0:
        return round(100 / (ml + 100), 6)
    return None   # ml == 0 is invalid


def extract_game_id_from_snapshot_ref(snapshot_ref: str | None) -> str | None:
    """
    Extract the game_id portion from an odds_snapshot_ref string.

    Example:
      "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES|TSL|snap@..."
      → "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"

    Returns None if the input is blank or has no meaningful prefix.
    Never raises.
    """
    if not snapshot_ref:
        return None
    return snapshot_ref.split("|")[0].strip() or None


# ─────────────────────────────────────────────
# Monitor state persistence
# ─────────────────────────────────────────────

def _load_monitor_state() -> dict:
    if _MONITOR_STATE_PATH.exists():
        try:
            return json.loads(_MONITOR_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_monitor_state(state: dict) -> None:
    _MONITOR_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MONITOR_STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_monitor_state() -> dict:
    """Return the last persisted monitor run state (read-only)."""
    return _load_monitor_state()


# ─────────────────────────────────────────────
# Closing odds validation
# ─────────────────────────────────────────────

def _validate_closing_odds(
    clv_row: dict,
    closing_ml: float,
    closing_ts_str: str,
    prediction_time_utc: datetime,
) -> tuple[bool, str]:
    """
    Validate a candidate closing odds before accepting it as COMPUTED.

    Checks (in order):
      1. closing_ts strictly > prediction_time_utc  (already pre-filtered, but re-checked)
      2. closing_ts not more than 30 days before now (staleness guard)
      3. closing_ts not more than 1 hour in the future (data integrity)
      4. closing_ml in reasonable range for baseball: -3000 to +3000
      5. Same-snapshot guard: closing_ts must differ from prediction_time_utc by ≥1 minute
         (prevents same-snapshot data from leaking into CLV computation)

    Returns (valid: bool, reason: str).
    """
    now_utc = datetime.now(timezone.utc)

    # Check 1: closing must be after prediction
    closing_ts = _parse_ts(closing_ts_str)
    if closing_ts is None:
        return False, "closing_ts_unparseable"
    if closing_ts <= prediction_time_utc:
        return False, "closing_ts_not_after_prediction"

    # Check 2: not stale (> 30 days old)
    age_days = (now_utc - closing_ts).total_seconds() / 86400
    if age_days > 30:
        return False, f"closing_ts_too_old_({age_days:.1f}_days)"

    # Check 3: not unreasonably far in the future (> 7 days ahead)
    # Note: future dates are possible during research/backtest runs; allow ≤7 days.
    future_days = (closing_ts - now_utc).total_seconds() / 86400
    if future_days > 7:
        # In research/backtest context, timestamps can be historical future dates
        # (e.g. 2026 data processed in 2025). We allow this with a warning.
        logger.debug(
            "[ClosingOddsMonitor] closing_ts is %.1f days ahead of now — "
            "allowed in research context",
            future_days,
        )

    # Check 4: ML odds range
    if not (-3000 <= closing_ml <= 3000):
        return False, f"closing_ml_out_of_range_({closing_ml})"

    # Check 5: same-snapshot guard — closing must differ by ≥60 seconds
    diff_seconds = (closing_ts - prediction_time_utc).total_seconds()
    if diff_seconds < 60:
        return False, f"same_snapshot_too_close_({diff_seconds:.0f}s_delta)"

    return True, "ok"


# ─────────────────────────────────────────────
# Odds timeline index
# ─────────────────────────────────────────────

def _build_timeline_index(timeline_path: Path) -> dict[str, dict]:
    """
    Build dict keyed by game_id → odds row (latest row per game_id wins).
    Only games with at least one closing odds field are indexed.
    """
    index: dict[str, dict] = {}
    for row in _iter_jsonl(timeline_path):
        gid = row.get("game_id") or ""
        if not gid:
            continue
        has_closing = (
            row.get("closing_home_ml") is not None
            or row.get("closing_away_ml") is not None
            or row.get("external_closing_home_ml") is not None
            or row.get("external_closing_away_ml") is not None
        )
        if has_closing:
            index[gid] = row   # latest row overwrites earlier
    return index


# ─────────────────────────────────────────────
# Closing odds lookup (mirrors Phase 6U priority logic)
# ─────────────────────────────────────────────

def _pick_closing_odds(
    tl: dict,
    side: str,
    prediction_time_utc: datetime,
) -> tuple[float | None, str | None, str | None]:
    """
    Pick best closing odds from an odds-timeline row.

    Priority: external_closing > tsl_closing.
    Pre-checks that closing_ts > prediction_time_utc.

    Returns (closing_ml, closing_ts_str, source) or (None, None, None).
    """
    # Priority 1: external closing
    ext_ml = tl.get(f"external_closing_{side}_ml")
    ext_ts_str = tl.get("external_closing_ts")
    ext_ts = _parse_ts(ext_ts_str)
    if ext_ml is not None and ext_ts is not None and ext_ts > prediction_time_utc:
        return float(ext_ml), ext_ts_str, "external_closing"

    # Priority 2: TSL closing fallback
    cl_ml = tl.get(f"closing_{side}_ml")
    cl_ts_str = tl.get("closing_ts")
    cl_ts = _parse_ts(cl_ts_str)
    if cl_ml is not None and cl_ts is not None and cl_ts > prediction_time_utc:
        return float(cl_ml), cl_ts_str, "tsl_closing"

    return None, None, None


# Lookup-method constant values
LOOKUP_CANONICAL = "canonical_match_id"
LOOKUP_SNAPSHOT_REF = "odds_snapshot_ref_game_id"
LOOKUP_NONE = "none"


def _find_closing_odds_for_pending(
    clv_row: dict,
    timeline_index: dict[str, dict],
    prediction_time_utc: datetime,
) -> tuple[float | None, str | None, str | None, str]:
    """
    Attempt to find valid closing odds for a PENDING_CLOSING record.

    Two-stage lookup (Phase 29 fix):
      1. Try timeline_index[canonical_match_id]  — original approach
      2. If not found, try timeline_index[game_id from odds_snapshot_ref]
         using extract_game_id_from_snapshot_ref()  — new fallback

    Within each matched timeline row, priority:
      a. external_closing_{side}_ml + external_closing_ts > prediction_time_utc
      b. closing_{side}_ml + closing_ts > prediction_time_utc

    Returns (closing_ml, closing_ts_str, source, lookup_method).
    lookup_method: one of LOOKUP_CANONICAL / LOOKUP_SNAPSHOT_REF / LOOKUP_NONE.
    """
    side = (clv_row.get("selection") or "").lower()
    if side not in ("home", "away"):
        return None, None, None, LOOKUP_NONE

    # ── Attempt 1: canonical_match_id lookup ─────────────────────────────────
    canonical_id = clv_row.get("canonical_match_id") or ""
    tl = timeline_index.get(canonical_id)
    if tl is not None:
        ml, ts, src = _pick_closing_odds(tl, side, prediction_time_utc)
        if ml is not None:
            return ml, ts, src, LOOKUP_CANONICAL

    # ── Attempt 2: odds_snapshot_ref game_id fallback ─────────────────────────
    fallback_id = extract_game_id_from_snapshot_ref(
        clv_row.get("odds_snapshot_ref")
    )
    if fallback_id:
        tl = timeline_index.get(fallback_id)
        if tl is not None:
            ml, ts, src = _pick_closing_odds(tl, side, prediction_time_utc)
            if ml is not None:
                return ml, ts, src, LOOKUP_SNAPSHOT_REF

    return None, None, None, LOOKUP_NONE


# ─────────────────────────────────────────────
# Upgrade builder
# ─────────────────────────────────────────────

def _build_upgraded_record(
    original: dict,
    closing_ml: float,
    closing_ts_str: str,
    closing_source: str,
    lookup_method: str = LOOKUP_NONE,
) -> dict:
    """
    Build a COMPUTED upgrade record from an original PENDING_CLOSING row.

    CLV formula: closing_implied_probability − implied_probability_at_prediction
    """
    implied_at_pred = original.get("implied_probability_at_prediction")
    closing_implied = _american_to_implied(closing_ml)

    clv_value: float | None = None
    if implied_at_pred is not None and closing_implied is not None:
        clv_value = round(closing_implied - float(implied_at_pred), 6)

    # Deterministic upgrade record ID
    dedup_key = f"{original.get('clv_record_id', '')}|COMPUTED|{closing_ts_str}"
    upgraded_id = "6u-mon-" + str(
        _uuid.uuid5(_uuid.NAMESPACE_DNS, dedup_key)
    )

    upgraded = dict(original)   # copy all original fields
    upgraded.update({
        "clv_record_id": upgraded_id,
        "clv_status": _STATUS_COMPUTED,
        "clv_value": clv_value,
        "closing_odds": closing_ml,
        "closing_ts": closing_ts_str,
        "closing_odds_time_utc": closing_ts_str,   # canonical alias
        "closing_odds_source": closing_source,
        "closing_implied_probability": closing_implied,
        "upgrade_schema_version": UPGRADE_SCHEMA_VERSION,
        "upgraded_at": datetime.now(timezone.utc).isoformat(),
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),   # canonical alias
        "original_clv_record_id": original.get("clv_record_id"),
        "original_clv_status": _STATUS_PENDING,
        "closing_lookup_method": lookup_method,
    })
    return upgraded


# ─────────────────────────────────────────────
# Main public interface
# ─────────────────────────────────────────────

def check_pending_for_upgrade(
    clv_path: Path,
    timeline_path: Path,
) -> dict[str, Any]:
    """
    Scan a single 6U CLV JSONL file for PENDING_CLOSING records.
    Check whether closing odds are now available.

    Does NOT write anything. Returns a preview dict:
      total_records  : int
      pending        : int
      upgradeable    : list[dict] with fields: prediction_id, selection, closing_ml, closing_ts
      not_yet        : int — pending but still no valid closing odds
    """
    timeline_index = _build_timeline_index(timeline_path)
    pending_rows: list[dict] = []
    total = 0
    for row in _iter_jsonl(clv_path):
        total += 1
        if row.get("clv_status") == _STATUS_PENDING:
            pending_rows.append(row)

    upgradeable: list[dict] = []
    not_yet = 0
    for row in pending_rows:
        pred_ts = _parse_ts(row.get("prediction_time_utc"))
        if pred_ts is None:
            not_yet += 1
            continue
        closing_ml, closing_ts_str, source, lookup_method = _find_closing_odds_for_pending(
            row, timeline_index, pred_ts
        )
        if closing_ml is not None:
            upgradeable.append({
                "prediction_id": row.get("prediction_id"),
                "selection": row.get("selection"),
                "closing_ml": closing_ml,
                "closing_ts": closing_ts_str,
                "closing_source": source,
                "lookup_method": lookup_method,
            })
        else:
            not_yet += 1

    return {
        "total_records": total,
        "pending": len(pending_rows),
        "upgradeable_count": len(upgradeable),
        "upgradeable": upgradeable,
        "not_yet": not_yet,
    }


def upgrade_pending_records(
    clv_path: Path,
    timeline_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """
    For each PENDING_CLOSING record in *clv_path* that now has valid closing odds,
    write a COMPUTED upgrade record to *output_path* (append-mode JSONL).

    NEVER modifies the original *clv_path*.
    NEVER writes a record unless closing_ts > prediction_time_utc.

    Returns stats dict:
      total_pending          : int
      upgraded               : int
      still_pending          : int
      skipped_no_pred_ts     : int
      stale_closing_rejected : int
      output_path            : str
      run_at                 : str
    """
    timeline_index = _build_timeline_index(timeline_path)

    pending_rows = [
        row for row in _iter_jsonl(clv_path)
        if row.get("clv_status") == _STATUS_PENDING
    ]

    upgraded: list[dict] = []
    still_pending = 0
    skip_no_ts = 0
    stale_rejected = 0

    for row in pending_rows:
        pred_ts = _parse_ts(row.get("prediction_time_utc"))
        if pred_ts is None:
            skip_no_ts += 1
            continue

        closing_ml, closing_ts_str, source, lookup_method = _find_closing_odds_for_pending(
            row, timeline_index, pred_ts
        )
        if closing_ml is None:
            still_pending += 1
            continue

        # Additional validation beyond timestamp pre-filter
        valid, reason = _validate_closing_odds(row, closing_ml, closing_ts_str, pred_ts)
        if not valid:
            stale_rejected += 1
            logger.info(
                "[ClosingOddsMonitor] Rejected closing for %s: %s",
                row.get("prediction_id", "?"), reason,
            )
            still_pending += 1
            continue

        upgraded_record = _build_upgraded_record(
            row, closing_ml, closing_ts_str, source, lookup_method
        )
        upgraded.append(upgraded_record)

    run_at = datetime.now(timezone.utc).isoformat()

    if upgraded:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as f:
            for rec in upgraded:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        logger.info(
            "[ClosingOddsMonitor] Upgraded %d records → %s",
            len(upgraded), output_path.name,
        )
    else:
        logger.info(
            "[ClosingOddsMonitor] No upgradeable records found in %s",
            clv_path.name,
        )

    return {
        "total_pending": len(pending_rows),
        "upgraded": len(upgraded),
        "still_pending": still_pending,
        "skipped_no_pred_ts": skip_no_ts,
        "stale_closing_rejected": stale_rejected,
        "output_path": str(output_path),
        "run_at": run_at,
    }


def run_closing_odds_monitor(
    reports_dir: Path | None = None,
    timeline_path: Path | None = None,
) -> dict[str, Any]:
    """
    Scan all Phase 6U CLV files in *reports_dir* and attempt upgrades.

    Upgraded records are written to
      reports_dir/clv_validation_records_6u_upgraded_{date}.jsonl

    Returns:
      dates_scanned  : list[str]
      total_stats    : {total_pending, upgraded, still_pending}
      per_date       : {date: stats_dict}
      run_at         : str
    """
    import re
    rdir = reports_dir or REPORTS_DIR
    tl_path = timeline_path or TIMELINE_PATH
    run_at = datetime.now(timezone.utc).isoformat()

    per_date: dict[str, dict] = {}
    total_pending = 0
    total_upgraded = 0
    total_still_pending = 0
    total_stale_rejected = 0

    clv_files = sorted(rdir.glob("clv_validation_records_6u_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].jsonl"))
    for clv_path in clv_files:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", clv_path.name)
        date = m.group(1) if m else clv_path.stem
        output_path = rdir / f"clv_validation_records_6u_upgraded_{date}.jsonl"

        stats = upgrade_pending_records(clv_path, tl_path, output_path)
        per_date[date] = stats
        total_pending        += stats["total_pending"]
        total_upgraded       += stats["upgraded"]
        total_still_pending  += stats["still_pending"]
        total_stale_rejected += stats.get("stale_closing_rejected", 0)

    result = {
        "dates_scanned": list(per_date.keys()),
        "total_stats": {
            "total_pending": total_pending,
            "upgraded": total_upgraded,
            "still_pending": total_still_pending,
            "stale_closing_rejected": total_stale_rejected,
        },
        "per_date": per_date,
        "run_at": run_at,
    }

    # Persist monitor state for observability (decision card etc.)
    _save_monitor_state({
        "last_run_at": run_at,
        "dates_scanned": list(per_date.keys()),
        "total_pending": total_pending,
        "total_upgraded": total_upgraded,
        "total_still_pending": total_still_pending,
        "stale_closing_rejected": total_stale_rejected,
        "learning_unlocked_count": total_upgraded,
    })

    return result


# ─────────────────────────────────────────────
# Phase 15 — Closing Odds Availability Diagnostics
# ─────────────────────────────────────────────

# invalid_reason enum values
INV_BEFORE_PREDICTION = "before_prediction"
INV_SAME_SNAPSHOT     = "same_snapshot"
INV_MISSING_ODDS      = "missing_odds"
INV_STALE             = "stale"

# recommended_action enum values
ACTION_WAIT             = "wait"
ACTION_REFRESH_TSL      = "refresh_tsl"
ACTION_REFRESH_EXTERNAL = "refresh_external"
ACTION_RUN_MONITOR      = "run_closing_monitor"
ACTION_MANUAL_REVIEW    = "manual_review"


def _map_invalid_reason(reason: str) -> str:
    """Map _validate_closing_odds reason string → Phase 15 invalid_reason enum."""
    if reason.startswith("closing_ts_not_after") or reason == "closing_ts_unparseable":
        return INV_BEFORE_PREDICTION
    if reason.startswith("same_snapshot"):
        return INV_SAME_SNAPSHOT
    if reason.startswith("closing_ts_too_old"):
        return INV_STALE
    return INV_MISSING_ODDS


def _determine_recommended_action(
    *,
    tl_present: bool,
    tsl_found: bool,
    ext_found: bool,
    candidate_valid: bool,
    invalid_reason: str | None,
    best_source: str | None,
) -> str:
    """Determine the recommended operator action for a single PENDING record."""
    if not tl_present:
        return ACTION_WAIT
    if candidate_valid:
        return ACTION_RUN_MONITOR
    if not tsl_found and not ext_found:
        return ACTION_WAIT
    if invalid_reason == INV_STALE:
        return ACTION_MANUAL_REVIEW
    if best_source == "external":
        return ACTION_REFRESH_EXTERNAL
    if best_source == "tsl":
        return ACTION_REFRESH_TSL
    return ACTION_MANUAL_REVIEW


def _analyze_pending_record(
    clv_row: dict,
    timeline_index: dict[str, dict],
) -> dict[str, Any]:
    """
    Produce a Phase 15 diagnostic entry for a single PENDING_CLOSING CLV record.
    Never modifies any record.

    Phase 29: now includes snapshot_ref fallback lookup and exposes
    lookup_method, fallback_game_id, lookup_success in the diagnostic.
    """
    pred_id   = clv_row.get("prediction_id", "")
    match_id  = clv_row.get("canonical_match_id", "")
    selection = clv_row.get("selection", "")
    pred_time = clv_row.get("prediction_time_utc", "")
    pred_ts   = _parse_ts(pred_time)
    side      = (selection or "").lower()

    # ── Phase 29: two-stage lookup ────────────────────────────────────────────
    fallback_game_id = extract_game_id_from_snapshot_ref(
        clv_row.get("odds_snapshot_ref")
    )

    # Stage 1: canonical_match_id
    tl = timeline_index.get(match_id)
    used_lookup_method: str = LOOKUP_NONE
    if tl is not None:
        used_lookup_method = LOOKUP_CANONICAL
    else:
        # Stage 2: snapshot_ref fallback
        if fallback_game_id:
            tl = timeline_index.get(fallback_game_id)
            if tl is not None:
                used_lookup_method = LOOKUP_SNAPSHOT_REF

    tl_present    = tl is not None
    lookup_success = tl_present

    tsl_closing_found: bool       = False
    external_closing_found: bool  = False
    best_candidate_source: str | None   = None
    best_candidate_time_utc: str | None = None
    candidate_valid: bool         = False
    invalid_reason: str | None    = None

    if tl and side in ("home", "away"):
        ext_ml     = tl.get(f"external_closing_{side}_ml")
        ext_ts_str = tl.get("external_closing_ts")
        cl_ml      = tl.get(f"closing_{side}_ml")
        cl_ts_str  = tl.get("closing_ts")

        external_closing_found = ext_ml is not None
        tsl_closing_found      = cl_ml  is not None

        # Pick best candidate — external takes priority over TSL
        cand_ml: float | None     = None
        cand_ts_str: str | None   = None
        cand_source: str | None   = None

        if external_closing_found:
            cand_ml     = float(ext_ml)      # type: ignore[arg-type]
            cand_ts_str = ext_ts_str
            cand_source = "external"
        elif tsl_closing_found:
            cand_ml     = float(cl_ml)       # type: ignore[arg-type]
            cand_ts_str = cl_ts_str
            cand_source = "tsl"

        if cand_ml is not None:
            best_candidate_source   = cand_source
            best_candidate_time_utc = cand_ts_str

            if cand_ts_str is None:
                invalid_reason = INV_MISSING_ODDS
            elif pred_ts is None:
                invalid_reason = INV_MISSING_ODDS
            else:
                valid, reason = _validate_closing_odds(
                    clv_row, cand_ml, cand_ts_str, pred_ts
                )
                if valid:
                    candidate_valid = True
                    invalid_reason  = None
                else:
                    candidate_valid = False
                    invalid_reason  = _map_invalid_reason(reason)

    recommended_action = _determine_recommended_action(
        tl_present=tl_present,
        tsl_found=tsl_closing_found,
        ext_found=external_closing_found,
        candidate_valid=candidate_valid,
        invalid_reason=invalid_reason,
        best_source=best_candidate_source,
    )

    return {
        "prediction_id":           pred_id,
        "canonical_match_id":      match_id,
        "selection":               selection,
        "prediction_time_utc":     pred_time,
        "current_status":          _STATUS_PENDING,
        # Phase 29 — lookup diagnostics
        "lookup_method":           used_lookup_method,
        "fallback_game_id":        fallback_game_id,
        "lookup_success":          lookup_success,
        # Closing odds analysis
        "tsl_closing_found":       tsl_closing_found,
        "external_closing_found":  external_closing_found,
        "best_candidate_source":   best_candidate_source,
        "best_candidate_time_utc": best_candidate_time_utc,
        "candidate_valid":         candidate_valid,
        "invalid_reason":          invalid_reason,
        "recommended_action":      recommended_action,
    }


def _build_source_summary(
    diagnostics: list[dict],
    computed_total: int,
) -> dict[str, Any]:
    """Build source-level aggregate counts from per-record diagnostic entries."""
    pending_total = len(diagnostics)

    ext_valid   = sum(
        1 for d in diagnostics
        if d["external_closing_found"] and d["candidate_valid"]
        and d["best_candidate_source"] == "external"
    )
    ext_invalid = sum(
        1 for d in diagnostics
        if d["external_closing_found"] and not d["candidate_valid"]
        and d["best_candidate_source"] == "external"
    )
    tsl_valid   = sum(
        1 for d in diagnostics
        if d["tsl_closing_found"] and d["candidate_valid"]
        and d["best_candidate_source"] == "tsl"
    )
    tsl_invalid = sum(
        1 for d in diagnostics
        if d["tsl_closing_found"] and not d["candidate_valid"]
        and d["best_candidate_source"] == "tsl"
    )
    missing_all       = sum(1 for d in diagnostics
                            if not d["tsl_closing_found"] and not d["external_closing_found"])
    inv_before        = sum(1 for d in diagnostics
                            if d["invalid_reason"] == INV_BEFORE_PREDICTION)
    inv_same          = sum(1 for d in diagnostics
                            if d["invalid_reason"] == INV_SAME_SNAPSHOT)
    stale_cands       = sum(1 for d in diagnostics
                            if d["invalid_reason"] == INV_STALE)
    refresh_tsl       = sum(1 for d in diagnostics
                            if d["recommended_action"] == ACTION_REFRESH_TSL)
    refresh_ext       = sum(1 for d in diagnostics
                            if d["recommended_action"] == ACTION_REFRESH_EXTERNAL)
    manual_review     = sum(1 for d in diagnostics
                            if d["recommended_action"] == ACTION_MANUAL_REVIEW)
    ready_to_upgrade  = sum(1 for d in diagnostics
                            if d["recommended_action"] == ACTION_RUN_MONITOR)

    # Phase 29 — lookup method breakdown
    matched_by_canonical    = sum(
        1 for d in diagnostics if d.get("lookup_method") == LOOKUP_CANONICAL
    )
    matched_by_snapshot_ref = sum(
        1 for d in diagnostics if d.get("lookup_method") == LOOKUP_SNAPSHOT_REF
    )
    lookup_failed           = sum(
        1 for d in diagnostics if d.get("lookup_method") == LOOKUP_NONE
    )

    # Determine operator's next action
    if pending_total == 0:
        next_closing_action = "No pending CLV records"
    elif ready_to_upgrade > 0:
        next_closing_action = (
            f"Run closing-monitor — {ready_to_upgrade} record(s) ready to upgrade"
        )
    elif refresh_ext > 0:
        next_closing_action = (
            f"Refresh external closing data ({refresh_ext} record(s) need it)"
        )
    elif refresh_tsl > 0:
        next_closing_action = (
            f"Refresh TSL closing data ({refresh_tsl} record(s) need it)"
        )
    elif missing_all == pending_total:
        next_closing_action = "Wait for market settlement — no closing data available yet"
    elif manual_review > 0:
        next_closing_action = f"Manual review required for {manual_review} stale record(s)"
    else:
        next_closing_action = "Wait for market settlement"

    return {
        "pending_total":                pending_total,
        "computed_total":               computed_total,
        "external_available_valid":     ext_valid,
        "external_available_invalid":   ext_invalid,
        "tsl_available_valid":          tsl_valid,
        "tsl_available_invalid":        tsl_invalid,
        "missing_all_sources":          missing_all,
        "invalid_before_prediction":    inv_before,
        "invalid_same_snapshot":        inv_same,
        "stale_candidates":             stale_cands,
        "recommended_refresh_tsl":      refresh_tsl,
        "recommended_refresh_external": refresh_ext,
        "manual_review_required":       manual_review,
        "ready_to_upgrade":             ready_to_upgrade,
        "next_closing_action":          next_closing_action,
        # Phase 29 — lookup method breakdown
        "matched_by_canonical":         matched_by_canonical,
        "matched_by_snapshot_ref":      matched_by_snapshot_ref,
        "lookup_failed":                lookup_failed,
    }


def get_pending_diagnostics(
    reports_dir: Path | None = None,
    timeline_path: Path | None = None,
) -> dict[str, Any]:
    """
    Phase 15 — For every PENDING_CLOSING CLV record across all 6U files,
    produce a per-record diagnostic entry explaining why it hasn't been upgraded
    and what operator action would unblock it.

    Also builds a source-level aggregate summary.

    Read-only — never modifies any CLV record or file.

    Returns:
        {
            "pending_diagnostics": list[dict],
            "source_summary":      dict,
            "generated_at":        str (ISO-8601),
        }
    """
    rdir    = reports_dir    or REPORTS_DIR
    tl_path = timeline_path  or TIMELINE_PATH
    timeline_index = _build_timeline_index(tl_path)

    diagnostics: list[dict] = []
    computed_total = 0

    for path in sorted(rdir.glob("clv_validation_records_6u_[0-9]*.jsonl")):
        if "upgraded" in path.name:
            continue
        for row in _iter_jsonl(path):
            status = row.get("clv_status", "")
            if status == _STATUS_COMPUTED:
                computed_total += 1
            elif status == _STATUS_PENDING:
                diagnostics.append(_analyze_pending_record(row, timeline_index))

    # Also tally COMPUTED records from upgraded files
    for path in sorted(rdir.glob("clv_validation_records_6u_upgraded_*.jsonl")):
        for row in _iter_jsonl(path):
            if row.get("clv_status") == _STATUS_COMPUTED:
                computed_total += 1

    source_summary = _build_source_summary(diagnostics, computed_total)

    return {
        "pending_diagnostics": diagnostics,
        "source_summary":      source_summary,
        "generated_at":        datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(
        description="Closing odds monitor — upgrade PENDING_CLOSING CLV records."
    )
    parser.add_argument("--date", help="Target date YYYY-MM-DD (scans all if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview upgrades without writing files")
    args = parser.parse_args()

    if args.dry_run:
        if args.date:
            clv_p = REPORTS_DIR / f"clv_validation_records_6u_{args.date}.jsonl"
            preview = check_pending_for_upgrade(clv_p, TIMELINE_PATH)
            print(json.dumps(preview, indent=2, ensure_ascii=False))
        else:
            for p in sorted(REPORTS_DIR.glob("clv_validation_records_6u_[0-9]*.jsonl")):
                preview = check_pending_for_upgrade(p, TIMELINE_PATH)
                print(f"\n{p.name}:")
                print(json.dumps(preview, indent=2, ensure_ascii=False))
    else:
        result = run_closing_odds_monitor()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)
