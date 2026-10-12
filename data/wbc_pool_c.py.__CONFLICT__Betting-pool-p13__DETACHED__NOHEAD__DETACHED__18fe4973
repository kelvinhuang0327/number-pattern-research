"""
WBC 2026 Pool C — Complete 10-game schedule with all 5 teams.

Teams: JPN, TPE, AUS, KOR, CZE
Venue: Tokyo Dome, Tokyo (all games)
Round: Pool C (pitch-count limit: 65 pitches)

Usage:
    from data.wbc_pool_c import fetch_wbc_match, list_wbc_matches

    matches = list_wbc_matches()           # all 10 games
    match   = fetch_wbc_match("C01")       # TPE vs AUS (03/05)
    match   = fetch_wbc_match("C04")       # JPN vs TPE (03/06)
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Tuple

from data.wbc_data import (
    PitcherStats, BatterStats, TeamStats, RosterVolatility,
    OddsLine, PitchCountRule, MatchData,
    _build_bullpen, _build_lineup,
)
from data.tsl_crawler import TSLCrawler


# ═══════════════════════════════════════════════════════════════════════════════
# ODDS HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def _std_odds(away: str, home: str, ts: str,
              ml_away: float, ml_home: float,
              rl_spread: float, rl_fav: str, rl_fav_odds: float, rl_dog_odds: float,
              ou_line: float, ou_over: float, ou_under: float,
              f5_away: float, f5_home: float,
              tt_away_line: float, tt_home_line: float) -> List[OddsLine]:
    """Generate standard TSL odds for a Pool C game."""
    rl_dog = home if rl_fav == away else away
    return [
        # ── 不讓分（獨贏）Money Line ──
        OddsLine("TSL", "ML", away, ml_away, timestamp=ts),
        OddsLine("TSL", "ML", home, ml_home, timestamp=ts),
        # ── 讓分 Run Line ──
        OddsLine("TSL", "RL", rl_fav, rl_fav_odds, line=-rl_spread, timestamp=ts),
        OddsLine("TSL", "RL", rl_dog, rl_dog_odds, line=+rl_spread, timestamp=ts),
        # ── 大小分 Over/Under ──
        OddsLine("TSL", "OU", "Over",  ou_over,  line=ou_line, timestamp=ts),
        OddsLine("TSL", "OU", "Under", ou_under, line=ou_line, timestamp=ts),
        # ── 單雙 Odd/Even ──
        OddsLine("TSL", "OE", "Odd",  1.90, timestamp=ts),
        OddsLine("TSL", "OE", "Even", 1.90, timestamp=ts),
        # ── 前五局獨贏 First 5 Innings ──
        OddsLine("TSL", "F5", away, f5_away, timestamp=ts),
        OddsLine("TSL", "F5", home, f5_home, timestamp=ts),
        # ── 隊伍總分 Team Totals ──
        OddsLine("TSL", "TT", f"{away}_Over",  1.85, line=tt_away_line, timestamp=ts),
        OddsLine("TSL", "TT", f"{away}_Under", 1.95, line=tt_away_line, timestamp=ts),
        OddsLine("TSL", "TT", f"{home}_Over",  1.85, line=tt_home_line, timestamp=ts),
        OddsLine("TSL", "TT", f"{home}_Under", 1.95, line=tt_home_line, timestamp=ts),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM DEFINITIONS — POOL C
# ═══════════════════════════════════════════════════════════════════════════════

def _team_jpn() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Japan — World #1, Pool C host at Tokyo Dome."""
    roster = RosterVolatility(
        roster_strength_index=98,  # Increased due to MLB heavy roster
        confirmed_stars=["Shohei Ohtani", "Yoshinobu Yamamoto", "Yusei Kikuchi",
                         "Munetaka Murakami", "Masataka Yoshida", "Seiya Suzuki",
                         "Kazuma Okamoto", "Shosei Togo"],
        uncertain_stars=["Hiroto Takahashi"],
        absent_stars=["Roki Sasaki", "Yuki Matsui", "Kaima Taira"],
        team_chemistry=0.88,
        mlb_player_count=12,
    )
    team = TeamStats(
        name="Japan", code="JPN", elo=1635,
        runs_per_game=6.0, runs_allowed_per_game=2.8,
        batting_avg=0.285, team_obp=0.360, team_slg=0.450,
        team_woba=0.362, bullpen_era=2.40,
        bullpen_pitches_3d=0,
        defense_efficiency=0.730, sb_success_rate=0.78,
        lineup_wrc_plus=135, clutch_woba=0.370,
        roster_vol=roster,
    )
    pitchers = {
        # ── Starting Pitchers ──
        "yamamoto": PitcherStats(
            name="Yoshinobu Yamamoto", team="JPN",
            era=3.10, fip=3.25, whip=1.12, k_per_9=10.4, bb_per_9=2.1,
            stuff_plus=125, ip_last_30=25.0, era_last_3=2.90,
            spring_era=2.40, pitch_count_last_3d=0,
            vs_left_ba=0.220, vs_right_ba=0.205,
            high_leverage_era=2.80, fastball_velo=96.5, role="SP",
        ),
        "kikuchi": PitcherStats(
            name="Yusei Kikuchi", team="JPN",
            era=3.65, fip=3.50, whip=1.20, k_per_9=10.5, bb_per_9=2.3,
            stuff_plus=115, ip_last_30=28.0, era_last_3=3.10,
            spring_era=2.80, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.225,
            high_leverage_era=3.20, fastball_velo=95.5, role="SP",
        ),
        "togo": PitcherStats(
            name="Shosei Togo", team="JPN",
            era=2.72, fip=3.10, whip=1.05, k_per_9=9.8, bb_per_9=2.0,
            stuff_plus=118, ip_last_30=24.0, era_last_3=2.50,
            spring_era=2.30, pitch_count_last_3d=0,
            vs_left_ba=0.215, vs_right_ba=0.200,
            high_leverage_era=2.90, fastball_velo=95.8, role="SP",
        ),
        "miyagi": PitcherStats(
            name="Hiroya Miyagi", team="JPN",
            era=2.85, fip=3.15, whip=1.10, k_per_9=9.0, bb_per_9=2.2,
            stuff_plus=115, ip_last_30=20.0, era_last_3=2.60,
            spring_era=2.70, pitch_count_last_3d=0,
            vs_left_ba=0.220, vs_right_ba=0.210,
            high_leverage_era=3.00, fastball_velo=93.5, role="SP",
        ),
        # ── Piggyback Starters ──
        "takahashi_pb": PitcherStats(
            name="Hiroto Takahashi", team="JPN",
            era=1.58, fip=2.40, whip=0.95, k_per_9=9.2, bb_per_9=1.8,
            stuff_plus=122, ip_last_30=18.0, era_last_3=1.20,
            spring_era=1.50, pitch_count_last_3d=0,
            vs_left_ba=0.190, vs_right_ba=0.185,
            high_leverage_era=1.40, fastball_velo=97.5, role="PB",
        ),
        "sugano_pb": PitcherStats(
            name="Tomoyuki Sugano", team="JPN",
            era=2.30, fip=2.80, whip=1.02, k_per_9=8.5, bb_per_9=1.5,
            stuff_plus=110, ip_last_30=16.0, era_last_3=2.10,
            spring_era=2.20, pitch_count_last_3d=0,
            vs_left_ba=0.210, vs_right_ba=0.205,
            high_leverage_era=2.50, fastball_velo=92.0, role="PB",
        ),
    }
    return team, pitchers


