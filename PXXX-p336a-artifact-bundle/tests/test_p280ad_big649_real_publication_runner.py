from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from tools.big649_real_publication_runner import (
    ALREADY_PUBLISHED_SAME_MANIFEST,
    BIG649_FROZEN_STRATEGY_IDS,
    DETERMINISTIC_MISMATCH_STOP,
    DUPLICATE_MANIFEST_CONFLICT_STOP,
    IDEMPOTENCY_PASS,
    PublicationGuardError,
    STOCHASTIC_POLICY_MISSING_STOP,
    STOCHASTIC_READY_WITH_SEED_AND_POLICY,
    SYNTHETIC_TARGET,
    build_publication_manifest_candidate,
    check_publication_duplicate,
    check_publication_idempotency,
    classify_publication_randomness,
    compute_manifest_sha256,
    resolve_publication_artifact_paths,
    validate_publication_manifest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "tools" / "big649_real_publication_runner.py"
RUNBOOK_PATH = (
    REPO_ROOT
    / "00-Plan"
    / "roadmap"
    / "agent_bootstrap"
    / "BIG649_REAL_PUBLICATION_RUNBOOK.md"
)
P280X_SKILL_PATH = (
    REPO_ROOT
    / "00-Plan"
    / "roadmap"
    / "agent_bootstrap"
    / "BIG649_ONE_SHOT_PUBLICATION_SKILL.md"
)

EXPECTED_STRATEGY_IDS = (
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


def _synthetic_tickets():
    return [
        {
            "strategy_id": strategy_id,
            "bet_index": 1,
            "predicted_main_numbers": list(range(index + 1, index + 7)),
        }
        for index, strategy_id in enumerate(BIG649_FROZEN_STRATEGY_IDS)
    ]


def _candidate(**overrides):
    kwargs = {
        "target_draw": SYNTHETIC_TARGET,
        "target_draw_date": "2099-01-02",
        "official_source_url": "https://example.invalid/synthetic-primary-source",
        "official_source_accessed_at": "2099-01-01T01:00:00+08:00",
        "official_deadline": "2099-01-01T20:00:00+08:00",
        "generation_timestamp_utc": "2099-01-01T02:00:00Z",
        "cutoff_policy": "SYNTHETIC_HISTORY_STRICTLY_BEFORE_TARGET",
        "history_cutoff": "SYNTHETIC_BIG649_HISTORY_CUTOFF",
        "tickets": _synthetic_tickets(),
        "source_digests": {"synthetic_fixture": "1" * 64},
        "tool_digests": {"runner": "2" * 64},
    }
    kwargs.update(overrides)
    return build_publication_manifest_candidate(**kwargs)


def _changed_tickets():
    tickets = _synthetic_tickets()
    tickets[0] = dict(tickets[0])
    tickets[0]["predicted_main_numbers"] = [20, 21, 22, 23, 24, 25]
    return tickets


def test_exact_11_strategy_ids():
    assert BIG649_FROZEN_STRATEGY_IDS == EXPECTED_STRATEGY_IDS
    assert len(BIG649_FROZEN_STRATEGY_IDS) == 11


def test_path_convention_for_synthetic_target():
    assert resolve_publication_artifact_paths(SYNTHETIC_TARGET) == {
        "manifest_json": (
            "outputs/publications/big649/pre_draw/"
            "SYNTHETIC_BIG649_TARGET_DO_NOT_PUBLISH/manifest.json"
        ),
        "manifest_markdown": (
            "outputs/publications/big649/pre_draw/"
            "SYNTHETIC_BIG649_TARGET_DO_NOT_PUBLISH/manifest.md"
        ),
    }


@pytest.mark.parametrize("target", ["../escape", "SYNTHETIC_BIG649_TARGET_DO_NOT_PUBLISH/..", "/tmp/x"])
def test_path_traversal_rejected(target):
    with pytest.raises(PublicationGuardError, match="target_draw"):
        resolve_publication_artifact_paths(target)


def test_target_is_required():
    with pytest.raises(PublicationGuardError, match="target_draw"):
        _candidate(target_draw="")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("official_source_url", "", "official_source_url"),
        ("official_source_accessed_at", "", "official_source_accessed_at"),
        ("official_deadline", "", "official_deadline"),
        ("outcome_unavailable_at_generation", False, "outcome_unavailable"),
        ("no_outcome_used", False, "no_outcome_used"),
        ("prediction_success_claim", True, "prediction_success_claim"),
        ("strategy_promoted", True, "strategy_promoted"),
        ("activation_authorized", True, "activation_authorized"),
    ],
)
def test_required_source_deadline_and_no_claim_flags(field, value, message):
    with pytest.raises(PublicationGuardError, match=message):
        _candidate(**{field: value})


