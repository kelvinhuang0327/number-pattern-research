"""
Decision Profiles — Phase N: Multi-Profile Decision Mode
=========================================================
Config-driven risk/reward profiles that control:
  - Learning bonus amplification
  - Winning quality amplification
  - Bet sizing (Var-N scale)
  - Portfolio concentration bias

Each profile adjusts behavior WITHOUT redesigning the system.
All existing components (DecisionEngineV2, Learning, WinningQuality)
remain unchanged — profiles only scale their outputs.

2026-04-16 Created — Phase N
"""
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionProfile:
    """Immutable decision profile configuration."""
    name: str
    learning_amp: float        # multiplier for learning bonus in aggregate_scores
    quality_amp: float         # multiplier for winning quality bonus
    var_n_scale: float         # scales Var-N bet count output
    concentration_bias: float  # scales portfolio concentration_top_n
    risk_mode: str             # "conservative" | "balanced" | "aggressive"


# ═══════════════════════════════════════════════════════════════════════════
# Pre-defined profiles
# ═══════════════════════════════════════════════════════════════════════════

PROFILES: Dict[str, DecisionProfile] = {
    'conservative': DecisionProfile(
        name='conservative',
        learning_amp=0.5,
        quality_amp=0.5,
        var_n_scale=0.8,
        concentration_bias=0.8,
        risk_mode='conservative',
    ),
    'balanced': DecisionProfile(
        name='balanced',
        learning_amp=1.0,
        quality_amp=1.0,
        var_n_scale=1.0,
        concentration_bias=1.0,
        risk_mode='balanced',
    ),
    'aggressive': DecisionProfile(
        name='aggressive',
        learning_amp=1.5,
        quality_amp=2.0,
        var_n_scale=1.2,
        concentration_bias=1.3,
        risk_mode='aggressive',
    ),
}

# ═══════════════════════════════════════════════════════════════════════════
# Per-lottery default profile mapping
# ═══════════════════════════════════════════════════════════════════════════

LOTTERY_PROFILE_MAP: Dict[str, str] = {
    'DAILY_539': 'conservative',
    'BIG_LOTTO': 'balanced',
    'POWER_LOTTO': 'aggressive',
}

# ═══════════════════════════════════════════════════════════════════════════
# Profile resolution
# ═══════════════════════════════════════════════════════════════════════════

def get_profile(
    profile_name: Optional[str] = None,
    lottery_type: Optional[str] = None,
) -> DecisionProfile:
    """
    Resolve a decision profile.

    Priority:
      1. Explicit profile_name if provided and valid
      2. Per-lottery default from LOTTERY_PROFILE_MAP
      3. Fallback to 'balanced'

    Always returns a valid profile — never raises.
    """
    if profile_name and profile_name in PROFILES:
        return PROFILES[profile_name]

    if lottery_type and lottery_type in LOTTERY_PROFILE_MAP:
        mapped = LOTTERY_PROFILE_MAP[lottery_type]
        return PROFILES.get(mapped, PROFILES['balanced'])

    return PROFILES['balanced']


def apply_var_n_scale(n_bets: int, profile: DecisionProfile, max_bets: int) -> int:
    """Scale Var-N output by profile, clamped to [1, max_bets]."""
    scaled = round(n_bets * profile.var_n_scale)
    return max(1, min(scaled, max_bets))


def apply_concentration_bias(
    base_top_n: int,
    profile: DecisionProfile,
) -> int:
    """
    Scale concentration pool size by profile bias.

    concentration_bias > 1.0 → larger pool (less concentrated)
    concentration_bias < 1.0 → smaller pool (more concentrated)

    Wait — the spec says aggressive = 1.3 = MORE concentration.
    But concentration_top_n is pool SIZE: smaller = more concentrated.
    So we INVERT: bias > 1.0 → reduce pool (= more concentration).
    """
    # Invert: high bias = smaller pool = more concentrated
    adjusted = round(base_top_n / profile.concentration_bias)
    return max(5, min(adjusted, 25))  # clamp to safe range
