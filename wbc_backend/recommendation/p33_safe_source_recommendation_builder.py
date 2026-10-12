"""
P33 Safe Source Recommendation Builder
========================================
Produces acquisition-safe recommendations for resolving the 2024 prediction
and odds source gaps. Recommendations are research-only pointers; they contain
no live API keys, no purchase agreements, and no automated scraping instructions.

PAPER_ONLY — no live odds acquisition, no bets, no fabrication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    SOURCE_MISSING,
    P33SourceGapSummary,
)


# ---------------------------------------------------------------------------
# Recommendation dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P33SourceRecommendation:
    """
    A single research-safe acquisition recommendation for a missing source.
    """

    recommendation_id: str
    target_data_type: str          # "prediction" | "odds"
    priority: int                  # 1 = highest
    source_name: str
    url_or_reference: str
    format_hint: str               # e.g. "CSV with columns: game_id, moneyline"
    license_note: str
    required_schema_fields: tuple
    acquisition_method: str        # "manual_download" | "api_key_required" | "retrain_model"
    estimated_effort: str          # "low" | "medium" | "high"
    paper_only: bool = True
    production_ready: bool = False
    blocker_if_skipped: str = ""


@dataclass
class P33SourceRecommendationSet:
    """All recommendations produced by the builder for a P33 gap run."""

    prediction_recommendations: List[P33SourceRecommendation] = field(
        default_factory=list
    )
    odds_recommendations: List[P33SourceRecommendation] = field(
        default_factory=list
    )
    total_count: int = 0
    paper_only: bool = True
    production_ready: bool = False
    summary_message: str = ""


# ---------------------------------------------------------------------------
# Static recommendation catalogue
# (Research-grade sources only — no live API secrets required)
# ---------------------------------------------------------------------------

_PREDICTION_RECOMMENDATIONS: List[P33SourceRecommendation] = [
    P33SourceRecommendation(
        recommendation_id="pred_r01",
        target_data_type="prediction",
        priority=1,
        source_name="Retrain local XGBoost/LightGBM on P32 gl2024 features",
        url_or_reference=(
            "Re-use gl2024.txt processed artifacts at "
            "data/mlb_2024/processed/mlb_2024_game_identity_outcomes_joined.csv "
            "as training targets; retrain offline model with cross-validation "
            "to produce p_oof (out-of-fold) predictions."
        ),
        format_hint=(
            "CSV with columns: game_id, game_date, home_team, away_team, "
            "p_model, p_oof, fold_id, model_version"
        ),
        license_note=(
            "Self-trained model on Retrosheet data. "
            "Must respect Retrosheet attribution requirement."
        ),
        required_schema_fields=(
            "game_id", "game_date", "home_team", "away_team",
            "p_model", "p_oof",
        ),
        acquisition_method="retrain_model",
        estimated_effort="high",
        blocker_if_skipped=(
            "P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE will remain until "
            "p_model / p_oof columns are generated for 2024 games."
        ),
    ),
    P33SourceRecommendation(
        recommendation_id="pred_r02",
        target_data_type="prediction",
        priority=2,
        source_name="FiveThirtyEight MLB ELO / Pitcher-adjusted win prob archive",
        url_or_reference=(
            "https://github.com/fivethirtyeight/data/tree/master/mlb-elo "
            "(historical CSV available; 2024 season included)"
        ),
        format_hint=(
            "CSV with columns: date, team1, team2, elo_prob1, pitcher1, pitcher2. "
            "Requires team name alias mapping to game_id."
        ),
        license_note=(
            "CC Attribution 4.0 International — attribution required. "
            "Check current availability; FTE data may require manual download."
        ),
        required_schema_fields=("game_id", "p_model"),
        acquisition_method="manual_download",
        estimated_effort="medium",
        blocker_if_skipped="Prediction gap persists without alternative model source.",
    ),
    P33SourceRecommendation(
        recommendation_id="pred_r03",
        target_data_type="prediction",
        priority=3,
        source_name="Baseball Prospectus (BP) / PECOTA win probability",
        url_or_reference=(
            "https://www.baseballprospectus.com/ — subscription required. "
            "Historic game-level win probabilities may be exportable."
        ),
        format_hint="CSV or Excel with game_id/date + win probability column.",
        license_note=(
            "Commercial subscription. "
            "Verify redistribution rights before committing to repo."
        ),
        required_schema_fields=("game_id", "p_model"),
        acquisition_method="api_key_required",
        estimated_effort="high",
        blocker_if_skipped="Prediction gap persists.",
    ),
]

_ODDS_RECOMMENDATIONS: List[P33SourceRecommendation] = [
    P33SourceRecommendation(
        recommendation_id="odds_r01",
        target_data_type="odds",
        priority=1,
        source_name="Retrosheet has no odds — must use historical odds database",
        url_or_reference=(
            "https://www.sportsbookreviewsonline.com/scoresoddsarchives/mlb/ "
            "(free download, 2024 closing moneylines available in XLS format)"
        ),
        format_hint=(
            "XLS with columns: Date, Rot, VH, Team, 1st, 2nd, 3rd, 4th, Final, "
            "Open, Close, ML. Requires manual parsing and game_id join."
        ),
        license_note=(
            "Historical data — personal/research use. "
            "Do not redistribute raw file. "
            "Verify current terms before downloading."
        ),
        required_schema_fields=(
            "game_id", "game_date", "home_team", "away_team",
            "odds_decimal", "p_market",
        ),
        acquisition_method="manual_download",
        estimated_effort="medium",
        blocker_if_skipped=(
            "P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE will remain until "
            "closing moneylines are acquired and joined for 2024 games."
        ),
    ),
    P33SourceRecommendation(
        recommendation_id="odds_r02",
        target_data_type="odds",
        priority=2,
        source_name="The Odds API — historical odds endpoint",
        url_or_reference=(
            "https://the-odds-api.com/liveapi/guides/v4/#get-historical-odds "
            "MLB historical endpoint; 2024 season data available. "
            "Requires paid API key."
        ),
        format_hint=(
            "JSON with h2h markets: home_team, away_team, commence_time, "
            "bookmakers[].markets[].outcomes[].price"
        ),
        license_note=(
            "Commercial API. Key must be stored securely (not in repo). "
            "Check rate limits and redistribution rights."
        ),
        required_schema_fields=("game_id", "odds_decimal", "p_market"),
        acquisition_method="api_key_required",
        estimated_effort="medium",
        blocker_if_skipped="Odds gap persists without alternative odds source.",
    ),
    P33SourceRecommendation(
        recommendation_id="odds_r03",
        target_data_type="odds",
        priority=3,
        source_name="Pinnacle historical odds (via third-party archive)",
        url_or_reference=(
            "https://www.betmetrics.net/ or https://www.oddsportal.com/ "
            "(Pinnacle closing lines available via scraping or manual export)"
        ),
        format_hint="CSV with game_date, home, away, home_close_ml, away_close_ml.",
        license_note=(
            "Verify terms of service before automated scraping. "
            "Manual export for research use typically acceptable."
        ),
        required_schema_fields=("game_id", "odds_decimal"),
        acquisition_method="manual_download",
        estimated_effort="high",
        blocker_if_skipped="Odds gap persists.",
    ),
]


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_prediction_source_recommendations(
    gap_summary: P33SourceGapSummary,
) -> List[P33SourceRecommendation]:
    """
    Return prioritised prediction source recommendations.
    Only non-empty when prediction_missing is True.
    """
    if not gap_summary.prediction_missing:
        return []
    return sorted(_PREDICTION_RECOMMENDATIONS, key=lambda r: r.priority)


def build_odds_source_recommendations(
    gap_summary: P33SourceGapSummary,
) -> List[P33SourceRecommendation]:
    """
    Return prioritised odds source recommendations.
    Only non-empty when odds_missing is True.
    """
    if not gap_summary.odds_missing:
        return []
    return sorted(_ODDS_RECOMMENDATIONS, key=lambda r: r.priority)


def validate_recommendation_safety(
    recommendations: List[P33SourceRecommendation],
) -> bool:
    """
    Safety check: all recommendations must be paper_only and not production_ready.
    Returns True if safe.
    """
    for r in recommendations:
        if not r.paper_only or r.production_ready:
            return False
    return True


def build_recommendation_set(
    gap_summary: P33SourceGapSummary,
) -> P33SourceRecommendationSet:
    """
    Build the full recommendation set for a P33 gap run.
    """
    if not PAPER_ONLY:
        raise RuntimeError("Recommendation builder must run with PAPER_ONLY=True.")

    pred_recs = build_prediction_source_recommendations(gap_summary)
    odds_recs = build_odds_source_recommendations(gap_summary)

    all_recs = pred_recs + odds_recs
    is_safe = validate_recommendation_safety(all_recs)
    if not is_safe:
        raise ValueError("Recommendation safety check failed: non-paper recommendation detected.")

    parts: List[str] = []
    if gap_summary.prediction_missing:
        parts.append(
            f"{len(pred_recs)} prediction source recommendations generated."
        )
    else:
        parts.append("Prediction sources: READY (no gap).")

    if gap_summary.odds_missing:
        parts.append(
            f"{len(odds_recs)} odds source recommendations generated."
        )
    else:
        parts.append("Odds sources: READY (no gap).")

    return P33SourceRecommendationSet(
        prediction_recommendations=pred_recs,
        odds_recommendations=odds_recs,
        total_count=len(all_recs),
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
        summary_message=" ".join(parts),
    )
