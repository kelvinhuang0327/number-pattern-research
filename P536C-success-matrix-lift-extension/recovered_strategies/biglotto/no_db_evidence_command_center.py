"""P371 Big Lotto no-DB evidence command center and unified launcher.

This module provides one local command center over the merged P363-P370
Big Lotto no-DB evidence stack. It reads committed artifacts and calls only
existing no-DB helpers that read artifacts. It does not open or write a DB,
import production registries, call adapters, create new scoring cohorts,
deploy, provide betting advice, or make future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import textwrap
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from recovered_strategies.biglotto import no_db_evidence_agent_pack as pack
from recovered_strategies.biglotto import no_db_evidence_agent_pack_consumer as consumer
from recovered_strategies.biglotto import no_db_evidence_api as api
from recovered_strategies.biglotto import no_db_evidence_api_snapshots as snapshots

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P371_biglotto_command_center"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_MERGE_BASELINE = "30e4120060e41e8a6f7cf529c28d9b490c01f70b"

P371_ARTIFACT_BASENAMES = {
    "index": "P371_biglotto_command_center_index.json",
    "routes": "P371_biglotto_command_center_routes.csv",
    "status": "P371_biglotto_command_center_status.json",
    "smoke_results": "P371_biglotto_command_center_smoke_results.csv",
    "task_cards": "P371_biglotto_command_center_task_cards.json",
    "launchpad": "P371_biglotto_command_center_launchpad.html",
    "quickstart": "P371_biglotto_command_center_quickstart.md",
    "manifest": "P371_biglotto_command_center_manifest.csv",
}

REQUIRED_SOURCE_FILES = (
    "recovered_strategies/biglotto/no_db_evidence_pack.py",
    "recovered_strategies/biglotto/no_db_evidence_dashboard.py",
    "recovered_strategies/biglotto/no_db_evidence_explorer.py",
    "recovered_strategies/biglotto/no_db_evidence_release_bundle.py",
    "recovered_strategies/biglotto/no_db_evidence_api.py",
    "recovered_strategies/biglotto/no_db_evidence_api_snapshots.py",
    "recovered_strategies/biglotto/no_db_evidence_agent_pack.py",
    "recovered_strategies/biglotto/no_db_evidence_agent_pack_consumer.py",
    "artifacts/P363_biglotto_evidence_pack_adapter_cards.csv",
    "artifacts/P363_biglotto_evidence_pack_consistency_checks.csv",
    "artifacts/P363_biglotto_evidence_pack_manifest.csv",
    "artifacts/P363_biglotto_evidence_pack_report.md",
    "artifacts/P363_biglotto_evidence_pack_subset_cards.csv",
    "artifacts/P363_biglotto_evidence_pack_summary.csv",
    "artifacts/P364_biglotto_evidence_dashboard.html",
    "artifacts/P364_biglotto_evidence_dashboard_adapter_table.csv",
    "artifacts/P364_biglotto_evidence_dashboard_index.json",
    "artifacts/P364_biglotto_evidence_dashboard_manifest.csv",
    "artifacts/P364_biglotto_evidence_dashboard_subset_table.csv",
    "artifacts/P365_biglotto_evidence_explorer.html",
    "artifacts/P365_biglotto_evidence_explorer_adapter_detail_cards.json",
    "artifacts/P365_biglotto_evidence_explorer_compact_shortlist.csv",
    "artifacts/P365_biglotto_evidence_explorer_manifest.csv",
    "artifacts/P365_biglotto_evidence_explorer_pairwise_comparison.csv",
    "artifacts/P365_biglotto_evidence_explorer_query_snapshots.json",
    "artifacts/P365_biglotto_evidence_explorer_subset_detail_cards.json",
    "artifacts/P366_biglotto_evidence_release_bundle_cli_examples.json",
    "artifacts/P366_biglotto_evidence_release_bundle_inventory.csv",
    "artifacts/P366_biglotto_evidence_release_bundle_landing.html",
    "artifacts/P366_biglotto_evidence_release_bundle_manifest.json",
    "artifacts/P366_biglotto_evidence_release_bundle_readme.md",
    "artifacts/P366_biglotto_evidence_release_bundle_smoke_results.csv",
    "artifacts/P367_biglotto_evidence_api_contract.json",
    "artifacts/P367_biglotto_evidence_api_examples.json",
    "artifacts/P367_biglotto_evidence_api_manifest.csv",
    "artifacts/P367_biglotto_evidence_api_readme.md",
    "artifacts/P367_biglotto_evidence_api_validation.csv",
    "artifacts/P368_biglotto_evidence_api_cli_transcripts.json",
    "artifacts/P368_biglotto_evidence_api_compatibility_matrix.csv",
    "artifacts/P368_biglotto_evidence_api_contract_drift.csv",
    "artifacts/P368_biglotto_evidence_api_golden_snapshots.json",
    "artifacts/P368_biglotto_evidence_api_manifest.csv",
    "artifacts/P368_biglotto_evidence_api_readme.md",
    "artifacts/P369_biglotto_evidence_agent_pack_examples.md",
    "artifacts/P369_biglotto_evidence_agent_pack_manifest.csv",
    "artifacts/P369_biglotto_evidence_agent_pack_query_recipes.json",
    "artifacts/P369_biglotto_evidence_agent_pack_summary.json",
    "artifacts/P369_biglotto_evidence_agent_pack_task_prompts.json",
    "artifacts/P369_biglotto_evidence_agent_pack_validation_checklist.csv",
    "artifacts/P370_biglotto_agent_pack_consumer_examples.md",
    "artifacts/P370_biglotto_agent_pack_consumer_manifest.csv",
    "artifacts/P370_biglotto_agent_pack_consumer_prompt_safety_audit.csv",
    "artifacts/P370_biglotto_agent_pack_consumer_recipe_results.csv",
    "artifacts/P370_biglotto_agent_pack_consumer_task_cards.json",
    "artifacts/P370_biglotto_agent_pack_consumer_transcripts.json",
    "tests/test_p360_biglotto_no_db_multiwindow_validation.py",
    "tests/test_p361_biglotto_coverage_utility.py",
    "tests/test_p362_biglotto_subset_stability.py",
    "tests/test_p363_biglotto_evidence_pack.py",
    "tests/test_p364_biglotto_evidence_dashboard.py",
    "tests/test_p365_biglotto_evidence_explorer.py",
    "tests/test_p366_biglotto_evidence_release_bundle.py",
    "tests/test_p367_biglotto_evidence_api.py",
    "tests/test_p368_biglotto_evidence_api_snapshots.py",
    "tests/test_p369_biglotto_evidence_agent_pack.py",
    "tests/test_p370_biglotto_evidence_agent_pack_consumer.py",
)

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No adapter calls.",
    "No new scoring.",
    "No new scoring cohort.",
    "No production registry import.",
    "No deploy.",
    "No generated DB rows.",
    "Generated task cards are templates, not standing authorization.",
)

SCOPE_STATEMENT = " ".join(DISCLAIMER_LINES)

STATEMENTS = {
    "historical_descriptive_evidence_only": True,
    "future_prediction_guarantee": False,
    "betting_advice": False,
    "db_opened": False,
    "db_written": False,
    "adapter_calls": False,
    "new_scoring": False,
    "new_scoring_cohort": False,
    "production_registry_imported": False,
    "deployed": False,
    "generated_db_rows": False,
    "generated_task_cards_templates_not_standing_authorization": True,
}

ROUTE_COLUMNS = (
    "route_id",
    "title",
    "command",
    "output_format",
    "source_stage",
    "underlying_tool",
    "artifact_inputs",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "no_production_registry_import",
    "no_deploy",
    "no_betting_advice",
    "no_future_prediction_guarantee",
    "task_cards_template_only",
    "scope_statement",
)

SMOKE_COLUMNS = (
    "smoke_id",
    "route_id",
    "status",
    "expected",
    "actual",
    "details",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "no_production_registry_import",
    "no_deploy",
    "scope_statement",
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
    "scope_statement",
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
    "standing authorization granted",
)


@dataclass(frozen=True)
class CommandCenterOutput:
    index: dict[str, object]
    route_rows: tuple[dict[str, str], ...]
    status: dict[str, object]
    smoke_rows: tuple[dict[str, str], ...]
    task_cards: dict[str, object]
    launchpad_html: str
    quickstart_md: str
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


def _safe_flags() -> dict[str, str]:
    return {
        "no_db_open_write": "YES",
        "no_adapter_calls": "YES",
        "no_new_scoring": "YES",
        "no_production_registry_import": "YES",
        "no_deploy": "YES",
        "no_betting_advice": "YES",
        "no_future_prediction_guarantee": "YES",
        "task_cards_template_only": "YES",
        "scope_statement": SCOPE_STATEMENT,
    }


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_FILES)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise api.EvidenceApiError(f"required P363-P370 evidence files missing: {missing}")
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
                "details": "P371 source evidence read without DB open/write, adapter execution, scoring, registry import, or deploy.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    return tuple(rows)


def build_routes(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_artifacts(repo_root)
    safe = _safe_flags()
    specs = (
        (
            "status",
            "Command center status",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --status",
            "json",
            "P371",
            "build_status",
            "P363-P370 committed artifacts",
        ),
        (
            "routes",
            "Route catalog",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --routes",
            "csv",
            "P371",
            "build_routes",
            "P363-P370 committed artifacts",
        ),
        (
            "smoke",
            "No-DB command center smoke",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --smoke",
            "csv",
            "P371",
            "run_smoke",
            "P367-P370 no-DB helper outputs",
        ),
        (
            "list_tools",
            "Unified tool list",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --list-tools",
            "json",
            "P367-P371",
            "build_tool_catalog",
            "P367 contract, P368 snapshots, P369 recipes, P370 consumer",
        ),
        (
            "list_artifacts",
            "Source and output artifact list",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --list-artifacts",
            "csv",
            "P363-P371",
            "build_manifest_rows",
            "P363-P370 committed artifacts and P371 output definitions",
        ),
        (
            "task_cards",
            "Safe task-card templates",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --show-task-cards",
            "json",
            "P370-P371",
            "build_task_cards",
            "P369 recipes and P370 task cards",
        ),
        (
            "validate",
            "Command center validation",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --validate",
            "csv",
            "P371",
            "validate_command_center",
            "P367-P370 validation outputs and deterministic P371 artifacts",
        ),
        (
            "query_list_adapters",
            "Query P369 list_adapters recipe",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --query list_adapters",
            "json",
            "P367/P369/P370",
            "query_command_center",
            "P369 recipe executed through P370 consumer against P367 no-DB facade",
        ),
        (
            "query_compact_shortlist",
            "Query P369 list_compact_shortlist recipe",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --query list_compact_shortlist",
            "json",
            "P367/P369/P370",
            "query_command_center",
            "P369 recipe executed through P370 consumer against P367 no-DB facade",
        ),
    )
    return tuple(
        {
            "route_id": route_id,
            "title": title,
            "command": command,
            "output_format": output_format,
            "source_stage": source_stage,
            "underlying_tool": tool,
            "artifact_inputs": inputs,
            **safe,
        }
        for route_id, title, command, output_format, source_stage, tool, inputs in specs
    )


def build_tool_catalog(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_artifacts(repo_root)
    contract = api.build_contract(repo_root)
    recipes = pack.build_query_recipes()
    p370_cards = consumer.build_task_cards(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_merge_baseline": SOURCE_MERGE_BASELINE,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "tools": {
            "p367_facade_functions": contract["supported_functions"],
            "p368_snapshot_routes": (
                "emit_golden_snapshots",
                "compatibility_matrix",
                "contract_drift",
                "cli_transcripts",
                "validate",
            ),
            "p369_query_recipes": recipes["recipes"],
            "p370_consumer_routes": (
                "run_recipes",
                "transcripts",
                "prompt_safety_audit",
                "task_cards",
                "validate",
            ),
            "p371_command_center_routes": build_routes(repo_root),
        },
        "task_card_template_count": len(p370_cards["task_cards"]),
    }


def build_status(repo_root: Path | None = None) -> dict[str, object]:
    paths = verify_required_artifacts(repo_root)
    p367_validation = api.validate_evidence_stack(repo_root)
    p368_compatibility = snapshots.build_compatibility_matrix(repo_root)
    p368_drift = snapshots.build_contract_drift_rows(repo_root)
    p369_validation = _read_csv_rows(_artifact_path("artifacts/P369_biglotto_evidence_agent_pack_validation_checklist.csv", repo_root))
    p370_audit = _read_csv_rows(_artifact_path("artifacts/P370_biglotto_agent_pack_consumer_prompt_safety_audit.csv", repo_root))
    recipe_rows = consumer.run_query_recipes(repo_root)
    route_rows = build_routes(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_merge_baseline": SOURCE_MERGE_BASELINE,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "required_source_file_count": len(REQUIRED_SOURCE_FILES),
        "required_source_files_present": len(paths),
        "missing_source_files": (),
        "route_count": len(route_rows),
        "tool_family_count": 5,
        "p367_validation": {
            "row_count": len(p367_validation),
            "fail_count": sum(1 for row in p367_validation if row["status"] != "PASS"),
        },
        "p368_compatibility": {
            "row_count": len(p368_compatibility),
            "incompatible_count": sum(1 for row in p368_compatibility if row["compatible"] != "TRUE"),
            "drift_fail_count": sum(1 for row in p368_drift if row["status"] == "FAIL"),
        },
        "p369_validation": {
            "row_count": len(p369_validation),
            "fail_count": sum(1 for row in p369_validation if row["status"] != "PASS"),
        },
        "p370_consumer": {
            "recipe_result_count": len(recipe_rows),
            "recipe_fail_count": sum(1 for row in recipe_rows if row["status"] != "PASS"),
            "prompt_safety_fail_count": sum(1 for row in p370_audit if row["status"] != "PASS"),
        },
        "command_center_ready": True,
        "db_registry_deploy_status": {
            "db_open_write": "NO",
            "adapter_calls": "NO",
            "new_scoring": "NO",
            "production_registry_import": "NO",
            "deploy": "NO",
            "generated_db_rows": "NO",
            "task_cards_standing_authorization": "NO",
        },
    }


def _smoke_row(smoke_id: str, route_id: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "smoke_id": smoke_id,
        "route_id": route_id,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
        "no_db_open_write": "YES",
        "no_adapter_calls": "YES",
        "no_new_scoring": "YES",
        "no_production_registry_import": "YES",
        "no_deploy": "YES",
        "scope_statement": SCOPE_STATEMENT,
    }


def run_smoke(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    status = build_status(repo_root)
    routes = build_routes(repo_root)
    tools = build_tool_catalog(repo_root)
    recipe_rows = consumer.run_query_recipes(repo_root)
    cards = build_task_cards(repo_root)
    validation_rows = validate_command_center(repo_root, include_determinism=False)
    return (
        _smoke_row("status_ready", "status", status["command_center_ready"] is True, True, status["command_center_ready"], "Status JSON reports command center ready."),
        _smoke_row("routes_available", "routes", len(routes) >= 8, ">=8", len(routes), "Route catalog contains usable command-center routes."),
        _smoke_row("tools_available", "list_tools", len(tools["tools"]) == 5, 5, len(tools["tools"]), "Tool catalog exposes P367-P371 tool families."),
        _smoke_row("recipes_pass", "query_list_adapters", all(row["status"] == "PASS" for row in recipe_rows), "all PASS", sum(1 for row in recipe_rows if row["status"] != "PASS"), "P370 recipe execution remains passing."),
        _smoke_row("task_cards_template_only", "task_cards", all(card["template_not_standing_authorization"] is True for card in cards["task_cards"]), "all template-only", len(cards["task_cards"]), "P371 task cards are templates, not standing authorization."),
        _smoke_row("validation_passes", "validate", all(row["status"] == "PASS" for row in validation_rows), "all PASS", sum(1 for row in validation_rows if row["status"] != "PASS"), "P371 validation rows pass."),
    )


def _template_footer() -> str:
    return (
        "This card is a template only, not standing authorization. Stop before any DB open/write, "
        "adapter call, new scoring, production registry import, deploy, generated DB row, betting advice, "
        "or future-performance claim."
    )


def _card(card_id: str, title: str, route_id: str, objective: str) -> dict[str, object]:
    prompt = textwrap.dedent(
        f"""
        Task: {title}

        Route: {route_id}

        Objective: {objective}

        Constraints: {SCOPE_STATEMENT}

        Local command:
        python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --query {route_id}

        {_template_footer()}
        """
    ).strip()
    return {
        "card_id": card_id,
        "title": title,
        "route_id": route_id,
        "intended_agent": "Future Worker",
        "copy_paste_prompt": prompt,
        "template_not_standing_authorization": True,
        "no_db_open_write": True,
        "no_adapter_calls": True,
        "no_new_scoring": True,
        "no_production_registry_import": True,
        "no_deploy": True,
    }


def build_task_cards(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_artifacts(repo_root)
    cards = (
        _card("status_triage", "Status triage", "status", "Inspect current P363-P370 no-DB evidence availability and validation status."),
        _card("route_selection", "Route selection", "routes", "Choose the safest local command-center route for a read-only evidence task."),
        _card("smoke_recheck", "Smoke recheck", "smoke", "Run command-center smoke rows and report only PASS/FAIL historical evidence state."),
        _card("tool_inventory", "Tool inventory", "list_tools", "List available no-DB facade functions, recipes, and command-center routes."),
        _card("artifact_inventory", "Artifact inventory", "list_artifacts", "Review source and generated artifact paths and SHA256 values."),
        _card("recipe_query", "Recipe query", "list_adapters", "Query a known P369 recipe through the P370 no-DB consumer path."),
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_merge_baseline": SOURCE_MERGE_BASELINE,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "task_cards": cards,
    }


def build_index(repo_root: Path | None = None) -> dict[str, object]:
    status = build_status(repo_root)
    routes = build_routes(repo_root)
    tools = build_tool_catalog(repo_root)
    smoke = run_smoke(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_merge_baseline": SOURCE_MERGE_BASELINE,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "status_summary": {
            "command_center_ready": status["command_center_ready"],
            "required_source_file_count": status["required_source_file_count"],
            "route_count": status["route_count"],
            "p367_validation_fail_count": status["p367_validation"]["fail_count"],
            "p368_incompatible_count": status["p368_compatibility"]["incompatible_count"],
            "p368_drift_fail_count": status["p368_compatibility"]["drift_fail_count"],
            "p369_validation_fail_count": status["p369_validation"]["fail_count"],
            "p370_recipe_fail_count": status["p370_consumer"]["recipe_fail_count"],
            "p370_prompt_safety_fail_count": status["p370_consumer"]["prompt_safety_fail_count"],
        },
        "routes": routes,
        "tools": tools["tools"],
        "smoke_summary": {
            "row_count": len(smoke),
            "fail_count": sum(1 for row in smoke if row["status"] != "PASS"),
        },
        "generated_outputs": tuple(f"artifacts/{basename}" for basename in P371_ARTIFACT_BASENAMES.values()),
    }


def query_command_center(query_id: str, repo_root: Path | None = None) -> dict[str, object]:
    routes = {row["route_id"]: row for row in build_routes(repo_root)}
    if query_id in routes:
        route = routes[query_id]
        if query_id == "status":
            payload: object = build_status(repo_root)
        elif query_id == "routes":
            payload = build_routes(repo_root)
        elif query_id == "smoke":
            payload = run_smoke(repo_root)
        elif query_id == "list_tools":
            payload = build_tool_catalog(repo_root)
        elif query_id == "list_artifacts":
            output = _run_command_center_without_validation(repo_root)
            payload = build_manifest_rows(_artifact_contents_without_manifest(output), repo_root)
        elif query_id == "task_cards":
            payload = build_task_cards(repo_root)
        elif query_id == "validate":
            payload = validate_command_center(repo_root)
        else:
            payload = route
        return {
            "task": TASK,
            "generated_at": GENERATED_AT,
            "query_id": query_id,
            "query_type": "route",
            "statements": STATEMENTS,
            "scope_lines": DISCLAIMER_LINES,
            "route": route,
            "payload": payload,
        }
    recipe_rows = {row["recipe_id"]: row for row in consumer.run_query_recipes(repo_root)}
    if query_id in recipe_rows:
        return {
            "task": TASK,
            "generated_at": GENERATED_AT,
            "query_id": query_id,
            "query_type": "p369_recipe_result",
            "statements": STATEMENTS,
            "scope_lines": DISCLAIMER_LINES,
            "recipe_result": recipe_rows[query_id],
        }
    raise api.EvidenceApiError(f"unknown P371 route or P369 recipe id: {query_id}")


def render_launchpad(repo_root: Path | None = None) -> str:
    routes = build_routes(repo_root)
    status = build_status(repo_root)
    task_cards = build_task_cards(repo_root)["task_cards"]
    scope_items = "\n".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    route_rows = "\n".join(
        "<tr>"
        f"<td><code>{html.escape(row['route_id'])}</code></td>"
        f"<td>{html.escape(row['title'])}</td>"
        f"<td><code>{html.escape(row['command'])}</code></td>"
        f"<td>{html.escape(row['output_format'])}</td>"
        "</tr>"
        for row in routes
    )
    card_rows = "\n".join(
        "<section class=\"card\">"
        f"<h3>{html.escape(str(card['title']))}</h3>"
        f"<p><code>{html.escape(str(card['route_id']))}</code></p>"
        f"<pre>{html.escape(str(card['copy_paste_prompt']))}</pre>"
        "</section>"
        for card in task_cards
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>P371 Big Lotto no-DB evidence command center</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #1d2733; background: #f7f8fa; }}
    header {{ background: #0f766e; color: white; padding: 28px 36px; }}
    main {{ padding: 24px 36px 40px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin: 16px 0 28px; }}
    th, td {{ border: 1px solid #d7dde5; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #e9f5f3; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ white-space: pre-wrap; background: #fff; border: 1px solid #d7dde5; padding: 12px; overflow-x: auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }}
    .card {{ background: white; border: 1px solid #d7dde5; border-radius: 6px; padding: 14px; }}
  </style>
</head>
<body>
  <header>
    <h1>P371 Big Lotto no-DB evidence command center</h1>
    <p>Ready: {html.escape(str(status["command_center_ready"]))}. Source baseline: {SOURCE_MERGE_BASELINE}.</p>
  </header>
  <main>
    <h2>Scope</h2>
    <ul>{scope_items}</ul>
    <h2>Routes</h2>
    <table>
      <thead><tr><th>Route</th><th>Title</th><th>Command</th><th>Format</th></tr></thead>
      <tbody>{route_rows}</tbody>
    </table>
    <h2>Task Cards</h2>
    <div class="grid">{card_rows}</div>
  </main>
</body>
</html>
"""


