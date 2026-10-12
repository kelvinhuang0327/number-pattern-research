"""Build the committed P545C R4 strategy-draw opportunity registry.

The sole row source is the isolated P545F SQLite snapshot.  The generator
verifies the pinned file identity before opening exactly one immutable,
read-only connection.  ``PRAGMA integrity_check`` is the first SQL statement.
All windows come from the frozen P273A anchors; snapshot-latest windows are
never used.

The output is research evidence only.  It does not modify a database, select a
strategy, make a prediction, or provide betting advice.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis import p273a_prize_aware_inferential_validation as inference
from lottery_api.prize_aware_replay_adapter import (
    EXCLUSION_MISSING_PREDICTED_SECOND_ZONE,
    _check_eligibility,
    map_replay_row_to_scorer_input,
)
from lottery_api.prize_aware_scorer import score_prize_aware_ticket


TASK_ID = "P545C_R4_COMMITTED_STRATEGY_DRAW_OPPORTUNITY_REGISTRY"
SCHEMA = "p545c_r4_strategy_draw_opportunity_registry.compact.v1"
EXPANDED_SCHEMA = "p545c_r4_strategy_draw_opportunity_registry.v1"
CLASSIFICATION = "research_only_committed_non_db_opportunity_registry"
FROZEN_COMMIT = "b3dbca40a96cfc81f25b291b396ed265a1301a0a"
SNAPSHOT_FILENAME = (
    "lottery_v2_post_p540b_202607091604_sha256_a9994f5d75e6_p545f.db"
)
SNAPSHOT_SIZE = 99_368_960
SNAPSHOT_SHA256 = (
    "a9994f5d75e6024f3fd9b7af1d23de4a1189516e5df9a494fefd75978e2cd87d"
)
SCHEMA_FINGERPRINT = (
    "a08e78b9cf24fb97bb62d5d11c347464ab3c116b600e356b34e7dbbd9d7fb343"
)
PRIMARY_PATH = "outputs/research/p273a_primary_window_observed_counts_20260615.json"
IDENTITY_PATH = "outputs/research/p273a_distinct_ticket_identity_20260615.json"
INFERENCE_PATH = "outputs/research/p273a_prize_aware_inferential_validation_20260615.json"
ROSTER_PATH = "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json"
SOURCE_SHA256 = {
    PRIMARY_PATH: "14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73",
    IDENTITY_PATH: "b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0",
    INFERENCE_PATH: "ab923a06327afcc8595f224e65bcd98fec0cfdeaf31b10aeeb86ac54ed6648fe",
    ROSTER_PATH: "3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241",
}
FROZEN_INPUTS = (
    ("frozen_roster", ROSTER_PATH),
    ("replay_exporter", "analysis/p273a_prizeaware_replay_export.py"),
    ("primary_exporter", "analysis/p273a_primary_window_observed_counts_export.py"),
    ("identity_exporter", "analysis/p273a_distinct_ticket_identity_export.py"),
    ("eligibility_adapter", "lottery_api/prize_aware_replay_adapter.py"),
    ("prize_aware_scorer", "lottery_api/prize_aware_scorer.py"),
    ("identity_artifact", IDENTITY_PATH),
    ("primary_counts", PRIMARY_PATH),
    ("inferential_validation", INFERENCE_PATH),
    ("endpoint_contract", "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json"),
    ("official_outcomes", "outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"),
    ("committed_outcome_registry", "outputs/research/p545a_readonly_official_outcomes_registry_20260710.json"),
)
PINNED_FROZEN_HASHES = {
    IDENTITY_PATH: "b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0",
    PRIMARY_PATH: "14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73",
    INFERENCE_PATH: "ab923a06327afcc8595f224e65bcd98fec0cfdeaf31b10aeeb86ac54ed6648fe",
    ROSTER_PATH: "3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241",
    "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json": "73517f8be239a5638489b1b6291e2bb6a382b59be82d353e63916472939329ab",
    "outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl": "f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8",
    "outputs/research/p545a_readonly_official_outcomes_registry_20260710.json": "a787c025579de924f9b37b0e43fbda2526c36e157561f8f0b39fa913a55287c8",
}
WINDOW_ORDER = ((50, "SHORT"), (300, "MID"), (750, "LONG"))
ZERO_IDENTITY_CELLS = {
    ("POWER_LOTTO", "fourier_rhythm_3bet"),
    ("POWER_LOTTO", "power_fourier_rhythm_2bet"),
    ("POWER_LOTTO", "power_orthogonal_5bet"),
    ("POWER_LOTTO", "power_precision_3bet"),
}

DEFAULT_SNAPSHOT = Path(
    "/Users/kelvin/Kelvin-WorkSpace/LotteryNew.evidence/P545F"
) / SNAPSHOT_FILENAME
DEFAULT_JSON = Path(
    "outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json"
)
DEFAULT_MARKDOWN = Path(
    "outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.md"
)


class RegistryError(RuntimeError):
    """Fail-closed P545C R4 generation error."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    candidate = dict(payload)
    candidate.pop("canonical_payload_digest", None)
    return _digest(candidate)


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return _canonical_bytes(payload) + b"\n"


def normalize_calendar_date(raw: Any) -> str:
    """Accept only YYYY/MM/DD or YYYY-MM-DD and return canonical ISO date."""
    if not isinstance(raw, str):
        raise RegistryError(f"date is not a string: {raw!r}")
    match = re.fullmatch(r"(\d{4})([-/])(\d{2})\2(\d{2})", raw)
    if match is None:
        raise RegistryError(f"unauthorized date representation: {raw!r}")
    try:
        value = dt.date(
            int(match.group(1)), int(match.group(3)), int(match.group(4))
        )
    except ValueError as exc:
        raise RegistryError(f"invalid calendar date: {raw!r}") from exc
    return value.isoformat()


