"""
P34 Joined Input Schema Package
=================================
Builds and writes the schema templates and validation rules for the P34
dual-source acquisition plan.

PAPER_ONLY=True  PRODUCTION_READY=False
No fake data. Templates are header-only structures, never populated with fabricated values.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    ODDS_TEMPLATE_COLUMNS,
    PAPER_ONLY,
    PREDICTION_TEMPLATE_COLUMNS,
    PRODUCTION_READY,
    P34SchemaRequirement,
)

# ---------------------------------------------------------------------------
# Output file constants
# ---------------------------------------------------------------------------

OUT_PREDICTION_TEMPLATE = "prediction_import_template.csv"
OUT_ODDS_TEMPLATE = "odds_import_template.csv"
OUT_VALIDATION_RULES = "joined_input_validation_rules.json"


def build_prediction_schema_template() -> P34SchemaRequirement:
    """Return the schema requirement object for the 2024 prediction import template."""
    return P34SchemaRequirement(
        season=2024,
        prediction_columns=PREDICTION_TEMPLATE_COLUMNS,
        odds_columns=(),
        paper_only=True,
        production_ready=False,
    )


def build_odds_schema_template() -> P34SchemaRequirement:
    """Return the schema requirement object for the 2024 odds import template."""
    return P34SchemaRequirement(
        season=2024,
        prediction_columns=(),
        odds_columns=ODDS_TEMPLATE_COLUMNS,
        paper_only=True,
        production_ready=False,
    )


def build_joined_input_validation_rules() -> Dict:
    """
    Build a JSON-serializable dict of all validation rules required for the
    2024 joined input. These rules must be satisfied before the joined input
    can be certified as P35-ready.

    HARD RULES enforced:
    - game_id required
    - game_date required
    - 0 <= p_oof <= 1
    - 0 <= p_market <= 1
    - odds_decimal > 1
    - no y_true-derived prediction
    - odds license required
    - no production_ready
    """
    return {
        "season": 2024,
        "paper_only": True,
        "production_ready": False,
        "description": (
            "Validation rules for the P35 2024 joined input. "
            "All rules must pass before the joined input is certified."
        ),
        "required_fields": {
            "prediction": list(PREDICTION_TEMPLATE_COLUMNS),
            "odds": list(ODDS_TEMPLATE_COLUMNS),
        },
        "field_rules": [
            {
                "field": "game_id",
                "rule": "required",
                "description": "game_id must be present and non-null for every row.",
            },
            {
                "field": "game_date",
                "rule": "required",
                "description": "game_date must be present and parseable as a date.",
            },
            {
                "field": "p_oof",
                "rule": "range_inclusive",
                "min": 0.0,
                "max": 1.0,
                "description": "p_oof must be a calibrated probability in [0, 1].",
            },
            {
                "field": "p_market",
                "rule": "range_inclusive",
                "min": 0.0,
                "max": 1.0,
                "description": "p_market must be an implied probability in [0, 1].",
            },
            {
                "field": "odds_decimal",
                "rule": "range_exclusive_min",
                "min": 1.0,
                "description": "odds_decimal must be > 1.0 (valid decimal odds).",
            },
            {
                "field": "generated_without_y_true",
                "rule": "must_be_true",
                "description": (
                    "generated_without_y_true must be True for every prediction row. "
                    "Predictions inferred from y_true are FORBIDDEN."
                ),
            },
            {
                "field": "license_ref",
                "rule": "required_non_empty",
                "description": (
                    "license_ref must be populated for every odds row. "
                    "Unlicensed odds are rejected."
                ),
            },
            {
                "field": "source_odds_ref",
                "rule": "required_non_empty",
                "description": "source_odds_ref must identify the provenance of each odds row.",
            },
            {
                "field": "source_prediction_ref",
                "rule": "required_non_empty",
                "description": "source_prediction_ref must identify the model/version used.",
            },
        ],
        "global_rules": [
            {
                "rule": "no_production_ready",
                "description": (
                    "production_ready must be False. The 2024 joined input is research-only."
                ),
            },
            {
                "rule": "no_outcome_derived_odds",
                "description": (
                    "Odds must NOT be reverse-engineered from game outcomes (y_true, scores, etc.)."
                ),
            },
            {
                "rule": "no_y_true_derived_predictions",
                "description": (
                    "Predictions (p_oof, p_model) must NOT be derived from final game scores "
                    "or y_true labels."
                ),
            },
            {
                "rule": "game_id_spine_match",
                "description": (
                    "Every game_id in prediction and odds templates must match "
                    "the P32 game identity spine (mlb_2024_game_identity.csv)."
                ),
            },
            {
                "rule": "season_2024_only",
                "description": "Only 2024 MLB regular-season games are permitted.",
            },
        ],
    }


def write_schema_templates(output_dir: str) -> List[str]:
    """
    Write prediction and odds import templates (header-only CSVs) and the
    validation rules JSON to output_dir.

    Returns list of written file paths.
    """
    if not PAPER_ONLY:
        raise RuntimeError("Schema package must run with PAPER_ONLY=True.")

    os.makedirs(output_dir, exist_ok=True)
    written: List[str] = []

    # --- Prediction import template ---
    pred_path = os.path.join(output_dir, OUT_PREDICTION_TEMPLATE)
    with open(pred_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(PREDICTION_TEMPLATE_COLUMNS))
    written.append(pred_path)

    # --- Odds import template ---
    odds_path = os.path.join(output_dir, OUT_ODDS_TEMPLATE)
    with open(odds_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(ODDS_TEMPLATE_COLUMNS))
    written.append(odds_path)

    # --- Validation rules JSON ---
    rules = build_joined_input_validation_rules()
    rules_path = os.path.join(output_dir, OUT_VALIDATION_RULES)
    with open(rules_path, "w", encoding="utf-8") as fh:
        json.dump(rules, fh, indent=2)
    written.append(rules_path)

    return written


def validate_schema_templates(output_dir: str) -> bool:
    """
    Verify that all three expected schema output files exist and are non-empty.
    Returns True if all present and valid, False otherwise.
    """
    expected = [OUT_PREDICTION_TEMPLATE, OUT_ODDS_TEMPLATE, OUT_VALIDATION_RULES]
    for fname in expected:
        fpath = os.path.join(output_dir, fname)
        if not os.path.isfile(fpath):
            return False
        if os.path.getsize(fpath) == 0:
            return False
    # Verify prediction template has correct header
    pred_path = os.path.join(output_dir, OUT_PREDICTION_TEMPLATE)
    with open(pred_path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
    if header != list(PREDICTION_TEMPLATE_COLUMNS):
        return False
    # Verify odds template has correct header
    odds_path = os.path.join(output_dir, OUT_ODDS_TEMPLATE)
    with open(odds_path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
    if header != list(ODDS_TEMPLATE_COLUMNS):
        return False
    # Verify validation rules JSON is parseable
    rules_path = os.path.join(output_dir, OUT_VALIDATION_RULES)
    try:
        with open(rules_path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return False
    except (json.JSONDecodeError, OSError):
        return False
    return True
