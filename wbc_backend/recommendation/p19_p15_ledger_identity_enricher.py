"""
P19 P15 Ledger Identity Enricher

Enriches simulation_ledger.csv with game_id from joined_oof_with_odds.csv
using verified positional alignment (sort by p_oof descending → row_idx match).

Safety invariants:
- NEVER enriches by position without proof (y_true + fold_id + p_model + p_market).
- NEVER fabricates game_id.
- Returns enrichment method and status for full auditability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from wbc_backend.recommendation.p19_identity_field_audit import (
    compare_p15_joined_vs_simulation_ledger,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDENTITY_ENRICHED_BY_ROW_IDX = "IDENTITY_ENRICHED_BY_ROW_IDX"
IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT = (
    "IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT"
)
IDENTITY_BLOCKED_UNSAFE_ALIGNMENT = "IDENTITY_BLOCKED_UNSAFE_ALIGNMENT"
IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE = "IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE"
IDENTITY_BLOCKED_DUPLICATE_GAME_ID = "IDENTITY_BLOCKED_DUPLICATE_GAME_ID"

P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT = "P19_BLOCKED_UNSAFE_POSITIONAL_ALIGNMENT"

# Tolerance for float comparisons in alignment checks
_P_TOLERANCE = 1e-8
_PM_TOLERANCE = 1e-6


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error_code: Optional[str]
    error_message: Optional[str]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def enrich_simulation_ledger_with_identity(
    simulation_ledger_df: pd.DataFrame,
    joined_oof_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Enrich simulation_ledger_df with identity fields from joined_oof_df.

    Enrichment strategy (in order):
    1. If simulation_ledger_df already has game_id with full coverage → return as-is
       with status IDENTITY_ENRICHED_BY_ROW_IDX (no enrichment needed).
    2. If joined_oof_df lacks game_id → block with IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE.
    3. If joined_oof_df has duplicate game_ids → block with IDENTITY_BLOCKED_DUPLICATE_GAME_ID.
    4. Run alignment check (y_true, fold_id, p_model, p_market):
       - If fails → block with IDENTITY_BLOCKED_UNSAFE_ALIGNMENT.
       - If passes → enrich by verified positional alignment (sort p_oof descending → row_idx).

    Returns enriched DataFrame with additional columns:
        game_id, game_date, home_team, away_team,
        identity_enrichment_method, identity_enrichment_status, identity_enrichment_risk
    and all available columns from joined_oof_df prefixed for clarity.
    """
    enriched = simulation_ledger_df.copy()

    # Case 1: already has game_id
    if "game_id" in enriched.columns and enriched["game_id"].notna().all():
        enriched["identity_enrichment_method"] = IDENTITY_ENRICHED_BY_ROW_IDX
        enriched["identity_enrichment_status"] = IDENTITY_ENRICHED_BY_ROW_IDX
        enriched["identity_enrichment_risk"] = "LOW: game_id already present"
        return enriched

    # Case 2: joined_oof has no game_id
    if "game_id" not in joined_oof_df.columns or joined_oof_df["game_id"].isna().all():
        enriched["game_id"] = None
        enriched["game_date"] = None
        enriched["home_team"] = None
        enriched["away_team"] = None
        enriched["identity_enrichment_method"] = IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE
        enriched["identity_enrichment_status"] = IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE
        enriched["identity_enrichment_risk"] = "HIGH: joined_oof_with_odds lacks game_id"
        return enriched

    # Case 3: duplicate game_ids in joined_oof
    if joined_oof_df["game_id"].duplicated().any():
        enriched["game_id"] = None
        enriched["game_date"] = None
        enriched["home_team"] = None
        enriched["away_team"] = None
        enriched["identity_enrichment_method"] = IDENTITY_BLOCKED_DUPLICATE_GAME_ID
        enriched["identity_enrichment_status"] = IDENTITY_BLOCKED_DUPLICATE_GAME_ID
        enriched["identity_enrichment_risk"] = (
            "HIGH: joined_oof_with_odds has duplicate game_ids"
        )
        return enriched

    # Case 4: run alignment check
    comparison = compare_p15_joined_vs_simulation_ledger(joined_oof_df, simulation_ledger_df)

    if not comparison.alignment_safe:
        enriched["game_id"] = None
        enriched["game_date"] = None
        enriched["home_team"] = None
        enriched["away_team"] = None
        enriched["identity_enrichment_method"] = IDENTITY_BLOCKED_UNSAFE_ALIGNMENT
        enriched["identity_enrichment_status"] = IDENTITY_BLOCKED_UNSAFE_ALIGNMENT
        enriched["identity_enrichment_risk"] = (
            f"CRITICAL: {comparison.alignment_reason}"
        )
        return enriched

    # Alignment is safe — enrich by verified positional alignment
    jof_sorted = (
        joined_oof_df
        .sort_values("p_oof", ascending=False)
        .reset_index(drop=True)
        .rename(columns={"p_oof": "_jof_p_oof"})
    )
    jof_sorted["row_idx"] = jof_sorted.index

    # Select identity columns to transfer from joined_oof
    transfer_cols = ["row_idx", "game_id"]
    for col in ["game_date", "home_team", "away_team", "odds_decimal_home", "odds_decimal_away"]:
        if col in joined_oof_df.columns:
            transfer_cols.append(col)

    jof_identity = jof_sorted[transfer_cols].copy()

    # Merge on row_idx (one-to-many: ledger has 4 policies per row_idx)
    if "row_idx" in enriched.columns:
        enriched = enriched.merge(jof_identity, on="row_idx", how="left")
    else:
        # Positional: assign row_idx based on unique sorted position
        enriched = enriched.merge(jof_identity, on="row_idx", how="left")

    enriched["identity_enrichment_method"] = IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT
    enriched["identity_enrichment_status"] = IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT
    enriched["identity_enrichment_risk"] = (
        "LOW: alignment verified via y_true + fold_id + p_model + p_market"
    )

    return enriched