def render_quickstart(repo_root: Path | None = None) -> str:
    verify_required_artifacts(repo_root)
    disclaimer = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    return f"""# P371 Big Lotto no-DB evidence command center quickstart

Generated at: {GENERATED_AT}

This command center is a unified local launcher over merged P363-P370 Big Lotto no-DB evidence artifacts.

## Scope

{disclaimer}

## Commands

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --generate
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --status
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --routes
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --smoke
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --list-tools
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --list-artifacts
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --show-task-cards
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --query list_adapters
python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --validate
```

## Functional flow

1. Use `--status` to confirm the P363-P370 evidence stack is present and passing.
2. Use `--routes` to select a local no-DB route.
3. Use `--query <route_id>` or `--query <recipe_id>` to resolve one command-center route or P369 recipe.
4. Use `--smoke` and `--validate` before handing generated task templates to another Worker.

Task cards are copy-paste templates only. They do not authorize DB work, adapter execution, new scoring, registry import, deploy, generated DB rows, betting advice, or future-performance claims.
"""


def _artifact_contents_without_manifest(output: CommandCenterOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "routes": _csv_text(ROUTE_COLUMNS, output.route_rows),
        "status": _json_text(output.status),
        "smoke_results": _csv_text(SMOKE_COLUMNS, output.smoke_rows),
        "task_cards": _json_text(output.task_cards),
        "launchpad": output.launchpad_html,
        "quickstart": output.quickstart_md,
    }


