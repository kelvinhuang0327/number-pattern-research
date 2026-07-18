#!/usr/bin/env python3
"""P20C v1 all-strategy BIG_LOTTO 20-ticket historical validation.

The committed CLI supersedes the uncommitted output-only P20 audit runner.  It
keeps native-only behavior available and adds an explicit
``--ticket-constructor strategy-preserving-v1`` mode.  Database access is
strictly read-only, target outcomes are passed only to the evaluator, and
constructor inputs contain only native strategy output plus cutoff identity.

Large draw/replicate detail is written to a task-owned temporary gzip file,
independently read back, hashed, and removed.  Only compact reproducibility
evidence is retained under ``outputs/research``.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
import os
import random
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.strategy_preserving_20_ticket import (  # noqa: E402
    CONSTRUCTOR_NAME,
    CONSTRUCTOR_VERSION,
    SHORT_IDENTIFIER,
    ConstructionTier,
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
    objective_constants,
)


TASK_ID = "P20C_V1_STRATEGY_PRESERVING_20_TICKET_CONSTRUCTOR"
TICKET_CONSTRUCTOR_NATIVE_ONLY = "native-only"
TICKET_CONSTRUCTOR_V1 = "strategy-preserving-v1"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p20c_v1_strategy_preserving_20_ticket_constructor"
)
P541B_ARTIFACT = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"
)
COMMON_MIN_HISTORY = 100
DEFAULT_RANDOM_REPLICATES = 10
DEFAULT_BOOTSTRAP_REPLICATES = 2000
COMPLETENESS_THRESHOLD = 0.99
USER_SEED_NAMESPACE = "p20c-v1-historical-validation"

PRIOR_REFERENCE_ROOT = Path(
    "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/outputs/"
    "all_strategy_20ticket_m4plus_backtest"
)
PRIOR_REFERENCE_FILES = (
    "audit_runner.py",
    "run_manifest.json",
    "environment_manifest.json",
    "reproducibility_manifest.json",
    "final_report.md",
    "validation_results.json",
    "strategy_inventory.csv",
    "strategy_preflight.csv",
    "skipped_and_failed_strategies.csv",
    "draw_level_results.csv",
    "ticket_level_results.csv.gz",
    "random_baseline_metrics.csv",
    "strategy_metrics.csv",
)

EVIDENCE_FILENAMES = (
    "manifest.json",
    "constructor_metrics.csv",
    "m4plus_native_ranking.csv",
    "m4plus_adapter_ranking.csv",
    "failed_strategies.csv",
    "validation_results.json",
    "final_report.md",
)

DETAIL_FIELDS = (
    "base_strategy_id",
    "effective_strategy_id",
    "strategy_name",
    "governance_status",
    "ranking_group",
    "execution_mode",
    "replicate_id",
    "target_index",
    "target_draw",
    "target_date",
    "history_cutoff_identity",
    "status",
    "failure_reason",
    "native_tickets_json",
    "tickets_json",
    "actual_numbers_json",
    "actual_special",
    "native_max_main_hits",
    "native_m4plus",
    "max_main_hits",
    "m4plus",
    "constructor_name",
    "constructor_version",
    "seed_material",
    "seed_digest",
    "native_input_count",
    "native_valid_count",
    "native_duplicate_count",
    "native_invalid_count",
    "native_retained_count",
    "constructed_ticket_count",
    "final_ticket_count",
    "native_ticket_share",
    "signal_source",
    "construction_tier",
    "relaxation_level",
    "warnings_json",
    "portfolio_sha256",
    "native_seed",
)


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    strategy_name: str
    governance_status: str
    min_history: int
    replicates: int
    execution_mode: str
    ranking_group: str
    formerly_partial: bool
    generator: Callable[[list[dict[str, Any]], dict[str, Any], int, int], Sequence[Sequence[int]]]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_seed(namespace: str, *parts: Any) -> int:
    material = "|".join((namespace, *(str(part) for part in parts)))
    return int.from_bytes(
        hashlib.sha256(material.encode("utf-8")).digest()[:8],
        "big",
        signed=False,
    )


@contextlib.contextmanager
def isolated_python_seed(seed: int):
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


@contextlib.contextmanager
def isolated_numpy_seed(seed: int):
    import numpy as np

    state = np.random.get_state()
    np.random.seed(seed & 0xFFFFFFFF)
    try:
        yield
    finally:
        np.random.set_state(state)


def open_database_readonly(database: Path) -> sqlite3.Connection:
    """Open an existing SQLite file without creating journals or new files."""

    database = database.resolve()
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    uri = f"file:{database}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def load_draws_and_quality(database: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    connection = open_database_readonly(database)
    try:
        raw_count = connection.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        rows = connection.execute(
            """SELECT id, draw, date, numbers, special, numbers_positional,
                      jackpot_amount, sell_amount, total_amount
               FROM draws_big_lotto_canonical_main
               ORDER BY CAST(draw AS INTEGER), id"""
        ).fetchall()
        replay_rows = connection.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        replay_targets = connection.execute(
            "SELECT COUNT(DISTINCT target_draw) "
            "FROM strategy_prediction_replays WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        missing_replay = connection.execute(
            """SELECT COUNT(*), COUNT(DISTINCT target_draw)
               FROM strategy_prediction_replays
               WHERE lottery_type='BIG_LOTTO'
                 AND target_draw NOT IN (
                     SELECT draw FROM draws_big_lotto_canonical_main
                 )"""
        ).fetchone()
        noncausal_replay = connection.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE lottery_type='BIG_LOTTO'
                 AND history_cutoff_draw IS NOT NULL
                 AND CAST(history_cutoff_draw AS INTEGER)
                     >= CAST(target_draw AS INTEGER)"""
        ).fetchone()[0]
    finally:
        connection.close()

    draws: list[dict[str, Any]] = []
    seen_draws: Counter[str] = Counter()
    seen_dates: Counter[str] = Counter()
    date_formats: Counter[str] = Counter()
    invalid_json = 0
    wrong_length = 0
    out_of_range = 0
    duplicate_numbers = 0
    invalid_special = 0
    null_positional = 0
    negative_financial = 0

    for row in rows:
        _, draw, date, numbers_raw, special, positional, jackpot, sell, total = row
        seen_draws[str(draw)] += 1
        seen_dates[str(date)] += 1
        date_formats["YYYY/MM/DD" if "/" in str(date) else "other"] += 1
        if positional is None:
            null_positional += 1
        if any(value is not None and value < 0 for value in (jackpot, sell, total)):
            negative_financial += 1
        try:
            numbers = json.loads(numbers_raw)
        except Exception:
            invalid_json += 1
            continue
        if len(numbers) != 6:
            wrong_length += 1
        if any(type(number) is not int or not 1 <= number <= 49 for number in numbers):
            out_of_range += 1
        if len(set(numbers)) != len(numbers):
            duplicate_numbers += 1
        if type(special) is not int or not 1 <= special <= 49 or special in numbers:
            invalid_special += 1
        draws.append(
            {
                "draw": str(draw),
                "date": str(date),
                "numbers": sorted(int(number) for number in numbers),
                "special": int(special),
                "id": int(row[0]),
            }
        )

    dataset_payload = [
        {
            "draw": draw["draw"],
            "date": draw["date"],
            "numbers": draw["numbers"],
            "special": draw["special"],
        }
        for draw in draws
    ]
    quality = {
        "raw_big_lotto_rows": int(raw_count),
        "canonical_main_rows": len(draws),
        "excluded_noncanonical_rows": int(raw_count) - len(draws),
        "first_draw": draws[0]["draw"],
        "last_draw": draws[-1]["draw"],
        "first_date": draws[0]["date"],
        "last_date": draws[-1]["date"],
        "canonical_dataset_sha256": hashlib.sha256(
            canonical_json_bytes(dataset_payload)
        ).hexdigest(),
        "database_sha256": sha256_file(database),
        "duplicate_draw_ids": sum(count > 1 for count in seen_draws.values()),
        "duplicate_dates": sum(count > 1 for count in seen_dates.values()),
        "invalid_json_rows": invalid_json,
        "wrong_main_number_count_rows": wrong_length,
        "out_of_range_rows": out_of_range,
        "duplicate_main_number_rows": duplicate_numbers,
        "invalid_or_overlapping_special_rows": invalid_special,
        "null_numbers_positional_rows": null_positional,
        "negative_financial_rows": negative_financial,
        "date_format_counts": dict(date_formats),
        "outside_selected_window_rows": 0,
        "sample_first_rows": dataset_payload[:5],
        "sample_last_rows": dataset_payload[-5:],
        "common_window_rows": max(0, len(draws) - COMMON_MIN_HISTORY),
        "big_lotto_replay_ticket_rows": int(replay_rows),
        "big_lotto_replay_distinct_targets": int(replay_targets),
        "replay_rows_missing_from_canonical_view": int(missing_replay[0]),
        "replay_targets_missing_from_canonical_view": int(missing_replay[1]),
        "replay_noncausal_cutoff_rows": int(noncausal_replay),
    }
    return draws, quality


