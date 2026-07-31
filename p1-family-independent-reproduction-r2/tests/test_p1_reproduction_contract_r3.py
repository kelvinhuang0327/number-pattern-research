from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
BUILDER_PATH = (
    REPO / "research" / "p1_reproduction_contract_r3" / "build_contract.py"
)
SPEC = importlib.util.spec_from_file_location("p1_contract_r3_builder", BUILDER_PATH)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILDER
SPEC.loader.exec_module(BUILDER)


def load_contract() -> dict:
    return json.loads(
        (
            REPO
            / "research"
            / "p1_reproduction_contract_r3"
            / "contract.json"
        ).read_bytes()
    )


def load_orthogonal() -> dict:
    return json.loads(
        (
            REPO
            / "research"
            / "p1_reproduction_contract_r3"
            / "orthogonal_authority.json"
        ).read_bytes()
    )


def test_deterministic_regeneration_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    BUILDER.write_content_outputs(REPO, first, check=False)
    BUILDER.write_content_outputs(REPO, second, check=False)
    assert {
        path.name: path.read_bytes() for path in sorted(first.iterdir())
    } == {
        path.name: path.read_bytes() for path in sorted(second.iterdir())
    }


def test_checked_in_outputs_are_canonical() -> None:
    BUILDER.write_content_outputs(
        REPO,
        REPO / BUILDER.PACKAGE_ROOT,
        check=True,
    )


def test_all_commit_path_blob_identities() -> None:
    contract = load_contract()
    control = contract["diagnostic_control_authority"]
    assert control["commit"] == BUILDER.PINS.adopted_commit
    assert control["path"] == BUILDER.PINS.adopted_path
    assert control["blob"] == BUILDER.PINS.adopted_blob
    assert control["helper_commit"] == BUILDER.PINS.helper_commit
    assert control["helper_path"] == BUILDER.PINS.helper_path
    assert control["helper_blob"] == BUILDER.PINS.helper_blob
    for role in ("four_bet", "five_bet"):
        authority = contract["historical_algorithm_source_authorities"][role]
        assert authority["commit"] == BUILDER.PINS.historical_commit
        assert authority["path"] == BUILDER.PINS.historical_path
        assert authority["blob"] == BUILDER.PINS.historical_blob


def test_historical_absence_and_later_presence() -> None:
    contract = load_contract()
    orthogonal = load_orthogonal()
    assert contract["historical_orthogonal_absence"]["status"] == "ABSENT"
    assert orthogonal["historical_absence"]["symbol_status"] == "ABSENT"
    assert orthogonal["source"]["symbol"] == "biglotto_5bet_orthogonal"


def test_helper_blob_equality_at_both_commits() -> None:
    orthogonal = load_orthogonal()
    helper = orthogonal["helper"]
    assert helper["commit"] == BUILDER.PINS.helper_commit
    assert helper["comparison_commit"] == BUILDER.PINS.helper_comparison_commit
    assert helper["blob"] == BUILDER.PINS.helper_blob
    assert helper["blob_equality"] is True


def test_exact_four_function_import_closure() -> None:
    orthogonal = load_orthogonal()
    assert tuple(orthogonal["source_closure"]["direct_imports"]) == (
        "fourier_rhythm_bet",
        "cold_numbers_bet",
        "tail_balance_bet",
        "markov_orthogonal_bet",
    )


def test_callable_closure_has_no_db_network_random_or_filesystem_dependency() -> None:
    verification = load_orthogonal()["semantic_verification"]
    assert verification["db_dependency"] == "ABSENT_IN_APPROVED_CALLABLE_CLOSURE"
    assert verification["network_dependency"] == "ABSENT_IN_APPROVED_CALLABLE_CLOSURE"
    assert verification["random_dependency"] == "ABSENT_IN_APPROVED_CALLABLE_CLOSURE"
    source = BUILDER.source_evidence(REPO, BUILDER.PINS)
    assert source["isolation"]["filesystem_dependency"] == (
        "ABSENT_IN_APPROVED_CALLABLE_CLOSURE"
    )


def test_big_lotto_range_and_five_ordered_tickets() -> None:
    semantic = load_orthogonal()["semantic_verification"]
    assert semantic["lottery_type"] == "BIG_LOTTO"
    assert semantic["main_number_range"] == [1, 49]
    assert semantic["ticket_count"] == 5
    assert semantic["ordered_tickets"] == [
        "bet1",
        "bet2",
        "bet3",
        "bet4",
        "bet5",
    ]


def test_equal_ticket_slices_are_exact() -> None:
    contract = load_contract()["diagnostic_control_authority"]
    assert contract["four_bet_comparator_ticket_slice"] == {
        "start": 0,
        "stop": 4,
        "meaning": "FIRST_FOUR_ORDERED_ORTHOGONAL_TICKETS",
    }
    assert contract["five_bet_comparator_ticket_slice"] == {
        "start": 0,
        "stop": 5,
        "meaning": "ALL_FIVE_ORDERED_ORTHOGONAL_TICKETS",
    }


def test_power_control_and_p1_self_control_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="POWER_LOTTO"):
        BUILDER.validate_control_policy(
            lottery_type="POWER_LOTTO",
            maximum_number=38,
            source_role="DIAGNOSTIC_CONTROL_AUTHORITY",
        )
    with pytest.raises(RuntimeError, match="own control"):
        BUILDER.validate_control_policy(
            lottery_type="BIG_LOTTO",
            maximum_number=49,
            source_role="ALGORITHM_SOURCE_AUTHORITY",
        )


