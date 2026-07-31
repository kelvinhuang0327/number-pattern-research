"""
Market Calibration Module — § 四 市場校準模組

Provides:
  market_adjustment()         — adjusts predictions based on market signals
  detect_steam_move()         — detects rapid odds movement
  compute_market_bias_score() — quantifies market mispricing
"""
from __future__ import annotations

import logging

from wbc_backend.config.settings import MarketConfig
from wbc_backend.domain.schemas import OddsLine, OddsTimeSeries

logger = logging.getLogger(__name__)
_MARKET_CODE_MAP = {
    "ML": "MNL",
    "RL": "HDC",
    "OU": "OU",
    "OE": "OE",
    "F5": "FMNL",
    "TT": "TTO",
}


def _market_support_summary(tsl_feed_state: str, matchup_status: dict | None) -> str:
    if tsl_feed_state in {"blocked", "blocked_cached"}:
        return "TSL blocked"
    if tsl_feed_state in {"migrating", "migrating_cached"}:
        return "TSL migrating"
    if tsl_feed_state in {"degraded", "degraded_cached"}:
        return "TSL degraded"
    if tsl_feed_state == "healthy_unlisted":
        return "TSL healthy, matchup unavailable"
    if matchup_status and matchup_status.get("in_snapshot"):
        if not matchup_status.get("is_fresh", True):
            return "TSL listed, stale"
        market_count = int(matchup_status.get("market_count", 0) or 0)
        if market_count > 0:
            return f"TSL listed, {market_count} markets"
        return "TSL listed"
    return "International only"


def _market_support_by_market(tsl_feed_state: str, matchup_status: dict | None) -> dict[str, str]:
    market_codes = {str(code).strip().upper() for code in ((matchup_status or {}).get("market_codes") or [])}
    in_snapshot = bool((matchup_status or {}).get("in_snapshot", False))
    is_fresh = bool((matchup_status or {}).get("is_fresh", True))

    states: dict[str, str] = {}
    for market, code in _MARKET_CODE_MAP.items():
        if tsl_feed_state in {"blocked", "blocked_cached"}:
            states[market] = "blocked"
        elif tsl_feed_state in {"migrating", "migrating_cached"}:
            states[market] = "migrating"
        elif tsl_feed_state in {"degraded", "degraded_cached"}:
            states[market] = "degraded"
        elif not in_snapshot:
            states[market] = "unlisted_matchup"
        elif code not in market_codes:
            states[market] = "unlisted_market"
        elif not is_fresh:
            states[market] = "stale"
        else:
            states[market] = "direct"
    return states


def _assess_tsl_feed_state(
    feed_status: dict | None,
    matchup_status: dict | None,
    odds_lines: list[OddsLine],
) -> tuple[str, float]:
    """Return (state, reliability multiplier) for TSL-derived market trust."""
    if not feed_status:
        return "unknown", 1.0
    has_tsl_lines = any(line.sportsbook == "TSL" for line in odds_lines)
    if feed_status.get("success"):
        if matchup_status and not matchup_status.get("in_snapshot", False) and not has_tsl_lines:
            return "healthy_unlisted", 0.5
        return "healthy", 1.0

    note = str(feed_status.get("note") or feed_status.get("error") or "")
    if "modern_pre_" in note and "403" in note:
        return ("blocked_cached" if has_tsl_lines else "blocked"), (0.35 if has_tsl_lines else 1.0)
    if "legacy_fetch_failed" in note:
        return ("migrating_cached" if has_tsl_lines else "migrating"), (0.55 if has_tsl_lines else 1.0)
    if has_tsl_lines:
        return "degraded_cached", 0.65
    return "degraded", 1.0


def decimal_to_implied_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1.0 / max(odds, 1.01)


def remove_vig(prob1: float, prob2: float) -> tuple[float, float]:
    """Remove vigorish from a two-outcome market."""
    total = prob1 + prob2
    if total <= 0:
        return 0.5, 0.5
    return prob1 / total, prob2 / total


def detect_steam_move(
    time_series: OddsTimeSeries,
    threshold: float = 0.10,
    window_minutes: int = 30,
) -> bool:
    """
    Detect steam move: odds shift > threshold% within window.

    A steam move indicates sharp money moving a line, suggesting
    professional bettors have identified value.
    """
    if len(time_series.snapshots) < 2:
        return False

    # Check most recent snapshots within window
    recent = time_series.snapshots[-10:]  # Last 10 data points
    if len(recent) < 2:
        return False

    first_odds = recent[0].get("odds", 0)
    last_odds = recent[-1].get("odds", 0)

    if first_odds <= 1.01:
        return False

    pct_change = abs(last_odds - first_odds) / first_odds
    is_steam = pct_change >= threshold

    if is_steam:
        direction = "down" if last_odds < first_odds else "up"
        logger.info(
            "STEAM MOVE detected: %s %s %s — odds moved %s %.1f%% (%s → %s)",
            time_series.sportsbook, time_series.market, time_series.side,
            direction, pct_change * 100, first_odds, last_odds,
        )

    return is_steam


