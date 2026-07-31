"""
Enhanced Reporting Renderers — § 十 輸出格式

Each game outputs:
  勝率 | 預測比分 | 市場偏差值 | EV | 最佳投注策略 | 信心指數
"""
from __future__ import annotations

import json

from wbc_backend.domain.schemas import (
    GameOutput,
    PredictionResult,
    SimulationSummary,
)


def _market_support_label(state: str) -> str:
    mapping = {
        "tsl_direct": "TSL direct",
        "tsl_stale": "TSL stale",
        "tsl_unlisted_market": "TSL matchup listed, market unavailable",
        "tsl_unlisted_matchup": "TSL matchup unavailable",
        "intl_only": "International only",
        "mixed": "Mixed support",
    }
    return mapping.get(str(state or ""), str(state or "unknown"))


def _compact_market_support_map(support_map: dict[str, str] | None) -> str:
    if not support_map:
        return ""
    ordered = ["ML", "RL", "OU", "OE", "F5", "TT"]
    parts = []
    for market in ordered:
        if market in support_map:
            parts.append(f"{market}:{_market_support_label(str(support_map[market]))}")
    return " | ".join(parts)


def _compact_market_support_breakdown(counts: dict[str, int] | None) -> str:
    if not counts:
        return ""
    ordered = [
        "tsl_direct",
        "intl_only",
        "tsl_stale",
        "tsl_unlisted_market",
        "tsl_unlisted_matchup",
        "mixed",
        "unknown",
    ]
    parts = []
    for state in ordered:
        if state in counts:
            parts.append(f"{_market_support_label(state)} x{int(counts[state])}")
    for state, count in counts.items():
        if state not in ordered:
            parts.append(f"{_market_support_label(state)} x{int(count)}")
    return " | ".join(parts)


def _top_market_support_groups(summary: dict[str, object] | None, limit: int = 3) -> list[str]:
    if not summary:
        return []
    groups = summary.get("groups")
    if not isinstance(groups, dict):
        return []
    lines: list[str] = []
    for state, metrics in list(groups.items())[:limit]:
        if not isinstance(metrics, dict):
            continue
        lines.append(
            f"{_market_support_label(str(state))}: "
            f"games={int(metrics.get('games', 0))}, "
            f"acc={float(metrics.get('winner_accuracy', 0.0)):.1%}, "
            f"brier={float(metrics.get('avg_brier', 0.0)):.4f}"
        )
    return lines


