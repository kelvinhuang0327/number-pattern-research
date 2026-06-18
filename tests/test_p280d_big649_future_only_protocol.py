from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from analysis import p280d_big649_future_only_protocol as protocol


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_JSON = ROOT / "outputs/research/p280d_big649_future_only_freeze_protocol_20260618.json"
ARTIFACT_MD = ROOT / "outputs/research/p280d_big649_future_only_freeze_protocol_20260618.md"
GENERATOR_SOURCE = ROOT / "tools/backtest_biglotto_enhancements.py"


def independent_bytes(value):
    return (json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ) + "\n").encode("utf-8")


def independent_manifest_hash(manifest):
    payload = copy.deepcopy(manifest)
    payload.pop("manifest_sha256", None)
    return hashlib.sha256(independent_bytes(payload)).hexdigest()


def synthetic_history():
    return [
        {"draw": draw, "numbers": sorted({
            ((draw * 7 + offset * 11 - 1) % 49) + 1 for offset in range(6)
        })}
        for draw in range(1, 41)
    ]


def source_digests():
    return {
        strategy_id: {
            "source_path": f"synthetic/{strategy_id}.py",
            "git_blob_sha1": hashlib.sha1(strategy_id.encode()).hexdigest(),
            "sha256": hashlib.sha256(strategy_id.encode()).hexdigest(),
            "generator_identity": f"synthetic:{strategy_id}",
        }
        for strategy_id in protocol.STRATEGY_IDS
    }


def build_kwargs():
    history = synthetic_history()
    return {
        "target_draw": 41,
        "target_draw_deadline_at": "2099-01-02T20:00:00+08:00",
        "deadline_timezone": "Asia/Taipei",
        "local_generated_at": "2099-01-02T19:00:00+08:00",
        "history_cutoff_draw": 40,
        "history": history,
        "strategy_tickets": protocol.synthetic_strategy_tickets(history),
        "origin_main_sha": "a" * 40,
        "protocol_source_sha256": "b" * 64,
        "strategy_source_digests": source_digests(),
    }


def build_manifest(**changes):
    kwargs = build_kwargs()
    kwargs.update(changes)
    return protocol.build_prediction_manifest(**kwargs)


def rehash(manifest):
    manifest["manifest_sha256"] = independent_manifest_hash(manifest)


def test_frozen_strategy_set_is_exact_lexical_11():
    assert len(protocol.STRATEGY_IDS) == 11
    assert list(protocol.STRATEGY_IDS) == sorted(protocol.STRATEGY_IDS)
    assert protocol.PRIMARY_BUDGET == protocol.BET_INDEX == 1
    assert protocol.ENDPOINT_ID == "BIG_ANY_PRIZE_AWARE_WIN"


def test_canonical_serializer_matches_independent_implementation():
    value = {"z": [3, 2, 1], "a": {"台": True, "x": None}}
    assert protocol.canonical_json_bytes(value) == independent_bytes(value)


def test_manifest_is_deterministic_under_strategy_and_history_reordering():
    kwargs = build_kwargs()
    first = protocol.build_prediction_manifest(**kwargs)
    kwargs["history"] = list(reversed(kwargs["history"]))
    kwargs["strategy_tickets"] = list(reversed(kwargs["strategy_tickets"]))
    second = protocol.build_prediction_manifest(**kwargs)
    assert first == second
    assert first["manifest_sha256"] == independent_manifest_hash(first)


def test_deterministic_hash_golden_value():
    manifest = build_manifest()
    assert manifest["manifest_sha256"] == (
        "523609ade0f4159851eea0e8a6cc601754da42416db910ce8e88103879091d49"
    )


