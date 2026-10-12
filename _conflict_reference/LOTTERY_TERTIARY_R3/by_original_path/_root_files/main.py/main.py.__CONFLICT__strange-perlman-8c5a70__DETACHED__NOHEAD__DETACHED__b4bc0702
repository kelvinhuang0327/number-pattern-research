#!/usr/bin/env python3
"""
WBC Quantitative Betting Engine — Main Orchestrator.

Usage:
    python main.py                     # Latest WBC match (JPN vs TPE)
    python main.py --game=C01          # Specific game (A01–A10, B01–B10, C01–C10, D01–D10)
    python main.py --all               # Run all 40 pool games
    python main.py --all=C             # Run all Pool C games only
    python main.py --list              # List all available games
    python main.py --json              # Also dump raw JSON details
"""
from __future__ import annotations
import sys
import json
import math

# ── Data ──────────────────────────────────────────────────
from data.wbc_data import fetch_latest_wbc_match
from data.wbc_pool_a import fetch_wbc_match_a, list_wbc_matches_a
from data.wbc_pool_b import fetch_wbc_match_b, list_wbc_matches_b
from data.wbc_pool_c import fetch_wbc_match, list_wbc_matches  # Pool C keeps original names
from data.wbc_pool_d import fetch_wbc_match_d, list_wbc_matches_d

# ── Models ────────────────────────────────────────────────
from models.ensemble import predict as ensemble_predict

# ── WBC Adjustments ──────────────────────────────────────
from wbc.adjustments import adjusted_probabilities, adjusted_total_runs

# ── Strategy ──────────────────────────────────────────────
from strategy.value_detector import detect as detect_value
from strategy.kelly_criterion import BankrollState, build_portfolio
from strategy.sharp_detector import detect as detect_sharp, overall_signal
from strategy.risk_control import evaluate as evaluate_risk

# ── Learning ─────────────────────────────────────────────
from learning.self_learning import get_recent_errors

# ── Report ───────────────────────────────────────────────
from report.formatter import build_report
from wbc_backend.config.settings import AppConfig
from wbc_backend.data.wbc_verification import verify_game_artifact


def _p_over(mu: float, line: float, sigma: float = 1.8) -> float:
    """P(X > line) via Normal approx."""
    z = (line + 0.5 - mu) / sigma
    return 0.5 * (1.0 - math.erf(z / math.sqrt(2.0)))


def _odd_even_probs(lam_a: float, lam_h: float) -> tuple[float, float]:
    """
    Estimate P(total is odd) and P(total is even) via Poisson.
    For independent Poisson(λ₁) + Poisson(λ₂), the parity follows:
       P(even) = 0.5 * (1 + exp(-2(λ₁+λ₂)))
    """
    total_lam = lam_a + lam_h
    p_even = 0.5 * (1.0 + math.exp(-2.0 * total_lam))
    p_odd = 1.0 - p_even
    return p_odd, p_even


def _fetch_by_game_id(game_id: str):
    """Route game_id to the correct pool fetch function."""
    prefix = game_id[0].upper()
    if prefix == "A":
        return fetch_wbc_match_a(game_id)
    elif prefix == "B":
        return fetch_wbc_match_b(game_id)
    elif prefix == "C":
        return fetch_wbc_match(game_id)
    elif prefix == "D":
        return fetch_wbc_match_d(game_id)
    else:
        raise ValueError(
            f"Unknown pool prefix '{prefix}' in game_id '{game_id}'. "
            "Use A01–A10, B01–B10, C01–C10, or D01–D10."
        )


def _list_all_matches() -> dict[str, list]:
    """Return all matches grouped by pool."""
    return {
        "Pool A (San Juan)": list_wbc_matches_a(),
        "Pool B (Houston)": list_wbc_matches_b(),
        "Pool C (Tokyo)": list_wbc_matches(),
        "Pool D (Miami)": list_wbc_matches_d(),
    }


