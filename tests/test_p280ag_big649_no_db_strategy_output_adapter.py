from __future__ import annotations

import ast
import copy
import hashlib
import json
import socket
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

import tools.big649_no_db_strategy_output_adapter as adapter
from tools.big649_no_db_strategy_output_adapter import (
    AdapterContractError,
    DETERMINISTIC_MISMATCH_STOP,
    DUPLICATE_COMPLETE_TICKET_STOP,
    MISSING_OR_EXTRA_STRATEGY_STOP,
    STOCHASTIC_POLICY_MISSING_STOP,
    build_adapter_report,
    classify_strategy_randomness,
    compute_strategy_output_digest,
    discover_strategy_adapters,
    generate_strategy_outputs_no_db,
    list_frozen_big649_strategy_ids,
    validate_strategy_adapter_contract,
    validate_strategy_outputs,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_PATH = REPO_ROOT / "tools/big649_no_db_strategy_output_adapter.py"
RUNBOOK_PATH = (
    REPO_ROOT
    / "00-Plan"
    / "roadmap"
    / "agent_bootstrap"
    / "BIG649_REAL_PUBLICATION_RUNBOOK.md"
)
EXPECTED_IDS = (
    "bet2_fourier_expansion_biglotto",
    "biglotto_deviation_2bet",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_ts3_markov_4bet_w30",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "ts3_regime_3bet",
)
EXPECTED_DUPLICATE_GROUPS = [
    [
        "bet2_fourier_expansion_biglotto",
        "biglotto_triple_strike",
        "biglotto_ts3_markov_4bet_w30",
        "ts3_regime_3bet",
    ],
    ["cold_complement_biglotto", "coldpool15_biglotto"],
    ["markov_2bet_biglotto", "markov_single_biglotto"],
]
TARGET_METADATA = {
    "target_draw": "SYNTHETIC_BIG649_TARGET_DO_NOT_PUBLISH",
    "synthetic": True,
}
HISTORY_CUTOFF = "SYNTHETIC_BIG649_HISTORY_CUTOFF"


def _synthetic_history() -> list[dict[str, object]]:
    history = []
    for draw_index in range(600):
        numbers: list[int] = []
        counter = 0
        while len(numbers) < 6:
            block = hashlib.sha256(
                f"P280AG:{draw_index}:{counter}".encode("ascii")
            ).digest()
            for byte in block:
                number = byte % 49 + 1
                if number not in numbers:
                    numbers.append(number)
                if len(numbers) == 6:
                    break
            counter += 1
        history.append(
            {
                "draw": f"SYN{draw_index:04d}",
                "date": f"SYNTHETIC-{draw_index:04d}",
                "numbers": sorted(numbers),
                "special": 0,
            }
        )
    return history


@pytest.fixture(scope="module")
def execution_evidence():
    db_calls: list[object] = []
    network_calls: list[object] = []

    def deny_db(*args, **kwargs):
        db_calls.append((args, kwargs))
        raise AssertionError("DB access attempted")

    def deny_network(*args, **kwargs):
        network_calls.append((args, kwargs))
        raise AssertionError("network access attempted")

    history = _synthetic_history()
    with patch.object(sqlite3, "connect", deny_db), patch.object(
        socket, "create_connection", deny_network
    ):
        raw = adapter._generate_source_outputs(history, HISTORY_CUTOFF, TARGET_METADATA)
        report = build_adapter_report(
            history=history,
            history_cutoff=HISTORY_CUTOFF,
            target_metadata=TARGET_METADATA,
        )
    return {
        "history": history,
        "raw": raw,
        "report": report,
        "db_calls": db_calls,
        "network_calls": network_calls,
    }


def test_exact_11_strategy_ids():
    assert list_frozen_big649_strategy_ids() == EXPECTED_IDS


def test_discover_all_11_adapters():
    discovered = discover_strategy_adapters()
    assert [record["strategy_id"] for record in discovered] == list(EXPECTED_IDS)
    assert all(record["status"] == "SAFE_CALLABLE_FOUND" for record in discovered)


def test_source_contract_hashes_and_functions_are_exact():
    validated = validate_strategy_adapter_contract()
    assert len(validated) == 11
    assert all(
        record["actual_sha256"] == record["expected_sha256"]
        and record["actual_git_blob_sha1"] == record["expected_git_blob_sha1"]
        for record in validated
    )


def test_adapter_has_zero_db_import_and_no_write_calls():
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported_roots.isdisjoint({"sqlite3", "sqlalchemy"})
    attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert attributes.isdisjoint({"connect", "write_bytes", "write_text", "mkdir"})


def test_adapter_has_no_network_or_github_side_effect_import():
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported_roots.isdisjoint(
        {"github", "httpx", "requests", "socket", "subprocess", "urllib", "urllib3"}
    )
    assert "create_pull_request" not in source


def test_guarded_execution_opens_no_db(execution_evidence):
    assert execution_evidence["db_calls"] == []
    assert execution_evidence["report"]["database_access"] == {
        "opened": False,
        "queried": False,
        "copied": False,
        "written": False,
    }


def test_guarded_execution_uses_no_network(execution_evidence):
    assert execution_evidence["network_calls"] == []
    assert execution_evidence["report"]["network_used"] is False


def test_target_and_deadline_mixing_stops(execution_evidence):
    metadata = dict(TARGET_METADATA, official_deadline="SYNTHETIC")
    with pytest.raises(AdapterContractError, match="TARGET_METADATA_MIXING_STOP"):
        adapter._generate_source_outputs(
            execution_evidence["history"], HISTORY_CUTOFF, metadata
        )


def test_target_outcome_access_stops(execution_evidence):
    metadata = dict(TARGET_METADATA, outcome_numbers=[1, 2, 3, 4, 5, 6])
    with pytest.raises(AdapterContractError, match="TARGET_METADATA_MIXING_STOP"):
        adapter._generate_source_outputs(
            execution_evidence["history"], HISTORY_CUTOFF, metadata
        )


def test_no_publication_artifact_write(execution_evidence):
    publication_root = REPO_ROOT / "outputs/publications"
    before = sorted(path.as_posix() for path in publication_root.rglob("*") if path.exists()) if publication_root.exists() else []
    build_adapter_report(
        history=execution_evidence["history"],
        history_cutoff=HISTORY_CUTOFF,
        target_metadata=TARGET_METADATA,
    )
    after = sorted(path.as_posix() for path in publication_root.rglob("*") if path.exists()) if publication_root.exists() else []
    assert after == before


def test_exact_source_generation_has_all_11_ids(execution_evidence):
    assert [record["strategy_id"] for record in execution_evidence["raw"]] == list(EXPECTED_IDS)


def test_every_source_output_has_one_valid_ticket(execution_evidence):
    for record in execution_evidence["raw"]:
        assert record["bet_index"] == 1
        ticket = record["predicted_main_numbers"]
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(type(number) is int and 1 <= number <= 49 for number in ticket)


def test_missing_strategy_stops(execution_evidence):
    with pytest.raises(AdapterContractError, match=MISSING_OR_EXTRA_STRATEGY_STOP):
        validate_strategy_outputs(execution_evidence["raw"][:-1])


def test_extra_strategy_stops(execution_evidence):
    outputs = copy.deepcopy(execution_evidence["raw"])
    outputs.append(
        {
            "strategy_id": "invented_strategy",
            "bet_index": 1,
            "predicted_main_numbers": [1, 2, 3, 4, 5, 6],
        }
    )
    with pytest.raises(AdapterContractError, match=MISSING_OR_EXTRA_STRATEGY_STOP):
        validate_strategy_outputs(outputs)


def test_invalid_ticket_stops(execution_evidence):
    outputs = copy.deepcopy(execution_evidence["raw"])
    outputs[0]["predicted_main_numbers"] = [1, 1, 2, 3, 4, 5]
    with pytest.raises(AdapterContractError, match="duplicate numbers"):
        validate_strategy_outputs(outputs)


def test_duplicate_complete_tickets_stop(execution_evidence):
    with pytest.raises(AdapterContractError, match=DUPLICATE_COMPLETE_TICKET_STOP):
        validate_strategy_outputs(execution_evidence["raw"])
    assert execution_evidence["report"]["duplicate_complete_ticket_groups"] == EXPECTED_DUPLICATE_GROUPS


def test_public_generation_fails_closed_on_real_source_duplicates(execution_evidence):
    with pytest.raises(AdapterContractError, match=DUPLICATE_COMPLETE_TICKET_STOP):
        generate_strategy_outputs_no_db(
            history=execution_evidence["history"],
            history_cutoff=HISTORY_CUTOFF,
            target_metadata=TARGET_METADATA,
        )


def test_deterministic_same_input_is_stable(execution_evidence):
    report = execution_evidence["report"]
    assert report["deterministic_rerun_status"] == "PASS_BYTE_STABLE_DIGEST"
    assert compute_strategy_output_digest(execution_evidence["raw"]) == report["strategy_output_digest"]


def test_deterministic_mismatch_stops(execution_evidence):
    with pytest.raises(AdapterContractError, match=DETERMINISTIC_MISMATCH_STOP):
        generate_strategy_outputs_no_db(
            history=execution_evidence["history"],
            history_cutoff=HISTORY_CUTOFF,
            target_metadata=TARGET_METADATA,
            previous_output_digest="0" * 64,
        )


def test_stochastic_requires_seed_and_policy():
    with pytest.raises(AdapterContractError, match=STOCHASTIC_POLICY_MISSING_STOP):
        classify_strategy_randomness(strategy_kind="stochastic")
    result = classify_strategy_randomness(
        strategy_kind="stochastic",
        seed="SYNTHETIC-SEED",
        policy={"algorithm": "synthetic-only"},
    )
    assert result["status"] == "STOCHASTIC_READY_WITH_SEED_AND_POLICY"


def test_strategy_output_digest_is_deterministic(execution_evidence):
    first = compute_strategy_output_digest(execution_evidence["raw"])
    second = compute_strategy_output_digest(copy.deepcopy(execution_evidence["raw"]))
    assert first == second and len(first) == 64


def test_adapter_report_records_callable_paths(execution_evidence):
    capabilities = execution_evidence["report"]["capabilities"]
    assert len(capabilities) == 11
    assert all(record["module"] and record["function"] for record in capabilities)
    assert all(record["caller_history_supported"] is True for record in capabilities)


def test_adapter_report_documents_unresolved_interface_blocker(execution_evidence):
    report = execution_evidence["report"]
    assert report["final_classification"] == (
        "P280AG_NO_DB_ADAPTER_BLOCKED_BY_STRATEGY_INTERFACE_GAP_NO_ACTIVATION"
    )
    assert report["publication_compatible"] is False
    assert "duplicate complete tickets" in report["remaining_blocker"]


def test_p280ad_runner_rejects_exact_source_duplicates(execution_evidence):
    report = execution_evidence["report"]
    assert report["p280ad_runner_compatibility"]["status"] == (
        "BLOCKED_DUPLICATE_COMPLETE_TICKETS"
    )
    assert report["p280ad_runner_compatibility"]["mode"] == "SAFE_VALIDATE_ONLY"


def test_no_fabricated_fallback_output_path():
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert "build_default_strategy_tickets" not in source
    assert "dry_run/" not in source
    assert all(record["module"] for record in adapter._SPECS)


def test_report_safety_claims_are_all_false(execution_evidence):
    report = execution_evidence["report"]
    assert report["real_target_selected"] is False
    assert report["official_deadline_lookup"] is False
    assert report["real_ticket_published"] is False
    assert report["publication_pr_created"] is False
    assert report["future_evaluation_started"] is False
    assert report["outcome_used"] is False
    assert report["prediction_success_claim"] is False
    assert report["strategy_promoted"] is False
    assert report["activation_authorized"] is False


def test_runbook_contains_adapter_stop_rules():
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    required = [
        "run the no-DB strategy-output adapter",
        "Missing any frozen strategy callable or output = STOP.",
        "Any adapter DB access = STOP.",
        "Any target outcome or result access = STOP.",
        "Invented or fallback output = STOP.",
        "Stochastic output without seed and policy = STOP.",
        "Duplicate complete-ticket conflict = STOP",
        "separate explicit Owner authorization",
    ]
    assert all(rule in text for rule in required)


def test_research_artifact_records_blocker_and_no_actions():
    artifact = json.loads(
        (
            REPO_ROOT
            / "outputs/research/p280ag_big649_no_db_strategy_output_adapter_20260619.json"
        ).read_text(encoding="utf-8")
    )
    assert artifact["final_classification"] == (
        "P280AG_NO_DB_ADAPTER_BLOCKED_BY_STRATEGY_INTERFACE_GAP_NO_ACTIVATION"
    )
    assert artifact["adapter_implemented"] is True
    assert artifact["publication_compatible"] is False
    assert artifact["database_access"] == {
        "opened": False,
        "queried": False,
        "copied": False,
        "written": False,
    }
