"""Tests for P538A strategy candidate evaluation readiness artifact (read-only, no DB)."""

from __future__ import annotations

import json
from pathlib import Path

import analysis.p538a_strategy_candidate_evaluation_readiness as R

REPO_ROOT = Path(__file__).resolve().parents[1]


def _stable_row(strategy_id="stableA", window=300, lift=1.5):
    return {
        "lottery_type": "BIG_LOTTO",
        "window": window,
        "strategy_id": strategy_id,
        "feature_family": "acb",
        "pick_k": 1,
        "metric": "any_main_hit",
        "observed_rate": 0.3,
        "baseline_rate": 0.2,
        "lift": lift,
        "log10_lift": 0.1,
        "support_draws": window,
        "why_included": "synthetic",
        "caution_label": "Historical replay review only; not a prediction or betting edge.",
        "review_label": "stable_review_candidate",
    }


def _spike_row(strategy_id="spikeA"):
    row = _stable_row(strategy_id=strategy_id, window=50, lift=2.0)
    row["review_label"] = "short_window_caution"
    return row


def _combo_row(combo_id, windows_present, avg_prize_signal_lift):
    return {
        "lottery_type": "BIG_LOTTO",
        "combo_id": combo_id,
        "requested_budget": 1,
        "windows_present": windows_present,
        "windows_present_count": len(windows_present),
        "metric": "prize_signal_and_any_main_hit_per_window",
        "avg_prize_signal_lift_across_present_windows": avg_prize_signal_lift,
        "per_window": {str(w): {"any_main_hit_lift": 1.1, "support_draws": w} for w in windows_present},
        "stability_rank": 1,
        "why_included": "synthetic",
        "caution_label": "Historical replay review only; not a prediction or betting edge.",
        "review_label": "combination_review_candidate",
    }


def _insufficient_row(combo_id="comboB:1"):
    row = _combo_row(combo_id, [50, 300, 750], None)
    row["review_label"] = "insufficient_context"
    row["insufficient_reason"] = "synthetic reason"
    return row


def _cross_row(family="acb", lotteries=("BIG_LOTTO", "DAILY_539")):
    return {
        "feature_family": family,
        "window": 50,
        "pick_k": 1,
        "lotteries": {lt: {"avg_any_main_hit_lift": 1.2, "strategy_count": 2} for lt in lotteries},
        "why_included": "synthetic",
        "caution_label": "Historical replay review only; not a prediction or betting edge.",
        "review_label": "cross_lottery_review_candidate",
    }


def _synthetic_p537a(data_hash="deadbeef") -> dict:
    return {
        "schema_version": "1.0",
        "task_id": "P537A",
        "extends_task_id": "P536K",
        "upstream_task_id": "P536C",
        "generated_at": "2026-07-09T02:23:29+00:00",
        "classification": "P537A_SHORTLIST_ROBUSTNESS_REVIEW_READY",
        "stable_candidates_for_owner_review": [_stable_row()],
        "short_window_spike_caution_list": [_spike_row()],
        "combination_candidates_for_followup": [_combo_row("comboA:1", [300, 750], 1.05)],
        "cross_lottery_candidates_for_followup": [_cross_row()],
        "insufficient_or_ambiguous_candidates": [_insufficient_row()],
        "provenance_and_limits": {
            "derived_from_artifact": "outputs/research/p536k_lift_candidate_shortlist_20260708.json",
            "derived_from_task_id": "P536K",
            "upstream_artifact": "outputs/research/p536c_success_matrix_lift_extension_20260708.json",
            "upstream_task_id": "P536C",
            "source_generated_at": "2026-07-08T13:12:26+00:00",
            "upstream_source_generated_at": "2026-07-08T07:42:01+00:00",
            "source_data_hash_sha256": data_hash,
            "upstream_data_hash_sha256": data_hash,
            "hash_chain_verified": True,
            "source_row_counts_by_lottery": {"BIG_LOTTO": 10, "DAILY_539": 10, "POWER_LOTTO": 10},
            "selection_method": "synthetic",
            "counts": {
                "stable_candidates_for_owner_review": 1,
                "short_window_spike_caution_list": 1,
                "combination_candidates_for_followup": 1,
                "cross_lottery_candidates_for_followup": 1,
                "insufficient_or_ambiguous_candidates": 1,
            },
            "limitations": ["synthetic limitation"],
            "disclaimer_en": R.DISCLAIMER_EN,
        },
    }


