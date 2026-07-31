"""
wbc_backend/recommendation/p30_required_artifact_spec_generator.py

P30 Required Artifact Spec Generator.

Defines the required artifacts for a target historical season and maps
existing sources to those requirements, identifying schema gaps.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wbc_backend.recommendation.p30_source_acquisition_contract import (
    ARTIFACT_GAME_IDENTITY,
    ARTIFACT_GAME_OUTCOMES,
    ARTIFACT_MARKET_ODDS,
    ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
    ARTIFACT_PAPER_REPLAY_OUTPUT,
    ARTIFACT_TRUE_DATE_JOINED_INPUT,
    ARTIFACT_TRUE_DATE_SLICE_OUTPUT,
    P30RequiredArtifactSpec,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required column definitions per artifact type
# ---------------------------------------------------------------------------

_ARTIFACT_REQUIRED_COLUMNS: Dict[str, List[str]] = {
    ARTIFACT_GAME_IDENTITY: ["game_id", "game_date", "home_team", "away_team"],
    ARTIFACT_GAME_OUTCOMES: ["game_id", "y_true"],
    ARTIFACT_MODEL_PREDICTIONS_OR_OOF: ["game_id", "game_date", "p_model"],
    ARTIFACT_MARKET_ODDS: ["game_id", "p_market", "odds_decimal"],
    ARTIFACT_TRUE_DATE_JOINED_INPUT: [
        "game_id", "game_date", "y_true", "p_model", "p_market", "odds_decimal",
        "home_team", "away_team",
    ],
    ARTIFACT_TRUE_DATE_SLICE_OUTPUT: [
        "game_id", "game_date", "y_true", "p_model", "p_market", "odds_decimal",
        "edge", "gate_reason", "paper_stake_units", "paper_only", "production_ready",
    ],
    ARTIFACT_PAPER_REPLAY_OUTPUT: [
        "game_id", "game_date", "y_true", "p_model", "p_market", "odds_decimal",
        "edge", "pnl_units", "roi", "is_win", "is_loss", "paper_only", "production_ready",
    ],
}

# Accepted aliases for each canonical column name
_COLUMN_ALIASES: Dict[str, List[str]] = {
    "game_id": ["gameid", "game_pk", "gamepk", "id"],
    "game_date": ["date", "Date", "game_dt"],
    "home_team": ["Home", "home", "home_name", "home_team_name"],
    "away_team": ["Away", "away", "away_name", "away_team_name"],
    "y_true": ["outcome", "result", "winner", "Away Score", "Home Score"],
    "p_model": ["p_oof", "model_prob", "pred_prob", "win_prob", "home_win_prob"],
    "p_market": ["market_prob", "implied_prob", "Away ML", "Home ML"],
    "odds_decimal": ["decimal_odds", "Away ML", "Home ML", "ml_away", "ml_home"],
    "edge": ["edge_vs_market"],
    "gate_reason": ["decision_reason", "gate_decision"],
    "paper_stake_units": ["stake_units", "paper_stake"],
    "paper_only": [],
    "production_ready": [],
    "pnl_units": ["pnl", "profit_loss"],
    "roi": ["return_on_investment"],
    "is_win": ["win", "won"],
    "is_loss": ["loss", "lost"],
}


def _get_aliases_json(required_columns: List[str]) -> str:
    """Build JSON string of accepted aliases for a list of required columns."""
    aliases = {}
    for col in required_columns:
        col_aliases = _COLUMN_ALIASES.get(col, [])
        if col_aliases:
            aliases[col] = col_aliases
    return json.dumps(aliases, ensure_ascii=False)


def _check_column_present(col: str, available_columns: List[str]) -> bool:
    """Check if canonical column or any alias is in available_columns."""
    available_lower = {c.lower().strip() for c in available_columns}
    if col.lower() in available_lower:
        return True
    for alias in _COLUMN_ALIASES.get(col, []):
        if alias.lower() in available_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_required_artifact_specs(target_season: str) -> List[P30RequiredArtifactSpec]:
    """
    Build the full list of required artifact specs for the given target season.
    Returns specs with coverage_status=MISSING (no existing sources mapped yet).
    """
    specs = []
    for artifact_type, required_cols in _ARTIFACT_REQUIRED_COLUMNS.items():
        spec = P30RequiredArtifactSpec(
            artifact_type=artifact_type,
            target_season=target_season,
            required_columns=", ".join(required_cols),
            accepted_aliases=_get_aliases_json(required_cols),
            is_present_in_existing_source=False,
            coverage_status="MISSING",
            missing_columns=", ".join(required_cols),
            schema_gap_note=f"No source mapped for artifact type {artifact_type}.",
            paper_only=True,
            production_ready=False,
        )
        specs.append(spec)
    return specs


def validate_required_artifact_specs(specs: List[P30RequiredArtifactSpec]) -> bool:
    """Validate that specs cover all required artifact types. Raises on error."""
    required_types = set(_ARTIFACT_REQUIRED_COLUMNS.keys())
    spec_types = {s.artifact_type for s in specs}
    missing_types = required_types - spec_types
    if missing_types:
        raise ValueError(f"Missing artifact spec types: {missing_types}")
    for spec in specs:
        if spec.coverage_status not in ("FULL", "PARTIAL", "MISSING"):
            raise ValueError(f"Invalid coverage_status '{spec.coverage_status}' for {spec.artifact_type}")
    return True


def map_existing_sources_to_specs(
    inventory: List[Dict[str, Any]],
    specs: List[P30RequiredArtifactSpec],
) -> List[P30RequiredArtifactSpec]:
    """
    Map existing source candidates to artifact specs.
    Returns updated specs with coverage_status filled in.
    """
    # Collect all available columns across inventory candidates
    all_available_columns: List[str] = []
    for candidate in inventory:
        cols = candidate.get("columns", [])
        if isinstance(cols, list):
            all_available_columns.extend(cols)
    # Also include inferred columns from has_* flags
    has_flags: Dict[str, bool] = {}
    for candidate in inventory:
        for key in ["has_game_id", "has_game_date", "has_y_true", "has_home_away_teams",
                    "has_p_model", "has_p_market", "has_odds_decimal"]:
            if candidate.get(key, False):
                has_flags[key] = True

    # Synthesize available canonical columns from flags (canonical names only —
    # do NOT include raw aliases to prevent false positive alias matching).
    flag_to_cols: Dict[str, List[str]] = {
        "has_game_id": ["game_id"],
        "has_game_date": ["game_date"],
        "has_y_true": ["y_true"],
        "has_home_away_teams": ["home_team", "away_team"],
        "has_p_model": ["p_model"],
        "has_p_market": ["p_market"],
        "has_odds_decimal": ["odds_decimal"],
    }
    for flag, cols in flag_to_cols.items():
        if has_flags.get(flag):
            all_available_columns.extend(cols)

    updated_specs: List[P30RequiredArtifactSpec] = []
    for spec in specs:
        required_cols = [c.strip() for c in spec.required_columns.split(",")]
        present = [c for c in required_cols if _check_column_present(c, all_available_columns)]
        missing = [c for c in required_cols if not _check_column_present(c, all_available_columns)]

        if not missing:
            coverage_status = "FULL"
            is_present = True
            note = "All required columns available in existing sources."
        elif present:
            coverage_status = "PARTIAL"
            is_present = True
            note = f"Partial coverage: missing columns: {', '.join(missing)}"
        else:
            coverage_status = "MISSING"
            is_present = False
            note = f"No coverage: all required columns absent: {', '.join(required_cols)}"

        updated = P30RequiredArtifactSpec(
            artifact_type=spec.artifact_type,
            target_season=spec.target_season,
            required_columns=spec.required_columns,
            accepted_aliases=spec.accepted_aliases,
            is_present_in_existing_source=is_present,
            coverage_status=coverage_status,
            missing_columns=", ".join(missing),
            schema_gap_note=note,
            paper_only=True,
            production_ready=False,
        )
        updated_specs.append(updated)

    return updated_specs


def identify_schema_gaps(
    mapped_specs: List[P30RequiredArtifactSpec],
) -> Dict[str, Any]:
    """
    Identify schema gaps across all mapped artifact specs.
    Returns a summary dict describing what is missing.
    """
    total = len(mapped_specs)
    full = [s for s in mapped_specs if s.coverage_status == "FULL"]
    partial = [s for s in mapped_specs if s.coverage_status == "PARTIAL"]
    missing = [s for s in mapped_specs if s.coverage_status == "MISSING"]

    all_missing_cols: List[str] = []
    for s in partial + missing:
        cols = [c.strip() for c in s.missing_columns.split(",") if c.strip()]
        all_missing_cols.extend(cols)

    # A spec is critically missing if it is MISSING or PARTIAL for a critical
    # artifact type (partial coverage means key columns like p_model are absent).
    _critical_artifact_types = (
        ARTIFACT_GAME_OUTCOMES,
        ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
        ARTIFACT_TRUE_DATE_JOINED_INPUT,
        ARTIFACT_TRUE_DATE_SLICE_OUTPUT,
    )
    critical_missing = [
        s.artifact_type for s in mapped_specs
        if s.coverage_status in ("MISSING", "PARTIAL")
        and s.artifact_type in _critical_artifact_types
    ]

    return {
        "total_specs": total,
        "n_full_coverage": len(full),
        "n_partial_coverage": len(partial),
        "n_missing_coverage": len(missing),
        "schema_gap_count": len(partial) + len(missing),
        "critical_missing_artifacts": critical_missing,
        "all_missing_columns": sorted(set(all_missing_cols)),
        "gap_details": [
            {
                "artifact_type": s.artifact_type,
                "coverage_status": s.coverage_status,
                "missing_columns": s.missing_columns,
                "note": s.schema_gap_note,
            }
            for s in partial + missing
        ],
        "has_critical_gaps": len(critical_missing) > 0,
        "recommendation": (
            "Critical artifact gaps prevent P25/P26 pipeline replay. "
            "Acquire missing columns (model predictions, market odds with decimals) before P31."
            if critical_missing
            else "Minor schema gaps. Adapter or join may resolve missing fields."
        ),
    }


def write_artifact_spec_docs(
    output_dir: Path,
    specs: List[P30RequiredArtifactSpec],
    schema_gaps: Dict[str, Any],
    target_season: str,
) -> None:
    """Write artifact spec JSON and schema gap report to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    import json as _json

    specs_data = [
        {
            "artifact_type": s.artifact_type,
            "target_season": s.target_season,
            "required_columns": s.required_columns,
            "coverage_status": s.coverage_status,
            "missing_columns": s.missing_columns,
            "schema_gap_note": s.schema_gap_note,
            "paper_only": s.paper_only,
            "production_ready": s.production_ready,
        }
        for s in specs
    ]

    spec_path = output_dir / "required_artifact_specs.json"
    with open(spec_path, "w", encoding="utf-8") as fh:
        _json.dump(
            {"target_season": target_season, "specs": specs_data},
            fh,
            indent=2,
            ensure_ascii=False,
        )

    gap_path = output_dir / "schema_gap_report.json"
    with open(gap_path, "w", encoding="utf-8") as fh:
        _json.dump(schema_gaps, fh, indent=2, ensure_ascii=False)

    logger.info("Artifact spec docs written to %s", output_dir)
