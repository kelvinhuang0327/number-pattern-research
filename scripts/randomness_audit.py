#!/usr/bin/env python3
<<<<<<< HEAD
"""Deterministic, read-only lottery randomness audit.

The historical 44-test artifact did not include its producer.  This runner
reconstructs that frozen registry, corrects its known methodological defects,
and binds every result to the current canonical SQLite row streams.
=======
"""Existing-logic randomness audit orchestration and cadence evaluation.

This module does not define a statistical methodology.  It supplies the
canonical BIG_LOTTO population through an enforced SQLite read-only path and
then calls P246K's committed audit runner unchanged.  Its P238B comparison
artifact is strictly decoded once and supplied through the donor's comparison
loader seam.  The historical 44-test artifact remains immutable legacy evidence
because its producing source is not committed in this repository.
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
"""
from __future__ import annotations

import argparse
import hashlib
<<<<<<< HEAD
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import quote
=======
import importlib.util
import json
import os
import re
import socket
import sqlite3
import sys
import tempfile
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Mapping, Optional, Sequence
from unittest.mock import patch
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

<<<<<<< HEAD
from lottery_api.utils.correction_gate import correction_gate_summary  # noqa: E402


AUDIT_VERSION = "2.0.0-p20r"
AUDIT_SOURCE = "RECONSTRUCTED"
DEFAULT_SEED = 42
DEFAULT_SIMULATIONS = 2000
DEFAULT_ALPHA = 0.05
CONFIRMATORY_FAMILY = "lottery_randomness_confirmatory_v2"
CADENCE_MAX_CALENDAR_DAYS = 14
CADENCE_MAX_NEW_DRAWS = 50
RESULTS_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_results.json"
SUMMARY_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
CORRECTION_SOURCE = REPO_ROOT / "lottery_api" / "utils" / "correction_gate.py"


class AuditContractError(RuntimeError):
    """Raised when input or generated evidence cannot satisfy the audit contract."""


@dataclass(frozen=True)
class GameConfig:
    game: str
    lottery_type: str
    source: str
    query: str
    pick_count: int
    max_ball: int
    special_min: Optional[int]
    special_max: Optional[int]
    prior_source: str
    prior_rows: int
    prior_date_min: str
    prior_date_max: str


@dataclass(frozen=True)
class Draw:
    draw: str
    date: str
    numbers: tuple[int, ...]
    special: Optional[int]


GAME_CONFIGS: tuple[GameConfig, ...] = (
    GameConfig(
        game="power_lotto",
        lottery_type="POWER_LOTTO",
        source="draws WHERE lottery_type='POWER_LOTTO'",
        query=(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' "
            "ORDER BY date(replace(date,'/','-')), CAST(draw AS INTEGER), draw"
        ),
        pick_count=6,
        max_ball=38,
        special_min=1,
        special_max=8,
        prior_source="draws/POWER_LOTTO",
        prior_rows=1906,
        prior_date_min="2008-01-24",
        prior_date_max="2026-04-27",
    ),
    GameConfig(
        game="big_lotto",
        lottery_type="BIG_LOTTO",
        source="draws_big_lotto_canonical_main",
        query=(
            "SELECT draw, date, numbers, special FROM draws_big_lotto_canonical_main "
            "ORDER BY date(replace(date,'/','-')), CAST(draw AS INTEGER), draw"
        ),
        pick_count=6,
        max_ball=49,
        special_min=1,
        special_max=49,
        prior_source="49_LOTTO (inferred from exact 2,130-row/date-range match)",
        prior_rows=2130,
        prior_date_min="2007-01-02",
        prior_date_max="2026-04-28",
    ),
    GameConfig(
        game="daily_539",
        lottery_type="DAILY_539",
        source="draws WHERE lottery_type='DAILY_539'",
        query=(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='DAILY_539' "
            "ORDER BY date(replace(date,'/','-')), CAST(draw AS INTEGER), draw"
        ),
        pick_count=5,
        max_ball=39,
        special_min=None,
        special_max=None,
        prior_source="draws/DAILY_539",
        prior_rows=5849,
        prior_date_min="2007-01-01",
        prior_date_max="2026-04-29",
    ),
)


PATTERN_SPECS: tuple[tuple[str, str], ...] = (
    ("consecutive_count", "Mean count of adjacent consecutive main-number pairs"),
    ("same_tail_count", "Mean count of main-number pairs sharing a final digit"),
    ("odd_count", "Mean count of odd main numbers"),
    ("low_count", "Mean count in the lower half of the main-number pool"),
    ("sum", "Mean main-number sum"),
    ("span", "Mean maximum-minus-minimum span"),
    ("repeat_from_prev", "Mean overlap with the immediately previous draw"),
    ("pair_cooccurrence_gini", "Gini coefficient of pair co-occurrence frequencies"),
    ("gap_distribution", "Mean adjacent sorted-number gap"),
)


def _build_confirmatory_registry() -> tuple[dict[str, Any], ...]:
    registry: list[dict[str, Any]] = []
    for config in GAME_CONFIGS:
        registry.append(
            {
                "test_id": f"{config.game}_overall_frequency",
                "game": config.game,
                "hypothesis": f"Main balls follow the {config.pick_count}-of-{config.max_ball} uniform draw model",
                "statistic_name": "pearson_frequency_dispersion",
                "method": "monte_carlo_exact_without_replacement",
                "correction_family": CONFIRMATORY_FAMILY,
            }
        )
        if config.special_min is not None:
            registry.append(
                {
                    "test_id": f"{config.game}_special_uniformity",
                    "game": config.game,
                    "hypothesis": f"Special number marginal is uniform over [{config.special_min}..{config.special_max}]",
                    "statistic_name": "pearson_special_frequency",
                    "method": "chi_square_asymptotic",
                    "correction_family": CONFIRMATORY_FAMILY,
                }
            )
        for metric, description in PATTERN_SPECS:
            registry.append(
                {
                    "test_id": f"{config.game}_pattern_{metric}",
                    "game": config.game,
                    "hypothesis": f"{description} is compatible with the exact draw model",
                    "statistic_name": metric,
                    "method": "monte_carlo_exact_without_replacement",
                    "correction_family": CONFIRMATORY_FAMILY,
                }
            )
        registry.extend(
            (
                {
                    "test_id": f"{config.game}_ljungbox_sum",
                    "game": config.game,
                    "hypothesis": "Draw sums are serially independent through lag 20",
                    "statistic_name": "ljung_box_q_lag20",
                    "method": "ljung_box_chi_square",
                    "correction_family": CONFIRMATORY_FAMILY,
                },
                {
                    "test_id": f"{config.game}_runs_odd",
                    "game": config.game,
                    "hypothesis": "Strictly odd-majority draws form a random binary sequence",
                    "statistic_name": "wald_wolfowitz_z",
                    "method": "wald_wolfowitz_runs",
                    "correction_family": CONFIRMATORY_FAMILY,
                },
                {
                    "test_id": f"{config.game}_runs_repeat",
                    "game": config.game,
                    "hypothesis": "Nonzero previous-draw overlap forms a random binary sequence",
                    "statistic_name": "wald_wolfowitz_z",
                    "method": "wald_wolfowitz_runs",
                    "correction_family": CONFIRMATORY_FAMILY,
                },
                {
                    "test_id": f"{config.game}_drift_halves",
                    "game": config.game,
                    "hypothesis": "Main-number frequency is stable between chronological halves",
                    "statistic_name": "pearson_two_half_dispersion",
                    "method": "monte_carlo_row_label_permutation",
                    "correction_family": CONFIRMATORY_FAMILY,
                },
            )
        )
    return tuple(registry)


CONFIRMATORY_REGISTRY = _build_confirmatory_registry()


def _build_exploratory_registry() -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for config in GAME_CONFIGS:
        for position in range(1, config.pick_count + 1):
            result.append(
                {
                    "test_id": f"{config.game}_position_{position}",
                    "game": config.game,
                    "hypothesis": (
                        f"Sorted position {position} compared with a marginal-uniform reference; "
                        "known sorted-order artifact"
                    ),
                    "statistic_name": "sorted_position_pearson_diagnostic",
                    "method": "exploratory_sorted_order_diagnostic",
                    "correction_family": None,
                }
            )
    return tuple(result)


EXPLORATORY_REGISTRY = _build_exploratory_registry()
=======
from scripts import p238b_nist_randomness_audit_artifact_build as p238b  # noqa: E402


TASK_ID = "P691_RANDOMNESS_EXISTING_LOGIC_TRANSFER_R1"
SCHEMA_VERSION = "2.0"
AUDIT_TYPE = "EXISTING_LOGIC_MIGRATION"
LOGICAL_DB_IDENTITY = "canonical_big_lotto_store"
CADENCE_MAX_CALENDAR_DAYS = 14
CADENCE_MAX_NEW_DRAWS = 50

P238B_SOURCE = REPO_ROOT / "scripts" / "p238b_nist_randomness_audit_artifact_build.py"
P246K_SOURCE = REPO_ROOT / "analysis" / "p246k_canonical_big_lotto_nist_reaudit.py"
P238B_COMPARISON_ARTIFACT = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p238b_nist_randomness_audit_artifact_20260604.json"
)
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
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
<<<<<<< HEAD
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def registry_sha256() -> str:
    return _sha256_bytes(_canonical_json_bytes(CONFIRMATORY_REGISTRY))


def _parse_date(value: Any) -> tuple[str, str]:
    if not isinstance(value, str) or not value:
        raise AuditContractError("draw date must be a non-empty string")
    for format_name, fmt in (("slash", "%Y/%m/%d"), ("dash", "%Y-%m-%d")):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date().isoformat(), format_name
        except ValueError:
            pass
    raise AuditContractError(f"unsupported draw date: {value!r}")


def _parse_numbers(value: Any, config: GameConfig, draw_id: str) -> tuple[int, ...]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as exc:
        raise AuditContractError(f"{config.game} draw {draw_id}: malformed numbers JSON") from exc
    if not isinstance(parsed, list) or len(parsed) != config.pick_count:
        raise AuditContractError(f"{config.game} draw {draw_id}: wrong main-number count")
    if any(isinstance(number, bool) or not isinstance(number, int) for number in parsed):
        raise AuditContractError(f"{config.game} draw {draw_id}: main numbers must be integers")
    numbers = tuple(parsed)
    if any(number < 1 or number > config.max_ball for number in numbers):
        raise AuditContractError(f"{config.game} draw {draw_id}: main number out of range")
    if len(set(numbers)) != len(numbers):
        raise AuditContractError(f"{config.game} draw {draw_id}: repeated number inside one draw")
    if numbers != tuple(sorted(numbers)):
        raise AuditContractError(f"{config.game} draw {draw_id}: canonical main numbers are not sorted")
    return numbers


def _parse_special(value: Any, config: GameConfig, draw_id: str, numbers: tuple[int, ...]) -> Optional[int]:
    if config.special_min is None:
        if value not in (None, 0, "", "0"):
            raise AuditContractError(f"{config.game} draw {draw_id}: unexpected special number")
        return None
    if isinstance(value, bool) or value is None:
        raise AuditContractError(f"{config.game} draw {draw_id}: required special number is missing")
    try:
        special = int(value)
    except (TypeError, ValueError) as exc:
        raise AuditContractError(f"{config.game} draw {draw_id}: invalid special number") from exc
    if special < config.special_min or special > config.special_max:
        raise AuditContractError(f"{config.game} draw {draw_id}: special number out of range")
    if config.game == "big_lotto" and special in numbers:
        raise AuditContractError(f"{config.game} draw {draw_id}: special number repeats a main number")
    return special


def classify_record_identity(draws: Sequence[Draw]) -> dict[str, int]:
    draw_ids = Counter(draw.draw for draw in draws)
    full_records = Counter((draw.draw, draw.date, draw.numbers, draw.special) for draw in draws)
    main_combinations = Counter(draw.numbers for draw in draws)
    full_outcomes = Counter((draw.numbers, draw.special) for draw in draws)
    return {
        "duplicate_draw_id_groups": sum(count > 1 for count in draw_ids.values()),
        "duplicate_draw_id_excess_rows": sum(max(0, count - 1) for count in draw_ids.values()),
        "duplicate_full_record_groups": sum(count > 1 for count in full_records.values()),
        "duplicate_full_record_excess_rows": sum(max(0, count - 1) for count in full_records.values()),
        "repeated_main_combination_groups": sum(count > 1 for count in main_combinations.values()),
        "repeated_main_combination_excess_rows": sum(max(0, count - 1) for count in main_combinations.values()),
        "repeated_full_outcome_groups": sum(count > 1 for count in full_outcomes.values()),
        "repeated_full_outcome_excess_rows": sum(max(0, count - 1) for count in full_outcomes.values()),
    }


def _resolve_db_path(db_path: Path) -> Path:
    if not db_path.is_absolute():
        raise AuditContractError("--db must be an absolute path")
    resolved = db_path.resolve()
    if not resolved.is_file():
        raise AuditContractError(f"canonical DB is not an existing regular file: {resolved}")
    wal = Path(f"{resolved}-wal")
    if wal.exists() and wal.stat().st_size:
        raise AuditContractError("canonical DB has a non-empty WAL; immutable audit would be incomplete")
    return resolved


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    resolved = _resolve_db_path(db_path)
    uri_path = quote(str(resolved), safe="/")
    connection = sqlite3.connect(
        f"file:{uri_path}?mode=ro&immutable=1&cache=private",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        connection.close()
        raise AuditContractError("SQLite query_only guard could not be enabled")
    return connection


def _row_stream(draws: Sequence[Draw]) -> bytes:
    rows = (
        {
            "date": draw.date,
            "draw": draw.draw,
            "numbers": list(draw.numbers),
            "special": draw.special,
        }
        for draw in draws
    )
    return b"".join(_canonical_json_bytes(row) + b"\n" for row in rows)


def _big_lotto_exclusions(connection: sqlite3.Connection) -> tuple[int, dict[str, int]]:
    raw = int(connection.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'").fetchone()[0])
    row = connection.execute(
        """
        SELECT
          SUM(draw LIKE '%-%') AS hyphenated_draw_id,
          SUM(LENGTH(draw)=8 AND draw LIKE '20%') AS date_style_draw_id,
          SUM((SELECT MAX(CAST(j.value AS INTEGER)) FROM json_each(draws.numbers) j) <= 25) AS small_pool
        FROM draws WHERE lottery_type='BIG_LOTTO'
        """
    ).fetchone()
    return raw, {
        "hyphenated_draw_id": int(row["hyphenated_draw_id"] or 0),
        "date_style_draw_id": int(row["date_style_draw_id"] or 0),
        "small_pool": int(row["small_pool"] or 0),
    }


def load_canonical_data(db_path: Path) -> dict[str, Any]:
    resolved = _resolve_db_path(db_path)
    db_sha_before = _sha256_file(resolved)
    connection = _connect_read_only(resolved)
    try:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(draws)")}
        required_columns = {"draw", "date", "lottery_type", "numbers", "special"}
        if not required_columns.issubset(columns):
            raise AuditContractError(f"draws schema is incomplete: {sorted(required_columns - columns)}")
        view = connection.execute(
            "SELECT type, sql FROM sqlite_master WHERE name='draws_big_lotto_canonical_main'"
        ).fetchone()
        if view is None or view["type"] != "view":
            raise AuditContractError("required canonical Big Lotto view is missing")

        sources: list[dict[str, Any]] = []
        draws_by_game: dict[str, list[Draw]] = {}
        for config in GAME_CONFIGS:
            rows = connection.execute(config.query).fetchall()
            draws: list[Draw] = []
            date_formats: Counter[str] = Counter()
            for row in rows:
                draw_id = str(row["draw"])
                date, date_format = _parse_date(row["date"])
                date_formats[date_format] += 1
                numbers = _parse_numbers(row["numbers"], config, draw_id)
                special = _parse_special(row["special"], config, draw_id, numbers)
                draws.append(Draw(draw=draw_id, date=date, numbers=numbers, special=special))
            if not draws:
                raise AuditContractError(f"{config.game}: canonical source is empty")
            identity = classify_record_identity(draws)
            if identity["duplicate_draw_id_groups"] or identity["duplicate_full_record_groups"]:
                raise AuditContractError(f"{config.game}: duplicate database records detected")
            if config.game == "big_lotto":
                raw_count, exclusion_breakdown = _big_lotto_exclusions(connection)
            else:
                raw_count = len(draws)
                exclusion_breakdown = {}
            stream_digest = _sha256_bytes(_row_stream(draws))
            new_draws_included = draws[-1].date > config.prior_date_max
            source = {
                "game": config.game,
                "source": config.source,
                "source_sql": config.query,
                "row_count": len(draws),
                "raw_row_count": raw_count,
                "excluded_row_count": raw_count - len(draws),
                "exclusion_breakdown": exclusion_breakdown,
                "date_min": draws[0].date,
                "date_max": draws[-1].date,
                "draw_min": draws[0].draw,
                "draw_max": draws[-1].draw,
                "digest": stream_digest,
                "digest_serialization": "UTF-8 canonical JSON Lines, chronological order",
                "date_formats_normalized": dict(sorted(date_formats.items())),
                "duplicate_draw_ids": identity["duplicate_draw_id_excess_rows"],
                "duplicate_full_records": identity["duplicate_full_record_excess_rows"],
                "repeated_main_combinations": identity["repeated_main_combination_excess_rows"],
                "repeated_full_outcomes": identity["repeated_full_outcome_excess_rows"],
                "invalid_repeated_numbers_inside_draw": 0,
                "invalid_rows_excluded": 0,
                "prior_evidence": {
                    "source": config.prior_source,
                    "row_count": config.prior_rows,
                    "date_min": config.prior_date_min,
                    "date_max": config.prior_date_max,
                    "row_count_delta_not_comparable_when_source_changed": len(draws) - config.prior_rows,
                },
                "new_draws_included": new_draws_included,
            }
            sources.append(source)
            draws_by_game[config.game] = draws
    finally:
        connection.close()

    db_sha_after = _sha256_file(resolved)
    if db_sha_after != db_sha_before:
        raise AuditContractError("canonical DB checksum changed during read-only load")
    identity_projection = [
        {
            key: source[key]
            for key in ("game", "source", "row_count", "date_min", "date_max", "digest")
        }
        for source in sources
    ]
    return {
        "draws": draws_by_game,
        "sources": sources,
        "dataset_identity": {
            "logical_database": "lottery_api/data/lottery_v2.db",
            "database_sha256": db_sha_before,
            "combined_selected_data_sha256": _sha256_bytes(_canonical_json_bytes(identity_projection)),
            "sqlite_open_mode": "mode=ro&immutable=1&cache=private",
            "pragma_query_only": True,
            "wal_precondition": "empty_or_absent",
        },
    }


def _science() -> tuple[Any, Any]:
    try:
        import numpy as np
        from scipy import stats
    except ImportError as exc:
        raise AuditContractError("required audit dependencies numpy/scipy are unavailable") from exc
    return np, stats


def _rng(seed: int, *parts: str) -> Any:
    np, _ = _science()
    material = ":".join((str(seed), *parts)).encode("utf-8")
    derived = int.from_bytes(hashlib.sha256(material).digest()[:16], "big")
    return np.random.default_rng(derived)


def _sample_histories(rng: Any, batch: int, rows: int, pick: int, pool: int) -> Any:
    np, _ = _science()
    samples = rng.integers(1, pool + 1, size=(batch, rows, pick), dtype=np.int16)
    for _ in range(100):
        ordered = np.sort(samples, axis=2)
        bad = np.any(np.diff(ordered, axis=2) == 0, axis=2)
        if not np.any(bad):
            return ordered
        samples[bad] = rng.integers(1, pool + 1, size=(int(np.sum(bad)), pick), dtype=np.int16)
    raise AuditContractError("without-replacement sampler did not converge")


def _gini(values: Any) -> float:
    np, _ = _science()
    ordered = np.sort(np.asarray(values, dtype=float))
    total = float(np.sum(ordered))
    if total == 0.0:
        return 0.0
    size = len(ordered)
    ranks = np.arange(1, size + 1, dtype=float)
    return float(np.sum((2 * ranks - size - 1) * ordered) / (size * total))


def _history_metrics(samples: Any, pool: int) -> dict[str, Any]:
    np, _ = _science()
    batch, rows, pick = samples.shape
    diffs = np.diff(samples, axis=2)
    pair_i, pair_j = np.triu_indices(pick, 1)
    metrics: dict[str, Any] = {
        "consecutive_count": np.mean(np.sum(diffs == 1, axis=2), axis=1),
        "same_tail_count": np.mean(
            np.sum(samples[:, :, pair_i] % 10 == samples[:, :, pair_j] % 10, axis=2), axis=1
        ),
        "odd_count": np.mean(np.sum(samples % 2 == 1, axis=2), axis=1),
        "low_count": np.mean(np.sum(samples <= pool // 2, axis=2), axis=1),
        "sum": np.mean(np.sum(samples, axis=2), axis=1),
        "span": np.mean(samples[:, :, -1] - samples[:, :, 0], axis=1),
        "gap_distribution": np.mean(diffs, axis=(1, 2)),
    }
    if rows > 1:
        overlap = np.sum(
            samples[:, 1:, :, None] == samples[:, :-1, None, :], axis=(2, 3)
        )
        metrics["repeat_from_prev"] = np.mean(overlap, axis=1)
    else:
        metrics["repeat_from_prev"] = np.zeros(batch)
    frequency_stats = np.empty(batch, dtype=float)
    pair_ginis = np.empty(batch, dtype=float)
    expected = rows * pick / pool
    valid_pair_codes = (np.arange(pool)[:, None] * pool + np.arange(pool)[None, :])[np.triu_indices(pool, 1)]
    for index in range(batch):
        counts = np.bincount(samples[index].ravel(), minlength=pool + 1)[1:]
        frequency_stats[index] = float(np.sum((counts - expected) ** 2 / expected))
        codes = (samples[index, :, pair_i] - 1) * pool + (samples[index, :, pair_j] - 1)
        pair_counts = np.bincount(codes.ravel(), minlength=pool * pool)
        pair_ginis[index] = _gini(pair_counts[valid_pair_codes])
    metrics["overall_frequency"] = frequency_stats
    metrics["pair_cooccurrence_gini"] = pair_ginis
    return metrics


def _observed_metrics(draws: Sequence[Draw], config: GameConfig) -> dict[str, float]:
    np, _ = _science()
    samples = np.asarray([draw.numbers for draw in draws], dtype=np.int16)[None, :, :]
    return {key: float(value[0]) for key, value in _history_metrics(samples, config.max_ball).items()}


def _empirical_p(null_values: Any, observed: float, *, upper_only: bool) -> tuple[float, int, float, float]:
    np, _ = _science()
    values = np.asarray(null_values, dtype=float)
    center = float(np.mean(values))
    if upper_only:
        extreme = int(np.sum(values >= observed - 1e-15))
    else:
        extreme = int(np.sum(np.abs(values - center) >= abs(observed - center) - 1e-15))
    return (extreme + 1) / (len(values) + 1), extreme, center, float(np.std(values, ddof=1))


def _monte_carlo_pattern_tests(
    draws: Sequence[Draw], config: GameConfig, simulations: int, seed: int
) -> dict[str, dict[str, Any]]:
    np, _ = _science()
    observed = _observed_metrics(draws, config)
    metric_names = ("overall_frequency",) + tuple(metric for metric, _ in PATTERN_SPECS)
    nulls = {metric: np.empty(simulations, dtype=float) for metric in metric_names}
    generator = _rng(seed, config.game, "exact_draw_model")
    batch_size = 16
    for start in range(0, simulations, batch_size):
        size = min(batch_size, simulations - start)
        samples = _sample_histories(
            generator, size, len(draws), config.pick_count, config.max_ball
        )
        metrics = _history_metrics(samples, config.max_ball)
        for metric in metric_names:
            nulls[metric][start : start + size] = metrics[metric]
    results: dict[str, dict[str, Any]] = {}
    for metric in metric_names:
        p_value, extreme, null_mean, null_sd = _empirical_p(
            nulls[metric], observed[metric], upper_only=metric == "overall_frequency"
        )
        results[metric] = {
            "statistic": observed[metric],
            "p_raw": p_value,
            "null_mean": null_mean,
            "null_sd": null_sd,
            "monte_carlo_extreme_count": extreme,
            "simulations": simulations,
        }
    return results


def _special_test(draws: Sequence[Draw], config: GameConfig) -> dict[str, Any]:
    _, stats = _science()
    assert config.special_min is not None and config.special_max is not None
    values = [draw.special for draw in draws]
    counts = [values.count(value) for value in range(config.special_min, config.special_max + 1)]
    expected = len(values) / len(counts)
    statistic = sum((count - expected) ** 2 / expected for count in counts)
    return {
        "statistic": statistic,
        "p_raw": float(stats.chi2.sf(statistic, len(counts) - 1)),
        "df": len(counts) - 1,
        "value_domain": [config.special_min, config.special_max],
        "marginal_null": "uniform",
    }


def _runs_test(binary: Sequence[bool]) -> dict[str, Any]:
    _, stats = _science()
    values = [bool(value) for value in binary]
    n1 = sum(values)
    n0 = len(values) - n1
    if n1 == 0 or n0 == 0 or len(values) < 2:
        raise AuditContractError("runs test requires both binary states")
    runs = 1 + sum(values[index] != values[index - 1] for index in range(1, len(values)))
    mean = 1 + 2 * n1 * n0 / (n1 + n0)
    variance = (
        2 * n1 * n0 * (2 * n1 * n0 - n1 - n0)
        / ((n1 + n0) ** 2 * (n1 + n0 - 1))
    )
    z_score = (runs - mean) / math.sqrt(variance)
    return {
        "statistic": z_score,
        "p_raw": float(2 * stats.norm.sf(abs(z_score))),
        "runs": runs,
        "true_count": n1,
        "false_count": n0,
    }


def _ljung_box(values: Sequence[float], lag: int = 20) -> dict[str, Any]:
    np, stats = _science()
    series = np.asarray(values, dtype=float)
    centered = series - np.mean(series)
    denominator = float(np.dot(centered, centered))
    if denominator == 0.0:
        raise AuditContractError("Ljung-Box series has zero variance")
    effective_lag = min(lag, len(series) - 1)
    q_value = 0.0
    for offset in range(1, effective_lag + 1):
        correlation = float(np.dot(centered[offset:], centered[:-offset]) / denominator)
        q_value += correlation * correlation / (len(series) - offset)
    q_value *= len(series) * (len(series) + 2)
    return {
        "statistic": q_value,
        "p_raw": float(stats.chi2.sf(q_value, effective_lag)),
        "lag": effective_lag,
        "df": effective_lag,
    }


def _half_dispersion(matrix: Any, first_indices: Any) -> float:
    np, _ = _science()
    first = np.sum(matrix[first_indices], axis=0).astype(float)
    total = np.sum(matrix, axis=0).astype(float)
    second = total - first
    row_totals = np.asarray([np.sum(first), np.sum(second)], dtype=float)
    grand = float(np.sum(total))
    expected_first = total * row_totals[0] / grand
    expected_second = total * row_totals[1] / grand
    return float(
        np.sum((first - expected_first) ** 2 / expected_first)
        + np.sum((second - expected_second) ** 2 / expected_second)
    )


def _drift_test(
    draws: Sequence[Draw], config: GameConfig, simulations: int, seed: int
) -> dict[str, Any]:
    np, _ = _science()
    matrix = np.zeros((len(draws), config.max_ball), dtype=np.uint8)
    for row_index, draw in enumerate(draws):
        matrix[row_index, np.asarray(draw.numbers) - 1] = 1
    first_size = len(draws) // 2
    observed_indices = np.arange(first_size)
    observed = _half_dispersion(matrix, observed_indices)
    generator = _rng(seed, config.game, "half_drift_permutation")
    extreme = 0
    for _ in range(simulations):
        indices = generator.permutation(len(draws))[:first_size]
        extreme += _half_dispersion(matrix, indices) >= observed - 1e-15
    return {
        "statistic": observed,
        "p_raw": (extreme + 1) / (simulations + 1),
        "monte_carlo_extreme_count": int(extreme),
        "simulations": simulations,
        "first_half_rows": first_size,
        "second_half_rows": len(draws) - first_size,
    }


def _serial_tests(
    draws: Sequence[Draw], config: GameConfig, simulations: int, seed: int
) -> dict[str, dict[str, Any]]:
    sums = [sum(draw.numbers) for draw in draws]
    odd_majority = [sum(number % 2 for number in draw.numbers) > config.pick_count / 2 for draw in draws]
    repeat_overlap = [
        bool(set(draws[index].numbers).intersection(draws[index - 1].numbers))
        for index in range(1, len(draws))
    ]
    return {
        "ljungbox_sum": _ljung_box(sums),
        "runs_odd": _runs_test(odd_majority),
        "runs_repeat": _runs_test(repeat_overlap),
        "drift_halves": _drift_test(draws, config, simulations, seed),
    }


def _exploratory_position_tests(
    draws: Sequence[Draw], config: GameConfig
) -> dict[str, dict[str, Any]]:
    np, stats = _science()
    matrix = np.asarray([draw.numbers for draw in draws], dtype=int)
    expected = len(draws) / config.max_ball
    results: dict[str, dict[str, Any]] = {}
    for position in range(config.pick_count):
        counts = np.bincount(matrix[:, position], minlength=config.max_ball + 1)[1:]
        statistic = float(np.sum((counts - expected) ** 2 / expected))
        results[f"position_{position + 1}"] = {
            "statistic": statistic,
            "p_raw": float(stats.chi2.sf(statistic, config.max_ball - 1)),
            "diagnostic_label": "SORTED_ORDER_ARTIFACT",
        }
    return results


def _run_tests(
    draws_by_game: Mapping[str, Sequence[Draw]], simulations: int, seed: int, alpha: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_results: dict[str, dict[str, Any]] = {}
    exploratory_results: dict[str, dict[str, Any]] = {}
    config_by_game = {config.game: config for config in GAME_CONFIGS}
    for config in GAME_CONFIGS:
        draws = draws_by_game[config.game]
        monte_carlo = _monte_carlo_pattern_tests(draws, config, simulations, seed)
        raw_results[f"{config.game}_overall_frequency"] = monte_carlo["overall_frequency"]
        if config.special_min is not None:
            raw_results[f"{config.game}_special_uniformity"] = _special_test(draws, config)
        for metric, _ in PATTERN_SPECS:
            raw_results[f"{config.game}_pattern_{metric}"] = monte_carlo[metric]
        serial = _serial_tests(draws, config, simulations, seed)
        for suffix, value in serial.items():
            raw_results[f"{config.game}_{suffix}"] = value
        positions = _exploratory_position_tests(draws, config)
        for suffix, value in positions.items():
            exploratory_results[f"{config.game}_{suffix}"] = value

    registry_ids = [entry["test_id"] for entry in CONFIRMATORY_REGISTRY]
    if set(raw_results) != set(registry_ids) or len(raw_results) != len(registry_ids):
        raise AuditContractError("executed confirmatory tests do not match the frozen registry")
    p_values = [float(raw_results[test_id]["p_raw"]) for test_id in registry_ids]
    corrections = correction_gate_summary(
        p_values,
        alpha=alpha,
        methods=("bonferroni", "bh_fdr"),
        family_label=CONFIRMATORY_FAMILY,
    )
    tests: list[dict[str, Any]] = []
    for index, registry_entry in enumerate(CONFIRMATORY_REGISTRY):
        value = dict(registry_entry)
        value.update(raw_results[registry_entry["test_id"]])
        value.update(
            {
                "confirmatory": True,
                "p_bonferroni": corrections["bonferroni"]["adjusted_p_values"][index],
                "q_bh_fdr": corrections["bh_fdr"]["adjusted_p_values"][index],
                "bonferroni_reject": corrections["bonferroni"]["rejected"][index],
                "bh_fdr_reject": corrections["bh_fdr"]["rejected"][index],
            }
        )
        if value["bonferroni_reject"] or value["bh_fdr_reject"]:
            verdict = "SIGNIFICANT_DEVIATION_REQUIRES_REVIEW"
        elif value["p_raw"] < alpha:
            verdict = "WEAK_DEVIATION_NOT_SIGNIFICANT_AFTER_CORRECTION"
        else:
            verdict = "CONSISTENT_WITH_RANDOM_DRAW_MODEL"
        value["verdict"] = verdict
        tests.append(value)

    for registry_entry in EXPLORATORY_REGISTRY:
        value = dict(registry_entry)
        value.update(exploratory_results[registry_entry["test_id"]])
        value.update(
            {
                "confirmatory": False,
                "p_bonferroni": None,
                "q_bh_fdr": None,
                "bonferroni_reject": None,
                "bh_fdr_reject": None,
                "verdict": "EXPLORATORY_SORTED_ORDER_ARTIFACT",
            }
        )
        tests.append(value)
    if any(test["correction_family"] is not None for test in tests if not test["confirmatory"]):
        raise AuditContractError("exploratory diagnostics entered the correction family")
    return tests, corrections


def _historical_evidence(existing: Mapping[str, Any]) -> dict[str, Any]:
    if existing.get("audit_version") == AUDIT_VERSION:
        provenance = existing.get("provenance", {})
        history = provenance.get("historical_evidence")
        if isinstance(history, dict):
            return history
    return {
        "actual_statistical_run_timestamp": "2026-05-01T23:39:17.808663Z",
        "actual_run_provenance": "initial artifact commit 0b33c88d",
        "artifact_claimed_run_timestamp": existing.get("run_timestamp"),
        "artifact_re_attestation_timestamp": existing.get("re_attestation_timestamp"),
        "artifact_re_attestation_type": existing.get("re_attestation_type"),
        "reanalysis_performed": existing.get("reanalysis_performed", False),
        "new_draws_analyzed": existing.get("new_draws_analyzed", False),
        "timestamp_only_changes": ["56a79f98", "d119ea6a", "9c5991f3"],
        "re_attestation_changes": ["d36e2544", "e64a4b56"],
        "historical_confirmatory_test_count": sum(
            bool(test.get("confirmatory")) for test in existing.get("tests", [])
        ),
        "historical_test_registry_recovered_from_artifact": True,
        "historical_producer_source_committed": False,
    }


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
=======
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
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
<<<<<<< HEAD
        raise AuditContractError("run timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AuditContractError("run_timestamp must use explicit UTC Z notation")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AuditContractError("run_timestamp is malformed") from exc
    return parsed.astimezone(timezone.utc)


def compute_audit(
    *,
    db_path: Path,
    seed: int,
    simulations: int,
    alpha: float,
    existing_results: Mapping[str, Any],
    run_timestamp: Optional[datetime] = None,
) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise AuditContractError("seed must be a non-negative integer")
    if isinstance(simulations, bool) or not isinstance(simulations, int) or simulations < 16:
        raise AuditContractError("simulations must be an integer >= 16")
    if not (0.0 < alpha < 1.0):
        raise AuditContractError("alpha must be between 0 and 1")
    started = run_timestamp or datetime.now(timezone.utc)
    run_timestamp_text = _format_utc(started)
    data = load_canonical_data(db_path)
    tests, corrections = _run_tests(data["draws"], simulations, seed, alpha)
    confirmatory = [test for test in tests if test["confirmatory"]]
    corrected_rejections = [
        test for test in confirmatory if test["bonferroni_reject"] or test["bh_fdr_reject"]
    ]
    raw_deviations = [test for test in confirmatory if test["p_raw"] < alpha]
    if corrected_rejections:
        final_verdict = "SIGNIFICANT_DEVIATION_REQUIRES_REVIEW"
        strategy_implication = "RANDOMNESS_DEVIATION_REQUIRES_OWNER_REVIEW_NO_STRATEGY_ACTION"
    elif raw_deviations:
        final_verdict = "WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION"
        strategy_implication = "NO_EXPLOITABLE_EDGE_FROM_DRAW_PROCESS"
    else:
        final_verdict = "CONSISTENT_WITH_RANDOM_DRAW_MODEL"
        strategy_implication = "NO_EXPLOITABLE_EDGE_FROM_DRAW_PROCESS"
    previous_verdict = existing_results.get(
        "final_verdict", "WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION"
    )
    substantive_change = final_verdict != previous_verdict
    runner_sha = _sha256_file(Path(__file__).resolve())
    correction_sha = _sha256_file(CORRECTION_SOURCE)
    base_head = _git_head()
    precommit_identity = _sha256_bytes(
        _canonical_json_bytes(
            {
                "base_head": base_head,
                "runner_sha256": runner_sha,
                "correction_source_sha256": correction_sha,
                "registry_sha256": registry_sha256(),
            }
        )
    )
    sources = data["sources"]
    new_draws_analyzed = any(source["new_draws_included"] for source in sources)
    import numpy as np
    import scipy

    games = {}
    for config in GAME_CONFIGS:
        game_tests = [test["test_id"] for test in tests if test["game"] == config.game]
        games[config.game] = {
            "data_source": next(source for source in sources if source["game"] == config.game),
            "test_ids": game_tests,
        }
    result = {
        "run_timestamp": run_timestamp_text,
        "audit_version": AUDIT_VERSION,
        "audit_commit": f"precommit:{base_head}:{precommit_identity}",
        "audit_source": AUDIT_SOURCE,
        "simulations": simulations,
        "seed": seed,
        "alpha": alpha,
        "confirmatory_test_count": len(confirmatory),
        "exploratory_test_count": len(tests) - len(confirmatory),
        "multiple_testing_methods": ["bonferroni", "bh_fdr"],
        "reanalysis_performed": True,
        "new_draws_analyzed": new_draws_analyzed,
        "data_sources": sources,
        "dataset_identity": data["dataset_identity"],
        "confirmatory_registry": list(CONFIRMATORY_REGISTRY),
        "confirmatory_registry_sha256": registry_sha256(),
        "games": games,
        "tests": tests,
        "multiple_testing": corrections,
        "final_verdict": final_verdict,
        "strategy_implication": strategy_implication,
        "substantive_verdict_change": substantive_change,
        "audit_execution": {
            "run_timestamp": run_timestamp_text,
            "timezone": "UTC",
            "parameters_frozen_before_current_p_values": True,
            "registry_frozen_before_current_p_values": True,
            "database_write_performed": False,
            "python_version": sys.version.split()[0],
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "rng": "numpy.random.PCG64 via deterministic derived seeds",
        },
        "validation_results": {
            "canonical_schema": {"status": "PASS"},
            "read_only_database": {"status": "PASS"},
            "dataset_binding": {"status": "PASS"},
            "data_quality": {"status": "PASS"},
            "confirmatory_registry_frozen": {"status": "PASS"},
            "exploratory_tests_excluded_from_correction": {"status": "PASS"},
            "multiple_testing_correction": {"status": "PASS"},
        },
        "provenance": {
            "implementation": {
                "source": AUDIT_SOURCE,
                "reason": "historical producer absent; exact 44-test registry recovered from committed artifact",
                "runner_path": "scripts/randomness_audit.py",
                "runner_sha256": runner_sha,
                "correction_source": "lottery_api/utils/correction_gate.py",
                "correction_source_sha256": correction_sha,
                "rejected_candidate": (
                    "c80f006c P691 migration audited only Big Lotto with five checks and retained "
                    "stale top-level freshness fields"
                ),
                "historical_parity_claimed": False,
            },
            "historical_evidence": _historical_evidence(existing_results),
        },
        "cadence": {
            "anchor": "run_timestamp",
            "max_calendar_days": CADENCE_MAX_CALENDAR_DAYS,
            "max_new_draws": CADENCE_MAX_NEW_DRAWS,
            "re_attestation_resets_cadence": False,
            "timezone": "UTC",
        },
        "limitations": [
            "Statistical compatibility does not prove physical randomness.",
            "The confirmatory family contains correlated tests; Bonferroni is the conservative family-wise gate.",
            "Monte Carlo p-values have finite resolution determined by simulations + 1.",
            "Sorted-position diagnostics are exploratory artifacts and are excluded from correction.",
            "The Big Lotto source is the canonical-main view; the historical artifact used a legacy 49_LOTTO population.",
            "No result is a prediction, strategy promotion, or betting recommendation.",
        ],
    }
    if len(confirmatory) != 44 or len(tests) != 61:
        raise AuditContractError("unexpected test count")
    return result


def render_summary(result: Mapping[str, Any]) -> str:
    lines = [
        "# Lottery Randomness Audit Report",
        "",
        f"**Run timestamp:** {result['run_timestamp']}",
        f"**Audit version:** {result['audit_version']}",
        f"**Audit commit:** `{result['audit_commit']}`",
        f"**Simulations:** {result['simulations']:,}",
        f"**Seed:** {result['seed']}",
        f"**Alpha:** {result['alpha']}",
        f"**Total confirmatory tests:** {result['confirmatory_test_count']}",
        f"**Exploratory sorted-position diagnostics:** {result['exploratory_test_count']}",
        "**Cadence anchor:** `run_timestamp` (UTC)",
        "**Reanalysis performed:** YES",
        f"**New draws analyzed:** {'YES' if result['new_draws_analyzed'] else 'NO'}",
        "",
        "## FINAL VERDICT",
        "",
        f"**{result['final_verdict']}**",
        "",
        f"> Strategy implication: {result['strategy_implication']}",
        "",
    ]
    if result["substantive_verdict_change"]:
        lines.extend(("**SUBSTANTIVE_VERDICT_CHANGE**", ""))
    lines.extend(
        (
            "## Canonical Data Binding",
            "",
            "| Game | Source | Rows | Date min | Date max | Excluded | SHA-256 |",
            "|---|---|---:|---|---|---:|---|",
        )
    )
    for source in result["data_sources"]:
        lines.append(
            f"| {source['game']} | `{source['source']}` | {source['row_count']} | "
            f"{source['date_min']} | {source['date_max']} | {source['excluded_row_count']} | "
            f"`{source['digest']}` |"
        )
    lines.extend(("", "## Data Quality Classification", ""))
    for source in result["data_sources"]:
        lines.append(
            f"- **{source['game']}**: duplicate draw IDs {source['duplicate_draw_ids']}; "
            f"duplicate full records {source['duplicate_full_records']}; repeated main combinations "
            f"on different draw IDs {source['repeated_main_combinations']}; invalid repeated numbers "
            f"inside a draw {source['invalid_repeated_numbers_inside_draw']}."
        )
    lines.extend(
        (
            "",
            "Repeated winning combinations across distinct draw IDs are possible outcomes, not duplicate database rows.",
            "",
            "## Confirmatory Results",
            "",
            "| Test ID | Statistic | p raw | Bonferroni p | BH-FDR q | Verdict |",
            "|---|---:|---:|---:|---:|---|",
        )
    )
    for test in result["tests"]:
        if not test["confirmatory"]:
            continue
        lines.append(
            f"| `{test['test_id']}` | {test['statistic']:.6g} | {test['p_raw']:.6g} | "
            f"{test['p_bonferroni']:.6g} | {test['q_bh_fdr']:.6g} | {test['verdict']} |"
        )
    lines.extend(
        (
            "",
            "## Exploratory Sorted-Position Diagnostics",
            "",
            "All 17 position tests compare sorted values with an intentionally inapplicable marginal-uniform reference. "
            "They are retained only to expose the sorted-order artifact and are excluded from Bonferroni and BH-FDR.",
            "",
            "## Cadence",
            "",
            f"A new executable audit is required after more than {CADENCE_MAX_CALENDAR_DAYS} calendar days or "
            f"after {CADENCE_MAX_NEW_DRAWS} new canonical draws, whichever occurs first. "
            "Re-attestation of unchanged evidence resets neither trigger.",
            "",
            "## Provenance and Limitations",
            "",
            "- Implementation: **RECONSTRUCTED** from the committed 44-test registry; historical parity is not claimed.",
            "- Big Lotto special-number marginal null: uniform over **1..49**, matching the sequential 6+special draw mechanism.",
            "- Big Lotto source: `draws_big_lotto_canonical_main`; the older 2,130-row artifact matched legacy `49_LOTTO`.",
        )
    )
    for limitation in result["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(("", "Research and entertainment only; not betting advice.", ""))
    return "\n".join(lines)


def _write_pair(results_text: str, summary_text: str, results_path: Path, summary_path: Path) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    original_results = results_path.read_bytes() if results_path.exists() else None
    original_summary = summary_path.read_bytes() if summary_path.exists() else None
    staged: list[Path] = []
    try:
        for target, payload in (
            (results_path, results_text.encode("utf-8")),
            (summary_path, summary_text.encode("utf-8")),
        ):
            descriptor, raw_path = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".stage")
            os.close(descriptor)
            stage = Path(raw_path)
            stage.write_bytes(payload)
            staged.append(stage)
        os.replace(staged[1], summary_path)
        os.replace(staged[0], results_path)
    except Exception:
        if original_summary is None:
            summary_path.unlink(missing_ok=True)
        else:
            summary_path.write_bytes(original_summary)
        if original_results is None:
            results_path.unlink(missing_ok=True)
        else:
            results_path.write_bytes(original_results)
        raise
    finally:
        for path in staged:
            path.unlink(missing_ok=True)


def _decode_strict_json_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AuditContractError(f"duplicate JSON object key {key!r}")
        value[key] = item
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_decode_strict_json_object,
        )
    except AuditContractError as exc:
        raise AuditContractError(f"unable to load JSON artifact: {path}: {exc}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditContractError(f"unable to load JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise AuditContractError("audit artifact must be a JSON object")
    return value


def normalized_result_digest(result: Mapping[str, Any]) -> str:
    normalized = json.loads(json.dumps(result))
    normalized.pop("run_timestamp", None)
    if isinstance(normalized.get("audit_execution"), dict):
        normalized["audit_execution"].pop("run_timestamp", None)
    return _sha256_bytes(_canonical_json_bytes(normalized))


def run_and_publish(args: argparse.Namespace) -> dict[str, Any]:
    existing = _load_json(args.results_out)
    result = compute_audit(
        db_path=args.db,
        seed=args.seed,
        simulations=args.simulations,
        alpha=args.alpha,
        existing_results=existing,
    )
    results_text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    summary_text = render_summary(result)
    _write_pair(results_text, summary_text, args.results_out, args.summary_out)
    return result


def verify_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    expected = _load_json(args.results)
    expected_timestamp = _parse_utc(expected.get("run_timestamp"))
    recomputed = compute_audit(
        db_path=args.db,
        seed=args.seed,
        simulations=args.simulations,
        alpha=args.alpha,
        existing_results=expected,
        run_timestamp=expected_timestamp,
    )
    if recomputed != expected:
        raise AuditContractError("fresh recomputation does not match committed JSON")
    expected_summary = args.summary.read_text(encoding="utf-8")
    if render_summary(recomputed) != expected_summary:
        raise AuditContractError("fresh recomputation does not match committed Markdown")
    return recomputed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--db", required=True, type=Path)
        subparser.add_argument("--seed", type=int, default=DEFAULT_SEED)
        subparser.add_argument("--simulations", type=int, default=DEFAULT_SIMULATIONS)
        subparser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
        if command == "run":
            subparser.add_argument("--results-out", type=Path, default=RESULTS_PATH)
            subparser.add_argument("--summary-out", type=Path, default=SUMMARY_PATH)
        else:
            subparser.add_argument("--results", type=Path, default=RESULTS_PATH)
            subparser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    subparsers.add_parser("show-registry")
=======
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


def _load_strict_p238b_comparison(path: Path) -> dict[str, Any]:
    """Read P238B once and reproduce the donor's non-statistical comparison view."""
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return {"artifact_found": False}
    document = strict_json_loads(payload, source=str(path))
    if not isinstance(document, Mapping):
        raise AuditProvenanceError("P238B comparison artifact must be a JSON object")
    return {
        "artifact_found": True,
        "classification": document.get("classification", "N/A"),
        "test_count": len(document.get("test_results", [])),
        "is_corrected_significant": document.get("is_corrected_significant", False),
        "note": (
            "P238B ran on raw mixed 22,238-row BIG_LOTTO population including "
            "ADD_ON_PRIZE_EXCLUDED, DATE_FORMAT_ALIEN, SMALL_POOL_ALIEN. "
            "P246K runs on canonical 2,113-row population only."
        ),
    }