def _team_tpe() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Chinese Taipei — Pool C, Elo 1430."""
    roster = RosterVolatility(
        roster_strength_index=78,
        confirmed_stars=["Ku Lin Jui-Yang", "Lin Yu-Min", "Cheng Tsung-Che",
                         "Yu Chang", "Hsu Jo-Hsi"],
        uncertain_stars=["Lin An-Ko"],
        absent_stars=[],
        team_chemistry=0.85,
        mlb_player_count=4,
    )
    team = TeamStats(
        name="Chinese Taipei", code="TPE", elo=1430,
        runs_per_game=4.2, runs_allowed_per_game=3.8,
        batting_avg=0.274, team_obp=0.335, team_slg=0.405,
        team_woba=0.322, bullpen_era=3.45,
        bullpen_pitches_3d=0,
        defense_efficiency=0.708, sb_success_rate=0.72,
        lineup_wrc_plus=102, clutch_woba=0.310,
        roster_vol=roster,
    )
    pitchers = {
        # ── Starting Pitchers ──
        "kulin": PitcherStats(
            name="Ku Lin Jui-Yang", team="TPE",
            era=3.62, fip=3.45, whip=1.22, k_per_9=9.5, bb_per_9=2.8,
            stuff_plus=115, ip_last_30=32.1, era_last_3=3.50,
            spring_era=2.80, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.230,
            high_leverage_era=3.70, fastball_velo=96.1, role="SP",
        ),
        "lin_yumin": PitcherStats(
            name="Lin Yu-Min", team="TPE",
            era=3.20, fip=3.35, whip=1.18, k_per_9=9.0, bb_per_9=2.5,
            stuff_plus=108, ip_last_30=28.0, era_last_3=3.00,
            spring_era=2.90, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.225,
            high_leverage_era=3.50, fastball_velo=94.5, role="SP",
        ),
        "hsu_johsi": PitcherStats(
            name="Hsu Jo-Hsi", team="TPE",
            era=3.45, fip=3.60, whip=1.20, k_per_9=8.8, bb_per_9=2.6,
            stuff_plus=105, ip_last_30=20.0, era_last_3=3.20,
            spring_era=3.00, pitch_count_last_3d=0,
            vs_left_ba=0.248, vs_right_ba=0.232,
            high_leverage_era=3.60, fastball_velo=94.0, role="SP",
        ),
        "chen_kuanyu": PitcherStats(
            name="Chen Kuan-Yu", team="TPE",
            era=3.90, fip=3.85, whip=1.28, k_per_9=7.8, bb_per_9=3.0,
            stuff_plus=100, ip_last_30=18.0, era_last_3=3.70,
            spring_era=3.50, pitch_count_last_3d=0,
            vs_left_ba=0.252, vs_right_ba=0.240,
            high_leverage_era=4.10, fastball_velo=93.0, role="SP",
        ),
        # ── Piggyback Starters (第二先發) ──
        "kuo_chunlin_pb": PitcherStats(
            name="Kuo Chun-Lin", team="TPE",
            era=4.15, fip=4.20, whip=1.35, k_per_9=7.1, bb_per_9=3.2,
            stuff_plus=92, ip_last_30=0.0, era_last_3=0.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.265, vs_right_ba=0.258,
            high_leverage_era=4.50, fastball_velo=91.5, role="PB",
        ),
        "tseng_jinho_pb": PitcherStats(
            name="Tseng Jen-Ho", team="TPE",
            era=4.10, fip=4.20, whip=1.30, k_per_9=7.5, bb_per_9=3.2,
            stuff_plus=95, ip_last_30=14.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.255, vs_right_ba=0.242,
            high_leverage_era=4.30, fastball_velo=92.5, role="PB",
        ),
        "cheng": PitcherStats(
            name="Cheng Hao-Chun", team="TPE",
            era=3.10, fip=3.20, whip=1.15, k_per_9=10.2, bb_per_9=2.5,
            stuff_plus=118, ip_last_30=22.0, era_last_3=1.49,
            spring_era=1.80, pitch_count_last_3d=0,
            vs_left_ba=0.225, vs_right_ba=0.210,
            high_leverage_era=2.50, fastball_velo=96.1, role="SP",
        ),
    }
    return team, pitchers


def _team_aus() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Australia — Pool C, Elo 1380."""
    roster = RosterVolatility(
        roster_strength_index=70,
        confirmed_stars=["Jack O'Loughlin", "Curtis Mead",
                         "Aaron Whitefield", "Robbie Glendinning"],
        uncertain_stars=["Liam Spence"],
        absent_stars=[],
        team_chemistry=0.82,
        mlb_player_count=2,
    )
    team = TeamStats(
        name="Australia", code="AUS", elo=1380,
        runs_per_game=4.2, runs_allowed_per_game=5.1,
        batting_avg=0.245, team_obp=0.315, team_slg=0.385,
        team_woba=0.305, bullpen_era=4.85,
        bullpen_pitches_3d=0,
        defense_efficiency=0.695, sb_success_rate=0.72,
        lineup_wrc_plus=88, clutch_woba=0.295,
        roster_vol=roster,
    )
    pitchers = {
        # ── Starting Pitchers ──
        "wells": PitcherStats(
            name="Alex Wells", team="AUS",
            era=3.80, fip=4.10, whip=1.35, k_per_9=7.2, bb_per_9=3.0,
            stuff_plus=95, ip_last_30=18.0, era_last_3=3.50,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.250, vs_right_ba=0.265,
            high_leverage_era=4.20, fastball_velo=91.5, role="SP",
        ),
        "oloughlin": PitcherStats(
            name="Jack O'Loughlin", team="AUS",
            era=6.70, fip=5.85, whip=1.65, k_per_9=6.3, bb_per_9=3.2,
            stuff_plus=98, ip_last_30=15.0, era_last_3=6.10,
            spring_era=4.50, pitch_count_last_3d=0,
            vs_left_ba=0.275, vs_right_ba=0.290,
            high_leverage_era=5.80, fastball_velo=92.5, role="SP",
        ),
        "van_steensel": PitcherStats(
            name="Todd Van Steensel", team="AUS",
            era=4.50, fip=4.70, whip=1.40, k_per_9=7.0, bb_per_9=3.5,
            stuff_plus=92, ip_last_30=12.0, era_last_3=4.20,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.265, vs_right_ba=0.275,
            high_leverage_era=4.80, fastball_velo=91.0, role="SP",
        ),
        "neunborn": PitcherStats(
            name="Mitch Neunborn", team="AUS",
            era=5.20, fip=5.10, whip=1.50, k_per_9=6.8, bb_per_9=3.8,
            stuff_plus=90, ip_last_30=10.0, era_last_3=5.00,
            spring_era=4.50, pitch_count_last_3d=0,
            vs_left_ba=0.270, vs_right_ba=0.280,
            high_leverage_era=5.50, fastball_velo=90.5, role="SP",
        ),
        # ── Piggyback Starters (第二先發) ──
        "spence_pb": PitcherStats(
            name="Liam Spence", team="AUS",
            era=5.50, fip=5.30, whip=1.55, k_per_9=6.5, bb_per_9=3.6,
            stuff_plus=88, ip_last_30=8.0, era_last_3=5.20,
            spring_era=4.80, pitch_count_last_3d=0,
            vs_left_ba=0.278, vs_right_ba=0.285,
            high_leverage_era=5.80, fastball_velo=89.5, role="PB",
        ),
        "mead_pb": PitcherStats(
            name="Riley Mead", team="AUS",
            era=5.80, fip=5.50, whip=1.58, k_per_9=6.2, bb_per_9=3.8,
            stuff_plus=85, ip_last_30=8.0, era_last_3=5.50,
            spring_era=5.00, pitch_count_last_3d=0,
            vs_left_ba=0.280, vs_right_ba=0.290,
            high_leverage_era=6.00, fastball_velo=89.0, role="PB",
        ),
        "hendrickson": PitcherStats(
            name="Josh Hendrickson", team="AUS",
            era=3.95, fip=4.05, whip=1.30, k_per_9=8.2, bb_per_9=2.6,
            stuff_plus=102, ip_last_30=20.0, era_last_3=3.80,
            spring_era=3.50, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.255,
            high_leverage_era=4.00, fastball_velo=93.5, role="SP",
        ),
    }
    return team, pitchers