def test_valid_ticket_shape_and_manifest_contract():
    manifest = _candidate()
    assert manifest["mode"] == "SAFE_VALIDATE_ONLY"
    assert manifest["strategy_count"] == 11
    assert manifest["N"] == 1
    assert manifest["bet_index"] == 1
    assert manifest["endpoint"] == "BIG_ANY_PRIZE_AWARE_WIN"
    assert manifest["ticket_validation"]["status"] == "PASS"
    assert len(manifest["tickets"]) == 11


def test_duplicate_numbers_rejected():
    tickets = _synthetic_tickets()
    tickets[0]["predicted_main_numbers"] = [1, 1, 2, 3, 4, 5]
    with pytest.raises(PublicationGuardError, match="duplicate numbers"):
        _candidate(tickets=tickets)


@pytest.mark.parametrize("numbers", [[0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 50]])
def test_out_of_range_numbers_rejected(numbers):
    tickets = _synthetic_tickets()
    tickets[0]["predicted_main_numbers"] = numbers
    with pytest.raises(PublicationGuardError, match="outside 1..49"):
        _candidate(tickets=tickets)


def test_missing_strategy_stops():
    with pytest.raises(PublicationGuardError, match="missing="):
        _candidate(tickets=_synthetic_tickets()[:-1])


def test_extra_strategy_stops():
    tickets = _synthetic_tickets()
    tickets.append(
        {
            "strategy_id": "extra_strategy",
            "bet_index": 1,
            "predicted_main_numbers": [30, 31, 32, 33, 34, 35],
        }
    )
    with pytest.raises(PublicationGuardError, match="extra="):
        _candidate(tickets=tickets)


def test_duplicate_same_manifest_is_already_published_same():
    manifest = _candidate()
    assert check_publication_duplicate(manifest, copy.deepcopy(manifest))["status"] == (
        ALREADY_PUBLISHED_SAME_MANIFEST
    )
    rebuilt = _candidate(existing_manifest=manifest)
    assert rebuilt["duplicate_guard"]["status"] == ALREADY_PUBLISHED_SAME_MANIFEST


def test_duplicate_different_manifest_conflict_stops():
    manifest = _candidate()
    different = _candidate(tickets=_changed_tickets())
    assert check_publication_duplicate(manifest, different)["status"] == (
        DUPLICATE_MANIFEST_CONFLICT_STOP
    )
    with pytest.raises(PublicationGuardError, match=DUPLICATE_MANIFEST_CONFLICT_STOP):
        _candidate(tickets=_changed_tickets(), existing_manifest=manifest)


def test_deterministic_rerun_same_passes():
    manifest = _candidate()
    assert check_publication_idempotency(manifest, copy.deepcopy(manifest))["status"] == (
        IDEMPOTENCY_PASS
    )
    rebuilt = _candidate(previous_manifest=manifest)
    assert rebuilt["idempotency_guard"]["status"] == IDEMPOTENCY_PASS


def test_deterministic_rerun_different_stops():
    manifest = _candidate()
    different = _candidate(tickets=_changed_tickets())
    assert check_publication_idempotency(manifest, different)["status"] == (
        DETERMINISTIC_MISMATCH_STOP
    )
    with pytest.raises(PublicationGuardError, match=DETERMINISTIC_MISMATCH_STOP):
        _candidate(tickets=_changed_tickets(), previous_manifest=manifest)


def test_stochastic_with_seed_and_policy_allowed():
    guard = classify_publication_randomness(
        strategy_kind="stochastic",
        seed="SYNTHETIC-SEED-001",
        policy={"algorithm": "synthetic-fixture-only"},
    )
    assert guard["status"] == STOCHASTIC_READY_WITH_SEED_AND_POLICY
    manifest = _candidate(
        strategy_kind="stochastic",
        randomness_seed="SYNTHETIC-SEED-001",
        randomness_policy={"algorithm": "synthetic-fixture-only"},
    )
    assert manifest["randomness_guard"]["status"] == STOCHASTIC_READY_WITH_SEED_AND_POLICY


