"""Markdown reporting for the lottery hedge fund architecture."""

from __future__ import annotations

from typing import Dict, List


def build_hedge_fund_report(report_payload: Dict) -> str:
    lines: List[str] = []
    lines.append('# Lottery Hedge Fund Strategy Report')
    lines.append('')

    for lottery_type, payload in report_payload['lotteries'].items():
        lines.append(f'## {lottery_type}')
        lines.append('')
        lines.append('### Section A — Prediction Results')
        lines.append(f"- Candidate source: {payload['prediction_source']}")
        lines.append(f"- Default tickets: {payload['default_bets']}")
        lines.append(
            f"- Current jackpot: {payload['assumptions']['jackpot']} "
            f"(breakeven={payload['assumptions'].get('breakeven_jackpot')})"
        )
        lines.append('')

        lines.append('### Section B — Player Behavior Analysis')
        for item in payload['baseline_prediction']['tickets']:
            lines.append(
                f"- {item['ticket']}: popularity={item['popularity_score']}, "
                f"split_risk={item['split_risk_level']}, payout_quality={item['payout_quality_score']}, "
                f"ev={item['expected_value']}"
            )
        lines.append('')

        lines.append('### Section C — Payout Optimization')
        lines.append(
            f"- Best payout portfolio score: {payload['portfolio_optimized']['portfolio_score']}"
        )
        lines.append(
            f"- Decision: {payload['portfolio_optimized'].get('decision', 'BET')} "
            f"({payload['portfolio_optimized'].get('reason', '')})"
        )
        lines.append(
            f"- Avg overlap: {payload['portfolio_optimized']['avg_overlap']}, "
            f"diversity bonus: {payload['portfolio_optimized']['diversity_bonus']}"
        )
        lines.append(
            f"- Portfolio EV sum: {payload['portfolio_optimized'].get('expected_value_sum', 0.0)}, "
            f"total cost: {payload['portfolio_optimized'].get('total_cost', 0.0)}"
        )
        lines.append('')

        lines.append('### Section D — Risk & Bankroll Analysis')
        best_bankroll = payload['bankroll_best']
        lines.append(
            f"- Safest bankroll strategy: {best_bankroll['strategy']} "
            f"({best_bankroll['adjusted_recommendation']}, optimal size={best_bankroll['optimal_bet_size']})"
        )
        lines.append(
            f"- Risk of ruin: {best_bankroll['risk_of_ruin']}, "
            f"survival probability: {best_bankroll['survival_probability']}"
        )
        lines.append('')

    lines.append('## Final Answers')
    lines.append('')
    lines.append(
        f"1. Does payout optimization improve real-world outcomes? "
        f"{report_payload['final_answers']['payout_optimization_improves_outcomes']}"
    )
    lines.append(
        f"2. How much does it reduce split risk? "
        f"{report_payload['final_answers']['split_risk_reduction']}"
    )
    lines.append(
        f"3. What is the optimal portfolio structure? "
        f"{report_payload['final_answers']['optimal_portfolio_structure']}"
    )
    lines.append(
        f"4. What is the safest bankroll strategy? "
        f"{report_payload['final_answers']['safest_bankroll_strategy']}"
    )
    lines.append(
        f"5. Can this system outperform naive betting in practice? "
        f"{report_payload['final_answers']['outperform_naive_betting']}"
    )
    lines.append('')

    return '\n'.join(lines)