@pytest.mark.parametrize("mode", ["missing", "duplicate", "extra"])
def test_rejects_non_exact_strategy_set(mode):
    kwargs = build_kwargs()
    records = kwargs["strategy_tickets"]
    if mode == "missing":
        records = records[:-1]
    elif mode == "duplicate":
        records = records + [copy.deepcopy(records[0])]
    else:
        records = records + [{
            "strategy_id": "not_frozen", "bet_index": 1,
            "predicted_main_numbers": [1, 2, 3, 4, 5, 6],
        }]
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.build_prediction_manifest(**{**kwargs, "strategy_tickets": records})


@pytest.mark.parametrize("numbers", [
    [1, 2, 3, 4, 5],
    [1, 2, 3, 4, 5, 5],
    [0, 2, 3, 4, 5, 6],
    [1, 2, 3, 4, 5, 50],
    [1, 2, 3, 4, 5, "6"],
])
def test_rejects_invalid_ticket(numbers):
    kwargs = build_kwargs()
    kwargs["strategy_tickets"][0]["predicted_main_numbers"] = numbers
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.build_prediction_manifest(**kwargs)


def test_rejects_non_one_bet_index():
    kwargs = build_kwargs()
    kwargs["strategy_tickets"][0]["bet_index"] = 2
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.build_prediction_manifest(**kwargs)


@pytest.mark.parametrize("target,cutoff", [(40, 40), (39, 40)])
def test_rejects_equal_or_later_cutoff(target, cutoff):
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(target_draw=target, history_cutoff_draw=cutoff)


def test_rejects_future_history_row_and_cutoff_gap():
    kwargs = build_kwargs()
    kwargs["history"].append({"draw": 41, "numbers": [1, 2, 3, 4, 5, 6]})
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.build_prediction_manifest(**kwargs)
    kwargs = build_kwargs()
    kwargs["history_cutoff_draw"] = 39
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.build_prediction_manifest(**kwargs)


def test_rejects_target_outcome_and_outcome_based_selection():
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(target_outcome={"actual_numbers": [1, 2, 3, 4, 5, 6]})
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(outcome_based_ticket_selection=True)


@pytest.mark.parametrize("field,value", [
    ("origin_main_sha", ""),
    ("protocol_source_sha256", ""),
    ("freeze_id", "wrong"),
    ("previous_manifest_sha256", "not-a-hash"),
])
def test_rejects_missing_or_invalid_identity_digest(field, value):
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(**{field: value})


def test_rejects_missing_strategy_source_digest():
    digests = source_digests()
    digests.pop(protocol.STRATEGY_IDS[0])
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(strategy_source_digests=digests)


def test_rejects_at_or_after_deadline_and_timezone_mismatch():
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(local_generated_at="2099-01-02T20:00:00+08:00")
    with pytest.raises(protocol.ProtocolValidationError):
        build_manifest(target_draw_deadline_at="2099-01-02T20:00:00+00:00")


def test_rejects_outcome_field_even_when_rehashed():
    manifest = build_manifest()
    manifest["actual_numbers"] = [1, 2, 3, 4, 5, 6]
    rehash(manifest)
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.validate_prediction_manifest(manifest)


def test_mutation_detection():
    manifest = build_manifest()
    manifest["strategies"][0]["canonical_sorted_ticket"][0] += 1
    with pytest.raises(protocol.ProtocolValidationError):
        protocol.validate_prediction_manifest(manifest)


def test_previous_manifest_chain():
    first = build_manifest()
    second = build_manifest(
        target_draw=42,
        history_cutoff_draw=41,
        history=synthetic_history() + [{"draw": 41, "numbers": [1, 2, 3, 4, 5, 6]}],
        previous_manifest_sha256=first["manifest_sha256"],
    )
    assert second["previous_manifest_sha256"] == first["manifest_sha256"]
    protocol.validate_prediction_manifest(second)


