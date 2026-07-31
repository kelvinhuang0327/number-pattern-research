from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest

from tools.big649_one_shot_publication_runner import (
    ALREADY_PUBLISHED_SAME_MANIFEST,
    BIG649_FROZEN_STRATEGY_IDS,
    DRY_RUN_ONLY_NOT_PUBLISHED,
    DRY_RUN_TARGET_LABEL,
    DUPLICATE_PUBLICATION_CONFLICT,
    IDEMPOTENCY_PASS,
    NOT_A_REAL_PREDICTION,
    NO_EXISTING_MANIFEST,
    RANDOMNESS_ALLOWED_WITH_SEED,
    RANDOMNESS_POLICY_MISSING,
    STOP_UNEXPLAINED_NONDETERMINISM,
    ProtocolValidationError,
    build_default_strategy_tickets,
    build_dry_run_manifest,
    check_duplicate_manifest,
    check_idempotency,
    manifest_sha256,
    stop_on_unexplained_difference,
    validate_ticket,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "agent_bootstrap" / "BIG649_ONE_SHOT_PUBLICATION_SKILL.md"
RUNNER_PATH = REPO_ROOT / "tools" / "big649_one_shot_publication_runner.py"

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


def _origin_main_sha() -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
        text=True,
    ).strip()


def _base_manifest():
    return build_dry_run_manifest(origin_main_sha=_origin_main_sha())


def _modified_manifest():
    tickets = build_default_strategy_tickets()
    tickets[0] = dict(tickets[0])
    tickets[0]["predicted_main_numbers"] = [1, 2, 3, 4, 5, 7]
    return build_dry_run_manifest(
        origin_main_sha=_origin_main_sha(),
        strategy_tickets=tickets,
    )


def test_exact_11_strategy_ids():
    assert BIG649_FROZEN_STRATEGY_IDS == EXPECTED_STRATEGY_IDS
    assert len(BIG649_FROZEN_STRATEGY_IDS) == 11


def test_dry_run_manifest_sets_required_no_publication_flags():
    manifest = _base_manifest()

    assert manifest["mode"] == "DRY_RUN_ONLY"
    assert manifest["publication_status"] == "NOT_PUBLISHED"
    assert manifest["dry_run_warning"] == NOT_A_REAL_PREDICTION
    assert manifest["target_draw_label"] == DRY_RUN_TARGET_LABEL
    assert manifest["real_target_selected"] is False
    assert manifest["real_ticket_published"] is False
    assert manifest["official_deadline_lookup"] is False
    assert manifest["future_evaluation_started"] is False
    assert manifest["no_github_publication_side_effect"] is True
    assert manifest["publication_guard_state"] == DRY_RUN_ONLY_NOT_PUBLISHED


def test_validate_ticket_accepts_one_to_forty_nine_unique_numbers():
    assert validate_ticket([1, 2, 3, 4, 5, 6]) == [1, 2, 3, 4, 5, 6]


def test_missing_strategy_and_extra_strategy_stop():
    missing = build_default_strategy_tickets()[:-1]
    with pytest.raises(ProtocolValidationError, match="exact frozen 11"):
        build_dry_run_manifest(origin_main_sha=_origin_main_sha(), strategy_tickets=missing)

    extra = build_default_strategy_tickets()
    extra.append(
        {
            "strategy_id": "extra_strategy",
            "bet_index": 1,
            "predicted_main_numbers": [1, 2, 3, 4, 5, 6],
        }
    )
    with pytest.raises(ProtocolValidationError, match="exact frozen 11"):
        build_dry_run_manifest(origin_main_sha=_origin_main_sha(), strategy_tickets=extra)


def test_duplicate_checks_distinguish_same_and_different_manifests():
    base = _base_manifest()
    same = copy.deepcopy(base)
    different = _modified_manifest()

    assert check_duplicate_manifest(base, same)["status"] == ALREADY_PUBLISHED_SAME_MANIFEST
    assert check_duplicate_manifest(base, different)["status"] == DUPLICATE_PUBLICATION_CONFLICT


def test_idempotency_checks_distinguish_same_and_different_manifests():
    base = _base_manifest()
    same = copy.deepcopy(base)
    different = _modified_manifest()

    assert check_idempotency(base, same)["status"] == IDEMPOTENCY_PASS

    with pytest.raises(ProtocolValidationError, match=STOP_UNEXPLAINED_NONDETERMINISM):
        stop_on_unexplained_difference(base, different, strategy_kind="deterministic")


def test_stochastic_rerun_rules():
    base = _base_manifest()
    different = _modified_manifest()

    allowed = check_idempotency(
        base,
        different,
        strategy_kind="stochastic",
        randomness_policy={"seed_source": "recorded"},
        seed="P280X-SEED-001",
    )
    assert allowed["status"] == RANDOMNESS_ALLOWED_WITH_SEED

    returned = stop_on_unexplained_difference(
        base,
        different,
        strategy_kind="stochastic",
        randomness_policy={"seed_source": "recorded"},
        seed="P280X-SEED-001",
    )
    assert returned["status"] == RANDOMNESS_ALLOWED_WITH_SEED

    with pytest.raises(ProtocolValidationError, match=RANDOMNESS_POLICY_MISSING):
        stop_on_unexplained_difference(base, different, strategy_kind="stochastic")


def test_manifest_hash_is_deterministic_and_mutation_changes_it():
    manifest_a = _base_manifest()
    manifest_b = _base_manifest()
    assert manifest_a["manifest_sha256"] == manifest_b["manifest_sha256"]
    assert manifest_a["manifest_sha256"] == manifest_sha256(manifest_a)

    mutated = copy.deepcopy(manifest_a)
    mutated["history_snapshot_digest"] = "0" * 64
    assert manifest_sha256(mutated) != manifest_a["manifest_sha256"]


def test_no_db_or_github_publication_side_effects_are_referenced_in_source():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    forbidden_tokens = [
        "sqlite3",
        "sqlalchemy",
        "SQLAlchemy",
        "sqlite://",
        ".connect(",
        "publish_pull_request",
        "create_pull_request",
    ]
    assert all(token not in source for token in forbidden_tokens)


def test_runbook_contains_required_guardrails():
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    required_phrases = [
        "never selects target",
        "never publishes real tickets",
        "Use the runner",
        "One Owner authorization = one run.",
        "One run = one manifest candidate.",
        "Check duplicate before write.",
        "Check idempotency before write.",
        "Check randomness policy before write.",
        "If deterministic rerun differs, STOP.",
        "If random strategy lacks seed/policy, STOP.",
        "If any DB path is touched, STOP.",
        "Real publication requires separate explicit Owner authorization.",
    ]
    assert all(phrase in text for phrase in required_phrases)
