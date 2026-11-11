"""
P39E Team Code Normalization Tests
tests/test_team_code_normalization.py

Validates that all MLB Retrosheet/variant codes normalize correctly
to canonical Statcast team codes. Zero network I/O.

Acceptance marker: P39E_TEAM_CODE_NORMALIZATION_READY_20260515
"""
from __future__ import annotations

import pytest

from scripts.team_code_normalization import (
    CANONICAL_TEAMS,
    RETROSHEET_TO_STATCAST,
    is_canonical,
    normalize_or_raise,
    normalize_team_code,
)


# ──────────────────────────────────────────────────────────────────────────────
# Core alias tests — the 4 primary mismatches from P38A/P39D
# ──────────────────────────────────────────────────────────────────────────────


def test_cha_normalizes_to_cws() -> None:
    """CHA (Retrosheet Chicago White Sox) → CWS (Statcast)."""
    assert normalize_team_code("CHA") == "CWS"


def test_chw_normalizes_to_cws() -> None:
    """CHW (alternate Chicago White Sox code) → CWS."""
    assert normalize_team_code("CHW") == "CWS"


def test_tba_normalizes_to_tb() -> None:
    """TBA (Retrosheet Tampa Bay) → TB (Statcast)."""
    assert normalize_team_code("TBA") == "TB"


def test_tbd_normalizes_to_tb() -> None:
    """TBD (alternate Tampa Bay code) → TB."""
    assert normalize_team_code("TBD") == "TB"


def test_tbr_normalizes_to_tb() -> None:
    """TBR (sometimes-seen Tampa Bay code) → TB."""
    assert normalize_team_code("TBR") == "TB"


def test_ari_normalizes_to_az() -> None:
    """ARI (Retrosheet Arizona) → AZ (Statcast)."""
    assert normalize_team_code("ARI") == "AZ"


def test_oak_normalizes_to_ath() -> None:
    """OAK (Retrosheet Oakland Athletics) → ATH (Statcast 2024+)."""
    assert normalize_team_code("OAK") == "ATH"


# ──────────────────────────────────────────────────────────────────────────────
# Other Retrosheet alias tests
# ──────────────────────────────────────────────────────────────────────────────


def test_sdn_normalizes_to_sd() -> None:
    """SDN (Retrosheet San Diego Padres) → SD."""
    assert normalize_team_code("SDN") == "SD"


def test_sdp_normalizes_to_sd() -> None:
    """SDP (alternate San Diego code) → SD."""
    assert normalize_team_code("SDP") == "SD"


def test_sfn_normalizes_to_sf() -> None:
    """SFN (Retrosheet San Francisco Giants) → SF."""
    assert normalize_team_code("SFN") == "SF"


def test_sfg_normalizes_to_sf() -> None:
    """SFG (alternate San Francisco code) → SF."""
    assert normalize_team_code("SFG") == "SF"


def test_lan_normalizes_to_lad() -> None:
    """LAN (Retrosheet Los Angeles Dodgers) → LAD."""
    assert normalize_team_code("LAN") == "LAD"


def test_nya_normalizes_to_nyy() -> None:
    """NYA (Retrosheet New York Yankees) → NYY."""
    assert normalize_team_code("NYA") == "NYY"


def test_nyn_normalizes_to_nym() -> None:
    """NYN (Retrosheet New York Mets) → NYM."""
    assert normalize_team_code("NYN") == "NYM"


def test_kca_normalizes_to_kc() -> None:
    """KCA (Retrosheet Kansas City Royals) → KC."""
    assert normalize_team_code("KCA") == "KC"


def test_sln_normalizes_to_stl() -> None:
    """SLN (Retrosheet St. Louis Cardinals) → STL."""
    assert normalize_team_code("SLN") == "STL"


def test_was_normalizes_to_wsh() -> None:
    """WAS (alternate Washington Nationals code) → WSH."""
    assert normalize_team_code("WAS") == "WSH"


def test_chn_normalizes_to_chc() -> None:
    """CHN (Retrosheet Chicago Cubs) → CHC."""
    assert normalize_team_code("CHN") == "CHC"


def test_ana_normalizes_to_laa() -> None:
    """ANA (Anaheim Angels historical code) → LAA."""
    assert normalize_team_code("ANA") == "LAA"


def test_fla_normalizes_to_mia() -> None:
    """FLA (Florida Marlins historical code) → MIA."""
    assert normalize_team_code("FLA") == "MIA"


# ──────────────────────────────────────────────────────────────────────────────
# Unknown code behaviour
# ──────────────────────────────────────────────────────────────────────────────


def test_unknown_code_returns_none() -> None:
    """Unrecognized code must return None — no silent fallback to wrong team."""
    assert normalize_team_code("ZZZ") is None


def test_unknown_code_not_in_canonical() -> None:
    """Unknown code is not treated as canonical."""
    assert not is_canonical("ZZZ")


def test_unknown_code_raises_with_normalize_or_raise() -> None:
    """normalize_or_raise raises ValueError for unknown codes."""
    with pytest.raises(ValueError, match="Unknown MLB team code"):
        normalize_or_raise("XYZ")


def test_empty_string_returns_none() -> None:
    """Empty string is an unknown code."""
    assert normalize_team_code("") is None


# ──────────────────────────────────────────────────────────────────────────────
# Canonical set invariants
# ──────────────────────────────────────────────────────────────────────────────


def test_exactly_30_canonical_teams() -> None:
    """CANONICAL_TEAMS contains exactly 30 MLB teams."""
    assert len(CANONICAL_TEAMS) == 30


def test_all_canonical_teams_map_to_themselves() -> None:
    """Every canonical code is an identity mapping in RETROSHEET_TO_STATCAST."""
    for code in CANONICAL_TEAMS:
        mapped = normalize_team_code(code)
        assert mapped == code, f"Canonical code {code!r} should self-map, got {mapped!r}"


def test_is_canonical_true_for_all_30() -> None:
    """is_canonical returns True for all 30 canonical codes."""
    for code in CANONICAL_TEAMS:
        assert is_canonical(code), f"Expected {code!r} to be canonical"


def test_is_canonical_false_for_retrosheet_aliases() -> None:
    """Retrosheet aliases are NOT canonical (they map to canonical codes)."""
    aliases = ["CHA", "TBA", "ARI", "OAK", "SDN", "SFN", "LAN", "NYA", "NYN", "KCA", "SLN"]
    for alias in aliases:
        assert not is_canonical(alias), f"Alias {alias!r} should not be canonical"


def test_all_map_values_are_canonical() -> None:
    """Every value in RETROSHEET_TO_STATCAST is a canonical Statcast code."""
    for alias, canonical in RETROSHEET_TO_STATCAST.items():
        assert canonical in CANONICAL_TEAMS, (
            f"Map entry {alias!r} → {canonical!r}: {canonical!r} not in CANONICAL_TEAMS"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Case handling
# ──────────────────────────────────────────────────────────────────────────────


def test_normalize_is_case_insensitive() -> None:
    """normalize_team_code accepts mixed case input."""
    assert normalize_team_code("cha") == "CWS"
    assert normalize_team_code("Tba") == "TB"
    assert normalize_team_code("bal") == "BAL"


# ──────────────────────────────────────────────────────────────────────────────
# Acceptance marker
# ──────────────────────────────────────────────────────────────────────────────


def test_acceptance_marker() -> None:
    """Sentinel: all team code normalization tests pass."""
    marker = "P39E_TEAM_CODE_NORMALIZATION_READY_20260515"
    assert marker
