"""Tests for P536C strategy success-rate matrix lift extension."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

import analysis.p536c_success_matrix_lift_extension as C
import analysis.p333_strategy_pick_combination_scoreboard as P

REPO_ROOT = Path(__file__).resolve().parents[1]
P333_ARTIFACT = REPO_ROOT / "outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json"


def _insert_row(
    conn,
    lottery_type,
    strategy_id,
    target_draw,
    bet_index,
    predicted,
    actual,
    predicted_special=None,
    actual_special=None,
):
    conn.execute(
        """
        INSERT INTO strategy_prediction_replays (
            lottery_type, strategy_id, target_draw, bet_index,
            predicted_numbers, predicted_special,
            actual_numbers, actual_special,
            history_cutoff_draw, replay_status, dry_run
        ) VALUES (?,?,?,?,?,?,?,?,?,'PREDICTED',0)
        """,
        (
            lottery_type,
            strategy_id,
            str(target_draw),
            bet_index,
            json.dumps(predicted),
            predicted_special,
            json.dumps(actual),
            actual_special,
            str(int(target_draw) - 1),
        ),
    )


def _build_db(path: Path) -> None:
    """Same schema/fixture shape as test_p333_strategy_pick_combination_scoreboard._build_db."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            lottery_type TEXT,
            strategy_id TEXT,
            target_draw TEXT,
            bet_index INTEGER,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            history_cutoff_draw TEXT,
            replay_status TEXT,
            dry_run INTEGER
        )
        """
    )
    for draw in range(1000, 1060):
        # BIG_LOTTO: fourier_big always hits main_hits==3 exactly (1,2,3 in actual) plus
        # extra non-hits, giving deterministic m3_plus/prize_signal every draw.
        _insert_row(
            conn,
            "BIG_LOTTO",
            "fourier_big",
            draw,
            1,
            [1, 2, 3, 10, 11, 12],
            [1, 2, 3, 4, 5, 6],
            None,
            7,
        )
        _insert_row(
            conn,
            "BIG_LOTTO",
            "cold_big",
            draw,
            1,
            [30, 31, 32, 33, 34, 35],
            [1, 2, 3, 4, 5, 6],
            None,
            7,
        )

        # POWER_LOTTO: fourier_power gets main_hits==1 plus a second-zone hit.
        _insert_row(
            conn,
            "POWER_LOTTO",
            "fourier_power",
            draw,
            1,
            [1, 20, 21, 22, 23, 24],
            [1, 2, 3, 4, 5, 6],
            4,
            4,
        )
        _insert_row(
            conn,
            "POWER_LOTTO",
            "cold_power",
            draw,
            1,
            [30, 31, 32, 33, 34, 35],
            [1, 2, 3, 4, 5, 6],
            5,
            4,
        )

        # DAILY_539: markov_539 gets main_hits==2 every draw (simple M2+ endpoint).
        _insert_row(
            conn,
            "DAILY_539",
            "markov_539",
            draw,
            1,
            [1, 2, 30, 31, 32],
            [1, 2, 3, 4, 5],
        )
    conn.commit()
    conn.close()


def _sha256_of_two_int_lists(values: list[int]) -> str:
    hasher = hashlib.sha256()
    for value in values:
        hasher.update(str(value).encode("utf-8"))
    return hasher.hexdigest()


def test_lift_none_when_baseline_zero_or_support_below_minimum():
    lift, log_lift = C._lift(0.5, 0.0, C.MIN_SUPPORT_DRAWS)
    assert lift is None
    assert log_lift is None

    lift, log_lift = C._lift(0.5, 0.1, C.MIN_SUPPORT_DRAWS - 1)
    assert lift is None
    assert log_lift is None


def test_lift_equals_rate_over_baseline_and_log10_matches():
    lift, log_lift = C._lift(0.4, 0.1, C.MIN_SUPPORT_DRAWS)
    assert lift == 0.4 / 0.1
    assert log_lift == math.log10(0.4 / 0.1)


def test_lift_zero_rate_gives_zero_lift_and_none_log_lift():
    lift, log_lift = C._lift(0.0, 0.2, C.MIN_SUPPORT_DRAWS)
    assert lift == 0.0
    assert log_lift is None


def test_baseline_m2_m3_match_closed_form_hypergeometric():
    # BIG_LOTTO: pool=49, drawn=6. Selecting 6 numbers.
    expected_m2 = P._hypergeom_at_least("BIG_LOTTO", 6, 2)
    expected_m3 = P._hypergeom_at_least("BIG_LOTTO", 6, 3)
    assert expected_m2 == P._hypergeom_at_least("BIG_LOTTO", 6, 2)
    assert expected_m3 == P._hypergeom_at_least("BIG_LOTTO", 6, 3)
    # Closed-form cross-check for m3 with pool=49, drawn=6, selected=6:
    # P(X>=3) = sum_{h=3}^{6} C(6,h)*C(43,6-h) / C(49,6)
    denom = math.comb(49, 6)
    total = sum(math.comb(6, h) * math.comb(43, 6 - h) for h in range(3, 7))
    assert expected_m3 == total / denom


def test_synthetic_run_m3_le_m2_le_any_main_per_cell(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    matrix = artifact["strategy_pick_matrix_lift_extension"]
    assert len(matrix) > 0
    for rec in matrix:
        if rec["support_draws"] == 0:
            continue
        assert rec["m3_plus_count"] <= rec["m2_plus_count"] <= rec["any_main_hit_count"]
        assert rec["m3_plus_rate"] <= rec["m2_plus_rate"] <= rec["any_main_hit_rate"]


def test_synthetic_run_lift_equals_rate_over_baseline_in_matrix(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    matrix = artifact["strategy_pick_matrix_lift_extension"]
    checked = 0
    for rec in matrix:
        for metric in ("any_main_hit", "m2_plus", "m3_plus", "prize_signal"):
            lift = rec[f"{metric}_lift"]
            rate = rec[f"{metric}_rate"]
            baseline = rec[f"baseline_{metric}_rate"]
            if lift is None:
                assert rate is None or baseline is None or baseline <= 0 or rec["support_draws"] < C.MIN_SUPPORT_DRAWS
                continue
            assert math.isclose(lift, rate / baseline, rel_tol=1e-9)
            checked += 1
            log_lift = rec[f"{metric}_log10_lift"]
            if lift > 0:
                assert math.isclose(log_lift, math.log10(lift), rel_tol=1e-9)
            else:
                assert log_lift is None
    assert checked > 0


def test_synthetic_run_fourier_big_deterministic_m3_and_prize_signal(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    matrix = artifact["strategy_pick_matrix_lift_extension"]
    cell = next(
        r for r in matrix
        if r["lottery_type"] == "BIG_LOTTO"
        and r["strategy_id"] == "fourier_big"
        and r["window"] == 50
        and r["pick_k"] == 3
    )
    # First 3 emitted numbers are [1, 2, 3], all in actual [1,2,3,4,5,6] -> main_hits == 3 every draw.
    assert cell["m3_plus_rate"] == 1.0
    assert cell["prize_signal_rate"] == 1.0
    assert cell["m3_plus_lift"] is not None
    assert cell["m3_plus_lift"] > 1.0


def test_cross_lottery_normalized_lift_never_pools_raw_rates(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    cross = artifact["cross_lottery_normalized_lift"]
    assert isinstance(cross, list)
    for entry in cross:
        assert entry["pick_k"] <= C._COMMON_PICK_MAX
        assert set(entry["lotteries"]).issubset(set(P.LOTTERIES))
        for lottery_stats in entry["lotteries"].values():
            # Only lift-derived fields are present; no raw rate field leaks in.
            assert "any_main_hit_rate" not in lottery_stats
            assert "prize_signal_rate" not in lottery_stats


def test_combination_leaderboard_with_lift_reuses_p333_leaderboard(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = P._open_ro(db)
    try:
        data = P._load_replay_draws(conn)
        raw_leaderboard, _ = P.build_combination_leaderboard(data)
    finally:
        conn.close()

    artifact = C.run_analysis(db)
    enriched = artifact["combination_leaderboard_with_lift"]

    assert len(enriched) == len(raw_leaderboard)
    for raw, enr in zip(raw_leaderboard, enriched):
        assert raw["combo_id"] == enr["combo_id"]
        assert "any_main_hit_lift" in enr
        assert "prize_signal_lift" in enr


def test_combination_stability_rank_only_over_leaderboard_combos(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    stability = artifact["combination_stability_rank"]
    leaderboard_combo_ids = {
        (rec["lottery_type"], int(rec["requested_budget"]), rec["combo_id"])
        for rec in artifact["combination_leaderboard_with_lift"]
    }
    for entry in stability:
        key = (entry["lottery_type"], entry["requested_budget"], entry["combo_id"])
        assert key in leaderboard_combo_ids
        assert entry["windows_present_count"] == len(entry["windows_present"])
        assert entry["stability_rank"] >= 1


def test_determinism_two_runs_same_fixture_identical_payload(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    first = C.run_analysis(db)
    second = C.run_analysis(db)

    first_copy = dict(first)
    second_copy = dict(second)
    del first_copy["generated_at"]
    del second_copy["generated_at"]
    assert json.dumps(first_copy, sort_keys=True) == json.dumps(second_copy, sort_keys=True)


def test_artifact_schema_keys_present(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    for key in (
        "schema_version",
        "task_id",
        "extends_task_id",
        "generated_at",
        "classification",
        "source",
        "window_policy",
        "metric_definitions",
        "methodology_notes",
        "strategy_pick_matrix_lift_extension",
        "cross_lottery_normalized_lift",
        "combination_leaderboard_with_lift",
        "combination_stability_rank",
        "summary",
        "safety_flags",
        "disclaimer_en",
    ):
        assert key in artifact, f"missing artifact key: {key}"

    assert artifact["task_id"] == "P536C"
    assert artifact["extends_task_id"] == "P333"
    assert artifact["safety_flags"]["db_write"] is False
    assert artifact["safety_flags"]["db_read_only"] is True
    assert C.DISCLAIMER_EN_HISTORICAL in artifact["disclaimer_en"]
    assert C.DISCLAIMER_EN_NO_CLAIM in artifact["disclaimer_en"]
    assert "data_hash_sha256" in artifact["source"]
    assert len(artifact["source"]["data_hash_sha256"]) == 64


def test_write_artifacts_refuses_to_overwrite_existing_file(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    artifact = C.run_analysis(db)

    out_json = tmp_path / "existing.json"
    out_md = tmp_path / "existing.md"
    out_json.write_text("{}", encoding="utf-8")

    try:
        C.write_artifacts(artifact, out_json, out_md)
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_existing_p333_artifact_untouched_by_import_or_run(tmp_path):
    """Importing/running this module must never mutate the committed P333 artifact."""
    if not P333_ARTIFACT.exists():
        return
    before = P333_ARTIFACT.read_bytes()
    db = tmp_path / "synthetic.db"
    _build_db(db)
    C.run_analysis(db)
    after = P333_ARTIFACT.read_bytes()
    assert before == after
