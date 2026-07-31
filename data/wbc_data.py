"""
WBC 2026 data provider.

In production this module would call live APIs (MLB Stats API, Odds API, etc.).
For the initial build it ships with curated seed data so every downstream module
can run end-to-end without network access.

Optimized for:
  • WBC pitch-count limits per round
  • Data recency weighting (spring training > season avg)
  • Roster volatility & star-player participation
  • Taiwan Sports Lottery (TSL) market coverage including 單雙 (Odd/Even)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import datetime
from data.tsl_crawler import TSLCrawler


# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class PitcherStats:
    name: str
    team: str
    era: float
    fip: float                     # Fielding Independent Pitching
    whip: float
    k_per_9: float
    bb_per_9: float
    stuff_plus: float              # Stuff+ metric (100 = avg)
    ip_last_30: float              # innings pitched last 30 days
    era_last_3: float              # ERA in last 3 games
    spring_era: float              # 2026 spring training ERA
    pitch_count_last_3d: int       # total pitches last 3 days (fatigue)
    vs_left_ba: float              # BA allowed vs LHB
    vs_right_ba: float             # BA allowed vs RHB
    high_leverage_era: float       # ERA in high-leverage situations
    fastball_velo: float           # average fastball velocity (mph)
    role: str = "SP"               # SP | RP | PB (piggyback)


@dataclass
class BatterStats:
    name: str
    team: str
    avg: float
    obp: float
    slg: float
    ops: float
    woba: float                    # weighted on-base average
    ops_plus: float                # OPS+ (100 = league avg)
    avg_last_30: float
    avg_last_3: float
    spring_avg: float              # 2026 spring training avg
    vs_left_avg: float
    vs_right_avg: float
    high_leverage_ops: float
    swstr_vs_98: float             # SwStr% vs 98mph+ fastballs
    clutch_woba: float             # wOBA in high-leverage plate appearances
    sb_success_rate: float


@dataclass
class RosterVolatility:
    """Tracks star-player participation and roster completeness."""
    roster_strength_index: float   # 0-100 (100 = best-possible roster)
    confirmed_stars: List[str]     # names of confirmed star players
    uncertain_stars: List[str]     # names with uncertain participation
    absent_stars: List[str]        # confirmed absent key players
    team_chemistry: float          # 0-1 (磨合度, 1 = well-drilled)
    mlb_player_count: int          # number of active MLB rostered players


@dataclass
class TeamStats:
    name: str
    code: str                     # 3-letter ISO-like code
    elo: float                    # Elo rating
    runs_per_game: float
    runs_allowed_per_game: float
    batting_avg: float
    team_obp: float
    team_slg: float
    team_woba: float              # team aggregate wOBA
    bullpen_era: float
    bullpen_pitches_3d: int       # pitches thrown by bullpen last 3 days
    defense_efficiency: float     # DER
    sb_success_rate: float
    lineup_wrc_plus: float        # wRC+ of projected lineup
    clutch_woba: float            # team clutch wOBA
    roster_vol: Optional[RosterVolatility] = None
    roster: List[str] = field(default_factory=list)


@dataclass
class OddsLine:
    book: str
    market: str          # ML | RL | OU | OE | F5 | TT
    side: str            # team code or "Over"/"Under"/"Odd"/"Even"
    price: float         # decimal odds
    line: Optional[float] = None   # spread / total
    timestamp: str = ""


@dataclass
class PitchCountRule:
    """WBC pitch-count rules for this match's round."""
    round_name: str
    max_pitches: int
    rest_after_30: int     # days rest if ≥30 pitches
    rest_after_50: int     # days rest if ≥50 pitches
    expected_sp_innings: float


