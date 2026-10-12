"""
Phase 6 Data Registry — read-only index of Phase 6T/6U pipeline outputs.

Exposes counts and row-level access without modifying any files.

Data sources (read-only):
  data/wbc_backend/reports/prediction_registry_6t_*.jsonl  — Phase 6T flat registry
  data/wbc_backend/reports/clv_validation_records_6u_*.jsonl   — Phase 6U CLV records
  data/wbc_backend/reports/clv_validation_records_6u_summary_*.json — run summaries
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = _REPO_ROOT / "data" / "wbc_backend" / "reports"

# ── CLV status constants (mirror Phase 6U enum) ──
CLV_COMPUTED = "COMPUTED"
CLV_PENDING_CLOSING = "PENDING_CLOSING"
CLV_BLOCKED = "BLOCKED"

# ── Governance token required for 6T rows ──
GOVERNANCE_VALIDATED = "VALIDATED_ML_ONLY"


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _iter_jsonl(path: Path):
    """Yield dicts from a JSONL file; silently skip malformed lines."""
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


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[Phase6Registry] Failed to load %s: %s", path.name, exc)
        return None


def _extract_date(filename: str) -> str | None:
    """Extract ISO date (YYYY-MM-DD) from filename like *_2026-04-30.jsonl."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else None


# ─────────────────────────────────────────────
# File discovery
# ─────────────────────────────────────────────

def discover_phase6_dates(reports_dir: Path | None = None) -> list[str]:
    """
    Return sorted list of date strings for which Phase 6T registry files exist.
    Example: ['2026-04-30']
    """
    rdir = reports_dir or REPORTS_DIR
    dates: list[str] = []
    for p in rdir.glob("prediction_registry_6t_*.jsonl"):
        d = _extract_date(p.name)
        if d and d not in dates:
            dates.append(d)
    return sorted(dates)


def get_phase6_paths(date: str, reports_dir: Path | None = None) -> dict[str, Path]:
    """
    Return canonical paths for all Phase 6 files associated with *date*.
    Keys: registry_6t, clv_6u, clv_summary_6u
    """
    rdir = reports_dir or REPORTS_DIR
    return {
        "registry_6t":   rdir / f"prediction_registry_6t_{date}.jsonl",
        "clv_6u":        rdir / f"clv_validation_records_6u_{date}.jsonl",
        "clv_summary_6u": rdir / f"clv_validation_records_6u_summary_{date}.json",
    }


# ─────────────────────────────────────────────
# Row-level loaders
# ─────────────────────────────────────────────

def load_registry_6t_rows(date: str, reports_dir: Path | None = None) -> list[dict]:
    """
    Load all Phase 6T flat registry rows for *date*.
    Filters to rows with governance_status == VALIDATED_ML_ONLY only.
    """
    paths = get_phase6_paths(date, reports_dir)
    rows: list[dict] = []
    for row in _iter_jsonl(paths["registry_6t"]):
        if row.get("governance_status") == GOVERNANCE_VALIDATED:
            rows.append(row)
    return rows


def load_clv_6u_rows(date: str, reports_dir: Path | None = None) -> list[dict]:
    """Load all Phase 6U CLV records for *date*."""
    paths = get_phase6_paths(date, reports_dir)
    return list(_iter_jsonl(paths["clv_6u"]))


def load_clv_6u_summary(date: str, reports_dir: Path | None = None) -> dict[str, Any] | None:
    """Load Phase 6U run summary JSON for *date*. Returns None if absent."""
    paths = get_phase6_paths(date, reports_dir)
    return _safe_load_json(paths["clv_summary_6u"])


# ─────────────────────────────────────────────
# Aggregated status
# ─────────────────────────────────────────────

