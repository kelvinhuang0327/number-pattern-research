from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wbc_backend.evaluation.mlb_decision_quality import evaluate_mlb_decision_quality
from wbc_backend.mlb_data.governance import mlb_governance_flags
from wbc_backend.models.mlb_regime_paper import run_mlb_regime_paper_mode
from wbc_backend.reports.spring_training_game_report import build_spring_training_tracking_summary
from wbc_backend.ux.report_style import build_report_header, build_report_summary


def _safe_mean(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.mean())


def _roi_from_frame(df: pd.DataFrame) -> float:
    picks = df[df["was_selected_for_bet"]]
    if picks.empty:
        return 0.0
    return _safe_mean(picks["paper_pnl"])


def _clv_sandbox(df: pd.DataFrame) -> dict[str, Any]:
    avail = df[df["clv_available"]]
    return {
        "available_count": int(len(avail)),
        "unavailable_count": int((~df["clv_available"]).sum()),
        "positive_count": int((avail["clv"] > 0).sum()) if not avail.empty else 0,
        "zero_count": int((avail["clv"] == 0).sum()) if not avail.empty else 0,
        "negative_count": int((avail["clv"] < 0).sum()) if not avail.empty else 0,
        "avg_clv_available_only": round(_safe_mean(avail["clv"]) if not avail.empty else 0.0, 4),
    }