def _load_pinned_json(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = repo_root / relative_path
    observed = _file_sha256(path)
    expected = SOURCE_SHA256[relative_path]
    if observed != expected:
        raise RegistryError(
            f"source hash mismatch for {relative_path}: {observed} != {expected}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RegistryError(f"{relative_path} is not a JSON object")
    return value


def _git_output(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RegistryError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def frozen_input_manifest(repo_root: Path) -> list[dict[str, Any]]:
    manifest = []
    for role, path in FROZEN_INPUTS:
        raw = _git_output(repo_root, "cat-file", "blob", f"{FROZEN_COMMIT}:{path}")
        observed = hashlib.sha256(raw).hexdigest()
        pinned = PINNED_FROZEN_HASHES.get(path)
        if pinned is not None and observed != pinned:
            raise RegistryError(
                f"frozen input hash mismatch for {path}: {observed} != {pinned}"
            )
        manifest.append(
            {
                "role": role,
                "path": path,
                "pinned_commit": FROZEN_COMMIT,
                "sha256": observed,
                "byte_size": len(raw),
                "provenance_status": "VERIFIED_LOCAL_GIT_BLOB",
            }
        )
    return manifest


def implementation_metadata(repo_root: Path) -> dict[str, str]:
    commit = _git_output(repo_root, "rev-parse", "HEAD").decode().strip()
    raw_timestamp = _git_output(
        repo_root, "show", "-s", "--format=%cI", commit
    ).decode().strip()
    parsed = dt.datetime.fromisoformat(raw_timestamp)
    if parsed.tzinfo is None:
        raise RegistryError("implementation-base timestamp has no timezone")
    generated = parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat(
        timespec="seconds"
    )
    return {
        "implementation_base_commit": commit,
        "generated_at_utc": generated,
        "generated_at_policy": "implementation base commit committer timestamp normalized to UTC seconds",
    }


def verify_snapshot_preopen(path: Path) -> dict[str, Any]:
    if path.name != SNAPSHOT_FILENAME:
        raise RegistryError(f"unauthorized snapshot filename: {path.name}")
    if not path.is_file() or path.is_symlink():
        raise RegistryError("snapshot must be a regular non-symlink file")
    stat = path.stat()
    if stat.st_size != SNAPSHOT_SIZE:
        raise RegistryError(
            f"snapshot size {stat.st_size} != pinned {SNAPSHOT_SIZE}"
        )
    observed = _file_sha256(path)
    if observed != SNAPSHOT_SHA256:
        raise RegistryError(
            f"snapshot SHA-256 {observed} != pinned {SNAPSHOT_SHA256}"
        )
    sidecars = [
        str(Path(str(path) + suffix))
        for suffix in ("-wal", "-shm", "-journal")
        if Path(str(path) + suffix).exists()
    ]
    if sidecars:
        raise RegistryError(f"snapshot sidecars present: {sidecars}")
    return {
        "filename": path.name,
        "size_bytes": stat.st_size,
        "sha256": observed,
        "mode_octal": format(stat.st_mode & 0o7777, "04o"),
        "inode": stat.st_ino,
        "mtime_ns": stat.st_mtime_ns,
    }


def _authorizer(denied: list[tuple[Any, ...]]):
    write_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_ANALYZE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_TRANSACTION,
    }
    approved_pragmas = {
        "integrity_check",
        "query_only",
        "temp_store",
        "database_list",
        "table_info",
        "schema_version",
        "user_version",
    }
    approved_tables = {"strategy_prediction_replays", "draws", "sqlite_master"}

    def callback(action: int, arg1: str, arg2: str, database: str, trigger: str):
        if action in write_actions:
            denied.append((action, arg1, arg2, database, trigger))
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_PRAGMA and str(arg1).lower() not in approved_pragmas:
            denied.append((action, arg1, arg2, database, trigger))
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1 not in approved_tables:
            denied.append((action, arg1, arg2, database, trigger))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return callback


def _schema_fingerprint(connection: sqlite3.Connection) -> tuple[str, dict[str, Any]]:
    required = {
        "strategy_prediction_replays": (
            "lottery_type",
            "target_draw",
            "strategy_id",
            "bet_index",
            "history_cutoff_draw",
            "predicted_numbers",
            "predicted_special",
            "actual_numbers",
            "actual_special",
            "replay_status",
            "dry_run",
        ),
        "draws": ("id", "lottery_type", "draw", "date", "numbers", "special"),
    }
    definitions: dict[str, str] = {}
    inventory: dict[str, Any] = {}
    for table, columns in required.items():
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if row is None or row[0] is None:
            raise RegistryError(f"required table missing: {table}")
        definitions[table] = " ".join(row[0].split())
        info = connection.execute(f"PRAGMA table_info({table})").fetchall()
        present = [item[1] for item in info]
        missing = [column for column in columns if column not in present]
        if missing:
            raise RegistryError(f"{table} missing required columns: {missing}")
        inventory[table] = [
            {
                "cid": item[0],
                "name": item[1],
                "type": item[2],
                "not_null": item[3],
                "default": item[4],
                "primary_key_position": item[5],
            }
            for item in info
        ]
    source = "\n".join(
        f"{table}::{definitions[table]}" for table in sorted(definitions)
    )
    observed = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if observed != SCHEMA_FINGERPRINT:
        raise RegistryError(
            f"schema fingerprint {observed} != pinned {SCHEMA_FINGERPRINT}"
        )
    return observed, inventory


def _row_dict(raw: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "source_row_id": raw[0],
        "lottery_type": raw[1],
        "target_draw": raw[2],
        "strategy_id": raw[3],
        "bet_index": raw[4],
        "history_cutoff_draw": raw[5],
        "predicted_numbers": raw[6],
        "predicted_special": raw[7],
        "actual_numbers": raw[8],
        "actual_special": raw[9],
        "replay_status": raw[10],
        "dry_run": raw[11],
        "_join_count": raw[12],
    }


def _parse_numbers(raw: Any) -> list[int]:
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise RegistryError(f"invalid number array: {raw!r}")
    return value


def _identity(row: Mapping[str, Any]) -> dict[str, Any]:
    content: dict[str, Any] = {
        "main_numbers": sorted(_parse_numbers(row["predicted_numbers"]))
    }
    if row["lottery_type"] == "POWER_LOTTO":
        content["predicted_second_zone"] = row["predicted_special"]
    return {
        "canonical_ticket_content": content,
        "fingerprint_sha256": _digest(content),
    }


def _distribution(values: Iterable[int]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(Counter(values).items())}


def _compare(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RegistryError(f"{label} mismatch")


INFERENCE_VALUE_FIELDS = (
    "expected_successes",
    "wilson_ci_95",
    "clopper_pearson_ci_95",
    "raw_p_value_one_sided_upper",
    "raw_p_value_one_sided_lower",
    "bonferroni_p_value",
    "bonferroni_p_value_lower",
    "statistical_status",
    "window_decision",
)


def normalized_inference_block(window: Mapping[str, Any]) -> dict[str, Any]:
    if "evaluable" not in window or "support_status" not in window:
        raise RegistryError("inferential window lacks authoritative support status")
    evaluable = bool(window["evaluable"])
    support_status = window["support_status"]
    if evaluable and support_status != "SUFFICIENT":
        raise RegistryError("evaluable window contradicts support status")
    if not evaluable and support_status == "SUFFICIENT":
        raise RegistryError("unevaluable window contradicts support status")
    recorded_presence = window.get("source_field_presence")
    if recorded_presence is not None and not isinstance(recorded_presence, Mapping):
        raise RegistryError("source_field_presence must be an object")
    presence = {}
    values = {}
    omitted = []
    for field in INFERENCE_VALUE_FIELDS:
        if recorded_presence is not None:
            state = recorded_presence.get(field)
            if state not in {"absent", "present-null", "present-value"}:
                raise RegistryError(f"invalid source presence for {field}: {state!r}")
            presence[field] = state
            values[field] = window.get(field)
            if state != "present-value":
                omitted.append(field)
        elif field not in window:
            presence[field] = "absent"
            values[field] = None
            omitted.append(field)
        elif window[field] is None:
            presence[field] = (
                "absent"
                if not evaluable and window.get("inferential_omission_reason")
                else "present-null"
            )
            values[field] = None
            omitted.append(field)
        else:
            presence[field] = "present-value"
            values[field] = window[field]
    if evaluable and omitted:
        raise RegistryError(f"evaluable window omits inferential fields: {omitted}")
    for field in (
        "raw_p_value_one_sided_upper",
        "raw_p_value_one_sided_lower",
        "bonferroni_p_value",
        "bonferroni_p_value_lower",
    ):
        value = values[field]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise RegistryError(f"invalid p-value {field}={value!r}")
    for field in ("wilson_ci_95", "clopper_pearson_ci_95"):
        value = values[field]
        if value is not None and (
            not isinstance(value, list)
            or len(value) != 2
            or any(
                isinstance(bound, bool) or not isinstance(bound, (int, float))
                for bound in value
            )
            or not 0.0 <= float(value[0]) <= float(value[1]) <= 1.0
        ):
            raise RegistryError(f"invalid confidence interval {field}={value!r}")
    omission_reason = None
    if omitted:
        omission_reason = f"UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:{support_status}"
    return {
        "evaluable": evaluable,
        "support_status": support_status,
        "source_field_presence": presence,
        "values": values,
        "omitted_fields": omitted,
        "omission_reason": omission_reason,
        "normalization_applied": bool(omitted),
        "source_artifact_reference": INFERENCE_PATH,
    }


def _outcome_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": record["outcome_id"],
        "lottery_type": record["lottery_type"],
        "target_draw": record["target_draw"],
        "raw_date": record.get("raw_date", record.get("draw_date_raw")),
        "canonical_date": record.get(
            "canonical_date", record.get("draw_date")
        ),
        "main_numbers": record["main_numbers"],
        "auxiliary": record["auxiliary"],
        "source_row_id": record.get("source_row_id", record.get("draw_pk")),
        "outcome_sha256": record["outcome_sha256"],
    }


def semantic_projection(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Return a layout- and reference-index-independent evidence projection."""
    compact = registry.get("schema") == SCHEMA
    source_cells = registry["cells"] if compact else registry["roster"]
    cells = [
        {
            "cell_id": cell.get(
                "cell_id", f"{cell['lottery_type']}:{cell['strategy_id']}"
            ),
            "lottery_type": cell["lottery_type"],
            "strategy_id": cell["strategy_id"],
            "expected_bet_indices": cell["expected_bet_indices"],
        }
        for cell in source_cells
    ]
    outcomes = [_outcome_projection(record) for record in registry["official_outcomes"]]
    outcomes_by_id = {record["outcome_id"]: record for record in outcomes}
    if len(outcomes_by_id) != len(outcomes):
        raise RegistryError("duplicate official outcome id")

    if compact:
        source_attempts = registry["attempts"]
        provenance_by_id = {
            item["provenance_id"]: item["value"]
            for item in registry["provenance_records"]
        }
        attempts = []
        for attempt in source_attempts:
            opportunity_id = attempt["opportunity_id"]
            outcome_id = opportunity_id.split(":", 1)[0] + ":" + opportunity_id.rsplit(":", 1)[1]
            outcome = outcomes_by_id[outcome_id]
            attempts.append(
                {
                    "attempt_id": attempt["attempt_id"],
                    "opportunity_id": opportunity_id,
                    "source_row_id": attempt["source_row_id"],
                    "bet_index": attempt["bet_index"],
                    "predicted_main_numbers": attempt["predicted_main_numbers"],
                    "predicted_auxiliary": attempt["predicted_auxiliary"],
                    "actual_main_numbers": outcome["main_numbers"],
                    "actual_auxiliary": (
                        None
                        if outcome["lottery_type"] == "DAILY_539"
                        else outcome["auxiliary"]
                    ),
                    "history_cutoff_draw": attempt["history_cutoff_draw"],
                    "replay_status": attempt["replay_status"],
                    "dry_run": attempt["dry_run"],
                    "draw_join_count": attempt["draw_join_count"],
                    "eligible": attempt["eligible"],
                    "exclusion_reason": attempt["exclusion_reason"],
                    "ticket_identity": attempt["ticket_identity"],
                    "score": attempt["score"],
                    "provenance": provenance_by_id[attempt["provenance_ref"]],
                    "attempt_sha256": attempt["attempt_sha256"],
                }
            )
        opportunity_source = registry["opportunities"]
    else:
        attempts = []
        for opportunity in registry["opportunities"]:
            for attempt in opportunity["attempts"]:
                attempts.append(
                    {
                        "attempt_id": f"{opportunity['opportunity_id']}:{attempt['bet_index']}",
                        "opportunity_id": opportunity["opportunity_id"],
                        "source_row_id": attempt["source_row_id"],
                        "bet_index": attempt["bet_index"],
                        "predicted_main_numbers": attempt["predicted_main_numbers"],
                        "predicted_auxiliary": attempt["predicted_auxiliary"],
                        "actual_main_numbers": attempt["actual_main_numbers"],
                        "actual_auxiliary": attempt["actual_auxiliary"],
                        "history_cutoff_draw": attempt["history_cutoff_draw"],
                        "replay_status": attempt["replay_status"],
                        "dry_run": attempt["dry_run"],
                        "draw_join_count": attempt["draw_join_count"],
                        "eligible": attempt["eligible"],
                        "exclusion_reason": attempt["exclusion_reason"],
                        "ticket_identity": attempt["ticket_identity"],
                        "score": attempt["score"],
                        "provenance": attempt["provenance"],
                        "attempt_sha256": attempt["record_sha256"],
                    }
                )
        opportunity_source = registry["opportunities"]

    opportunities = []
    for record in opportunity_source:
        opportunities.append(
            {
                "opportunity_id": record["opportunity_id"],
                "cell_id": record["cell_id"],
                "outcome_id": record.get(
                    "outcome_id", record.get("official_outcome_ref")
                ),
                "target_draw": record["target_draw"],
                "window_membership": (
                    record["window_membership"]
                    if "window_membership" in record
                    else [
                        label
                        for bit, label in ((1, "SHORT"), (2, "MID"), (4, "LONG"))
                        if record["window_mask"] & bit
                    ]
                ),
                "gross_attempt_count": record["gross_attempt_count"],
                "eligible_attempt_count": record["eligible_attempt_count"],
                "excluded_attempt_count": record["excluded_attempt_count"],
                "supported": record["supported"],
                "all_attempts_excluded": record["all_attempts_excluded"],
                "exclusion_by_reason": record["exclusion_by_reason"],
                "observed_bet_indices": record["observed_bet_indices"],
                "missing_expected_bet_indices": record[
                    "missing_expected_bet_indices"
                ],
                "unexpected_bet_indices": record["unexpected_bet_indices"],
                "same_key_duplicate_count": record.get(
                    "same_key_duplicate_count", record.get("same_key_duplicate_rows")
                ),
                "identical_content_collapse_count": record[
                    "identical_content_collapse_count"
                ],
                "cross_index_duplicate_ticket_count": record[
                    "cross_index_duplicate_ticket_count"
                ],
                "same_index_conflict_count": record["same_index_conflict_count"],
                "opportunity_sha256": record["opportunity_sha256"],
            }
        )

    windows = []
    for record in registry["window_reconciliation"]:
        inference_block = (
            record["inference"]
            if "inference" in record
            else normalized_inference_block(record)
        )
        windows.append(
            {
                "lottery_type": record["lottery_type"],
                "strategy_id": record["strategy_id"],
                "window": record["window"],
                "window_label": record["window_label"],
                "latest_target_draw": record["latest_target_draw"],
                "earliest_target_draw": record["earliest_target_draw"],
                "draw_set_sha256": record["draw_set_sha256"],
                "gross_attempts": record["gross_attempts"],
                "eligible_attempts": record["eligible_attempts"],
                "excluded_attempts": record["excluded_attempts"],
                "support_draws": record["support_draws"],
                "observed_successes": record["observed_successes"],
                "exclusion_by_reason": record["exclusion_by_reason"],
                "distinct_ticket_count_distribution": record[
                    "distinct_ticket_count_distribution"
                ],
                "duplicate_content_draw_count": record[
                    "duplicate_content_draw_count"
                ],
                "inference": inference_block,
                "inferential_record_sha256": record[
                    "inferential_record_sha256"
                ],
            }
        )
    projection = {
        "cells": sorted(cells, key=lambda item: item["cell_id"]),
        "official_outcomes": sorted(
            outcomes, key=lambda item: item["outcome_id"]
        ),
        "attempts": sorted(attempts, key=lambda item: item["attempt_id"]),
        "opportunities": sorted(
            opportunities, key=lambda item: item["opportunity_id"]
        ),
        "window_reconciliation": sorted(
            windows,
            key=lambda item: (
                item["lottery_type"],
                item["strategy_id"],
                item["window"],
            ),
        ),
        "global_summary": registry["global_summary"],
        "snapshot_sha256": registry["snapshot_source"]["sha256"],
        "frozen_contract_commit": registry["frozen_contract_commit"],
        "canonical_database_opened": registry["safety"][
            "canonical_database_opened"
        ],
    }
    return projection


def semantic_projection_digest(registry: Mapping[str, Any]) -> str:
    return _digest(semantic_projection(registry))


def compact_registry(
    expanded: Mapping[str, Any],
    blocked_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    provenance_values = sorted(
        {
            _canonical_bytes(attempt["provenance"])
            for opportunity in expanded["opportunities"]
            for attempt in opportunity["attempts"]
        }
    )
    provenance_records = []
    provenance_id_by_bytes = {}
    for index, raw in enumerate(provenance_values):
        provenance_id = f"provenance:{index}"
        value = json.loads(raw.decode("utf-8"))
        provenance_records.append(
            {"provenance_id": provenance_id, "value": value}
        )
        provenance_id_by_bytes[raw] = provenance_id

    outcomes = [_outcome_projection(record) for record in expanded["official_outcomes"]]
    attempts = []
    opportunities = []
    for opportunity in expanded["opportunities"]:
        start = len(attempts)
        for attempt in opportunity["attempts"]:
            attempts.append(
                {
                    "attempt_id": f"{opportunity['opportunity_id']}:{attempt['bet_index']}",
                    "opportunity_id": opportunity["opportunity_id"],
                    "source_row_id": attempt["source_row_id"],
                    "bet_index": attempt["bet_index"],
                    "predicted_main_numbers": attempt["predicted_main_numbers"],
                    "predicted_auxiliary": attempt["predicted_auxiliary"],
                    "history_cutoff_draw": attempt["history_cutoff_draw"],
                    "replay_status": attempt["replay_status"],
                    "dry_run": attempt["dry_run"],
                    "draw_join_count": attempt["draw_join_count"],
                    "eligible": attempt["eligible"],
                    "exclusion_reason": attempt["exclusion_reason"],
                    "ticket_identity": attempt["ticket_identity"],
                    "score": attempt["score"],
                    "provenance_ref": provenance_id_by_bytes[
                        _canonical_bytes(attempt["provenance"])
                    ],
                    "attempt_sha256": attempt["record_sha256"],
                }
            )
        mask = sum(
            bit
            for bit, label in ((1, "SHORT"), (2, "MID"), (4, "LONG"))
            if label in opportunity["window_membership"]
        )
        opportunities.append(
            {
                "opportunity_id": opportunity["opportunity_id"],
                "cell_id": opportunity["cell_id"],
                "outcome_id": opportunity["official_outcome_ref"],
                "target_draw": opportunity["target_draw"],
                "window_mask": mask,
                "gross_attempt_count": opportunity["gross_attempt_count"],
                "eligible_attempt_count": opportunity["eligible_attempt_count"],
                "excluded_attempt_count": opportunity["excluded_attempt_count"],
                "supported": opportunity["supported"],
                "all_attempts_excluded": opportunity["all_attempts_excluded"],
                "exclusion_by_reason": opportunity["exclusion_by_reason"],
                "observed_bet_indices": opportunity["observed_bet_indices"],
                "missing_expected_bet_indices": opportunity[
                    "missing_expected_bet_indices"
                ],
                "unexpected_bet_indices": opportunity[
                    "unexpected_bet_indices"
                ],
                "same_key_duplicate_count": opportunity[
                    "same_key_duplicate_rows"
                ],
                "identical_content_collapse_count": opportunity[
                    "identical_content_collapse_count"
                ],
                "cross_index_duplicate_ticket_count": opportunity[
                    "cross_index_duplicate_ticket_count"
                ],
                "same_index_conflict_count": opportunity[
                    "same_index_conflict_count"
                ],
                "attempt_start": start,
                "attempt_count": len(opportunity["attempts"]),
                "opportunity_sha256": opportunity["opportunity_sha256"],
            }
        )

    windows_by_cell: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for window in expanded["window_reconciliation"]:
        windows_by_cell[
            f"{window['lottery_type']}:{window['strategy_id']}"
        ].append(window)
    endpoint_by_lottery = {
        "DAILY_539": "D539_ANY_PRIZE_AWARE_WIN",
        "BIG_LOTTO": "BIG_ANY_PRIZE_AWARE_WIN",
        "POWER_LOTTO": "POWER_ANY_PRIZE_AWARE_WIN",
    }
    cells = []
    for roster in expanded["roster"]:
        cell_id = f"{roster['lottery_type']}:{roster['strategy_id']}"
        cell_windows = sorted(
            windows_by_cell[cell_id], key=lambda item: item["window"]
        )
        cells.append(
            {
                "cell_id": cell_id,
                "lottery_type": roster["lottery_type"],
                "strategy_id": roster["strategy_id"],
                "declared_bet_count": len(roster["expected_bet_indices"]),
                "expected_bet_indices": roster["expected_bet_indices"],
                "window_anchors": [
                    {
                        "window": item["window"],
                        "window_label": item["window_label"],
                        "latest_target_draw": item["latest_target_draw"],
                        "earliest_target_draw": item["earliest_target_draw"],
                        "draw_set_sha256": item["draw_set_sha256"],
                    }
                    for item in cell_windows
                ],
                "endpoint_id": endpoint_by_lottery[roster["lottery_type"]],
                "source_references": {
                    "roster": ROSTER_PATH,
                    "primary": PRIMARY_PATH,
                    "identity": IDENTITY_PATH,
                    "inference": INFERENCE_PATH,
                },
            }
        )

    windows = []
    for record in expanded["window_reconciliation"]:
        windows.append(
            {
                "lottery_type": record["lottery_type"],
                "strategy_id": record["strategy_id"],
                "window": record["window"],
                "window_label": record["window_label"],
                "latest_target_draw": record["latest_target_draw"],
                "earliest_target_draw": record["earliest_target_draw"],
                "draw_set_sha256": record["draw_set_sha256"],
                "gross_attempts": record["gross_attempts"],
                "eligible_attempts": record["eligible_attempts"],
                "excluded_attempts": record["excluded_attempts"],
                "support_draws": record["support_draws"],
                "observed_successes": record["observed_successes"],
                "exclusion_by_reason": record["exclusion_by_reason"],
                "distinct_ticket_count_distribution": record[
                    "distinct_ticket_count_distribution"
                ],
                "duplicate_content_draw_count": record[
                    "duplicate_content_draw_count"
                ],
                "inference": normalized_inference_block(record),
                "primary_reconciliation": record["primary_reconciliation"],
                "identity_reconciliation": record["identity_reconciliation"],
                "inferential_reconciliation": record[
                    "inferential_reconciliation"
                ],
                "inferential_record_sha256": record[
                    "inferential_record_sha256"
                ],
                "source_artifact_references": record[
                    "source_artifact_references"
                ],
            }
        )

    compact = {
        "schema": SCHEMA,
        "task_id": expanded["task_id"],
        "classification": expanded["classification"],
        "generated_at_utc": expanded["generated_at_utc"],
        "generated_at_policy": expanded["generated_at_policy"],
        "implementation_base_commit": expanded["implementation_base_commit"],
        "frozen_contract_commit": expanded["frozen_contract_commit"],
        "snapshot_source": expanded["snapshot_source"],
        "input_artifacts": expanded["input_artifacts"],
        "physical_schema_mapping": expanded["physical_schema_mapping"],
        "date_normalization": expanded["date_normalization"],
        "frozen_window_policy": {
            **expanded["frozen_window_policy"],
            "window_mask_bits": {"SHORT": 1, "MID": 2, "LONG": 4},
        },
        "provenance_records": provenance_records,
        "cells": cells,
        "official_outcomes": outcomes,
        "attempts": attempts,
        "opportunities": opportunities,
        "window_reconciliation": windows,
        "global_summary": expanded["global_summary"],
        "semantic_equivalence": dict(blocked_metadata),
        "safety": expanded["safety"],
        "limitations": expanded["limitations"],
        "reconciliation": expanded["reconciliation"],
        "zero_identity_power_lotto": expanded["zero_identity_power_lotto"],
        "postfreeze_correction": expanded["postfreeze_correction"],
        "sql_audit": expanded["sql_audit"],
    }
    compact["canonical_payload_digest"] = canonical_payload_digest(compact)
    return compact


def _window_draws(
    connection: sqlite3.Connection,
    lottery: str,
    expected_window: Mapping[str, Any],
) -> list[dict[str, Any]]:
    earliest = int(expected_window["earliest_target_draw"])
    latest = int(expected_window["latest_target_draw"])
    rows = connection.execute(
        "SELECT id, draw, date, numbers, special FROM draws "
        "WHERE lottery_type=? AND CAST(draw AS INTEGER) BETWEEN ? AND ? "
        "ORDER BY CAST(draw AS INTEGER) DESC",
        (lottery, earliest, latest),
    ).fetchall()
    if len(rows) != expected_window["window"]:
        raise RegistryError(
            f"{lottery} w{expected_window['window']} has {len(rows)} official draws"
        )
    result = []
    for row in rows:
        result.append(
            {
                "draw_pk": row[0],
                "target_draw": row[1],
                "draw_date_raw": row[2],
                "draw_date": normalize_calendar_date(row[2]),
                "main_numbers": _parse_numbers(row[3]),
                "auxiliary": row[4],
            }
        )
    if (
        result[0]["target_draw"] != expected_window["latest_target_draw"]
        or result[-1]["target_draw"] != expected_window["earliest_target_draw"]
    ):
        raise RegistryError("official draw anchors differ from P273A")
    return result


def _aggregate_primary(
    lottery: str,
    strategy: str,
    expected: Mapping[str, Any],
    draw_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    support = sum(record["supported"] for record in draw_records)
    observed = sum(record["observed_success"] for record in draw_records)
    eligible = sum(record["eligible_attempts"] for record in draw_records)
    excluded = sum(record["excluded_attempts"] for record in draw_records)
    reasons = sum(
        (Counter(record["exclusion_by_reason"]) for record in draw_records),
        Counter(),
    )
    bet_counts = [record["eligible_attempts"] for record in draw_records if record["supported"]]
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "window": expected["window"],
        "requested_window": expected["window"],
        "support_draws": support,
        "observed_successes": observed,
        "observed_success_rate": observed / support if support else None,
        "scoreable_rows": eligible,
        "excluded_rows": excluded,
        "excluded_missing_special_rows": reasons.get(
            EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0
        ),
        "exclusion_by_reason": dict(sorted(reasons.items())),
        "bet_count_min": min(bet_counts) if bet_counts else None,
        "bet_count_max": max(bet_counts) if bet_counts else None,
        "bet_count_constant": len(set(bet_counts)) <= 1 if bet_counts else None,
        "bet_count_distribution": _distribution(bet_counts),
        "distinct_draws_in_window": len(draw_records),
        "latest_target_draw": draw_records[0]["target_draw"],
        "earliest_target_draw": draw_records[-1]["target_draw"],
        "endpoint_id": expected["endpoint_id"],
        "endpoint_source_ref": "P271A",
        "strategy_source_ref": "P267C",
        "window_label": expected["window_label"],
    }


def _aggregate_identity(
    lottery: str,
    strategy: str,
    expected: Mapping[str, Any],
    draw_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    supported = [record for record in draw_records if record["supported"]]
    reasons = sum(
        (Counter(record["exclusion_by_reason"]) for record in draw_records),
        Counter(),
    )
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "window": expected["window"],
        "window_label": expected["window_label"],
        "requested_window": expected["window"],
        "distinct_draws_in_window": len(draw_records),
        "support_draws": len(supported),
        "eligible_bet_index_count_distribution": _distribution(
            record["eligible_attempts"] for record in supported
        ),
        "distinct_ticket_count_distribution": _distribution(
            record["distinct_ticket_count"] for record in supported
        ),
        "duplicate_content_draw_count": sum(
            record["duplicate_ticket_count"] > 0 for record in supported
        ),
        "total_duplicate_ticket_content_count": sum(
            record["duplicate_ticket_count"] for record in supported
        ),
        "excluded_rows": sum(record["excluded_attempts"] for record in draw_records),
        "excluded_missing_special_rows": reasons.get(
            EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0
        ),
        "exclusion_by_reason": dict(sorted(reasons.items())),
        "latest_target_draw": draw_records[0]["target_draw"],
        "earliest_target_draw": draw_records[-1]["target_draw"],
    }


def build_registry(
    snapshot_path: Path,
    repo_root: Path,
) -> tuple[dict[str, Any], str]:
    source_identity = verify_snapshot_preopen(snapshot_path)
    inputs = frozen_input_manifest(repo_root)
    implementation = implementation_metadata(repo_root)
    primary = _load_pinned_json(repo_root, PRIMARY_PATH)
    identity_expected = _load_pinned_json(repo_root, IDENTITY_PATH)
    inference_expected = _load_pinned_json(repo_root, INFERENCE_PATH)
    roster = _load_pinned_json(repo_root, ROSTER_PATH)
    max_bets = {
        (item["lottery_type"], item["strategy_id"]): int(item["stored_max_bets"])
        for item in roster["results"]
    }
    primary_by_key = {
        (cell["lottery_type"], cell["strategy_id"]): cell
        for cell in primary["cells"]
    }
    identity_by_key = {
        (cell["lottery_type"], cell["strategy_id"]): cell
        for cell in identity_expected["cells"]
    }
    if len(max_bets) != 36 or set(max_bets) != set(primary_by_key) or set(max_bets) != set(identity_by_key):
        raise RegistryError("frozen 36-cell roster does not align")

    denied: list[tuple[Any, ...]] = []
    trace: list[str] = []
    uri = f"file:{snapshot_path}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.isolation_level = None
    connection.enable_load_extension(False)
    connection.set_authorizer(_authorizer(denied))
    connection.set_trace_callback(trace.append)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            raise RegistryError(f"integrity_check failed: {integrity!r}")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA temp_store=MEMORY")
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise RegistryError("query_only could not be proven")
        databases = connection.execute("PRAGMA database_list").fetchall()
        if len(databases) != 1 or databases[0][1] != "main" or Path(databases[0][2]) != snapshot_path:
            raise RegistryError(f"unexpected database list: {databases!r}")
        schema_fingerprint, schema_inventory = _schema_fingerprint(connection)

        draw_set_cache: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
        official_outcomes: dict[tuple[str, str], dict[str, Any]] = {}
        for cell in primary["cells"]:
            lottery = cell["lottery_type"]
            for window in cell["windows"]:
                key = (
                    lottery,
                    int(window["earliest_target_draw"]),
                    int(window["latest_target_draw"]),
                )
                if key not in draw_set_cache:
                    draw_set_cache[key] = _window_draws(connection, lottery, window)
                for outcome in draw_set_cache[key]:
                    outcome_key = (lottery, outcome["target_draw"])
                    prior = official_outcomes.setdefault(outcome_key, outcome)
                    if prior != outcome:
                        raise RegistryError(f"conflicting official outcome {outcome_key}")

        query = (
            "SELECT r.rowid,r.lottery_type,r.target_draw,r.strategy_id,r.bet_index,"
            "r.history_cutoff_draw,r.predicted_numbers,r.predicted_special,"
            "r.actual_numbers,r.actual_special,r.replay_status,r.dry_run,"
            "(SELECT COUNT(*) FROM draws d WHERE d.lottery_type=r.lottery_type "
            "AND d.draw=r.target_draw) AS join_count "
            "FROM strategy_prediction_replays r "
            "WHERE r.lottery_type=? AND r.strategy_id=? "
            "AND r.replay_status='PREDICTED' AND r.dry_run=0 "
            "ORDER BY CAST(r.target_draw AS INTEGER) DESC,r.bet_index ASC"
        )
        opportunities: list[dict[str, Any]] = []
        generated_primary_cells = []
        generated_identity_cells = []
        window_registry = []
        same_key_duplicates = 0
        cross_index_duplicates = 0
        conflicts = 0
        postfreeze_rows = []

        for expected_cell in primary["cells"]:
            lottery = expected_cell["lottery_type"]
            strategy = expected_cell["strategy_id"]
            cell_key = (lottery, strategy)
            expected_identity_cell = identity_by_key[cell_key]
            long_expected = next(
                window for window in expected_cell["windows"] if window["window"] == 750
            )
            lower = int(long_expected["earliest_target_draw"])
            upper = int(long_expected["latest_target_draw"])
            all_rows = [_row_dict(row) for row in connection.execute(query, cell_key).fetchall()]
            if cell_key == ("DAILY_539", "acb_markov_midfreq_3bet"):
                postfreeze_rows = [
                    {
                        "target_draw": row["target_draw"],
                        "bet_index": row["bet_index"],
                    }
                    for row in all_rows
                    if 115000122 <= int(row["target_draw"]) <= 115000165
                ]
                if len(postfreeze_rows) != 44 or {row["bet_index"] for row in postfreeze_rows} != {1}:
                    raise RegistryError("post-freeze 44-draw correction proof failed")
            rows = [
                row for row in all_rows if lower <= int(row["target_draw"]) <= upper
            ]
            grouped: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(
                lambda: defaultdict(list)
            )
            for row in rows:
                grouped[row["target_draw"]][row["bet_index"]].append(row)
            long_draw_key = (lottery, lower, upper)
            long_draws = draw_set_cache[long_draw_key]
            draw_record_by_id: dict[str, dict[str, Any]] = {}
            expected_indices = list(range(1, max_bets[cell_key] + 1))

            for outcome in long_draws:
                target_draw = outcome["target_draw"]
                candidates = grouped.get(target_draw)
                if candidates is None:
                    raise RegistryError(f"missing source rows for {cell_key}/{target_draw}")
                if sorted(candidates) != expected_indices:
                    raise RegistryError(
                        f"bet-index coverage mismatch for {cell_key}/{target_draw}"
                    )
                attempts = []
                eligible_by_index = {}
                exclusion_counter: Counter[str] = Counter()
                for bet_index in expected_indices:
                    same_index = candidates[bet_index]
                    same_key_duplicates += max(0, len(same_index) - 1)
                    identities = {}
                    reasons = []
                    for row in same_index:
                        eligible, reason = _check_eligibility(row)
                        if eligible:
                            identity = _identity(row)
                            identities[_canonical_bytes(identity["canonical_ticket_content"])] = (
                                identity,
                                row,
                            )
                        else:
                            reasons.append(reason or "UNKNOWN_EXCLUSION")
                    if len(identities) > 1:
                        conflicts += 1
                        raise RegistryError(
                            f"same-index content conflict for {cell_key}/{target_draw}/{bet_index}"
                        )
                    row = same_index[0]
                    eligible, reason = _check_eligibility(row)
                    score = None
                    ticket_identity = None
                    if eligible:
                        score = score_prize_aware_ticket(
                            **map_replay_row_to_scorer_input(row)
                        )
                        ticket_identity = _identity(row)
                        eligible_by_index[bet_index] = ticket_identity
                    else:
                        exclusion_counter[reason or "UNKNOWN_EXCLUSION"] += 1
                    actual_main = _parse_numbers(row["actual_numbers"])
                    if actual_main != outcome["main_numbers"]:
                        raise RegistryError(
                            f"replay/official main outcome mismatch for {cell_key}/{target_draw}"
                        )
                    official_aux = outcome["auxiliary"]
                    if lottery == "DAILY_539":
                        if row["actual_special"] is not None:
                            raise RegistryError("DAILY_539 actual auxiliary must be null")
                    elif row["actual_special"] != official_aux:
                        raise RegistryError(
                            f"replay/official auxiliary mismatch for {cell_key}/{target_draw}"
                        )
                    attempt = {
                        "source_row_id": row["source_row_id"],
                        "bet_index": bet_index,
                        "history_cutoff_draw": row["history_cutoff_draw"],
                        "predicted_main_numbers": _parse_numbers(row["predicted_numbers"]),
                        "predicted_auxiliary": row["predicted_special"],
                        "actual_main_numbers": actual_main,
                        "actual_auxiliary": row["actual_special"],
                        "replay_status": row["replay_status"],
                        "dry_run": row["dry_run"],
                        "draw_join_count": row["_join_count"],
                        "eligible": eligible,
                        "exclusion_reason": reason,
                        "ticket_identity": ticket_identity,
                        "provenance": {
                            "source_table": "strategy_prediction_replays",
                            "snapshot_sha256": SNAPSHOT_SHA256,
                            "base_query_status": "PREDICTED_NON_DRY_RUN",
                        },
                        "score": (
                            {
                                "main_hit_count": score["main_hit_count"],
                                "special_hit": score["special_hit"],
                                "prize_tier": score["prize_tier"],
                                "any_prize_aware_win": score["any_prize_aware_win"],
                            }
                            if score is not None
                            else None
                        ),
                    }
                    attempt["record_sha256"] = _digest(attempt)
                    attempts.append(attempt)
                content_groups: dict[bytes, list[int]] = defaultdict(list)
                for bet_index, value in eligible_by_index.items():
                    content_groups[
                        _canonical_bytes(value["canonical_ticket_content"])
                    ].append(bet_index)
                duplicate_ticket_count = sum(
                    len(indexes) - 1 for indexes in content_groups.values()
                )
                cross_index_duplicates += duplicate_ticket_count
                observed_success = any(
                    attempt["score"] is not None
                    and attempt["score"]["any_prize_aware_win"]
                    for attempt in attempts
                )
                opportunity = {
                    "opportunity_id": f"{lottery}:{strategy}:{target_draw}",
                    "cell_id": f"{lottery}:{strategy}",
                    "lottery_type": lottery,
                    "strategy_id": strategy,
                    "declared_bet_count": max_bets[cell_key],
                    "target_draw": target_draw,
                    "target_draw_numeric": int(target_draw),
                    "raw_draw_date": outcome["draw_date_raw"],
                    "canonical_draw_date": outcome["draw_date"],
                    "official_outcome_ref": f"{lottery}:{target_draw}",
                    "window_membership": [],
                    "in_short_window": False,
                    "in_mid_window": False,
                    "in_long_window": True,
                    "window_anchor_group": {
                        "latest_target_draw": long_expected["latest_target_draw"],
                        "earliest_long_target_draw": long_expected[
                            "earliest_target_draw"
                        ],
                    },
                    "expected_bet_indices": expected_indices,
                    "gross_attempts": len(attempts),
                    "gross_attempt_count": len(attempts),
                    "eligible_attempts": sum(attempt["eligible"] for attempt in attempts),
                    "eligible_attempt_count": sum(
                        attempt["eligible"] for attempt in attempts
                    ),
                    "excluded_attempts": sum(not attempt["eligible"] for attempt in attempts),
                    "excluded_attempt_count": sum(
                        not attempt["eligible"] for attempt in attempts
                    ),
                    "supported": any(attempt["eligible"] for attempt in attempts),
                    "all_attempts_excluded": not any(
                        attempt["eligible"] for attempt in attempts
                    ),
                    "observed_success": observed_success,
                    "exclusion_by_reason": dict(sorted(exclusion_counter.items())),
                    "observed_bet_indices": sorted(candidates),
                    "missing_expected_bet_indices": sorted(
                        set(expected_indices) - set(candidates)
                    ),
                    "unexpected_bet_indices": sorted(
                        set(candidates) - set(expected_indices)
                    ),
                    "distinct_ticket_count": len(content_groups),
                    "duplicate_ticket_count": duplicate_ticket_count,
                    "same_key_duplicate_rows": sum(
                        max(0, len(candidates[index]) - 1) for index in expected_indices
                    ),
                    "identical_content_collapse_count": 0,
                    "cross_index_duplicate_ticket_count": duplicate_ticket_count,
                    "same_index_conflict_count": 0,
                    "attempts": attempts,
                }
                opportunity["opportunity_sha256"] = _digest(opportunity)
                draw_record_by_id[target_draw] = opportunity
                opportunities.append(opportunity)

            primary_windows = []
            identity_windows = []
            for expected_window in expected_cell["windows"]:
                window_key = (
                    lottery,
                    int(expected_window["earliest_target_draw"]),
                    int(expected_window["latest_target_draw"]),
                )
                selected_ids = [
                    outcome["target_draw"] for outcome in draw_set_cache[window_key]
                ]
                selected = [draw_record_by_id[target] for target in selected_ids]
                for record in selected:
                    record["window_membership"].append(expected_window["window_label"])
                    record[
                        f"in_{expected_window['window_label'].lower()}_window"
                    ] = True
                    record["opportunity_sha256"] = _digest(
                        {
                            key: value
                            for key, value in record.items()
                            if key != "opportunity_sha256"
                        }
                    )
                primary_window = _aggregate_primary(
                    lottery, strategy, expected_window, selected
                )
                _compare(
                    f"primary {cell_key}/w{expected_window['window']}",
                    primary_window,
                    expected_window,
                )
                expected_identity_window = next(
                    item
                    for item in expected_identity_cell["windows"]
                    if item["window"] == expected_window["window"]
                )
                identity_window = _aggregate_identity(
                    lottery, strategy, expected_window, selected
                )
                _compare(
                    f"identity {cell_key}/w{expected_window['window']}",
                    identity_window,
                    {
                        key: value
                        for key, value in expected_identity_window.items()
                        if key != "artifact_alignment"
                    },
                )
                primary_windows.append(primary_window)
                identity_windows.append(
                    {
                        **identity_window,
                        "artifact_alignment": expected_identity_window[
                            "artifact_alignment"
                        ],
                    }
                )
            supported_draws = []
            for target_draw in [outcome["target_draw"] for outcome in long_draws]:
                opportunity = draw_record_by_id[target_draw]
                if not opportunity["supported"]:
                    continue
                groups = defaultdict(list)
                identity_map = {}
                for attempt in opportunity["attempts"]:
                    if not attempt["eligible"]:
                        continue
                    ticket_identity = attempt["ticket_identity"]
                    key_bytes = _canonical_bytes(
                        ticket_identity["canonical_ticket_content"]
                    )
                    groups[key_bytes].append(attempt["bet_index"])
                    identity_map[key_bytes] = ticket_identity
                canonical_groups = []
                for key_bytes in sorted(groups):
                    ticket_identity = identity_map[key_bytes]
                    indexes = sorted(groups[key_bytes])
                    canonical_groups.append(
                        {
                            "canonical_ticket_content": ticket_identity[
                                "canonical_ticket_content"
                            ],
                            "fingerprint_sha256": ticket_identity[
                                "fingerprint_sha256"
                            ],
                            "bet_index_values": indexes,
                            "group_multiplicity": len(indexes),
                        }
                    )
                supported_draws.append(
                    {
                        "lottery_type": lottery,
                        "strategy_id": strategy,
                        "target_draw": target_draw,
                        "eligible_bet_index_count": opportunity["eligible_attempts"],
                        "distinct_ticket_count": opportunity["distinct_ticket_count"],
                        "duplicate_ticket_count": opportunity["duplicate_ticket_count"],
                        "excluded_rows": opportunity["excluded_attempts"],
                        "excluded_missing_special_rows": opportunity[
                            "exclusion_by_reason"
                        ].get(EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0),
                        "exclusion_by_reason": opportunity["exclusion_by_reason"],
                        "canonical_ticket_groups": canonical_groups,
                    }
                )
            _compare(
                f"supported identity draws {cell_key}",
                supported_draws,
                expected_identity_cell["supported_draws"],
            )
            generated_primary_cells.append(
                {
                    "lottery_type": lottery,
                    "strategy_id": strategy,
                    "distinct_draws_available": expected_cell[
                        "distinct_draws_available"
                    ],
                    "windows": primary_windows,
                }
            )
            generated_identity_cells.append(
                {
                    "lottery_type": lottery,
                    "strategy_id": strategy,
                    "distinct_draws_available": expected_identity_cell[
                        "distinct_draws_available"
                    ],
                    "identity_scope_max_primary_window": 750,
                    "same_bet_index_duplicate_rows_collapsed": 0,
                    "supported_draws": supported_draws,
                    "windows": identity_windows,
                }
            )

        generated_primary = {
            (cell["lottery_type"], cell["strategy_id"]): cell
            for cell in generated_primary_cells
        }
        generated_identity = {
            (cell["lottery_type"], cell["strategy_id"]): cell
            for cell in generated_identity_cells
        }
        groups = []
        for lottery in inference.LOTTERIES:
            for strategy in inference.FROZEN_STRATEGY_CELLS[lottery]:
                key = (lottery, strategy)
                groups.append(
                    inference.evaluate_group(
                        lottery,
                        strategy,
                        generated_primary[key],
                        generated_identity[key],
                    )
                )
        evaluable_index = []
        raw_pvalues = []
        for group_index, group in enumerate(groups):
            for window_index, window in enumerate(group["windows"]):
                if window["evaluable"]:
                    evaluable_index.append((group_index, window_index))
                    raw_pvalues.append(float(window["raw_p_value_one_sided_upper"]))
        for (group_index, window_index), flag in zip(
            evaluable_index, inference.benjamini_hochberg(raw_pvalues)
        ):
            groups[group_index]["windows"][window_index][
                "bh_fdr_descriptive_reject"
            ] = bool(flag)
        for group in groups:
            for window in group["windows"]:
                window.setdefault("bh_fdr_descriptive_reject", None)
        _compare("full inferential groups", groups, inference_expected["inference"]["groups"])

        inference_index = {
            (group["lottery_type"], group["strategy_id"], window["window"]): window
            for group in groups
            for window in group["windows"]
        }
        inference_group_index = {
            (group["lottery_type"], group["strategy_id"]): group
            for group in groups
        }
        for cell in generated_primary_cells:
            lottery = cell["lottery_type"]
            strategy = cell["strategy_id"]
            identity_cell = generated_identity[(lottery, strategy)]
            for primary_window, identity_window in zip(
                cell["windows"], identity_cell["windows"]
            ):
                inferential = inference_index[
                    (lottery, strategy, primary_window["window"])
                ]
                evaluable = bool(inferential["evaluable"])
                required_when_evaluable = (
                    "expected_successes",
                    "wilson_ci_95",
                    "clopper_pearson_ci_95",
                    "raw_p_value_one_sided_upper",
                    "raw_p_value_one_sided_lower",
                    "bonferroni_p_value",
                    "bonferroni_p_value_lower",
                    "statistical_status",
                    "window_decision",
                )
                if evaluable:
                    missing_inference = [
                        field
                        for field in required_when_evaluable
                        if field not in inferential or inferential[field] is None
                    ]
                    if missing_inference:
                        raise RegistryError(
                            f"evaluable inferential window missing fields: "
                            f"{lottery}/{strategy}/w{primary_window['window']} "
                            f"{missing_inference}"
                        )
                    omission_reason = None
                else:
                    omission_reason = (
                        "UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:"
                        + str(inferential["support_status"])
                    )
                draw_key = (
                    lottery,
                    int(primary_window["earliest_target_draw"]),
                    int(primary_window["latest_target_draw"]),
                )
                draw_ids = [
                    item["target_draw"] for item in draw_set_cache[draw_key]
                ]
                inferential_group = inference_group_index[(lottery, strategy)]
                source_field_presence = {
                    field: (
                        "absent"
                        if field not in inferential
                        else (
                            "present-null"
                            if inferential[field] is None
                            else "present-value"
                        )
                    )
                    for field in INFERENCE_VALUE_FIELDS
                }
                window_registry.append(
                    {
                        "lottery_type": lottery,
                        "strategy_id": strategy,
                        "window": primary_window["window"],
                        "window_label": primary_window["window_label"],
                        "latest_target_draw": primary_window["latest_target_draw"],
                        "earliest_target_draw": primary_window["earliest_target_draw"],
                        "draw_set_sha256": _digest(draw_ids),
                        "gross_attempts": primary_window["scoreable_rows"]
                        + primary_window["excluded_rows"],
                        "eligible_attempts": primary_window["scoreable_rows"],
                        "excluded_attempts": primary_window["excluded_rows"],
                        "support_draws": primary_window["support_draws"],
                        "observed_successes": primary_window["observed_successes"],
                        "exclusion_by_reason": primary_window["exclusion_by_reason"],
                        "distinct_ticket_count_distribution": identity_window[
                            "distinct_ticket_count_distribution"
                        ],
                        "duplicate_content_draw_count": identity_window[
                            "duplicate_content_draw_count"
                        ],
                        "evaluable": evaluable,
                        "source_field_presence": source_field_presence,
                        "inferential_omission_reason": omission_reason,
                        "expected_successes": inferential.get("expected_successes"),
                        "wilson_ci_95": inferential.get("wilson_ci_95"),
                        "clopper_pearson_ci_95": inferential.get(
                            "clopper_pearson_ci_95"
                        ),
                        "raw_p_value_one_sided_upper": inferential.get(
                            "raw_p_value_one_sided_upper"
                        ),
                        "raw_p_value_one_sided_lower": inferential.get(
                            "raw_p_value_one_sided_lower"
                        ),
                        "bonferroni_p_value": inferential.get(
                            "bonferroni_p_value"
                        ),
                        "bonferroni_p_value_lower": inferential.get(
                            "bonferroni_p_value_lower"
                        ),
                        "support_status": inferential["support_status"],
                        "statistical_status": inferential.get("statistical_status"),
                        "window_decision": inferential.get("window_decision"),
                        "stability_status": inferential_group["stability"]["status"],
                        "group_decision": inferential_group[
                            "overall_group_decision"
                        ],
                        "primary_reconciliation": "PASS",
                        "identity_reconciliation": "PASS",
                        "inferential_reconciliation": "PASS",
                        "inferential_record_sha256": _digest(inferential),
                        "source_artifact_references": {
                            "primary": PRIMARY_PATH,
                            "identity": IDENTITY_PATH,
                            "inference": INFERENCE_PATH,
                        },
                    }
                )

        opportunities.sort(
            key=lambda record: (
                list(inference.LOTTERIES).index(record["lottery_type"]),
                record["strategy_id"],
                -int(record["target_draw"]),
            )
        )
        outcomes = []
        for (lottery, target_draw), outcome in sorted(
            official_outcomes.items(),
            key=lambda item: (
                list(inference.LOTTERIES).index(item[0][0]),
                -int(item[0][1]),
            ),
        ):
            record = {
                "outcome_id": f"{lottery}:{target_draw}",
                "lottery_type": lottery,
                "target_draw": target_draw,
                "raw_date": outcome["draw_date_raw"],
                "canonical_date": outcome["draw_date"],
                "source_row_id": outcome["draw_pk"],
                **outcome,
            }
            record["outcome_sha256"] = _digest(record)
            outcomes.append(record)

        totals = {
            "frozen_cells": len(primary_by_key),
            "long_opportunities": len(opportunities),
            "gross_attempts": sum(record["gross_attempts"] for record in opportunities),
            "eligible_attempts": sum(
                record["eligible_attempts"] for record in opportunities
            ),
            "excluded_attempts": sum(
                record["excluded_attempts"] for record in opportunities
            ),
            "supported_opportunities": sum(record["supported"] for record in opportunities),
            "identity_missing_opportunities": sum(
                not record["supported"] for record in opportunities
            ),
            "official_outcomes": len(outcomes),
            "window_records": len(window_registry),
            "same_key_duplicate_rows": same_key_duplicates,
            "cross_index_duplicate_tickets": cross_index_duplicates,
            "same_index_conflicts": conflicts,
        }
        expected_totals = {
            "frozen_cells": 36,
            "long_opportunities": 27_000,
            "gross_attempts": 47_250,
            "eligible_attempts": 33_749,
            "excluded_attempts": 13_501,
            "supported_opportunities": 23_999,
            "identity_missing_opportunities": 3_001,
            "official_outcomes": 2_253,
            "window_records": 108,
            "same_key_duplicate_rows": 0,
            "cross_index_duplicate_tickets": 0,
            "same_index_conflicts": 0,
        }
        _compare("global registry totals", totals, expected_totals)
        if denied:
            raise RegistryError(f"authorizer denied operations: {denied}")
    finally:
        connection.close()

    source_after = verify_snapshot_preopen(snapshot_path)
    _compare("snapshot pre/post identity", source_after, source_identity)
    zero_cells = [
        record
        for record in opportunities
        if (record["lottery_type"], record["strategy_id"]) in ZERO_IDENTITY_CELLS
    ]
    zero_summary = {
        "opportunities": len(zero_cells),
        "gross_attempts": sum(record["gross_attempts"] for record in zero_cells),
        "eligible_attempts": sum(
            record["eligible_attempts"] for record in zero_cells
        ),
        "excluded_attempts": sum(
            record["excluded_attempts"] for record in zero_cells
        ),
        "exclusion_by_reason": dict(
            sorted(
                sum(
                    (
                        Counter(record["exclusion_by_reason"])
                        for record in zero_cells
                    ),
                    Counter(),
                ).items()
            )
        ),
        "row_evidence_sha256": _digest(zero_cells),
        "digest_schema": "p545c_r4_zero_identity_opportunity_records.v1",
        "reported_prior_run_digest": (
            "ca472d8fac5ed3b6fde75812ca0fd3b6d926209a3f73b0036e28117f3b45a5d8"
        ),
        "prior_digest_reproduction_status": (
            "NOT_REPRODUCED_DIFFERENT_REPORTED_CANONICALIZATION"
        ),
    }
    _compare(
        "zero-identity totals",
        {
            key: value
            for key, value in zero_summary.items()
            if key
            not in {
                "row_evidence_sha256",
                "digest_schema",
                "reported_prior_run_digest",
                "prior_digest_reproduction_status",
            }
        },
        {
            "opportunities": 3_000,
            "gross_attempts": 9_750,
            "eligible_attempts": 0,
            "excluded_attempts": 9_750,
            "exclusion_by_reason": {
                EXCLUSION_MISSING_PREDICTED_SECOND_ZONE: 9_750
            },
        },
    )
    registry = {
        "schema": EXPANDED_SCHEMA,
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        **implementation,
        "frozen_contract_commit": FROZEN_COMMIT,
        "snapshot_source": source_identity,
        "input_artifacts": inputs,
        "safety": {
            "sqlite_connection_count": 1,
            "sqlite_uri_mode": "mode=ro&immutable=1",
            "integrity_check_first": True,
            "integrity_check_result": "ok",
            "query_only": True,
            "temp_store_memory": True,
            "extension_loading_disabled": True,
            "canonical_database_opened": False,
            "database_write_performed": False,
            "network_used_for_generation": False,
        },
        "physical_schema_mapping": {
            "schema_fingerprint_sha256": schema_fingerprint,
            "draw_pk": "draws.id",
            "target_draw": "draws.draw",
            "draw_date": "draws.date",
            "lottery_type": "draws.lottery_type",
            "official_main_numbers": "draws.numbers",
            "official_auxiliary": "draws.special",
            "column_inventory": schema_inventory,
        },
        "date_normalization": {
            "accepted_raw_formats": ["YYYY-MM-DD", "YYYY/MM/DD"],
            "canonical_output": "YYYY-MM-DD",
            "raw_values_preserved": True,
            "comparison_only": True,
        },
        "frozen_window_policy": {
            "selection": "exact committed P273A anchors and official draw membership",
            "primary_windows": [50, 300, 750],
            "dynamic_snapshot_latest_selection": False,
        },
        "global_summary": totals,
        "zero_identity_power_lotto": zero_summary,
        "postfreeze_correction": {
            "cell": "DAILY_539/acb_markov_midfreq_3bet",
            "frozen_latest_target_draw": "115000121",
            "postfreeze_range": ["115000122", "115000165"],
            "postfreeze_rows": len(postfreeze_rows),
            "postfreeze_bet_indices": sorted(
                {record["bet_index"] for record in postfreeze_rows}
            ),
            "excluded_from_registry": True,
            "dynamic_window_deficit_explained": 88,
        },
        "reconciliation": {
            "primary_windows": "108/108 PASS",
            "identity_windows": "108/108 PASS",
            "inferential_windows": "108/108 PASS",
            "overall_project_classification_reproduced": inference_expected[
                "overall_project_classification"
            ],
            "inference_summary": inference_expected["summary"],
            "window_registry_sha256": _digest(window_registry),
            "window_digest_schema": "p545c_r4_window_reconciliation_records.v1",
            "reported_prior_run_window_digest": (
                "1fe6b1a580e3377e43a5dadfc7dee4a20a7933b0318ef84329bc086f021d9b12"
            ),
            "prior_window_digest_reproduction_status": (
                "NOT_REPRODUCED_DIFFERENT_REPORTED_CANONICALIZATION"
            ),
            "opportunity_registry_sha256": _digest(opportunities),
            "official_outcome_registry_sha256": _digest(outcomes),
        },
        "roster": [
            {
                "lottery_type": cell["lottery_type"],
                "strategy_id": cell["strategy_id"],
                "expected_bet_indices": list(
                    range(
                        1,
                        max_bets[(cell["lottery_type"], cell["strategy_id"])] + 1,
                    )
                ),
            }
            for cell in primary["cells"]
        ],
        "window_reconciliation": window_registry,
        "official_outcomes": outcomes,
        "opportunities": opportunities,
        "limitations": [
            "Frozen retrospective research evidence only.",
            "No historical database byte-identity claim.",
            "No predictive-validity, production-readiness, ROI, EV, or betting claim.",
            "Registry excludes post-freeze rows and does not resume P545B.",
        ],
        "sql_audit": {
            "connection_count": 1,
            "statement_count": len(trace),
            "first_statement": trace[0] if trace else None,
            "pragmas": [
                statement
                for statement in trace
                if statement.lstrip().upper().startswith("PRAGMA")
            ],
            "tables_read": ["draws", "sqlite_master", "strategy_prediction_replays"],
            "denied_operation_count": len(denied),
            "non_read_attempt_count": 0,
        },
    }
    registry["canonical_payload_digest"] = canonical_payload_digest(registry)
    markdown = render_markdown(registry)
    return registry, markdown


def render_markdown(registry: Mapping[str, Any]) -> str:
    totals = registry["global_summary"]
    zero = registry["zero_identity_power_lotto"]
    equivalence = registry.get("semantic_equivalence", {})
    original_size = equivalence.get("blocked_expanded_json_byte_size")
    compact_size = len(canonical_json_bytes(registry))
    reduction = (
        (1.0 - compact_size / original_size) * 100.0 if original_size else None
    )
    lines = [
        "# P545C R4 — Committed Strategy-Draw Opportunity Registry",
        "",
        "> Research evidence only. This registry is not a prediction, betting recommendation, or production-readiness claim.",
        "",
        "## Classification",
        "",
        f"`{registry['classification']}`",
        "",
        "## Frozen scope",
        "",
        f"- Frozen contract commit: `{registry['frozen_contract_commit']}`",
        f"- Implementation base: `{registry['implementation_base_commit']}`",
        f"- Deterministic timestamp: `{registry['generated_at_utc']}`",
        f"- Snapshot SHA-256: `{registry['snapshot_source']['sha256']}`",
        f"- Frozen cells: **{totals['frozen_cells']:,}**",
        f"- LONG strategy-draw opportunities: **{totals['long_opportunities']:,}**",
        f"- Ticket attempts: **{totals['gross_attempts']:,}**",
        f"- Eligible / excluded attempts: **{totals['eligible_attempts']:,} / {totals['excluded_attempts']:,}**",
        f"- Supported / identity-missing opportunities: **{totals['supported_opportunities']:,} / {totals['identity_missing_opportunities']:,}**",
        f"- Official outcomes: **{totals['official_outcomes']:,}**",
        "",
        "## Reconciliation",
        "",
        "- Primary windows: **108/108 PASS**",
        "- Identity windows: **108/108 PASS**",
        "- Inferential windows: **108/108 PASS**",
        f"- Window registry SHA-256: `{registry['reconciliation']['window_registry_sha256']}`",
        f"- Opportunity registry SHA-256: `{registry['reconciliation']['opportunity_registry_sha256']}`",
        f"- Official outcome registry SHA-256: `{registry['reconciliation']['official_outcome_registry_sha256']}`",
        "",
        "## Compact semantic equivalence",
        "",
        f"- Result: **{equivalence.get('equivalence_result', 'N/A')}**",
        f"- Expanded projection: `{equivalence.get('expanded_semantic_projection_digest', 'N/A')}`",
        f"- Compact projection: `{equivalence.get('compact_semantic_projection_digest', 'N/A')}`",
        f"- Expanded JSON bytes: **{original_size:,}**" if original_size else "- Expanded JSON bytes: N/A",
        f"- Compact JSON bytes: **{compact_size:,}**",
        f"- Size reduction: **{reduction:.2f}%**" if reduction is not None else "- Size reduction: N/A",
        "",
        "## Four zero-identity POWER_LOTTO cells",
        "",
        f"- Opportunities: **{zero['opportunities']:,}**",
        f"- Gross / eligible / excluded: **{zero['gross_attempts']:,} / {zero['eligible_attempts']:,} / {zero['excluded_attempts']:,}**",
        f"- Exclusion reason: `{EXCLUSION_MISSING_PREDICTED_SECOND_ZONE}`",
        f"- Row-evidence SHA-256: `{zero['row_evidence_sha256']}`",
        f"- Prior reported row digest: `{zero['reported_prior_run_digest']}`",
        "",
        "## Safety",
        "",
        "- SQLite connections: **1**",
        "- Open mode: `mode=ro&immutable=1`",
        "- First statement: `PRAGMA integrity_check` → `ok`",
        "- Canonical database opened: **NO**",
        "- Database write performed: **NO**",
        "- Network used for generation: **NO**",
        "",
        "## Limitations and no-claim statement",
        "",
        "- Frozen retrospective research evidence only.",
        "- No historical database byte-identity claim.",
        "- No predictive-validity, production-readiness, ROI, EV, or betting claim.",
        "",
        f"Canonical payload digest: `{registry['canonical_payload_digest']}`",
        "",
    ]
    return "\n".join(lines)


def generate(
    snapshot_path: Path,
    repo_root: Path,
    output_json: Path,
    output_markdown: Path,
) -> dict[str, Any]:
    if not output_json.exists():
        raise RegistryError("blocked expanded JSON is required for equivalence proof")
    blocked_bytes = output_json.read_bytes()
    blocked_sha256 = hashlib.sha256(blocked_bytes).hexdigest()
    blocked = json.loads(blocked_bytes)
    if len(blocked_bytes) != 111_091_815:
        raise RegistryError("blocked expanded JSON byte size changed")
    if blocked_sha256 != "e74c0be30711a410c12ca63006ef6d3d75b79001de100a2ff9fecbd23999da5d":
        raise RegistryError("blocked expanded JSON SHA-256 changed")
    if blocked.get("canonical_payload_digest") != (
        "ba3a19d3ff0474cb080fdecca84387dbf4f5cded959f7b64a6b7a7e47554804d"
    ):
        raise RegistryError("blocked expanded canonical payload digest changed")
    if canonical_payload_digest(blocked) != blocked["canonical_payload_digest"]:
        raise RegistryError("blocked expanded canonical payload digest is invalid")
    blocked_projection_digest = semantic_projection_digest(blocked)

    expanded, _expanded_markdown = build_registry(snapshot_path, repo_root)
    regenerated_projection_digest = semantic_projection_digest(expanded)
    if regenerated_projection_digest != blocked_projection_digest:
        raise RegistryError("regenerated expanded semantic projection differs")
    equivalence = {
        "blocked_expanded_json_byte_size": len(blocked_bytes),
        "blocked_expanded_json_sha256": blocked_sha256,
        "blocked_expanded_canonical_payload_digest": blocked[
            "canonical_payload_digest"
        ],
        "expanded_semantic_projection_digest": blocked_projection_digest,
        "regenerated_expanded_semantic_projection_digest": regenerated_projection_digest,
        "compact_semantic_projection_digest": None,
        "equivalence_result": None,
        "normalization_transformations": [
            "compact UTF-8 JSON serialization",
            "cell descriptors stored once and referenced by cell_id",
            "official outcomes stored once and referenced by outcome_id",
            "attempts flattened and referenced by stable start/count ranges",
            "attempt provenance deduplicated by provenance_ref",
            "official actual values resolved through outcome references",
            "window membership encoded as documented bit mask",
            "unevaluable inferential omissions normalized to explicit null metadata",
        ],
        "deduplicated_fields": [
            "lottery_type and strategy_id from opportunities",
            "official outcome values from attempts",
            "repeated provenance objects from attempts",
            "nested attempts from opportunities",
        ],
    }
    registry = compact_registry(expanded, equivalence)
    compact_projection_digest = semantic_projection_digest(registry)
    if compact_projection_digest != blocked_projection_digest:
        raise RegistryError("compact semantic projection differs from expanded")
    registry["semantic_equivalence"][
        "compact_semantic_projection_digest"
    ] = compact_projection_digest
    registry["semantic_equivalence"]["equivalence_result"] = "PASS"
    registry["canonical_payload_digest"] = canonical_payload_digest(registry)
    markdown = render_markdown(registry)
    first_json = canonical_json_bytes(registry)
    second_json = canonical_json_bytes(registry)
    first_markdown = markdown.encode("utf-8")
    second_markdown = render_markdown(registry).encode("utf-8")
    if first_json != second_json:
        raise RegistryError("two-build JSON determinism check failed")
    if first_markdown != second_markdown:
        raise RegistryError("two-build Markdown determinism check failed")
    if len(first_json) >= 83_886_080:
        raise RegistryError(
            f"compact JSON remains too large: {len(first_json)} bytes"
        )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_bytes(first_json)
    output_markdown.write_bytes(first_markdown)
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    registry = generate(
        args.snapshot.resolve(),
        args.repo_root.resolve(),
        args.output_json,
        args.output_markdown,
    )
    print(
        json.dumps(
            {
                "task_id": registry["task_id"],
                "totals": registry["global_summary"],
                "canonical_payload_digest": registry["canonical_payload_digest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