@dataclass
class MatchData:
    home: TeamStats
    away: TeamStats
    home_sp: PitcherStats
    away_sp: PitcherStats
    home_piggyback: Optional[PitcherStats]   # 第二先發
    away_piggyback: Optional[PitcherStats]   # 第二先發
    home_bullpen: List[PitcherStats]
    away_bullpen: List[PitcherStats]
    home_lineup: List[BatterStats]
    away_lineup: List[BatterStats]
    odds: List[OddsLine]
    pitch_count_rule: PitchCountRule
    game_time: str
    venue: str
    round_name: str            # "Pool A" / "Quarter-Final" / etc.
    neutral_site: bool = True
    game_type: str = "INTERNATIONAL" # INTERNATIONAL | PROFESSIONAL
    steam_move: float = 0.0          # Market sentiment shift
    data_source: str = "MOCK/SEED (人工建置)"
    liquidity_level: str = "LOW (盤口深度未知)"


# ─── Seed Data Generator ─────────────────────────────────────────────────────

def _build_bullpen(team: str, era: float, pitches_3d: int,
                   avg_stuff: float = 100.0) -> List[PitcherStats]:
    """Generate a simplified 4-man bullpen with full PitcherStats fields."""
    names = {
        "JPN": ["Yuki Matsui", "Hiroya Miyagi", "Taisei Ota", "Tomoyuki Sugano"],
        "USA": ["Clay Holmes", "Mason Miller", "Clayton Kershaw", "Tarik Skubal"],
        "KOR": ["Woo-Suk Go", "Hyun-Jin Ryu", "Byung-Hyun Cho", "Yeong-hyeon Park"],
        "TPE": ["Tseng Chun-Yueh", "Hsu Jo-Hsi", "Lin Yu-Min", "Chen Po-Yu"],
        "DOM": ["Emmanuel Clase", "Camilo Doval", "Yennier Cano", "Wandy Peralta"],
        "MEX": ["Andrés Muñoz", "Javier Assad", "Taj Bradley", "Taijuan Walker"],
        "PUR": ["Edwin Díaz", "Jorge López", "Seth Lugo", "Jose De León"],
        "CUB": ["Raidel Martinez", "Livan Moinelo", "Yariel Rodríguez", "Yoan López"],
        "CAN": ["James Paxton", "Cal Quantrill", "Michael Soroka", "Jameson Taillon"],
        "PAN": ["Javy Guerra", "Ariel Jurado", "Jaime Barria", "Paolo Espino"],
        "COL": ["Jose Quintana", "Julio Teheran", "Nabil Crismatt", "Luis Patiño"],
        "ITA": ["Jordan Romano", "Andre Pallante", "Joe Biagini", "Samuel Aldegheri"],
        "GBR": ["Vance Worley", "Tristan Beck", "Chavez Fernander", "Michael Petersen"],
        "BRA": ["Thyago Vieira", "Bo Takahashi", "Eric Pardinho", "Daniel Misaki"],
        "AUS": ["Jack O'Loughlin", "Todd Van Steensel", "Mitch Neunborn", "Liam Spence (P)"],
        "CZE": ["Martin Schneider", "Daniel Padysak", "Jan Novak", "Tomas Ondra"],
        "VEN": ["Pablo Lopez", "Jose Alvarado", "Ranger Suarez", "German Marquez"],
        "NED": ["Kenley Jansen", "Lars Huijer", "Shairon Martis", "Jaydenn Estanista"],
        "ISR": ["Dean Kremer", "Tommy Kahnle", "Eli Morgan", "Matt Bowman"],
        "NIC": ["Erasmo Ramírez", "J. C. Ramírez", "Carlos Rodriguez", "Duque Hebbert"],
    }
    pen = []
    for i, n in enumerate(names.get(team, ["RP1", "RP2", "RP3", "RP4"])):
        pen.append(PitcherStats(
            name=n, team=team,
            era=era + (i * 0.15 - 0.2),
            fip=era + (i * 0.12 - 0.15),
            whip=1.10 + i * 0.03,
            k_per_9=10.2 - i * 0.4,
            bb_per_9=2.8 + i * 0.2,
            stuff_plus=avg_stuff - i * 3,
            ip_last_30=12.0 - i,
            era_last_3=era + 0.30,
            spring_era=era + 0.20,
            pitch_count_last_3d=pitches_3d // 4,
            vs_left_ba=0.230 + i * 0.005,
            vs_right_ba=0.210 + i * 0.005,
            high_leverage_era=era + 0.5,
            fastball_velo=95.0 - i * 1.2,
            role="RP",
        ))
    return pen