def _synthetic_p536k(data_hash="deadbeef") -> dict:
    return {
        "schema_version": "1.0",
        "task_id": "P536K",
        "extends_task_id": "P536C",
        "generated_at": "2026-07-08T13:12:26+00:00",
        "classification": "P536K_LIFT_CANDIDATE_SHORTLIST_READY",
        "stable_300_750_review_candidates": [_stable_row()],
        "short_window_spike_review_candidates": [_spike_row()],
        "combination_review_candidates": [_combo_row("comboA:1", [300, 750], 1.05), _insufficient_row()],
        "cross_lottery_review_candidates": [_cross_row()],
        "provenance_and_limits": {
            "derived_from_artifact": "outputs/research/p536c_success_matrix_lift_extension_20260708.json",
            "derived_from_task_id": "P536C",
            "source_generated_at": "2026-07-08T07:42:01+00:00",
            "source_data_hash_sha256": data_hash,
            "source_row_counts_by_lottery": {"BIG_LOTTO": 10, "DAILY_539": 10, "POWER_LOTTO": 10},
            "selection_method": "synthetic",
            "counts": {
                "stable_300_750_review_candidates": 1,
                "short_window_spike_review_candidates": 1,
                "combination_review_candidates": 2,
                "cross_lottery_review_candidates": 1,
            },
            "limitations": ["synthetic limitation"],
            "disclaimer_en": R.DISCLAIMER_EN,
        },
    }


def _matrix_row_with_draw_range():
    return {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": "stableA",
        "pick_k": 1,
        "window": 300,
        "support_draws": 300,
        "latest_target_draw": "115000054",
        "earliest_target_draw": "115000005",
        "any_main_hit_rate": 0.3,
        "feature_family": "acb",
    }


def _combo_leaderboard_row_with_draw_range():
    return {
        "lottery_type": "BIG_LOTTO",
        "window": 300,
        "support_draws": 300,
        "latest_target_draw": "115000053",
        "earliest_target_draw": "115000004",
        "combo_id": "comboA:1",
        "requested_budget": 1,
    }


def _synthetic_p536c(data_hash="deadbeef", include_draw_range=True) -> dict:
    matrix_row = _matrix_row_with_draw_range()
    combo_row = _combo_leaderboard_row_with_draw_range()
    if not include_draw_range:
        matrix_row = {k: v for k, v in matrix_row.items() if k not in ("earliest_target_draw", "latest_target_draw")}
        combo_row = {k: v for k, v in combo_row.items() if k not in ("earliest_target_draw", "latest_target_draw")}
    return {
        "schema_version": "1.0",
        "task_id": "P536C",
        "extends_task_id": "P333",
        "generated_at": "2026-07-08T07:42:01+00:00",
        "classification": "P536C_SUCCESS_MATRIX_LIFT_EXTENSION_READY",
        "window_policy": {
            "primary_windows": [50, 300, 750],
            "minimum_support_draws": 30,
        },
        "source": {
            "data_hash_sha256": data_hash,
            "row_counts_by_lottery": {"BIG_LOTTO": 10, "DAILY_539": 10, "POWER_LOTTO": 10},
        },
        "strategy_pick_matrix_lift_extension": [matrix_row],
        "cross_lottery_normalized_lift": [
            {
                "feature_family": "acb",
                "window": 50,
                "pick_k": 1,
                "lotteries": {"BIG_LOTTO": {"strategy_count": 2, "avg_any_main_hit_lift": 1.2}},
            }
        ],
        "combination_leaderboard_with_lift": [combo_row],
        "combination_stability_rank": [
            {
                "lottery_type": "BIG_LOTTO",
                "combo_id": "comboA:1",
                "windows_present": [300, 750],
                "stability_rank": 1,
            }
        ],
    }


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_sources(
    tmp_path: Path, p537a_hash="deadbeef", p536k_hash="deadbeef", p536c_hash="deadbeef", include_draw_range=True
) -> tuple[Path, Path, Path]:
    p537a_path = _write(tmp_path, "synthetic_p537a.json", _synthetic_p537a(p537a_hash))
    p536k_path = _write(tmp_path, "synthetic_p536k.json", _synthetic_p536k(p536k_hash))
    p536c_path = _write(
        tmp_path, "synthetic_p536c.json", _synthetic_p536c(p536c_hash, include_draw_range=include_draw_range)
    )
    return p537a_path, p536k_path, p536c_path


