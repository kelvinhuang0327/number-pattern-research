#!/usr/bin/env python3
"""
P39E — MLB Team Code Normalization

Maps Retrosheet codes (and other aliases) to canonical Statcast team codes.
Used by the P39C join utility to resolve team code mismatches between P38A OOF
predictions (Retrosheet codes) and P39B rolling features (Statcast codes).

SCRIPT_VERSION = "p39e_team_code_normalization_v1"
PAPER_ONLY = True
production_ready = False

Acceptance marker: P39E_TEAM_CODE_NORMALIZATION_READY_20260515
"""
from __future__ import annotations

SCRIPT_VERSION = "p39e_team_code_normalization_v1"
PAPER_ONLY = True

# ──────────────────────────────────────────────────────────────────────────────
# Canonical Statcast Team Codes (30 MLB Teams, 2024 season)
# ──────────────────────────────────────────────────────────────────────────────

CANONICAL_TEAMS: frozenset[str] = frozenset({
    "ATH",  # Oakland/Sacramento Athletics (Statcast canonical since 2024)
    "ATL",  # Atlanta Braves
    "AZ",   # Arizona Diamondbacks
    "BAL",  # Baltimore Orioles
    "BOS",  # Boston Red Sox
    "CHC",  # Chicago Cubs
    "CIN",  # Cincinnati Reds
    "CLE",  # Cleveland Guardians
    "COL",  # Colorado Rockies
    "CWS",  # Chicago White Sox
    "DET",  # Detroit Tigers
    "HOU",  # Houston Astros
    "KC",   # Kansas City Royals
    "LAA",  # Los Angeles Angels
    "LAD",  # Los Angeles Dodgers
    "MIA",  # Miami Marlins
    "MIL",  # Milwaukee Brewers
    "MIN",  # Minnesota Twins
    "NYM",  # New York Mets
    "NYY",  # New York Yankees
    "PHI",  # Philadelphia Phillies
    "PIT",  # Pittsburgh Pirates
    "SD",   # San Diego Padres
    "SEA",  # Seattle Mariners
    "SF",   # San Francisco Giants
    "STL",  # St. Louis Cardinals
    "TB",   # Tampa Bay Rays
    "TEX",  # Texas Rangers
    "TOR",  # Toronto Blue Jays
    "WSH",  # Washington Nationals
})

# ──────────────────────────────────────────────────────────────────────────────
# Normalization Map: Retrosheet + variant codes → Statcast canonical
# ──────────────────────────────────────────────────────────────────────────────

RETROSHEET_TO_STATCAST: dict[str, str] = {
    # ── Chicago White Sox (Retrosheet: CHA or CHW) ───────────────────────────
    "CHA": "CWS",
    "CHW": "CWS",
    # ── Chicago Cubs (Retrosheet: CHN) ───────────────────────────────────────
    "CHN": "CHC",
    # ── Tampa Bay Rays (Retrosheet: TBA or TBD; also seen as TBR) ────────────
    "TBA": "TB",
    "TBD": "TB",
    "TBR": "TB",
    # ── Arizona Diamondbacks (Retrosheet: ARI) ────────────────────────────────
    "ARI": "AZ",
    # ── Oakland / Sacramento Athletics (Retrosheet: OAK; Statcast: ATH) ──────
    "OAK": "ATH",
    # ── San Diego Padres (Retrosheet: SDN or SDP) ────────────────────────────
    "SDN": "SD",
    "SDP": "SD",
    # ── San Francisco Giants (Retrosheet: SFN or SFG) ────────────────────────
    "SFN": "SF",
    "SFG": "SF",
    # ── Los Angeles Dodgers (Retrosheet: LAN) ────────────────────────────────
    "LAN": "LAD",
    # ── Los Angeles Angels (Retrosheet: ANA or LAA) ──────────────────────────
    "ANA": "LAA",
    # ── New York Yankees (Retrosheet: NYA) ───────────────────────────────────
    "NYA": "NYY",
    # ── New York Mets (Retrosheet: NYN) ──────────────────────────────────────
    "NYN": "NYM",
    # ── Kansas City Royals (Retrosheet: KCA) ─────────────────────────────────
    "KCA": "KC",
    # ── St. Louis Cardinals (Retrosheet: SLN) ────────────────────────────────
    "SLN": "STL",
    # ── Washington Nationals (also seen as WAS) ───────────────────────────────
    "WAS": "WSH",
    # ── Miami Marlins (historical: FLA for Florida Marlins pre-2012) ──────────
    "FLA": "MIA",
    # ── Direct Statcast canonical codes (identity mapping) ────────────────────
    "ATH": "ATH",
    "ATL": "ATL",
    "AZ":  "AZ",
    "BAL": "BAL",
    "BOS": "BOS",
    "CHC": "CHC",
    "CIN": "CIN",
    "CLE": "CLE",
    "COL": "COL",
    "CWS": "CWS",
    "DET": "DET",
    "HOU": "HOU",
    "KC":  "KC",
    "LAA": "LAA",
    "LAD": "LAD",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NYM": "NYM",
    "NYY": "NYY",
    "PHI": "PHI",
    "PIT": "PIT",
    "SD":  "SD",
    "SEA": "SEA",
    "SF":  "SF",
    "STL": "STL",
    "TB":  "TB",
    "TEX": "TEX",
    "TOR": "TOR",
    "WSH": "WSH",
}


# ──────────────────────────────────────────────────────────────────────────────
# Public Functions
# ──────────────────────────────────────────────────────────────────────────────


def normalize_team_code(code: str) -> str | None:
    """
    Normalize an MLB team code to its canonical Statcast form.

    Args:
        code: Raw team code (case-insensitive).

    Returns:
        Canonical Statcast team code string, or None if the code is unknown.
        Returns None rather than silently keeping an unrecognized code so
        callers can detect and report unknown codes explicitly.

    Examples:
        >>> normalize_team_code("CHA")
        'CWS'
        >>> normalize_team_code("TBA")
        'TB'
        >>> normalize_team_code("BAL")
        'BAL'
        >>> normalize_team_code("ZZZ") is None
        True
    """
    return RETROSHEET_TO_STATCAST.get(code.upper())


def is_canonical(code: str) -> bool:
    """
    Return True if code is already a canonical Statcast team code.

    Args:
        code: Team code to check (case-sensitive — canonical codes are uppercase).

    Returns:
        True if code is in CANONICAL_TEAMS, False otherwise.
    """
    return code in CANONICAL_TEAMS


def normalize_or_raise(code: str) -> str:
    """
    Normalize a team code, raising ValueError for unknown codes.

    Prefer normalize_team_code() for fail-soft behaviour.

    Args:
        code: Raw team code.

    Returns:
        Canonical Statcast team code string.

    Raises:
        ValueError: If the code is not recognized.
    """
    result = normalize_team_code(code)
    if result is None:
        raise ValueError(
            f"Unknown MLB team code: {code!r}. "
            f"Not in RETROSHEET_TO_STATCAST map."
        )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Marker
# ──────────────────────────────────────────────────────────────────────────────

# P39E_TEAM_CODE_NORMALIZATION_READY_20260515
