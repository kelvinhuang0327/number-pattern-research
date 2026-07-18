#!/usr/bin/env python3
"""Existing-logic randomness audit orchestration and cadence evaluation.

This module does not define a statistical methodology.  It supplies the
canonical BIG_LOTTO population through an enforced SQLite read-only path and
then calls P246K's committed audit runner unchanged.  The historical 44-test
artifact remains immutable legacy evidence because its producing source is not
committed in this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import socket
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Mapping, Optional, Sequence
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import p238b_nist_randomness_audit_artifact_build as p238b  # noqa: E402


TASK_ID = "P691_RANDOMNESS_EXISTING_LOGIC_TRANSFER_R1"
SCHEMA_VERSION = "2.0"
AUDIT_TYPE = "EXISTING_LOGIC_MIGRATION"
LOGICAL_DB_IDENTITY = "canonical_big_lotto_store"
CADENCE_MAX_CALENDAR_DAYS = 14
CADENCE_MAX_NEW_DRAWS = 50

P238B_SOURCE = REPO_ROOT / "scripts" / "p238b_nist_randomness_audit_artifact_build.py"
P246K_SOURCE = REPO_ROOT / "analysis" / "p246k_canonical_big_lotto_nist_reaudit.py"
DEFAULT_RESULTS_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_results.json"
DEFAULT_SUMMARY_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
DEFAULT_WIKI_PATH = REPO_ROOT / "wiki" / "system" / "randomness_final_verdict.md"

CANONICAL_VIEW_NAME = "draws_big_lotto_canonical_main"
CANONICAL_POPULATION_SQL = """SELECT draw, date, numbers, special
FROM draws_big_lotto_canonical_main
ORDER BY CAST(draw AS INTEGER) DESC, draw DESC"""
RAW_POPULATION_COUNT_SQL = "SELECT COUNT(*) FROM draws WHERE lottery_type = ?"
RAW_POPULATION_COUNT_PARAMS = ("BIG_LOTTO",)

ROW_STREAM_SERIALIZATION = (
    "UTF-8 JSON Lines; each row has draw/date/numbers/special; "
    "keys sorted; compact separators; SQL result order"
)

LEGACY_TOP_LEVEL_KEYS = (
    "run_timestamp",
    "re_attestation_timestamp",
    "reanalysis_performed",
    "new_draws_analyzed",
    "re_attestation_type",
    "re_attestation_basis",
    "simulations",
    "seed",
    "alpha",
    "games",
    "tests",
    "multiple_testing",
    "final_verdict",
    "strategy_implication",
)
LEGACY_CANONICAL_SHA256 = "24283ecaae136c17ab3447f2b9b49555e87aaff44c9fc58bee909108eee51b90"

P246K_SEMANTIC_KEYS = (
    "classification",
    "raw_population_count",
    "canonical_population_count",
    "excluded_add_on_count",
    "exclusion_rules_verified",
    "audit_methods",
    "audit_results",
)

P246K_CHECK_PATHS = (
    ("draw_sum_distribution",),
    ("number_frequency_uniformity",),
    ("serial_randomness", "runs_test"),
    ("serial_randomness", "ljung_box_lag10"),
    ("entropy",),
)

P246K_REQUIRED_AUDIT_METHODS = {
    "draw_sum_ks_test": "KS test vs normal distribution",
    "number_frequency_chi2": "Chi-square uniformity test (pool_size=49, k=6)",
    "runs_test": "Runs test on above/below-mean draw sums",
    "ljung_box_lag10": "Ljung-Box autocorrelation test (lag=10)",
    "shannon_entropy": "Normalized Shannon entropy of number frequencies",
    "per_position_analysis": "Mean/range of sorted-position numbers",
    "era_stability": "Per-year sum mean — temporal stability check",
}

HISTORICAL_DATE_CONFLICT = {
    "wiki_historical_date": "2026-05-01",
    "preserved_historical_artifact_date": "2026-06-02",
    "protected_historical_producer_status": "ABSENT",
    "wiki_date_is_currently_reproducible": False,
    "artifact_date_is_currently_reproducible": False,
    "current_existing_logic_migration_is_separate": True,
    "continuity_or_direct_comparability_claimed": False,
    "disclosure": (
        "The wiki historically cited 2026-05-01, while the preserved historical "
        "artifact timestamp is 2026-06-02. The protected historical producer is "
        "absent, so neither historical date represents a currently reproducible "
        "audit. The current executable existing-logic migration is separate; no "
        "continuity or direct comparability is claimed."
    ),
}

WIKI_AUDIT_BEGIN = "<!-- P692_CURRENT_EXECUTABLE_AUDIT_BEGIN -->"
WIKI_AUDIT_END = "<!-- P692_CURRENT_EXECUTABLE_AUDIT_END -->"

LEGACY_SUMMARY_BEGIN = "<!-- P691_LEGACY_44_TEST_SUMMARY_BEGIN -->"
LEGACY_SUMMARY_END = "<!-- P691_LEGACY_44_TEST_SUMMARY_END -->"


class AuditProvenanceError(ValueError):
    """Raised when audit or population provenance cannot be trusted."""


def _reject_duplicate_json_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AuditProvenanceError(f"duplicate JSON object key rejected: {key!r}")
        value[key] = item
    return value


def strict_json_loads(payload: Any, *, source: str) -> Any:
    """Parse one JSON trust boundary while rejecting duplicate object keys."""
    try:
        return json.loads(payload, object_pairs_hook=_reject_duplicate_json_object)
    except AuditProvenanceError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise AuditProvenanceError(f"strict JSON parse failed for {source}") from exc


@dataclass(frozen=True)
class PopulationLoad:
    draws: list[dict[str, Any]]
    raw_count: int
    provenance: dict[str, Any]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _row_stream_bytes(draws: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json_bytes(dict(draw)) + b"\n" for draw in draws)


def _parse_utc_timestamp(value: str, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AuditProvenanceError(f"{field_name} must be a non-empty ISO-8601 timestamp")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AuditProvenanceError(f"{field_name} is not valid ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuditProvenanceError(f"{field_name} must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuditProvenanceError("UTC timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_db_path(db_path: Path) -> Path:
    candidate = db_path.expanduser()
    if not candidate.is_absolute():
        raise AuditProvenanceError("--db must be an absolute path")
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise AuditProvenanceError(f"canonical DB is not an existing regular file: {resolved}")
    return resolved


def _source_implementations() -> list[dict[str, Any]]:
    return [
        {
            "implementation_id": "P246K",
            "role": "canonical BIG_LOTTO statistical controller",
            "source_path": str(P246K_SOURCE.relative_to(REPO_ROOT)),
            "source_sha256": _sha256_file(P246K_SOURCE),
            "entry_symbol": "run_canonical_nist_reaudit",
            "transitive_statistical_symbols": [
                "verify_exclusions",
                "draw_sum_analysis",
                "number_frequency_analysis",
                "serial_randomness_tests",
                "entropy_analysis",
                "per_position_analysis",
                "era_stability",
            ],
            "reuse_mode": "unchanged_through_read_only_population_adapter",
        },
        {
            "implementation_id": "P238B",
            "role": "population-independent SQLite read-only connection helper only",
            "source_path": str(P238B_SOURCE.relative_to(REPO_ROOT)),
            "source_sha256": _sha256_file(P238B_SOURCE),
            "entry_symbol": "_connect_ro",
            "reuse_mode": "unchanged",
            "excluded": [
                "raw BIG_LOTTO population",
                "all P238B statistical helpers",
                "multiple-testing corrections",
                "classification and verdict logic",
                "artifact rendering",
            ],
        },
    ]


def _read_only_connection(db_path: Path) -> sqlite3.Connection:
    """Use P238B's covered helper without participating in WAL shared memory."""
    wal_path = Path(f"{db_path}-wal")
    if wal_path.exists() and wal_path.stat().st_size != 0:
        raise AuditProvenanceError(
            "immutable canonical DB read requires an empty or absent WAL sidecar"
        )

    native_connect = sqlite3.connect

    def immutable_connect(database: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        if kwargs.get("uri") is not True:
            raise AuditProvenanceError("P238B read-only helper did not request URI mode")
        uri = str(database)
        if "?mode=ro" not in uri:
            raise AuditProvenanceError("P238B read-only helper did not request mode=ro")
        return native_connect(f"{uri}&immutable=1&cache=private", *args, **kwargs)

    with patch.object(sqlite3, "connect", side_effect=immutable_connect):
        conn = p238b._connect_ro(db_path)
    try:
        conn.execute("PRAGMA query_only=ON")
        enabled = int(conn.execute("PRAGMA query_only").fetchone()[0])
        if enabled != 1:
            raise AuditProvenanceError("SQLite PRAGMA query_only could not be enabled")
        return conn
    except Exception:
        conn.close()
        raise


def load_canonical_big_lotto_population(db_path: Path) -> PopulationLoad:
    """Load the exact P246K canonical population through read-only SQLite."""
    resolved = _validate_db_path(db_path)
    conn = _read_only_connection(resolved)
    try:
        view = conn.execute(
            "SELECT type FROM sqlite_master WHERE name = ?",
            (CANONICAL_VIEW_NAME,),
        ).fetchone()
        if view is None or str(view["type"]) != "view":
            raise AuditProvenanceError(
                f"required canonical view is missing: {CANONICAL_VIEW_NAME}"
            )
        rows = conn.execute(CANONICAL_POPULATION_SQL).fetchall()
        raw_count = int(
            conn.execute(RAW_POPULATION_COUNT_SQL, RAW_POPULATION_COUNT_PARAMS).fetchone()[0]
        )
    finally:
        conn.close()

    draws: list[dict[str, Any]] = []
    for row in rows:
        numbers = strict_json_loads(
            row["numbers"],
            source=f"canonical row {row['draw']!r} numbers",
        )
        if not isinstance(numbers, list):
            raise AuditProvenanceError(
                f"canonical row {row['draw']!r} numbers JSON must be an array"
            )
        try:
            parsed_numbers = [int(number) for number in numbers]
        except (TypeError, ValueError) as exc:
            raise AuditProvenanceError(
                f"canonical row {row['draw']!r} contains non-numeric numbers"
            ) from exc
        draw = {
            "draw": str(row["draw"]),
            "date": str(row["date"]),
            "numbers": parsed_numbers,
            "special": row["special"],
        }
        draws.append(draw)

    if not draws:
        raise AuditProvenanceError("canonical BIG_LOTTO population is empty")
    if len({draw["draw"] for draw in draws}) != len(draws):
        raise AuditProvenanceError("canonical BIG_LOTTO population has duplicate draw IDs")

    newest = draws[0]
    oldest = draws[-1]
    stream_hash = _sha256_bytes(_row_stream_bytes(draws))
    provenance = {
        "db_identity": LOGICAL_DB_IDENTITY,
        "db_open_mode": "sqlite_uri_mode_ro",
        "sqlite_immutable": True,
        "sqlite_cache": "private",
        "wal_precondition": "empty_or_absent",
        "pragma_query_only": True,
        "selected_population": "BIG_LOTTO/CANONICAL_MAIN_DRAW",
        "canonical_view": CANONICAL_VIEW_NAME,
        "sql": {
            "canonical_population": CANONICAL_POPULATION_SQL,
            "raw_population_count": RAW_POPULATION_COUNT_SQL,
            "raw_population_count_params": list(RAW_POPULATION_COUNT_PARAMS),
        },
        "raw_population_count": raw_count,
        "selected_row_count": len(draws),
        "oldest_selected_row": {"draw": oldest["draw"], "date": oldest["date"]},
        "newest_selected_row": {"draw": newest["draw"], "date": newest["date"]},
        "selected_date_min": min(draw["date"] for draw in draws),
        "selected_date_max": max(draw["date"] for draw in draws),
        "selected_row_stream_serialization": ROW_STREAM_SERIALIZATION,
        "selected_row_stream_sha256": stream_hash,
    }
    return PopulationLoad(draws=draws, raw_count=raw_count, provenance=provenance)


def _load_p246k_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("p246k_existing_logic", P246K_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load P246K source: {P246K_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_p246k_existing_logic(
    population: PopulationLoad,
    db_path: Path,
    *,
    module: Optional[ModuleType] = None,
) -> dict[str, Any]:
    """Call P246K unchanged while replacing only its write-capable loader seam."""
    p246k = module or _load_p246k_module()
    with patch.object(
        p246k,
        "load_canonical_draws",
        return_value=(population.draws, population.raw_count),
    ):
        result = p246k.run_canonical_nist_reaudit(_validate_db_path(db_path))
    if not isinstance(result, dict) or "audit_results" not in result:
        raise AuditProvenanceError("P246K did not return a complete audit result")
    if result.get("canonical_population_count") != len(population.draws):
        raise AuditProvenanceError("P246K result count does not match selected population")
    return result


def _p246k_semantic_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in P246K_SEMANTIC_KEYS if key not in result]
    if missing:
        raise AuditProvenanceError(f"P246K result is missing semantic fields: {missing}")
    return {key: result[key] for key in P246K_SEMANTIC_KEYS}


def _scientific_limitations(p246k_result: Mapping[str, Any]) -> list[dict[str, str]]:
    audit_results = p246k_result.get("audit_results")
    if not isinstance(audit_results, Mapping):
        raise AuditProvenanceError("P246K audit results are unavailable for limitation publication")
    frequency = audit_results.get("number_frequency_uniformity")
    if not isinstance(frequency, Mapping):
        raise AuditProvenanceError("P246K frequency result is unavailable for limitation publication")
    current_max = frequency.get("max_frequency")
    current_min = frequency.get("min_frequency")
    if not _is_positive_int(current_max) or not _is_positive_int(current_min):
        raise AuditProvenanceError("P246K frequency extrema are missing or malformed")
    return [
        {
            "id": "fitted_normal_ks_discrete_sum_calibration",
            "statement": (
                "The fitted-normal KS diagnostic is applied to a discrete draw-sum "
                "distribution and is not a fully calibrated goodness-of-fit proof."
            ),
        },
        {
            "id": "entropy_threshold_not_p_value",
            "statement": "The entropy threshold is not a p-value.",
        },
        {
            "id": "five_diagnostics_no_multiplicity_correction",
            "statement": "The five P246K diagnostics have no multiplicity correction.",
        },
        {
            "id": "power_and_mde_not_established",
            "statement": (
                "Statistical power and minimum-detectable-effect have not been established "
                "for the published five-test diagnostic."
            ),
        },
        {
            "id": "p246k_green_not_randomness_proof",
            "statement": "P246K GREEN does not prove randomness.",
        },
        {
            "id": "historical_frequency_extrema_conflict",
            "statement": (
                "Earlier JSON and Markdown frequency-extrema values were inconsistent "
                "(JSON max/min 285/221; Markdown max/min 284/243). The current migration "
                "preserves both as conflicting historical evidence, selects neither "
                "historical value, and reports the separately recomputed current canonical "
                f"extrema {current_max}/{current_min} only as part of the unchanged P246K "
                "source diagnostic payload."
            ),
        },
    ]


def _p246k_payload_metadata(p246k_result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "UNCHANGED_SOURCE_DIAGNOSTIC_PAYLOAD",
        "statistical_payload_unchanged": True,
        "authoritative_for_proving_randomness": False,
        "equivalent_to_historical_44_test_audit": False,
        "evidence_of_no_exploitable_edge": False,
        "validates_another_lottery": False,
        "authorizes_prediction": False,
        "authorizes_betting": False,
        "scientific_limitations": _scientific_limitations(p246k_result),
    }


def _bounded_current_conclusion(p246k_result: Mapping[str, Any]) -> dict[str, Any]:
    audit_results = p246k_result.get("audit_results")
    summary = audit_results.get("summary") if isinstance(audit_results, Mapping) else None
    if not isinstance(summary, Mapping):
        raise AuditProvenanceError("P246K summary is unavailable for bounded publication")
    total = summary.get("total_tests")
    green = summary.get("green")
    yellow = summary.get("yellow")
    overall = summary.get("overall_status")
    if not _is_positive_int(total):
        raise AuditProvenanceError("P246K bounded conclusion total is malformed")
    if not isinstance(green, int) or isinstance(green, bool) or green < 0:
        raise AuditProvenanceError("P246K bounded conclusion green count is malformed")
    if not isinstance(yellow, int) or isinstance(yellow, bool) or yellow < 0:
        raise AuditProvenanceError("P246K bounded conclusion yellow count is malformed")
    if green + yellow != total or overall not in {"GREEN", "YELLOW"}:
        raise AuditProvenanceError("P246K bounded conclusion is inconsistent")
    return {
        "status": "DIAGNOSTIC_ONLY",
        "p246k_overall_status": overall,
        "total_checks": total,
        "green_checks": green,
        "yellow_checks": yellow,
        "statement": (
            f"The unchanged P246K source diagnostics report {green} GREEN and {yellow} "
            f"YELLOW outcomes across {total} checks for the current canonical BIG_LOTTO "
            "population. This bounded diagnostic result does not prove randomness, "
            "establish absence of an exploitable edge, validate another lottery, or "
            "authorize prediction or betting."
        ),
    }


def _published_p246k_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Remove runtime location while retaining every statistical field unchanged."""
    published = dict(result)
    published.pop("db_path", None)
    published["db_identity"] = LOGICAL_DB_IDENTITY
    return published


def _extract_legacy_payload(existing: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in LEGACY_TOP_LEVEL_KEYS if key not in existing]
    if missing:
        raise AuditProvenanceError(f"legacy 44-test evidence is missing fields: {missing}")
    payload = {key: existing[key] for key in LEGACY_TOP_LEVEL_KEYS}
    actual = _sha256_bytes(_canonical_json_bytes(payload))
    if actual != LEGACY_CANONICAL_SHA256:
        raise AuditProvenanceError(
            "legacy 44-test evidence changed; expected canonical SHA-256 "
            f"{LEGACY_CANONICAL_SHA256}, got {actual}"
        )
    return payload


def extract_legacy_summary(text: str) -> str:
    begin_count = text.count(LEGACY_SUMMARY_BEGIN)
    end_count = text.count(LEGACY_SUMMARY_END)
    if begin_count == 0 and end_count == 0:
        return text
    if begin_count != 1 or end_count != 1:
        raise AuditProvenanceError("legacy summary markers are malformed")
    start = text.index(LEGACY_SUMMARY_BEGIN) + len(LEGACY_SUMMARY_BEGIN)
    if not text.startswith("\n", start):
        raise AuditProvenanceError("legacy summary begin marker must end its own line")
    start += 1
    end = text.index(LEGACY_SUMMARY_END, start)
    return text[start:end]


def build_results_document(
    *,
    existing_results: Mapping[str, Any],
    existing_results_bytes: bytes,
    legacy_summary: str,
    executed_at_utc: datetime,
    population: PopulationLoad,
    p246k_result: Mapping[str, Any],
) -> dict[str, Any]:
    legacy_payload = _extract_legacy_payload(existing_results)
    previous_legacy = existing_results.get("legacy_44_test_evidence", {})
    if previous_legacy and not isinstance(previous_legacy, Mapping):
        raise AuditProvenanceError("legacy_44_test_evidence metadata is malformed")

    original_file_sha = previous_legacy.get(
        "original_artifact_file_sha256",
        _sha256_bytes(existing_results_bytes),
    )
    legacy_summary_sha = _sha256_bytes(legacy_summary.encode("utf-8"))
    previous_summary_sha = previous_legacy.get("original_summary_file_sha256")
    if previous_summary_sha is not None and previous_summary_sha != legacy_summary_sha:
        raise AuditProvenanceError("immutable legacy summary content changed")

    semantic_payload = _p246k_semantic_payload(p246k_result)
    semantic_hash = _sha256_bytes(_canonical_json_bytes(semantic_payload))
    published_p246k = _published_p246k_result(p246k_result)
    executed = _format_utc(executed_at_utc)
    result: dict[str, Any] = dict(legacy_payload)
    result.update(
        {
            "artifact_schema_version": SCHEMA_VERSION,
            "legacy_44_test_evidence": {
                "status": "IMMUTABLE_LEGACY_EVIDENCE",
                "reproducible_from_committed_source": False,
                "historical_confirmatory_test_count": 44,
                "producer_source_status": "scripts/randomness_audit.py was absent for the historical run",
                "immutable_top_level_keys": list(LEGACY_TOP_LEVEL_KEYS),
                "canonical_payload_sha256": LEGACY_CANONICAL_SHA256,
                "original_artifact_file_sha256": original_file_sha,
                "original_summary_file_sha256": legacy_summary_sha,
                "statistical_values_mutated": False,
            },
            "current_executable_audit": {
                "task_id": TASK_ID,
                "audit_type": AUDIT_TYPE,
                "historical_44_test_reproduction": False,
                "executed_at_utc": executed,
                "scope": {
                    "lottery_type": "BIG_LOTTO",
                    "population": "CANONICAL_MAIN_DRAW",
                    "statistical_controller": "P246K",
                },
                "implementation_sources": _source_implementations(),
                "input_provenance": population.provenance,
                "p246k_existing_logic_payload_metadata": _p246k_payload_metadata(
                    published_p246k
                ),
                "p246k_existing_logic_result": published_p246k,
                "p246k_semantic_output_sha256": semantic_hash,
                "current_authoritative_conclusion": _bounded_current_conclusion(
                    published_p246k
                ),
                "historical_date_conflict": dict(HISTORICAL_DATE_CONFLICT),
                "p246k_result_retained_unchanged": True,
                "p246k_nonsemantic_location_sanitized": True,
                "p246k_static_narrative_caveat": (
                    "The unchanged P246K payload contains historical raw-access prose "
                    "referencing 22,238 rows and the legacy aggregate field name "
                    "excluded_add_on_count. They are retained for exact equivalence and "
                    "are not current row-family provenance. Current raw and canonical "
                    "counts are the exact SQL results recorded above: "
                    f"{population.raw_count} and {len(population.draws)}."
                ),
                "cadence_anchor": {
                    "real_executable_audit_timestamp_utc": executed,
                    "canonical_draw_count": len(population.draws),
                    "selected_row_stream_sha256": population.provenance[
                        "selected_row_stream_sha256"
                    ],
                    "oldest_selected_row": population.provenance["oldest_selected_row"],
                    "newest_selected_row": population.provenance["newest_selected_row"],
                },
                "cadence_policy": {
                    "max_calendar_days": CADENCE_MAX_CALENDAR_DAYS,
                    "max_new_canonical_draws": CADENCE_MAX_NEW_DRAWS,
                    "trigger": "whichever_occurs_first",
                    "timestamp_only_re_attestation_is_gating": False,
                },
                "orchestration_additions_only": [
                    "provenance",
                    "cadence",
                    "publication_containment",
                ],
                "new_statistical_procedure_introduced": False,
                "combined_p238b_p246k_verdict": False,
                "db_write_performed": False,
            },
        }
    )
    return result


def _markdown_table_row(values: Sequence[Any]) -> str:
    return "| " + " | ".join(str(value) for value in values) + " |"


def render_summary(document: Mapping[str, Any], legacy_summary: str) -> str:
    current = document["current_executable_audit"]
    provenance = current["input_provenance"]
    p246k_result = current["p246k_existing_logic_result"]
    audit_results = p246k_result["audit_results"]
    summary = audit_results["summary"]
    sources = current["implementation_sources"]
    anchor = current["cadence_anchor"]
    policy = current["cadence_policy"]
    containment = current["p246k_existing_logic_payload_metadata"]
    limitations = containment["scientific_limitations"]
    conclusion = current["current_authoritative_conclusion"]
    date_conflict = current["historical_date_conflict"]
    lines = [
        "# Lottery Randomness Audit Report — Current Executable Path",
        "",
        f"**Current executable audit timestamp (UTC):** {current['executed_at_utc']}",
        f"**Task:** `{current['task_id']}`",
        "**Type:** existing-logic migration; not historical 44-test reproduction",
        "**Current scope:** canonical BIG_LOTTO only; P246K controls statistical behavior",
        (
            "**Unchanged nested P246K diagnostic status (non-authoritative):** "
            f"`{summary['overall_status']}`"
        ),
        f"**Current bounded publication status:** `{conclusion['status']}`",
        "**New statistical procedure introduced:** NO",
        "**Database write performed:** NO",
        "",
        "## Current Executable Audit Result",
        "",
        _markdown_table_row(["Existing P246K check", "Result"]),
        _markdown_table_row(["---", "---"]),
        _markdown_table_row(["Draw-sum KS", audit_results["draw_sum_distribution"]["status"]]),
        _markdown_table_row(["Number-frequency chi-square", audit_results["number_frequency_uniformity"]["status"]]),
        _markdown_table_row(["Runs test", audit_results["serial_randomness"]["runs_test"]["status"]]),
        _markdown_table_row(["Ljung-Box lag 10", audit_results["serial_randomness"]["ljung_box_lag10"]["status"]]),
        _markdown_table_row(["Shannon entropy", audit_results["entropy"]["status"]]),
        "",
        (
            f"P246K summary: **{summary['green']}/{summary['total_tests']} GREEN**, "
            f"**{summary['yellow']} YELLOW**. This is a randomness diagnostic, not a "
            "prediction, strategy, or betting recommendation."
        ),
        conclusion["statement"],
        "",
        "## Canonical Input Provenance",
        "",
        f"- Logical DB identity: `{provenance['db_identity']}`",
        (
            "- SQLite mode: URI `mode=ro&immutable=1&cache=private`; "
            "`PRAGMA query_only=ON` verified; WAL empty/absent precondition enforced"
        ),
        f"- Selected population: `{provenance['selected_population']}`",
        f"- Canonical rows: `{provenance['selected_row_count']}`",
        f"- Raw BIG_LOTTO rows observed: `{provenance['raw_population_count']}`",
        (
            "- P246K compatibility note: its unchanged nested payload retains a historical "
            "22,238-row raw-access sentence and legacy aggregate exclusion field name; the "
            "SQL-derived counts above are the current provenance values."
        ),
        (
            f"- Boundary: `{provenance['oldest_selected_row']['draw']}` through "
            f"`{provenance['newest_selected_row']['draw']}`"
        ),
        f"- Selected-row stream SHA-256: `{provenance['selected_row_stream_sha256']}`",
        f"- P246K semantic output SHA-256: `{current['p246k_semantic_output_sha256']}`",
        "- Exact canonical SQL:",
        "",
        "```sql",
        provenance["sql"]["canonical_population"],
        "```",
        "",
        "## Source Implementations",
        "",
    ]
    for source in sources:
        lines.append(
            f"- `{source['implementation_id']}` `{source['source_path']}::{source['entry_symbol']}` "
            f"SHA-256 `{source['source_sha256']}` — {source['reuse_mode']}"
        )
    lines.extend(
        [
            "",
            "## Non-Authoritative P246K Source Payload",
            "",
            f"- Status: `{containment['status']}`",
            "- The nested payload is retained unchanged as a source diagnostic payload.",
            "- It is non-authoritative for proving randomness.",
            "- It is not equivalent to the historical 44-test audit.",
            "- It is not evidence of no exploitable edge and does not validate another lottery.",
            "- It authorizes neither prediction nor betting.",
            "",
            "## Scientific Limitations",
            "",
        ]
    )
    for index, limitation in enumerate(limitations, start=1):
        lines.append(f"{index}. {limitation['statement']}")
    lines.extend(
        [
            "",
            "## Historical Date-Conflict Disclosure",
            "",
            date_conflict["disclosure"],
        ]
    )
    lines.extend(
        [
            "",
            "## Cadence",
            "",
            (
                f"The next real executable audit is due at **{CADENCE_MAX_CALENDAR_DAYS} "
                f"calendar days** or **{CADENCE_MAX_NEW_DRAWS} new canonical BIG_LOTTO "
                "draws**, whichever occurs first. Timestamp-only re-attestation is "
                "non-gating and resets neither trigger."
            ),
            f"- Executable anchor timestamp: `{anchor['real_executable_audit_timestamp_utc']}`",
            f"- Executable anchor canonical rows: `{anchor['canonical_draw_count']}`",
            f"- Cadence policy identity: `{policy['trigger']}`",
            "- Every future or incompatible executable anchor fails closed.",
            "",
            "## Historical 44-Test Evidence",
            "",
            (
                "The historical 44-test values below are immutable legacy evidence. "
                "Their producing implementation is not committed, so they are not "
                "reproducible from repository source and are not claimed equivalent to "
                "the current P246K executable audit."
            ),
            "",
            LEGACY_SUMMARY_BEGIN,
        ]
    )
    current_text = "\n".join(lines) + "\n"
    return current_text + legacy_summary + LEGACY_SUMMARY_END + "\n"


def _render_wiki_audit_section(document: Mapping[str, Any]) -> str:
    current = document["current_executable_audit"]
    provenance = current["input_provenance"]
    containment = current["p246k_existing_logic_payload_metadata"]
    conclusion = current["current_authoritative_conclusion"]
    date_conflict = current["historical_date_conflict"]
    limitations = containment["scientific_limitations"]
    lines = [
        WIKI_AUDIT_BEGIN,
        "## 3. Randomness Audit Result",
        "",
        f"**Latest real executable audit:** {current['executed_at_utc']}",
        "**Audit script:** `scripts/randomness_audit.py`  ",
        "**Audit outputs:** `outputs/randomness_audit/`  ",
        f"**Current bounded publication status:** `{conclusion['status']}`",
        "",
        conclusion["statement"],
        "",
        "### Canonical input and execution provenance",
        "",
        "- Scope: canonical BIG_LOTTO `CANONICAL_MAIN_DRAW` only.",
        (
            f"- Population: {provenance['selected_row_count']} rows from draw "
            f"`{provenance['oldest_selected_row']['draw']}` through "
            f"`{provenance['newest_selected_row']['draw']}`."
        ),
        f"- Logical store: `{provenance['db_identity']}`.",
        (
            "- SQLite contract: URI `mode=ro&immutable=1&cache=private`; "
            "`PRAGMA query_only=ON`; nonempty WAL fails closed."
        ),
        f"- Selected-row stream SHA-256: `{provenance['selected_row_stream_sha256']}`.",
        f"- P246K semantic output SHA-256: `{current['p246k_semantic_output_sha256']}`.",
        "- No statistic, p-value, threshold, correction, simulation, seed, or verdict value changed.",
        "- P238B contributes only its unchanged population-independent `_connect_ro` helper.",
        "",
        "### Non-authoritative P246K source payload",
        "",
        f"- Status: `{containment['status']}`.",
        "- The nested P246K payload is an unchanged source diagnostic payload.",
        "- It is non-authoritative for proving randomness and is not equivalent to the historical 44-test audit.",
        "- It is not evidence of no exploitable edge, does not validate another lottery, and authorizes neither prediction nor betting.",
        "",
        "### Scientific limitations",
        "",
    ]
    for index, limitation in enumerate(limitations, start=1):
        lines.append(f"{index}. {limitation['statement']}")
    lines.extend(
        [
            "",
            "### Historical date-conflict disclosure",
            "",
            date_conflict["disclosure"],
            "The historical 44-test evidence remains unreproducible from committed source.",
            "",
            "### What this means for research",
            "",
            "- The current publication reports the outcomes of five existing P246K diagnostics only.",
            "- It supplies no prediction signal, strategy authorization, betting recommendation, or cross-lottery validation.",
            "- BIG_LOTTO predictive research remains blocked under its existing governance.",
            WIKI_AUDIT_END,
        ]
    )
    return "\n".join(lines) + "\n"


def render_wiki(document: Mapping[str, Any], existing_wiki: str) -> str:
    """Replace only the governed current-audit section using document evidence."""
    if not isinstance(existing_wiki, str) or not existing_wiki.strip():
        raise AuditProvenanceError("wiki source is empty or malformed")
    section = _render_wiki_audit_section(document)
    if existing_wiki.count(WIKI_AUDIT_BEGIN) == existing_wiki.count(WIKI_AUDIT_END) == 1:
        start = existing_wiki.index(WIKI_AUDIT_BEGIN)
        end = existing_wiki.index(WIKI_AUDIT_END, start) + len(WIKI_AUDIT_END)
        if existing_wiki.startswith("\n", end):
            end += 1
        rendered = existing_wiki[:start] + section + existing_wiki[end:]
    else:
        heading = "## 3. Randomness Audit Result"
        next_section = "\n---\n\n## 4. Edge Discovery Path — Open Under Governance"
        if existing_wiki.count(heading) != 1 or next_section not in existing_wiki:
            raise AuditProvenanceError("wiki current-audit section markers are malformed")
        start = existing_wiki.index(heading)
        end = existing_wiki.index(next_section, start)
        rendered = existing_wiki[:start] + section + existing_wiki[end:]

    old_summary = (
        "| Are canonical BIG_LOTTO draws compatible with randomness under the current "
        "executable audit? | **YES — with qualification** (P246K existing logic: 5/5 "
        "checks GREEN; this is not an exploitable-edge claim) |"
    )
    bounded_summary = (
        "| What did the current canonical BIG_LOTTO audit observe? | **P246K diagnostic: "
        "5/5 GREEN — not proof of randomness and not an exploitable-edge claim** |"
    )
    rendered = rendered.replace(old_summary, bounded_summary)
    rendered = rendered.replace("**Version:** 1.2", "**Version:** 1.3", 1)
    rendered = rendered.replace(
        "--now-utc 2026-07-18T08:43:47Z",
        "--now-utc <evaluation-utc>",
    )
    version_12 = (
        "| 1.2 | 2026-07-18 | Added the existing-logic P246K executable path, separated "
        "immutable/unreproducible legacy 44-test evidence, and anchored cadence to real "
        "execution plus independent canonical draw counts. |"
    )
    version_13 = (
        "| 1.3 | 2026-07-18 | Added strict duplicate-key rejection, complete fail-closed "
        "provenance, bounded P246K containment, six scientific limitations, historical-date "
        "disclosure, and one-timestamp JSON/Markdown/wiki publication. |"
    )
    if version_13 not in rendered:
        rendered = rendered.replace(version_12, version_12 + "\n" + version_13)
    return rendered


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _required_boundary(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise AuditProvenanceError(f"{field_name} is missing")
    if not all(
        isinstance(value.get(key), str) and bool(value.get(key).strip())
        for key in ("draw", "date")
    ):
        raise AuditProvenanceError(f"{field_name} is malformed")
    return value


def _validate_executable_audit_document(
    document: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], datetime]:
    """Validate the exact completed P246K audit contract used by cadence."""
    if not isinstance(document, Mapping) or not document:
        raise AuditProvenanceError("audit document must be a non-empty mapping")
    if document.get("artifact_schema_version") != SCHEMA_VERSION:
        raise AuditProvenanceError("artifact schema is incompatible with executable cadence")

    current = document.get("current_executable_audit")
    if not isinstance(current, Mapping):
        raise AuditProvenanceError("current_executable_audit provenance is missing")
    if current.get("task_id") != TASK_ID or current.get("audit_type") != AUDIT_TYPE:
        raise AuditProvenanceError("current executable audit identity is incompatible")
    if current.get("historical_44_test_reproduction") is not False:
        raise AuditProvenanceError("legacy evidence cannot serve as the executable anchor")
    if current.get("scope") != {
        "lottery_type": "BIG_LOTTO",
        "population": "CANONICAL_MAIN_DRAW",
        "statistical_controller": "P246K",
    }:
        raise AuditProvenanceError("current executable audit scope is incompatible")
    if current.get("new_statistical_procedure_introduced") is not False:
        raise AuditProvenanceError("current executable audit statistical identity is incompatible")
    if current.get("combined_p238b_p246k_verdict") is not False:
        raise AuditProvenanceError("combined donor verdict cannot serve as the cadence anchor")
    if current.get("db_write_performed") is not False:
        raise AuditProvenanceError("write-capable execution cannot serve as the cadence anchor")
    if current.get("p246k_result_retained_unchanged") is not True:
        raise AuditProvenanceError("P246K result-retention proof is missing")
    if current.get("p246k_nonsemantic_location_sanitized") is not True:
        raise AuditProvenanceError("P246K location-sanitization proof is missing")
    caveat = current.get("p246k_static_narrative_caveat")
    if not isinstance(caveat, str) or not caveat.strip():
        raise AuditProvenanceError("P246K static-narrative caveat is missing")
    if current.get("orchestration_additions_only") != [
        "provenance",
        "cadence",
        "publication_containment",
    ]:
        raise AuditProvenanceError("orchestration addition identity is incompatible")

    executed_raw = current.get("executed_at_utc")
    executed = _parse_utc_timestamp(executed_raw, field_name="executed_at_utc")
    if executed_raw != _format_utc(executed):
        raise AuditProvenanceError("executed_at_utc must use canonical UTC formatting")

    sources = current.get("implementation_sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise AuditProvenanceError("implementation source provenance is incomplete")
    if not all(isinstance(source, Mapping) for source in sources):
        raise AuditProvenanceError("implementation source provenance is malformed")
    source_by_id = {source.get("implementation_id"): source for source in sources}
    if set(source_by_id) != {"P246K", "P238B"}:
        raise AuditProvenanceError("implementation source identity is incompatible")
    if sources != _source_implementations():
        raise AuditProvenanceError("implementation source provenance is incompatible")
    if source_by_id["P246K"].get("entry_symbol") != "run_canonical_nist_reaudit":
        raise AuditProvenanceError("P246K executable entry symbol is incompatible")
    if source_by_id["P238B"].get("entry_symbol") != "_connect_ro":
        raise AuditProvenanceError("P238B donor boundary is incompatible")
    if not all(_is_sha256(source.get("source_sha256")) for source in sources):
        raise AuditProvenanceError("implementation source hash is missing or malformed")

    provenance = current.get("input_provenance")
    if not isinstance(provenance, Mapping):
        raise AuditProvenanceError("audit input provenance is missing")
    if provenance.get("db_identity") != LOGICAL_DB_IDENTITY:
        raise AuditProvenanceError("logical DB identity is incompatible")
    if provenance.get("db_open_mode") != "sqlite_uri_mode_ro":
        raise AuditProvenanceError("read-only DB provenance is missing")
    if provenance.get("sqlite_immutable") is not True:
        raise AuditProvenanceError("immutable DB provenance is missing")
    if provenance.get("sqlite_cache") != "private":
        raise AuditProvenanceError("private SQLite cache provenance is missing")
    if provenance.get("wal_precondition") != "empty_or_absent":
        raise AuditProvenanceError("WAL precondition provenance is missing")
    if provenance.get("pragma_query_only") is not True:
        raise AuditProvenanceError("query-only DB provenance is missing")
    if provenance.get("selected_population") != "BIG_LOTTO/CANONICAL_MAIN_DRAW":
        raise AuditProvenanceError("selected population provenance is incompatible")
    if provenance.get("canonical_view") != CANONICAL_VIEW_NAME:
        raise AuditProvenanceError("canonical view provenance is incompatible")
    sql = provenance.get("sql")
    if not isinstance(sql, Mapping) or sql.get("canonical_population") != CANONICAL_POPULATION_SQL:
        raise AuditProvenanceError("canonical population SQL provenance is incompatible")
    if sql.get("raw_population_count") != RAW_POPULATION_COUNT_SQL:
        raise AuditProvenanceError("raw population SQL provenance is incompatible")
    if sql.get("raw_population_count_params") != list(RAW_POPULATION_COUNT_PARAMS):
        raise AuditProvenanceError("raw population SQL parameters are missing or incompatible")
    if provenance.get("selected_row_stream_serialization") != ROW_STREAM_SERIALIZATION:
        raise AuditProvenanceError("selected-row serialization provenance is incompatible")

    canonical_count = provenance.get("selected_row_count")
    raw_count = provenance.get("raw_population_count")
    if not _is_positive_int(canonical_count):
        raise AuditProvenanceError("selected_row_count is malformed")
    if not _is_positive_int(raw_count) or raw_count < canonical_count:
        raise AuditProvenanceError("raw_population_count is malformed")
    oldest = _required_boundary(
        provenance.get("oldest_selected_row"),
        field_name="oldest selected-row boundary",
    )
    newest = _required_boundary(
        provenance.get("newest_selected_row"),
        field_name="newest selected-row boundary",
    )
    if provenance.get("selected_date_min") != oldest["date"]:
        raise AuditProvenanceError("selected-date minimum does not match oldest boundary")
    if provenance.get("selected_date_max") != newest["date"]:
        raise AuditProvenanceError("selected-date maximum does not match newest boundary")
    row_hash = provenance.get("selected_row_stream_sha256")
    if not _is_sha256(row_hash):
        raise AuditProvenanceError("selected-row-stream hash is missing or malformed")

    p246k_result = current.get("p246k_existing_logic_result")
    if not isinstance(p246k_result, Mapping):
        raise AuditProvenanceError("completed P246K result is missing")
    if p246k_result.get("schema_version") != "1.0" or p246k_result.get("task_id") != "P246K":
        raise AuditProvenanceError("P246K result identity is incompatible")
    if p246k_result.get("db_identity") != LOGICAL_DB_IDENTITY or "db_path" in p246k_result:
        raise AuditProvenanceError("P246K published DB identity is incompatible")
    if p246k_result.get("db_read") is not True or p246k_result.get("db_read_only") is not True:
        raise AuditProvenanceError("P246K execution did not complete through read-only input")
    if p246k_result.get("db_write_performed") is not False or "error" in p246k_result:
        raise AuditProvenanceError("P246K execution was not successful and read-only")
    if p246k_result.get("input_population") != "CANONICAL_MAIN_DRAW":
        raise AuditProvenanceError("P246K result population is incompatible")
    if p246k_result.get("canonical_population_count") != canonical_count:
        raise AuditProvenanceError("P246K canonical count does not match provenance")
    if p246k_result.get("raw_population_count") != raw_count:
        raise AuditProvenanceError("P246K raw count does not match provenance")
    if p246k_result.get("excluded_add_on_count") != raw_count - canonical_count:
        raise AuditProvenanceError("P246K exclusion count is inconsistent")

    exclusions = p246k_result.get("exclusion_rules_verified")
    if not isinstance(exclusions, Mapping) or not exclusions:
        raise AuditProvenanceError("P246K exclusion proof is empty or missing")
    expected_exclusions = {
        "canonical_count": canonical_count,
        "raw_count": raw_count,
        "excluded_count": raw_count - canonical_count,
        "hyphen_in_canonical": 0,
        "date_format_in_canonical": 0,
        "small_pool_in_canonical": 0,
        "all_exclusions_verified": True,
        "max_num_all_above_25": True,
        "num_range_valid": True,
    }
    if any(exclusions.get(key) != value for key, value in expected_exclusions.items()):
        raise AuditProvenanceError("P246K exclusion proof is incomplete or incompatible")

    audit_methods = p246k_result.get("audit_methods")
    if audit_methods != P246K_REQUIRED_AUDIT_METHODS:
        raise AuditProvenanceError("P246K audit method provenance is incomplete or incompatible")

    audit_results = p246k_result.get("audit_results")
    if not isinstance(audit_results, Mapping) or not audit_results:
        raise AuditProvenanceError("P246K five-check result is incomplete")
    statuses: list[str] = []
    required_check_fields = {
        ("draw_sum_distribution",): ("n", "ks_stat", "ks_p", "status"),
        ("number_frequency_uniformity",): (
            "n_draws",
            "n_numbers",
            "chi2_stat",
            "chi2_p",
            "status",
        ),
        ("serial_randomness", "runs_test"): ("z_stat", "p_value", "status"),
        ("serial_randomness", "ljung_box_lag10"): ("stat", "p_value", "status"),
        ("entropy",): ("normalized_entropy", "status"),
    }
    for path in P246K_CHECK_PATHS:
        check: Any = audit_results
        for key in path:
            if not isinstance(check, Mapping):
                check = None
                break
            check = check.get(key)
        if not isinstance(check, Mapping) or check.get("status") not in {"GREEN", "YELLOW"}:
            raise AuditProvenanceError(f"P246K check is missing or incomplete: {'.'.join(path)}")
        for field in required_check_fields[path]:
            if field not in check or check[field] is None:
                raise AuditProvenanceError(
                    f"P246K check outcome is incomplete: {'.'.join(path)}.{field}"
                )
            if field != "status" and not _is_number(check[field]):
                raise AuditProvenanceError(
                    f"P246K check outcome is malformed: {'.'.join(path)}.{field}"
                )
        statuses.append(check["status"])
    if not isinstance(audit_results.get("per_position"), Mapping) or not audit_results[
        "per_position"
    ]:
        raise AuditProvenanceError("P246K per-position diagnostic provenance is empty")
    if not isinstance(audit_results.get("era_stability"), Mapping) or not audit_results[
        "era_stability"
    ]:
        raise AuditProvenanceError("P246K era-stability diagnostic provenance is empty")
    summary = audit_results.get("summary")
    if not isinstance(summary, Mapping):
        raise AuditProvenanceError("P246K five-check summary is missing")
    green_count = statuses.count("GREEN")
    yellow_count = statuses.count("YELLOW")
    expected_overall = "GREEN" if yellow_count == 0 else "YELLOW"
    if summary.get("total_tests") != len(P246K_CHECK_PATHS):
        raise AuditProvenanceError("P246K five-check total is incompatible")
    if summary.get("green") != green_count or summary.get("yellow") != yellow_count:
        raise AuditProvenanceError("P246K five-check summary is inconsistent")
    if summary.get("overall_status") != expected_overall:
        raise AuditProvenanceError("P246K overall status is inconsistent")
    expected_classification = (
        "P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE"
        if expected_overall == "GREEN"
        else "P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY"
    )
    if p246k_result.get("classification") != expected_classification:
        raise AuditProvenanceError("P246K classification is inconsistent")

    semantic_hash = current.get("p246k_semantic_output_sha256")
    if not _is_sha256(semantic_hash):
        raise AuditProvenanceError("P246K semantic hash is missing or malformed")
    actual_semantic_hash = _sha256_bytes(
        _canonical_json_bytes(_p246k_semantic_payload(p246k_result))
    )
    if semantic_hash != actual_semantic_hash:
        raise AuditProvenanceError("P246K semantic hash does not match completed result")

    containment = current.get("p246k_existing_logic_payload_metadata")
    if containment != _p246k_payload_metadata(p246k_result):
        raise AuditProvenanceError("P246K non-authoritative payload containment is incomplete")
    limitations = containment.get("scientific_limitations")
    if not isinstance(limitations, list) or len(limitations) != 6:
        raise AuditProvenanceError("six machine-readable scientific limitations are required")
    if current.get("current_authoritative_conclusion") != _bounded_current_conclusion(
        p246k_result
    ):
        raise AuditProvenanceError("bounded current publication conclusion is incompatible")
    if current.get("historical_date_conflict") != HISTORICAL_DATE_CONFLICT:
        raise AuditProvenanceError("historical date-conflict disclosure is incomplete")

    policy = current.get("cadence_policy")
    expected_policy = {
        "max_calendar_days": CADENCE_MAX_CALENDAR_DAYS,
        "max_new_canonical_draws": CADENCE_MAX_NEW_DRAWS,
        "trigger": "whichever_occurs_first",
        "timestamp_only_re_attestation_is_gating": False,
    }
    if policy != expected_policy:
        raise AuditProvenanceError("cadence policy identity is incompatible")

    anchor = current.get("cadence_anchor")
    if not isinstance(anchor, Mapping):
        raise AuditProvenanceError("cadence anchor is missing")
    if anchor.get("real_executable_audit_timestamp_utc") != executed_raw:
        raise AuditProvenanceError("cadence anchor timestamp does not match completed execution")
    if anchor.get("canonical_draw_count") != canonical_count:
        raise AuditProvenanceError("cadence anchor count does not match completed execution")
    if anchor.get("selected_row_stream_sha256") != row_hash:
        raise AuditProvenanceError("cadence anchor hash does not match completed execution")
    if anchor.get("newest_selected_row") != newest:
        raise AuditProvenanceError("cadence anchor boundary does not match completed execution")
    if anchor.get("oldest_selected_row") != oldest:
        raise AuditProvenanceError("cadence anchor oldest boundary does not match execution")
    return current, anchor, provenance, executed


def evaluate_cadence(
    document: Mapping[str, Any],
    current_population: PopulationLoad,
    now_utc: datetime,
) -> dict[str, Any]:
    """Evaluate 14-day / 50-new-draw cadence against an independent DB load."""
    _, anchor, provenance, audit_time = _validate_executable_audit_document(document)
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise AuditProvenanceError("now_utc must be timezone-aware")
    now = now_utc.astimezone(timezone.utc)
    if audit_time > now:
        raise AuditProvenanceError("real executable audit timestamp is in the future")
    elapsed = now - audit_time

    baseline_count = anchor.get("canonical_draw_count")
    baseline_hash = anchor.get("selected_row_stream_sha256")
    if not _is_positive_int(baseline_count):
        raise AuditProvenanceError("canonical_draw_count is malformed")
    if not _is_sha256(baseline_hash):
        raise AuditProvenanceError("selected_row_stream_sha256 is malformed")
    if provenance.get("selected_row_count") != baseline_count:
        raise AuditProvenanceError("cadence count does not match audit input provenance")
    if provenance.get("selected_row_stream_sha256") != baseline_hash:
        raise AuditProvenanceError("cadence hash does not match audit input provenance")

    current_draws = current_population.draws
    if len(current_draws) < baseline_count:
        raise AuditProvenanceError("current canonical population is smaller than audit baseline")
    baseline_candidate = current_draws[len(current_draws) - baseline_count :]
    candidate_hash = _sha256_bytes(_row_stream_bytes(baseline_candidate))
    if candidate_hash != baseline_hash:
        raise AuditProvenanceError(
            "current canonical history does not preserve the audited row stream"
        )

    new_draws = len(current_draws) - baseline_count
    calendar_due = elapsed >= timedelta(days=CADENCE_MAX_CALENDAR_DAYS)
    draw_due = new_draws >= CADENCE_MAX_NEW_DRAWS
    due = calendar_due or draw_due
    if calendar_due and draw_due:
        trigger = "CALENDAR_AND_DRAW_COUNT"
    elif calendar_due:
        trigger = "CALENDAR"
    elif draw_due:
        trigger = "DRAW_COUNT"
    else:
        trigger = "NONE"
    return {
        "status": "DUE" if due else "CURRENT",
        "due": due,
        "trigger": trigger,
        "calendar_due": calendar_due,
        "draw_due": draw_due,
        "audit_timestamp_utc": _format_utc(audit_time),
        "evaluated_at_utc": _format_utc(now),
        "elapsed_seconds": elapsed.total_seconds(),
        "max_calendar_days": CADENCE_MAX_CALENDAR_DAYS,
        "new_canonical_draws": new_draws,
        "max_new_canonical_draws": CADENCE_MAX_NEW_DRAWS,
        "current_canonical_draw_count": len(current_draws),
        "current_draw_source": "independent_read_only_canonical_DB_query",
    }


def _reject_machine_specific_text(text: str, *, artifact_name: str) -> None:
    patterns = (
        r"/Users/[^/\s`]+/",
        r"/home/[^/\s`]+/",
        r"[A-Za-z]:\\Users\\[^\\\s`]+\\",
    )
    if any(re.search(pattern, text) for pattern in patterns):
        raise AuditProvenanceError(f"{artifact_name} contains a machine-specific path")
    home = str(Path.home())
    if home and home in text:
        raise AuditProvenanceError(f"{artifact_name} contains the runtime home directory")
    hostname = socket.gethostname()
    if hostname and hostname in text:
        raise AuditProvenanceError(f"{artifact_name} contains the runtime hostname")


def _validate_rendered_pair(results_text: str, summary_text: str) -> None:
    document = strict_json_loads(results_text, source="generated JSON artifact")
    if not isinstance(document, Mapping):
        raise AuditProvenanceError("generated JSON artifact must be an object")
    _validate_executable_audit_document(document)
    legacy_summary = extract_legacy_summary(summary_text)
    if render_summary(document, legacy_summary) != summary_text:
        raise AuditProvenanceError("generated JSON and Markdown artifacts disagree")
    _reject_machine_specific_text(results_text, artifact_name="JSON artifact")
    _reject_machine_specific_text(summary_text, artifact_name="Markdown artifact")


def _validate_rendered_artifacts(
    results_text: str,
    summary_text: str,
    wiki_text: str,
) -> None:
    _validate_rendered_pair(results_text, summary_text)
    document = strict_json_loads(results_text, source="generated JSON artifact")
    if render_wiki(document, wiki_text) != wiki_text:
        raise AuditProvenanceError("generated JSON and wiki artifacts disagree")
    current = document["current_executable_audit"]
    timestamp = current["executed_at_utc"]
    if summary_text.count(
        f"**Current executable audit timestamp (UTC):** {timestamp}"
    ) != 1:
        raise AuditProvenanceError("JSON and Markdown execution timestamps disagree")
    if wiki_text.count(f"**Latest real executable audit:** {timestamp}") != 1:
        raise AuditProvenanceError("JSON and wiki execution timestamps disagree")
    limitations = current["p246k_existing_logic_payload_metadata"][
        "scientific_limitations"
    ]
    if len(limitations) != 6:
        raise AuditProvenanceError("publication requires exactly six scientific limitations")
    for limitation in limitations:
        statement = limitation["statement"]
        if statement not in summary_text or statement not in wiki_text:
            raise AuditProvenanceError(
                f"scientific limitation publication disagrees: {limitation['id']}"
            )
    disclosure = current["historical_date_conflict"]["disclosure"]
    if disclosure not in summary_text or disclosure not in wiki_text:
        raise AuditProvenanceError("historical date-conflict publication disagrees")
    _reject_machine_specific_text(wiki_text, artifact_name="wiki artifact")


def _stage_bytes(target: Path, payload: bytes, *, suffix: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=suffix,
    )
    os.close(descriptor)
    staged = Path(raw_path)
    try:
        staged.write_bytes(payload)
        if staged.read_bytes() != payload:
            raise AuditProvenanceError(f"staged artifact bytes do not match: {target}")
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def _replace_file(source: Path, target: Path) -> None:
    source.replace(target)


def _restore_path(
    target: Path,
    original: Optional[bytes],
    cleanup_paths: list[Path],
) -> None:
    if original is None:
        target.unlink(missing_ok=True)
        return
    restore_stage = _stage_bytes(target, original, suffix=".rollback")
    cleanup_paths.append(restore_stage)
    _replace_file(restore_stage, target)


def _publish_artifacts(artifacts: Sequence[tuple[Path, str]]) -> None:
    """Publish an ordered artifact set and restore every published target on failure."""
    resolved_targets = [target.resolve() for target, _ in artifacts]
    if len(resolved_targets) != len(set(resolved_targets)):
        raise AuditProvenanceError("publication artifact targets must be distinct")
    originals = {
        target: target.read_bytes() if target.exists() else None
        for target, _ in artifacts
    }
    cleanup_paths: list[Path] = []
    staged: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for target, text in artifacts:
            stage = _stage_bytes(target, text.encode("utf-8"), suffix=".stage")
            cleanup_paths.append(stage)
            staged.append((stage, target))
        try:
            for stage, target in staged:
                _replace_file(stage, target)
                published.append(target)
        except Exception as publication_error:
            rollback_errors: list[str] = []
            for target in reversed(published):
                try:
                    _restore_path(target, originals[target], cleanup_paths)
                except Exception as rollback_error:
                    rollback_errors.append(f"{target}: {rollback_error}")
            if rollback_errors:
                raise AuditProvenanceError(
                    "artifact publication failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from publication_error
            if published:
                raise AuditProvenanceError(
                    "artifact publication failed; the original artifact set was restored"
                ) from publication_error
            raise AuditProvenanceError(
                "artifact publication failed before any final file changed"
            ) from publication_error
    finally:
        cleanup_failures: list[str] = []
        for path in cleanup_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_failures.append(f"{path}: {exc}")
        if cleanup_failures and sys.exc_info()[0] is None:
            raise AuditProvenanceError(
                "artifact staging cleanup failed: " + "; ".join(cleanup_failures)
            )


def _publish_artifact_pair(
    *,
    results_text: str,
    summary_text: str,
    results_out: Path,
    summary_out: Path,
) -> None:
    _publish_artifacts(
        (
            (summary_out, summary_text),
            (results_out, results_text),
        )
    )


def _publish_artifact_triplet(
    *,
    results_text: str,
    summary_text: str,
    wiki_text: str,
    results_out: Path,
    summary_out: Path,
    wiki_out: Path,
) -> None:
    # Publish human-readable surfaces first and cadence-bearing JSON last.
    _publish_artifacts(
        (
            (summary_out, summary_text),
            (wiki_out, wiki_text),
            (results_out, results_text),
        )
    )


def generate(
    *,
    db_path: Path,
    executed_at_utc: datetime,
    legacy_results_path: Path = DEFAULT_RESULTS_PATH,
    legacy_summary_path: Path = DEFAULT_SUMMARY_PATH,
    wiki_source_path: Path = DEFAULT_WIKI_PATH,
    results_out: Path = DEFAULT_RESULTS_PATH,
    summary_out: Path = DEFAULT_SUMMARY_PATH,
    wiki_out: Path = DEFAULT_WIKI_PATH,
) -> dict[str, Any]:
    existing_results_bytes = legacy_results_path.read_bytes()
    existing_results = strict_json_loads(
        existing_results_bytes,
        source=str(legacy_results_path),
    )
    summary_text = legacy_summary_path.read_text(encoding="utf-8")
    legacy_summary = extract_legacy_summary(summary_text)
    wiki_source = wiki_source_path.read_text(encoding="utf-8")
    population = load_canonical_big_lotto_population(db_path)
    p246k_result = run_p246k_existing_logic(population, db_path)
    document = build_results_document(
        existing_results=existing_results,
        existing_results_bytes=existing_results_bytes,
        legacy_summary=legacy_summary,
        executed_at_utc=executed_at_utc,
        population=population,
        p246k_result=p246k_result,
    )
    # Keep the legacy payload's original insertion order and no-final-newline
    # formatting so generation appends current metadata without mechanically
    # rewriting the immutable historical evidence.
    results_text = json.dumps(document, ensure_ascii=False, indent=2)
    summary_output = render_summary(document, legacy_summary)
    wiki_output = render_wiki(document, wiki_source)
    _validate_rendered_artifacts(results_text, summary_output, wiki_output)
    _publish_artifact_triplet(
        results_text=results_text,
        summary_text=summary_output,
        wiki_text=wiki_output,
        results_out=results_out,
        summary_out=summary_out,
        wiki_out=wiki_out,
    )
    return document


def _load_results(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AuditProvenanceError(f"unable to load audit results: {path}") from exc
    value = strict_json_loads(payload, source=str(path))
    if not isinstance(value, dict):
        raise AuditProvenanceError("audit results must be a JSON object")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="execute P246K through the read-only adapter")
    run_parser.add_argument("--db", type=Path, required=True)
    run_parser.add_argument("--executed-at-utc", required=True)
    run_parser.add_argument("--legacy-results", type=Path, default=DEFAULT_RESULTS_PATH)
    run_parser.add_argument("--legacy-summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    run_parser.add_argument("--wiki-source", type=Path, default=DEFAULT_WIKI_PATH)
    run_parser.add_argument("--results-out", type=Path, default=DEFAULT_RESULTS_PATH)
    run_parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_PATH)
    run_parser.add_argument("--wiki-out", type=Path, default=DEFAULT_WIKI_PATH)

    cadence_parser = subparsers.add_parser("cadence", help="evaluate cadence from the canonical DB")
    cadence_parser.add_argument("--db", type=Path, required=True)
    cadence_parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS_PATH)
    cadence_parser.add_argument("--now-utc", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            executed = _parse_utc_timestamp(
                args.executed_at_utc,
                field_name="executed_at_utc",
            )
            document = generate(
                db_path=args.db,
                executed_at_utc=executed,
                legacy_results_path=args.legacy_results,
                legacy_summary_path=args.legacy_summary,
                wiki_source_path=args.wiki_source,
                results_out=args.results_out,
                summary_out=args.summary_out,
                wiki_out=args.wiki_out,
            )
            print(
                json.dumps(
                    {
                        "status": "GENERATED",
                        "task_id": TASK_ID,
                        "executed_at_utc": document["current_executable_audit"]["executed_at_utc"],
                        "results": str(args.results_out),
                        "summary": str(args.summary_out),
                        "wiki": str(args.wiki_out),
                    },
                    sort_keys=True,
                )
            )
            return 0
        document = _load_results(args.results)
        population = load_canonical_big_lotto_population(args.db)
        now = _parse_utc_timestamp(args.now_utc, field_name="now_utc")
        cadence = evaluate_cadence(document, population, now)
        print(json.dumps(cadence, sort_keys=True))
        return 1 if cadence["due"] else 0
    except (AuditProvenanceError, FileNotFoundError, ImportError, json.JSONDecodeError) as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
