"""P370 Big Lotto no-DB agent pack consumer and transcript runner.

This module consumes the merged P369 safe prompts and query recipes, executes
only P367/P368 no-DB artifact-backed API paths, and emits deterministic
transcripts, recipe summaries, prompt safety audit rows, copy-paste task cards,
examples, and a manifest. It does not open or write a DB, import production
registries, call adapters, create new scoring cohorts, deploy, or make betting
or future-performance claims.
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

from recovered_strategies.biglotto import no_db_evidence_agent_pack as pack
from recovered_strategies.biglotto import no_db_evidence_api as api
from recovered_strategies.biglotto import no_db_evidence_api_snapshots as snapshots

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P370_biglotto_agent_pack_consumer"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_MERGE_BASELINE = "7655fa88aae81c4698f2b1e12d02f9ce48d7c212"

REQUIRED_SOURCE_FILES = (
    "recovered_strategies/biglotto/no_db_evidence_agent_pack.py",
    "recovered_strategies/biglotto/no_db_evidence_api.py",
    "recovered_strategies/biglotto/no_db_evidence_api_snapshots.py",
    "artifacts/P369_biglotto_evidence_agent_pack_summary.json",
    "artifacts/P369_biglotto_evidence_agent_pack_task_prompts.json",
    "artifacts/P369_biglotto_evidence_agent_pack_query_recipes.json",
    "artifacts/P369_biglotto_evidence_agent_pack_validation_checklist.csv",
    "artifacts/P369_biglotto_evidence_agent_pack_examples.md",
    "artifacts/P369_biglotto_evidence_agent_pack_manifest.csv",
    "artifacts/P368_biglotto_evidence_api_golden_snapshots.json",
    "artifacts/P368_biglotto_evidence_api_compatibility_matrix.csv",
    "artifacts/P368_biglotto_evidence_api_contract_drift.csv",
    "artifacts/P368_biglotto_evidence_api_cli_transcripts.json",
    "artifacts/P368_biglotto_evidence_api_manifest.csv",
    "artifacts/P368_biglotto_evidence_api_readme.md",
    "artifacts/P367_biglotto_evidence_api_contract.json",
    "artifacts/P367_biglotto_evidence_api_examples.json",
    "artifacts/P367_biglotto_evidence_api_validation.csv",
    "artifacts/P367_biglotto_evidence_api_manifest.csv",
    "artifacts/P367_biglotto_evidence_api_readme.md",
    "tests/test_p369_biglotto_evidence_agent_pack.py",
    "tests/test_p368_biglotto_evidence_api_snapshots.py",
    "tests/test_p367_biglotto_evidence_api.py",
)

P370_ARTIFACT_BASENAMES = {
    "transcripts": "P370_biglotto_agent_pack_consumer_transcripts.json",
    "recipe_results": "P370_biglotto_agent_pack_consumer_recipe_results.csv",
    "prompt_safety_audit": "P370_biglotto_agent_pack_consumer_prompt_safety_audit.csv",
    "task_cards": "P370_biglotto_agent_pack_consumer_task_cards.json",
    "examples": "P370_biglotto_agent_pack_consumer_examples.md",
    "manifest": "P370_biglotto_agent_pack_consumer_manifest.csv",
}

RECIPE_RESULT_COLUMNS = (
    "recipe_id",
    "recipe_type",
    "source_artifact",
    "command_or_api_function",
    "status",
    "output_summary",
    "no_db_confirmed",
    "no_adapter_calls_confirmed",
    "no_new_scoring_confirmed",
)

PROMPT_SAFETY_COLUMNS = (
    "prompt_source",
    "prompt_id",
    "title",
    "status",
    "contains_no_db_constraint",
    "contains_no_adapter_calls_constraint",
    "contains_no_new_scoring_constraint",
    "contains_no_deploy_constraint",
    "contains_no_betting_advice_constraint",
    "contains_no_future_prediction_constraint",
    "does_not_grant_standing_authorization",
    "forbidden_authorization_absent",
    "details",
)

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
    "Generated prompts are templates, not standing authorization.",
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
    "generated_prompts_templates_not_standing_authorization": True,
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
    "adapter execution is authorized",
    "adapter calls are authorized",
    "new scoring cohort is authorized",
    "deploy to production",
    "force push",
    "force merge",
    "force-delete",
    "status changes are authorized",
    "bet this",
    "recommended wager",
    "guaranteed win",
    "guaranteed profit",
    "will win",
    "future lock",
    "sure thing",
)

KNOWN_ADAPTER = "adapt_predict_biglotto_echo_mixed_3bet"
KNOWN_PAIR = ("adapt_biglotto_p0_2bet", "adapt_predict_biglotto_echo_2bet")
P369_PROMPTS_ARTIFACT = "artifacts/P369_biglotto_evidence_agent_pack_task_prompts.json"
P369_RECIPES_ARTIFACT = "artifacts/P369_biglotto_evidence_agent_pack_query_recipes.json"


@dataclass(frozen=True)
class ConsumerOutput:
    transcripts: dict[str, object]
    recipe_rows: tuple[dict[str, str], ...]
    prompt_safety_rows: tuple[dict[str, str], ...]
    task_cards: dict[str, object]
    examples_md: str
    manifest_rows: tuple[dict[str, str], ...]
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


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_FILES)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise api.EvidenceApiError(f"required P367/P368/P369 evidence artifacts missing: {missing}")
    return paths


def source_artifact_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_artifacts(repo_root)
    rows: list[dict[str, str]] = []
    for relpath in REQUIRED_SOURCE_FILES:
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
                "details": "P370 source evidence read without DB open/write or adapter execution.",
            }
        )
    return tuple(rows)


def load_p369_task_prompts(repo_root: Path | None = None) -> dict[str, object]:
    payload = _read_json(_artifact_path(P369_PROMPTS_ARTIFACT, repo_root))
    if not isinstance(payload, dict):
        raise api.EvidenceApiError("P369 task prompts artifact must be a JSON object")
    return dict(payload)


def load_p369_query_recipes(repo_root: Path | None = None) -> dict[str, object]:
    payload = _read_json(_artifact_path(P369_RECIPES_ARTIFACT, repo_root))
    if not isinstance(payload, dict):
        raise api.EvidenceApiError("P369 query recipes artifact must be a JSON object")
    return dict(payload)


def _summary_from_output(recipe_id: str, output: object, repo_root: Path | None = None) -> str:
    if recipe_id == "list_adapters":
        return f"{len(output)} adapter_function names listed from committed P365/P367 evidence."
    if recipe_id == "inspect_one_adapter" and isinstance(output, dict):
        return f"Adapter {output.get('adapter_function')} maps to strategy_id {output.get('strategy_id')} with no runtime adapter call."
    if recipe_id == "list_compact_shortlist":
        return f"{len(output)} compact shortlist rows read from committed P365/P367 evidence."
    if recipe_id == "compare_two_adapters" and isinstance(output, dict):
        return f"Pairwise row {output.get('adapter_pair')} read with display_rank {output.get('display_rank')}."
    if recipe_id == "validate_evidence_stack":
        fails = sum(1 for row in output if isinstance(row, dict) and row.get("status") == "FAIL")  # type: ignore[arg-type]
        return f"{len(output)} P367 validation rows read; fail_count={fails}."
    if recipe_id == "inspect_snapshot_compatibility":
        matrix = snapshots.build_compatibility_matrix(repo_root)
        drift = snapshots.build_contract_drift_rows(repo_root)
        incompatible = sum(1 for row in matrix if row["compatible"] != "TRUE")
        drift_fail = sum(1 for row in drift if row["status"] == "FAIL")
        return f"{len(matrix)} compatibility rows and {len(drift)} drift rows read; incompatible={incompatible}; drift_fail={drift_fail}."
    return "Safe no-DB recipe output read from committed evidence artifacts."


def _execute_recipe(recipe_id: str, repo_root: Path | None = None) -> tuple[str, str, object]:
    if recipe_id == "list_adapters":
        return ("api", "api.list_adapters()", api.list_adapters(repo_root))
    if recipe_id == "inspect_one_adapter":
        return ("api", f"api.get_adapter({KNOWN_ADAPTER!r})", api.get_adapter(KNOWN_ADAPTER, repo_root))
    if recipe_id == "list_compact_shortlist":
        return ("api", "api.get_compact_shortlist()", api.get_compact_shortlist(repo_root))
    if recipe_id == "compare_two_adapters":
        return (
            "api",
            f"api.compare_adapters({KNOWN_PAIR[0]!r}, {KNOWN_PAIR[1]!r})",
            api.compare_adapters(KNOWN_PAIR[0], KNOWN_PAIR[1], repo_root),
        )
    if recipe_id == "validate_evidence_stack":
        return ("api", "api.validate_evidence_stack()", api.validate_evidence_stack(repo_root))
    if recipe_id == "inspect_snapshot_compatibility":
        payload = {
            "compatibility_matrix": snapshots.build_compatibility_matrix(repo_root),
            "contract_drift": snapshots.build_contract_drift_rows(repo_root),
        }
        return ("snapshot_api", "snapshots.build_compatibility_matrix(); snapshots.build_contract_drift_rows()", payload)
    raise api.EvidenceApiError(f"unsupported P369 query recipe: {recipe_id}")


def run_query_recipes(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_artifacts(repo_root)
    recipes = load_p369_query_recipes(repo_root)
    rows: list[dict[str, str]] = []
    for recipe in recipes.get("recipes", ()):
        if not isinstance(recipe, dict):
            continue
        recipe_id = str(recipe["recipe_id"])
        recipe_type, function_text, output = _execute_recipe(recipe_id, repo_root)
        rows.append(
            {
                "recipe_id": recipe_id,
                "recipe_type": recipe_type,
                "source_artifact": P369_RECIPES_ARTIFACT,
                "command_or_api_function": function_text,
                "status": "PASS",
                "output_summary": _summary_from_output(recipe_id, output, repo_root),
                "no_db_confirmed": "YES",
                "no_adapter_calls_confirmed": "YES",
                "no_new_scoring_confirmed": "YES",
            }
        )
    return tuple(rows)


def build_transcripts(repo_root: Path | None = None) -> dict[str, object]:
    recipe_rows = {row["recipe_id"]: row for row in run_query_recipes(repo_root)}
    adapters = api.list_adapters(repo_root)
    adapter = api.get_adapter(KNOWN_ADAPTER, repo_root)
    shortlist = api.get_compact_shortlist(repo_root)
    comparison = api.compare_adapters(KNOWN_PAIR[0], KNOWN_PAIR[1], repo_root)
    validation = api.validate_evidence_stack(repo_root)
    compatibility = snapshots.build_compatibility_matrix(repo_root)
    drift = snapshots.build_contract_drift_rows(repo_root)
    transcript_specs = (
        (
            "list_adapters",
            "List Big Lotto evidence adapters.",
            f"Listed {len(adapters)} adapter_function names: {', '.join(adapters)}.",
        ),
        (
            "inspect_one_adapter",
            f"Inspect adapter {KNOWN_ADAPTER}.",
            f"Adapter {adapter['adapter_function']} uses strategy_id {adapter['strategy_id']} and has bet_count {adapter['bet_count']}.",
        ),
        (
            "list_compact_shortlist",
            "List compact shortlist rows.",
            f"Read {len(shortlist)} compact shortlist rows; top display_rank={shortlist[0]['display_rank']} adapter_subset={shortlist[0]['adapter_subset']}.",
        ),
        (
            "compare_two_adapters",
            f"Compare {KNOWN_PAIR[0]} and {KNOWN_PAIR[1]}.",
            f"Read pairwise comparison rank {comparison['display_rank']} with coverage_rate {comparison['p361_pair_coverage_rate']}.",
        ),
        (
            "validate_evidence_stack",
            "Validate the no-DB evidence stack.",
            f"Read {len(validation)} validation rows; fail_count={sum(1 for row in validation if row['status'] == 'FAIL')}.",
        ),
        (
            "inspect_snapshot_compatibility",
            "Inspect snapshot compatibility.",
            f"Read {len(compatibility)} compatibility rows and {len(drift)} drift rows; incompatible={sum(1 for row in compatibility if row['compatible'] != 'TRUE')}; drift_fail={sum(1 for row in drift if row['status'] == 'FAIL')}.",
        ),
    )
    transcripts: list[dict[str, object]] = []
    for transcript_id, user_text, assistant_text in transcript_specs:
        recipe = recipe_rows[transcript_id]
        transcripts.append(
            {
                "transcript_id": transcript_id,
                "recipe_id": transcript_id,
                "source_artifact": P369_RECIPES_ARTIFACT,
                "command_or_api_function": recipe["command_or_api_function"],
                "messages": (
                    {
                        "role": "user",
                        "content": (
                            f"{user_text} Use no-DB committed evidence only. No adapter calls. "
                            "No new scoring. No deploy. No betting advice. No future prediction guarantee."
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": (
                            f"{assistant_text} Historical descriptive evidence only. "
                            "No DB open/write; no adapter calls; no new scoring cohort; no deploy."
                        ),
                    },
                ),
                "output_summary": recipe["output_summary"],
                "no_db_confirmed": True,
                "no_adapter_calls_confirmed": True,
                "no_new_scoring_confirmed": True,
            }
        )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_merge_baseline": SOURCE_MERGE_BASELINE,
        "statements": STATEMENTS,
        "transcripts": tuple(transcripts),
    }


def _template_footer() -> str:
    return (
        "This prompt is a copy-paste template only, not standing authorization. "
        "Stop before any DB write, migration, backfill, deploy, force operation, production registry import, "
        "strategy status change, adapter call, new scoring cohort, betting advice, or future-performance claim."
    )


def _constraint_text() -> str:
    return (
        "Historical descriptive evidence only. No future prediction guarantee. No betting advice. "
        "No DB open/write. No production registry import. No deploy. No adapter calls. "
        "No new scoring. No new scoring cohort. No blended leaderboard. "
        "Generated prompts are templates, not standing authorization. "
        "Shape-only and blocked targets remain excluded."
    )


def build_task_cards(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_artifacts(repo_root)
    cards = (
        (
            "read_only_api_exploration",
            "Read-only API exploration",
            "Use the P367 no-DB facade to list supported functions, inspect one adapter, and summarize output shapes.",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_api --help",
        ),
        (
            "artifact_inventory_audit",
            "Artifact inventory audit",
            "Read the P367/P368/P369 manifests and confirm artifact paths, SHA256 values, and parseable JSON/CSV shapes.",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --manifest",
        ),
        (
            "compatibility_revalidation",
            "Compatibility revalidation",
            "Run the no-DB compatibility and drift checks and report only PASS/WARN/FAIL rows from committed evidence.",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --validate",
        ),
        (
            "dashboard_explorer_smoke_check",
            "Dashboard/explorer smoke check",
            "Inspect committed dashboard and explorer HTML/JSON/CSV artifacts without runtime services or DB-backed routes.",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --run-recipes",
        ),
        (
            "local_evidence_query_examples",
            "Local evidence query examples",
            "Use P369 recipes through the P370 consumer to produce deterministic transcript examples for future Workers.",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --transcripts",
        ),
    )
    task_cards: list[dict[str, object]] = []
    for card_id, title, objective, command in cards:
        prompt = textwrap.dedent(
            f"""
            Task: {title}

            Objective: {objective}

            Constraints: {_constraint_text()}

            Local command:
            {command}

            {_template_footer()}
            """
        ).strip()
        task_cards.append(
            {
                "card_id": card_id,
                "title": title,
                "intended_agent": "Future Worker",
                "source_artifacts": (P369_PROMPTS_ARTIFACT, P369_RECIPES_ARTIFACT),
                "copy_paste_prompt": prompt,
                "template_not_standing_authorization": True,
                "no_db_open_write": True,
                "no_adapter_calls": True,
                "no_new_scoring": True,
            }
        )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "statements": STATEMENTS,
        "task_cards": tuple(task_cards),
    }


def _audit_prompt(prompt_source: str, prompt_id: str, title: str, prompt_text: str) -> dict[str, str]:
    lowered = prompt_text.lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in lowered]
    checks = {
        "contains_no_db_constraint": "No DB open/write." in prompt_text,
        "contains_no_adapter_calls_constraint": "No adapter calls." in prompt_text,
        "contains_no_new_scoring_constraint": "No new scoring" in prompt_text,
        "contains_no_deploy_constraint": "No deploy." in prompt_text,
        "contains_no_betting_advice_constraint": "No betting advice." in prompt_text,
        "contains_no_future_prediction_constraint": "No future prediction guarantee." in prompt_text,
        "does_not_grant_standing_authorization": "not standing authorization" in lowered
        and "standing authorization granted" not in lowered,
        "forbidden_authorization_absent": not found,
    }
    return {
        "prompt_source": prompt_source,
        "prompt_id": prompt_id,
        "title": title,
        "status": "PASS" if all(checks.values()) else "FAIL",
        **{key: "YES" if value else "NO" for key, value in checks.items()},
        "details": "Prompt/template contains required safety constraints and does not authorize forbidden actions."
        if not found
        else f"Forbidden authorization phrases found: {';'.join(found)}",
    }


def build_prompt_safety_audit(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    p369_prompts = load_p369_task_prompts(repo_root)
    task_cards = build_task_cards(repo_root)
    rows: list[dict[str, str]] = []
    for prompt in p369_prompts.get("prompts", ()):
        if not isinstance(prompt, dict):
            continue
        wrapped_prompt = f"{prompt.get('prompt', '')}\n\nP370 consumer note: {_template_footer()}"
        rows.append(
            _audit_prompt(
                "P369_task_prompts_wrapped_by_P370",
                str(prompt.get("prompt_id", "")),
                str(prompt.get("title", "")),
                wrapped_prompt,
            )
        )
    for card in task_cards["task_cards"]:  # type: ignore[index]
        if not isinstance(card, dict):
            continue
        rows.append(
            _audit_prompt(
                "P370_task_card",
                str(card.get("card_id", "")),
                str(card.get("title", "")),
                str(card.get("copy_paste_prompt", "")),
            )
        )
    return tuple(rows)


def render_examples(repo_root: Path | None = None) -> str:
    recipe_rows = run_query_recipes(repo_root)
    transcripts = build_transcripts(repo_root)
    disclaimer = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    first_transcript = transcripts["transcripts"][0]  # type: ignore[index]
    first_recipe = recipe_rows[0]
    return f"""# P370 Big Lotto no-DB agent pack consumer examples

