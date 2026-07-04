"""P369 Big Lotto no-DB evidence agent handoff pack.

This module builds deterministic handoff artifacts for future Planner and
Worker agents on top of the merged P367/P368 Big Lotto evidence API. It reads
committed artifacts and calls only the P367/P368 no-DB API helpers that read
artifacts. It does not open or write a DB, import production registries, call
adapters, create new scoring cohorts, deploy, or make betting or
future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import textwrap
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from recovered_strategies.biglotto import no_db_evidence_api as api
from recovered_strategies.biglotto import no_db_evidence_api_snapshots as snapshots

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P369_biglotto_evidence_agent_pack"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_MERGE_BASELINE = "30942e1719f548f8fff2d2fb99c7351cc6f3c443"

REQUIRED_SOURCE_FILES = (
    "recovered_strategies/biglotto/no_db_evidence_api.py",
    "recovered_strategies/biglotto/no_db_evidence_api_snapshots.py",
    "recovered_strategies/biglotto/no_db_evidence_release_bundle.py",
    "artifacts/P367_biglotto_evidence_api_contract.json",
    "artifacts/P367_biglotto_evidence_api_examples.json",
    "artifacts/P367_biglotto_evidence_api_validation.csv",
    "artifacts/P367_biglotto_evidence_api_manifest.csv",
    "artifacts/P367_biglotto_evidence_api_readme.md",
    "artifacts/P368_biglotto_evidence_api_golden_snapshots.json",
    "artifacts/P368_biglotto_evidence_api_compatibility_matrix.csv",
    "artifacts/P368_biglotto_evidence_api_contract_drift.csv",
    "artifacts/P368_biglotto_evidence_api_cli_transcripts.json",
    "artifacts/P368_biglotto_evidence_api_manifest.csv",
    "artifacts/P368_biglotto_evidence_api_readme.md",
    "tests/test_p368_biglotto_evidence_api_snapshots.py",
    "tests/test_p367_biglotto_evidence_api.py",
)

P369_ARTIFACT_BASENAMES = {
    "summary": "P369_biglotto_evidence_agent_pack_summary.json",
    "task_prompts": "P369_biglotto_evidence_agent_pack_task_prompts.json",
    "query_recipes": "P369_biglotto_evidence_agent_pack_query_recipes.json",
    "validation_checklist": "P369_biglotto_evidence_agent_pack_validation_checklist.csv",
    "examples": "P369_biglotto_evidence_agent_pack_examples.md",
    "manifest": "P369_biglotto_evidence_agent_pack_manifest.csv",
}

VALIDATION_COLUMNS = ("check_name", "status", "expected", "actual", "details")

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

PROMPT_REQUIRED_PHRASES = (
    "No DB open/write.",
    "No adapter calls.",
    "No new scoring.",
    "No deploy.",
    "No betting advice.",
    "No future prediction guarantee.",
)

FORBIDDEN_AUTHORIZATION_PHRASES = (
    "you may open the db",
    "you may write the db",
    "open the database",
    "write to the database",
    "you may run adapters",
    "you may execute adapters",
    "you may call adapters",
    "adapter execution is authorized",
    "adapter calls are authorized",
    "create scoring",
    "new scoring cohort is authorized",
    "deploy to production",
    "force push",
    "force merge",
    "bet this",
    "recommended wager",
    "guaranteed win",
    "guaranteed profit",
    "will win",
    "future lock",
    "sure thing",
)


@dataclass(frozen=True)
class AgentPackOutput:
    summary: dict[str, object]
    task_prompts: dict[str, object]
    query_recipes: dict[str, object]
    validation_rows: tuple[dict[str, str], ...]
    examples_md: str
    manifest_rows: tuple[dict[str, str], ...]


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


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_FILES)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise api.EvidenceApiError(f"required P367/P368 evidence files missing: {missing}")
    return paths


def source_artifact_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_artifacts(repo_root)
    rows: list[dict[str, str]] = []
    for relpath in REQUIRED_SOURCE_FILES:
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "path": relpath,
                "sha256": sha256_file(path),
                "source_stage": "P367/P368",
                "artifact_role": Path(relpath).stem,
            }
        )
    return tuple(rows)


def _load_p367_validation(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P367_biglotto_evidence_api_validation.csv", repo_root))


def _load_p368_compatibility(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P368_biglotto_evidence_api_compatibility_matrix.csv", repo_root))


def _load_p368_contract_drift(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    return _read_csv_rows(_artifact_path("artifacts/P368_biglotto_evidence_api_contract_drift.csv", repo_root))


def build_summary(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_artifacts(repo_root)
    p367_contract = api.build_contract(repo_root)
    p367_validation = _load_p367_validation(repo_root)
    compatibility = snapshots.build_compatibility_matrix(repo_root)
    drift = snapshots.build_contract_drift_rows(repo_root)
    source_rows = source_artifact_rows(repo_root)
    supported_functions = tuple(str(row["name"]) for row in p367_contract["supported_functions"])  # type: ignore[index]
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_merge_baseline": SOURCE_MERGE_BASELINE,
        "source_artifacts": tuple(
            {"path": row["path"], "sha256": row["sha256"], "source_stage": row["source_stage"]}
            for row in source_rows
        ),
        "api_facade_availability": {
            "p367_api_task": p367_contract["task"],
            "supported_function_count": len(supported_functions),
            "supported_functions": supported_functions,
            "available": True,
        },
        "snapshot_compatibility_status": {
            "p367_validation_fail_count": sum(1 for row in p367_validation if row["status"] != "PASS"),
            "p368_incompatible_row_count": sum(1 for row in compatibility if row["compatible"] != "TRUE"),
            "p368_contract_drift_fail_count": sum(1 for row in drift if row["status"] == "FAIL"),
            "compatible": all(row["compatible"] == "TRUE" for row in compatibility)
            and all(row["status"] != "FAIL" for row in drift)
            and all(row["status"] == "PASS" for row in p367_validation),
        },
        "statements": STATEMENTS,
        "scope_statements": DISCLAIMER_LINES,
        "recommended_safe_next_task_categories": (
            "read-only API exploration",
            "no-DB artifact audit",
            "no-DB dashboard smoke check",
            "no-DB compatibility revalidation",
            "no-DB CLI usage examples",
        ),
    }


def _prompt(prompt_id: str, title: str, objective: str, allowed_actions: Sequence[str]) -> dict[str, object]:
    constraints = " ".join(PROMPT_REQUIRED_PHRASES)
    prompt_text = textwrap.dedent(
        f"""
        Task: {title}

        Objective: {objective}

        Constraints: {constraints} Historical descriptive evidence only. No production registry import. No blended leaderboard. Shape-only and blocked targets remain excluded.

        Allowed actions:
        {chr(10).join(f"- {action}" for action in allowed_actions)}

        Stop if the task would require DB access, adapter execution, new scoring, deploy, force operations, betting advice, or future-performance claims.
        """
    ).strip()
    return {
        "prompt_id": prompt_id,
        "title": title,
        "intended_agent": "Planner or Worker",
        "prompt": prompt_text,
        "required_constraints": PROMPT_REQUIRED_PHRASES,
    }


def build_task_prompts() -> dict[str, object]:
    prompts = (
        _prompt(
            "read_only_api_exploration",
            "Read-only API exploration",
            "Inspect the P367 Big Lotto no-DB evidence API facade and summarize available functions and output shapes for handoff use.",
            (
                "Run `python3 -m recovered_strategies.biglotto.no_db_evidence_api --help`.",
                "Use only facade calls that read committed artifacts.",
                "Report function names, arguments, and output schemas.",
            ),
        ),
        _prompt(
            "no_db_artifact_audit",
            "No-DB artifact audit",
            "Check that required P367/P368 evidence artifacts exist, parse, and have stable SHA256 values.",
            (
                "Read JSON and CSV artifacts with stdlib parsers.",
                "Compare manifest paths and source SHA256 values.",
                "Report only historical artifact availability and parse status.",
            ),
        ),
        _prompt(
            "no_db_dashboard_smoke_check",
            "No-DB dashboard smoke check",
            "Smoke check committed dashboard and explorer artifacts without importing production registries or executing adapters.",
            (
                "Inspect committed HTML/JSON/CSV artifacts under `artifacts/`.",
                "Confirm static links and evidence tables are present.",
                "Avoid runtime services and DB-backed routes.",
            ),
        ),
        _prompt(
            "no_db_compatibility_revalidation",
            "No-DB compatibility revalidation",
            "Revalidate P367 API compatibility with P368 golden snapshots and report any contract drift.",
            (
                "Run `python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --validate`.",
                "Inspect compatibility matrix rows for incompatible entries.",
                "Inspect contract drift rows for FAIL status.",
            ),
        ),
        _prompt(
            "no_db_cli_usage_examples",
            "No-DB CLI usage examples",
            "Generate safe local CLI examples for future workers using the P367/P368 evidence API only.",
            (
                "Use `--list-adapters`, `--get-adapter`, `--compact-shortlist`, and `--validate` examples.",
                "Label outputs as historical descriptive evidence.",
                "Include no-betting and no-future-prediction disclaimers.",
            ),
        ),
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "statements": STATEMENTS,
        "prompts": prompts,
    }


def build_query_recipes() -> dict[str, object]:
    recipes = (
        {
            "recipe_id": "list_adapters",
            "purpose": "List adapter function names exposed by the P367 facade.",
            "python_api": "api.list_adapters()",
            "cli": "python3 -m recovered_strategies.biglotto.no_db_evidence_api --list-adapters",
            "expected_result": "JSON array of adapter_function strings.",
        },
        {
            "recipe_id": "inspect_one_adapter",
            "purpose": "Inspect one adapter detail card from committed evidence.",
            "python_api": "api.get_adapter(adapter_function)",
            "cli": "python3 -m recovered_strategies.biglotto.no_db_evidence_api --get-adapter adapt_predict_biglotto_echo_mixed_3bet",
            "expected_result": "JSON object for one adapter detail card.",
        },
        {
            "recipe_id": "list_compact_shortlist",
            "purpose": "List the compact shortlist rows from P365 evidence through P367.",
            "python_api": "api.get_compact_shortlist()",
            "cli": "python3 -m recovered_strategies.biglotto.no_db_evidence_api --compact-shortlist",
            "expected_result": "CSV rows for compact historical evidence candidates.",
        },
        {
            "recipe_id": "compare_two_adapters",
            "purpose": "Read one pairwise comparison row for two adapter names.",
            "python_api": "api.compare_adapters(adapter_a, adapter_b)",
            "cli": "python3 -m recovered_strategies.biglotto.no_db_evidence_api --compare-adapters adapt_biglotto_p0_2bet adapt_predict_biglotto_echo_2bet",
            "expected_result": "JSON object for one pairwise historical comparison.",
        },
        {
            "recipe_id": "validate_evidence_stack",
            "purpose": "Validate required source artifacts and P367 generated shapes.",
            "python_api": "api.validate_evidence_stack()",
            "cli": "python3 -m recovered_strategies.biglotto.no_db_evidence_api --validate",
            "expected_result": "CSV validation rows with PASS status.",
        },
        {
            "recipe_id": "inspect_snapshot_compatibility",
            "purpose": "Inspect P368 compatibility and drift without new scoring.",
            "python_api": "snapshots.build_compatibility_matrix(); snapshots.build_contract_drift_rows()",
            "cli": "python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --compatibility-matrix",
            "expected_result": "CSV compatibility rows with compatible TRUE and no drift FAIL rows.",
        },
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "statements": STATEMENTS,
        "constraints": DISCLAIMER_LINES,
        "recipes": recipes,
    }


def _prompts_text(prompts: Mapping[str, object]) -> str:
    return "\n\n".join(str(row["prompt"]) for row in prompts["prompts"])  # type: ignore[index]


def _artifact_contents_without_manifest(output: AgentPackOutput) -> dict[str, str]:
    return {
        "summary": _json_text(output.summary),
        "task_prompts": _json_text(output.task_prompts),
        "query_recipes": _json_text(output.query_recipes),
        "validation_checklist": _csv_text(VALIDATION_COLUMNS, output.validation_rows),
        "examples": output.examples_md,
    }


def _artifact_contents(output: AgentPackOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"validation_checklist", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"summary", "task_prompts", "query_recipes"}:
        return "", "1"
    if role == "examples":
        return str(len(text.splitlines())), ""
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for source in source_artifact_rows(repo_root):
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": source["artifact_role"],
                "path": source["path"],
                "source_sha256": source["sha256"],
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P369 source evidence read without DB open/write or adapter execution.",
            }
        )
    for role, basename in P369_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_FILES) + len(P369_ARTIFACT_BASENAMES) + 2)
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
                "details": "P369 generated agent handoff pack artifact.",
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
                "details": "P369 artifact generation performs deterministic double-run equality before write.",
            },
        )
    )
    return tuple(rows)


def render_examples() -> str:
    disclaimer = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    return f"""# P369 Big Lotto no-DB evidence agent pack examples