def _team_kor() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """South Korea — Pool C, Elo 1510. Strong KBO + MLB presence."""
    roster = RosterVolatility(
        roster_strength_index=85,
        confirmed_stars=["Lee Jung-Hoo", "Kim Ha-Seong", "Go Woo-Suk",
                         "Kim Do-yeong", "Won Tae-In"],
        uncertain_stars=["An Woo-Jin"],
        absent_stars=[],
        team_chemistry=0.83,
        mlb_player_count=5,
    )
    team = TeamStats(
        name="South Korea", code="KOR", elo=1510,
        runs_per_game=4.8, runs_allowed_per_game=3.5,
        batting_avg=0.275, team_obp=0.342, team_slg=0.425,
        team_woba=0.338, bullpen_era=3.10,
        bullpen_pitches_3d=0,
        defense_efficiency=0.715, sb_success_rate=0.75,
        lineup_wrc_plus=118, clutch_woba=0.330,
        roster_vol=roster,
    )
    pitchers = {
        # ── Starting Pitchers ──
        "ko_youngpyo": PitcherStats(
            name="Ko Young-pyo", team="KOR",
            era=2.95, fip=3.20, whip=1.10, k_per_9=7.8, bb_per_9=1.2,
            stuff_plus=105, ip_last_30=25.0, era_last_3=2.70,
            spring_era=3.10, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.215,
            high_leverage_era=3.20, fastball_velo=88.5, role="SP",
        ),
        "an_woojin": PitcherStats(
            name="An Woo-Jin", team="KOR",
            era=3.10, fip=3.25, whip=1.15, k_per_9=9.2, bb_per_9=2.5,
            stuff_plus=110, ip_last_30=24.0, era_last_3=2.80,
            spring_era=2.70, pitch_count_last_3d=0,
            vs_left_ba=0.235, vs_right_ba=0.220,
            high_leverage_era=3.20, fastball_velo=95.0, role="SP",
        ),
        "kim_kwanghyun": PitcherStats(
            name="Kim Kwang-Hyun", team="KOR",
            era=3.40, fip=3.55, whip=1.20, k_per_9=7.8, bb_per_9=2.4,
            stuff_plus=105, ip_last_30=22.0, era_last_3=3.20,
            spring_era=3.00, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.228,
            high_leverage_era=3.50, fastball_velo=92.0, role="SP",
        ),
        "koo_changmo": PitcherStats(
            name="Koo Chang-Mo", team="KOR",
            era=3.60, fip=3.70, whip=1.22, k_per_9=8.0, bb_per_9=2.6,
            stuff_plus=102, ip_last_30=20.0, era_last_3=3.40,
            spring_era=3.20, pitch_count_last_3d=0,
            vs_left_ba=0.242, vs_right_ba=0.232,
            high_leverage_era=3.80, fastball_velo=93.0, role="SP",
        ),
        # ── Piggyback Starters (第二先發) ──
        "go_woosuk_pb": PitcherStats(
            name="Go Woo-Suk", team="KOR",
            era=2.50, fip=2.80, whip=0.98, k_per_9=11.0, bb_per_9=2.8,
            stuff_plus=125, ip_last_30=10.0, era_last_3=2.20,
            spring_era=2.00, pitch_count_last_3d=0,
            vs_left_ba=0.195, vs_right_ba=0.185,
            high_leverage_era=2.30, fastball_velo=97.5, role="PB",
        ),
        "ryu_pb": PitcherStats(
            name="Hyun-Jin Ryu", team="KOR",
            era=4.20, fip=4.00, whip=1.28, k_per_9=7.2, bb_per_9=2.0,
            stuff_plus=98, ip_last_30=12.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.248, vs_right_ba=0.235,
            high_leverage_era=4.30, fastball_velo=89.5, role="PB",
        ),
    }
    return team, pitchers