def render_full_report(  # noqa: C901
    game: GameOutput,
    pred: PredictionResult,
    sim: SimulationSummary,
    market_result: dict,
    adv_features=None,
    decision_report=None,
    calibration_metrics: dict | None = None,
    portfolio_metrics: dict | None = None,
    market_support_performance: dict | None = None,
) -> str:
    """Generate comprehensive markdown report."""
    lines = [
        "=" * 70,
        f"🏟️  WBC MATCH REPORT: {game.game_id}",
        f"    {game.away_team} @ {game.home_team}",
        "=" * 70,
        "",
        "━" * 40,
        "📊 CORE PREDICTION",
        "━" * 40,
        "  最終勝率 (Final Calibrated Win Probability):",
        f"    {game.home_team}: {game.home_win_prob:.1%}",
        f"    {game.away_team}: {game.away_win_prob:.1%}",
        "",
        "  最終展示比分 (Display Score):",
        f"    {game.home_team} {game.predicted_home_score:.1f} - "
        f"{game.predicted_away_score:.1f} {game.away_team}",
        "",
        f"  市場偏差值 (Market Bias): {game.market_bias_score:+.4f}",
        f"  最佳 EV: {game.ev_best:+.4f}",
        f"  信心指數 (Confidence): {game.confidence_index:.0%}",
        "  註: 勝率與展示比分以最終校準方向為主；Monte Carlo 區塊為模擬層參考。",
        "",
    ]

    # ── Sub-model breakdown ──────────────────────────────
    if pred.sub_model_results:
        lines.extend([
            "━" * 40,
            "🧠 SUB-MODEL RESULTS",
            "━" * 40,
        ])
        for sr in pred.sub_model_results:
            lines.append(
                f"  {sr.model_name:12s}: Home={sr.home_win_prob:.3f}  "
                f"Away={sr.away_win_prob:.3f}  (conf={sr.confidence:.2f})"
            )
        lines.append("")

    # ── Advanced Features ────────────────────────────────
    if adv_features:
        lines.extend([
            "━" * 40,
            "🧬 ADVANCED FEATURES",
            "━" * 40,
            f"  SP Fatigue:     Home={adv_features.home_sp_fatigue:.3f}  "
            f"Away={adv_features.away_sp_fatigue:.3f}",
            f"  Bullpen Stress: Home={adv_features.home_bullpen_stress:.3f}  "
            f"Away={adv_features.away_bullpen_stress:.3f}",
            f"  Matchup Edge:   Home={adv_features.home_matchup_edge:+.3f}  "
            f"Away={adv_features.away_matchup_edge:+.3f}",
            f"  Clutch Index:   Home={adv_features.home_clutch_index:+.3f}  "
            f"Away={adv_features.away_clutch_index:+.3f}",
            "",
        ])

    # ── Monte Carlo Results ──────────────────────────────
    lines.extend([
        "━" * 40,
        f"🎲 MONTE CARLO SIMULATION LAYER ({sim.n_simulations:,} simulations)",
        "━" * 40,
        f"  Home Win:     {sim.home_win_prob:.1%}",
        f"  Over {7.5}:    {sim.over_prob:.1%}",
        f"  Home Cover:   {sim.home_cover_prob:.1%}",
        f"  Odd Total:    {sim.odd_prob:.1%}",
        f"  Home F5 Win:  {sim.home_f5_win_prob:.1%}",
        f"  Mean Total:   {sim.mean_total_runs:.1f} (σ={sim.std_total_runs:.1f})",
        "",
    ])

    # ── Top Scores ───────────────────────────────────────
    if sim.score_distribution:
        lines.append("  Top 5 Most Likely Scores:")
        for score, prob in list(sim.score_distribution.items())[:5]:
            lines.append(f"    {score}: {prob:.1%}")
        lines.append("")

    # ── Market Calibration ───────────────────────────────
    lines.extend([
        "━" * 40,
        "💰 MARKET CALIBRATION",
        "━" * 40,
        f"  Market-Implied Home: {market_result.get('market_implied_home', 0):.1%}",
        f"  Model Home:          {pred.home_win_prob:.1%}",
        f"  Adjusted Home:       {market_result.get('adjusted_home_prob', 0):.1%}",
        f"  Market Bias:         {market_result.get('market_bias_score', 0):+.4f}",
        f"  Model Weight:        {market_result.get('model_weight_applied', 0.85):.0%}",
        f"  Market Weight:       {market_result.get('market_weight_applied', 0.15):.0%}",
        f"  Steam Moves:         {market_result.get('n_steam_moves', 0)}",
        f"  Market Support:      {market_result.get('market_support_summary', '')}",
        "",
    ])
    support_map = market_result.get("market_support_by_market")
    if isinstance(support_map, dict) and support_map:
        lines.append(f"  Market Support Map:  {_compact_market_support_map(support_map)}")
        lines.append("")

    tsl_status = pred.diagnostics.get("tsl_status")
    if isinstance(tsl_status, dict):
        lines.extend([
            "━" * 40,
            "🎯 TSL FEED STATUS",
            "━" * 40,
            f"  Source:             {tsl_status.get('source', '')}",
            f"  Success:            {tsl_status.get('success', False)}",
            f"  Games Count:        {tsl_status.get('games_count', 0)}",
            f"  Fetched At:         {tsl_status.get('fetched_at', '')}",
        ])
        if tsl_status.get("note"):
            lines.append(f"  Note:               {tsl_status.get('note')}")
        if tsl_status.get("error"):
            lines.append(f"  Error:              {tsl_status.get('error')}")
        tsl_matchup = pred.diagnostics.get("tsl_matchup")
        if isinstance(tsl_matchup, dict):
            lines.append(f"  Matchup In Snapshot:{' ' if tsl_matchup.get('in_snapshot') else ''} {tsl_matchup.get('in_snapshot', False)}")
            if tsl_matchup.get("game_id"):
                lines.append(f"  Snapshot Game ID:   {tsl_matchup.get('game_id')}")
            if tsl_matchup.get("game_time"):
                lines.append(f"  Snapshot Game Time: {tsl_matchup.get('game_time')}")
            if tsl_matchup.get("market_count") is not None:
                lines.append(f"  Snapshot Markets:   {tsl_matchup.get('market_count', 0)}")
            market_codes = tsl_matchup.get("market_codes") or []
            if market_codes:
                lines.append(f"  Market Codes:       {', '.join(market_codes)}")
        lines.append("")

    # ── X-Factors ────────────────────────────────────────
    if pred.x_factors:
        lines.extend([
            "━" * 40,
            "⚡ X-FACTORS",
            "━" * 40,
        ])
        for xf in pred.x_factors:
            lines.append(f"  • {xf}")
        lines.append("")

    # ── TOP 3 BETS ───────────────────────────────────────
    lines.extend([
        "━" * 40,
        "🏆 TOP 3 BETS",
        "━" * 40,
    ])

    if not game.top_3_bets:
        lines.append("  No positive-EV bets found above threshold.")
    else:
        for i, bet in enumerate(game.top_3_bets, 1):
            market_desc = f"{bet.market} {bet.side}"
            if bet.line is not None:
                market_desc += f" ({bet.line:+.1f})"

            lines.extend([
                f"  {i}. {market_desc} @ {bet.sportsbook}",
                f"     EV = {bet.ev:+.4f}  |  Edge = {bet.edge:.3f}  |  "
                f"Confidence = {bet.confidence:.0%}",
                f"     Kelly = {bet.kelly_fraction:.4f}  |  "
                f"Stake = ${bet.stake_amount:,.0f} ({bet.stake_fraction:.1%})",
                f"     Win Prob = {bet.win_probability:.1%}  |  "
                f"Implied = {bet.implied_probability:.1%}",
            ])
            if getattr(bet, "market_support_state", ""):
                lines.append(
                    f"     Market Support = {_market_support_label(getattr(bet, 'market_support_state', ''))}"
                )
            if getattr(bet, "decision_timing", "IMMEDIATE") != "IMMEDIATE":
                lines.append(
                    f"     Timing = {bet.decision_timing} "
                    f"(delay {getattr(bet, 'delay_minutes', 0)} min)"
                )
            if i < len(game.top_3_bets):
                lines.append("")

    # ── Institutional Decision Engine ────────────────────
    if decision_report is not None:
        lines.extend([
            "━" * 40,
            "🏛️ INSTITUTIONAL DECISION ENGINE",
            "━" * 40,
            f"  Verdict:       {decision_report.decision}",
            f"  Confidence:    {decision_report.confidence}",
            f"  Edge Score:    {decision_report.edge_score:.1f}",
            f"  Market Regime: {decision_report.market_regime}",
        ])
        if hasattr(decision_report, 'bets') and decision_report.bets:
            lines.append(f"  Approved Bets: {len(decision_report.bets)}")
        lines.append("")

    # ── Portfolio Optimization ───────────────────────────
    if portfolio_metrics:
        lines.extend([
            "━" * 40,
            "📈 PORTFOLIO OPTIMIZATION",
            "━" * 40,
            f"  Survival Prob (30d):  {portfolio_metrics.get('survival_prob', 0):.1%}",
            f"  CVaR (95%):           {portfolio_metrics.get('cvar_95', 0):.6f}",
            f"  Expected Return:      {portfolio_metrics.get('expected_return', 0):.6f}",
            f"  Gross Exposure:       {portfolio_metrics.get('gross_exposure', 0):.4f}",
            f"  Drawdown Scale:       {portfolio_metrics.get('drawdown_scale', 1.0):.4f}",
            f"  Current Drawdown:     {portfolio_metrics.get('current_drawdown', 0):.1%}",
            f"  Risk Level:           {portfolio_metrics.get('risk_level', '')}",
            f"  Data Quality Risk:    {portfolio_metrics.get('data_quality_risk', '')}",
            f"  TSL Feed State:       {portfolio_metrics.get('tsl_feed_state', '')}",
            f"  TSL Matchup Listed:   {portfolio_metrics.get('tsl_matchup_in_snapshot', False)}",
            f"  TSL Matchup Markets:  {portfolio_metrics.get('tsl_matchup_market_count', 0)}",
            f"  Market Support:       {_market_support_label(portfolio_metrics.get('market_support_profile', ''))}",
            f"  Support Tilt:         {portfolio_metrics.get('market_support_tilt', '')}",
            "",
        ])
        if portfolio_metrics.get("tsl_feed_summary"):
            lines.append(f"  TSL Feed Summary:     {portfolio_metrics.get('tsl_feed_summary')}")
        if portfolio_metrics.get("market_support_breakdown"):
            lines.append(
                "  Support Breakdown:   "
                f"{_compact_market_support_breakdown(portfolio_metrics.get('market_support_breakdown'))}"
            )
        if portfolio_metrics.get("market_support_adjustments"):
            adjustments = portfolio_metrics.get("market_support_adjustments") or {}
            ordered = []
            for state, multiplier in adjustments.items():
                ordered.append(f"{_market_support_label(str(state))} x{float(multiplier):.3f}")
            lines.append(f"  Support Adjustments: {' | '.join(ordered)}")
        for warning in portfolio_metrics.get("warnings", []) or []:
            lines.append(f"  Warning:              {warning}")
        lines.append("")

    if market_support_performance:
        lines.extend([
            "━" * 40,
            "📚 MARKET SUPPORT PERFORMANCE",
            "━" * 40,
            f"  Group By:            {market_support_performance.get('group_by', '')}",
            f"  Tracked Games:       {market_support_performance.get('n_games', 0)}",
        ])
        if market_support_performance.get("decision_note"):
            lines.append(f"  Decision Note:       {market_support_performance.get('decision_note')}")
        for row in _top_market_support_groups(market_support_performance):
            lines.append(f"  {row}")
        lines.append("")

    # ── Calibration Monitoring ───────────────────────────
    if calibration_metrics:
        lines.extend([
            "━" * 40,
            "🎯 CALIBRATION MONITORING",
            "━" * 40,
            f"  Brier Score:   {calibration_metrics.get('brier', 0):.4f}",
            f"  Log Loss:      {calibration_metrics.get('logloss', 0):.4f}",
            f"  ECE:           {calibration_metrics.get('ece', 0):.4f}",
            f"  MCE:           {calibration_metrics.get('mce', 0):.4f}",
            f"  Predictions:   {int(calibration_metrics.get('n_predictions', 0))}",
        ])
        if calibration_metrics.get('drift_flag'):
            lines.append(f"  ⚠️  DRIFT DETECTED  (PSI={calibration_metrics.get('psi', 0):.4f})")
        lines.append("")

    lines.extend(["", "=" * 70])
    return "\n".join(lines)


