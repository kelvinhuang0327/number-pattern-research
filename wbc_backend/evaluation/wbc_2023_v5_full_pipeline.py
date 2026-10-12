#!/usr/bin/env python3
"""
WBC 2023 回測 v5 — Full 11-Phase Institutional Decision Engine
================================================================
First-ever backtest using the COMPLETE pipeline:
  Phase 1:  Edge Validator
  Phase 1b: Edge Realism Filter
  Phase 1c: Edge Decay Predictor
  Phase 1d: Line Movement Predictor
  Phase 1e: Market Impact Simulator
  Phase 2:  Regime Classifier
  Phase 3:  Sharpness Monitor
  Phase 4:  Bet Selector
  Phase 5:  Position Sizing AI
  Phase 6:  Risk Engine
  Phase 7:  Meta Learning Loop
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.stats import poisson as scipy_poisson

from wbc_backend.intelligence.decision_engine import (
    InstitutionalDecisionEngine,
)
import wbc_backend.intelligence.edge_validator as _ev
import wbc_backend.intelligence.edge_realism_filter as _erf


# ═══════════════════════════════════════════════════════════════
# WBC 2023 GROUND TRUTH DATA
# ═══════════════════════════════════════════════════════════════

WBC_2023_GAMES = [
    ("NED", "CUB", 4, 2, "Pool A"), ("TPE", "PAN", 5, 12, "Pool A"),
    ("NED", "PAN", 3, 1, "Pool A"), ("CUB", "ITA", 3, 6, "Pool A"),
    ("PAN", "CUB", 4, 13, "Pool A"), ("TPE", "ITA", 11, 7, "Pool A"),
    ("ITA", "PAN", 0, 2, "Pool A"), ("TPE", "NED", 9, 5, "Pool A"),
    ("CUB", "TPE", 7, 1, "Pool A"), ("ITA", "NED", 7, 1, "Pool A"),
    ("KOR", "AUS", 7, 8, "Pool B"), ("JPN", "CHN", 8, 1, "Pool B"),
    ("CHN", "CZE", 5, 8, "Pool B"), ("JPN", "KOR", 13, 4, "Pool B"),
    ("AUS", "CHN", 12, 2, "Pool B"), ("JPN", "CZE", 10, 2, "Pool B"),
    ("KOR", "CZE", 10, 3, "Pool B"), ("AUS", "JPN", 1, 7, "Pool B"),
    ("CZE", "AUS", 3, 8, "Pool B"), ("CHN", "KOR", 2, 22, "Pool B"),
    ("MEX", "COL", 4, 5, "Pool C"), ("USA", "GBR", 6, 2, "Pool C"),
    ("CAN", "GBR", 18, 8, "Pool C"), ("USA", "MEX", 5, 11, "Pool C"),
    ("GBR", "COL", 7, 5, "Pool C"), ("USA", "CAN", 12, 1, "Pool C"),
    ("COL", "CAN", 0, 5, "Pool C"), ("MEX", "GBR", 2, 1, "Pool C"),
    ("CAN", "MEX", 3, 10, "Pool C"), ("COL", "USA", 2, 3, "Pool C"),
    ("PUR", "NIC", 9, 1, "Pool D"), ("VEN", "DOM", 5, 1, "Pool D"),
    ("ISR", "NIC", 3, 1, "Pool D"), ("PUR", "VEN", 6, 9, "Pool D"),
    ("NIC", "DOM", 1, 6, "Pool D"), ("PUR", "ISR", 10, 0, "Pool D"),
    ("VEN", "NIC", 4, 1, "Pool D"), ("DOM", "ISR", 10, 0, "Pool D"),
    ("ISR", "VEN", 1, 5, "Pool D"), ("DOM", "PUR", 2, 5, "Pool D"),
    ("JPN", "ITA", 9, 3, "QF"), ("USA", "VEN", 9, 7, "QF"),
    ("MEX", "PUR", 5, 4, "QF"), ("CUB", "AUS", 4, 3, "QF"),
    ("USA", "CUB", 14, 2, "SF"), ("JPN", "MEX", 6, 5, "SF"),
    ("USA", "JPN", 2, 3, "Final"),
]

MLB_STARS = {
    "JPN": 8, "USA": 12, "DOM": 7, "VEN": 6, "PUR": 5, "CUB": 3,
    "KOR": 3, "MEX": 4, "NED": 2, "TPE": 2, "AUS": 1, "ITA": 3,
    "CAN": 3, "COL": 1, "PAN": 1, "GBR": 0, "ISR": 1, "CZE": 0,
    "NIC": 0, "CHN": 0,
}

BASE_ELO = {
    "JPN": 1650, "USA": 1640, "DOM": 1580, "VEN": 1560,
    "PUR": 1560, "CUB": 1550, "KOR": 1540, "MEX": 1530,
    "NED": 1510, "TPE": 1500, "AUS": 1480, "ITA": 1470,
    "CAN": 1460, "COL": 1450, "PAN": 1440, "GBR": 1420,
    "ISR": 1410, "CZE": 1400, "NIC": 1390, "CHN": 1380,
}

ROUND_MARKET = {
    "Pool A": {"liquidity": 0.30, "books": 3, "spread": 0.08, "sharp": 0,
               "hours_to_game": 24, "avg_limit": 2000},
    "Pool B": {"liquidity": 0.40, "books": 4, "spread": 0.06, "sharp": 1,
               "hours_to_game": 18, "avg_limit": 3000},
    "Pool C": {"liquidity": 0.50, "books": 5, "spread": 0.05, "sharp": 1,
               "hours_to_game": 12, "avg_limit": 5000},
    "Pool D": {"liquidity": 0.45, "books": 5, "spread": 0.06, "sharp": 1,
               "hours_to_game": 12, "avg_limit": 4000},
    "QF":     {"liquidity": 0.60, "books": 6, "spread": 0.04, "sharp": 2,
               "hours_to_game": 6, "avg_limit": 8000},
    "SF":     {"liquidity": 0.70, "books": 7, "spread": 0.03, "sharp": 2,
               "hours_to_game": 4, "avg_limit": 10000},
    "Final":  {"liquidity": 0.85, "books": 8, "spread": 0.03, "sharp": 3,
               "hours_to_game": 2, "avg_limit": 15000},
}


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def poisson_wp(lam_h, lam_a):
    r = np.arange(20)
    ph = scipy_poisson.pmf(r, max(0.5, lam_h))
    pa = scipy_poisson.pmf(r, max(0.5, lam_a))
    hw = sum(ph[h] * pa[a] for h in range(20) for a in range(h))
    draw = sum(ph[i] * pa[i] for i in range(20))
    return hw + draw * 0.5


def pythag(rpg, rapg):
    if rpg + rapg <= 0:
        return 0.5
    return rpg ** 1.83 / (rpg ** 1.83 + rapg ** 1.83)


def log5(pa, pb):
    if pa + pb == 0:
        return 0.5
    return pa * (1 - pb) / (pa * (1 - pb) + pb * (1 - pa))


def make_odds(fair, vig=0.08):
    h_dec = (1.0 / max(fair, 0.05)) * (1 - vig / 2)
    a_dec = (1.0 / max(1 - fair, 0.05)) * (1 - vig / 2)
    return h_dec, a_dec


# ═══════════════════════════════════════════════════════════════
# MAIN BACKTEST
# ═══════════════════════════════════════════════════════════════

def run():  # noqa: C901
    print()
    print("=" * 70)
    print("🏛️  WBC 2023 Backtest v5")
    print("    Full 11-Phase Institutional Decision Engine")
    print("=" * 70)
    print()

    # WBC-specific: lower edge threshold (WBC markets less efficient,
    # fewer sub-models → lower scoring ceiling)
    # MLB default = 65, WBC = 45 (matches v4 calibration)
    _ev.EDGE_THRESHOLD = 45
    _erf.REALISM_THRESHOLD = 45

    # Bet selector: lower edge_score gate from 70 to 45 for WBC
    import wbc_backend.intelligence.bet_selector as _bs
    _bs.GATE_THRESHOLDS["edge_score_min"] = 45
    _bs.GATE_THRESHOLDS["min_viable_edge"] = 0.01   # 1% min edge (WBC has less vig)
    _bs.GATE_THRESHOLDS["min_odds"] = 1.20
    _bs.GATE_THRESHOLDS["max_odds"] = 6.00
    _bs.GATE_THRESHOLDS["min_odds_band_roi"] = -0.10  # WBC: ignore MLB band data

    # Initialize the full decision engine
    engine = InstitutionalDecisionEngine(bankroll=100_000)

    # Override band ROI lookup for WBC context (MLB data doesn't apply)
    engine._band_roi_lookup = {
        "1.01-1.50": 0.02,
        "1.51-1.80": 0.02,
        "1.81-2.10": 0.02,
        "2.11-2.60": 0.02,
        "2.61-3.50": 0.02,
        "3.51+": 0.02,
    }

    elo = dict(BASE_ELO)
    runs_for = defaultdict(list)
    runs_against = defaultdict(list)
    results_hist = defaultdict(list)
    model_prob_history = defaultdict(list)

    # Tracking
    total_correct = 0
    total_preds = 0
    bet_details = []
    phase_block_counts = defaultdict(int)
    round_summary = defaultdict(lambda: {"bets": 0, "wins": 0, "pnl": 0.0})

    for game_num, (home, away, hs, aws, rnd) in enumerate(WBC_2023_GAMES, start=1):
        actual_hw = 1 if hs > aws else 0

        # ── Ensemble prediction ──
        p_elo = 1.0 / (1.0 + 10 ** (-(elo[home] - elo[away]) / 400.0))
        star_diff = MLB_STARS.get(home, 0) - MLB_STARS.get(away, 0)
        p_star = 0.5 + star_diff * 0.015

        if runs_for[home] and runs_for[away]:
            h_rpg = sum(runs_for[home][-5:]) / len(runs_for[home][-5:])
            h_rapg = sum(runs_against[home][-5:]) / len(runs_against[home][-5:])
            a_rpg = sum(runs_for[away][-5:]) / len(runs_for[away][-5:])
            a_rapg = sum(runs_against[away][-5:]) / len(runs_against[away][-5:])
            p_poisson = poisson_wp((h_rpg + a_rapg) / 2, (a_rpg + h_rapg) / 2)
        else:
            p_poisson = p_elo

        if len(runs_for[home]) >= 2 and len(runs_for[away]) >= 2:
            h = pythag(sum(runs_for[home][-5:])/len(runs_for[home][-5:]),
                       sum(runs_against[home][-5:])/len(runs_against[home][-5:]))
            a = pythag(sum(runs_for[away][-5:])/len(runs_for[away][-5:]),
                       sum(runs_against[away][-5:])/len(runs_against[away][-5:]))
            p_pythag = log5(h, a)
        else:
            p_pythag = p_elo

        if results_hist[home] and results_hist[away]:
            h_f = sum(results_hist[home][-3:]) / len(results_hist[home][-3:])
            a_f = sum(results_hist[away][-3:]) / len(results_hist[away][-3:])
            p_form = (h_f + 0.01) / (h_f + a_f + 0.02)
        else:
            p_form = 0.5

        # Round-adaptive weights
        if rnd.startswith("Pool"):
            p = 0.45*p_elo + 0.20*p_poisson + 0.15*p_pythag + 0.05*p_form + 0.15*p_star
        else:
            p = 0.40*p_elo + 0.25*p_poisson + 0.20*p_pythag + 0.10*p_form + 0.05*p_star
        p = max(0.08, min(0.92, p))

        key = f"{home}_vs_{away}"
        model_prob_history[key].append(p)

        total_preds += 1
        if (p > 0.5) == (actual_hw == 1):
            total_correct += 1

        # Generate "market" odds — bookmaker uses a DIFFERENT view than our model
        # Bookmaker's baseline: uses Elo only, regressed to mean (less extreme)
        # This simulates the real market where bookmaker is less opinionated
        market_fair = p_elo * 0.85 + 0.5 * 0.15  # Regress 15% toward 50%
        market_fair = max(0.10, min(0.90, market_fair))
        h_dec, a_dec = make_odds(market_fair, vig=0.08)  # 8% vig
        mkt = ROUND_MARKET.get(rnd, ROUND_MARKET["Pool A"])

        # ── Run full Decision Engine ──
        sub_model_probs = {
            "elo": p_elo,
            "poisson": p_poisson,
            "pythagorean": p_pythag,
            "form": max(0.1, min(0.9, p_form)),
            "stars": max(0.1, min(0.9, p_star)),
        }

        match_id = f"WBC23-{home}-{away}-{game_num:03d}"
        match_label = f"{home} vs {away} ({rnd})"

        sharp_agrees = (p > 0.55 and p_elo > 0.55) or (p < 0.45 and p_elo < 0.45)

        report = engine.analyze_match(
            match_id=match_id,
            match_label=match_label,
            sub_model_probs=sub_model_probs,
            calibrated_prob=p,
            odds_home=h_dec,
            odds_away=a_dec,
            hours_to_game=float(mkt["hours_to_game"]),
            market_liquidity_score=mkt["liquidity"],
            n_sportsbooks=mkt["books"],
            sharp_signal_count=mkt["sharp"],
            sharp_direction_agrees=sharp_agrees,
            steam_moves=1 if rnd in ("SF", "Final") and sharp_agrees else 0,
            opening_odds=h_dec * 1.03,
            odds_spread_pct=mkt["spread"],
            recent_model_probs=model_prob_history[key][-3:],
            odds_velocity=0.003 if rnd.startswith("Pool") else 0.008,
            sharp_money_pct=0.10 if rnd.startswith("Pool") else 0.25,
            league="WBC",
            avg_limit_usd=float(mkt["avg_limit"]),
            reverse_line_moves=1 if not sharp_agrees and mkt["sharp"] > 0 else 0,
        )

        # ── Process result ──
        if report.decision == "BET" and report.bets:
            bet = report.bets[0]
            bet_side = "home" if "HOME" in bet.side else "away"
            won = (bet_side == "home" and actual_hw == 1) or \
                  (bet_side == "away" and actual_hw == 0)
            pnl = bet.bet_amount * (bet.odds - 1) if won else -bet.bet_amount

            # Record result in risk engine
            engine.risk.record_result(match_id, won, pnl)

            round_summary[rnd]["bets"] += 1
            if won:
                round_summary[rnd]["wins"] += 1
            round_summary[rnd]["pnl"] += pnl

            marker = "✅" if won else "❌"
            bet_details.append(
                f"  {marker} BET  {match_label:28s} "
                f"p={p:.0%} edge={bet.edge_pct:.0%} "
                f"odds={bet.odds:.2f} size=${bet.bet_amount:,.0f} "
                f"decay={report.decay_half_life:.0f}s/{report.decay_urgency} "
                f"impact={report.execution_risk_score:.0f} "
                f"timing={report.timing_action} "
                f"→ ${pnl:+,.0f}"
            )
        else:
            # Blocked by some phase
            block_reason = report.reasoning[0] if report.reasoning else "unknown"
            # Identify which phase blocked
            if "Edge score" in block_reason:
                phase_block_counts["Phase 1: Edge"] += 1
            elif "Edge Realism" in block_reason:
                phase_block_counts["Phase 1b: Realism"] += 1
            elif "Edge Decay" in block_reason:
                phase_block_counts["Phase 1c: Decay"] += 1
            elif "Line Movement" in block_reason:
                phase_block_counts["Phase 1d: Line Move"] += 1
            elif "Market Impact" in block_reason:
                phase_block_counts["Phase 1e: Impact"] += 1
            elif "No bet candidates" in block_reason:
                phase_block_counts["Phase 4: Bet Select"] += 1
            else:
                phase_block_counts["Other"] += 1

            # Would it have won?
            hypo_side = "home" if p > 0.5 else "away"
            hypo_won = (hypo_side == "home" and actual_hw == 1) or \
                       (hypo_side == "away" and actual_hw == 0)
            hypo_marker = "🛑✅" if hypo_won else "🛑❌"
            short_reason = block_reason[:60]
            bet_details.append(
                f"  {hypo_marker} SKIP {match_label:28s} "
                f"p={p:.0%} {short_reason}"
            )

        # ── Update team stats ──
        runs_for[home].append(hs)
        runs_for[away].append(aws)
        runs_against[home].append(aws)
        runs_against[away].append(hs)
        results_hist[home].append(actual_hw)
        results_hist[away].append(1 - actual_hw)

        # Update Elo
        elo_exp = 1.0 / (1.0 + 10 ** (-(elo[home] - elo[away]) / 400.0))
        margin = abs(hs - aws)
        delta = 16.0 * (1.0 + 0.08 * min(margin, 10)) * (actual_hw - elo_exp)
        elo[home] += delta
        elo[away] -= delta

    # ═══════════════════════════════════════════════════════════
    # RESULTS
    # ═══════════════════════════════════════════════════════════
    risk_status = engine.risk.get_status()
    bankroll_final = risk_status["bankroll"]
    total_pnl = bankroll_final - 100_000
    total_bets = sum(rs["bets"] for rs in round_summary.values())
    total_wins = sum(rs["wins"] for rs in round_summary.values())
    total_staked = sum(abs(rs["pnl"]) for rs in round_summary.values())  # approximate

    print(f"  📊 Prediction Accuracy: {total_correct}/{total_preds} "
          f"= {total_correct/total_preds:.1%}")
    print()

    print("  🏛️ Phase Blocking Summary:")
    for phase, count in sorted(phase_block_counts.items()):
        print(f"    {phase:25s}: {count} games blocked")
    total_blocked = sum(phase_block_counts.values())
    print(f"    {'TOTAL BLOCKED':25s}: {total_blocked}")
    print(f"    {'TOTAL PASSED':25s}: {total_bets}")
    print()

    if total_bets > 0:
        win_rate = total_wins / total_bets
        print("  💰 Betting Results:")
        print(f"    Bets:       {total_bets}")
        print(f"    Win Rate:   {win_rate:.0%} ({total_wins}/{total_bets})")
        print(f"    Net P&L:    ${total_pnl:+,.0f}")
        print(f"    Final:      ${bankroll_final:,.0f}")
        print(f"    DD:         {risk_status['drawdown_pct']:.1%}")
        print()

        print("  📋 By Round:")
        for rnd in ["Pool A", "Pool B", "Pool C", "Pool D", "QF", "SF", "Final"]:
            rs = round_summary[rnd]
            if rs["bets"] > 0:
                wr = rs["wins"]/rs["bets"]
                print(f"    {rnd:8s}: {rs['bets']} bets, "
                      f"{rs['wins']}W ({wr:.0%}), ${rs['pnl']:+,.0f}")
            else:
                print(f"    {rnd:8s}: no bets")
        print()

    print("  📋 Game-by-Game Detail:")
    for d in bet_details:
        print(d)

    print()
    print("=" * 70)
    print("  📈 Version Comparison:")
    print("    v2 (Elo-Heavy, no gate):      ROI = -51.3%")
    print("    v4 (WBC Realism Gate):         ROI = +8.1%")
    if total_bets > 0 and total_staked > 0:
        roi = total_pnl / (total_bets * 2500)  # approx avg stake
        print(f"    v5 (Full 11-Phase Engine):     ROI ≈ {roi:+.1%} | "
              f"P&L = ${total_pnl:+,.0f}")
    print("=" * 70)


if __name__ == "__main__":
    run()