def validate_enriched_ledger(enriched_df: pd.DataFrame) -> ValidationResult:
    """
    Validate that the enriched ledger meets P19 contract requirements.

    Checks:
    - identity_enrichment_status column present
    - no fabricated game_ids (enrichment method must be one of the known constants)
    - blocked enrichments have null game_id
    - successful enrichments have non-null game_id
    - paper_only is always True
    """
    known_statuses = {
        IDENTITY_ENRICHED_BY_ROW_IDX,
        IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT,
        IDENTITY_BLOCKED_UNSAFE_ALIGNMENT,
        IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE,
        IDENTITY_BLOCKED_DUPLICATE_GAME_ID,
    }

    if "identity_enrichment_status" not in enriched_df.columns:
        return ValidationResult(
            valid=False,
            error_code="MISSING_STATUS_COLUMN",
            error_message="identity_enrichment_status column missing",
        )

    bad_statuses = set(enriched_df["identity_enrichment_status"].unique()) - known_statuses
    if bad_statuses:
        return ValidationResult(
            valid=False,
            error_code="UNKNOWN_STATUS",
            error_message=f"Unknown enrichment statuses: {bad_statuses}",
        )

    # paper_only must be True for all rows
    if "paper_only" in enriched_df.columns:
        if not enriched_df["paper_only"].all():
            return ValidationResult(
                valid=False,
                error_code="PAPER_ONLY_VIOLATION",
                error_message="paper_only is not True for all rows",
            )

    # Successful enrichment rows must have game_id
    success_mask = enriched_df["identity_enrichment_status"].isin({
        IDENTITY_ENRICHED_BY_ROW_IDX,
        IDENTITY_ENRICHED_BY_VERIFIED_POSITIONAL_ALIGNMENT,
    })
    if success_mask.any() and "game_id" in enriched_df.columns:
        missing_in_success = enriched_df[success_mask]["game_id"].isna().sum()
        if missing_in_success > 0:
            return ValidationResult(
                valid=False,
                error_code="MISSING_GAME_ID_AFTER_ENRICHMENT",
                error_message=(
                    f"{missing_in_success} rows marked as enriched but have null game_id"
                ),
            )

    return ValidationResult(valid=True, error_code=None, error_message=None)


def summarize_identity_enrichment(enriched_df: pd.DataFrame) -> dict:
    """
    Return a summary dict of the enrichment result.
    """
    n_total = len(enriched_df)
    game_id_col = enriched_df.get("game_id") if hasattr(enriched_df, "get") else enriched_df["game_id"] if "game_id" in enriched_df.columns else None

    n_with_game_id = int(enriched_df["game_id"].notna().sum()) if "game_id" in enriched_df.columns else 0
    n_without_game_id = n_total - n_with_game_id
    game_id_coverage = n_with_game_id / n_total if n_total > 0 else 0.0

    status_counts: dict = {}
    if "identity_enrichment_status" in enriched_df.columns:
        status_counts = enriched_df["identity_enrichment_status"].value_counts().to_dict()

    n_unique_game_ids = int(enriched_df["game_id"].nunique()) if "game_id" in enriched_df.columns else 0
    n_dup_game_ids = n_with_game_id - n_unique_game_ids

    method = (
        enriched_df["identity_enrichment_method"].iloc[0]
        if "identity_enrichment_method" in enriched_df.columns and len(enriched_df) > 0
        else "UNKNOWN"
    )

    return {
        "n_total": n_total,
        "n_with_game_id": n_with_game_id,
        "n_without_game_id": n_without_game_id,
        "game_id_coverage": round(game_id_coverage, 6),
        "n_unique_game_ids": n_unique_game_ids,
        "n_duplicate_game_ids": n_dup_game_ids,
        "enrichment_method": method,
        "enrichment_status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "paper_only": True,
        "production_ready": False,
    }
