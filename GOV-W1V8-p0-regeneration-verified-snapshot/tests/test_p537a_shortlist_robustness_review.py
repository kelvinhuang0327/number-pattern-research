"""Tests for P537A shortlist robustness review artifact (read-only, no DB)."""

from __future__ import annotations

import json
from pathlib import Path

import analysis.p537a_shortlist_robustness_review as R

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
    }


def _spike_row(strategy_id="spikeA"):
    row = _stable_row(strategy_id=strategy_id, window=50, lift=2.0)
    row["caution_label"] = "SHORT-WINDOW SPIKE — review only, not a stable pattern; do not treat as a validated edge."
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
        "per_window": {str(w): {"any_main_hit_lift": 1.1} for w in windows_present},
        "stability_rank": 1,
        "why_included": "synthetic",
        "caution_label": "Historical replay review only; not a prediction or betting edge.",
    }


def _cross_row(family="acb", lotteries=("BIG_LOTTO", "DAILY_539")):
    return {
        "feature_family": family,
        "window": 50,
        "pick_k": 1,
        "lotteries": {lt: {"avg_any_main_hit_lift": 1.2} for lt in lotteries},
        "why_included": "synthetic",
        "caution_label": "Historical replay review only; not a prediction or betting edge.",
    }


def _synthetic_k_source(data_hash="deadbeef") -> dict:
    return {
        "schema_version": "1.0",
        "task_id": "P536K",
        "extends_task_id": "P536C",
        "generated_at": "2026-07-08T13:12:26+00:00",
        "classification": "P536K_LIFT_CANDIDATE_SHORTLIST_READY",
        "stable_300_750_review_candidates": [_stable_row()],
        "short_window_spike_review_candidates": [_spike_row()],
        "combination_review_candidates": [
            _combo_row("comboA:1", [300, 750], 1.05),
            _combo_row("comboB:1", [50, 300, 750], None),
        ],
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


def _synthetic_c_source(data_hash="deadbeef") -> dict:
    return {
        "schema_version": "1.0",
        "task_id": "P536C",
        "extends_task_id": "P333",
        "generated_at": "2026-07-08T07:42:01+00:00",
        "classification": "P536C_SUCCESS_MATRIX_LIFT_EXTENSION_READY",
        "source": {
            "data_hash_sha256": data_hash,
            "row_counts_by_lottery": {"BIG_LOTTO": 10, "DAILY_539": 10, "POWER_LOTTO": 10},
        },
    }


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_sources(tmp_path: Path, k_hash="deadbeef", c_hash="deadbeef") -> tuple[Path, Path]:
    k_path = _write(tmp_path, "synthetic_p536k.json", _synthetic_k_source(k_hash))
    c_path = _write(tmp_path, "synthetic_p536c.json", _synthetic_c_source(c_hash))
    return k_path, c_path


def test_stable_candidates_relabeled_and_passed_through(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    stable = result["stable_candidates_for_owner_review"]
    assert len(stable) == 1
    assert stable[0]["strategy_id"] == "stableA"
    assert stable[0]["review_label"] == R.LABEL_STABLE
    assert stable[0]["lift"] == 1.5


def test_short_window_spike_relabeled_and_passed_through(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    spike = result["short_window_spike_caution_list"]
    assert len(spike) == 1
    assert spike[0]["strategy_id"] == "spikeA"
    assert spike[0]["review_label"] == R.LABEL_SHORT_WINDOW


def test_combination_split_by_avg_prize_signal_lift_presence(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    followup = result["combination_candidates_for_followup"]
    insufficient = result["insufficient_or_ambiguous_candidates"]

    assert [r["combo_id"] for r in followup] == ["comboA:1"]
    assert followup[0]["review_label"] == R.LABEL_COMBINATION
    assert followup[0]["avg_prize_signal_lift_across_present_windows"] == 1.05

    assert [r["combo_id"] for r in insufficient] == ["comboB:1"]
    assert insufficient[0]["review_label"] == R.LABEL_INSUFFICIENT
    assert insufficient[0]["insufficient_reason"] == R.INSUFFICIENT_REASON_COMBO


def test_cross_lottery_relabeled_and_passed_through(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    cross = result["cross_lottery_candidates_for_followup"]
    assert len(cross) == 1
    assert cross[0]["feature_family"] == "acb"
    assert cross[0]["review_label"] == R.LABEL_CROSS_LOTTERY


def test_hash_chain_verified_true_when_hashes_match(tmp_path):
    k_path, c_path = _write_sources(tmp_path, k_hash="samehash", c_hash="samehash")
    result = R.run_review(k_path, c_path)
    assert result["provenance_and_limits"]["hash_chain_verified"] is True


def test_hash_chain_verified_false_when_hashes_differ(tmp_path):
    k_path, c_path = _write_sources(tmp_path, k_hash="hashA", c_hash="hashB")
    result = R.run_review(k_path, c_path)
    assert result["provenance_and_limits"]["hash_chain_verified"] is False


def test_no_values_invented_all_copied_from_source(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    stable = result["stable_candidates_for_owner_review"][0]
    assert stable["observed_rate"] == 0.3
    assert stable["baseline_rate"] == 0.2


def test_provenance_disclaimer_matches_required_sentence(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    prov = result["provenance_and_limits"]
    assert prov["disclaimer_en"] == (
        "Historical replay review artifact only; not a prediction, betting edge, "
        "future-winning, or production-readiness claim."
    )
    assert prov["derived_from_task_id"] == "P536K"
    assert prov["upstream_task_id"] == "P536C"


def test_provenance_counts_match_section_lengths(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    counts = result["provenance_and_limits"]["counts"]
    assert counts["stable_candidates_for_owner_review"] == len(result["stable_candidates_for_owner_review"])
    assert counts["short_window_spike_caution_list"] == len(result["short_window_spike_caution_list"])
    assert counts["combination_candidates_for_followup"] == len(result["combination_candidates_for_followup"])
    assert counts["cross_lottery_candidates_for_followup"] == len(result["cross_lottery_candidates_for_followup"])
    assert counts["insufficient_or_ambiguous_candidates"] == len(result["insufficient_or_ambiguous_candidates"])


def test_markdown_contains_disclaimer_and_all_sections(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    md = R.render_markdown(result)
    assert R.DISCLAIMER_EN in md
    assert "Stable Candidates For Owner Review" in md
    assert "Short-Window Spike Caution List" in md
    assert "Combination Candidates For Followup" in md
    assert "Cross-Lottery Candidates For Followup" in md
    assert "Insufficient Or Ambiguous Candidates" in md
    assert "Provenance & Limits" in md


def test_write_artifacts_creates_json_and_md_and_refuses_overwrite(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    R.write_artifacts(result, out_json, out_md)
    assert out_json.exists()
    assert out_md.exists()
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["task_id"] == "P537A"

    try:
        R.write_artifacts(result, out_json, out_md)
        assert False, "expected FileExistsError on overwrite attempt"
    except FileExistsError:
        pass


def test_json_and_md_size_under_5mb(tmp_path):
    k_path, c_path = _write_sources(tmp_path)
    result = R.run_review(k_path, c_path)
    out_json = tmp_path / "size.json"
    out_md = tmp_path / "size.md"
    R.write_artifacts(result, out_json, out_md)
    assert out_json.stat().st_size < 5 * 1024 * 1024
    assert out_md.stat().st_size < 5 * 1024 * 1024


# --- Integration check against the real, committed P536K/P536C artifacts ---

def test_against_real_committed_p536k_and_p536c_artifacts():
    """Guards against silent schema drift in the committed source artifacts."""
    k_path = R.DEFAULT_K_SOURCE_ARTIFACT
    c_path = R.DEFAULT_C_SOURCE_ARTIFACT
    assert k_path.exists(), f"expected committed P536K artifact at {k_path}"
    assert c_path.exists(), f"expected committed P536C artifact at {c_path}"

    result = R.run_review(k_path, c_path)

    assert result["provenance_and_limits"]["derived_from_task_id"] == "P536K"
    assert result["provenance_and_limits"]["upstream_task_id"] == "P536C"
    assert result["provenance_and_limits"]["hash_chain_verified"] is True

    counts = result["provenance_and_limits"]["counts"]
    # Expected counts computed directly from the committed P536K artifact.
    # Any change here signals either the source artifact changed or the
    # relabel/split logic drifted.
    assert counts["stable_candidates_for_owner_review"] == 177
    assert counts["short_window_spike_caution_list"] == 90
    assert counts["combination_candidates_for_followup"] == 102
    assert counts["cross_lottery_candidates_for_followup"] == 60
    assert counts["insufficient_or_ambiguous_candidates"] == 31

    total_combo_rows = (
        counts["combination_candidates_for_followup"]
        + counts["insufficient_or_ambiguous_candidates"]
    )
    assert total_combo_rows == 133  # matches P536K's own combination_review_candidates count

    for row in result["combination_candidates_for_followup"]:
        assert row["avg_prize_signal_lift_across_present_windows"] is not None
    for row in result["insufficient_or_ambiguous_candidates"]:
        assert row["avg_prize_signal_lift_across_present_windows"] is None
        assert row["insufficient_reason"] == R.INSUFFICIENT_REASON_COMBO


def test_no_db_module_imported():
    import inspect

    src = inspect.getsource(R)
    assert "sqlite3" not in src
    assert "import sqlite3" not in src