def compute_market_bias_score(
    model_prob: float,
    odds_lines: list[OddsLine],
    market_type: str = "ML",
    side: str = "",
) -> float:
    """
    Compute how much the market disagrees with our model.

    market_bias_score > 0 → Market overvalues this side (our edge is on the OTHER side)
    market_bias_score < 0 → Market undervalues this side (our edge is ON this side)

    |score| > 0.10 → significant mispricing
    """
    relevant = [o for o in odds_lines
                if o.market == market_type and (not side or o.side == side)]

    if not relevant:
        return 0.0

    implied_probs = [decimal_to_implied_prob(o.decimal_odds) for o in relevant]

    # Average implied probability across books (after vig removal)
    # For ML, we need to find the complementary side
    if len(implied_probs) >= 2:
        # Use Pinnacle as truth if available
        pinnacle = [o for o in relevant if o.sportsbook.lower() == "pinnacle"]
        if pinnacle:
            avg_implied = decimal_to_implied_prob(pinnacle[0].decimal_odds)
        else:
            avg_implied = sum(implied_probs) / len(implied_probs)
    else:
        avg_implied = implied_probs[0]

    # Remove estimated vig (use average of TSL and international)
    avg_implied *= 0.96  # Approximate vig removal

    bias = avg_implied - model_prob
    return round(bias, 4)


def market_adjustment(
    model_home_prob: float,
    odds_lines: list[OddsLine],
    home_code: str,
    away_code: str,
    config: MarketConfig | None = None,
    odds_history: dict[str, OddsTimeSeries] | None = None,
    feed_status: dict | None = None,
    matchup_status: dict | None = None,
) -> dict:
    """
    Full market calibration:
      1. Compute market-implied probabilities
      2. Detect steam moves
      3. Compute market bias score
      4. Adjust model prediction based on market signals

    Returns dict with:
      - adjusted_home_prob
      - market_bias_score
      - steam_moves_detected
      - market_implied_home
      - market_weight_applied
    """
    config = config or MarketConfig()
    tsl_feed_state, tsl_reliability = _assess_tsl_feed_state(feed_status, matchup_status, odds_lines)
    if tsl_reliability < 1.0:
        odds_lines = [
            line for line in odds_lines
            if line.sportsbook != "TSL"
        ] or odds_lines

    # ── 1. Market implied probabilities ──────────────────
    ml_home_odds = [o for o in odds_lines
                    if o.market == "ML" and o.side == home_code]
    ml_away_odds = [o for o in odds_lines
                    if o.market == "ML" and o.side == away_code]

    if ml_home_odds and ml_away_odds:
        home_implied = decimal_to_implied_prob(ml_home_odds[0].decimal_odds)
        away_implied = decimal_to_implied_prob(ml_away_odds[0].decimal_odds)
        home_fair, away_fair = remove_vig(home_implied, away_implied)
        market_available = True
    else:
        home_fair = model_home_prob
        away_fair = 1.0 - model_home_prob
        market_available = False

    # ── 2. Steam move detection ──────────────────────────
    steam_moves = []
    market_weight = 0.0

    if odds_history:
        for key, ts in odds_history.items():
            is_steam = detect_steam_move(ts, config.steam_move_threshold, config.steam_move_window_minutes)
            if is_steam:
                steam_moves.append(key)
                market_weight += config.steam_weight_boost

    # ── 3. Market bias score ─────────────────────────────
    bias = compute_market_bias_score(model_home_prob, odds_lines, "ML", home_code)

    # ── 4. Adjust model prediction ───────────────────────
    # Base: 85% model, 15% market (increased if steam moves detected)
    base_market_weight = 0.15 + market_weight if market_available else 0.0
    base_market_weight *= tsl_reliability
    base_market_weight = min(0.40, base_market_weight)  # Cap at 40%
    model_weight = 1.0 - base_market_weight

    adjusted_home_prob = model_weight * model_home_prob + base_market_weight * home_fair
    adjusted_home_prob = max(0.05, min(0.95, adjusted_home_prob))

    result = {
        "adjusted_home_prob": round(adjusted_home_prob, 4),
        "adjusted_away_prob": round(1 - adjusted_home_prob, 4),
        "market_bias_score": round(bias, 4),
        "steam_moves_detected": steam_moves,
        "n_steam_moves": len(steam_moves),
        "market_implied_home": round(home_fair, 4),
        "market_implied_away": round(away_fair, 4),
        "model_weight_applied": round(model_weight, 4),
        "market_weight_applied": round(base_market_weight, 4),
        "tsl_feed_state": tsl_feed_state,
        "tsl_feed_reliability": round(tsl_reliability, 4),
        "market_support_summary": _market_support_summary(tsl_feed_state, matchup_status),
        "market_support_by_market": _market_support_by_market(tsl_feed_state, matchup_status),
    }

    logger.info(
        "Market adjustment: model=%.3f → adjusted=%.3f (market=%.3f, bias=%.3f, steams=%d, tsl=%s)",
        model_home_prob, adjusted_home_prob, home_fair, bias, len(steam_moves), tsl_feed_state,
    )

    return result
