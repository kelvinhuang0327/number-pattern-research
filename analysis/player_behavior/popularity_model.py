"""
Popularity Model — Player Behavior Bias Scoring
=================================================
HEURISTIC model — NOT a predictive model.

Scores how "popular" a ticket might be among human players based on
known cognitive biases and cultural patterns in Taiwan lottery behavior.

A higher score means more people likely chose a similar combination,
leading to higher prize-splitting risk for pari-mutuel tiers.
"""
from typing import List, Dict


# Taiwan culturally lucky/unlucky numbers
LUCKY_NUMBERS = {7, 8, 9, 17, 18, 28, 38, 48}    # 8=發, 9=久, 7=universal lucky
UNLUCKY_NUMBERS = {4, 14, 24, 34, 44}              # 4≈死 in Chinese


def _birthday_bias(numbers: List[int], max_num: int) -> float:
    """Score: what fraction of numbers are in the birthday range (1-31)?
    Higher than expected ratio → more popular (more people pick dates)."""
    birthday_range = 31
    count_in_range = sum(1 for n in numbers if n <= birthday_range)
    pick = len(numbers)
    # Expected ratio if uniform: min(birthday_range, max_num) / max_num
    expected_ratio = min(birthday_range, max_num) / max_num
    actual_ratio = count_in_range / pick
    # Score 0-1: how much above expected
    if actual_ratio <= expected_ratio:
        return 0.0
    excess = (actual_ratio - expected_ratio) / (1.0 - expected_ratio)
    return min(1.0, excess)


def _lucky_number_bias(numbers: List[int], max_num: int) -> float:
    """Score: presence of culturally lucky numbers increases popularity."""
    applicable_lucky = {n for n in LUCKY_NUMBERS if n <= max_num}
    if not applicable_lucky:
        return 0.0
    count = sum(1 for n in numbers if n in applicable_lucky)
    # Normalize: 2+ lucky numbers is very popular
    return min(1.0, count / 2.0)


def _consecutive_bias(numbers: List[int]) -> float:
    """Score: consecutive number runs (e.g., 3,4,5) are very commonly played."""
    sorted_nums = sorted(numbers)
    max_run = 1
    current_run = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] == sorted_nums[i - 1] + 1:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    # 2 consecutive: mild, 3+: strong signal
    if max_run >= 4:
        return 1.0
    if max_run == 3:
        return 0.7
    if max_run == 2:
        return 0.3
    return 0.0


def _arithmetic_sequence_bias(numbers: List[int]) -> float:
    """Score: arithmetic progressions like 5,10,15,20,25 are visually appealing."""
    sorted_nums = sorted(numbers)
    if len(sorted_nums) < 3:
        return 0.0
    # Check if all differences are equal
    diffs = [sorted_nums[i + 1] - sorted_nums[i] for i in range(len(sorted_nums) - 1)]
    if len(set(diffs)) == 1 and diffs[0] > 0:
        return 1.0  # Perfect AP
    # Check if most differences are equal (near-AP)
    from collections import Counter
    diff_counts = Counter(diffs)
    most_common_diff, most_common_count = diff_counts.most_common(1)[0]
    if most_common_count >= len(diffs) - 1 and most_common_diff > 0:
        return 0.5  # Near-AP
    return 0.0


