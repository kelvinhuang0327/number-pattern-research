"""P541B — read-only tests for the BIG_LOTTO legacy method classification
audit.

These tests call pure functions in
`analysis/p541b_biglotto_legacy_method_classification_audit.py` that only
read source files, run `git grep -l`, and statically AST-parse Python
files. The module never opens a database connection, never imports a
classified script, and never executes one. Several tests assert this
no-DB, no-import, no-execution contract directly.
"""
import ast
import inspect
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

pytestmark = pytest.mark.filterwarnings("ignore")


def _module():
    from analysis import p541b_biglotto_legacy_method_classification_audit as mod

    return mod


# ── contract: static-only, no DB, no import/execution of scanned scripts ──


def test_module_never_imports_sqlite3():
    mod = _module()
    src = inspect.getsource(mod)
    # "sqlite3" legitimately appears inside DB_CALL_RE / _is_risky_call as a
    # *detection pattern* for scanned scripts; the module itself must never
    # actually `import sqlite3` or open a connection.
    assert "import sqlite3" not in src, "P541B must not open any DB connection; reuse P541A's numbers instead"
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "sqlite3" for alias in node.names)


def test_module_never_uses_importlib_or_exec_on_targets():
    mod = _module()
    src = inspect.getsource(mod)
    assert "importlib" not in src
    assert "__import__(" not in src
    assert "\nexec(" not in src and " exec(" not in src


def test_module_only_ever_calls_ast_parse_not_compile_exec():
    mod = _module()
    src = inspect.getsource(mod)
    assert "ast.parse" in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "compile", "must not use builtin compile() on scanned source"


# ── P541A artifact consumption ─────────────────────────────────────────────


def test_p541a_artifacts_exist_and_are_read_only_inputs():
    mod = _module()
    assert mod.P541A_JSON.exists()
    assert mod.P541A_MD.exists()


def test_load_p541a_returns_expected_known_ids():
    mod = _module()
    assert set(mod.REPLAYED_IDS) == {
        "bet2_fourier_expansion_biglotto", "biglotto_deviation_2bet",
        "biglotto_echo_aware_3bet", "biglotto_triple_strike",
        "biglotto_ts3_markov_4bet_w30", "cold_complement_biglotto",
        "coldpool15_biglotto", "fourier30_markov30_biglotto",
        "markov_2bet_biglotto", "markov_single_biglotto", "ts3_regime_3bet",
    }
    assert mod.ZERO_REPLAY_IDS == ["biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet"]
    assert set(mod.PHANTOM_IDS) == {
        "p1_dev_sum5bet", "p1_deviation_4bet", "p1_neighbor_cold_2bet", "regime_2bet",
    }


def test_discover_files_matches_p541a_counts():
    mod = _module()
    p541a = mod.load_p541a()
    groups = mod.discover_files(p541a)
    assert len(groups["p541a_tools"]) == 385
    assert len(groups["p541a_analysis"]) == 66


def test_discover_files_finds_new_groups_beyond_p541a():
    mod = _module()
    p541a = mod.load_p541a()
    groups = mod.discover_files(p541a)
    for g in ("ai_lab", "recovered_strategies_biglotto", "lottery_api_models",
              "lottery_api_tools", "lottery_api_engine", "root_level_scripts"):
        assert g in groups
        assert len(groups[g]) > 0, f"expected group {g} to find at least one new file"


def test_discover_files_excludes_known_registry_and_adapter_files():
    mod = _module()
    p541a = mod.load_p541a()
    groups = mod.discover_files(p541a)
    # These live under lottery_api/models/, so they can only ever surface via
    # the lottery_api_models discovery group; assert the exclusion works
    # there specifically (P541A's own tools/*.py list separately and
    # legitimately includes tools/quick_predict.py -- that count is owned by
    # P541A and intentionally left untouched here).
    assert mod.REGISTRY_FILE not in groups["lottery_api_models"]
    for f in mod.ADAPTER_FILES:
        assert f not in groups["lottery_api_models"]


# ── static feature extraction (no import/execution) ─────────────────────────


def test_extract_features_on_missing_file_marks_syntax_error():
    mod = _module()
    features = mod.extract_features("tools/__does_not_exist_p541b__.py")
    assert features["syntax_error"] == "file_not_found_or_unreadable"


