from __future__ import annotations

from dataclasses import dataclass


MANDATORY_FEATURE_DOMAINS = [
    "Team strength features",
    "Pitcher micro-metrics",
    "Bullpen fatigue metrics",
    "Lineup synergy metrics",
    "Game theory variables",
    "Travel & rest factors",
    "Weather variables",
    "Market microstructure signals",
    "Line movement velocity",
    "Sharp money detection",
    "Closing line divergence",
    "Volatility clustering",
    "Cross-market correlation",
    "Score state transition probabilities",
    "Psychological pressure proxies",
]


@dataclass(frozen=True)
class FeatureDomainSpec:
    domain: str
    feature: str
    signal_hypothesis: str
    quantification: str
    data_requirements: str
    validation_method: str


def build_feature_space_expansion() -> list[FeatureDomainSpec]:
    specs = [
        FeatureDomainSpec(
            domain="Team strength features",
            feature="Bayes-shrunk team latent power",
            signal_hypothesis="Shrunk latent power captures persistent quality beyond noisy short windows.",
            quantification="Posterior mean from Elo + run-differential + roster-strength hierarchical prior.",
            data_requirements="Historical game results, opponent-adjusted run differential, roster availability timeline.",
            validation_method="Nested walk-forward with Brier/logloss delta and calibration slope stability.",
        ),
        FeatureDomainSpec(
            domain="Pitcher micro-metrics",
            feature="Pitch-mix shape drift index",
            signal_hypothesis="Intra-tournament pitch-shape drift predicts command degradation and run prevention decay.",
            quantification="Mahalanobis distance of pitch characteristics vs trailing baseline by pitch type.",
            data_requirements="Pitch-level data: velocity, IVB/HB, spin, release point, usage by outing.",
            validation_method="Out-of-time uplift on expected runs MAE and first-5 market CLV.",
        ),
        FeatureDomainSpec(
            domain="Bullpen fatigue metrics",
            feature="Leverage-weighted reliever load",
            signal_hypothesis="High-leverage overuse is more predictive than raw pitch counts.",
            quantification="Sum(pitches_last_3d * leverage_index) / active_relievers.",
            data_requirements="Reliever appearances, leverage index, pitch counts, rest days.",
            validation_method="Ablation test on late-inning win-prob calibration and tail-loss rate.",
        ),
        FeatureDomainSpec(
            domain="Lineup synergy metrics",
            feature="Order interaction run-creation score",
            signal_hypothesis="Adjacent hitter interaction improves run generation beyond independent batter quality.",
            quantification="Markov run expectancy gain from lineup adjacency interaction coefficients.",
            data_requirements="Projected lineup order, handedness chain, base/out run expectancy matrix.",
            validation_method="Cross-year transfer test on team total and over/under accuracy.",
        ),
        FeatureDomainSpec(
            domain="Game theory variables",
            feature="Bullpen strategy game-state response",
            signal_hypothesis="Manager strategy under tournament constraints shifts matchup probabilities.",
            quantification="Expected leverage deployment score conditioned on elimination pressure and rest.",
            data_requirements="Manager historical substitution patterns, tournament stage, bullpen status.",
            validation_method="Counterfactual replay on historical games with strategy intervention modeling.",
        ),
        FeatureDomainSpec(
            domain="Travel & rest factors",
            feature="Circadian disruption index",
            signal_hypothesis="Jet lag and compressed rest reduce batting contact quality and command precision.",
            quantification="Timezone shift magnitude * days since arrival decay + travel distance penalty.",
            data_requirements="Travel itinerary, local game time, rest days, timezone offsets.",
            validation_method="Difference-in-differences against matched non-travel control games.",
        ),
        FeatureDomainSpec(
            domain="Weather variables",
            feature="Aerodynamic run environment factor",
            signal_hypothesis="Humidity, temperature, and wind change batted-ball carry and run distribution.",
            quantification="Physics-informed carry multiplier merged into expected run parameters.",
            data_requirements="Venue weather snapshots, roof state, historical weather-to-run mapping.",
            validation_method="Calibration by weather regime bins and outlier sensitivity checks.",
        ),
        FeatureDomainSpec(
            domain="Market microstructure signals",
            feature="Order-book fragility score",
            signal_hypothesis="Fragile liquidity predicts fast repricing and edge decay.",
            quantification="Spread width + quote refresh rate + top-of-book depth imbalance.",
            data_requirements="Timestamped quotes across books, spread and limit snapshots.",
            validation_method="Edge half-life prediction MAE and execution slippage backtest.",
        ),
        FeatureDomainSpec(
            domain="Line movement velocity",
            feature="Signed odds velocity and acceleration",
            signal_hypothesis="Rapid repricing before lineup confirmation contains information about private signals.",
            quantification="First and second derivative of implied probability over time.",
            data_requirements="Odds time series with synchronized timestamps per sportsbook.",
            validation_method="Lead-lag Granger-style test against closing-line movement and CLV.",
        ),
        FeatureDomainSpec(
            domain="Sharp money detection",
            feature="Consensus-disagreement sharp score",
            signal_hypothesis="When sharp books move first and soft books lag, true information edge is higher.",
            quantification="Weighted lead time of sharp books vs soft books and volume-weighted divergence.",
            data_requirements="Book classification map, odds time series, optional limits/volume proxies.",
            validation_method="Precision-recall on profitable CLV events and false-positive control.",
        ),
        FeatureDomainSpec(
            domain="Closing line divergence",
            feature="Pre-close model/market divergence path",
            signal_hypothesis="Persistent divergence that narrows into close indicates exploitable pre-close inefficiency.",
            quantification="Integral of model minus consensus implied probability until close.",
            data_requirements="Model snapshots by time, consensus odds snapshots, close line.",
            validation_method="Link divergence quantiles to realized CLV and ROI decay curves.",
        ),
        FeatureDomainSpec(
            domain="Volatility clustering",
            feature="Market volatility regime state",
            signal_hypothesis="Volatility clusters imply non-stationary error variance and stake sizing should adapt.",
            quantification="EWMA volatility + change-point probability from rolling implied-prob returns.",
            data_requirements="High-frequency odds snapshots per market and book.",
            validation_method="Hit-rate stability and drawdown comparison across volatility bins.",
        ),
        FeatureDomainSpec(
            domain="Cross-market correlation",
            feature="Joint dislocation score (ML/RL/OU)",
            signal_hypothesis="Multi-market incoherence identifies mispriced books and synthetic arb-like edges.",
            quantification="Distance between observed odds vector and no-arbitrage manifold.",
            data_requirements="Synchronized ML/RL/OU lines and prices for same game/time slice.",
            validation_method="Outlier-driven backtest with transaction-cost adjusted profitability.",
        ),
        FeatureDomainSpec(
            domain="Score state transition probabilities",
            feature="State-conditional run transition residual",
            signal_hypothesis="State transitions capture tactical bunting/bullpen choices not reflected in aggregate stats.",
            quantification="Difference between observed and expected transition matrix under base-out states.",
            data_requirements="Play-by-play state transitions with inning and score context.",
            validation_method="Likelihood improvement in state-space simulator and late-game calibration.",
        ),
        FeatureDomainSpec(
            domain="Psychological pressure proxies",
            feature="Elimination pressure stress index",
            signal_hypothesis="High-pressure contexts shift managerial risk appetite and player performance variance.",
            quantification="Weighted function of elimination probability, rivalry intensity, host crowd factor.",
            data_requirements="Tournament standings, game importance, venue context, historical pressure outcomes.",
            validation_method="Cross-tournament holdout and uplift decomposition by pressure deciles.",
        ),
    ]
    return specs


def domain_coverage(specs: list[FeatureDomainSpec]) -> dict[str, int]:
    coverage = {domain: 0 for domain in MANDATORY_FEATURE_DOMAINS}
    for item in specs:
        if item.domain in coverage:
            coverage[item.domain] += 1
    return coverage
