from __future__ import annotations

import ast
import base64
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = PROJECT_ROOT / "tools" / "build_environment_authority.py"
SPEC = importlib.util.spec_from_file_location("p1_env_r3_builder", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
SHA256_RE = __import__("re").compile(r"^[0-9a-f]{64}$")

R2_ROOT = PROJECT_ROOT.parent / "p1_reproduction_environment_authority_r2"
R1_ROOT = PROJECT_ROOT.parent / "p1_reproduction_environment_authority_r1"


def load_json(name: str) -> dict:
    return json.loads((PROJECT_ROOT / name).read_text(encoding="utf-8"))


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def assert_schema_required_properties(instance: dict, schema: dict) -> None:
    missing = [field for field in schema["required"] if field not in instance]
    assert not missing, f"missing required properties: {missing}"


def record_hash(payload: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
    return "sha256=" + encoded.rstrip(b"=").decode("ascii")


def write_record(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def fixture_install(
    tmp_path: Path,
    *,
    console_scripts: dict[str, str] | None = None,
    launcher_relative_path: str = "bin/demo",
) -> tuple[Path, Path, list[list[str]]]:
    """A minimal installed distribution, optionally with a console script."""
    root = tmp_path / "install"
    site = root / "lib" / "python3.12" / "site-packages"
    package = site / "demo" / "__init__.py"
    dist_info = site / "demo-1.0.dist-info"
    package.parent.mkdir(parents=True)
    dist_info.mkdir()
    package.write_bytes(b"VALUE = 1\n")
    metadata = dist_info / "METADATA"
    metadata.write_bytes(b"Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n")
    uv_cache = dist_info / "uv_cache.json"
    uv_cache.write_bytes(
        b'{"timestamp":{"secs_since_epoch":1,"nanos_since_epoch":2}}'
    )
    rows = [
        ["demo/__init__.py", record_hash(package.read_bytes()), str(package.stat().st_size)],
        [
            "demo-1.0.dist-info/METADATA",
            record_hash(metadata.read_bytes()),
            str(metadata.stat().st_size),
        ],
        [
            "demo-1.0.dist-info/uv_cache.json",
            record_hash(uv_cache.read_bytes()),
            str(uv_cache.stat().st_size),
        ],
    ]
    if console_scripts is not None:
        entry_points = dist_info / "entry_points.txt"
        lines = ["[console_scripts]"]
        lines += [f"{name} = {target}" for name, target in console_scripts.items()]
        entry_points.write_text("\n".join(lines) + "\n", encoding="utf-8")
        launcher_path = root / launcher_relative_path
        launcher_path.parent.mkdir(parents=True, exist_ok=True)
        interpreter = str(root / "bin" / "python3.12")
        launcher_bytes = (
            BUILDER.TRAMPOLINE_PREFIX
            + interpreter.encode("utf-8")
            + BUILDER.TRAMPOLINE_SUFFIX
            + b"# -*- coding: utf-8 -*-\nimport sys\nfrom demo import main\nsys.exit(main())\n"
        )
        launcher_path.write_bytes(launcher_bytes)
        launcher_path.chmod(0o755)
        # site-packages sits 3 levels below target_root (lib/python3.12/site-packages),
        # regardless of how many path segments the launcher's own path has.
        rows.append(
            [
                f"../../../{launcher_relative_path}",
                record_hash(launcher_path.read_bytes()),
                str(launcher_path.stat().st_size),
            ]
        )
    rows.append(["demo-1.0.dist-info/RECORD", "", ""])
    write_record(dist_info / "RECORD", rows)
    return root, dist_info, rows


def make_launcher_bytes(interpreter: str, rest: bytes) -> bytes:
    return (
        BUILDER.TRAMPOLINE_PREFIX
        + interpreter.encode("utf-8")
        + BUILDER.TRAMPOLINE_SUFFIX
        + rest
    )


def make_python_shebang_launcher_bytes(interpreter: str, rest: bytes) -> bytes:
    return b"#!" + interpreter.encode("utf-8") + b"\n" + rest


DEFAULT_REST = b"# -*- coding: utf-8 -*-\nimport sys\nfrom demo import main\nsys.exit(main())\n"


# ---------------------------------------------------------------------------
# Baseline / positive tests
# ---------------------------------------------------------------------------


def test_frozen_r2_environment_inputs_are_byte_identical() -> None:
    for name, expected in BUILDER.FROZEN_INPUT_SHA256.items():
        assert hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() == expected


def test_committed_generated_json_is_canonical() -> None:
    names = [
        "supersedes.json",
        "launcher_normalization_policy.json",
        "installation_recipe.json",
        "runtime_fingerprint.schema.json",
        "approved_platform_fingerprint.json",
        "expected_distributions.json",
        "approved_artifacts.json",
        "installation_receipt.json",
        "runtime_fingerprint.json",
        "environment_authority.json",
        "console_script_semantics.json",
        "launcher_raw_diagnostics.json",
    ]
    for name in names:
        raw = (PROJECT_ROOT / name).read_bytes()
        assert not raw.endswith(b"\n")
        assert raw == canonical_bytes(json.loads(raw))


def test_supersession_is_narrow_and_preserves_r2_facts() -> None:
    document = load_json("supersedes.json")
    assert document["r2_merge_commit"] == BUILDER.R2_MERGE_COMMIT
    assert (
        document["r2_environment_authority_sha256"]
        == BUILDER.R2_ENVIRONMENT_AUTHORITY_SHA256
    )
    assert document["affected_distributions"] == [
        "fastapi",
        "idna",
        "numpy",
        "pygments",
        "pytest",
    ]
    assert document["affected_launchers"] == [
        "bin/fastapi",
        "bin/idna",
        "bin/f2py",
        "bin/numpy-config",
        "bin/pygmentize",
        "bin/pytest",
        "bin/py.test",
    ]
    assert document["r3_effective_schema_version"] == "RuntimeFingerprintV3"


def test_preinstall_receipt_binds_all_approved_artifacts_and_targets() -> None:
    receipt = load_json("installation_receipt.json")
    approved = load_json("approved_artifacts.json")["artifacts"]
    assert receipt["generated_before_installation"] is True
    assert receipt["offline"] is True
    assert receipt["no_index"] is True
    assert receipt["hashes_required"] is True
    assert len(receipt["distributions"]) == len(approved) == 23
    assert {row["target_install_identity"] for row in receipt["targets"]} == {
        "install-short",
        "install-long-path-for-normalization-proof",
        "verification-install",
    }


def test_runtime_v3_required_fields_and_sets() -> None:
    runtime = load_json("runtime_fingerprint.json")
    schema = load_json("runtime_fingerprint.schema.json")
    assert runtime["schema_version"] == "RuntimeFingerprintV3"
    for field in schema["required"]:
        assert field in runtime
    assert runtime["distribution_set_match"] is True
    assert len(runtime["actual_distribution_set"]) == 23
    assert len(runtime["console_script_semantic_set"]) == 7
    for distribution in runtime["actual_distribution_set"]:
        assert SHA256_RE.fullmatch(distribution["source_artifact_sha256"])
        assert SHA256_RE.fullmatch(distribution["record_semantic_sha256"])
        assert distribution["record_raw_sha256"]["diagnostic_only"] is True
    for row in runtime["console_script_semantic_set"]:
        assert SHA256_RE.fullmatch(row["normalized_launcher_sha256"])
        assert row["executable_mode"] == "755"
        assert row["launcher_type"] == "uv_console_script"
    diagnostics = load_json("launcher_raw_diagnostics.json")
    assert len(diagnostics) == 7
    for row in diagnostics:
        assert row["raw_launcher_type"]["diagnostic_only"] is True
        assert set(row["raw_launcher_type"]["observations"].values()) == {
            "python_shebang",
            "shell_trampoline",
        }
        assert row["raw_launcher_sha256"]["diagnostic_only"] is True
        assert len(row["raw_launcher_sha256"]["observations"]) == 3


def test_schema_accepts_current_semantic_console_script_rows() -> None:
    runtime = load_json("runtime_fingerprint.json")
    item_schema = load_json("runtime_fingerprint.schema.json")["properties"][
        "console_script_semantic_set"
    ]["items"]
    assert "raw_launcher_type" not in item_schema["required"]
    assert "raw_launcher_sha256" not in item_schema["required"]
    assert "raw_launcher_size" not in item_schema["required"]
    assert item_schema["properties"]["launcher_type"]["const"] == "uv_console_script"
    for row in runtime["console_script_semantic_set"]:
        assert_schema_required_properties(row, item_schema)


def test_schema_rejects_a_missing_semantic_console_script_field() -> None:
    runtime = load_json("runtime_fingerprint.json")
    item_schema = load_json("runtime_fingerprint.schema.json")["properties"][
        "console_script_semantic_set"
    ]["items"]
    incomplete = dict(runtime["console_script_semantic_set"][0])
    incomplete.pop("target_callable")
    with pytest.raises(AssertionError, match="target_callable"):
        assert_schema_required_properties(incomplete, item_schema)


def test_recipe_defines_non_skipping_regeneration_acceptance() -> None:
    recipe = load_json("installation_recipe.json")
    acceptance = recipe[
        "mandatory_regeneration_acceptance"
    ]
    command = acceptance["command_form"]
    assert acceptance["runtime_root_must_be_explicit"] is True
    assert acceptance["skip_allowed"] is False
    assert command[0] == "${RUNTIME_ROOT}/venv/bin/python"
    assert command[-3:] == ["--runtime-root", "${RUNTIME_ROOT}", "--check"]
    assert recipe["approved_console_script_raw_template_types"] == [
        "python_shebang",
        "shell_trampoline",
    ]
    assert recipe["semantic_console_script_launcher_type"] == "uv_console_script"


def test_launcher_policy_v2_defines_cross_template_equivalence() -> None:
    policy = load_json("launcher_normalization_policy.json")
    normalization = policy["normalization"]
    assert policy["schema_version"] == "LauncherNormalizationPolicyV2"
    assert normalization["semantic_launcher_type"] == "uv_console_script"
    assert {
        row["raw_launcher_type"] for row in normalization["recognized_templates"]
    } == {"python_shebang", "shell_trampoline"}
    assert normalization["non_bootstrap_byte_differences_are_acceptance_critical"] is True


def test_three_installs_have_identical_v3_fingerprints() -> None:
    authority = load_json("environment_authority.json")
    assert authority["v3_fingerprint_byte_identity"] is True
    assert len(set(authority["per_install_v3_fingerprint"].values())) == 1
    assert set(authority["per_install_v3_fingerprint"]) == {
        "install-short",
        "install-long-path-for-normalization-proof",
        "verification-install",
    }


def test_raw_launcher_hashes_differ_across_installs() -> None:
    authority = load_json("environment_authority.json")
    diagnostics = authority["raw_vs_normalized_launcher_comparison"]
    assert len(diagnostics) == 7
    for row in diagnostics:
        observations = row["raw_launcher_sha256"]["observations"]
        assert len(set(observations.values())) == len(observations) == 3


def test_no_database_api_or_database_path_is_referenced() -> None:
    tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
    imported_roots = set()
    database_path_literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            if lowered.endswith((".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm")):
                database_path_literals.append(node.value)
    assert "sqlite3" not in imported_roots
    assert database_path_literals == []
    boundaries = load_json("environment_authority.json")["boundaries"]
    assert boundaries["database_opened"] is False
    assert boundaries["database_read"] is False


def test_deterministic_regeneration_check() -> None:
    runtime_root = os.environ.get("P1_R3_RUNTIME_ROOT")
    if not runtime_root:
        pytest.skip(
            "P1_R3_RUNTIME_ROOT not set; live determinism regeneration check "
            "requires the task-created runtime root with three real offline "
            "installs and is skipped when that infrastructure isn't present"
        )
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--project-root",
            str(PROJECT_ROOT),
            "--runtime-root",
            runtime_root,
            "--check",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert '"result": "PASS"' in result.stdout


# ---------------------------------------------------------------------------
# R1 / R2 invariance (negative test 18)
# ---------------------------------------------------------------------------


def test_r1_and_r2_sealed_roots_remain_unchanged() -> None:
    assert (
        hashlib.sha256((R2_ROOT / "environment_authority.json").read_bytes()).hexdigest()
        == BUILDER.R2_ENVIRONMENT_AUTHORITY_SHA256
    )
    assert (
        hashlib.sha256((R2_ROOT / "runtime_fingerprint.json").read_bytes()).hexdigest()
        == BUILDER.R2_RUNTIME_FINGERPRINT_SHA256
    )
    assert (
        hashlib.sha256((R2_ROOT / "MANIFEST.json").read_bytes()).hexdigest()
        == BUILDER.R2_MANIFEST_SHA256
    )
    assert (
        hashlib.sha256((R2_ROOT / "SHA256SUMS").read_bytes()).hexdigest()
        == BUILDER.R2_SHA256SUMS_SHA256
    )
    for name, expected in {
        "environment_authority.json": "8db59e2bba1ac3b448c60c3cb73771aa61a7ca5f1ccf2e1e9562439d5df42ca9",
        "runtime_fingerprint.json": "d11006142d814ddf69313056210780c3ff0e16506cee923b39c07d8740d80388",
    }.items():
        assert hashlib.sha256((R1_ROOT / name).read_bytes()).hexdigest() == expected


# ---------------------------------------------------------------------------
# Negative test 1: changing a non-path launcher byte invalidates
# ---------------------------------------------------------------------------


def test_non_path_launcher_byte_change_invalidates() -> None:
    interpreter = "/Users/kelvin/short/bin/python3.12"
    original = make_launcher_bytes(interpreter, DEFAULT_REST)
    mutated = make_launcher_bytes(interpreter, DEFAULT_REST.replace(b"main", b"mair"))
    _, normalized_original = BUILDER.classify_and_normalize_launcher(original, interpreter)
    _, normalized_mutated = BUILDER.classify_and_normalize_launcher(mutated, interpreter)
    assert normalized_original != normalized_mutated


# ---------------------------------------------------------------------------
# Negative test 2: changing the entry-point target invalidates
# ---------------------------------------------------------------------------


def test_entry_point_target_change_invalidates() -> None:
    base = {
        "relative_posix_path": "bin/demo",
        "executable_mode": "755",
        "distribution_normalized_name": "demo",
        "distribution_version": "1.0",
        "entry_point_group": "console_scripts",
        "entry_point_name": "demo",
        "target_module": "demo",
        "target_callable": "main",
        "launcher_type": "uv_console_script",
        "source_wheel_filename": "demo-1.0-py3-none-any.whl",
        "source_wheel_sha256": "a" * 64,
        "normalized_launcher_sha256": "b" * 64,
    }
    changed = {**base, "target_callable": "other"}
    original = BUILDER.console_script_semantic_set_fingerprint([base])
    assert BUILDER.console_script_semantic_set_fingerprint([changed]) != original


# ---------------------------------------------------------------------------
# Negative test 3: changing executable mode invalidates
# ---------------------------------------------------------------------------


def test_executable_mode_change_invalidates() -> None:
    base = {
        "relative_posix_path": "bin/demo",
        "executable_mode": "755",
        "distribution_normalized_name": "demo",
        "distribution_version": "1.0",
        "entry_point_group": "console_scripts",
        "entry_point_name": "demo",
        "target_module": "demo",
        "target_callable": "main",
        "launcher_type": "uv_console_script",
        "source_wheel_filename": "demo-1.0-py3-none-any.whl",
        "source_wheel_sha256": "a" * 64,
        "normalized_launcher_sha256": "b" * 64,
    }
    changed = {**base, "executable_mode": "644"}
    original = BUILDER.console_script_semantic_set_fingerprint([base])
    assert BUILDER.console_script_semantic_set_fingerprint([changed]) != original


# ---------------------------------------------------------------------------
# Negative test 4: missing declared launcher invalidates
# ---------------------------------------------------------------------------


def test_missing_declared_launcher_invalidates(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path, console_scripts={"demo": "demo:main"})
    # Drop the launcher's RECORD row so it is never discovered.
    filtered = [row for row in rows if not row[0].endswith("bin/demo")]
    write_record(dist_info / "RECORD", filtered)
    with pytest.raises(BUILDER.RecordValidationError, match="missing declared console-script launcher"):
        BUILDER.semantic_record(
            root, dist_info, launcher_relative_paths={"bin/demo": "demo"}
        )


# ---------------------------------------------------------------------------
# Negative test 5: extra undeclared launcher invalidates
# ---------------------------------------------------------------------------


def fixture_full_runtime_install(
    tmp_path: Path, *, extra_bin_filename: str | None = None
) -> tuple[Path, Path, dict]:
    """A full install-target layout usable directly with inventory_installation()."""
    runtime_root = tmp_path / "runtime"
    wheelhouse = runtime_root / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    target_root = runtime_root / "install-x"
    site = target_root / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    bin_dir = target_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python3.12").write_bytes(b"stub-interpreter")

    wheel_bytes = b"fake wheel content for inventory_installation fixture"
    wheel_name = "demo-1.0-py3-none-any.whl"
    (wheelhouse / wheel_name).write_bytes(wheel_bytes)
    wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()

    package = site / "demo" / "__init__.py"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"VALUE = 1\n")
    dist_info = site / "demo-1.0.dist-info"
    dist_info.mkdir()
    metadata = dist_info / "METADATA"
    metadata.write_bytes(b"Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n")
    uv_cache = dist_info / "uv_cache.json"
    uv_cache.write_bytes(
        b'{"timestamp":{"secs_since_epoch":1,"nanos_since_epoch":2}}'
    )
    (dist_info / "entry_points.txt").write_text(
        "[console_scripts]\ndemo = demo:main\n", encoding="utf-8"
    )

    interpreter = str(bin_dir / "python3.12")
    launcher_path = bin_dir / "demo"
    launcher_path.write_bytes(make_launcher_bytes(interpreter, DEFAULT_REST))
    launcher_path.chmod(0o755)

    if extra_bin_filename is not None:
        extra_path = bin_dir / extra_bin_filename
        extra_path.write_bytes(b"#!/bin/sh\necho hi\n")
        extra_path.chmod(0o755)

    rows = [
        ["demo/__init__.py", record_hash(package.read_bytes()), str(package.stat().st_size)],
        [
            "demo-1.0.dist-info/METADATA",
            record_hash(metadata.read_bytes()),
            str(metadata.stat().st_size),
        ],
        [
            "demo-1.0.dist-info/uv_cache.json",
            record_hash(uv_cache.read_bytes()),
            str(uv_cache.stat().st_size),
        ],
        [
            "../../../bin/demo",
            record_hash(launcher_path.read_bytes()),
            str(launcher_path.stat().st_size),
        ],
        ["demo-1.0.dist-info/RECORD", "", ""],
    ]
    write_record(dist_info / "RECORD", rows)

    receipt = {
        "distributions": [
            {
                "normalized_name": "demo",
                "version": "1.0",
                "approved_wheel_filename": wheel_name,
                "approved_wheel_sha256": wheel_sha256,
            }
        ]
    }
    return tmp_path, runtime_root, receipt


def test_extra_undeclared_launcher_invalidates(tmp_path: Path) -> None:
    project_root, runtime_root, receipt = fixture_full_runtime_install(
        tmp_path, extra_bin_filename="mystery-tool"
    )
    with pytest.raises(RuntimeError, match="undeclared extra launcher"):
        BUILDER.inventory_installation(
            project_root, runtime_root, "install-x", "wheelhouse", receipt
        )


def test_no_extra_launcher_is_a_false_positive(tmp_path: Path) -> None:
    """Sibling to the test above: the same layout without an extra file must pass."""
    project_root, runtime_root, receipt = fixture_full_runtime_install(tmp_path)
    result = BUILDER.inventory_installation(
        project_root, runtime_root, "install-x", "wheelhouse", receipt
    )
    assert len(result["console_script_rows"]) == 1
    assert result["console_script_rows"][0]["relative_posix_path"] == "bin/demo"


# ---------------------------------------------------------------------------
# Negative test 6: duplicate launcher mapping invalidates
# ---------------------------------------------------------------------------


def test_duplicate_launcher_mapping_invalidates() -> None:
    claimed: dict[str, str] = {}
    BUILDER.register_launcher_claim(claimed, "bin/demo", "demo-a")
    with pytest.raises(RuntimeError, match="duplicate console-script launcher mapping"):
        BUILDER.register_launcher_claim(claimed, "bin/demo", "demo-b")


# ---------------------------------------------------------------------------
# Negative test 7: unknown launcher template invalidates
# ---------------------------------------------------------------------------


def test_unknown_launcher_template_invalidates() -> None:
    interpreter = "/Users/kelvin/short/bin/python3.12"
    garbage = b"\x7fELF garbage binary launcher, not a recognized template\n"
    with pytest.raises(BUILDER.LauncherValidationError, match="unrecognized launcher template"):
        BUILDER.classify_and_normalize_launcher(garbage, interpreter)


# ---------------------------------------------------------------------------
# Negative test 8: a second unrelated absolute path invalidates
# ---------------------------------------------------------------------------


def test_second_unrelated_absolute_path_invalidates() -> None:
    interpreter = "/Users/kelvin/short/bin/python3.12"
    injected_rest = DEFAULT_REST + b"# leaked build path: /Users/other/leaked/path\n"
    data = make_launcher_bytes(interpreter, injected_rest)
    with pytest.raises(
        BUILDER.LauncherValidationError,
        match="unexpected absolute path outside the approved trampoline position",
    ):
        BUILDER.classify_and_normalize_launcher(data, interpreter)


# ---------------------------------------------------------------------------
# Negative test 9: a path traversal launcher path invalidates
# ---------------------------------------------------------------------------


def test_path_traversal_launcher_path_invalidates(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    rows.insert(-1, ["../../../../etc/passwd", record_hash(b"x"), "1"])
    write_record(dist_info / "RECORD", rows)
    with pytest.raises(BUILDER.RecordValidationError, match="traverses"):
        BUILDER.semantic_record(root, dist_info)


# ---------------------------------------------------------------------------
# Negative test 10: a launcher outside the authorized scripts root invalidates
# ---------------------------------------------------------------------------


def test_launcher_outside_scripts_root_invalidates(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(
        tmp_path,
        console_scripts={"demo": "demo:main"},
        launcher_relative_path="bin/nested/demo",
    )
    # Declared entry point expects bin/demo, but the launcher is nested one
    # level deeper, so it is never recognized as the declared launcher.
    with pytest.raises(BUILDER.RecordValidationError, match="missing declared console-script launcher"):
        BUILDER.semantic_record(
            root, dist_info, launcher_relative_paths={"bin/demo": "demo"}
        )


# ---------------------------------------------------------------------------
# Negative test 11: wrong source-wheel hash invalidates
# ---------------------------------------------------------------------------


def test_wrong_source_wheel_hash_invalidates() -> None:
    base = {
        "relative_posix_path": "bin/demo",
        "executable_mode": "755",
        "distribution_normalized_name": "demo",
        "distribution_version": "1.0",
        "entry_point_group": "console_scripts",
        "entry_point_name": "demo",
        "target_module": "demo",
        "target_callable": "main",
        "launcher_type": "uv_console_script",
        "source_wheel_filename": "demo-1.0-py3-none-any.whl",
        "source_wheel_sha256": "a" * 64,
        "normalized_launcher_sha256": "b" * 64,
    }
    changed = {**base, "source_wheel_sha256": "f" * 64}
    original = BUILDER.console_script_semantic_set_fingerprint([base])
    assert BUILDER.console_script_semantic_set_fingerprint([changed]) != original


# ---------------------------------------------------------------------------
# Negative test 12: wrong distribution identity invalidates
# ---------------------------------------------------------------------------


def test_wrong_distribution_identity_invalidates() -> None:
    base = {
        "relative_posix_path": "bin/demo",
        "executable_mode": "755",
        "distribution_normalized_name": "demo",
        "distribution_version": "1.0",
        "entry_point_group": "console_scripts",
        "entry_point_name": "demo",
        "target_module": "demo",
        "target_callable": "main",
        "launcher_type": "uv_console_script",
        "source_wheel_filename": "demo-1.0-py3-none-any.whl",
        "source_wheel_sha256": "a" * 64,
        "normalized_launcher_sha256": "b" * 64,
    }
    changed = {**base, "distribution_version": "2.0"}
    original = BUILDER.console_script_semantic_set_fingerprint([base])
    assert BUILDER.console_script_semantic_set_fingerprint([changed]) != original


# ---------------------------------------------------------------------------
# Negative test 13: mutating only the approved interpreter path leaves
# normalized identity unchanged
# ---------------------------------------------------------------------------


def test_interpreter_path_only_mutation_leaves_normalized_identity_unchanged() -> None:
    short = make_launcher_bytes("/Users/kelvin/short/bin/python3.12", DEFAULT_REST)
    long = make_launcher_bytes(
        "/Users/kelvin/a/much/longer/installation/root/path/bin/python3.12",
        DEFAULT_REST,
    )
    _, normalized_short = BUILDER.classify_and_normalize_launcher(
        short, "/Users/kelvin/short/bin/python3.12"
    )
    _, normalized_long = BUILDER.classify_and_normalize_launcher(
        long, "/Users/kelvin/a/much/longer/installation/root/path/bin/python3.12"
    )
    assert normalized_short == normalized_long
    assert hashlib.sha256(short).hexdigest() != hashlib.sha256(long).hexdigest()


def test_approved_raw_templates_share_one_semantic_launcher_identity() -> None:
    interpreter = "/Users/kelvin/runtime/bin/python3.12"
    shebang = make_python_shebang_launcher_bytes(interpreter, DEFAULT_REST)
    trampoline = make_launcher_bytes(interpreter, DEFAULT_REST)
    shebang_type, normalized_shebang = BUILDER.classify_and_normalize_launcher(
        shebang, interpreter
    )
    trampoline_type, normalized_trampoline = BUILDER.classify_and_normalize_launcher(
        trampoline, interpreter
    )
    assert {shebang_type, trampoline_type} == {
        "python_shebang",
        "shell_trampoline",
    }
    assert normalized_shebang == normalized_trampoline
    assert normalized_shebang.startswith(
        BUILDER.CANONICAL_UV_CONSOLE_SCRIPT_PREFIX
    )


def test_cross_template_non_bootstrap_payload_change_invalidates() -> None:
    interpreter = "/Users/kelvin/runtime/bin/python3.12"
    shebang = make_python_shebang_launcher_bytes(interpreter, DEFAULT_REST)
    trampoline = make_launcher_bytes(
        interpreter, DEFAULT_REST.replace(b"main", b"other")
    )
    _, normalized_shebang = BUILDER.classify_and_normalize_launcher(
        shebang, interpreter
    )
    _, normalized_trampoline = BUILDER.classify_and_normalize_launcher(
        trampoline, interpreter
    )
    assert normalized_shebang != normalized_trampoline


# ---------------------------------------------------------------------------
# Negative test 14: two different absolute install roots produce identical
# canonical receipts and V3 fingerprints through production builder functions
# ---------------------------------------------------------------------------


def create_production_builder_fixture(
    project_root: Path,
    runtime_root: Path,
    *,
    wheel_name: str,
    wheel_bytes: bytes,
) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
    (project_root / "approved_artifacts.json").write_bytes(
        canonical_bytes(
            {
                "artifacts": [
                    {
                        "filename": wheel_name,
                        "normalized_name": "demo",
                        "platform_tags": ["py3-none-any"],
                        "sha256": wheel_sha256,
                        "version": "1.0",
                    }
                ]
            }
        )
    )
    (project_root / "expected_distributions.json").write_bytes(
        canonical_bytes(
            {
                "distributions": [{"normalized_name": "demo", "version": "1.0"}]
            }
        )
    )
    (project_root / "approved_platform_fingerprint.json").write_bytes(
        (PROJECT_ROOT / "approved_platform_fingerprint.json").read_bytes()
    )
    (project_root / "uv.lock").write_bytes((PROJECT_ROOT / "uv.lock").read_bytes())

    wheelhouse = runtime_root / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    (wheelhouse / wheel_name).write_bytes(wheel_bytes)
    for target_identity, _wheelhouse_identity in BUILDER.TARGETS:
        target_root = runtime_root / target_identity
        site = target_root / "lib" / "python3.12" / "site-packages"
        site.mkdir(parents=True)
        bin_dir = target_root / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python3.12").write_bytes(b"stub-interpreter")

        package = site / "demo" / "__init__.py"
        package.parent.mkdir()
        package.write_bytes(b"VALUE = 1\n")
        dist_info = site / "demo-1.0.dist-info"
        dist_info.mkdir()
        metadata = dist_info / "METADATA"
        metadata.write_bytes(b"Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n")
        uv_cache = dist_info / "uv_cache.json"
        uv_cache.write_bytes(
            b'{"timestamp":{"secs_since_epoch":1,"nanos_since_epoch":2}}'
        )
        (dist_info / "entry_points.txt").write_text(
            "[console_scripts]\ndemo = demo:main\n", encoding="utf-8"
        )
        launcher = bin_dir / "demo"
        interpreter = str(bin_dir / "python3.12")
        if target_identity == "install-short":
            launcher_bytes = make_python_shebang_launcher_bytes(
                interpreter, DEFAULT_REST
            )
        else:
            launcher_bytes = make_launcher_bytes(interpreter, DEFAULT_REST)
        launcher.write_bytes(launcher_bytes)
        launcher.chmod(0o755)
        write_record(
            dist_info / "RECORD",
            [
                [
                    "demo/__init__.py",
                    record_hash(package.read_bytes()),
                    str(package.stat().st_size),
                ],
                [
                    "demo-1.0.dist-info/METADATA",
                    record_hash(metadata.read_bytes()),
                    str(metadata.stat().st_size),
                ],
                [
                    "demo-1.0.dist-info/uv_cache.json",
                    record_hash(uv_cache.read_bytes()),
                    str(uv_cache.stat().st_size),
                ],
                [
                    "../../../bin/demo",
                    record_hash(launcher.read_bytes()),
                    str(launcher.stat().st_size),
                ],
                ["demo-1.0.dist-info/RECORD", "", ""],
            ],
        )


def test_two_absolute_install_roots_produce_identical_v3_fingerprint(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    short_runtime = tmp_path / "r"
    long_runtime = (
        tmp_path
        / "materially"
        / "different"
        / "absolute"
        / "parent"
        / "installation"
        / "root"
    )
    wheel_name = "demo-1.0-py3-none-any.whl"
    wheel_bytes = b"production-builder cross-root fixture wheel"
    create_production_builder_fixture(
        project_root,
        short_runtime,
        wheel_name=wheel_name,
        wheel_bytes=wheel_bytes,
    )
    create_production_builder_fixture(
        project_root,
        long_runtime,
        wheel_name=wheel_name,
        wheel_bytes=wheel_bytes,
    )

    short_receipt = BUILDER.installation_receipt_document(
        project_root, short_runtime, require_empty_targets=False
    )
    long_receipt = BUILDER.installation_receipt_document(
        project_root, long_runtime, require_empty_targets=False
    )
    assert canonical_bytes(short_receipt) == canonical_bytes(long_receipt)

    observations = [
        BUILDER.inventory_installation(
            project_root, short_runtime, "install-short", "wheelhouse", short_receipt
        ),
        BUILDER.inventory_installation(
            project_root,
            long_runtime,
            "install-long-path-for-normalization-proof",
            "wheelhouse",
            long_receipt,
        ),
        BUILDER.inventory_installation(
            project_root,
            short_runtime,
            "verification-install",
            "wheelhouse",
            short_receipt,
        ),
    ]
    launcher_rows = [observation["console_script_rows"][0] for observation in observations]
    assert len({row["raw_launcher_sha256"] for row in launcher_rows}) == 3
    assert {row["raw_launcher_type"] for row in launcher_rows} == {
        "python_shebang",
        "shell_trampoline",
    }
    assert {row["launcher_type"] for row in launcher_rows} == {"uv_console_script"}
    assert len(
        {
            canonical_bytes(BUILDER.console_script_acceptance_row(row))
            for row in launcher_rows
        }
    ) == 1

    receipt_sha256 = hashlib.sha256(canonical_bytes(short_receipt)).hexdigest()
    launcher_policy_sha256 = hashlib.sha256(
        canonical_bytes(BUILDER.launcher_normalization_policy_document())
    ).hexdigest()
    runtime, _diagnostics = BUILDER.aggregate_runtime_document(
        project_root, observations, receipt_sha256, launcher_policy_sha256
    )
    assert runtime["installation_receipt_sha256"] == receipt_sha256
    assert len(set(runtime["per_install_environment_fingerprint_sha256"].values())) == 1


# ---------------------------------------------------------------------------
# Negative test 15: non-launcher package-file mutation still invalidates
# ---------------------------------------------------------------------------


def test_non_launcher_package_file_mutation_invalidates(tmp_path: Path) -> None:
    root, dist_info, _rows = fixture_install(tmp_path)
    (dist_info.parent / "demo" / "__init__.py").write_bytes(b"VALUE = 2\n")
    with pytest.raises(BUILDER.RecordValidationError, match="hash mismatch"):
        BUILDER.semantic_record(root, dist_info)


# ---------------------------------------------------------------------------
# Negative test 16: METADATA mutation still invalidates
# ---------------------------------------------------------------------------


def test_metadata_mutation_invalidates_distribution_fingerprint() -> None:
    distribution = {
        "normalized_name": "demo",
        "version": "1.0",
        "metadata_name": "demo",
        "source_artifact_sha256": "a" * 64,
        "distribution_metadata_sha256": "b" * 64,
        "record_semantic_sha256": "c" * 64,
        "installer_metadata_policy_version": "InstallerMetadataPolicyV1",
        "installer_metadata_paths": ["lib/python3.12/site-packages/demo-1.0.dist-info/uv_cache.json"],
    }
    original = BUILDER.distribution_acceptance_fingerprint(distribution)
    distribution["distribution_metadata_sha256"] = "d" * 64
    assert BUILDER.distribution_acceptance_fingerprint(distribution) != original


# ---------------------------------------------------------------------------
# Negative test 17: extra/missing distribution still invalidates
# ---------------------------------------------------------------------------


def test_extra_or_missing_distribution_invalidates() -> None:
    expected = [("a", "1"), ("b", "2")]
    valid = [
        {"normalized_name": "a", "version": "1"},
        {"normalized_name": "b", "version": "2"},
    ]
    BUILDER.validate_distribution_sets(expected, valid)
    with pytest.raises(RuntimeError, match="distribution set mismatch"):
        BUILDER.validate_distribution_sets(expected, valid[:-1])
    with pytest.raises(RuntimeError, match="distribution set mismatch"):
        BUILDER.validate_distribution_sets(
            expected, [*valid, {"normalized_name": "c", "version": "3"}]
        )


# test 18 (R1/R2 invariance) is test_r1_and_r2_sealed_roots_remain_unchanged above.
# test 19 (no DB access) is test_no_database_api_or_database_path_is_referenced above.


# ---------------------------------------------------------------------------
# Additional structural tests carried over from R2's exclusion contract
# ---------------------------------------------------------------------------


def test_launcher_rows_are_excluded_from_non_launcher_semantic_record(tmp_path: Path) -> None:
    root, dist_info, _rows = fixture_install(tmp_path, console_scripts={"demo": "demo:main"})
    without_launcher = BUILDER.semantic_record(root, dist_info)
    with_launcher = BUILDER.semantic_record(
        root, dist_info, launcher_relative_paths={"bin/demo": "demo"}
    )
    assert without_launcher["record_semantic_sha256"] != with_launcher["record_semantic_sha256"]
    assert len(with_launcher["launcher_rows"]) == 1
    assert with_launcher["launcher_rows"][0]["path"] == "bin/demo"


def test_semantic_serialization_has_contract_order_and_no_newline() -> None:
    sample = BUILDER.semantic_canonical_bytes(
        [{"path": "a", "hash": "sha256=x", "size": 1}]
    )
    assert sample == b'[{"path":"a","hash":"sha256=x","size":1}]'
    assert not sample.endswith(b"\n")
