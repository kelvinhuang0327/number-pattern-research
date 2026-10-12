from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wbc_backend.mlb_data.ids import make_mlb_game_id
from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.validator import MLBValidityTier, validate_mlb_game_data
from wbc_backend.models.mlb_moneyline_base import MLBMoneylineBaseModel
from wbc_backend.ux.report_style import build_report_header, build_report_summary


def _american_to_implied_prob(odds: Any) -> float:
    if odds is None:
        return np.nan
    if isinstance(odds, str):
        token = odds.strip()
        if token in {"", "-", "NA", "N/A", "null", "None"}:
            return np.nan
        odds = token
    try:
        odds = float(odds)
    except Exception:
        return np.nan
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 100.0 / (odds + 100.0)


def _safe_numeric(series: pd.Series, default: float = 0.0) -> np.ndarray:
    return np.nan_to_num(pd.to_numeric(series, errors="coerce").to_numpy(dtype=float), nan=default, posinf=default, neginf=default)


def _read_context_records(context_path: str) -> dict[str, dict]:
    records_by_gid: dict[str, dict] = {}
    for row in load_mlb_game_data(csv_path="data/mlb_2025/mlb_odds_2025_real.csv", context_path=context_path):
        records_by_gid[row.game_id] = {
            "confirmed_home_lineup": int(row.features.confirmed_home_lineup.available),
            "confirmed_away_lineup": int(row.features.confirmed_away_lineup.available),
            "bullpen_home": int(row.features.bullpen_usage_last_3d_home.available),
            "bullpen_away": int(row.features.bullpen_usage_last_3d_away.available),
            "weather": int(row.features.weather.available),
            "wind": int(row.features.wind.available),
            "injury_report": int(row.features.injury_rest.injury_report.available),
            "rest_home": int(row.features.injury_rest.rest_days_home.available),
            "rest_away": int(row.features.injury_rest.rest_days_away.available),
            "odds_history": int(row.features.odds.odds_history.available),
            "closing_home_ml": row.features.odds.closing_home_ml.value,
            "open_home_ml": row.features.odds.opening_home_ml.value,
            "strict_fresh_ready": int(
                row.features.confirmed_home_starter.available
                and row.features.confirmed_away_starter.available
                and row.features.confirmed_home_lineup.available
                and row.features.confirmed_away_lineup.available
                and row.features.bullpen_usage_last_3d_home.available
                and row.features.bullpen_usage_last_3d_away.available
                and row.features.weather.available
                and row.features.wind.available
                and row.features.injury_rest.injury_report.available
                and row.features.injury_rest.rest_days_home.available
                and row.features.injury_rest.rest_days_away.available
                and row.features.odds.odds_history.available
                and row.features.odds.closing_home_ml.available
            ),
        }
    return records_by_gid


@dataclass(frozen=True)
class ExperimentResult:
    name: str
    groups: tuple[str, ...]
    tier: str
    n_games: int
    n_bets: int
    roi: float
    brier: float
    logloss: float
    clv: float
    fold_roi_std: float
    alpha_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "groups": list(self.groups),
            "tier": self.tier,
            "n_games": self.n_games,
            "n_bets": self.n_bets,
            "roi": self.roi,
            "brier": self.brier,
            "logloss": self.logloss,
            "clv": self.clv,
            # mean_bet_edge: alias for 'clv' — avg edge (model_prob - market_prob) on selected bets.
            # NOT genuine CLV. 2025 data is single-snapshot post-game proxy only.
            "mean_bet_edge": self.clv,
            "fold_roi_std": self.fold_roi_std,
            "alpha_class": self.alpha_class,
        }


