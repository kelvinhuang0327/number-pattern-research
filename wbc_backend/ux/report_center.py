from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .report_style import render_section_block

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "data" / "wbc_backend" / "reports"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _section(title: str, lines: list[str]) -> str:
    return render_section_block(title, lines, width=72)


def _summary_from_report(
    report: dict[str, Any],
    *,
    default_mode: str,
    default_safety: str,
    default_scope: str,
    default_status: str,
    default_next_step: str,
    default_open_file: str,
    default_purpose: str,
) -> dict[str, Any]:
    summary = report.get("report_summary") or {}
    if summary:
        return summary
    header = report.get("report_header") or {}
    return {
        "mode": header.get("mode", default_mode),
        "safety": header.get("safety", default_safety),
        "scope": header.get("scope", default_scope),
        "status": header.get("status", default_status),
        "next_step": default_next_step,
        "open_file": default_open_file,
        "purpose": header.get("purpose", default_purpose),
    }


def _wbc_block() -> list[str]:
    review = _load_text(REPORTS / "WBC_Review_Meeting_Latest.md")
    first_heading = "unknown"
    if review:
        for line in review.splitlines():
            if line.startswith("## "):
                first_heading = line.replace("##", "").strip()
                break
    return [
        f"Latest Review:  {first_heading}",
        f"Report File:    data/wbc_backend/reports/WBC_Review_Meeting_Latest.md",
        "Status:         production / verified",
    ]


def _mlb_block() -> list[str]:
    decision = _load_json(REPORTS / "mlb_decision_quality_report.json")
    alpha = _load_json(REPORTS / "mlb_alpha_discovery_report.json")
    tracking = _load_json(REPORTS / "mlb_paper_tracking_report.json")
    coverage = _load_json(REPORTS / "mlb_pregame_coverage_report.json")
    qa = _load_json(REPORTS / "mlb_2025_odds_timeline_qa_report.json")
    summary = _summary_from_report(
        decision or alpha or tracking,
        default_mode="PAPER_ONLY",
        default_safety="NO BETTING",
        default_scope="historical 2025 MLB",
        default_status="paper-only / benchmark only",
        default_next_step="Open the decision quality and alpha discovery reports for detail.",
        default_open_file="data/wbc_backend/reports/mlb_decision_quality_report.json",
        default_purpose="single-snapshot benchmark and paper-only research",
    )
    return [
        f"Summary Mode:      {summary.get('mode', 'UNKNOWN')}",
        f"Decision Quality:  {decision.get('report_sections', {}).get('decision_quality_scale_status', {}).get('status', 'UNKNOWN')}",
        f"CLV Status:        {decision.get('report_sections', {}).get('sandbox_clv_diagnostics', {}).get('clv_status', 'UNKNOWN')}",
        f"Alpha Verdict:     {alpha.get('final_verdict', 'n/a')}",
        f"Paper Monitor:     {tracking.get('governance_visibility', {}).get('execution_mode', 'PAPER_ONLY')}",
        f"Timeline QA:       strict={qa.get('strict_4point_coverage_rate', 'n/a')} closing_only={qa.get('closing_only_coverage_rate', 'n/a')}",
        f"Pregame Coverage:  {coverage.get('data_status', 'n/a')}",
        f"Next Step:         {summary.get('next_step', 'n/a')}",
        "Status:            paper-only / benchmark only",
    ]


def _spring_block() -> list[str]:
    tracking = _load_json(REPORTS / "mlb_paper_tracking_report.json")
    timeline = _load_json(REPORTS / "tsl_timeline_research_asset.json")
    spring = tracking.get("spring_training_tracking", {})
    summary = _summary_from_report(
        tracking,
        default_mode="SANDBOX_ONLY",
        default_safety="NOT RECOMMENDED FOR BETTING",
        default_scope="spring training",
        default_status="sandbox-only / not for betting",
        default_next_step="Observe and collect spring snapshots; do not place bets.",
        default_open_file="data/wbc_backend/reports/tsl_timeline_research_asset.json",
        default_purpose="shared analysis with sandbox-only governance",
    )
    return [
        f"Summary Mode:      {summary.get('mode', 'SANDBOX_ONLY')}",
        f"Timeline Scope:    {timeline.get('scope', 'n/a')}",
        f"Movement Games:    {timeline.get('games_with_actual_line_movement', 'n/a')}",
        f"Sandbox Sample:    {spring.get('sample_count', 'n/a')}",
        f"Recommendation:    {spring.get('metrics_pool', 'SPRING_SANDBOX_ONLY')}",
        f"Next Step:         {summary.get('next_step', 'n/a')}",
        "Status:            sandbox-only / not for betting",
    ]


def build_report_center() -> str:
    parts = [
        "=" * 72,
        "BETTING-POOL REPORT CENTER",
        "A single place to inspect the latest outputs for each mode.",
        "=" * 72,
        "",
        "Use this when you already know which mode you are in and want the latest output file.",
    ]
    parts.append(_section("WBC PRODUCTION", _wbc_block()))
    parts.append(_section("MLB PAPER / BENCHMARK", _mlb_block()))
    parts.append(_section("SPRING TRAINING SANDBOX", _spring_block()))
    parts.append(
        _section(
            "FILES TO OPEN",
            [
                "  WBC:      data/wbc_backend/reports/WBC_Review_Meeting_Latest.md",
                "  MLB Q:    data/wbc_backend/reports/mlb_decision_quality_report.json",
                "  MLB α:    data/wbc_backend/reports/mlb_alpha_discovery_report.json",
                "  MLB MT:   data/wbc_backend/reports/mlb_paper_tracking_report.json",
                "  Spring:   data/wbc_backend/reports/tsl_timeline_research_asset.json",
            ],
        )
    )
    return "\n".join(parts)