def normalise_native_tickets(
    raw_tickets: Sequence[Sequence[int]],
) -> tuple[list[tuple[int, ...]], int, int]:
    unique: set[tuple[int, ...]] = set()
    duplicates = 0
    invalid = 0
    for raw in raw_tickets:
        try:
            if isinstance(raw, (str, bytes)) or len(raw) != 6:
                raise ValueError
            if not all(type(number) is int for number in raw):
                raise ValueError
            ticket = tuple(sorted(raw))
            if len(set(ticket)) != 6 or any(number < 1 or number > 49 for number in ticket):
                raise ValueError
        except (TypeError, ValueError):
            invalid += 1
            continue
        if ticket in unique:
            duplicates += 1
        else:
            unique.add(ticket)
    return sorted(unique), duplicates, invalid


def portfolio_sha256(tickets: Sequence[Sequence[int]]) -> str:
    canonical = [list(ticket) for ticket in sorted(tuple(ticket) for ticket in tickets)]
    return hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()


def evaluate_hits(
    tickets: Sequence[Sequence[int]], actual_numbers: Sequence[int]
) -> tuple[list[int], int, int]:
    actual = set(actual_numbers)
    hits = [len(set(ticket) & actual) for ticket in tickets]
    maximum = max(hits, default=0)
    return hits, maximum, int(maximum >= 4)


def prepare_portfolio(
    *,
    strategy_id: str,
    draw_id: str,
    replicate_id: int,
    cutoff_identity: str,
    raw_tickets: Sequence[Sequence[int]],
    actual_numbers: Sequence[int],
    constructor_mode: str,
    user_seed: str | int = USER_SEED_NAMESPACE,
) -> dict[str, Any]:
    """Pure integration boundary used by the historical runner and tests."""

    native, duplicate_count, invalid_count = normalise_native_tickets(raw_tickets)
    native_hits, native_max, native_m4plus = evaluate_hits(native, actual_numbers)
    _ = native_hits

    if constructor_mode == TICKET_CONSTRUCTOR_NATIVE_ONLY:
        complete = len(native) == 20
        return {
            "ok": complete,
            "status": "COMPLETED_NATIVE_20" if complete else "INSUFFICIENT_TICKETS",
            "failure_reason": "" if complete else "INSUFFICIENT_TICKETS",
            "tickets": tuple(native),
            "native_tickets": tuple(native),
            "native_max_main_hits": native_max,
            "native_m4plus": native_m4plus,
            "metadata": None,
            "native_input_count": len(raw_tickets),
            "native_valid_count": len(native),
            "native_duplicate_count": duplicate_count,
            "native_invalid_count": invalid_count,
        }

    if constructor_mode != TICKET_CONSTRUCTOR_V1:
        raise ValueError(f"unsupported constructor mode: {constructor_mode}")

    result = construct_strategy_preserving_20_ticket(
        ConstructorRequest(
            strategy_id=strategy_id,
            draw_id=draw_id,
            replicate_id=replicate_id,
            raw_tickets=raw_tickets,
            historical_cutoff_identity=cutoff_identity,
            user_seed=user_seed,
        )
    )
    if not isinstance(result, ConstructorSuccess):
        return {
            "ok": False,
            "status": "CONSTRUCTOR_FAILURE",
            "failure_reason": result.reason.value,
            "tickets": (),
            "native_tickets": tuple(native),
            "native_max_main_hits": native_max,
            "native_m4plus": native_m4plus,
            "metadata": None,
            "constructor_failure": result.to_dict(),
            "native_input_count": len(raw_tickets),
            "native_valid_count": len(native),
            "native_duplicate_count": duplicate_count,
            "native_invalid_count": invalid_count,
        }
    return {
        "ok": True,
        "status": "COMPLETED_NATIVE_20"
        if result.metadata.construction_tier == ConstructionTier.NATIVE_COMPLETE.value
        else "COMPLETED_ADAPTER_20",
        "failure_reason": "",
        "tickets": result.tickets,
        "native_tickets": tuple(native),
        "native_max_main_hits": native_max,
        "native_m4plus": native_m4plus,
        "metadata": result.metadata,
        "native_input_count": len(raw_tickets),
        "native_valid_count": len(native),
        "native_duplicate_count": duplicate_count,
        "native_invalid_count": invalid_count,
    }


def _uniform_baseline(
    history: list[dict[str, Any]],
    target: dict[str, Any],
    replicate: int,
    seed: int,
) -> list[list[int]]:
    del history, target, replicate
    generator = random.Random(seed)
    tickets: set[tuple[int, ...]] = set()
    while len(tickets) < 20:
        tickets.add(tuple(sorted(generator.sample(range(1, 50), 6))))
    return [list(ticket) for ticket in sorted(tickets)]


