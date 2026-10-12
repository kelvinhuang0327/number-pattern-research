"""
Domain schemas — expanded to cover all data flowing through the prediction pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Team / Player Snapshots ──────────────────────────────────────────────────

@dataclass
class PitcherSnapshot:
    name: str
    team: str
    era: float
    fip: float
    whip: float
    k_per_9: float
    bb_per_9: float
    stuff_plus: float
    ip_last_30: float
    era_last_3: float
    pitch_count_last_3d: int
    fastball_velo: float
    high_leverage_era: float
    role: str = "SP"   # SP | RP | PB
    pitch_mix: dict[str, float] = field(default_factory=dict)
    recent_fastball_velos: list[float] = field(default_factory=list)
    career_fastball_velo: float = 0.0
    woba_vs_left: float = 0.320
    woba_vs_right: float = 0.320
    innings_last_14d: float = 0.0
    season_avg_innings_per_14d: float = 0.0
    recent_spin_rate: float = 0.0
    career_spin_rate_mean: float = 0.0
    career_spin_rate_std: float = 0.0

    @property
    def fatigue_score(self) -> float:
        """0-1 fatigue index based on recent workload."""
        base = min(1.0, self.pitch_count_last_3d / 100.0)
        era_penalty = max(0, (self.era_last_3 - self.era)) / 3.0
        return min(1.0, base + era_penalty * 0.3)


@dataclass
class BatterSnapshot:
    name: str
    team: str
    avg: float
    obp: float
    slg: float
    woba: float
    ops_plus: float
    clutch_woba: float
    vs_left_avg: float
    vs_right_avg: float
    barrel_pct: float = 0.0
    # Extended alpha signal fields
    xwoba: float = 0.0            # Expected wOBA (Statcast)
    hard_hit_pct: float = 0.38   # Hard-hit ball % (exit velo ≥ 95 mph)
    launch_angle_avg: float = 12.0  # Average launch angle (degrees)
    exit_velo_avg: float = 88.0   # Average exit velocity (mph)
    k_pct: float = 0.22           # Strikeout %
    bb_pct: float = 0.09          # Walk %
    chase_pct: float = 0.30       # Chase rate (O-Swing%)
    contact_pct: float = 0.77     # Contact rate
    iso: float = 0.155            # Isolated power (SLG - AVG)
    babip: float = 0.300          # BABIP
    sprint_speed: float = 27.0    # ft/s
    wrc_plus: float = 100.0       # wRC+


@dataclass
class TeamSnapshot:
    team: str
    elo: float
    batting_woba: float
    batting_ops_plus: float
    pitching_fip: float
    pitching_whip: float
    pitching_stuff_plus: float
    der: float
    bullpen_depth: float
    pitch_limit: int
    bullpen_era: float = 3.50
    bullpen_pitches_3d: int = 0
    runs_per_game: float = 4.5
    runs_allowed_per_game: float = 4.5
    clutch_woba: float = 0.320
    roster_strength_index: float = 80.0
    missing_core_batter: bool = False
    ace_pitch_count_limited: bool = False
    top50_stars: int = 0
    sample_size: int = 120
    league_prior_strength: float = 0.0
    win_pct_last_10: float = 0.5
    rest_days: int = 1
    time_zone_offset: float = 0.0          # Time zone difference relative to UTC
    dist_traveled_prev_7d: float = 0.0     # km traveled in last 7 days
    # ── Extended alpha signal fields ─────────────────────────────────────────
    # Batting deep metrics
    batting_xwoba: float = 0.0            # Team xwOBA (default: use wOBA proxy)
    batting_hard_hit_pct: float = 0.38    # Team hard-hit %
    batting_barrel_pct: float = 0.08      # Team barrel %
    batting_k_pct: float = 0.22           # Team strikeout %
    batting_bb_pct: float = 0.09          # Team walk %
    batting_chase_pct: float = 0.30       # Team chase rate
    batting_iso: float = 0.155            # Team ISO
    batting_babip: float = 0.300          # Team BABIP
    batting_line_drive_pct: float = 0.22  # Line drive %
    batting_gb_pct: float = 0.43          # Ground ball %
    batting_fb_pct: float = 0.35          # Fly ball %
    batting_sprint_speed: float = 27.0    # Team avg sprint speed (ft/s)
    batting_wrc_plus: float = 100.0       # Team wRC+
    batting_stolen_base_pct: float = 0.70  # SB success %
    batting_two_out_risp_avg: float = 0.240  # 2-out RISP batting avg
    # Pitching deep metrics (SP-level)
    pitching_xfip: float = 0.0           # xFIP (default: use FIP proxy)
    pitching_siera: float = 0.0          # SIERA (default: use FIP proxy)
    pitching_k_pct: float = 0.22         # SP strikeout %
    pitching_bb_pct: float = 0.09        # SP walk %
    pitching_swstr_pct: float = 0.11     # Swinging strike %
    pitching_gb_pct: float = 0.45        # SP ground ball %
    pitching_hr9: float = 1.20           # HR/9
    pitching_lob_pct: float = 0.72       # Left on base %
    pitching_babip: float = 0.300        # SP BABIP
    # Bullpen deep metrics
    bullpen_fip: float = 4.50            # Bullpen FIP
    bullpen_xfip: float = 0.0            # Bullpen xFIP
    bullpen_k_pct: float = 0.22          # Bullpen K%
    bullpen_bb_pct: float = 0.09         # Bullpen BB%
    bullpen_hr9: float = 1.20            # Bullpen HR/9
    bullpen_high_leverage_era: float = 4.00  # High-leverage ERA
    bullpen_arms_available: int = 5      # Arms with 1+ days rest
    bullpen_workload_7d: int = 0         # Total pitches last 7 days
    closer_available: bool = True        # Closer available (not fatigued)
    # Defensive metrics
    team_drs: float = 0.0               # Defensive Runs Saved
    team_uzr: float = 0.0               # Ultimate Zone Rating
    catcher_framing_runs: float = 0.0   # Catcher framing runs
    # WBC / International experience
    wbc_experience_games: int = 0       # Career WBC games played
    intl_era: float = 0.0               # Career ERA in international play
    intl_woba_allowed: float = 0.0      # Career wOBA allowed in intl play
    intl_batting_woba: float = 0.0      # Team batting wOBA in intl play
    intl_win_pct: float = 0.50          # Win % in international play
    intl_run_diff: float = 0.0          # Run diff/game in intl play
    # Time-series / Momentum
    form_3g: float = 0.50               # Win rate last 3 games
    form_7g: float = 0.50               # Win rate last 7 games
    win_streak: int = 0                 # Current win streak (negative = loss)
    runs_scored_trend_3g: float = 0.0   # Avg runs scored last 3 games vs season avg
    runs_allowed_trend_3g: float = 0.0  # Avg runs allowed last 3 games vs season avg
    woba_trend_7g: float = 0.0          # wOBA trend vs season avg (7-game rolling)
    era_trend_7g: float = 0.0           # ERA trend vs season avg (7-game rolling)
    # Market / Betting signals (pre-game)
    opening_ml_prob: float = 0.50       # Implied prob from opening money line
    closing_ml_prob: float = 0.50       # Implied prob from closing money line
    public_bet_pct: float = 0.50        # % of public bets (0-1)
    sharp_handle_pct: float = 0.50      # % of sharp money (0-1)
    # Schedule / workload
    games_last_5d: int = 1              # Games played in last 5 days
    consecutive_games: int = 0          # Consecutive games without a day off


@dataclass
class Matchup:
    game_id: str
    tournament: str
    game_time_utc: str
    home: TeamSnapshot
    away: TeamSnapshot
    home_sp: PitcherSnapshot | None = None
    away_sp: PitcherSnapshot | None = None
    home_bullpen: list[PitcherSnapshot] = field(default_factory=list)
    # ── Extended Matchup fields ───────────────────────────────────────────────
    away_bullpen: list[PitcherSnapshot] = field(default_factory=list)
    home_lineup: list[BatterSnapshot] = field(default_factory=list)
    away_lineup: list[BatterSnapshot] = field(default_factory=list)
    venue: str = ""
    round_name: str = "Pool"
    neutral_site: bool = True
    weather: str = "dome"
    umpire_id: str = "generic_avg"         # For umpire strike zone profile
    elevation_m: float = 0.0               # Venue elevation (affects ball flight)
    temp_f: float = 72.0
    humidity_pct: float = 0.50
    wind_speed_mph: float = 0.0
    wind_direction: str = "none"
    is_dome: bool = False
    # ── WBC Stage & Pressure ─────────────────────────────────────────────────
    is_elimination_game: bool = False      # Loser is eliminated
    is_knockout_stage: bool = False        # QF / SF / F
    tournament_round_num: int = 1          # 1=Pool, 2=Super Round, 3=QF, 4=SF, 5=F
    crowd_home_pct: float = 0.50           # % of crowd supporting home team
    # ── Market Intelligence ───────────────────────────────────────────────────
    opening_ml_home_odds: float = 0.0      # Decimal odds for home (opening)
    closing_ml_home_odds: float = 0.0      # Decimal odds for home (closing)
    opening_ou_line: float = 7.5           # Opening O/U line
    closing_ou_line: float = 7.5           # Closing O/U line
    public_bet_pct_home: float = 0.50      # Public bets on home team
    sharp_handle_pct_home: float = 0.50    # Sharp money on home team
    steam_move_flag: bool = False          # Steam move detected
    reverse_line_move_flag: bool = False   # RLM: public backs away, line moves home
    # ── Park Factor Granular ──────────────────────────────────────────────────
    park_hr_factor: float = 1.0            # HR park factor
    park_run_factor: float = 1.0           # Run park factor
    park_k_factor: float = 1.0             # Strikeout park factor
    stadium_capacity_pct: float = 0.80     # Crowd fill ratio (noise factor)
    local_time_hour: int = 19              # Local game time (hour, 0-23)


# ── Odds ─────────────────────────────────────────────────────────────────────

@dataclass
class OddsLine:
    sportsbook: str
    market: str           # ML | RL | OU | OE | F5 | TT
    side: str
    line: float | None
    decimal_odds: float
    source_type: str      # international | tsl
    timestamp: str = ""


@dataclass
class OddsTimeSeries:
    """Tracks odds movement over time for steam-move detection."""
    sportsbook: str
    market: str
    side: str
    snapshots: list[dict] = field(default_factory=list)
    # Each snapshot: {"timestamp": ..., "odds": ..., "line": ...}


# ── Predictions ──────────────────────────────────────────────────────────────

@dataclass
class SubModelResult:
    model_name: str
    home_win_prob: float
    away_win_prob: float
    expected_home_runs: float = 0.0
    expected_away_runs: float = 0.0
    confidence: float = 0.5
    diagnostics: dict = field(default_factory=dict)


@dataclass
class PredictionResult:
    game_id: str
    home_win_prob: float
    away_win_prob: float
    expected_home_runs: float
    expected_away_runs: float
    x_factors: list[str]
    diagnostics: dict[str, float]
    sub_model_results: list[SubModelResult] = field(default_factory=list)
    confidence_score: float = 0.5
    market_bias_score: float = 0.0


# ── Simulation ───────────────────────────────────────────────────────────────

@dataclass
class SimulationSummary:
    home_win_prob: float
    away_win_prob: float
    over_prob: float
    under_prob: float
    home_cover_prob: float
    away_cover_prob: float
    mean_total_runs: float = 0.0
    std_total_runs: float = 0.0
    odd_prob: float = 0.5
    even_prob: float = 0.5
    home_f5_win_prob: float = 0.5
    away_f5_win_prob: float = 0.5
    score_distribution: dict = field(default_factory=dict)
    scenarios: dict = field(default_factory=dict)
    n_simulations: int = 50_000


# ── Betting ──────────────────────────────────────────────────────────────────

@dataclass
class BetRecommendation:
    market: str
    side: str
    line: float | None
    sportsbook: str
    source_type: str
    win_probability: float
    implied_probability: float
    ev: float
    edge: float
    kelly_fraction: float
    stake_fraction: float
    stake_amount: float = 0.0
    confidence: float = 0.5
    reason: str = ""


# ── Backtest ─────────────────────────────────────────────────────────────────

@dataclass
class BacktestMetrics:
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    total_staked: float = 0.0
    total_return: float = 0.0
    roi: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_ev: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    kelly_growth_rate: float = 0.0


# ── Training Results ─────────────────────────────────────────────────────────

@dataclass
class TrainingResult:
    model_name: str
    accuracy: float
    logloss: float
    brier_score: float
    auc_roc: float = 0.0
    feature_importance: dict[str, float] = field(default_factory=dict)
    training_time_seconds: float = 0.0
    n_samples: int = 0
    cv_scores: list[float] = field(default_factory=list)


# ── Game Output ──────────────────────────────────────────────────────────────

@dataclass
class GameOutput:
    """Final output for each game — all 10 required fields."""
    game_id: str
    home_team: str
    away_team: str
    home_win_prob: float
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
    market_bias_score: float
    ev_best: float
    best_bet_strategy: str
    confidence_index: float
    top_3_bets: list[BetRecommendation] = field(default_factory=list)


# ── API Contracts ────────────────────────────────────────────────────────────

@dataclass
class AnalyzeRequest:
    game_id: str
    line_total: float = 7.5
    line_spread_home: float = -1.5
    force_retrain: bool = False


@dataclass
class AnalyzeResponse:
    game_output: GameOutput | None = None
    markdown_report: str = ""
    json_report: str = ""
    decision_report: Any | None = None
    calibration_metrics: dict[str, float] | None = None
    portfolio_metrics: dict[str, float] | None = None
    deployment_gate_report: dict[str, Any] | None = None