def _build_lineup(team: str, avg: float, obp: float, slg: float,
                  woba: float = 0.340, wrc_plus: float = 110.0,
                  spring_adj: float = 0.0) -> List[BatterStats]:
    """Generate a 9-man lineup with slot variance and full BatterStats fields."""
    stubs = {
        "JPN": ["Shohei Ohtani", "Lars Nootbaar", "Masataka Yoshida",
                 "Munetaka Murakami", "Kensuke Kondoh", "Seiya Suzuki",
                 "Sosuke Genda", "Shugo Maki", "Kazuma Okamoto"],
        "USA": ["Aaron Judge", "Bryce Harper", "Paul Goldschmidt",
                 "Alex Bregman", "Bobby Witt Jr.", "Gunnar Henderson",
                 "Will Smith", "Brice Turang", "Corbin Carroll"],
        "KOR": ["Lee Jung-Hoo", "Kim Ha-Seong", "Kim Do-yeong",
                 "Ahn Hyun-Min", "Koo Ja-wook", "Yang Eui-Ji",
                 "Noh Si-Hwan", "Shin Min-jae", "Park Hae-min"],
        "TPE": ["Chen Chieh-Hsien", "Lin Li", "Lin An-Ko",
                 "Yu Chang", "Cheng Tsung-Che", "Lee Hao-Yu",
                 "Chiang Kun-Yu", "Wu Nien-Ting", "Chen Chen-Wei"],
        "DOM": ["Juan Soto", "Vladimir Guerrero Jr.", "Rafael Devers",
                 "Manny Machado", "Ketel Marte", "Teoscar Hernández",
                 "Julio Rodriguez", "Starling Marte", "José Ramírez"],
        "MEX": ["Randy Arozarena", "Jarren Duran", "Isaac Paredes",
                 "Rowdy Tellez", "Joey Meneses", "Luis Urías",
                 "Alejandro Kirk", "Joey Ortiz", "Ramón Urías"],
        "PUR": ["Francisco Lindor", "Carlos Correa", "Nolan Arenado",
                 "MJ Melendez", "Heliot Ramos", "Willi Castro",
                 "MJ Melendez", "MJ Melendez", "MJ Melendez"], # Note: Lindor/Correa mapping
        "CUB": ["Yoán Moncada", "Luis Robert", "Randy Arozarena (CUB)", # mapping
                 "Alfredo Despaigne", "Yoelkis Guibert", "Ariel Martinez",
                 "Erisbel Arruebarrena", "Alexei Ramirez", "Yoel Yanqui"],
        "CAN": ["Freddie Freeman", "Tyler O'Neill", "Joey Votto",
                 "Edouard Julien", "Charles Leblanc", "Bo Naylor",
                 "Owen Caissie", "Abraham Toro", "Otto Lopez"],
        "PAN": ["Edmundo Sosa", "Jose Caballero", "Christian Bethancourt",
                 "Ivan Herrera", "Jonathan Arauz", "Johan Camargo",
                 "Miguel Amaya", "Leo Jimenez", "Jose Ramos"],
        "COL": ["Harold Ramirez", "Gio Urshela", "Donovan Solano",
                 "Jorge Alfaro", "Elias Diaz", "Jordan Diaz",
                 "Reynaldo Rodriguez", "Michael Arroyo", "Dayan Frias"],
        "ITA": ["Vinnie Pasquantino", "Dominic Canzone", "Jon Berti",
                 "Miles Mastrobuoni", "Brett Sullivan", "Zach Dezenzo",
                 "Sam Antonacci", "Jakob Marsee", "Nick Cimillo"],
        "GBR": ["Jazz Chisholm Jr.", "Trayce Thompson", "Harry Ford",
                 "Lucius Fox", "Nate Eaton", "B.J. Murray",
                 "Matt Koperniak", "Kristian Robinson", "Ivan Johnson"],
        "BRA": ["Dante Bichette Jr.", "Leonardo Reginatto", "Gabriel Maciel",
                 "Lucas Rojo", "Thyago Vieira (DH)", "Gabriel Carmo",
                 "Vitor Ito", "Felipe Koragi", "Osvaldo Carvalho"],
        "AUS": ["Aaron Whitefield", "Robbie Glendinning", "Darryl George",
                 "Rixon Wingrove", "Logan Wade", "Liam Spence",
                 "Alex Hall", "Robbie Perkins", "Jake Bowey"],
        "CZE": ["Martin Cervenka", "Marek Chlup", "Martin Zelenka",
                 "Vojtech Mensik", "Martin Muzik", "Eric Sogard",
                 "Marek Krejcirik", "William Escala", "Matous Bubenik"],
        "VEN": ["Ronald Acuña Jr.", "Jose Altuve", "Luis Arraez",
                 "Salvador Perez", "William Contreras", "Andres Gimenez",
                 "Jackson Chourio", "Ezequiel Tovar", "Gleyber Torres"],
        "NED": ["Xander Bogaerts", "Ozzie Albies", "Jurickson Profar",
                 "Kenley Jansen (DH)", "Ceddanne Rafaela", "Didi Gregorius",
                 "Juremi Profar", "Chadwick Tromp", "Druw Jones"],
        "ISR": ["Harrison Bader", "Garrett Stubbs", "Spencer Horwitz",
                 "Matt Mervis", "Troy Johnston", "Zack Gelof",
                 "Cole Carrigg", "Noah Mendlinger", "RJ Schreck"],
        "NIC": ["Ismael Munguia", "Mark Vientos", "Cheslor Cuthbert",
                 "Jeter Downs", "Juan Montes", "Melvin Novoa",
                 "Benjamin Alegria", "Brandon Leyton", "Freddy Zamora"],
    }
    names = stubs.get(team, [f"Batter {i+1}" for i in range(9)])
    lineup = []
    for i, n in enumerate(names[:9]):
        noise = (i - 4) * 0.008
        slot_woba = woba + noise * 0.9
        slot_obp = obp + noise * 0.8
        slot_slg = slg + noise * 1.2
        lineup.append(BatterStats(
            name=n, team=team,
            avg=avg + noise,
            obp=slot_obp,
            slg=slot_slg,
            ops=slot_obp + slot_slg,
            woba=slot_woba,
            ops_plus=wrc_plus + (4 - i) * 3,
            avg_last_30=avg + noise + 0.012,
            avg_last_3=avg + noise - 0.005,
            spring_avg=avg + noise + spring_adj,
            vs_left_avg=avg + 0.015,
            vs_right_avg=avg - 0.010,
            high_leverage_ops=(slot_obp + slot_slg) + 0.020,
            swstr_vs_98=22.0 + i * 1.5,   # % swing-and-miss vs 98mph+
            clutch_woba=slot_woba + 0.010,
            sb_success_rate=0.72 + i * 0.01,
        ))
    return lineup