def build_strategy_specs(random_replicates: int) -> list[StrategySpec]:
    """Load only the 15 previously preflighted causal generator identities."""

    from lottery_api.models.core_satellite import CoreSatelliteStrategy
    from lottery_api.models.p42_wave3_biglotto_adapters import WAVE3_ADAPTER_MAP
    from lottery_api.models.p93_tierb_replay_adapters import (
        BigLottoEchoAware3BetAdapter,
        BigLottoTs3Markov4BetW30Adapter,
    )
    from lottery_api.models.replay_strategy_registry import (
        _ts3_regime_3bet_predict,
        get_strategy_lifecycle_status,
    )
    from lottery_api.models.social_wisdom_predictor import SocialWisdomPredictor
    from lottery_api.models.zone_split import ZoneSplitStrategy
    from tools.predict_biglotto_deviation_2bet import deviation_complement_2bet
    from tools.predict_biglotto_triple_strike import generate_triple_strike

    def zone(history, target, replicate, seed):
        del history, target, replicate
        with isolated_python_seed(seed):
            return ZoneSplitStrategy(max_num=49, pick_count=6).generate_bets(20)

    def core(history, target, replicate, seed):
        del history, target, replicate
        with isolated_python_seed(seed):
            pool = list(range(1, 50))
            random.shuffle(pool)
            return CoreSatelliteStrategy(max_num=49, pick_count=6).generate_bets(
                20, candidate_pool=pool, core_size=2
            )

    def social(history, target, replicate, seed):
        del target, replicate
        newest_first = list(reversed(history[-50:]))
        with isolated_numpy_seed(seed):
            rows = SocialWisdomPredictor(max_num=49).generate_8_bets(
                newest_first, pick_count=6
            )
        return [row["numbers"] for row in rows]

    def triple(history, target, replicate, seed):
        del target, replicate, seed
        return generate_triple_strike(history)

    def deviation(history, target, replicate, seed):
        del target, replicate, seed
        return deviation_complement_2bet(history)

    def ts3(history, target, replicate, seed):
        del target, replicate, seed
        return _ts3_regime_3bet_predict(history)

    echo_adapter = BigLottoEchoAware3BetAdapter()
    markov4_adapter = BigLottoTs3Markov4BetW30Adapter()

    def echo(history, target, replicate, seed):
        del target, replicate, seed
        return echo_adapter.get_all_bets(history)

    def markov4(history, target, replicate, seed):
        del target, replicate, seed
        return markov4_adapter.get_all_bets(history)

    def governed_status(short_id: str) -> str:
        return {
            "ONLINE": "accepted",
            "REJECTED": "rejected",
            "RETIRED": "deprecated",
            "OBSERVATION": "experimental",
        }.get(get_strategy_lifecycle_status(short_id) or "", "unknown")

    specs = [
        StrategySpec(
            "baseline::uniform_random_20",
            "Uniform Random 20-ticket Baseline",
            "baseline",
            0,
            random_replicates,
            "uniform_random_sha256_seeded",
            "baseline",
            False,
            _uniform_baseline,
        ),
        StrategySpec(
            "history::lottery_api/models/zone_split.py",
            "zone_split",
            "candidate",
            0,
            random_replicates,
            "direct_original_seeded_by_caller",
            "native",
            False,
            zone,
        ),
        StrategySpec(
            "history::lottery_api/models/core_satellite.py",
            "core_satellite",
            "candidate",
            0,
            random_replicates,
            "direct_original_seeded_by_caller",
            "native",
            False,
            core,
        ),
        StrategySpec(
            "history::lottery_api/models/social_wisdom_predictor.py",
            "social_wisdom_predictor",
            "candidate",
            1,
            random_replicates,
            "direct_original_8bet_seeded_by_caller",
            "adapter",
            True,
            social,
        ),
        StrategySpec(
            "registry::biglotto_triple_strike",
            "大樂透 Triple Strike",
            governed_status("biglotto_triple_strike"),
            100,
            1,
            "direct_original_generator",
            "adapter",
            True,
            triple,
        ),
        StrategySpec(
            "registry::biglotto_deviation_2bet",
            "大樂透 Deviation 2注",
            governed_status("biglotto_deviation_2bet"),
            100,
            1,
            "direct_original_generator",
            "adapter",
            True,
            deviation,
        ),
        StrategySpec(
            "registry::ts3_regime_3bet",
            "大樂透 TS3+Regime 3注",
            governed_status("ts3_regime_3bet"),
            100,
            1,
            "existing_registry_compatibility_reconstruction",
            "adapter",
            True,
            ts3,
        ),
        StrategySpec(
            "registry::biglotto_echo_aware_3bet",
            "大樂透 Echo Aware 3注",
            governed_status("biglotto_echo_aware_3bet"),
            100,
            1,
            "existing_p93_compatibility_adapter",
            "adapter",
            True,
            echo,
        ),
        StrategySpec(
            "registry::biglotto_ts3_markov_4bet_w30",
            "大樂透 TS3+Markov 4注 w30",
            governed_status("biglotto_ts3_markov_4bet_w30"),
            100,
            1,
            "existing_p93_compatibility_adapter",
            "adapter",
            True,
            markov4,
        ),
    ]

    wave_names = {
        "markov_single_biglotto": "大樂透 Markov Single",
        "markov_2bet_biglotto": "大樂透 Markov 2注",
        "bet2_fourier_expansion_biglotto": "大樂透 Bet2 Fourier Expansion",
        "fourier30_markov30_biglotto": "大樂透 Fourier30+Markov30",
        "cold_complement_biglotto": "大樂透 Cold Complement",
        "coldpool15_biglotto": "大樂透 ColdPool-15",
    }
    wave_minimum = {
        "markov_single_biglotto": 100,
        "markov_2bet_biglotto": 100,
        "bet2_fourier_expansion_biglotto": 50,
        "fourier30_markov30_biglotto": 30,
        "cold_complement_biglotto": 100,
        "coldpool15_biglotto": 100,
    }
    wave_modes = {
        "markov_2bet_biglotto": "existing_p42_compatibility_adapter_bet1_only",
        "bet2_fourier_expansion_biglotto": "existing_p42_compatibility_adapter_bet1_only",
        "fourier30_markov30_biglotto": "existing_p42_compatibility_adapter_bet1_only",
        "cold_complement_biglotto": "existing_p42_compatibility_adapter_bet1_only",
    }
    for short_id in sorted(wave_names):
        adapter = WAVE3_ADAPTER_MAP[short_id]

        def one_bet(history, target, replicate, seed, _adapter=adapter):
            del target, replicate, seed
            numbers, _ = _adapter.get_one_bet(history, "BIG_LOTTO")
            return [numbers]

        specs.append(
            StrategySpec(
                f"registry::{short_id}",
                wave_names[short_id],
                governed_status(short_id),
                wave_minimum[short_id],
                1,
                wave_modes.get(short_id, "existing_p42_compatibility_adapter"),
                "adapter",
                True,
                one_bet,
            )
        )
    return specs


