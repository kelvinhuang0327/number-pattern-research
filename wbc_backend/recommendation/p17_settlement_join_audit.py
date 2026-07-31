"""
wbc_backend/recommendation/p17_settlement_join_audit.py

P17 Settlement Join Audit — audit the join between P16.6 recommendation rows
and the P15 simulation ledger to measure outcome data quality.

Functions:
  audit_recommendation_to_p15_join(recommendation_rows_df, p15_ledger_df)
  summarize_settlement_join_quality(joined_df)
  identify_unmatched_recommendations(joined_df)
  identify_duplicate_game_ids(joined_df)

Key design:
  - Primary join key: game_id (identity join, no position-based assumptions)
  - If game_id join yields 0 matches, we surface the fragility warning
    (P15 known limitation: position-based join may not preserve game_id correctly)
  - Result is a SettlementJoinResult dataclass

PAPER_ONLY — no production systems.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from wbc_backend.recommendation.p17_paper_ledger_contract import SettlementJoinResult

# ── Join quality thresholds ────────────────────────────────────────────────────
_HIGH_COVERAGE = 0.95
_MEDIUM_COVERAGE = 0.50
JOIN_METHOD_GAME_ID = "game_id"
JOIN_METHOD_POSITION = "position"
JOIN_METHOD_NONE = "none"
JOIN_METHOD_ROW_IDX = "row_idx"

# P19 explicit join method constants (for enriched ledger)
JOIN_BY_GAME_ID = "JOIN_BY_GAME_ID"
JOIN_BY_ROW_IDX = "JOIN_BY_ROW_IDX"
JOIN_BLOCKED_MISSING_IDENTITY = "JOIN_BLOCKED_MISSING_IDENTITY"
JOIN_BLOCKED_DUPLICATE_IDENTITY = "JOIN_BLOCKED_DUPLICATE_IDENTITY"
JOIN_BLOCKED_UNSAFE_ALIGNMENT = "JOIN_BLOCKED_UNSAFE_ALIGNMENT"


def audit_recommendation_to_p15_join(
    recommendation_rows_df: pd.DataFrame,
    p15_ledger_df: pd.DataFrame,
) -> tuple[pd.DataFrame, SettlementJoinResult]:
    """
    Join recommendation rows to P15 ledger on game_id, audit the quality.

    Returns
    -------
    (joined_df, SettlementJoinResult)
      joined_df has all recommendation rows plus P15 columns where available
      (y_true, fold_id, p_market, decimal_odds from P15 side).
    """
    rec_df = recommendation_rows_df.copy()
    p15_df = p15_ledger_df.copy()

    n_rec = len(rec_df)
    risk_notes: list[str] = []

    # Detect game_id column availability on both sides
    rec_has_game_id = "game_id" in rec_df.columns
    p15_has_game_id = "game_id" in p15_df.columns

    # Attempt identity join on game_id
    if rec_has_game_id and p15_has_game_id:
        # Deduplicate P15 by game_id to avoid fan-out
        dup_game_ids_p15 = p15_df["game_id"].duplicated().sum()
        if dup_game_ids_p15 > 0:
            risk_notes.append(
                f"P15 ledger has {dup_game_ids_p15} duplicate game_id rows — "
                f"using first occurrence per game_id"
            )
            p15_dedup = p15_df.drop_duplicates(subset=["game_id"], keep="first")
        else:
            p15_dedup = p15_df

        p15_cols_for_join = [
            c for c in ["game_id", "y_true", "fold_id", "p_market", "decimal_odds",
                         "row_idx", "reason"]
            if c in p15_dedup.columns
        ]
        p15_sub = p15_dedup[p15_cols_for_join].rename(
            columns={c: f"p15_{c}" for c in p15_cols_for_join if c != "game_id"}
        )

        joined_df = rec_df.merge(p15_sub, on="game_id", how="left")
        n_joined = int(joined_df["game_id"].isin(p15_dedup["game_id"]).sum())
        join_method = JOIN_METHOD_GAME_ID

        if n_joined == 0:
            risk_notes.append(
                "game_id join yielded 0 matches. "
                "This may indicate P15 position-based join fragility: "
                "game_id values in P15 may not correspond to recommendation game_ids. "
                "Settlement will be UNSETTLED_MISSING_OUTCOME for all active rows."
            )

        # Check for game_ids present in rec but missing from P15
        if "game_id" in rec_df.columns and len(rec_df) > 0:
            rec_game_ids = set(rec_df["game_id"].dropna().unique())
            p15_game_ids = set(p15_dedup["game_id"].dropna().unique())
            missing_from_p15 = rec_game_ids - p15_game_ids
            if missing_from_p15:
                risk_notes.append(
                    f"{len(missing_from_p15)} recommendation game_ids not found in P15 ledger"
                )

    else:
        # Cannot do identity join
        if not rec_has_game_id:
            risk_notes.append("recommendation_rows_df missing 'game_id' column — cannot join")
        if not p15_has_game_id:
            risk_notes.append("p15_ledger_df missing 'game_id' column — cannot join")
        joined_df = rec_df.copy()
        n_joined = 0
        join_method = JOIN_METHOD_NONE

    n_unmatched = n_rec - n_joined
    join_coverage = n_joined / n_rec if n_rec > 0 else 0.0

    if join_coverage >= _HIGH_COVERAGE:
        join_quality = "HIGH"
    elif join_coverage >= _MEDIUM_COVERAGE:
        join_quality = "MEDIUM"
        risk_notes.append(f"Join coverage {join_coverage:.1%} is below HIGH threshold ({_HIGH_COVERAGE:.0%})")
    elif join_coverage > 0:
        join_quality = "LOW"
        risk_notes.append(f"Join coverage {join_coverage:.1%} is very low")
    else:
        join_quality = "NONE"

    dup_count = _count_duplicate_game_ids_in_rec(rec_df)
    if dup_count > 0:
        risk_notes.append(
            f"Recommendation rows contain {dup_count} duplicate game_id values — "
            f"may indicate multiple sides per game"
        )

    result = SettlementJoinResult(
        n_recommendations=n_rec,
        n_joined=n_joined,
        n_unmatched=n_unmatched,
        n_duplicate_game_ids=dup_count,
        join_coverage=join_coverage,
        join_method=join_method,
        join_quality=join_quality,
        risk_notes=risk_notes,
    )
    return joined_df, result


def _count_duplicate_game_ids_in_rec(df: pd.DataFrame) -> int:
    """Count how many game_id values appear more than once in the recommendation frame."""
    if "game_id" not in df.columns:
        return 0
    return int(df["game_id"].duplicated().sum())


def summarize_settlement_join_quality(joined_df: pd.DataFrame) -> dict[str, Any]:
    """
    Return a plain-dict summary of join quality for the joined ledger.

    Useful for writing to JSON output.
    """
    n_rows = len(joined_df)
    n_with_y_true = 0
    n_without_y_true = 0

    # y_true can come from the recommendation rows directly or from p15_y_true after join
    y_true_col = "y_true" if "y_true" in joined_df.columns else (
        "p15_y_true" if "p15_y_true" in joined_df.columns else None
    )

    if y_true_col:
        n_with_y_true = int(joined_df[y_true_col].notna().sum())
        n_without_y_true = n_rows - n_with_y_true

    duplicate_game_ids = _count_duplicate_game_ids_in_rec(joined_df)

    return {
        "n_total_rows": n_rows,
        "n_with_y_true": n_with_y_true,
        "n_without_y_true": n_without_y_true,
        "y_true_coverage": n_with_y_true / n_rows if n_rows > 0 else 0.0,
        "duplicate_game_id_count": duplicate_game_ids,
    }


def identify_unmatched_recommendations(joined_df: pd.DataFrame) -> list[str]:
    """
    Return list of recommendation_ids (or game_ids) that were not matched in P15.

    Detected by checking for NaN in p15_y_true (set by left join) or y_true when no P15 join.
    """
    if "p15_y_true" in joined_df.columns:
        unmatched_mask = joined_df["p15_y_true"].isna()
    elif "y_true" in joined_df.columns:
        unmatched_mask = joined_df["y_true"].isna()
    else:
        return []

    id_col = "recommendation_id" if "recommendation_id" in joined_df.columns else (
        "game_id" if "game_id" in joined_df.columns else None
    )
    if id_col is None:
        return []

    return joined_df.loc[unmatched_mask, id_col].dropna().tolist()


def identify_duplicate_game_ids(joined_df: pd.DataFrame) -> list[str]:
    """Return list of game_id values that appear more than once in the joined frame."""
    if "game_id" not in joined_df.columns:
        return []
    dup_mask = joined_df["game_id"].duplicated(keep=False)
    return joined_df.loc[dup_mask, "game_id"].unique().tolist()


def audit_recommendation_to_enriched_p15_join(
    recommendation_rows_df: pd.DataFrame,
    enriched_p15_df: pd.DataFrame,
) -> tuple[pd.DataFrame, SettlementJoinResult]:
    """
    Join recommendation rows to a P19-enriched P15 ledger.

    Supports enriched ledger with game_id (from P19 identity repair).
    Returns (joined_df, SettlementJoinResult) using explicit P19 join methods.

    Behaviour:
    - If enriched_p15_df has 'identity_enrichment_status' that is a blocked status →
      emits JOIN_BLOCKED_MISSING_IDENTITY / JOIN_BLOCKED_UNSAFE_ALIGNMENT.
    - If enriched_p15_df has game_id with no duplicates → JOIN_BY_GAME_ID.
    - Falls back to original audit_recommendation_to_p15_join behaviour.
    """
    from wbc_backend.recommendation.p19_p15_ledger_identity_enricher import (
        IDENTITY_BLOCKED_UNSAFE_ALIGNMENT,
        IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE,
        IDENTITY_BLOCKED_DUPLICATE_GAME_ID,
    )

    rec_df = recommendation_rows_df.copy()
    enriched_df = enriched_p15_df.copy()
    n_rec = len(rec_df)
    risk_notes: list[str] = []

    # Check enrichment status
    enrichment_status: str | None = None
    if "identity_enrichment_status" in enriched_df.columns and len(enriched_df) > 0:
        enrichment_status = str(enriched_df["identity_enrichment_status"].iloc[0])

    # Blocked enrichment → cannot join
    if enrichment_status in {
        IDENTITY_BLOCKED_UNSAFE_ALIGNMENT,
        IDENTITY_BLOCKED_MISSING_GAME_ID_SOURCE,
        IDENTITY_BLOCKED_DUPLICATE_GAME_ID,
    }:
        if enrichment_status == IDENTITY_BLOCKED_UNSAFE_ALIGNMENT:
            join_method_p19 = JOIN_BLOCKED_UNSAFE_ALIGNMENT
            risk_notes.append("P19 identity enrichment blocked: unsafe positional alignment")
        elif enrichment_status == IDENTITY_BLOCKED_DUPLICATE_GAME_ID:
            join_method_p19 = JOIN_BLOCKED_DUPLICATE_IDENTITY
            risk_notes.append("P19 identity enrichment blocked: duplicate game_id in source")
        else:
            join_method_p19 = JOIN_BLOCKED_MISSING_IDENTITY
            risk_notes.append("P19 identity enrichment blocked: missing game_id source")

        return rec_df.copy(), SettlementJoinResult(
            n_recommendations=n_rec,
            n_joined=0,
            n_unmatched=n_rec,
            n_duplicate_game_ids=0,
            join_coverage=0.0,
            join_method=join_method_p19,
            join_quality="NONE",
            risk_notes=risk_notes,
        )

    # Check game_id availability in enriched ledger
    enriched_has_game_id = (
        "game_id" in enriched_df.columns and enriched_df["game_id"].notna().any()
    )

    if not enriched_has_game_id:
        risk_notes.append("enriched_p15_df missing 'game_id' column — cannot join")
        return rec_df.copy(), SettlementJoinResult(
            n_recommendations=n_rec,
            n_joined=0,
            n_unmatched=n_rec,
            n_duplicate_game_ids=0,
            join_coverage=0.0,
            join_method=JOIN_BLOCKED_MISSING_IDENTITY,
            join_quality="NONE",
            risk_notes=risk_notes,
        )

    # Check for duplicates in enriched ledger game_ids
    # Use one row per game_id (dedup — enriched ledger has 4 policies per row_idx)
    enriched_dedup = enriched_df.drop_duplicates(subset=["game_id"], keep="first")

    # Build p15 columns for join
    p15_cols_for_join = [
        c for c in ["game_id", "y_true", "fold_id", "p_market", "decimal_odds",
                     "row_idx", "reason"]
        if c in enriched_dedup.columns
    ]
    p15_sub = enriched_dedup[p15_cols_for_join].rename(
        columns={c: f"p15_{c}" for c in p15_cols_for_join if c != "game_id"}
    )

    joined_df = rec_df.merge(p15_sub, on="game_id", how="left")
    n_joined = int(joined_df["game_id"].isin(enriched_dedup["game_id"]).sum())

    dup_count = _count_duplicate_game_ids_in_rec(rec_df)
    if dup_count > 0:
        risk_notes.append(
            f"Recommendation rows contain {dup_count} duplicate game_id values"
        )

    n_unmatched = n_rec - n_joined
    join_coverage = n_joined / n_rec if n_rec > 0 else 0.0

    if join_coverage >= _HIGH_COVERAGE:
        join_quality = "HIGH"
    elif join_coverage >= _MEDIUM_COVERAGE:
        join_quality = "MEDIUM"
        risk_notes.append(f"Join coverage {join_coverage:.1%} below HIGH threshold")
    elif join_coverage > 0:
        join_quality = "LOW"
        risk_notes.append(f"Join coverage {join_coverage:.1%} is very low")
    else:
        join_quality = "NONE"

    result = SettlementJoinResult(
        n_recommendations=n_rec,
        n_joined=n_joined,
        n_unmatched=n_unmatched,
        n_duplicate_game_ids=dup_count,
        join_coverage=join_coverage,
        join_method=JOIN_BY_GAME_ID,
        join_quality=join_quality,
        risk_notes=risk_notes,
    )
    return joined_df, result
