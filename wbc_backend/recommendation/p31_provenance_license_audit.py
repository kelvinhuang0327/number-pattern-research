"""
P31 Provenance & License Audit Module.

Assesses the three 2024 acquisition candidates:
  1. Retrosheet 2024 game logs (gl2024)
  2. MLB Stats API 2024 schedule + linescore
  3. 2024 closing moneyline odds (provider TBD)

Each candidate is evaluated for:
  - source_name
  - source_type
  - expected_payload
  - provenance_status
  - license_status
  - acquisition_risk
  - schema_gap
  - recommended_decision

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False


class ProvenanceStatus(str, Enum):
    VERIFIED = "VERIFIED"           # URL known, file format documented
    UNRESOLVED = "UNRESOLVED"       # Source not yet identified
    PARTIAL = "PARTIAL"             # Source known but schema partial


class LicenseStatus(str, Enum):
    SAFE_NON_COMMERCIAL = "SAFE_NON_COMMERCIAL"     # Free non-commercial use permitted
    REQUIRES_ATTRIBUTION = "REQUIRES_ATTRIBUTION"   # Free but attribution required
    PAID_COMMERCIAL = "PAID_COMMERCIAL"              # Requires paid subscription
    TOS_RISK = "TOS_RISK"                            # Scraping / TOS unclear
    UNKNOWN = "UNKNOWN"                              # Not yet determined


class AcquisitionRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class CandidateDecision(str, Enum):
    GO = "GO"
    GO_PARTIAL = "GO_PARTIAL"    # Source is usable but incomplete (no odds)
    NO_GO = "NO_GO"
    PENDING_LICENSE = "PENDING_LICENSE"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Provenance2024Candidate:
    source_name: str
    source_type: str
    expected_payload: str
    provenance_status: ProvenanceStatus
    license_status: LicenseStatus
    acquisition_risk: AcquisitionRisk
    schema_gap: list[str]
    recommended_decision: CandidateDecision
    notes: str = ""
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_type": self.source_type,
            "expected_payload": self.expected_payload,
            "url": self.url,
            "provenance_status": self.provenance_status.value,
            "license_status": self.license_status.value,
            "acquisition_risk": self.acquisition_risk.value,
            "schema_gap": self.schema_gap,
            "recommended_decision": self.recommended_decision.value,
            "notes": self.notes,
        }


@dataclass
class ProvenanceLicenseAuditResult:
    candidates: list[Provenance2024Candidate] = field(default_factory=list)
    overall_p32_recommendation: str = "PENDING"
    odds_license_resolved: bool = False
    game_logs_license_safe: bool = False
    paper_only: bool = PAPER_ONLY
    production_ready: bool = PRODUCTION_READY

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_only": self.paper_only,
            "production_ready": self.production_ready,
            "overall_p32_recommendation": self.overall_p32_recommendation,
            "odds_license_resolved": self.odds_license_resolved,
            "game_logs_license_safe": self.game_logs_license_safe,
            "candidates": [c.to_dict() for c in self.candidates],
        }


# ---------------------------------------------------------------------------
# Candidate definitions
# ---------------------------------------------------------------------------


def _build_retrosheet_candidate() -> Provenance2024Candidate:
    """
    Retrosheet 2024 game logs (gl2024).

    Retrosheet is a free, non-commercial dataset of historical MLB game results.
    It does NOT include betting odds or closing moneylines.
    License: Attribution required; no commercial redistribution.
    URL: https://www.retrosheet.org/gamelogs/index.html
    """
    return Provenance2024Candidate(
        source_name="Retrosheet 2024 Game Logs (gl2024)",
        source_type="RAW_SECONDARY",
        expected_payload=(
            "~2,430 regular-season game records with date, teams, final scores, "
            "starting pitchers, attendance. Fixed-width text, ~161 columns. "
            "NO betting odds included."
        ),
        provenance_status=ProvenanceStatus.VERIFIED,
        license_status=LicenseStatus.REQUIRES_ATTRIBUTION,
        acquisition_risk=AcquisitionRisk.LOW,
        schema_gap=[
            "closing_moneyline_home",
            "closing_moneyline_away",
            "run_line_spread",
            "over_under",
        ],
        recommended_decision=CandidateDecision.GO_PARTIAL,
        url="https://www.retrosheet.org/gamelogs/index.html",
        notes=(
            "gl2024.zip is publicly available for non-commercial research. "
            "Schema provides game outcomes and starting pitchers but no closing odds. "
            "A supplemental odds source (separate license) is required for full "
            "moneyline model training. "
            "P32 can proceed for game-log ingestion independently of odds resolution. "
            "Attribution required per Retrosheet terms: "
            "'The information used here was obtained free of charge from and is "
            "copyrighted by Retrosheet.'"
        ),
    )


def _build_mlb_stats_api_candidate() -> Provenance2024Candidate:
    """
    MLB Stats API 2024 schedule + linescore.

    The MLB Stats API is a public REST API providing schedule, game status,
    and linescore data. It does NOT include betting odds.
    License: MLB data; non-commercial research generally tolerated; no
    redistribution of raw feed.
    """
    return Provenance2024Candidate(
        source_name="MLB Stats API 2024 Schedule + Linescore",
        source_type="RAW_SECONDARY",
        expected_payload=(
            "2024 regular-season schedule (~2,430 games), game status, "
            "linescore (inning-by-inning runs), team abbreviations. JSON format. "
            "NO closing odds included."
        ),
        provenance_status=ProvenanceStatus.VERIFIED,
        license_status=LicenseStatus.REQUIRES_ATTRIBUTION,
        acquisition_risk=AcquisitionRisk.MEDIUM,
        schema_gap=[
            "closing_moneyline_home",
            "closing_moneyline_away",
            "run_line_spread",
            "over_under",
        ],
        recommended_decision=CandidateDecision.GO_PARTIAL,
        url="https://statsapi.mlb.com/api/v1/schedule?sportId=1&season=2024",
        notes=(
            "MLB Stats API provides game outcomes but no betting odds. "
            "Useful as a cross-validation source alongside Retrosheet gl2024. "
            "Risk: MLB may rate-limit; API schema changes between seasons require "
            "field-mapping validation. "
            "Not a source for odds — must be paired with a licensed odds provider "
            "for full moneyline model input. "
            "Medium risk due to potential schema drift; recommend pinning API version."
        ),
    )


def _build_closing_odds_candidate() -> Provenance2024Candidate:
    """
    2024 Closing Moneyline Odds — provider unresolved.

    Multiple providers exist but all have commercial or TOS restrictions:
    - The Odds API (historical tier): paid subscription required
    - OddsPortal: scraping violates TOS
    - Pinnacle historical API: commercial license required
    - SBR Odds (SportsBettingReference): scraping risk

    Until a provider with explicit non-commercial research permission is
    identified, this candidate is PENDING_LICENSE.
    """
    return Provenance2024Candidate(
        source_name="2024 Closing Moneyline Odds (Provider TBD)",
        source_type="RAW_PRIMARY_CANDIDATE",
        expected_payload=(
            "Pre-game and closing moneyline odds for ~2,430 MLB games in 2024. "
            "Required columns: closing_moneyline_home, closing_moneyline_away, "
            "game_date, home_team, away_team."
        ),
        provenance_status=ProvenanceStatus.UNRESOLVED,
        license_status=LicenseStatus.UNKNOWN,
        acquisition_risk=AcquisitionRisk.HIGH,
        schema_gap=[
            # Odds ARE the payload here; the gap is license resolution
        ],
        recommended_decision=CandidateDecision.PENDING_LICENSE,
        url="",  # No confirmed URL until provider selected
        notes=(
            "CRITICAL BLOCKER for full GO decision. "
            "Three candidate providers evaluated:\n"
            "  1. The Odds API (historical tier): "
            "     https://the-odds-api.com/ — paid subscription; "
            "     non-commercial research use unclear; requires direct license inquiry.\n"
            "  2. OddsPortal: scraping prohibited by TOS; HIGH legal risk.\n"
            "  3. Pinnacle historical API: commercial license required; "
            "     research exception not documented.\n"
            "ACTION REQUIRED before P32: Select provider, obtain license confirmation "
            "in writing, record in data/p31_provenance_audit.json. "
            "Until resolved, P32 can only ingest game logs (GO_PARTIAL). "
            "Full GO requires this blocker cleared."
        ),
    )


# ---------------------------------------------------------------------------
# Main audit function
# ---------------------------------------------------------------------------


def run_provenance_license_audit() -> ProvenanceLicenseAuditResult:
    """
    Assess all three 2024 acquisition candidates and determine the P32
    recommendation.

    Returns:
        ProvenanceLicenseAuditResult with candidates and overall decision.
    """
    result = ProvenanceLicenseAuditResult()

    retrosheet = _build_retrosheet_candidate()
    mlb_api = _build_mlb_stats_api_candidate()
    odds = _build_closing_odds_candidate()

    result.candidates = [retrosheet, mlb_api, odds]

    # Determine overall flags
    game_log_decisions = {
        CandidateDecision.GO,
        CandidateDecision.GO_PARTIAL,
    }
    result.game_logs_license_safe = (
        retrosheet.recommended_decision in game_log_decisions
        and mlb_api.recommended_decision in game_log_decisions
    )
    result.odds_license_resolved = (
        odds.recommended_decision == CandidateDecision.GO
    )

    # Overall P32 recommendation
    if result.game_logs_license_safe and result.odds_license_resolved:
        result.overall_p32_recommendation = "GO_FULL"
    elif result.game_logs_license_safe and not result.odds_license_resolved:
        result.overall_p32_recommendation = "GO_PARTIAL_GAME_LOGS_ONLY"
    else:
        result.overall_p32_recommendation = "NO_GO"

    return result


def write_provenance_audit_json(
    result: ProvenanceLicenseAuditResult,
    output_path: str | Path,
) -> None:
    """Write provenance audit result to a JSON file."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, ensure_ascii=False)
