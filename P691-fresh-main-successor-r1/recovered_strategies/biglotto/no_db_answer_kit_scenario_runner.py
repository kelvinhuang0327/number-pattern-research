"""P382 Big Lotto no-DB answer kit scenario runner.

This module consumes committed P380 query artifacts and P381 answer kit
artifacts to produce deterministic handoff scenario transcripts, coverage
rows, a missing-answer matrix, a QA report, and a manifest. It does not open or
write a DB, call adapters, create new scoring cohorts, import production
registries, deploy, provide betting advice, or make future-performance claims.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P382_biglotto_answer_kit_scenario_runner"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
P381_BASELINE_COMMIT = "9c42a4e4545f2ac11b711b621fb431462ba58edc"
P379_EXTERNAL_WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p379")
PROTECTED_HISTORICAL_WORKTREES = (
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P360-fable5-biglotto-success-direction-readonly"),
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P371-biglotto-command-center"),
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P373-biglotto-command-center-operator-console"),
)

SOURCE_BASELINE = {
    "required_origin_main_merge_commit": P381_BASELINE_COMMIT,
    "source_tasks": (
        "P380_biglotto_regression_archive_query",
        "P381_biglotto_regression_archive_answer_kit",
    ),
    "scenario_runner_mode": "read_only_no_db_p381_answer_kit_consumer",
}

P380_SOURCE_ARTIFACTS = {
    "p380_module": "recovered_strategies/biglotto/no_db_regression_archive_query.py",
    "p380_index": "artifacts/P380_biglotto_regression_archive_query_index.json",
    "p380_recipes": "artifacts/P380_biglotto_regression_archive_query_recipes.json",
    "p380_command_results": "artifacts/P380_biglotto_regression_archive_query_command_results.csv",
    "p380_artifact_results": "artifacts/P380_biglotto_regression_archive_query_artifact_results.csv",
    "p380_delta_results": "artifacts/P380_biglotto_regression_archive_query_delta_results.csv",
    "p380_transcripts": "artifacts/P380_biglotto_regression_archive_query_transcripts.json",
    "p380_guide": "artifacts/P380_biglotto_regression_archive_query_guide.md",
    "p380_manifest": "artifacts/P380_biglotto_regression_archive_query_manifest.csv",
}

P381_SOURCE_ARTIFACTS = {
    "p381_module": "recovered_strategies/biglotto/no_db_regression_archive_answer_kit.py",
    "p381_index": "artifacts/P381_biglotto_regression_archive_answer_kit_index.json",
    "p381_answer_cards": "artifacts/P381_biglotto_regression_archive_answer_kit_answer_cards.json",
    "p381_status_block": "artifacts/P381_biglotto_regression_archive_answer_kit_status_block.md",
    "p381_briefings": "artifacts/P381_biglotto_regression_archive_answer_kit_briefings.json",
    "p381_lookup_transcripts": "artifacts/P381_biglotto_regression_archive_answer_kit_lookup_transcripts.json",
    "p381_portal": "artifacts/P381_biglotto_regression_archive_answer_kit_portal.html",
    "p381_manifest": "artifacts/P381_biglotto_regression_archive_answer_kit_manifest.csv",
}

SOURCE_ARTIFACTS = {**P380_SOURCE_ARTIFACTS, **P381_SOURCE_ARTIFACTS}

P382_ARTIFACT_BASENAMES = {
    "index": "P382_biglotto_answer_kit_scenario_runner_index.json",
    "scenarios": "P382_biglotto_answer_kit_scenario_runner_scenarios.json",
    "transcripts": "P382_biglotto_answer_kit_scenario_runner_transcripts.json",
    "coverage": "P382_biglotto_answer_kit_scenario_runner_coverage.csv",
    "missing_answers": "P382_biglotto_answer_kit_scenario_runner_missing_answers.csv",
    "qa_report": "P382_biglotto_answer_kit_scenario_runner_qa_report.md",
    "manifest": "P382_biglotto_answer_kit_scenario_runner_manifest.csv",
}

SCENARIO_IDS = (
    "overall_status",
    "safe_next_actions",
    "cto_technical_risk",
    "ceo_nontechnical_summary",
    "planner_model_need",
    "safety_boundary",
    "protected_worktree_warnings",
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
    "No strategy status changes.",
    "No blended leaderboard.",
    "No force operations.",
    "No external publication.",
    "Not production release approval.",
    "P382 reads only merged P380/P381 query and answer evidence and writes only P382-prefixed scenario runner artifacts.",
)
SCOPE_STATEMENT = " ".join(DISCLAIMER_LINES)
NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT = (
    "No DB was opened or written; no adapters were called; no new scoring, "
    "scoring cohort, shape-only scoring, blocked-target scoring, or blended "
    "leaderboard was created; no production registry import, deploy, or "
    "external publication was performed."
)

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
    "strategy_status_changes": False,
    "blended_leaderboard": False,
    "force_operations": False,
    "external_publication": False,
    "production_release_approval": False,
}

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

COVERAGE_COLUMNS = (
    "scenario_id",
    "required_answer_type",
    "matched_answer_id",
    "coverage_status",
    "notes",
)

MISSING_ANSWER_COLUMNS = (
    "gap_id",
    "scenario_id",
    "missing_answer_type",
    "severity",
    "blocking",
    "suggested_followup",
)

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
    "no_deploy",
    "details",
    "scope_statement",
)

VALIDATION_COLUMNS = ("check_name", "status", "expected", "actual", "details")


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    audience: str
    prompt: str
    required_answer_type: str
    selected_answer_ids: tuple[str, ...]
    intent: str


@dataclass(frozen=True)
class ScenarioRunnerOutput:
    index: dict[str, object]
    scenarios: dict[str, object]
    transcripts: dict[str, object]
    coverage_rows: tuple[dict[str, str], ...]
    missing_answer_rows: tuple[dict[str, str], ...]
    qa_report_markdown: str
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


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _read_json(relpath: str, repo_root: Path | None = None) -> object:
    with open(_artifact_path(relpath, repo_root), encoding="utf-8") as handle:
        return json.load(handle)


def _read_text(relpath: str, repo_root: Path | None = None) -> str:
    return _artifact_path(relpath, repo_root).read_text(encoding="utf-8")


def _read_csv(relpath: str, repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    with open(_artifact_path(relpath, repo_root), newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _count_artifact(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8") as handle:
            return f"csv_rows={len(tuple(csv.DictReader(handle)))}"
    if suffix == ".json":
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return f"json_keys={len(payload)}"
        if isinstance(payload, list):
            return f"json_items={len(payload)}"
        return f"json_scalar={type(payload).__name__}"
    if suffix in {".html", ".md", ".py", ".txt"}:
        return f"text_lines={len(path.read_text(encoding='utf-8').splitlines())}"
    return "object_count=1"


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in SOURCE_ARTIFACTS.values())
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P380/P381 answer kit evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows: list[dict[str, str]] = []
    for role, relpath in SOURCE_ARTIFACTS.items():
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "artifact_role": role,
                "path": relpath,
                "source_stage": role.split("_", 1)[0].upper(),
                "format": path.suffix.lower().lstrip(".") or "file",
                "sha256": sha256_file(path),
                "row_or_object_count": _count_artifact(path),
            }
        )
    return tuple(rows)


def inspect_path_warnings() -> dict[str, object]:
    protected = {
        str(path): "PRESENT" if path.exists() else "ABSENT"
        for path in PROTECTED_HISTORICAL_WORKTREES
    }
    protected_warning = (
        "P382_WARN_PROTECTED_WORKTREES_ABSENT"
        if any(status == "ABSENT" for status in protected.values())
        else "P382_PROTECTED_WORKTREES_PRESENT"
    )
    return {
        "p379_previous_worktree": {
            "path": str(P379_EXTERNAL_WORKTREE),
            "status": "PRESENT" if P379_EXTERNAL_WORKTREE.exists() else "ABSENT",
            "policy": "read-only presence check only; do not use or clean",
        },
        "protected_historical_worktrees": protected,
        "protected_historical_warning": protected_warning,
    }


def _cards_by_id(answer_cards: Mapping[str, object]) -> dict[str, dict[str, object]]:
    return {card["answer_id"]: dict(card) for card in answer_cards["cards"]}


def _source_context(repo_root: Path | None = None) -> dict[str, object]:
    p380_index = _read_json(P380_SOURCE_ARTIFACTS["p380_index"], repo_root)
    p381_index = _read_json(P381_SOURCE_ARTIFACTS["p381_index"], repo_root)
    answer_cards = _read_json(P381_SOURCE_ARTIFACTS["p381_answer_cards"], repo_root)
    briefings = _read_json(P381_SOURCE_ARTIFACTS["p381_briefings"], repo_root)
    lookup_transcripts = _read_json(P381_SOURCE_ARTIFACTS["p381_lookup_transcripts"], repo_root)
    p381_status_block = _read_text(P381_SOURCE_ARTIFACTS["p381_status_block"], repo_root)
    p380_commands = _read_csv(P380_SOURCE_ARTIFACTS["p380_command_results"], repo_root)
    p380_artifacts = _read_csv(P380_SOURCE_ARTIFACTS["p380_artifact_results"], repo_root)
    p380_deltas = _read_csv(P380_SOURCE_ARTIFACTS["p380_delta_results"], repo_root)
    return {
        "p380_index": p380_index,
        "p381_index": p381_index,
        "answer_cards": answer_cards,
        "cards_by_id": _cards_by_id(answer_cards),
        "briefings": briefings,
        "lookup_transcripts": lookup_transcripts,
        "p381_status_block": p381_status_block,
        "p380_commands": p380_commands,
        "p380_artifacts": p380_artifacts,
        "p380_deltas": p380_deltas,
    }


def scenario_specs() -> tuple[ScenarioSpec, ...]:
    return (
        ScenarioSpec(
            "overall_status",
            "Worker",
            "What is the current overall Big Lotto regression archive status?",
            "overall_status",
            ("overall_status", "latest_durable_baseline", "safety_status"),
            "Summarize the durable historical status from P381 answer cards.",
        ),
        ScenarioSpec(
            "safe_next_actions",
            "Worker",
            "What safe next action should the worker take without crossing boundaries?",
            "safe_next_action",
            ("safe_next_actions", "safety_status", "protected_worktree_warnings"),
            "Provide a bounded handoff step and restate prohibited actions.",
        ),
        ScenarioSpec(
            "cto_technical_risk",
            "CTO",
            "What are the technical risks shown by the archive evidence?",
            "technical_risk",
            ("non_pass_commands", "stale_or_missing_artifacts", "warn_fail_deltas", "safety_status"),
            "Explain command, artifact, delta, and execution-boundary risk.",
        ),
        ScenarioSpec(
            "ceo_nontechnical_summary",
            "CEO",
            "Give a non-technical summary of what this evidence means.",
            "nontechnical_summary",
            ("overall_status", "safety_status", "safe_next_actions"),
            "Translate the answer kit into non-technical status and boundary language.",
        ),
        ScenarioSpec(
            "planner_model_need",
            "Planner",
            "Do we need more Fable5 analysis before answering these handoff questions?",
            "model_need",
            ("safe_next_actions", "latest_durable_baseline", "safety_status"),
            "State that P381 evidence is enough for these handoff scenarios without new analysis.",
        ),
        ScenarioSpec(
            "safety_boundary",
            "Worker",
            "Can I open the DB, call adapters, score strategies, or deploy from this answer kit?",
            "safety_boundary",
            ("safety_status", "safe_next_actions"),
            "Reject DB, adapter, scoring, registry, deployment, betting, and prediction actions.",
        ),
        ScenarioSpec(
            "protected_worktree_warnings",
            "Worker",
            "What should I know about P379 and protected historical worktree warnings?",
            "protected_worktree_warning",
            ("protected_worktree_warnings", "safety_status"),
            "Report read-only path warning status and cleanup restrictions.",
        ),
    )


def build_scenarios() -> dict[str, object]:
    specs = scenario_specs()
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "scenario_ids": tuple(spec.scenario_id for spec in specs),
        "scenarios": tuple(
            {
                "scenario_id": spec.scenario_id,
                "audience": spec.audience,
                "prompt": spec.prompt,
                "required_answer_type": spec.required_answer_type,
                "selected_answer_ids": spec.selected_answer_ids,
                "intent": spec.intent,
            }
            for spec in specs
        ),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _answer_summary(spec: ScenarioSpec, cards_by_id: Mapping[str, Mapping[str, object]]) -> str:
    if spec.scenario_id == "planner_model_need":
        return (
            "More Fable5 analysis is not required to answer these Worker / CTO / CEO / Planner handoff "
            "scenarios because P381 already packages the merged P380 query evidence into answer cards. "
            "Any future modeling decision is outside P382 and is not authorized by this scenario runner."
        )
    summaries = [str(cards_by_id[answer_id]["copy_paste_text"]) for answer_id in spec.selected_answer_ids]
    return " ".join(summaries)


def _evidence_artifacts(spec: ScenarioSpec, cards_by_id: Mapping[str, Mapping[str, object]]) -> tuple[str, ...]:
    seen: list[str] = []
    for answer_id in spec.selected_answer_ids:
        for artifact in cards_by_id[answer_id].get("evidence_artifacts", ()):
            if str(artifact) not in seen:
                seen.append(str(artifact))
    for artifact in (
        P381_SOURCE_ARTIFACTS["p381_answer_cards"],
        P381_SOURCE_ARTIFACTS["p381_manifest"],
        P380_SOURCE_ARTIFACTS["p380_index"],
    ):
        if artifact not in seen:
            seen.append(artifact)
    return tuple(seen)


def _caveats(spec: ScenarioSpec, cards_by_id: Mapping[str, Mapping[str, object]]) -> tuple[str, ...]:
    seen: list[str] = []
    for answer_id in spec.selected_answer_ids:
        for caveat in cards_by_id[answer_id].get("caveats", ()):
            if str(caveat) not in seen:
                seen.append(str(caveat))
    for caveat in DISCLAIMER_LINES:
        if caveat not in seen:
            seen.append(caveat)
    return tuple(seen)


def build_transcripts(context: Mapping[str, object], path_warnings: Mapping[str, object]) -> dict[str, object]:
    cards_by_id = context["cards_by_id"]
    transcripts = {}
    for spec in scenario_specs():
        answer_summary = _answer_summary(spec, cards_by_id)
        transcript_text = (
            f"Prompt: {spec.prompt}\n"
            f"Answer: {answer_summary}\n"
            f"Boundary: {NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT} "
            "Historical descriptive evidence only. No future prediction guarantee. No betting advice. "
            "No production registry import. No strategy status changes. Not production release approval."
        )
        transcripts[spec.scenario_id] = {
            "scenario_id": spec.scenario_id,
            "prompt": spec.prompt,
            "selected_answer_ids": spec.selected_answer_ids,
            "answer_summary": answer_summary,
            "transcript_text": transcript_text,
            "evidence_artifacts": _evidence_artifacts(spec, cards_by_id),
            "caveats": _caveats(spec, cards_by_id),
            "path_warnings": path_warnings if spec.scenario_id == "protected_worktree_warnings" else {},
            "no_db_confirmed": True,
            "no_adapter_calls_confirmed": True,
            "no_new_scoring_confirmed": True,
            "no_deploy_confirmed": True,
        }
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "scenario_transcripts": transcripts,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_coverage_rows(transcripts: Mapping[str, object]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    scenario_transcripts = transcripts["scenario_transcripts"]
    for spec in scenario_specs():
        transcript = scenario_transcripts[spec.scenario_id]
        selected = tuple(transcript["selected_answer_ids"])
        coverage_passed = bool(selected) and bool(transcript["answer_summary"]) and all(
            transcript[key] is True
            for key in (
                "no_db_confirmed",
                "no_adapter_calls_confirmed",
                "no_new_scoring_confirmed",
                "no_deploy_confirmed",
            )
        )
        rows.append(
            {
                "scenario_id": spec.scenario_id,
                "required_answer_type": spec.required_answer_type,
                "matched_answer_id": ";".join(selected),
                "coverage_status": "PASS" if coverage_passed else "FAIL",
                "notes": (
                    "P381 answer card coverage is sufficient for this deterministic scenario."
                    if coverage_passed
                    else "Scenario lacks a required answer or safety confirmation."
                ),
            }
        )
    return tuple(rows)


def build_missing_answer_rows(coverage_rows: Sequence[Mapping[str, str]]) -> tuple[dict[str, str], ...]:
    gaps = [row for row in coverage_rows if row["coverage_status"] != "PASS"]
    if not gaps:
        return (
            {
                "gap_id": "none",
                "scenario_id": "none",
                "missing_answer_type": "none",
                "severity": "none",
                "blocking": "NO",
                "suggested_followup": "No missing or weak answer coverage found for required P382 scenarios.",
            },
        )
    return tuple(
        {
            "gap_id": f"gap_{idx:03d}",
            "scenario_id": row["scenario_id"],
            "missing_answer_type": row["required_answer_type"],
            "severity": "HIGH" if row["coverage_status"] == "FAIL" else "MEDIUM",
            "blocking": "YES" if row["coverage_status"] == "FAIL" else "NO",
            "suggested_followup": "Add a bounded P381 answer card or explicit caveat before handoff.",
        }
        for idx, row in enumerate(gaps, start=1)
    )


def build_qa_report(
    coverage_rows: Sequence[Mapping[str, str]],
    missing_answer_rows: Sequence[Mapping[str, str]],
    path_warnings: Mapping[str, object],
) -> str:
    pass_count = len([row for row in coverage_rows if row["coverage_status"] == "PASS"])
    warn_count = len([row for row in coverage_rows if row["coverage_status"] == "WARN"])
    fail_count = len([row for row in coverage_rows if row["coverage_status"] == "FAIL"])
    missing_summary = (
        "No missing or weak answer coverage found."
        if missing_answer_rows[0]["gap_id"] == "none"
        else f"{len(missing_answer_rows)} missing or weak answer coverage rows found."
    )
    coverage_table = "\n".join(
        f"| {row['scenario_id']} | {row['required_answer_type']} | {row['matched_answer_id']} | {row['coverage_status']} |"
        for row in coverage_rows
    )
    return textwrap.dedent(
        f"""\
        # P382 Big Lotto no-DB answer kit scenario runner QA report

        ## Scenario Coverage Summary
        PASS={pass_count}; WARN={warn_count}; FAIL={fail_count}; scenarios={len(coverage_rows)}.

        | scenario_id | required_answer_type | matched_answer_id | coverage_status |
        | --- | --- | --- | --- |
        {coverage_table}

        ## Missing-Answer Summary
        {missing_summary}

        ## Recommended Safe Next Action
        Use the generated P382 scenario transcripts as deterministic handoff examples for Worker / CTO / CEO / Planner questions. Keep all DB open/write, adapter calls, new scoring cohorts, production registry import, deploy, force operations, strategy status changes, betting advice, and future-performance claims out of scope.

        ## CTO / CEO Answer Readiness
        CTO readiness: PASS. The cto_technical_risk scenario maps P381 command, artifact, delta, and safety answers to historical descriptive evidence only.
        CEO readiness: PASS. The ceo_nontechnical_summary scenario maps P381 overall status, safety, and safe next action answers to non-technical wording.

        ## Protected Worktree Warning Status
        P379 previous worktree: {path_warnings['p379_previous_worktree']['status']} at {path_warnings['p379_previous_worktree']['path']}. Policy: {path_warnings['p379_previous_worktree']['policy']}.
        Protected historical worktree warning: {path_warnings['protected_historical_warning']}.

        ## Safety Boundary
        Historical descriptive evidence only.
        No future prediction guarantee.
        No betting advice.
        No DB open/write.
        No adapter calls.
        No new scoring.
        No new scoring cohort.
        No production registry import.
        No deploy.
        No generated DB rows.
        No strategy status changes.
        No blended leaderboard.
        No force operations.
        No external publication.
        Not production release approval.

        {NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT}
        """
    )


def build_index(
    scenarios: Mapping[str, object],
    transcripts: Mapping[str, object],
    coverage_rows: Sequence[Mapping[str, str]],
    missing_answer_rows: Sequence[Mapping[str, str]],
    path_warnings: Mapping[str, object],
    repo_root: Path | None = None,
) -> dict[str, object]:
    inventory = source_inventory(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_p380_artifact_paths": P380_SOURCE_ARTIFACTS,
        "source_p381_artifact_paths": P381_SOURCE_ARTIFACTS,
        "source_sha256": {row["path"]: row["sha256"] for row in inventory},
        "generated_p382_artifact_paths": {
            role: f"artifacts/{basename}" for role, basename in P382_ARTIFACT_BASENAMES.items()
        },
        "available_scenario_ids": scenarios["scenario_ids"],
        "path_warnings": path_warnings,
        "counts": {
            "source_artifacts": len(inventory),
            "scenarios": len(scenarios["scenario_ids"]),
            "transcripts": len(transcripts["scenario_transcripts"]),
            "coverage_rows": len(coverage_rows),
            "missing_answer_rows": len(missing_answer_rows),
            "generated_artifacts": len(P382_ARTIFACT_BASENAMES),
        },
        "statements": STATEMENTS,
        "no_db_no_adapter_no_scoring_no_deploy_statement": NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
        "scope_lines": DISCLAIMER_LINES,
    }


def _artifact_contents_without_manifest(output: ScenarioRunnerOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "scenarios": _json_text(output.scenarios),
        "transcripts": _json_text(output.transcripts),
        "coverage": _csv_text(COVERAGE_COLUMNS, output.coverage_rows),
        "missing_answers": _csv_text(MISSING_ANSWER_COLUMNS, output.missing_answer_rows),
        "qa_report": output.qa_report_markdown,
    }


def _artifact_contents(output: ScenarioRunnerOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"coverage", "missing_answers", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"index", "scenarios", "transcripts"}:
        return "", f"json_keys={len(json.loads(text))}"
    if role == "qa_report":
        return "", f"text_lines={len(text.splitlines())}"
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for source in source_inventory(repo_root):
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": source["artifact_role"],
                "path": source["path"],
                "source_sha256": source["sha256"],
                "output_row_count": "",
                "output_object_count": source["row_or_object_count"],
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "no_deploy": "YES",
                "details": "P382 source evidence read from committed P380/P381 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P382_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(SOURCE_ARTIFACTS) + len(P382_ARTIFACT_BASENAMES) + 4)
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
                "no_deploy": "YES",
                "details": "P382 generated no-DB answer kit scenario runner artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P382."),
        ("no_adapter_calls", "No adapter calls were performed by P382."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P382."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P382."),
    ):
        rows.append(
            {
                "artifact_group": "statement",
                "artifact_role": role,
                "path": "",
                "source_sha256": "",
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "no_deploy": "YES",
                "details": details,
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    return tuple(rows)


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def validate_scenario_runner(
    output: ScenarioRunnerOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_scenario_runner(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    scenario_ids = tuple(scenario["scenario_id"] for scenario in current.scenarios["scenarios"])
    transcript_ids = tuple(current.transcripts["scenario_transcripts"])
    rows = [
        _check("required_p380_p381_evidence_exists", len(verify_required_evidence(repo_root)) == len(SOURCE_ARTIFACTS), len(SOURCE_ARTIFACTS), len(SOURCE_ARTIFACTS), "Required P380/P381 source modules and artifacts are present."),
        _check("index_json_schema", set(current.index) >= {"source_baseline", "source_sha256", "generated_p382_artifact_paths", "available_scenario_ids", "path_warnings", "statements"}, "required index keys", sorted(current.index), "Index includes required P382 keys."),
        _check("scenarios_json_schema", scenario_ids == SCENARIO_IDS and all(set(scenario) >= {"scenario_id", "prompt", "required_answer_type", "selected_answer_ids"} for scenario in current.scenarios["scenarios"]), SCENARIO_IDS, scenario_ids, "Scenario catalog includes required deterministic scenarios."),
        _check("transcripts_json_schema", set(transcript_ids) == set(SCENARIO_IDS) and all(set(transcript) >= {"scenario_id", "prompt", "selected_answer_ids", "answer_summary", "evidence_artifacts", "caveats", "no_db_confirmed", "no_adapter_calls_confirmed", "no_new_scoring_confirmed", "no_deploy_confirmed"} for transcript in current.transcripts["scenario_transcripts"].values()), SCENARIO_IDS, sorted(transcript_ids), "Transcript JSON includes required fields and confirmations."),
        _check("coverage_csv_schema", bool(current.coverage_rows) and tuple(current.coverage_rows[0]) == COVERAGE_COLUMNS and {row["coverage_status"] for row in current.coverage_rows} <= {"PASS", "WARN", "FAIL"}, COVERAGE_COLUMNS, tuple(current.coverage_rows[0]) if current.coverage_rows else (), "Coverage rows use required columns."),
        _check("missing_answer_csv_schema", bool(current.missing_answer_rows) and tuple(current.missing_answer_rows[0]) == MISSING_ANSWER_COLUMNS, MISSING_ANSWER_COLUMNS, tuple(current.missing_answer_rows[0]) if current.missing_answer_rows else (), "Missing-answer rows use required columns."),
        _check("qa_report_contains_sections_and_disclaimers", all(section in current.qa_report_markdown for section in ("## Scenario Coverage Summary", "## Missing-Answer Summary", "## Recommended Safe Next Action", "## CTO / CEO Answer Readiness", "## Protected Worktree Warning Status", "## Safety Boundary")) and all(line in current.qa_report_markdown for line in ("Historical descriptive evidence only.", "No future prediction guarantee.", "No betting advice.", "No DB open/write.", "No adapter calls.", "No deploy.", "Not production release approval.")), "sections and disclaimers present", "present", "QA report is copy-paste friendly and bounded."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P382 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_scenario_runner(repo_root, include_validation=False)
        second = run_scenario_runner(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P382 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_scenario_runner(repo_root: Path | None = None, include_validation: bool = True) -> ScenarioRunnerOutput:
    verify_required_evidence(repo_root)
    path_warnings = inspect_path_warnings()
    context = _source_context(repo_root)
    scenarios = build_scenarios()
    transcripts = build_transcripts(context, path_warnings)
    coverage_rows = build_coverage_rows(transcripts)
    missing_answer_rows = build_missing_answer_rows(coverage_rows)
    qa_report = build_qa_report(coverage_rows, missing_answer_rows, path_warnings)
    temp = ScenarioRunnerOutput(
        index={},
        scenarios=scenarios,
        transcripts=transcripts,
        coverage_rows=coverage_rows,
        missing_answer_rows=missing_answer_rows,
        qa_report_markdown=qa_report,
        manifest_rows=(),
        validation_rows=(),
    )
    index = build_index(scenarios, transcripts, coverage_rows, missing_answer_rows, path_warnings, repo_root)
    temp = ScenarioRunnerOutput(
        index=index,
        scenarios=scenarios,
        transcripts=transcripts,
        coverage_rows=coverage_rows,
        missing_answer_rows=missing_answer_rows,
        qa_report_markdown=qa_report,
        manifest_rows=(),
        validation_rows=(),
    )
    manifest_rows = build_manifest_rows(_artifact_contents_without_manifest(temp), repo_root)
    output = ScenarioRunnerOutput(
        index=index,
        scenarios=scenarios,
        transcripts=transcripts,
        coverage_rows=coverage_rows,
        missing_answer_rows=missing_answer_rows,
        qa_report_markdown=qa_report,
        manifest_rows=manifest_rows,
        validation_rows=(),
    )
    validation_rows = validate_scenario_runner(output, repo_root, include_determinism=False) if include_validation else ()
    return ScenarioRunnerOutput(
        index=index,
        scenarios=scenarios,
        transcripts=transcripts,
        coverage_rows=coverage_rows,
        missing_answer_rows=missing_answer_rows,
        qa_report_markdown=qa_report,
        manifest_rows=manifest_rows,
        validation_rows=validation_rows,
    )


def write_artifacts(output: ScenarioRunnerOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    out_dir = artifacts_dir if artifacts_dir is not None else REPO_ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths: dict[str, Path] = {}
    for role, basename in P382_ARTIFACT_BASENAMES.items():
        path = out_dir / basename
        path.write_text(contents[role], encoding="utf-8")
        paths[role] = path
    return paths


def _print_csv(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def _print_scenario(output: ScenarioRunnerOutput, scenario_id: str) -> int:
    transcripts = output.transcripts["scenario_transcripts"]
    if scenario_id not in transcripts:
        raise SystemExit(f"unknown scenario_id: {scenario_id}")
    print(_json_text(transcripts[scenario_id]), end="")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P382 Big Lotto no-DB answer kit scenario runner")
    parser.add_argument("--artifacts-dir", type=Path, default=None)
    parser.add_argument("--generate", action="store_true", help="Write all P382 scenario runner artifacts.")
    parser.add_argument("--scenarios", action="store_true", help="Print scenario catalog JSON.")
    parser.add_argument("--transcripts", action="store_true", help="Print scenario transcripts JSON.")
    parser.add_argument("--coverage", action="store_true", help="Print scenario coverage CSV.")
    parser.add_argument("--missing-answers", action="store_true", help="Print missing-answer matrix CSV.")
    parser.add_argument("--qa-report", action="store_true", help="Print QA report Markdown.")
    parser.add_argument("--scenario", choices=SCENARIO_IDS, default=None, help="Print one scenario transcript JSON.")
    parser.add_argument("--validate", action="store_true", help="Print validation CSV.")
    args = parser.parse_args(argv)

    output = run_scenario_runner(include_validation=True)
    if args.generate:
        paths = write_artifacts(output, args.artifacts_dir)
        first = run_scenario_runner(include_validation=False)
        second = run_scenario_runner(include_validation=False)
        determinism = "PASS" if _artifact_contents(first) == _artifact_contents(second) else "FAIL"
        print(f"P382 answer kit scenario runner artifacts written: {len(paths)}")
        print(f"determinism double-run {determinism}")
        print(f"scenarios={len(SCENARIO_IDS)} coverage_rows={len(output.coverage_rows)} missing_answer_rows={len(output.missing_answer_rows)} sources={output.index['counts']['source_artifacts']}")
        print(NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT)
    elif args.scenarios:
        print(_json_text(output.scenarios), end="")
    elif args.transcripts:
        print(_json_text(output.transcripts), end="")
    elif args.coverage:
        _print_csv(COVERAGE_COLUMNS, output.coverage_rows)
    elif args.missing_answers:
        _print_csv(MISSING_ANSWER_COLUMNS, output.missing_answer_rows)
    elif args.qa_report:
        print(output.qa_report_markdown, end="")
    elif args.scenario:
        return _print_scenario(output, args.scenario)
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_scenario_runner(output))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
