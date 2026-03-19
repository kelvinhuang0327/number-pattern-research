"""
Anti-Crowd Recommendation — Lower-Popularity Alternative Suggestion
====================================================================
HEURISTIC model — NOT a predictive model.

When a ticket has high popularity/split-risk, suggests a structurally
close alternative with lower crowd overlap. Only modifies at most 2
numbers to maintain similarity to the original prediction.

IMPORTANT: This does NOT claim to improve prediction accuracy.
It only improves potential payout quality if the ticket wins.
"""
import random
from typing import List, Dict, Optional

from .popularity_model import compute_popularity, LUCKY_NUMBERS

# Seed for reproducibility within a session
_rng = random.Random(42)


def _find_replacement_candidates(numbers: List[int], max_num: int) -> List[dict]:
    """Identify which numbers to replace, prioritizing bias-heavy ones."""
    candidates = []
    for n in numbers:
        priority = 0
        reasons = []
        # Birthday range numbers (1-31) are most impactful to replace
        if n <= 31:
            priority += 2
            reasons.append('birthday_range')
        # Lucky numbers are popular
        if n in LUCKY_NUMBERS and n <= max_num:
            priority += 1
            reasons.append('lucky_number')
        # Low numbers
        if n <= max_num // 3:
            priority += 1
            reasons.append('low_number')
        # Round numbers
        if n % 5 == 0:
            priority += 1
            reasons.append('round_number')
        candidates.append({'number': n, 'priority': priority, 'reasons': reasons})

    # Sort by priority descending (replace highest-bias numbers first)
    candidates.sort(key=lambda x: x['priority'], reverse=True)
    return candidates


def _find_unpopular_numbers(exclude: set, max_num: int, count: int) -> List[int]:
    """Find numbers that are less commonly chosen by humans."""
    pool = []
    for n in range(1, max_num + 1):
        if n in exclude:
            continue
        score = 0
        # Prefer numbers > 31 (outside birthday range)
        if n > 31:
            score += 3
        # Prefer non-lucky, non-unlucky
        if n not in LUCKY_NUMBERS:
            score += 1
        # Prefer non-round
        if n % 5 != 0:
            score += 1
        # Prefer higher numbers
        if n > max_num * 2 // 3:
            score += 1
        pool.append((n, score))

    # Sort by score descending, pick top candidates
    pool.sort(key=lambda x: (-x[1], x[0]))
    return [n for n, _ in pool[:count * 3]]  # Return more than needed for variety


def suggest_anti_crowd(numbers: List[int], max_num: int, pick: int,
                       popularity_score: float) -> Dict:
    """
    Suggest a lower-popularity alternative ticket.

    ADVISORY ONLY — does not affect prediction ranking.

    Args:
        numbers: original predicted numbers (sorted)
        max_num: game pool maximum
        pick: numbers per ticket
        popularity_score: from compute_popularity()

    Returns:
        dict with alternative ticket (if applicable), changes, and new score
    """
    # Only suggest alternatives for MEDIUM-HIGH risk tickets
    if popularity_score < 50:
        return {
            'alternative': None,
            'alternative_score': None,
            'changes_made': [],
            'structural_distance': 0,
            'reason': 'Popularity score below threshold — no alternative needed',
        }

    # Maximum replacements: min(2, 33% of ticket)
    max_replacements = min(2, max(1, pick // 3))

    candidates = _find_replacement_candidates(numbers, max_num)
    exclude = set(numbers)
    unpopular_pool = _find_unpopular_numbers(exclude, max_num, max_replacements + 2)

    if not unpopular_pool:
        return {
            'alternative': None,
            'alternative_score': None,
            'changes_made': [],
            'structural_distance': 0,
            'reason': 'No suitable replacement numbers found',
        }

    # Build alternative by replacing highest-bias numbers
    alternative = list(numbers)
    changes = []
    replacements_made = 0

    for candidate in candidates:
        if replacements_made >= max_replacements:
            break
        if candidate['priority'] < 1:
            break  # Only replace numbers with actual bias
        if not unpopular_pool:
            break

        old_num = candidate['number']
        new_num = unpopular_pool.pop(0)
        idx = alternative.index(old_num)
        alternative[idx] = new_num
        changes.append(f'{old_num:02d}→{new_num:02d} ({", ".join(candidate["reasons"])})')
        replacements_made += 1

    alternative.sort()

    # Compute new popularity score
    new_pop = compute_popularity(alternative, max_num, pick)

    return {
        'alternative': alternative,
        'alternative_score': new_pop['popularity_score'],
        'changes_made': changes,
        'structural_distance': replacements_made,
        'improvement': round(popularity_score - new_pop['popularity_score'], 1),
    }