def _period_slices(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df, df, df
    latest_date = df["game_date"].max()
    cur_week = latest_date.to_period("W-MON")
    prev_week = cur_week - 1
    cur_month = latest_date.to_period("M")
    prev_month = cur_month - 1
    week_cur_df = df[df["game_date"].dt.to_period("W-MON") == cur_week]
    week_prev_df = df[df["game_date"].dt.to_period("W-MON") == prev_week]
    month_cur_df = df[df["game_date"].dt.to_period("M") == cur_month]
    month_prev_df = df[df["game_date"].dt.to_period("M") == prev_month]
    return week_cur_df, week_prev_df, month_cur_df, month_prev_df


def _metric_block(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "sample_count": int(len(df)),
        "strict_only_roi": round(_roi_from_frame(df), 4),
        "strict_only_brier": round(_safe_mean(df["brier"]), 4) if not df.empty else 0.0,
        "strict_only_logloss": round(_safe_mean(df["logloss"]), 4) if not df.empty else 0.0,
        "sandbox_clv": _clv_sandbox(df),
    }


def _regime_trend_table(df: pd.DataFrame, week_cur_df: pd.DataFrame, week_prev_df: pd.DataFrame, month_cur_df: pd.DataFrame, month_prev_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    regimes = sorted(df["regime"].dropna().unique().tolist())
    for regime in regimes:
        all_rg = df[df["regime"] == regime]
        cur_w = week_cur_df[week_cur_df["regime"] == regime]
        prev_w = week_prev_df[week_prev_df["regime"] == regime]
        cur_m = month_cur_df[month_cur_df["regime"] == regime]
        prev_m = month_prev_df[month_prev_df["regime"] == regime]
        row = {
            "regime": regime,
            "sample_count_total": int(len(all_rg)),
            "sample_count_week_current": int(len(cur_w)),
            "sample_count_week_prior": int(len(prev_w)),
            "sample_count_month_current": int(len(cur_m)),
            "sample_count_month_prior": int(len(prev_m)),
            "sample_growth_week": int(len(cur_w) - len(prev_w)),
            "sample_growth_month": int(len(cur_m) - len(prev_m)),
            "roi_total": round(_roi_from_frame(all_rg), 4),
            "roi_week_current": round(_roi_from_frame(cur_w), 4),
            "roi_week_prior": round(_roi_from_frame(prev_w), 4),
            "roi_month_current": round(_roi_from_frame(cur_m), 4),
            "roi_month_prior": round(_roi_from_frame(prev_m), 4),
            "clv_sandbox_total": _clv_sandbox(all_rg),
            "clv_sandbox_week_current": _clv_sandbox(cur_w),
            "clv_sandbox_week_prior": _clv_sandbox(prev_w),
        }
        rows.append(row)
    return rows


def _regime_suggestion(row: dict[str, Any], fold_stability: float) -> str:
    sample = int(row["sample_count_total"])
    roi = float(row["roi_total"])
    clv_avail = int(row["clv_sandbox_total"]["available_count"])
    improving = float(row["roi_week_current"]) > float(row["roi_week_prior"])
    if sample >= 120 and roi > 0 and fold_stability < 0.15 and clv_avail > 0:
        return "keep"
    if sample >= 60 and (improving or roi > -0.03):
        return "watch"
    return "retire"


def _load_redesign_report(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


@dataclass(frozen=True)
class PaperMonitorSummary:
    status: str
    report_path: str
    regimes_monitored: int


def run_mlb_paper_tracking_monitor(
    *,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
    decision_quality_report_path: str = "data/wbc_backend/reports/mlb_decision_quality_report.json",
    regime_paper_report_path: str = "data/wbc_backend/reports/mlb_regime_paper_report.json",
    redesign_report_path: str = "data/wbc_backend/reports/mlb_regime_feature_redesign_report.json",
    spring_training_reports: list[dict[str, Any]] | None = None,
    output_path: str = "data/wbc_backend/reports/mlb_paper_tracking_report.json",
) -> PaperMonitorSummary:
    decision_report = evaluate_mlb_decision_quality(
        csv_path=csv_path,
        context_path=context_path,
        report_path=decision_quality_report_path,
    )
    regime_report = run_mlb_regime_paper_mode(
        csv_path=csv_path,
        context_path=context_path,
        report_path=regime_paper_report_path,
    )
    redesign_report = _load_redesign_report(redesign_report_path)
    spring_tracking = None
    if spring_training_reports is not None:
        spring_tracking = build_spring_training_tracking_summary(spring_training_reports)

    per_game = pd.DataFrame(decision_report.get("per_game", []))
    if per_game.empty:
        payload = {
            "status": "NO_DATA",
            "governance_flags": mlb_governance_flags(),
            "message": "No strict-only MLB paper records available.",
        }
        Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return PaperMonitorSummary(status="NO_DATA", report_path=output_path, regimes_monitored=0)

    per_game["game_date"] = pd.to_datetime(per_game["game_id"].str.extract(r"MLB-(\d{4}_\d{2}_\d{2})")[0].str.replace("_", "-"), errors="coerce")
    per_game = per_game.dropna(subset=["game_date"]).copy()
    per_game["game_date"] = pd.to_datetime(per_game["game_date"]).dt.tz_localize(None)

    week_cur_df, week_prev_df, month_cur_df, month_prev_df = _period_slices(per_game)
    overall = _metric_block(per_game)
    weekly = {
        "current_week": _metric_block(week_cur_df),
        "prior_week": _metric_block(week_prev_df),
    }
    monthly = {
        "current_month": _metric_block(month_cur_df),
        "prior_month": _metric_block(month_prev_df),
    }

    trend = {
        "week_over_week": {
            "roi_delta": round(weekly["current_week"]["strict_only_roi"] - weekly["prior_week"]["strict_only_roi"], 4),
            "brier_delta": round(weekly["current_week"]["strict_only_brier"] - weekly["prior_week"]["strict_only_brier"], 4),
            "logloss_delta": round(weekly["current_week"]["strict_only_logloss"] - weekly["prior_week"]["strict_only_logloss"], 4),
            "sample_delta": int(weekly["current_week"]["sample_count"] - weekly["prior_week"]["sample_count"]),
        },
        "month_over_month": {
            "roi_delta": round(monthly["current_month"]["strict_only_roi"] - monthly["prior_month"]["strict_only_roi"], 4),
            "brier_delta": round(monthly["current_month"]["strict_only_brier"] - monthly["prior_month"]["strict_only_brier"], 4),
            "logloss_delta": round(monthly["current_month"]["strict_only_logloss"] - monthly["prior_month"]["strict_only_logloss"], 4),
            "sample_delta": int(monthly["current_month"]["sample_count"] - monthly["prior_month"]["sample_count"]),
        },
    }

    regime_rows = _regime_trend_table(per_game, week_cur_df, week_prev_df, month_cur_df, month_prev_df)
    fold_by_regime = {
        item.get("regime"): float(item.get("fold_stability", 0.0))
        for item in regime_report.get("paper_mode_reporting", {}).get("by_regime", [])
    }
    regime_monitoring = []
    improving_regimes = []
    for row in regime_rows:
        fold_std = fold_by_regime.get(row["regime"], 0.0)
        suggestion = _regime_suggestion(row, fold_std)
        if row["roi_week_current"] > row["roi_week_prior"] and row["sample_growth_week"] >= 0:
            improving_regimes.append(row["regime"])
        regime_monitoring.append(
            {
                **row,
                "fold_stability": round(fold_std, 4),
                "suggestion": suggestion,
            }
        )

    retained_regimes = sorted(redesign_report.get("strict_only_results_after_redesign", {}).keys()) or sorted(per_game["regime"].unique().tolist())
    retained_summary = [r for r in regime_monitoring if r["regime"] in retained_regimes]

    flags = mlb_governance_flags()
    payload = {
        "report_summary": build_report_summary(
            mode=flags["execution_mode"],
            safety="NO LIVE BETTING",
            scope="historical 2025 MLB",
            status="paper-only / benchmark only",
            next_step="Open the paper, alpha, and decision-quality reports for detail.",
            open_file="data/wbc_backend/reports/mlb_paper_tracking_report.json",
            purpose="governance monitoring for paper-only research",
        ),
        "report_header": build_report_header(
            title="MLB PAPER TRACKING REPORT",
            mode=flags["execution_mode"],
            safety="NO LIVE BETTING",
            purpose="governance monitoring for paper-only research",
            scope="historical 2025 MLB",
            source="wbc_backend/research/mlb_paper_monitor.py",
            status="paper-only / benchmark only",
        ),
        "status": "OK",
        "governance_flags": flags,
        "governance_visibility": {
            "execution_mode": flags["execution_mode"],
            "clv_mode": flags["clv_mode"],
            "decision_quality_scale": flags["decision_quality_scale"],
            "promotion_guard": flags["promotion_guard"],
            "live_recommendation": flags["live_recommendation"],
        },
        "report_schema": {
            "overall_strict_metrics": ["strict_only_roi", "strict_only_brier", "strict_only_logloss"],
            "sandbox_clv_metrics": ["available_count", "unavailable_count", "positive_count", "zero_count", "negative_count", "avg_clv_available_only"],
            "trend_windows": ["current_week", "prior_week", "current_month", "prior_month"],
            "regime_monitoring_fields": ["sample_count_total", "roi_total", "clv_sandbox_total", "fold_stability", "suggestion"],
        },
        "overall_strict_metrics": overall,
        "weekly_tracking": weekly,
        "monthly_tracking": monthly,
        "trend_monitoring": {
            **trend,
            "sample_growth_by_regime": [
                {
                    "regime": r["regime"],
                    "week_growth": r["sample_growth_week"],
                    "month_growth": r["sample_growth_month"],
                }
                for r in regime_monitoring
            ],
            "regimes_improving_toward_tradable_thresholds": improving_regimes,
        },
        "regime_monitoring": {
            "retained_research_regimes": retained_regimes,
            "summary": retained_summary,
        },
        "frozen_recommendation": "KEEP_MLB_FROZEN",
        "notes": [
            "MLB paper tracking is for research monitoring only.",
            "Sandbox CLV metrics do not imply full-universe CLV availability.",
            "No live recommendation, sizing, or execution is permitted under current governance.",
        ],
    }
    if spring_tracking is not None:
        payload["spring_training_tracking"] = spring_tracking
        payload["report_schema"]["spring_training_tracking"] = [
            "sample_count",
            "analysis_count",
            "prediction_distribution",
            "confidence_distribution",
            "uncertainty_flags",
            "metrics_pool",
            "roi",
            "clv",
        ]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return PaperMonitorSummary(status="OK", report_path=output_path, regimes_monitored=len(regime_monitoring))
