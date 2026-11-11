"""Tests for P35 prediction rebuild feasibility auditor."""
import os
import tempfile

import pytest

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,
    FEASIBILITY_BLOCKED_LEAKAGE_RISK,
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
)
from wbc_backend.recommendation.p35_prediction_rebuild_feasibility_auditor import (
    evaluate_2024_oof_rebuild_feasibility,
    scan_feature_pipeline_candidates,
    scan_model_training_candidates,
    scan_oof_generation_candidates,
    summarize_prediction_rebuild_feasibility,
)

# Repo root relative to this test file
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TEST_DIR)
_MODELS_DIR = os.path.join(_REPO_ROOT, "wbc_backend", "models")
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "scripts")
_WBC_BACKEND_DIR = os.path.join(_REPO_ROOT, "wbc_backend")


# ---------------------------------------------------------------------------
# scan_feature_pipeline_candidates
# ---------------------------------------------------------------------------


def test_scan_feature_pipeline_candidates_returns_list():
    result = scan_feature_pipeline_candidates([_MODELS_DIR, _SCRIPTS_DIR])
    assert isinstance(result, list)


def test_scan_feature_pipeline_candidates_each_has_path():
    result = scan_feature_pipeline_candidates([_MODELS_DIR, _WBC_BACKEND_DIR])
    for item in result:
        assert isinstance(item, str)
        assert len(item) > 0


def test_scan_feature_pipeline_candidates_nonexistent_dir():
    result = scan_feature_pipeline_candidates(["/nonexistent/path"])
    assert result == []


def test_scan_feature_pipeline_finds_models():
    # wbc_backend/models has trainer.py etc. which contain FEATURE_NAMES
    result = scan_feature_pipeline_candidates([_WBC_BACKEND_DIR])
    assert len(result) >= 1, f"Expected at least 1 feature pipeline, got: {result}"


# ---------------------------------------------------------------------------
# scan_model_training_candidates
# ---------------------------------------------------------------------------


def test_scan_model_training_candidates_returns_list():
    result = scan_model_training_candidates([_MODELS_DIR])
    assert isinstance(result, list)


def test_scan_model_training_candidates_finds_trainer():
    result = scan_model_training_candidates([_MODELS_DIR])
    assert len(result) >= 1, f"Expected model training files, got: {result}"


def test_scan_model_training_candidates_each_is_string():
    result = scan_model_training_candidates([_WBC_BACKEND_DIR, _SCRIPTS_DIR])
    for item in result:
        assert isinstance(item, str)


# ---------------------------------------------------------------------------
# scan_oof_generation_candidates
# ---------------------------------------------------------------------------


def test_scan_oof_generation_candidates_returns_list():
    result = scan_oof_generation_candidates([_SCRIPTS_DIR, _MODELS_DIR])
    assert isinstance(result, list)


def test_scan_oof_generation_candidates_finds_walk_forward_script():
    result = scan_oof_generation_candidates([_SCRIPTS_DIR, _WBC_BACKEND_DIR])
    assert len(result) >= 1, f"Expected OOF generation candidates, got: {result}"


def test_scan_oof_generation_candidates_includes_known_script():
    # scripts/run_p13_walk_forward_logistic_oof.py should be detected
    oof_script = os.path.join(_SCRIPTS_DIR, "run_p13_walk_forward_logistic_oof.py")
    if not os.path.isfile(oof_script):
        pytest.skip("OOF script not found in scripts/")
    result = scan_oof_generation_candidates([_SCRIPTS_DIR])
    # At least one result should reference this file
    result_basenames = [os.path.basename(p) for p in result]
    assert "run_p13_walk_forward_logistic_oof.py" in result_basenames


# ---------------------------------------------------------------------------
# evaluate_2024_oof_rebuild_feasibility
# ---------------------------------------------------------------------------


def test_evaluate_feasibility_adapter_missing():
    """Core test: pipeline exists but 2024 adapter is missing."""
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    assert result.feasibility_status == FEASIBILITY_BLOCKED_ADAPTER_MISSING


def test_evaluate_feasibility_feature_pipeline_found():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    assert result.feature_pipeline_found is True


def test_evaluate_feasibility_adapter_not_found():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    assert result.adapter_for_2024_format_found is False


def test_evaluate_feasibility_leakage_guard_found():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    # walk_forward_logistic.py has temporal separation
    assert result.leakage_guard_found is True


def test_evaluate_feasibility_time_aware_split_found():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    assert result.time_aware_split_found is True


def test_evaluate_feasibility_paper_only():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    assert result.paper_only is True
    assert result.production_ready is False
    assert result.season == 2024


def test_evaluate_feasibility_candidate_scripts_is_tuple():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    assert isinstance(result.candidate_scripts, tuple)
    assert isinstance(result.candidate_models, tuple)


def test_evaluate_feasibility_no_pipeline_in_empty_dir():
    """When scanning an empty temp dir, pipeline should not be found."""
    with tempfile.TemporaryDirectory() as tmp:
        result = evaluate_2024_oof_rebuild_feasibility(
            game_log_path="/nonexistent/game_log.csv",
            base_paths=[tmp],
        )
    assert result.feasibility_status == FEASIBILITY_BLOCKED_PIPELINE_MISSING


# ---------------------------------------------------------------------------
# summarize_prediction_rebuild_feasibility
# ---------------------------------------------------------------------------


def test_summarize_returns_string():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    summary = summarize_prediction_rebuild_feasibility(result)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_summarize_contains_feasibility_status():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    summary = summarize_prediction_rebuild_feasibility(result)
    assert FEASIBILITY_BLOCKED_ADAPTER_MISSING in summary


def test_summarize_contains_adapter_info():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    summary = summarize_prediction_rebuild_feasibility(result)
    # Must mention adapter status
    assert "adapter" in summary.lower() or "2024" in summary


def test_summarize_contains_paper_only():
    result = evaluate_2024_oof_rebuild_feasibility(
        game_log_path="/nonexistent/game_log.csv",
        base_paths=[_WBC_BACKEND_DIR, _SCRIPTS_DIR],
    )
    summary = summarize_prediction_rebuild_feasibility(result)
    assert "PAPER_ONLY" in summary or "paper_only" in summary.lower()