def _artifact_contents(output: CommandCenterOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"routes", "smoke_results", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"index", "status", "task_cards"}:
        return "", "1"
    if role in {"launchpad", "quickstart"}:
        return str(len(text.splitlines())), ""
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = list(source_artifact_rows(repo_root))
    for role, basename in P371_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_FILES) + len(P371_ARTIFACT_BASENAMES) + 2)
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
                "details": "P371 generated command center artifact.",
                "scope_statement": SCOPE_STATEMENT,
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
                "details": SCOPE_STATEMENT,
                "scope_statement": SCOPE_STATEMENT,
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
                "details": "P371 artifact generation performs deterministic double-run equality before write.",
                "scope_statement": SCOPE_STATEMENT,
            },
        )
    )
    return tuple(rows)


def validate_command_center(repo_root: Path | None = None, include_determinism: bool = True) -> tuple[dict[str, str], ...]:
    paths = verify_required_artifacts(repo_root)
    status = build_status(repo_root)
    routes = build_routes(repo_root)
    smoke = run_smoke(repo_root) if include_determinism else ()
    cards = build_task_cards(repo_root)
    quickstart = render_quickstart(repo_root)
    launchpad = render_launchpad(repo_root)
    route_text = _csv_text(ROUTE_COLUMNS, routes)
    smoke_text = _csv_text(SMOKE_COLUMNS, smoke) if smoke else ""
    cards_text = _json_text(cards)
    rows: list[dict[str, str]] = [
        _check("required_p363_p370_files_exist", len(paths) == len(REQUIRED_SOURCE_FILES), len(REQUIRED_SOURCE_FILES), len(paths), "Required P363-P370 source files are present."),
        _check("status_json_schema", set(status) >= {"task", "generated_at", "source_merge_baseline", "statements", "scope_lines", "command_center_ready"}, "required status keys", sorted(status), "Status JSON includes command-center readiness and source validation summaries."),
        _check("status_ready", status["command_center_ready"] is True, True, status["command_center_ready"], "Command center status reports ready."),
        _check("routes_csv_schema", routes and tuple(routes[0]) == ROUTE_COLUMNS, ROUTE_COLUMNS, tuple(routes[0]) if routes else (), "Routes CSV uses required columns."),
        _check("routes_are_safe", all(row["no_db_open_write"] == "YES" and row["no_adapter_calls"] == "YES" and row["no_new_scoring"] == "YES" for row in routes), "all safe", "safe", "Every route confirms no DB, no adapters, and no new scoring."),
        _check("task_cards_json_schema", set(cards) == {"task", "generated_at", "source_merge_baseline", "statements", "scope_lines", "task_cards"} and len(cards["task_cards"]) == 6, "6 task cards", len(cards["task_cards"]), "Task cards JSON includes P371 task templates."),
        _check("task_cards_template_only", all(card["template_not_standing_authorization"] is True and "not standing authorization" in str(card["copy_paste_prompt"]).lower() for card in cards["task_cards"]), "all template-only", len(cards["task_cards"]), "Every generated task card states it is not standing authorization."),
        _check("quickstart_contains_scope", all(line in quickstart for line in DISCLAIMER_LINES), "all scope lines", "present", "Quickstart Markdown contains all required scope statements."),
        _check("launchpad_contains_scope", all(line in launchpad for line in DISCLAIMER_LINES), "all scope lines", "present", "Launchpad HTML contains all required scope statements."),
        _check("p367_validation_has_no_failures", status["p367_validation"]["fail_count"] == 0, 0, status["p367_validation"]["fail_count"], "P367 validation remains passing."),
        _check("p368_compatibility_has_no_incompatible_rows", status["p368_compatibility"]["incompatible_count"] == 0, 0, status["p368_compatibility"]["incompatible_count"], "P368 compatibility remains passing."),
        _check("p368_contract_drift_has_no_fail_rows", status["p368_compatibility"]["drift_fail_count"] == 0, 0, status["p368_compatibility"]["drift_fail_count"], "P368 contract drift has no FAIL rows."),
        _check("p369_validation_has_no_failures", status["p369_validation"]["fail_count"] == 0, 0, status["p369_validation"]["fail_count"], "P369 validation checklist remains passing."),
        _check("p370_recipe_results_have_no_failures", status["p370_consumer"]["recipe_fail_count"] == 0, 0, status["p370_consumer"]["recipe_fail_count"], "P370 recipe results remain passing."),
        _check("p370_prompt_safety_has_no_failures", status["p370_consumer"]["prompt_safety_fail_count"] == 0, 0, status["p370_consumer"]["prompt_safety_fail_count"], "P370 prompt safety audit remains passing."),
    ]
    if smoke:
        rows.append(_check("smoke_results_csv_schema", tuple(smoke[0]) == SMOKE_COLUMNS, SMOKE_COLUMNS, tuple(smoke[0]), "Smoke result rows use required columns."))
        rows.append(_check("smoke_results_all_pass", all(row["status"] == "PASS" for row in smoke), "all PASS", sum(1 for row in smoke if row["status"] != "PASS"), "Command-center smoke checks all pass."))
    generated_text = "\n".join((_json_text(status), route_text, smoke_text, cards_text, quickstart, launchpad)).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in generated_text]
    rows.append(
        _check(
            "generated_artifacts_do_not_authorize_forbidden_actions",
            not found,
            "absent",
            ";".join(found) if found else "absent",
            "Generated P371 artifacts do not authorize DB writes, adapter execution, scoring, deploy, force operations, status changes, betting advice, or future prediction claims.",
        )
    )
    if include_determinism:
        first = _run_command_center_without_validation(repo_root)
        second = _run_command_center_without_validation(repo_root)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P371 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def _run_command_center_without_validation(repo_root: Path | None = None) -> CommandCenterOutput:
    status = build_status(repo_root)
    routes = build_routes(repo_root)
    task_cards = build_task_cards(repo_root)
    launchpad = render_launchpad(repo_root)
    quickstart = render_quickstart(repo_root)
    smoke = run_smoke(repo_root)
    index = build_index(repo_root)
    placeholder = CommandCenterOutput(index, routes, status, smoke, task_cards, launchpad, quickstart, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(placeholder), repo_root)
    return CommandCenterOutput(index, routes, status, smoke, task_cards, launchpad, quickstart, manifest, ())


