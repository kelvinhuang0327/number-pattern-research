"""
P19 Identity Field Audit

Audits which files have game_id, inspects alignment between
simulation_ledger.csv and joined_oof_with_odds.csv, and reports
identity coverage quality for P17 settlement join repair.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDENTITY_COLS = [
    "game_id", "date", "game_date", "row_idx", "fold_id",
    "home_team", "away_team",
    "p_model", "p_market", "p_oof",
    "odds_decimal", "decimal_odds", "odds_decimal_home", "odds_decimal_away",
    "y_true", "policy", "should_bet", "stake_fraction",
]

COVERAGE_HIGH = 0.95
COVERAGE_MEDIUM = 0.50


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoverageReport:
    column: str
    n_total: int
    n_non_null: int
    coverage: float
    quality: str  # HIGH, MEDIUM, LOW, NONE
    unique_count: int


@dataclass(frozen=True)
class DuplicateReport:
    keys: list
    n_total: int
    n_unique: int
    n_duplicates: int
    has_duplicates: bool
    duplicate_samples: list

    def __hash__(self):
        return hash((tuple(self.keys), self.n_total, self.n_unique))


@dataclass(frozen=True)
class IdentityComparison:
    n_sim_rows: int
    n_joined_rows: int
    rows_equal: bool
    sort_key_used: str  # "p_oof_descending"
    ytrue_match: bool
    fold_id_match: bool
    p_model_max_diff: float
    p_market_max_diff: float
    alignment_safe: bool
    alignment_reason: str


@dataclass
class IdentityFieldAudit:
    """Mutable aggregate: summarises identity fields across all input files."""
    files_checked: list[str] = field(default_factory=list)
    files_with_game_id: list[str] = field(default_factory=list)
    files_without_game_id: list[str] = field(default_factory=list)
    coverage_reports: list[CoverageReport] = field(default_factory=list)
    comparison: Optional[IdentityComparison] = None
    enrichment_feasible: bool = False
    enrichment_blocker: Optional[str] = None
    join_keys_available: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def detect_available_join_keys(df: pd.DataFrame) -> list[str]:
    """Return the subset of IDENTITY_COLS present in df."""
    return [c for c in IDENTITY_COLS if c in df.columns]


def detect_game_id_coverage(df: pd.DataFrame) -> CoverageReport:
    """Return a CoverageReport for game_id (or a stub if absent)."""
    n_total = len(df)
    if "game_id" not in df.columns:
        return CoverageReport(
            column="game_id",
            n_total=n_total,
            n_non_null=0,
            coverage=0.0,
            quality="NONE",
            unique_count=0,
        )
    col = df["game_id"]
    n_non_null = int(col.notna().sum())
    coverage = n_non_null / n_total if n_total > 0 else 0.0
    quality = (
        "HIGH" if coverage >= COVERAGE_HIGH else
        "MEDIUM" if coverage >= COVERAGE_MEDIUM else
        "LOW" if coverage > 0 else
        "NONE"
    )
    return CoverageReport(
        column="game_id",
        n_total=n_total,
        n_non_null=n_non_null,
        coverage=coverage,
        quality=quality,
        unique_count=int(col.nunique()),
    )


def detect_duplicate_identity_keys(
    df: pd.DataFrame,
    keys: list[str],
) -> DuplicateReport:
    """Return a DuplicateReport for the given key columns."""
    present_keys = [k for k in keys if k in df.columns]
    if not present_keys:
        return DuplicateReport(
            keys=keys,
            n_total=len(df),
            n_unique=0,
            n_duplicates=0,
            has_duplicates=False,
            duplicate_samples=[],
        )
    n_total = len(df)
    n_unique = int(df[present_keys].drop_duplicates().shape[0])
    n_duplicates = n_total - n_unique
    has_dups = n_duplicates > 0
    dup_samples: list = []
    if has_dups:
        dup_mask = df.duplicated(subset=present_keys, keep=False)
        dup_samples = (
            df[dup_mask][present_keys]
            .drop_duplicates()
            .head(5)
            .to_dict(orient="records")
        )
    return DuplicateReport(
        keys=present_keys,
        n_total=n_total,
        n_unique=n_unique,
        n_duplicates=n_duplicates,
        has_duplicates=has_dups,
        duplicate_samples=dup_samples,
    )


def compare_p15_joined_vs_simulation_ledger(
    joined_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
) -> IdentityComparison:
    """
    Compare joined_oof_with_odds.csv against simulation_ledger.csv.

    The P15 simulation runner sorts joined_df by p_oof descending before
    assigning row_idx.  We replicate that sort to verify alignment.

    Returns IdentityComparison with alignment_safe=True only when all
    four checks pass: y_true, fold_id, p_model, p_market.
    """
    n_sim = len(ledger_df)
    n_jof = len(joined_df)

    if n_sim == 0 or n_jof == 0:
        return IdentityComparison(
            n_sim_rows=n_sim, n_joined_rows=n_jof,
            rows_equal=False, sort_key_used="p_oof_descending",
            ytrue_match=False, fold_id_match=False,
            p_model_max_diff=float("nan"), p_market_max_diff=float("nan"),
            alignment_safe=False,
            alignment_reason="One or both DataFrames are empty.",
        )

    # Unique row_idx count in ledger must equal joined rows
    unique_row_idx = ledger_df["row_idx"].nunique() if "row_idx" in ledger_df.columns else -1
    rows_equal = (unique_row_idx == n_jof)

    if not rows_equal:
        return IdentityComparison(
            n_sim_rows=n_sim, n_joined_rows=n_jof,
            rows_equal=False, sort_key_used="p_oof_descending",
            ytrue_match=False, fold_id_match=False,
            p_model_max_diff=float("nan"), p_market_max_diff=float("nan"),
            alignment_safe=False,
            alignment_reason=(
                f"row_idx unique count ({unique_row_idx}) != "
                f"joined_oof row count ({n_jof})."
            ),
        )

    # Replicate P15 sort
    jof_sorted = (
        joined_df
        .sort_values("p_oof", ascending=False)
        .reset_index(drop=True)
    )
    jof_sorted.index.name = "row_idx"

    # Take one-policy slice from simulation ledger (first policy encountered)
    if "policy" in ledger_df.columns:
        first_policy = ledger_df["policy"].iloc[0]
        sim_slice = ledger_df[ledger_df["policy"] == first_policy].copy()
    else:
        sim_slice = ledger_df.copy()
    sim_slice = sim_slice.set_index("row_idx") if "row_idx" in sim_slice.columns else sim_slice

    # Alignment checks
    ytrue_ok = bool((sim_slice["y_true"] == jof_sorted["y_true"]).all())
    fold_ok = bool((sim_slice["fold_id"] == jof_sorted["fold_id"]).all())

    p_diff = float(
        (sim_slice["p_model"] - jof_sorted["p_oof"]).abs().max()
    ) if "p_model" in sim_slice.columns and "p_oof" in jof_sorted.columns else float("nan")

    pm_diff = float(
        (sim_slice["p_market"] - jof_sorted["p_market"]).abs().max()
    ) if "p_market" in sim_slice.columns and "p_market" in jof_sorted.columns else float("nan")

    p_ok = not np.isnan(p_diff) and p_diff < 1e-8
    pm_ok = not np.isnan(pm_diff) and pm_diff < 1e-6

    safe = ytrue_ok and fold_ok and p_ok and pm_ok

    if safe:
        reason = (
            "All alignment checks pass: y_true, fold_id, p_model, p_market "
            "match exactly after sorting joined_oof_with_odds by p_oof descending. "
            "Enrichment by row_idx is safe."
        )
    else:
        parts = []
        if not ytrue_ok:
            parts.append("y_true mismatch")
        if not fold_ok:
            parts.append("fold_id mismatch")
        if not p_ok:
            parts.append(f"p_model max_diff={p_diff:.6f}")
        if not pm_ok:
            parts.append(f"p_market max_diff={pm_diff:.6f}")
        reason = "UNSAFE: " + "; ".join(parts)

    return IdentityComparison(
        n_sim_rows=n_sim,
        n_joined_rows=n_jof,
        rows_equal=rows_equal,
        sort_key_used="p_oof_descending",
        ytrue_match=ytrue_ok,
        fold_id_match=fold_ok,
        p_model_max_diff=p_diff,
        p_market_max_diff=pm_diff,
        alignment_safe=safe,
        alignment_reason=reason,
    )


def audit_identity_columns(paths: dict[str, str]) -> IdentityFieldAudit:
    """
    Load each CSV in paths, check for game_id presence, and compare
    simulation_ledger vs joined_oof_with_odds.

    paths keys (all optional):
        "simulation_ledger"  -> path to P15 simulation_ledger.csv
        "joined_oof"         -> path to P15 joined_oof_with_odds.csv
        "recommendation_rows"-> path to P16.6 recommendation_rows.csv
        "p17_ledger"         -> path to P17 paper_recommendation_ledger.csv
    """
    audit = IdentityFieldAudit()

    loaded: dict[str, pd.DataFrame] = {}
    for name, path in paths.items():
        try:
            df = pd.read_csv(path)
            loaded[name] = df
            audit.files_checked.append(name)
            audit.join_keys_available[name] = detect_available_join_keys(df)
            cov = detect_game_id_coverage(df)
            audit.coverage_reports.append(cov)
            if cov.n_non_null > 0:
                audit.files_with_game_id.append(name)
            else:
                audit.files_without_game_id.append(name)
        except Exception as exc:
            audit.files_checked.append(f"{name}:ERROR:{exc}")

    # Compare simulation_ledger vs joined_oof if both loaded
    if "simulation_ledger" in loaded and "joined_oof" in loaded:
        audit.comparison = compare_p15_joined_vs_simulation_ledger(
            joined_df=loaded["joined_oof"],
            ledger_df=loaded["simulation_ledger"],
        )
        if audit.comparison.alignment_safe:
            # Also require game_id to exist in joined_oof
            jof_cr = next(
                (cr for cr in audit.coverage_reports
                 if audit.files_checked[audit.coverage_reports.index(cr)] == "joined_oof"
                    or (len(audit.coverage_reports) >= 2 and audit.coverage_reports.index(cr) == list(loaded.keys()).index("joined_oof") if "joined_oof" in loaded else False)),
                None
            )
            joined_oof_df = loaded["joined_oof"]
            if "game_id" in joined_oof_df.columns and joined_oof_df["game_id"].notna().any():
                audit.enrichment_feasible = True
                audit.enrichment_blocker = None
            else:
                audit.enrichment_feasible = False
                audit.enrichment_blocker = "joined_oof lacks game_id — cannot enrich simulation_ledger"
        else:
            audit.enrichment_feasible = False
            audit.enrichment_blocker = audit.comparison.alignment_reason
    elif "joined_oof" not in loaded:
        audit.enrichment_feasible = False
        audit.enrichment_blocker = "joined_oof_with_odds.csv not loaded"
    elif "simulation_ledger" not in loaded:
        audit.enrichment_feasible = False
        audit.enrichment_blocker = "simulation_ledger.csv not loaded"

    return audit
