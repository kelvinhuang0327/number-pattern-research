from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _section(title: str, lines: list[str]) -> str:
    out = [
        "",
        "━" * 72,
        title,
        "━" * 72,
    ]
    out.extend(lines)
    return "\n".join(out)


def _mode_card(
    *,
    title: str,
    mode: str,
    command: str,
    safe_for_betting: str,
    summary_lines: list[str],
    next_step: str,
) -> str:
    lines = [
        f"  Mode:            {mode}",
        f"  Recommended Cmd: {command}",
        f"  Betting Status:  {safe_for_betting}",
    ]
    lines.extend([f"  {line}" for line in summary_lines])
    lines.append(f"  Next Step:       {next_step}")
    return _section(title, lines)


def _wbc_summary() -> list[str]:
    review = _load_text(REPORTS / "WBC_Review_Meeting_Latest.md")
    postgame_count = 0
    postgame_path = REPORTS / "postgame_results.jsonl"
    if postgame_path.exists():
        postgame_count = len([line for line in postgame_path.read_text(encoding="utf-8").splitlines() if line.strip()])
    headline = "WBC production pipeline"
    if review:
        for line in review.splitlines():
            if line.strip().startswith("## "):
                headline = line.replace("##", "").strip()
                break
    return [
        f"Status:          {headline}",
        f"Postgame Records: {postgame_count}",
        "Scope:           Official WBC / production only",
    ]


def _mlb_paper_summary() -> list[str]:
    decision = _load_json(REPORTS / "mlb_decision_quality_report.json")
    alpha = _load_json(REPORTS / "mlb_alpha_discovery_report.json")
    tracking = _load_json(REPORTS / "mlb_paper_tracking_report.json")
    summary = decision.get("summary", {})
    report_sections = decision.get("report_sections", {})
    clv_diag = report_sections.get("sandbox_clv_diagnostics", {})
    scale = report_sections.get("decision_quality_scale_status", {})
    vis = tracking.get("governance_visibility", {})
    return [
        f"Decision Scale:  {scale.get('status', 'UNKNOWN')}",
        f"CLV Status:      {clv_diag.get('clv_status', 'UNKNOWN')}",
        f"CLV Available:   {summary.get('clv_available_rate', 'n/a')}",
        f"Alpha Verdict:   {alpha.get('final_verdict', 'n/a')}",
        f"Mode:            {vis.get('execution_mode', 'PAPER_ONLY')}",
        "Use for:         single-snapshot benchmark / paper-only research",
    ]


def _spring_summary() -> list[str]:
    timeline = _load_json(REPORTS / "tsl_timeline_research_asset.json")
    tracking = _load_json(REPORTS / "mlb_paper_tracking_report.json")
    spring_tracking = tracking.get("spring_training_tracking", {})
    timeline_breakdown = timeline.get("timeline_tier_breakdown", {})
    return [
        f"Timeline Scope:  {timeline.get('scope', 'spring research asset')}",
        f"Movement Games:  {timeline.get('games_with_actual_line_movement', 'n/a')}",
        f"2+ Snapshots:    {timeline_breakdown.get('timeline_2plus', 'n/a')}",
        f"Sandbox Sample:  {spring_tracking.get('sample_count', 'n/a')}",
        "Status:          sandbox-only / not for betting",
    ]


def build_product_dashboard(mode: str | None = None) -> str:
    mode_key = (mode or "all").strip().lower()
    parts = [
        "=" * 72,
        "BETTING-POOL PRODUCT DASHBOARD",
        "A single place to decide what to run, what it means, and what not to bet.",
        "=" * 72,
        "",
        "Start here:",
        "  1. Dashboard -> python scripts/run_mode.py --mode dashboard",
        "  2. WBC production -> python scripts/run_mode.py --mode wbc",
        "  3. MLB paper-only -> python scripts/run_mode.py --mode mlb-paper",
        "  4. MLB benchmark -> python scripts/run_mode.py --mode mlb-benchmark",
        "  5. MLB alpha discovery -> python scripts/run_mode.py --mode mlb-alpha",
        "  6. Spring sandbox -> python scripts/run_mode.py --mode spring",
        "  7. Report center -> python scripts/report_center.py",
        "",
        "Mode legend:",
        "  WBC            = production",
        "  MLB paper-only = no betting, no live sizing, no execution",
        "  Spring         = SANDBOX_ONLY / NOT RECOMMENDED FOR BETTING",
        "  Reports        = latest outputs by mode",
    ]

    if mode_key in {"all", "wbc"}:
        parts.append(
            _mode_card(
                title="WBC PRODUCTION",
                mode="WBC",
                command="python scripts/run_mode.py --mode wbc",
                safe_for_betting="YES, production path",
                summary_lines=_wbc_summary(),
                next_step="Run the latest WBC match analysis and review the formal report output.",
            )
        )
    if mode_key in {"all", "mlb", "paper"}:
        parts.append(
            _mode_card(
                title="MLB PAPER-ONLY RESEARCH",
                mode="PAPER_ONLY",
                command="python scripts/run_mode.py --mode mlb-paper",
                safe_for_betting="NO",
                summary_lines=_mlb_paper_summary(),
                next_step="Open the generated JSON reports if you need deeper research detail.",
            )
        )
        parts.append(
            _section(
                "MLB SINGLE-SNAPSHOT BENCHMARK",
                [
                    "  Mode:            benchmark only",
                    "  Command:         python scripts/run_mode.py --mode mlb-benchmark",
                    "  Betting Status:  NO CLV / NO live betting",
                    "  Scope:           model-vs-snapshot comparison only",
                ],
            )
        )
    if mode_key in {"all", "spring"}:
        parts.append(
            _mode_card(
                title="SPRING TRAINING SANDBOX",
                mode="SANDBOX_ONLY",
                command="python scripts/run_mode.py --mode spring",
                safe_for_betting="NO",
                summary_lines=_spring_summary(),
                next_step="Use this to observe and collect spring data, not to place bets.",
            )
        )

    if mode_key in {"all", "reports"}:
        parts.append(
            _section(
                "REPORT CENTER",
                [
                    "  Command:         python scripts/report_center.py",
                    "  Purpose:         open the latest report snapshot by mode",
                    "  WBC:             review meeting / production status",
                    "  MLB:             decision quality + alpha + paper monitor",
                    "  Spring:          timeline research asset / sandbox tracking",
                ],
            )
        )

    parts.append(
        _section(
            "REFERENCE",
            [
                "  Mode guide:      docs/MODE_GUIDE.md",
                "  WBC review:      data/wbc_backend/reports/WBC_Review_Meeting_Latest.md",
                "  MLB decision:    data/wbc_backend/reports/mlb_decision_quality_report.json",
                "  MLB alpha:       data/wbc_backend/reports/mlb_alpha_discovery_report.json",
                "  Spring tracking:  data/wbc_backend/reports/mlb_paper_tracking_report.json",
                "  Report center:    data/wbc_backend/reports/tsl_timeline_research_asset.json",
            ],
        )
    )
    return "\n".join(parts)
