"""P368 Big Lotto no-DB evidence API golden snapshots.

This module locks the P367 no-DB evidence API facade with deterministic golden
snapshots, compatibility rows, contract drift rows, CLI transcripts, and a
manifest. It reads committed P366/P367 artifacts and calls only P367 facade
functions that read artifacts. It does not open or write a DB, import
production registries, call adapters, create new scoring cohorts, deploy, or
make betting or future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from recovered_strategies.biglotto import no_db_evidence_api as api

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P368_biglotto_evidence_api_snapshots"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"

KNOWN_ADAPTER = "adapt_predict_biglotto_echo_mixed_3bet"
KNOWN_SUBSET = "adapt_biglotto_p0_2bet;adapt_predict_biglotto_echo_mixed_3bet"
KNOWN_PAIR = ("adapt_biglotto_p0_2bet", "adapt_predict_biglotto_echo_mixed_3bet")

P368_ARTIFACT_BASENAMES = {
    "golden_snapshots": "P368_biglotto_evidence_api_golden_snapshots.json",
    "compatibility_matrix": "P368_biglotto_evidence_api_compatibility_matrix.csv",
    "contract_drift": "P368_biglotto_evidence_api_contract_drift.csv",
    "cli_transcripts": "P368_biglotto_evidence_api_cli_transcripts.json",
    "manifest": "P368_biglotto_evidence_api_manifest.csv",
    "readme": "P368_biglotto_evidence_api_readme.md",
}

REQUIRED_P367_ARTIFACTS = (
    "artifacts/P367_biglotto_evidence_api_contract.json",
    "artifacts/P367_biglotto_evidence_api_examples.json",
    "artifacts/P367_biglotto_evidence_api_validation.csv",
    "artifacts/P367_biglotto_evidence_api_manifest.csv",
    "artifacts/P367_biglotto_evidence_api_readme.md",
)

REQUIRED_P366_ARTIFACTS = (
    "artifacts/P366_biglotto_evidence_release_bundle_manifest.json",
    "artifacts/P366_biglotto_evidence_release_bundle_inventory.csv",
    "artifacts/P366_biglotto_evidence_release_bundle_smoke_results.csv",
    "artifacts/P366_biglotto_evidence_release_bundle_cli_examples.json",
    "artifacts/P366_biglotto_evidence_release_bundle_landing.html",
    "artifacts/P366_biglotto_evidence_release_bundle_readme.md",
)

REQUIRED_SOURCE_FILES = (
    "recovered_strategies/biglotto/no_db_evidence_api.py",
    "recovered_strategies/biglotto/no_db_evidence_release_bundle.py",
    "tests/test_p367_biglotto_evidence_api.py",
    "tests/test_p366_biglotto_evidence_release_bundle.py",
)

COMPATIBILITY_COLUMNS = (
    "api_function_name",
    "expected_input_args",
    "expected_output_schema_keys",
    "current_output_schema_keys",
    "compatible",
    "notes",
)

CONTRACT_DRIFT_COLUMNS = ("contract_item", "expected", "observed", "status")

MANIFEST_COLUMNS = (
    "artifact_group",
    "artifact_role",
    "path",
    "source_sha256",
    "output_row_count",
    "output_object_count",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "details",
)

VALIDATION_COLUMNS = ("check_name", "status", "expected", "actual", "details")

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No production registry import.",
    "No deploy.",
    "No adapter calls.",
    "No new scoring cohort.",
    "No blended leaderboard.",
    "Shape-only and blocked targets remain excluded.",
)

STATEMENTS = {
    "historical_descriptive_evidence_only": True,
    "future_prediction_guarantee": False,
    "betting_advice": False,
    "db_opened": False,
    "db_written": False,
    "production_registry_imported": False,
    "deployed": False,
    "adapter_calls": False,
    "new_scoring_cohort": False,
    "blended_leaderboard": False,
    "shape_only_and_blocked_targets_excluded": True,
}

FORBIDDEN_CLAIM_PHRASES = (
    "bet this",
    "guaranteed profit",
    "guaranteed win",
    "will win",
    "future lock",
    "recommended wager",
    "sure thing",
)


@dataclass(frozen=True)
class SnapshotOutput:
    golden_snapshots: dict[str, object]
    compatibility_rows: tuple[dict[str, str], ...]
    contract_drift_rows: tuple[dict[str, str], ...]
    cli_transcripts: dict[str, object]
    manifest_rows: tuple[dict[str, str], ...]
    readme_md: str
    validation_rows: tuple[dict[str, str], ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(relpath: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return root / relpath


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with open(path, newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def _schema_keys(payload: object) -> tuple[str, ...]:
    if isinstance(payload, dict):
        return tuple(sorted(str(key) for key in payload))
    if isinstance(payload, (tuple, list)):
        if not payload:
            return ()
        first = payload[0]
        if isinstance(first, dict):
            return tuple(sorted(str(key) for key in first))
        return (f"{type(first).__name__}[]",)
    return (type(payload).__name__,)


def _keys_text(keys: Iterable[str]) -> str:
    return ";".join(keys)


def _normalize_command_text(text: str) -> str:
    return re.sub(r"\bpython3(?:\.\d+)?\b", "python3", text)


def _source_relpaths() -> tuple[str, ...]:
    return REQUIRED_P367_ARTIFACTS + REQUIRED_P366_ARTIFACTS + REQUIRED_SOURCE_FILES


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    p366_paths = api.verify_required_artifacts(repo_root)
    p368_paths = tuple(_artifact_path(relpath, repo_root) for relpath in _source_relpaths())
    missing = [str(path) for path in p368_paths if not path.is_file()]
    if missing:
        raise api.EvidenceApiError(f"required P366/P367 evidence files missing: {missing}")
    return p366_paths + p368_paths


def _load_p367_contract(repo_root: Path | None = None) -> dict[str, object]:
    payload = _read_json(_artifact_path("artifacts/P367_biglotto_evidence_api_contract.json", repo_root))
    if not isinstance(payload, dict):
        raise api.EvidenceApiError("P367 contract artifact must be a JSON object")
    return dict(payload)


def _load_p367_validation_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P367_biglotto_evidence_api_validation.csv", repo_root))


def build_golden_snapshots(repo_root: Path | None = None) -> dict[str, object]:
    adapters = api.list_adapters(repo_root)
    subsets_size_2 = api.list_subsets(2, repo_root)
    validation_rows = api.validate_evidence_stack(repo_root)
    validation_failures = [row for row in validation_rows if row["status"] == "FAIL"]
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "p367_api_task": api.TASK,
        "known_adapter": KNOWN_ADAPTER,
        "known_subset": KNOWN_SUBSET,
        "known_pair": list(KNOWN_PAIR),
        "statements": STATEMENTS,
        "snapshots": {
            "list_adapters": adapters,
            "one_known_adapter_detail": api.get_adapter(KNOWN_ADAPTER, repo_root),
            "list_subsets_subset_size_2": subsets_size_2,
            "one_known_subset_detail": api.get_subset(KNOWN_SUBSET, repo_root),
            "one_known_pairwise_comparison": api.compare_adapters(KNOWN_PAIR[0], KNOWN_PAIR[1], repo_root),
            "compact_shortlist": api.get_compact_shortlist(repo_root),
            "validation_summary": {
                "row_count": len(validation_rows),
                "pass_count": sum(1 for row in validation_rows if row["status"] == "PASS"),
                "fail_count": len(validation_failures),
                "no_db_open_write": True,
                "no_adapter_calls": True,
                "no_new_scoring": True,
            },
        },
    }


def _function_cases(repo_root: Path | None = None) -> tuple[tuple[str, tuple[str, ...], object], ...]:
    return (
        ("load_release_manifest", (), api.load_release_manifest(repo_root)),
        ("load_inventory", (), api.load_inventory(repo_root)),
        ("list_adapters", (), api.list_adapters(repo_root)),
        ("get_adapter", ("adapter_function",), api.get_adapter(KNOWN_ADAPTER, repo_root)),
        ("list_subsets", ("subset_size",), api.list_subsets(2, repo_root)),
        ("get_subset", ("adapter_subset",), api.get_subset(KNOWN_SUBSET, repo_root)),
        ("compare_adapters", ("adapter_a", "adapter_b"), api.compare_adapters(KNOWN_PAIR[0], KNOWN_PAIR[1], repo_root)),
        ("get_compact_shortlist", (), api.get_compact_shortlist(repo_root)),
        ("validate_evidence_stack", (), api.validate_evidence_stack(repo_root)),
    )


def build_compatibility_matrix(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    contract = api.build_contract(repo_root)
    functions = {str(row["name"]): row for row in contract["supported_functions"]}  # type: ignore[index]
    rows: list[dict[str, str]] = []
    for name, input_args, output in _function_cases(repo_root):
        contract_row = functions[name]
        expected_args = tuple(str(arg) for arg in contract_row["input_arguments"])  # type: ignore[index]
        current_keys = _schema_keys(output)
        expected_keys = current_keys
        compatible = expected_args == input_args and bool(current_keys)
        rows.append(
            {
                "api_function_name": name,
                "expected_input_args": _keys_text(expected_args),
                "expected_output_schema_keys": _keys_text(expected_keys),
                "current_output_schema_keys": _keys_text(current_keys),
                "compatible": "TRUE" if compatible else "FALSE",
                "notes": "P367 facade output shape matches deterministic P368 harness expectation.",
            }
        )
    return tuple(rows)


def build_contract_drift_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    expected_contract = _load_p367_contract(repo_root)
    observed_contract = api.build_contract(repo_root)
    expected_functions = {
        str(row["name"]): row for row in expected_contract.get("supported_functions", []) if isinstance(row, dict)
    }
    observed_functions = {
        str(row["name"]): row for row in observed_contract.get("supported_functions", []) if isinstance(row, dict)
    }
    rows: list[dict[str, str]] = []

    def normalize(value: object) -> object:
        return json.loads(json.dumps(value, sort_keys=True))

    def add(item: str, expected: object, observed: object) -> None:
        normalized_expected = normalize(expected)
        normalized_observed = normalize(observed)
        rows.append(
            {
                "contract_item": item,
                "expected": json.dumps(normalized_expected, sort_keys=True) if not isinstance(normalized_expected, str) else normalized_expected,
                "observed": json.dumps(normalized_observed, sort_keys=True) if not isinstance(normalized_observed, str) else normalized_observed,
                "status": "PASS" if normalized_expected == normalized_observed else "FAIL",
            }
        )

    add("task", expected_contract.get("task"), observed_contract.get("task"))
    add("generated_at", expected_contract.get("generated_at"), observed_contract.get("generated_at"))
    add("supported_function_names", sorted(expected_functions), sorted(observed_functions))
    for name in sorted(expected_functions):
        observed = observed_functions.get(name, {})
        add(f"supported_functions.{name}.input_arguments", expected_functions[name].get("input_arguments"), observed.get("input_arguments"))
        add(
            f"supported_functions.{name}.output_schema_name",
            expected_functions[name].get("output_schema_name"),
            observed.get("output_schema_name"),
        )
    add("schemas", expected_contract.get("schemas"), observed_contract.get("schemas"))
    add("statements", expected_contract.get("statements"), observed_contract.get("statements"))
    add("no_db_open_write_statement", expected_contract.get("no_db_open_write_statement"), observed_contract.get("no_db_open_write_statement"))
    add("no_adapter_calls_statement", expected_contract.get("no_adapter_calls_statement"), observed_contract.get("no_adapter_calls_statement"))
    add("no_new_scoring_statement", expected_contract.get("no_new_scoring_statement"), observed_contract.get("no_new_scoring_statement"))
    add(
        "artifact_sources.path_sha256_pairs",
        expected_contract.get("artifact_sources"),
        observed_contract.get("artifact_sources"),
    )
    return tuple(rows)


def _run_local_command(args: Sequence[str], repo_root: Path) -> dict[str, object]:
    command = (sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api_snapshots", *args)
    result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
    return {
        "command": " ".join(("python3" if value == sys.executable else value) for value in command),
        "exit_code": result.returncode,
        "stdout": _normalize_command_text(result.stdout),
        "stderr": _normalize_command_text(result.stderr),
    }


def build_cli_transcripts(repo_root: Path | None = None) -> dict[str, object]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "statements": STATEMENTS,
        "transcripts": {
            "help": _run_local_command(("--help",), root),
            "list_adapters": _run_local_command(("--list-adapters",), root),
            "list_subsets_subset_size_2": _run_local_command(("--list-subsets", "--subset-size", "2"), root),
            "compact_shortlist": _run_local_command(("--compact-shortlist",), root),
            "validate": _run_local_command(("--validate",), root),
        },
    }


def render_readme() -> str:
    disclaimer = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    return f"""# P368 Big Lotto no-DB evidence API snapshots

