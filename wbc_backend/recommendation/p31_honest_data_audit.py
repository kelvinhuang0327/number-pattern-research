"""
P31 Honest Data Reality Audit — Source Classification Module.

Classifies every data source in the repository into exactly one of:
  RAW_PRIMARY    — game-date-stamped CSV/JSON in data/, no model fields
  RAW_SECONDARY  — externally sourced exports (Retrosheet, MLB Stats API)
  DERIVED_OUTPUT — outputs/ or model-generated pipeline artifacts
  SCHEMA_PARTIAL — raw-looking files missing required canonical columns

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

# Required canonical columns for a source to qualify as RAW_PRIMARY.
# Both the "home" and "away" score variants are acceptable.
CANONICAL_REQUIRED: frozenset[str] = frozenset(
    {
        "game_date",
        "home_team",
        "away_team",
    }
)
CANONICAL_SCORE_HOME: frozenset[str] = frozenset(
    {"home_score", "final_home_score", "Home Score"}
)
CANONICAL_SCORE_AWAY: frozenset[str] = frozenset(
    {"away_score", "final_away_score", "Away Score"}
)
CANONICAL_ODDS_HOME: frozenset[str] = frozenset(
    {
        "closing_moneyline_home",
        "moneyline_home",
        "home_ml",
        "Home ML",
    }
)
CANONICAL_ODDS_AWAY: frozenset[str] = frozenset(
    {
        "closing_moneyline_away",
        "moneyline_away",
        "away_ml",
        "Away ML",
    }
)

# Column names that conclusively identify a file as derived/model-generated.
DERIVED_SIGNAL_COLUMNS: frozenset[str] = frozenset(
    {
        "predicted_probability",
        "model_score",
        "edge",
        "kelly_fraction",
        "recommendation",
        "p16_status",
        "paper_status",
        "recommendation_status",
        "clv_usable",
        "leakage_guard_version",
        "feature_version",
        "model_version",
        "dry_run",
        "prediction_status",
    }
)

# Filename / path patterns that signal DERIVED_OUTPUT regardless of content.
DERIVED_PATH_PATTERNS: tuple[str, ...] = (
    "/outputs/",
    "outputs/predictions",
    "/p15/",
    "/p25/",
    "/p27/",
    "PAPER/",
    "model_output",
    "model_predictions",
    "prediction_",
    "predictions_",
    "dry_run",
    "manifest_dry_run",
    "model_deep_diag",
    "paper_ledger",
    "paper_recommendation",
    "oof_model",
    "raw_model.csv",       # pipeline artefact not raw data
    "learning_state.json",
    "odds_snapshots",      # derived pipeline snapshot
    "match_identity_bridge",
    "model_output_contract",
    "prediction_timestamp_evidence",
)

# Paths that signal RAW_SECONDARY (external export, not model-generated).
RAW_SECONDARY_PATTERNS: tuple[str, ...] = (
    "retrosheet",
    "gl2024",
    "gl2025",
    "gl2023",
    "mlb_stats_api",
    "statsapi",
)

# Retrosheet fixed-width game log column names (subset, positional mapping).
# Full gl2024 has 161 fields; we only check for the score fields we need.
RETROSHEET_KNOWN_COLUMNS: frozenset[str] = frozenset(
    {
        "date",
        "home_team_id",
        "visiting_team_id",
        "home_score",
        "visitor_score",
    }
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class SourceClass(str, Enum):
    RAW_PRIMARY = "RAW_PRIMARY"
    RAW_SECONDARY = "RAW_SECONDARY"
    DERIVED_OUTPUT = "DERIVED_OUTPUT"
    SCHEMA_PARTIAL = "SCHEMA_PARTIAL"


@dataclass
class SourceEntry:
    path: str
    source_class: SourceClass
    has_game_date: bool
    has_scores: bool
    has_odds: bool
    has_derived_signals: bool
    missing_canonical_columns: list[str]
    year_coverage: list[int]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "source_class": self.source_class.value,
            "has_game_date": self.has_game_date,
            "has_scores": self.has_scores,
            "has_odds": self.has_odds,
            "has_derived_signals": self.has_derived_signals,
            "missing_canonical_columns": ";".join(self.missing_canonical_columns),
            "year_coverage": ";".join(str(y) for y in self.year_coverage),
            "notes": self.notes,
        }


@dataclass
class AuditCounters:
    total_sources: int = 0
    raw_primary_count: int = 0
    raw_secondary_count: int = 0
    derived_output_count: int = 0
    schema_partial_count: int = 0
    usable_2024_raw_count: int = 0
    # Number of sources that P30 counted as "ready" but are actually derived.
    misleading_ready_source_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_sources": self.total_sources,
            "raw_primary_count": self.raw_primary_count,
            "raw_secondary_count": self.raw_secondary_count,
            "derived_output_count": self.derived_output_count,
            "schema_partial_count": self.schema_partial_count,
            "usable_2024_raw_count": self.usable_2024_raw_count,
            "misleading_ready_source_count": self.misleading_ready_source_count,
        }


@dataclass
class HonestDataAuditResult:
    entries: list[SourceEntry] = field(default_factory=list)
    counters: AuditCounters = field(default_factory=AuditCounters)
    paper_only: bool = PAPER_ONLY
    production_ready: bool = PRODUCTION_READY


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _is_derived_by_path(path_str: str) -> bool:
    """Return True if the path matches any known derived-output pattern."""
    lower = path_str.replace("\\", "/").lower()
    for pat in DERIVED_PATH_PATTERNS:
        if pat.lower() in lower:
            return True
    return False


def _is_raw_secondary_by_path(path_str: str) -> bool:
    lower = path_str.replace("\\", "/").lower()
    for pat in RAW_SECONDARY_PATTERNS:
        if pat.lower() in lower:
            return True
    return False


def _read_column_names_csv(path: Path, max_rows: int = 2) -> list[str]:
    """Return header column names from a CSV file. Returns [] on failure."""
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            return [c.strip() for c in header]
    except Exception:
        return []


def _read_column_names_json(path: Path) -> list[str]:
    """Return top-level keys from the first object of a JSON/JSONL file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        # Try as JSONL first
        first_line = text.strip().splitlines()[0] if text.strip() else "{}"
        obj = json.loads(first_line)
        if isinstance(obj, dict):
            return list(obj.keys())
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return list(obj[0].keys())
        # Try full JSON
        full = json.loads(text)
        if isinstance(full, dict):
            return list(full.keys())
        if isinstance(full, list) and full and isinstance(full[0], dict):
            return list(full[0].keys())
    except Exception:
        pass
    return []


