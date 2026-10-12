from __future__ import annotations

from dataclasses import dataclass

from wbc_backend.evaluation.institutional_backtest import GameRecord
from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.validator import MLBValidityTier, validate_mlb_game_data
from wbc_backend.models.mlb_f5_moneyline import run_f5_moneyline_validation
from wbc_backend.models.mlb_moneyline import default_mlb_moneyline_model, walk_forward_backtest_mlb_moneyline
from wbc_backend.models.mlb_team_total import run_team_total_validation

from .league_backtest import BacktestConfig, LeagueBacktestEngine


@dataclass(frozen=True)
class MLBBacktestReport:
    model_name: str
    n_games: int
    n_bets: int
    roi: float
    brier: float
    logloss: float
    clv: float
    threshold_pass: bool
    fold_roi_std: float
    tier: str = "RESEARCH_VALID"


@dataclass(frozen=True)
class MLBModelFamilyReport:
    moneyline_strict: MLBBacktestReport
    moneyline_research: MLBBacktestReport
    strict_valid_rate: float
    promotable: bool
    f5_moneyline: dict
    team_total: dict


def _to_report(metrics: dict) -> MLBBacktestReport:
    return MLBBacktestReport(
        model_name="mlb_moneyline",
        n_games=int(metrics["n_games"]),
        n_bets=int(metrics["n_bets"]),
        roi=float(metrics["roi"]),
        brier=float(metrics["brier"]),
        logloss=float(metrics["logloss"]),
        clv=float(metrics["clv"]),
        fold_roi_std=float(metrics.get("fold_roi_std", 0.0)),
        threshold_pass=bool(metrics["pass_thresholds"]),
        tier=str(metrics.get("tier", "UNKNOWN")),
    )


def run_mlb_moneyline_report(tier: MLBValidityTier) -> MLBBacktestReport:
    metrics = walk_forward_backtest_mlb_moneyline(tier=tier)
    return _to_report(metrics)


def run_mlb_model_family_report() -> MLBModelFamilyReport:
    rows = load_mlb_game_data()
    validation = validate_mlb_game_data(rows)
    strict_rate = validation.strict_valid_games / max(1, validation.total_games)
    ml_strict = run_mlb_moneyline_report(MLBValidityTier.STRICT_VALID)
    ml_research = run_mlb_moneyline_report(MLBValidityTier.RESEARCH_VALID)
    promotable = bool(
        ml_strict.threshold_pass
        and strict_rate >= 0.85
        and ml_strict.fold_roi_std < 0.30
    )
    f5 = run_f5_moneyline_validation()
    tt = run_team_total_validation()
    return MLBModelFamilyReport(
        moneyline_strict=ml_strict,
        moneyline_research=ml_research,
        strict_valid_rate=float(strict_rate),
        promotable=promotable,
        f5_moneyline=f5,
        team_total=tt,
    )


def run_mlb_canonical_backtest(records: list[GameRecord]):
    model = default_mlb_moneyline_model()
    engine = LeagueBacktestEngine(BacktestConfig(league="MLB", min_sample_size=50))
    return engine.run(
        records,
        predict_fn=lambda r: {
            "home_win_prob": model.predict_home_win_prob_from_record(r),
            "away_win_prob": 1.0 - model.predict_home_win_prob_from_record(r),
        },
    )
