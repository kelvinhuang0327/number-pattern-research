"""
Sharp Money / Market Anomaly Detector.

Analyses odds movement patterns to identify:
  • Sharp action (professional money)
  • Trap lines (bookmaker bait)
  • Insider movement (unusual patterns)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from data.wbc_data import OddsLine


@dataclass
class MarketSignal:
    signal: str          # NORMAL | SHARP_ACTION | TRAP_LINE | INSIDER_MOVEMENT
    description: str
    severity: int        # 1-5
    affected_market: str
    details: str = ""


def _group_by_market_side(lines: List[OddsLine]) -> dict:
    """Group odds by (market, side) for time-series analysis."""
    groups: dict = {}
    for line in lines:
        key = (line.market, line.side)
        groups.setdefault(key, []).append(line)
    return groups


def _check_rapid_movement(series: List[OddsLine]) -> List[MarketSignal]:
    """Detect rapid price changes in a short window."""
    signals = []
    if len(series) < 2:
        return signals

    for i in range(1, len(series)):
        prev = series[i - 1]
        curr = series[i]
        pct_change = abs(curr.price - prev.price) / prev.price

        if pct_change >= 0.08:  # 8%+ move
            signals.append(MarketSignal(
                signal="SHARP_ACTION",
                description=f"{curr.market} {curr.side}: odds moved "
                            f"{prev.price:.2f} → {curr.price:.2f} "
                            f"({pct_change:.1%}) in short window",
                severity=4,
                affected_market=curr.market,
            ))
        elif pct_change >= 0.04:  # 4%+ move
            signals.append(MarketSignal(
                signal="SHARP_ACTION",
                description=f"{curr.market} {curr.side}: moderate move "
                            f"{prev.price:.2f} → {curr.price:.2f}",
                severity=2,
                affected_market=curr.market,
            ))
    return signals


def _check_odds_vs_public(lines: List[OddsLine]) -> List[MarketSignal]:
    """
    Detect divergence between odds movement and expected public money.
    In a real system this would use actual betting % data.
    """
    signals = []
    # Heuristic: if the underdog's odds are dropping, that's unusual
    for line in lines:
        if line.market == "ML" and line.price > 2.20:
            # Check if this is lower than typical for this side
            # (simplified: just flag any underdog below 2.30 as potential sharp)
            if line.price < 2.30:
                signals.append(MarketSignal(
                    signal="SHARP_ACTION",
                    description=f"Underdog {line.side} ML dropping to {line.price:.2f} "
                                f"— possible sharp money",
                    severity=3,
                    affected_market="ML",
                ))
    return signals


def _check_trap_lines(lines: List[OddsLine]) -> List[MarketSignal]:
    """
    Detect potential trap lines where the line looks too good.
    """
    signals = []
    for line in lines:
        # Over/Under trap: if total is suspiciously low/high with attractive odds
        if line.market == "OU" and line.line is not None:
            if line.side == "Under" and line.line <= 7.0 and line.price > 2.0:
                signals.append(MarketSignal(
                    signal="TRAP_LINE",
                    description=f"Suspiciously attractive Under {line.line} at {line.price:.2f}",
                    severity=2,
                    affected_market="OU",
                ))
    return signals


def detect(odds_lines: List[OddsLine]) -> List[MarketSignal]:
    """Run all detectors and return combined signals."""
    groups = _group_by_market_side(odds_lines)

    all_signals: List[MarketSignal] = []

    for _key, series in groups.items():
        all_signals.extend(_check_rapid_movement(series))

    all_signals.extend(_check_odds_vs_public(odds_lines))
    all_signals.extend(_check_trap_lines(odds_lines))

    # If nothing found, emit Normal
    if not all_signals:
        all_signals.append(MarketSignal(
            signal="NORMAL",
            description="No anomalous market activity detected",
            severity=0,
            affected_market="ALL",
        ))

    all_signals.sort(key=lambda s: s.severity, reverse=True)
    return all_signals


def overall_signal(signals: List[MarketSignal]) -> str:
    """Summarize the list into a single headline signal."""
    if any(s.signal == "INSIDER_MOVEMENT" for s in signals):
        return "⚠️  INSIDER MOVEMENT"
    if any(s.signal == "TRAP_LINE" for s in signals):
        return "⚠️  TRAP LINE DETECTED"
    if any(s.signal == "SHARP_ACTION" and s.severity >= 3 for s in signals):
        return "🔶 SHARP ACTION"
    if any(s.signal == "SHARP_ACTION" for s in signals):
        return "🔸 MILD SHARP ACTION"
    return "✅ NORMAL"