# --- artifact_schema_capability_map -------------------------------------------


def test_schema_capability_map_has_all_three_artifacts(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    schema_map = result["artifact_schema_capability_map"]
    assert set(schema_map.keys()) == {"P537A", "P536K", "P536C"}
    assert schema_map["P537A"]["task_id"] == "P537A"
    assert schema_map["P536K"]["task_id"] == "P536K"
    assert schema_map["P536C"]["task_id"] == "P536C"


def test_schema_capability_map_records_row_counts_and_fields(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    section = result["artifact_schema_capability_map"]["P537A"]["sections"]["stable_candidates_for_owner_review"]
    assert section["row_count"] == 1
    assert "strategy_id" in section["fields_present"]
    assert "lift" in section["fields_present"]


def test_schema_capability_map_records_p536c_window_policy(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    assert result["artifact_schema_capability_map"]["P536C"]["window_policy"]["minimum_support_draws"] == 30


# --- candidate_groups_for_next_stage_review -----------------------------------


def test_candidate_groups_cover_all_five_named_groups(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    groups = result["candidate_groups_for_next_stage_review"]
    assert set(groups.keys()) == {
        "stable_review_candidates",
        "short_window_spike_cautions",
        "combination_followup_candidates",
        "cross_lottery_followup_candidates",
        "insufficient_context_candidates",
    }


def test_candidate_groups_counts_match_source_sections(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    groups = result["candidate_groups_for_next_stage_review"]
    assert groups["stable_review_candidates"]["count"] == 1
    assert groups["short_window_spike_cautions"]["count"] == 1
    assert groups["combination_followup_candidates"]["count"] == 1
    assert groups["cross_lottery_followup_candidates"]["count"] == 1
    assert groups["insufficient_context_candidates"]["count"] == 1


def test_candidate_groups_sample_rows_are_verbatim_from_source(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    stable_sample = result["candidate_groups_for_next_stage_review"]["stable_review_candidates"][
        "sample_rows_verbatim"
    ]
    assert stable_sample[0]["strategy_id"] == "stableA"
    assert stable_sample[0]["lift"] == 1.5


def test_cross_lottery_group_has_lottery_participation_not_lottery_type_breakdown(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    cross_group = result["candidate_groups_for_next_stage_review"]["cross_lottery_followup_candidates"]
    assert "lottery_type_participation_counts" in cross_group
    assert cross_group["lottery_type_participation_counts"] == {"BIG_LOTTO": 1, "DAILY_539": 1}


# --- rolling_or_out_of_sample_feasibility -------------------------------------


def test_feasibility_stable_group_feasible_via_join_when_p536c_has_draw_range(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path, include_draw_range=True)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    entry = result["rolling_or_out_of_sample_feasibility"]["stable_review_candidates"]
    assert entry["feasible_directly_from_p537a_or_p536k"] is False
    assert entry["feasible_via_join_to_p536c"] is True
    assert "earliest_target_draw" in entry["recoverable_fields_via_join"]


def test_feasibility_stable_group_not_feasible_when_p536c_lacks_draw_range(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path, include_draw_range=False)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    entry = result["rolling_or_out_of_sample_feasibility"]["stable_review_candidates"]
    assert entry["feasible_via_join_to_p536c"] is False
    assert entry["recoverable_fields_via_join"] == []


def test_feasibility_combination_group_joins_on_combo_id(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    entry = result["rolling_or_out_of_sample_feasibility"]["combination_followup_candidates"]
    assert entry["join_key_if_via_p536c"] == ["lottery_type", "combo_id", "window"]
    assert entry["feasible_via_join_to_p536c"] is True


def test_feasibility_cross_lottery_group_always_not_feasible(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    entry = result["rolling_or_out_of_sample_feasibility"]["cross_lottery_followup_candidates"]
    assert entry["feasible_directly_from_p537a_or_p536k"] is False
    assert entry["feasible_via_join_to_p536c"] is False
    assert entry["join_target"] is None


def test_feasibility_insufficient_context_group_always_not_feasible(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    entry = result["rolling_or_out_of_sample_feasibility"]["insufficient_context_candidates"]
    assert entry["feasible_directly_from_p537a_or_p536k"] is False
    assert entry["feasible_via_join_to_p536c"] is False


def test_feasibility_includes_artifact_wide_note(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    note = result["rolling_or_out_of_sample_feasibility"]["artifact_wide_note"]
    assert "per-draw outcome rows" in note


# --- missing_fields_or_blockers -----------------------------------------------


def test_missing_fields_checklist_flags_target_draw_absent_everywhere(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    checklist = result["missing_fields_or_blockers"]["field_presence_checklist"]
    target_draw_row = next(r for r in checklist if r["required_field"] == "target draw or draw index")
    assert target_draw_row["present_in_stable_short_window_groups"] is False
    assert target_draw_row["present_in_combination_group"] is False
    assert target_draw_row["present_in_cross_lottery_group"] is False


def test_missing_fields_checklist_flags_identity_and_lottery_type_present(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    checklist = result["missing_fields_or_blockers"]["field_presence_checklist"]
    identity_row = next(r for r in checklist if "identity" in r["required_field"])
    assert identity_row["present_in_stable_short_window_groups"] is True
    lottery_row = next(r for r in checklist if r["required_field"] == "lottery_type")
    assert lottery_row["present_in_stable_short_window_groups"] is True
    assert lottery_row["present_in_cross_lottery_group"] is False


def test_missing_fields_has_hard_blockers_and_db_flags(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    blockers = result["missing_fields_or_blockers"]
    assert len(blockers["hard_blockers_for_rolling_or_out_of_sample_evaluation"]) >= 1
    assert blockers["db_access_required_for_full_resolution"] is True
    assert blockers["db_access_performed_in_this_task"] is False


# --- recommended_next_single_worker_task --------------------------------------


def test_recommended_next_task_is_read_only_and_excludes_blocked_groups(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    next_task = result["recommended_next_single_worker_task"]
    assert next_task["not_run_in_this_task"] is True
    assert any("cross_lottery" in item for item in next_task["excluded_from_this_proposed_task"])
    assert any("insufficient_context" in item for item in next_task["excluded_from_this_proposed_task"])
    assert "read-only" in next_task["scope"]


def test_recommended_next_task_references_window_policy_minimum_support(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    assert "30" in result["recommended_next_single_worker_task"]["scope"]


# --- provenance_and_limits ------------------------------------------------------


def test_provenance_replay_data_hash_chain_verified_when_all_equal(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(
        tmp_path, p537a_hash="samehash", p536k_hash="samehash", p536c_hash="samehash"
    )
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    assert result["provenance_and_limits"]["replay_data_hash_chain"]["verified_equal_across_all_three"] is True


def test_provenance_replay_data_hash_chain_not_verified_when_mismatched(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(
        tmp_path, p537a_hash="hashA", p536k_hash="hashB", p536c_hash="hashC"
    )
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    assert result["provenance_and_limits"]["replay_data_hash_chain"]["verified_equal_across_all_three"] is False


def test_provenance_disclaimer_matches_required_sentence(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    assert result["provenance_and_limits"]["disclaimer_en"] == (
        "Historical replay review artifact only; not a prediction, betting edge, "
        "future-winning, or production-readiness claim."
    )


def test_provenance_records_file_sha256_for_each_source_artifact(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    source_artifacts = result["provenance_and_limits"]["source_artifacts"]
    assert source_artifacts["P537A"]["file_sha256"] == R._sha256_file(p537a_path)
    assert source_artifacts["P536K"]["file_sha256"] == R._sha256_file(p536k_path)
    assert source_artifacts["P536C"]["file_sha256"] == R._sha256_file(p536c_path)


# --- write_artifacts / markdown / size ------------------------------------------


def test_markdown_contains_disclaimer_and_all_required_sections(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    md = R.render_markdown(result)
    assert R.DISCLAIMER_EN in md
    assert "Artifact Schema Capability Map" in md
    assert "Candidate Groups For Next-Stage Review" in md
    assert "Rolling / Out-of-Sample Feasibility" in md
    assert "Missing Fields Or Blockers" in md
    assert "Recommended Next Single-Worker Task" in md
    assert "Provenance & Limits" in md


def test_write_artifacts_creates_json_and_md_and_refuses_overwrite(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    R.write_artifacts(result, out_json, out_md)
    assert out_json.exists()
    assert out_md.exists()
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["task_id"] == "P538A"

    try:
        R.write_artifacts(result, out_json, out_md)
        assert False, "expected FileExistsError on overwrite attempt"
    except FileExistsError:
        pass


def test_json_and_md_size_under_5mb(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    out_json = tmp_path / "size.json"
    out_md = tmp_path / "size.md"
    R.write_artifacts(result, out_json, out_md)
    assert out_json.stat().st_size < 5 * 1024 * 1024
    assert out_md.stat().st_size < 5 * 1024 * 1024


def test_result_is_json_serializable(tmp_path):
    p537a_path, p536k_path, p536c_path = _write_sources(tmp_path)
    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)
    json.dumps(result)  # must not raise


# --- Integration check against the real, committed P537A/P536K/P536C artifacts -


def test_against_real_committed_artifacts():
    """Guards against silent schema drift in the committed source artifacts."""
    p537a_path = R.DEFAULT_P537A_ARTIFACT
    p536k_path = R.DEFAULT_P536K_ARTIFACT
    p536c_path = R.DEFAULT_P536C_ARTIFACT
    assert p537a_path.exists(), f"expected committed P537A artifact at {p537a_path}"
    assert p536k_path.exists(), f"expected committed P536K artifact at {p536k_path}"
    assert p536c_path.exists(), f"expected committed P536C artifact at {p536c_path}"

    result = R.run_readiness_assessment(p537a_path, p536k_path, p536c_path)

    assert result["task_id"] == "P538A"
    assert result["source_task_ids"] == ["P537A", "P536K", "P536C"]
    assert result["provenance_and_limits"]["replay_data_hash_chain"]["verified_equal_across_all_three"] is True

    groups = result["candidate_groups_for_next_stage_review"]
    assert groups["stable_review_candidates"]["count"] == 177
    assert groups["short_window_spike_cautions"]["count"] == 90
    assert groups["combination_followup_candidates"]["count"] == 102
    assert groups["cross_lottery_followup_candidates"]["count"] == 60
    assert groups["insufficient_context_candidates"]["count"] == 31

    # Real P536C strategy_pick_matrix_lift_extension does carry the draw-range
    # fields, so a join-based OOS feasibility should be recoverable for the
    # strategy-level groups against the real committed artifacts.
    feasibility = result["rolling_or_out_of_sample_feasibility"]
    assert feasibility["stable_review_candidates"]["feasible_via_join_to_p536c"] is True
    assert feasibility["combination_followup_candidates"]["feasible_via_join_to_p536c"] is True
    assert feasibility["cross_lottery_followup_candidates"]["feasible_via_join_to_p536c"] is False


def test_no_db_module_imported():
    import sys

    assert "sqlite3" not in sys.modules or not any(
        mod.startswith("analysis.p538a") for mod in sys.modules if "sqlite3" in mod
    )
    assert not hasattr(R, "sqlite3")
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(R))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "sqlite3" not in imported_modules


def test_no_forbidden_route_ui_or_promotion_terms():
    import inspect

    src = inspect.getsource(R)
    for forbidden in ("app.include_router", "FastAPI(", "betting_advice=True", "strategy_promotion=True"):
        assert forbidden not in src