def run_p246k_existing_logic(
    population: PopulationLoad,
    db_path: Path,
    *,
    module: Optional[ModuleType] = None,
) -> dict[str, Any]:
    """Call P246K unchanged behind bounded population and comparison seams."""
    p246k = module or _load_p246k_module()
    strict_comparison = None
    if hasattr(p246k, "load_p238b_comparison"):
        strict_comparison = _load_strict_p238b_comparison(P238B_COMPARISON_ARTIFACT)

    with ExitStack() as overrides:
        overrides.enter_context(
            patch.object(
                p246k,
                "load_canonical_draws",
                return_value=(population.draws, population.raw_count),
            )
        )
        if strict_comparison is not None:
            overrides.enter_context(
                patch.object(
                    p246k,
                    "load_p238b_comparison",
                    side_effect=lambda: deepcopy(strict_comparison),
                )
            )
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
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
<<<<<<< HEAD
    args = _parser().parse_args(argv)
    try:
        if args.command == "show-registry":
            print(json.dumps({"count": len(CONFIRMATORY_REGISTRY), "sha256": registry_sha256()}, sort_keys=True))
            return 0
        if args.command == "run":
            result = run_and_publish(args)
            status = "GENERATED"
        else:
            result = verify_artifacts(args)
            status = "VERIFIED"
        print(
            json.dumps(
                {
                    "status": status,
                    "run_timestamp": result["run_timestamp"],
                    "normalized_result_sha256": normalized_result_digest(result),
                    "final_verdict": result["final_verdict"],
                },
                sort_keys=True,
            )
        )
        return 0
    except (AuditContractError, OSError, sqlite3.Error, ValueError) as exc:
=======
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
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