Generated at: {GENERATED_AT}

This handoff pack helps future Planner and Worker agents consume the stable P367/P368 no-DB evidence API without manually parsing scattered artifacts.

## Local CLI commands

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --help
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --emit-summary
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --task-prompts
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --query-recipes
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --validation-checklist
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --print-handoff
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack --validate
```

With no action flag, the CLI writes all P369 artifacts into `artifacts/`.

## Safe copy/paste task examples

```text
Use the P369 Big Lotto no-DB evidence agent pack to inspect read-only API functions. No DB open/write. No adapter calls. No new scoring. No deploy. No betting advice. No future prediction guarantee.
```

```text
Use the P369 query recipes to validate P367/P368 compatibility rows. Historical descriptive evidence only. No DB open/write. No adapter calls. No new scoring. No deploy. No future prediction guarantee. No betting advice.
```

## Expected output summaries

- Summary JSON reports the P368 merge baseline, source artifact paths, SHA256 values, facade availability, snapshot compatibility, and safe next-task categories.
- Task prompts JSON contains deterministic templates for read-only API exploration, no-DB artifact audit, no-DB dashboard smoke check, no-DB compatibility revalidation, and no-DB CLI examples.
- Query recipes JSON contains deterministic recipes for list adapters, inspect one adapter, list compact shortlist, compare two adapters, validate evidence stack, and inspect snapshot compatibility.
- Validation checklist CSV reports PASS/FAIL rows for required files, P367 validation, P368 compatibility, P368 drift, prompt constraints, forbidden authorization language, and deterministic generation.
- Manifest CSV records source artifacts, source SHA256 values, output artifacts, output row/object counts, and no-DB/no-adapter/no-scoring statements.

## Disclaimers

{disclaimer}

The pack does not import production registries, deploy, call adapters, open a DB, write a DB, create a new scoring cohort, create a blended leaderboard, score shape-only targets, or score blocked targets.
"""


def validate_agent_pack(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    paths = verify_required_artifacts(repo_root)
    p367_validation = _load_p367_validation(repo_root)
    p368_compatibility = _load_p368_compatibility(repo_root)
    p368_drift = _load_p368_contract_drift(repo_root)
    summary = build_summary(repo_root)
    prompts = build_task_prompts()
    recipes = build_query_recipes()
    examples = render_examples()
    prompt_text = _prompts_text(prompts)
    generated_text = "\n".join((_json_text(summary), _json_text(prompts), _json_text(recipes), examples)).lower()
    forbidden_found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in generated_text]
    rows.extend(
        (
            _check("required_p367_p368_files_exist", len(paths) == len(REQUIRED_SOURCE_FILES), len(REQUIRED_SOURCE_FILES), len(paths), "Required P367/P368 source files are present."),
            _check("p367_api_validation_has_no_failures", all(row["status"] == "PASS" for row in p367_validation), "all PASS", sum(1 for row in p367_validation if row["status"] != "PASS"), "P367 validation CSV has no failing rows."),
            _check("p368_compatibility_matrix_has_no_fail_rows", all(row["compatible"] == "TRUE" for row in p368_compatibility), "all TRUE", sum(1 for row in p368_compatibility if row["compatible"] != "TRUE"), "P368 compatibility matrix has no incompatible rows."),
            _check("p368_contract_drift_has_no_fail_rows", all(row["status"] != "FAIL" for row in p368_drift), "no FAIL", sum(1 for row in p368_drift if row["status"] == "FAIL"), "P368 contract drift CSV has no FAIL rows."),
            _check("summary_json_schema", set(summary) == {"task", "generated_at", "source_merge_baseline", "source_artifacts", "api_facade_availability", "snapshot_compatibility_status", "statements", "scope_statements", "recommended_safe_next_task_categories"}, "required summary keys", sorted(summary), "Summary JSON includes the required P369 sections."),
            _check("task_prompts_json_schema", set(prompts) == {"task", "generated_at", "statements", "prompts"} and len(prompts["prompts"]) == 5, "5 prompts", len(prompts["prompts"]), "Task prompts JSON includes deterministic prompt templates."),
            _check("query_recipes_json_schema", set(recipes) == {"task", "generated_at", "statements", "constraints", "recipes"} and len(recipes["recipes"]) == 6, "6 recipes", len(recipes["recipes"]), "Query recipes JSON includes deterministic recipe templates."),
            _check("generated_prompts_contain_required_constraints", all(all(phrase in str(prompt["prompt"]) for phrase in PROMPT_REQUIRED_PHRASES) for prompt in prompts["prompts"]), "all required phrases in every prompt", "present", "Each generated prompt contains no-DB/no-adapter/no-scoring/no-deploy/no-betting/no-future-claim constraints."),
            _check("generated_examples_contain_required_sections", all(section in examples for section in ("## Local CLI commands", "## Safe copy/paste task examples", "## Expected output summaries", "## Disclaimers")), "all examples sections", "present", "Examples Markdown includes required sections."),
            _check("generated_examples_contain_disclaimers", all(line in examples for line in DISCLAIMER_LINES), "all disclaimer lines", "present", "Examples Markdown contains all required disclaimers."),
            _check("generated_prompts_do_not_authorize_forbidden_actions", not forbidden_found, "absent", ";".join(forbidden_found) if forbidden_found else "absent", "Generated pack text does not authorize DB writes, adapter execution, scoring, deploy, force operations, or betting claims."),
            _check("snapshot_compatibility_status_true", summary["snapshot_compatibility_status"]["compatible"] is True, True, summary["snapshot_compatibility_status"]["compatible"], "Summary reports compatible P367/P368 evidence state."),
            _check("prompt_text_is_nonempty", bool(prompt_text.strip()), "nonempty", len(prompt_text), "Prompt text is available for agent handoff."),
        )
    )
    return tuple(rows)


def run_agent_pack(repo_root: Path | None = None) -> AgentPackOutput:
    summary = build_summary(repo_root)
    task_prompts = build_task_prompts()
    query_recipes = build_query_recipes()
    examples = render_examples()
    validation_rows = validate_agent_pack(repo_root)
    placeholder = AgentPackOutput(summary, task_prompts, query_recipes, validation_rows, examples, ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(placeholder), repo_root)
    return AgentPackOutput(summary, task_prompts, query_recipes, validation_rows, examples, manifest)


def _assert_deterministic(first: AgentPackOutput, second: AgentPackOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P369 agent pack artifacts are not reproducible")


def write_artifacts(output: AgentPackOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P369_ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        with open(path, "w", encoding="utf-8", newline="" if path.suffix == ".csv" else None) as handle:
            handle.write(contents[key])
    return paths


def _print_json(payload: object) -> None:
    print(_json_text(payload), end="")


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def _print_handoff(output: AgentPackOutput) -> None:
    prompt = output.task_prompts["prompts"][0]["prompt"]  # type: ignore[index]
    print("P369 Big Lotto no-DB evidence agent handoff")
    print(f"baseline: {SOURCE_MERGE_BASELINE}")
    print(f"compatible: {output.summary['snapshot_compatibility_status']['compatible']}")  # type: ignore[index]
    print("constraints: " + " ".join(PROMPT_REQUIRED_PHRASES))
    print()
    print(prompt)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    parser.add_argument("--generate", action="store_true", help="write all P369 artifacts")
    parser.add_argument("--emit-summary", action="store_true", help="emit agent pack summary JSON")
    parser.add_argument("--task-prompts", action="store_true", help="emit safe task prompts JSON")
    parser.add_argument("--query-recipes", action="store_true", help="emit query recipes JSON")
    parser.add_argument("--validation-checklist", action="store_true", help="emit validation checklist CSV")
    parser.add_argument("--examples", action="store_true", help="emit examples Markdown")
    parser.add_argument("--manifest", action="store_true", help="emit manifest CSV")
    parser.add_argument("--print-handoff", action="store_true", help="print one example agent handoff")
    parser.add_argument("--validate", action="store_true", help="emit validation checklist CSV")
    args = parser.parse_args(argv)

    if args.emit_summary:
        _print_json(build_summary())
    elif args.task_prompts:
        _print_json(build_task_prompts())
    elif args.query_recipes:
        _print_json(build_query_recipes())
    elif args.validation_checklist or args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_agent_pack())
    elif args.examples:
        print(render_examples(), end="")
    elif args.manifest:
        output = run_agent_pack()
        _print_csv(MANIFEST_COLUMNS, output.manifest_rows)
    elif args.print_handoff:
        _print_handoff(run_agent_pack())
    else:
        first = run_agent_pack()
        second = run_agent_pack()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P369 Big Lotto no-DB evidence agent pack: determinism double-run PASS")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring cohort was created; no deploy was performed.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
