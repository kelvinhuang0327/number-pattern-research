"""
P34 Odds Source Planner
========================
Evaluates all candidate paths for acquiring verified 2024 MLB market closing odds.

HARD RULES:
- Do NOT scrape odds from any live or historical source.
- Do NOT infer odds from game outcomes (outcome-reverse-engineering is forbidden).
- Do NOT call live odds APIs.
- Do NOT use unclear-license odds as ready.
- PAPER_ONLY=True, PRODUCTION_READY=False.
"""

from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    LEAKAGE_CONFIRMED,
    LEAKAGE_LOW,
    LEAKAGE_NONE,
    ODDS_TEMPLATE_COLUMNS,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_BLOCKED_SCHEMA_GAP,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    PAPER_ONLY,
    PRODUCTION_READY,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    P34OddsAcquisitionOption,
)


def load_p33_odds_candidates(path: str) -> pd.DataFrame:
    """
    Load the P33 odds source candidates CSV.
    Returns empty DataFrame if file is missing.
    """
    if not os.path.isfile(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def evaluate_candidate_license_safety(candidate: pd.Series) -> str:
    """
    Determine the license safety category for an odds candidate.

    Returns one of:
    - "internal" — self-generated, no license concern
    - "research_permitted" — license explicitly allows research/personal use
    - "review_required" — license exists but terms not verified
    - "unknown" — no license information available
    - "blocked_no_redistribution" — license forbids the use case
    """
    source_ref = str(candidate.get("source_odds_ref", "")).lower()
    # Known safe-for-research sources
    if "retrosheet" in source_ref:
        return "research_permitted"
    # No license info at all
    if not source_ref or source_ref in ("", "none", "nan", "unknown"):
        return "unknown"
    # TSL or commercial sportsbooks without explicit license approval
    if any(t in source_ref for t in ("tsl", "betway", "pinnacle", "unibet", "888", "live_odds")):
        return "review_required"
    return "review_required"


def evaluate_odds_schema(candidate: pd.Series) -> dict:
    """
    Check which required ODDS_TEMPLATE_COLUMNS are present / missing.

    Returns:
    - present: list of matched columns
    - missing: list of missing columns
    - has_game_id: bool
    - has_odds_decimal: bool
    """
    raw_cols_str = str(candidate.get("detected_columns", ""))
    # Parse comma-separated column string if present
    if raw_cols_str and raw_cols_str not in ("nan", "None", ""):
        detected = {c.strip().lower() for c in raw_cols_str.split(",")}
    else:
        detected = set()

    required_lower = {c.lower() for c in ODDS_TEMPLATE_COLUMNS}
    present = [c for c in ODDS_TEMPLATE_COLUMNS if c.lower() in detected]
    missing = [c for c in ODDS_TEMPLATE_COLUMNS if c.lower() not in detected]
    return {
        "present": present,
        "missing": missing,
        "has_game_id": "game_id" in detected,
        "has_odds_decimal": any(k in detected for k in ("odds_decimal", "home_ml", "away_ml", "decimal_odds")),
    }


def build_odds_acquisition_options(
    odds_candidates_df: pd.DataFrame,
) -> List[P34OddsAcquisitionOption]:
    """
    Build the full ordered list of P34 odds acquisition options.

    Option order:
    1. odds_r01 — Approved licensed historical odds export (sportsbookreviewsonline.com)
    2. odds_r02 — Paid provider API export (The Odds API)
    3. odds_r03 — Existing repo candidates (if any survive P33 filter)
    4. odds_r04 — Explicit blocker
    """
    options: List[P34OddsAcquisitionOption] = []

    # --- odds_r01: sportsbookreviewsonline.com ---
    # This is the highest-priority recommended path. Freely downloadable Excel/CSV.
    # License: personal/research use. ToS review required before redistribution.
    options.append(
        P34OddsAcquisitionOption(
            option_id="odds_r01",
            source_name="sportsbookreviewsonline.com 2024 MLB Closing Moneylines",
            source_type="licensed_export",
            acquisition_method=(
                "Manual download of per-month Excel files from "
                "https://www.sportsbookreviewsonline.com/scoresoddsarchives/mlb/mlboddsarchives.htm. "
                "Parse home/away moneyline columns, convert American odds to decimal, "
                "align game_id via (date, team) join against P32 spine. "
                "Do NOT scrape; download manually."
            ),
            expected_columns=ODDS_TEMPLATE_COLUMNS,
            missing_columns=("closing_timestamp",),  # often absent in Excel archives
            provenance_status="external_public_archive",
            license_status="personal_research_verify_tos",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_LOW,
            estimated_coverage=0.90,
            status=OPTION_REQUIRES_LICENSE_REVIEW,
            blocker_if_skipped=(
                "No market prior; Kelly criterion and EV calculations cannot be validated."
            ),
            notes=(
                "License: freely available for personal/research. "
                "Verify ToS before any redistribution. "
                "Must align to P32 game_id spine before use. "
                "Expected: American moneylines → convert to decimal."
            ),
        )
    )

    # --- odds_r02: The Odds API ---
    options.append(
        P34OddsAcquisitionOption(
            option_id="odds_r02",
            source_name="The Odds API — Historical MLB 2024 Moneylines",
            source_type="paid_provider",
            acquisition_method=(
                "Use paid API key to query historical h2h moneyline snapshots for "
                "MLB 2024 (2024-03-20 to 2024-09-30). Paginate by date range. "
                "Do NOT call live endpoints. Requires paid subscription."
            ),
            expected_columns=ODDS_TEMPLATE_COLUMNS,
            missing_columns=(),
            provenance_status="paid_api_snapshots",
            license_status="paid_subscription_internal_research",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_MEDIUM,
            estimated_coverage=0.85,
            status=OPTION_REQUIRES_MANUAL_APPROVAL,
            blocker_if_skipped="Fallback if odds_r01 license is rejected.",
            notes=(
                "Requires API key and paid plan. Historical endpoint covers pre-game "
                "snapshots (not live). Budget ~$50–100 USD for full 2024 MLB season."
            ),
        )
    )

    # --- odds_r03: Existing repo candidates ---
    repo_options = _build_repo_candidate_options(odds_candidates_df)
    options.extend(repo_options)

    # --- odds_r04: Explicit blocker (always last) ---
    options.append(
        P34OddsAcquisitionOption(
            option_id="odds_r04",
            source_name="No odds source available",
            source_type="blocker",
            acquisition_method="none",
            expected_columns=ODDS_TEMPLATE_COLUMNS,
            missing_columns=ODDS_TEMPLATE_COLUMNS,
            provenance_status="blocked",
            license_status="blocked",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_HIGH,
            estimated_coverage=0.0,
            status=OPTION_BLOCKED_PROVENANCE,
            blocker_if_skipped=(
                "Without a verified odds source, market calibration is impossible. "
                "EV analysis and Kelly position sizing cannot be validated."
            ),
            notes=(
                "Explicit blocker. All repo-resident odds sources were blocked by P33 "
                "due to wrong season (2025/2026) or license unclear."
            ),
        )
    )

    return options


def _build_repo_candidate_options(
    odds_candidates_df: pd.DataFrame,
) -> List[P34OddsAcquisitionOption]:
    """
    Evaluate existing P33 odds candidates for P34 options.
    All are expected to be blocked (wrong year, dry-run, or no license).
    """
    options: List[P34OddsAcquisitionOption] = []
    if odds_candidates_df.empty or "status" not in odds_candidates_df.columns:
        return options

    # Only consider SOURCE_PARTIAL or SOURCE_READY candidates from P33
    viable = odds_candidates_df[
        odds_candidates_df["status"].isin(["SOURCE_READY", "SOURCE_PARTIAL"])
    ]

    for idx, row in viable.iterrows():
        file_path = str(row.get("file_path", ""))
        cand_id = str(row.get("candidate_id", f"c{idx}"))
        license_safety = evaluate_candidate_license_safety(row)
        schema = evaluate_odds_schema(row)

        if license_safety in ("unknown", "blocked_no_redistribution"):
            status = OPTION_BLOCKED_PROVENANCE
        elif license_safety == "review_required":
            status = OPTION_REQUIRES_LICENSE_REVIEW
        else:
            status = OPTION_REQUIRES_MANUAL_APPROVAL

        options.append(
            P34OddsAcquisitionOption(
                option_id=f"odds_r03_{cand_id}",
                source_name=os.path.basename(file_path),
                source_type="repo_candidate",
                acquisition_method="existing_repo_file",
                expected_columns=ODDS_TEMPLATE_COLUMNS,
                missing_columns=tuple(schema["missing"]),
                provenance_status="p33_candidate",
                license_status=license_safety,
                leakage_risk=LEAKAGE_LOW if schema["has_game_id"] else LEAKAGE_CONFIRMED,
                implementation_risk=RISK_HIGH,
                estimated_coverage=0.0,
                status=status,
                blocker_if_skipped="Repo candidate blocked — wrong season or license unclear.",
                notes=(
                    f"P33 candidate: {file_path}. "
                    f"Schema: {len(schema['present'])} present, {len(schema['missing'])} missing. "
                    f"License: {license_safety}."
                ),
            )
        )

    return options


def rank_odds_options(
    options: List[P34OddsAcquisitionOption],
) -> List[P34OddsAcquisitionOption]:
    """
    Sort odds options by safety:
    1. OPTION_READY_FOR_IMPLEMENTATION_PLAN
    2. OPTION_REQUIRES_LICENSE_REVIEW (preferred over manual approval — path exists)
    3. OPTION_REQUIRES_MANUAL_APPROVAL
    4. OPTION_BLOCKED_PROVENANCE / OPTION_BLOCKED_SCHEMA_GAP
    5. OPTION_REJECTED_FAKE_OR_LEAKAGE (always last)
    """
    status_rank = {
        "OPTION_READY_FOR_IMPLEMENTATION_PLAN": 0,
        OPTION_REQUIRES_LICENSE_REVIEW: 1,
        OPTION_REQUIRES_MANUAL_APPROVAL: 2,
        OPTION_BLOCKED_PROVENANCE: 3,
        OPTION_BLOCKED_SCHEMA_GAP: 3,
        OPTION_REJECTED_FAKE_OR_LEAKAGE: 4,
    }
    return sorted(options, key=lambda o: status_rank.get(o.status, 99))


def summarize_odds_plan(options: List[P34OddsAcquisitionOption]) -> str:
    """Return a single-paragraph human-readable summary of odds acquisition options."""
    if not options:
        return "No odds acquisition options evaluated."
    ranked = rank_odds_options(options)
    best = ranked[0]
    total = len(options)
    review_count = sum(1 for o in options if o.status == OPTION_REQUIRES_LICENSE_REVIEW)
    blocked = sum(
        1 for o in options if o.status in (OPTION_BLOCKED_PROVENANCE, OPTION_REJECTED_FAKE_OR_LEAKAGE)
    )
    return (
        f"Evaluated {total} odds acquisition options: {review_count} require license review, "
        f"{blocked} blocked. Best option: [{best.option_id}] {best.source_name} "
        f"(status={best.status}, coverage={best.estimated_coverage:.0%}, "
        f"license={best.license_status}). "
        "Do NOT scrape or infer odds. License review must precede any download. "
        f"PAPER_ONLY=True, PRODUCTION_READY=False."
    )
