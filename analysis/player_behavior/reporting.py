"""
Reporting — Format Advisory Output for CLI and API
====================================================
HEURISTIC model — NOT a predictive model.

Formats player behavior / split-risk analysis into human-readable output
for both markdown (API/frontend) and plain text (CLI).
"""


def format_advisory(analysis: dict) -> str:
    """
    Format analysis dict into markdown for API/frontend display.

    Args:
        analysis: output from analyze_tickets()

    Returns:
        Markdown-formatted advisory string
    """
    if not analysis or 'bets' not in analysis:
        return ''

    bets = analysis.get('bets', [])
    summary = analysis.get('summary', {})
    if not bets:
        return ''

    lines = []
    lines.append('---')
    lines.append('### Player Behavior / Split-Risk Analysis (Advisory Only)')
    lines.append('')

    for i, bet_info in enumerate(bets, 1):
        nums = bet_info.get('numbers', [])
        pop = bet_info.get('popularity', {})
        risk = bet_info.get('split_risk', {})
        anti = bet_info.get('anti_crowd', {})

        nums_str = ', '.join(f'{n:02d}' for n in nums)
        score = pop.get('popularity_score', 0)
        level = risk.get('split_risk_level', 'LOW')
        flags = pop.get('bias_flags', [])

        lines.append(f'**注{i}**: {nums_str}')
        lines.append(f'- Popularity: **{score:.0f}/100** ({level})')

        if flags:
            lines.append(f'- Bias flags: {", ".join(flags)}')

        lines.append(f'- Split risk: {risk.get("expected_dilution", "")}')

        # Anti-crowd alternative
        if anti.get('alternative'):
            alt_str = ', '.join(f'{n:02d}' for n in anti['alternative'])
            alt_score = anti.get('alternative_score', 0)
            improvement = anti.get('improvement', 0)
            changes = anti.get('changes_made', [])
            lines.append(f'- Alternative: {alt_str} (score {alt_score:.0f}, -{improvement:.0f}pts)')
            if changes:
                lines.append(f'  - Changes: {"; ".join(changes)}')

        lines.append('')

    # Summary
    lines.append(f'**Summary**: avg popularity {summary.get("avg_popularity", 0):.0f}/100, '
                 f'max {summary.get("max_popularity", 0):.0f}/100, '
                 f'highest risk: {summary.get("highest_risk", "LOW")}')
    lines.append('')
    lines.append('> *This section is ADVISORY ONLY. '
                 'It does NOT affect prediction accuracy or ranking. '
                 'It only estimates potential payout dilution if the ticket wins.*')

    return '\n'.join(lines)


def format_advisory_cli(analysis: dict) -> str:
    """
    Format analysis dict into plain text for CLI display.

    Args:
        analysis: output from analyze_tickets()

    Returns:
        Plain-text advisory string for terminal output
    """
    if not analysis or 'bets' not in analysis:
        return ''

    bets = analysis.get('bets', [])
    summary = analysis.get('summary', {})
    if not bets:
        return ''

    lines = []
    lines.append('============================================================')
    lines.append('  PLAYER BEHAVIOR / SPLIT-RISK ANALYSIS (Advisory Only)')
    lines.append('============================================================')

    for i, bet_info in enumerate(bets, 1):
        nums = bet_info.get('numbers', [])
        pop = bet_info.get('popularity', {})
        risk = bet_info.get('split_risk', {})
        anti = bet_info.get('anti_crowd', {})

        nums_str = ', '.join(f'{n:02d}' for n in nums)
        score = pop.get('popularity_score', 0)
        level = risk.get('split_risk_level', 'LOW')
        flags = pop.get('bias_flags', [])

        lines.append(f'  注{i}: {nums_str}')
        lines.append(f'    Popularity: {score:.0f}/100 ({level})')

        if flags:
            lines.append(f'    Bias flags: {", ".join(flags)}')

        dilution = risk.get('expected_dilution', '')
        pari_tiers = risk.get('pari_mutuel_tiers', [])
        if pari_tiers:
            tier_names = '/'.join(t.split('(')[0].strip() for t in pari_tiers[:3])
            lines.append(f'    Split risk: {level} — {tier_names} may be diluted')
        else:
            lines.append(f'    Split risk: {level}')

        # Anti-crowd alternative
        if anti.get('alternative'):
            alt_str = ', '.join(f'{n:02d}' for n in anti['alternative'])
            alt_score = anti.get('alternative_score', 0)
            improvement = anti.get('improvement', 0)
            changes = anti.get('changes_made', [])
            lines.append(f'    Alternative: {alt_str} (score {alt_score:.0f}, -{improvement:.0f}pts)')
            for ch in changes:
                lines.append(f'      {ch}')

        lines.append('')

    lines.append('------------------------------------------------------------')
    lines.append(f'  Summary: avg={summary.get("avg_popularity", 0):.0f} '
                 f'max={summary.get("max_popularity", 0):.0f} '
                 f'risk={summary.get("highest_risk", "LOW")}')
    lines.append('  This section is ADVISORY ONLY.')
    lines.append('  It does NOT affect prediction accuracy or ranking.')
    lines.append('============================================================')

    return '\n'.join(lines)
