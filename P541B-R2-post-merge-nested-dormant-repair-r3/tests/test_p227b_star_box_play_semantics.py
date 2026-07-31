"""
tests/test_p227b_star_box_play_semantics.py
===========================================
P227B — Unit tests for 3_STAR / 4_STAR box-play metric semantics.

All tests exercise lottery_api.models.star_box_play only.
No DB reads/writes, no strategy_prediction_replays, no calculate_match_score.

Run with:
    pytest tests/test_p227b_star_box_play_semantics.py -v
"""
from __future__ import annotations

import json
import pytest
from collections import Counter
from lottery_api.models.star_box_play import (
    star_box_exact_match,
    star_digit_overlap_count,
    star_calculate_box_score,
    get_box_baseline,
    validate_star_input,
    build_dryrun_row,
    STAR_CONFIG,
    STAR_LOTTERY_TYPES,
    STRAIGHT_PLAY_BLOCKED_REASON,
)


# ---------------------------------------------------------------------------
# 1. Exact box match
# ---------------------------------------------------------------------------


def test_exact_match_identical():
    assert star_box_exact_match([5, 6, 9], [5, 6, 9]) is True


def test_exact_match_wrong_order_still_hits():
    """Box-play: order does not matter — [9,6,5] matches [5,6,9]."""
    assert star_box_exact_match([9, 6, 5], [5, 6, 9]) is True


def test_exact_match_all_permutations_hit():
    from itertools import permutations
    for perm in permutations([1, 3, 7]):
        assert star_box_exact_match(list(perm), [1, 3, 7]) is True


def test_exact_match_total_miss():
    assert star_box_exact_match([1, 2, 3], [5, 6, 9]) is False


def test_exact_match_partial_miss():
    """2 of 3 digits match but not all 3 → no box win."""
    assert star_box_exact_match([5, 6, 0], [5, 6, 9]) is False


# ---------------------------------------------------------------------------
# 2. Repeated digit handling
# ---------------------------------------------------------------------------


def test_exact_match_triple_repeat():
    assert star_box_exact_match([5, 5, 5], [5, 5, 5]) is True


def test_exact_match_triple_repeat_miss():
    assert star_box_exact_match([5, 5, 5], [5, 5, 9]) is False


def test_exact_match_double_repeat_hit():
    assert star_box_exact_match([5, 5, 9], [5, 5, 9]) is True
    assert star_box_exact_match([9, 5, 5], [5, 5, 9]) is True   # order irrelevant


def test_exact_match_double_repeat_vs_no_repeat():
    """[5,5,9] must NOT match [5,6,9] — the extra 5 vs 6 matters."""
    assert star_box_exact_match([5, 5, 9], [5, 6, 9]) is False


# ---------------------------------------------------------------------------
# 3. Overlap count (multiset semantics)
# ---------------------------------------------------------------------------


def test_overlap_full_match():
    assert star_digit_overlap_count([5, 6, 9], [5, 6, 9]) == 3


def test_overlap_partial():
    assert star_digit_overlap_count([5, 6, 1], [5, 6, 9]) == 2


def test_overlap_zero():
    assert star_digit_overlap_count([1, 2, 3], [5, 6, 9]) == 0


def test_overlap_one():
    assert star_digit_overlap_count([5, 0, 0], [5, 6, 9]) == 1


def test_overlap_repeated_digit_multiset_correct():
    """
    Multiset intersection (Counter) must handle repeated digits correctly.

    predicted = [5,5,9] → Counter({5:2, 9:1})
    actual    = [5,6,9] → Counter({5:1, 6:1, 9:1})
    intersection = {5:1, 9:1} → size 2

    set intersection would give: {5,9} & {5,6,9} = {5,9} → size 2 (same here).
    But for the next case the difference becomes visible.
    """
    assert star_digit_overlap_count([5, 5, 9], [5, 6, 9]) == 2


def test_overlap_repeated_digit_multiset_differs_from_set():
    """
    Demonstrate that multiset intersection differs from set intersection
    when both sides have repeated digits.

    predicted = [5,5,5] → Counter({5:3})
    actual    = [5,5,9] → Counter({5:2, 9:1})
    multiset intersection = {5:2} → size 2

    set intersection: {5} & {5,9} = {5} → size 1  ← WRONG
    """
    multi = star_digit_overlap_count([5, 5, 5], [5, 5, 9])
    # set semantics (wrong)
    set_result = len(set([5, 5, 5]) & set([5, 5, 9]))
    assert multi == 2, f"Expected multiset overlap 2, got {multi}"
    assert set_result == 1, "set overlap is 1 (confirms set semantics are wrong here)"
    assert multi != set_result, "multiset and set semantics must differ in this case"