def test_duplicate_ticket_is_recorded_without_merging_strategy_identity():
    kwargs = build_kwargs()
    kwargs["strategy_tickets"][1]["predicted_main_numbers"] = copy.deepcopy(
        kwargs["strategy_tickets"][0]["predicted_main_numbers"]
    )
    manifest = protocol.build_prediction_manifest(**kwargs)
    assert len(manifest["strategies"]) == 11
    first, second = manifest["strategies"][:2]
    assert first["ticket_sha256"] == second["ticket_sha256"]
    assert first["duplicate_ticket_relationship"] == {
        "collision": True, "other_strategy_ids": [second["strategy_id"]],
    }
    assert second["duplicate_ticket_relationship"] == {
        "collision": True, "other_strategy_ids": [first["strategy_id"]],
    }


def test_synthetic_rehearsal_is_in_memory_and_deterministic(tmp_path):
    before = list(tmp_path.iterdir())
    kwargs = build_kwargs()
    tickets_one = protocol.synthetic_strategy_tickets(kwargs["history"])
    tickets_two = protocol.synthetic_strategy_tickets(kwargs["history"])
    assert tickets_one == tickets_two
    assert len(tickets_one) == 11
    assert [record["strategy_id"] for record in tickets_one] == list(protocol.STRATEGY_IDS)
    assert all(record["bet_index"] == 1 for record in tickets_one)
    assert all(
        len(record["predicted_main_numbers"]) == 6
        and len(set(record["predicted_main_numbers"])) == 6
        and record["predicted_main_numbers"] == sorted(record["predicted_main_numbers"])
        and all(1 <= number <= 49 for number in record["predicted_main_numbers"])
        for record in tickets_one
    )
    build_manifest(strategy_tickets=tickets_one)
    assert list(tmp_path.iterdir()) == before


def test_module_has_no_db_network_or_repository_output_interfaces():
    source = (ROOT / "analysis/p280d_big649_future_only_protocol.py").read_text()
    forbidden = ["import sqlite3", "requests", "urllib", "subprocess", "open(", "write_text("]
    assert all(token not in source for token in forbidden)


def test_generator_database_dependency_is_cli_local_only():
    tree = ast.parse(GENERATOR_SOURCE.read_text(encoding="utf-8"))
    module_imports = [
        node for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "lottery_api.database"
        for node in module_imports
    )
    assert not any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) == "DatabaseManager"
        for node in tree.body
    )

    main = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "lottery_api.database"
        and [alias.name for alias in node.names] == ["DatabaseManager"]
        for node in main.body
    )


