from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.governance import mlb_governance_flags
from wbc_backend.models.mlb_moneyline import american_to_implied_prob
from wbc_backend.research.mlb_regime_feature_redesign import build_regime_prediction_table_for_decision_quality
from wbc_backend.ux.report_style import build_report_header, build_report_summary


DECISION_LABELS = (
    "GOOD_BET_WIN",
    "GOOD_BET_LOSS",
    "BAD_BET_WIN",
    "BAD_BET_LOSS",
    "NO_BET",
)


@dataclass(frozen=True)
class DecisionQualityRow:
    game_id: str
    regime: str
    decision: str
    edge: float
    clv: float
    brier: float
    logloss: float
    calibration_flag: str
    predicted_home_win_prob: float
    market_home_prob: float
    decision_home_prob: float
    closing_home_prob: float
    actual_result: int
    passed_strict_gate: bool
    was_selected_for_bet: bool
    clv_available: bool
    # Tracks the source of the market snapshot used:
    # "decision_home_ml"   = genuine pre-game decision odds (CLV meaningful)
    # "closing_fallback"   = single post-game snapshot used as proxy (CLV=0, NOT real CLV)
    # "fallback_market_prob" = no odds data, pure model fallback
    # CLV is ONLY meaningful when clv_source == "decision_home_ml".
    clv_source: str = "fallback_market_prob"
    # Research framing: single-snapshot benchmark (model edge vs market snapshot).
    # CLV is unavailable for all 2025 MLB games (post-game single scrape only).
    benchmark_source: str = "single_snapshot"

    def as_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "regime": self.regime,
            "decision": self.decision,
            "edge": self.edge,
            "clv": self.clv,
            "brier": self.brier,
            "logloss": self.logloss,
            "calibration_flag": self.calibration_flag,
            "predicted_home_win_prob": self.predicted_home_win_prob,
            "market_home_prob": self.market_home_prob,
            "decision_home_prob": self.decision_home_prob,
            "closing_home_prob": self.closing_home_prob,
            "actual_result": self.actual_result,
            "passed_strict_gate": self.passed_strict_gate,
            "was_selected_for_bet": self.was_selected_for_bet,
            "clv_available": self.clv_available,
            "clv_source": self.clv_source,
            "benchmark_source": self.benchmark_source,
        }


def _logloss(prob: float, actual: int) -> float:
    p = float(np.clip(prob, 1e-7, 1 - 1e-7))
    y = int(actual)
    return float(-(y * math.log(p) + (1 - y) * math.log(1 - p)))


def _calibration_flag_from_brier(brier: float) -> str:
    if brier > 0.30:
        return "POOR_CALIBRATION"
    if brier < 0.20:
        return "GOOD_CALIBRATION"
    return "NORMAL"


def _decision_label(
    *,
    was_selected_for_bet: bool,
    clv_available: bool,
    edge: float,
    clv: float,
    actual_result: int,
) -> str:
    if not was_selected_for_bet:
        return "NO_BET"
    if not clv_available:
        return "NO_BET"
    is_good = (edge > 0.0) and (clv > 0.0)
    if is_good:
        return "GOOD_BET_WIN" if int(actual_result) == 1 else "GOOD_BET_LOSS"
    return "BAD_BET_WIN" if int(actual_result) == 1 else "BAD_BET_LOSS"


def _odds_prob_maps(csv_path: str, context_path: str | None) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    rows = load_mlb_game_data(csv_path=csv_path, context_path=context_path)
    decision: dict[str, float] = {}
    closing: dict[str, float] = {}
    decision_source: dict[str, str] = {}
    for row in rows:
        if row.features.odds.decision_home_ml.available:
            decision_prob = american_to_implied_prob(row.features.odds.decision_home_ml.value)
            if np.isfinite(decision_prob):
                decision[row.game_id] = float(decision_prob)
                decision_source[row.game_id] = "decision_home_ml"
        if row.features.odds.closing_home_ml.available:
            close_prob = american_to_implied_prob(row.features.odds.closing_home_ml.value)
            if np.isfinite(close_prob):
                closing[row.game_id] = float(close_prob)
                # Fallback: if no decision price, use closing as proxy (CLV=0, honest)
                if row.game_id not in decision:
                    decision[row.game_id] = float(close_prob)
                    decision_source[row.game_id] = "closing_fallback"
    return decision, closing, decision_source


