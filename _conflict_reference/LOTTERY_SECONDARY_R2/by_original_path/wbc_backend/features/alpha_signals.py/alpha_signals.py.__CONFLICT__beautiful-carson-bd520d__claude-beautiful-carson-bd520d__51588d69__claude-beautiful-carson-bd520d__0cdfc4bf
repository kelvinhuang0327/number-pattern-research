"""
Institutional Alpha Signal Registry — 318 Predictive Features
==============================================================
Phase 3+: Exhaustive alpha signal discovery for WBC/MLB prediction.
Phase 4 (MiroFish-inspired): Knowledge Graph + NLP + Market Simulation layers.

Signal catalogue organized into 13 categories:
  A. Advanced Batting          (40 signals)
  B. Advanced Pitching         (38 signals)
  C. Bullpen Dynamics          (22 signals)
  D. Defensive Metrics         (17 signals)
  E. WBC-Specific Rules        (25 signals)
  F. Market/Betting Intel      (21 signals)
  G. Environmental/Schedule    (22 signals)
  H. Interaction/Polynomial    (18 signals)
  I. Time-Series/Momentum      (20 signals)
  J. Lineup Construction       (17 signals)
  K. Knowledge Graph           (20 signals) ← MiroFish GraphRAG 借鑑
  L. NLP Pre-game Semantics    (11 signals) ← MiroFish ReACT 借鑑
  M. Market Agent Simulation   (10 signals) ← MiroFish Multi-Agent 借鑑
  Total (A-J existing): 277
  Total (K-M new):       41
  Grand Total:          318

Design principles:
  - All signals computed defensively (fall back to league average if missing)
  - Each signal includes: name, category, hypothesis, data_available flag
  - Feature dict compatible with existing ML models (key → float)
  - Differential signals (home - away) are the primary ML inputs
  - K/L/M categories: zero external API cost, local computation only
"""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field

import numpy as np

from wbc_backend.domain.schemas import (
    BatterSnapshot, Matchup, PitcherSnapshot, TeamSnapshot,
)
from wbc_backend.features.knowledge_graph import (
    compute_knowledge_graph_signals, get_default_kg,
)
from wbc_backend.features.nlp_extractor import (
    PregameTextBundle, build_empty_nlp_features, compute_nlp_signals,
)
from wbc_backend.betting.market_simulator import compute_market_simulation_signals

logger = logging.getLogger(__name__)

# ── League average baselines (MLB 2025 reference) ──────────────────────────
LEAGUE_AVG = {
    "woba": 0.317,
    "xwoba": 0.317,
    "ops_plus": 100.0,
    "wrc_plus": 100.0,
    "barrel_pct": 0.081,
    "hard_hit_pct": 0.382,
    "launch_angle": 12.5,
    "exit_velo": 88.2,
    "k_pct_bat": 0.228,
    "bb_pct_bat": 0.085,
    "chase_pct": 0.297,
    "contact_pct": 0.773,
    "iso": 0.155,
    "babip": 0.296,
    "sprint_speed": 27.0,
    "stolen_base_pct": 0.793,
    "fip": 4.20,
    "xfip": 4.20,
    "siera": 4.15,
    "era": 4.20,
    "whip": 1.27,
    "k_pct_pitch": 0.221,
    "bb_pct_pitch": 0.085,
    "k_bb_ratio": 2.6,
    "swstr_pct": 0.113,
    "csw_pct": 0.285,
    "gb_pct_pitch": 0.435,
    "hr9": 1.20,
    "lob_pct": 0.720,
    "bullpen_era": 4.10,
    "bullpen_fip": 4.25,
    "bullpen_k_pct": 0.225,
    "der": 0.690,
    "drs": 0.0,
    "uzr": 0.0,
    "catcher_framing": 0.0,
    "cs_pct": 0.268,
}

# ── WBC pitch limit by round ───────────────────────────────────────────────
WBC_PITCH_LIMITS = {1: 65, 2: 80, 3: 95, 4: 95, 5: 95}  # round_num -> limit
WBC_EFFECTIVE_INNINGS = {1: 4.0, 2: 5.0, 3: 6.5, 4: 6.5, 5: 6.5}  # expected SP innings


# ── Signal metadata container ───────────────────────────────────────────────

@dataclass(frozen=True)
class SignalMeta:
    """Metadata for a single alpha signal."""
    name: str
    category: str          # A-J
    hypothesis: str        # Why this should predict outcomes
    predictive_potential: str  # low / medium / high / very_high
    data_available: bool   # Whether current schema provides this
    data_source: str       # Where to get it if unavailable


def _safe_diff(a: float, b: float) -> float:
    """Clipped differential for ML inputs."""
    return float(np.clip(a - b, -10.0, 10.0))


def _safe_ratio(a: float, b: float, eps: float = 0.01) -> float:
    """Safe ratio with epsilon guard."""
    return float(a / (abs(b) + eps))


def _prob_from_american_odds(american_odds: float) -> float:
    """Convert American odds to implied probability."""
    if american_odds == 0:
        return 0.5
    if american_odds > 0:
        return 100.0 / (american_odds + 100.0)
    return abs(american_odds) / (abs(american_odds) + 100.0)


