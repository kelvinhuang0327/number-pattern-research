"""
P19 — Power Lotto Single Strategy Replay Dry-Run Tests.

Verifies the P19 script produces correct dry-run candidates for POWER_LOTTO:
- Real predicted_numbers from the fourier_rhythm_3bet adapter
- Real actual_numbers from the DB
- hit_count == len(hit_numbers)
- prediction_cutoff_date <= target_date
- No production DB writes
- counts_as_success always False
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT  = Path(__file__).resolve().parents[1]
_SCRIPT     = _REPO_ROOT / "scripts" / "p19_powerlotto_single_strategy_replay_dry_run.py"
_OUTPUT     = _REPO_ROOT / "outputs" / "replay" / "p19_powerlotto_single_strategy_replay_dry_run_20260520.json"
_DB_PATH    = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PROD_ROWS_BASELINE  = 12460  # updated post-P21B apply
PROD_ROWS_SNAPSHOT  = 4960  # frozen in P19 output JSON (captured pre-P19B)


@pytest.fixture(scope="module")
def output() -> dict:
    assert _OUTPUT.exists(), f"Output JSON not found: {_OUTPUT}"
    return json.loads(_OUTPUT.read_text())


# ── basic structural tests ────────────────────────────────────────────────────

def test_script_exists():
    assert _SCRIPT.exists()


def test_output_exists():
    assert _OUTPUT.exists()


def test_output_valid_json():
    data = json.loads(_OUTPUT.read_text())
    assert isinstance(data, dict)


def test_dry_run_only(output: dict):
    assert output["dry_run_only"] is True


def test_lottery_type(output: dict):
    assert output["lottery_type"] == "POWER_LOTTO"


def test_production_rows_before(output: dict):
    assert output["production_rows_before"] == PROD_ROWS_SNAPSHOT


def test_production_rows_after(output: dict):
    assert output["production_rows_after"] == PROD_ROWS_SNAPSHOT


def test_no_db_write(output: dict):
    assert output["no_db_write"] is True


def test_selected_strategy_id_not_empty(output: dict):
    assert output["selected_strategy_id"] != ""


def test_selected_strategy_not_artifact_only(output: dict):
    sid = output["selected_strategy_id"]
    assert "ARTIFACT" not in output.get("strategy_lifecycle_status", "")
    assert sid in ("fourier_rhythm_3bet", "power_precision_3bet", "power_orthogonal_5bet")


def test_generated_candidates_lte_target(output: dict):
    assert output["generated_candidates"] <= 1500


def test_fake_success_count_zero(output: dict):
    assert output["fake_success_count"] == 0


def test_page_ready_sample_exists(output: dict):
    assert len(output["page_ready_sample"]) > 0


def test_final_classification(output: dict):
    assert output["final_classification"] in (
        "P19_POWERLOTTO_SINGLE_STRATEGY_DRY_RUN_READY",
        "P19_POWERLOTTO_PARTIAL_WINDOW_READY",
    )


# ── production DB guard ───────────────────────────────────────────────────────

def test_production_db_rows_at_baseline():
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS_BASELINE


# ── candidates_sample tests ───────────────────────────────────────────────────

def test_all_sample_candidates_power_lotto(output: dict):
    for c in output["candidates_sample"]:
        assert c["lottery_type"] == "POWER_LOTTO"


def test_ready_sample_have_predicted_numbers(output: dict):
    for c in output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["predicted_numbers"] is not None
            assert isinstance(c["predicted_numbers"], list)
            assert len(c["predicted_numbers"]) == 6


def test_ready_sample_have_actual_numbers(output: dict):
    for c in output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["actual_numbers"] is not None
            assert len(c["actual_numbers"]) == 6


def test_ready_sample_hit_count_matches(output: dict):
    for c in output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["hit_count"] == len(c["hit_numbers"]), \
                f"draw={c['target_draw']}: hit_count={c['hit_count']} len(hit_numbers)={len(c['hit_numbers'])}"


def test_ready_sample_have_prediction_cutoff_date(output: dict):
    for c in output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["prediction_cutoff_date"] is not None, \
                f"draw={c['target_draw']}: prediction_cutoff_date must not be None for READY rows"


def test_ready_sample_have_prediction_generated_at(output: dict):
    for c in output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["prediction_generated_at"] is not None


def test_ready_sample_cutoff_lte_target_date(output: dict):
    """prediction_cutoff_date must be <= target_date (no future leakage)."""
    for c in output["candidates_sample"]:
        if c["prediction_status"] == "READY" and c["prediction_cutoff_date"] and c["target_date"]:
            assert c["prediction_cutoff_date"] <= c["target_date"], \
                f"draw={c['target_draw']}: cutoff={c['prediction_cutoff_date']} > target={c['target_date']}"


def test_all_sample_not_success(output: dict):
    for c in output["candidates_sample"]:
        assert c["counts_as_success"] is False


def test_all_sample_would_not_insert(output: dict):
    for c in output["candidates_sample"]:
        assert c["would_insert"] is False


# ── page_ready_sample field tests ─────────────────────────────────────────────

def test_page_ready_sample_fields(output: dict):
    required = {
        "target_draw", "target_date", "strategy_name",
        "predicted_numbers", "actual_numbers", "hit_numbers",
        "hit_count", "special_hit", "prediction_cutoff_date",
        "prediction_generated_at", "display_status", "truth_level",
    }
    for row in output["page_ready_sample"]:
        missing = required - row.keys()
        assert not missing, f"page_ready_sample missing fields: {missing}"


def test_page_ready_sample_display_status(output: dict):
    for row in output["page_ready_sample"]:
        assert row["display_status"] == "SHOW_REPLAY_DRY_RUN"


def test_page_ready_sample_truth_level(output: dict):
    for row in output["page_ready_sample"]:
        assert row["truth_level"] == "DRY_RUN_REPLAY_BACKFILL"


def test_page_ready_sample_cutoff_lte_target(output: dict):
    for row in output["page_ready_sample"]:
        if row["prediction_cutoff_date"] and row["target_date"]:
            assert row["prediction_cutoff_date"] <= row["target_date"], \
                f"target={row['target_draw']}: cutoff {row['prediction_cutoff_date']} > target {row['target_date']}"


# ── live script re-run tests ──────────────────────────────────────────────────

def test_full_run_no_db_write():
    from scripts.p19_powerlotto_single_strategy_replay_dry_run import run
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp = Path(tf.name)
    try:
        result = run(out_file=tmp)
        assert result["production_rows_before"] == result["production_rows_after"]
        assert result["no_db_write"] is True
    finally:
        tmp.unlink(missing_ok=True)


def test_full_run_all_candidates_power_lotto():
    from scripts.p19_powerlotto_single_strategy_replay_dry_run import run
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp = Path(tf.name)
    try:
        result = run(out_file=tmp)
        for c in result["candidates_sample"]:
            assert c["lottery_type"] == "POWER_LOTTO"
    finally:
        tmp.unlink(missing_ok=True)


def test_full_run_ready_hit_count_consistent():
    from scripts.p19_powerlotto_single_strategy_replay_dry_run import run
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp = Path(tf.name)
    try:
        result = run(out_file=tmp)
        for c in result["candidates_sample"]:
            if c["prediction_status"] == "READY":
                assert c["hit_count"] == len(c["hit_numbers"])
                assert c["counts_as_success"] is False
                assert c["would_insert"] is False
    finally:
        tmp.unlink(missing_ok=True)
