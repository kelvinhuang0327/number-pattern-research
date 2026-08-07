from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import math
import random
import re
import sys
from pathlib import Path
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "research/p1_family_independent_reproduction_r5"
BUILDER_PATH = PACKAGE / "build_reproduction.py"
SCHEMA_PATH = PACKAGE / "result.schema.json"
RUNTIME_ROOT = Path(
    "/Users/kelvin/Kelvin-WorkSpace/.runtime/LotteryNew/"
    "p1-family-independent-reproduction-r5"
)

SPEC = importlib.util.spec_from_file_location("p1_r5_builder", BUILDER_PATH)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILDER
SPEC.loader.exec_module(BUILDER)


class Draft202012Validator:
    """Closed, dependency-free validator for the exact schema keyword subset used here."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    def validate(self, instance: Any, schema: dict[str, Any] | None = None) -> None:
        self._validate(instance, self.schema if schema is None else schema, "$")

    def _resolve(self, reference: str) -> dict[str, Any]:
        assert reference.startswith("#/")
        value: Any = self.schema
        for part in reference[2:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
        return value

    def _validate(self, value: Any, schema: dict[str, Any], path: str) -> None:
        if "$ref" in schema:
            self._validate(value, self._resolve(schema["$ref"]), path)
        if "if" in schema:
            try:
                self._validate(value, schema["if"], path)
            except (AssertionError, TypeError, ValueError):
                if "else" in schema:
                    self._validate(value, schema["else"], path)
            else:
                if "then" in schema:
                    self._validate(value, schema["then"], path)
        for part in schema.get("allOf", []):
            self._validate(value, part, path)
        if "anyOf" in schema:
            failures = []
            for part in schema["anyOf"]:
                try:
                    self._validate(value, part, path)
                    break
                except (AssertionError, TypeError, ValueError) as exc:
                    failures.append(exc)
            else:
                raise AssertionError(f"{path}: no anyOf branch matched: {failures}")
        if "const" in schema:
            assert value == schema["const"], f"{path}: const"
        if "enum" in schema:
            assert value in schema["enum"], f"{path}: enum"
        expected = schema.get("type")
        if expected is None and isinstance(value, dict) and "properties" in schema:
            for key, part in schema["properties"].items():
                if key in value:
                    self._validate(value[key], part, f"{path}.{key}")
        if isinstance(value, list):
            assert len(value) >= schema.get("minItems", 0)
            assert len(value) <= schema.get("maxItems", len(value))
            if "contains" in schema:
                matches = 0
                for item in value:
                    try:
                        self._validate(item, schema["contains"], f"{path}[]")
                    except (AssertionError, TypeError, ValueError):
                        continue
                    matches += 1
                assert matches >= schema.get("minContains", 1), f"{path}: contains"
                assert matches <= schema.get("maxContains", matches), f"{path}: contains"
        if expected == "object":
            assert isinstance(value, dict), f"{path}: object"
            required = set(schema.get("required", []))
            assert required <= set(value), f"{path}: required"
            if schema.get("additionalProperties") is False:
                assert set(value) <= set(schema.get("properties", {})), path
            for key, part in schema.get("properties", {}).items():
                if key in value:
                    self._validate(value[key], part, f"{path}.{key}")
        elif expected == "array":
            assert isinstance(value, list), f"{path}: array"
            assert len(value) >= schema.get("minItems", 0)
            assert len(value) <= schema.get("maxItems", len(value))
            if schema.get("uniqueItems"):
                rendered = [json.dumps(item, sort_keys=True) for item in value]
                assert len(rendered) == len(set(rendered))
            prefix = schema.get("prefixItems", [])
            for index, part in enumerate(prefix):
                if index < len(value):
                    self._validate(value[index], part, f"{path}[{index}]")
            items = schema.get("items")
            if items is False:
                assert len(value) <= len(prefix)
            elif isinstance(items, dict):
                for index, item in enumerate(value[len(prefix) :], len(prefix)):
                    self._validate(item, items, f"{path}[{index}]")
        elif expected == "string":
            assert isinstance(value, str), f"{path}: string"
            assert len(value) >= schema.get("minLength", 0)
            if "pattern" in schema:
                assert re.fullmatch(schema["pattern"], value)
        elif expected == "integer":
            assert isinstance(value, int) and not isinstance(value, bool)
        elif expected == "number":
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
            assert math.isfinite(value)
        elif expected == "boolean":
            assert isinstance(value, bool)
        elif expected == "null":
            assert value is None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema:
                assert value >= schema["minimum"]
            if "maximum" in schema:
                assert value <= schema["maximum"]


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def all_object_schemas(value: Any):
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield value
        for child in value.values():
            yield from all_object_schemas(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_object_schemas(child)


def metric(eligible: int, hits: int, controls: int, probability: float) -> dict[str, Any]:
    observed = hits / eligible
    control_rate = controls / eligible
    edge = observed - probability
    return {
        "eligible_draws": eligible,
        "strategy_hits": hits,
        "observed_hit_rate": observed,
        "random_probability": probability,
        "edge_decimal": edge,
        "edge_percentage_points": edge * 100.0,
        "orthogonal_hits": controls,
        "orthogonal_hit_rate": control_rate,
        "p1_minus_orthogonal_decimal": observed - control_rate,
    }


def valid_strategy(identity: str, ticket_count: int) -> dict[str, Any]:
    probability = 0.1
    w150 = metric(150, 15, 15, probability)
    w500 = metric(500, 50, 50, probability)
    w1500 = metric(1500, 150, 150, probability)
    oos = metric(44, 4, 4, probability)
    incremental = None
    if ticket_count == 5:
        incremental = {
            "eligible_draws": 1500,
            "four_bet_hits": 140,
            "five_bet_hits": 150,
            "four_bet_hit_rate": 140 / 1500,
            "five_bet_hit_rate": 150 / 1500,
            "five_minus_four_hit_rate": 10 / 1500,
            "diagnostic_only": True,
        }
    return {
        "strategy_identity": identity,
        "reproduction_valid": True,
        "invalid_reasons": [],
        "hard_gate_results": {
            "edge500_decimal": 0.0,
            "edge500_percentage_points": 0.0,
            "edge500_pass": False,
            "edge1500_decimal": 0.0,
            "edge1500_percentage_points": 0.0,
            "edge1500_pass": False,
            "monte_carlo_p1500": 0.5,
            "monte_carlo_p1500_pass": False,
            "oos_eligible_draws": 44,
            "oos_mature": False,
            "edge_oos_decimal": None,
            "edge_oos_percentage_points": None,
            "edge_oos_pass": None,
        },
        "insufficient_evidence_reasons": [],
        "diagnostic_results": {
            "ticket_count": ticket_count,
            "complete_draw_count": 2127,
            "eligible_draw_count": 2124,
            "first_eligible_draw": 96000004,
            "last_eligible_draw": 115000072,
            "skipped_draws": [
                {"draw": draw, "reason": "INSUFFICIENT_HISTORICAL_PREFIX"}
                for draw in (96000001, 96000002, 96000003)
            ],
            "random_probability": probability,
            "window150": w150,
            "window500": w500,
            "window1500": w1500,
            "oos": oos,
            "orthogonal_control": {
                "ticket_count": ticket_count,
                "slice": [0, ticket_count],
                "eligible_draws": 2124,
                "hits": 212,
                "hit_rate": 212 / 2124,
                "p1_minus_control_hit_rate": 0.0,
                "diagnostic_only": True,
            },
            "monte_carlo": {
                "B": 9999,
                "null_statistics_count": 9999,
                "subseed_sha256": BUILDER.subseed(identity, ticket_count)[0],
                "subseed_integer": BUILDER.subseed(identity, ticket_count)[1],
                "observed_statistic": 0.1,
                "upper_tail_count": 4999,
                "p_value": 0.5,
                "alternative": "greater",
                "epsilon": 1e-12,
            },
            "mcnemar": {"b": 0, "c": 0, "discordant_count": 0, "p_value": 1.0},
            "sharpe": {
                "rolling_window": 300,
                "step": 150,
                "window_edges": [0.0] * 9,
                "value": None,
                "status": "UNDEFINED_ZERO_VARIANCE",
            },
            "incremental_5_vs_4": incremental,
        },
        "outcome": "FAIL",
        "outcome_precedence_rule": BUILDER.OUTCOME_PRECEDENCE,
    }


def valid_semantic_result() -> dict[str, Any]:
    return {
        "strategy_results": [
            valid_strategy("BIG_LOTTO_P1_DEVIATION_4BET", 4),
            valid_strategy("BIG_LOTTO_P1_DEVIATION_5BET", 5),
        ]
    }


def invalid_monte_carlo_result() -> dict[str, Any]:
    result = valid_semantic_result()
    for row in result["strategy_results"]:
        row["reproduction_valid"] = False
        row["invalid_reasons"] = ["MONTE_CARLO_COUNT_INVALID"]
        row["outcome"] = "INVALID_REPRODUCTION"
        row["diagnostic_results"]["monte_carlo"]["upper_tail_count"] = None
        row["diagnostic_results"]["monte_carlo"]["p_value"] = None
        row["hard_gate_results"]["monte_carlo_p1500"] = None
        row["hard_gate_results"]["monte_carlo_p1500_pass"] = None
    return result


def make_executable(path: Path, *, executable: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test interpreter terminal\n")
    path.chmod(0o755 if executable else 0o644)
    return path


def configure_runtime_process(
    monkeypatch: pytest.MonkeyPatch,
    runtime_root: Path,
    interpreter: Path,
    *,
    prefix: Path | None = None,
) -> None:
    monkeypatch.setattr(BUILDER, "EXPECTED_RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(BUILDER.sys, "executable", interpreter.as_posix())
    monkeypatch.setattr(
        BUILDER.sys,
        "prefix",
        (runtime_root / "venv" if prefix is None else prefix).as_posix(),
    )


@pytest.mark.parametrize("basename", ["python3.12", "python3"])
def test_runtime_identity_accepts_standard_uv_relative_alias(
    basename: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    terminal = make_executable(runtime_root / "venv/bin/python")
    interpreter = terminal.parent / basename
    interpreter.symlink_to("python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    identity = BUILDER.require_runtime_identity(REPO, runtime_root)
    assert identity["lexical_interpreter_path"] == interpreter.as_posix()
    assert identity["resolved_terminal_path"] == terminal.as_posix()
    assert identity["symlink_hops"] == [
        {
            "path": interpreter.as_posix(),
            "target": "python",
            "next_path": terminal.as_posix(),
        }
    ]


def test_runtime_identity_accepts_direct_venv_python_regular_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = make_executable(runtime_root / "venv/bin/python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    identity = BUILDER.require_runtime_identity(REPO, runtime_root)
    assert identity["resolved_terminal_path"] == interpreter.as_posix()
    assert identity["symlink_hops"] == []


def test_runtime_identity_accepts_uv_alias_into_runtime_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    terminal = make_executable(
        runtime_root / "python/cpython-3.12.12-macos-aarch64-none/bin/python3.12"
    )
    venv_python = runtime_root / "venv/bin/python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(terminal)
    interpreter = venv_python.parent / "python3.12"
    interpreter.symlink_to("python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    identity = BUILDER.require_runtime_identity(REPO, runtime_root)
    assert identity["resolved_terminal_path"] == terminal.as_posix()
    assert [hop["target"] for hop in identity["symlink_hops"]] == [
        "python",
        terminal.as_posix(),
    ]


@pytest.mark.parametrize("escape_kind", ["absolute", "relative"])
def test_runtime_identity_rejects_symlink_escape(
    escape_kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    outside = make_executable(tmp_path / "outside-python")
    interpreter = runtime_root / "venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    target = outside if escape_kind == "absolute" else Path("../../../outside-python")
    interpreter.symlink_to(target)
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*escaped",
    ) as failure:
        BUILDER.require_runtime_identity(REPO, runtime_root)
    assert "lexical_interpreter_path" in failure.value.detail
    assert "resolved_terminal_path" in failure.value.detail


def test_runtime_identity_rejects_broken_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = runtime_root / "venv/bin/python3.12"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to("python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*broken",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_runtime_identity_rejects_symlink_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = runtime_root / "venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to("python3")
    (interpreter.parent / "python3").symlink_to("python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*loop",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_runtime_identity_rejects_symlink_hop_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    venv_bin = runtime_root / "venv/bin"
    venv_bin.mkdir(parents=True)
    interpreter = venv_bin / "python"
    interpreter.symlink_to("link-0")
    for index in range(BUILDER.MAX_INTERPRETER_SYMLINK_HOPS):
        target = f"link-{index + 1}"
        (venv_bin / f"link-{index}").symlink_to(target)
    make_executable(venv_bin / f"link-{BUILDER.MAX_INTERPRETER_SYMLINK_HOPS}")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*hop bound",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_runtime_identity_rejects_intermediate_directory_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    runtime_root.mkdir()
    outside_venv = tmp_path / "outside-venv"
    interpreter = make_executable(outside_venv / "bin/python")
    (runtime_root / "venv").symlink_to(outside_venv)
    lexical_interpreter = runtime_root / "venv/bin/python"
    configure_runtime_process(monkeypatch, runtime_root, lexical_interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*escaped",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)
    assert interpreter.is_file()


def test_runtime_identity_rejects_unexpected_interpreter_basename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = make_executable(runtime_root / "venv/bin/pypy")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*approved lexical",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_runtime_identity_rejects_system_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BUILDER.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(BUILDER.sys, "prefix", (RUNTIME_ROOT / "venv").as_posix())
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*approved lexical",
    ):
        BUILDER.require_runtime_identity(REPO, RUNTIME_ROOT)


@pytest.mark.parametrize("terminal_kind", ["directory", "non-executable"])
def test_runtime_identity_rejects_invalid_terminal(
    terminal_kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = runtime_root / "venv/bin/python"
    if terminal_kind == "directory":
        interpreter.mkdir(parents=True)
    else:
        make_executable(interpreter, executable=False)
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*regular executable",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_runtime_identity_rejects_wrong_task_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong_root = tmp_path / "another-task-runtime"
    interpreter = make_executable(wrong_root / "venv/bin/python")
    monkeypatch.setattr(BUILDER.sys, "executable", interpreter.as_posix())
    monkeypatch.setattr(BUILDER.sys, "prefix", (wrong_root / "venv").as_posix())
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*wrong task runtime",
    ):
        BUILDER.require_runtime_identity(REPO, wrong_root)


def test_runtime_identity_rejects_wrong_sys_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = make_executable(runtime_root / "venv/bin/python")
    configure_runtime_process(
        monkeypatch,
        runtime_root,
        interpreter,
        prefix=tmp_path / "another-venv",
    )
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*sys.prefix",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_runtime_identity_rejects_wrong_python_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = make_executable(runtime_root / "venv/bin/python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    monkeypatch.setattr(BUILDER.platform, "python_version", lambda: "3.12.11")
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*version mismatch",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


@pytest.mark.parametrize(
    "identity_constant",
    ["INSTALLATION_RECEIPT_SHA256", "RUNTIME_FINGERPRINT_V3"],
)
def test_runtime_identity_rejects_environment_r3_fingerprint_mismatch(
    identity_constant: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "approved-runtime"
    interpreter = make_executable(runtime_root / "venv/bin/python")
    configure_runtime_process(monkeypatch, runtime_root, interpreter)
    monkeypatch.setattr(BUILDER, identity_constant, "0" * 64)
    with pytest.raises(
        BUILDER.ReproductionInvalid,
        match="RUNTIME_FINGERPRINT_MISMATCH.*Environment R3",
    ):
        BUILDER.require_runtime_identity(REPO, runtime_root)


def test_build_reproduction_entry_executes_actual_runtime_identity_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SourceIdentityReached(RuntimeError):
        pass

    def stop_after_runtime_identity(*_args: Any, **_kwargs: Any) -> bytes:
        raise SourceIdentityReached("production source identity reached")

    monkeypatch.setattr(BUILDER, "_git", stop_after_runtime_identity)
    with pytest.raises(SourceIdentityReached, match="production source identity reached"):
        BUILDER.build_reproduction(REPO, RUNTIME_ROOT)


def test_schema_identity_and_required_field_order() -> None:
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("p1-family-independent-reproduction-r5-result-v1.json")
    assert schema["title"] == "LotteryNewP1FamilyIndependentReproductionResultR5"
    assert schema["x-schema-version"] == "1.0.0"
    for object_schema in all_object_schemas(schema):
        assert object_schema["additionalProperties"] is False
        assert object_schema["required"] == object_schema["x-canonical-order"]
        assert set(object_schema["required"]) == set(object_schema["properties"])
    assert "RunComparisonV1" in schema["$defs"]
    assert len(schema["$defs"]["strategyResult"]["allOf"]) >= 7
    validator = Draft202012Validator(schema)
    result = valid_semantic_result()
    for index, row in enumerate(result["strategy_results"]):
        validator.validate(
            row, schema["properties"]["strategy_results"]["prefixItems"][index]
        )
    contradictory = valid_strategy("BIG_LOTTO_P1_DEVIATION_4BET", 4)
    contradictory["reproduction_valid"] = False
    contradictory["outcome"] = "PASS"
    with pytest.raises(AssertionError):
        validator.validate(
            contradictory,
            schema["properties"]["strategy_results"]["prefixItems"][0],
        )
    wrong_position = valid_strategy("BIG_LOTTO_P1_DEVIATION_4BET", 4)
    wrong_position["diagnostic_results"]["ticket_count"] = 5
    with pytest.raises(AssertionError):
        validator.validate(
            wrong_position,
            schema["properties"]["strategy_results"]["prefixItems"][0],
        )


def test_invalid_reproduction_nullability_is_reason_scoped() -> None:
    schema = load_schema()
    validator = Draft202012Validator(schema)
    prefixes = schema["properties"]["strategy_results"]["prefixItems"]
    legal = invalid_monte_carlo_result()
    for index, row in enumerate(legal["strategy_results"]):
        validator.validate(row, prefixes[index])
    BUILDER.validate_result_semantics(legal)
    assert legal["strategy_results"][0]["hard_gate_results"]["edge500_decimal"] == 0.0
    assert legal["strategy_results"][0]["hard_gate_results"]["edge500_pass"] is False

    valid_with_nulls = invalid_monte_carlo_result()
    for row in valid_with_nulls["strategy_results"]:
        row["reproduction_valid"] = True
        row["invalid_reasons"] = []
        row["outcome"] = "FAIL"
    with pytest.raises(AssertionError):
        validator.validate(valid_with_nulls["strategy_results"][0], prefixes[0])
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(valid_with_nulls)

    empty_reasons = invalid_monte_carlo_result()
    empty_reasons["strategy_results"][0]["invalid_reasons"] = []
    with pytest.raises(AssertionError):
        validator.validate(empty_reasons["strategy_results"][0], prefixes[0])
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(empty_reasons)

    unrelated_reason = invalid_monte_carlo_result()
    unrelated_reason["strategy_results"][0]["invalid_reasons"] = ["TICKET_INVALID"]
    with pytest.raises(AssertionError):
        validator.validate(unrelated_reason["strategy_results"][0], prefixes[0])
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(unrelated_reason)

    calculable_gate_null = invalid_monte_carlo_result()
    calculable_gate_null["strategy_results"][0]["hard_gate_results"][
        "edge500_decimal"
    ] = None
    with pytest.raises(AssertionError):
        validator.validate(calculable_gate_null["strategy_results"][0], prefixes[0])
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(calculable_gate_null)


def test_canonical_result_bytes_and_normalized_strategy_order() -> None:
    schema = load_schema()
    prefix = schema["properties"]["strategy_results"]["prefixItems"]
    assert prefix[0]["allOf"][1]["properties"]["strategy_identity"]["const"].endswith(
        "4BET"
    )
    assert prefix[1]["allOf"][1]["properties"]["strategy_identity"]["const"].endswith(
        "5BET"
    )
    sample = {"z": 1, "a": -0.0}
    payload = BUILDER.canonical_bytes(sample)
    assert payload == b'{"z":1,"a":0.0}\n'
    assert payload.endswith(b"\n") and not payload.endswith(b"\n\n")
    result_path = PACKAGE / "result.json"
    if result_path.exists():
        raw = result_path.read_bytes()
        instance = json.loads(raw)
        Draft202012Validator(schema).validate(instance)
        BUILDER.validate_result_semantics(instance)
        assert raw == BUILDER.canonical_bytes(instance)


def test_source_blob_callable_and_six_function_ast_closure() -> None:
    historical = BUILDER.require_blob(
        REPO, BUILDER.ALGORITHM_COMMIT, BUILDER.ALGORITHM_PATH, BUILDER.ALGORITHM_BLOB
    )
    functions = BUILDER._functions(historical, "historical")
    assert tuple(name for name in BUILDER.ALGORITHM_CLOSURE if name in functions) == (
        BUILDER.ALGORITHM_CLOSURE
    )
    algorithm, control = BUILDER.source_closures(REPO)
    assert algorithm.__name__ == BUILDER.ALGORITHM_CALLABLE
    assert control.__name__ == BUILDER.CONTROL_SYMBOL


def test_historical_module_import_and_DatabaseManager_are_never_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded(name: str, *args: Any, **kwargs: Any):
        if name in {"database", "lottery_api.database"}:
            raise AssertionError("historical database import executed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    BUILDER.source_closures(REPO)
    module = ast.parse(BUILDER_PATH.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module in {"database", "lottery_api.database"}
        for node in ast.walk(module)
    )


def test_snapshot_identity_readonly_immutable_query_only_and_no_sidecars() -> None:
    draws = BUILDER.load_draws()
    assert len(draws) == 2127
    assert draws[0].draw == 96000001
    assert draws[-1].draw == 115000072
    assert not Path(f"{BUILDER.SNAPSHOT_PATH}-wal").exists()
    assert not Path(f"{BUILDER.SNAPSHOT_PATH}-shm").exists()


def test_draw_order_prefix_is_exact_and_future_blind() -> None:
    draws = BUILDER.load_draws()
    assert all(a.draw < b.draw for a, b in zip(draws, draws[1:]))
    for index in (3, 100, len(draws) - 1):
        prefix = [draw.history_row() for draw in draws[:index]]
        assert len(prefix) == index
        assert prefix[-1]["draw"] < draws[index].draw
        assert draws[index].draw not in {row["draw"] for row in prefix}


def test_ticket_validity_and_exact_4_5_counts() -> None:
    raw = [{"numbers": list(range(1 + offset * 6, 7 + offset * 6))} for offset in range(5)]
    assert len(BUILDER.validate_tickets(raw, 4)) == 4
    assert len(BUILDER.validate_tickets(raw, 5)) == 5
    with pytest.raises(BUILDER.ReproductionInvalid, match="TICKET_COUNT_INVALID"):
        BUILDER.validate_tickets(raw[:3], 4)
    with pytest.raises(BUILDER.ReproductionInvalid, match="TICKET_INVALID"):
        BUILDER.validate_tickets([{"numbers": [1, 1, 2, 3, 4, 5]}] * 4, 4)


def test_target_event_m4plus_excludes_special() -> None:
    tickets = [[1, 2, 3, 4, 40, 41]]
    assert BUILDER.hit(tickets, [1, 2, 3, 4, 5, 6])
    assert not BUILDER.hit(tickets, [1, 2, 3, 5, 6, 7])
    assert not BUILDER.hit([[1, 2, 3, 49, 48, 47]], [1, 2, 3, 4, 5, 6])


def test_equal_ticket_random_baseline_uses_4_and_5() -> None:
    p4 = BUILDER.equal_ticket_probability(4)
    p5 = BUILDER.equal_ticket_probability(5)
    assert 0 < p4 < p5 < 1
    total = math.comb(49, 6)
    single = sum(
        math.comb(6, m) * math.comb(43, 6 - m) / total for m in range(4, 7)
    )
    assert p4 == 1 - (1 - single) ** 4
    assert p5 == 1 - (1 - single) ** 5


def test_orthogonal_slices_and_forbidden_controls() -> None:
    authority = BUILDER._authorities()["diagnostic_control"]
    assert authority["lottery_type"] == "BIG_LOTTO"
    assert authority["main_number_max"] == 49
    assert authority["four_bet_slice"] == [0, 4]
    assert authority["five_bet_slice"] == [0, 5]
    assert authority["diagnostic_only"] is True
    assert authority["symbol"] != BUILDER.ALGORITHM_CALLABLE


def test_windows_edges_and_exact_zero_failure() -> None:
    metric = BUILDER.window_metric([True, False], [False, False], 0.5)
    assert metric["edge_decimal"] == 0
    hard = {
        "edge500_pass": metric["edge_decimal"] > 0,
        "edge1500_pass": True,
        "monte_carlo_p1500_pass": True,
        "oos_mature": True,
        "edge_oos_pass": True,
    }
    assert BUILDER.outcome_for(True, [], hard)[0] == "FAIL"
    valid = valid_semantic_result()
    BUILDER.validate_result_semantics(valid)
    valid["strategy_results"][0]["diagnostic_results"]["window500"][
        "edge_percentage_points"
    ] = 1.0
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(valid)


def test_subseed_preimage_vectors_independent_rng_version2() -> None:
    assert BUILDER.subseed("BIG_LOTTO_P1_DEVIATION_4BET", 4)[0] == (
        "b13bf2d7fc3ce6299fffa57a4c42d110e9724c87d9070857b4995fe4773691f3"
    )
    assert BUILDER.subseed("BIG_LOTTO_P1_DEVIATION_5BET", 5)[0] == (
        "06063d4ee2e642c42f9c792971553d50ed04954e832452a72d129941db4b147a"
    )
    assert BUILDER.subseed("BIG_LOTTO_P1_DEVIATION_4BET", 4)[1] != BUILDER.subseed(
        "BIG_LOTTO_P1_DEVIATION_5BET", 5
    )[1]


def test_mc_B_plus_one_epsilon_and_p_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedRandom:
        def seed(self, value: int, version: int) -> None:
            assert value >= 0 and version == 2

        def random(self) -> float:
            return 1.0

    monkeypatch.setattr(BUILDER.random, "Random", FixedRandom)
    rng = BUILDER.independent_rng("BIG_LOTTO_P1_DEVIATION_4BET", 4)
    result = BUILDER.monte_carlo(
        "BIG_LOTTO_P1_DEVIATION_4BET", 4, 1.0, rng=rng, b=9999
    )
    assert result["upper_tail_count"] == 0
    assert result["p_value"] == 0.0001
    assert (0.025 < 0.025) is False
    with pytest.raises(BUILDER.ReproductionInvalid, match="MONTE_CARLO_COUNT_INVALID"):
        BUILDER.monte_carlo(
            "BIG_LOTTO_P1_DEVIATION_4BET", 4, 0.1, rng=rng, b=9998
        )
    invalid = valid_semantic_result()
    invalid["strategy_results"][0]["diagnostic_results"]["monte_carlo"][
        "p_value"
    ] = 0.4
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(invalid)


def test_oos_cutoff_maturity_and_edge_gate() -> None:
    hard = {
        "edge500_pass": True,
        "edge1500_pass": True,
        "monte_carlo_p1500_pass": True,
        "oos_mature": False,
        "edge_oos_pass": None,
    }
    assert BUILDER.outcome_for(True, [], hard) == (
        "INSUFFICIENT_EVIDENCE",
        ["OOS_ELIGIBLE_DRAWS_LT_150"],
    )
    hard.update(oos_mature=True, edge_oos_pass=False)
    assert BUILDER.outcome_for(True, [], hard)[0] == "FAIL"
    valid = valid_semantic_result()
    valid["strategy_results"][0]["hard_gate_results"]["oos_mature"] = True
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(valid)


def test_production_monte_carlo_pair_rejects_shared_rng_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BUILDER, "MONTE_CARLO_B", 3)
    monkeypatch.setattr(BUILDER, "MONTE_CARLO_WINDOW", 2)
    observed = {4: 0.1, 5: 0.2}
    created: list[tuple[str, int, random.Random]] = []

    def tracking_factory(strategy: str, ticket_count: int) -> random.Random:
        rng = BUILDER.independent_rng(strategy, ticket_count)
        created.append((strategy, ticket_count, rng))
        return rng

    global_state = random.getstate()
    results = BUILDER.production_monte_carlo_pair(
        observed, rng_factory=tracking_factory, b=3
    )
    assert [item[:2] for item in created] == list(BUILDER.STRATEGIES)
    assert created[0][2] is not created[1][2]
    assert list(results) == [4, 5]
    assert [results[count]["subseed_sha256"] for count in results] == [
        "b13bf2d7fc3ce6299fffa57a4c42d110e9724c87d9070857b4995fe4773691f3",
        "06063d4ee2e642c42f9c792971553d50ed04954e832452a72d129941db4b147a",
    ]
    assert random.getstate() == global_state

    shared = random.Random(7)
    with pytest.raises(
        BUILDER.ReproductionInvalid, match="RNG_INDEPENDENCE_INVALID"
    ):
        BUILDER.production_monte_carlo_pair(
            observed, rng_factory=lambda _strategy, _count: shared, b=3
        )
    assert random.getstate() == global_state


def test_outcome_precedence_truth_table() -> None:
    base = {
        "edge500_pass": True,
        "edge1500_pass": True,
        "monte_carlo_p1500_pass": True,
        "oos_mature": True,
        "edge_oos_pass": True,
    }
    assert BUILDER.outcome_for(False, ["TICKET_INVALID"], base)[0] == (
        "INVALID_REPRODUCTION"
    )
    assert BUILDER.outcome_for(True, [], base)[0] == "PASS"
    for key in ("edge500_pass", "edge1500_pass", "monte_carlo_p1500_pass"):
        candidate = dict(base)
        candidate[key] = False
        assert BUILDER.outcome_for(True, [], candidate)[0] == "FAIL"
    contradictory = valid_semantic_result()
    contradictory["strategy_results"][0]["outcome"] = "PASS"
    with pytest.raises(BUILDER.ReproductionInvalid, match="RESULT_SCHEMA_INVALID"):
        BUILDER.validate_result_semantics(contradictory)


def test_missing_nonfinite_mature_values_invalid() -> None:
    with pytest.raises(BUILDER.ReproductionInvalid, match="MANDATORY_VALUE_MISSING"):
        BUILDER.require_finite(None, "edge_oos_decimal")
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(
            BUILDER.ReproductionInvalid, match="MANDATORY_VALUE_NONFINITE"
        ):
            BUILDER.require_finite(value, "edge_oos_decimal")


def test_mcnemar_exact_and_zero_discordance() -> None:
    assert BUILDER.mcnemar([True, False], [True, False]) == {
        "b": 0,
        "c": 0,
        "discordant_count": 0,
        "p_value": 1.0,
    }
    result = BUILDER.mcnemar([True, True, False], [False, True, True])
    assert result["discordant_count"] == result["b"] + result["c"]
    assert 0 <= result["p_value"] <= 1


def test_sharpe_nine_windows_and_zero_variance() -> None:
    undefined = BUILDER.sharpe_diagnostic([False] * 1500, 0.0)
    assert undefined["window_edges"] == [0.0] * 9
    assert undefined["value"] is None
    assert undefined["status"] == "UNDEFINED_ZERO_VARIANCE"
    changing = BUILDER.sharpe_diagnostic(
        [index % 7 == 0 for index in range(1500)], 0.1
    )
    assert len(changing["window_edges"]) == 9


def test_two_run_canonical_and_per_draw_byte_identity(tmp_path: Path) -> None:
    run1, run2 = tmp_path / "run1", tmp_path / "run2"
    run1.mkdir()
    run2.mkdir()
    for root in (run1, run2):
        (root / "result.json").write_bytes(b'{"same":true}\n')
        (root / "p1_4bet_per_draw.jsonl").write_bytes(b'{"draw":1}\n')
        (root / "p1_5bet_per_draw.jsonl").write_bytes(b'{"draw":1}\n')
    comparison = BUILDER.comparison_document(run1, run2)
    validator = Draft202012Validator(load_schema())
    validator.validate(comparison, load_schema()["$defs"]["RunComparisonV1"])
    assert comparison["result_byte_identical"] is True
    assert comparison["per_draw_bundle_byte_identical"] is True


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("changed source-blob hex", "SOURCE_IDENTITY_MISMATCH"),
        ("nonexistent callable substitution", "SOURCE_CLOSURE_INVALID"),
        ("historical module import or DatabaseManager execution", "blocked import"),
        ("draws[:i+1]", "PREFIX_ISOLATION_FAILED"),
        ("wrong ticket count or algorithm slice", "TICKET_COUNT_INVALID"),
        ("orthogonal [1:5]", "CONTROL_SLICE_INVALID"),
        ("POWER_LOTTO maximum 38", "CONTROL_LOTTERY_INVALID"),
        ("P1 self-control", "CONTROL_SELF_REFERENCE"),
        ("B=9998", "MONTE_CARLO_COUNT_INVALID"),
        ("shared RNG state", "RNG_INDEPENDENCE_INVALID"),
        ("omitted NUL", "SUBSEED_VECTOR_INVALID"),
        ("reversed strategy order", "RESULT_SCHEMA_INVALID"),
        ("cutoff-inclusive OOS", "OOS_BOUNDARY_INVALID"),
        ("p <= 0.025 acceptance", "P_VALUE_BOUNDARY_INVALID"),
        ("NaN serialization", "ValueError"),
        ("unsorted reason/set output", "RESULT_SCHEMA_INVALID"),
        ("missing schema required property", "RESULT_SCHEMA_INVALID"),
        ("any added result property", "RESULT_SCHEMA_INVALID"),
        ("result or per-draw byte mismatch", "RUN_OUTPUT_MISMATCH"),
        ("MANIFEST coverage omission", "SEAL_COVERAGE_INVALID"),
        ("checksum ordering or format mutation", "SEAL_FORMAT_INVALID"),
    ],
)
def test_mutation_matrix(
    mutation: str,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert mutation and expected
    if mutation == "changed source-blob hex":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.require_blob(REPO, BUILDER.ALGORITHM_COMMIT, BUILDER.ALGORITHM_PATH, "0" * 40)
    elif mutation == "nonexistent callable substitution":
        monkeypatch.setattr(BUILDER, "ALGORITHM_CALLABLE", "nonexistent_callable")
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.source_closures(REPO)
    elif mutation == "historical module import or DatabaseManager execution":
        original_import = builtins.__import__

        def guarded(name: str, *args: Any, **kwargs: Any):
            if name in {"database", "lottery_api.database"}:
                raise AssertionError("blocked import")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", guarded)
        with pytest.raises(AssertionError, match=expected):
            builtins.__import__("database")
        compiled_algorithm, _ = BUILDER.source_closures(REPO)
        assert "DatabaseManager" not in compiled_algorithm.__globals__
    elif mutation == "draws[:i+1]":
        target = BUILDER.Draw(20, "x", (1, 2, 3, 4, 5, 6), 7)
        contaminated = [{"draw": 10}, {"draw": 20}]
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.require_prefix(contaminated, target, 2)
    elif mutation == "wrong ticket count or algorithm slice":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_tickets([], 4)
    elif mutation == "orthogonal [1:5]":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_control_policy(
                lottery_type="BIG_LOTTO",
                maximum_number=49,
                four_slice=(1, 5),
                five_slice=(0, 5),
                control_symbol=BUILDER.CONTROL_SYMBOL,
            )
    elif mutation == "POWER_LOTTO maximum 38":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_control_policy(
                lottery_type="POWER_LOTTO",
                maximum_number=38,
                four_slice=(0, 4),
                five_slice=(0, 5),
                control_symbol=BUILDER.CONTROL_SYMBOL,
            )
    elif mutation == "P1 self-control":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_control_policy(
                lottery_type="BIG_LOTTO",
                maximum_number=49,
                four_slice=(0, 4),
                five_slice=(0, 5),
                control_symbol=BUILDER.ALGORITHM_CALLABLE,
            )
    elif mutation == "B=9998":
        rng = BUILDER.independent_rng("BIG_LOTTO_P1_DEVIATION_4BET", 4)
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.monte_carlo(
                "BIG_LOTTO_P1_DEVIATION_4BET", 4, 0.1, rng=rng, b=9998
            )
    elif mutation == "shared RNG state":
        rng = BUILDER.independent_rng("BIG_LOTTO_P1_DEVIATION_4BET", 4)
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.production_monte_carlo_pair(
                {4: 0.1, 5: 0.1},
                rng_factory=lambda _strategy, _count: rng,
            )
    elif mutation == "omitted NUL":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.subseed_preimage(
                "BIG_LOTTO_P1_DEVIATION_4BET", 4, separator=b""
            )
    elif mutation == "NaN serialization":
        with pytest.raises(ValueError):
            BUILDER.canonical_bytes({"value": math.nan})
    elif mutation == "reversed strategy order":
        rows = [
            {"strategy_identity": "BIG_LOTTO_P1_DEVIATION_5BET"},
            {"strategy_identity": "BIG_LOTTO_P1_DEVIATION_4BET"},
        ]
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_strategy_order(rows)
    elif mutation == "cutoff-inclusive OOS":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_oos_selection([{"draw": BUILDER.CUTOFF_DRAW}])
    elif mutation == "p <= 0.025 acceptance":
        assert BUILDER.p_value_pass(0.025) is False
        assert BUILDER.p_value_pass(math.nextafter(0.025, 0.0)) is True
    elif mutation == "unsorted reason/set output":
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.normalize_reason_array(["TICKET_INVALID", "SOURCE_CLOSURE_INVALID"])
    elif mutation in {
        "missing schema required property",
        "any added result property",
    }:
        comparison = {
            "schema_version": BUILDER.COMPARISON_SCHEMA_VERSION,
            "task_name": BUILDER.TASK_NAME,
            "run1_result_sha256": "0" * 64,
            "run2_result_sha256": "0" * 64,
            "result_byte_identical": True,
            "run1_per_draw_bundle_sha256": "0" * 64,
            "run2_per_draw_bundle_sha256": "0" * 64,
            "per_draw_bundle_byte_identical": True,
            "canonical_result_sha256": "0" * 64,
            "decision": "ACCEPT_BYTE_IDENTICAL_RUNS",
        }
        if mutation.startswith("missing"):
            del comparison["decision"]
        else:
            comparison["extra"] = True
        validator = Draft202012Validator(load_schema())
        with pytest.raises(AssertionError):
            validator.validate(
                comparison, load_schema()["$defs"]["RunComparisonV1"]
            )
    elif mutation == "result or per-draw byte mismatch":
        run1, run2 = tmp_path / "a", tmp_path / "b"
        run1.mkdir()
        run2.mkdir()
        for root, value in ((run1, b"1"), (run2, b"2")):
            (root / "result.json").write_bytes(value)
            (root / "p1_4bet_per_draw.jsonl").write_bytes(b"")
            (root / "p1_5bet_per_draw.jsonl").write_bytes(b"")
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.comparison_document(run1, run2)
    elif mutation == "MANIFEST coverage omission":
        manifest = {
            "sha256sums_coverage": list(BUILDER.CONTENT_PATHS),
        }
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_manifest_coverage(manifest)
    elif mutation == "checksum ordering or format mutation":
        paths = ["a", "b"]
        malformed = f"{'0' * 64}  b\n{'0' * 64} a\n"
        with pytest.raises(BUILDER.ReproductionInvalid, match=expected):
            BUILDER.validate_sha256sum_lines(malformed, paths)
    else:
        raise AssertionError(f"unhandled mutation: {mutation}")