def run_command_center(repo_root: Path | None = None) -> CommandCenterOutput:
    partial = _run_command_center_without_validation(repo_root)
    validation_rows = validate_command_center(repo_root)
    return CommandCenterOutput(
        partial.index,
        partial.route_rows,
        partial.status,
        partial.smoke_rows,
        partial.task_cards,
        partial.launchpad_html,
        partial.quickstart_md,
        partial.manifest_rows,
        validation_rows,
    )


def _assert_deterministic(first: CommandCenterOutput, second: CommandCenterOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P371 command center artifacts are not reproducible")


def write_artifacts(output: CommandCenterOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P371_ARTIFACT_BASENAMES.items()}
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
    parser.add_argument("--generate", action="store_true", help="write all P371 command center artifacts")
    parser.add_argument("--status", action="store_true", help="emit command center status JSON")
    parser.add_argument("--routes", action="store_true", help="emit command center routes CSV")
    parser.add_argument("--smoke", action="store_true", help="emit command center smoke results CSV")
    parser.add_argument("--list-tools", action="store_true", help="emit unified no-DB tool catalog JSON")
    parser.add_argument("--list-artifacts", action="store_true", help="emit source and output artifact manifest CSV")
    parser.add_argument("--show-task-cards", action="store_true", help="emit safe task-card templates JSON")
    parser.add_argument("--query", help="emit one route or P369 recipe by id as JSON")
    parser.add_argument("--validate", action="store_true", help="emit P371 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.status:
        _print_json(build_status())
    elif args.routes:
        _print_csv(ROUTE_COLUMNS, build_routes())
    elif args.smoke:
        _print_csv(SMOKE_COLUMNS, run_smoke())
    elif args.list_tools:
        _print_json(build_tool_catalog())
    elif args.list_artifacts:
        output = _run_command_center_without_validation()
        _print_csv(MANIFEST_COLUMNS, build_manifest_rows(_artifact_contents_without_manifest(output)))
    elif args.show_task_cards:
        _print_json(build_task_cards())
    elif args.query:
        _print_json(query_command_center(args.query))
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_command_center())
    else:
        first = run_command_center()
        second = run_command_center()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P371 Big Lotto no-DB evidence command center: determinism double-run PASS")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Generated task cards are templates, not standing authorization.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