def get_phase6_status(reports_dir: Path | None = None) -> dict[str, Any]:
    """
    Scan all Phase 6 outputs across all dates and return a rolled-up status dict.

    Returned fields:
      dates                  : list of date strings with 6T data
      registry_rows          : total 6T rows (VALIDATED_ML_ONLY)
      clv_total              : total 6U CLV records
      clv_computed           : count with clv_status == COMPUTED
      clv_pending_closing    : count with clv_status == PENDING_CLOSING
      clv_blocked            : count with clv_status == BLOCKED
      eligible_for_simulation: rows with positive EV and execution_mode == RESEARCH_ONLY
      eligible_for_strategy_update: clv_computed count (has real CLV signal)
      all_clv_pending        : True if clv_computed == 0 and clv_pending_closing > 0
      next_required_event    : human-readable note
      last_updated           : UTC timestamp of this scan
    """
    dates = discover_phase6_dates(reports_dir)

    registry_rows = 0
    clv_total = 0
    clv_computed = 0
    clv_pending = 0
    clv_blocked = 0
    eligible_for_sim = 0

    for date in dates:
        rows_6t = load_registry_6t_rows(date, reports_dir)
        registry_rows += len(rows_6t)
        for r in rows_6t:
            ev = r.get("ev_percent")
            mode = r.get("execution_mode", "")
            if isinstance(ev, (int, float)) and ev > 0 and mode == "RESEARCH_ONLY":
                eligible_for_sim += 1

        rows_6u = load_clv_6u_rows(date, reports_dir)
        clv_total += len(rows_6u)
        for r in rows_6u:
            status = r.get("clv_status", "")
            if status == CLV_COMPUTED:
                clv_computed += 1
            elif status == CLV_PENDING_CLOSING:
                clv_pending += 1
            elif status == CLV_BLOCKED:
                clv_blocked += 1

    all_pending = clv_computed == 0 and clv_pending > 0

    if all_pending:
        next_event = "Wait for post-prediction closing odds to become available"
    elif clv_computed > 0 and clv_pending > 0:
        next_event = f"Partial: {clv_computed} COMPUTED, {clv_pending} still PENDING_CLOSING"
    elif clv_computed > 0 and clv_pending == 0:
        next_event = "All CLV COMPUTED — ready for full CLV-based reinforcement"
    else:
        next_event = "No Phase 6 data available yet"

    return {
        "dates": dates,
        "registry_rows": registry_rows,
        "clv_total": clv_total,
        "clv_computed": clv_computed,
        "clv_pending_closing": clv_pending,
        "clv_blocked": clv_blocked,
        "eligible_for_simulation": eligible_for_sim,
        "eligible_for_strategy_update": clv_computed,
        "all_clv_pending": all_pending,
        "next_required_event": next_event,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────
# Simulation-ready row adapter
# ─────────────────────────────────────────────

def registry_rows_to_simulation_records(
    rows: list[dict],
) -> list[dict]:
    """
    Convert Phase 6T registry rows into lightweight dicts that can be
    consumed by simulation scenarios (EV / edge stress tests only).

    IMPORTANT: These records do NOT carry `result`, `roi`, or `pnl`
    because no game has settled.  They carry `predicted_prob`,
    `market_prob` (implied_probability), `ev_percent`, and `regime`.
    Callers MUST NOT use these for Brier or realized-ROI computation.
    """
    out: list[dict] = []
    for r in rows:
        pred = r.get("ml_predicted_probability")
        mkt = r.get("implied_probability")
        if pred is None or mkt is None:
            continue
        out.append({
            "source": "phase6t_registry",
            "prediction_id": r.get("prediction_id"),
            "game_id": r.get("canonical_match_id"),
            "selection": r.get("selection"),
            "market_type": r.get("market_type"),
            "predicted_prob": float(pred),
            "market_prob": float(mkt),
            "ev_percent": float(r.get("ev_percent") or 0.0),
            "regime": r.get("regime") or "wbc_2026",
            "execution_mode": r.get("execution_mode", "RESEARCH_ONLY"),
            "clv_usable": bool(r.get("clv_usable", False)),
            # No result / roi / pnl — no settlement yet
            "result": None,
            "roi": None,
            "pnl": None,
        })
    return out