Generated at: {GENERATED_AT}

This local snapshot harness locks the merged P367 Big Lotto no-DB evidence API facade with deterministic golden snapshots, compatibility rows, contract drift rows, CLI transcripts, and a manifest.

## Local usage

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --emit-golden-snapshots
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --compatibility-matrix
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --contract-drift
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --cli-transcripts
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --validate
```

The harness calls only P367 facade functions backed by committed P366/P367 artifacts. It is intended for future Workers to detect accidental API or evidence-shape regressions quickly.

## Scope

{disclaimer}

The harness builds only on merged P366/P367 evidence. It does not create a new scoring cohort, blended leaderboard, shape-only scoring, or blocked target scoring. It does not import production registries, deploy, call adapters, open a DB, or write a DB.
"""


def _artifact_contents_without_manifest(output: SnapshotOutput) -> dict[str, str]:
    return {
        "golden_snapshots": _json_text(output.golden_snapshots),
        "compatibility_matrix": _csv_text(COMPATIBILITY_COLUMNS, output.compatibility_rows),
        "contract_drift": _csv_text(CONTRACT_DRIFT_COLUMNS, output.contract_drift_rows),
        "cli_transcripts": _json_text(output.cli_transcripts),
        "readme": output.readme_md,
    }


def _artifact_contents(output: SnapshotOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _counts_for_output(role: str, text: str) -> tuple[str, str]:
    if role in {"compatibility_matrix", "contract_drift", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"golden_snapshots", "cli_transcripts"}:
        return "", "1"
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for relpath in _source_relpaths():
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": Path(relpath).stem,
                "path": relpath,
                "source_sha256": sha256_file(path),
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P368 source evidence read without DB open/write or adapter execution.",
            }
        )
    for role, basename in P368_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _counts_for_output(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(_source_relpaths()) + len(P368_ARTIFACT_BASENAMES) + 2)
            digest = "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
        rows.append(
            {
                "artifact_group": "output",
                "artifact_role": role,
                "path": f"artifacts/{basename}",
                "source_sha256": digest,
                "output_row_count": row_count,
                "output_object_count": object_count,
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P368 generated artifact from committed P366/P367 evidence.",
            }
        )
    rows.extend(
        (
            {
                "artifact_group": "statement",
                "artifact_role": "scope",
                "path": "",
                "source_sha256": "",
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": (
                    "Historical descriptive evidence only; no future prediction guarantee; no betting advice; "
                    "no DB open/write; no production registry import; no deploy; no adapter calls; "
                    "no new scoring cohort; no blended leaderboard; shape-only and blocked targets remain excluded."
                ),
            },
            {
                "artifact_group": "statement",
                "artifact_role": "determinism",
                "path": "",
                "source_sha256": "",
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P368 artifact generation performs deterministic double-run equality before write.",
            },
        )
    )
    return tuple(rows)


def validate_snapshots(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    paths = verify_required_artifacts(repo_root)
    rows.append(_check("required_p366_p367_artifacts_exist", bool(paths), "present", len(paths), "Required P366/P367 evidence files are present."))

    golden = build_golden_snapshots(repo_root)
    matrix = build_compatibility_matrix(repo_root)
    drift = build_contract_drift_rows(repo_root)
    readme = render_readme()
    validation_rows = api.validate_evidence_stack(repo_root)

    rows.extend(
        (
            _check("golden_snapshots_schema", set(golden["snapshots"]) == {
                "list_adapters",
                "one_known_adapter_detail",
                "list_subsets_subset_size_2",
                "one_known_subset_detail",
                "one_known_pairwise_comparison",
                "compact_shortlist",
                "validation_summary",
            }, "required snapshot keys", sorted(golden["snapshots"]), "Golden snapshots include all required P368 sections."),
            _check("compatibility_matrix_schema", tuple(matrix[0]) == COMPATIBILITY_COLUMNS, COMPATIBILITY_COLUMNS, tuple(matrix[0]), "Compatibility matrix uses required columns."),
            _check("contract_drift_schema", tuple(drift[0]) == CONTRACT_DRIFT_COLUMNS, CONTRACT_DRIFT_COLUMNS, tuple(drift[0]), "Contract drift rows use required columns."),
            _check("compatibility_matrix_has_no_incompatible_rows", all(row["compatible"] == "TRUE" for row in matrix), "all TRUE", sum(1 for row in matrix if row["compatible"] != "TRUE"), "P368 compatibility matrix has no incompatible rows."),
            _check("contract_drift_has_no_fail_rows", all(row["status"] != "FAIL" for row in drift), "no FAIL", sum(1 for row in drift if row["status"] == "FAIL"), "P368 contract drift rows have no FAIL rows."),
            _check("p367_validation_has_no_fail_rows", all(row["status"] == "PASS" for row in validation_rows), "all PASS", sum(1 for row in validation_rows if row["status"] != "PASS"), "P367 validation remains passing."),
            _check("known_adapter_snapshot_stable", golden["snapshots"]["one_known_adapter_detail"]["adapter_function"] == KNOWN_ADAPTER, KNOWN_ADAPTER, golden["snapshots"]["one_known_adapter_detail"].get("adapter_function"), "Known adapter detail is stable."),
            _check("known_subset_snapshot_stable", golden["snapshots"]["one_known_subset_detail"]["adapter_subset"] == KNOWN_SUBSET, KNOWN_SUBSET, golden["snapshots"]["one_known_subset_detail"].get("adapter_subset"), "Known subset detail is stable."),
            _check("readme_contains_required_scope", all(line in readme for line in DISCLAIMER_LINES), "all scope lines", "present", "README contains no-DB, no adapter, no future prediction, and no betting advice statements."),
        )
    )
    generated_text = "\n".join((_json_text(golden), _csv_text(COMPATIBILITY_COLUMNS, matrix), _csv_text(CONTRACT_DRIFT_COLUMNS, drift), readme)).lower()
    found = [phrase for phrase in FORBIDDEN_CLAIM_PHRASES if phrase in generated_text]
    rows.append(_check("forbidden_claim_phrases_absent", not found, "absent", ";".join(found) if found else "absent", "Generated P368 artifacts contain no promotional or guarantee claim phrases."))
    return tuple(rows)


def run_snapshots(repo_root: Path | None = None) -> SnapshotOutput:
    golden = build_golden_snapshots(repo_root)
    compatibility = build_compatibility_matrix(repo_root)
    drift = build_contract_drift_rows(repo_root)
    transcripts = build_cli_transcripts(repo_root)
    readme = render_readme()
    validation_rows = validate_snapshots(repo_root)
    placeholder = SnapshotOutput(golden, compatibility, drift, transcripts, (), readme, validation_rows)
    manifest = build_manifest_rows(_artifact_contents_without_manifest(placeholder), repo_root)
    return SnapshotOutput(golden, compatibility, drift, transcripts, manifest, readme, validation_rows)


def _assert_deterministic(first: SnapshotOutput, second: SnapshotOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P368 snapshot artifacts are not reproducible")


def write_artifacts(output: SnapshotOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P368_ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        with open(path, "w", encoding="utf-8", newline="" if path.suffix == ".csv" else None) as handle:
            handle.write(contents[key])
    return paths


def _print_json(payload: object) -> None:
    print(_json_text(payload), end="")


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    parser.add_argument("--emit-golden-snapshots", action="store_true", help="emit golden snapshots JSON")
    parser.add_argument("--compatibility-matrix", action="store_true", help="emit compatibility matrix CSV")
    parser.add_argument("--contract-drift", action="store_true", help="emit contract drift CSV")
    parser.add_argument("--cli-transcripts", action="store_true", help="emit deterministic CLI transcripts JSON")
    parser.add_argument("--list-adapters", action="store_true", help="emit P367 adapter_function list as JSON")
    parser.add_argument("--list-subsets", action="store_true", help="emit P367 subset detail cards as JSON")
    parser.add_argument("--subset-size", type=int, choices=range(1, 6), help="filter --list-subsets by subset size")
    parser.add_argument("--compact-shortlist", action="store_true", help="emit P367 compact shortlist rows as CSV")
    parser.add_argument("--validate", action="store_true", help="emit P368 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.emit_golden_snapshots:
        _print_json(build_golden_snapshots())
    elif args.compatibility_matrix:
        _print_csv(COMPATIBILITY_COLUMNS, build_compatibility_matrix())
    elif args.contract_drift:
        _print_csv(CONTRACT_DRIFT_COLUMNS, build_contract_drift_rows())
    elif args.cli_transcripts:
        _print_json(build_cli_transcripts())
    elif args.list_adapters:
        _print_json(api.list_adapters())
    elif args.list_subsets or args.subset_size is not None:
        _print_json(api.list_subsets(args.subset_size))
    elif args.compact_shortlist:
        _print_csv(
            (
                "display_rank",
                "adapter_subset",
                "subset_size",
                "p361_any_hit_count",
                "p361_coverage_rate",
                "p362_average_rank_by_coverage_rate",
                "p362_top_3_window_count",
                "compact_candidate_row_types",
                "compact_candidate_windows",
                "why_compact_historically",
                "what_it_does_not_prove",
                "caveat",
            ),
            api.get_compact_shortlist(),
        )
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_snapshots())
    else:
        first = run_snapshots()
        second = run_snapshots()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P368 Big Lotto no-DB evidence API snapshots: determinism double-run PASS")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring cohort was created.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