def render_json(
    game: GameOutput,
    pred: PredictionResult,
    sim: SimulationSummary,
    market_result: dict,
    decision_report=None,
    calibration_metrics: dict | None = None,
    portfolio_metrics: dict | None = None,
    market_support_performance: dict | None = None,
) -> str:
    """Generate JSON report."""
    payload = {
        "game_output": {
            "game_id": game.game_id,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_win_prob": game.home_win_prob,
            "away_win_prob": game.away_win_prob,
            "predicted_home_score": game.predicted_home_score,
            "predicted_away_score": game.predicted_away_score,
            "market_bias_score": game.market_bias_score,
            "ev_best": game.ev_best,
            "best_bet_strategy": game.best_bet_strategy,
            "confidence_index": game.confidence_index,
        },
        "sub_models": [
            {
                "model": sr.model_name,
                "home_wp": sr.home_win_prob,
                "away_wp": sr.away_win_prob,
                "confidence": sr.confidence,
            }
            for sr in pred.sub_model_results
        ],
        "simulation": {
            "n": sim.n_simulations,
            "home_win": sim.home_win_prob,
            "over_prob": sim.over_prob,
            "home_cover": sim.home_cover_prob,
            "odd_prob": sim.odd_prob,
            "mean_total": sim.mean_total_runs,
            "std_total": sim.std_total_runs,
            "top_scores": sim.score_distribution,
        },
        "market": market_result,
        "final_probability_basis": "market_calibrated",
        "diagnostics": pred.diagnostics,
        "x_factors": pred.x_factors,
        "top_3_bets": [
            {
                "rank": i + 1,
                "market": b.market,
                "side": b.side,
                "line": b.line,
                "sportsbook": b.sportsbook,
                "ev": b.ev,
                "edge": b.edge,
                "confidence": b.confidence,
                "kelly": b.kelly_fraction,
                "stake": b.stake_amount,
                "win_prob": b.win_probability,
                "implied_prob": b.implied_probability,
                "approved": b.approved,
                "timing": b.decision_timing,
                "delay_minutes": b.delay_minutes,
                "market_support_state": b.market_support_state,
                "market_support_label": _market_support_label(b.market_support_state),
            }
            for i, b in enumerate(game.top_3_bets)
        ],
    }
    if decision_report is not None:
        payload["decision_engine"] = {
            "verdict": decision_report.decision,
            "confidence": decision_report.confidence,
            "edge_score": decision_report.edge_score,
            "market_regime": decision_report.market_regime,
            "n_approved_bets": len(decision_report.bets) if hasattr(decision_report, 'bets') and decision_report.bets else 0,
        }
    if portfolio_metrics:
        payload["portfolio"] = portfolio_metrics
        if portfolio_metrics.get("market_support_breakdown"):
            payload["portfolio"]["market_support_breakdown_label"] = _compact_market_support_breakdown(
                portfolio_metrics.get("market_support_breakdown")
            )
    if calibration_metrics:
        payload["calibration"] = calibration_metrics
    if market_support_performance:
        payload["market_support_performance"] = market_support_performance

    return json.dumps(payload, ensure_ascii=False, indent=2)