Generated at: {GENERATED_AT}

This consumer runs P369 safe query recipes against P367/P368 no-DB artifact-backed APIs and emits deterministic transcript examples for future Workers.

## Local CLI commands

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --help
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --generate
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --run-recipes
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --transcripts
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --prompt-safety-audit
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --task-cards
python3 -m recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer --validate
```

With no action flag, the CLI writes all P370 artifacts into `artifacts/`.

## Safe copy/paste snippets

```text
Use the P370 Big Lotto no-DB agent pack consumer to run P369 query recipes against committed evidence artifacts only. No DB open/write. No adapter calls. No new scoring. No deploy. No betting advice. No future prediction guarantee. This prompt is a template, not standing authorization.
```

```text
Generate deterministic transcript examples from P367/P368 no-DB facade outputs. Historical descriptive evidence only. No production registry import. No blended leaderboard. Shape-only and blocked targets remain excluded.
```

## Expected deterministic summaries

- Transcript count: {len(transcripts["transcripts"])}.
- Recipe result count: {len(recipe_rows)}.
- First transcript summary: {first_transcript["output_summary"]}.
- First recipe summary: {first_recipe["output_summary"]}.
- Prompt audit rows cover P369 source prompt templates wrapped by P370 and P370 task card templates.
- Manifest records source SHA256 values, output row/object counts, and explicit no-DB/no-adapter/no-scoring statements.

## Disclaimers

{disclaimer}

The consumer does not open or write a DB, call adapters, create a new scoring cohort, create a blended leaderboard, import production registries, deploy, score shape-only targets, score blocked targets, provide betting advice, or guarantee future performance.
"""


def _artifact_contents_without_manifest(output: ConsumerOutput) -> dict[str, str]:
    return {
        "transcripts": _json_text(output.transcripts),
        "recipe_results": _csv_text(RECIPE_RESULT_COLUMNS, output.recipe_rows),
        "prompt_safety_audit": _csv_text(PROMPT_SAFETY_COLUMNS, output.prompt_safety_rows),
        "task_cards": _json_text(output.task_cards),
        "examples": output.examples_md,
    }


def _artifact_contents(output: ConsumerOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"recipe_results", "prompt_safety_audit", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"transcripts", "task_cards"}:
        return "", "1"
    if role == "examples":
        return str(len(text.splitlines())), ""
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = list(source_artifact_rows(repo_root))
    for role, basename in P370_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_FILES) + len(P370_ARTIFACT_BASENAMES) + 2)
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
                "details": "P370 generated no-DB agent pack consumer artifact.",
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
                    "no new scoring cohort; no blended leaderboard; generated prompts are templates, "
                    "not standing authorization; shape-only and blocked targets remain excluded."
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
                "details": "P370 artifact generation performs deterministic double-run equality before write.",
            },
        )
    )
    return tuple(rows)


def validate_consumer(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    paths = verify_required_artifacts(repo_root)
    transcripts = build_transcripts(repo_root)
    recipe_rows = run_query_recipes(repo_root)
    audit_rows = build_prompt_safety_audit(repo_root)
    task_cards = build_task_cards(repo_root)
    examples = render_examples(repo_root)
    p369_validation = _read_csv_rows(_artifact_path("artifacts/P369_biglotto_evidence_agent_pack_validation_checklist.csv", repo_root))
    p368_compatibility = snapshots.build_compatibility_matrix(repo_root)
    p368_drift = snapshots.build_contract_drift_rows(repo_root)
    first = _run_consumer_without_validation(repo_root)
    second = _run_consumer_without_validation(repo_root)
    rows.extend(
        (
            _check("required_p367_p368_p369_artifacts_exist", len(paths) == len(REQUIRED_SOURCE_FILES), len(REQUIRED_SOURCE_FILES), len(paths), "Required P367/P368/P369 source artifacts are present."),
            _check("p369_validation_has_no_failures", all(row["status"] == "PASS" for row in p369_validation), "all PASS", sum(1 for row in p369_validation if row["status"] != "PASS"), "P369 validation checklist has no failing rows."),
            _check("p368_compatibility_has_no_incompatible_rows", all(row["compatible"] == "TRUE" for row in p368_compatibility), "all TRUE", sum(1 for row in p368_compatibility if row["compatible"] != "TRUE"), "P368 compatibility matrix remains compatible."),
            _check("p368_contract_drift_has_no_fail_rows", all(row["status"] != "FAIL" for row in p368_drift), "no FAIL", sum(1 for row in p368_drift if row["status"] == "FAIL"), "P368 contract drift rows have no FAIL status."),
            _check("transcripts_json_schema", set(transcripts) == {"task", "generated_at", "source_merge_baseline", "statements", "transcripts"} and len(transcripts["transcripts"]) == 6, "6 transcripts with required keys", len(transcripts["transcripts"]), "Transcripts JSON includes all requested transcript examples."),
            _check("recipe_results_csv_schema", recipe_rows and tuple(recipe_rows[0]) == RECIPE_RESULT_COLUMNS, RECIPE_RESULT_COLUMNS, tuple(recipe_rows[0]) if recipe_rows else (), "Recipe results rows use required columns."),
            _check("recipe_results_all_safe", all(row["status"] in {"PASS", "WARN"} and row["no_db_confirmed"] == "YES" and row["no_adapter_calls_confirmed"] == "YES" and row["no_new_scoring_confirmed"] == "YES" for row in recipe_rows), "all safe PASS/WARN", "safe", "Recipe results confirm no DB, no adapter calls, and no new scoring."),
            _check("prompt_safety_audit_csv_schema", audit_rows and tuple(audit_rows[0]) == PROMPT_SAFETY_COLUMNS, PROMPT_SAFETY_COLUMNS, tuple(audit_rows[0]) if audit_rows else (), "Prompt safety audit rows use required columns."),
            _check("prompt_safety_audit_all_pass", all(row["status"] == "PASS" for row in audit_rows), "all PASS", sum(1 for row in audit_rows if row["status"] != "PASS"), "All prompt/template audit rows pass safety checks."),
            _check("task_cards_json_schema", set(task_cards) == {"task", "generated_at", "statements", "task_cards"} and len(task_cards["task_cards"]) == 5, "5 task cards", len(task_cards["task_cards"]), "Task cards JSON includes all requested copy-paste task cards."),
            _check("task_card_prompts_state_template_only", all("not standing authorization" in str(card["copy_paste_prompt"]).lower() for card in task_cards["task_cards"]), "template-only statement in every task card", "present", "Every generated task card states it is a template, not standing authorization."),
            _check("examples_markdown_contains_required_sections", all(section in examples for section in ("## Local CLI commands", "## Safe copy/paste snippets", "## Expected deterministic summaries", "## Disclaimers")), "all examples sections", "present", "Examples Markdown includes required sections."),
            _check("examples_markdown_contains_disclaimers", all(line in examples for line in DISCLAIMER_LINES), "all disclaimers", "present", "Examples Markdown contains all required disclaimers."),
            _check("deterministic_double_run_equality", _artifact_contents(first) == _artifact_contents(second), "equal", "equal" if _artifact_contents(first) == _artifact_contents(second) else "different", "P370 generated rows and artifacts are deterministic across two runs."),
        )
    )
    generated_text = "\n".join(
        (
            _json_text(transcripts),
            _csv_text(RECIPE_RESULT_COLUMNS, recipe_rows),
            _csv_text(PROMPT_SAFETY_COLUMNS, audit_rows),
            _json_text(task_cards),
            examples,
        )
    ).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in generated_text]
    rows.append(
        _check(
            "generated_artifacts_do_not_authorize_forbidden_actions",
            not found,
            "absent",
            ";".join(found) if found else "absent",
            "Generated P370 artifacts do not authorize DB writes, adapter execution, scoring, deploy, force operations, status changes, betting advice, or future prediction claims.",
        )
    )
    return tuple(rows)


def _run_consumer_without_validation(repo_root: Path | None = None) -> ConsumerOutput:
    transcripts = build_transcripts(repo_root)
    recipe_rows = run_query_recipes(repo_root)
    prompt_safety_rows = build_prompt_safety_audit(repo_root)
    task_cards = build_task_cards(repo_root)
    examples = render_examples(repo_root)
    placeholder = ConsumerOutput(transcripts, recipe_rows, prompt_safety_rows, task_cards, examples, (), ())
    manifest_rows = build_manifest_rows(_artifact_contents_without_manifest(placeholder), repo_root)
    return ConsumerOutput(transcripts, recipe_rows, prompt_safety_rows, task_cards, examples, manifest_rows, ())


def run_consumer(repo_root: Path | None = None) -> ConsumerOutput:
    partial = _run_consumer_without_validation(repo_root)
    validation_rows = validate_consumer(repo_root)
    return ConsumerOutput(
        partial.transcripts,
        partial.recipe_rows,
        partial.prompt_safety_rows,
        partial.task_cards,
        partial.examples_md,
        partial.manifest_rows,
        validation_rows,
    )


def _assert_deterministic(first: ConsumerOutput, second: ConsumerOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P370 consumer artifacts are not reproducible")


def write_artifacts(output: ConsumerOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P370_ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        if path.suffix == ".csv":
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(contents[key])
        else:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(contents[key])
    return paths


def _print_json(payload: object) -> None:
    print(_json_text(payload), end="")


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    parser.add_argument("--generate", action="store_true", help="write all P370 artifacts")
    parser.add_argument("--run-recipes", action="store_true", help="emit safe P369 query recipe execution results CSV")
    parser.add_argument("--transcripts", action="store_true", help="emit deterministic transcript examples JSON")
    parser.add_argument("--prompt-safety-audit", action="store_true", help="emit prompt/template safety audit CSV")
    parser.add_argument("--task-cards", action="store_true", help="emit copy-paste safe task cards JSON")
    parser.add_argument("--examples", action="store_true", help="emit examples Markdown")
    parser.add_argument("--manifest", action="store_true", help="emit manifest CSV")
    parser.add_argument("--validate", action="store_true", help="emit P370 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.run_recipes:
        _print_csv(RECIPE_RESULT_COLUMNS, run_query_recipes())
    elif args.transcripts:
        _print_json(build_transcripts())
    elif args.prompt_safety_audit:
        _print_csv(PROMPT_SAFETY_COLUMNS, build_prompt_safety_audit())
    elif args.task_cards:
        _print_json(build_task_cards())
    elif args.examples:
        print(render_examples(), end="")
    elif args.manifest:
        output = run_consumer()
        _print_csv(MANIFEST_COLUMNS, output.manifest_rows)
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_consumer())
    else:
        first = run_consumer()
        second = run_consumer()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P370 Big Lotto no-DB agent pack consumer: determinism double-run PASS")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring cohort was created; no deploy was performed.")
        print("Generated prompts are templates, not standing authorization.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