def _team_cze() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Czech Republic — Pool C wildcard, Elo 1200. Mostly domestic league."""
    roster = RosterVolatility(
        roster_strength_index=45,
        confirmed_stars=["Martin Schneider", "Martin Cervenka", "Eric Sogard"],
        uncertain_stars=[],
        absent_stars=[],
        team_chemistry=0.78,
        mlb_player_count=0,
    )
    team = TeamStats(
        name="Czech Republic", code="CZE", elo=1200,
        runs_per_game=3.2, runs_allowed_per_game=5.5,
        batting_avg=0.235, team_obp=0.295, team_slg=0.340,
        team_woba=0.280, bullpen_era=5.50,
        bullpen_pitches_3d=0,
        defense_efficiency=0.680, sb_success_rate=0.65,
        lineup_wrc_plus=72, clutch_woba=0.270,
        roster_vol=roster,
    )
    pitchers = {
        # ── Starting Pitchers ──
        "schneider": PitcherStats(
            name="Martin Schneider", team="CZE",
            era=4.50, fip=4.80, whip=1.42, k_per_9=6.5, bb_per_9=3.5,
            stuff_plus=85, ip_last_30=14.0, era_last_3=4.20,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.270, vs_right_ba=0.280,
            high_leverage_era=5.00, fastball_velo=90.0, role="SP",
        ),
        "padysak": PitcherStats(
            name="Daniel Padysak", team="CZE",
            era=5.10, fip=5.30, whip=1.52, k_per_9=5.8, bb_per_9=4.0,
            stuff_plus=80, ip_last_30=10.0, era_last_3=4.80,
            spring_era=4.50, pitch_count_last_3d=0,
            vs_left_ba=0.280, vs_right_ba=0.290,
            high_leverage_era=5.50, fastball_velo=88.5, role="SP",
        ),
        "novak": PitcherStats(
            name="Jan Novak", team="CZE",
            era=5.50, fip=5.60, whip=1.58, k_per_9=5.5, bb_per_9=4.2,
            stuff_plus=78, ip_last_30=8.0, era_last_3=5.20,
            spring_era=5.00, pitch_count_last_3d=0,
            vs_left_ba=0.285, vs_right_ba=0.295,
            high_leverage_era=5.80, fastball_velo=87.5, role="SP",
        ),
        # ── Piggyback Starters (第二先發) ──
        "ondra_pb": PitcherStats(
            name="Tomas Ondra", team="CZE",
            era=5.80, fip=5.90, whip=1.60, k_per_9=5.2, bb_per_9=4.5,
            stuff_plus=75, ip_last_30=6.0, era_last_3=5.50,
            spring_era=5.20, pitch_count_last_3d=0,
            vs_left_ba=0.290, vs_right_ba=0.300,
            high_leverage_era=6.00, fastball_velo=87.0, role="PB",
        ),
    }
    return team, pitchers


# ── Team factory registry ────────────────────────────────────────────────────

_TEAM_FACTORIES = {
    "JPN": _team_jpn,
    "TPE": _team_tpe,
    "AUS": _team_aus,
    "KOR": _team_kor,
    "CZE": _team_cze,
}


# ═══════════════════════════════════════════════════════════════════════════════
# POOL C GAME SCHEDULE (10 games)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Bullpen fatigue (bullpen_pitches_3d) estimated at ~65 pitches per game.
# In production, these values are replaced with actual data after each game.
#
# SP Rotation Logic (pitch-count 65 → ≥50 pitches requires 4 days rest):
#   JPN: C04 Yamamoto → C06 Imanaga → C08 Togo → C10 Yamamoto
#   TPE: C01 Lin Yu-Min → C04 Ku Lin → C05 Hsu Jo-Hsi → C07 Chen Kuan-Yu
#   AUS: C01 O'Loughlin → C03 Van Steensel → C08 Neunborn → C09 O'Loughlin
#   KOR: C02 An Woo-Jin → C06 Won Tae-In → C07 Kim Kwang-Hyun → C09 Koo Chang-Mo
#   CZE: C02 Schneider → C03 Padysak → C05 Novak → C10 Schneider
#

_POOL_C_SCHEDULE = [
    # ─── Day 1: March 5 ──────────────────────────────────────────────────────
    {
        "game_id": "C01",
        "date": "2026-03-05",
        "game_time": "2026-03-05T12:00:00+09:00",
        "tw_time": "03/05 11:00",
        "away_code": "TPE",
        "home_code": "AUS",
        "away_sp": "hsu_johsi",
        "home_sp": "wells",
        "away_pb": "kuo_chunlin_pb",
        "home_pb": "spence_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.40, "ml_home": 2.19,
            "rl_spread": 1.5, "rl_fav": "TPE", "rl_fav_odds": 2.10, "rl_dog_odds": 1.78,
            "ou_line": 8.0, "ou_over": 1.95, "ou_under": 1.88,
            "f5_away": 1.65, "f5_home": 2.25,
            "tt_away_line": 4.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "C02",
        "date": "2026-03-05",
        "game_time": "2026-03-05T19:00:00+09:00",
        "tw_time": "03/05 18:00",
        "away_code": "CZE",
        "home_code": "KOR",
        "away_sp": "schneider",
        "home_sp": "an_woojin",
        "away_pb": "ondra_pb",
        "home_pb": "ryu_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 4.20, "ml_home": 1.25,
            "rl_spread": 2.5, "rl_fav": "KOR", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 3.30, "f5_home": 1.35,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 2: March 6 ──────────────────────────────────────────────────────
    {
        "game_id": "C03",
        "date": "2026-03-06",
        "game_time": "2026-03-06T12:00:00+09:00",
        "tw_time": "03/06 11:00",
        "away_code": "AUS",
        "home_code": "CZE",
        "away_sp": "hendrickson",
        "home_sp": "padysak",
        "away_pb": "mead_pb",
        "home_pb": "ondra_pb",
        "away_bp_pitches_3d": 65,   # AUS played C01
        "home_bp_pitches_3d": 65,   # CZE played C02
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.20, "ml_home": 4.75,
            "rl_spread": 1.5, "rl_fav": "AUS", "rl_fav_odds": 1.65, "rl_dog_odds": 2.25,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.35, "f5_home": 3.20,
            "tt_away_line": 4.5, "tt_home_line": 2.5,
        },
    },
    {
        "game_id": "C04",
        "date": "2026-03-06",
        "game_time": "2026-03-06T19:00:00+09:00",
        "tw_time": "03/06 18:00",
        "away_code": "TPE",
        "home_code": "JPN",
        "away_sp": "cheng",
        "home_sp": "yamamoto",
        "away_pb": "tseng_jinho_pb",
        "home_pb": "takahashi_pb",
        "away_bp_pitches_3d": 65,   # TPE played C01
        "home_bp_pitches_3d": 0,    # JPN first game
        "neutral_site": False,       # JPN home at Tokyo Dome
        "odds_params": {
            "ml_away": 7.00, "ml_home": 1.10,
            "rl_spread": 4.5, "rl_fav": "JPN", "rl_fav_odds": 1.62, "rl_dog_odds": 1.85,
            "ou_line": 7.5, "ou_over": 1.70, "ou_under": 1.95,
            "f5_away": 4.20, "f5_home": 1.25,
            "tt_away_line": 1.5, "tt_home_line": 5.5,
        },
    },
    # ─── Day 3: March 7 ──────────────────────────────────────────────────────
    {
        "game_id": "C05",
        "date": "2026-03-07",
        "game_time": "2026-03-07T12:00:00+09:00",
        "tw_time": "03/07 11:00",
        "away_code": "TPE",
        "home_code": "CZE",
        "away_sp": "hsu_johsi",
        "home_sp": "novak",
        "away_pb": "huang_ensih_pb",
        "home_pb": "ondra_pb",
        "away_bp_pitches_3d": 130,  # TPE played C01+C04
        "home_bp_pitches_3d": 130,  # CZE played C02+C03
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.35, "ml_home": 3.50,
            "rl_spread": 2.5, "rl_fav": "TPE", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.42, "f5_home": 3.00,
            "tt_away_line": 4.5, "tt_home_line": 2.5,
        },
    },
    {
        "game_id": "C06",
        "date": "2026-03-07",
        "game_time": "2026-03-07T19:00:00+09:00",
        "tw_time": "03/07 18:00",
        "away_code": "KOR",
        "home_code": "JPN",
        "away_sp": "ko_youngpyo",
        "home_sp": "kikuchi",
        "away_pb": "go_woosuk_pb",
        "home_pb": "takahashi_pb",
        "away_bp_pitches_3d": 65,   # KOR played C02
        "home_bp_pitches_3d": 65,   # JPN played C04
        "neutral_site": False,       # JPN home
        "odds_params": {
            "ml_away": 2.45, "ml_home": 1.60,
            "rl_spread": 1.5, "rl_fav": "JPN", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 7.5, "ou_over": 1.90, "ou_under": 1.90,
            "f5_away": 2.35, "f5_home": 1.65,
            "tt_away_line": 3.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 4: March 8 ──────────────────────────────────────────────────────
    {
        "game_id": "C07",
        "date": "2026-03-08",
        "game_time": "2026-03-08T12:00:00+09:00",
        "tw_time": "03/08 11:00",
        "away_code": "TPE",
        "home_code": "KOR",
        "away_sp": "chen_kuanyu",
        "home_sp": "kim_kwanghyun",
        "away_pb": "tseng_jinho_pb",
        "home_pb": "ryu_pb",
        "away_bp_pitches_3d": 170,  # TPE: C01+C04+C05 (3 games in 3 days — HEAVY)
        "home_bp_pitches_3d": 130,  # KOR: C02+C06
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.20, "ml_home": 1.72,
            "rl_spread": 1.5, "rl_fav": "KOR", "rl_fav_odds": 2.15, "rl_dog_odds": 1.72,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.15, "f5_home": 1.75,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "C08",
        "date": "2026-03-08",
        "game_time": "2026-03-08T19:00:00+09:00",
        "tw_time": "03/08 18:00",
        "away_code": "AUS",
        "home_code": "JPN",
        "away_sp": "neunborn",
        "home_sp": "togo",
        "away_pb": "mead_pb",
        "home_pb": "miyagi_pb",
        "away_bp_pitches_3d": 130,  # AUS: C01+C03
        "home_bp_pitches_3d": 130,  # JPN: C04+C06
        "neutral_site": False,       # JPN home
        "odds_params": {
            "ml_away": 4.50, "ml_home": 1.22,
            "rl_spread": 2.5, "rl_fav": "JPN", "rl_fav_odds": 1.80, "rl_dog_odds": 2.00,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 3.60, "f5_home": 1.30,
            "tt_away_line": 2.5, "tt_home_line": 5.5,
        },
    },
    # ─── Day 5: March 9 ──────────────────────────────────────────────────────
    {
        "game_id": "C09",
        "date": "2026-03-09",
        "game_time": "2026-03-09T19:00:00+09:00",
        "tw_time": "03/09 18:00",
        "away_code": "KOR",
        "home_code": "AUS",
        "away_sp": "koo_changmo",
        "home_sp": "oloughlin",     # O'Loughlin back (4 days rest since C01)
        "away_pb": "ryu_pb",
        "home_pb": "spence_pb",
        "away_bp_pitches_3d": 130,  # KOR: C06+C07
        "home_bp_pitches_3d": 130,  # AUS: C03+C08 (C01 dropped from 3-day window)
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.52, "ml_home": 2.65,
            "rl_spread": 1.5, "rl_fav": "KOR", "rl_fav_odds": 1.95, "rl_dog_odds": 1.85,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.58, "f5_home": 2.50,
            "tt_away_line": 4.5, "tt_home_line": 3.5,
        },
    },
    # ─── Day 6: March 10 ─────────────────────────────────────────────────────
    {
        "game_id": "C10",
        "date": "2026-03-10",
        "game_time": "2026-03-10T19:00:00+09:00",
        "tw_time": "03/10 18:00",
        "away_code": "CZE",
        "home_code": "JPN",
        "away_sp": "schneider",     # Schneider back (5 days rest since C02)
        "home_sp": "yamamoto",      # Yamamoto back (4 days rest since C04)
        "away_pb": "ondra_pb",
        "home_pb": "takahashi_pb",
        "away_bp_pitches_3d": 65,   # CZE: C05 only (C02+C03 dropped from window)
        "home_bp_pitches_3d": 130,  # JPN: C06+C08 (C04 dropped from window)
        "neutral_site": False,       # JPN home
        "odds_params": {
            "ml_away": 8.00, "ml_home": 1.10,
            "rl_spread": 3.5, "rl_fav": "JPN", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 9.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 6.00, "f5_home": 1.15,
            "tt_away_line": 2.5, "tt_home_line": 6.5,
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# CHINESE-NAME → CODE MAPPING (for TSL live crawler)
# ═══════════════════════════════════════════════════════════════════════════════

_CHINESE_TEAM_NAMES = {
    "日本": "JPN",
    "中華台北": "TPE",
    "澳洲": "AUS",
    "南韓": "KOR",
    "韓國": "KOR",
    "捷克": "CZE",
}

_CODE_TO_CHINESE = {v: k for k, v in _CHINESE_TEAM_NAMES.items() if k != "韓國"}


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def list_wbc_matches() -> List[dict]:
    """Return Pool C schedule summary.

    >>> for g in list_wbc_matches():
    ...     print(f"{g['game_id']}  {g['tw_time']}  {g['away']} vs {g['home']}")
    C01  03/05 11:00  TPE vs AUS
    C02  03/05 18:00  CZE vs KOR
    ...
    """
    return [
        {
            "game_id": g["game_id"],
            "date": g["date"],
            "tw_time": g["tw_time"],
            "away": g["away_code"],
            "home": g["home_code"],
            "game_time": g["game_time"],
        }
        for g in _POOL_C_SCHEDULE
    ]


def fetch_wbc_match(game_id: str,
                    live: bool = False,
                    use_mock: bool = False) -> MatchData:
    """Fetch a specific WBC 2026 Pool C game by game_id (C01–C10).

    Parameters
    ----------
    game_id : str
        Game identifier, e.g. "C01" for TPE vs AUS on 03/05.
    live : bool
        If True, attempts to fetch real-time TSL odds via crawler.
    use_mock : bool
        If True, uses mock data in the TSL crawler.

    Returns
    -------
    MatchData
        Complete match data ready for the ensemble model pipeline.
    """
    # ── Look up game in schedule ──
    game = None
    for g in _POOL_C_SCHEDULE:
        if g["game_id"] == game_id.upper():
            game = g
            break
    if game is None:
        available = [g["game_id"] for g in _POOL_C_SCHEDULE]
        raise ValueError(
            f"Unknown game_id '{game_id}'. Available: {available}"
        )

    # ── Build team data ──
    away_code = game["away_code"]
    home_code = game["home_code"]
    away_team, away_pitchers = _TEAM_FACTORIES[away_code]()
    home_team, home_pitchers = _TEAM_FACTORIES[home_code]()

    # Apply bullpen fatigue
    away_team.bullpen_pitches_3d = game["away_bp_pitches_3d"]
    home_team.bullpen_pitches_3d = game["home_bp_pitches_3d"]

    # ── Pitch count rule (Pool round: max 65) ──
    pc_rule = PitchCountRule(
        round_name="Pool C",
        max_pitches=65,
        rest_after_30=1,
        rest_after_50=4,
        expected_sp_innings=3.5,
    )

    # ── Build odds ──
    ts = game["game_time"].replace("+09:00", "Z").replace("T", "T")
    p = game["odds_params"]
    odds = _std_odds(
        away_code, home_code, ts,
        ml_away=p["ml_away"], ml_home=p["ml_home"],
        rl_spread=p["rl_spread"], rl_fav=p["rl_fav"],
        rl_fav_odds=p["rl_fav_odds"], rl_dog_odds=p["rl_dog_odds"],
        ou_line=p["ou_line"], ou_over=p["ou_over"], ou_under=p["ou_under"],
        f5_away=p["f5_away"], f5_home=p["f5_home"],
        tt_away_line=p["tt_away_line"], tt_home_line=p["tt_home_line"],
    )

    # ── Live odds override ──
    if live:
        away_cn = _CODE_TO_CHINESE.get(away_code, away_code)
        home_cn = _CODE_TO_CHINESE.get(home_code, home_code)
        try:
            crawler = TSLCrawler(use_mock=use_mock)
            live_match = crawler.parse_wbc_match(home_cn, away_cn)
            if live_match:
                new_odds = []
                for m_type, outcomes in live_match.markets.items():
                    for side, details in outcomes.items():
                        side_code = _CHINESE_TEAM_NAMES.get(side, side)
                        if side == "大": side_code = "Over"
                        elif side == "小": side_code = "Under"
                        elif side == "單": side_code = "Odd"
                        elif side == "雙": side_code = "Even"
                        new_odds.append(OddsLine(
                            book="TSL", market=m_type, side=side_code,
                            price=details["price"], line=details.get("line"),
                            timestamp=datetime.datetime.now().isoformat(),
                        ))
                if new_odds:
                    odds = new_odds
        except Exception:
            pass  # fallback to seed odds

    # ── Resolve SP / PB ──
    away_sp = away_pitchers[game["away_sp"]]
    home_sp = home_pitchers[game["home_sp"]]
    away_pb = away_pitchers.get(game.get("away_pb"))
    home_pb = home_pitchers.get(game.get("home_pb"))

    # ── Build bullpens & lineups ──
    away_bp_stuff = 100.0
    home_bp_stuff = 100.0
    if away_code == "JPN": away_bp_stuff = 120.0
    elif away_code == "KOR": away_bp_stuff = 110.0
    elif away_code == "CZE": away_bp_stuff = 78.0
    stuff = {
        "JPN": 120.0,
        "KOR": 110.0,
        "CZE": 78.0,
    }

    return MatchData(
        home=home_team,
        away=away_team,
        home_sp=home_sp,
        away_sp=away_sp,
        home_piggyback=home_pb,
        away_piggyback=away_pb,
        home_bullpen=_build_bullpen(
            home_code, home_team.bullpen_era,
            game["home_bp_pitches_3d"], avg_stuff=stuff.get(home_code, 90),
        ),
        away_bullpen=_build_bullpen(
            away_code, away_team.bullpen_era,
            game["away_bp_pitches_3d"], avg_stuff=stuff.get(away_code, 90),
        ),
        home_lineup=_build_lineup(
            home_code, home_team.batting_avg,
            home_team.team_obp, home_team.team_slg,
            woba=home_team.team_woba,
            wrc_plus=home_team.lineup_wrc_plus,
        ),
        away_lineup=_build_lineup(
            away_code, away_team.batting_avg,
            away_team.team_obp, away_team.team_slg,
            woba=away_team.team_woba,
            wrc_plus=away_team.lineup_wrc_plus,
        ),
        odds=odds,
        pitch_count_rule=pc_rule,
        game_time=game["game_time"],
        venue="Tokyo Dome, Tokyo",
        round_name="Pool C",
        neutral_site=game["neutral_site"],
        data_source= "MIXED (Pinnacle 國際盤 + 陣容 Seed)" if game_id.upper() == "C01" else "MOCK/SEED (人工建置模擬賽前盤口)",
        liquidity_level= "HIGH (國際主流盤口水流)" if game_id.upper() == "C01" else "LOW (尚未開盤)"
    )


def fetch_all_pool_c(live: bool = False,
                     use_mock: bool = False) -> List[MatchData]:
    """Fetch all 10 Pool C games."""
    return [fetch_wbc_match(g["game_id"], live=live, use_mock=use_mock)
            for g in _POOL_C_SCHEDULE]
