#!/usr/bin/env python3
"""P20U nested 10/15/20-ticket Big Lotto M4+ historical analysis.

The runner reuses the merged P20C/P20S/P20T strategy generators.  It creates
one ordered 20-ticket portfolio per strategy/draw/replicate and evaluates only
the 10-, 15-, and 20-ticket prefixes.  Large draw detail remains in caller-
owned resumable checkpoints; only compact, independently validated evidence is
published in the repository.
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
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from statistics import fmean
from typing import Any, Iterator, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from scripts import p20c_strategy_preserving_20_ticket_backtest as p20c  # noqa: E402
from scripts import p20s_all_strategies_bulk_recovery as p20s  # noqa: E402
from scripts import p20t_remaining_16_strategy_recovery as p20t  # noqa: E402


TASK_ID = "P20U_MULTI_TICKET_COUNT_M4PLUS_ANALYSIS"
RUNNER_VERSION = "p20u-v1-nested-multi-ticket-count"
METRIC_CONTRACT_VERSION = "p20u-m4plus-marginal/v1"
PORTFOLIO_HASH_SCHEME = "p20u-nested-ticket-count-aware/v1"
PORTFOLIO_ORDERING_CONTRACT = "nested_prefix_from_single_ordered_20"
SEED_NAMESPACE = "p20c-native-v1"
CONSTRUCTOR_IDENTIFIER = "strategy_preserving_20_ticket/v1"
UPSTREAM_P20T_MERGE_COMMIT = "e74a23092047f5c7113ad972101512593d3381fe"
EXPECTED_DRAWS = 2125
COMMON_MIN_HISTORY = 100
EXPECTED_COMMON_DRAWS = 2025
EXPECTED_COMPLETED = 30
EXPECTED_EXCLUDED = 9
EXPECTED_GOVERNED = 39
TICKET_COUNTS = (10, 15, 20)
MARGINAL_TRANSITIONS = ((10, 15), (15, 20), (10, 20))
RANDOM_REPLICATES = 10
DEFAULT_BOOTSTRAP_REPLICATES = 2000
DEFAULT_TIMEOUT_SECONDS = 1800
CONFIRMATORY_ALPHA = 0.05
CONFIRMATORY_FAMILY_DEFINITION = (
    "unique independent_algorithm_id x ticket_count across the frozen 30-strategy "
    "universe and ticket counts 10,15,20; one-sided exact draw-cluster sign-flip "
    "p-values; credible adjusted advantage requires paired CI lower bound > 0 and "
    "Bonferroni-adjusted p < 0.05; BH-FDR is reported as a secondary adjustment"
)

P20T_DIR = REPO_ROOT / "outputs/research/p20t_remaining_16_strategy_recovery"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "outputs/research/p20u_multi_ticket_count_m4plus_analysis"
)
P20T_MANIFEST = P20T_DIR / "run_manifest.json"

REQUIRED_OUTPUTS = (
    "run_manifest.json",
    "completed_30_strategy_universe.csv",
    "ticket_count_configuration.json",
    "portfolio_nesting_validation.csv",
    "p20t_20_ticket_parity.csv",
    "strategy_ticket_count_metrics.csv",
    "random_ticket_count_metrics.csv",
    "paired_strategy_vs_random.csv",
    "marginal_gain_10_to_15.csv",
    "marginal_gain_15_to_20.csv",
    "marginal_gain_10_to_20.csv",
    "marginal_gain_vs_random.csv",
    "ticket_efficiency_metrics.csv",
    "ranking_10_ticket_m4plus.csv",
    "ranking_15_ticket_m4plus.csv",
    "ranking_20_ticket_m4plus.csv",
    "ranking_same_count_random_uplift.csv",
    "ranking_marginal_gain.csv",
    "multiplicity_adjustment_results.csv",
    "validation_results.json",
    "final_report.md",
)

DETAIL_FIELDS = (
    "strategy_id",
    "execution_strategy_id",
    "effective_strategy_id",
    "strategy_name",
    "governance_status",
    "ranking_group",
    "replicate_id",
    "target_index",
    "target_draw",
    "target_date",
    "history_cutoff_identity",
    "status",
    "failure_reason",
    "native_tickets_json",
    "ordered_tickets_20_json",
    "actual_numbers_json",
    "actual_special",
    "constructor_name",
    "constructor_version",
    "native_seed",
    "native_input_count",
    "native_valid_count",
    "native_duplicate_count",
    "native_invalid_count",
    "native_retained_count",
    "constructed_ticket_count",
    "construction_tier",
    "p20t_portfolio_sha256",
    "portfolio_sha256_10",
    "portfolio_sha256_15",
    "portfolio_sha256_20",
    "max_main_hits_10",
    "max_main_hits_15",
    "max_main_hits_20",
    "m4plus_10",
    "m4plus_15",
    "m4plus_20",
    "incremental_10_to_15",
    "incremental_15_to_20",
    "incremental_10_to_20",
)

METRIC_FIELDS = (
    "strategy_id",
    "effective_strategy_id",
    "governance_status",
    "independent_algorithm_id",
    "equivalence_group",
    "ticket_count",
    "evaluated_draws",
    "common_window_draws",
    "strategy_replicates",
    "complete_portfolios",
    "completion_rate",
    "m4plus_hits",
    "m4plus_rate",
    "m4plus_confidence_interval_95",
    "confidence_method",
    "random_m4plus_hits",
    "random_m4plus_rate",
    "random_confidence_interval_95",
    "paired_difference_vs_random",
    "paired_difference_interval_95",
    "paired_p_value",
    "multiplicity_adjusted_p_value",
    "bh_fdr_adjusted_p_value",
    "credible_advantage_unadjusted",
    "credible_advantage_adjusted",
    "runtime_seconds",
)

RANDOM_FIELDS = (
    "strategy_id",
    "ticket_count",
    "evaluated_draws",
    "random_replicates",
    "complete_portfolios",
    "m4plus_hits",
    "m4plus_rate",
    "m4plus_confidence_interval_95",
    "confidence_method",
    "total_ticket_evaluations",
)

MARGINAL_FIELDS = (
    "strategy_id",
    "effective_strategy_id",
    "independent_algorithm_id",
    "equivalence_group",
    "from_ticket_count",
    "to_ticket_count",
    "evaluated_draws",
    "complete_portfolios",
    "incremental_m4plus_hits",
    "incremental_m4plus_rate",
    "incremental_interval_95",
    "random_incremental_m4plus_hits",
    "random_incremental_m4plus_rate",
    "random_incremental_interval_95",
    "incremental_difference_vs_random",
    "incremental_difference_interval_95",
    "paired_p_value",
)


class ContractError(RuntimeError):
    """Raised when a frozen P20U contract cannot be satisfied."""


class CheckpointRejected(ContractError):
    """Raised when a checkpoint exists but does not match the full key."""


@dataclass(frozen=True)
class ExecutionIdentity:
    strategy_id: str
    spec: p20c.StrategySpec
    governance: Mapping[str, str]
    upstream_metric: Mapping[str, str]

    @property
    def expected_effective_strategy_id(self) -> str:
        return str(self.upstream_metric["effective_strategy_id"])


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, value)
    os.replace(temporary, path)


def write_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def interval_text(low: float, high: float) -> str:
    return f"[{low:.12f},{high:.12f}]"


def parse_interval(value: str) -> tuple[float, float]:
    raw = json.loads(value)
    return float(raw[0]), float(raw[1])


def validate_ticket_counts(values: Sequence[Any]) -> tuple[int, ...]:
    if not values:
        raise ValueError("ticket counts must not be empty")
    counts: list[int] = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("ticket counts must be positive integers")
        try:
            count = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("ticket counts must be positive integers") from exc
        if str(value).strip() != str(count) or count <= 0:
            raise ValueError("ticket counts must be positive integers")
        counts.append(count)
    if len(counts) != len(set(counts)):
        raise ValueError("duplicate ticket counts are not allowed")
    if max(counts) > 20:
        raise ValueError("ticket count exceeds the ordered 20-ticket portfolio")
    if tuple(counts) != TICKET_COUNTS:
        raise ValueError(f"P20U accepts exactly {TICKET_COUNTS}")
    return tuple(counts)


def ordered_prefixes(
    ordered_tickets: Sequence[Sequence[int]],
    ticket_counts: Sequence[Any] = TICKET_COUNTS,
) -> dict[int, tuple[tuple[int, ...], ...]]:
    counts = validate_ticket_counts(ticket_counts)
    prefixes = {
        count: p20t.ordered_portfolio_prefix(ordered_tickets, count) for count in counts
    }
    if prefixes[10] != prefixes[15][:10] or prefixes[15] != prefixes[20][:15]:
        raise ContractError("portfolio prefixes are not nested")
    return prefixes


def ticket_count_portfolio_sha256(
    *,
    strategy_id: str,
    effective_strategy_id: str,
    ticket_count: int,
    target_draw: str,
    replicate_id: int,
    source_head: str,
    constructor_version: str,
    tickets: Sequence[Sequence[int]],
) -> str:
    prefix = p20t.ordered_portfolio_prefix(tickets, ticket_count)
    payload = {
        "hash_scheme": PORTFOLIO_HASH_SCHEME,
        "strategy_id": strategy_id,
        "effective_strategy_id": effective_strategy_id,
        "ticket_count": ticket_count,
        "target_draw": str(target_draw),
        "replicate_id": int(replicate_id),
        "source_head": source_head,
        "constructor_version": constructor_version,
        "seed_namespace": SEED_NAMESPACE,
        "ordered_tickets": [list(ticket) for ticket in prefix],
    }
    return sha256_bytes(canonical_json_bytes(payload))


def score_nested_portfolio(
    ordered_tickets: Sequence[Sequence[int]], actual_numbers: Sequence[int]
) -> dict[str, int]:
    prefixes = ordered_prefixes(ordered_tickets)
    result: dict[str, int] = {}
    for count, tickets in prefixes.items():
        _, maximum, m4plus = p20c.evaluate_hits(tickets, actual_numbers)
        result[f"max_main_hits_{count}"] = maximum
        result[f"m4plus_{count}"] = m4plus
    if not (result["m4plus_10"] <= result["m4plus_15"] <= result["m4plus_20"]):
        raise ContractError("nested M4+ monotonicity failed")
    for start, end in MARGINAL_TRANSITIONS:
        result[f"incremental_{start}_to_{end}"] = (
            result[f"m4plus_{end}"] - result[f"m4plus_{start}"]
        )
    return result


def combined_tree_digest(root: Path) -> str:
    lines = []
    for path in sorted(item for item in root.iterdir() if item.is_file()):
        relative = path.relative_to(REPO_ROOT)
        lines.append(f"{sha256_file(path)}  {relative}\n")
    return sha256_bytes("".join(lines).encode("utf-8"))


def sidecar_inventory(database: Path) -> list[dict[str, Any]]:
    rows = []
    for suffix in ("-shm", "-wal", "-journal"):
        path = Path(str(database) + suffix)
        if path.is_file():
            rows.append(
                {
                    "path": str(path),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return rows


def normalized_unrelated_worktree_sha256(
    repository: Path, reusable_worktree: Path
) -> str:
    raw = git_value(repository, "worktree", "list", "--porcelain")
    blocks = []
    for block in raw.split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        path_line = next((line for line in lines if line.startswith("worktree ")), "")
        path = Path(path_line.removeprefix("worktree ")).resolve()
        if path == reusable_worktree.resolve():
            continue
        blocks.append("\n".join(lines))
    return sha256_bytes(("\n\n".join(blocks) + "\n").encode("utf-8"))


def load_frozen_universe() -> dict[str, Any]:
    ledger = read_csv(P20T_DIR / "final_39_resolution_ledger.csv")
    metrics = read_csv(P20T_DIR / "final_39_completed_strategy_metrics.csv")
    capabilities = read_csv(P20T_DIR / "ticket_count_capability.csv")
    nested = read_csv(P20T_DIR / "nested_portfolio_capability.csv")
    complete_dispositions = {"COMPLETE_NATIVE_20", "COMPLETE_ADAPTER_20"}
    completed = [
        row for row in ledger if row["terminal_disposition"] in complete_dispositions
    ]
    excluded = [
        row
        for row in ledger
        if row["terminal_disposition"] not in complete_dispositions
    ]
    completed_ids = [row["strategy_id"] for row in completed]
    excluded_ids = [row["strategy_id"] for row in excluded]
    metric_by_id = {row["strategy_id"]: row for row in metrics}
    capability_by_id = {row["strategy_id"]: row for row in capabilities}
    nested_by_id = {row["strategy_id"]: row for row in nested}
    checks = {
        "governed_count": len(ledger) == EXPECTED_GOVERNED,
        "unique_governed": len({row["strategy_id"] for row in ledger})
        == EXPECTED_GOVERNED,
        "completed_count": len(completed_ids) == EXPECTED_COMPLETED,
        "unique_completed": len(set(completed_ids)) == EXPECTED_COMPLETED,
        "excluded_count": len(excluded_ids) == EXPECTED_EXCLUDED,
        "metric_set": set(metric_by_id) == set(completed_ids),
        "capability_set": set(capability_by_id)
        == {row["strategy_id"] for row in ledger},
        "nested_set": set(nested_by_id) == {row["strategy_id"] for row in ledger},
        "all_20_run": all(
            capability_by_id[strategy_id]["historical_20_status"] == "RUN"
            for strategy_id in completed_ids
        ),
        "all_nested": all(
            capability_by_id[strategy_id]["nested_prefix_supported"] == "True"
            and nested_by_id[strategy_id]["nested_prefix_supported"] == "True"
            for strategy_id in completed_ids
        ),
        "excluded_absent": not (set(excluded_ids) & set(metric_by_id)),
    }
    if not all(checks.values()):
        raise ContractError(f"frozen strategy-universe mismatch: {checks}")
    return {
        "ledger": ledger,
        "completed": completed,
        "excluded": excluded,
        "completed_ids": completed_ids,
        "excluded_ids": excluded_ids,
        "metric_by_id": metric_by_id,
        "checks": checks,
    }


def build_execution_identities(universe: Mapping[str, Any]) -> list[ExecutionIdentity]:
    p20s_specs = p20s.build_strategy_specs(RANDOM_REPLICATES)
    p20t_specs = p20t.build_strategy_specs(RANDOM_REPLICATES)
    baseline = next(spec for spec in p20s_specs if spec.ranking_group == "baseline")
    real: dict[str, p20c.StrategySpec] = {}
    for spec in p20s_specs:
        if spec.ranking_group != "baseline":
            real[p20s.SPEC_TO_IDENTITY[spec.strategy_id]] = spec
    for spec in p20t_specs:
        if spec.ranking_group != "baseline":
            real[spec.strategy_id] = spec
            p20s.SPEC_TO_IDENTITY[spec.strategy_id] = spec.strategy_id
    expected = set(universe["completed_ids"])
    if set(real) != expected or len(real) != EXPECTED_COMPLETED:
        raise ContractError(
            f"execution universe mismatch: missing={sorted(expected - set(real))}, "
            f"extra={sorted(set(real) - expected)}"
        )
    governance = {row["strategy_id"]: row for row in universe["completed"]}
    metrics = universe["metric_by_id"]
    entries = [
        ExecutionIdentity(
            strategy_id,
            real[strategy_id],
            governance[strategy_id],
            metrics[strategy_id],
        )
        for strategy_id in sorted(real)
    ]
    baseline_governance = {
        "strategy_id": baseline.strategy_id,
        "strategy_name": baseline.strategy_name,
        "governance_status": "BASELINE",
        "independent_algorithm_id": baseline.strategy_id,
        "equivalence_group": "",
    }
    baseline_metric = {"effective_strategy_id": baseline.strategy_id}
    return [
        ExecutionIdentity(
            baseline.strategy_id, baseline, baseline_governance, baseline_metric
        ),
        *entries,
    ]


def universe_output_rows(entries: Sequence[ExecutionIdentity]) -> list[dict[str, Any]]:
    rows = []
    for entry in entries:
        if entry.spec.ranking_group == "baseline":
            continue
        rows.append(
            {
                "strategy_id": entry.strategy_id,
                "execution_strategy_id": entry.spec.strategy_id,
                "effective_strategy_id": entry.expected_effective_strategy_id,
                "strategy_name": entry.governance["strategy_name"],
                "governance_status": entry.governance["governance_status"],
                "independent_algorithm_id": entry.governance[
                    "independent_algorithm_id"
                ],
                "alias_of": entry.governance["alias_of"],
                "equivalence_group": entry.governance["equivalence_group"],
                "terminal_disposition": entry.governance["terminal_disposition"],
                "ranking_group": entry.spec.ranking_group,
                "strategy_replicates": entry.spec.replicates,
                "minimum_history": entry.spec.min_history,
                "nested_prefix_supported": True,
            }
        )
    return rows


def checkpoint_compatibility_key(
    *,
    source_head: str,
    dataset_digest: str,
    database_digest: str,
    runner_source_sha256: str,
    entry: ExecutionIdentity,
    common_window_draws: int,
) -> dict[str, Any]:
    return {
        "source_head": source_head,
        "dataset_digest": dataset_digest,
        "database_digest": database_digest,
        "constructor_version": CONSTRUCTOR_IDENTIFIER,
        "runner_version": RUNNER_VERSION,
        "runner_source_sha256": runner_source_sha256,
        "strategy_identity": entry.strategy_id,
        "execution_strategy_identity": entry.spec.strategy_id,
        "effective_strategy_identity": entry.expected_effective_strategy_id,
        "ticket_counts": list(TICKET_COUNTS),
        "random_replicates": RANDOM_REPLICATES,
        "portfolio_ordering_contract": PORTFOLIO_ORDERING_CONTRACT,
        "portfolio_hash_scheme": PORTFOLIO_HASH_SCHEME,
        "metric_contract_version": METRIC_CONTRACT_VERSION,
        "common_window_draws": common_window_draws,
    }


def checkpoint_compatible(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def checkpoint_stem(strategy_id: str) -> str:
    return sha256_bytes(strategy_id.encode("utf-8"))[:20]


def deterministic_gzip_csv(path: Path, fields: Sequence[str]):
    @contextlib.contextmanager
    def manager():
        with path.open("wb") as raw_handle:
            with gzip.GzipFile(
                filename="", mode="wb", compresslevel=6, fileobj=raw_handle, mtime=0
            ) as compressed:
                with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                    writer = csv.DictWriter(text, fieldnames=fields)
                    writer.writeheader()
                    yield writer

    return manager()


def _construct_portfolio(
    entry: ExecutionIdentity,
    history: list[dict[str, Any]],
    target: dict[str, Any],
    replicate_id: int,
    native_seed: int,
) -> dict[str, Any]:
    raw = entry.spec.generator(history, target, replicate_id, native_seed)
    if entry.spec.ranking_group == "baseline":
        native, duplicates, invalid = p20c.normalise_native_tickets(raw)
        if len(native) != 20 or duplicates or invalid:
            raise ContractError(
                "uniform-random baseline did not produce 20 unique legal tickets"
            )
        return {
            "tickets": tuple(native),
            "native_tickets": (),
            "metadata": None,
            "native_input_count": len(raw),
            "native_valid_count": len(native),
            "native_duplicate_count": duplicates,
            "native_invalid_count": invalid,
            "status": "COMPLETED_RANDOM_BASELINE",
        }
    portfolio = p20c.prepare_portfolio(
        strategy_id=entry.spec.strategy_id,
        draw_id=target["draw"],
        replicate_id=replicate_id,
        cutoff_identity=history[-1]["draw"],
        raw_tickets=raw,
        actual_numbers=target["numbers"],
        constructor_mode=p20c.TICKET_CONSTRUCTOR_V1,
    )
    if not portfolio["ok"]:
        raise ContractError(str(portfolio.get("failure_reason", "portfolio failed")))
    return portfolio


def _detail_row(
    *,
    entry: ExecutionIdentity,
    source_head: str,
    target_index: int,
    target: dict[str, Any],
    cutoff: str,
    replicate_id: int,
    native_seed: int,
    portfolio: Mapping[str, Any],
) -> dict[str, Any]:
    tickets = tuple(tuple(ticket) for ticket in portfolio["tickets"])
    prefixes = ordered_prefixes(tickets)
    if len(tickets) != 20 or len(set(tickets)) != 20:
        raise ContractError("full portfolio is not 20 unique tickets")
    metadata = portfolio.get("metadata")
    if metadata is None:
        effective = entry.spec.strategy_id
        metadata_record: Mapping[str, Any] = {}
        constructor_name = "uniform_random_ordered_20"
        constructor_version = "v1"
    else:
        effective = metadata.effective_strategy_id
        metadata_record = metadata.to_dict()
        constructor_name = metadata.constructor_name
        constructor_version = metadata.constructor_version
    if effective != entry.expected_effective_strategy_id:
        raise ContractError(
            f"effective identity drift for {entry.strategy_id}: "
            f"{effective} != {entry.expected_effective_strategy_id}"
        )
    scores = score_nested_portfolio(tickets, target["numbers"])
    hashes = {
        count: ticket_count_portfolio_sha256(
            strategy_id=entry.strategy_id,
            effective_strategy_id=effective,
            ticket_count=count,
            target_draw=target["draw"],
            replicate_id=replicate_id,
            source_head=source_head,
            constructor_version=f"{constructor_name}/{constructor_version}",
            tickets=prefixes[count],
        )
        for count in TICKET_COUNTS
    }
    p20t_hash = (
        metadata_record.get("portfolio_sha256")
        if metadata is not None
        else p20c.portfolio_sha256(tickets)
    )
    if p20t_hash != p20c.portfolio_sha256(tickets):
        raise ContractError("P20T 20-ticket portfolio hash drift")
    return {
        "strategy_id": entry.strategy_id,
        "execution_strategy_id": entry.spec.strategy_id,
        "effective_strategy_id": effective,
        "strategy_name": entry.governance["strategy_name"],
        "governance_status": entry.governance["governance_status"],
        "ranking_group": entry.spec.ranking_group,
        "replicate_id": replicate_id,
        "target_index": target_index,
        "target_draw": target["draw"],
        "target_date": target["date"],
        "history_cutoff_identity": cutoff,
        "status": portfolio["status"],
        "failure_reason": "",
        "native_tickets_json": json.dumps(
            portfolio["native_tickets"], separators=(",", ":")
        ),
        "ordered_tickets_20_json": json.dumps(tickets, separators=(",", ":")),
        "actual_numbers_json": json.dumps(target["numbers"], separators=(",", ":")),
        "actual_special": target["special"],
        "constructor_name": constructor_name,
        "constructor_version": constructor_version,
        "native_seed": native_seed,
        "native_input_count": portfolio["native_input_count"],
        "native_valid_count": portfolio["native_valid_count"],
        "native_duplicate_count": portfolio["native_duplicate_count"],
        "native_invalid_count": portfolio["native_invalid_count"],
        "native_retained_count": metadata_record.get(
            "native_retained_count", len(portfolio["native_tickets"])
        ),
        "constructed_ticket_count": metadata_record.get("constructed_ticket_count", 0),
        "construction_tier": metadata_record.get(
            "construction_tier", "random_baseline"
        ),
        "p20t_portfolio_sha256": p20t_hash,
        "portfolio_sha256_10": hashes[10],
        "portfolio_sha256_15": hashes[15],
        "portfolio_sha256_20": hashes[20],
        **scores,
    }


def execute_identity(
    *,
    entry: ExecutionIdentity,
    draws: list[dict[str, Any]],
    checkpoint_dir: Path,
    source_head: str,
    dataset_digest: str,
    database_digest: str,
    runner_source_sha256: str,
    timeout_seconds: int,
    resume: bool,
) -> dict[str, Any]:
    stem = checkpoint_stem(entry.strategy_id)
    metadata_path = checkpoint_dir / f"{stem}.json"
    detail_path = checkpoint_dir / f"{stem}.csv.gz"
    expected = checkpoint_compatibility_key(
        source_head=source_head,
        dataset_digest=dataset_digest,
        database_digest=database_digest,
        runner_source_sha256=runner_source_sha256,
        entry=entry,
        common_window_draws=len(draws) - COMMON_MIN_HISTORY,
    )
    if metadata_path.exists() or detail_path.exists():
        if not resume:
            raise CheckpointRejected(
                f"fresh execution refuses existing checkpoint for {entry.strategy_id}"
            )
        if not (metadata_path.is_file() and detail_path.is_file()):
            raise CheckpointRejected(
                f"incomplete checkpoint pair for {entry.strategy_id}"
            )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not checkpoint_compatible(metadata, expected):
            raise CheckpointRejected(f"checkpoint key mismatch for {entry.strategy_id}")
        if metadata.get("run_status") != "COMPLETE":
            raise CheckpointRejected(
                f"checkpoint is not complete for {entry.strategy_id}"
            )
        if metadata.get("detail_sha256") != sha256_file(detail_path):
            raise CheckpointRejected(
                f"checkpoint detail hash mismatch for {entry.strategy_id}"
            )
        return {
            "strategy_id": entry.strategy_id,
            "execution_strategy_id": entry.spec.strategy_id,
            "detail_path": str(detail_path),
            "detail_sha256": metadata["detail_sha256"],
            "detail_rows": int(metadata["detail_rows"]),
            "detail_stream_sha256": metadata["detail_stream_sha256"],
            "runtime_seconds": float(metadata["runtime_seconds"]),
            "run_status": "COMPLETE",
            "checkpoint_reused": True,
        }

    temporary_detail = detail_path.with_suffix(detail_path.suffix + ".tmp")
    started = time.monotonic()
    row_count = 0
    stream_digest = hashlib.sha256()
    try:
        with p20s.strategy_timeout(timeout_seconds):
            with deterministic_gzip_csv(temporary_detail, DETAIL_FIELDS) as writer:
                for target_index in range(COMMON_MIN_HISTORY, len(draws)):
                    history = draws[:target_index]
                    target = draws[target_index]
                    cutoff = history[-1]["draw"]
                    for replicate_id in range(entry.spec.replicates):
                        native_seed = p20c.stable_seed(
                            SEED_NAMESPACE,
                            entry.spec.strategy_id,
                            target["draw"],
                            replicate_id,
                        )
                        portfolio = _construct_portfolio(
                            entry, history, target, replicate_id, native_seed
                        )
                        row = _detail_row(
                            entry=entry,
                            source_head=source_head,
                            target_index=target_index,
                            target=target,
                            cutoff=cutoff,
                            replicate_id=replicate_id,
                            native_seed=native_seed,
                            portfolio=portfolio,
                        )
                        writer.writerow(row)
                        stream_digest.update(canonical_json_bytes(row))
                        row_count += 1
        os.replace(temporary_detail, detail_path)
    except Exception:
        if temporary_detail.exists():
            temporary_detail.unlink()
        raise
    elapsed = round(time.monotonic() - started, 6)
    metadata = {
        **expected,
        "run_status": "COMPLETE",
        "runtime_seconds": elapsed,
        "detail_sha256": sha256_file(detail_path),
        "detail_rows": row_count,
        "detail_stream_sha256": stream_digest.hexdigest(),
    }
    write_json_atomic(metadata_path, metadata)
    return {
        "strategy_id": entry.strategy_id,
        "execution_strategy_id": entry.spec.strategy_id,
        "detail_path": str(detail_path),
        "detail_sha256": metadata["detail_sha256"],
        "detail_rows": row_count,
        "detail_stream_sha256": metadata["detail_stream_sha256"],
        "runtime_seconds": elapsed,
        "run_status": "COMPLETE",
        "checkpoint_reused": False,
    }


def execute_all(
    *,
    entries: Sequence[ExecutionIdentity],
    draws: list[dict[str, Any]],
    checkpoint_dir: Path,
    source_head: str,
    dataset_digest: str,
    database_digest: str,
    runner_source_sha256: str,
    timeout_seconds: int,
    resume: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs = []
    failures = []
    for entry in entries:
        try:
            run = execute_identity(
                entry=entry,
                draws=draws,
                checkpoint_dir=checkpoint_dir,
                source_head=source_head,
                dataset_digest=dataset_digest,
                database_digest=database_digest,
                runner_source_sha256=runner_source_sha256,
                timeout_seconds=timeout_seconds,
                resume=resume,
            )
            runs.append(run)
        except Exception as exc:
            failures.append(
                {
                    "strategy_id": entry.strategy_id,
                    "failure_class": type(exc).__name__,
                    "reason": str(exc),
                }
            )
        write_json_atomic(
            checkpoint_dir / "progress.json",
            {
                "task": TASK_ID,
                "completed_strategy_ids": [row["strategy_id"] for row in runs],
                "failures": failures,
                "next_unprocessed_unit": next(
                    (
                        candidate.strategy_id
                        for candidate in entries
                        if candidate.strategy_id
                        not in {row["strategy_id"] for row in runs}
                        and candidate.strategy_id
                        not in {row["strategy_id"] for row in failures}
                    ),
                    None,
                ),
            },
        )
    return runs, failures


def stable_run_records(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in run.items() if key != "checkpoint_reused"}
        for run in runs
    ]


def iter_detail(path: Path) -> Iterator[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def _normalized_full20_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    tickets_key = (
        "ordered_tickets_20_json"
        if "ordered_tickets_20_json" in row
        else "tickets_json"
    )
    hash_key = (
        "p20t_portfolio_sha256"
        if "p20t_portfolio_sha256" in row
        else "portfolio_sha256"
    )
    m4_key = "m4plus_20" if "m4plus_20" in row else "m4plus"
    return {
        "target_draw": str(row["target_draw"]),
        "replicate_id": int(row["replicate_id"]),
        "tickets": json.loads(str(row[tickets_key])),
        "portfolio_sha256": str(row[hash_key]),
        "m4plus": int(row[m4_key]),
    }


def normalized_full20_digest(
    path: Path, *, upstream_p20t: bool = False
) -> tuple[str, int]:
    digest = hashlib.sha256()
    rows = 0
    for row in iter_detail(path):
        if upstream_p20t and int(row["target_index"]) < COMMON_MIN_HISTORY:
            continue
        digest.update(canonical_json_bytes(_normalized_full20_payload(row)))
        rows += 1
    return digest.hexdigest(), rows


def validate_detail_file(
    run: Mapping[str, Any], entry: ExecutionIdentity, source_head: str
) -> dict[str, Any]:
    failures = Counter()
    count = 0
    count_hashes = {ticket_count: hashlib.sha256() for ticket_count in TICKET_COUNTS}
    full_digest = hashlib.sha256()
    for row in iter_detail(Path(str(run["detail_path"]))):
        count += 1
        tickets = json.loads(row["ordered_tickets_20_json"])
        actual = json.loads(row["actual_numbers_json"])
        try:
            prefixes = ordered_prefixes(tickets)
        except Exception:
            failures["nesting_failures"] += 1
            continue
        if any(
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(
                type(number) is not int or not 1 <= number <= 49 for number in ticket
            )
            for ticket in tickets
        ):
            failures["ticket_legality_failures"] += 1
        if len({tuple(ticket) for ticket in tickets}) != 20:
            failures["portfolio_uniqueness_failures"] += 1
        scores = score_nested_portfolio(tickets, actual)
        for key, expected in scores.items():
            if int(row[key]) != expected:
                failures["hit_recomputation_mismatches"] += 1
        if not (
            int(row["m4plus_10"]) <= int(row["m4plus_15"]) <= int(row["m4plus_20"])
        ):
            failures["monotonicity_failures"] += 1
        for ticket_count in TICKET_COUNTS:
            expected_hash = ticket_count_portfolio_sha256(
                strategy_id=entry.strategy_id,
                effective_strategy_id=row["effective_strategy_id"],
                ticket_count=ticket_count,
                target_draw=row["target_draw"],
                replicate_id=int(row["replicate_id"]),
                source_head=source_head,
                constructor_version=(
                    f"{row['constructor_name']}/{row['constructor_version']}"
                ),
                tickets=prefixes[ticket_count],
            )
            if row[f"portfolio_sha256_{ticket_count}"] != expected_hash:
                failures["portfolio_hash_mismatches"] += 1
            count_hashes[ticket_count].update(
                canonical_json_bytes(
                    {
                        "target_draw": row["target_draw"],
                        "replicate_id": int(row["replicate_id"]),
                        "hash": expected_hash,
                    }
                )
            )
        if row["p20t_portfolio_sha256"] != p20c.portfolio_sha256(tickets):
            failures["p20t_hash_mismatches"] += 1
        if int(row["history_cutoff_identity"]) >= int(row["target_draw"]):
            failures["history_cutoff_failures"] += 1
        full_digest.update(canonical_json_bytes(_normalized_full20_payload(row)))
    if count != int(run["detail_rows"]):
        failures["row_count_mismatches"] += 1
    if sha256_file(Path(str(run["detail_path"]))) != run["detail_sha256"]:
        failures["detail_file_hash_mismatches"] += 1
    return {
        "strategy_id": entry.strategy_id,
        "detail_rows": count,
        "failures": dict(failures),
        "all_pass": not failures,
        "normalized_full20_digest": full_digest.hexdigest(),
        "ticket_count_digests": {
            str(key): value.hexdigest() for key, value in count_hashes.items()
        },
    }


def validate_details_parallel(
    runs: Sequence[Mapping[str, Any]],
    entries: Sequence[ExecutionIdentity],
    source_head: str,
    workers: int,
) -> list[dict[str, Any]]:
    by_id = {entry.strategy_id: entry for entry in entries}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as executor:
        futures = [
            executor.submit(
                validate_detail_file, run, by_id[str(run["strategy_id"])], source_head
            )
            for run in runs
        ]
        return [future.result() for future in futures]


def load_scalar_series(path: Path) -> dict[str, Any]:
    count_rows = {ticket_count: [] for ticket_count in TICKET_COUNTS}
    marginal_rows = {transition: [] for transition in MARGINAL_TRANSITIONS}
    native_counts = []
    constructed_counts = []
    effective_ids = set()
    for row in iter_detail(path):
        effective_ids.add(row["effective_strategy_id"])
        native_counts.append(int(row["native_valid_count"]))
        constructed_counts.append(int(row["constructed_ticket_count"]))
        for ticket_count in TICKET_COUNTS:
            count_rows[ticket_count].append(
                {
                    "target_draw": row["target_draw"],
                    "replicate_id": int(row["replicate_id"]),
                    "m4plus": int(row[f"m4plus_{ticket_count}"]),
                }
            )
        for transition in MARGINAL_TRANSITIONS:
            start, end = transition
            marginal_rows[transition].append(
                {
                    "target_draw": row["target_draw"],
                    "replicate_id": int(row["replicate_id"]),
                    "m4plus": int(row[f"incremental_{start}_to_{end}"]),
                }
            )
    return {
        "counts": count_rows,
        "marginals": marginal_rows,
        "native_counts": native_counts,
        "constructed_counts": constructed_counts,
        "effective_ids": effective_ids,
    }


def draw_mean_fractions(rows: Sequence[Mapping[str, Any]]) -> dict[str, Fraction]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        grouped[str(row["target_draw"])].append(int(row["m4plus"]))
    return {
        draw: Fraction(sum(values), len(values)) for draw, values in grouped.items()
    }


def paired_draw_differences(
    rows: Sequence[Mapping[str, Any]], baseline_rows: Sequence[Mapping[str, Any]]
) -> list[Fraction]:
    strategy = draw_mean_fractions(rows)
    baseline = draw_mean_fractions(baseline_rows)
    common = sorted(set(strategy) & set(baseline))
    return [strategy[draw] - baseline[draw] for draw in common]


def exact_one_sided_sign_flip_p_value(differences: Sequence[Fraction]) -> float:
    nonzero = [abs(value) for value in differences if value]
    observed = sum(differences, Fraction(0))
    if not nonzero:
        return 1.0
    denominator = math.lcm(
        *(value.denominator for value in nonzero), observed.denominator
    )
    weights = [int(value * denominator) for value in nonzero]
    threshold = int(observed * denominator)
    distribution: dict[int, float] = {0: 1.0}
    for weight in weights:
        updated: dict[int, float] = defaultdict(float)
        for total, probability in distribution.items():
            updated[total + weight] += probability * 0.5
            updated[total - weight] += probability * 0.5
        distribution = dict(updated)
    return min(
        1.0,
        sum(
            probability
            for total, probability in distribution.items()
            if total >= threshold
        ),
    )


def adjust_bh(p_values: Sequence[float]) -> list[float]:
    size = len(p_values)
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * size
    running = 1.0
    for rank_index in range(size - 1, -1, -1):
        original_index, value = ordered[rank_index]
        rank = rank_index + 1
        running = min(running, value * size / rank)
        adjusted[original_index] = min(1.0, running)
    return adjusted


def _cluster_interval(
    rows: Sequence[Mapping[str, Any]], identity: str, bootstrap_replicates: int
) -> tuple[float, float, str]:
    return p20c.cluster_interval(
        rows, identity=identity, bootstrap_replicates=bootstrap_replicates
    )


def _paired_interval(
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    identity: str,
    bootstrap_replicates: int,
) -> tuple[float, float, float]:
    return p20c.paired_baseline_interval(
        rows,
        baseline_rows,
        identity=identity,
        bootstrap_replicates=bootstrap_replicates,
    )


def aggregate_metrics(
    *,
    entries: Sequence[ExecutionIdentity],
    runs: Sequence[Mapping[str, Any]],
    bootstrap_replicates: int,
) -> dict[str, Any]:
    run_by_id = {str(run["strategy_id"]): run for run in runs}
    baseline_run = run_by_id["baseline::uniform_random_20"]
    baseline = load_scalar_series(Path(str(baseline_run["detail_path"])))
    random_rows = []
    for ticket_count in TICKET_COUNTS:
        rows = baseline["counts"][ticket_count]
        identity = (
            "baseline::uniform_random_20"
            if ticket_count == 20
            else f"baseline::uniform_random_20|ticket_count={ticket_count}"
        )
        low, high, method = _cluster_interval(rows, identity, bootstrap_replicates)
        hits = sum(int(row["m4plus"]) for row in rows)
        random_rows.append(
            {
                "strategy_id": "baseline::uniform_random_20",
                "ticket_count": ticket_count,
                "evaluated_draws": len({row["target_draw"] for row in rows}),
                "random_replicates": RANDOM_REPLICATES,
                "complete_portfolios": len(rows),
                "m4plus_hits": hits,
                "m4plus_rate": hits / len(rows),
                "m4plus_confidence_interval_95": interval_text(low, high),
                "confidence_method": method,
                "total_ticket_evaluations": len(rows) * ticket_count,
                "_ci_low": low,
                "_ci_high": high,
            }
        )
    random_by_count = {int(row["ticket_count"]): row for row in random_rows}

    metrics = []
    paired_rows = []
    marginal_rows = []
    entry_by_id = {entry.strategy_id: entry for entry in entries}
    for strategy_id in sorted(entry_by_id):
        entry = entry_by_id[strategy_id]
        if entry.spec.ranking_group == "baseline":
            continue
        run = run_by_id[strategy_id]
        series = load_scalar_series(Path(str(run["detail_path"])))
        if series["effective_ids"] != {entry.expected_effective_strategy_id}:
            raise ContractError(f"effective identity drift in detail for {strategy_id}")
        for ticket_count in TICKET_COUNTS:
            rows = series["counts"][ticket_count]
            baseline_rows = baseline["counts"][ticket_count]
            identity = (
                entry.spec.strategy_id
                if ticket_count == 20
                else f"{entry.spec.strategy_id}|ticket_count={ticket_count}"
            )
            hits = sum(int(row["m4plus"]) for row in rows)
            low, high, method = _cluster_interval(rows, identity, bootstrap_replicates)
            difference, paired_low, paired_high = _paired_interval(
                rows, baseline_rows, identity, bootstrap_replicates
            )
            p_value = exact_one_sided_sign_flip_p_value(
                paired_draw_differences(rows, baseline_rows)
            )
            random_metric = random_by_count[ticket_count]
            metric = {
                "strategy_id": strategy_id,
                "effective_strategy_id": entry.expected_effective_strategy_id,
                "governance_status": entry.governance["governance_status"],
                "independent_algorithm_id": entry.governance[
                    "independent_algorithm_id"
                ],
                "equivalence_group": entry.governance["equivalence_group"],
                "ticket_count": ticket_count,
                "evaluated_draws": len({row["target_draw"] for row in rows}),
                "common_window_draws": EXPECTED_COMMON_DRAWS,
                "strategy_replicates": entry.spec.replicates,
                "complete_portfolios": len(rows),
                "completion_rate": 1.0,
                "m4plus_hits": hits,
                "m4plus_rate": hits / len(rows),
                "m4plus_confidence_interval_95": interval_text(low, high),
                "confidence_method": method,
                "random_m4plus_hits": random_metric["m4plus_hits"],
                "random_m4plus_rate": random_metric["m4plus_rate"],
                "random_confidence_interval_95": random_metric[
                    "m4plus_confidence_interval_95"
                ],
                "paired_difference_vs_random": difference,
                "paired_difference_interval_95": interval_text(paired_low, paired_high),
                "paired_p_value": p_value,
                "multiplicity_adjusted_p_value": 1.0,
                "bh_fdr_adjusted_p_value": 1.0,
                "credible_advantage_unadjusted": p_value < CONFIRMATORY_ALPHA
                and paired_low > 0,
                "credible_advantage_adjusted": False,
                "runtime_seconds": run["runtime_seconds"],
                "_paired_ci_low": paired_low,
                "_paired_ci_high": paired_high,
                "_execution_identity": entry.spec.strategy_id,
            }
            metrics.append(metric)
            paired_rows.append(dict(metric))
        for start, end in MARGINAL_TRANSITIONS:
            rows = series["marginals"][(start, end)]
            baseline_rows = baseline["marginals"][(start, end)]
            identity = f"{entry.spec.strategy_id}|marginal={start}->{end}"
            hits = sum(int(row["m4plus"]) for row in rows)
            random_hits = sum(int(row["m4plus"]) for row in baseline_rows)
            low, high, _ = _cluster_interval(rows, identity, bootstrap_replicates)
            random_low, random_high, _ = _cluster_interval(
                baseline_rows,
                f"baseline::uniform_random_20|marginal={start}->{end}",
                bootstrap_replicates,
            )
            difference, paired_low, paired_high = _paired_interval(
                rows, baseline_rows, identity, bootstrap_replicates
            )
            marginal_rows.append(
                {
                    "strategy_id": strategy_id,
                    "effective_strategy_id": entry.expected_effective_strategy_id,
                    "independent_algorithm_id": entry.governance[
                        "independent_algorithm_id"
                    ],
                    "equivalence_group": entry.governance["equivalence_group"],
                    "from_ticket_count": start,
                    "to_ticket_count": end,
                    "evaluated_draws": len({row["target_draw"] for row in rows}),
                    "complete_portfolios": len(rows),
                    "incremental_m4plus_hits": hits,
                    "incremental_m4plus_rate": hits / len(rows),
                    "incremental_interval_95": interval_text(low, high),
                    "random_incremental_m4plus_hits": random_hits,
                    "random_incremental_m4plus_rate": random_hits / len(baseline_rows),
                    "random_incremental_interval_95": interval_text(
                        random_low, random_high
                    ),
                    "incremental_difference_vs_random": difference,
                    "incremental_difference_interval_95": interval_text(
                        paired_low, paired_high
                    ),
                    "paired_p_value": exact_one_sided_sign_flip_p_value(
                        paired_draw_differences(rows, baseline_rows)
                    ),
                }
            )

    apply_multiplicity(metrics)
    metric_lookup = {
        (row["strategy_id"], int(row["ticket_count"])): row for row in metrics
    }
    for row in paired_rows:
        adjusted = metric_lookup[(row["strategy_id"], int(row["ticket_count"]))]
        row.update(
            {
                "multiplicity_adjusted_p_value": adjusted[
                    "multiplicity_adjusted_p_value"
                ],
                "bh_fdr_adjusted_p_value": adjusted["bh_fdr_adjusted_p_value"],
                "credible_advantage_adjusted": adjusted["credible_advantage_adjusted"],
            }
        )
    return {
        "metrics": metrics,
        "paired": paired_rows,
        "random": random_rows,
        "marginals": marginal_rows,
        "baseline_series": baseline,
    }


def apply_multiplicity(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    representatives: dict[tuple[str, int], dict[str, Any]] = {}
    for row in sorted(metrics, key=lambda item: str(item["strategy_id"])):
        key = (str(row["independent_algorithm_id"]), int(row["ticket_count"]))
        representatives.setdefault(key, row)
    family = list(representatives.values())
    if len(family) != EXPECTED_COMPLETED * len(TICKET_COUNTS):
        raise ContractError(f"confirmatory-family drift: {len(family)} != 90")
    p_values = [float(row["paired_p_value"]) for row in family]
    bh_values = adjust_bh(p_values)
    by_key = {}
    for row, bh_value in zip(family, bh_values):
        bonferroni = min(1.0, float(row["paired_p_value"]) * len(family))
        key = (str(row["independent_algorithm_id"]), int(row["ticket_count"]))
        by_key[key] = (bonferroni, bh_value)
    for row in metrics:
        key = (str(row["independent_algorithm_id"]), int(row["ticket_count"]))
        bonferroni, bh_value = by_key[key]
        row["multiplicity_adjusted_p_value"] = bonferroni
        row["bh_fdr_adjusted_p_value"] = bh_value
        row["credible_advantage_adjusted"] = (
            bonferroni < CONFIRMATORY_ALPHA and float(row["_paired_ci_low"]) > 0
        )
    return metrics


def multiplicity_rows(metrics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in metrics:
        rows.append(
            {
                "confirmatory_family_id": (
                    f"{row['independent_algorithm_id']}|ticket_count={row['ticket_count']}"
                ),
                "strategy_id": row["strategy_id"],
                "independent_algorithm_id": row["independent_algorithm_id"],
                "equivalence_group": row["equivalence_group"],
                "ticket_count": row["ticket_count"],
                "raw_p_value": row["paired_p_value"],
                "bonferroni_adjusted_p_value": row["multiplicity_adjusted_p_value"],
                "bh_fdr_adjusted_p_value": row["bh_fdr_adjusted_p_value"],
                "paired_interval_95": row["paired_difference_interval_95"],
                "credible_advantage_unadjusted": row["credible_advantage_unadjusted"],
                "credible_advantage_adjusted": row["credible_advantage_adjusted"],
                "confirmatory_rule": CONFIRMATORY_FAMILY_DEFINITION,
            }
        )
    return rows


def ticket_efficiency_rows(
    metrics: Sequence[Mapping[str, Any]], marginals: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for metric in metrics:
        ticket_count = int(metric["ticket_count"])
        rows.append(
            {
                "strategy_id": metric["strategy_id"],
                "metric_scope": "ticket_count",
                "ticket_count": ticket_count,
                "from_ticket_count": "",
                "to_ticket_count": "",
                "m4plus_rate": metric["m4plus_rate"],
                "m4plus_rate_per_ticket": float(metric["m4plus_rate"]) / ticket_count,
                "incremental_m4plus_rate": "",
                "incremental_m4plus_rate_per_5_added_tickets": "",
                "additional_portfolios_succeeding_per_1000_draws": "",
                "extra_tickets_per_additional_m4plus_success": "",
                "status": "COUNT_RATE",
                "denominator": "evaluated draw portfolios",
            }
        )
    for marginal in marginals:
        start = int(marginal["from_ticket_count"])
        end = int(marginal["to_ticket_count"])
        rate = float(marginal["incremental_m4plus_rate"])
        added = end - start
        rows.append(
            {
                "strategy_id": marginal["strategy_id"],
                "metric_scope": "marginal",
                "ticket_count": "",
                "from_ticket_count": start,
                "to_ticket_count": end,
                "m4plus_rate": "",
                "m4plus_rate_per_ticket": "",
                "incremental_m4plus_rate": rate,
                "incremental_m4plus_rate_per_5_added_tickets": rate * 5 / added,
                "additional_portfolios_succeeding_per_1000_draws": rate * 1000,
                "extra_tickets_per_additional_m4plus_success": (
                    added / rate if rate else "NOT_APPLICABLE"
                ),
                "status": "OK" if rate else "NO_INCREMENTAL_SUCCESSES",
                "denominator": "evaluated draw portfolios",
            }
        )
    return rows


def rank_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    rate_field: str,
    hit_field: str | None = None,
    group_fields: Sequence[str] = (),
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in group_fields)].append(dict(row))
    ranked = []
    for key in sorted(grouped, key=lambda value: tuple(str(item) for item in value)):
        ordered = sorted(
            grouped[key],
            key=lambda row: (
                -float(row[rate_field]),
                -int(row[hit_field]) if hit_field else 0,
                str(row["strategy_id"]),
            ),
        )
        for rank, row in enumerate(ordered, 1):
            row["rank"] = rank
            ranked.append(row)
    return ranked


def independent_aggregate_recompute(
    runs: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    marginals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected_metrics = {
        (str(row["strategy_id"]), int(row["ticket_count"])): row for row in metrics
    }
    expected_marginals = {
        (
            str(row["strategy_id"]),
            int(row["from_ticket_count"]),
            int(row["to_ticket_count"]),
        ): row
        for row in marginals
    }
    mismatches = []
    rows_checked = 0
    for run in runs:
        strategy_id = str(run["strategy_id"])
        if strategy_id == "baseline::uniform_random_20":
            continue
        counts = Counter()
        hits = Counter()
        marginal_hits = Counter()
        draws = set()
        for row in iter_detail(Path(str(run["detail_path"]))):
            rows_checked += 1
            draws.add(row["target_draw"])
            for ticket_count in TICKET_COUNTS:
                counts[ticket_count] += 1
                hits[ticket_count] += int(row[f"m4plus_{ticket_count}"])
            for start, end in MARGINAL_TRANSITIONS:
                marginal_hits[(start, end)] += int(row[f"incremental_{start}_to_{end}"])
        for ticket_count in TICKET_COUNTS:
            expected = expected_metrics[(strategy_id, ticket_count)]
            if (
                counts[ticket_count] != int(expected["complete_portfolios"])
                or hits[ticket_count] != int(expected["m4plus_hits"])
                or not math.isclose(
                    hits[ticket_count] / counts[ticket_count],
                    float(expected["m4plus_rate"]),
                    abs_tol=1e-15,
                )
                or len(draws) != int(expected["evaluated_draws"])
            ):
                mismatches.append(f"{strategy_id}:{ticket_count}")
        for start, end in MARGINAL_TRANSITIONS:
            expected = expected_marginals[(strategy_id, start, end)]
            if marginal_hits[(start, end)] != int(expected["incremental_m4plus_hits"]):
                mismatches.append(f"{strategy_id}:{start}->{end}")
    return {
        "rows_checked": rows_checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "all_pass": not mismatches,
    }


def _close_float(left: Any, right: Any, *, tolerance: float = 1e-15) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)


def build_p20t_parity(
    *,
    metrics: Sequence[Mapping[str, Any]],
    random_rows: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, Any]],
    detail_validations: Sequence[Mapping[str, Any]],
    entries: Sequence[ExecutionIdentity],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    upstream_metrics = {
        row["strategy_id"]: row
        for row in read_csv(P20T_DIR / "final_39_completed_strategy_metrics.csv")
    }
    current_20 = {
        str(row["strategy_id"]): row
        for row in metrics
        if int(row["ticket_count"]) == 20
    }
    if set(current_20) != set(upstream_metrics):
        raise ContractError("P20T strategy identity set parity failed")
    manifest = json.loads(P20T_MANIFEST.read_text(encoding="utf-8"))
    validation = json.loads(
        (P20T_DIR / "validation_results.json").read_text(encoding="utf-8")
    )
    direct_files = {
        str(row["strategy_id"]): row for row in manifest["execution"]["detail_files"]
    }
    run_by_id = {str(row["strategy_id"]): row for row in runs}
    detail_by_id = {str(row["strategy_id"]): row for row in detail_validations}
    entry_by_id = {entry.strategy_id: entry for entry in entries}
    p20s_reuse_pass = bool(validation["p20s_reuse"]["pass"])

    baseline_upstream = direct_files.get("baseline::uniform_random_20")
    baseline_direct_pass = False
    baseline_direct_details: dict[str, Any] = {}
    if baseline_upstream:
        upstream_path = Path(str(baseline_upstream["path"]))
        if (
            upstream_path.is_file()
            and sha256_file(upstream_path) == baseline_upstream["sha256"]
        ):
            upstream_digest, upstream_rows = normalized_full20_digest(
                upstream_path, upstream_p20t=True
            )
            new_digest, new_rows = normalized_full20_digest(
                Path(str(run_by_id["baseline::uniform_random_20"]["detail_path"]))
            )
            baseline_direct_pass = (
                upstream_digest == new_digest
                and upstream_rows
                == new_rows
                == EXPECTED_COMMON_DRAWS * RANDOM_REPLICATES
            )
            baseline_direct_details = {
                "upstream_digest": upstream_digest,
                "new_digest": new_digest,
                "rows": new_rows,
            }

    parity_rows = []
    for strategy_id in sorted(current_20):
        current = current_20[strategy_id]
        upstream = upstream_metrics[strategy_id]
        metric_checks = {
            "effective_strategy_id": current["effective_strategy_id"]
            == upstream["effective_strategy_id"],
            "evaluated_draws": int(current["evaluated_draws"])
            == int(upstream["evaluated_draws"]),
            "common_window_draws": int(current["common_window_draws"])
            == int(upstream["common_window_draws"]),
            "replicates": int(current["strategy_replicates"])
            == int(upstream["replicates"]),
            "complete_portfolios": int(current["complete_portfolios"])
            == int(upstream["complete_portfolios"]),
            "completion_rate": _close_float(
                current["completion_rate"], upstream["completion_rate"]
            ),
            "m4plus_hits": int(current["m4plus_hits"]) == int(upstream["m4plus_hits"]),
            "m4plus_rate": _close_float(
                current["m4plus_rate"], upstream["m4plus_rate"]
            ),
            "m4plus_interval": current["m4plus_confidence_interval_95"]
            == upstream["confidence_interval_95"],
            "random_rate": _close_float(
                current["random_m4plus_rate"],
                upstream["random_m4plus_rate_same_ticket_count"],
            ),
            "paired_difference": _close_float(
                current["paired_difference_vs_random"],
                upstream["paired_difference_vs_random"],
            ),
            "paired_interval": current["paired_difference_interval_95"]
            == upstream["paired_interval_95"],
        }
        metric_pass = all(metric_checks.values())
        direct = direct_files.get(entry_by_id[strategy_id].spec.strategy_id)
        direct_digest_pass = False
        upstream_digest = ""
        if direct:
            direct_path = Path(str(direct["path"]))
            if direct_path.is_file() and sha256_file(direct_path) == direct["sha256"]:
                upstream_digest, upstream_rows = normalized_full20_digest(
                    direct_path, upstream_p20t=True
                )
                direct_digest_pass = upstream_digest == detail_by_id[strategy_id][
                    "normalized_full20_digest"
                ] and upstream_rows == int(run_by_id[strategy_id]["detail_rows"])
        if direct:
            portfolio_method = "DIRECT_P20T_NORMALIZED_DETAIL_DIGEST"
            portfolio_pass = direct_digest_pass
        else:
            portfolio_method = (
                "P20T_VERIFIED_P20S_SOURCE_BINDING_PLUS_DETERMINISTIC_REEXECUTION"
            )
            portfolio_pass = p20s_reuse_pass and metric_pass
        status = "PASS" if metric_pass and portfolio_pass else "FAIL"
        parity_rows.append(
            {
                "strategy_id": strategy_id,
                "effective_strategy_id": current["effective_strategy_id"],
                "metric_parity": "PASS" if metric_pass else "FAIL",
                "portfolio_hash_parity": "PASS" if portfolio_pass else "FAIL",
                "portfolio_parity_method": portfolio_method,
                "upstream_normalized_detail_digest": upstream_digest,
                "p20u_normalized_detail_digest": detail_by_id[strategy_id][
                    "normalized_full20_digest"
                ],
                "evaluated_draws": current["evaluated_draws"],
                "m4plus_hits": current["m4plus_hits"],
                "m4plus_rate": current["m4plus_rate"],
                "paired_difference_vs_random": current["paired_difference_vs_random"],
                "failed_metric_checks": ";".join(
                    key for key, passed in metric_checks.items() if not passed
                ),
                "status": status,
            }
        )

    upstream_ranking = [
        row["strategy_id"]
        for row in sorted(
            read_csv(P20T_DIR / "final_39_m4plus_all_valid_ranking.csv"),
            key=lambda row: int(row["rank"]),
        )
    ]
    current_ranking = [
        row["strategy_id"]
        for row in sorted(
            current_20.values(),
            key=lambda row: (
                -float(row["m4plus_rate"]),
                -int(row["m4plus_hits"]),
                str(row["effective_strategy_id"]),
            ),
        )
    ]
    random_20 = next(row for row in random_rows if int(row["ticket_count"]) == 20)
    upstream_random = manifest["backtest"]["random_baseline"]
    random_metric_pass = (
        int(random_20["complete_portfolios"])
        == int(upstream_random["evaluated_portfolios"])
        and int(random_20["m4plus_hits"]) == int(upstream_random["m4plus_draw_hits"])
        and _close_float(random_20["m4plus_rate"], upstream_random["m4plus_draw_rate"])
        and _close_float(
            parse_interval(random_20["m4plus_confidence_interval_95"])[0],
            upstream_random["m4plus_ci95_low"],
        )
        and _close_float(
            parse_interval(random_20["m4plus_confidence_interval_95"])[1],
            upstream_random["m4plus_ci95_high"],
        )
    )
    summary = {
        "strategy_identity_set": set(current_20) == set(upstream_metrics),
        "effective_identity_set": {
            row["effective_strategy_id"] for row in current_20.values()
        }
        == {row["effective_strategy_id"] for row in upstream_metrics.values()},
        "metric_parity": all(row["metric_parity"] == "PASS" for row in parity_rows),
        "portfolio_hash_parity": all(
            row["portfolio_hash_parity"] == "PASS" for row in parity_rows
        ),
        "random_metric_parity": random_metric_pass,
        "random_portfolio_hash_parity": baseline_direct_pass,
        "ranking_parity": current_ranking == upstream_ranking,
        "baseline_direct_details": baseline_direct_details,
        "direct_strategy_detail_comparisons": sum(
            row["portfolio_parity_method"] == "DIRECT_P20T_NORMALIZED_DETAIL_DIGEST"
            for row in parity_rows
        ),
        "source_bound_p20s_reexecutions": sum(
            row["portfolio_parity_method"].startswith("P20T_VERIFIED_P20S")
            for row in parity_rows
        ),
    }
    summary["all_pass"] = all(
        value for key, value in summary.items() if isinstance(value, bool)
    )
    return parity_rows, summary


def nesting_rows(
    detail_validations: Sequence[Mapping[str, Any]],
    entries: Sequence[ExecutionIdentity],
) -> list[dict[str, Any]]:
    entry_by_id = {entry.strategy_id: entry for entry in entries}
    rows = []
    for result in sorted(detail_validations, key=lambda item: item["strategy_id"]):
        entry = entry_by_id[str(result["strategy_id"])]
        failures = result["failures"]
        rows.append(
            {
                "row_type": (
                    "random_baseline"
                    if entry.spec.ranking_group == "baseline"
                    else "strategy"
                ),
                "strategy_id": entry.strategy_id,
                "effective_strategy_id": entry.expected_effective_strategy_id,
                "validated_portfolios": result["detail_rows"],
                "prefix_10_in_15": "PASS"
                if not failures.get("nesting_failures")
                else "FAIL",
                "prefix_15_in_20": "PASS"
                if not failures.get("nesting_failures")
                else "FAIL",
                "m4plus_monotonicity": "PASS"
                if not failures.get("monotonicity_failures")
                else "FAIL",
                "ticket_legality": "PASS"
                if not failures.get("ticket_legality_failures")
                else "FAIL",
                "portfolio_uniqueness": "PASS"
                if not failures.get("portfolio_uniqueness_failures")
                else "FAIL",
                "portfolio_hashes": "PASS"
                if not failures.get("portfolio_hash_mismatches")
                else "FAIL",
                "nesting_failures": failures.get("nesting_failures", 0),
                "monotonicity_failures": failures.get("monotonicity_failures", 0),
                "digest_10": result["ticket_count_digests"]["10"],
                "digest_15": result["ticket_count_digests"]["15"],
                "digest_20": result["ticket_count_digests"]["20"],
                "status": "PASS" if result["all_pass"] else "FAIL",
            }
        )
    return rows


def strip_internal(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def ranked_metric_rows(
    metrics: Sequence[Mapping[str, Any]], ticket_count: int
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in metrics if int(row["ticket_count"]) == ticket_count]
    rows.sort(
        key=lambda row: (
            -float(row["m4plus_rate"]),
            -int(row["m4plus_hits"]),
            str(row["effective_strategy_id"]),
        )
    )
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def markdown_rate(value: Any) -> str:
    return f"{float(value):.4%}"


def generate_final_report(
    *,
    metrics: Sequence[Mapping[str, Any]],
    random_rows: Sequence[Mapping[str, Any]],
    marginals: Sequence[Mapping[str, Any]],
    parity: Mapping[str, Any],
    nesting: Sequence[Mapping[str, Any]],
    verification: Mapping[str, Any],
) -> str:
    metric_by_key = {
        (str(row["strategy_id"]), int(row["ticket_count"])): row for row in metrics
    }
    random_by_count = {int(row["ticket_count"]): row for row in random_rows}
    strategy_ids = sorted({str(row["strategy_id"]) for row in metrics})
    descriptive = {
        count: [
            strategy_id
            for strategy_id in strategy_ids
            if float(metric_by_key[(strategy_id, count)]["paired_difference_vs_random"])
            > 0
        ]
        for count in TICKET_COUNTS
    }
    adjusted = {
        count: [
            strategy_id
            for strategy_id in strategy_ids
            if bool(metric_by_key[(strategy_id, count)]["credible_advantage_adjusted"])
        ]
        for count in TICKET_COUNTS
    }
    marginal_by_key = {
        (
            str(row["strategy_id"]),
            int(row["from_ticket_count"]),
            int(row["to_ticket_count"]),
        ): row
        for row in marginals
    }
    leader_10_15 = max(
        (
            row
            for row in marginals
            if int(row["from_ticket_count"]) == 10 and int(row["to_ticket_count"]) == 15
        ),
        key=lambda row: (
            float(row["incremental_m4plus_rate"]),
            str(row["strategy_id"]),
        ),
    )
    leader_15_20 = max(
        (
            row
            for row in marginals
            if int(row["from_ticket_count"]) == 15 and int(row["to_ticket_count"]) == 20
        ),
        key=lambda row: (
            float(row["incremental_m4plus_rate"]),
            str(row["strategy_id"]),
        ),
    )
    diminishing = [
        strategy_id
        for strategy_id in strategy_ids
        if float(marginal_by_key[(strategy_id, 15, 20)]["incremental_m4plus_rate"])
        < float(marginal_by_key[(strategy_id, 10, 15)]["incremental_m4plus_rate"])
    ]
    marginal_exceeds_random = {
        transition: sum(
            float(row["incremental_difference_vs_random"]) > 0
            for row in marginals
            if (int(row["from_ticket_count"]), int(row["to_ticket_count"]))
            == transition
        )
        for transition in MARGINAL_TRANSITIONS
    }
    top_efficiency = {
        count: max(
            (metric_by_key[(strategy_id, count)] for strategy_id in strategy_ids),
            key=lambda row: (
                float(row["m4plus_rate"]) / count,
                str(row["strategy_id"]),
            ),
        )["strategy_id"]
        for count in TICKET_COUNTS
    }
    grouped_leaders = []
    for count in TICKET_COUNTS:
        for row in ranked_metric_rows(metrics, count)[:5]:
            if row["equivalence_group"]:
                grouped_leaders.append(
                    f"`{row['strategy_id']}` ({row['equivalence_group']}, {count} tickets)"
                )
    grouped_leaders = sorted(set(grouped_leaders))
    overall_changed = any(adjusted[count] for count in TICKET_COUNTS)
    mean_rates = {
        count: fmean(
            float(metric_by_key[(strategy_id, count)]["m4plus_rate"])
            for strategy_id in strategy_ids
        )
        for count in TICKET_COUNTS
    }

    lines = [
        "# P20U Big Lotto 10/15/20-Ticket M4+ Analysis",
        "",
        "All 30 completed governed strategies were evaluated over the same 2,025 historical target draws. Each 10- and 15-ticket portfolio is a prefix of the exact ordered 20-ticket portfolio; the random baseline uses the same nesting and ticket count. All nesting, M4+ monotonicity, and P20T 20-ticket parity gates passed.",
        "",
        "This is descriptive historical research for entertainment purposes only. It is not a future winning probability, betting recommendation, profitability analysis, or production guarantee.",
        "",
        "## Historical rates by strategy",
        "",
        "Each cell is strategy M4+ rate followed by the same-count random rate in parentheses.",
        "",
        "| Strategy | 10 tickets | 15 tickets | 20 tickets |",
        "|---|---:|---:|---:|",
    ]
    for strategy_id in strategy_ids:
        cells = []
        for count in TICKET_COUNTS:
            metric = metric_by_key[(strategy_id, count)]
            cells.append(
                f"{markdown_rate(metric['m4plus_rate'])} ({markdown_rate(metric['random_m4plus_rate'])})"
            )
        lines.append(f"| `{strategy_id}` | {' | '.join(cells)} |")
    lines.extend(
        [
            "",
            "## Answers",
            "",
            f"1. The complete per-strategy rates are in the table above and `strategy_ticket_count_metrics.csv` ({len(metrics)} strategy/count rows).",
            f"2. Same-count random rates were 10 tickets: {markdown_rate(random_by_count[10]['m4plus_rate'])}; 15 tickets: {markdown_rate(random_by_count[15]['m4plus_rate'])}; 20 tickets: {markdown_rate(random_by_count[20]['m4plus_rate'])}.",
            f"3. Strategies descriptively above random: 10 tickets = {len(descriptive[10])}; 15 tickets = {len(descriptive[15])}; 20 tickets = {len(descriptive[20])}. Descriptive uplift is not confirmatory evidence.",
            f"4. Strategies surviving the frozen Bonferroni confirmatory rule: 10 tickets = {len(adjusted[10])}; 15 tickets = {len(adjusted[15])}; 20 tickets = {len(adjusted[20])}.",
            f"5. The largest 10→15 historical gain was `{leader_10_15['strategy_id']}` at {markdown_rate(leader_10_15['incremental_m4plus_rate'])}; all 30 results and uncertainty intervals are in `marginal_gain_10_to_15.csv`.",
            f"6. The largest 15→20 historical gain was `{leader_15_20['strategy_id']}` at {markdown_rate(leader_15_20['incremental_m4plus_rate'])}; all results are in `marginal_gain_15_to_20.csv`.",
            f"7. Positive strategy-minus-random marginal differences occurred for {marginal_exceeds_random[(10, 15)]}/30 strategies at 10→15, {marginal_exceeds_random[(15, 20)]}/30 at 15→20, and {marginal_exceeds_random[(10, 20)]}/30 at 10→20. The paired intervals determine uncertainty.",
            f"8. The five-ticket marginal leaders are `{leader_10_15['strategy_id']}` for 10→15 and `{leader_15_20['strategy_id']}` for 15→20.",
            f"9. {len(diminishing)} strategies had a smaller 15→20 increment than 10→15; this is the report's descriptive definition of diminishing marginal improvement.",
            f"10. The highest M4+ rate per ticket was `{top_efficiency[10]}` at 10 tickets, `{top_efficiency[15]}` at 15, and `{top_efficiency[20]}` at 20. These are hit-rate efficiency measures, not financial returns.",
            f"11. Nested M4+ monotonicity passed for every strategy and the random baseline ({sum(row['status'] == 'PASS' for row in nesting)}/{len(nesting)} detail groups).",
            f"12. The 20-ticket slice reproduced P20T: metric parity = {parity['metric_parity']}, portfolio-hash parity = {parity['portfolio_hash_parity']}, random parity = {parity['random_metric_parity'] and parity['random_portfolio_hash_parity']}, ranking parity = {parity['ranking_parity']}.",
            f"13. The multiplicity-adjusted conclusion about credible historical advantage {'changed' if overall_changed else 'did not change'}; the earlier P20T result had zero credible 20-ticket advantages. No historical conclusion establishes future predictive advantage.",
            "14. Apparent leaders tied to governed alias/equivalence groups: "
            + (
                ", ".join(grouped_leaders)
                if grouped_leaders
                else "none among the top-five rows"
            )
            + ". Group members are not counted as independent confirmation.",
            f"15. Across strategies, the mean historical M4+ rate rose from {markdown_rate(mean_rates[10])} at 10 tickets to {markdown_rate(mean_rates[15])} at 15 and {markdown_rate(mean_rates[20])} at 20. More tickets mechanically expand coverage, while the marginal files show how much additional historical success the extra prefixes supplied.",
            "16. This analysis cannot establish future win probabilities, causal predictive skill, expected profit, ticket affordability, an optimal spend, or a production guarantee. It also does not justify strategy promotion.",
            "",
            "## Reproducibility and verification",
            "",
            f"- Historical draw portfolios: {sum(int(row['complete_portfolios']) for row in metrics)} count-specific strategy portfolios across the three ticket counts.",
            f"- Confirmatory family: {CONFIRMATORY_FAMILY_DEFINITION}.",
            f"- Tests: {verification['tests']['passed']} passed, {verification['tests']['failed']} failed, {verification['tests']['skipped']} skipped, {verification['tests']['deselected']} deselected.",
            "- Large ticket detail was independently recomputed, used for aggregate reproduction, and removed after successful byte reproduction; only compact evidence is committed.",
            "",
            "Across 30 completed governed Big Lotto strategies, the historical portfolio-level M4+ rates were evaluated at 10, 15 and 20 tickets using nested portfolios and same-ticket-count random baselines. These results describe historical behavior only and do not establish future winning probabilities or betting profitability.",
            "",
        ]
    )
    return "\n".join(lines)


def artifact_tree(path: Path) -> dict[str, str]:
    return {
        item.name: sha256_file(item)
        for item in sorted(path.iterdir())
        if item.is_file()
    }


def build_bundle(stage: Path, payload: Mapping[str, Any]) -> dict[str, str]:
    stage.mkdir(parents=True, exist_ok=False)
    metrics = [strip_internal(row) for row in payload["metrics"]]
    paired = [strip_internal(row) for row in payload["paired"]]
    random_rows = [strip_internal(row) for row in payload["random"]]
    marginals = [strip_internal(row) for row in payload["marginals"]]
    universe_fields = (
        "strategy_id",
        "execution_strategy_id",
        "effective_strategy_id",
        "strategy_name",
        "governance_status",
        "independent_algorithm_id",
        "alias_of",
        "equivalence_group",
        "terminal_disposition",
        "ranking_group",
        "strategy_replicates",
        "minimum_history",
        "nested_prefix_supported",
    )
    nesting_fields = (
        "row_type",
        "strategy_id",
        "effective_strategy_id",
        "validated_portfolios",
        "prefix_10_in_15",
        "prefix_15_in_20",
        "m4plus_monotonicity",
        "ticket_legality",
        "portfolio_uniqueness",
        "portfolio_hashes",
        "nesting_failures",
        "monotonicity_failures",
        "digest_10",
        "digest_15",
        "digest_20",
        "status",
    )
    parity_fields = (
        "strategy_id",
        "effective_strategy_id",
        "metric_parity",
        "portfolio_hash_parity",
        "portfolio_parity_method",
        "upstream_normalized_detail_digest",
        "p20u_normalized_detail_digest",
        "evaluated_draws",
        "m4plus_hits",
        "m4plus_rate",
        "paired_difference_vs_random",
        "failed_metric_checks",
        "status",
    )
    efficiency_fields = (
        "strategy_id",
        "metric_scope",
        "ticket_count",
        "from_ticket_count",
        "to_ticket_count",
        "m4plus_rate",
        "m4plus_rate_per_ticket",
        "incremental_m4plus_rate",
        "incremental_m4plus_rate_per_5_added_tickets",
        "additional_portfolios_succeeding_per_1000_draws",
        "extra_tickets_per_additional_m4plus_success",
        "status",
        "denominator",
    )
    multiplicity_fields = (
        "confirmatory_family_id",
        "strategy_id",
        "independent_algorithm_id",
        "equivalence_group",
        "ticket_count",
        "raw_p_value",
        "bonferroni_adjusted_p_value",
        "bh_fdr_adjusted_p_value",
        "paired_interval_95",
        "credible_advantage_unadjusted",
        "credible_advantage_adjusted",
        "confirmatory_rule",
    )
    write_csv(
        stage / "completed_30_strategy_universe.csv",
        payload["universe"],
        universe_fields,
    )
    write_json(
        stage / "ticket_count_configuration.json", payload["ticket_configuration"]
    )
    write_csv(
        stage / "portfolio_nesting_validation.csv", payload["nesting"], nesting_fields
    )
    write_csv(
        stage / "p20t_20_ticket_parity.csv", payload["parity_rows"], parity_fields
    )
    write_csv(stage / "strategy_ticket_count_metrics.csv", metrics, METRIC_FIELDS)
    write_csv(stage / "random_ticket_count_metrics.csv", random_rows, RANDOM_FIELDS)
    write_csv(stage / "paired_strategy_vs_random.csv", paired, METRIC_FIELDS)
    for start, end in MARGINAL_TRANSITIONS:
        write_csv(
            stage / f"marginal_gain_{start}_to_{end}.csv",
            [
                row
                for row in marginals
                if int(row["from_ticket_count"]) == start
                and int(row["to_ticket_count"]) == end
            ],
            MARGINAL_FIELDS,
        )
    write_csv(stage / "marginal_gain_vs_random.csv", marginals, MARGINAL_FIELDS)
    write_csv(
        stage / "ticket_efficiency_metrics.csv",
        payload["efficiency"],
        efficiency_fields,
    )
    for ticket_count in TICKET_COUNTS:
        ranking = [
            strip_internal(row)
            for row in ranked_metric_rows(payload["metrics"], ticket_count)
        ]
        write_csv(
            stage / f"ranking_{ticket_count}_ticket_m4plus.csv",
            ranking,
            ("rank", *METRIC_FIELDS),
        )
    uplift = rank_rows(
        metrics,
        rate_field="paired_difference_vs_random",
        group_fields=("ticket_count",),
    )
    write_csv(
        stage / "ranking_same_count_random_uplift.csv",
        uplift,
        ("rank", *METRIC_FIELDS),
    )
    marginal_ranking = rank_rows(
        marginals,
        rate_field="incremental_m4plus_rate",
        hit_field="incremental_m4plus_hits",
        group_fields=("from_ticket_count", "to_ticket_count"),
    )
    write_csv(
        stage / "ranking_marginal_gain.csv",
        marginal_ranking,
        ("rank", *MARGINAL_FIELDS),
    )
    write_csv(
        stage / "multiplicity_adjustment_results.csv",
        payload["multiplicity"],
        multiplicity_fields,
    )
    (stage / "final_report.md").write_text(payload["report"], encoding="utf-8")

    validation = json.loads(json.dumps(payload["validation"]))
    payload_names = sorted(
        name
        for name in REQUIRED_OUTPUTS
        if name not in {"run_manifest.json", "validation_results.json"}
    )
    payload_hashes = {name: sha256_file(stage / name) for name in payload_names}
    validation["checks"]["artifact_payload_hashes"] = {
        "pass": all(
            sha256_file(stage / name) == digest
            for name, digest in payload_hashes.items()
        ),
        "details": payload_hashes,
    }
    validation["status"] = (
        "PASS"
        if all(
            item.get("pass", False)
            for item in validation["checks"].values()
            if isinstance(item, Mapping)
        )
        else "FAIL"
    )
    write_json(stage / "validation_results.json", validation)

    manifest = json.loads(json.dumps(payload["manifest"]))
    manifest["outputs"] = {
        name: sha256_file(stage / name)
        for name in sorted(item.name for item in stage.iterdir() if item.is_file())
    }
    manifest["validation_status"] = validation["status"]
    write_json(stage / "run_manifest.json", manifest)
    missing = [name for name in REQUIRED_OUTPUTS if not (stage / name).is_file()]
    if missing:
        raise ContractError(f"required output files missing: {missing}")
    checksum_lines = [
        f"{sha256_file(stage / name)}  {name}\n" for name in sorted(REQUIRED_OUTPUTS)
    ]
    (stage / "artifact_hashes.sha256").write_text(
        "".join(checksum_lines), encoding="utf-8"
    )
    for line in checksum_lines:
        digest, name = line.rstrip("\n").split("  ", 1)
        if sha256_file(stage / name) != digest:
            raise ContractError(f"artifact checksum validation failed: {name}")
    return artifact_tree(stage)


def cleanup_checkpoint_directory(checkpoint_dir: Path) -> None:
    checkpoint_dir = checkpoint_dir.resolve()
    if checkpoint_dir in {Path("/"), Path.home().resolve(), REPO_ROOT.resolve()}:
        raise ContractError(f"refusing broad checkpoint cleanup: {checkpoint_dir}")
    manifest_path = checkpoint_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ContractError("checkpoint cleanup requires its task manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("task") != TASK_ID:
        raise ContractError("checkpoint directory is not owned by P20U")
    for path in sorted(checkpoint_dir.iterdir()):
        if path.is_file():
            path.unlink()
        else:
            raise ContractError(f"unexpected checkpoint subdirectory: {path}")
    checkpoint_dir.rmdir()


def pre_run_manifest(
    *,
    source_head: str,
    origin_main: str,
    p20t_manifest_sha256: str,
    p20t_tree_digest: str,
    dataset_sha256: str,
    database_sha256: str,
    completed_ids: Sequence[str],
    excluded_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "task": TASK_ID,
        "status": "PREPARED_BEFORE_HISTORICAL_EXECUTION",
        "source_head": source_head,
        "origin_main": origin_main,
        "upstream_p20t_merge_commit": UPSTREAM_P20T_MERGE_COMMIT,
        "upstream_p20t_manifest_sha256": p20t_manifest_sha256,
        "upstream_p20t_tree_digest": p20t_tree_digest,
        "dataset_sha256": dataset_sha256,
        "database_sha256": database_sha256,
        "constructor_version": CONSTRUCTOR_IDENTIFIER,
        "ticket_counts": list(TICKET_COUNTS),
        "portfolio_contract": PORTFOLIO_ORDERING_CONTRACT,
        "random_replicates": RANDOM_REPLICATES,
        "completed_strategy_count": len(completed_ids),
        "completed_strategy_ids": list(completed_ids),
        "excluded_strategy_count": len(excluded_ids),
        "excluded_strategy_ids": list(excluded_ids),
        "confirmatory_family_definition": CONFIRMATORY_FAMILY_DEFINITION,
        "confirmatory_family_size": len(completed_ids) * len(TICKET_COUNTS),
        "metric_contract_version": METRIC_CONTRACT_VERSION,
    }


def parse_verification_summary(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("verification summary must be valid JSON") from exc
    required = {"passed", "failed", "skipped", "deselected", "commands"}
    if not required.issubset(payload):
        raise ValueError(
            f"verification summary missing {sorted(required - set(payload))}"
        )
    if int(payload["failed"]) != 0:
        raise ValueError("verification summary contains failures")
    return payload


def quality_pass(quality: Mapping[str, Any]) -> bool:
    zero_fields = (
        "duplicate_draw_ids",
        "duplicate_dates",
        "invalid_json_rows",
        "wrong_main_number_count_rows",
        "out_of_range_rows",
        "duplicate_main_number_rows",
        "invalid_or_overlapping_special_rows",
        "negative_financial_rows",
        "outside_selected_window_rows",
    )
    return (
        int(quality["canonical_main_rows"]) == EXPECTED_DRAWS
        and int(quality["common_window_rows"]) == EXPECTED_COMMON_DRAWS
        and all(int(quality[field]) == 0 for field in zero_fields)
        and quality["date_format_counts"] == {"YYYY/MM/DD": EXPECTED_DRAWS}
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--canonical-repo", type=Path, required=True)
    parser.add_argument("--reusable-worktree", type=Path, required=True)
    parser.add_argument("--expected-canonical-status-sha256", required=True)
    parser.add_argument("--expected-canonical-branch", required=True)
    parser.add_argument("--expected-canonical-head", required=True)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--expected-unrelated-worktree-sha256", required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--bootstrap-replicates", type=int, default=DEFAULT_BOOTSTRAP_REPLICATES
    )
    parser.add_argument("--validation-workers", type=int, default=4)
    parser.add_argument("--verification-summary-json", default="")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--cleanup-checkpoints-on-success", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_ticket_counts(TICKET_COUNTS)
    if args.timeout_seconds <= 0:
        parser.error("timeout seconds must be positive")
    if args.bootstrap_replicates <= 0:
        parser.error("bootstrap replicates must be positive")
    if not 1 <= args.validation_workers <= 4:
        parser.error("validation workers must be in 1..4")

    reusable = args.reusable_worktree.resolve()
    if reusable != REPO_ROOT.resolve():
        parser.error(f"runner must execute in the reusable worktree: {REPO_ROOT}")
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        parser.error(f"refusing to overwrite immutable evidence: {output_dir}")
    if output_dir.parent != (REPO_ROOT / "outputs/research").resolve():
        parser.error("output directory must be a direct child of outputs/research")

    canonical_repo = args.canonical_repo.resolve()
    database = args.database.resolve()
    canonical_status_before = p20c.normalized_git_status_sha256(canonical_repo)
    canonical_branch_before = git_value(canonical_repo, "branch", "--show-current")
    canonical_head_before = git_value(canonical_repo, "rev-parse", "HEAD")
    if canonical_status_before != args.expected_canonical_status_sha256:
        parser.error("canonical checkout status changed before execution")
    if canonical_branch_before != args.expected_canonical_branch:
        parser.error("canonical branch changed before execution")
    if canonical_head_before != args.expected_canonical_head:
        parser.error("canonical HEAD changed before execution")
    database_before = sha256_file(database)
    if database_before != args.expected_database_sha256:
        parser.error("canonical database hash changed before execution")
    sidecars_before = sidecar_inventory(database)
    unrelated_before = normalized_unrelated_worktree_sha256(canonical_repo, reusable)
    if unrelated_before != args.expected_unrelated_worktree_sha256:
        parser.error("unrelated worktree inventory changed before execution")

    origin_main = git_value(REPO_ROOT, "rev-parse", "origin/main")
    source_head = git_value(REPO_ROOT, "rev-parse", "HEAD")
    if subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "merge-base",
            "--is-ancestor",
            UPSTREAM_P20T_MERGE_COMMIT,
            "origin/main",
        ],
        check=False,
    ).returncode:
        parser.error("required P20T merge is absent from origin/main")
    if not args.preflight_only and git_value(REPO_ROOT, "status", "--short"):
        parser.error(
            "full historical reproduction requires a clean code-commit worktree"
        )

    p20t_manifest_hash = sha256_file(P20T_MANIFEST)
    p20t_tree_before = combined_tree_digest(P20T_DIR)
    p20t_manifest = json.loads(P20T_MANIFEST.read_text(encoding="utf-8"))
    if (
        p20t_manifest_hash
        != "12abef07b6223de3661aae6def9e40bbe56a2771a26824649e1aa255e273d46c"
    ):
        parser.error("P20T manifest hash drift")
    required_accounting = {
        "completed": 30,
        "engineering_backlog": 0,
        "governed_identities": 39,
        "terminally_excluded": 9,
    }
    if any(
        int(p20t_manifest["final_accounting"].get(key, -1)) != expected
        for key, expected in required_accounting.items()
    ):
        parser.error("P20T final accounting drift")

    draws, quality = p20c.load_draws_and_quality(database)
    if not quality_pass(quality):
        parser.error(f"canonical data-quality gate failed: {quality}")
    if quality["canonical_dataset_sha256"] != p20t_manifest["dataset_sha256"]:
        parser.error("canonical dataset digest drift")
    universe = load_frozen_universe()
    entries = build_execution_identities(universe)
    real_entries = [
        entry for entry in entries if entry.spec.ranking_group != "baseline"
    ]

    preflight = p20s.preflight_executable_specs(
        draws, [entry.spec for entry in entries]
    )
    if len(preflight) != EXPECTED_COMPLETED or any(
        row["preflight_status"] != "PASS" for row in preflight
    ):
        print(
            json.dumps(preflight, ensure_ascii=False, sort_keys=True),
            file=os.sys.stderr,
        )
        return 2
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "completed_strategy_count": len(real_entries),
                    "preflight_passed": len(preflight),
                    "dataset_sha256": quality["canonical_dataset_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    try:
        tests = parse_verification_summary(args.verification_summary_json)
    except ValueError as exc:
        parser.error(str(exc))

    checkpoint_dir = args.checkpoint_dir.resolve()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    runner_source_sha256 = sha256_file(Path(__file__))
    prepared_manifest = pre_run_manifest(
        source_head=source_head,
        origin_main=origin_main,
        p20t_manifest_sha256=p20t_manifest_hash,
        p20t_tree_digest=p20t_tree_before,
        dataset_sha256=quality["canonical_dataset_sha256"],
        database_sha256=database_before,
        completed_ids=universe["completed_ids"],
        excluded_ids=universe["excluded_ids"],
    )
    checkpoint_manifest = checkpoint_dir / "run_manifest.json"
    if checkpoint_manifest.exists():
        actual = json.loads(checkpoint_manifest.read_text(encoding="utf-8"))
        if actual != prepared_manifest:
            parser.error("P20U checkpoint run manifest is incompatible")
    else:
        write_json_atomic(checkpoint_manifest, prepared_manifest)

    runs, failures = execute_all(
        entries=entries,
        draws=draws,
        checkpoint_dir=checkpoint_dir,
        source_head=source_head,
        dataset_digest=quality["canonical_dataset_sha256"],
        database_digest=database_before,
        runner_source_sha256=runner_source_sha256,
        timeout_seconds=args.timeout_seconds,
        resume=not args.no_resume,
    )
    if failures or len(runs) != len(entries):
        print(
            json.dumps(
                {
                    "status": "PARTIALLY_COMPLETED_RESOURCE_BOUND",
                    "completed": len(runs),
                    "failures": failures,
                    "checkpoint_dir": str(checkpoint_dir),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=os.sys.stderr,
        )
        return 4

    resumed_runs, resumed_failures = execute_all(
        entries=entries,
        draws=draws,
        checkpoint_dir=checkpoint_dir,
        source_head=source_head,
        dataset_digest=quality["canonical_dataset_sha256"],
        database_digest=database_before,
        runner_source_sha256=runner_source_sha256,
        timeout_seconds=args.timeout_seconds,
        resume=True,
    )
    checkpoint_reproduction_pass = (
        not resumed_failures
        and stable_run_records(runs) == stable_run_records(resumed_runs)
        and all(bool(row["checkpoint_reused"]) for row in resumed_runs)
    )
    if not checkpoint_reproduction_pass:
        print("checkpoint reproduction failed", file=os.sys.stderr)
        return 5

    detail_validations = validate_details_parallel(
        runs, entries, source_head, args.validation_workers
    )
    if any(not row["all_pass"] for row in detail_validations):
        print(json.dumps(detail_validations, sort_keys=True), file=os.sys.stderr)
        return 6
    aggregate = aggregate_metrics(
        entries=entries,
        runs=runs,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    recompute = independent_aggregate_recompute(
        runs, aggregate["metrics"], aggregate["marginals"]
    )
    parity_rows, parity_summary = build_p20t_parity(
        metrics=aggregate["metrics"],
        random_rows=aggregate["random"],
        runs=runs,
        detail_validations=detail_validations,
        entries=entries,
    )
    nested = nesting_rows(detail_validations, entries)
    if not recompute["all_pass"] or not parity_summary["all_pass"]:
        print(
            json.dumps(
                {"recompute": recompute, "parity": parity_summary}, sort_keys=True
            ),
            file=os.sys.stderr,
        )
        return 7

    database_after = sha256_file(database)
    sidecars_after = sidecar_inventory(database)
    canonical_status_after = p20c.normalized_git_status_sha256(canonical_repo)
    canonical_branch_after = git_value(canonical_repo, "branch", "--show-current")
    canonical_head_after = git_value(canonical_repo, "rev-parse", "HEAD")
    unrelated_after = normalized_unrelated_worktree_sha256(canonical_repo, reusable)
    p20t_tree_after = combined_tree_digest(P20T_DIR)
    source_after = sha256_file(Path(__file__))
    invariance = {
        "database_unchanged": database_before == database_after,
        "database_sidecars_unchanged": sidecars_before == sidecars_after,
        "canonical_status_unchanged": canonical_status_before == canonical_status_after,
        "canonical_branch_unchanged": canonical_branch_before == canonical_branch_after,
        "canonical_head_unchanged": canonical_head_before == canonical_head_after,
        "unrelated_worktrees_unchanged": unrelated_before == unrelated_after,
        "p20t_tree_unchanged": p20t_tree_before == p20t_tree_after,
        "source_unchanged_after_reproduction": runner_source_sha256 == source_after,
    }
    if not all(invariance.values()):
        print(json.dumps(invariance, sort_keys=True), file=os.sys.stderr)
        return 8

    universe_rows = universe_output_rows(entries)
    efficiency = ticket_efficiency_rows(aggregate["metrics"], aggregate["marginals"])
    multiplicity = multiplicity_rows(aggregate["metrics"])
    ticket_configuration = {
        "ticket_counts": list(TICKET_COUNTS),
        "accepted_ticket_counts_exact": True,
        "portfolio_contract": PORTFOLIO_ORDERING_CONTRACT,
        "prefixes": {
            "10": "ordered_portfolio_20[0:10]",
            "15": "ordered_portfolio_20[0:15]",
            "20": "ordered_portfolio_20[0:20]",
        },
        "constructor_version": CONSTRUCTOR_IDENTIFIER,
        "portfolio_hash_scheme": PORTFOLIO_HASH_SCHEME,
        "random_replicates": RANDOM_REPLICATES,
        "random_portfolio_contract": PORTFOLIO_ORDERING_CONTRACT,
        "common_window_draws": EXPECTED_COMMON_DRAWS,
        "confirmatory_family_definition": CONFIRMATORY_FAMILY_DEFINITION,
        "confirmatory_family_size": EXPECTED_COMPLETED * len(TICKET_COUNTS),
    }
    count_specific_strategy_portfolios = sum(
        int(row["complete_portfolios"]) for row in aggregate["metrics"]
    )
    count_specific_random_portfolios = sum(
        int(row["complete_portfolios"]) for row in aggregate["random"]
    )
    ticket_evaluations = sum(
        int(row["complete_portfolios"]) * int(row["ticket_count"])
        for row in aggregate["metrics"]
    ) + sum(
        int(row["complete_portfolios"]) * int(row["ticket_count"])
        for row in aggregate["random"]
    )
    validation = {
        "task": TASK_ID,
        "status": "PASS",
        "checks": {
            "strategy_universe": {
                "pass": all(universe["checks"].values()),
                "details": universe["checks"],
            },
            "data_quality": {"pass": quality_pass(quality), "details": quality},
            "preflight_and_leakage": {
                "pass": len(preflight) == EXPECTED_COMPLETED
                and all(row["preflight_status"] == "PASS" for row in preflight),
                "details": preflight,
            },
            "execution_complete": {
                "pass": not failures and len(runs) == EXPECTED_COMPLETED + 1,
                "details": {"runs": len(runs), "failures": failures},
            },
            "nested_prefixes": {
                "pass": all(row["status"] == "PASS" for row in nested),
                "details": {
                    "groups": len(nested),
                    "failures": sum(row["status"] != "PASS" for row in nested),
                },
            },
            "detail_recomputation": {
                "pass": all(row["all_pass"] for row in detail_validations),
                "details": detail_validations,
            },
            "aggregate_recomputation": {
                "pass": recompute["all_pass"],
                "details": recompute,
            },
            "p20t_20_ticket_parity": {
                "pass": parity_summary["all_pass"],
                "details": parity_summary,
            },
            "checkpoint_byte_reproduction": {
                "pass": checkpoint_reproduction_pass,
                "details": {
                    "primary_runs": len(runs),
                    "resumed_runs": len(resumed_runs),
                },
            },
            "canonical_and_source_invariance": {
                "pass": all(invariance.values()),
                "details": invariance,
            },
            "tests": {"pass": int(tests["failed"]) == 0, "details": tests},
        },
        "tests": tests,
    }
    report = generate_final_report(
        metrics=aggregate["metrics"],
        random_rows=aggregate["random"],
        marginals=aggregate["marginals"],
        parity=parity_summary,
        nesting=nested,
        verification=validation,
    )
    adjusted_counts = {
        str(count): sum(
            bool(row["credible_advantage_adjusted"])
            for row in aggregate["metrics"]
            if int(row["ticket_count"]) == count
        )
        for count in TICKET_COUNTS
    }
    unadjusted_counts = {
        str(count): sum(
            bool(row["credible_advantage_unadjusted"])
            for row in aggregate["metrics"]
            if int(row["ticket_count"]) == count
        )
        for count in TICKET_COUNTS
    }
    manifest = {
        **prepared_manifest,
        "status": "COMPLETED",
        "runner_version": RUNNER_VERSION,
        "runner_source_sha256": runner_source_sha256,
        "source_head": source_head,
        "source_unchanged_after_reproduction": invariance[
            "source_unchanged_after_reproduction"
        ],
        "data": {
            "historical_source": "draws_big_lotto_canonical_main",
            "historical_draws": len(draws),
            "common_window_draws": EXPECTED_COMMON_DRAWS,
            "database_path": str(database),
            "database_sha256_before": database_before,
            "database_sha256_after": database_after,
            "dataset_sha256": quality["canonical_dataset_sha256"],
            "canonical_db_read": True,
            "canonical_db_written": False,
            "sidecars_before": sidecars_before,
            "sidecars_after": sidecars_after,
            "quality": quality,
        },
        "execution": {
            "ticket_counts": list(TICKET_COUNTS),
            "random_replicates": RANDOM_REPLICATES,
            "strategy_runs": stable_run_records(runs),
            "checkpoint_primary_reused": sum(
                bool(row["checkpoint_reused"]) for row in runs
            ),
            "checkpoint_resume_reused": sum(
                bool(row["checkpoint_reused"]) for row in resumed_runs
            ),
            "checkpoint_byte_reproduction": checkpoint_reproduction_pass,
            "count_specific_strategy_portfolios": count_specific_strategy_portfolios,
            "count_specific_random_portfolios": count_specific_random_portfolios,
            "ticket_evaluations": ticket_evaluations,
            "detail_files_retained": False,
        },
        "parity": parity_summary,
        "results": {
            "credible_advantages_unadjusted": unadjusted_counts,
            "credible_advantages_adjusted": adjusted_counts,
            "overall_conclusion_changed": any(adjusted_counts.values()),
        },
        "verification": {
            "tests": tests,
            "detail_recomputation": True,
            "aggregate_recomputation": True,
            "artifact_hashes": "PASS",
            "byte_reproduction": "PASS",
            **invariance,
        },
        "guards": {
            "canonical_repo_touched": False,
            "canonical_db_read": True,
            "canonical_db_written": False,
            "dependencies_installed": False,
            "live_external_services_called": False,
            "predecessor_artifacts_modified": False,
            "deployment_performed": False,
        },
    }
    payload = {
        "universe": universe_rows,
        "ticket_configuration": ticket_configuration,
        "nesting": nested,
        "parity_rows": parity_rows,
        "metrics": aggregate["metrics"],
        "paired": aggregate["paired"],
        "random": aggregate["random"],
        "marginals": aggregate["marginals"],
        "efficiency": efficiency,
        "multiplicity": multiplicity,
        "validation": validation,
        "manifest": manifest,
        "report": report,
    }

    with (
        tempfile.TemporaryDirectory(prefix="p20u-artifacts-a-") as first_root,
        tempfile.TemporaryDirectory(prefix="p20u-artifacts-b-") as second_root,
    ):
        first_stage = Path(first_root) / "bundle"
        second_stage = Path(second_root) / "bundle"
        first_tree = build_bundle(first_stage, payload)
        second_tree = build_bundle(second_stage, payload)
        if first_tree != second_tree:
            print(
                json.dumps(
                    {"first_tree": first_tree, "second_tree": second_tree},
                    sort_keys=True,
                ),
                file=os.sys.stderr,
            )
            return 9
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(first_stage, output_dir)

    if args.cleanup_checkpoints_on_success:
        cleanup_checkpoint_directory(checkpoint_dir)
    print(
        json.dumps(
            {
                "status": "COMPLETED",
                "source_head": source_head,
                "output_dir": str(output_dir),
                "artifact_tree_sha256": sha256_bytes(
                    canonical_json_bytes(artifact_tree(output_dir))
                ),
                "strategies": EXPECTED_COMPLETED,
                "ticket_counts": list(TICKET_COUNTS),
                "p20t_parity": "PASS",
                "byte_reproduction": "PASS",
                "checkpoint_cleanup": args.cleanup_checkpoints_on_success,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