def _decade_clustering_bias(numbers: List[int], max_num: int) -> float:
    """Score: numbers clustered in same decade (e.g., all in 1-10) are more popular."""
    if not numbers:
        return 0.0
    # Assign each number to a decade: 1-10, 11-20, 21-30, 31-40, 41-50
    decades = [(n - 1) // 10 for n in numbers]
    n_decades = max_num // 10 + (1 if max_num % 10 else 0)
    unique_decades = len(set(decades))
    # Fewer unique decades = more clustered = more popular
    expected_decades = min(len(numbers), n_decades)
    if expected_decades <= 1:
        return 0.0
    # 1 decade = fully clustered, expected = well spread
    clustering = 1.0 - (unique_decades - 1) / (expected_decades - 1)
    return max(0.0, clustering)


def _low_number_bias(numbers: List[int], max_num: int) -> float:
    """Score: humans tend to pick lower numbers (cognitive ease)."""
    pick = len(numbers)
    bottom_third = max_num // 3
    count_low = sum(1 for n in numbers if n <= bottom_third)
    expected_ratio = bottom_third / max_num
    actual_ratio = count_low / pick
    if actual_ratio <= expected_ratio:
        return 0.0
    excess = (actual_ratio - expected_ratio) / (1.0 - expected_ratio)
    return min(1.0, excess)


def _round_number_bias(numbers: List[int]) -> float:
    """Score: multiples of 5 and 10 are more popular (round number effect)."""
    count_round = sum(1 for n in numbers if n % 5 == 0)
    # 2+ round numbers is notable
    return min(1.0, count_round / 2.0)


def _grid_pattern_bias(numbers: List[int], max_num: int, grid_cols: int = 7) -> float:
    """Score: visual patterns on the bet slip grid (straight lines, diagonals).
    Taiwan bet slips typically use a 7-column grid layout."""
    if grid_cols <= 0:
        return 0.0
    # Map numbers to (row, col) positions on grid
    positions = []
    for n in numbers:
        row = (n - 1) // grid_cols
        col = (n - 1) % grid_cols
        positions.append((row, col))

    # Check for same-row (horizontal line)
    from collections import Counter
    row_counts = Counter(r for r, c in positions)
    max_same_row = max(row_counts.values()) if row_counts else 0

    # Check for same-column (vertical line)
    col_counts = Counter(c for r, c in positions)
    max_same_col = max(col_counts.values()) if col_counts else 0

    # Diagonal check: positions where row-col or row+col is constant
    diag1 = Counter(r - c for r, c in positions)
    diag2 = Counter(r + c for r, c in positions)
    max_diag = max(
        max(diag1.values()) if diag1 else 0,
        max(diag2.values()) if diag2 else 0
    )

    # 3+ in a line is a very popular pattern
    max_line = max(max_same_row, max_same_col, max_diag)
    if max_line >= 4:
        return 1.0
    if max_line >= 3:
        return 0.5
    return 0.0


def _parity_uniformity_bias(numbers: List[int]) -> float:
    """Score: all-odd or all-even tickets are visually neat but commonly played."""
    n_odd = sum(1 for n in numbers if n % 2 == 1)
    n_even = len(numbers) - n_odd
    if n_odd == 0 or n_even == 0:
        return 1.0  # All same parity
    if n_odd == len(numbers) - 1 or n_even == len(numbers) - 1:
        return 0.3  # Nearly uniform parity
    return 0.0


# Bias weights for the final score
BIAS_WEIGHTS = {
    'birthday': 0.20,
    'lucky_numbers': 0.10,
    'consecutive': 0.15,
    'arithmetic_seq': 0.10,
    'decade_cluster': 0.15,
    'low_number': 0.10,
    'round_number': 0.05,
    'grid_pattern': 0.10,
    'parity_uniform': 0.05,
}


def compute_popularity(numbers: List[int], max_num: int, pick: int,
                       grid_cols: int = 7) -> Dict:
    """
    Compute a popularity score (0-100) for a ticket.

    This is a HEURISTIC model based on known human cognitive biases.
    A higher score means the combination is more likely to be chosen
    by other players, increasing prize split risk.

    Args:
        numbers: sorted list of selected numbers
        max_num: maximum number in the game pool
        pick: how many numbers are selected
        grid_cols: number of columns on the physical bet slip (default 7)

    Returns:
        dict with popularity_score (0-100), bias_flags, and bias_details
    """
    bias_scores = {
        'birthday': _birthday_bias(numbers, max_num),
        'lucky_numbers': _lucky_number_bias(numbers, max_num),
        'consecutive': _consecutive_bias(numbers),
        'arithmetic_seq': _arithmetic_sequence_bias(numbers),
        'decade_cluster': _decade_clustering_bias(numbers, max_num),
        'low_number': _low_number_bias(numbers, max_num),
        'round_number': _round_number_bias(numbers),
        'grid_pattern': _grid_pattern_bias(numbers, max_num, grid_cols),
        'parity_uniform': _parity_uniformity_bias(numbers),
    }

    # Weighted sum → 0-1 range
    raw_score = sum(bias_scores[k] * BIAS_WEIGHTS[k] for k in bias_scores)
    # Scale to 0-100
    popularity_score = round(min(100.0, raw_score * 100.0), 1)

    # Flag active biases (score > 0.3 threshold)
    bias_flags = [k for k, v in bias_scores.items() if v > 0.3]

    return {
        'popularity_score': popularity_score,
        'bias_flags': bias_flags,
        'bias_details': {k: round(v, 3) for k, v in bias_scores.items()},
    }
