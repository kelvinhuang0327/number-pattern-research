"""
wbc_backend/recommendation/p16_recommendation_input_adapter.py

P16 Recommendation Input Adapter.

Transforms P15 joined_oof_with_odds.csv into standardised P16 input rows.

Rules:
  - Only odds_join_status == "JOINED" is eligible.
  - Invalid / missing odds are preserved but marked ineligible.
  - paper_only = True always.
  - production_ready = False always.
  - source_model and source_bss_oof injected from P15 summary.

PAPER_ONLY: Paper simulation only. No production bets.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


# ── Constants ─────────────────────────────────────────────────────────────────

SOURCE_MODEL = "p13_walk_forward_logistic"
SOURCE_BSS_OOF: float = 0.008253
ODDS_JOIN_COVERAGE: float = 0.9987


# ── Row contract ──────────────────────────────────────────────────────────────

@dataclass
class P16InputRow:
    game_id: str
    date: str
    p_model: float | None
    p_market: float | None
    edge: float | None
    odds_decimal: float | None
    odds_join_status: str
    y_true: int | None
    source_model: str
    source_bss_oof: float
    odds_join_coverage: float
    paper_only: bool
    production_ready: bool
    eligible: bool
    ineligibility_reason: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _is_valid_probability(p: float | None) -> bool:
    return p is not None and 0.0 < p < 1.0


def _is_valid_odds(o: float | None) -> bool:
    return o is not None and o > 1.0


def _compute_eligibility(row: P16InputRow) -> tuple[bool, str | None]:
    """Return (eligible, reason_if_not)."""
    if row.odds_join_status != "JOINED":
        return False, f"odds_join_status={row.odds_join_status!r} (must be JOINED)"
    if not _is_valid_probability(row.p_model):
        return False, f"invalid p_model={row.p_model}"
    if not _is_valid_probability(row.p_market):
        return False, f"invalid p_market={row.p_market}"
    if not _is_valid_odds(row.odds_decimal):
        return False, f"invalid odds_decimal={row.odds_decimal}"
    return True, None


# ── Main adapter ──────────────────────────────────────────────────────────────

def load_p16_input_rows(
    joined_oof_path: str,
    source_bss_oof: float = SOURCE_BSS_OOF,
    odds_join_coverage: float = ODDS_JOIN_COVERAGE,
) -> list[P16InputRow]:
    """
    Load and adapt P15 joined_oof_with_odds.csv into P16InputRow list.

    Parameters
    ----------
    joined_oof_path : str
        Path to P15 joined_oof_with_odds.csv.
    source_bss_oof : float
        OOF BSS from P13. Injected into every row.
    odds_join_coverage : float
        Odds join coverage fraction from P15 report.

    Returns
    -------
    list[P16InputRow]
    """
    df = pd.read_csv(joined_oof_path)

    # Determine which odds column to use for decimal_odds
    # P15 joined CSV has: odds_decimal_home, odds_decimal_away, p_market, edge
    # We use edge = p_model - p_market to determine direction, then pick odds
    # that corresponds to the model's favoured side.
    # If edge > 0 → model favours home → odds_decimal_home
    # If edge <= 0 → model favours away → odds_decimal_away
    # Fall back to a unified 'odds_decimal' column if present.

    rows: list[P16InputRow] = []
    for _, series in df.iterrows():
        game_id = str(series.get("game_id", "UNKNOWN"))
        date = str(series.get("game_date", series.get("date", "UNKNOWN")))
        p_model = _safe_float(series.get("p_oof", series.get("p_model")))
        p_market = _safe_float(series.get("p_market"))
        edge = _safe_float(series.get("edge"))

        # Determine decimal odds for the model-favoured side
        if edge is not None and edge >= 0.0:
            odds_decimal = _safe_float(
                series.get("odds_decimal_home", series.get("odds_decimal"))
            )
        else:
            odds_decimal = _safe_float(
                series.get("odds_decimal_away", series.get("odds_decimal"))
            )

        odds_join_status = str(series.get("odds_join_status", "UNKNOWN"))
        y_true = _safe_int(series.get("y_true"))

        row = P16InputRow(
            game_id=game_id,
            date=date,
            p_model=p_model,
            p_market=p_market,
            edge=edge,
            odds_decimal=odds_decimal,
            odds_join_status=odds_join_status,
            y_true=y_true,
            source_model=SOURCE_MODEL,
            source_bss_oof=source_bss_oof,
            odds_join_coverage=odds_join_coverage,
            paper_only=True,
            production_ready=False,
            eligible=False,  # will be set below
            ineligibility_reason=None,
        )

        eligible, reason = _compute_eligibility(row)
        # Create updated row with eligibility
        rows.append(P16InputRow(
            game_id=row.game_id,
            date=row.date,
            p_model=row.p_model,
            p_market=row.p_market,
            edge=row.edge,
            odds_decimal=row.odds_decimal,
            odds_join_status=row.odds_join_status,
            y_true=row.y_true,
            source_model=row.source_model,
            source_bss_oof=row.source_bss_oof,
            odds_join_coverage=row.odds_join_coverage,
            paper_only=True,
            production_ready=False,
            eligible=eligible,
            ineligibility_reason=reason,
        ))

    return rows


def input_rows_to_dataframe(rows: list[P16InputRow]) -> pd.DataFrame:
    """Convert list of P16InputRow to a DataFrame."""
    return pd.DataFrame([
        {
            "game_id": r.game_id,
            "date": r.date,
            "p_model": r.p_model,
            "p_market": r.p_market,
            "edge": r.edge,
            "odds_decimal": r.odds_decimal,
            "odds_join_status": r.odds_join_status,
            "y_true": r.y_true,
            "source_model": r.source_model,
            "source_bss_oof": r.source_bss_oof,
            "odds_join_coverage": r.odds_join_coverage,
            "paper_only": r.paper_only,
            "production_ready": r.production_ready,
            "eligible": r.eligible,
            "ineligibility_reason": r.ineligibility_reason,
        }
        for r in rows
    ])