def test_diagnostic_flags_are_closed() -> None:
    classification = load_contract()["classification"]
    assert classification == {
        "evidence_status": "HISTORICAL_RESEARCH_ONLY",
        "current_significance": "NOT_ESTABLISHED",
        "diagnostic_only": True,
        "production_eligible": False,
        "ranking_eligible": False,
        "promotion_eligible": False,
        "rejection_authority": False,
        "live_db_execution_allowed": False,
        "production_wiring_allowed": False,
    }


def test_prefix_only_and_determinism_boundaries() -> None:
    contract = load_contract()["diagnostic_control_authority"]
    semantic = load_orthogonal()["semantic_verification"]
    assert contract["input_boundary"] == "SUPPLIED_HISTORICAL_DRAW_PREFIX_ONLY"
    assert contract["determinism"] == "REQUIRED"
    assert semantic["prefix_only_input"] is True
    assert semantic["deterministic"] is True


def test_outputs_have_no_timestamp_or_machine_local_path() -> None:
    package = REPO / BUILDER.PACKAGE_ROOT
    for name in ("contract.json", "orthogonal_authority.json", "REPORT.md"):
        text = (package / name).read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert "generated_at" not in text
        assert "datetime.now" not in text


def test_environment_r3_identities_match_merged_package() -> None:
    environment = load_contract()["environment_authority"]
    assert environment == {
        "merge_commit": BUILDER.PINS.environment_merge_commit,
        "fixed_head": BUILDER.PINS.environment_fixed_head,
        "fixed_tree": BUILDER.PINS.environment_fixed_tree,
        "root": BUILDER.PINS.environment_root,
        "installation_receipt_sha256": (
            BUILDER.PINS.installation_receipt_sha256
        ),
        "runtime_fingerprint_v3": BUILDER.PINS.runtime_fingerprint_v3,
        "reference_only": True,
        "modified_by_this_contract": False,
    }


def test_builder_has_no_db_network_or_strategy_runtime_import() -> None:
    module = ast.parse(BUILDER_PATH.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert not (
        imports
        & {
            "sqlite3",
            "requests",
            "urllib",
            "socket",
            "httpx",
            "aiohttp",
            "random",
        }
    )
    commands = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]
    assert len(commands) == 1


def test_exact_package_path_allowlist() -> None:
    assert BUILDER.PACKAGE_PATHS == (
        "research/p1_reproduction_contract_r3/build_contract.py",
        "research/p1_reproduction_contract_r3/contract.json",
        "research/p1_reproduction_contract_r3/orthogonal_authority.json",
        "research/p1_reproduction_contract_r3/REPORT.md",
        "research/p1_reproduction_contract_r3/MANIFEST.json",
        "research/p1_reproduction_contract_r3/SHA256SUMS",
        "tests/test_p1_reproduction_contract_r3.py",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("historical_commit", "0" * 40, "immutable Git read failed"),
        ("historical_blob", "0" * 40, "pinned blob mismatch"),
        ("main_number_max", 38, "closed policy mismatch"),
        ("ticket_count", 4, "closed policy mismatch"),
        ("helper_blob", "0" * 40, "pinned blob mismatch"),
        ("current_significance", "ESTABLISHED", "closed policy mismatch"),
    ],
)
def test_mutation_sensitive_failures(
    field: str,
    value: object,
    message: str,
) -> None:
    mutated = dataclasses.replace(BUILDER.PINS, **{field: value})
    with pytest.raises(RuntimeError, match=message):
        BUILDER.build_documents(REPO, mutated)


def test_task_effects_are_all_closed() -> None:
    assert load_contract()["task_effects"] == {
        "db_opened": False,
        "backtest_run": False,
        "reproduction_run": False,
        "strategy_executed": False,
        "production_changed": False,
        "rejection_state_changed": False,
        "environment_authority_changed": False,
    }


def test_module_level_nonclosure_code_is_explicitly_excluded() -> None:
    closure = load_orthogonal()["source_closure"]
    assert closure["module_import_execution_approved"] is False
    assert closure["strategy_or_backtest_execution_performed"] is False
    dispositions = {
        row["disposition"] for row in closure["module_level_nonclosure_findings"]
    }
    assert dispositions == {"EXCLUDED_NOT_APPROVED_NOT_EXECUTED"}


def test_canonical_json_is_stable_key_order_with_newline() -> None:
    package = REPO / BUILDER.PACKAGE_ROOT
    for name in ("contract.json", "orthogonal_authority.json"):
        payload = (package / name).read_bytes()
        assert payload.endswith(b"\n")
        assert payload == BUILDER.canonical_bytes(json.loads(payload))


def test_no_seal_files_exist_before_content_judge() -> None:
    package = REPO / BUILDER.PACKAGE_ROOT
    manifest = package / "MANIFEST.json"
    sums = package / "SHA256SUMS"
    if manifest.exists() or sums.exists():
        BUILDER.write_seal(REPO, check=True)


def test_git_object_reads_do_not_change_repository_status() -> None:
    before = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain=v1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    BUILDER.build_documents(REPO)
    after = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain=v1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert before == after


def test_document_digest_is_reproducible() -> None:
    first = BUILDER.build_documents(REPO)
    second = BUILDER.build_documents(REPO)
    first_digest = hashlib.sha256(
        b"".join(first[name] for name in sorted(first))
    ).hexdigest()
    second_digest = hashlib.sha256(
        b"".join(second[name] for name in sorted(second))
    ).hexdigest()
    assert first_digest == second_digest
