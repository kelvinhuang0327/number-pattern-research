#!/usr/bin/env python3
"""Deterministic, read-only lottery randomness audit.

The historical 44-test artifact did not include its producer.  This runner
reconstructs that frozen registry, corrects its known methodological defects,
and binds every result to the current canonical SQLite row streams.
"""
from __future__ import annotations

import argparse
import hashlib
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


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
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


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
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
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
