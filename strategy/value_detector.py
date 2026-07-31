"""
Value Bet Detector.

Compares model (true) probability against market-implied probability
for every available betting line, and computes Expected Value.

Supports all Taiwan Sports Lottery (TSL) markets:
  ML (不讓分/獨贏), RL (讓分), OU (大小分), OE (單雙), F5 (前五局), TT (隊伍總分)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from config.settings import EV_STRONG, EV_MEDIUM, EV_SMALL
from data.wbc_data import OddsLine


@dataclass
class ValueBet:
    market: str           # ML / RL / OU / OE / F5 / TT
    side: str             # team code or Over/Under/Odd/Even
    book: str
    decimal_odds: float
    implied_prob: float
    true_prob: float
    ev: float             # expected value as fraction (0.07 = 7%)
    line: float | None
    edge_tier: str        # STRONG / MEDIUM / SMALL / PASS
    kelly_frac: float     # raw Kelly fraction


def implied_probability(decimal_odds: float, margin: float = 0.0) -> float:
    """Convert decimal odds to implied probability (optionally margin-adjusted)."""
    return (1.0 / decimal_odds) - margin


def expected_value(true_prob: float, decimal_odds: float) -> float:
    """EV = p * (odds − 1) − (1 − p)."""
    return true_prob * (decimal_odds - 1.0) - (1.0 - true_prob)


def kelly_fraction(true_prob: float, decimal_odds: float) -> float:
    """Full Kelly: f* = (bp − q) / b  where b = odds−1."""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - true_prob
    f = (b * true_prob - q) / b
    return max(0.0, f)


def _edge_tier(ev: float, market: str, edge_diff: float) -> str:
    # 限制極端機率與市場警告: 
    # 關閉負 ROI 市場作為主推
    if market in ["RL", "OU", "OE"]:
        # Only allow SMALL or MEDIUM at best, never STRONG
        if ev >= EV_MEDIUM:
            return "MEDIUM (Market Restricted)"
        elif ev > 0:
            return "SMALL (Market Restricted)"
        return "PASS"
        
    # 只對可下注候選（正 EV）標記二次驗證，避免負 EV 被誤標為可行動訊號。
    if edge_diff > 0.15 and ev > 0:
        return "SECONDARY_VALIDATION_REQUIRED"

    if ev >= EV_STRONG:
        return "STRONG"
    elif ev >= EV_MEDIUM:
        return "MEDIUM"
    elif ev >= EV_SMALL:
        return "SMALL"
    return "PASS"


def _build_lookup_key(line: OddsLine) -> str:
    """
    Build the key used to look up true probability from the true_probs dict.

    Convention:
        ML  → "ML_JPN"
        RL  → "RL_JPN"
        OU  → "OU_Over" / "OU_Under"
        OE  → "OE_Odd" / "OE_Even"
        F5  → "F5_JPN"
        TT  → "TT_JPN_Over" etc.
    """
    if line.market == "TT":
        return f"TT_{line.side}"
    return f"{line.market}_{line.side}"


def detect(
    odds_lines: List[OddsLine],
    true_probs: dict,
) -> List[ValueBet]:
    """
    Evaluate every odds line and return value-bet objects.

    `true_probs` should use the convention:
        {"ML_JPN": 0.68, "ML_TPE": 0.32,
         "RL_JPN": 0.45, "RL_TPE": 0.55,
         "OU_Over": 0.52, "OU_Under": 0.48,
         "OE_Odd": 0.50, "OE_Even": 0.50,
         "F5_JPN": 0.65, "F5_TPE": 0.35,
         "TT_JPN_Over": 0.55, ...}
    """
    results: List[ValueBet] = []

    for line in odds_lines:
        key = _build_lookup_key(line)
        tp = true_probs.get(key)
        if tp is None:
            continue
        ip = implied_probability(line.price)
        
        # Platt/Isotonic-like edge compression:
        # clamp model edge when deviation from market-implied prob is extreme.
        edge = tp - ip
        if abs(edge) > 0.12:
            # 觸發極端機率限制: 進行強力壓縮
            tp = ip + (0.12 if edge > 0 else -0.12) + (edge * 0.1) # 允許偏移被大幅壓縮
            tp = max(0.01, min(0.99, tp))
            
        ev = expected_value(tp, line.price)
        kf = kelly_fraction(tp, line.price)

        results.append(ValueBet(
            market=line.market,
            side=line.side,
            book=line.book,
            decimal_odds=line.price,
            implied_prob=round(ip, 4),
            true_prob=round(tp, 4),
            ev=round(ev, 4),
            line=line.line,
            edge_tier=_edge_tier(ev, line.market, abs(edge)),
            kelly_frac=round(kf, 4),
        ))

    # Sort by EV descending
    results.sort(key=lambda v: v.ev, reverse=True)
    return results