# ---------------------------------------------------------------------------
# 4. calculate_box_score encoding
# ---------------------------------------------------------------------------


def test_box_score_exact_hit_returns_pick_count():
    hit_count, exact, overlap = star_calculate_box_score([9, 5, 6], [5, 6, 9], 3)
    assert exact is True
    assert hit_count == 3
    assert overlap == 3


def test_box_score_miss_returns_zero():
    hit_count, exact, overlap = star_calculate_box_score([1, 2, 3], [5, 6, 9], 3)
    assert exact is False
    assert hit_count == 0
    assert overlap == 0


def test_box_score_partial_hit_count_is_zero():
    """Partial overlap is NOT a box win — hit_count must be 0."""
    hit_count, exact, overlap = star_calculate_box_score([5, 6, 1], [5, 6, 9], 3)
    assert exact is False
    assert hit_count == 0
    assert overlap == 2  # 2 digits overlap but not a win


def test_box_score_4star():
    hit_count, exact, overlap = star_calculate_box_score(
        [0, 1, 5, 6], [0, 1, 5, 6], 4
    )
    assert exact is True
    assert hit_count == 4


def test_box_score_wrong_length_raises():
    with pytest.raises(ValueError, match="predicted length"):
        star_calculate_box_score([1, 2], [5, 6, 9], 3)
    with pytest.raises(ValueError, match="actual length"):
        star_calculate_box_score([1, 2, 3], [5, 6], 3)


# ---------------------------------------------------------------------------
# 5. Baselines
# ---------------------------------------------------------------------------


def test_baseline_3star_no_repeat():
    b = get_box_baseline("3_STAR", repeats_detected=False)
    assert abs(b - 1 / 120) < 1e-9


def test_baseline_4star_no_repeat():
    b = get_box_baseline("4_STAR", repeats_detected=False)
    assert abs(b - 1 / 210) < 1e-9


def test_baseline_3star_with_repeat():
    b = get_box_baseline("3_STAR", repeats_detected=True)
    assert abs(b - 1 / 220) < 1e-9


def test_baseline_4star_with_repeat():
    b = get_box_baseline("4_STAR", repeats_detected=True)
    assert abs(b - 1 / 715) < 1e-9


def test_baseline_unknown_type_raises():
    with pytest.raises(ValueError):
        get_box_baseline("BIG_LOTTO")


# ---------------------------------------------------------------------------
# 6. Sorted-input limitation documented
# ---------------------------------------------------------------------------


def test_straight_play_blocked_string_present():
    """STRAIGHT_PLAY_BLOCKED_REASON must document positional order loss."""
    assert "positional" in STRAIGHT_PLAY_BLOCKED_REASON.lower()
    assert "sorted" in STRAIGHT_PLAY_BLOCKED_REASON.lower() or \
           "re-ingest" in STRAIGHT_PLAY_BLOCKED_REASON.lower()


def test_active_mode_is_box_exact():
    """Both star types must declare active_mode = 'box_exact'."""
    for lt in ("3_STAR", "4_STAR"):
        assert STAR_CONFIG[lt]["active_mode"] == "box_exact", \
            f"{lt} active_mode must be 'box_exact'"


def test_star_lottery_types_constant():
    assert "3_STAR" in STAR_LOTTERY_TYPES
    assert "4_STAR" in STAR_LOTTERY_TYPES


# ---------------------------------------------------------------------------
# 7. calculate_match_score is NOT the scoring function for star lotteries
# ---------------------------------------------------------------------------


def test_set_intersection_wrong_for_repeated_digits():
    """
    Demonstrate why calculate_match_score (set intersection) is wrong for
    3_STAR / 4_STAR repeated-digit scenarios.

    This test does NOT import calculate_match_score — it re-implements the
    set-intersection logic inline to prove the semantic difference.
    """
    def old_set_match(predicted, actual):
        """Reproduces calculate_match_score semantics: set intersection."""
        return len(set(predicted) & set(actual))

    # Case: [5,5,5] vs [5,5,9]
    pred, act = [5, 5, 5], [5, 5, 9]
    set_result = old_set_match(pred, act)    # {5} & {5,9} = {5} → 1
    multi_result = star_digit_overlap_count(pred, act)  # Counter min → 2

    assert set_result == 1, "set semantics gives 1 (too low)"
    assert multi_result == 2, "multiset semantics gives 2 (correct)"
    assert set_result != multi_result, \
        "set and multiset semantics must differ for this repeated-digit case"


