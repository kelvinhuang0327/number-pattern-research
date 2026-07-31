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

import lottery_api.models.p42_wave3_biglotto_adapters as wave3
import tools.big649_no_db_strategy_output_adapter as adapter
from analysis import p280d_big649_future_only_protocol as protocol
from tools.big649_no_db_strategy_output_adapter import (
    AdapterContractError,
    DETERMINISTIC_MISMATCH_STOP,
    DUPLICATE_COMPLETE_TICKET_STOP,
    MISSING_OR_EXTRA_STRATEGY_STOP,
    SELECTION_RULE,
    STOCHASTIC_POLICY_MISSING_STOP,
    UNRESOLVED_DUPLICATE_STOP,
    build_adapter_report,
    classify_strategy_randomness,
    compute_strategy_output_digest,
    discover_strategy_adapters,
    enumerate_strategy_candidates,
    frozen_primary_duplicate_groups,
    frozen_primary_outputs,
    generate_strategy_outputs_no_db,
    list_frozen_big649_strategy_ids,
    resolve_unique_strategy_outputs,
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
P280D_ARTIFACT_JSON = (
    REPO_ROOT / "outputs/research/p280d_big649_future_only_freeze_protocol_20260618.json"
)
P280AG_ARTIFACT_JSON = (
    REPO_ROOT / "outputs/research/p280ag_big649_no_db_strategy_output_adapter_20260619.json"
)
P280AQ_ARTIFACT_JSON = (
    REPO_ROOT
    / "outputs/research/p280aq_big649_private_strategy_pack_duplicate_remediation_20260619.json"
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
# Pre-remediation P280AH duplicate root cause on the synthetic fixture.
EXPECTED_FROZEN_DUPLICATE_GROUPS = [
    [
        "bet2_fourier_expansion_biglotto",
        "biglotto_triple_strike",
        "biglotto_ts3_markov_4bet_w30",
        "ts3_regime_3bet",
    ],
    ["cold_complement_biglotto", "coldpool15_biglotto"],
    ["markov_2bet_biglotto", "markov_single_biglotto"],
]
BLOCKED_CANDIDATE_FUNCTIONS = {
    "markov_2bet_biglotto": "predict_markov_2bet_candidates",
    "coldpool15_biglotto": "predict_coldpool15_candidates",
    "ts3_regime_3bet": "ts3_regime_candidates",
}
CANDIDATE_FUNCTIONS = {
    **BLOCKED_CANDIDATE_FUNCTIONS,
    "fourier30_markov30_biglotto": "predict_fourier30_markov30_candidates",
}
TARGET_METADATA = {
    "target_draw": "SYNTHETIC_BIG649_TARGET_DO_NOT_PUBLISH",
    "synthetic": True,
}
HISTORY_CUTOFF = "SYNTHETIC_BIG649_HISTORY_CUTOFF"


def _synthetic_history(tag: str = "P280AG") -> list[dict[str, object]]:
    history = []
    for draw_index in range(600):
        numbers: list[int] = []
        counter = 0
        while len(numbers) < 6:
            block = hashlib.sha256(
                f"{tag}:{draw_index}:{counter}".encode("ascii")
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
        enumerated = enumerate_strategy_candidates(history, HISTORY_CUTOFF, TARGET_METADATA)
        resolved = resolve_unique_strategy_outputs(history, HISTORY_CUTOFF, TARGET_METADATA)
        report = build_adapter_report(
            history=history,
            history_cutoff=HISTORY_CUTOFF,
            target_metadata=TARGET_METADATA,
        )
    return {
        "history": history,
        "enumerated": enumerated,
        "resolved": resolved,
        "report": report,
        "db_calls": db_calls,
        "network_calls": network_calls,
    }


# ── Identity / contract ────────────────────────────────────────────────────────

def test_exact_11_strategy_ids():
    assert list_frozen_big649_strategy_ids() == EXPECTED_IDS


def test_discover_all_11_adapters_and_source_hashes_exact():
    discovered = discover_strategy_adapters()
    assert [record["strategy_id"] for record in discovered] == list(EXPECTED_IDS)
    assert all(record["status"] == "SAFE_CALLABLE_FOUND" for record in discovered)
    assert all(
        record["actual_sha256"] == record["expected_sha256"]
        and record["actual_git_blob_sha1"] == record["expected_git_blob_sha1"]
        for record in discovered
    )
    validate_strategy_adapter_contract()


# ── Req 1: pre-remediation duplicate root cause reproduced ──────────────────────

def test_frozen_primary_duplicate_groups_reproduced(execution_evidence):
    groups = frozen_primary_duplicate_groups(
        execution_evidence["history"], HISTORY_CUTOFF, TARGET_METADATA
    )
    assert groups == EXPECTED_FROZEN_DUPLICATE_GROUPS
    assert execution_evidence["report"]["frozen_primary_duplicate_groups"] == (
        EXPECTED_FROZEN_DUPLICATE_GROUPS
    )
    primaries = frozen_primary_outputs(
        execution_evidence["history"], HISTORY_CUTOFF, TARGET_METADATA
    )
    assert [record["strategy_id"] for record in primaries] == list(EXPECTED_IDS)


# ── Req 2: new candidate interface exists for the three blocked strategies ───────

def test_new_candidate_interfaces_exist_for_blocked_strategies():
    discovered = {record["strategy_id"]: record for record in discover_strategy_adapters()}
    for strategy_id, candidate_function in CANDIDATE_FUNCTIONS.items():
        record = discovered[strategy_id]
        assert record["candidate_function"] == candidate_function
        # the candidate interface is genuinely distinct from the frozen bet-1 one
        assert record["candidate_function"] != record["frozen_function"]
    wave3_fns = {
        node.name
        for node in ast.walk(ast.parse(
            (REPO_ROOT / "lottery_api/models/p42_wave3_biglotto_adapters.py").read_text()
        ))
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "predict_markov_2bet_candidates",
        "predict_coldpool15_candidates",
        "predict_fourier30_markov30_candidates",
    } <= wave3_fns
    enh_fns = {
        node.name
        for node in ast.walk(ast.parse(
            (REPO_ROOT / "tools/backtest_biglotto_enhancements.py").read_text()
        ))
        if isinstance(node, ast.FunctionDef)
    }
    assert "ts3_regime_candidates" in enh_fns


def test_fourier30_markov30_candidates_preserve_primary_and_family_contract(
    execution_evidence,
):
    history = execution_evidence["history"]
    candidates = wave3.predict_fourier30_markov30_candidates(history)
    assert candidates[0] == wave3.predict_fourier30_markov30_bet1(history)
    assert len(candidates) == 2
    assert candidates == wave3.predict_fourier30_markov30_candidates(history)
    assert len(set(candidates[0]) & set(candidates[1])) <= 3
    assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in candidates)


# ── Req 3: candidate interface uses caller-supplied history ─────────────────────

def test_candidate_interface_uses_caller_supplied_history(execution_evidence):
    # too-short caller history fails closed
    with pytest.raises(AdapterContractError, match="at least 500 draws"):
        enumerate_strategy_candidates(
            execution_evidence["history"][:10], HISTORY_CUTOFF, TARGET_METADATA
        )
    # a different caller history yields different frozen primaries (no fixed source)
    other = frozen_primary_outputs(_synthetic_history("P280AG-ALT"), HISTORY_CUTOFF, TARGET_METADATA)
    base = frozen_primary_outputs(execution_evidence["history"], HISTORY_CUTOFF, TARGET_METADATA)
    assert other != base


# ── Req 4 & 22: no DB access ────────────────────────────────────────────────────

def test_guarded_execution_opens_no_db(execution_evidence):
    assert execution_evidence["db_calls"] == []
    assert execution_evidence["report"]["database_access"] == {
        "opened": False,
        "queried": False,
        "copied": False,
        "written": False,
    }


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


# ── Req 5: no network ───────────────────────────────────────────────────────────

def test_guarded_execution_uses_no_network(execution_evidence):
    assert execution_evidence["network_calls"] == []
    assert execution_evidence["report"]["network_used"] is False
    assert execution_evidence["report"]["github_side_effect"] is False


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


# ── Req 6: candidate tickets valid 1..49 ────────────────────────────────────────

def test_candidate_tickets_are_valid(execution_evidence):
    for record in execution_evidence["enumerated"]:
        assert record["candidates"], record["strategy_id"]
        for ticket in record["candidates"]:
            assert len(ticket) == 6
            assert len(set(ticket)) == 6
            assert ticket == sorted(ticket)
            assert all(type(number) is int and 1 <= number <= 49 for number in ticket)


# ── Req 7: deterministic non-duplicate selection per blocked strategy ───────────

def test_each_blocked_strategy_selects_distinct_candidate(execution_evidence):
    provenance = {
        record["strategy_id"]: record
        for record in execution_evidence["resolved"]["provenance"]
    }
    outputs = {
        record["strategy_id"]: tuple(record["predicted_main_numbers"])
        for record in execution_evidence["resolved"]["outputs"]
    }
    for strategy_id in BLOCKED_CANDIDATE_FUNCTIONS:
        assert provenance[strategy_id]["rebound_off_frozen_primary"] is True
    # markov_single keeps its frozen bet-1 identity; markov_2bet rebinds to bet-2
    assert provenance["markov_single_biglotto"]["rebound_off_frozen_primary"] is False
    assert outputs["markov_2bet_biglotto"] != outputs["markov_single_biglotto"]
    assert outputs["coldpool15_biglotto"] != outputs["cold_complement_biglotto"]


# ── Req 8: eleven final tickets are unique ──────────────────────────────────────

def test_eleven_final_tickets_are_unique(execution_evidence):
    outputs = generate_strategy_outputs_no_db(
        history=execution_evidence["history"],
        history_cutoff=HISTORY_CUTOFF,
        target_metadata=TARGET_METADATA,
    )
    assert [record["strategy_id"] for record in outputs] == list(EXPECTED_IDS)
    tickets = {tuple(record["predicted_main_numbers"]) for record in outputs}
    assert len(tickets) == 11
    assert all(record["bet_index"] == 1 for record in outputs)
    assert execution_evidence["report"]["resolved_unique_ticket_count"] == 11


# ── Req 9: provenance records index / count / callable / digest ─────────────────

def test_selection_provenance_is_complete(execution_evidence):
    report = execution_evidence["report"]
    assert report["selection_rule"] == SELECTION_RULE
    assert len(report["selection_provenance"]) == 11
    for record in report["selection_provenance"]:
        assert isinstance(record["selected_candidate_index"], int)
        assert record["candidate_count"] >= 1
        assert 0 <= record["selected_candidate_index"] < record["candidate_count"]
        assert record["source_callable"].count(":") == 1
        assert len(record["source_sha256"]) == 64
        assert record["selection_rule"] == SELECTION_RULE
    assert len(report["strategy_output_digest"]) == 64


# ── Req 10 & 11: deterministic rerun + stable digest ────────────────────────────

def test_deterministic_rerun_is_stable(execution_evidence):
    report = execution_evidence["report"]
    assert report["deterministic_rerun_status"] == "PASS_BYTE_STABLE_DIGEST"
    again = resolve_unique_strategy_outputs(
        execution_evidence["history"], HISTORY_CUTOFF, TARGET_METADATA
    )
    assert again["outputs"] == execution_evidence["resolved"]["outputs"]
    assert (
        compute_strategy_output_digest(again["outputs"]) == report["strategy_output_digest"]
    )


def test_output_digest_is_deterministic(execution_evidence):
    outputs = execution_evidence["resolved"]["outputs"]
    first = compute_strategy_output_digest(outputs)
    second = compute_strategy_output_digest(copy.deepcopy(outputs))
    assert first == second and len(first) == 64


# ── Req 12: mutation changes the digest ─────────────────────────────────────────

def test_mutation_changes_digest(execution_evidence):
    outputs = copy.deepcopy(execution_evidence["resolved"]["outputs"])
    baseline = compute_strategy_output_digest(outputs)
    swap = outputs[0]["predicted_main_numbers"]
    outputs[0]["predicted_main_numbers"] = sorted(
        n if n != swap[0] else (swap[0] % 49) + 1 for n in swap
    ) if len(set(swap)) == 6 else swap
    # guarantee a real mutation
    outputs[0]["predicted_main_numbers"] = [1, 2, 3, 4, 5, 6]
    assert compute_strategy_output_digest(outputs) != baseline


def test_deterministic_mismatch_stops(execution_evidence):
    with pytest.raises(AdapterContractError, match=DETERMINISTIC_MISMATCH_STOP):
        generate_strategy_outputs_no_db(
            history=execution_evidence["history"],
            history_cutoff=HISTORY_CUTOFF,
            target_metadata=TARGET_METADATA,
            previous_output_digest="0" * 64,
        )


# ── Req 13 & 14: missing / extra strategy STOP ──────────────────────────────────

def test_missing_strategy_stops(execution_evidence):
    outputs = execution_evidence["resolved"]["outputs"]
    with pytest.raises(AdapterContractError, match=MISSING_OR_EXTRA_STRATEGY_STOP):
        validate_strategy_outputs(outputs[:-1])


def test_extra_strategy_stops(execution_evidence):
    outputs = copy.deepcopy(execution_evidence["resolved"]["outputs"])
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
    outputs = copy.deepcopy(execution_evidence["resolved"]["outputs"])
    outputs[0]["predicted_main_numbers"] = [1, 1, 2, 3, 4, 5]
    with pytest.raises(AdapterContractError, match="duplicate numbers"):
        validate_strategy_outputs(outputs)


# ── Req 15: unresolved duplicate STOP ───────────────────────────────────────────

def test_unresolved_duplicate_stops(execution_evidence, monkeypatch):
    history = execution_evidence["history"]
    # bet2_fourier (canonical position 1) claims its ticket first; force coldpool15
    # to offer only that already-claimed ticket so it cannot resolve.
    claimed = frozen_primary_outputs(history, HISTORY_CUTOFF, TARGET_METADATA)[0][
        "predicted_main_numbers"
    ]
    monkeypatch.setattr(
        wave3, "predict_coldpool15_candidates", lambda hist: [list(claimed)]
    )
    with pytest.raises(AdapterContractError, match=UNRESOLVED_DUPLICATE_STOP):
        resolve_unique_strategy_outputs(history, HISTORY_CUTOFF, TARGET_METADATA)


# ── Req 16/17/18: no fabricated / outcome-aware / historical-best selection ──────

def test_no_fabricated_fallback_output(execution_evidence):
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert "build_default_strategy_tickets" not in source
    assert "dry_run/" not in source
    assert execution_evidence["report"]["fabricated_fallback_output"] is False
    # every published ticket is traceable to an actual source candidate
    for record, provenance in zip(
        execution_evidence["resolved"]["outputs"],
        execution_evidence["resolved"]["provenance"],
    ):
        candidates = next(
            item["candidates"]
            for item in execution_evidence["enumerated"]
            if item["strategy_id"] == record["strategy_id"]
        )
        assert record["predicted_main_numbers"] in candidates


def test_no_outcome_aware_selection(execution_evidence):
    report = execution_evidence["report"]
    assert report["outcome_aware_selection"] is False
    assert report["outcome_used"] is False
    # outcome data smuggled through target metadata is rejected
    metadata = dict(TARGET_METADATA, outcome_numbers=[1, 2, 3, 4, 5, 6])
    with pytest.raises(AdapterContractError, match="TARGET_METADATA_MIXING_STOP"):
        enumerate_strategy_candidates(execution_evidence["history"], HISTORY_CUTOFF, metadata)
    metadata = dict(TARGET_METADATA, official_deadline="SYNTHETIC")
    with pytest.raises(AdapterContractError, match="TARGET_METADATA_MIXING_STOP"):
        enumerate_strategy_candidates(execution_evidence["history"], HISTORY_CUTOFF, metadata)


def test_no_historical_best_selection(execution_evidence):
    report = execution_evidence["report"]
    assert report["historical_best_past_selection"] is False
    # No outcome/performance ranking drives selection. (The negative-attestation
    # field names are deliberately excluded from this token scan.)
    source = ADAPTER_PATH.read_text(encoding="utf-8").lower()
    for token in ("win_count", "best_strategy", "p_value", "performance_rank", "sort_by_hit"):
        assert token not in source


# ── Req 19: P280AD SAFE_VALIDATE_ONLY compatibility ─────────────────────────────

def test_p280ad_safe_validate_only_compatibility(execution_evidence):
    compat = execution_evidence["report"]["p280ad_runner_compatibility"]
    assert compat["status"] == "PASS_SAFE_VALIDATE_ONLY"
    assert compat["mode"] == "SAFE_VALIDATE_ONLY"
    assert compat["error"] is None
    assert execution_evidence["report"]["publication_compatible"] is True


def test_no_publication_artifact_write(execution_evidence):
    publication_root = REPO_ROOT / "outputs/publications"
    before = (
        sorted(path.as_posix() for path in publication_root.rglob("*") if path.exists())
        if publication_root.exists()
        else []
    )
    build_adapter_report(
        history=execution_evidence["history"],
        history_cutoff=HISTORY_CUTOFF,
        target_metadata=TARGET_METADATA,
    )
    after = (
        sorted(path.as_posix() for path in publication_root.rglob("*") if path.exists())
        if publication_root.exists()
        else []
    )
    assert after == before


# ── Req 20: P280D freeze reconciliation passes ──────────────────────────────────

def test_p280d_freeze_reconciles_after_interface_change():
    artifact = json.loads(P280D_ARTIFACT_JSON.read_text(encoding="utf-8"))
    protocol.validate_freeze_artifact(artifact)
    for record in artifact["strategies"]:
        data = (REPO_ROOT / record["source_path"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(data).hexdigest()
        assert record["git_blob_sha1"] == hashlib.sha1(
            f"blob {len(data)}\0".encode() + data
        ).hexdigest()
    revision = artifact["p280aj_publication_interface_revision"]
    assert revision["bet1_semantics_preserved"] is True
    assert revision["historical_future_only_evidence_changed"] is False
    changed = {item["source_path"] for item in revision["changed_source_files"]}
    assert changed == {
        "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "tools/backtest_biglotto_enhancements.py",
    }


# ── Req 21: runbook remediation rules present ───────────────────────────────────

def test_runbook_contains_remediation_rules():
    text = RUNBOOK_PATH.read_text(encoding="utf-8").lower()
    required = [
        "run the no-db strategy-output adapter",
        "any adapter db access = stop.",
        "invented or fallback output = stop.",
        "deterministic source-candidate selection",
        "candidate provenance",
        "p280d freeze reconciliation",
        "outcome-aware selection",
        "historical-best",
        "separate explicit owner authorization",
    ]
    missing = [rule for rule in required if rule not in text]
    assert not missing, missing


# ── randomness governance ───────────────────────────────────────────────────────

def test_stochastic_requires_seed_and_policy():
    with pytest.raises(AdapterContractError, match=STOCHASTIC_POLICY_MISSING_STOP):
        classify_strategy_randomness(strategy_kind="stochastic")
    result = classify_strategy_randomness(
        strategy_kind="stochastic",
        seed="SYNTHETIC-SEED",
        policy={"algorithm": "synthetic-only"},
    )
    assert result["status"] == "STOCHASTIC_READY_WITH_SEED_AND_POLICY"


# ── research artifact + report safety claims ────────────────────────────────────

def test_report_safety_claims_are_all_false(execution_evidence):
    report = execution_evidence["report"]
    for flag in (
        "real_target_selected",
        "official_deadline_lookup",
        "real_ticket_published",
        "publication_pr_created",
        "future_evaluation_started",
        "outcome_used",
        "fabricated_fallback_output",
        "outcome_aware_selection",
        "historical_best_past_selection",
        "prediction_success_claim",
        "strategy_promoted",
        "registry_mutated",
        "activation_authorized",
        "production_ready_claim",
    ):
        assert report[flag] is False


def test_research_artifact_records_resolution_and_no_actions():
    artifact = json.loads(P280AG_ARTIFACT_JSON.read_text(encoding="utf-8"))
    assert artifact["final_classification"] == (
        "P280AJ_BIG649_STRATEGY_INTERFACE_AND_FREEZE_REMEDIATED_PR461_UPDATED_NOT_ACTIVATED"
    )
    assert artifact["adapter_implemented"] is True
    assert artifact["publication_compatible"] is True
    assert artifact["database_access"] == {
        "opened": False,
        "queried": False,
        "copied": False,
        "written": False,
    }
    assert artifact["activation_authorized"] is False


def test_p280aq_private_pack_artifact_is_complete_and_publication_free():
    artifact = json.loads(P280AQ_ARTIFACT_JSON.read_text(encoding="utf-8"))
    assert artifact["final_classification"] == (
        "P280AQ_PRIVATE_BIG649_STRATEGY_PACK_DUPLICATE_REMEDIATED_PR_OPEN_NO_PUBLICATION"
    )
    assert artifact["root_cause_classification"] == (
        "SAFE_ADDITIVE_CANDIDATE_INTERFACE_NEEDED"
    )
    pack = artifact["strategy_adapter_pack"]
    assert [item["strategy_id"] for item in pack["tickets"]] == list(EXPECTED_IDS)
    outputs = [
        {
            "strategy_id": item["strategy_id"],
            "bet_index": 1,
            "predicted_main_numbers": item["ticket"],
        }
        for item in pack["tickets"]
    ]
    assert compute_strategy_output_digest(outputs) == pack["adapter_digest"]
    validate_strategy_outputs(outputs)
    assert artifact["diversified_random_pack"]["seed_material"] == (
        "P280AP|25e7f8520164aaf61f440a866a11eca403bb76a3|115000062"
    )
    assert artifact["database_access"]["copied"] is False
    assert artifact["database_access"]["written"] is False
    assert all(
        value is False
        for key, value in artifact["safety"].items()
        if key.endswith("performed") or key in {
            "pre_draw_manifest_created",
            "prediction_success_claim",
            "strategy_promoted",
            "activation",
            "production_or_controlled_apply",
            "outcome_used",
        }
    )
