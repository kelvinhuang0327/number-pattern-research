"""
Market Impact Simulator — Institutional Intelligence Module
=============================================================
Simulates how sportsbook lines will react if our system places a bet,
enabling optimal execution strategy.

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │ INPUTS                                                      │
  │ • Market state: liquidity, regime, books, avg limits        │
  │ • Bet profile:  stake, type, timing                         │
  │ • Historical:   past reactions, book sensitivity, detection │
  └──────────────────────────┬──────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │ Single    │ │ Multi     │ │ Delayed   │
        │ Book Sim  │ │ Book Sim  │ │ Execution │
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │              │              │
              └──────┬───────┘──────────────┘
                     │
            ┌────────▼───────────┐
            │ Monte Carlo Agg.   │
            │ (≥200 simulations) │
            └────────┬───────────┘
                     │
            ┌────────▼──────────────────────────┐
            │ OUTPUT                            │
            │ • expected_slippage               │
            │ • impact_probability              │
            │ • odds_after_bet                  │
            │ • books_that_move: int            │
            │ • recommended_split_count         │
            │ • max_safe_bet_size               │
            │ • execution_risk_score: 0‑100     │
            │ • execution_strategy: str         │
            └───────────────────────────────────┘

Decision rules (applied in decision_engine):
  IF expected_slippage > edge  → NO_BET
  IF execution_risk_score > 70 → reduce bet size by 50 %
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ═══════════════════════════════════════════════════════════════

class ExecutionStrategy(Enum):
    """Recommended execution approach."""
    SINGLE_BOOK = "SINGLE_BOOK"
    MULTI_BOOK_SPLIT = "MULTI_BOOK_SPLIT"
    DELAYED_STAGGER = "DELAYED_STAGGER"
    RANDOMISED_MULTI = "RANDOMISED_MULTI"
    DO_NOT_EXECUTE = "DO_NOT_EXECUTE"


# Default simulation count
DEFAULT_SIM_COUNT = 200

# Bookmaker sensitivity profiles (impact per $1000 bet, in implied prob points)
BOOK_SENSITIVITY: dict[str, float] = {
    "pinnacle": 0.002,      # low sensitivity, high limits
    "bet365": 0.005,
    "draftkings": 0.004,
    "fanduel": 0.004,
    "bovada": 0.006,
    "betmgm": 0.005,
    "generic_sharp": 0.003,
    "generic_soft": 0.008,  # soft books = high sensitivity
    "generic": 0.005,
}

# Sharp detection probability by book tier
SHARP_DETECTION_PROB: dict[str, float] = {
    "sharp": 0.15,       # sharp books tolerate sharp action
    "mid": 0.35,
    "soft": 0.65,        # soft books quickly flag sharps
    "generic": 0.30,
}

# Maximum reasonable implied probability shift per single bet
MAX_SINGLE_BET_SHIFT = 0.05


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class MarketImpactInput:
    """All features required for market impact simulation."""
    # ── Market state ──────────────────────────────────────────
    liquidity_score: float = 0.5          # 0-1 depth proxy
    regime: str = "LIQUID_MARKET"         # from regime_classifier
    n_books: int = 3                      # available sportsbooks
    avg_limit_usd: float = 5000.0         # average max bet per book
    current_odds: float = 2.0             # decimal odds we are targeting
    current_implied_prob: float = 0.0     # auto-computed if 0

    # ── Bet profile ───────────────────────────────────────────
    intended_stake_usd: float = 200.0
    bet_type: str = "ML"                  # ML / RL / OU / F5
    bankroll: float = 10000.0
    hours_to_game: float = 24.0

    # ── Historical reaction database ─────────────────────────
    past_line_reactions: list[float] | None = None   # list of past slippages
    book_tier: str = "generic"            # sharp / mid / soft / generic
    sharp_detection_history: float = 0.0  # 0-1 how often we've been flagged

    # ── Edge context ──────────────────────────────────────────
    edge_pct: float = 0.0                 # raw edge for slippage comparison

    # ── Reproducibility ───────────────────────────────────────
    seed: int | None = None
    n_simulations: int = DEFAULT_SIM_COUNT


@dataclass
class SimulationRun:
    """Single Monte Carlo simulation result."""
    slippage: float = 0.0                 # implied-prob points lost
    odds_after: float = 0.0               # post-bet decimal odds
    books_moved: int = 0
    detected: bool = False                # flagged as sharp?
    fill_pct: float = 1.0                 # fraction of bet actually filled
    strategy_used: ExecutionStrategy = ExecutionStrategy.SINGLE_BOOK


@dataclass
class MarketImpactReport:
    """Aggregated simulation results."""
    # Primary outputs
    expected_slippage: float = 0.0        # mean implied-prob slippage
    impact_probability: float = 0.0       # P(any line movement due to our bet)
    odds_after_bet: float = 0.0           # expected post-execution odds
    books_that_move: int = 0              # expected # of books that react
    recommended_split_count: int = 1      # how many books to split across
    max_safe_bet_size: float = 0.0        # largest stake with slippage < 50 % edge
    execution_risk_score: float = 0.0     # 0-100 composite

    # Best strategy
    execution_strategy: ExecutionStrategy = ExecutionStrategy.SINGLE_BOOK
    strategy_reasoning: str = ""

    # Distribution data
    slippage_p10: float = 0.0
    slippage_p50: float = 0.0
    slippage_p90: float = 0.0

    # Detection risk
    detection_probability: float = 0.0

    # Diagnostics
    n_simulations: int = 0
    details: dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# SIMULATION ENGINES
# ═══════════════════════════════════════════════════════════════

def _book_sensitivity(book_tier: str) -> float:
    """Return impact coefficient for book tier."""
    return BOOK_SENSITIVITY.get(book_tier, BOOK_SENSITIVITY["generic"])


def _detection_prob(book_tier: str, sharp_history: float) -> float:
    """Probability our bet gets flagged as sharp action."""
    base = SHARP_DETECTION_PROB.get(book_tier, SHARP_DETECTION_PROB["generic"])
    # History amplifies detection
    return min(base + 0.3 * sharp_history, 0.95)


def _simulate_single_book(
    stake: float,
    odds: float,
    sensitivity: float,
    avg_limit: float,
    detection_prob: float,
    rng: random.Random,
) -> SimulationRun:
    """
    Simulate placing full stake at a single book.
    """
    implied = 1.0 / max(odds, 1.01)

    # Fill probability: stake / limit
    fill_ratio = stake / max(avg_limit, 100.0)
    if fill_ratio > 1.0:
        fill_pct = 1.0 / fill_ratio  # partial fill
    else:
        fill_pct = 1.0

    actual_stake = stake * fill_pct

    # Impact: proportional to stake × sensitivity
    base_impact = sensitivity * (actual_stake / 1000.0)
    # Add noise
    impact = base_impact * (1.0 + rng.gauss(0, 0.25))
    impact = max(impact, 0.0)
    impact = min(impact, MAX_SINGLE_BET_SHIFT)

    # Detection
    detected = rng.random() < detection_prob
    if detected:
        impact *= 1.5   # flagged → extra line movement

    new_implied = implied + impact
    new_odds = 1.0 / max(new_implied, 0.01) if new_implied > 0 else odds

    return SimulationRun(
        slippage=round(impact, 6),
        odds_after=round(new_odds, 4),
        books_moved=1 if impact > 0.001 else 0,
        detected=detected,
        fill_pct=round(fill_pct, 4),
        strategy_used=ExecutionStrategy.SINGLE_BOOK,
    )


def _simulate_multi_book(
    stake: float,
    odds: float,
    sensitivity: float,
    avg_limit: float,
    detection_prob: float,
    n_books: int,
    rng: random.Random,
) -> SimulationRun:
    """
    Simulate splitting the bet across multiple books.
    Each book receives stake / n_books.
    Cross-book information leakage adds residual impact.
    """
    implied = 1.0 / max(odds, 1.01)
    split = max(n_books, 1)
    per_book = stake / split

    total_impact = 0.0
    books_moved = 0
    any_detected = False

    for _ in range(split):
        per_impact = sensitivity * (per_book / 1000.0) * (1.0 + rng.gauss(0, 0.20))
        per_impact = max(per_impact, 0.0)

        det = rng.random() < (detection_prob * 0.7)  # lower per-book detection
        if det:
            per_impact *= 1.3
            any_detected = True

        if per_impact > 0.001:
            books_moved += 1

        total_impact += per_impact

    # Cross-book leakage: markets are correlated
    leakage = total_impact * 0.15 * rng.uniform(0.5, 1.5)
    total_impact = total_impact * 0.6 + leakage  # splitting reduces ~40 %

    total_impact = min(total_impact, MAX_SINGLE_BET_SHIFT)

    new_implied = implied + total_impact
    new_odds = 1.0 / max(new_implied, 0.01)

    return SimulationRun(
        slippage=round(total_impact, 6),
        odds_after=round(new_odds, 4),
        books_moved=books_moved,
        detected=any_detected,
        fill_pct=1.0,
        strategy_used=ExecutionStrategy.MULTI_BOOK_SPLIT,
    )


def _simulate_delayed(
    stake: float,
    odds: float,
    sensitivity: float,
    avg_limit: float,
    detection_prob: float,
    n_books: int,
    rng: random.Random,
) -> SimulationRun:
    """
    Simulate staggered execution: split across books with random delays.
    Adds timing noise to avoid detection but risks market drift.
    """
    implied = 1.0 / max(odds, 1.01)
    split = max(n_books, 1)
    per_book = stake / split

    total_impact = 0.0
    books_moved = 0
    any_detected = False

    for i in range(split):
        # Each tranche has slightly different sensitivity (market moved)
        time_decay = 1.0 + 0.05 * i  # later tranches face slightly worse odds
        per_impact = sensitivity * (per_book / 1000.0) * time_decay
        per_impact *= (1.0 + rng.gauss(0, 0.15))
        per_impact = max(per_impact, 0.0)

        # Lower detection with delay + randomisation
        det = rng.random() < (detection_prob * 0.45)
        if det:
            per_impact *= 1.2
            any_detected = True

        # Market drift between tranches (can go either way)
        drift = rng.gauss(0, 0.002)
        per_impact += drift

        per_impact = max(per_impact, 0.0)

        if per_impact > 0.001:
            books_moved += 1
        total_impact += per_impact

    total_impact = min(total_impact, MAX_SINGLE_BET_SHIFT)

    new_implied = implied + total_impact
    new_odds = 1.0 / max(new_implied, 0.01)

    return SimulationRun(
        slippage=round(total_impact, 6),
        odds_after=round(new_odds, 4),
        books_moved=books_moved,
        detected=any_detected,
        fill_pct=1.0,
        strategy_used=ExecutionStrategy.DELAYED_STAGGER,
    )


def _simulate_randomised(
    stake: float,
    odds: float,
    sensitivity: float,
    avg_limit: float,
    detection_prob: float,
    n_books: int,
    rng: random.Random,
) -> SimulationRun:
    """
    Simulate randomised multi-book execution: random sizing per book,
    random ordering, random timing offsets.  Best anti-detection strategy.
    """
    implied = 1.0 / max(odds, 1.01)
    split = max(n_books, 1)

    # Random allocation across books (Dirichlet-like)
    raw_weights = [rng.random() for _ in range(split)]
    total_w = sum(raw_weights) or 1.0
    allocations = [stake * w / total_w for w in raw_weights]

    total_impact = 0.0
    books_moved = 0
    any_detected = False

    for alloc in allocations:
        per_impact = sensitivity * (alloc / 1000.0) * (1.0 + rng.gauss(0, 0.18))
        per_impact = max(per_impact, 0.0)

        # Randomisation halves detection probability
        det = rng.random() < (detection_prob * 0.35)
        if det:
            per_impact *= 1.15
            any_detected = True

        if per_impact > 0.001:
            books_moved += 1
        total_impact += per_impact

    # Randomisation reduces cross-book leakage
    leakage = total_impact * 0.10 * rng.uniform(0.3, 1.0)
    total_impact = total_impact * 0.5 + leakage

    total_impact = min(total_impact, MAX_SINGLE_BET_SHIFT)

    new_implied = implied + total_impact
    new_odds = 1.0 / max(new_implied, 0.01)

    return SimulationRun(
        slippage=round(total_impact, 6),
        odds_after=round(new_odds, 4),
        books_moved=books_moved,
        detected=any_detected,
        fill_pct=1.0,
        strategy_used=ExecutionStrategy.RANDOMISED_MULTI,
    )


# ═══════════════════════════════════════════════════════════════
# MONTE CARLO AGGREGATION
# ═══════════════════════════════════════════════════════════════

def _run_strategy_simulations(
    strategy_fn,
    strategy_enum: ExecutionStrategy,
    inp: MarketImpactInput,
    sensitivity: float,
    det_prob: float,
    rng: random.Random,
    n_sims: int,
) -> tuple[list[SimulationRun], float]:
    """Run N simulations for a single strategy, return (runs, mean_slippage)."""
    runs: list[SimulationRun] = []
    for _ in range(n_sims):
        if strategy_enum == ExecutionStrategy.SINGLE_BOOK:
            run = strategy_fn(
                inp.intended_stake_usd, inp.current_odds, sensitivity,
                inp.avg_limit_usd, det_prob, rng,
            )
        else:
            run = strategy_fn(
                inp.intended_stake_usd, inp.current_odds, sensitivity,
                inp.avg_limit_usd, det_prob, inp.n_books, rng,
            )
        runs.append(run)

    mean_slip = statistics.mean(r.slippage for r in runs)
    return runs, mean_slip


def _compute_execution_risk(
    slippage_mean: float,
    slippage_p90: float,
    detection_rate: float,
    fill_rate: float,
    edge_pct: float,
    inp: MarketImpactInput,
) -> float:
    """
    Composite execution risk score (0-100).
      0  = zero risk, execute freely
      100 = extreme risk, do not execute
    """
    # Slippage vs edge ratio (0-35)
    if edge_pct > 0:
        slip_ratio = slippage_mean / edge_pct
    else:
        slip_ratio = 1.0
    slip_score = min(slip_ratio * 35.0, 35.0)

    # P90 tail risk (0-20)
    tail_score = min(slippage_p90 * 400.0, 20.0)

    # Detection risk (0-20)
    det_score = detection_rate * 20.0

    # Fill risk (0-15): low fill = need to re-execute elsewhere
    fill_score = max(0.0, (1.0 - fill_rate) * 15.0)

    # Stake/limit concentration (0-10)
    if inp.avg_limit_usd > 0:
        conc = inp.intended_stake_usd / inp.avg_limit_usd
    else:
        conc = 1.0
    conc_score = min(conc * 10.0, 10.0)

    return min(slip_score + tail_score + det_score + fill_score + conc_score, 100.0)


def _find_max_safe_size(
    odds: float,
    sensitivity: float,
    avg_limit: float,
    edge_pct: float,
    n_books: int,
) -> float:
    """
    Binary search for the largest stake where expected slippage < 50% of edge.
    """
    if edge_pct <= 0:
        return 0.0

    max_slip = edge_pct * 0.5
    # Single-book impact: sensitivity * (stake / 1000)
    # Multi-book reduces by ~50%
    effective_sensitivity = sensitivity * 0.6 if n_books > 1 else sensitivity
    # max_slip = effective_sensitivity * (stake / 1000)
    # ⇒ stake = max_slip * 1000 / effective_sensitivity
    if effective_sensitivity > 0:
        safe = (max_slip * 1000.0) / effective_sensitivity
    else:
        safe = avg_limit * n_books

    # Cap at total available limit
    safe = min(safe, avg_limit * n_books)
    return round(max(safe, 0.0), 2)


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def simulate_market_impact(inp: MarketImpactInput) -> MarketImpactReport:
    """
    Run Monte Carlo simulation of market impact across four execution
    strategies and recommend the optimal approach.

    Args:
        inp: MarketImpactInput with market state, bet profile, and history.

    Returns:
        MarketImpactReport with expected slippage, risk score, and strategy.
    """
    rng = random.Random(inp.seed) if inp.seed is not None else random.Random()

    if inp.current_implied_prob <= 0:
        inp.current_implied_prob = 1.0 / max(inp.current_odds, 1.01)

    sensitivity = _book_sensitivity(inp.book_tier)
    det_prob = _detection_prob(inp.book_tier, inp.sharp_detection_history)

    n_sims = max(inp.n_simulations, 50)
    per_strategy_sims = n_sims // 4

    # ── Run all four strategies ───────────────────────────────
    strategies = [
        (_simulate_single_book, ExecutionStrategy.SINGLE_BOOK),
        (_simulate_multi_book, ExecutionStrategy.MULTI_BOOK_SPLIT),
        (_simulate_delayed, ExecutionStrategy.DELAYED_STAGGER),
        (_simulate_randomised, ExecutionStrategy.RANDOMISED_MULTI),
    ]

    best_strategy = ExecutionStrategy.SINGLE_BOOK
    best_runs: list[SimulationRun] = []
    best_mean_slip = float("inf")
    all_results: dict[str, float] = {}

    for fn, strat_enum in strategies:
        # Skip multi-book strategies if only 1 book
        if strat_enum != ExecutionStrategy.SINGLE_BOOK and inp.n_books < 2:
            continue

        runs, mean_slip = _run_strategy_simulations(
            fn, strat_enum, inp, sensitivity, det_prob, rng, per_strategy_sims,
        )
        all_results[strat_enum.value] = round(mean_slip, 6)

        if mean_slip < best_mean_slip:
            best_mean_slip = mean_slip
            best_strategy = strat_enum
            best_runs = runs

    # If no runs (shouldn't happen), create a default
    if not best_runs:
        return MarketImpactReport(
            execution_strategy=ExecutionStrategy.DO_NOT_EXECUTE,
            execution_risk_score=100.0,
            details={"error": "no simulation runs completed"},
        )

    # ── Aggregate best-strategy results ───────────────────────
    slippages = [r.slippage for r in best_runs]
    sorted_slip = sorted(slippages)
    n = len(sorted_slip)

    mean_slip = statistics.mean(slippages)
    p10 = sorted_slip[max(int(n * 0.10), 0)]
    p50 = sorted_slip[max(int(n * 0.50), 0)]
    p90 = sorted_slip[min(int(n * 0.90), n - 1)]

    mean_odds_after = statistics.mean(r.odds_after for r in best_runs)
    mean_books_moved = statistics.mean(r.books_moved for r in best_runs)
    detection_rate = sum(1 for r in best_runs if r.detected) / max(n, 1)
    fill_rate = statistics.mean(r.fill_pct for r in best_runs)

    impact_prob = sum(1 for s in slippages if s > 0.001) / max(n, 1)

    # ── Execution risk ────────────────────────────────────────
    exec_risk = _compute_execution_risk(
        mean_slip, p90, detection_rate, fill_rate, inp.edge_pct, inp,
    )

    # ── Max safe bet size ─────────────────────────────────────
    max_safe = _find_max_safe_size(
        inp.current_odds, sensitivity, inp.avg_limit_usd,
        inp.edge_pct, inp.n_books,
    )

    # ── Recommended split count ───────────────────────────────
    if best_strategy == ExecutionStrategy.SINGLE_BOOK:
        split_count = 1
    elif inp.n_books >= 4:
        split_count = min(inp.n_books, 4)
    else:
        split_count = inp.n_books

    # ── Override: if execution risk > threshold, recommend DO_NOT_EXECUTE
    if mean_slip > inp.edge_pct and inp.edge_pct > 0:
        best_strategy = ExecutionStrategy.DO_NOT_EXECUTE
        strategy_reason = (
            f"Expected slippage ({mean_slip:.4f}) exceeds edge ({inp.edge_pct:.4f})"
        )
    else:
        strategy_reason = (
            f"{best_strategy.value} has lowest mean slippage "
            f"({best_mean_slip:.5f}) across {per_strategy_sims} sims"
        )

    # ── Build report ──────────────────────────────────────────
    report = MarketImpactReport(
        expected_slippage=round(mean_slip, 6),
        impact_probability=round(impact_prob, 4),
        odds_after_bet=round(mean_odds_after, 4),
        books_that_move=round(mean_books_moved),
        recommended_split_count=split_count,
        max_safe_bet_size=max_safe,
        execution_risk_score=round(exec_risk, 1),
        execution_strategy=best_strategy,
        strategy_reasoning=strategy_reason,
        slippage_p10=round(p10, 6),
        slippage_p50=round(p50, 6),
        slippage_p90=round(p90, 6),
        detection_probability=round(detection_rate, 4),
        n_simulations=n,
        details={
            "strategy_comparison": str(all_results),
            "sensitivity": f"{sensitivity:.4f}",
            "detection_base": f"{det_prob:.2%}",
            "fill_rate": f"{fill_rate:.2%}",
            "max_safe_usd": f"${max_safe:.0f}",
        },
    )
    return report
