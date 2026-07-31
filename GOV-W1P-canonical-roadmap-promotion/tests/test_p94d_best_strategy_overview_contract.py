"""P94D Best Strategy Overview Contract Tests — 15+ tests."""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "replay", "p94d_best_strategy_overview_contract_20260527.json")
MD_PATH = os.path.join(REPO_ROOT, "docs", "replay", "p94d_best_strategy_overview_contract_20260527.md")


@pytest.fixture(scope="module")
def contract():
    with open(JSON_PATH) as f:
        return json.load(f)


# ── Artifact existence ─────────────────────────────────────────────────────────

def test_json_artifact_exists():
    assert os.path.isfile(JSON_PATH), f"JSON artifact missing: {JSON_PATH}"


def test_md_artifact_exists():
    assert os.path.isfile(MD_PATH), f"MD artifact missing: {MD_PATH}"


# ── Classification ─────────────────────────────────────────────────────────────

def test_classification_correct(contract):
    assert contract["final_classification"] == "P94D_BEST_STRATEGY_OVERVIEW_CONTRACT_READY"


# ── Lottery type coverage ──────────────────────────────────────────────────────

def test_contract_includes_all_three_lottery_types(contract):
    sources = contract["data_sources"]
    assert "BIG_LOTTO" in sources
    assert "POWER_LOTTO" in sources
    assert "DAILY_539" in sources


# ── Bet count coverage ─────────────────────────────────────────────────────────

def test_contract_includes_all_bet_counts(contract):
    bet_counts = contract["ranking_filters"]["bet_count"]
    for bc in [1, 2, 3, 5]:
        assert bc in bet_counts, f"bet_count {bc} missing from ranking_filters"


# ── Observation window coverage ────────────────────────────────────────────────

def test_contract_includes_all_observation_windows(contract):
    windows = contract["ranking_filters"]["observation_window"]
    for w in [30, 100, 500, 1500]:
        assert w in windows, f"window {w} missing from ranking_filters"


# ── Ranking card schema ────────────────────────────────────────────────────────

def test_ranking_card_schema_exists(contract):
    schema = contract.get("ranking_card_schema")
    assert schema is not None
    fields = schema.get("fields", {})
    required = ["rank", "strategy_id", "display_name", "lottery_type", "bet_count",
                "observation_window", "lifecycle_status", "source_category", "row_backed",
                "benchmark_only", "adapter_generated", "rejected_or_offline_caveat",
                "sample_size", "m3plus_rate", "avg_hit_count", "m4plus_rate",
                "zero_hit_rate", "special_hit_rate", "stability_across_windows", "warning_flags"]
    for f in required:
        assert f in fields, f"ranking_card_schema missing field: {f}"


# ── Next prediction schema ─────────────────────────────────────────────────────

def test_next_prediction_schema_exists(contract):
    schema = contract.get("next_prediction_schema")
    assert schema is not None
    fields = schema.get("fields", {})
    required = ["next_draw_lottery_type", "strategy_id", "bet_count", "predicted_bets",
                "predicted_special", "adapter_name", "generation_status", "disclaimer"]
    for f in required:
        assert f in fields, f"next_prediction_schema missing field: {f}"


# ── POWER_LOTTO special_hit_rate ───────────────────────────────────────────────

def test_power_lotto_special_hit_rate_required(contract):
    rules = contract["ranking_card_schema"]["lottery_type_rules"]
    pl = rules.get("POWER_LOTTO", {})
    assert pl.get("special_hit_rate") == "required", "POWER_LOTTO special_hit_rate must be required"
    assert pl.get("special_number") is True


def test_power_lotto_next_prediction_special(contract):
    rules = contract["next_prediction_schema"]["lottery_type_rules"]
    pl = rules.get("POWER_LOTTO", {})
    assert pl.get("predicted_special") == "required_integer_1_to_8"


# ── DAILY_539 no-special rule ──────────────────────────────────────────────────

def test_daily539_no_special_in_ranking_schema(contract):
    rules = contract["ranking_card_schema"]["lottery_type_rules"]
    d539 = rules.get("DAILY_539", {})
    assert d539.get("special_number") is False
    assert d539.get("special_hit_rate") is None


def test_daily539_no_special_in_prediction_schema(contract):
    rules = contract["next_prediction_schema"]["lottery_type_rules"]
    d539 = rules.get("DAILY_539", {})
    assert d539.get("predicted_special") is None


# ── BIG_LOTTO 6-number rule ────────────────────────────────────────────────────

def test_biglotto_six_main_numbers(contract):
    rules = contract["ranking_card_schema"]["lottery_type_rules"]
    bl = rules.get("BIG_LOTTO", {})
    assert bl.get("main_numbers") == 6
    assert bl.get("special_number") is False
    assert bl.get("special_hit_rate") is None


