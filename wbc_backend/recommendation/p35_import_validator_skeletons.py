"""P35 Import Validator Skeletons

Builds JSON validator specification files for both the odds and prediction
import paths defined in P34. These specs describe what validation rules
must be applied when actual data is provided in a later phase.

HARD GUARDS:
- PAPER_ONLY = True always.
- PRODUCTION_READY = False always.
- No actual data is validated here — only specs are written.
- No odds data is downloaded or read.
- No predictions are fabricated.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    ODDS_REQUIRED_COLUMNS,
    PAPER_ONLY,
    PREDICTION_REQUIRED_COLUMNS,
    PRODUCTION_READY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output file name constants
# ---------------------------------------------------------------------------

OUT_ODDS_VALIDATOR_SPEC = "odds_import_validator_spec.json"
OUT_PREDICTION_VALIDATOR_SPEC = "prediction_import_validator_spec.json"


# ---------------------------------------------------------------------------
# Spec builders
# ---------------------------------------------------------------------------


def build_odds_import_validator_spec() -> Dict[str, Any]:
    """Build the odds import validator specification.

    Defines all required fields, field-level rules, and global rules that
    must be enforced when validating a real odds import CSV.
    """
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"

    return {
        "spec_name": "odds_import_validator",
        "season": 2024,
        "paper_only": True,
        "production_ready": False,
        "source_type": "licensed_export",
        "required_columns": list(ODDS_REQUIRED_COLUMNS),
        "field_rules": {
            "game_id": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Must match P32 game_id spine exactly.",
            },
            "game_date": {
                "required": True,
                "nullable": False,
                "type": "date",
                "format": "YYYY-MM-DD",
                "description": "Game date; must be in 2024 MLB season (2024-03-20 to 2024-10-30).",
            },
            "home_team": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Home team abbreviation; must match P32 spine.",
            },
            "away_team": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Away team abbreviation; must match P32 spine.",
            },
            "p_market": {
                "required": True,
                "nullable": False,
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "description": "Market-implied home win probability; derived from odds_decimal. Range [0, 1].",
            },
            "odds_decimal": {
                "required": True,
                "nullable": False,
                "type": "float",
                "min_exclusive": 1.0,
                "description": "Closing home moneyline in decimal odds format. Must be > 1.0.",
            },
            "sportsbook": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Name of the sportsbook or archive source.",
            },
            "market_type": {
                "required": True,
                "nullable": False,
                "type": "string",
                "allowed_values": ["moneyline", "h2h"],
                "description": "Odds market type. Only moneyline/h2h is supported.",
            },
            "closing_timestamp": {
                "required": True,
                "nullable": False,
                "type": "datetime",
                "description": "Timestamp of closing odds; must be BEFORE game start.",
            },
            "source_odds_ref": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Reference to original data source (URL or archive name).",
            },
            "license_ref": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Reference to the approved license record. Must be non-empty.",
            },
        },
        "global_rules": {
            "no_production_ready": {
                "rule": "No row may be used for live betting or production output.",
                "enforcement": "paper_only=True must be present in pipeline config.",
            },
            "no_outcome_derived_odds": {
                "rule": "Odds must never be inferred from game outcomes (y_true).",
                "enforcement": "Provenance audit must confirm odds source predates game.",
            },
            "no_scraping": {
                "rule": "Odds must be downloaded manually; scraping is forbidden.",
                "enforcement": "acquisition_method must be 'manual_download'.",
            },
            "game_id_spine_match": {
                "rule": "Every game_id in odds import must match a P32 game_id.",
                "enforcement": "Left-join on P32 game_identity; no unmatched rows allowed.",
            },
            "closing_before_game_start": {
                "rule": "closing_timestamp must be before the game start time.",
                "enforcement": "Validated by timestamp comparison against P32 game_date.",
            },
            "season_2024_only": {
                "rule": "Only 2024 MLB season data is permitted.",
                "enforcement": "game_date year must be 2024.",
            },
            "license_ref_required": {
                "rule": "Every row must have a non-empty license_ref.",
                "enforcement": "Validated during import; rows without license_ref are rejected.",
            },
        },
    }


def build_prediction_import_validator_spec() -> Dict[str, Any]:
    """Build the prediction import validator specification.

    Defines all required fields, field-level rules, and global rules that
    must be enforced when validating a real prediction import CSV.
    """
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"

    return {
        "spec_name": "prediction_import_validator",
        "season": 2024,
        "paper_only": True,
        "production_ready": False,
        "source_type": "oof_rebuild",
        "required_columns": list(PREDICTION_REQUIRED_COLUMNS),
        "field_rules": {
            "game_id": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Must match P32 game_id spine exactly.",
            },
            "game_date": {
                "required": True,
                "nullable": False,
                "type": "date",
                "format": "YYYY-MM-DD",
                "description": "Game date; must be in 2024 MLB season.",
            },
            "home_team": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Home team abbreviation; must match P32 spine.",
            },
            "away_team": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Away team abbreviation; must match P32 spine.",
            },
            "p_oof": {
                "required": True,
                "nullable": False,
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "description": (
                    "Out-of-fold model probability for home team win. "
                    "Must be in [0, 1]. NEVER derived from y_true."
                ),
            },
            "model_version": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Model identifier and version string.",
            },
            "fold_id": {
                "required": True,
                "nullable": False,
                "type": "integer",
                "min": 0,
                "description": "Walk-forward fold index; must be >= 0.",
            },
            "source_prediction_ref": {
                "required": True,
                "nullable": False,
                "type": "string",
                "description": "Reference to prediction generation script and run ID.",
            },
            "generated_without_y_true": {
                "required": True,
                "nullable": False,
                "type": "boolean",
                "must_be_true": True,
                "description": (
                    "Flag certifying p_oof was generated without access to y_true. "
                    "Must be True for EVERY row — no exceptions."
                ),
            },
        },
        "global_rules": {
            "no_production_ready": {
                "rule": "No prediction row may be used for live betting.",
                "enforcement": "paper_only=True must be present in pipeline config.",
            },
            "no_y_true_derived_predictions": {
                "rule": "p_oof must NEVER be derived from y_true / home_win / outcome.",
                "enforcement": (
                    "generated_without_y_true must be True for all rows. "
                    "Provenance audit required before use."
                ),
            },
            "game_id_spine_match": {
                "rule": "Every game_id in prediction import must match a P32 game_id.",
                "enforcement": "Left-join on P32 game_identity; no unmatched rows allowed.",
            },
            "oof_temporal_integrity": {
                "rule": "p_oof for game G must be generated using only data from games before G.",
                "enforcement": "Walk-forward split must be verified; training cutoff < game_date.",
            },
            "p_oof_range": {
                "rule": "p_oof must be in [0.0, 1.0] inclusive for all rows.",
                "enforcement": "Validated during import; out-of-range values rejected.",
            },
            "season_2024_only": {
                "rule": "Only 2024 MLB season predictions are permitted.",
                "enforcement": "game_date year must be 2024.",
            },
        },
    }


# ---------------------------------------------------------------------------
# Writer and validator
# ---------------------------------------------------------------------------


def write_validator_specs(output_dir: str) -> List[str]:
    """Write both validator spec JSON files to output_dir.

    Parameters
    ----------
    output_dir:
        Directory to write specs into. Created if missing.

    Returns
    -------
    List of written file paths.
    """
    if not PAPER_ONLY:
        raise RuntimeError("PAPER_ONLY must be True; refusing to write specs.")
    if PRODUCTION_READY:
        raise RuntimeError("PRODUCTION_READY must be False; refusing to write specs.")

    os.makedirs(output_dir, exist_ok=True)

    odds_spec = build_odds_import_validator_spec()
    prediction_spec = build_prediction_import_validator_spec()

    generated_at = datetime.now(timezone.utc).isoformat()

    written: List[str] = []

    for fname, spec in (
        (OUT_ODDS_VALIDATOR_SPEC, odds_spec),
        (OUT_PREDICTION_VALIDATOR_SPEC, prediction_spec),
    ):
        spec["generated_at"] = generated_at
        out_path = os.path.join(output_dir, fname)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh, indent=2, ensure_ascii=False)
        written.append(out_path)
        logger.info("Wrote %s", out_path)

    return written


def validate_validator_specs(output_dir: str) -> bool:
    """Validate that both spec files were written correctly.

    Returns True if both files exist, are valid JSON, and contain
    all required top-level fields.
    """
    required_top_keys = {
        "spec_name",
        "season",
        "paper_only",
        "production_ready",
        "required_columns",
        "field_rules",
        "global_rules",
    }

    for fname in (OUT_ODDS_VALIDATOR_SPEC, OUT_PREDICTION_VALIDATOR_SPEC):
        path = os.path.join(output_dir, fname)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            logger.warning("Missing or empty spec file: %s", path)
            return False
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not parse spec file %s: %s", path, exc)
            return False
        missing_keys = required_top_keys - set(data.keys())
        if missing_keys:
            logger.warning("Spec %s missing keys: %s", fname, missing_keys)
            return False
        if data.get("paper_only") is not True:
            logger.warning("Spec %s has paper_only != True", fname)
            return False
        if data.get("production_ready") is not False:
            logger.warning("Spec %s has production_ready != False", fname)
            return False

    return True
