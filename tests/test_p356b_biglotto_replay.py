from __future__ import annotations

import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = REPO_ROOT / "artifacts"
WINDOWS = {"30", "150", "750", "1500"}

SEED_BIG_LOTTO = {
    "biglotto_ts3_markov_freq_5bet",
    "biglotto_ts3_markov_4bet_w30",
    "coldpool15_biglotto",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "ts3_regime_3bet",
    "cold_complement_biglotto",
    "markov_single_biglotto",
    "markov_2bet_biglotto",
    "fourier30_markov30_biglotto",
    "biglotto_ts3_acb_4bet",
    "bet2_fourier_expansion_biglotto",
}


def read_csv(name: str) -> list[dict[str, str]]:
    with (ARTIFACT_DIR / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_p356b_artifacts_exist() -> None:
    for name in [
        "P356B_replay_eligible_manifest.csv",
        "P356B_replay_eligible_manifest.md",
        "P356B_biglotto_replay_30_150_750_1500.csv",
        "P356B_biglotto_replay_30_150_750_1500.md",
        "P356B_validation_log.md",
    ]:
        assert (ARTIFACT_DIR / name).exists(), name


def test_manifest_has_complete_biglotto_exclusions() -> None:
    rows = read_csv("P356B_replay_eligible_manifest.csv")
    assert len(rows) == 57
    assert SEED_BIG_LOTTO.issubset({row["strategy_id"] for row in rows})
    assert all(row["exclusion_reason"] for row in rows if row["eligibility_status"] == "EXCLUDED")
    by_id = {}
    for row in rows:
        by_id.setdefault(row["strategy_id"], []).append(row)
    assert {row["exclusion_reason"] for row in by_id["bet2_fourier_expansion_biglotto"]} == {"ID_REUSED"}
    assert by_id["biglotto_ts3_acb_4bet"][0]["exclusion_reason"] == "MISSING_CODE"
    assert by_id["biglotto_ts3_markov_freq_5bet"][0]["exclusion_reason"] == "MISSING_CODE"


def test_replay_rows_cover_every_eligible_strategy_and_window() -> None:
    manifest = read_csv("P356B_replay_eligible_manifest.csv")
    eligible = {row["strategy_id"] for row in manifest if row["eligibility_status"] == "ELIGIBLE"}
    replay = read_csv("P356B_biglotto_replay_30_150_750_1500.csv")
    assert eligible
    assert len(replay) == len(eligible) * len(WINDOWS)
    for strategy_id in eligible:
        rows = [row for row in replay if row["strategy_id"] == strategy_id]
        assert {row["window"] for row in rows} == WINDOWS
        assert all(row["replay_status"] == "COMPLETED" for row in rows)
        assert all(int(row["total_periods"]) == int(row["window"]) for row in rows)


def test_replay_metrics_are_probabilities_and_db_guard_passed() -> None:
    replay = read_csv("P356B_biglotto_replay_30_150_750_1500.csv")
    for row in replay:
        assert 0 <= float(row["hit_rate"]) <= 1
        assert 0 < float(row["baseline"]) < 1
        assert int(row["hit_count"]) <= int(row["total_periods"])
    log = (ARTIFACT_DIR / "P356B_validation_log.md").read_text(encoding="utf-8")
    assert "`db_sha_guard`: PASS" in log
    assert "`draw_rows_guard`: PASS" in log
    assert "`replay_rows_guard`: PASS" in log
    assert "The value `35` is the direct count" in log
    assert "The value `42` from P356A is the broader strategy-like DB evidence set" in log
