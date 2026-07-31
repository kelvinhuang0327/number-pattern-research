from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import statistics
from typing import Any

from wbc_backend.pipeline.game_classification import GameType, classify_game_type
from wbc_backend.mlb_data.governance import spring_training_governance_flags
from wbc_backend.ux.report_style import build_report_header, build_report_summary, render_report_banner, render_report_summary, render_section_block


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _safe_len(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    return 0


def _confidence_from_result(result: Any) -> float:
    model_outputs = getattr(result, "model_outputs", None) or []
    confidences = []
    for output in model_outputs:
        try:
            confidences.append(float(getattr(output, "confidence", 0.0)))
        except Exception:
            continue
    if confidences:
        return round(sum(confidences) / len(confidences), 4)
    try:
        low, high = getattr(result, "confidence_interval_95", (0.0, 0.0))
        width = max(0.0, float(high) - float(low))
        return round(max(0.0, 1.0 - width), 4)
    except Exception:
        return 0.0


def _lookup_starting_pitcher(record: Any, side: str) -> str:
    for attr in (f"{side}_sp", f"{side}_starter"):
        value = _safe_getattr(record, attr, None)
        if value is None:
            continue
        name = getattr(value, "name", value)
        text = str(name or "").strip()
        if text:
            return text
    return "unknown"


def _market_snapshot(record: Any) -> dict[str, Any]:
    odds = _safe_getattr(record, "odds", None) or {}
    market_home_prob = _safe_getattr(record, "market_home_prob", None)
    market_snapshot = {
        "market_home_prob": round(float(market_home_prob), 4) if market_home_prob is not None else None,
        "ou_line": _safe_getattr(record, "ou_line", None),
        "home_ml": odds.get("home_ml") if isinstance(odds, dict) else None,
        "away_ml": odds.get("away_ml") if isinstance(odds, dict) else None,
        "book": odds.get("book") if isinstance(odds, dict) else None,
    }
    return market_snapshot


def _risk_flags(record: Any) -> list[str]:
    flags: list[str] = []
    home_lineup = _safe_getattr(record, "home_lineup", None)
    away_lineup = _safe_getattr(record, "away_lineup", None)
    if _safe_len(home_lineup) < 9 or _safe_len(away_lineup) < 9:
        flags.append("lineup_instability")
    if not _lookup_starting_pitcher(record, "home") or _lookup_starting_pitcher(record, "home") == "unknown":
        flags.append("home_pitcher_uncertainty")
    if not _lookup_starting_pitcher(record, "away") or _lookup_starting_pitcher(record, "away") == "unknown":
        flags.append("away_pitcher_uncertainty")
    if _safe_getattr(record, "bullpen_usage", None) is None and _safe_getattr(record, "bullpen_usage_last_3d", None) is None:
        flags.append("bullpen_usage_uncertainty")
    flags.extend([
        "substitution_randomness",
        "pitcher_rotation_uncertainty",
        "lower_predictive_reliability",
    ])
    return list(dict.fromkeys(flags))


def render_spring_training_game_report(report: dict[str, Any]) -> str:
    header = report.get("header", {})
    matchup = report.get("matchup", {})
    analysis = report.get("shared_analysis_summary", {})
    risk = report.get("sandbox_risk_section", {})
    output = report.get("output_section", {})
    lines = [
        render_report_banner(
            build_report_header(
                title=header.get("title", "SPRING TRAINING"),
                mode=header.get("mode", "SANDBOX_ONLY"),
                safety=header.get("betting_advice", "NOT RECOMMENDED FOR BETTING"),
                purpose="shared analysis with sandbox-only governance",
                scope="spring training",
                source="wbc_backend/reports/spring_training_game_report.py",
                status="sandbox-only / not for betting",
                generated_at=report.get("generated_at"),
            )
        ).rstrip(),
        render_report_summary(report.get("report_summary", {})),
        render_section_block(
            "MATCHUP",
            [
                f"  Game ID:        {matchup.get('game_id', '')}",
                f"  Matchup:        {matchup.get('away_team', 'AWAY')} @ {matchup.get('home_team', 'HOME')}",
                f"  Start Time:     {matchup.get('game_time_utc', '')}",
                f"  Game Type:      {report.get('game_type', 'SPRING_TRAINING')}",
            ],
        ),
        render_section_block(
            "SHARED ANALYSIS SUMMARY",
            [
                f"  Home Win Prob:  {analysis.get('home_win_prob', 0.0):.1%}",
                f"  Away Win Prob:  {analysis.get('away_win_prob', 0.0):.1%}",
                f"  Market Edge:    {analysis.get('edge_vs_market', 0.0):+.4f}",
                f"  Expected Total: {analysis.get('expected_total_runs', 0.0):.2f}",
                f"  Starter Home:   {analysis.get('starter_info', {}).get('home', 'unknown')}",
                f"  Starter Away:   {analysis.get('starter_info', {}).get('away', 'unknown')}",
                f"  Lineup Home:    {analysis.get('lineup_context', {}).get('home_lineup_size', 0)}",
                f"  Lineup Away:    {analysis.get('lineup_context', {}).get('away_lineup_size', 0)}",
                f"  Bullpen Note:   {analysis.get('bullpen_context', {}).get('note', 'n/a')}",
                f"  Market Snapshot: {analysis.get('market_snapshot', {})}",
            ],
        ),
        render_section_block(
            "SANDBOX RISK SECTION",
            [
                f"  Risk Level:     {risk.get('overall_risk_level', 'HIGH')}",
                *[f"  - {flag}" for flag in risk.get("risk_flags", [])],
            ],
        ),
        render_section_block(
            "OUTPUT SECTION",
            [
                f"  Paper Side:     {output.get('paper_side', 'skip')}",
                f"  Confidence:     {output.get('confidence', 0.0):.1%}",
                f"  Recommendation: {output.get('recommendation', 'NO_BET')}",
                f"  Live Rec:       {output.get('live_recommendation', 'disabled')}",
                f"  Live Sizing:    {output.get('live_sizing', 'disabled')}",
                f"  Live Execution: {output.get('live_execution', 'disabled')}",
                "",
                "NOTE: Spring training is sandbox-only and must not be used for betting, ROI, or CLV evaluation.",
            ],
        ),
    ]
    return "\n".join(lines)


def build_spring_training_game_report(
    *,
    record: Any,
    orchestrator_result: Any,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    game_type = classify_game_type(record)
    if game_type != GameType.SPRING_TRAINING:
        raise ValueError("build_spring_training_game_report only accepts spring training games")

    game_id = str(_safe_getattr(record, "game_id", "UNKNOWN"))
    home_team = str(_safe_getattr(record, "home_team", "HOME"))
    away_team = str(_safe_getattr(record, "away_team", "AWAY"))
    market_snapshot = _market_snapshot(record)
    confidence = _confidence_from_result(orchestrator_result)
    home_prob = float(getattr(orchestrator_result, "home_win_prob", 0.5))
    away_prob = float(getattr(orchestrator_result, "away_win_prob", 0.5))
    edge_vs_market = float(getattr(orchestrator_result, "edge_vs_market", 0.0))
    paper_side = "home" if home_prob > away_prob else "away"
    if abs(edge_vs_market) < 0.02:
        paper_side = "skip"

    risk_flags = _risk_flags(record)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "game_type": game_type.value,
        "header": {
            "title": "SPRING TRAINING",
            "mode": "SANDBOX_ONLY",
            "betting_advice": "NOT RECOMMENDED FOR BETTING",
        },
        "report_summary": build_report_summary(
            mode="SANDBOX_ONLY",
            safety="NOT RECOMMENDED FOR BETTING",
            scope="spring training",
            status="sandbox-only / not for betting",
            next_step="Use this for observation only; do not place bets.",
            open_file="data/wbc_backend/reports/tsl_timeline_research_asset.json",
            purpose="shared analysis with sandbox-only governance",
        ),
        "report_header": build_report_header(
            title="SPRING TRAINING",
            mode="SANDBOX_ONLY",
            safety="NOT RECOMMENDED FOR BETTING",
            purpose="shared analysis with sandbox-only governance",
            scope="spring training",
            source="wbc_backend/reports/spring_training_game_report.py",
            status="sandbox-only / not for betting",
        ),
        "governance_flags": spring_training_governance_flags(),
        "matchup": {
            "game_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "game_time_utc": str(_safe_getattr(record, "game_time_utc", "")),
            "round_name": str(_safe_getattr(record, "round_name", "Warmup")),
            "league": str(_safe_getattr(record, "league", "")),
        },
        "shared_analysis_summary": {
            "home_win_prob": round(home_prob, 4),
            "away_win_prob": round(away_prob, 4),
            "edge_vs_market": round(edge_vs_market, 4),
            "expected_total_runs": round(float(getattr(orchestrator_result, "expected_total_runs", 0.0)), 2),
            "starter_info": {
                "home": _lookup_starting_pitcher(record, "home"),
                "away": _lookup_starting_pitcher(record, "away"),
            },
            "lineup_context": {
                "home_lineup_size": _safe_len(_safe_getattr(record, "home_lineup", None)),
                "away_lineup_size": _safe_len(_safe_getattr(record, "away_lineup", None)),
            },
            "bullpen_context": {
                "home_bullpen_count": _safe_len(_safe_getattr(record, "home_bullpen", None)),
                "away_bullpen_count": _safe_len(_safe_getattr(record, "away_bullpen", None)),
                "note": "spring_training_usage_is_highly_variable",
            },
            "market_snapshot": market_snapshot,
            "analysis_basis": [getattr(m, "model_name", str(m)) for m in getattr(orchestrator_result, "model_outputs", [])],
        },
        "sandbox_risk_section": {
            "overall_risk_level": "HIGH",
            "risk_flags": risk_flags,
            "reason": "Spring Training lineups, substitutions, and pitcher usage are unstable by design.",
        },
        "output_section": {
            "paper_side": paper_side,
            "confidence": confidence,
            "recommendation": "NO_BET",
            "live_recommendation": "disabled",
            "live_sizing": "disabled",
            "live_execution": "disabled",
            "execution_mode": "SANDBOX_ONLY",
            "betting_advice": "NOT_RECOMMENDED_FOR_BETTING",
            "metrics_pool": "SPRING_SANDBOX_ONLY",
        },
    }
    report["markdown_report"] = render_spring_training_game_report(report)
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_spring_training_tracking_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    sample_count = len(reports)
    if sample_count == 0:
        return {
            "sample_count": 0,
            "analysis_count": 0,
            "prediction_distribution": {},
            "confidence_distribution": {
                "mean": 0.0,
                "median": 0.0,
                "min": 0.0,
                "max": 0.0,
            },
            "uncertainty_flags": {},
            "metrics_pool": "SPRING_SANDBOX_ONLY",
            "roi": "unavailable",
            "clv": "unavailable",
        }

    recommendations = Counter()
    confidences: list[float] = []
    flags = Counter()
    for report in reports:
        output = report.get("output_section", {}) if isinstance(report, dict) else {}
        recommendations[str(output.get("recommendation", "NO_BET"))] += 1
        try:
            confidences.append(float(output.get("confidence", 0.0)))
        except Exception:
            confidences.append(0.0)
        for flag in (report.get("sandbox_risk_section", {}) or {}).get("risk_flags", []):
            flags[str(flag)] += 1

    return {
        "sample_count": sample_count,
        "analysis_count": sample_count,
        "prediction_distribution": dict(recommendations),
        "confidence_distribution": {
            "mean": round(sum(confidences) / sample_count, 4),
            "median": round(float(statistics.median(confidences)), 4),
            "min": round(min(confidences), 4),
            "max": round(max(confidences), 4),
        },
        "uncertainty_flags": dict(flags),
        "metrics_pool": "SPRING_SANDBOX_ONLY",
        "roi": "unavailable",
        "clv": "unavailable",
        "notes": [
            "Spring training tracking is sandbox-only.",
            "No ROI, CLV, or promotion metrics are computed for this pool.",
        ],
    }
