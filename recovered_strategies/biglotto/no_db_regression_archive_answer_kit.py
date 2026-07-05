"""P381 Big Lotto no-DB regression archive answer kit.

This module transforms committed P377/P378/P379/P380 regression archive
evidence into copy-paste ready answer artifacts. It reads only source files and
generated archive/query artifacts, writes only P381-prefixed artifacts, and
does not open or write a DB, call adapters, create new scoring cohorts, import
production registries, deploy, provide betting advice, or make
future-performance claims.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P381_biglotto_regression_archive_answer_kit"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
P380_BASELINE_COMMIT = "4cf6a00362b05917638e2ae77d06fd596ac224ea"
P379_EXTERNAL_WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p379")
PROTECTED_HISTORICAL_WORKTREES = (
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P360-fable5-biglotto-success-direction-readonly"),
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P371-biglotto-command-center"),
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P373-biglotto-command-center-operator-console"),
)

SOURCE_BASELINE = {
    "required_origin_main_merge_commit": P380_BASELINE_COMMIT,
    "source_tasks": (
        "P377_biglotto_command_center_regression_runner",
        "P378_biglotto_regression_run_archive",
        "P379_biglotto_regression_archive_explorer",
        "P380_biglotto_regression_archive_query",
    ),
    "answer_kit_mode": "read_only_no_db_p380_answer_artifact_transformer",
}

P377_SOURCE_ARTIFACTS = {
    "p377_module": "recovered_strategies/biglotto/no_db_command_center_regression_runner.py",
    "p377_results": "artifacts/P377_biglotto_command_center_regression_results.json",
    "p377_commands": "artifacts/P377_biglotto_command_center_regression_commands.csv",
    "p377_failures": "artifacts/P377_biglotto_command_center_regression_failures.csv",
    "p377_freshness": "artifacts/P377_biglotto_command_center_regression_artifact_freshness.csv",
    "p377_report": "artifacts/P377_biglotto_command_center_regression_report.html",
    "p377_manifest": "artifacts/P377_biglotto_command_center_regression_manifest.csv",
}
P378_SOURCE_ARTIFACTS = {
    "p378_module": "recovered_strategies/biglotto/no_db_regression_run_archive.py",
    "p378_index": "artifacts/P378_biglotto_regression_run_archive_index.json",
    "p378_snapshot": "artifacts/P378_biglotto_regression_run_archive_snapshot.json",
    "p378_comparison": "artifacts/P378_biglotto_regression_run_archive_comparison.json",
    "p378_command_delta": "artifacts/P378_biglotto_regression_run_archive_command_delta.csv",
    "p378_freshness_delta": "artifacts/P378_biglotto_regression_run_archive_freshness_delta.csv",
    "p378_report": "artifacts/P378_biglotto_regression_run_archive_report.html",
    "p378_manifest": "artifacts/P378_biglotto_regression_run_archive_manifest.csv",
}
P379_SOURCE_ARTIFACTS = {
    "p379_module": "recovered_strategies/biglotto/no_db_regression_archive_explorer.py",
    "p379_index": "artifacts/P379_biglotto_regression_archive_explorer_index.json",
    "p379_catalog": "artifacts/P379_biglotto_regression_archive_explorer_catalog.csv",
    "p379_snapshot_summary": "artifacts/P379_biglotto_regression_archive_explorer_snapshot_summary.json",
    "p379_command_view": "artifacts/P379_biglotto_regression_archive_explorer_command_view.csv",
    "p379_freshness_view": "artifacts/P379_biglotto_regression_archive_explorer_freshness_view.csv",
    "p379_query_snapshots": "artifacts/P379_biglotto_regression_archive_explorer_query_snapshots.json",
    "p379_report": "artifacts/P379_biglotto_regression_archive_explorer_report.html",
    "p379_manifest": "artifacts/P379_biglotto_regression_archive_explorer_manifest.csv",
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
SOURCE_ARTIFACTS = {
    **P377_SOURCE_ARTIFACTS,
    **P378_SOURCE_ARTIFACTS,
    **P379_SOURCE_ARTIFACTS,
    **P380_SOURCE_ARTIFACTS,
}

P381_ARTIFACT_BASENAMES = {
    "index": "P381_biglotto_regression_archive_answer_kit_index.json",
    "answer_cards": "P381_biglotto_regression_archive_answer_kit_answer_cards.json",
    "status_block": "P381_biglotto_regression_archive_answer_kit_status_block.md",
    "briefings": "P381_biglotto_regression_archive_answer_kit_briefings.json",
    "lookup_transcripts": "P381_biglotto_regression_archive_answer_kit_lookup_transcripts.json",
    "portal": "P381_biglotto_regression_archive_answer_kit_portal.html",
    "manifest": "P381_biglotto_regression_archive_answer_kit_manifest.csv",
}

ANSWER_IDS = (
    "overall_status",
    "non_pass_commands",
    "stale_or_missing_artifacts",
    "warn_fail_deltas",
    "protected_worktree_warnings",
    "safety_status",
    "latest_durable_baseline",
    "safe_next_actions",
)
LOOKUP_TRANSCRIPT_IDS = (
    "overall_status",
    "non_pass_commands",
    "stale_or_missing_artifacts",
    "protected_worktree_warnings",
    "safe_next_actions",
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
    "P381 reads only merged P377/P378/P379/P380 regression archive artifacts and writes only P381-prefixed answer artifacts.",
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
class AnswerKitOutput:
    index: dict[str, object]
    answer_cards: dict[str, object]
    status_block_markdown: str
    briefings: dict[str, object]
    lookup_transcripts: dict[str, object]
    portal_html: str
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
        raise RuntimeError(f"required P377/P378/P379/P380 regression archive evidence missing: {missing}")
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
        "P381_WARN_PROTECTED_WORKTREES_ABSENT"
        if any(status == "ABSENT" for status in protected.values())
        else "P381_PROTECTED_WORKTREES_PRESENT"
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


def _filter_by_query(rows: Sequence[Mapping[str, str]], query_id: str) -> tuple[dict[str, str], ...]:
    return tuple(dict(row) for row in rows if row.get("query_id") == query_id)


def _p380_context(repo_root: Path | None = None) -> dict[str, object]:
    p377_results = _read_json(P377_SOURCE_ARTIFACTS["p377_results"], repo_root)
    p380_index = _read_json(P380_SOURCE_ARTIFACTS["p380_index"], repo_root)
    p380_transcripts = _read_json(P380_SOURCE_ARTIFACTS["p380_transcripts"], repo_root)
    command_rows = _read_csv(P380_SOURCE_ARTIFACTS["p380_command_results"], repo_root)
    artifact_rows = _read_csv(P380_SOURCE_ARTIFACTS["p380_artifact_results"], repo_root)
    delta_rows = _read_csv(P380_SOURCE_ARTIFACTS["p380_delta_results"], repo_root)
    return {
        "p377_results": p377_results,
        "p380_index": p380_index,
        "p380_transcripts": p380_transcripts,
        "command_rows": command_rows,
        "artifact_rows": artifact_rows,
        "delta_rows": delta_rows,
        "all_commands": _filter_by_query(command_rows, "all_commands"),
        "non_pass_commands": _filter_by_query(command_rows, "non_pass_commands"),
        "all_artifacts": _filter_by_query(artifact_rows, "all_artifacts"),
        "stale_or_missing_artifacts": _filter_by_query(artifact_rows, "stale_or_missing_artifacts"),
        "all_deltas": _filter_by_query(delta_rows, "all_deltas"),
        "warn_or_fail_deltas": _filter_by_query(delta_rows, "warn_or_fail_deltas"),
    }


def _real_issue_count(rows: Sequence[Mapping[str, str]], sentinel_key: str, sentinel_value: str = "none") -> int:
    return len([row for row in rows if row.get(sentinel_key) != sentinel_value])


def _card(
    answer_id: str,
    title: str,
    audience: Sequence[str],
    summary: str,
    evidence_artifacts: Sequence[str],
    caveats: Sequence[str],
    copy_paste_text: str,
) -> dict[str, object]:
    return {
        "answer_id": answer_id,
        "title": title,
        "audience": tuple(audience),
        "summary": summary,
        "evidence_artifacts": tuple(evidence_artifacts),
        "caveats": tuple(caveats),
        "copy_paste_text": copy_paste_text,
    }


def build_answer_cards(context: Mapping[str, object], path_warnings: Mapping[str, object]) -> dict[str, object]:
    p377_results = context["p377_results"]
    p380_index = context["p380_index"]
    all_commands = context["all_commands"]
    all_artifacts = context["all_artifacts"]
    all_deltas = context["all_deltas"]
    non_pass = context["non_pass_commands"]
    stale = context["stale_or_missing_artifacts"]
    warn_fail = context["warn_or_fail_deltas"]

    non_pass_count = _real_issue_count(non_pass, "command_id")
    stale_count = _real_issue_count(stale, "artifact_path")
    warn_fail_count = _real_issue_count(warn_fail, "delta_id")
    protected_warning = str(path_warnings["protected_historical_warning"])
    p379_status = str(path_warnings["p379_previous_worktree"]["status"])
    latest_baseline = p380_index["source_baseline"]["required_origin_main_merge_commit"]

    common_caveats = (
        "Historical descriptive evidence only.",
        "No future prediction guarantee.",
        "No betting advice.",
        "Not production release approval.",
    )
    cards = (
        _card(
            "overall_status",
            "Overall regression archive status",
            ("Worker", "CTO", "CEO"),
            f"P377 recorded overall_status={p377_results['overall_status']} across {len(all_commands)} command rows; P380 indexed {len(all_artifacts)} source artifacts and {len(all_deltas)} deltas.",
            (
                P377_SOURCE_ARTIFACTS["p377_results"],
                P380_SOURCE_ARTIFACTS["p380_index"],
                P380_SOURCE_ARTIFACTS["p380_command_results"],
                P380_SOURCE_ARTIFACTS["p380_delta_results"],
            ),
            common_caveats,
            f"Big Lotto no-DB regression archive answer: P377 overall_status={p377_results['overall_status']}; P380 indexed {len(all_commands)} archived commands, {len(all_artifacts)} source artifacts, and {len(all_deltas)} deltas. This is historical descriptive evidence only, with no future prediction guarantee, no betting advice, and no production release approval.",
        ),
        _card(
            "non_pass_commands",
            "Non-pass commands",
            ("Worker", "CTO"),
            f"Committed P380 query evidence contains {non_pass_count} real non-PASS command rows.",
            (
                P380_SOURCE_ARTIFACTS["p380_command_results"],
                P378_SOURCE_ARTIFACTS["p378_command_delta"],
                P377_SOURCE_ARTIFACTS["p377_commands"],
            ),
            common_caveats,
            f"Non-pass command answer: {non_pass_count} real non-PASS command rows are present in committed P380 query evidence. P381 did not execute P371-P380 commands; it transformed existing archive artifacts only.",
        ),
        _card(
            "stale_or_missing_artifacts",
            "Stale or missing artifacts",
            ("Worker", "CTO"),
            f"Committed P380 query evidence contains {stale_count} real stale or missing source artifact rows.",
            (
                P380_SOURCE_ARTIFACTS["p380_artifact_results"],
                P378_SOURCE_ARTIFACTS["p378_freshness_delta"],
                P377_SOURCE_ARTIFACTS["p377_freshness"],
            ),
            common_caveats,
            f"Stale/missing artifact answer: {stale_count} real stale or missing source artifact rows are present in committed P380 query evidence. All P381 output is a no-DB answer transformation.",
        ),
        _card(
            "warn_fail_deltas",
            "Warn/fail deltas",
            ("Worker", "CTO"),
            f"Committed P380 query evidence contains {warn_fail_count} real WARN/FAIL delta rows.",
            (
                P380_SOURCE_ARTIFACTS["p380_delta_results"],
                P378_SOURCE_ARTIFACTS["p378_command_delta"],
                P378_SOURCE_ARTIFACTS["p378_freshness_delta"],
            ),
            common_caveats,
            f"WARN/FAIL delta answer: {warn_fail_count} real WARN/FAIL delta rows are present in committed P380 query evidence. This does not authorize DB writes, adapter execution, new scoring, or deploy.",
        ),
        _card(
            "protected_worktree_warnings",
            "Protected worktree warnings",
            ("Worker",),
            f"/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p379 is {p379_status}; protected historical worktree status is {protected_warning}.",
            (P380_SOURCE_ARTIFACTS["p380_index"],),
            common_caveats + (
                "Read-only presence check only.",
                "Do not use or clean /Users/kelvin/Kelvin-WorkSpace/LotteryNew-p379.",
                "Do not recreate, repair, delete, or clean absent protected historical paths.",
            ),
            f"Path warning answer: /Users/kelvin/Kelvin-WorkSpace/LotteryNew-p379 is {p379_status}. Protected historical worktree warning is {protected_warning}. No protected path was used, cleaned, recreated, or repaired by P381.",
        ),
        _card(
            "safety_status",
            "DB / adapter / scoring / deploy safety status",
            ("Worker", "CTO", "CEO"),
            NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
            (P380_SOURCE_ARTIFACTS["p380_manifest"], P381_ARTIFACT_BASENAMES["manifest"]),
            common_caveats + (
                "No production registry import.",
                "No strategy status changes.",
                "No blended leaderboard.",
            ),
            f"Safety answer: {NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT} P381 is not production release approval.",
        ),
        _card(
            "latest_durable_baseline",
            "Latest durable baseline",
            ("Worker", "CTO"),
            f"P381 is built on merged P380 query API evidence at baseline {P380_BASELINE_COMMIT}; P380 source evidence names prior archive baseline {latest_baseline}.",
            (P380_SOURCE_ARTIFACTS["p380_index"], P380_SOURCE_ARTIFACTS["p380_transcripts"]),
            common_caveats,
            f"Latest durable baseline answer: P381 source baseline is {P380_BASELINE_COMMIT}. P380 query evidence references prior archive baseline {latest_baseline}. This is historical evidence packaging only.",
        ),
        _card(
            "safe_next_actions",
            "Safe next action summary",
            ("Worker", "Planner"),
            "Use the P381 answer cards, status block, briefings, lookup transcripts, portal, and manifest for handoff. Keep all DB, adapter, scoring, registry, and deploy actions out of scope.",
            (
                f"artifacts/{P381_ARTIFACT_BASENAMES['answer_cards']}",
                f"artifacts/{P381_ARTIFACT_BASENAMES['status_block']}",
                f"artifacts/{P381_ARTIFACT_BASENAMES['portal']}",
            ),
            common_caveats + ("No standing authorization is created by this answer kit.",),
            "Safe next action answer: hand off the P381 answer pack as descriptive archive evidence. No DB open/write; do not call adapters, create scoring cohorts, import production registries, deploy, force operations, give betting advice, or make future-performance claims.",
        ),
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "answer_ids": ANSWER_IDS,
        "cards": cards,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _cards_by_id(answer_cards: Mapping[str, object]) -> dict[str, dict[str, object]]:
    return {card["answer_id"]: card for card in answer_cards["cards"]}


def build_status_block(answer_cards: Mapping[str, object], path_warnings: Mapping[str, object]) -> str:
    cards = _cards_by_id(answer_cards)
    return textwrap.dedent(
        f"""\
        # P381 Big Lotto no-DB regression archive answer kit status

        ## Overall
        {cards['overall_status']['copy_paste_text']}

        ## Evidence Flags
        {cards['non_pass_commands']['copy_paste_text']}
        {cards['stale_or_missing_artifacts']['copy_paste_text']}
        {cards['warn_fail_deltas']['copy_paste_text']}

        ## Path Warnings
        {cards['protected_worktree_warnings']['copy_paste_text']}

        ## Safe Next Actions
        {cards['safe_next_actions']['copy_paste_text']}

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
        Not production release approval.

        P379 previous worktree: {path_warnings['p379_previous_worktree']['status']}
        Protected historical worktree warning: {path_warnings['protected_historical_warning']}
        """
    )


def build_briefings(answer_cards: Mapping[str, object]) -> dict[str, object]:
    cards = _cards_by_id(answer_cards)
    safety = cards["safety_status"]["copy_paste_text"]
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "briefings": {
            "cto_briefing_draft": {
                "audience": "CTO",
                "text": (
                    f"{cards['overall_status']['copy_paste_text']} "
                    f"{cards['non_pass_commands']['copy_paste_text']} "
                    f"{cards['stale_or_missing_artifacts']['copy_paste_text']} "
                    f"{cards['warn_fail_deltas']['copy_paste_text']} {safety}"
                ),
            },
            "ceo_briefing_draft": {
                "audience": "CEO",
                "text": (
                    "The Big Lotto regression archive has been packaged into a no-DB answer kit for historical review. "
                    f"{cards['overall_status']['copy_paste_text']} {safety} "
                    "This is not betting advice, not a future prediction guarantee, and not production release approval."
                ),
            },
            "worker_handoff_draft": {
                "audience": "Worker",
                "text": (
                    f"Use P381 generated artifacts for handoff: answer cards, status block, briefings, lookup transcripts, portal, and manifest. "
                    f"{cards['protected_worktree_warnings']['copy_paste_text']} "
                    f"{cards['safe_next_actions']['copy_paste_text']}"
                ),
            },
            "planner_note": {
                "audience": "Planner",
                "text": (
                    "P381 converts merged P377/P378/P379/P380 evidence into response artifacts only. "
                    "It does not create roadmap approval, production release approval, future-performance claims, or betting advice."
                ),
            },
        },
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_lookup_transcripts(answer_cards: Mapping[str, object]) -> dict[str, object]:
    cards = _cards_by_id(answer_cards)
    transcripts = {}
    for answer_id in LOOKUP_TRANSCRIPT_IDS:
        card = cards[answer_id]
        transcripts[answer_id] = {
            "command": f"python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --answer {answer_id}",
            "answer_id": answer_id,
            "stdout": card["copy_paste_text"],
            "evidence_artifacts": card["evidence_artifacts"],
            "caveats": card["caveats"],
        }
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "lookup_transcripts": transcripts,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_index(
    answer_cards: Mapping[str, object],
    path_warnings: Mapping[str, object],
    repo_root: Path | None = None,
) -> dict[str, object]:
    inventory = source_inventory(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_p377_artifact_paths": P377_SOURCE_ARTIFACTS,
        "source_p378_artifact_paths": P378_SOURCE_ARTIFACTS,
        "source_p379_artifact_paths": P379_SOURCE_ARTIFACTS,
        "source_p380_artifact_paths": P380_SOURCE_ARTIFACTS,
        "source_sha256": {row["path"]: row["sha256"] for row in inventory},
        "generated_p381_artifact_paths": {
            role: f"artifacts/{basename}" for role, basename in P381_ARTIFACT_BASENAMES.items()
        },
        "available_answer_ids": answer_cards["answer_ids"],
        "path_warnings": path_warnings,
        "counts": {
            "source_artifacts": len(inventory),
            "answer_cards": len(answer_cards["cards"]),
            "lookup_transcripts": len(LOOKUP_TRANSCRIPT_IDS),
            "generated_artifacts": len(P381_ARTIFACT_BASENAMES),
        },
        "statements": STATEMENTS,
        "no_db_no_adapter_no_scoring_no_deploy_statement": NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_portal(
    index: Mapping[str, object],
    answer_cards: Mapping[str, object],
    status_block: str,
    briefings: Mapping[str, object],
) -> str:
    cards = answer_cards["cards"]
    card_html = "\n".join(
        "<section class=\"card\">"
        f"<h2>{html.escape(card['title'])}</h2>"
        f"<p><strong>Answer ID:</strong> {html.escape(card['answer_id'])}</p>"
        f"<p>{html.escape(card['summary'])}</p>"
        f"<pre>{html.escape(card['copy_paste_text'])}</pre>"
        "</section>"
        for card in cards
    )
    source_rows = "\n".join(
        f"<tr><td>{html.escape(path)}</td><td>{html.escape(digest)}</td></tr>"
        for path, digest in index["source_sha256"].items()
    )
    briefing_html = "\n".join(
        f"<section><h3>{html.escape(key.replace('_', ' ').title())}</h3><p>{html.escape(value['text'])}</p></section>"
        for key, value in briefings["briefings"].items()
    )
    commands = "\n".join(
        html.escape(command)
        for command in (
            "python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --answers",
            "python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --status-block",
            "python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --briefings",
            "python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --lookup-transcripts",
            "python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --answer overall_status",
            "python3 -m recovered_strategies.biglotto.no_db_regression_archive_answer_kit --validate",
        )
    )
    disclaimers = " ".join(DISCLAIMER_LINES)
    return textwrap.dedent(
        f"""\
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>P381 Big Lotto no-DB regression archive answer kit</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 0; color: #1f2933; background: #f7f7f3; }}
            header {{ background: #17324d; color: white; padding: 24px; }}
            main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
            section {{ margin: 0 0 24px; }}
            .card {{ background: white; border: 1px solid #d7d7ce; border-radius: 6px; padding: 16px; }}
            pre {{ white-space: pre-wrap; background: #f0f3f5; padding: 12px; border-radius: 4px; }}
            table {{ border-collapse: collapse; width: 100%; background: white; }}
            th, td {{ border: 1px solid #d7d7ce; padding: 8px; text-align: left; vertical-align: top; }}
            code {{ background: #eef2f3; padding: 2px 4px; border-radius: 3px; }}
          </style>
        </head>
        <body>
          <header>
            <h1>P381 Big Lotto no-DB regression archive answer kit</h1>
            <p>Scope banner: {html.escape(disclaimers)}</p>
          </header>
          <main>
            <section>
              <h2>Answer Cards</h2>
              {card_html}
            </section>
            <section>
              <h2>Status Block</h2>
              <pre>{html.escape(status_block)}</pre>
            </section>
            <section>
              <h2>Briefing Snippets</h2>
              {briefing_html}
            </section>
            <section>
              <h2>Source Artifact Inventory</h2>
              <table><thead><tr><th>Path</th><th>SHA256</th></tr></thead><tbody>{source_rows}</tbody></table>
            </section>
            <section>
              <h2>Local Commands</h2>
              <pre>{commands}</pre>
            </section>
            <section>
              <h2>Safety Disclaimers</h2>
              <p>{html.escape(NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT)}</p>
              <p>No betting advice. No future prediction guarantee. Not production release approval.</p>
            </section>
          </main>
        </body>
        </html>
        """
    )


def _artifact_contents_without_manifest(output: AnswerKitOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "answer_cards": _json_text(output.answer_cards),
        "status_block": output.status_block_markdown,
        "briefings": _json_text(output.briefings),
        "lookup_transcripts": _json_text(output.lookup_transcripts),
        "portal": output.portal_html,
    }


def _artifact_contents(output: AnswerKitOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role == "manifest":
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"index", "answer_cards", "briefings", "lookup_transcripts"}:
        return "", f"json_keys={len(json.loads(text))}"
    if role in {"status_block", "portal"}:
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
                "details": "P381 source evidence read from committed P377/P378/P379/P380 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P381_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(SOURCE_ARTIFACTS) + len(P381_ARTIFACT_BASENAMES) + 4)
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
                "details": "P381 generated no-DB regression archive answer kit artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P381."),
        ("no_adapter_calls", "No adapter calls were performed by P381."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P381."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P381."),
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


def validate_answer_kit(
    output: AnswerKitOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_answer_kit(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    card_ids = tuple(card["answer_id"] for card in current.answer_cards["cards"])
    rows = [
        _check("required_p377_p378_p379_p380_evidence_exists", len(verify_required_evidence(repo_root)) == len(SOURCE_ARTIFACTS), len(SOURCE_ARTIFACTS), len(SOURCE_ARTIFACTS), "Required source modules and artifacts are present."),
        _check("index_json_schema", set(current.index) >= {"source_baseline", "source_sha256", "generated_p381_artifact_paths", "available_answer_ids", "path_warnings", "statements"}, "required index keys", sorted(current.index), "Index includes required P381 keys."),
        _check("answer_cards_json_schema", set(current.answer_cards) >= {"answer_ids", "cards", "statements"} and card_ids == ANSWER_IDS and all(set(card) >= {"answer_id", "title", "audience", "summary", "evidence_artifacts", "caveats", "copy_paste_text"} for card in current.answer_cards["cards"]), "required answer card keys", card_ids, "Answer cards include required schema and deterministic IDs."),
        _check("status_block_markdown_contains_sections_and_disclaimers", all(section in current.status_block_markdown for section in ("## Overall", "## Evidence Flags", "## Path Warnings", "## Safe Next Actions", "## Safety Boundary")) and all(line in current.status_block_markdown for line in ("Historical descriptive evidence only.", "No future prediction guarantee.", "No betting advice.", "No DB open/write.", "No adapter calls.", "No deploy.", "Not production release approval.")), "sections and disclaimers present", "present", "Status block is copy-paste friendly and bounded."),
        _check("briefings_json_schema", set(current.briefings.get("briefings", {})) == {"cto_briefing_draft", "ceo_briefing_draft", "worker_handoff_draft", "planner_note"}, "required briefing drafts", sorted(current.briefings.get("briefings", {})), "Briefings include CTO, CEO, Worker, and Planner drafts."),
        _check("lookup_transcripts_json_schema", set(current.lookup_transcripts.get("lookup_transcripts", {})) == set(LOOKUP_TRANSCRIPT_IDS), LOOKUP_TRANSCRIPT_IDS, sorted(current.lookup_transcripts.get("lookup_transcripts", {})), "Lookup transcripts include required answer examples."),
        _check("portal_contains_required_sections_and_disclaimers", all(section in current.portal_html for section in ("Scope banner", "Answer Cards", "Status Block", "Briefing Snippets", "Source Artifact Inventory", "Local Commands", "Safety Disclaimers")) and "No DB open/write." in current.portal_html and "No adapter calls." in current.portal_html, "portal sections and disclaimers", "present", "Portal is self-contained with required sections."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P381 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_answer_kit(repo_root, include_validation=False)
        second = run_answer_kit(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P381 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_answer_kit(repo_root: Path | None = None, include_validation: bool = True) -> AnswerKitOutput:
    verify_required_evidence(repo_root)
    path_warnings = inspect_path_warnings()
    context = _p380_context(repo_root)
    answer_cards = build_answer_cards(context, path_warnings)
    status_block = build_status_block(answer_cards, path_warnings)
    briefings = build_briefings(answer_cards)
    lookup_transcripts = build_lookup_transcripts(answer_cards)
    index = build_index(answer_cards, path_warnings, repo_root)
    temp = AnswerKitOutput(
        index=index,
        answer_cards=answer_cards,
        status_block_markdown=status_block,
        briefings=briefings,
        lookup_transcripts=lookup_transcripts,
        portal_html="",
        manifest_rows=(),
        validation_rows=(),
    )
    portal = build_portal(index, answer_cards, status_block, briefings)
    temp = AnswerKitOutput(
        index=index,
        answer_cards=answer_cards,
        status_block_markdown=status_block,
        briefings=briefings,
        lookup_transcripts=lookup_transcripts,
        portal_html=portal,
        manifest_rows=(),
        validation_rows=(),
    )
    manifest_rows = build_manifest_rows(_artifact_contents_without_manifest(temp), repo_root)
    output = AnswerKitOutput(
        index=index,
        answer_cards=answer_cards,
        status_block_markdown=status_block,
        briefings=briefings,
        lookup_transcripts=lookup_transcripts,
        portal_html=portal,
        manifest_rows=manifest_rows,
        validation_rows=(),
    )
    validation_rows = validate_answer_kit(output, repo_root, include_determinism=False) if include_validation else ()
    return AnswerKitOutput(
        index=index,
        answer_cards=answer_cards,
        status_block_markdown=status_block,
        briefings=briefings,
        lookup_transcripts=lookup_transcripts,
        portal_html=portal,
        manifest_rows=manifest_rows,
        validation_rows=validation_rows,
    )


def write_artifacts(output: AnswerKitOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    out_dir = artifacts_dir if artifacts_dir is not None else REPO_ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths: dict[str, Path] = {}
    for role, basename in P381_ARTIFACT_BASENAMES.items():
        path = out_dir / basename
        path.write_text(contents[role], encoding="utf-8")
        paths[role] = path
    return paths


def _print_csv(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def _print_answer(output: AnswerKitOutput, answer_id: str) -> int:
    cards = _cards_by_id(output.answer_cards)
    if answer_id not in cards:
        raise SystemExit(f"unknown answer_id: {answer_id}")
    print(cards[answer_id]["copy_paste_text"])
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P381 Big Lotto no-DB regression archive answer kit")
    parser.add_argument("--artifacts-dir", type=Path, default=None)
    parser.add_argument("--generate", action="store_true", help="Write all P381 answer kit artifacts.")
    parser.add_argument("--answers", action="store_true", help="Print answer cards JSON.")
    parser.add_argument("--status-block", action="store_true", help="Print Worker handoff status block Markdown.")
    parser.add_argument("--briefings", action="store_true", help="Print briefing drafts JSON.")
    parser.add_argument("--lookup-transcripts", action="store_true", help="Print lookup transcripts JSON.")
    parser.add_argument("--portal", action="store_true", help="Print self-contained answer portal HTML.")
    parser.add_argument("--answer", choices=ANSWER_IDS, default=None, help="Print one copy-paste answer by answer_id.")
    parser.add_argument("--validate", action="store_true", help="Print validation CSV.")
    args = parser.parse_args(argv)

    output = run_answer_kit(include_validation=True)
    if args.generate:
        paths = write_artifacts(output, args.artifacts_dir)
        first = run_answer_kit(include_validation=False)
        second = run_answer_kit(include_validation=False)
        determinism = "PASS" if _artifact_contents(first) == _artifact_contents(second) else "FAIL"
        print(f"P381 regression archive answer kit artifacts written: {len(paths)}")
        print(f"determinism double-run {determinism}")
        print(f"answers={len(ANSWER_IDS)} lookup_transcripts={len(LOOKUP_TRANSCRIPT_IDS)} sources={output.index['counts']['source_artifacts']}")
        print(NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT)
    elif args.answers:
        print(_json_text(output.answer_cards), end="")
    elif args.status_block:
        print(output.status_block_markdown, end="")
    elif args.briefings:
        print(_json_text(output.briefings), end="")
    elif args.lookup_transcripts:
        print(_json_text(output.lookup_transcripts), end="")
    elif args.portal:
        print(output.portal_html, end="")
    elif args.answer:
        return _print_answer(output, args.answer)
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_answer_kit(output))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
