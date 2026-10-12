"""
wbc_backend/prediction/mlb_context_safety_audit.py

P12: Context safety audit for MLB prediction pipeline.

Evaluates each context file (JSONL / CSV / JSON) for:
  - Postgame leakage risk (columns that are only available after game completion)
  - Pregame safety (columns that are available before game start)
  - Unknown / ambiguous files

Safety classification:
  PREGAME_SAFE     — file contains only pregame-available data
  POSTGAME_RISK    — file contains columns suggesting postgame / outcome data
  UNKNOWN          — cannot determine from column names alone
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "audit_context_safety",
    "summarize_context_safety",
]

# ─────────────────────────────────────────────────────────────────────────────
# § 1  Keyword lists
# ─────────────────────────────────────────────────────────────────────────────

_POSTGAME_KEYWORDS: list[str] = [
    "final",
    "result",
    "score",
    "runs",
    "winner",
    "win",
    "loss",
    "settled",
    "closing",
    "postgame",
    "actual",
    "home_score",
    "away_score",
    "home_win",
    "away_win",
    "outcome",
    "finished",
]

_PREGAME_KEYWORDS: list[str] = [
    "probable",
    "starter",
    "weather",
    "forecast",
    "rest",
    "scheduled",
    "pregame",
    "bullpen",
    "usage",
    "injury",
    "lineup",
    "era",
    "wind",
    "temp",
    "roof",
    "park",
    "inactive",
    "odds",
    "spread",
    "moneyline",
    "over_under",
]

# Columns that are always identity / metadata — not scored
_META_COLUMNS: set[str] = {
    "game_id",
    "fetched_at",
    "source",
    "unavailable_fields",
    "date",
    "home_team",
    "away_team",
    "start_time",
}


def _col_has_keyword(col: str, keywords: list[str]) -> bool:
    col_lower = col.lower()
    # Split on underscores, hyphens, dots for compound column names
    parts = set(re.split(r"[_\-\.]", col_lower))
    for kw in keywords:
        if kw in parts:
            return True
        # Also check direct substring for multi-word keywords
        if kw in col_lower and len(kw) >= 4:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# § 2  File readers
# ─────────────────────────────────────────────────────────────────────────────

def _read_file_sample(
    path: Path,
    sample_size: int,
) -> tuple[list[dict], str]:
    """
    Read up to sample_size rows from a JSONL, CSV, or JSON file.

    Returns (rows, detected_type).
    """
    suffix = path.suffix.lower()

    if suffix == ".jsonl":
        rows: list[dict] = []
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if len(rows) >= sample_size:
                        break
        except OSError:
            return [], "jsonl"
        return rows, "jsonl"

    if suffix == ".csv":
        rows = []
        try:
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
                    if len(rows) >= sample_size:
                        break
        except OSError:
            return [], "csv"
        return rows, "csv"

    if suffix == ".json":
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return [], "json"
        if isinstance(data, list):
            return data[:sample_size], "json_array"
        if isinstance(data, dict):
            return [data], "json_object"
        return [], "json"

    return [], f"unknown({suffix})"


def _count_file_rows(path: Path) -> int:
    """Count rows / entries in a file."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".jsonl":
            count = 0
            with path.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
            return count
        if suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return sum(1 for _ in reader)
        if suffix == ".json":
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return len(data)
            return 1
    except OSError:
        pass
    return -1


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Single-file audit
# ─────────────────────────────────────────────────────────────────────────────

def _audit_single_file(path: Path, sample_size: int) -> dict[str, Any]:
    rows, detected_type = _read_file_sample(path, sample_size)
    row_count = _count_file_rows(path)

    if not rows:
        return {
            "file_path": str(path),
            "row_count": row_count,
            "detected_context_type": detected_type,
            "key_columns": [],
            "value_columns": [],
            "has_outcome_columns": False,
            "has_postgame_keywords": False,
            "has_pregame_keywords": False,
            "safety_status": "UNKNOWN",
            "safety_reasons": ["file_empty_or_unreadable"],
            "sample_keys": [],
        }

    # Gather all column names from sample rows
    all_cols: set[str] = set()
    for row in rows:
        all_cols.update(_flatten_keys(row))

    key_cols = [c for c in sorted(all_cols) if "game_id" in c.lower() or "date" in c.lower() or "team" in c.lower()]
    value_cols = [c for c in sorted(all_cols) if c not in _META_COLUMNS]

    postgame_hits: list[str] = [
        c for c in all_cols
        if c.lower() not in _META_COLUMNS
        and _col_has_keyword(c, _POSTGAME_KEYWORDS)
    ]
    pregame_hits: list[str] = [
        c for c in all_cols
        if c.lower() not in _META_COLUMNS
        and _col_has_keyword(c, _PREGAME_KEYWORDS)
    ]

    has_postgame = len(postgame_hits) > 0
    has_pregame = len(pregame_hits) > 0

    # Detect outcome columns specifically
    outcome_cols = [
        c for c in all_cols
        if any(kw in c.lower() for kw in ("_score", "home_win", "away_win", "winner", "outcome", "home_score", "away_score", "result"))
        and c.lower() not in _META_COLUMNS
    ]
    has_outcome = len(outcome_cols) > 0

    # Determine safety status
    reasons: list[str] = []
    if has_outcome:
        reasons.append(f"outcome_columns_present: {outcome_cols}")
    if has_postgame and not has_outcome:
        # Some postgame keywords are also in pregame context (e.g. "closing odds")
        # Only flag non-outcome postgame keywords as WARNING
        non_outcome_pg = [c for c in postgame_hits if c not in outcome_cols]
        if non_outcome_pg:
            reasons.append(f"postgame_keyword_columns: {non_outcome_pg}")

    if has_postgame and has_outcome:
        status = "POSTGAME_RISK"
    elif has_postgame and not has_pregame:
        status = "POSTGAME_RISK"
        reasons.append("no_pregame_keywords_found")
    elif has_pregame:
        status = "PREGAME_SAFE"
        reasons.append(f"pregame_keywords_present: {pregame_hits[:5]}")
    else:
        status = "UNKNOWN"
        reasons.append("no_clear_temporal_keywords")

    # Sample keys
    sample_keys: list[str] = []
    for row in rows[:3]:
        gid = row.get("game_id") or row.get("Date") or row.get("date")
        if gid:
            sample_keys.append(str(gid))

    return {
        "file_path": str(path),
        "row_count": row_count,
        "detected_context_type": detected_type,
        "key_columns": key_cols,
        "value_columns": value_cols[:20],
        "has_outcome_columns": has_outcome,
        "has_postgame_keywords": has_postgame,
        "has_pregame_keywords": has_pregame,
        "postgame_keyword_hits": postgame_hits[:10],
        "pregame_keyword_hits": pregame_hits[:10],
        "outcome_columns": outcome_cols,
        "safety_status": status,
        "safety_reasons": reasons,
        "sample_keys": sample_keys,
    }