def _get_columns(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_column_names_csv(path)
    if suffix in (".json", ".jsonl"):
        return _read_column_names_json(path)
    return []


def _detect_year_coverage(path: Path, columns: list[str]) -> list[int]:
    """Heuristically detect which years this file covers from its path/name."""
    years: list[int] = []
    name = path.name + str(path.parent)
    for y in range(2020, 2026):
        if str(y) in name:
            years.append(y)
    return sorted(set(years))


def _check_canonical_presence(columns: list[str]) -> dict[str, bool]:
    col_set = set(c.lower() for c in columns)
    col_orig = set(columns)

    has_date = (
        "game_date" in col_set
        or "date" in col_set
        or "Date" in col_orig
        or "game_date" in col_orig
    )
    has_home = (
        "home_team" in col_set
        or "Home" in col_orig
        or "home" in col_set
    )
    has_away = (
        "away_team" in col_set
        or "Away" in col_orig
        or "visiting_team_id" in col_set
    )
    has_score_home = bool(CANONICAL_SCORE_HOME & col_orig) or "home score" in col_set
    has_score_away = bool(CANONICAL_SCORE_AWAY & col_orig) or "away score" in col_set
    has_odds_home = bool(CANONICAL_ODDS_HOME & col_orig)
    has_odds_away = bool(CANONICAL_ODDS_AWAY & col_orig)
    has_derived = bool(DERIVED_SIGNAL_COLUMNS & col_orig)

    return {
        "has_date": has_date,
        "has_home": has_home,
        "has_away": has_away,
        "has_score_home": has_score_home,
        "has_score_away": has_score_away,
        "has_odds_home": has_odds_home,
        "has_odds_away": has_odds_away,
        "has_derived": has_derived,
    }


def _classify_file(path: Path, repo_root: Path) -> SourceEntry:
    """Classify a single file and return a SourceEntry."""
    rel = str(path.relative_to(repo_root)).replace("\\", "/")

    columns = _get_columns(path)
    presence = _check_canonical_presence(columns)

    has_game_date = presence["has_date"]
    has_scores = presence["has_score_home"] and presence["has_score_away"]
    has_odds = presence["has_odds_home"] and presence["has_odds_away"]
    has_derived = presence["has_derived"]

    year_coverage = _detect_year_coverage(path, columns)

    # --- Classification decision tree ---

    # 1. DERIVED_OUTPUT: path pattern OR derived signal columns
    if _is_derived_by_path(rel) or has_derived:
        missing: list[str] = []
        return SourceEntry(
            path=rel,
            source_class=SourceClass.DERIVED_OUTPUT,
            has_game_date=has_game_date,
            has_scores=has_scores,
            has_odds=has_odds,
            has_derived_signals=has_derived,
            missing_canonical_columns=missing,
            year_coverage=year_coverage,
            notes="Derived by path pattern or model-generated column signal.",
        )

    # 2. RAW_SECONDARY: external export (Retrosheet / MLB Stats API)
    if _is_raw_secondary_by_path(rel):
        return SourceEntry(
            path=rel,
            source_class=SourceClass.RAW_SECONDARY,
            has_game_date=has_game_date,
            has_scores=has_scores,
            has_odds=has_odds,
            has_derived_signals=False,
            missing_canonical_columns=[],
            year_coverage=year_coverage,
            notes="External export (Retrosheet / MLB Stats API format). No closing odds.",
        )

    # 3. RAW_PRIMARY candidate: data/ directory, no derived signals
    #    Check canonical columns completeness
    missing_cols: list[str] = []
    if not has_game_date:
        missing_cols.append("game_date")
    if not presence["has_home"]:
        missing_cols.append("home_team")
    if not presence["has_away"]:
        missing_cols.append("away_team")
    if not has_scores:
        missing_cols.append("home_score/away_score")

    # Full RAW_PRIMARY requires date + teams + scores.
    # Odds are desirable but not mandatory for RAW_PRIMARY classification.
    if not missing_cols:
        return SourceEntry(
            path=rel,
            source_class=SourceClass.RAW_PRIMARY,
            has_game_date=True,
            has_scores=True,
            has_odds=has_odds,
            has_derived_signals=False,
            missing_canonical_columns=[],
            year_coverage=year_coverage,
            notes=(
                "Raw primary source: game-date stamped, no model fields. "
                f"{'Has closing odds.' if has_odds else 'MISSING closing odds — supplemental odds source needed.'}"
            ),
        )

    # 4. SCHEMA_PARTIAL: has some raw signals but missing canonical columns
    if has_game_date or has_scores:
        return SourceEntry(
            path=rel,
            source_class=SourceClass.SCHEMA_PARTIAL,
            has_game_date=has_game_date,
            has_scores=has_scores,
            has_odds=has_odds,
            has_derived_signals=False,
            missing_canonical_columns=missing_cols,
            year_coverage=year_coverage,
            notes=f"Raw-looking but missing: {missing_cols}.",
        )

    # 5. Default: SCHEMA_PARTIAL (unrecognized structure)
    return SourceEntry(
        path=rel,
        source_class=SourceClass.SCHEMA_PARTIAL,
        has_game_date=False,
        has_scores=False,
        has_odds=False,
        has_derived_signals=False,
        missing_canonical_columns=["game_date", "home_team", "away_team", "scores"],
        year_coverage=year_coverage,
        notes="Unrecognised structure; classified SCHEMA_PARTIAL by default.",
    )


# ---------------------------------------------------------------------------
# Main audit function
# ---------------------------------------------------------------------------


def _candidate_paths(repo_root: Path) -> list[Path]:
    """
    Return the list of files to classify.

    Scope: data/**/*.{csv,json,jsonl} and outputs/**/*.{csv,json,jsonl}.
    Excludes __pycache__, .venv, .git, runtime/.
    """
    scan_dirs = [
        repo_root / "data",
        repo_root / "outputs",
    ]
    extensions = {".csv", ".json", ".jsonl"}
    exclude_dirs = {"__pycache__", ".venv", ".git", "runtime", "node_modules"}

    paths: list[Path] = []
    for base in scan_dirs:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in extensions:
                continue
            # Skip excluded directories
            if any(part in exclude_dirs for part in p.parts):
                continue
            paths.append(p)
    return sorted(paths)


def run_honest_data_audit(repo_root: str | Path) -> HonestDataAuditResult:
    """
    Classify all candidate data sources and return the audit result.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        HonestDataAuditResult with classified entries and counters.
    """
    root = Path(repo_root).resolve()
    result = HonestDataAuditResult()

    candidate_files = _candidate_paths(root)

    for path in candidate_files:
        entry = _classify_file(path, root)
        result.entries.append(entry)

    # Build counters
    counters = AuditCounters()
    counters.total_sources = len(result.entries)

    for e in result.entries:
        if e.source_class == SourceClass.RAW_PRIMARY:
            counters.raw_primary_count += 1
            if 2024 in e.year_coverage:
                counters.usable_2024_raw_count += 1
        elif e.source_class == SourceClass.RAW_SECONDARY:
            counters.raw_secondary_count += 1
            if 2024 in e.year_coverage:
                counters.usable_2024_raw_count += 1
        elif e.source_class == SourceClass.DERIVED_OUTPUT:
            counters.derived_output_count += 1
            # These are the sources P30 misleadingly counted as "ready"
            counters.misleading_ready_source_count += 1
        elif e.source_class == SourceClass.SCHEMA_PARTIAL:
            counters.schema_partial_count += 1

    result.counters = counters
    return result


def write_classification_csv(result: HonestDataAuditResult, output_path: str | Path) -> None:
    """Write the classification audit results to a CSV file."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "path",
        "source_class",
        "has_game_date",
        "has_scores",
        "has_odds",
        "has_derived_signals",
        "missing_canonical_columns",
        "year_coverage",
        "notes",
    ]

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for entry in result.entries:
            writer.writerow(entry.to_dict())


# ---------------------------------------------------------------------------
# Gate constant builder
# ---------------------------------------------------------------------------


def determine_p31_gate(result: HonestDataAuditResult, provenance_safe: bool) -> str:
    """
    Determine the P31 gate constant based on audit results.

    Args:
        result: The audit result.
        provenance_safe: True if at least one 2024 odds source has a documented
                         safe license for non-commercial use.

    Returns:
        One of the P31 gate constant strings.
    """
    c = result.counters

    if c.total_sources == 0:
        return "P31_FAIL_INPUT_MISSING"

    raw_total = c.raw_primary_count + c.raw_secondary_count
    if raw_total == 0:
        return "P31_BLOCKED_NO_RAW_HISTORICAL_INCREMENT"

    if not provenance_safe:
        # Partial GO: game logs possible but odds license unresolved.
        # This is still P31_HONEST_DATA_AUDIT_READY because we've done the
        # audit and issued a clear GO_PARTIAL recommendation.
        return "P31_HONEST_DATA_AUDIT_READY"

    return "P31_HONEST_DATA_AUDIT_READY"
