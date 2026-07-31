from __future__ import annotations


from wbc_backend.config.settings import StrategyConfig
from wbc_backend.domain.schemas import BetRecommendation, OddsLine
from wbc_backend.odds.analyzer import decimal_to_implied_prob
from wbc_backend.strategy.market_filters import is_odds_in_conf_band, load_high_confidence_odds_bands
from wbc_backend.strategy.market_quality import load_market_quality


def _market_key(odd: OddsLine, home_code: str, away_code: str) -> str:
    if odd.market == "ML":
        return f"ML_{odd.side}"
    if odd.market == "RL":
        return f"RL_{odd.side}"
    if odd.market == "OU":
        return f"OU_{odd.side}"
    raise ValueError(f"unsupported market: {odd.market}")


def _ev(win_prob: float, odds: float) -> float:
    return win_prob * (odds - 1.0) - (1.0 - win_prob)


def _kelly_fraction(win_prob: float, odds: float) -> float:
    b = odds - 1.0
    q = 1.0 - win_prob
    if b <= 0:
        return 0.0
    k = (b * win_prob - q) / b
    return max(0.0, k)


def recommend_top_bets(
    odds_lines: list[OddsLine],
    true_probs: dict[str, float],
    home_code: str,
    away_code: str,
    config: StrategyConfig,
) -> list[BetRecommendation]:
    bets: list[BetRecommendation] = []
    quality = load_market_quality()
    conf_bands = load_high_confidence_odds_bands()

    for odd in odds_lines:
        market_q = quality.get(odd.market, 1.0)
        if market_q <= 0.0:
            continue

        if not is_odds_in_conf_band(odd.market, odd.decimal_odds, conf_bands):
            continue

        key = _market_key(odd, home_code, away_code)
        if key not in true_probs:
            continue

        wp = true_probs[key]
        implied = decimal_to_implied_prob(odd.decimal_odds)
        edge = wp - implied
        raw_ev = _ev(wp, odd.decimal_odds)
        weighted_ev = raw_ev * market_q

        if edge < config.edge_threshold:
            continue
        if weighted_ev < config.min_ev:
            continue

        base_kelly = _kelly_fraction(wp, odd.decimal_odds)
        stake_fraction = min(config.max_stake_fraction, base_kelly * config.fractional_kelly)
        if stake_fraction <= 0:
            continue

        bets.append(
            BetRecommendation(
                market=odd.market,
                side=odd.side,
                line=odd.line,
                sportsbook=odd.sportsbook,
                source_type=odd.source_type,
                win_probability=round(wp, 4),
                implied_probability=round(implied, 4),
                ev=round(weighted_ev, 4),
                edge=round(edge, 4),
                kelly_fraction=round(base_kelly, 4),
                stake_fraction=round(stake_fraction, 4),
                reason=(
                    f"edge={edge:.3f}; EV={raw_ev:.3f}; quality={market_q:.2f}; "
                    f"kelly={base_kelly:.3f}; fractional={config.fractional_kelly:.2f}"
                ),
            )
        )

    bets.sort(
        key=lambda b: (
            b.ev,
            b.stake_fraction,
            config.market_priority.get(b.market, 0),
            1 if b.source_type == "international" else 0,
        ),
        reverse=True,
    )
    return bets[: config.max_recommendations]