def test_generator_import_and_n1_call_are_db_side_effect_free(tmp_path):
    expected = [
        {
            "case": "synthetic_100",
            "input_sha256": "9fd3aa40efdc293685e98a41f4b5f66f5b779c0196b94dbd17f9d2efd75c32f0",
            "output_sha256": "d7d49072b0c5a16d99f8699f3e7497ea2c330bf1d28ec6736262d610c59a2c7f",
            "ticket": [6, 13, 20, 27, 34, 48],
        },
        {
            "case": "synthetic_137",
            "input_sha256": "e58ce6151e770017212ef67d54f4c210f96a7a4c7b16bde84daed5b578f71226",
            "output_sha256": "b5c1f222987b1a9de4dd959b66f1e41d6bcf8be932ac6e764690c742c21a5497",
            "ticket": [7, 14, 21, 35, 42, 49],
        },
        {
            "case": "synthetic_211_reversed_then_canonicalized",
            "input_sha256": "13fb148c7c64e358cbee02440e6709882d1ac545565b68a156805dc518d7a91a",
            "output_sha256": "7fa1e45d759c24a8ade99de1680e5f740cfad3bd1aaa444a1f0887690aec820e",
            "ticket": [5, 12, 26, 36, 45, 47],
        },
    ]
    script = textwrap.dedent(
        """
        import hashlib
        import importlib.abc
        import json
        import os
        import sys

        class DatabaseBlocker(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "lottery_api.database" or fullname.startswith("sqlalchemy"):
                    raise RuntimeError(f"forbidden database import: {fullname}")
                return None

        def blocked_path(value):
            try:
                path = os.fspath(value)
            except TypeError:
                return False
            if isinstance(path, bytes):
                path = os.fsdecode(path)
            lowered = path.lower().split("?", 1)[0]
            return lowered.endswith((".db", ".sqlite", ".sqlite3"))

        def audit(event, args):
            if event == "sqlite3.connect":
                raise RuntimeError(f"forbidden sqlite connection: {args!r}")
            if event == "open" and args and blocked_path(args[0]):
                raise RuntimeError(f"forbidden database path access: {args[0]!r}")

        sys.meta_path.insert(0, DatabaseBlocker())
        sys.addaudithook(audit)

        import tools.backtest_biglotto_enhancements
        from lottery_api.models.replay_strategy_registry import get_adapter

        def canonical_bytes(value):
            return json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")

        def digest(value):
            return hashlib.sha256(canonical_bytes(value)).hexdigest()

        def history(length, multiplier, offset):
            rows = []
            for index in range(length):
                base = (index * multiplier + offset) % 49
                numbers = sorted({((base + step * 7) % 49) + 1 for step in range(6)})
                rows.append({
                    "draw": str(900000000 + index),
                    "date": f"2024-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
                    "numbers": numbers,
                    "special": ((base + 43) % 49) + 1,
                })
            return rows

        cases = [
            ("synthetic_100", history(100, 3, 1)),
            ("synthetic_137", history(137, 5, 11)),
            ("synthetic_211_reversed_then_canonicalized", list(reversed(history(211, 9, 23)))),
        ]
        adapter = get_adapter("ts3_regime_3bet")
        results = []
        for name, raw in cases:
            canonical = sorted(raw, key=lambda row: int(row["draw"]))
            first, special = adapter.get_one_bet(canonical, "BIG_LOTTO")
            rerun, rerun_special = adapter.get_one_bet(canonical, "BIG_LOTTO")
            assert (first, special) == (rerun, rerun_special)
            assert special is None
            results.append({
                "case": name,
                "input_sha256": digest(canonical),
                "output_sha256": digest({"bet_index": 1, "predicted_main_numbers": first}),
                "ticket": first,
            })
        print(json.dumps(results, sort_keys=True))
        """
    )
    env = os.environ.copy()
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
        "PYTHONPATH": str(ROOT),
    })
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == expected


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def test_freeze_artifact_reconciles_protocol_and_strategy_sources():
    artifact = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    protocol.validate_freeze_artifact(artifact)
    protocol_bytes = (ROOT / "analysis/p280d_big649_future_only_protocol.py").read_bytes()
    assert artifact["protocol_source_sha256"] == hashlib.sha256(protocol_bytes).hexdigest()
    for record in artifact["strategies"]:
        data = (ROOT / record["source_path"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(data).hexdigest()
        assert record["git_blob_sha1"] == git_blob_sha1(data)


def test_artifacts_exclude_performance_selection_and_real_prediction_data():
    artifact = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    rendered = json.dumps(artifact, sort_keys=True).lower()
    forbidden_keys = [
        '"p_value"', '"historical_win_count"', '"candidate_ranking"',
        '"best_strategy"', '"worst_strategy"', '"real_target_draw"',
        '"future_ticket"',
    ]
    assert all(key not in rendered for key in forbidden_keys)
    assert artifact["claims"] == {
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "activation_authorized": False,
    }
    markdown = ARTIFACT_MD.read_text(encoding="utf-8")
    assert artifact["freeze_id"] in markdown
    assert "NO_VALID_PRE_DRAW_PUBLICATION" in markdown
    assert "real future prediction" not in markdown.lower()
    assert artifact["final_classification"] == (
        "P280D_BIG649_FUTURE_ONLY_FREEZE_PROTOCOL_IMPLEMENTED_NOT_ACTIVATED"
    )
    assert "PR_OPEN_NOT_ACTIVATED" not in ARTIFACT_JSON.read_text(encoding="utf-8")
    assert "PR_OPEN_NOT_ACTIVATED" not in markdown
    assert "this PR must remain open" not in markdown
