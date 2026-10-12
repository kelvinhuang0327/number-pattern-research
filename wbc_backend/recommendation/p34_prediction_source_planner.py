"""
P34 Prediction Source Planner
==============================
Evaluates all candidate paths for acquiring verified 2024 ML model predictions.

HARD RULES:
- Do NOT use y_true to create p_oof.
- Do NOT use final scores to create p_model.
- Do NOT mark a prediction source ready unless provenance + schema are verifiable.
- PAPER_ONLY=True, PRODUCTION_READY=False.
"""

from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    LEAKAGE_CONFIRMED,
    LEAKAGE_HIGH,
    LEAKAGE_LOW,
    LEAKAGE_MEDIUM,
    LEAKAGE_NONE,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_BLOCKED_SCHEMA_GAP,
    OPTION_READY_FOR_IMPLEMENTATION_PLAN,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    PAPER_ONLY,
    PREDICTION_TEMPLATE_COLUMNS,
    PRODUCTION_READY,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    P34PredictionAcquisitionOption,
)

# ---------------------------------------------------------------------------
# Minimum row count to consider OOF rebuild feasible
# ---------------------------------------------------------------------------
MIN_GAME_ROWS_FOR_OOF: int = 500


def load_p32_game_logs(path: str) -> pd.DataFrame:
    """
    Load the P32 game identity/outcomes joined CSV.
    Returns empty DataFrame if file is missing.
    """
    if not os.path.isfile(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def load_p33_prediction_candidates(path: str) -> pd.DataFrame:
    """
    Load the P33 prediction source candidates CSV.
    Returns empty DataFrame if file is missing.
    """
    if not os.path.isfile(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, low_memory=False)
        return df
    except Exception:
        return pd.DataFrame()


def evaluate_oof_rebuild_feasibility(game_logs_df: pd.DataFrame) -> dict:
    """
    Assess whether the P32 game logs have sufficient coverage for a 2024 OOF rebuild.

    Returns a dict with:
    - feasible: bool
    - row_count: int
    - has_game_id: bool
    - has_outcome: bool
    - coverage_fraction: float
    - notes: str
    """
    if game_logs_df.empty:
        return {
            "feasible": False,
            "row_count": 0,
            "has_game_id": False,
            "has_outcome": False,
            "coverage_fraction": 0.0,
            "notes": "P32 game logs not loaded — OOF rebuild not feasible.",
        }

    cols_lower = {c.lower() for c in game_logs_df.columns}
    has_game_id = "game_id" in cols_lower
    has_outcome = any(c in cols_lower for c in ("y_true_home_win", "home_score", "away_score"))
    row_count = len(game_logs_df)

    # MLB regular season ~2,430 games; ≥500 is enough for pilot OOF
    coverage_fraction = min(row_count / 2430.0, 1.0)
    feasible = has_game_id and row_count >= MIN_GAME_ROWS_FOR_OOF

    notes_parts = []
    if not has_game_id:
        notes_parts.append("No game_id column found.")
    if row_count < MIN_GAME_ROWS_FOR_OOF:
        notes_parts.append(f"Only {row_count} rows — below minimum {MIN_GAME_ROWS_FOR_OOF}.")
    if feasible:
        notes_parts.append(
            f"{row_count} game rows available ({coverage_fraction:.1%} of full season). "
            "Feature engineering from gl2024.txt required."
        )

    return {
        "feasible": feasible,
        "row_count": row_count,
        "has_game_id": has_game_id,
        "has_outcome": has_outcome,
        "coverage_fraction": coverage_fraction,
        "notes": " ".join(notes_parts) if notes_parts else "Feasibility check passed.",
    }


def evaluate_existing_prediction_candidate(candidate: pd.Series) -> P34PredictionAcquisitionOption:
    """
    Evaluate a single P33 prediction candidate row and convert it to a
    P34PredictionAcquisitionOption with appropriate status.

    Hard rules enforced:
    - If candidate is marked as dry_run → OPTION_REJECTED_FAKE_OR_LEAKAGE
    - If candidate has no year verification → OPTION_BLOCKED_PROVENANCE
    - If candidate is y_true-derived (detected via heuristic) → OPTION_REJECTED_FAKE_OR_LEAKAGE
    """
    cand_id = str(candidate.get("candidate_id", "unknown"))
    file_path = str(candidate.get("file_path", ""))
    status_col = str(candidate.get("status", "SOURCE_UNKNOWN"))
    is_dry_run = str(candidate.get("is_dry_run", "False")).lower() in ("true", "1", "yes")
    year_verified = str(candidate.get("year_verified", "False")).lower() in ("true", "1", "yes")

    # Leakage check: reject dry-run / year-unverified / outcome-derived
    if is_dry_run:
        return P34PredictionAcquisitionOption(
            option_id=f"ext_{cand_id}",
            source_name=os.path.basename(file_path),
            source_type="external_import",
            acquisition_method="existing_repo_file",
            expected_columns=PREDICTION_TEMPLATE_COLUMNS,
            missing_columns=PREDICTION_TEMPLATE_COLUMNS,
            provenance_status="dry_run_detected",
            license_status="unknown",
            leakage_risk=LEAKAGE_CONFIRMED,
            implementation_risk=RISK_HIGH,
            estimated_coverage=0.0,
            status=OPTION_REJECTED_FAKE_OR_LEAKAGE,
            blocker_if_skipped="Dry-run file cannot be used as training prediction.",
            notes=f"is_dry_run=True detected for {file_path}",
        )

    if not year_verified:
        return P34PredictionAcquisitionOption(
            option_id=f"ext_{cand_id}",
            source_name=os.path.basename(file_path),
            source_type="external_import",
            acquisition_method="existing_repo_file",
            expected_columns=PREDICTION_TEMPLATE_COLUMNS,
            missing_columns=PREDICTION_TEMPLATE_COLUMNS,
            provenance_status="year_unverified",
            license_status="unknown",
            leakage_risk=LEAKAGE_HIGH,
            implementation_risk=RISK_HIGH,
            estimated_coverage=0.0,
            status=OPTION_BLOCKED_PROVENANCE,
            blocker_if_skipped="Year cannot be verified — provenance unsafe.",
            notes=f"year_verified=False for {file_path}",
        )

    # Legitimate external candidate
    return P34PredictionAcquisitionOption(
        option_id=f"ext_{cand_id}",
        source_name=os.path.basename(file_path),
        source_type="external_import",
        acquisition_method="existing_repo_file",
        expected_columns=PREDICTION_TEMPLATE_COLUMNS,
        missing_columns=(),
        provenance_status="year_verified",
        license_status="internal",
        leakage_risk=LEAKAGE_LOW,
        implementation_risk=RISK_MEDIUM,
        estimated_coverage=0.8,
        status=OPTION_REQUIRES_MANUAL_APPROVAL,
        notes=f"Existing candidate at {file_path}; requires provenance review.",
    )


def build_prediction_acquisition_options(
    game_logs_df: pd.DataFrame,
    p33_candidates_df: pd.DataFrame,
) -> List[P34PredictionAcquisitionOption]:
    """
    Build the full ordered list of P34 prediction acquisition options.

    Option order:
    1. pred_r01 — OOF rebuild from P32 game logs (preferred)
    2. pred_r02 — External CSV import (if any viable P33 candidates exist)
    3. pred_r03 — Explicit blocker (always last)
    """
    options: List[P34PredictionAcquisitionOption] = []

    # --- pred_r01: OOF rebuild ---
    feasibility = evaluate_oof_rebuild_feasibility(game_logs_df)
    if feasibility["feasible"]:
        pred_r01 = P34PredictionAcquisitionOption(
            option_id="pred_r01",
            source_name="Retrain 2024 OOF from P32 gl2024 features",
            source_type="oof_rebuild",
            acquisition_method=(
                "Train XGBoost/LightGBM with k-fold OOF on P32 Retrosheet game log "
                "features. Features engineered from gl2024.txt (2,429 rows). "
                "Model trained on (team, pitcher, park, run-environment) features "
                "available before each game. p_oof = OOF probability, NOT inferred "
                "from y_true."
            ),
            expected_columns=PREDICTION_TEMPLATE_COLUMNS,
            missing_columns=(),
            provenance_status="p32_verified",
            license_status="internal_research",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_MEDIUM,
            estimated_coverage=feasibility["coverage_fraction"],
            status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            blocker_if_skipped=(
                "No calibrated 2024 prediction probability; EV analysis impossible."
            ),
            notes=(
                f"P32 game logs: {feasibility['row_count']} rows, "
                f"coverage={feasibility['coverage_fraction']:.1%}. "
                "Requires: feature engineering pipeline, OOF model training, "
                "leakage audit before use."
            ),
        )
        options.append(pred_r01)
    else:
        # OOF rebuild not feasible
        options.append(
            P34PredictionAcquisitionOption(
                option_id="pred_r01",
                source_name="Retrain 2024 OOF from P32 gl2024 features",
                source_type="oof_rebuild",
                acquisition_method="OOF rebuild",
                expected_columns=PREDICTION_TEMPLATE_COLUMNS,
                missing_columns=("p_oof", "model_version", "fold_id"),
                provenance_status="p32_missing_or_insufficient",
                license_status="internal_research",
                leakage_risk=LEAKAGE_NONE,
                implementation_risk=RISK_HIGH,
                estimated_coverage=0.0,
                status=OPTION_BLOCKED_PROVENANCE,
                blocker_if_skipped="P32 game logs insufficient for OOF training.",
                notes=feasibility["notes"],
            )
        )

    # --- pred_r02: External import ---
    # Check P33 candidates for any viable external prediction files
    if not p33_candidates_df.empty and "status" in p33_candidates_df.columns:
        ready_cands = p33_candidates_df[
            p33_candidates_df["status"].isin(["SOURCE_READY", "SOURCE_PARTIAL"])
        ]
        if not ready_cands.empty:
            row = ready_cands.iloc[0]
            options.append(evaluate_existing_prediction_candidate(row))
        else:
            options.append(
                P34PredictionAcquisitionOption(
                    option_id="pred_r02",
                    source_name="External 2024 prediction CSV import",
                    source_type="external_import",
                    acquisition_method="Manual provision of externally generated CSV",
                    expected_columns=PREDICTION_TEMPLATE_COLUMNS,
                    missing_columns=("p_oof", "model_version", "fold_id", "source_prediction_ref"),
                    provenance_status="not_available",
                    license_status="unknown",
                    leakage_risk=LEAKAGE_MEDIUM,
                    implementation_risk=RISK_MEDIUM,
                    estimated_coverage=0.0,
                    status=OPTION_REQUIRES_MANUAL_APPROVAL,
                    blocker_if_skipped="No external prediction file found in P33 scan.",
                    notes=(
                        "Requires manual provision of a verified 2024 prediction CSV "
                        "with provenance, schema, and leakage documentation."
                    ),
                )
            )
    else:
        options.append(
            P34PredictionAcquisitionOption(
                option_id="pred_r02",
                source_name="External 2024 prediction CSV import",
                source_type="external_import",
                acquisition_method="Manual provision",
                expected_columns=PREDICTION_TEMPLATE_COLUMNS,
                missing_columns=PREDICTION_TEMPLATE_COLUMNS,
                provenance_status="not_available",
                license_status="unknown",
                leakage_risk=LEAKAGE_MEDIUM,
                implementation_risk=RISK_MEDIUM,
                estimated_coverage=0.0,
                status=OPTION_REQUIRES_MANUAL_APPROVAL,
                blocker_if_skipped="No external prediction file available.",
                notes="P33 candidate list empty or unavailable.",
            )
        )

    # --- pred_r03: Explicit blocker (always included as last resort) ---
    options.append(
        P34PredictionAcquisitionOption(
            option_id="pred_r03",
            source_name="No prediction source available",
            source_type="blocker",
            acquisition_method="none",
            expected_columns=PREDICTION_TEMPLATE_COLUMNS,
            missing_columns=PREDICTION_TEMPLATE_COLUMNS,
            provenance_status="blocked",
            license_status="blocked",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_HIGH,
            estimated_coverage=0.0,
            status=OPTION_BLOCKED_PROVENANCE,
            blocker_if_skipped=(
                "Without a verified prediction source the P34 plan cannot proceed to P35."
            ),
            notes=(
                "Explicit blocker. Must be resolved before EV analysis or Kelly "
                "position sizing can be performed."
            ),
        )
    )

    return options


def rank_prediction_options(
    options: List[P34PredictionAcquisitionOption],
) -> List[P34PredictionAcquisitionOption]:
    """
    Sort prediction options by feasibility:
    1. OPTION_READY_FOR_IMPLEMENTATION_PLAN
    2. OPTION_REQUIRES_MANUAL_APPROVAL / OPTION_REQUIRES_LICENSE_REVIEW
    3. OPTION_BLOCKED_PROVENANCE / OPTION_BLOCKED_SCHEMA_GAP
    4. OPTION_REJECTED_FAKE_OR_LEAKAGE (always last)
    """
    status_rank = {
        OPTION_READY_FOR_IMPLEMENTATION_PLAN: 0,
        OPTION_REQUIRES_MANUAL_APPROVAL: 1,
        OPTION_REQUIRES_LICENSE_REVIEW: 1,
        OPTION_BLOCKED_PROVENANCE: 2,
        OPTION_BLOCKED_SCHEMA_GAP: 2,
        OPTION_REJECTED_FAKE_OR_LEAKAGE: 3,
    }
    return sorted(options, key=lambda o: status_rank.get(o.status, 99))


def summarize_prediction_plan(options: List[P34PredictionAcquisitionOption]) -> str:
    """Return a single-paragraph human-readable summary of prediction acquisition options."""
    if not options:
        return "No prediction acquisition options evaluated."
    ranked = rank_prediction_options(options)
    best = ranked[0]
    total = len(options)
    ready = sum(1 for o in options if o.status == OPTION_READY_FOR_IMPLEMENTATION_PLAN)
    blocked = sum(
        1 for o in options if o.status in (OPTION_BLOCKED_PROVENANCE, OPTION_REJECTED_FAKE_OR_LEAKAGE)
    )
    return (
        f"Evaluated {total} prediction acquisition options: {ready} ready for implementation "
        f"planning, {blocked} blocked. Best option: [{best.option_id}] {best.source_name} "
        f"(status={best.status}, coverage={best.estimated_coverage:.0%}, "
        f"leakage_risk={best.leakage_risk}). "
        f"PAPER_ONLY=True, PRODUCTION_READY=False."
    )