def test_star_module_does_not_import_or_call_calculate_match_score():
    """
    Verify the star_box_play module does not import or call calculate_match_score.

    The module may mention the name in docstrings (as a warning), but it must
    never import or invoke it.  We check by inspecting the module's namespace
    and its AST call nodes.
    """
    import ast
    import inspect
    import lottery_api.models.star_box_play as star_mod

    # 1. The name must not be importable from the module namespace
    assert not hasattr(star_mod, "calculate_match_score"), \
        "star_box_play must not export calculate_match_score"

    # 2. The AST must contain no Call nodes whose func is 'calculate_match_score'
    source = inspect.getsource(star_mod)
    tree = ast.parse(source)
    bad_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(getattr(node, "func", None), ast.Name)
        and node.func.id == "calculate_match_score"
    ]
    assert bad_calls == [], \
        "star_box_play.py must not call calculate_match_score"


# ---------------------------------------------------------------------------
# 8. validate_star_input
# ---------------------------------------------------------------------------


def test_validate_correct_3star():
    validate_star_input([0, 5, 9], "3_STAR")  # no exception


def test_validate_correct_4star():
    validate_star_input([0, 1, 5, 6], "4_STAR")  # no exception


def test_validate_wrong_length():
    with pytest.raises(ValueError, match="expects"):
        validate_star_input([1, 2], "3_STAR")


def test_validate_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        validate_star_input([0, 5, 10], "3_STAR")


def test_validate_negative_digit():
    with pytest.raises(ValueError, match="out of range"):
        validate_star_input([-1, 5, 9], "3_STAR")


# ---------------------------------------------------------------------------
# 9. build_dryrun_row
# ---------------------------------------------------------------------------


def test_dryrun_row_dry_run_always_1():
    row = build_dryrun_row(
        "3_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [5, 6, 9], [5, 6, 9], bet_index=1
    )
    assert row["dry_run"] == 1, "dry_run must always be 1"


def test_dryrun_row_truth_level_labels():
    row = build_dryrun_row(
        "3_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [1, 2, 3], [5, 6, 9], bet_index=1
    )
    assert "DRY_RUN" in row["truth_level"]
    assert "BOX_PLAY" in row["truth_level"]


def test_dryrun_row_special_hit_zero():
    row = build_dryrun_row(
        "4_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [0, 1, 5, 6], [0, 1, 5, 6], bet_index=1
    )
    assert row["special_hit"] == 0


def test_dryrun_row_exact_hit_encoding():
    row = build_dryrun_row(
        "3_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [9, 6, 5], [5, 6, 9], bet_index=1
    )
    assert row["hit_count"] == 3        # pick_count on exact hit
    assert row["_exact_box_hit"] is True


def test_dryrun_row_miss_encoding():
    row = build_dryrun_row(
        "3_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [1, 2, 3], [5, 6, 9], bet_index=1
    )
    assert row["hit_count"] == 0
    assert row["_exact_box_hit"] is False


def test_dryrun_row_straight_play_blocked_documented():
    row = build_dryrun_row(
        "3_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [5, 6, 9], [5, 6, 9], bet_index=1
    )
    blocked = row["_straight_play_blocked"]
    assert "positional" in blocked.lower()
    assert len(blocked) > 20


def test_dryrun_row_serializable():
    """dry-run row must be JSON serialisable (no non-primitive types)."""
    row = build_dryrun_row(
        "4_STAR", "115000001", "2026-01-01", "test_strategy", "Test",
        "115000000", [0, 1, 5, 6], [0, 1, 5, 6], bet_index=1
    )
    # Replace bool with str-coercible value for JSON
    row["_exact_box_hit"] = bool(row["_exact_box_hit"])
    row["_straight_play_blocked"] = str(row["_straight_play_blocked"])
    row["predicted_numbers"] = list(row["predicted_numbers"])
    row["actual_numbers"] = list(row["actual_numbers"])
    row["hit_numbers"] = list(row["hit_numbers"])
    try:
        json.dumps(row)
    except TypeError as e:
        pytest.fail(f"dry-run row is not JSON serialisable: {e}")