# ─── Public Fetch Function ───────────────────────────────────────────────────

def fetch_latest_wbc_match(live: bool = False, use_mock: bool = False) -> MatchData:
    """
    Return match data for the latest WBC 2026 fixture.
    If live=True, attempts to fetch current TSL odds.

    *** 2026 WBC Pool C Game 1: Japan vs. Chinese Taipei ***
    Venue: Tokyo Dome, Tokyo  |  2026-03-06 19:00 JST
    Round: Pool  →  pitch-count limit = 65 balls, SP ~3.5 IP expected
    """

    # ─────────────────────────────────────────────────────
    # ── Japan (JPN) ──────────────────────────────────────
    # ─────────────────────────────────────────────────────
    jpn_roster = RosterVolatility(
        roster_strength_index=95,
        confirmed_stars=["Shohei Ohtani", "Yoshinobu Yamamoto",
                         "Munetaka Murakami", "Masataka Yoshida", "Seiya Suzuki"],
        uncertain_stars=[],
        absent_stars=["Roki Sasaki"], # Specifically noted as absent per latest wiki roster
        team_chemistry=0.88,
        mlb_player_count=12,
    )
    jpn = TeamStats(
        name="Japan", code="JPN", elo=1620,
        runs_per_game=5.8, runs_allowed_per_game=2.9,
        batting_avg=0.282, team_obp=0.355, team_slg=0.445,
        team_woba=0.358, bullpen_era=2.45,   # Improved based on 2025 NPB top-tier performance
        bullpen_pitches_3d=0,       # Pool Game 1 — fresh bullpen
        defense_efficiency=0.725, sb_success_rate=0.78,
        lineup_wrc_plus=132, clutch_woba=0.365,
        roster_vol=jpn_roster,
    )

    # SP: Yoshinobu Yamamoto (山本由伸) — 2025 Real MLB Dodgers Stats
    jpn_sp = PitcherStats(
        name="Yoshinobu Yamamoto", team="JPN",
        era=3.10, fip=3.25, whip=1.12, k_per_9=10.4, bb_per_9=2.1, # Updated to 2025 real MLB performance
        stuff_plus=125, ip_last_30=25.0, era_last_3=2.90,
        spring_era=2.40, pitch_count_last_3d=0,
        vs_left_ba=0.220, vs_right_ba=0.205,
        high_leverage_era=2.80, fastball_velo=96.5, role="SP",
    )

    # Piggyback (第二先發): Hiroto Takahashi (高橋宏斗)
    jpn_pb = PitcherStats(
        name="Hiroto Takahashi", team="JPN",
        era=1.58, fip=2.40, whip=0.95, k_per_9=9.2, bb_per_9=1.8, # Updated to 2025 real NPB performance
        stuff_plus=122, ip_last_30=18.0, era_last_3=1.20,
        spring_era=1.50, pitch_count_last_3d=0,
        vs_left_ba=0.190, vs_right_ba=0.185,
        high_leverage_era=1.40, fastball_velo=97.5, role="PB",
    )

    # ─────────────────────────────────────────────────────
    # ── Chinese Taipei (TPE) ─────────────────────────────
    # ─────────────────────────────────────────────────────
    tpe_roster = RosterVolatility(
        roster_strength_index=78,
        confirmed_stars=["Ku Lin Jui-Yang", "Lin Yu-Min", "Cheng Tsung-Che", "Yu Chang", "Hsu Jo-Hsi"],
        uncertain_stars=["Lin An-Ko"],
        absent_stars=[],
        team_chemistry=0.85,
        mlb_player_count=4,
    )
    tpe = TeamStats(
        name="Chinese Taipei", code="TPE", elo=1430,
        runs_per_game=4.2, runs_allowed_per_game=3.8,
        batting_avg=0.274, team_obp=0.335, team_slg=0.405, # Boosted by 2025 CPBL high-AVG stars
        team_woba=0.322, bullpen_era=3.45,
        bullpen_pitches_3d=0,       # Pool Game 1 — fresh bullpen
        defense_efficiency=0.708, sb_success_rate=0.72,
        lineup_wrc_plus=102, clutch_woba=0.310,
        roster_vol=tpe_roster,
    )

    # ─────────────────────────────────────────────────────
    # ── Australia (AUS) ──────────────────────────────────
    # ─────────────────────────────────────────────────────
    aus_roster = RosterVolatility(
        roster_strength_index=70,
        confirmed_stars=["Jack O'Loughlin", "Curtis Mead", "Aaron Whitefield", "Robbie Glendinning"],
        uncertain_stars=["Liam Spence"],
        absent_stars=[],
        team_chemistry=0.82,
        mlb_player_count=2,
    )
    aus = TeamStats(
        name="Australia", code="AUS", elo=1380,
        runs_per_game=4.2, runs_allowed_per_game=5.1,
        batting_avg=0.245, team_obp=0.315, team_slg=0.385,
        team_woba=0.305, bullpen_era=4.85, # Based on 2025 minor league performance
        bullpen_pitches_3d=0,
        defense_efficiency=0.695, sb_success_rate=0.72,
        lineup_wrc_plus=88, clutch_woba=0.295,
        roster_vol=aus_roster,
    )

    # SP: Jack O'Loughlin — 2025 Real MiLB (Rockies AAA/ACL) Stats
    aus_sp = PitcherStats(
        name="Jack O'Loughlin", team="AUS",
        era=6.70, fip=5.85, whip=1.65, k_per_9=6.3, bb_per_9=3.2, # 2025 Mixed AAA/ACL Stats
        stuff_plus=98, ip_last_30=15.0, era_last_3=6.10,
        spring_era=4.50, pitch_count_last_3d=0,
        vs_left_ba=0.275, vs_right_ba=0.290,
        high_leverage_era=5.80, fastball_velo=92.5, role="SP",
    )

    # SP: 古林睿煬 (Ku Lin Jui-Yang) — 2025 Real NPB Fighters Stats
    tpe_sp = PitcherStats(
        name="Ku Lin Jui-Yang", team="TPE",
        era=3.62, fip=3.45, whip=1.22, k_per_9=9.5, bb_per_9=2.8, # Updated to 2025 real NPB performance
        stuff_plus=115, ip_last_30=32.1, era_last_3=3.50,
        spring_era=2.80, pitch_count_last_3d=0,
        vs_left_ba=0.245, vs_right_ba=0.230,
        high_leverage_era=3.70, fastball_velo=96.1, role="SP",
    )

    # Piggyback (第二先發): Huang En-Sih — enters ~4th inning
    tpe_pb = PitcherStats(
        name="Huang En-Sih", team="TPE",
        era=3.80, fip=3.95, whip=1.25, k_per_9=8.2, bb_per_9=3.1,
        stuff_plus=98, ip_last_30=15.0, era_last_3=3.60,
        spring_era=3.50, pitch_count_last_3d=0,
        vs_left_ba=0.250, vs_right_ba=0.238,
        high_leverage_era=4.10, fastball_velo=93.0, role="PB",
    )

    # ─────────────────────────────────────────────────────
    # ── Pitch Count Rule (Pool round) ────────────────────
    # ─────────────────────────────────────────────────────
    pc_rule = PitchCountRule(
        round_name="Pool C",
        max_pitches=65,
        rest_after_30=1,
        rest_after_50=4,
        expected_sp_innings=3.5,
    )

    # ─────────────────────────────────────────────────────
    # ── Taiwan Sports Lottery (TSL) + Pinnacle Odds ──────
    # ─────────────────────────────────────────────────────
    ts = "2026-03-06T10:00Z"
    odds: List[OddsLine] = [
        # ── 不讓分（獨贏）Money Line ──
        OddsLine("TSL",      "ML", "JPN", 1.42, timestamp=ts),
        OddsLine("TSL",      "ML", "TPE", 3.10, timestamp=ts),
        OddsLine("Pinnacle", "ML", "JPN", 1.45, timestamp=ts),
        OddsLine("Pinnacle", "ML", "TPE", 2.95, timestamp=ts),
        # ── 讓分 Run Line ──
        OddsLine("TSL",      "RL", "JPN", 1.85, line=-2.5, timestamp=ts),
        OddsLine("TSL",      "RL", "TPE", 1.95, line=+2.5, timestamp=ts),
        OddsLine("Pinnacle", "RL", "JPN", 1.90, line=-2.5, timestamp=ts),
        OddsLine("Pinnacle", "RL", "TPE", 1.95, line=+2.5, timestamp=ts),
        # ── 大小分 Over/Under ──
        OddsLine("TSL",      "OU", "Over",  1.85, line=7.5, timestamp=ts),
        OddsLine("TSL",      "OU", "Under", 1.95, line=7.5, timestamp=ts),
        OddsLine("Pinnacle", "OU", "Over",  1.88, line=7.5, timestamp=ts),
        OddsLine("Pinnacle", "OU", "Under", 1.97, line=7.5, timestamp=ts),
        # ── 單雙 Odd/Even ──
        OddsLine("TSL",      "OE", "Odd",  1.90, timestamp=ts),
        OddsLine("TSL",      "OE", "Even", 1.90, timestamp=ts),
        # ── 前五局獨贏 First 5 Innings ──
        OddsLine("TSL",      "F5", "JPN", 1.55, timestamp=ts),
        OddsLine("TSL",      "F5", "TPE", 2.60, timestamp=ts),
        OddsLine("Pinnacle", "F5", "JPN", 1.58, timestamp=ts),
        OddsLine("Pinnacle", "F5", "TPE", 2.50, timestamp=ts),
        # ── 隊伍總分 Team Totals ──
        OddsLine("TSL", "TT", "JPN_Over",  1.85, line=4.5, timestamp=ts),
        OddsLine("TSL", "TT", "JPN_Under", 1.95, line=4.5, timestamp=ts),
        OddsLine("TSL", "TT", "TPE_Over",  2.05, line=2.5, timestamp=ts),
        OddsLine("TSL", "TT", "TPE_Under", 1.80, line=2.5, timestamp=ts),
    ]

    # ── Live Odds Integration ─────────────────────────────
    if live:
        crawler = TSLCrawler(use_mock=use_mock)
        live_match = crawler.parse_wbc_match("日本", "中華台北")
        if live_match:
            new_odds = []
            # Keep non-TSL odds (like Pinnacle) if they exist
            for o in odds:
                if o.book != "TSL":
                    new_odds.append(o)
            
            # Add updated TSL odds from crawler
            for m_type, outcomes in live_match.markets.items():
                for side, details in outcomes.items():
                    # Map Chinese names back to codes for the engine
                    side_code = side
                    if side == "日本": side_code = "JPN"
                    elif side == "中華台北": side_code = "TPE"
                    elif side == "大": side_code = "Over"
                    elif side == "小": side_code = "Under"
                    elif side == "單": side_code = "Odd"
                    elif side == "雙": side_code = "Even"
                    
                    new_odds.append(OddsLine(
                        book="TSL",
                        market=m_type,
                        side=side_code,
                        price=details["price"],
                        line=details["line"],
                        timestamp=datetime.datetime.now().isoformat()
                    ))
            odds = new_odds

    return MatchData(
        home=jpn,     # Tokyo Dome — JPN as home
        away=tpe,
        home_sp=jpn_sp,
        away_sp=tpe_sp,
        home_piggyback=jpn_pb,
        away_piggyback=tpe_pb,
        home_bullpen=_build_bullpen("JPN", 2.65, 0, avg_stuff=120),
        away_bullpen=_build_bullpen("TPE", 3.65, 0, avg_stuff=98),
        home_lineup=_build_lineup("JPN", 0.282, 0.355, 0.445,
                                  woba=0.358, wrc_plus=132, spring_adj=0.015),
        away_lineup=_build_lineup("TPE", 0.274, 0.335, 0.405,
                                  woba=0.322, wrc_plus=102, spring_adj=0.005),
        odds=odds,
        pitch_count_rule=pc_rule,
        game_time="2026-03-06T19:00:00+09:00",
        venue="Tokyo Dome, Tokyo",
        round_name="Pool C",
        neutral_site=False,
    )
