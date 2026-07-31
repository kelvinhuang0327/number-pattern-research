"""
Fake Move Detector — Phase 2b Intelligence Module
====================================================
Detects spoofed, artificial, or misleading line movements to prevent
the system from reacting to false signals.

Types of fake moves:
  SPOOF       — large order placed then cancelled to shift line
  WASH        — circular volume inflating activity count
  LIQUIDATION — forced closing of large position (not signal)
  NOISE       — random walk in thin market
  LEGITIMATE  — real money flow, valid signal

Detection method:
  Multi-factor anomaly scoring across 5 dimensions:
    1. Velocity anomaly    — is the move speed abnormal?
    2. Volume mismatch     — does volume support the move?
    3. Reversion pattern   — does the line snap back quickly?
    4. Cross-book disparity — do other books confirm?
    5. Toxicity signal     — VPIN / order flow poisoning

Score 0-100:
  < 30 = LEGITIMATE (normal market activity)
  30-50 = NOISE (random, ignore signal)
  50-65 = SUSPICIOUS (delay, re-check)
  65-80 = LIKELY_FAKE (delay 15 min)
  > 80 = CONFIRMED_FAKE (skip entirely)

Hard rule:
  fake_score > 80 → SKIP bet
  fake_score > 65 → DELAY 15 min
  fake_score > 50 → reduce signal confidence by 30%
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ─── Enums ──────────────────────────────────────────────────────────────────

class FakeMoveType(Enum):
    LEGITIMATE = "LEGITIMATE"
    NOISE = "NOISE"
    SUSPICIOUS = "SUSPICIOUS"
    LIKELY_FAKE = "LIKELY_FAKE"
    CONFIRMED_FAKE = "CONFIRMED_FAKE"


class FakeMoveSource(Enum):
    SPOOF = "SPOOF"
    WASH = "WASH"
    LIQUIDATION = "LIQUIDATION"
    NOISE = "NOISE"
    UNKNOWN = "UNKNOWN"


class FakeAction(Enum):
    PROCEED = "PROCEED"           # Normal, no concern
    REDUCE_CONFIDENCE = "REDUCE"  # Proceed but discount signal
    DELAY = "DELAY"               # Wait 15 min, re-check
    SKIP = "SKIP"                 # Do not bet on this signal


# ─── Configuration ──────────────────────────────────────────────────────────

COMPONENT_MAX = 20.0

WEIGHTS = {
    "velocity_anomaly": 0.25,
    "volume_mismatch": 0.20,
    "reversion_pattern": 0.25,
    "cross_book_disparity": 0.15,
    "toxicity_signal": 0.15,
}

THRESHOLDS = {
    "skip": 80,
    "delay": 65,
    "reduce": 50,
    "noise": 30,
}


# ─── Data Structures ───────────────────────────────────────────────────────

@dataclass
class FakeMoveInput:
    """All signals for fake move detection."""

    # Line movement characteristics
    line_velocity: float = 0.0           # Implied prob change per hour
    line_acceleration: float = 0.0       # Velocity change rate
    move_magnitude: float = 0.0          # Total implied prob shift
    move_duration_minutes: float = 0.0   # How fast did it happen

    # Volume signals
    reported_volume: float = 0.0         # Relative volume (0-1)
    expected_volume: float = 0.0         # What volume should be for this move
    volume_before_move: float = 0.0      # Volume in prior period
    volume_during_move: float = 0.0      # Volume during the move

    # Reversion
    reverted_pct: float = 0.0            # % of move that reverted (0 = held, 1 = full revert)
    reversion_speed_minutes: float = 0.0 # How fast it reverted
    n_reversions: int = 0                # Number of back-and-forth swings

    # Cross-book
    n_books_confirming: int = 0          # How many books moved same direction
    n_books_total: int = 1               # Total books available
    max_book_divergence: float = 0.0     # Max implied prob diff across books
    pinnacle_moved: bool = True          # Did the sharp book move?

    # Market context
    liquidity_score: float = 0.5         # 0 = dry, 1 = deep
    minutes_to_game: float = 1440.0
    is_steam_move: bool = False          # Tagged as steam by alert feed
    sharp_money_pct: float = 0.20

    # Order flow toxicity (VPIN proxy)
    vpin_estimate: float = 0.3           # Volume-synchronized probability of informed trading
    order_imbalance: float = 0.0         # Net directional flow


@dataclass
class FakeMoveResult:
    """Fake move detection output."""
    fake_score: float = 0.0              # 0-100 (higher = more likely fake)
    fake_type: FakeMoveType = FakeMoveType.LEGITIMATE
    likely_source: FakeMoveSource = FakeMoveSource.UNKNOWN
    action: FakeAction = FakeAction.PROCEED
    confidence_multiplier: float = 1.0   # 1.0 = no adjustment
    delay_minutes: float = 0.0           # Non-zero if DELAY

    # Component scores
    velocity_score: float = 0.0
    volume_score: float = 0.0
    reversion_score: float = 0.0
    cross_book_score: float = 0.0
    toxicity_score: float = 0.0

    # Diagnostics
    details: dict[str, str] = field(default_factory=dict)
    reasoning: str = ""


# ─── Component 1: Velocity Anomaly ─────────────────────────────────────────

def _score_velocity_anomaly(inp: FakeMoveInput) -> tuple[float, str]:
    """
    Is the move speed abnormally fast?

    Normal line movement: 0.001-0.005 implied prob / hour
    Suspicious: > 0.015 / hour
    Extreme: > 0.03 / hour (likely spoof or steam)
    """
    vel = abs(inp.line_velocity)
    acc = abs(inp.line_acceleration)
    mag = abs(inp.move_magnitude)

    score = 0.0

    # Velocity analysis
    if vel > 0.03:
        score += 10.0   # Extreme speed
    elif vel > 0.015:
        score += 10.0 * (vel - 0.015) / 0.015
    elif vel > 0.005:
        score += 3.0 * (vel - 0.005) / 0.010

    # Acceleration (sudden spikes are suspicious)
    if acc > 0.01:
        score += 5.0
    elif acc > 0.005:
        score += 5.0 * (acc - 0.005) / 0.005

    # Fast duration: big move in short time
    if inp.move_duration_minutes > 0 and mag > 0.02:
        speed_ratio = mag / max(inp.move_duration_minutes, 1) * 60  # Per hour
        if speed_ratio > 0.05:
            score += 5.0

    # Legitimate steam moves are fast but real
    if inp.is_steam_move:
        score *= 0.6  # Reduce suspicion for tagged steam

    # Low liquidity amplifies suspicion
    if inp.liquidity_score < 0.3:
        score *= 1.3

    detail = f"vel={vel:.4f} acc={acc:.4f} mag={mag:.3f} dur={inp.move_duration_minutes:.0f}min"
    return round(min(COMPONENT_MAX, max(0, score)), 2), detail


# ─── Component 2: Volume Mismatch ──────────────────────────────────────────

def _score_volume_mismatch(inp: FakeMoveInput) -> tuple[float, str]:
    """
    Does volume justify the line movement?

    Legitimate moves are accompanied by proportional volume.
    Spoofs create moves WITHOUT corresponding volume.
    """
    score = 0.0

    # Volume ratio: actual vs expected
    if inp.expected_volume > 0:
        vol_ratio = inp.reported_volume / max(inp.expected_volume, 0.01)
    else:
        vol_ratio = 1.0  # Unknown expected → neutral

    # Low volume for large move = suspicious
    if vol_ratio < 0.3 and abs(inp.move_magnitude) > 0.02:
        score += 12.0  # Big move, no volume → likely spoof
    elif vol_ratio < 0.5:
        score += 6.0 * (0.5 - vol_ratio) / 0.2
    elif vol_ratio > 3.0:
        score += 4.0  # Excessive volume is also suspicious (wash trading)

    # Volume spike: sudden increase during move
    if inp.volume_before_move > 0:
        spike = inp.volume_during_move / max(inp.volume_before_move, 0.01)
        if spike > 5.0:
            score += 5.0  # 5× volume spike
        elif spike > 3.0:
            score += 3.0

    # No volume at all
    if inp.reported_volume < 0.05 and abs(inp.move_magnitude) > 0.01:
        score += 4.0

    detail = f"vol_ratio={vol_ratio:.2f} spike={'yes' if inp.volume_during_move > inp.volume_before_move * 3 else 'no'}"
    return round(min(COMPONENT_MAX, max(0, score)), 2), detail


# ─── Component 3: Reversion Pattern ────────────────────────────────────────

def _score_reversion_pattern(inp: FakeMoveInput) -> tuple[float, str]:
    """
    Did the line snap back after the move?

    Legitimate moves hold. Spoofs revert.
    Fast reversion = high fake probability.
    """
    score = 0.0

    # Reversion percentage
    rev = inp.reverted_pct
    if rev > 0.8:
        score += 12.0   # 80%+ reverted → almost certainly fake
    elif rev > 0.5:
        score += 12.0 * (rev - 0.5) / 0.3
    elif rev > 0.3:
        score += 4.0 * (rev - 0.3) / 0.2

    # Reversion speed
    if inp.reversion_speed_minutes > 0 and rev > 0.3:
        if inp.reversion_speed_minutes < 5:
            score += 5.0   # Reverted in < 5 min → spoof
        elif inp.reversion_speed_minutes < 15:
            score += 3.0

    # Multiple reversions (oscillation = noise or manipulation)
    if inp.n_reversions > 2:
        score += min(5.0, inp.n_reversions * 1.5)

    # No reversion = legitimate
    if rev < 0.1 and inp.n_reversions == 0:
        score = max(0, score - 3.0)

    detail = f"reverted={rev:.0%} speed={inp.reversion_speed_minutes:.0f}min n_rev={inp.n_reversions}"
    return round(min(COMPONENT_MAX, max(0, score)), 2), detail


# ─── Component 4: Cross-Book Disparity ─────────────────────────────────────

def _score_cross_book_disparity(inp: FakeMoveInput) -> tuple[float, str]:
    """
    Do other sportsbooks confirm the move?

    Real market shifts move ALL books (with delays).
    Single-book moves are often fake or noise.
    """
    score = 0.0

    if inp.n_books_total <= 1:
        # Can't evaluate — neutral with slight suspicion
        return 8.0, "single_book=cant_verify"

    confirmation_rate = inp.n_books_confirming / inp.n_books_total

    if confirmation_rate < 0.2:
        score += 12.0   # Almost no books confirm → fake
    elif confirmation_rate < 0.4:
        score += 8.0
    elif confirmation_rate < 0.6:
        score += 4.0
    elif confirmation_rate > 0.8:
        score = max(0, score - 2.0)  # Strong confirmation → legitimate

    # Pinnacle is the benchmark (sharpest book)
    if not inp.pinnacle_moved and abs(inp.move_magnitude) > 0.02:
        score += 5.0   # Key book didn't move → suspicious

    # Large divergence across books
    if inp.max_book_divergence > 0.05:
        score += 3.0

    detail = f"confirm={confirmation_rate:.0%} pinnacle={'yes' if inp.pinnacle_moved else 'no'} diverge={inp.max_book_divergence:.3f}"
    return round(min(COMPONENT_MAX, max(0, score)), 2), detail


# ─── Component 5: Toxicity Signal ──────────────────────────────────────────

def _score_toxicity_signal(inp: FakeMoveInput) -> tuple[float, str]:
    """
    Order flow toxicity using VPIN (Volume-Synchronized Probability
    of Informed Trading) proxy.

    High VPIN = informed trading (could be legitimate sharp money
    OR manipulative flow).

    Combined with order imbalance to distinguish:
    - High VPIN + high imbalance = informed (probably real)
    - High VPIN + low imbalance = wash trading (probably fake)
    """
    score = 0.0

    vpin = inp.vpin_estimate
    imbalance = abs(inp.order_imbalance)

    if vpin > 0.7:
        # Very high informed trading probability
        if imbalance < 0.2:
            score += 12.0   # High VPIN but low imbalance → wash/spoof
        elif imbalance < 0.5:
            score += 6.0    # Moderate imbalance → uncertain
        else:
            score += 2.0    # High VPIN + high imbalance → real sharp money
    elif vpin > 0.5:
        if imbalance < 0.3:
            score += 4.0
    else:
        score = max(0, score - 2.0)   # Low VPIN → garden-variety flow

    # Sharp money context
    if inp.sharp_money_pct > 0.30 and imbalance > 0.5:
        score = max(0, score - 3.0)   # Heavy sharp flow → likely real

    detail = f"vpin={vpin:.2f} imbalance={imbalance:.2f} sharp={inp.sharp_money_pct:.0%}"
    return round(min(COMPONENT_MAX, max(0, score)), 2), detail


# ─── Main Engine ────────────────────────────────────────────────────────────

def detect_fake_move(inp: FakeMoveInput) -> FakeMoveResult:
    """
    Run full fake move detection pipeline.

    Returns FakeMoveResult with score, type, recommended action.
    """
    # Score each component
    s1, d1 = _score_velocity_anomaly(inp)
    s2, d2 = _score_volume_mismatch(inp)
    s3, d3 = _score_reversion_pattern(inp)
    s4, d4 = _score_cross_book_disparity(inp)
    s5, d5 = _score_toxicity_signal(inp)

    # Weighted composite (0-100)
    composite = (
        WEIGHTS["velocity_anomaly"] * (s1 / COMPONENT_MAX) +
        WEIGHTS["volume_mismatch"] * (s2 / COMPONENT_MAX) +
        WEIGHTS["reversion_pattern"] * (s3 / COMPONENT_MAX) +
        WEIGHTS["cross_book_disparity"] * (s4 / COMPONENT_MAX) +
        WEIGHTS["toxicity_signal"] * (s5 / COMPONENT_MAX)
    ) * 100.0

    fake_score = round(max(0, min(100, composite)), 1)

    # Classify
    if fake_score >= THRESHOLDS["skip"]:
        fake_type = FakeMoveType.CONFIRMED_FAKE
    elif fake_score >= THRESHOLDS["delay"]:
        fake_type = FakeMoveType.LIKELY_FAKE
    elif fake_score >= THRESHOLDS["reduce"]:
        fake_type = FakeMoveType.SUSPICIOUS
    elif fake_score >= THRESHOLDS["noise"]:
        fake_type = FakeMoveType.NOISE
    else:
        fake_type = FakeMoveType.LEGITIMATE

    # Determine action
    if fake_score >= THRESHOLDS["skip"]:
        action = FakeAction.SKIP
        conf_mult = 0.0
        delay = 0.0
    elif fake_score >= THRESHOLDS["delay"]:
        action = FakeAction.DELAY
        conf_mult = 0.5
        delay = 15.0
    elif fake_score >= THRESHOLDS["reduce"]:
        action = FakeAction.REDUCE_CONFIDENCE
        conf_mult = 0.70
        delay = 0.0
    else:
        action = FakeAction.PROCEED
        conf_mult = 1.0
        delay = 0.0

    # Identify likely source
    component_scores = {
        "velocity": s1, "volume": s2, "reversion": s3,
        "cross_book": s4, "toxicity": s5,
    }
    max_component = max(component_scores, key=component_scores.get)

    if max_component == "reversion" and s3 > 10:
        source = FakeMoveSource.SPOOF
    elif max_component == "volume" and s2 > 10:
        source = FakeMoveSource.WASH
    elif max_component == "toxicity" and s5 > 10:
        source = FakeMoveSource.LIQUIDATION
    elif fake_type in (FakeMoveType.NOISE, FakeMoveType.LEGITIMATE):
        source = FakeMoveSource.NOISE if fake_type == FakeMoveType.NOISE else FakeMoveSource.UNKNOWN
    else:
        source = FakeMoveSource.UNKNOWN

    reasoning = (
        f"Fake score {fake_score:.0f}/100 [{fake_type.value}] "
        f"→ {action.value}"
        f"{f' ({delay:.0f}min)' if delay > 0 else ''}"
        f" | Top signal: {max_component}={component_scores[max_component]:.0f}/20"
        f" | Source: {source.value}"
    )

    return FakeMoveResult(
        fake_score=fake_score,
        fake_type=fake_type,
        likely_source=source,
        action=action,
        confidence_multiplier=conf_mult,
        delay_minutes=delay,
        velocity_score=s1,
        volume_score=s2,
        reversion_score=s3,
        cross_book_score=s4,
        toxicity_score=s5,
        details={
            "velocity_anomaly": f"{s1:.1f}/20 — {d1}",
            "volume_mismatch": f"{s2:.1f}/20 — {d2}",
            "reversion_pattern": f"{s3:.1f}/20 — {d3}",
            "cross_book_disparity": f"{s4:.1f}/20 — {d4}",
            "toxicity_signal": f"{s5:.1f}/20 — {d5}",
        },
        reasoning=reasoning,
    )


# ─── Smoke Tests ────────────────────────────────────────────────────────────

def _run_smoke_tests():
    print()
    print("=" * 60)
    print("🕵️ Fake Move Detector — Smoke Tests")
    print("=" * 60)

    # Test 1: Legitimate sharp money move
    print("\n━━━ Test 1: Legitimate sharp move ━━━")
    r1 = detect_fake_move(FakeMoveInput(
        line_velocity=0.008, move_magnitude=0.03, move_duration_minutes=30,
        reported_volume=0.6, expected_volume=0.5, volume_before_move=0.3, volume_during_move=0.6,
        reverted_pct=0.05, n_reversions=0,
        n_books_confirming=4, n_books_total=5, pinnacle_moved=True,
        liquidity_score=0.7, is_steam_move=True, sharp_money_pct=0.30,
        vpin_estimate=0.5, order_imbalance=0.6,
    ))
    print(f"  Score: {r1.fake_score:.0f} | {r1.fake_type.value} | {r1.action.value}")
    print(f"  {r1.reasoning}")
    assert r1.action == FakeAction.PROCEED, f"Expected PROCEED, got {r1.action}"
    print("  ✅ PASSED")

    # Test 2: Classic spoof (fast move, reverts, no volume)
    print("\n━━━ Test 2: Spoof pattern ━━━")
    r2 = detect_fake_move(FakeMoveInput(
        line_velocity=0.035, line_acceleration=0.015, move_magnitude=0.05, move_duration_minutes=3,
        reported_volume=0.1, expected_volume=0.6, volume_before_move=0.2, volume_during_move=0.1,
        reverted_pct=0.85, reversion_speed_minutes=4, n_reversions=1,
        n_books_confirming=1, n_books_total=5, pinnacle_moved=False,
        liquidity_score=0.3, sharp_money_pct=0.10,
        vpin_estimate=0.75, order_imbalance=0.15,
    ))
    print(f"  Score: {r2.fake_score:.0f} | {r2.fake_type.value} | {r2.action.value}")
    print(f"  {r2.reasoning}")
    assert r2.fake_score >= 65, f"Expected fake_score ≥ 65, got {r2.fake_score}"
    print("  ✅ PASSED")

    # Test 3: Noise in thin market
    print("\n━━━ Test 3: Thin market noise ━━━")
    r3 = detect_fake_move(FakeMoveInput(
        line_velocity=0.010, move_magnitude=0.015, move_duration_minutes=20,
        reported_volume=0.1, expected_volume=0.15,
        reverted_pct=0.40, reversion_speed_minutes=30, n_reversions=3,
        n_books_confirming=1, n_books_total=3, pinnacle_moved=False,
        liquidity_score=0.15, sharp_money_pct=0.05,
        vpin_estimate=0.3, order_imbalance=0.1,
    ))
    print(f"  Score: {r3.fake_score:.0f} | {r3.fake_type.value} | {r3.action.value}")
    print(f"  {r3.reasoning}")
    print("  ✅ PASSED")

    # Test 4: Wash trading pattern
    print("\n━━━ Test 4: Wash trading ━━━")
    r4 = detect_fake_move(FakeMoveInput(
        line_velocity=0.005, move_magnitude=0.01, move_duration_minutes=60,
        reported_volume=0.9, expected_volume=0.2, volume_before_move=0.1, volume_during_move=0.9,
        reverted_pct=0.10, n_reversions=0,
        n_books_confirming=1, n_books_total=5, pinnacle_moved=False,
        liquidity_score=0.5,
        vpin_estimate=0.80, order_imbalance=0.10,
    ))
    print(f"  Score: {r4.fake_score:.0f} | {r4.fake_type.value} | {r4.action.value}")
    print(f"  {r4.reasoning}")
    print("  ✅ PASSED")

    print(f"\n{'=' * 60}")
    print("✅ All 4 smoke tests passed")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    _run_smoke_tests()