class MLBAlphaLab:
    def __init__(self, csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv", context_path: str = "data/mlb_context"):
        self.csv_path = csv_path
        self.context_path = context_path
        self.df = pd.read_csv(csv_path).copy()
        self.df["game_id"] = self.df.apply(
            lambda r: make_mlb_game_id(str(r.get("Date", "")), str(r.get("Start Time (EDT)", "")), str(r.get("Away", "")), str(r.get("Home", ""))),
            axis=1,
        )
        context_map = _read_context_records(context_path)
        self._attach_context_columns(context_map)
        self.df = self._attach_validity(self.df)
        self.feature_groups = self._build_feature_groups(self.df)

    def _attach_context_columns(self, context_map: dict[str, dict]) -> None:
        default_ctx = {
            "confirmed_home_lineup": 0,
            "confirmed_away_lineup": 0,
            "bullpen_home": 0,
            "bullpen_away": 0,
            "weather": 0,
            "wind": 0,
            "injury_report": 0,
            "rest_home": 0,
            "rest_away": 0,
            "odds_history": 0,
            "closing_home_ml": np.nan,
            "open_home_ml": np.nan,
            "strict_fresh_ready": 0,
        }
        for key in default_ctx:
            self.df[key] = self.df["game_id"].map(lambda gid: context_map.get(gid, default_ctx).get(key, default_ctx[key]))

    def _attach_validity(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = load_mlb_game_data(csv_path=self.csv_path, context_path=self.context_path)
        validation = validate_mlb_game_data(rows)
        out = df.copy()
        out["validity_tier"] = out["game_id"].map(lambda gid: validation.status_by_game.get(gid, MLBValidityTier.INVALID).value)
        return out

    def _build_feature_groups(self, df: pd.DataFrame) -> dict[str, list[str]]:
        df["_date_key"] = pd.to_datetime(df["Date"], errors="coerce")
        df.sort_values(by=["_date_key", "Start Time (EDT)"], inplace=True, kind="mergesort")
        home_ml = df["Home ML"].apply(_american_to_implied_prob).fillna(0.5)
        away_ml = df["Away ML"].apply(_american_to_implied_prob).fillna(0.5)
        close_home = df["closing_home_ml"].apply(_american_to_implied_prob).fillna(home_ml)
        open_home = df["open_home_ml"].apply(_american_to_implied_prob).fillna(home_ml)

        team_games: dict[str, int] = {}
        team_wins: dict[str, int] = {}
        team_run_diff: dict[str, float] = {}
        home_prior_win: list[float] = []
        away_prior_win: list[float] = []
        home_prior_rd: list[float] = []
        away_prior_rd: list[float] = []
        for _, row in df.iterrows():
            home = str(row.get("Home", ""))
            away = str(row.get("Away", ""))
            hg = max(1, team_games.get(home, 0))
            ag = max(1, team_games.get(away, 0))
            home_prior_win.append(team_wins.get(home, 0) / hg)
            away_prior_win.append(team_wins.get(away, 0) / ag)
            home_prior_rd.append(team_run_diff.get(home, 0.0) / hg)
            away_prior_rd.append(team_run_diff.get(away, 0.0) / ag)

            hs = pd.to_numeric(row.get("Home Score"), errors="coerce")
            as_ = pd.to_numeric(row.get("Away Score"), errors="coerce")
            if pd.notna(hs) and pd.notna(as_):
                team_games[home] = team_games.get(home, 0) + 1
                team_games[away] = team_games.get(away, 0) + 1
                if hs > as_:
                    team_wins[home] = team_wins.get(home, 0) + 1
                else:
                    team_wins[away] = team_wins.get(away, 0) + 1
                team_run_diff[home] = team_run_diff.get(home, 0.0) + float(hs - as_)
                team_run_diff[away] = team_run_diff.get(away, 0.0) + float(as_ - hs)

        df["base_home_market"] = home_ml
        df["base_away_market"] = away_ml
        df["base_market_delta"] = home_ml - away_ml
        df["base_home_bias"] = 1.0
        df["base_ou"] = _safe_numeric(df["O/U"], default=8.5)
        df["base_starter_known"] = (~df["Home Starter"].isna()).astype(float) + (~df["Away Starter"].isna()).astype(float)
        df["base_home_recent_proxy"] = np.array(home_prior_win) - np.array(away_prior_win)
        df["base_run_diff_proxy"] = np.array(home_prior_rd) - np.array(away_prior_rd)

        df["adv_matchup_interaction"] = df["base_market_delta"] * df["base_ou"]
        df["adv_pitcher_fatigue_proxy"] = np.where(df["base_starter_known"] < 2, 0.4, 0.0)
        df["adv_momentum_proxy"] = pd.Series(df["base_run_diff_proxy"]).rolling(7, min_periods=1).mean()
        df["adv_variance_proxy"] = pd.Series(df["base_run_diff_proxy"]).rolling(9, min_periods=2).std().fillna(0.0)

        df["mkt_implied_prob"] = home_ml
        df["mkt_line_movement_delta"] = close_home - open_home
        df["mkt_open_close_gap"] = close_home - home_ml
        df["mkt_public_sharp_proxy"] = np.where(np.abs(df["mkt_line_movement_delta"]) > 0.03, 1.0, 0.0)

        df["ctx_lineup_delta"] = df["confirmed_home_lineup"] - df["confirmed_away_lineup"]
        df["ctx_bullpen_delta"] = df["bullpen_home"] - df["bullpen_away"]
        df["ctx_weather_wind_ready"] = ((df["weather"] == 1) & (df["wind"] == 1)).astype(float)
        df["ctx_injury_rest_delta"] = (df["injury_report"] + df["rest_home"]) - (df["rest_away"])
        df["ctx_odds_timeline_ready"] = df["odds_history"].astype(float)
        df.drop(columns=["_date_key"], inplace=True)

        return {
            "base": [
                "base_home_market",
                "base_away_market",
                "base_market_delta",
                "base_home_bias",
                "base_ou",
                "base_starter_known",
                "base_run_diff_proxy",
                "base_home_recent_proxy",
            ],
            "advanced": [
                "adv_matchup_interaction",
                "adv_pitcher_fatigue_proxy",
                "adv_momentum_proxy",
                "adv_variance_proxy",
            ],
            "market": [
                "mkt_implied_prob",
                "mkt_line_movement_delta",
                "mkt_open_close_gap",
                "mkt_public_sharp_proxy",
            ],
            "context": [
                "ctx_lineup_delta",
                "ctx_bullpen_delta",
                "ctx_weather_wind_ready",
                "ctx_injury_rest_delta",
                "ctx_odds_timeline_ready",
            ],
        }

    @staticmethod
    def _metrics(probs: np.ndarray, y: np.ndarray, market_prob: np.ndarray) -> dict[str, float]:
        eps = 1e-7
        brier = float(np.mean((probs - y) ** 2))
        logloss = float(np.mean(-(y * np.log(np.clip(probs, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - probs, eps, 1 - eps)))))
        edge = probs - market_prob
        bets = np.abs(edge) >= 0.025
        pnl = np.where((edge > 0) & (y == 1), 1.0, np.where((edge <= 0) & (y == 0), 1.0, -1.0))
        roi = float(pnl[bets].mean()) if np.any(bets) else 0.0
        # NOTE: 'clv' here is actually mean_bet_edge (avg model-vs-market edge on selected bets).
        # This is NOT Closing Line Value — no independent pregame+closing timestamps exist for 2025 data.
        mean_bet_edge = float(np.mean(edge[bets])) if np.any(bets) else 0.0
        return {"roi": roi, "brier": brier, "logloss": logloss, "clv": mean_bet_edge, "mean_bet_edge": mean_bet_edge, "n_bets": int(np.sum(bets))}

    def _run_walkforward(self, features: list[str], tier: MLBValidityTier, n_splits: int = 6) -> dict[str, float]:
        df = self.df[self.df["validity_tier"] == tier.value].copy().reset_index(drop=True)
        if len(df) < 80:
            return {"n_games": int(len(df)), "n_bets": 0, "roi": 0.0, "brier": 1.0, "logloss": 1.0, "clv": 0.0, "fold_roi_std": 0.0}
        X = np.nan_to_num(df[features].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        y = (pd.to_numeric(df["Home Score"], errors="coerce") > pd.to_numeric(df["Away Score"], errors="coerce")).astype(int).to_numpy()
        mkt = df["Home ML"].apply(_american_to_implied_prob).fillna(0.5).to_numpy(dtype=float)
        split = max(40, len(df) // n_splits)
        probs = np.zeros(len(df), dtype=float)
        fold_rois = []

        for start in range(split, len(df), split):
            end = min(len(df), start + split)
            model = MLBMoneylineBaseModel().fit(X[:start], y[:start])
            pred = np.clip(model.predict_proba(X[start:end]), 1e-5, 1 - 1e-5)
            probs[start:end] = pred
            fold_rois.append(self._metrics(pred, y[start:end], mkt[start:end])["roi"])
        probs[:split] = mkt[:split]
        metrics = self._metrics(np.clip(probs, 1e-5, 1 - 1e-5), y, mkt)
        metrics["n_games"] = int(len(df))
        metrics["fold_roi_std"] = float(np.std(fold_rois)) if fold_rois else 0.0
        return metrics

    @staticmethod
    def _alpha_class(candidate: dict[str, float], baseline: dict[str, float]) -> str:
        d_clv = candidate["clv"] - baseline["clv"]
        d_brier = baseline["brier"] - candidate["brier"]
        stable = candidate["fold_roi_std"] <= 0.30
        if d_clv > 0.003 and d_brier > 0 and stable:
            return "TRUE_ALPHA"
        if d_clv > 0 and stable:
            return "WEAK_ALPHA"
        if d_clv < -0.003 or candidate["fold_roi_std"] > 0.42:
            return "OVERFIT_SIGNAL"
        return "NOISE"

    def run_feature_exploration(self, tier: MLBValidityTier = MLBValidityTier.RESEARCH_VALID) -> list[ExperimentResult]:
        experiments: list[tuple[str, tuple[str, ...], list[str]]] = []
        experiments.append(("base_only", ("base",), list(self.feature_groups["base"])))
        optional_groups = ["advanced", "market", "context"]
        for g in optional_groups:
            experiments.append((f"base_plus_{g}", ("base", g), list(self.feature_groups["base"] + self.feature_groups[g])))
        for p in combinations(optional_groups, 2):
            groups = ("base",) + p
            cols = list(self.feature_groups["base"] + self.feature_groups[p[0]] + self.feature_groups[p[1]])
            experiments.append((f"base_plus_{p[0]}_{p[1]}", groups, cols))
        all_combo = ("base", "advanced", "market", "context")
        experiments.append(("base_plus_advanced_market_context", all_combo, sum((self.feature_groups[g] for g in all_combo), [])))
        for p in combinations(optional_groups, 3):
            groups = ("base",) + p
            cols = list(self.feature_groups["base"])
            for g in p:
                cols.extend(self.feature_groups[g])
            experiments.append((f"base_plus_{'_'.join(p)}", groups, cols))

        baseline_metrics = self._run_walkforward(self.feature_groups["base"], tier=tier)
        results: list[ExperimentResult] = []
        for name, groups, cols in experiments:
            metrics = baseline_metrics if name == "base_only" else self._run_walkforward(cols, tier=tier)
            results.append(
                ExperimentResult(
                    name=name,
                    groups=groups,
                    tier=tier.value,
                    n_games=int(metrics["n_games"]),
                    n_bets=int(metrics["n_bets"]),
                    roi=float(metrics["roi"]),
                    brier=float(metrics["brier"]),
                    logloss=float(metrics["logloss"]),
                    clv=float(metrics["clv"]),
                    fold_roi_std=float(metrics["fold_roi_std"]),
                    alpha_class=self._alpha_class(metrics, baseline_metrics),
                )
            )
        return results

    def diagnose_model(self, tier: MLBValidityTier = MLBValidityTier.RESEARCH_VALID) -> dict[str, Any]:
        df = self.df[self.df["validity_tier"] == tier.value].copy().reset_index(drop=True)
        if len(df) < 80:
            return {"status": "INSUFFICIENT_DATA", "tier": tier.value}
        X = np.nan_to_num(df[self.feature_groups["base"]].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        y = (pd.to_numeric(df["Home Score"], errors="coerce") > pd.to_numeric(df["Away Score"], errors="coerce")).astype(int).to_numpy()
        model = MLBMoneylineBaseModel().fit(X, y)
        probs = np.clip(model.predict_proba(X), 1e-4, 1 - 1e-4)
        bins = np.linspace(0, 1, 11)
        bucket_summary = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            mask = (probs >= lo) & (probs < hi if i < len(bins) - 2 else probs <= hi)
            if np.any(mask):
                bucket_summary.append(
                    {
                        "bucket": f"{lo:.1f}-{hi:.1f}",
                        "n": int(np.sum(mask)),
                        "pred_mean": float(np.mean(probs[mask])),
                        "actual_rate": float(np.mean(y[mask])),
                    }
                )
        entropy = float(np.mean(-(probs * np.log(probs) + (1 - probs) * np.log(1 - probs))))
        sharpness = float(np.mean(np.abs(probs - 0.5)))
        return {"tier": tier.value, "calibration_buckets": bucket_summary, "entropy_mean": entropy, "sharpness": sharpness}

    def production_gap_map(self) -> dict[str, Any]:
        rows = load_mlb_game_data(csv_path=self.csv_path, context_path=self.context_path)
        validation = validate_mlb_game_data(rows)
        n = max(1, len(rows))
        fields = {
            "confirmed_lineups": lambda r: r.features.confirmed_home_lineup.available and r.features.confirmed_away_lineup.available,
            "bullpen_usage_3d": lambda r: r.features.bullpen_usage_last_3d_home.available and r.features.bullpen_usage_last_3d_away.available,
            "odds_timeline": lambda r: r.features.odds.odds_history.available,
            "weather_wind": lambda r: r.features.weather.available and r.features.wind.available,
            "injury_rest": lambda r: r.features.injury_rest.injury_report.available and r.features.injury_rest.rest_days_home.available and r.features.injury_rest.rest_days_away.available,
        }
        missing = {}
        for name, fn in fields.items():
            present = sum(1 for r in rows if fn(r))
            miss_rate = 1.0 - (present / n)
            if miss_rate >= 0.5:
                priority = "critical"
            elif miss_rate >= 0.25:
                priority = "high_impact"
            elif miss_rate >= 0.1:
                priority = "optional"
            else:
                priority = "negligible"
            missing[name] = {"present_rate": round(present / n, 4), "missing_rate": round(miss_rate, 4), "priority": priority}
        # Odds timeline tier breakdown (how many games have each level of odds coverage)
        closing_only_count = sum(
            1 for r in rows
            if r.features.odds.closing_home_ml.available
            and not r.features.odds.opening_home_ml.available
            and not r.features.odds.decision_home_ml.available
        )
        strict_timeline_count = sum(
            1 for r in rows
            if r.features.odds.opening_home_ml.available
            and r.features.odds.decision_home_ml.available
            and r.features.odds.closing_home_ml.available
        )
        no_odds_count = sum(1 for r in rows if not r.features.odds.closing_home_ml.available)
        return {
            "strict_valid_rate": round(validation.strict_valid_games / n, 4),
            "research_valid_count": validation.research_valid_games,
            "status_distribution": {
                "STRICT_VALID": validation.strict_valid_games,
                "RESEARCH_VALID": validation.research_valid_games,
                "INVALID": validation.invalid_games,
            },
            # Odds timeline tier: what quality of odds data exists per game
            # strict_timeline: has opening + decision + closing (genuine CLV possible)
            # closing_only:    single post-game snapshot only (CLV unavailable, used as single-snapshot benchmark)
            # no_odds_data:    no odds at all
            "odds_tier_summary": {
                "strict_timeline": strict_timeline_count,
                "closing_only": closing_only_count,
                "no_odds_data": no_odds_count,
                "closing_coverage_rate": round((strict_timeline_count + closing_only_count) / n, 4),
                "strict_clv_coverage_rate": round(strict_timeline_count / n, 4),
                "note": (
                    "closing_only games use a single post-game snapshot as market reference. "
                    "CLV is UNAVAILABLE (not a proxy — same snapshot cannot produce meaningful CLV). "
                    "Research framing: single-snapshot benchmark. "
                    "True CLV requires strict_timeline (opening < decision < closing, all pregame)."
                ),
            },
            "context_gap_priority": missing,
        }

    def _strict_gate(self, strict_results: list[ExperimentResult]) -> dict[str, Any]:
        if not strict_results or strict_results[0].n_games == 0:
            return {"status": "BLOCKED BY DATA LAYER", "promotable": False}
        best = max(strict_results, key=lambda r: (r.clv, r.roi, -r.brier))
        promotable = bool(
            (best.roi > 0)
            and (best.brier < 0.240)
            and (best.logloss < 0.670)
            and (best.clv > 0)
            and (best.fold_roi_std <= 0.30)
        )
        return {"status": "PASS" if promotable else "FAIL", "promotable": promotable, "best_strict_model": best.as_dict()}

    def run_full_research_cycle(self, report_path: str = "data/wbc_backend/reports/mlb_alpha_discovery_report.json") -> dict[str, Any]:
        research_results = self.run_feature_exploration(tier=MLBValidityTier.RESEARCH_VALID)
        strict_results = self.run_feature_exploration(tier=MLBValidityTier.STRICT_VALID)
        diagnosis = self.diagnose_model(tier=MLBValidityTier.RESEARCH_VALID)
        gap = self.production_gap_map()
        strict_gate = self._strict_gate(strict_results)
        clv_rank = sorted(research_results, key=lambda r: (r.clv, -r.brier), reverse=True)
        alpha_ranking = {
            "TRUE_ALPHA": [r.name for r in research_results if r.alpha_class == "TRUE_ALPHA"],
            "WEAK_ALPHA": [r.name for r in research_results if r.alpha_class == "WEAK_ALPHA"],
            "NOISE": [r.name for r in research_results if r.alpha_class == "NOISE"],
            "OVERFIT_SIGNAL": [r.name for r in research_results if r.alpha_class == "OVERFIT_SIGNAL"],
        }
        payload = {
            "report_summary": build_report_summary(
                mode="PAPER_ONLY",
                safety="NO BETTING",
                scope="historical 2025 MLB",
                status="RESEARCH_VALID" if strict_gate["status"] == "BLOCKED BY DATA LAYER" else "MIXED",
                next_step="Review the model classes and paper-only benchmark outputs.",
                open_file="data/wbc_backend/reports/mlb_alpha_discovery_report.json",
                purpose="single-snapshot benchmark alpha research",
            ),
            "report_header": build_report_header(
                title="MLB ALPHA DISCOVERY REPORT",
                mode="PAPER_ONLY",
                safety="NO BETTING",
                purpose="single-snapshot benchmark alpha research",
                scope="historical 2025 MLB",
                source="wbc_backend/research/mlb_alpha_lab.py",
                status="RESEARCH_VALID" if strict_gate["status"] == "BLOCKED BY DATA LAYER" else "MIXED",
            ),
            # Research scope declaration — clarifies what this report actually measures.
            "research_scope": {
                "framing": "single_snapshot_benchmark",
                "clv_available": False,
                "data_tier": "post_game_proxy_only",
                "note": (
                    "This report measures model performance vs a single canonical market snapshot. "
                    "CLV research requires independent pre-game decision + closing timestamps. "
                    "2025 MLB data: post-season single scrape only — genuine CLV is structurally unavailable. "
                    "Alpha classes (TRUE_ALPHA/WEAK_ALPHA) are based on mean_bet_edge (model vs snapshot edge), "
                    "not true Closing Line Value."
                ),
            },
            "feature_impact_table": [r.as_dict() for r in research_results],
            "alpha_ranking": alpha_ranking,
            "clv_analysis": {
                # IMPORTANT: 'clv' values below are actually mean_bet_edge (avg model-vs-market edge
                # on selected bets), NOT genuine Closing Line Value. 2025 MLB data is single-snapshot
                # post-game proxy — no independent pregame decision + closing timestamps exist.
                # These values measure model edge vs a single market snapshot, not true CLV.
                "clv_note": (
                    "Values labeled 'clv' in this section are mean_bet_edge (mean edge on selected bets). "
                    "Genuine CLV is UNAVAILABLE for 2025 MLB (single post-game snapshot only). "
                    "Research framing: single-snapshot benchmark, not CLV research."
                ),
                "current_base_clv": next((r.clv for r in research_results if r.name == "base_only"), 0.0),
                "current_base_mean_bet_edge": next((r.clv for r in research_results if r.name == "base_only"), 0.0),
                "best_research_clv": clv_rank[0].clv if clv_rank else 0.0,
                "top_clv_models": [r.as_dict() for r in clv_rank[:5]],
            },
            "model_diagnosis": diagnosis,
            "production_gap_map": gap,
            # Explicit data tier summary — distinguishes subset coverage from full-universe conclusions.
            # Subset conclusions must NOT be extrapolated to the full MLB 2025 universe.
            "data_tier_summary": {
                "total_games": gap.get("status_distribution", {}).get("STRICT_VALID", 0)
                    + gap.get("status_distribution", {}).get("RESEARCH_VALID", 0)
                    + gap.get("status_distribution", {}).get("INVALID", 0),
                "research_valid_games": gap.get("status_distribution", {}).get("RESEARCH_VALID", 0),
                "strict_valid_games": gap.get("status_distribution", {}).get("STRICT_VALID", 0),
                "strict_timeline_games": gap.get("odds_tier_summary", {}).get("strict_timeline", 0),
                "closing_only_games": gap.get("odds_tier_summary", {}).get("closing_only", 0),
                "no_odds_games": gap.get("odds_tier_summary", {}).get("no_odds_data", 0),
                "clv_pipeline_status": (
                    "genuine_clv_available" if gap.get("odds_tier_summary", {}).get("strict_timeline", 0) > 0
                    else "single_snapshot_benchmark_only"
                ),
                "subset_inference_warning": (
                    "Research conclusions based on RESEARCH_VALID subset only. "
                    "CLV is UNAVAILABLE for all 2025 games (single post-game snapshot, no pregame data). "
                    "Metrics measure model edge vs single market snapshot — NOT closing line value. "
                    "Genuine CLV requires multi-timepoint pregame data from an external API."
                ),
            },
            "implementation_summary": {
                "mlb_research_mode": "NON_TRADABLE",
                "experiments_run": len(research_results),
                "strict_gate": strict_gate,
            },
            "final_verdict": (
                "PARTIAL READY (RESEARCH_VALID)"
                if (strict_gate["status"] == "BLOCKED BY DATA LAYER" and research_results)
                else "BLOCKED BY DATA"
                if strict_gate["status"] == "BLOCKED BY DATA LAYER"
                else ("PARTIAL READY" if not strict_gate["promotable"] else "PRODUCTION READY")
            ),
            "strict_results": [r.as_dict() for r in strict_results],
        }
        out = Path(report_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