def test_stochastic_without_seed_or_policy_stops():
    guard = classify_publication_randomness(strategy_kind="stochastic")
    assert guard["status"] == STOCHASTIC_POLICY_MISSING_STOP
    with pytest.raises(PublicationGuardError, match=STOCHASTIC_POLICY_MISSING_STOP):
        _candidate(strategy_kind="stochastic")


def test_manifest_validator_rejects_forged_stochastic_ready_status():
    manifest = _candidate()
    manifest["randomness_guard"] = {
        "status": STOCHASTIC_READY_WITH_SEED_AND_POLICY,
        "strategy_kind": "stochastic",
        "seed": None,
        "policy": None,
    }
    manifest["manifest_sha256"] = compute_manifest_sha256(manifest)
    with pytest.raises(PublicationGuardError, match="seed/policy missing"):
        validate_publication_manifest(manifest)


def test_manifest_hash_is_deterministic():
    first = _candidate()
    second = _candidate()
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first["manifest_sha256"] == compute_manifest_sha256(first)


def test_manifest_mutation_invalidates_hash():
    manifest = _candidate()
    manifest["history_cutoff"] = "MUTATED_SYNTHETIC_CUTOFF"
    with pytest.raises(PublicationGuardError, match="manifest hash mismatch"):
        validate_publication_manifest(manifest)


def test_runner_has_no_db_import_open_or_database_library_behavior():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
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
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint({"open", "connect", "create_engine"})
    assert "SQLAlchemy" not in source


def test_runner_has_no_network_or_github_publication_side_effect():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported_roots.isdisjoint(
        {"requests", "httpx", "socket", "subprocess", "github", "urllib3"}
    )
    forbidden_calls = {"urlopen", "request", "post", "put", "create_pull_request"}
    attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert attributes.isdisjoint(forbidden_calls)


def test_runbook_contains_required_stop_rules():
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    required = [
        "does not authorize real publication by itself",
        "separate explicit Owner authorization",
        "primary-source based",
        "One Owner authorization = one target attempt.",
        "One target attempt = one manifest candidate.",
        "Do not rerun to improve numbers.",
        "Duplicate guard before write.",
        "Idempotency guard before write.",
        "Randomness guard before write.",
        "Deterministic mismatch = STOP.",
        "Stochastic without seed/policy = STOP.",
        "Outcome unavailable must be verified before generation.",
        "No post-draw evaluation in the publication task.",
        "Publication PR must be before the official deadline.",
        "must not be merged or modified unless separately authorized",
        "Branch deletion is unauthorized.",
        "DB write/copy is unauthorized.",
        "real task must STOP",
    ]
    assert all(phrase in text for phrase in required)


def test_p280x_skill_pointer_added_without_weakening_stop_rules():
    text = P280X_SKILL_PATH.read_text(encoding="utf-8")
    required_old_rules = [
        "This skill never selects target by itself.",
        "This skill never publishes real tickets by itself.",
        "One Owner authorization = one run.",
        "One run = one manifest candidate.",
        "If deterministic rerun differs, STOP.",
        "If random strategy lacks seed/policy, STOP.",
        "If any DB path is touched, STOP.",
    ]
    assert all(rule in text for rule in required_old_rules)
    assert "P280X is dry-run planning." in text
    assert "BIG649_REAL_PUBLICATION_RUNBOOK.md" in text
    assert "Real publication remains separate Owner authorization." in text


def test_research_json_records_no_real_execution_claims():
    path = REPO_ROOT / "outputs/research/p280ad_big649_real_publication_tooling_20260619.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["no_real_target_selected"] is True
    assert artifact["no_official_deadline_lookup"] is True
    assert artifact["no_real_ticket_generated"] is True
    assert artifact["no_publication_pr_created"] is True
    assert artifact["no_future_evaluation"] is True
    assert artifact["database_access"] == {
        "opened": False,
        "queried": False,
        "copied": False,
        "written": False,
    }
