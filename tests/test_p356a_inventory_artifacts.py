from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = REPO_ROOT / "artifacts"


REQUIRED = {
    "P356A_phase0_evidence.md",
    "P356A_strategy_inventory_all.csv",
    "P356A_strategy_inventory_all.json",
    "P356A_replay_skipped_strategies.md",
    "P356A_strategy_id_reuse_cases.md",
    "P356A_inventory_summary.md",
    "P356A_validation_log.md",
}

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


def load_payload() -> dict:
    return json.loads((ARTIFACT_DIR / "P356A_strategy_inventory_all.json").read_text(encoding="utf-8"))


def test_required_artifacts_exist() -> None:
    missing = [name for name in REQUIRED if not (ARTIFACT_DIR / name).exists()]
    assert not missing


def test_csv_and_json_inventory_agree() -> None:
    payload = load_payload()
    with (ARTIFACT_DIR / "P356A_strategy_inventory_all.csv").open(encoding="utf-8", newline="") as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) == len(payload["inventory"])
    assert len(csv_rows) == payload["summary"]["counts"]["total_strategy_lineages"]


def test_big_lotto_seed_coverage_is_complete() -> None:
    payload = load_payload()
    coverage = payload["summary"]["big_lotto_seed_coverage"]
    assert set(coverage) == SEED_BIG_LOTTO
    assert all(item["covered"] for item in coverage.values())


def test_special_case_classifications() -> None:
    rows = load_payload()["inventory"]
    by_id = {}
    for row in rows:
        by_id.setdefault(row["strategy_id"], []).append(row)

    ts3_acb = by_id["biglotto_ts3_acb_4bet"]
    assert any(row["executable_status"] == "MISSING_CODE" for row in ts3_acb)
    assert all("fake execution" not in row["callable_entrypoint"] for row in ts3_acb)

    bet2 = by_id["bet2_fourier_expansion_biglotto"]
    assert len(bet2) >= 2
    assert {row["executable_status"] for row in bet2} == {"ID_REUSED"}
    assert {
        "bet2_fourier_expansion_biglotto__p42_p280_frozen_code",
        "bet2_fourier_expansion_biglotto__rejected_json_historical",
    }.issubset({row["lineage_id"] for row in bet2})


def test_replay_not_run_and_all_rows_have_skip_reason() -> None:
    payload = load_payload()
    assert payload["summary"]["replay_status"] == "NOT_RUN"
    assert not (ARTIFACT_DIR / "P356A_biglotto_replay_30_150_750_1500.csv").exists()
    assert not (ARTIFACT_DIR / "P356A_biglotto_replay_30_150_750_1500.md").exists()
    assert all(row["skip_reason"] for row in payload["inventory"])