def _detail_row(
    *,
    spec: StrategySpec,
    target_index: int,
    target: dict[str, Any],
    cutoff: str,
    replicate: int,
    native_seed: int,
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    tickets = portfolio["tickets"]
    _, maximum, m4plus = evaluate_hits(tickets, target["numbers"])
    metadata = portfolio.get("metadata")
    if metadata is not None:
        metadata_record = metadata.to_dict()
        effective = metadata.effective_strategy_id
    else:
        metadata_record = {}
        effective = spec.strategy_id
    return {
        "base_strategy_id": spec.strategy_id,
        "effective_strategy_id": effective,
        "strategy_name": spec.strategy_name,
        "governance_status": spec.governance_status,
        "ranking_group": spec.ranking_group,
        "execution_mode": spec.execution_mode,
        "replicate_id": replicate,
        "target_index": target_index,
        "target_draw": target["draw"],
        "target_date": target["date"],
        "history_cutoff_identity": cutoff,
        "status": portfolio["status"],
        "failure_reason": portfolio["failure_reason"],
        "native_tickets_json": json.dumps(portfolio["native_tickets"], separators=(",", ":")),
        "tickets_json": json.dumps(tickets, separators=(",", ":")),
        "actual_numbers_json": json.dumps(target["numbers"], separators=(",", ":")),
        "actual_special": target["special"],
        "native_max_main_hits": portfolio["native_max_main_hits"],
        "native_m4plus": portfolio["native_m4plus"],
        "max_main_hits": maximum,
        "m4plus": m4plus,
        "constructor_name": metadata_record.get("constructor_name", ""),
        "constructor_version": metadata_record.get("constructor_version", ""),
        "seed_material": metadata_record.get("seed_material", ""),
        "seed_digest": metadata_record.get("seed_digest", ""),
        "native_input_count": portfolio["native_input_count"],
        "native_valid_count": portfolio["native_valid_count"],
        "native_duplicate_count": portfolio["native_duplicate_count"],
        "native_invalid_count": portfolio["native_invalid_count"],
        "native_retained_count": metadata_record.get(
            "native_retained_count", len(portfolio["native_tickets"])
        ),
        "constructed_ticket_count": metadata_record.get("constructed_ticket_count", 0),
        "final_ticket_count": len(tickets),
        "native_ticket_share": metadata_record.get(
            "native_ticket_share", len(portfolio["native_tickets"]) / 20 if tickets else 0
        ),
        "signal_source": metadata_record.get("signal_source", "random_baseline"),
        "construction_tier": metadata_record.get(
            "construction_tier", "random_baseline"
        ),
        "relaxation_level": metadata_record.get("relaxation_level", 0),
        "warnings_json": json.dumps(metadata_record.get("warnings", ()), separators=(",", ":")),
        "portfolio_sha256": metadata_record.get(
            "portfolio_sha256", portfolio_sha256(tickets) if tickets else ""
        ),
        "native_seed": native_seed,
    }


def execute_backtest(
    *,
    draws: list[dict[str, Any]],
    specs: Sequence[StrategySpec],
    constructor_mode: str,
    detail_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    runtime_failures: list[dict[str, Any]] = []
    reproducibility_samples: dict[str, dict[str, Any]] = {}
    portfolio_digest = hashlib.sha256()

    with detail_path.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=6,
            fileobj=raw_handle,
            mtime=0,
        ) as compressed_handle:
            with io.TextIOWrapper(
                compressed_handle, encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=DETAIL_FIELDS)
                writer.writeheader()
                for spec in specs:
                    for target_index in range(spec.min_history, len(draws)):
                        history = draws[:target_index]
                        target = draws[target_index]
                        cutoff = history[-1]["draw"] if history else "GENESIS"
                        for replicate in range(spec.replicates):
                            native_seed = stable_seed(
                                "p20c-native-v1",
                                spec.strategy_id,
                                target["draw"],
                                replicate,
                            )
                            try:
                                raw = spec.generator(
                                    history, target, replicate, native_seed
                                )
                                if spec.ranking_group == "baseline":
                                    native, duplicates, invalid = (
                                        normalise_native_tickets(raw)
                                    )
                                    portfolio = {
                                        "ok": len(native) == 20,
                                        "status": "COMPLETED_RANDOM_BASELINE"
                                        if len(native) == 20
                                        else "BASELINE_FAILURE",
                                        "failure_reason": ""
                                        if len(native) == 20
                                        else "CANNOT_REACH_UNIQUE_TARGET",
                                        "tickets": tuple(native),
                                        "native_tickets": (),
                                        "native_max_main_hits": 0,
                                        "native_m4plus": 0,
                                        "metadata": None,
                                        "native_input_count": len(raw),
                                        "native_valid_count": len(native),
                                        "native_duplicate_count": duplicates,
                                        "native_invalid_count": invalid,
                                    }
                                else:
                                    portfolio = prepare_portfolio(
                                        strategy_id=spec.strategy_id,
                                        draw_id=target["draw"],
                                        replicate_id=replicate,
                                        cutoff_identity=cutoff,
                                        raw_tickets=raw,
                                        actual_numbers=target["numbers"],
                                        constructor_mode=constructor_mode,
                                    )
                            except Exception as exc:
                                portfolio = {
                                    "ok": False,
                                    "status": "GENERATOR_FAILURE",
                                    "failure_reason": f"{type(exc).__name__}: {exc}",
                                    "tickets": (),
                                    "native_tickets": (),
                                    "native_max_main_hits": 0,
                                    "native_m4plus": 0,
                                    "metadata": None,
                                    "native_input_count": 0,
                                    "native_valid_count": 0,
                                    "native_duplicate_count": 0,
                                    "native_invalid_count": 0,
                                }
                            row = _detail_row(
                                spec=spec,
                                target_index=target_index,
                                target=target,
                                cutoff=cutoff,
                                replicate=replicate,
                                native_seed=native_seed,
                                portfolio=portfolio,
                            )
                            writer.writerow(row)
                            portfolio_digest.update(canonical_json_bytes(row))
                            observations.append(row)
                            if not portfolio["ok"]:
                                runtime_failures.append(
                                    {
                                        "strategy_id": spec.strategy_id,
                                        "governance_status": spec.governance_status,
                                        "failure_stage": row["status"],
                                        "reason_code": row["failure_reason"],
                                        "target_draw": target["draw"],
                                        "replicate_id": replicate,
                                        "detailed_reason": row["failure_reason"],
                                    }
                                )
                            elif (
                                spec.ranking_group != "baseline"
                                and spec.strategy_id not in reproducibility_samples
                            ):
                                reproducibility_samples[spec.strategy_id] = {
                                    "draw_id": target["draw"],
                                    "replicate_id": replicate,
                                    "cutoff_identity": cutoff,
                                    "raw_tickets": [
                                        list(ticket)
                                        for ticket in portfolio["native_tickets"]
                                    ],
                                    "portfolio_sha256": row["portfolio_sha256"],
                                }
    return observations, runtime_failures, {
        "detail_row_count": len(observations),
        "detail_stream_sha256": portfolio_digest.hexdigest(),
        "reproducibility_samples": reproducibility_samples,
    }


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def cluster_interval(
    rows: Sequence[Mapping[str, Any]],
    *,
    identity: str,
    bootstrap_replicates: int,
    value_field: str = "m4plus",
) -> tuple[float, float, str]:
    by_draw: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_draw[str(row["target_draw"])].append(float(row[value_field]))
    cluster_values = [fmean(values) for _, values in sorted(by_draw.items())]
    if len(cluster_values) <= 1 or max(len(values) for values in by_draw.values()) == 1:
        low, high = wilson_interval(
            sum(int(row[value_field]) for row in rows), len(rows)
        )
        return low, high, "Wilson score"
    generator = random.Random(stable_seed("p20c-bootstrap-v1", identity))
    sample_count = len(cluster_values)
    estimates = []
    for _ in range(bootstrap_replicates):
        estimates.append(
            sum(cluster_values[generator.randrange(sample_count)] for _ in range(sample_count))
            / sample_count
        )
    estimates.sort()
    lower_index = int(0.025 * (bootstrap_replicates - 1))
    upper_index = int(0.975 * (bootstrap_replicates - 1))
    return (
        estimates[lower_index],
        estimates[upper_index],
        "draw-cluster bootstrap percentile",
    )


def paired_baseline_interval(
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    *,
    identity: str,
    bootstrap_replicates: int,
) -> tuple[float, float, float]:
    def draw_means(source: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        values: dict[str, list[float]] = defaultdict(list)
        for row in source:
            values[str(row["target_draw"])].append(float(row["m4plus"]))
        return {draw: fmean(group) for draw, group in values.items()}

    strategy = draw_means(rows)
    baseline = draw_means(baseline_rows)
    common = sorted(set(strategy) & set(baseline))
    if not common:
        return 0.0, 0.0, 0.0
    differences = [strategy[draw] - baseline[draw] for draw in common]
    point = fmean(differences)
    generator = random.Random(stable_seed("p20c-paired-bootstrap-v1", identity))
    estimates = []
    sample_count = len(differences)
    for _ in range(bootstrap_replicates):
        estimates.append(
            sum(differences[generator.randrange(sample_count)] for _ in range(sample_count))
            / sample_count
        )
    estimates.sort()
    return (
        point,
        estimates[int(0.025 * (bootstrap_replicates - 1))],
        estimates[int(0.975 * (bootstrap_replicates - 1))],
    )


def metric_row(
    *,
    spec: StrategySpec,
    rows: Sequence[dict[str, Any]],
    baseline_rows: Sequence[dict[str, Any]],
    bootstrap_replicates: int,
    expected_common: int,
) -> dict[str, Any]:
    completed = [row for row in rows if int(row["final_ticket_count"]) == 20]
    hits = sum(int(row["m4plus"]) for row in completed)
    total = len(completed)
    rate = hits / total if total else 0.0
    low, high, confidence_method = cluster_interval(
        completed,
        identity=spec.strategy_id,
        bootstrap_replicates=bootstrap_replicates,
    )
    difference, difference_low, difference_high = paired_baseline_interval(
        completed,
        baseline_rows,
        identity=spec.strategy_id,
        bootstrap_replicates=bootstrap_replicates,
    )
    native_counts = [int(row["native_valid_count"]) for row in rows]
    constructed_counts = [int(row["constructed_ticket_count"]) for row in rows]
    shares = [float(row["native_ticket_share"]) for row in rows]
    native_hits = sum(int(row["native_m4plus"]) for row in rows)
    tiers = Counter(str(row["construction_tier"]) for row in rows)
    replicate_rates = []
    by_replicate: dict[int, list[int]] = defaultdict(list)
    for row in completed:
        by_replicate[int(row["replicate_id"])].append(int(row["m4plus"]))
    for values in by_replicate.values():
        replicate_rates.append(fmean(values))
    return {
        "base_strategy_id": spec.strategy_id,
        "effective_strategy_id": (
            spec.strategy_id
            if spec.ranking_group == "native"
            else f"{spec.strategy_id}@{SHORT_IDENTIFIER}"
        ),
        "strategy_name": spec.strategy_name,
        "governance_status": spec.governance_status,
        "ranking_group": spec.ranking_group,
        "constructor_name": CONSTRUCTOR_NAME,
        "constructor_version": CONSTRUCTOR_VERSION,
        "expected_common_portfolios": expected_common,
        "completed_common_portfolios": total,
        "completion_ratio": total / expected_common if expected_common else 0.0,
        "unique_target_draws": len({row["target_draw"] for row in completed}),
        "replicates": spec.replicates,
        "m4plus_draw_hits": hits,
        "m4plus_draw_rate": rate,
        "m4plus_ci95_low": low,
        "m4plus_ci95_high": high,
        "confidence_method": confidence_method,
        "baseline_difference": difference,
        "baseline_difference_ci95_low": difference_low,
        "baseline_difference_ci95_high": difference_high,
        "replicate_rate_mean": fmean(replicate_rates) if replicate_rates else 0.0,
        "replicate_rate_sd": pstdev(replicate_rates) if len(replicate_rates) > 1 else 0.0,
        "native_ticket_count_mean": fmean(native_counts) if native_counts else 0.0,
        "constructed_ticket_count_mean": fmean(constructed_counts)
        if constructed_counts
        else 0.0,
        "native_ticket_share_mean": fmean(shares) if shares else 0.0,
        "native_m4plus_draw_hits": native_hits,
        "native_m4plus_draw_rate": native_hits / len(rows) if rows else 0.0,
        "construction_tier_counts": json.dumps(dict(sorted(tiers.items())), sort_keys=True),
        "total_ticket_evaluations": total * 20,
    }


def build_metrics(
    *,
    observations: Sequence[dict[str, Any]],
    specs: Sequence[StrategySpec],
    bootstrap_replicates: int,
    draw_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    common = [
        row
        for row in observations
        if int(row["target_index"]) >= COMMON_MIN_HISTORY
    ]
    baseline_rows = [
        row
        for row in common
        if row["base_strategy_id"] == "baseline::uniform_random_20"
        and int(row["final_ticket_count"]) == 20
    ]
    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in common:
        by_base[str(row["base_strategy_id"])].append(row)

    constructor_metrics = []
    native_ranking = []
    adapter_ranking = []
    for spec in specs:
        if spec.ranking_group == "baseline":
            continue
        rows = by_base.get(spec.strategy_id, [])
        if spec.ranking_group == "native":
            ranking_rows = [
                row
                for row in rows
                if row["effective_strategy_id"] == spec.strategy_id
                and int(row["final_ticket_count"]) == 20
            ]
        else:
            ranking_rows = [
                row for row in rows if int(row["final_ticket_count"]) == 20
            ]
        expected_common = max(0, draw_count - max(COMMON_MIN_HISTORY, spec.min_history)) * spec.replicates
        metric = metric_row(
            spec=spec,
            rows=ranking_rows,
            baseline_rows=baseline_rows,
            bootstrap_replicates=bootstrap_replicates,
            expected_common=expected_common,
        )
        all_expected = max(0, draw_count - spec.min_history) * spec.replicates
        all_rows = [row for row in observations if row["base_strategy_id"] == spec.strategy_id]
        completed_all = sum(int(row["final_ticket_count"]) == 20 for row in all_rows)
        metric["expected_available_portfolios"] = all_expected
        metric["completed_available_portfolios"] = completed_all
        metric["available_completion_ratio"] = completed_all / all_expected if all_expected else 0.0
        metric["formerly_partial"] = spec.formerly_partial
        constructor_metrics.append(metric)
        if spec.ranking_group == "native" and metric["completion_ratio"] >= COMPLETENESS_THRESHOLD:
            native_ranking.append(dict(metric))
        if spec.ranking_group == "adapter" and metric["completion_ratio"] >= COMPLETENESS_THRESHOLD:
            adapter_ranking.append(dict(metric))

    def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            rows,
            key=lambda row: (
                -float(row["m4plus_draw_rate"]),
                -int(row["m4plus_draw_hits"]),
                str(row["effective_strategy_id"]),
            ),
        )
        for index, row in enumerate(ordered, 1):
            row["rank"] = index
        return ordered

    baseline_hits = sum(int(row["m4plus"]) for row in baseline_rows)
    baseline_low, baseline_high, baseline_method = cluster_interval(
        baseline_rows,
        identity="baseline::uniform_random_20",
        bootstrap_replicates=bootstrap_replicates,
    )
    baseline = {
        "strategy_id": "baseline::uniform_random_20",
        "evaluated_portfolios": len(baseline_rows),
        "unique_target_draws": len({row["target_draw"] for row in baseline_rows}),
        "replicates": len({row["replicate_id"] for row in baseline_rows}),
        "m4plus_draw_hits": baseline_hits,
        "m4plus_draw_rate": baseline_hits / len(baseline_rows) if baseline_rows else 0.0,
        "m4plus_ci95_low": baseline_low,
        "m4plus_ci95_high": baseline_high,
        "confidence_method": baseline_method,
        "total_ticket_evaluations": len(baseline_rows) * 20,
    }
    return constructor_metrics, rank(native_ranking), rank(adapter_ranking), baseline


def independent_detail_validation(
    detail_path: Path,
    observations: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    legality_failures = 0
    uniqueness_failures = 0
    portfolio_hash_mismatches = 0
    hit_mismatches = 0
    cutoff_failures = 0
    native_preservation_failures = 0
    constructor_metadata_mismatches = 0
    aggregate: Counter[str] = Counter()
    row_count = 0
    with gzip.open(detail_path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row_count += 1
            tickets = [tuple(ticket) for ticket in json.loads(row["tickets_json"])]
            native_tickets = [
                tuple(ticket) for ticket in json.loads(row["native_tickets_json"])
            ]
            actual = json.loads(row["actual_numbers_json"])
            if tickets:
                if any(
                    len(ticket) != 6
                    or len(set(ticket)) != 6
                    or any(type(number) is not int or not 1 <= number <= 49 for number in ticket)
                    for ticket in tickets
                ):
                    legality_failures += 1
                if len(set(tickets)) != len(tickets):
                    uniqueness_failures += 1
                if portfolio_sha256(tickets) != row["portfolio_sha256"]:
                    portfolio_hash_mismatches += 1
                _, maximum, m4plus = evaluate_hits(tickets, actual)
                if maximum != int(row["max_main_hits"]) or m4plus != int(row["m4plus"]):
                    hit_mismatches += 1
                aggregate[row["base_strategy_id"]] += m4plus
                if row["ranking_group"] != "baseline":
                    native_set = set(native_tickets)
                    ticket_set = set(tickets)
                    if len(native_tickets) <= 20:
                        preserved = native_set.issubset(ticket_set)
                    else:
                        preserved = ticket_set.issubset(native_set)
                    if not preserved:
                        native_preservation_failures += 1
                    expected_retained = min(len(native_tickets), 20)
                    expected_constructed = len(tickets) - expected_retained
                    expected_share = expected_retained / 20
                    if (
                        int(row["native_retained_count"]) != expected_retained
                        or int(row["constructed_ticket_count"])
                        != expected_constructed
                        or abs(float(row["native_ticket_share"]) - expected_share)
                        > 1e-12
                    ):
                        constructor_metadata_mismatches += 1
            cutoff = row["history_cutoff_identity"]
            target = row["target_draw"]
            if cutoff != "GENESIS" and cutoff.isdecimal() and target.isdecimal():
                if int(cutoff) >= int(target):
                    cutoff_failures += 1

    expected_aggregate: Counter[str] = Counter()
    for row in observations:
        if int(row["final_ticket_count"]) > 0:
            expected_aggregate[str(row["base_strategy_id"])] += int(row["m4plus"])
    return {
        "detail_rows_recounted": row_count,
        "row_count_matches": row_count == len(observations),
        "ticket_legality_failures": legality_failures,
        "portfolio_uniqueness_failures": uniqueness_failures,
        "portfolio_hash_mismatches": portfolio_hash_mismatches,
        "hit_recomputation_mismatches": hit_mismatches,
        "history_cutoff_failures": cutoff_failures,
        "native_preservation_failures": native_preservation_failures,
        "constructor_metadata_mismatches": constructor_metadata_mismatches,
        "aggregate_recomputation_mismatches": sum(
            aggregate[key] != expected_aggregate[key]
            for key in set(aggregate) | set(expected_aggregate)
        ),
    }


def check_constructor_reproducibility(samples: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    mismatches = []
    for strategy_id, sample in sorted(samples.items()):
        result = construct_strategy_preserving_20_ticket(
            ConstructorRequest(
                strategy_id=strategy_id,
                draw_id=str(sample["draw_id"]),
                replicate_id=int(sample["replicate_id"]),
                raw_tickets=sample["raw_tickets"],
                historical_cutoff_identity=str(sample["cutoff_identity"]),
                user_seed=USER_SEED_NAMESPACE,
            )
        )
        if not isinstance(result, ConstructorSuccess) or (
            result.metadata.portfolio_sha256 != sample["portfolio_sha256"]
        ):
            mismatches.append(strategy_id)
    return {
        "sample_count": len(samples),
        "mismatch_count": len(mismatches),
        "mismatched_strategy_ids": mismatches,
    }


def build_inventory_and_failure_ledger(
    specs: Sequence[StrategySpec],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    p541b = json.loads(P541B_ARTIFACT.read_text(encoding="utf-8"))
    executable = {spec.strategy_id for spec in specs}
    ledger: list[dict[str, Any]] = []
    confirmed_historical = 0
    historical_records = p541b["method_classification_records"]
    for record in historical_records:
        historical = record.get("historical_p541b_classification", {})
        actual = historical.get("is_actual_prediction_method", "unknown")
        if actual is True:
            confirmed_historical += 1
        strategy_id = f"history::{record['method_id']}"
        if strategy_id in executable:
            continue
        risk = record.get("safety_classification", {}).get("risk_level", "unknown")
        if strategy_id == "history::tools/big_lotto_exhaustive_audit.py":
            reason = "DATA_LEAKAGE_RISK"
            detail = "Outcome-aware evaluator consumes the target result and is excluded."
        elif actual is False:
            reason = "DOCUMENT_ONLY"
            detail = "Committed classification says this is not an actual prediction method."
        elif actual == "unknown":
            reason = "PARTIAL_IMPLEMENTATION"
            detail = "Committed classification cannot confirm a strategy identity."
        elif risk == "low":
            reason = "MISSING_ENTRYPOINT"
            detail = "No approved causal entrypoint is committed for this historical surface."
        elif risk == "high":
            reason = "UNSAFE_EXTERNAL_STATE"
            detail = "Static classification found unsafe or external-state behavior."
        else:
            reason = "UNKNOWN_FAILURE"
            detail = "Identity or transitive safety remains unknown; fail-closed."
        ledger.append(
            {
                "strategy_id": strategy_id,
                "governance_status": {
                    "include_in_replay_readiness": "candidate",
                    "exclude_from_replay": "rejected",
                    "mark_duplicate": "deprecated",
                    "mark_deprecated": "deprecated",
                }.get(historical.get("recommended_action"), "unknown"),
                "failure_stage": "preflight",
                "reason_code": reason,
                "target_draw": "",
                "replicate_id": "",
                "detailed_reason": detail,
            }
        )

    from lottery_api.models.replay_strategy_registry import (
        list_strategy_lifecycle_metadata,
    )

    registry_rows = list_strategy_lifecycle_metadata()
    for row in registry_rows:
        strategy_id = f"registry::{row['strategy_id']}"
        if strategy_id in executable:
            continue
        ledger.append(
            {
                "strategy_id": strategy_id,
                "governance_status": {
                    "ONLINE": "accepted",
                    "REJECTED": "rejected",
                    "RETIRED": "deprecated",
                    "OBSERVATION": "experimental",
                    "OFFLINE": "offline",
                }.get(row["lifecycle_status"], "unknown"),
                "failure_stage": "preflight",
                "reason_code": "MISSING_APPROVED_MULTI_TICKET_ENTRYPOINT",
                "target_draw": "",
                "replicate_id": "",
                "detailed_reason": (
                    "Registry metadata is preserved; this task does not invent an "
                    "unapproved generator entrypoint."
                ),
            }
        )
    return (
        {
            "p541b_records": len(historical_records),
            "prior_confirmed_strategy_identities": 247,
            "confirmed_historical_method_surfaces": confirmed_historical,
            "current_governed_strategy_identities": len(registry_rows),
            "current_confirmed_strategy_identities": (
                confirmed_historical + len(registry_rows) + 1
            ),
            "current_registry_entries": len(registry_rows),
            "inventory_identity_rows": (
                len(historical_records) + len(registry_rows) + 1
            ),
            "runnable_strategy_identities": len(specs) - 1,
            "random_baseline_identities": 1,
            "formerly_partial_identities": sum(spec.formerly_partial for spec in specs),
        },
        ledger,
    )


def prior_reference_hashes() -> list[dict[str, Any]]:
    rows = []
    for filename in PRIOR_REFERENCE_FILES:
        path = PRIOR_REFERENCE_ROOT / filename
        rows.append(
            {
                "path": str(path),
                "sha256": sha256_file(path) if path.is_file() else None,
                "status": "READ_ONLY_REFERENCE" if path.is_file() else "MISSING",
            }
        )
    return rows


def normalized_git_status_sha256(repository: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-uall"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = sorted(result.stdout.splitlines())
    normalized = "\n".join(lines) + ("\n" if lines else "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_focused_tests() -> dict[str, Any]:
    paths = [
        "tests/test_strategy_preserving_20_ticket.py",
        "tests/test_p20c_strategy_preserving_backtest.py",
        "tests/test_replay_strategy_lifecycle_registry.py",
        "tests/test_replay_strategy_lifecycle_exposure.py",
        "tests/test_replay_strategy_registry_online_candidates.py",
    ]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        *paths,
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    output = (process.stdout + process.stderr).strip()
    counts = {}
    for label in ("passed", "failed", "skipped", "xfailed", "xpassed"):
        match = re.search(rf"(\d+) {label}", output)
        counts[label] = int(match.group(1)) if match else 0
    return {
        "command": "python -m pytest -q -p no:cacheprovider " + " ".join(paths),
        "returncode": process.returncode,
        "status": "PASS" if process.returncode == 0 else "FAIL",
        "counts": counts,
        "output": (
            f"{counts['passed']} passed; {counts['failed']} failed; "
            f"{counts['skipped']} skipped"
            if process.returncode == 0
            else output[-16000:]
        ),
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def markdown_table(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[tuple[str, str]],
) -> str:
    if not rows:
        return "_No rows._"
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        cells = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                value = f"{value:.6f}"
            cells.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def generate_report(
    *,
    status: str,
    manifest: Mapping[str, Any],
    constructor_metrics: Sequence[Mapping[str, Any]],
    native_ranking: Sequence[Mapping[str, Any]],
    adapter_ranking: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    failures: Sequence[Mapping[str, Any]],
    validation: Mapping[str, Any],
) -> str:
    formerly_partial = [row for row in constructor_metrics if row["formerly_partial"]]
    failure_counts = Counter(row["reason_code"] for row in failures)
    theoretical_single = sum(
        math.comb(6, hits) * math.comb(43, 6 - hits) / math.comb(49, 6)
        for hits in range(4, 7)
    )
    theoretical_twenty = 1 - (1 - theoretical_single) ** 20
    return f"""# P20C v1 Strategy-Preserving 20-Ticket Constructor

Status: **{status}**. The explicit adapter mode completed {manifest['historical_run']['constructor_completed']} of {manifest['historical_run']['constructor_attempted']} formerly partial strategy identities at the 99% draw/replicate threshold. Native strategy governance states were not changed, and adapter-assisted identities remain qualified with `@{SHORT_IDENTIFIER}`.

This is a historical empirical backtest for research and entertainment, not a future winning probability, betting recommendation, or strategy-promotion decision.

## Constructor contract

- Identifier: `{CONSTRUCTOR_NAME}/{CONSTRUCTOR_VERSION}`
- Native tickets are canonicalized, deduplicated, and retained.
- Tier B uses strategy-owned number scores/rankings; Tier C derives frequency signal only from native ticket membership, never ticket position.
- Synthesized tickets meet the fixed signal-pool minimums (3 of 6 for pools 6–8, 4 for 9–14, 5 for 15+) and disclose neutral 1–49 fills.
- Selection combines signal score, maximum-overlap penalty, number-concentration penalty, and SHA-256 tie-breaking.
- Constants fixed before the historical run: `{json.dumps(objective_constants(), sort_keys=True)}`.

## Repository and data identity

| Field | Value |
| --- | --- |
| Base commit | `{manifest['repo']['base_commit']}` |
| Branch | `{manifest['repo']['branch']}` |
| Canonical DB SHA-256 | `{manifest['data']['database_sha256_before']}` |
| Canonical dataset SHA-256 | `{manifest['data']['canonical_dataset_sha256']}` |
| Draws | {manifest['data']['historical_draws']} ({manifest['data']['first_date']} through {manifest['data']['last_date']}) |
| Common window | {manifest['parameters']['common_window_draws']} draws after {COMMON_MIN_HISTORY} prior draws |
| Random replicates | {manifest['parameters']['random_replicates']} |

The raw-data quality pass found {manifest['data']['excluded_noncanonical_rows']} noncanonical BIG_LOTTO rows outside the selected view, {manifest['data']['duplicate_draw_ids']} duplicate canonical draw IDs, {manifest['data']['invalid_json_rows']} invalid JSON rows, {manifest['data']['out_of_range_rows']} range errors, and {manifest['data']['negative_financial_rows']} negative financial rows. All 2,125 positional-order fields are null, so the constructor never treats sorted ticket position as signal.

## Formerly partial strategy completion

{markdown_table(formerly_partial, (("base_strategy_id", "Base strategy"), ("governance_status", "Governance"), ("native_ticket_count_mean", "Native mean"), ("constructed_ticket_count_mean", "Constructed mean"), ("native_ticket_share_mean", "Native share"), ("available_completion_ratio", "Completion"), ("m4plus_draw_rate", "Adapter M4+")))}

Every valid native ticket remains in its final portfolio. Exact behavior for representative native counts is pinned by unit/parity tests: 1→19 constructed, 2→18, 4→16, and 8→12, all with 20 unique legal final tickets.

## Native-complete 20-ticket ranking

{markdown_table(native_ranking, (("rank", "Rank"), ("effective_strategy_id", "Strategy"), ("m4plus_draw_hits", "M4+ hits"), ("completed_common_portfolios", "Portfolios"), ("m4plus_draw_rate", "Rate"), ("m4plus_ci95_low", "CI low"), ("m4plus_ci95_high", "CI high"), ("baseline_difference", "vs baseline")))}

Occasional duplicate native portfolios are not silently counted as native-complete; constructor-assisted repairs carry the adapter-qualified identity and are excluded from the native ranking row.

## Adapter-assisted 20-ticket ranking

{markdown_table(adapter_ranking, (("rank", "Rank"), ("effective_strategy_id", "Effective strategy"), ("governance_status", "Governance"), ("m4plus_draw_hits", "M4+ hits"), ("completed_common_portfolios", "Portfolios"), ("m4plus_draw_rate", "Rate"), ("m4plus_ci95_low", "CI low"), ("m4plus_ci95_high", "CI high"), ("baseline_difference", "vs baseline")))}

These rows measure the versioned adapter portfolios, not the native strategies. A rejected or deprecated base strategy remains rejected or deprecated regardless of rank.

## Native partial results

{markdown_table(formerly_partial, (("base_strategy_id", "Base strategy"), ("native_ticket_count_mean", "Native tickets"), ("native_m4plus_draw_hits", "Native M4+ hits"), ("native_m4plus_draw_rate", "Native M4+ rate")))}

Native partial rates use unequal 1–8-ticket budgets and are descriptive only; they are not mixed with either 20-ticket ranking.

## Random baseline

The paired uniform-random 20-ticket baseline produced {baseline['m4plus_draw_hits']} M4+ replicate-draws in {baseline['evaluated_portfolios']} portfolios: {baseline['m4plus_draw_rate']:.6%} (95% draw-cluster CI {baseline['m4plus_ci95_low']:.6%}–{baseline['m4plus_ci95_high']:.6%}). The independent-ticket approximation is {theoretical_twenty:.6%}; the empirical baseline enforces unique tickets.

Point estimates and historical confidence intervals do not establish future advantage. Multiple comparisons, historical reuse, and correlated strategy families remain material limitations.

## Leakage, determinism, and recomputation

- The constructor API has no target-result or database parameter.
- Every integration slice ends strictly before its target draw; mutation and cutoff tests are included in the focused suite.
- Detail read-back independently checked legality, uniqueness, portfolio SHA-256, hit counts, cutoffs, and aggregate totals: `{json.dumps(validation['checks']['independent_detail_recomputation']['details'], sort_keys=True)}`.
- Constructor reproducibility sample mismatches: {validation['checks']['constructor_reproducibility']['details']['mismatch_count']}.
- The known outcome-aware `tools/big_lotto_exhaustive_audit.py` surface remains excluded with `DATA_LEAKAGE_RISK`.

## Remaining failures and skipped strategies

{markdown_table([{"reason_code": key, "count": value} for key, value in sorted(failure_counts.items())], (("reason_code", "Reason"), ("count", "Count")))}

Skipped identities retain their committed lifecycle/classification. No missing entrypoint was fabricated, no dependency was installed, and no constructor constant was adjusted after viewing M4+ results.

## Reproducibility

The committed runner, constructor, focused tests, manifest, compact CSVs, validation JSON, and this report reproduce the result. The temporary draw/replicate detail contained {manifest['detail']['row_count']} rows, SHA-256 `{manifest['detail']['file_sha256']}`, and independent stream digest `{manifest['detail']['stream_sha256']}`; it was removed after verification.

Focused test command: `{manifest['tests']['command']}`

Focused result: {manifest['tests']['counts']} (status `{manifest['tests']['status']}`). Exact-head GitHub CI is reported in the PR lifecycle state, not inferred here.
"""


def stage_compact_evidence(
    *,
    staging: Path,
    output_dir: Path,
    manifest: dict[str, Any],
    constructor_metrics: Sequence[dict[str, Any]],
    native_ranking: Sequence[dict[str, Any]],
    adapter_ranking: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
    validation: dict[str, Any],
    status: str,
) -> None:
    write_csv(staging / "constructor_metrics.csv", constructor_metrics)
    write_csv(staging / "m4plus_native_ranking.csv", native_ranking)
    write_csv(staging / "m4plus_adapter_ranking.csv", adapter_ranking)
    write_csv(staging / "failed_strategies.csv", failures)
    write_json(staging / "validation_results.json", validation)
    report = generate_report(
        status=status,
        manifest=manifest,
        constructor_metrics=constructor_metrics,
        native_ranking=native_ranking,
        adapter_ranking=adapter_ranking,
        baseline=manifest["random_baseline"],
        failures=failures,
        validation=validation,
    )
    (staging / "final_report.md").write_text(report, encoding="utf-8")
    manifest["outputs"] = {
        filename: sha256_file(staging / filename)
        for filename in EVIDENCE_FILENAMES
        if filename != "manifest.json"
    }
    write_json(staging / "manifest.json", manifest)

    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence directory: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    for filename in EVIDENCE_FILENAMES:
        source = staging / filename
        destination = output_dir / filename
        destination.write_bytes(source.read_bytes())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P20C deterministic strategy-preserving 20-ticket backtest"
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--ticket-constructor",
        choices=(TICKET_CONSTRUCTOR_NATIVE_ONLY, TICKET_CONSTRUCTOR_V1),
        default=TICKET_CONSTRUCTOR_NATIVE_ONLY,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--random-replicates", type=int, default=DEFAULT_RANDOM_REPLICATES)
    parser.add_argument(
        "--bootstrap-replicates", type=int, default=DEFAULT_BOOTSTRAP_REPLICATES
    )
    parser.add_argument("--canonical-repo", type=Path, default=None)
    parser.add_argument("--expected-canonical-status-sha256", default=None)
    parser.add_argument("--run-focused-tests", action="store_true")
    args = parser.parse_args(argv)

    if args.ticket_constructor != TICKET_CONSTRUCTOR_V1:
        parser.error("historical evidence publication requires strategy-preserving-v1")
    if args.random_replicates != DEFAULT_RANDOM_REPLICATES:
        parser.error("P20C evidence requires exactly 10 random/stochastic replicates")
    if args.bootstrap_replicates <= 0:
        parser.error("bootstrap replicates must be positive")
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        parser.error(f"output directory already exists: {output_dir}")

    canonical_status_before = None
    if args.canonical_repo:
        canonical_status_before = normalized_git_status_sha256(args.canonical_repo)
        if (
            args.expected_canonical_status_sha256
            and canonical_status_before != args.expected_canonical_status_sha256
        ):
            parser.error(
                "canonical Git status changed before run: "
                f"{canonical_status_before} != {args.expected_canonical_status_sha256}"
            )

    database = args.database.resolve()
    database_sha_before = sha256_file(database)
    draws, quality = load_draws_and_quality(database)
    if len(draws) != 2125 or quality["common_window_rows"] != 2025:
        parser.error(
            "live canonical dataset identity is outside the authorized P20C boundary: "
            f"draws={len(draws)} common={quality['common_window_rows']}"
        )
    specs = build_strategy_specs(args.random_replicates)
    inventory_summary, preflight_failures = build_inventory_and_failure_ledger(specs)
    tests = run_focused_tests() if args.run_focused_tests else {
        "command": "NOT_RUN",
        "returncode": None,
        "status": "NOT_RUN",
        "counts": {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "xpassed": 0},
        "output": "",
    }
    if args.run_focused_tests and tests["status"] != "PASS":
        print(tests["output"], file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="p20c-v1-") as temporary:
        temporary_path = Path(temporary)
        detail_path = temporary_path / "draw_replicate_detail.csv.gz"
        staging = temporary_path / "compact"
        staging.mkdir()

        observations, runtime_failures, execution = execute_backtest(
            draws=draws,
            specs=specs,
            constructor_mode=args.ticket_constructor,
            detail_path=detail_path,
        )
        detail_file_sha = sha256_file(detail_path)
        detail_validation = independent_detail_validation(detail_path, observations)
        reproducibility = check_constructor_reproducibility(
            execution["reproducibility_samples"]
        )
        constructor_metrics, native_ranking, adapter_ranking, baseline = build_metrics(
            observations=observations,
            specs=specs,
            bootstrap_replicates=args.bootstrap_replicates,
            draw_count=len(draws),
        )
        failures = sorted(
            [*preflight_failures, *runtime_failures],
            key=lambda row: (
                str(row["strategy_id"]),
                str(row["target_draw"]),
                str(row["replicate_id"]),
            ),
        )
        formerly_partial = [
            row for row in constructor_metrics if row["formerly_partial"]
        ]
        constructor_attempted = len(formerly_partial)
        constructor_completed = sum(
            float(row["available_completion_ratio"]) >= COMPLETENESS_THRESHOLD
            for row in formerly_partial
        )

        database_sha_after = sha256_file(database)
        canonical_status_after = (
            normalized_git_status_sha256(args.canonical_repo)
            if args.canonical_repo
            else None
        )
        validation_checks = {
            "focused_tests": {
                "pass": tests["status"] == "PASS",
                "details": tests,
            },
            "canonical_data_quality": {
                "pass": all(
                    quality[key] == 0
                    for key in (
                        "duplicate_draw_ids",
                        "duplicate_dates",
                        "invalid_json_rows",
                        "wrong_main_number_count_rows",
                        "out_of_range_rows",
                        "duplicate_main_number_rows",
                        "invalid_or_overlapping_special_rows",
                        "negative_financial_rows",
                        "outside_selected_window_rows",
                        "replay_noncausal_cutoff_rows",
                    )
                ),
                "details": quality,
            },
            "independent_detail_recomputation": {
                "pass": detail_validation["row_count_matches"]
                and all(
                    detail_validation[key] == 0
                    for key in (
                        "ticket_legality_failures",
                        "portfolio_uniqueness_failures",
                        "portfolio_hash_mismatches",
                        "hit_recomputation_mismatches",
                        "history_cutoff_failures",
                        "native_preservation_failures",
                        "constructor_metadata_mismatches",
                        "aggregate_recomputation_mismatches",
                    )
                ),
                "details": detail_validation,
            },
            "constructor_reproducibility": {
                "pass": reproducibility["mismatch_count"] == 0,
                "details": reproducibility,
            },
            "formerly_partial_completion": {
                "pass": constructor_attempted == 12 and constructor_completed == 12,
                "details": {
                    "attempted": constructor_attempted,
                    "completed_at_99pct": constructor_completed,
                },
            },
            "identity_and_ranking_separation": {
                "pass": all("@sp20_v1" in row["effective_strategy_id"] for row in adapter_ranking)
                and all("@sp20_v1" not in row["effective_strategy_id"] for row in native_ranking),
                "details": {
                    "native_rows": len(native_ranking),
                    "adapter_rows": len(adapter_ranking),
                },
            },
            "database_unchanged": {
                "pass": database_sha_before == database_sha_after,
                "details": {
                    "sha256_before": database_sha_before,
                    "sha256_after": database_sha_after,
                },
            },
            "canonical_git_status_unchanged": {
                "pass": canonical_status_before == canonical_status_after
                and (
                    args.expected_canonical_status_sha256 is None
                    or canonical_status_after == args.expected_canonical_status_sha256
                ),
                "details": {
                    "sha256_before": canonical_status_before,
                    "sha256_after": canonical_status_after,
                    "expected": args.expected_canonical_status_sha256,
                },
            },
            "known_leakage_invalid_excluded": {
                "pass": any(
                    row["strategy_id"] == "history::tools/big_lotto_exhaustive_audit.py"
                    and row["reason_code"] == "DATA_LEAKAGE_RISK"
                    for row in failures
                ),
                "details": {"identity": "history::tools/big_lotto_exhaustive_audit.py"},
            },
        }
        validation_pass = all(check["pass"] for check in validation_checks.values())
        validation = {
            "status": "PASS" if validation_pass else "FAIL",
            "checks": validation_checks,
        }
        status = (
            "COMPLETED"
            if validation_pass and constructor_completed == 12 and not runtime_failures
            else "PARTIALLY_COMPLETED"
        )

        git_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        manifest = {
            "task_id": TASK_ID,
            "status": status,
            "constructor": {
                "name": CONSTRUCTOR_NAME,
                "version": CONSTRUCTOR_VERSION,
                "mode": args.ticket_constructor,
                "objective_constants": objective_constants(),
                "algorithm_constants_locked_before_historical_results": True,
            },
            "repo": {
                "path": str(REPO_ROOT),
                "branch": git_branch,
                "base_commit": git_head,
                "canonical_repo": str(args.canonical_repo) if args.canonical_repo else None,
                "canonical_status_sha256_before": canonical_status_before,
                "canonical_status_sha256_after": canonical_status_after,
            },
            "data": {
                **quality,
                "historical_draws": len(draws),
                "database_path": str(database),
                "database_sha256_before": database_sha_before,
                "database_sha256_after": database_sha_after,
            },
            "parameters": {
                "tickets_per_draw": 20,
                "common_min_history": COMMON_MIN_HISTORY,
                "common_window_draws": len(draws) - COMMON_MIN_HISTORY,
                "random_replicates": args.random_replicates,
                "bootstrap_replicates": args.bootstrap_replicates,
                "completion_threshold": COMPLETENESS_THRESHOLD,
                "m4plus_definition": (
                    "Per draw/replicate, at least one of 20 unique tickets "
                    "matches four or more main numbers; special is separate."
                ),
            },
            "inventory": inventory_summary,
            "historical_run": {
                "prior_partial_identities": 12,
                "constructor_attempted": constructor_attempted,
                "constructor_completed": constructor_completed,
                "still_incomplete": constructor_attempted - constructor_completed,
                "native_eligible_identities": len(native_ranking),
                "adapter_eligible_identities": len(adapter_ranking),
                "total_ticket_evaluations": sum(
                    int(row["final_ticket_count"]) for row in observations
                ),
                "runtime_failure_rows": len(runtime_failures),
            },
            "random_baseline": baseline,
            "detail": {
                "retained": False,
                "cleanup": "task-owned TemporaryDirectory removed after compact evidence publication",
                "row_count": execution["detail_row_count"],
                "file_sha256": detail_file_sha,
                "stream_sha256": execution["detail_stream_sha256"],
            },
            "tests": tests,
            "prior_uncommitted_reference_sources": prior_reference_hashes(),
            "limitations": [
                "Historical rates are not future winning probabilities.",
                "Multiple comparisons and historical reuse remain substantial.",
                "Native partial rates use unequal ticket budgets and are not ranked with 20-ticket portfolios.",
                "Null positional fields prevent positional-order strategy validation.",
            ],
        }
        stage_compact_evidence(
            staging=staging,
            output_dir=output_dir,
            manifest=manifest,
            constructor_metrics=constructor_metrics,
            native_ranking=native_ranking,
            adapter_ranking=adapter_ranking,
            failures=failures,
            validation=validation,
            status=status,
        )

    print(
        json.dumps(
            {
                "status": status,
                "output_dir": str(output_dir),
                "constructor_attempted": constructor_attempted,
                "constructor_completed": constructor_completed,
                "validation": validation["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