def evaluate_mlb_decision_quality(
    *,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
    redesign_report_path: str = "data/wbc_backend/reports/mlb_regime_feature_redesign_report.json",
    report_path: str = "data/wbc_backend/reports/mlb_decision_quality_report.json",
) -> dict[str, Any]:
    pred_table = build_regime_prediction_table_for_decision_quality(
        csv_path=csv_path,
        context_path=context_path,
        redesign_report_path=redesign_report_path,
    )
    decision_map, close_map, decision_source_map = _odds_prob_maps(csv_path=csv_path, context_path=context_path)

    rows: list[DecisionQualityRow] = []
    for _, rec in pred_table.iterrows():
        game_id = str(rec["game_id"])
        pred = float(rec["predicted_home_win_prob"])
        fallback_market = float(rec["market_home_prob"])
        decision_prob = decision_map.get(game_id)
        # clv_available is True ONLY when genuine pre-game decision odds exist (not closing fallback).
        # Same-snapshot closing_fallback produces CLV=0 mechanically — not real CLV.
        clv_available = decision_source_map.get(game_id, "fallback_market_prob") == "decision_home_ml"
        market = float(decision_prob if decision_prob is not None else fallback_market)
        actual = int(rec["actual_result"])
        closing = float(close_map.get(game_id, market))
        edge = float(pred - market)
        clv = float(closing - market) if clv_available else 0.0
        brier = float((pred - actual) ** 2)
        logloss = _logloss(pred, actual)
        was_selected = bool(rec["was_selected_for_bet"])
        label = _decision_label(
            was_selected_for_bet=was_selected,
            clv_available=clv_available,
            edge=edge,
            clv=clv,
            actual_result=actual,
        )
        rows.append(
            DecisionQualityRow(
                game_id=game_id,
                regime=str(rec["regime_label"]),
                decision=label,
                edge=round(edge, 4),
                clv=round(clv, 4),
                brier=round(brier, 4),
                logloss=round(logloss, 4),
                calibration_flag=_calibration_flag_from_brier(brier),
                predicted_home_win_prob=round(pred, 4),
                market_home_prob=round(market, 4),
                decision_home_prob=round(market, 4),
                closing_home_prob=round(closing, 4),
                actual_result=actual,
                passed_strict_gate=bool(rec["passed_strict_gate"]),
                was_selected_for_bet=was_selected,
                clv_available=clv_available,
                clv_source=decision_source_map.get(game_id, "fallback_market_prob"),
                benchmark_source="single_snapshot",
            )
        )

    df = pd.DataFrame([r.as_dict() for r in rows])
    if df.empty:
        flags = mlb_governance_flags()
        payload = {
            "report_summary": build_report_summary(
                mode="PAPER_ONLY",
                safety="NO BETTING",
                scope="historical 2025 MLB",
                status="UNAVAILABLE_SINGLE_SNAPSHOT",
                next_step="Open the benchmark and alpha reports for paper-only analysis.",
                open_file="data/wbc_backend/reports/mlb_decision_quality_report.json",
                purpose="single-snapshot benchmark and paper-only research",
            ),
            "report_header": build_report_header(
                title="MLB DECISION QUALITY REPORT",
                mode="PAPER_ONLY",
                safety="NO BETTING",
                purpose="single-snapshot benchmark and paper-only research",
                scope="historical 2025 MLB",
                source="wbc_backend/evaluation/mlb_decision_quality.py",
                status="UNAVAILABLE_SINGLE_SNAPSHOT",
            ),
            "status": "NO_STRICT_PREDICTIONS",
            "per_game": [],
            "summary": {},
            "paper_mode": True,
            "execution_mode": flags["execution_mode"],
            "governance_flags": flags,
            "report_sections": {
                "paper_modeling_metrics": {},
                "sandbox_clv_diagnostics": {"clv_status": "UNAVAILABLE_SINGLE_SNAPSHOT"},
                "decision_quality_scale_status": {
                    "status": "UNAVAILABLE",
                    "reason": "no_strict_predictions",
                },
            },
        }
        Path(report_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    counts = {label: int((df["decision"] == label).sum()) for label in DECISION_LABELS}
    total_bets = max(1, int(df["was_selected_for_bet"].sum()))
    good_bet_count = counts["GOOD_BET_WIN"] + counts["GOOD_BET_LOSS"]
    bad_bet_count = counts["BAD_BET_WIN"] + counts["BAD_BET_LOSS"]

    good_mask = df["decision"].isin(["GOOD_BET_WIN", "GOOD_BET_LOSS"])
    bad_mask = df["decision"].isin(["BAD_BET_WIN", "BAD_BET_LOSS"])
    pick_mask = df["was_selected_for_bet"]

    def _pnl(row: pd.Series) -> float:
        if not bool(row["was_selected_for_bet"]):
            return 0.0
        return 1.0 if int(row["actual_result"]) == 1 else -1.0

    df["paper_pnl"] = df.apply(_pnl, axis=1)

    regime_rows = []
    for regime, rg in df.groupby("regime"):
        bets = rg[rg["was_selected_for_bet"]]
        regime_rows.append(
            {
                "regime": regime,
                "good_bet_rate": round(float((bets["decision"].isin(["GOOD_BET_WIN", "GOOD_BET_LOSS"]).mean()) if len(bets) else 0.0), 4),
                "avg_clv": round(float(bets["clv"].mean()) if len(bets) else 0.0, 4),
                "ROI": round(float(bets["paper_pnl"].mean()) if len(bets) else 0.0, 4),
                "sample_count": int(len(rg)),
                "bet_count": int(len(bets)),
            }
        )

    clv_source_series = pd.Series([decision_source_map.get(gid, "fallback_market_prob") for gid in df["game_id"]])
    clv_source_counts = {k: int(v) for k, v in clv_source_series.value_counts().items()}
    summary = {
        "label_counts": counts,
        "clv_distribution": {
            "positive": int((df["clv"] > 0).sum()),
            "zero": int((df["clv"] == 0).sum()),
            "negative": int((df["clv"] < 0).sum()),
            "available": int(df["clv_available"].sum()),
            "unavailable": int((~df["clv_available"]).sum()),
            "decision_source_counts": clv_source_counts,
        },
        # Snapshot source breakdown — what market data tier backs each game's evaluation.
        # "decision_home_ml": genuine pre-game decision odds (CLV meaningful, currently 0)
        # "closing_fallback": single post-game snapshot used as proxy (CLV=0, NOT real CLV)
        # "fallback_market_prob": no odds data, pure model fallback
        "clv_source_counts": clv_source_counts,
        "clv_available_rate": round(float(df["clv_available"].mean()), 4),
        # Odds timeline tier breakdown — data quality classification per game.
        # All 2025 MLB games are post_game_proxy_only (post-season single scrape).
        # genuine_decision_odds: games with real pregame decision odds (CLV possible).
        # closing_fallback: single snapshot used as benchmark reference (CLV=0, not informative).
        # no_odds: no odds data available at all.
        "odds_timeline_tier_breakdown": {
            "genuine_decision_odds": clv_source_counts.get("decision_home_ml", 0),
            "closing_fallback": clv_source_counts.get("closing_fallback", 0),
            "no_odds": clv_source_counts.get("fallback_market_prob", 0),
            "total_games_evaluated": int(len(df)),
            "genuine_clv_rate": round(clv_source_counts.get("decision_home_ml", 0) / max(1, len(df)), 4),
            "data_tier_note": (
                "All 2025 MLB games are single-snapshot post-game proxy (post-season scrape). "
                "canonical closing_home_ml is NULL (no genuine pregame snapshot). "
                "CLV is UNAVAILABLE for all 2025 games. "
                "Research framing: single-snapshot benchmark (model edge vs market snapshot). "
                "TSL spring 2026 has 38 MLB games with pregame snapshots but no 2025 outcomes."
            ),
        },
        # Single-snapshot benchmark summary — the correct research framing for 2025 data.
        # Measures model quality vs a single canonical market reference, without CLV validation.
        "benchmark_summary": {
            "benchmark_type": "single_snapshot",
            "snapshot_source": "post_game_proxy",
            "clv_available": False,
            "clv_note": (
                "CLV requires independent pre-game decision and closing timestamps. "
                "2025 data has a single post-game snapshot only — CLV is structurally unavailable. "
                "All edge/ROI metrics use model_prob vs single_snapshot_market_prob."
            ),
            "avg_edge_selected_bets": round(
                float(df.loc[pick_mask, "edge"].mean()) if pick_mask.any() else 0.0, 4
            ),
            "roi_all_bets": round(
                float(df.loc[pick_mask, "paper_pnl"].mean()) if pick_mask.any() else 0.0, 4
            ),
            "avg_brier": round(float(df["brier"].mean()), 4),
        },
        "decision_quality_ratios": {
            "good_bet_rate": round(float(good_bet_count / total_bets), 4),
            "bad_bet_rate": round(float(bad_bet_count / total_bets), 4),
        },
        "clv_by_category": {
            "avg_clv_good_bet": round(float(df.loc[good_mask, "clv"].mean()) if good_mask.any() else 0.0, 4),
            "avg_clv_bad_bet": round(float(df.loc[bad_mask, "clv"].mean()) if bad_mask.any() else 0.0, 4),
        },
        "roi_split": {
            "ROI_good_bet": round(float(df.loc[good_mask, "paper_pnl"].mean()) if good_mask.any() else 0.0, 4),
            "ROI_bad_bet": round(float(df.loc[bad_mask, "paper_pnl"].mean()) if bad_mask.any() else 0.0, 4),
            "ROI_all_bets": round(float(df.loc[pick_mask, "paper_pnl"].mean()) if pick_mask.any() else 0.0, 4),
        },
        "regime_breakdown": regime_rows,
    }

    flags = mlb_governance_flags()
    payload = {
        "report_summary": build_report_summary(
            mode="PAPER_ONLY",
            safety="NO BETTING",
            scope="historical 2025 MLB",
            status="PARTIAL" if summary["clv_distribution"]["available"] > 0 else "UNAVAILABLE_SINGLE_SNAPSHOT",
            next_step="Use this as a single-snapshot benchmark, not CLV.",
            open_file="data/wbc_backend/reports/mlb_decision_quality_report.json",
            purpose="single-snapshot benchmark and paper-only research",
        ),
        "report_header": build_report_header(
            title="MLB DECISION QUALITY REPORT",
            mode="PAPER_ONLY",
            safety="NO BETTING",
            purpose="single-snapshot benchmark and paper-only research",
            scope="historical 2025 MLB",
            source="wbc_backend/evaluation/mlb_decision_quality.py",
            status="UNAVAILABLE_SINGLE_SNAPSHOT" if summary["clv_distribution"]["available"] == 0 else "PARTIAL",
        ),
        "paper_mode": True,
        "execution_mode": flags["execution_mode"],
        "governance_flags": flags,
        "strict_only": True,
        "per_game": df.to_dict(orient="records"),
        "summary": summary,
        "report_sections": {
            "paper_modeling_metrics": {
                "roi_all_bets": summary["roi_split"]["ROI_all_bets"],
                "good_bet_rate": summary["decision_quality_ratios"]["good_bet_rate"],
                "bad_bet_rate": summary["decision_quality_ratios"]["bad_bet_rate"],
                "sample_count": int(len(df)),
            },
            "sandbox_clv_diagnostics": {
                # NOTE: CLV is UNAVAILABLE for all 2025 MLB games.
                # This section tracks snapshot sourcing, NOT real CLV diagnostics.
                # "closing_fallback" games use the same post-game snapshot for both
                # "decision" and "closing" references — CLV=0 is mechanical, not informative.
                # Real CLV requires independent pre-game decision + closing timestamps.
                "clv_distribution": summary["clv_distribution"],
                "decision_source_counts": summary["clv_distribution"]["decision_source_counts"],
                "scope": "strict_only_paper_mode",
                "clv_status": "UNAVAILABLE_SINGLE_SNAPSHOT",
                "note": (
                    "No genuine CLV for 2025 MLB. All games are post-game proxy single-snapshot. "
                    "Framing: single-snapshot benchmark (edge = model_prob - market_snapshot_prob)."
                ),
            },
            "decision_quality_scale_status": {
                "status": "UNAVAILABLE" if summary["clv_distribution"]["available"] == 0 else "PARTIAL",
                "reason": "historical_timeline_not_aligned_to_full_2025_universe"
                if summary["clv_distribution"]["available"] == 0
                else "subset_only",
            },
        },
        "live_recommendation": "disabled",
    }
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
