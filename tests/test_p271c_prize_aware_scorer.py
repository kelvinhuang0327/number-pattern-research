"""
P271C — Standalone Prize-Aware Scorer Unit Tests

Tests the pure-function module lottery_api/prize_aware_scorer.py.
No DB, no replay pipeline, no strategy selection, no network/file/env access.
Existing M3+/replay scoring is unchanged; this module is a parallel
diagnostic track only (P271B design contract).

Fixture matrix source:
outputs/research/p271b_official_prize_rule_scoring_engine_design_20260611.json
  -> unit_test_fixture_matrix (33 fixtures: 14 POWER_LOTTO, 13 BIG_LOTTO, 6 DAILY_539)
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(REPO_ROOT, "lottery_api", "prize_aware_scorer.py")
P271B_JSON_PATH = os.path.join(
    REPO_ROOT, "outputs", "research",
    "p271b_official_prize_rule_scoring_engine_design_20260611.json",
)

import lottery_api.prize_aware_scorer as scorer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p271b_artifact():
    with open(P271B_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


POWER_VALID_MAIN = (1, 2, 3, 4, 5, 6)
POWER_VALID_ACTUAL = (1, 2, 3, 4, 5, 7)  # 5 hits
BIG_VALID_MAIN = (1, 2, 3, 4, 5, 6)
BIG_VALID_ACTUAL = (1, 2, 3, 4, 5, 7)  # 5 hits
D539_VALID_MAIN = (1, 2, 3, 4, 5)
D539_VALID_ACTUAL = (1, 2, 3, 4, 9)  # 4 hits


# ---------------------------------------------------------------------------
# 1. Module imports without side effects
# ---------------------------------------------------------------------------

def test_module_imports_without_side_effects():
    # Re-importing must not raise and must not perform I/O.
    mod = importlib.reload(scorer)
    assert mod is not None


# ---------------------------------------------------------------------------
# 2. Supported lottery-type constants
# ---------------------------------------------------------------------------

def test_supported_lottery_type_constants():
    assert scorer.SUPPORTED_LOTTERY_TYPES == ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")


# ---------------------------------------------------------------------------
# 3. Exact scoring_version
# ---------------------------------------------------------------------------

def test_scoring_version_exact():
    assert scorer.SCORING_VERSION == "prize_aware_v1"
    result = scorer.score_replay_row("DAILY_539", 5, 0)
    assert result["scoring_version"] == "prize_aware_v1"


# ---------------------------------------------------------------------------
# 4. Exact source verification status
# ---------------------------------------------------------------------------

def test_source_verification_status_exact():
    assert scorer.SOURCE_VERIFICATION_STATUS == "MANUAL_VERIFICATION_REQUIRED"
    result = scorer.score_replay_row("DAILY_539", 5, 0)
    assert result["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 5. Parallel-feature marker
# ---------------------------------------------------------------------------

def test_parallel_feature_marker_true():
    for lottery_type, hit_count, special_hit in [
        ("POWER_LOTTO", 6, 1),
        ("BIG_LOTTO", 6, 0),
        ("DAILY_539", 5, 0),
    ]:
        result = scorer.score_replay_row(lottery_type, hit_count, special_hit)
        assert result["parallel_feature"] is True


# ---------------------------------------------------------------------------
# 6. Existing M3+/replay changed flag remains false
# ---------------------------------------------------------------------------

def test_existing_m3_replay_scoring_changed_flag_false():
    for lottery_type, hit_count, special_hit in [
        ("POWER_LOTTO", 6, 1),
        ("BIG_LOTTO", 6, 0),
        ("DAILY_539", 5, 0),
    ]:
        result = scorer.score_replay_row(lottery_type, hit_count, special_hit)
        assert result["existing_m3_replay_scoring_changed"] is False


# ---------------------------------------------------------------------------
# 7 / 8. POWER_LOTTO tier combinations + no-prize boundary (P271B fixtures)
# ---------------------------------------------------------------------------

POWER_FIXTURES = [
    (6, 1, "POWER_FIRST_PRIZE", True, True),
    (6, 0, "POWER_SECOND_PRIZE", True, True),
    (5, 1, "POWER_THIRD_PRIZE", True, True),
    (5, 0, "POWER_FOURTH_PRIZE", True, True),
    (4, 1, "POWER_FIFTH_PRIZE", True, True),
    (4, 0, "POWER_SIXTH_PRIZE", True, True),
    (3, 1, "POWER_SEVENTH_PRIZE", True, True),
    (2, 1, "POWER_EIGHTH_PRIZE", True, False),
    (3, 0, "POWER_NINTH_PRIZE", True, True),
    (1, 1, "POWER_CONSOLATION_PRIZE", True, False),
    (2, 0, "POWER_NO_PRIZE", False, False),
    (1, 0, "POWER_NO_PRIZE", False, False),
    (0, 1, "POWER_NO_PRIZE", False, False),
    (0, 0, "POWER_NO_PRIZE", False, False),
]


@pytest.mark.parametrize(
    "hit_count,special_hit,expected_tier,expected_win,expected_m3_plus",
    POWER_FIXTURES,
)
def test_power_lotto_tier_combinations(
    hit_count, special_hit, expected_tier, expected_win, expected_m3_plus
):
    result = scorer.score_replay_row("POWER_LOTTO", hit_count, special_hit)
    assert result["tier_class"] == expected_tier
    assert result["prize_tier"] == expected_tier
    assert result["is_prize_aware_win"] == expected_win
    assert result["any_prize_aware_win"] == expected_win
    assert result["is_m3_plus"] == expected_m3_plus
    assert result["endpoint_flags"]["m3_plus_diagnostic"] == expected_m3_plus
    assert result["lottery_type"] == "POWER_LOTTO"


def test_power_lotto_no_prize_boundary_combinations():
    no_prize_cases = [(2, 0), (1, 0), (0, 1), (0, 0)]
    for hit_count, special_hit in no_prize_cases:
        result = scorer.score_replay_row("POWER_LOTTO", hit_count, special_hit)
        assert result["tier_class"] == "POWER_NO_PRIZE"
        assert result["any_prize_aware_win"] is False
        assert result["is_prize_aware_win"] is False


# ---------------------------------------------------------------------------
# 9 / 10 / 11. BIG_LOTTO tier combinations + special-hit semantics + no-prize
# ---------------------------------------------------------------------------

BIG_FIXTURES = [
    (6, 0, "BIG_FIRST_PRIZE", True, True),
    (6, 1, "BIG_FIRST_PRIZE", True, True),
    (5, 1, "BIG_SECOND_PRIZE", True, True),
    (5, 0, "BIG_THIRD_PRIZE", True, True),
    (4, 1, "BIG_FOURTH_PRIZE", True, True),
    (4, 0, "BIG_FIFTH_PRIZE", True, True),
    (3, 1, "BIG_SIXTH_PRIZE", True, True),
    (3, 0, "BIG_SEVENTH_PRIZE", True, True),
    (2, 1, "BIG_CONSOLATION_PRIZE", True, False),
    (2, 0, "BIG_NO_PRIZE", False, False),
    (1, 1, "BIG_NO_PRIZE", False, False),
    (1, 0, "BIG_NO_PRIZE", False, False),
    (0, 0, "BIG_NO_PRIZE", False, False),
]


@pytest.mark.parametrize(
    "hit_count,special_hit,expected_tier,expected_win,expected_m3_plus",
    BIG_FIXTURES,
)
def test_big_lotto_tier_combinations(
    hit_count, special_hit, expected_tier, expected_win, expected_m3_plus
):
    result = scorer.score_replay_row("BIG_LOTTO", hit_count, special_hit)
    assert result["tier_class"] == expected_tier
    assert result["prize_tier"] == expected_tier
    assert result["is_prize_aware_win"] == expected_win
    assert result["any_prize_aware_win"] == expected_win
    assert result["is_m3_plus"] == expected_m3_plus
    assert result["endpoint_flags"]["m3_plus_diagnostic"] == expected_m3_plus
    assert result["lottery_type"] == "BIG_LOTTO"


def test_big_lotto_special_hit_uses_six_predicted_main_numbers():
    # special_hit semantics: actual_special_number IN predicted_main_numbers
    predicted = (1, 2, 3, 4, 5, 6)
    actual_main = (10, 11, 12, 13, 14, 15)  # 0 hits

    # actual special is in predicted main -> special_hit = 1
    result_hit = scorer.score_prize_aware_ticket(
        "BIG_LOTTO",
        predicted_main_numbers=predicted,
        actual_main_numbers=actual_main,
        actual_special_number=6,
    )
    assert result_hit["special_hit"] == 1
    assert result_hit["main_hit_count"] == 0

    # actual special is NOT in predicted main -> special_hit = 0
    result_no_hit = scorer.score_prize_aware_ticket(
        "BIG_LOTTO",
        predicted_main_numbers=predicted,
        actual_main_numbers=actual_main,
        actual_special_number=20,
    )
    assert result_no_hit["special_hit"] == 0


def test_big_lotto_no_prize_boundary_combinations():
    no_prize_cases = [(2, 0), (1, 1), (1, 0), (0, 0)]
    for hit_count, special_hit in no_prize_cases:
        result = scorer.score_replay_row("BIG_LOTTO", hit_count, special_hit)
        assert result["tier_class"] == "BIG_NO_PRIZE"
        assert result["any_prize_aware_win"] is False


# ---------------------------------------------------------------------------
# 12 / 13. DAILY_539 tier combinations + no-prize boundary
# ---------------------------------------------------------------------------

D539_FIXTURES = [
    (5, "D539_FIRST_PRIZE", True, True),
    (4, "D539_SECOND_PRIZE", True, True),
    (3, "D539_THIRD_PRIZE", True, True),
    (2, "D539_FOURTH_PRIZE", True, False),
    (1, "D539_NO_PRIZE", False, False),
    (0, "D539_NO_PRIZE", False, False),
]


@pytest.mark.parametrize(
    "hit_count,expected_tier,expected_win,expected_m3_plus",
    D539_FIXTURES,
)
def test_daily_539_tier_combinations(hit_count, expected_tier, expected_win, expected_m3_plus):
    result = scorer.score_replay_row("DAILY_539", hit_count, 0)
    assert result["tier_class"] == expected_tier
    assert result["prize_tier"] == expected_tier
    assert result["is_prize_aware_win"] == expected_win
    assert result["any_prize_aware_win"] == expected_win
    assert result["is_m3_plus"] == expected_m3_plus
    assert result["lottery_type"] == "DAILY_539"
    assert result["second_zone_hit"] is None


def test_daily_539_no_prize_boundary_combinations():
    for hit_count in (1, 0):
        result = scorer.score_replay_row("DAILY_539", hit_count, 0)
        assert result["tier_class"] == "D539_NO_PRIZE"
        assert result["any_prize_aware_win"] is False


# ---------------------------------------------------------------------------
# 14. any_prize_aware_win consistency with prize_tier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lottery_type,hit_count,special_hit",
    [
        ("POWER_LOTTO", hc, sh)
        for hc, sh, _, _, _ in POWER_FIXTURES
    ]
    + [
        ("BIG_LOTTO", hc, sh)
        for hc, sh, _, _, _ in BIG_FIXTURES
    ]
    + [
        ("DAILY_539", hc, 0)
        for hc, _, _, _ in D539_FIXTURES
    ],
)
def test_any_prize_aware_win_consistency_with_prize_tier(lottery_type, hit_count, special_hit):
    result = scorer.score_replay_row(lottery_type, hit_count, special_hit)
    expected = not result["prize_tier"].endswith("_NO_PRIZE")
    assert result["any_prize_aware_win"] == expected
    assert result["is_prize_aware_win"] == expected
    assert scorer.is_any_prize_aware_win(lottery_type, hit_count, special_hit) == expected


# ---------------------------------------------------------------------------
# 15. endpoint_flags consistency
# ---------------------------------------------------------------------------

def test_endpoint_flags_consistency():
    # POWER: consolation_or_above = hit_count >= 1 AND special_hit == 1
    r = scorer.score_replay_row("POWER_LOTTO", 1, 1)
    assert r["endpoint_flags"]["consolation_or_above"] is True
    r = scorer.score_replay_row("POWER_LOTTO", 0, 1)
    assert r["endpoint_flags"]["consolation_or_above"] is False

    # BIG: consolation_or_above = hit_count == 2 AND special_hit == 1
    r = scorer.score_replay_row("BIG_LOTTO", 2, 1)
    assert r["endpoint_flags"]["consolation_or_above"] is True
    r = scorer.score_replay_row("BIG_LOTTO", 3, 1)
    assert r["endpoint_flags"]["consolation_or_above"] is False

    # DAILY_539: consolation_or_above = hit_count == 2
    r = scorer.score_replay_row("DAILY_539", 2, 0)
    assert r["endpoint_flags"]["consolation_or_above"] is True
    r = scorer.score_replay_row("DAILY_539", 3, 0)
    assert r["endpoint_flags"]["consolation_or_above"] is False

    for lottery_type, hit_count, special_hit in [
        ("POWER_LOTTO", 6, 1),
        ("BIG_LOTTO", 6, 0),
        ("DAILY_539", 5, 0),
    ]:
        result = scorer.score_replay_row(lottery_type, hit_count, special_hit)
        flags = result["endpoint_flags"]
        assert set(flags.keys()) == {
            "any_prize_aware_win",
            "m3_plus_diagnostic",
            "consolation_or_above",
        }
        assert flags["any_prize_aware_win"] == result["any_prize_aware_win"]
        assert flags["m3_plus_diagnostic"] == result["is_m3_plus"]


# ---------------------------------------------------------------------------
# 16 / 17. Input immutability + order independence
# ---------------------------------------------------------------------------

def test_input_immutability_lists_not_mutated():
    predicted = [6, 5, 4, 3, 2, 1]
    actual = [1, 2, 3, 4, 5, 7]
    predicted_copy = list(predicted)
    actual_copy = list(actual)

    scorer.score_prize_aware_ticket(
        "BIG_LOTTO",
        predicted_main_numbers=predicted,
        actual_main_numbers=actual,
        actual_special_number=20,
    )

    assert predicted == predicted_copy
    assert actual == actual_copy


def test_input_immutability_tuples_accepted():
    result = scorer.score_prize_aware_ticket(
        "DAILY_539",
        predicted_main_numbers=(1, 2, 3, 4, 5),
        actual_main_numbers=(1, 2, 3, 9, 10),
    )
    assert result["main_hit_count"] == 3


def test_order_independence_of_number_lists():
    predicted_sorted = [1, 2, 3, 4, 5, 6]
    predicted_shuffled = [6, 1, 4, 2, 5, 3]
    actual = [1, 2, 3, 4, 5, 7]

    r1 = scorer.score_prize_aware_ticket(
        "BIG_LOTTO",
        predicted_main_numbers=predicted_sorted,
        actual_main_numbers=actual,
        actual_special_number=20,
    )
    r2 = scorer.score_prize_aware_ticket(
        "BIG_LOTTO",
        predicted_main_numbers=predicted_shuffled,
        actual_main_numbers=list(reversed(actual)),
        actual_special_number=20,
    )
    assert r1["main_hit_count"] == r2["main_hit_count"]
    assert r1["tier_class"] == r2["tier_class"]


# ---------------------------------------------------------------------------
# 18. Duplicate-number rejection
# ---------------------------------------------------------------------------

def test_duplicate_number_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=(1, 1, 2, 3, 4),
            actual_main_numbers=(1, 2, 3, 4, 5),
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=(1, 2, 3, 4, 5),
            actual_main_numbers=(1, 2, 3, 4, 4),
        )


# ---------------------------------------------------------------------------
# 19. Wrong-count rejection
# ---------------------------------------------------------------------------

def test_wrong_count_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=(1, 2, 3, 4),  # 4 numbers, need 5
            actual_main_numbers=(1, 2, 3, 4, 5),
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "BIG_LOTTO",
            predicted_main_numbers=(1, 2, 3, 4, 5, 6, 7),  # 7 numbers, need 6
            actual_main_numbers=(1, 2, 3, 4, 5, 6),
            actual_special_number=20,
        )


# ---------------------------------------------------------------------------
# 20. Out-of-range rejection
# ---------------------------------------------------------------------------

def test_out_of_range_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=(1, 2, 3, 4, 40),  # 40 > 39
            actual_main_numbers=(1, 2, 3, 4, 5),
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "BIG_LOTTO",
            predicted_main_numbers=(0, 2, 3, 4, 5, 6),  # 0 < 1
            actual_main_numbers=(1, 2, 3, 4, 5, 6),
            actual_special_number=20,
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "POWER_LOTTO",
            predicted_main_numbers=(1, 2, 3, 4, 5, 39),  # 39 > 38
            actual_main_numbers=(1, 2, 3, 4, 5, 6),
            predicted_second_zone=1,
            actual_second_zone=1,
        )


# ---------------------------------------------------------------------------
# 21. Non-integer rejection
# ---------------------------------------------------------------------------

def test_non_integer_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=(1, 2, 3, 4, "5"),
            actual_main_numbers=(1, 2, 3, 4, 5),
        )
    with pytest.raises(ValueError):
        scorer.score_replay_row("DAILY_539", 3.0, 0)


# ---------------------------------------------------------------------------
# 22. bool rejection
# ---------------------------------------------------------------------------

def test_bool_rejection():
    with pytest.raises(ValueError):
        scorer.score_replay_row("DAILY_539", True, 0)
    with pytest.raises(ValueError):
        scorer.score_replay_row("DAILY_539", 3, False)
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=(1, 2, 3, 4, True),
            actual_main_numbers=(1, 2, 3, 4, 5),
        )


# ---------------------------------------------------------------------------
# 23. Unsupported-lottery rejection
# ---------------------------------------------------------------------------

def test_unsupported_lottery_rejection():
    with pytest.raises(ValueError):
        scorer.classify_tier("3_STAR", 3, 0)
    with pytest.raises(ValueError):
        scorer.score_replay_row("UNKNOWN_GAME", 3, 0)
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "UNKNOWN_GAME",
            predicted_main_numbers=(1, 2, 3, 4, 5),
            actual_main_numbers=(1, 2, 3, 4, 5),
        )


# ---------------------------------------------------------------------------
# 24 / 25. Missing/unexpected POWER second-zone & special-number rejection
# ---------------------------------------------------------------------------

def test_missing_power_second_zone_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "POWER_LOTTO",
            predicted_main_numbers=POWER_VALID_MAIN,
            actual_main_numbers=POWER_VALID_ACTUAL,
            predicted_second_zone=1,
            actual_second_zone=None,
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "POWER_LOTTO",
            predicted_main_numbers=POWER_VALID_MAIN,
            actual_main_numbers=POWER_VALID_ACTUAL,
            predicted_second_zone=None,
            actual_second_zone=1,
        )


def test_unexpected_power_special_number_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "POWER_LOTTO",
            predicted_main_numbers=POWER_VALID_MAIN,
            actual_main_numbers=POWER_VALID_ACTUAL,
            predicted_second_zone=1,
            actual_second_zone=1,
            actual_special_number=5,
        )


# ---------------------------------------------------------------------------
# 26 / 27 / 28. BIG_LOTTO special-number rejections
# ---------------------------------------------------------------------------

def test_missing_big_special_number_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "BIG_LOTTO",
            predicted_main_numbers=BIG_VALID_MAIN,
            actual_main_numbers=BIG_VALID_ACTUAL,
            actual_special_number=None,
        )


def test_unexpected_big_second_zone_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "BIG_LOTTO",
            predicted_main_numbers=BIG_VALID_MAIN,
            actual_main_numbers=BIG_VALID_ACTUAL,
            predicted_second_zone=1,
            actual_special_number=20,
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "BIG_LOTTO",
            predicted_main_numbers=BIG_VALID_MAIN,
            actual_main_numbers=BIG_VALID_ACTUAL,
            actual_second_zone=1,
            actual_special_number=20,
        )


def test_big_actual_special_main_overlap_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "BIG_LOTTO",
            predicted_main_numbers=BIG_VALID_MAIN,
            actual_main_numbers=BIG_VALID_ACTUAL,
            actual_special_number=BIG_VALID_ACTUAL[0],  # overlaps actual main
        )


# ---------------------------------------------------------------------------
# 29. Unexpected DAILY_539 auxiliary-field rejection
# ---------------------------------------------------------------------------

def test_unexpected_daily_539_auxiliary_field_rejection():
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=D539_VALID_MAIN,
            actual_main_numbers=D539_VALID_ACTUAL,
            predicted_second_zone=1,
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=D539_VALID_MAIN,
            actual_main_numbers=D539_VALID_ACTUAL,
            actual_second_zone=1,
        )
    with pytest.raises(ValueError):
        scorer.score_prize_aware_ticket(
            "DAILY_539",
            predicted_main_numbers=D539_VALID_MAIN,
            actual_main_numbers=D539_VALID_ACTUAL,
            actual_special_number=10,
        )


# ---------------------------------------------------------------------------
# 30. No DB/replay/strategy imports
# ---------------------------------------------------------------------------

def test_no_db_replay_strategy_imports():
    with open(MODULE_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    forbidden_substrings = (
        "lottery_api.routes",
        "lottery_api.engine",
        "lottery_api.data",
        "replay",
        "registry",
        "sqlite3",
        "database",
    )

    imported_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.append(node.module)

    for name in imported_names:
        lowered = name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, f"forbidden import found: {name}"


# ---------------------------------------------------------------------------
# 31. No file/network/subprocess/environment access
# ---------------------------------------------------------------------------

def _source_without_module_docstring() -> str:
    with open(MODULE_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    docstring = ast.get_docstring(tree)
    if docstring:
        source = source.replace(docstring, "", 1)
    return source


def test_no_file_network_subprocess_environment_access():
    source = _source_without_module_docstring()

    forbidden_tokens = (
        "open(",
        "os.environ",
        "os.getenv",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "httpx",
        "sqlite3",
        "print(",
        "logging",
    )
    for token in forbidden_tokens:
        assert token not in source, f"forbidden token found in module: {token}"

    assert "import os" not in source
    assert "import sys" not in source


# ---------------------------------------------------------------------------
# 32. No prize amount / EV / ROI / recommendation output
# ---------------------------------------------------------------------------

def test_no_prize_amount_ev_roi_recommendation_output():
    forbidden_keys = (
        "prize_amount",
        "ev",
        "roi",
        "recommendation",
        "expected_value",
        "bet_advice",
        "kelly",
    )
    for lottery_type, hit_count, special_hit in [
        ("POWER_LOTTO", 6, 1),
        ("BIG_LOTTO", 6, 0),
        ("DAILY_539", 5, 0),
    ]:
        result = scorer.score_replay_row(lottery_type, hit_count, special_hit)
        keys_lower = {k.lower() for k in result.keys()}
        for forbidden in forbidden_keys:
            assert forbidden not in keys_lower

    source = _source_without_module_docstring().lower()
    for forbidden in ("prize_amount", "expected_value", "kelly", "bet_advice"):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# 33. P271B fixture-matrix traceability
# ---------------------------------------------------------------------------

def test_p271b_fixture_matrix_traceability(p271b_artifact):
    fixture_matrix = p271b_artifact["unit_test_fixture_matrix"]

    power_fixtures = fixture_matrix["POWER_LOTTO"]
    big_fixtures = fixture_matrix["BIG_LOTTO"]
    d539_fixtures = fixture_matrix["DAILY_539"]

    total_fixtures = len(power_fixtures) + len(big_fixtures) + len(d539_fixtures)
    assert total_fixtures == 33
    assert len(power_fixtures) == 14
    assert len(big_fixtures) == 13
    assert len(d539_fixtures) == 6

    # Every POWER_LOTTO fixture has an executable counterpart in this file.
    executable_power = {(hc, sh) for hc, sh, _, _, _ in POWER_FIXTURES}
    for fx in power_fixtures:
        key = (fx["hit_count"], fx["special_hit"])
        assert key in executable_power, f"POWER_LOTTO fixture not covered: {fx}"
        result = scorer.score_replay_row("POWER_LOTTO", *key)
        assert result["tier_class"] == fx["expected_tier"]
        assert result["any_prize_aware_win"] == fx["expected_win"]
        assert result["is_m3_plus"] == fx["expected_m3_plus"]

    # Every BIG_LOTTO fixture has an executable counterpart in this file.
    executable_big = {(hc, sh) for hc, sh, _, _, _ in BIG_FIXTURES}
    for fx in big_fixtures:
        key = (fx["hit_count"], fx["special_hit"])
        assert key in executable_big, f"BIG_LOTTO fixture not covered: {fx}"
        result = scorer.score_replay_row("BIG_LOTTO", *key)
        assert result["tier_class"] == fx["expected_tier"]
        assert result["any_prize_aware_win"] == fx["expected_win"]
        assert result["is_m3_plus"] == fx["expected_m3_plus"]

    # Every DAILY_539 fixture has an executable counterpart in this file.
    executable_d539 = {hc for hc, _, _, _ in D539_FIXTURES}
    for fx in d539_fixtures:
        hc = fx["hit_count"]
        assert hc in executable_d539, f"DAILY_539 fixture not covered: {fx}"
        assert fx["special_hit"] == 0
        result = scorer.score_replay_row("DAILY_539", hc, 0)
        assert result["tier_class"] == fx["expected_tier"]
        assert result["any_prize_aware_win"] == fx["expected_win"]
        assert result["is_m3_plus"] == fx["expected_m3_plus"]


# ---------------------------------------------------------------------------
# Extra: pure-function / determinism + coexistence guarantee
# ---------------------------------------------------------------------------

def test_pure_function_determinism():
    a = scorer.score_replay_row("BIG_LOTTO", 4, 1)
    b = scorer.score_replay_row("BIG_LOTTO", 4, 1)
    assert a == b


def test_coexistence_guarantee_is_m3_plus_always_present():
    for lottery_type, hit_count, special_hit in [
        ("POWER_LOTTO", 2, 1),  # prize-aware win, not M3+
        ("BIG_LOTTO", 2, 1),  # prize-aware win, not M3+
        ("DAILY_539", 2, 0),  # prize-aware win, not M3+
    ]:
        result = scorer.score_replay_row(lottery_type, hit_count, special_hit)
        assert result["any_prize_aware_win"] is True
        assert result["is_m3_plus"] is False
