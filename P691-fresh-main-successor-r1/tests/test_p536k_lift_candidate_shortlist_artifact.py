"""Tests for P536K lift candidate shortlist artifact (read-only, no DB)."""

from __future__ import annotations

import json
from pathlib import Path

import analysis.p536k_lift_candidate_shortlist_artifact as K

REPO_ROOT = Path(__file__).resolve().parents[1]


def _matrix_row(lottery_type, strategy_id, window, pick_k, lift, family="acb"):
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "pick_k": pick_k,
        "window": window,
        "support_draws": window,
        "any_main_hit_rate": 0.3,
        "baseline_any_main_hit_rate": 0.2,
        "any_main_hit_lift": lift,
        "any_main_hit_log10_lift": None if lift is None else round(lift, 4),
        "feature_family": family,
    }


def _stability_row(lottery_type, combo_id, windows_present, rank):
    return {
        "lottery_type": lottery_type,
        "requested_budget": 1,
        "combo_id": combo_id,
        "windows_present": windows_present,
        "windows_present_count": len(windows_present),
        "avg_prize_signal_lift_across_present_windows": None,
        "per_window": {str(w): {"any_main_hit_lift": 1.1} for w in windows_present},
        "stability_rank": rank,
    }


def _cross_row(family, window, pick_k, lotteries):
    return {
        "feature_family": family,
        "window": window,
        "pick_k": pick_k,
        "lotteries": {lt: {"avg_any_main_hit_lift": 1.2} for lt in lotteries},
    }


def _synthetic_source() -> dict:
    return {
        "task_id": "P536C",
        "generated_at": "2026-07-08T00:00:00+00:00",
        "source": {
            "data_hash_sha256": "deadbeef",
            "row_counts_by_lottery": {"BIG_LOTTO": 10, "DAILY_539": 10, "POWER_LOTTO": 10},
        },
        "strategy_pick_matrix_lift_extension": [
            _matrix_row("BIG_LOTTO", "stableA", 300, 1, 1.5),
            _matrix_row("BIG_LOTTO", "stableA", 750, 1, 1.2),
            _matrix_row("BIG_LOTTO", "notLifted", 300, 1, 0.8),
            _matrix_row("BIG_LOTTO", "nullLift", 300, 1, None),
            _matrix_row("DAILY_539", "spikeA", 50, 1, 2.0),
            _matrix_row("DAILY_539", "spikeNotLifted", 50, 1, 0.5),
        ],
        "combination_stability_rank": [
            _stability_row("BIG_LOTTO", "comboA:1", [50, 300, 750], 1),
            _stability_row("BIG_LOTTO", "comboB:1", [300, 750], 2),
            _stability_row("BIG_LOTTO", "comboC:1", [50], 3),
        ],
        "cross_lottery_normalized_lift": [
            _cross_row("acb", 50, 1, ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]),
            _cross_row("fourier", 50, 1, ["BIG_LOTTO", "DAILY_539"]),
            _cross_row("markov", 50, 1, ["BIG_LOTTO"]),
        ],
    }