def test_biglotto_no_special_in_prediction_schema(contract):
    rules = contract["next_prediction_schema"]["lottery_type_rules"]
    bl = rules.get("BIG_LOTTO", {})
    assert bl.get("predicted_bets_length") == 6
    assert bl.get("predicted_special") is None


# ── Rejected/offline caveat ────────────────────────────────────────────────────

def test_rejected_offline_caveat_exists(contract):
    policy = contract.get("rejected_offline_policy")
    assert policy is not None
    assert policy.get("may_appear_in_ranking") is True
    caveat_field = contract["ranking_card_schema"]["fields"]["rejected_or_offline_caveat"]
    enum_values = caveat_field.get("enum", [])
    assert "REJECTED: historical benchmark only" in enum_values
    assert "OFFLINE: decommissioned" in enum_values
    assert None in enum_values


def test_rejected_offline_default_generation_status(contract):
    policy = contract["rejected_offline_policy"]
    assert policy["default_generation_status"] == "REJECTED_REPLAY_ONLY"


# ── Benchmark vs next prediction distinction ───────────────────────────────────

def test_benchmark_ranking_vs_next_prediction_distinction(contract):
    ui = contract.get("ui_placement", {})
    overview = ui.get("best_strategy_overview_page", {})
    assert "ranking_grid" in overview.get("components", [])
    assert "next_prediction_panel" in overview.get("card_expand", [])
    replay = ui.get("raw_replay_list_page", {})
    assert replay.get("no_ranking") is True
    assert replay.get("no_next_number_recommendation") is True


# ── Unsupported bet count policy ───────────────────────────────────────────────

def test_unsupported_bet_count_policy_exists(contract):
    policy = contract.get("unsupported_bet_count_policy")
    assert policy is not None
    assert policy.get("generation_status") == "UNSUPPORTED_BET_COUNT"
    assert policy.get("fabrication") == "never"
    assert policy.get("next_prediction_panel") == "disabled"
    assert policy.get("ranking_visibility") is not None


# ── No DB-write instruction ────────────────────────────────────────────────────

def test_no_db_write_instruction(contract):
    assert contract.get("db_writes") is False
    assert contract.get("replay_row_changes") == 0
    assert contract.get("lifecycle_promotions") == 0
    p95 = contract.get("recommended_p95_implementation", {})
    assert p95.get("db_mutations") == "none"


# ── Recommended P95 implementation ────────────────────────────────────────────

def test_recommended_p95_implementation_exists(contract):
    p95 = contract.get("recommended_p95_implementation")
    assert p95 is not None
    endpoints = p95.get("api_endpoints", [])
    assert len(endpoints) >= 2
    paths = [e["path"] for e in endpoints]
    assert any("/api/best-strategy-overview" in p for p in paths)
    assert any("next-prediction" in p for p in paths)
    frontend = p95.get("frontend", {})
    assert frontend.get("new_tab") is not None
    assert frontend.get("graceful_source_unavailable") is not None


# ── Generation status enum completeness ───────────────────────────────────────

def test_generation_status_enum_complete(contract):
    field = contract["next_prediction_schema"]["fields"]["generation_status"]
    enum_values = field.get("enum", [])
    required = ["READY", "ADAPTER_MISSING", "UNSUPPORTED_BET_COUNT", "REJECTED_REPLAY_ONLY", "SOURCE_UNAVAILABLE"]
    for v in required:
        assert v in enum_values, f"generation_status missing: {v}"


# ── Warning flags completeness ─────────────────────────────────────────────────

def test_warning_flags_enum_complete(contract):
    flags = contract.get("warning_flag_triggers", {})
    required = ["SMALL_SAMPLE", "SHORT_WINDOW_ONLY", "BENCHMARK_ONLY", "REJECTED_STRATEGY", "NO_ADAPTER", "UNSUPPORTED_BET_COUNT"]
    for f in required:
        assert f in flags, f"warning_flag_triggers missing: {f}"


# ── DAILY_539 planning-only source_unavailable ─────────────────────────────────

def test_daily539_source_unavailable(contract):
    sources = contract["data_sources"]
    d539 = sources.get("DAILY_539", {})
    assert d539.get("availability") == "SOURCE_UNAVAILABLE"
    assert d539.get("pr_status") == "OPEN"


# ── Stability score formula ────────────────────────────────────────────────────

def test_stability_score_formula_defined(contract):
    formula = contract.get("stability_score_formula")
    assert formula is not None
    assert "formula" in formula
    assert "null_condition" in formula


# ── Ranking metric default ─────────────────────────────────────────────────────

def test_ranking_metric_default_is_m3plus(contract):
    metric = contract["ranking_filters"]["ranking_metric"]
    assert metric.get("default") == "m3plus_rate"
    assert "m4plus_rate" in metric.get("options", [])
    assert "stability_score" in metric.get("options", [])
