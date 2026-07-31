"""
scripts/enrich_p38a_with_identity_bridge.py

P39F — P38A OOF × Identity Bridge Enrichment Utility

Enriches P38A OOF predictions with home_team, away_team, and game_date
from a pre-built identity bridge (Retrosheet game log), recovering the
away_team that was absent from the original P38A CSV.

PAPER_ONLY = True
SCRIPT_VERSION = "p39f_p38a_bridge_enrichment_v1"

Acceptance marker: P39F_P38A_BRIDGE_ENRICHMENT_UTILITY_READY_20260515
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

# ── Constants ─────────────────────────────────────────────────────────────────

SCRIPT_VERSION: str = "p39f_p38a_bridge_enrichment_v1"
PAPER_ONLY: bool = True

REQUIRED_BRIDGE_COLUMNS: frozenset[str] = frozenset({
    "game_id",
    "game_date",
    "home_team",
    "away_team",
})

FORBIDDEN_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "odds",
    "moneyline",
    "spread",
    "total",
    "clv",
    "ev",
    "kelly",
    "line",
    "implied_prob",
    "market_prob",
})

BRIDGE_ENRICHMENT_MARKER: str = "P39F_P38A_BRIDGE_ENRICHMENT_UTILITY_READY_20260515"


# ── Validation ─────────────────────────────────────────────────────────────────


def validate_bridge_schema(bridge_df: pd.DataFrame) -> None:
    """Validate bridge DataFrame has required columns and no duplicate game_id.

    Raises ValueError if schema is invalid.
    """
    missing = REQUIRED_BRIDGE_COLUMNS - set(bridge_df.columns)
    if missing:
        raise ValueError(
            f"Bridge CSV missing required columns: {sorted(missing)}"
        )

    dup_count = bridge_df["game_id"].duplicated().sum()
    if dup_count > 0:
        dupes = bridge_df[bridge_df["game_id"].duplicated(keep=False)]["game_id"].unique()[:5]
        raise ValueError(
            f"Bridge has {dup_count} duplicate game_id rows. Examples: {list(dupes)}"
        )

    missing_away = bridge_df["away_team"].isna().sum()
    if missing_away > 0:
        raise ValueError(
            f"Bridge has {missing_away} rows with missing away_team"
        )


def assert_no_odds_columns(df: pd.DataFrame, context: str = "") -> None:
    """Raise ValueError if any forbidden odds column is present."""
    found = [c for c in df.columns if c.lower() in FORBIDDEN_OUTPUT_COLUMNS]
    if found:
        raise ValueError(
            f"Odds columns detected in {context or 'DataFrame'}: {found}. "
            "Enrichment must not include odds data."
        )


# ── Core Enrichment ───────────────────────────────────────────────────────────


def enrich_p38a_with_bridge(
    p38a_df: pd.DataFrame,
    bridge_df: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join P38A predictions with identity bridge on game_id.

    Args:
        p38a_df: P38A OOF predictions DataFrame. Must contain `game_id`.
        bridge_df: Identity bridge DataFrame. Must pass validate_bridge_schema.

    Returns:
        Enriched DataFrame with additional columns:
            game_date, home_team, away_team, bridge_match_status
        All original P38A columns are preserved unchanged.
        p_oof values are NEVER modified.
    """
    if "game_id" not in p38a_df.columns:
        raise ValueError("P38A DataFrame must have a 'game_id' column")

    validate_bridge_schema(bridge_df)
    assert_no_odds_columns(p38a_df, "p38a_df")

    # Select only needed bridge columns to avoid column conflicts
    bridge_cols = ["game_id", "game_date", "home_team", "away_team"]
    bridge_subset = bridge_df[bridge_cols].copy()

    # Left join — all P38A rows preserved
    enriched = p38a_df.merge(bridge_subset, on="game_id", how="left")

    # Add match status column
    enriched["bridge_match_status"] = enriched["away_team"].apply(
        lambda v: "MATCHED" if pd.notna(v) else "UNMATCHED"
    )

    assert_no_odds_columns(enriched, "enriched output")

    # Sanity: p_oof must not have changed
    if "p_oof" in p38a_df.columns and "p_oof" in enriched.columns:
        original_hash = pd.util.hash_pandas_object(p38a_df["p_oof"], index=False).sum()
        enriched_hash = pd.util.hash_pandas_object(enriched["p_oof"], index=False).sum()
        if original_hash != enriched_hash:
            raise RuntimeError(
                "p_oof values changed during bridge enrichment — this is a data integrity violation."
            )

    return enriched