def _write_source(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic_p536c.json"
    path.write_text(json.dumps(_synthetic_source()), encoding="utf-8")
    return path


def test_stable_candidates_filter_window_and_positive_lift(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    stable = result["stable_300_750_review_candidates"]
    assert {r["strategy_id"] for r in stable} == {"stableA"}
    assert {r["window"] for r in stable} == {300, 750}
    assert all(r["lift"] > 1 for r in stable)


def test_spike_candidates_filter_window_50_and_positive_lift(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    spike = result["short_window_spike_review_candidates"]
    assert [r["strategy_id"] for r in spike] == ["spikeA"]
    assert spike[0]["window"] == 50
    assert spike[0]["caution_label"] == K.CAUTION_SPIKE


def test_combination_candidates_require_two_or_more_windows(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    combo_ids = {r["combo_id"] for r in result["combination_review_candidates"]}
    assert combo_ids == {"comboA:1", "comboB:1"}
    assert "comboC:1" not in combo_ids


def test_cross_lottery_candidates_require_two_or_more_lotteries(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    families = {r["feature_family"] for r in result["cross_lottery_review_candidates"]}
    assert families == {"acb", "fourier"}
    assert "markov" not in families


def test_no_values_invented_all_copied_from_source(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    stable = result["stable_300_750_review_candidates"][0]
    assert stable["lift"] == 1.5
    assert stable["observed_rate"] == 0.3
    assert stable["baseline_rate"] == 0.2


def test_provenance_disclaimer_matches_required_sentence(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    prov = result["provenance_and_limits"]
    assert prov["disclaimer_en"] == (
        "Historical replay review artifact only; not a prediction, betting edge, "
        "future-winning, or production-readiness claim."
    )
    assert prov["source_data_hash_sha256"] == "deadbeef"
    assert prov["derived_from_task_id"] == "P536C"


def test_provenance_counts_match_section_lengths(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    counts = result["provenance_and_limits"]["counts"]
    assert counts["stable_300_750_review_candidates"] == len(result["stable_300_750_review_candidates"])
    assert counts["short_window_spike_review_candidates"] == len(result["short_window_spike_review_candidates"])
    assert counts["combination_review_candidates"] == len(result["combination_review_candidates"])
    assert counts["cross_lottery_review_candidates"] == len(result["cross_lottery_review_candidates"])


def test_markdown_contains_disclaimer_and_all_sections(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    md = K.render_markdown(result)
    assert K.DISCLAIMER_EN in md
    assert "Stable 300/750 Review Candidates" in md
    assert "Short-Window Spike Review Candidates" in md
    assert "Combination Review Candidates" in md
    assert "Cross-Lottery Review Candidates" in md
    assert "Provenance & Limits" in md


def test_write_artifacts_creates_json_and_md_and_refuses_overwrite(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    K.write_artifacts(result, out_json, out_md)
    assert out_json.exists()
    assert out_md.exists()
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["task_id"] == "P536K"

    try:
        K.write_artifacts(result, out_json, out_md)
        assert False, "expected FileExistsError on overwrite attempt"
    except FileExistsError:
        pass


def test_json_and_md_size_under_5mb(tmp_path):
    result = K.run_shortlist(_write_source(tmp_path))
    out_json = tmp_path / "size.json"
    out_md = tmp_path / "size.md"
    K.write_artifacts(result, out_json, out_md)
    assert out_json.stat().st_size < 5 * 1024 * 1024
    assert out_md.stat().st_size < 5 * 1024 * 1024


# --- Integration check against the real, committed P536C artifact ---

def test_against_real_committed_p536c_artifact():
    """Guards against silent schema drift in the committed source artifact."""
    source_path = K.DEFAULT_SOURCE_ARTIFACT
    assert source_path.exists(), f"expected committed P536C artifact at {source_path}"

    result = K.run_shortlist(source_path)

    assert result["provenance_and_limits"]["derived_from_task_id"] == "P536C"
    counts = result["provenance_and_limits"]["counts"]
    # Expected counts computed directly from the committed artifact fields
    # (window in (300,750) & any_main_hit_lift>1 / window==50 & lift>1 /
    # windows_present_count>=2 / len(lotteries)>=2). Any change here signals
    # either the source artifact changed or the filter logic drifted.
    assert counts["stable_300_750_review_candidates"] == 177
    assert counts["short_window_spike_review_candidates"] == 90
    assert counts["combination_review_candidates"] == 133
    assert counts["cross_lottery_review_candidates"] == 60

    # Every candidate row must trace back to an actually-present field value.
    for row in result["stable_300_750_review_candidates"]:
        assert row["window"] in (300, 750)
        assert row["lift"] > 1
    for row in result["short_window_spike_review_candidates"]:
        assert row["window"] == 50
        assert row["lift"] > 1
    for row in result["combination_review_candidates"]:
        assert row["windows_present_count"] >= 2
    for row in result["cross_lottery_review_candidates"]:
        assert len(row["lotteries"]) >= 2


def test_no_db_module_imported():
    import inspect

    src = inspect.getsource(K)
    assert "sqlite3" not in src
    assert "import sqlite3" not in src