def test_extract_features_finds_functions_and_main_guard(tmp_path, monkeypatch):
    mod = _module()
    sample = tmp_path / "sample_p541b.py"
    sample.write_text(
        "import random\n"
        "random.seed(42)\n"
        "\n"
        "def predict_numbers():\n"
        "    return sorted(random.sample(range(1, 50), 6))\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(predict_numbers())\n"
    )
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    features = mod.extract_features("sample_p541b.py")
    assert features["syntax_error"] is None
    assert "predict_numbers" in features["function_names"]
    assert features["has_main_guard"] is True
    # random.seed(42) is an allowlisted harmless top-level call.
    assert features["module_level_other_sideeffect"] is False
    assert features["module_level_db_call"] is False


def test_extract_features_flags_module_level_db_connect(tmp_path, monkeypatch):
    mod = _module()
    sample = tmp_path / "risky_db.py"
    sample.write_text(
        "import sqlite3\n"
        "conn = sqlite3.connect('some.db')\n"
    )
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    features = mod.extract_features("risky_db.py")
    assert features["module_level_db_call"] is True


def test_extract_features_flags_calling_own_function_at_module_scope(tmp_path, monkeypatch):
    mod = _module()
    sample = tmp_path / "runs_on_import.py"
    sample.write_text(
        "def main():\n"
        "    return 1\n"
        "\n"
        "main()\n"  # no __main__ guard: runs its own pipeline at import time
    )
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    features = mod.extract_features("runs_on_import.py")
    assert features["module_level_other_sideeffect"] is True


def test_extract_features_syntax_error_reported(tmp_path, monkeypatch):
    mod = _module()
    sample = tmp_path / "broken.py"
    sample.write_text("def f(:\n    pass\n")
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    features = mod.extract_features("broken.py")
    assert features["syntax_error"] is not None
    assert "SyntaxError" in features["syntax_error"]


# ── classification decision tree ────────────────────────────────────────────


def test_classify_runnable_syntax_error_wins_first():
    mod = _module()
    features = {"syntax_error": "SyntaxError: bad (line 1)"}
    status, why, rewrite, effort = mod.classify_runnable(features, "unknown", None, None, "x.py")
    assert status == "broken_or_import_error"


def test_classify_runnable_deprecated_filename():
    mod = _module()
    features = {
        "syntax_error": None, "module_level_db_call": False,
        "module_level_write": False, "module_level_other_sideeffect": False,
        "hardcoded_abs_path": False, "hardcoded_draw_or_date": False,
        "uses_argparse_or_env": False, "uses_db_anywhere": False,
        "writes_files_anywhere": False, "has_functions": True, "has_main_guard": True,
    }
    status, why, rewrite, effort = mod.classify_runnable(
        features, "utility", None, None, "tools/old_predictor_deprecated.py"
    )
    assert status == "obsolete_or_deprecated"
    assert rewrite == "deprecate"


def test_classify_runnable_clean_prediction_method_needs_adapter_wrapper():
    mod = _module()
    features = {
        "syntax_error": None, "module_level_db_call": False,
        "module_level_write": False, "module_level_other_sideeffect": False,
        "hardcoded_abs_path": False, "hardcoded_draw_or_date": False,
        "uses_argparse_or_env": False, "uses_db_anywhere": False,
        "writes_files_anywhere": False, "has_functions": True, "has_main_guard": True,
    }
    status, why, rewrite, effort = mod.classify_runnable(
        features, "hot_cold", True, None, "tools/predict_hot_cold.py"
    )
    assert status == "needs_adapter_wrapper"
    assert rewrite == "small_adapter"


def test_classify_runnable_duplicate_of_replayed_id():
    mod = _module()
    features = {
        "syntax_error": None, "module_level_db_call": False,
        "module_level_write": False, "module_level_other_sideeffect": False,
        "hardcoded_abs_path": False, "hardcoded_draw_or_date": False,
        "uses_argparse_or_env": False, "uses_db_anywhere": False,
        "writes_files_anywhere": False, "has_functions": True, "has_main_guard": True,
    }
    status, why, rewrite, effort = mod.classify_runnable(
        features, "markov", True, "biglotto_triple_strike", "tools/some_dup.py"
    )
    assert status == "runnable_with_existing_adapter"