# ── Summary ───────────────────────────────────────────────────────────────────


def summarize_bridge_enrichment(enriched_df: pd.DataFrame) -> dict[str, object]:
    """Compute and print a bridge enrichment summary.

    Returns a dict with match_count, unmatched_count, match_rate, etc.
    """
    total = len(enriched_df)
    matched = (enriched_df["bridge_match_status"] == "MATCHED").sum()
    unmatched = total - matched
    match_rate = matched / max(total, 1)

    away_missing = enriched_df["away_team"].isna().sum()

    # Deterministic hash on key output columns
    hash_cols = [c for c in ["game_id", "home_team", "away_team", "p_oof"] if c in enriched_df.columns]
    hash_bytes = pd.util.hash_pandas_object(
        enriched_df[hash_cols].fillna(""), index=False
    ).values.tobytes()
    det_hash = hashlib.md5(hash_bytes).hexdigest()[:16]

    odds_cols = [c for c in enriched_df.columns if c.lower() in FORBIDDEN_OUTPUT_COLUMNS]

    summary = {
        "total_p38a_rows": total,
        "matched_rows": int(matched),
        "unmatched_rows": int(unmatched),
        "match_rate": round(match_rate, 6),
        "match_rate_pct": f"{match_rate * 100:.2f}%",
        "missing_away_team": int(away_missing),
        "odds_columns_found": odds_cols,
        "deterministic_hash": det_hash,
    }

    print(f"  bridge_match_status  : {matched}/{total} MATCHED ({match_rate*100:.1f}%)")
    print(f"  unmatched_rows       : {unmatched}")
    print(f"  missing_away_team    : {away_missing}")
    print(f"  odds_columns         : {odds_cols or 'NONE'}")
    print(f"  deterministic_hash   : {det_hash}")
    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P39F: Enrich P38A OOF predictions with identity bridge (home_team, away_team, game_date)"
    )
    parser.add_argument("--p38a-path", required=True, help="Path to P38A OOF predictions CSV")
    parser.add_argument("--bridge-path", required=True, help="Path to identity bridge CSV")
    parser.add_argument(
        "--out-file",
        required=True,
        help="Output enriched CSV path (must contain 'local_only' for security)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print summary without writing output file",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run enrichment (otherwise dry-run only)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    print(f"[enrich_p38a_with_identity_bridge] v={SCRIPT_VERSION} PAPER_ONLY={PAPER_ONLY}")
    print()

    # Security gate: output path must contain local_only
    if "local_only" not in args.out_file and not args.summary_only:
        print(f"  ERROR: --out-file must contain 'local_only' in path. Got: {args.out_file}")
        return 1

    if not args.execute:
        print("  [DRY-RUN] --execute not set. No data will be read or written.")
        print(f"  Would read P38A from : {args.p38a_path}")
        print(f"  Would read bridge from: {args.bridge_path}")
        print(f"  Would write to       : {args.out_file}")
        return 0

    # Load inputs
    print(f"  Loading P38A from  : {args.p38a_path}")
    p38a_df = pd.read_csv(args.p38a_path)
    print(f"  P38A rows          : {len(p38a_df)}")
    print(f"  P38A columns       : {list(p38a_df.columns)}")

    print()
    print(f"  Loading bridge from: {args.bridge_path}")
    bridge_df = pd.read_csv(args.bridge_path)
    print(f"  Bridge rows        : {len(bridge_df)}")
    print(f"  Bridge columns     : {list(bridge_df.columns)}")

    print()
    print("  Running bridge enrichment ...")
    try:
        enriched = enrich_p38a_with_bridge(p38a_df, bridge_df)
    except ValueError as exc:
        print(f"  ERROR: {exc}")
        return 1

    print()
    print("  ==> Enrichment summary:")
    summarize_bridge_enrichment(enriched)

    if not args.summary_only:
        out_path = Path(args.out_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        enriched.to_csv(out_path, index=False)
        print(f"\n  Output written to  : {out_path}")
        print(f"  Output rows        : {len(enriched)}")
        print(f"  Output columns     : {list(enriched.columns)}")
    else:
        print("\n  [--summary-only] Output file not written.")

    print()
    print(f"  Marker: {BRIDGE_ENRICHMENT_MARKER}")
    print("  PAPER_ONLY=True | pybaseball != odds source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