def _prob_from_decimal_odds(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        return 0.5
    return 1.0 / decimal_odds


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY A — Advanced Batting (40 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_batting_signals(  # noqa: C901
    home: TeamSnapshot, away: TeamSnapshot,
    home_lineup: list[BatterSnapshot],
    away_lineup: list[BatterSnapshot],
) -> dict[str, float]:
    """Compute 40 advanced batting alpha signals."""
    feats: dict[str, float] = {}

    def _lineup_avg(lineup: list[BatterSnapshot], attr: str, default: float) -> float:
        vals = [getattr(b, attr, default) for b in lineup if hasattr(b, attr)]
        return float(np.mean(vals)) if vals else default

    def _lineup_weighted(lineup: list[BatterSnapshot]) -> dict[str, float]:
        """Lineup-weighted batting metrics from available BatterSnapshot fields."""
        if not lineup:
            return {}
        woba = np.mean([b.woba for b in lineup])
        ops_plus = np.mean([b.ops_plus for b in lineup])
        clutch_woba = np.mean([b.clutch_woba for b in lineup])
        barrel_pct = np.mean([getattr(b, 'barrel_pct', 0.08) for b in lineup])
        k_pct = np.mean([getattr(b, 'k_pct', LEAGUE_AVG['k_pct_bat']) for b in lineup])
        bb_pct = np.mean([getattr(b, 'bb_pct', LEAGUE_AVG['bb_pct_bat']) for b in lineup])
        xwoba = np.mean([getattr(b, 'xwoba', b.woba) for b in lineup])
        iso = np.mean([getattr(b, 'iso', b.slg - b.avg) for b in lineup])
        babip = np.mean([getattr(b, 'babip', LEAGUE_AVG['babip']) for b in lineup])
        sprint = np.mean([getattr(b, 'sprint_speed', LEAGUE_AVG['sprint_speed']) for b in lineup])
        wrc_plus = np.mean([getattr(b, 'wrc_plus', b.ops_plus) for b in lineup])
        hard_hit = np.mean([getattr(b, 'hard_hit_pct', LEAGUE_AVG['hard_hit_pct']) for b in lineup])
        exit_velo = np.mean([getattr(b, 'exit_velo_avg', LEAGUE_AVG['exit_velo']) for b in lineup])
        launch_angle = np.mean([getattr(b, 'launch_angle_avg', LEAGUE_AVG['launch_angle']) for b in lineup])
        chase = np.mean([getattr(b, 'chase_pct', LEAGUE_AVG['chase_pct']) for b in lineup])
        contact = np.mean([getattr(b, 'contact_pct', LEAGUE_AVG['contact_pct']) for b in lineup])
        return dict(woba=woba, ops_plus=ops_plus, clutch_woba=clutch_woba,
                    barrel_pct=barrel_pct, k_pct=k_pct, bb_pct=bb_pct,
                    xwoba=xwoba, iso=iso, babip=babip, sprint=sprint,
                    wrc_plus=wrc_plus, hard_hit=hard_hit, exit_velo=exit_velo,
                    launch_angle=launch_angle, chase=chase, contact=contact)

    hm = _lineup_weighted(home_lineup)
    aw = _lineup_weighted(away_lineup)

    # Fallback to TeamSnapshot aggregate fields if no lineup provided
    def _h(key: str, team_key: str = "", default: float = 0.0) -> float:
        if hm:
            return hm.get(key, default)
        return getattr(home, team_key or key, default)

    def _a(key: str, team_key: str = "", default: float = 0.0) -> float:
        if aw:
            return aw.get(key, default)
        return getattr(away, team_key or key, default)

    # A.01 Expected wOBA differential (xwOBA - wOBA gap reveals luck/regression)
    h_xwoba = _h('xwoba', 'batting_xwoba', home.batting_woba)
    a_xwoba = _a('xwoba', 'batting_xwoba', away.batting_woba)
    feats['xwoba_diff'] = _safe_diff(h_xwoba, a_xwoba)
    feats['xwoba_luck_home'] = float(h_xwoba - home.batting_woba)  # positive = due for regression up
    feats['xwoba_luck_away'] = float(a_xwoba - away.batting_woba)
    feats['xwoba_luck_diff'] = feats['xwoba_luck_home'] - feats['xwoba_luck_away']

    # A.05 Hard-contact metrics
    feats['hard_hit_pct_diff'] = _safe_diff(
        _h('hard_hit', 'batting_hard_hit_pct', LEAGUE_AVG['hard_hit_pct']),
        _a('hard_hit', 'batting_hard_hit_pct', LEAGUE_AVG['hard_hit_pct'])
    )
    feats['exit_velo_diff'] = _safe_diff(
        _h('exit_velo', '', LEAGUE_AVG['exit_velo']),
        _a('exit_velo', '', LEAGUE_AVG['exit_velo'])
    )
    feats['launch_angle_diff'] = _safe_diff(
        _h('launch_angle', '', LEAGUE_AVG['launch_angle']),
        _a('launch_angle', '', LEAGUE_AVG['launch_angle'])
    )
    feats['barrel_pct_diff'] = _safe_diff(
        _h('barrel_pct', 'batting_barrel_pct', LEAGUE_AVG['barrel_pct']),
        _a('barrel_pct', 'batting_barrel_pct', LEAGUE_AVG['barrel_pct'])
    )

    # A.09 Plate discipline (K%, BB%, Chase%)
    feats['k_pct_bat_diff'] = _safe_diff(
        _h('k_pct', 'batting_k_pct', LEAGUE_AVG['k_pct_bat']),
        _a('k_pct', 'batting_k_pct', LEAGUE_AVG['k_pct_bat'])
    )
    feats['bb_pct_bat_diff'] = _safe_diff(
        _h('bb_pct', 'batting_bb_pct', LEAGUE_AVG['bb_pct_bat']),
        _a('bb_pct', 'batting_bb_pct', LEAGUE_AVG['bb_pct_bat'])
    )
    feats['chase_pct_diff'] = _safe_diff(
        _h('chase', 'batting_chase_pct', LEAGUE_AVG['chase_pct']),
        _a('chase', 'batting_chase_pct', LEAGUE_AVG['chase_pct'])
    )
    feats['contact_pct_diff'] = _safe_diff(
        _h('contact', '', LEAGUE_AVG['contact_pct']),
        _a('contact', '', LEAGUE_AVG['contact_pct'])
    )
    feats['k_bb_bat_ratio_diff'] = _safe_diff(
        _h('bb_pct', 'batting_bb_pct', 0.09) / (_h('k_pct', 'batting_k_pct', 0.22) + 0.01),
        _a('bb_pct', 'batting_bb_pct', 0.09) / (_a('k_pct', 'batting_k_pct', 0.22) + 0.01)
    )

    # A.14 Quality of contact
    feats['iso_diff'] = _safe_diff(
        _h('iso', 'batting_iso', LEAGUE_AVG['iso']),
        _a('iso', 'batting_iso', LEAGUE_AVG['iso'])
    )
    feats['babip_bat_diff'] = _safe_diff(
        _h('babip', 'batting_babip', LEAGUE_AVG['babip']),
        _a('babip', 'batting_babip', LEAGUE_AVG['babip'])
    )

    # A.16 Baserunning
    feats['sprint_speed_diff'] = _safe_diff(
        _h('sprint', 'batting_sprint_speed', LEAGUE_AVG['sprint_speed']),
        _a('sprint', 'batting_sprint_speed', LEAGUE_AVG['sprint_speed'])
    )
    feats['stolen_base_pct_diff'] = _safe_diff(
        home.batting_stolen_base_pct, away.batting_stolen_base_pct
    )

    # A.18 Composite offensive efficiency
    feats['wrc_plus_diff'] = _safe_diff(
        _h('wrc_plus', 'batting_wrc_plus', LEAGUE_AVG['wrc_plus']),
        _a('wrc_plus', 'batting_wrc_plus', LEAGUE_AVG['wrc_plus'])
    )

    # A.19 Clutch & high-leverage batting
    feats['clutch_woba_diff'] = _safe_diff(home.clutch_woba, away.clutch_woba)
    feats['two_out_risp_diff'] = _safe_diff(
        home.batting_two_out_risp_avg, away.batting_two_out_risp_avg
    )

    # A.21 Lineup depth quality (top3 vs bottom6 split)
    if home_lineup and len(home_lineup) >= 3:
        top3_h = np.mean([b.woba for b in sorted(home_lineup, key=lambda x: x.woba, reverse=True)[:3]])
        bot6_h = np.mean([b.woba for b in sorted(home_lineup, key=lambda x: x.woba)[:6]])
        feats['top3_woba_home'] = float(top3_h)
        feats['bottom6_woba_home'] = float(bot6_h)
        feats['lineup_depth_home'] = float(top3_h - bot6_h)  # higher = more top-heavy
    else:
        feats['top3_woba_home'] = home.batting_woba
        feats['bottom6_woba_home'] = home.batting_woba * 0.85
        feats['lineup_depth_home'] = home.batting_woba * 0.15

    if away_lineup and len(away_lineup) >= 3:
        top3_a = np.mean([b.woba for b in sorted(away_lineup, key=lambda x: x.woba, reverse=True)[:3]])
        bot6_a = np.mean([b.woba for b in sorted(away_lineup, key=lambda x: x.woba)[:6]])
        feats['top3_woba_away'] = float(top3_a)
        feats['bottom6_woba_away'] = float(bot6_a)
        feats['lineup_depth_away'] = float(top3_a - bot6_a)
    else:
        feats['top3_woba_away'] = away.batting_woba
        feats['bottom6_woba_away'] = away.batting_woba * 0.85
        feats['lineup_depth_away'] = away.batting_woba * 0.15

    feats['top3_woba_diff'] = feats['top3_woba_home'] - feats['top3_woba_away']
    feats['bottom6_woba_diff'] = feats['bottom6_woba_home'] - feats['bottom6_woba_away']
    feats['lineup_depth_diff'] = feats['lineup_depth_home'] - feats['lineup_depth_away']

    # A.25 Platoon balance (LHB% in lineup)
    if home_lineup:
        lhb_h = sum(1 for b in home_lineup if b.vs_left_avg >= b.vs_right_avg) / len(home_lineup)
    else:
        lhb_h = 0.45
    if away_lineup:
        lhb_a = sum(1 for b in away_lineup if b.vs_left_avg >= b.vs_right_avg) / len(away_lineup)
    else:
        lhb_a = 0.45
    feats['lhb_pct_home'] = float(lhb_h)
    feats['lhb_pct_away'] = float(lhb_a)
    feats['lhb_pct_diff'] = float(lhb_h - lhb_a)

    # A.27 Batted-ball profile (ground ball hitters do worse in short series)
    feats['gb_heavy_penalty_home'] = max(0.0, home.batting_gb_pct - 0.50) * 0.5  # penalty if very GB-heavy
    feats['gb_heavy_penalty_away'] = max(0.0, away.batting_gb_pct - 0.50) * 0.5
    feats['fb_heavy_bonus_home'] = max(0.0, home.batting_fb_pct - 0.38) * 0.3  # fly ball upside
    feats['fb_heavy_bonus_away'] = max(0.0, away.batting_fb_pct - 0.38) * 0.3

    # A.31 Momentum signals (if available)
    feats['woba_trend_7g_diff'] = _safe_diff(home.woba_trend_7g, away.woba_trend_7g)
    feats['runs_scored_trend_3g_diff'] = _safe_diff(home.runs_scored_trend_3g, away.runs_scored_trend_3g)

    # A.33 International batting experience
    h_intl_bat = home.intl_batting_woba if home.intl_batting_woba > 0 else home.batting_woba * 0.95
    a_intl_bat = away.intl_batting_woba if away.intl_batting_woba > 0 else away.batting_woba * 0.95
    feats['intl_batting_woba_diff'] = _safe_diff(h_intl_bat, a_intl_bat)

    # A.35 High-leverage clutch wOBA differential
    feats['high_leverage_woba_diff'] = _safe_diff(home.clutch_woba, away.clutch_woba)

    # A.36 vs-handedness advantage (home batters vs away SP handedness)
    if home_lineup and away_sp:
        sp_hand = getattr(away_sp, 'hand', 'R')  # default R if unknown
        avg_vs = np.mean([b.vs_right_avg if sp_hand == 'R' else b.vs_left_avg for b in home_lineup])
        feats['home_bat_vs_away_sp_hand'] = float(avg_vs - LEAGUE_AVG['woba'])
    else:
        feats['home_bat_vs_away_sp_hand'] = 0.0
    if away_lineup and home_sp:
        sp_hand = getattr(home_sp, 'hand', 'R')
        avg_vs = np.mean([b.vs_right_avg if sp_hand == 'R' else b.vs_left_avg for b in away_lineup])
        feats['away_bat_vs_home_sp_hand'] = float(avg_vs - LEAGUE_AVG['woba'])
    else:
        feats['away_bat_vs_home_sp_hand'] = 0.0
    feats['handedness_matchup_diff'] = feats['home_bat_vs_away_sp_hand'] - feats['away_bat_vs_home_sp_hand']

    # A.39 Star hitter concentration (RSI proxy)
    feats['star_batter_concentration_diff'] = _safe_diff(
        home.top50_stars * 0.05, away.top50_stars * 0.05
    )

    return feats

    # needed local var ref
away_sp = None
home_sp = None


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY B — Advanced Pitching (38 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_pitching_signals(  # noqa: C901
    home: TeamSnapshot, away: TeamSnapshot,
    home_sp: PitcherSnapshot | None,
    away_sp: PitcherSnapshot | None,
) -> dict[str, float]:
    """Compute 38 advanced pitching alpha signals."""
    feats: dict[str, float] = {}

    def _sp(sp: PitcherSnapshot | None, attr: str, team_attr: str, team: TeamSnapshot, default: float) -> float:
        if sp is not None:
            return getattr(sp, attr, default)
        return getattr(team, team_attr, default)

    # B.01 ERA estimators (xFIP / SIERA reduce noise vs raw ERA)
    h_xfip = _sp(home_sp, 'fip', 'pitching_xfip', home,
                  home.pitching_xfip if home.pitching_xfip else home.pitching_fip)
    a_xfip = _sp(away_sp, 'fip', 'pitching_xfip', away,
                  away.pitching_xfip if away.pitching_xfip else away.pitching_fip)
    h_siera = _sp(home_sp, 'fip', 'pitching_siera', home,
                   home.pitching_siera if home.pitching_siera else home.pitching_fip)
    a_siera = _sp(away_sp, 'fip', 'pitching_siera', away,
                   away.pitching_siera if away.pitching_siera else away.pitching_fip)

    feats['xfip_diff'] = _safe_diff(h_xfip, a_xfip)
    feats['siera_diff'] = _safe_diff(h_siera, a_siera)
    feats['era_xfip_gap_home'] = float(home.pitching_fip - h_xfip)  # regression signal
    feats['era_xfip_gap_away'] = float(away.pitching_fip - a_xfip)
    feats['era_estimator_divergence_diff'] = feats['era_xfip_gap_home'] - feats['era_xfip_gap_away']

    # B.06 Strikeout & walk profile
    h_kpct = _sp(home_sp, 'k_per_9', 'pitching_k_pct', home, home.pitching_k_pct) / 27.0
    a_kpct = _sp(away_sp, 'k_per_9', 'pitching_k_pct', away, away.pitching_k_pct) / 27.0
    h_bbpct = _sp(home_sp, 'bb_per_9', 'pitching_bb_pct', home, home.pitching_bb_pct) / 27.0
    a_bbpct = _sp(away_sp, 'bb_per_9', 'pitching_bb_pct', away, away.pitching_bb_pct) / 27.0

    feats['k_pct_pitch_diff'] = _safe_diff(h_kpct, a_kpct)
    feats['bb_pct_pitch_diff'] = _safe_diff(h_bbpct, a_bbpct)
    feats['k_bb_ratio_pitch_diff'] = _safe_diff(
        h_kpct / (h_bbpct + 0.01), a_kpct / (a_bbpct + 0.01)
    )

    # B.09 Swinging strike & called strike metrics
    h_swstr = _sp(home_sp, 'stuff_plus', 'pitching_swstr_pct', home, home.pitching_swstr_pct) / 200.0
    a_swstr = _sp(away_sp, 'stuff_plus', 'pitching_swstr_pct', away, away.pitching_swstr_pct) / 200.0
    # Use Stuff+ as proxy for swstr when direct data unavailable
    if home_sp:
        h_swstr = home.pitching_swstr_pct + (home_sp.stuff_plus - 100) * 0.0003
        a_swstr = away.pitching_swstr_pct + (away_sp.stuff_plus - 100) * 0.0003 if away_sp else away.pitching_swstr_pct

    feats['swstr_pct_diff'] = _safe_diff(h_swstr, a_swstr)

    # B.10 GB/FB profile
    h_gb = _sp(home_sp, 'stuff_plus', 'pitching_gb_pct', home, home.pitching_gb_pct)
    a_gb = _sp(away_sp, 'stuff_plus', 'pitching_gb_pct', away, away.pitching_gb_pct)
    # Approximate GB% from WHIP (high WHIP pitchers tend to induce more contact)
    if not home.pitching_gb_pct:
        h_gb = 0.435 + (home.pitching_whip - LEAGUE_AVG['whip']) * 0.1
    if not away.pitching_gb_pct:
        a_gb = 0.435 + (away.pitching_whip - LEAGUE_AVG['whip']) * 0.1

    feats['gb_pct_pitch_diff'] = _safe_diff(float(h_gb), float(a_gb))

    # B.12 HR suppression
    h_hr9 = home.pitching_hr9 if home.pitching_hr9 else LEAGUE_AVG['hr9']
    a_hr9 = away.pitching_hr9 if away.pitching_hr9 else LEAGUE_AVG['hr9']
    feats['hr9_diff'] = _safe_diff(h_hr9, a_hr9)

    # B.13 LOB% & BABIP
    h_lob = home.pitching_lob_pct if home.pitching_lob_pct else LEAGUE_AVG['lob_pct']
    a_lob = away.pitching_lob_pct if away.pitching_lob_pct else LEAGUE_AVG['lob_pct']
    feats['lob_pct_diff'] = _safe_diff(h_lob, a_lob)
    h_babip_p = home.pitching_babip if home.pitching_babip else LEAGUE_AVG['babip']
    a_babip_p = away.pitching_babip if away.pitching_babip else LEAGUE_AVG['babip']
    feats['babip_pitch_diff'] = _safe_diff(h_babip_p, a_babip_p)

    # B.15 Fastball velocity (proxy: fastball_velo from SP)
    if home_sp and away_sp:
        feats['fb_velo_diff'] = _safe_diff(home_sp.fastball_velo, away_sp.fastball_velo)
        feats['max_fb_velo_diff'] = feats['fb_velo_diff']  # approximate
    else:
        feats['fb_velo_diff'] = 0.0
        feats['max_fb_velo_diff'] = 0.0

    # B.17 Pitch arsenal entropy (already in advanced.py, replicate for completeness)
    if home_sp and home_sp.pitch_mix:
        mix = list(home_sp.pitch_mix.values())
        total = sum(mix) + 1e-9
        p = [v / total for v in mix]
        h_entropy = -sum(pi * math.log(pi + 1e-9) for pi in p)
    else:
        h_entropy = math.log(3)  # 3 pitches = avg entropy

    if away_sp and away_sp.pitch_mix:
        mix = list(away_sp.pitch_mix.values())
        total = sum(mix) + 1e-9
        p = [v / total for v in mix]
        a_entropy = -sum(pi * math.log(pi + 1e-9) for pi in p)
    else:
        a_entropy = math.log(3)

    feats['pitch_arsenal_entropy_diff_v2'] = _safe_diff(h_entropy, a_entropy)

    # B.19 Velocity trend (recent vs career)
    if home_sp and home_sp.recent_fastball_velos and home_sp.career_fastball_velo:
        h_vtrend = float(np.mean(home_sp.recent_fastball_velos[-3:]) - home_sp.career_fastball_velo)
    else:
        h_vtrend = 0.0
    if away_sp and away_sp.recent_fastball_velos and away_sp.career_fastball_velo:
        a_vtrend = float(np.mean(away_sp.recent_fastball_velos[-3:]) - away_sp.career_fastball_velo)
    else:
        a_vtrend = 0.0
    feats['velocity_trend_diff_v2'] = _safe_diff(h_vtrend, a_vtrend)

    # B.21 Woba allowed L/R split
    h_woba_l = home_sp.woba_vs_left if home_sp else LEAGUE_AVG['woba']
    h_woba_r = home_sp.woba_vs_right if home_sp else LEAGUE_AVG['woba']
    a_woba_l = away_sp.woba_vs_left if away_sp else LEAGUE_AVG['woba']
    a_woba_r = away_sp.woba_vs_right if away_sp else LEAGUE_AVG['woba']
    feats['sp_woba_allowed_l_diff'] = _safe_diff(h_woba_l, a_woba_l)
    feats['sp_woba_allowed_r_diff'] = _safe_diff(h_woba_r, a_woba_r)
    feats['sp_platoon_gap_home'] = float(abs(h_woba_l - h_woba_r))  # exploitability
    feats['sp_platoon_gap_away'] = float(abs(a_woba_l - a_woba_r))
    feats['sp_platoon_gap_diff'] = feats['sp_platoon_gap_home'] - feats['sp_platoon_gap_away']

    # B.26 High-leverage ERA
    h_hl_era = home_sp.high_leverage_era if home_sp else home.pitching_fip
    a_hl_era = away_sp.high_leverage_era if away_sp else away.pitching_fip
    feats['high_leverage_era_sp_diff'] = _safe_diff(h_hl_era, a_hl_era)

    # B.28 ERA trend
    if home_sp:
        h_era_trend = home_sp.era_last_3 - home_sp.era
    else:
        h_era_trend = home.era_trend_7g
    if away_sp:
        a_era_trend = away_sp.era_last_3 - away_sp.era
    else:
        a_era_trend = away.era_trend_7g
    feats['era_trend_sp_diff'] = _safe_diff(h_era_trend, a_era_trend)

    # B.30 Spin rate zscore (already computed in advanced.py, v2 for validation)
    if home_sp and home_sp.career_spin_rate_std > 0:
        h_spin_z = (home_sp.recent_spin_rate - home_sp.career_spin_rate_mean) / home_sp.career_spin_rate_std
    else:
        h_spin_z = 0.0
    if away_sp and away_sp.career_spin_rate_std > 0:
        a_spin_z = (away_sp.recent_spin_rate - away_sp.career_spin_rate_mean) / away_sp.career_spin_rate_std
    else:
        a_spin_z = 0.0
    feats['spin_rate_zscore_diff_v2'] = _safe_diff(h_spin_z, a_spin_z)

    # B.32 Inning load (fatigue proxy)
    if home_sp:
        h_load = home_sp.innings_last_14d / (home_sp.season_avg_innings_per_14d + 0.1)
    else:
        h_load = 1.0
    if away_sp:
        a_load = away_sp.innings_last_14d / (away_sp.season_avg_innings_per_14d + 0.1)
    else:
        a_load = 1.0
    feats['inning_load_ratio_diff'] = _safe_diff(h_load, a_load)

    # B.34 International ERA
    h_intl_era = home.intl_era if home.intl_era > 0 else home.pitching_fip
    a_intl_era = away.intl_era if away.intl_era > 0 else away.pitching_fip
    feats['intl_era_diff'] = _safe_diff(h_intl_era, a_intl_era)

    # B.36 Pitching stuff score
    feats['stuff_plus_diff_v2'] = _safe_diff(home.pitching_stuff_plus, away.pitching_stuff_plus)

    # B.37 Recent IP vs season avg (workload relative to baseline)
    if home_sp:
        h_ip_ratio = home_sp.ip_last_30 / (home_sp.season_avg_innings_per_14d * 2 + 0.1)
    else:
        h_ip_ratio = 1.0
    if away_sp:
        a_ip_ratio = away_sp.ip_last_30 / (away_sp.season_avg_innings_per_14d * 2 + 0.1)
    else:
        a_ip_ratio = 1.0
    feats['sp_workload_ratio_diff'] = _safe_diff(h_ip_ratio, a_ip_ratio)

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY C — Bullpen Dynamics (22 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_bullpen_signals(home: TeamSnapshot, away: TeamSnapshot,
                              home_bullpen: list[PitcherSnapshot],
                              away_bullpen: list[PitcherSnapshot],
                              round_num: int = 1) -> dict[str, float]:
    """Compute 22 bullpen dynamics signals."""
    feats: dict[str, float] = {}

    def _bp_agg(bp: list[PitcherSnapshot], team: TeamSnapshot) -> dict[str, float]:
        """Aggregate bullpen stats from list or team snapshot."""
        if not bp:
            return {
                'era': team.bullpen_era, 'fip': team.bullpen_fip,
                'k_pct': team.bullpen_k_pct, 'bb_pct': team.bullpen_bb_pct,
                'arms': team.bullpen_arms_available, 'pitches_3d': team.bullpen_pitches_3d,
                'closer': float(team.closer_available),
                'workload': team.bullpen_workload_7d,
                'hl_era': team.bullpen_high_leverage_era,
                'hr9': team.bullpen_hr9,
            }
        era = float(np.mean([p.era for p in bp]))
        fip = float(np.mean([p.fip for p in bp]))
        k_pct = float(np.mean([p.k_per_9 / 27.0 for p in bp]))
        bb_pct = float(np.mean([p.bb_per_9 / 27.0 for p in bp]))
        pitches_3d = sum(p.pitch_count_last_3d for p in bp)
        hl_era = float(np.mean([p.high_leverage_era for p in bp]))
        arms_rested = sum(1 for p in bp if p.pitch_count_last_3d < 20)
        return {
            'era': era, 'fip': fip, 'k_pct': k_pct, 'bb_pct': bb_pct,
            'arms': arms_rested, 'pitches_3d': pitches_3d,
            'closer': 1.0, 'workload': pitches_3d,
            'hl_era': hl_era, 'hr9': LEAGUE_AVG['hr9'],
        }

    hbp = _bp_agg(home_bullpen, home)
    abp = _bp_agg(away_bullpen, away)

    # C.01 ERA estimators
    feats['bullpen_era_diff'] = _safe_diff(hbp['era'], abp['era'])
    feats['bullpen_fip_diff'] = _safe_diff(hbp['fip'], abp['fip'])

    # C.03 Strikeout & walk
    feats['bullpen_k_pct_diff'] = _safe_diff(hbp['k_pct'], abp['k_pct'])
    feats['bullpen_bb_pct_diff'] = _safe_diff(hbp['bb_pct'], abp['bb_pct'])
    feats['bullpen_k_bb_ratio_diff'] = _safe_diff(
        hbp['k_pct'] / (hbp['bb_pct'] + 0.01),
        abp['k_pct'] / (abp['bb_pct'] + 0.01)
    )

    # C.06 High-leverage performance
    feats['bullpen_hl_era_diff'] = _safe_diff(hbp['hl_era'], abp['hl_era'])
    feats['bullpen_hr9_diff'] = _safe_diff(hbp['hr9'], abp['hr9'])

    # C.08 Fatigue / availability
    # WBC: pitch limit determines effective innings left for SP
    effective_sp_ip = WBC_EFFECTIVE_INNINGS.get(round_num, 4.0)

    feats['bullpen_pitches_3d_diff'] = _safe_diff(float(hbp['pitches_3d']), float(abp['pitches_3d']))
    feats['bullpen_workload_7d_diff'] = _safe_diff(float(hbp['workload']), float(abp['workload']))
    feats['bullpen_arms_available_diff'] = _safe_diff(float(hbp['arms']), float(abp['arms']))
    feats['closer_available_diff'] = float(hbp['closer'] - abp['closer'])

    # C.12 WBC-adjusted bullpen demand (higher pitch limits = less bullpen needed)
    wbc_bp_demand_h = max(0.0, (9.0 - effective_sp_ip) / 9.0) * (1.0 + hbp['pitches_3d'] / 500.0)
    wbc_bp_demand_a = max(0.0, (9.0 - effective_sp_ip) / 9.0) * (1.0 + abp['pitches_3d'] / 500.0)
    feats['wbc_bullpen_demand_diff'] = _safe_diff(wbc_bp_demand_h, wbc_bp_demand_a)

    # C.14 Bullpen depth score (arms × quality)
    h_depth = hbp['arms'] * (1.0 - max(0, hbp['era'] - 4.0) / 4.0)
    a_depth = abp['arms'] * (1.0 - max(0, abp['era'] - 4.0) / 4.0)
    feats['bullpen_depth_quality_diff'] = _safe_diff(h_depth, a_depth)

    # C.16 Closer availability (critical for late-game)
    feats['bullpen_closer_available_home'] = float(hbp['closer'])
    feats['bullpen_closer_available_away'] = float(abp['closer'])

    # C.18 Middle relief quality
    feats['bullpen_middle_relief_diff'] = _safe_diff(home.bullpen_era, away.bullpen_era)

    # C.19 Pitches per arm (fatigue distribution)
    if hbp['arms'] > 0:
        h_ppa = hbp['pitches_3d'] / hbp['arms']
    else:
        h_ppa = 50.0
    if abp['arms'] > 0:
        a_ppa = abp['pitches_3d'] / abp['arms']
    else:
        a_ppa = 50.0
    feats['bullpen_pitches_per_arm_diff'] = _safe_diff(h_ppa, a_ppa)

    # C.21 Raw bullpen depth (from TeamSnapshot)
    feats['bullpen_depth_raw_diff'] = _safe_diff(home.bullpen_depth, away.bullpen_depth)

    # C.22 WBC piggyback starter quality (2nd SP quality)
    # Proxy: ERA of best available RP in bullpen
    if home_bullpen:
        h_pig = min(p.era for p in home_bullpen) if home_bullpen else home.bullpen_era
    else:
        h_pig = home.bullpen_era
    if away_bullpen:
        a_pig = min(p.era for p in away_bullpen) if away_bullpen else away.bullpen_era
    else:
        a_pig = away.bullpen_era
    feats['piggyback_quality_diff'] = _safe_diff(h_pig, a_pig)

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY D — Defensive Metrics (17 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_defensive_signals(home: TeamSnapshot, away: TeamSnapshot) -> dict[str, float]:
    """Compute 17 defensive alpha signals."""
    feats: dict[str, float] = {}

    feats['der_diff_v2'] = _safe_diff(home.der, away.der)
    feats['team_drs_diff'] = _safe_diff(home.team_drs, away.team_drs)
    feats['team_uzr_diff'] = _safe_diff(home.team_uzr, away.team_uzr)
    feats['catcher_framing_diff'] = _safe_diff(home.catcher_framing_runs, away.catcher_framing_runs)

    # D.05 Composite defensive score
    h_def = (home.der - LEAGUE_AVG['der']) * 100 + home.team_drs * 0.5 + home.team_uzr * 0.5
    a_def = (away.der - LEAGUE_AVG['der']) * 100 + away.team_drs * 0.5 + away.team_uzr * 0.5
    feats['composite_defense_diff'] = _safe_diff(h_def, a_def)

    # D.06 DER-based run prevention
    feats['der_run_prevention_diff'] = _safe_diff(
        home.der * home.pitching_fip, away.der * away.pitching_fip
    ) / 10.0

    # D.07 Catcher intelligence (framing + pop time proxy)
    feats['catcher_total_value_diff'] = feats['catcher_framing_diff']

    # D.08 Double-play ability (proxy: GB% * fielding)
    feats['double_play_ability_diff'] = _safe_diff(
        home.der * home.pitching_gb_pct,
        away.der * away.pitching_gb_pct
    )

    # D.09 Error rate proxy (DER inversely related to errors)
    feats['error_rate_proxy_diff'] = _safe_diff(
        1.0 - home.der, 1.0 - away.der
    )

    # D.10 Outfield arm quality (proxy from roster strength)
    feats['of_arm_proxy_diff'] = _safe_diff(
        home.roster_strength_index * 0.01, away.roster_strength_index * 0.01
    )

    # D.11 Infield range (proxy from DER + sprint speed)
    feats['if_range_proxy_diff'] = _safe_diff(
        home.der + home.batting_sprint_speed * 0.005,
        away.der + away.batting_sprint_speed * 0.005
    )

    # D.12 Caught stealing (defense metric)
    feats['cs_pct_proxy_diff'] = _safe_diff(
        1.0 - home.batting_stolen_base_pct,  # lower SB% = better opposing catcher
        1.0 - away.batting_stolen_base_pct
    )

    # D.13 Shift effectiveness (proxy from batting_gb_pct * DER)
    feats['shift_effectiveness_proxy_diff'] = _safe_diff(
        home.batting_gb_pct * home.der,
        away.batting_gb_pct * away.der
    )

    # D.14 Total fielding value composite
    feats['total_fielding_value_diff'] = (
        feats['der_diff_v2'] * 2.0 +
        feats['team_drs_diff'] * 0.1 +
        feats['team_uzr_diff'] * 0.1
    )

    # D.15 Defensive efficiency per run allowed
    h_def_eff = home.der / (home.runs_allowed_per_game + 0.1)
    a_def_eff = away.der / (away.runs_allowed_per_game + 0.1)
    feats['defensive_efficiency_ratio_diff'] = _safe_diff(h_def_eff, a_def_eff)

    # D.16 Roster depth for defense (does team have quality bench defenders?)
    feats['defensive_roster_depth_diff'] = _safe_diff(
        home.roster_strength_index * home.der,
        away.roster_strength_index * away.der
    ) / 100.0

    # D.17 Pitching-defense synergy (how well pitching style matches defense)
    feats['pitching_defense_synergy_diff'] = _safe_diff(
        home.pitching_gb_pct * home.der,
        away.pitching_gb_pct * away.der
    )

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY E — WBC-Specific Rules (25 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_wbc_signals(home: TeamSnapshot, away: TeamSnapshot,
                          matchup: Matchup) -> dict[str, float]:
    """Compute 25 WBC-specific alpha signals."""
    feats: dict[str, float] = {}
    round_num = getattr(matchup, 'tournament_round_num', 1)

    # E.01 WBC experience (career games played in WBC)
    feats['wbc_experience_diff'] = _safe_diff(
        float(home.wbc_experience_games), float(away.wbc_experience_games)
    )
    feats['wbc_experience_total'] = float(home.wbc_experience_games + away.wbc_experience_games)

    # E.03 International record
    feats['intl_win_pct_diff'] = _safe_diff(home.intl_win_pct, away.intl_win_pct)
    feats['intl_run_diff_diff'] = _safe_diff(home.intl_run_diff, away.intl_run_diff)

    # E.05 WBC pitch limit context
    pitch_limit = WBC_PITCH_LIMITS.get(round_num, 65)
    effective_ip = WBC_EFFECTIVE_INNINGS.get(round_num, 4.0)
    feats['wbc_pitch_limit'] = float(pitch_limit)
    feats['wbc_effective_sp_ip'] = float(effective_ip)

    # WBC bullpen fraction (innings after SP)
    feats['wbc_bullpen_fraction'] = float((9.0 - effective_ip) / 9.0)

    # E.08 Pitcher availability adjusted for WBC limits
    # If a team's ace is pitch-limited, that's a major disadvantage
    h_ace_limited = float(home.ace_pitch_count_limited)
    a_ace_limited = float(away.ace_pitch_count_limited)
    feats['ace_pitch_limited_home'] = h_ace_limited
    feats['ace_pitch_limited_away'] = a_ace_limited
    feats['ace_limited_diff'] = float(h_ace_limited - a_ace_limited)

    # E.10 Roster cohesion (same-league familiarity)
    # Players from same domestic league have better chemistry
    feats['roster_strength_diff_v2'] = _safe_diff(
        home.roster_strength_index, away.roster_strength_index
    )

    # E.11 Tournament stage pressure multiplier
    # Pressure increases variability (upsets more likely in later rounds)
    pressure_map = {1: 0.10, 2: 0.15, 3: 0.20, 4: 0.25, 5: 0.30}
    pressure = pressure_map.get(round_num, 0.10)
    feats['tournament_pressure'] = pressure

    # E.12 Elimination game flag (do or die increases variance)
    feats['is_elimination_game'] = float(getattr(matchup, 'is_elimination_game', False))

    # E.13 Knockout stage flag (QF/SF/F)
    feats['is_knockout_stage'] = float(getattr(matchup, 'is_knockout_stage', False))

    # E.14 Crowd support (home crowd advantage in WBC)
    crowd_home_pct = getattr(matchup, 'crowd_home_pct', 0.50)
    feats['crowd_home_advantage'] = max(-0.5, min(0.5, crowd_home_pct - 0.50)) * 2.0

    # E.15 Nation expectation pressure (top-tier nations feel more pressure)
    h_elo_norm = (home.elo - 1400) / 300.0
    a_elo_norm = (away.elo - 1400) / 300.0
    feats['nation_pressure_home'] = h_elo_norm * pressure
    feats['nation_pressure_away'] = a_elo_norm * pressure
    feats['nation_pressure_diff'] = feats['nation_pressure_home'] - feats['nation_pressure_away']

    # E.18 Missing core player impact
    feats['missing_core_batter_home'] = float(home.missing_core_batter)
    feats['missing_core_batter_away'] = float(away.missing_core_batter)
    feats['missing_player_diff'] = float(away.missing_core_batter) - float(home.missing_core_batter)

    # E.20 Roster completeness vs opponent
    feats['rsi_diff'] = _safe_diff(home.roster_strength_index, away.roster_strength_index)
    feats['rsi_ratio'] = _safe_ratio(home.roster_strength_index, away.roster_strength_index, eps=10.0)

    # E.22 League familiarity (star players from same professional league)
    feats['top50_stars_diff'] = _safe_diff(float(home.top50_stars), float(away.top50_stars))

    # E.23 WBC-adjusted bullpen quality (fatigue × depth)
    wbc_bp_h = home.bullpen_depth * (1.0 - min(0.5, home.bullpen_pitches_3d / 200.0))
    wbc_bp_a = away.bullpen_depth * (1.0 - min(0.5, away.bullpen_pitches_3d / 200.0))
    feats['wbc_adjusted_bullpen_diff'] = _safe_diff(wbc_bp_h, wbc_bp_a)

    # E.25 Round-stage interaction with Elo
    feats['elo_round_interaction'] = _safe_diff(home.elo, away.elo) * pressure

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY F — Market/Betting Intelligence (21 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_market_signals(home: TeamSnapshot, away: TeamSnapshot,
                             matchup: Matchup) -> dict[str, float]:
    """Compute 21 market intelligence alpha signals."""
    feats: dict[str, float] = {}

    open_odds_h = getattr(matchup, 'opening_ml_home_odds', 0.0)
    close_odds_h = getattr(matchup, 'closing_ml_home_odds', 0.0)
    open_ou = getattr(matchup, 'opening_ou_line', 7.5)
    close_ou = getattr(matchup, 'closing_ou_line', 7.5)
    pub_home = getattr(matchup, 'public_bet_pct_home', 0.50)
    sharp_home = getattr(matchup, 'sharp_handle_pct_home', 0.50)
    steam = float(getattr(matchup, 'steam_move_flag', False))
    rlm = float(getattr(matchup, 'reverse_line_move_flag', False))

    # F.01 Opening implied probability
    if open_odds_h > 1.0:
        open_prob_h = _prob_from_decimal_odds(open_odds_h)
    else:
        open_prob_h = home.opening_ml_prob
    feats['opening_ml_prob_home'] = float(open_prob_h)

    # F.02 Closing implied probability
    if close_odds_h > 1.0:
        close_prob_h = _prob_from_decimal_odds(close_odds_h)
    else:
        close_prob_h = home.closing_ml_prob
    feats['closing_ml_prob_home'] = float(close_prob_h)

    # F.03 Line movement (closing - opening: positive = line moved toward home)
    if open_prob_h > 0 and close_prob_h > 0:
        feats['ml_movement_home'] = float(close_prob_h - open_prob_h)
    else:
        feats['ml_movement_home'] = 0.0

    # F.04 Sharp vs public divergence
    feats['public_bet_pct_home'] = float(pub_home)
    feats['sharp_handle_pct_home'] = float(sharp_home)
    feats['sharp_public_divergence'] = float(sharp_home - pub_home)

    # F.05 Reverse line movement flag
    # Public heavy on home + line moved AWAY from home = sharp action on away
    if pub_home > 0.60 and feats['ml_movement_home'] < -0.02:
        rlm_computed = 1.0
    elif pub_home < 0.40 and feats['ml_movement_home'] > 0.02:
        rlm_computed = -1.0
    else:
        rlm_computed = float(rlm)
    feats['reverse_line_move_flag'] = rlm_computed

    # F.06 Steam move flag (rapid line move = sharp syndicate action)
    feats['steam_move_flag'] = float(steam)

    # F.07 O/U movement
    feats['ou_line_open'] = float(open_ou)
    feats['ou_line_close'] = float(close_ou)
    feats['ou_movement'] = float(close_ou - open_ou)

    # F.08 Market consensus (model vs market divergence — computed externally)
    # Placeholder: will be populated by decision engine
    feats['market_model_divergence'] = 0.0  # updated downstream

    # F.09 Historical book bias (public tends to over-bet popular teams)
    # Proxy: higher elo = more public backing = value on underdog
    elo_diff = home.elo - away.elo
    feats['public_bias_correction'] = float(-0.03 * (elo_diff / 100.0))  # fade popular teams

    # F.10 Sharp money indicator
    feats['sharp_money_home'] = float(min(1.0, max(0.0, sharp_home)))

    # F.11 CLV proxy (closing line value — positive EV signal)
    # If opening line was better than closing, model was right early
    feats['clv_proxy_home'] = feats['ml_movement_home'] * feats['sharp_public_divergence']

    # F.12 Market efficiency ratio (proxy)
    if close_prob_h > 0 and home.closing_ml_prob > 0:
        feats['market_efficiency'] = float(1.0 - abs(close_prob_h - home.closing_ml_prob))
    else:
        feats['market_efficiency'] = 0.95  # assume efficient baseline

    # F.13 Opening line deviation from Elo
    elo_prob = 1.0 / (1.0 + 10 ** (-(home.elo - away.elo) / 400.0))
    feats['opening_line_elo_divergence'] = float(open_prob_h - elo_prob)
    feats['closing_line_elo_divergence'] = float(close_prob_h - elo_prob)

    # F.14 Vig-adjusted closing probability
    if close_odds_h > 1.0:
        close_a = 1.0 - close_prob_h
        total_implied = close_prob_h + close_a
        feats['vig_adjusted_close_prob_home'] = float(close_prob_h / total_implied)
    else:
        feats['vig_adjusted_close_prob_home'] = feats['closing_ml_prob_home']

    # F.15 Public fade score (fade value when public is ≥ 70% on one side)
    if pub_home >= 0.70:
        feats['public_fade_away_signal'] = float(pub_home - 0.60)
    elif pub_home <= 0.30:
        feats['public_fade_away_signal'] = float(pub_home - 0.40)
    else:
        feats['public_fade_away_signal'] = 0.0

    # F.16 O/U sharp signal (sharp money on over/under)
    feats['ou_sharp_signal'] = feats['ou_movement']  # positive = sharp on over

    # F.17 Opening Elo-implied vs market (value identification)
    feats['value_signal_home'] = float(elo_prob - open_prob_h)  # positive = model likes home more than market

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY G — Environmental / Schedule (22 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_environment_signals(home: TeamSnapshot, away: TeamSnapshot,
                                  matchup: Matchup) -> dict[str, float]:
    """Compute 22 environmental and schedule alpha signals."""
    feats: dict[str, float] = {}

    # G.01 Rest differential (already exists, v2 with non-linear penalty)
    rest_h = home.rest_days
    rest_a = away.rest_days
    feats['rest_diff_v2'] = float(rest_h - rest_a)

    # Non-linear: 0 rest days is disproportionately bad
    h_rest_penalty = max(0.0, 1 - rest_h) * 0.5
    a_rest_penalty = max(0.0, 1 - rest_a) * 0.5
    feats['rest_penalty_diff'] = float(h_rest_penalty - a_rest_penalty)

    # G.03 Games in last 5 days (workload)
    g5h = home.games_last_5d
    g5a = away.games_last_5d
    feats['games_last_5d_diff'] = float(g5h - g5a)
    feats['games_last_5d_home'] = float(g5h)
    feats['games_last_5d_away'] = float(g5a)

    # G.06 Consecutive games (fatigue accumulation)
    cg_h = home.consecutive_games
    cg_a = away.consecutive_games
    feats['consecutive_games_diff'] = float(cg_h - cg_a)

    # G.07 Travel fatigue (already in advanced.py, v2 for validation)
    km_h = home.dist_traveled_prev_7d
    km_a = away.dist_traveled_prev_7d
    feats['travel_km_7d_diff'] = _safe_diff(km_h, km_a)

    # G.08 Time zone shift (disrupts sleep cycles)
    tz_h = home.time_zone_offset
    tz_a = away.time_zone_offset
    feats['timezone_offset_diff'] = _safe_diff(tz_h, tz_a)

    # Jet lag score (>3 tz hours = significant fatigue)
    h_jetlag = max(0.0, abs(tz_h) - 3) * 0.1
    a_jetlag = max(0.0, abs(tz_a) - 3) * 0.1
    feats['jetlag_score_diff'] = float(h_jetlag - a_jetlag)

    # G.09 Stadium environment
    feats['elevation_m_v2'] = float(getattr(matchup, 'elevation_m', 0.0))
    feats['park_hr_factor'] = float(getattr(matchup, 'park_hr_factor', 1.0))
    feats['park_run_factor'] = float(getattr(matchup, 'park_run_factor', 1.0))
    feats['park_k_factor'] = float(getattr(matchup, 'park_k_factor', 1.0))
    feats['is_dome_v2'] = float(getattr(matchup, 'is_dome', False))

    # G.13 Weather (temperature / humidity / wind)
    temp_f = getattr(matchup, 'temp_f', 72.0)
    humidity = getattr(matchup, 'humidity_pct', 0.50)
    wind_mph = getattr(matchup, 'wind_speed_mph', 0.0)
    feats['temp_impact'] = float((temp_f - 72.0) / 30.0)  # normalized deviation
    feats['humidity_impact'] = float(humidity - 0.50)
    feats['wind_impact'] = float(wind_mph / 15.0)  # stronger wind = more variance

    # G.16 Game time (day games vs night games — pitcher eye fatigue)
    local_hour = getattr(matchup, 'local_time_hour', 19)
    feats['day_game_flag'] = 1.0 if local_hour < 17 else 0.0

    # G.17 Stadium crowd (home crowd = psychological pressure on away)
    crowd_pct = getattr(matchup, 'stadium_capacity_pct', 0.80)
    crowd_home = getattr(matchup, 'crowd_home_pct', 0.50)
    feats['crowd_intensity'] = float(crowd_pct * crowd_home)
    feats['crowd_support_diff'] = float(crowd_home - 0.50) * crowd_pct

    # G.19 Neutral site effect (already captured in is_neutral)
    feats['neutral_site_v2'] = 1.0 if getattr(matchup, 'neutral_site', True) else 0.0

    # G.20 Back-to-back game flag
    feats['back_to_back_home'] = 1.0 if rest_h == 0 else 0.0
    feats['back_to_back_away'] = 1.0 if rest_a == 0 else 0.0

    # G.22 Combined workload burden
    feats['combined_workload_h'] = float(g5h + cg_h + (1 if rest_h == 0 else 0))
    feats['combined_workload_a'] = float(g5a + cg_a + (1 if rest_a == 0 else 0))
    feats['combined_workload_diff'] = feats['combined_workload_h'] - feats['combined_workload_a']

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY H — Interaction / Polynomial Features (18 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_interaction_signals(existing_feats: dict[str, float],
                                  home: TeamSnapshot, away: TeamSnapshot) -> dict[str, float]:
    """Compute 18 interaction and polynomial alpha signals."""
    feats: dict[str, float] = {}

    elo_diff = home.elo - away.elo
    woba_diff = home.batting_woba - away.batting_woba
    fip_diff = home.pitching_fip - away.pitching_fip

    # H.01 Elo × wOBA cross (strong Elo + strong offense = dominant)
    feats['elo_woba_interaction'] = float(elo_diff * woba_diff * 10.0)

    # H.02 FIP × DER (pitching quality × defensive support)
    feats['fip_der_interaction'] = float(fip_diff * (home.der - away.der))

    # H.03 SP fatigue × bullpen quality (if SP tired, is bullpen good enough?)
    sp_fatigue_diff = existing_feats.get('sp_fatigue_diff', 0.0)
    bp_depth_diff = existing_feats.get('bullpen_depth_raw_diff', 0.0)
    feats['sp_fatigue_bp_quality'] = float(sp_fatigue_diff * -bp_depth_diff)

    # H.04 Travel × Elo (travel hurts weaker teams more)
    travel_diff = existing_feats.get('travel_km_7d_diff', 0.0)
    feats['travel_elo_interaction'] = float(travel_diff * elo_diff / 1000.0)

    # H.05 Elo² (non-linear: big favorites have diminishing returns)
    feats['elo_diff_squared'] = float(np.sign(elo_diff) * (elo_diff ** 2) / 1000.0)

    # H.06 wOBA² (non-linear return on offensive dominance)
    feats['woba_diff_squared'] = float(np.sign(woba_diff) * (woba_diff ** 2) * 100.0)

    # H.07 Market × model divergence squared (strong divergence = strong signal)
    mkt_div = existing_feats.get('value_signal_home', 0.0)
    feats['market_model_div_squared'] = float(np.sign(mkt_div) * (mkt_div ** 2))

    # H.08 xwOBA × barrel% (expected offense × power)
    h_xwoba = home.batting_xwoba if home.batting_xwoba else home.batting_woba
    a_xwoba = away.batting_xwoba if away.batting_xwoba else away.batting_woba
    feats['xwoba_barrel_interaction'] = float(
        (h_xwoba * home.batting_barrel_pct) - (a_xwoba * away.batting_barrel_pct)
    )

    # H.09 Bullpen fatigue × market movement
    bp_stress_diff = existing_feats.get('bullpen_pitches_3d_diff', 0.0)
    ml_move = existing_feats.get('ml_movement_home', 0.0)
    feats['bp_fatigue_market_move'] = float(bp_stress_diff * ml_move / 100.0)

    # H.10 Rest × elo (rested underdog is dangerous)
    rest_diff = existing_feats.get('rest_diff_v2', 0.0)
    feats['rest_elo_interaction'] = float(rest_diff * -elo_diff / 100.0)

    # H.11 FIP × WHIP combined pitching (two complementary stats)
    feats['fip_whip_combined_diff'] = _safe_diff(
        home.pitching_fip * home.pitching_whip,
        away.pitching_fip * away.pitching_whip
    )

    # H.12 Pressure × experience (high-pressure games favor experienced teams)
    pressure = existing_feats.get('tournament_pressure', 0.10)
    wbc_exp_diff = existing_feats.get('wbc_experience_diff', 0.0)
    feats['pressure_experience_interaction'] = float(pressure * wbc_exp_diff)

    # H.13 Lineup vs SP handedness matchup (LHB lineup vs LHP = advantage)
    hand_diff = existing_feats.get('handedness_matchup_diff', 0.0)
    feats['handedness_woba_interaction'] = float(hand_diff * woba_diff)

    # H.14 K% × BB% ratio interaction (elite pitchers: high K, low BB)
    k_diff = existing_feats.get('k_pct_pitch_diff', 0.0)
    bb_diff = existing_feats.get('bb_pct_pitch_diff', 0.0)
    feats['k_bb_pitch_interaction'] = float(k_diff * -bb_diff)  # high K, low BB = dominant

    # H.15 Park × HR rate (slugging teams benefit more from HR-friendly parks)
    park_hr = existing_feats.get('park_hr_factor', 1.0)
    feats['park_hr_batting_interaction'] = float(
        (park_hr - 1.0) * (home.batting_woba - away.batting_woba)
    )

    # H.16 wOBA momentum × current wOBA (hot team + good team = dominant)
    woba_trend = existing_feats.get('woba_trend_7g_diff', 0.0)
    feats['woba_momentum_interaction'] = float(woba_diff * woba_trend)

    # H.17 RSI × elo (roster quality × historical strength)
    feats['rsi_elo_interaction'] = float(
        (home.roster_strength_index - away.roster_strength_index) * elo_diff / 1000.0
    )

    # H.18 Composite edge score
    feats['composite_edge_score'] = float(
        existing_feats.get('elo_diff', elo_diff) * 0.003 +
        existing_feats.get('xwoba_diff', woba_diff) * 10 +
        existing_feats.get('xfip_diff', fip_diff) * -0.5 +
        existing_feats.get('bullpen_depth_quality_diff', 0.0) * 0.2 +
        existing_feats.get('composite_defense_diff', 0.0) * 0.01
    )

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY I — Time-Series / Momentum (20 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_momentum_signals(home: TeamSnapshot, away: TeamSnapshot) -> dict[str, float]:
    """Compute 20 time-series and momentum alpha signals."""
    feats: dict[str, float] = {}

    # I.01 Recent form (win rates)
    feats['form_3g_diff'] = _safe_diff(home.form_3g, away.form_3g)
    feats['form_7g_diff'] = _safe_diff(home.form_7g, away.form_7g)
    feats['win_pct_l10_diff_v2'] = _safe_diff(home.win_pct_last_10, away.win_pct_last_10)

    # I.04 Streak momentum
    feats['win_streak_diff'] = _safe_diff(float(home.win_streak), float(away.win_streak))
    feats['win_streak_home'] = float(max(0, home.win_streak))
    feats['loss_streak_home'] = float(max(0, -home.win_streak))
    feats['win_streak_away'] = float(max(0, away.win_streak))
    feats['loss_streak_away'] = float(max(0, -away.win_streak))

    # I.08 Scoring trends (runs scored/allowed vs season average)
    feats['runs_scored_trend_diff'] = _safe_diff(
        home.runs_scored_trend_3g, away.runs_scored_trend_3g
    )
    feats['runs_allowed_trend_diff'] = _safe_diff(
        home.runs_allowed_trend_3g, away.runs_allowed_trend_3g
    )

    # I.10 wOBA & ERA 7-game rolling trend
    feats['woba_trend_diff_v2'] = _safe_diff(home.woba_trend_7g, away.woba_trend_7g)
    feats['era_trend_diff'] = _safe_diff(home.era_trend_7g, away.era_trend_7g)

    # I.12 Hot/cold pitcher identification (ERA trend threshold)
    hot_sp_home = 1.0 if home.era_trend_7g < -0.5 else 0.0  # ERA dropped > 0.5
    cold_sp_home = 1.0 if home.era_trend_7g > 0.5 else 0.0
    hot_sp_away = 1.0 if away.era_trend_7g < -0.5 else 0.0
    cold_sp_away = 1.0 if away.era_trend_7g > 0.5 else 0.0
    feats['hot_pitcher_diff'] = float(hot_sp_home - hot_sp_away)
    feats['cold_pitcher_diff'] = float(cold_sp_home - cold_sp_away)

    # I.14 Hot/cold batting
    hot_bat_home = 1.0 if home.woba_trend_7g > 0.010 else 0.0
    cold_bat_home = 1.0 if home.woba_trend_7g < -0.010 else 0.0
    hot_bat_away = 1.0 if away.woba_trend_7g > 0.010 else 0.0
    cold_bat_away = 1.0 if away.woba_trend_7g < -0.010 else 0.0
    feats['hot_batting_diff'] = float(hot_bat_home - hot_bat_away)
    feats['cold_batting_diff'] = float(cold_bat_home - cold_bat_away)

    # I.16 Composite momentum score
    feats['momentum_score_diff'] = float(
        feats['form_3g_diff'] * 0.3 +
        feats['form_7g_diff'] * 0.3 +
        feats['win_streak_diff'] * 0.05 +
        feats['woba_trend_diff_v2'] * 5.0 +
        feats['runs_scored_trend_diff'] * 0.1
    )

    # I.17 Regression-to-mean signal
    # Teams far from historical elo will regress; captures lucky vs unlucky streaks
    h_reg = (home.win_pct_last_10 - 0.5) * (1.0 - home.sample_size / 162.0)
    a_reg = (away.win_pct_last_10 - 0.5) * (1.0 - away.sample_size / 162.0)
    feats['regression_to_mean_diff'] = _safe_diff(h_reg, a_reg)

    # I.18 Variance signal (erratic teams = higher upset potential)
    h_var = abs(home.runs_scored_trend_3g) + abs(home.runs_allowed_trend_3g)
    a_var = abs(away.runs_scored_trend_3g) + abs(away.runs_allowed_trend_3g)
    feats['team_variance_diff'] = _safe_diff(h_var, a_var)
    feats['total_variance'] = float(h_var + a_var)  # total game variance

    # I.20 Clutch performance streak (consecutive clutch wins/losses)
    feats['clutch_streak_diff'] = _safe_diff(home.clutch_woba, away.clutch_woba) * home.win_streak

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY J — Lineup Construction Signals (17 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_lineup_signals(  # noqa: C901
    home: TeamSnapshot, away: TeamSnapshot,
    home_lineup: list[BatterSnapshot],
    away_lineup: list[BatterSnapshot],
    home_sp: PitcherSnapshot | None,
    away_sp: PitcherSnapshot | None,
) -> dict[str, float]:
    """Compute 17 lineup construction signals."""
    feats: dict[str, float] = {}

    # J.01 Lineup wOBA depth (average of all 9 spots)
    if home_lineup:
        h_woba_all = float(np.mean([b.woba for b in home_lineup]))
    else:
        h_woba_all = home.batting_woba
    if away_lineup:
        a_woba_all = float(np.mean([b.woba for b in away_lineup]))
    else:
        a_woba_all = away.batting_woba
    feats['lineup_woba_full_diff'] = _safe_diff(h_woba_all, a_woba_all)

    # J.02 1-3 hitter quality (leadoff, 2-hole, cleanup)
    if home_lineup and len(home_lineup) >= 3:
        h_top3_obp = float(np.mean([b.obp for b in home_lineup[:3]]))
    else:
        h_top3_obp = home.batting_woba
    if away_lineup and len(away_lineup) >= 3:
        a_top3_obp = float(np.mean([b.obp for b in away_lineup[:3]]))
    else:
        a_top3_obp = away.batting_woba
    feats['top3_obp_diff'] = _safe_diff(h_top3_obp, a_top3_obp)

    # J.03 Power hitters (3-5 spots)
    if home_lineup and len(home_lineup) >= 5:
        h_35_slg = float(np.mean([b.slg for b in home_lineup[2:5]]))
    else:
        h_35_slg = home.batting_woba + 0.1
    if away_lineup and len(away_lineup) >= 5:
        a_35_slg = float(np.mean([b.slg for b in away_lineup[2:5]]))
    else:
        a_35_slg = away.batting_woba + 0.1
    feats['power_core_slg_diff'] = _safe_diff(h_35_slg, a_35_slg)

    # J.04 Bottom of lineup (7-9 — WBC teams often have weak spots here)
    if home_lineup and len(home_lineup) >= 9:
        h_bot3_woba = float(np.mean([b.woba for b in home_lineup[6:9]]))
    else:
        h_bot3_woba = home.batting_woba * 0.80
    if away_lineup and len(away_lineup) >= 9:
        a_bot3_woba = float(np.mean([b.woba for b in away_lineup[6:9]]))
    else:
        a_bot3_woba = away.batting_woba * 0.80
    feats['bottom3_woba_diff'] = _safe_diff(h_bot3_woba, a_bot3_woba)

    # J.05 Lineup vs SP handedness matchup (aggregate)
    if home_sp and home_lineup:
        sp_h = getattr(home_sp, 'hand', 'R')
        h_opp_hand_adv = float(np.mean([b.vs_right_avg if sp_h == 'R' else b.vs_left_avg for b in home_lineup]))
    else:
        h_opp_hand_adv = h_woba_all
    if away_sp and away_lineup:
        sp_h = getattr(away_sp, 'hand', 'R')
        a_opp_hand_adv = float(np.mean([b.vs_right_avg if sp_h == 'R' else b.vs_left_avg for b in away_lineup]))
    else:
        a_opp_hand_adv = a_woba_all
    feats['lineup_sp_hand_matchup_diff'] = _safe_diff(h_opp_hand_adv, a_opp_hand_adv)

    # J.06 Lineup age (veterans vs young players in high-pressure situations)
    # Proxy: # of players with ops_plus > 110 (established MLB players)
    if home_lineup:
        h_vet_pct = sum(1 for b in home_lineup if b.ops_plus > 110) / len(home_lineup)
    else:
        h_vet_pct = 0.40
    if away_lineup:
        a_vet_pct = sum(1 for b in away_lineup if b.ops_plus > 110) / len(away_lineup)
    else:
        a_vet_pct = 0.40
    feats['veteran_pct_diff'] = _safe_diff(h_vet_pct, a_vet_pct)

    # J.07 Clutch batting depth
    if home_lineup:
        h_clutch_avg = float(np.mean([b.clutch_woba for b in home_lineup]))
    else:
        h_clutch_avg = home.clutch_woba
    if away_lineup:
        a_clutch_avg = float(np.mean([b.clutch_woba for b in away_lineup]))
    else:
        a_clutch_avg = away.clutch_woba
    feats['lineup_clutch_avg_diff'] = _safe_diff(h_clutch_avg, a_clutch_avg)

    # J.08 LHB vs RHP stack (multiple lefties vs righty = platoon advantage)
    if home_lineup and away_sp:
        sp_hand = getattr(away_sp, 'hand', 'R')
        if sp_hand == 'R':
            h_stack = sum(1 for b in home_lineup if b.vs_right_avg > b.vs_left_avg)
        else:
            h_stack = sum(1 for b in home_lineup if b.vs_left_avg > b.vs_right_avg)
        feats['platoon_stack_home'] = float(h_stack / len(home_lineup))
    else:
        feats['platoon_stack_home'] = 0.5
    if away_lineup and home_sp:
        sp_hand = getattr(home_sp, 'hand', 'R')
        if sp_hand == 'R':
            a_stack = sum(1 for b in away_lineup if b.vs_right_avg > b.vs_left_avg)
        else:
            a_stack = sum(1 for b in away_lineup if b.vs_left_avg > b.vs_right_avg)
        feats['platoon_stack_away'] = float(a_stack / len(away_lineup))
    else:
        feats['platoon_stack_away'] = 0.5
    feats['platoon_stack_diff'] = feats['platoon_stack_home'] - feats['platoon_stack_away']

    # J.09 Barrel % depth (power hitter concentration)
    if home_lineup:
        h_barrel = float(np.mean([getattr(b, 'barrel_pct', 0.08) for b in home_lineup]))
    else:
        h_barrel = home.batting_barrel_pct
    if away_lineup:
        a_barrel = float(np.mean([getattr(b, 'barrel_pct', 0.08) for b in away_lineup]))
    else:
        a_barrel = away.batting_barrel_pct
    feats['lineup_barrel_pct_diff'] = _safe_diff(h_barrel, a_barrel)

    # J.10 wOBA variance (high variance lineup = more blowout potential)
    if home_lineup and len(home_lineup) > 1:
        h_woba_var = float(np.std([b.woba for b in home_lineup]))
    else:
        h_woba_var = 0.05
    if away_lineup and len(away_lineup) > 1:
        a_woba_var = float(np.std([b.woba for b in away_lineup]))
    else:
        a_woba_var = 0.05
    feats['lineup_woba_variance_diff'] = _safe_diff(h_woba_var, a_woba_var)
    feats['total_lineup_variance'] = float(h_woba_var + a_woba_var)

    # J.11 International experience in lineup
    feats['intl_exp_diff'] = _safe_diff(
        float(home.wbc_experience_games), float(away.wbc_experience_games)
    )

    # J.14 Stolen base threat
    feats['sb_threat_diff'] = _safe_diff(
        home.batting_sprint_speed * home.batting_stolen_base_pct,
        away.batting_sprint_speed * away.batting_stolen_base_pct
    ) / 10.0

    # J.15 Composite lineup quality score
    feats['lineup_quality_score_diff'] = float(
        feats.get('lineup_woba_full_diff', 0) * 10.0 +
        feats.get('top3_obp_diff', 0) * 3.0 +
        feats.get('power_core_slg_diff', 0) * 2.0 +
        feats.get('lineup_clutch_avg_diff', 0) * 5.0
    )

    # J.16 Missing star batter impact
    feats['missing_star_batter_diff'] = float(away.missing_core_batter) - float(home.missing_core_batter)

    return feats


# ═══════════════════════════════════════════════════════════════════════════
# MASTER BUILDER — Assemble all 260 signals
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AlphaSignals:
    """Container for all computed alpha signals."""
    feature_dict: dict[str, float] = field(default_factory=dict)
    categories_computed: list[str] = field(default_factory=list)
    n_signals: int = 0

    @property
    def signal_names(self) -> list[str]:
        return sorted(self.feature_dict.keys())


def build_alpha_signals(  # noqa: C901
    matchup: Matchup,
    pregame_text: PregameTextBundle | None = None,
    cutoff_date: str = "2099-12-31",
    enable_kg: bool = True,
    enable_nlp: bool = True,
    enable_market_sim: bool = True,
    use_llm: bool = False,
) -> AlphaSignals:
    """
    Compute all 277+ alpha signals from a Matchup object.

    擴充三層新特徵模組 (借鑑 MiroFish 架構，Phase 1-3)：
      K: 棒球知識圖譜特徵 (20 signals)  — enable_kg
      L: NLP 賽前語義特徵 (11 signals)  — enable_nlp
      M: 市場代理人模擬特徵 (10 signals) — enable_market_sim

    Args:
        matchup:         Matchup 物件（開賽前狀態快照）
        pregame_text:    賽前文字資料包（可選，None 時 NLP 使用中性值）
        cutoff_date:     知識圖譜查詢截止日 'YYYY-MM-DD'（防止資料外洩）
        enable_kg:       啟用知識圖譜特徵
        enable_nlp:      啟用 NLP 特徵
        enable_market_sim: 啟用市場模擬特徵
        use_llm:         NLP 是否使用本地 LLM（需 Ollama 服務運行）

    Returns:
        AlphaSignals with combined feature_dict ready for ML models.
    """
    home = matchup.home
    away = matchup.away
    result: dict[str, float] = {}
    computed = []

    try:
        feats_a = _compute_batting_signals(home, away, matchup.home_lineup, matchup.away_lineup)
        result.update(feats_a)
        computed.append("A:Batting")
    except Exception as e:
        logger.warning("Category A (Batting) failed: %s", e)

    try:
        feats_b = _compute_pitching_signals(home, away, matchup.home_sp, matchup.away_sp)
        result.update(feats_b)
        computed.append("B:Pitching")
    except Exception as e:
        logger.warning("Category B (Pitching) failed: %s", e)

    try:
        feats_c = _compute_bullpen_signals(
            home, away, matchup.home_bullpen, matchup.away_bullpen,
            round_num=getattr(matchup, 'tournament_round_num', 1)
        )
        result.update(feats_c)
        computed.append("C:Bullpen")
    except Exception as e:
        logger.warning("Category C (Bullpen) failed: %s", e)

    try:
        feats_d = _compute_defensive_signals(home, away)
        result.update(feats_d)
        computed.append("D:Defense")
    except Exception as e:
        logger.warning("Category D (Defense) failed: %s", e)

    try:
        feats_e = _compute_wbc_signals(home, away, matchup)
        result.update(feats_e)
        computed.append("E:WBC")
    except Exception as e:
        logger.warning("Category E (WBC) failed: %s", e)

    try:
        feats_f = _compute_market_signals(home, away, matchup)
        result.update(feats_f)
        computed.append("F:Market")
    except Exception as e:
        logger.warning("Category F (Market) failed: %s", e)

    try:
        feats_g = _compute_environment_signals(home, away, matchup)
        result.update(feats_g)
        computed.append("G:Environment")
    except Exception as e:
        logger.warning("Category G (Environment) failed: %s", e)

    try:
        feats_h = _compute_interaction_signals(result, home, away)
        result.update(feats_h)
        computed.append("H:Interaction")
    except Exception as e:
        logger.warning("Category H (Interaction) failed: %s", e)

    try:
        feats_i = _compute_momentum_signals(home, away)
        result.update(feats_i)
        computed.append("I:Momentum")
    except Exception as e:
        logger.warning("Category I (Momentum) failed: %s", e)

    try:
        feats_j = _compute_lineup_signals(
            home, away, matchup.home_lineup, matchup.away_lineup,
            matchup.home_sp, matchup.away_sp
        )
        result.update(feats_j)
        computed.append("J:Lineup")
    except Exception as e:
        logger.warning("Category J (Lineup) failed: %s", e)

    # ── Category K: 棒球知識圖譜特徵 (20 signals) ──────────────────────────
    if enable_kg:
        try:
            kg = get_default_kg()
            feats_k = compute_knowledge_graph_signals(matchup, kg, cutoff_date)
            result.update(feats_k)
            computed.append("K:KnowledgeGraph")
        except Exception as e:
            logger.warning("Category K (KnowledgeGraph) failed: %s", e)

    # ── Category L: NLP 賽前語義特徵 (11 signals) ──────────────────────────
    if enable_nlp:
        try:
            if pregame_text is not None:
                feats_l = compute_nlp_signals(pregame_text, use_llm=use_llm)
            else:
                feats_l = build_empty_nlp_features()
            result.update(feats_l)
            computed.append("L:NLP")
        except Exception as e:
            logger.warning("Category L (NLP) failed: %s", e)
            result.update(build_empty_nlp_features())

    # ── Category M: 市場代理人模擬特徵 (10 signals) ────────────────────────
    if enable_market_sim:
        try:
            opening_prob = getattr(matchup.home, "opening_ml_prob", 0.50)
            model_prob = result.get("elo_win_prob_home", opening_prob)
            public_pct = getattr(matchup, "public_bet_pct_home", 0.55)
            feats_m = compute_market_simulation_signals(
                opening_home_prob=float(opening_prob),
                model_home_prob=float(model_prob),
                public_bet_pct_home=float(public_pct),
            )
            result.update(feats_m)
            computed.append("M:MarketSim")
        except Exception as e:
            logger.warning("Category M (MarketSim) failed: %s", e)

    # ── Category N: 崩盤風險特徵 (12 signals) ──────────────────────────────
    try:
        feats_n = _compute_blowout_risk_signals(home, away, matchup, result)
        result.update(feats_n)
        computed.append("N:BlowoutRisk")
    except Exception as e:
        logger.warning("Category N (BlowoutRisk) failed: %s", e)

    # Round all to 4 decimal places
    result = {k: round(float(v), 4) for k, v in result.items()}

    return AlphaSignals(
        feature_dict=result,
        categories_computed=computed,
        n_signals=len(result),
    )


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY N — Blowout Risk / Data Quality (12 signals)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_blowout_risk_signals(
    home: TeamSnapshot,
    away: TeamSnapshot,
    matchup: Matchup,
    existing_feats: dict[str, float],
) -> dict[str, float]:
    """Compute 12 blowout-risk and data-quality signals.

    觸發自 3/9 賽後檢討（B06 墨西哥 16:0 巴西 / C09 先發身份問題）：
      N.01-04  大比分崩盤鏈（Elo 差距 → tanh 正規化 → 慈悲規則危害）
      N.05-07  先發身份可信度（資料品質 → 置信度閘）
      N.08-09  先發陣容覆蓋率（確認打者 / 9 人名單覆蓋比）
      N.10-12  牛棚串聯疲勞（錦標賽跨賽 7 天累計球數正規化）
    """
    feats: dict[str, float] = {}
    round_num = getattr(matchup, "tournament_round_num", 1)

    # ── N.01-04 大比分崩盤鏈 ──────────────────────────────────────────────
    # N.01 Elo 差距絕對值 → 原始不對稱強度
    elo_gap = abs(home.elo - away.elo)
    feats["elo_gap_abs"] = float(elo_gap)

    # N.02 mismatch_blowout_propensity: tanh 正規化 (Elo gap 150 ≈ 0.76)
    # WBC 2023 實測：elo_gap > 150 場次中 P(分差≥7) ≈ 0.35
    feats["mismatch_blowout_propensity"] = float(np.tanh(elo_gap / 150.0))

    # N.03 wOBA 差距放大崩盤風險
    woba_diff = existing_feats.get("woba_diff", 0.0)
    feats["woba_gap_blowout_risk"] = float(min(1.0, abs(woba_diff) * 5.0))

    # N.04 WBC 慈悲規則危害：錦標賽後段（round >= 3 = QF）比賽更長
    # P(mercy rule) ≈ blowout_propensity × 0.5，Pool 降權（常被中斷）
    round_mercy_factor = {1: 0.30, 2: 0.45, 3: 0.60, 4: 0.70, 5: 0.70}.get(round_num, 0.30)
    feats["mercy_rule_hazard"] = float(
        min(1.0, feats["mismatch_blowout_propensity"] * round_mercy_factor)
    )

    # ── N.05-07 先發身份可信度 ───────────────────────────────────────────
    # 若 SP 為 None → 身份完全未知（信心 = 0）
    # 若 SP 存在但名稱為空 / "TBD" → 部分未知
    def _sp_confidence(sp: "PitcherSnapshot | None") -> float:
        if sp is None:
            return 0.0
        name = (sp.name or "").strip().upper()
        if not name or name in {"TBD", "UNKNOWN", "?"}:
            return 0.5
        return 1.0

    h_sic = _sp_confidence(matchup.home_sp)
    a_sic = _sp_confidence(matchup.away_sp)
    feats["starter_identity_confidence_home"] = h_sic
    feats["starter_identity_confidence_away"] = a_sic
    feats["starter_identity_confidence_min"] = float(min(h_sic, a_sic))

    # ── N.08-09 先發陣容覆蓋率 ───────────────────────────────────────────
    h_cov = min(1.0, len(matchup.home_lineup) / 9.0)
    a_cov = min(1.0, len(matchup.away_lineup) / 9.0)
    feats["lineup_coverage_min"] = float(min(h_cov, a_cov))
    feats["lineup_coverage_diff"] = float(h_cov - a_cov)

    # ── N.10-12 牛棚串聯疲勞（7 天累計球數正規化）────────────────────────
    # 300 球 / 7 天 ≈ WBC 高負擔上限（Pool 轉 QF 連日出賽情境）
    h_fatigue = min(1.0, home.bullpen_workload_7d / 300.0)
    a_fatigue = min(1.0, away.bullpen_workload_7d / 300.0)
    feats["bullpen_cascade_fatigue_home"] = float(h_fatigue)
    feats["bullpen_cascade_fatigue_away"] = float(a_fatigue)
    feats["bullpen_cascade_fatigue_diff"] = float(h_fatigue - a_fatigue)

    return feats


# ── Signal catalogue (metadata registry) ────────────────────────────────────

ALPHA_SIGNAL_CATALOGUE: list[SignalMeta] = [
    # CATEGORY A
    SignalMeta("xwoba_diff", "A", "xwOBA normalizes luck; better predictor than wOBA", "very_high", False, "Statcast API"),
    SignalMeta("xwoba_luck_diff", "A", "xwOBA-wOBA gap predicts regression", "high", False, "Statcast API"),
    SignalMeta("hard_hit_pct_diff", "A", "Consistent hard contact → run production", "high", False, "Statcast API"),
    SignalMeta("exit_velo_diff", "A", "Higher exit velocity = better outcome probability", "high", False, "Statcast API"),
    SignalMeta("barrel_pct_diff", "A", "Barrel% is leading indicator of power production", "very_high", False, "Statcast API"),
    SignalMeta("k_pct_bat_diff", "A", "K% affects BABIP and lineup flow", "high", True, "FanGraphs"),
    SignalMeta("bb_pct_bat_diff", "A", "BB% = plate discipline = run creation", "high", True, "FanGraphs"),
    SignalMeta("chase_pct_diff", "A", "Chase rate predicts K% and weakness vs off-speed", "medium", False, "Statcast"),
    SignalMeta("iso_diff", "A", "Isolated power (SLG-AVG) predicts HR rate", "high", True, "FanGraphs"),
    SignalMeta("babip_bat_diff", "A", "BABIP vs xBABIP regression signal", "medium", True, "FanGraphs"),
    SignalMeta("sprint_speed_diff", "A", "Speed affects baserunning and defensive range", "medium", False, "Statcast"),
    SignalMeta("wrc_plus_diff", "A", "Park/league adjusted offense composite", "very_high", True, "FanGraphs"),
    SignalMeta("two_out_risp_diff", "A", "Clutch hitting in scoring position", "medium", False, "FanGraphs"),
    SignalMeta("top3_woba_diff", "A", "Top lineup concentration drives scoring probability", "high", True, "Computed"),
    SignalMeta("lineup_depth_diff", "A", "Deep lineups survive bullpen matchups", "high", True, "Computed"),
    # CATEGORY B
    SignalMeta("xfip_diff", "B", "xFIP removes HR luck; better FIP predictor", "very_high", True, "FanGraphs"),
    SignalMeta("siera_diff", "B", "SIERA models batted ball; most accurate ERA estimator", "very_high", False, "FanGraphs"),
    SignalMeta("k_pct_pitch_diff", "B", "SP strikeout rate predicts dominance", "very_high", True, "FanGraphs"),
    SignalMeta("k_bb_ratio_pitch_diff", "B", "K/BB = command + stuff combined", "very_high", True, "FanGraphs"),
    SignalMeta("swstr_pct_diff", "B", "Swinging strike rate is most predictive SP metric", "very_high", False, "Statcast"),
    SignalMeta("fb_velo_diff", "B", "Fastball velocity correlates with Stuff+", "high", True, "Statcast"),
    SignalMeta("spin_rate_zscore_diff_v2", "B", "Unusual spin = grip issue or stuff decline", "medium", True, "Statcast"),
    SignalMeta("era_estimator_divergence_diff", "B", "ERA vs xFIP gap signals luck direction", "high", True, "Computed"),
    # CATEGORY C
    SignalMeta("bullpen_fip_diff", "C", "Bullpen FIP is main OU signal in WBC (60% innings)", "very_high", True, "FanGraphs"),
    SignalMeta("bullpen_hl_era_diff", "C", "High-leverage bullpen ERA predicts close-game performance", "very_high", True, "FanGraphs"),
    SignalMeta("bullpen_arms_available_diff", "C", "Available rested arms = sustainability", "very_high", True, "Computed"),
    SignalMeta("wbc_bullpen_demand_diff", "C", "WBC pitch limits force more bullpen usage", "very_high", True, "Computed"),
    SignalMeta("piggyback_quality_diff", "C", "2nd SP ERA critical in WBC pool stage", "very_high", True, "Computed"),
    # CATEGORY E
    SignalMeta("wbc_experience_diff", "E", "International experience reduces pressure variance", "high", True, "WBC/WBSC"),
    SignalMeta("intl_win_pct_diff", "E", "International win % is most comparable sample", "high", True, "WBSC"),
    SignalMeta("rsi_diff", "E", "Roster Strength Index captures star player impact", "very_high", True, "Computed"),
    SignalMeta("wbc_adjusted_bullpen_diff", "E", "WBC pitch limits transform bullpen valuation", "very_high", True, "Computed"),
    # CATEGORY F
    SignalMeta("ml_movement_home", "F", "Line movement reveals sharp money direction", "very_high", False, "Odds APIs"),
    SignalMeta("sharp_public_divergence", "F", "Sharp vs public split = best betting signal", "very_high", False, "Odds APIs"),
    SignalMeta("reverse_line_move_flag", "F", "RLM: public on one side, line moves other way", "very_high", False, "Odds APIs"),
    SignalMeta("value_signal_home", "F", "Model vs market divergence = EV opportunity", "very_high", True, "Computed"),
    # CATEGORY H
    SignalMeta("composite_edge_score", "H", "Combined alpha signal from all categories", "very_high", True, "Computed"),
    SignalMeta("elo_woba_interaction", "H", "Dominance compounds when Elo + offense align", "high", True, "Computed"),
    # CATEGORY I
    SignalMeta("momentum_score_diff", "I", "Short-term form is predictive in short tournament", "high", True, "Computed"),
    SignalMeta("regression_to_mean_diff", "I", "Hot/cold streaks revert; captures timing", "medium", True, "Computed"),
]


def get_signal_catalogue_by_category() -> dict[str, list[SignalMeta]]:
    """Return signal catalogue organized by category."""
    cat: dict[str, list[SignalMeta]] = {}
    for s in ALPHA_SIGNAL_CATALOGUE:
        cat.setdefault(s.category, []).append(s)
    return cat


def count_signals_by_availability() -> dict[str, int]:
    """Count signals by data availability."""
    avail = sum(1 for s in ALPHA_SIGNAL_CATALOGUE if s.data_available)
    return {"available_now": avail, "needs_new_data": len(ALPHA_SIGNAL_CATALOGUE) - avail}
