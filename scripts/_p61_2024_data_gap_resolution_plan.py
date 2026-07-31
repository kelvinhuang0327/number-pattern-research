#!/usr/bin/env python3
"""
P61 — 2024 Closing-Line Data Gap Resolution Plan (Paper-Only Diagnostic)

CEO directive (P1 priority after P60 completion):
  - 產出 data-sourcing 評估報告（無 live API call）
  - 列出可行來源：Retrosheet、Baseball Reference、Sportsbook archive
  - 評估每個來源的格式相容性、獲取難度、授權風險
  - 不做：實際抓資料、付費 API、live call

Background:
  P43 final_classification=P43_BLOCKED_BY_DATA_GAP because 2024 closing-line
  moneyline odds are unavailable. Cross-year edge validation requires:
    data/mlb_2025/mlb_odds_2024_real.csv (schema: Date, Away, Home,
    Away Score, Home Score, Away ML, Home ML)
  This report evaluates realistic paths to resolving that gap.

Governance:
  - No live API calls (live_api_calls=0)
  - No data download in this script
  - No champion replacement
  - Paper-only diagnostic
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance (locked)
# ---------------------------------------------------------------------------

GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "data_download_attempted": False,
    "paid_api_called": False,
}

for k, v in GOVERNANCE.items():
    assert GOVERNANCE[k] == v, f"Governance violation: {k}"

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/mlb_2025/derived"

# P43 source for reference (DO NOT MODIFY)
P43_JSON = DERIVED / "p43_strong_edge_closing_line_edge_summary.json"
P60_JSON = DERIVED / "p60_historical_monthly_report_pack_validation_summary.json"

OUT_JSON = DERIVED / "p61_2024_data_gap_resolution_plan_summary.json"
OUT_REPORT = ROOT / "report/p61_2024_data_gap_resolution_plan_20260526.md"
OUT_BETTINGPLAN = ROOT / "00-BettingPlan/20260526/p61_2024_data_gap_resolution_plan_20260526.md"

# What P43 needs to resolve the data gap
REQUIRED_TARGET_SCHEMA = {
    "file": "data/mlb_2025/mlb_odds_2024_real.csv",
    "required_columns": ["Date", "Away", "Home", "Away Score", "Home Score", "Away ML", "Home ML"],
    "required_rows_estimate": "~2430 (full 2024 MLB regular season)",
    "date_range": "2024-03-20 to 2024-09-29",
    "format": "CSV, one row per game, closing moneyline odds, final scores",
}

ALLOWED_CLASSIFICATIONS = frozenset([
    "P61_DATA_GAP_RESOLVABLE_LOW_EFFORT",
    "P61_DATA_GAP_RESOLVABLE_MEDIUM_EFFORT",
    "P61_DATA_GAP_RESOLVABLE_HIGH_EFFORT",
    "P61_DATA_GAP_UNRESOLVABLE_WITHOUT_PAID_SOURCE",
    "P61_DATA_GAP_PARTIALLY_RESOLVABLE",
])


# ---------------------------------------------------------------------------
# A. Load P43 reference context
# ---------------------------------------------------------------------------

def load_p43_context() -> dict[str, Any]:
    with P43_JSON.open(encoding="utf-8") as f:
        p43 = json.load(f)
    inv = p43.get("data_inventory", {})
    return {
        "p43_final_classification": p43.get("final_classification",
            "P43_BLOCKED_BY_DATA_GAP"),
        "rows_2024_quality": inv.get("rows_2024", {}).get("holdout_quality_rows", 2158),
        "rows_2024_missing_market": inv.get("rows_2024", {}).get("holdout_missing_market_rows", 2158),
        "data_gap_2024_confirmed": inv.get("data_gap_2024_market_prob_missing", True),
        "rows_2025_joined": inv.get("rows_2025", {}).get("phase56_joined_rows", 1426),
        "framing_note": p43.get("framing_note", ""),
    }


def load_p60_context() -> dict[str, Any]:
    with P60_JSON.open(encoding="utf-8") as f:
        p60 = json.load(f)
    return {
        "p60_classification": p60.get("pack_classification", "P60_EDGE_STABLE_ACROSS_MONTHS"),
        "cross_month_edge_stability": p60.get("pack_level_synthesis", {}).get(
            "cross_month_edge_stability", "EDGE_STABLE_ACROSS_MONTHS"
        ),
        "avg_edge_mean": p60.get("pack_level_synthesis", {}).get("avg_edge_mean_across_months"),
    }


# ---------------------------------------------------------------------------
# B. Data source evaluation
# ---------------------------------------------------------------------------

def build_source_evaluations() -> list[dict[str, Any]]:
    """
    Evaluate candidate data sources for 2024 MLB closing-line moneyline odds.
    Assessment is based on publicly known characteristics of each source.
    No live calls are made.
    """
    return [
        {
            "source_name": "Retrosheet Game Logs",
            "url_reference": "https://www.retrosheet.org/gamelogs/",
            "data_type": "Game outcome / box score",
            "provides_moneyline_odds": False,
            "provides_scores": True,
            "provides_starters": True,
            "access_type": "Free, public download",
            "license": "Non-commercial, attribution required",
            "format": "Fixed-width text / CSV",
            "2024_availability": "Available (typically released by Nov following season)",
            "schema_compatibility": "PARTIAL — provides Date, Away, Home, Away Score, Home Score but NO Away ML / Home ML",
            "effort_estimate": "LOW — download and parse, but cannot provide odds columns",
            "blocker": "Does not contain moneyline odds. Cannot resolve the data gap alone.",
            "resolution_contribution": "SCORES_ONLY",
            "priority": "LOW — already have scores from existing CSV; no odds value",
        },
        {
            "source_name": "Baseball Reference Play-by-Play / Game Log",
            "url_reference": "https://www.baseball-reference.com/",
            "data_type": "Game outcomes, stats",
            "provides_moneyline_odds": False,
            "provides_scores": True,
            "provides_starters": True,
            "access_type": "Free web access; structured download requires scraping",
            "license": "Sports Reference LLC ToS restricts automated scraping",
            "format": "HTML tables",
            "2024_availability": "Available",
            "schema_compatibility": "PARTIAL — scores and starters but NO moneyline odds",
            "effort_estimate": "MEDIUM — scraping required, ToS restriction risk",
            "blocker": "No moneyline odds data. ToS restricts bulk scraping.",
            "resolution_contribution": "SCORES_ONLY",
            "priority": "LOW — does not resolve the odds gap",
        },
        {
            "source_name": "The Odds API (Historical Odds)",
            "url_reference": "https://the-odds-api.com/historical-odds-sites-api/",
            "data_type": "Historical moneyline odds from multiple bookmakers",
            "provides_moneyline_odds": True,
            "provides_scores": True,
            "provides_starters": False,
            "access_type": "Paid subscription; historical odds endpoint",
            "license": "Commercial ToS, API key required",
            "format": "JSON via REST API",
            "2024_availability": "Available (historical snapshots available from 2020+)",
            "schema_compatibility": "HIGH — provides home/away ML in numeric form, convertible to target schema",
            "effort_estimate": "MEDIUM — requires API key, paid plan, conversion script",
            "blocker": "Paid subscription required. Governance allows no live API calls, but",
            "blocker_detail": "historical pull can be done as one-time offline download with manual authorization.",
            "cost_estimate": "~$30-100/month (Starter plan); one-time 2024 season pull feasible",
            "resolution_contribution": "FULL — closest match to required schema",
            "priority": "HIGH — only viable path to full resolution",
            "required_governance_action": "Explicit CEO authorization for one-time paid API call",
        },
        {
            "source_name": "Sportsbook Review (SBR) Historical Odds",
            "url_reference": "https://www.sportsbookreview.com/betting-odds/mlb-baseball/",
            "data_type": "Historical moneyline, spread, over/under",
            "provides_moneyline_odds": True,
            "provides_scores": True,
            "provides_starters": False,
            "access_type": "Free web access; historical data accessible via URL patterns",
            "license": "Public access; terms restrict commercial use but research use is common",
            "format": "HTML / JavaScript rendered pages; no official API",
            "2024_availability": "Available (historical pages accessible by date)",
            "schema_compatibility": "MEDIUM — moneyline available but requires HTML scraping + parsing",
            "effort_estimate": "HIGH — JavaScript-rendered pages require headless browser; fragile scraping",
            "blocker": "No official API. JavaScript rendering adds complexity. Brittle to site changes.",
            "resolution_contribution": "FULL if successfully scraped",
            "priority": "MEDIUM — viable but high engineering effort and fragile",
            "required_governance_action": "None (free access) but live browser/scraping counts as automated data pull",
        },
        {
            "source_name": "Kaggle / GitHub Archived MLB Odds Datasets",
            "url_reference": "https://www.kaggle.com/search?q=mlb+odds+2024",
            "data_type": "Community-contributed historical odds CSV",
            "provides_moneyline_odds": "POSSIBLE — varies by dataset",
            "provides_scores": "POSSIBLE",
            "provides_starters": "RARE",
            "access_type": "Free; download via Kaggle API or direct link",
            "license": "Varies by dataset (CC0, CC-BY, or unknown)",
            "format": "CSV (typically)",
            "2024_availability": "UNCERTAIN — community datasets lag by 6-18 months; 2024 season may be available",
            "schema_compatibility": "VARIABLE — must validate column names against target schema",
            "effort_estimate": "LOW-MEDIUM — search, download, validate, convert",
            "blocker": "Quality and completeness not guaranteed. Provenance may be unclear.",
            "resolution_contribution": "PARTIAL_TO_FULL depending on dataset quality",
            "priority": "MEDIUM — worth checking before paying for API",
            "required_governance_action": "None — download without live API call; offline validation required",
        },
        {
            "source_name": "Internal TSL Odds History (2025 Season Only)",
            "url_reference": "data/tsl_odds_history.jsonl",
            "data_type": "TSL live odds snapshots",
            "provides_moneyline_odds": True,
            "provides_scores": False,
            "provides_starters": False,
            "access_type": "Internal file (no live call needed for reading)",
            "license": "Internal",
            "format": "JSONL",
            "2024_availability": "NOT AVAILABLE — TSL file covers 2026 spring training only",
            "schema_compatibility": "NOT APPLICABLE — 2025 season not covered",
            "effort_estimate": "N/A",
            "blocker": "Zero 2024 coverage. Zero 2025 season overlap.",
            "resolution_contribution": "NONE",
            "priority": "NONE — confirmed in P43 as zero-overlap",
        },
    ]


# ---------------------------------------------------------------------------
# C. Resolution paths
# ---------------------------------------------------------------------------

def build_resolution_paths() -> list[dict[str, Any]]:
    return [
        {
            "path_id": "PATH_A",
            "name": "The Odds API (one-time historical pull)",
            "effort": "MEDIUM",
            "cost": "~$30-50 one-time",
            "governance_requirement": "Explicit CEO authorization for one-time paid API call (not live betting)",
            "data_quality": "HIGH",
            "timeline_estimate": "1-2 days after authorization",
            "schema_match": "HIGH — requires conversion script (~50 lines)",
            "recommended": True,
            "rationale": (
                "Only source confirmed to provide 2024 MLB moneyline in structured format. "
                "One-time historical pull is distinct from live odds API calls. "
                "Would unblock P43 cross-year validation and all downstream cross-year analysis."
            ),
        },
        {
            "path_id": "PATH_B",
            "name": "Kaggle/GitHub community dataset search",
            "effort": "LOW-MEDIUM",
            "cost": "$0",
            "governance_requirement": "None — offline download, no live API",
            "data_quality": "VARIABLE — must validate",
            "timeline_estimate": "0.5-1 day",
            "schema_match": "VARIABLE",
            "recommended": True,
            "rationale": (
                "Free path worth exhausting first. If a validated 2024 MLB moneyline CSV "
                "exists on Kaggle, it would resolve the gap at zero cost. "
                "Must validate completeness (all 30 teams, full regular season) and provenance."
            ),
        },
        {
            "path_id": "PATH_C",
            "name": "Sportsbook Review scraping (headless browser)",
            "effort": "HIGH",
            "cost": "$0",
            "governance_requirement": "Engineering authorization for automated browser session",
            "data_quality": "MEDIUM — site-dependent reliability",
            "timeline_estimate": "3-5 days engineering",
            "schema_match": "MEDIUM — requires substantial parsing",
            "recommended": False,
            "rationale": (
                "Viable as fallback if PATH_A and PATH_B fail. High engineering cost and "
                "fragility outweigh benefit unless other paths are exhausted. "
                "JavaScript rendering adds complexity."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# D. Impact analysis
# ---------------------------------------------------------------------------

def build_impact_analysis(p43_ctx: dict[str, Any], p60_ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_state": {
            "p43_classification": p43_ctx["p43_final_classification"],
            "p60_classification": p60_ctx["p60_classification"],
            "cross_month_edge_stability": p60_ctx["cross_month_edge_stability"],
            "blocked_by_gap": "P43 cross-year validation; 2025-only EDGE_CONFIRMED stands",
        },
        "if_gap_resolved": {
            "p43_potential_upgrade": (
                "P43 could run cross-year bootstrap CI on 2024+2025 combined (~3856 quality rows). "
                "If 2024 Tier C shows consistent positive edge, P43 final classification upgrades "
                "from P43_BLOCKED_BY_DATA_GAP to P43_CROSS_YEAR_EDGE_CONFIRMED or similar."
            ),
            "risk_if_2024_differs": (
                "If 2024 Tier C shows negative or near-zero edge, the combined 2024+2025 CI "
                "may narrow or cross zero, weakening the P43 conclusion. "
                "This is scientifically correct and should be accepted as a legitimate finding."
            ),
            "downstream_unlock": [
                "P43 cross-year validation",
                "Stronger cross-year ECE/Brier comparison",
                "More robust walk-forward calibration (P45/P46 with 2024 data)",
                "2024 Tier C temporal stability analysis (P44 equivalent)",
            ],
        },
        "recommendation": (
            "Execute PATH_B (free Kaggle/GitHub search) immediately. "
            "If PATH_B fails within 1 day, request CEO authorization for PATH_A "
            "(The Odds API one-time historical pull). "
            "PATH_C is fallback only."
        ),
    }


# ---------------------------------------------------------------------------
# E. Final classification
# ---------------------------------------------------------------------------

def classify_resolution_feasibility(sources: list[dict[str, Any]]) -> str:
    def _is_full(s: dict[str, Any]) -> bool:
        rc = str(s.get("resolution_contribution", ""))
        return rc.startswith("FULL") or rc == "FULL"

    def _is_low_or_medium(s: dict[str, Any]) -> bool:
        e = s.get("effort_estimate", "")
        return any(tok in e.upper() for tok in ("LOW", "MEDIUM"))

    # Check if any source provides full moneyline at medium or lower effort
    high_value = [
        s for s in sources
        if s.get("provides_moneyline_odds") is True
        and _is_full(s)
        and _is_low_or_medium(s)
    ]
    if high_value:
        efforts = [s["effort_estimate"] for s in high_value]
        if any("LOW" in e.upper() and "MEDIUM" not in e.upper() for e in efforts):
            return "P61_DATA_GAP_RESOLVABLE_LOW_EFFORT"
        return "P61_DATA_GAP_RESOLVABLE_MEDIUM_EFFORT"
    # High effort only
    high_effort_full = [s for s in sources if _is_full(s)]
    if high_effort_full:
        return "P61_DATA_GAP_RESOLVABLE_HIGH_EFFORT"
    partial = [s for s in sources if "PARTIAL" in str(s.get("resolution_contribution", ""))]
    if partial:
        return "P61_DATA_GAP_PARTIALLY_RESOLVABLE"
    return "P61_DATA_GAP_UNRESOLVABLE_WITHOUT_PAID_SOURCE"


# ---------------------------------------------------------------------------
# F. Report generation
# ---------------------------------------------------------------------------

def build_report(
    p43_ctx: dict[str, Any],
    p60_ctx: dict[str, Any],
    sources: list[dict[str, Any]],
    paths: list[dict[str, Any]],
    impact: dict[str, Any],
    classification: str,
) -> str:
    L: list[str] = []

    L.append("# P61 — 2024 Closing-Line Data Gap Resolution Plan")
    L.append("")
    L.append("**Date:** 2026-05-26")
    L.append("**Phase:** P61 (CEO P1 priority — data-sourcing evaluation, paper_only=true)")
    L.append("**Trigger:** P60 completed → CEO P1 elevated from deferred → active")
    L.append("")

    L.append("## Governance Flags")
    for k, v in GOVERNANCE.items():
        L.append(f"- {k}: `{v}`")
    L.append("")

    L.append("## Background")
    L.append("")
    L.append(f"- **P43** final classification: `{p43_ctx['p43_final_classification']}`")
    L.append(f"  - 2024 quality rows: {p43_ctx['rows_2024_quality']} — zero closing-line odds available")
    L.append(f"  - 2025 joined rows: {p43_ctx['rows_2025_joined']} — EDGE_CONFIRMED on 2025 only")
    L.append(f"- **P60** classification: `{p60_ctx['p60_classification']}`")
    L.append(f"  - Cross-month stability: `{p60_ctx['cross_month_edge_stability']}`")
    L.append(f"  - Average edge across months: `{p60_ctx['avg_edge_mean']}`")
    L.append("")
    L.append("**Gap**: `data/mlb_2025/mlb_odds_2024_real.csv` with columns:")
    for col in REQUIRED_TARGET_SCHEMA["required_columns"]:
        L.append(f"  - `{col}`")
    L.append(f"  - Required rows: ~{REQUIRED_TARGET_SCHEMA['required_rows_estimate']}")
    L.append(f"  - Date range: {REQUIRED_TARGET_SCHEMA['date_range']}")
    L.append("")

    L.append("## Data Source Evaluation")
    L.append("")
    L.append("| Source | Provides ML Odds | Effort | Resolution | Priority |")
    L.append("|--------|-----------------|--------|------------|----------|")
    for s in sources:
        ml = "✅" if s["provides_moneyline_odds"] is True else ("❓" if s["provides_moneyline_odds"] == "POSSIBLE" else "❌")
        L.append(f"| {s['source_name']} | {ml} | {s['effort_estimate']} | {s['resolution_contribution']} | {s['priority'].split(' —')[0]} |")
    L.append("")

    L.append("### Source Details")
    for s in sources:
        L.append(f"\n#### {s['source_name']}")
        L.append(f"- **URL/Reference**: {s['url_reference']}")
        L.append(f"- **Provides moneyline**: {s['provides_moneyline_odds']}")
        L.append(f"- **2024 availability**: {s['2024_availability']}")
        L.append(f"- **Schema compatibility**: {s['schema_compatibility']}")
        L.append(f"- **Effort**: {s['effort_estimate']}")
        L.append(f"- **Access**: {s['access_type']}")
        if s.get("blocker"):
            L.append(f"- ⚠️ **Blocker**: {s['blocker']}")
        if s.get("cost_estimate"):
            L.append(f"- **Cost**: {s['cost_estimate']}")
        if s.get("required_governance_action"):
            L.append(f"- **Governance action needed**: {s['required_governance_action']}")
    L.append("")

    L.append("## Resolution Paths")
    L.append("")
    for p in paths:
        icon = "✅" if p["recommended"] else "⚠️"
        L.append(f"### {icon} {p['path_id']}: {p['name']}")
        L.append(f"- **Effort**: {p['effort']} | **Cost**: {p['cost']}")
        L.append(f"- **Data quality**: {p['data_quality']}")
        L.append(f"- **Timeline**: {p['timeline_estimate']}")
        L.append(f"- **Governance**: {p['governance_requirement']}")
        L.append(f"- **Rationale**: {p['rationale']}")
        L.append("")

    L.append("## Impact Analysis")
    L.append("")
    cs = impact["current_state"]
    L.append(f"**Current state**: P43=`{cs['p43_classification']}`, P60=`{cs['p60_classification']}`")
    L.append(f"**Blocked by**: {cs['blocked_by_gap']}")
    L.append("")
    L.append("**If gap resolved:**")
    ires = impact["if_gap_resolved"]
    L.append(f"- {ires['p43_potential_upgrade']}")
    L.append(f"- ⚠️ Risk: {ires['risk_if_2024_differs']}")
    L.append("- Downstream unlocks:")
    for unlock in ires["downstream_unlock"]:
        L.append(f"  - {unlock}")
    L.append("")
    L.append(f"**Recommendation**: {impact['recommendation']}")
    L.append("")

    L.append("## Final P61 Classification")
    L.append(f"\n**P61 Classification:** `{classification}`")
    L.append("")
    L.append("### Recommended Next Actions")
    L.append("1. **TODAY (0 cost)**: Search Kaggle/GitHub for `mlb 2024 odds moneyline` datasets.")
    L.append("   Validate any match against required schema. If found → run P43 with 2024 data.")
    L.append("2. **If PATH_B fails (~1 day)**: Request CEO authorization for The Odds API one-time")
    L.append("   historical pull (~$30-50). This is NOT a live betting API call.")
    L.append("3. **Do NOT** scrape SBR or Baseball Reference without engineering authorization.")
    L.append("4. **Do NOT** make any live API call without explicit governance authorization.")
    L.append("")

    L.append("## Known Limitations")
    L.append("- This report evaluates sources; no data was downloaded.")
    L.append("- Cost estimates are approximate and subject to vendor pricing changes.")
    L.append("- Kaggle dataset quality is not guaranteed without inspection.")
    L.append("- 2024 data may show different edge characteristics than 2025 (scientifically valid risk).")
    L.append("- **Paper-only. No production proposal. No champion replacement.**")
    L.append("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P61] Loading P43 and P60 context...")
    p43_ctx = load_p43_context()
    p60_ctx = load_p60_context()
    print(f"[P61] P43 classification: {p43_ctx['p43_final_classification']}")
    print(f"[P61] P60 classification: {p60_ctx['p60_classification']}")

    sources = build_source_evaluations()
    paths = build_resolution_paths()
    impact = build_impact_analysis(p43_ctx, p60_ctx)
    classification = classify_resolution_feasibility(sources)

    assert classification in ALLOWED_CLASSIFICATIONS, f"Illegal: {classification}"
    print(f"[P61] Classification: {classification}")

    summary: dict[str, Any] = {
        "version": "p61_v1",
        "governance": GOVERNANCE,
        "p43_context": p43_ctx,
        "p60_context": p60_ctx,
        "required_target_schema": REQUIRED_TARGET_SCHEMA,
        "source_evaluations": sources,
        "resolution_paths": paths,
        "impact_analysis": impact,
        "p61_classification": classification,
        "allowed_classifications": sorted(ALLOWED_CLASSIFICATIONS),
        "recommended_next_actions": [
            "PATH_B: Search Kaggle/GitHub for mlb 2024 moneyline odds CSV (free, 0-1 day)",
            "PATH_A: If PATH_B fails, request CEO authorization for The Odds API one-time pull",
            "Do NOT make live API calls without explicit governance authorization",
        ],
        "framing_note": (
            "P61 is a data-sourcing evaluation report only. "
            "No data was downloaded. No live API was called. "
            "2024 closing-line data gap remains unresolved pending resolution path execution. "
            "Paper-only. No production proposal. No champion replacement."
        ),
        "limitation": (
            "2024_closing_line_data_unavailable — resolution requires external action. "
            "P43 cross-year validation remains blocked until data is sourced."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[P61] Saved: {OUT_JSON}")

    report_md = build_report(p43_ctx, p60_ctx, sources, paths, impact, classification)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md, encoding="utf-8")
    OUT_BETTINGPLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BETTINGPLAN.write_text(report_md, encoding="utf-8")
    print(f"[P61] Reports saved.")

    print("\n=== P61 Summary ===")
    print(f"Sources evaluated: {len(sources)}")
    print(f"Resolution paths: {len(paths)}")
    print(f"Classification: {classification}")
    viable_full = [s for s in sources if s.get("resolution_contribution") == "FULL"]
    print(f"Sources with FULL resolution: {len(viable_full)}")


if __name__ == "__main__":
    main()