def _flatten_keys(obj: Any, prefix: str = "") -> list[str]:
    """Flatten nested dict/list keys to a flat list of dot-separated keys."""
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys.append(full_key)
            if isinstance(v, dict):
                keys.extend(_flatten_keys(v, full_key))
    return keys


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Multi-file audit
# ─────────────────────────────────────────────────────────────────────────────

_SUPPORTED_EXTENSIONS = {".jsonl", ".csv", ".json"}


def _discover_context_files(roots: list[str | Path]) -> list[Path]:
    """Recursively discover JSONL/CSV/JSON files under the given roots."""
    found: list[Path] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for ext in _SUPPORTED_EXTENSIONS:
            for p in sorted(root_path.rglob(f"*{ext}")):
                if p.is_file():
                    found.append(p)
    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in found:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def audit_context_safety(
    context_files: list[str | Path] | None = None,
    *,
    roots: list[str | Path] | None = None,
    sample_size: int = 20,
) -> dict[str, Any]:
    """
    Audit context files for postgame leakage and pregame safety.

    Parameters
    ----------
    context_files : list of explicit paths to audit, OR
    roots         : directories to search recursively
    sample_size   : number of rows to sample per file

    Returns a dict with:
      files            : list of per-file audit dicts
      total_files      : int
      safety_counts    : dict{PREGAME_SAFE, POSTGAME_RISK, UNKNOWN}
    """
    if context_files:
        paths = [Path(p) for p in context_files]
    elif roots:
        paths = _discover_context_files(roots)
    else:
        paths = []

    file_audits: list[dict] = []
    for path in paths:
        file_audits.append(_audit_single_file(path, sample_size))

    counts: dict[str, int] = {"PREGAME_SAFE": 0, "POSTGAME_RISK": 0, "UNKNOWN": 0}
    for fa in file_audits:
        status = fa.get("safety_status", "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1

    return {
        "files": file_audits,
        "total_files": len(file_audits),
        "safety_counts": counts,
        "sample_size_used": sample_size,
    }


def summarize_context_safety(audit: dict) -> dict[str, Any]:
    """
    Summarize a context safety audit result.

    Returns a high-level dict for reporting.
    """
    counts = audit.get("safety_counts", {})
    total = audit.get("total_files", 0)
    safe = counts.get("PREGAME_SAFE", 0)
    risk = counts.get("POSTGAME_RISK", 0)
    unknown = counts.get("UNKNOWN", 0)
    usable = safe
    unsafe = risk

    files = audit.get("files", [])
    risk_files = [f["file_path"] for f in files if f.get("safety_status") == "POSTGAME_RISK"]
    unknown_files = [f["file_path"] for f in files if f.get("safety_status") == "UNKNOWN"]
    safe_files = [f["file_path"] for f in files if f.get("safety_status") == "PREGAME_SAFE"]

    if risk > 0:
        recommendation = (
            f"CAUTION: {risk} file(s) have postgame leakage risk. "
            "Exclude from pregame feature pipeline. "
            f"Risky files: {risk_files}"
        )
    elif unknown > 0:
        recommendation = (
            f"REVIEW: {unknown} file(s) have ambiguous temporal status. "
            "Manually verify before using as pregame features."
        )
    else:
        recommendation = f"OK: All {safe} audited file(s) appear pregame-safe."

    return {
        "total_files": total,
        "pregame_safe_count": safe,
        "postgame_risk_count": risk,
        "unknown_count": unknown,
        "usable_file_count": usable,
        "unsafe_file_count": unsafe,
        "safe_files": safe_files,
        "risk_files": risk_files,
        "unknown_files": unknown_files,
        "safety_recommendation": recommendation,
    }