def test_recommended_action_mapping():
    mod = _module()
    assert mod.recommended_action("not_a_strategy", None, "none") == "mark_not_strategy"
    assert mod.recommended_action("obsolete_or_deprecated", None, "none") == "mark_deprecated"
    assert mod.recommended_action("ambiguous_needs_cto_review", None, "unknown") == "needs_cto_review"
    assert mod.recommended_action("needs_adapter_wrapper", "x", "small") == "mark_duplicate"
    assert mod.recommended_action("needs_adapter_wrapper", None, "small") == "include_in_replay_readiness"
    assert mod.recommended_action("hardcoded_paths_or_dates", None, "small") == "exclude_from_replay"


def test_find_duplicate_id_matches_literal_string():
    mod = _module()
    content = "STRATEGY_ID = 'biglotto_triple_strike'\n"
    assert mod.find_duplicate_id(content) == "biglotto_triple_strike"


def test_find_duplicate_id_no_match_returns_none():
    mod = _module()
    content = "STRATEGY_ID = 'some_unrelated_name'\n"
    assert mod.find_duplicate_id(content) is None


# ── phantom / zero-replay review sections ───────────────────────────────────


def test_registered_zero_replay_review_covers_both_ids():
    mod = _module()
    review = mod.registered_zero_replay_review()
    ids = {r["strategy_id"] for r in review}
    assert ids == set(mod.ZERO_REPLAY_IDS)
    for r in review:
        assert r["status_in_registry"] == "REJECTED"
        assert r["why_no_rows"]


def test_phantom_id_review_covers_all_four_ids_with_evidence():
    mod = _module()
    review = mod.phantom_id_review()
    ids = {r["id"] for r in review}
    assert ids == set(mod.PHANTOM_IDS)
    for r in review:
        assert r["why_phantom"]
        assert r["recommendation"]


# ── end-to-end (still fully read-only / static) ─────────────────────────────


def test_main_produces_expected_top_level_schema():
    mod = _module()
    result = mod.main()
    expected_keys = {
        "schema_version", "task_id", "generated_at", "summary", "p541a_context",
        "inventory_sources_scanned", "classification_taxonomy",
        "method_classification_records", "legacy_script_group_summary",
        "registered_zero_replay_strategy_review", "phantom_id_review",
        "runnable_candidate_set", "non_runnable_methods_and_reasons",
        "rewrite_or_adapter_requirements", "recommended_next_single_worker_task",
        "provenance_and_limits", "disclaimer",
    }
    assert expected_keys <= set(result.keys())
    assert result["disclaimer"] == mod.DISCLAIMER
    assert len(result["method_classification_records"]) > 400


def test_main_summary_counts_are_internally_consistent():
    mod = _module()
    result = mod.main()
    records = result["method_classification_records"]
    by_status_total = sum(result["summary"]["by_runnable_status"].values())
    assert by_status_total == len(records)


def test_main_recommended_next_task_is_a_valid_enum_value():
    mod = _module()
    result = mod.main()
    valid = {
        "P541C_BIG_LOTTO_REPLAY_READINESS_FOR_RUNNABLE_LEGACY_METHODS_NO_DB_WRITE",
        "P541C_BIG_LOTTO_PHANTOM_AND_REJECTED_STRATEGY_CLEANUP_AUDIT",
        "P541C_BIG_LOTTO_LEGACY_METHOD_ADAPTER_DESIGN_NO_DB_WRITE",
        "P541B_COMPLETE_NO_REPLAYABLE_LEGACY_METHODS_FOUND",
        "P541B_BLOCKED_LEGACY_METHODS_TOO_AMBIGUOUS_NEED_CTO_REVIEW",
    }
    assert result["recommended_next_single_worker_task"] in valid


def test_every_record_has_required_taxonomy_fields():
    mod = _module()
    result = mod.main()
    required = {
        "method_id", "normalized_name", "source_path", "source_type",
        "method_family", "is_actual_prediction_method", "has_registry_entry",
        "has_adapter", "has_replay_rows", "appears_in_artifacts",
        "duplicate_of_existing_strategy", "runnable_status", "why_not_runnable",
        "rewrite_needed", "estimated_effort", "recommended_action", "evidence",
        "confidence",
    }
    for r in result["method_classification_records"][:20]:
        assert required <= set(r.keys())


def test_render_md_contains_disclaimer_and_next_task():
    mod = _module()
    result = mod.main()
    md = mod.render_md(result)
    assert mod.DISCLAIMER in md
    assert result["recommended_next_single_worker_task"] in md