def main(dump_json: bool = False, game_id: str | None = None):
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. FETCH DATA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if game_id:
        match = _fetch_by_game_id(game_id)
    else:
        match = fetch_latest_wbc_match()

    verification = verify_game_artifact(
        game_id=game_id or match.away.code + "_AT_" + match.home.code,
        expected_home=match.home.code,
        expected_away=match.away.code,
        expected_game_time=match.game_time,
        expected_home_sp=match.home_sp.name,
        expected_away_sp=match.away_sp.name,
        expected_home_lineup=[player.name for player in match.home_lineup],
        expected_away_lineup=[player.name for player in match.away_lineup],
        data_source=match.data_source,
        snapshot_path=AppConfig().sources.wbc_authoritative_snapshot_json,
    )
    verification.ensure_verified()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. ENSEMBLE PREDICTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    raw_away, raw_home, ensemble_details = ensemble_predict(match)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. WBC ADJUSTMENTS (round-specific)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    away_wp, home_wp, wbc_details = adjusted_probabilities(
        match, raw_away, raw_home,
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. BUILD TRUE-PROB MAP FOR ALL MARKETS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    away_code = match.away.code
    home_code = match.home.code

    # Poisson / MC details for totals
    poi_detail = ensemble_details["sub_models"].get("poisson", {})
    mc_detail  = ensemble_details["sub_models"].get("monte_carlo", {})

    lam_a = poi_detail.get("lambda_away", match.away.runs_per_game)
    lam_h = poi_detail.get("lambda_home", match.home.runs_per_game)

    # WBC-adjusted lambdas
    lam_a_adj, lam_h_adj = adjusted_total_runs(
        lam_a, lam_h, round_name=match.round_name,
    )
    total_mu = mc_detail.get("total_runs_avg", lam_a_adj + lam_h_adj)

    # O/U probs from MC distribution (or fallback to Normal approx)
    total_dist = mc_detail.get("total_runs_distribution", {})
    # Extract OU line from odds (dynamic, not hardcoded)
    _ou_lines = [o.line for o in match.odds if o.market == "OU" and o.line is not None]
    ou_line = _ou_lines[0] if _ou_lines else 7.5
    if total_dist:
        over_ou = sum(v for k, v in total_dist.items() if int(k) > ou_line)
    else:
        over_ou = _p_over(total_mu, ou_line)
    under_ou = 1.0 - over_ou

    # Run-line: P(away wins by 2+) ≈ away_wp * 0.55 (heuristic from MC)
    spread_line = 2.5  # TSL RL = -2.5
    rl_away_cover = away_wp * 0.40  # harder to cover -2.5
    rl_home_cover = 1.0 - rl_away_cover

    # F5: first 5 innings — SP dominates, use SP-weighted probability
    f5_away = away_wp * 1.03
    f5_home = 1.0 - f5_away

    # Team totals
    away_runs_mu = mc_detail.get("away_avg_runs", lam_a_adj)
    home_runs_mu = mc_detail.get("home_avg_runs", lam_h_adj)

    # Extract TT lines from odds (dynamic)
    _tt_lines = {}
    for _o in match.odds:
        if _o.market == "TT" and _o.line is not None:
            _tt_lines[_o.side] = _o.line
    away_tt_line = _tt_lines.get(f"{away_code}_Over", 3.5)
    home_tt_line = _tt_lines.get(f"{home_code}_Over", 3.5)

    # Odd/Even (單雙)
    p_odd, p_even = _odd_even_probs(lam_a_adj, lam_h_adj)

    true_probs = {
        # 不讓分 Money Line
        f"ML_{away_code}": away_wp,
        f"ML_{home_code}": home_wp,
        # 讓分 Run Line
        f"RL_{away_code}": rl_away_cover,
        f"RL_{home_code}": rl_home_cover,
        # 大小分 Over/Under
        "OU_Over":  max(0.05, over_ou),
        "OU_Under": max(0.05, under_ou),
        # 單雙 Odd/Even
        "OE_Odd":  p_odd,
        "OE_Even": p_even,
        # 前五局 First 5
        f"F5_{away_code}": min(0.95, f5_away),
        f"F5_{home_code}": max(0.05, f5_home),
        # 隊伍總分 Team Totals
        f"TT_{away_code}_Over":  _p_over(away_runs_mu, away_tt_line),
        f"TT_{away_code}_Under": 1 - _p_over(away_runs_mu, away_tt_line),
        f"TT_{home_code}_Over":  _p_over(home_runs_mu, home_tt_line),
        f"TT_{home_code}_Under": 1 - _p_over(home_runs_mu, home_tt_line),
    }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. VALUE BET DETECTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    value_bets = detect_value(match.odds, true_probs)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. MARKET SIGNAL DETECTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    market_signals = detect_sharp(match.odds)
    market_headline = overall_signal(market_signals)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 7. RISK EVALUATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    bankroll = BankrollState()
    recent_errors = get_recent_errors(5)
    risk_status = evaluate_risk(bankroll, market_signals, recent_errors)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 8. PORTFOLIO / KELLY SIZING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if risk_status.allow_betting:
        portfolio = build_portfolio(value_bets, bankroll)
    else:
        portfolio = []

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 9. GENERATE REPORT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    report = build_report(
        match=match,
        away_wp=away_wp,
        home_wp=home_wp,
        wbc_details=wbc_details,
        ensemble_details=ensemble_details,
        poisson_details=poi_detail,
        mc_details=mc_detail,
        value_bets=value_bets,
        portfolio=portfolio,
        bankroll=bankroll,
        market_signals=market_signals,
        market_headline=market_headline,
        risk_status=risk_status,
    )

    print(report)

    # Optional JSON dump
    if dump_json:
        payload = {
            "match": f"{away_code} vs {home_code}",
            "round": match.round_name,
            "venue": match.venue,
            "pitch_limit": match.pitch_count_rule.max_pitches,
            "away_wp": round(away_wp, 4),
            "home_wp": round(home_wp, 4),
            "wbc_adjustments": wbc_details,
            "ensemble": ensemble_details,
            "true_probs": {k: round(v, 4) for k, v in true_probs.items()},
            "value_bets": [
                {
                    "market": v.market, "side": v.side,
                    "odds": v.decimal_odds, "ev": v.ev,
                    "tier": v.edge_tier,
                } for v in value_bets
            ],
            "portfolio": [
                {
                    "market": p.bet.market, "side": p.bet.side,
                    "odds": p.bet.decimal_odds, "stake": p.stake_amount,
                    "ev": p.bet.ev,
                } for p in portfolio
            ],
            "risk": {
                "level": risk_status.risk_level,
                "allow": risk_status.allow_betting,
                "reasons": risk_status.reasons,
            },
            "market_signal": market_headline,
        }
        print("\n\n--- RAW JSON ---")
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    dump = "--json" in sys.argv

    # ── List available games ──
    if "--list" in sys.argv:
        all_pools = _list_all_matches()
        for pool_name, games in all_pools.items():
            print(f"\n📅 WBC 2026 {pool_name}")
            print("=" * 55)
            for g in games:
                print(f"  {g['game_id']}  {g['tw_time']}  {g['away']} vs {g['home']}")
        total = sum(len(v) for v in all_pools.values())
        print(f"\n  Total: {total} games")
        print("\nUsage: python main.py --game=C01")
        sys.exit(0)

    # ── Parse game_id ──
    target_game = None
    for arg in sys.argv[1:]:
        if arg.startswith("--game="):
            target_game = arg.split("=", 1)[1]

    # ── Run all games ──
    # --all       => all 40 games
    # --all=A     => Pool A only
    # --all=B,C   => Pools B and C
    all_arg = None
    for arg in sys.argv[1:]:
        if arg == "--all":
            all_arg = "ABCD"
        elif arg.startswith("--all="):
            all_arg = arg.split("=", 1)[1].upper()

    if all_arg:
        pool_map = {
            "A": ("Pool A (San Juan)", list_wbc_matches_a()),
            "B": ("Pool B (Houston)", list_wbc_matches_b()),
            "C": ("Pool C (Tokyo)", list_wbc_matches()),
            "D": ("Pool D (Miami)", list_wbc_matches_d()),
        }
        for pool_key in sorted(all_arg):
            if pool_key not in pool_map:
                print(f"⚠️  Unknown pool '{pool_key}', skipping.")
                continue
            pool_name, games = pool_map[pool_key]
            print(f"\n{'#'*60}")
            print(f"  {pool_name}")
            print(f"{'#'*60}")
            for g in games:
                print(f"\n{'='*60}")
                print(f"  GAME {g['game_id']}: {g['away']} vs {g['home']}  ({g['tw_time']})")
                print(f"{'='*60}")
                main(dump_json=dump, game_id=g["game_id"])
    else:
        main(dump_json=dump, game_id=target_game)
