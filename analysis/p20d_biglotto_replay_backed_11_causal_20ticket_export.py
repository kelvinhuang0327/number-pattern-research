"""P20D — BIG_LOTTO replay-backed 11-strategy causal 20-ticket export.

Reads the 11 native BIG_LOTTO strategies' historical rows from
``strategy_prediction_replays`` (read-only; native-ticket authority) and
exports three separate evidence layers per the adopted R2 export contract:

1. Census — every raw DB row, in native DB order, duplicates included.
2. Portfolios — one deterministic 20-ticket canonical portfolio per
   resolvable (strategy_id, target_draw) group, built by the existing
   ``strategy_preserving_20_ticket/v1`` constructor from cutoff-only signal.
3. Outcomes — hit-count scoring against the target draw's actual numbers,
   computed strictly after portfolio finalization; outcomes are never passed
   into the constructor.

A group is "closed" (no portfolio, no outcome, excluded from scoring
eligibility, but retained in the census) when its target or cutoff draw does
not resolve against the canonical ``draws_big_lotto_canonical_main`` view, or
when the stored cutoff is not causally before the target. This module does
not generate, execute, or promote any strategy and does not write to the DB.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.strategy_preserving_20_ticket import (  # noqa: E402
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
)

TASK_ID = "P20D_BIGLOTTO_REPLAY_BACKED_11_CAUSAL_20TICKET_EXPORT"
LOTTERY_TYPE = "BIG_LOTTO"
DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# The exact 11 native BIG_LOTTO strategy IDs adopted for this export, fixed by
# direct census of the canonical DB (11 distinct strategy_id values under
# lottery_type='BIG_LOTTO', summing to the 24,140-row expected census).
EXPECTED_STRATEGY_IDS: tuple[str, ...] = (
    "bet2_fourier_expansion_biglotto",
    "biglotto_deviation_2bet",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_ts3_markov_4bet_w30",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "ts3_regime_3bet",
)
EXPECTED_CENSUS_ROW_COUNT = 24140

# Decision 5: no replicate axis exists in this schema, so every group is
# treated as the single legacy sequence.
LEGACY_DB_SINGLE_SEQUENCE_SENTINEL = 0

# Decision 6/7 closure reasons for a group that gets no portfolio/outcome.
SOURCE_DRAW_REFERENCE_UNAVAILABLE = "SOURCE_DRAW_REFERENCE_UNAVAILABLE"
NONCAUSAL_HISTORY_CUTOFF = "NONCAUSAL_HISTORY_CUTOFF"

RAW_ROW_COLUMNS = (
    "id",
    "target_draw",
    "target_date",
    "strategy_id",
    "strategy_name",
    "strategy_version",
    "history_cutoff_draw",
    "replay_status",
    "reject_reason",
    "predicted_numbers",
    "predicted_special",
    "actual_numbers",
    "actual_special",
    "hit_numbers",
    "hit_count",
    "special_hit",
    "replay_run_id",
    "generated_at",
)

# Provenance-only identity kept separate from the execution/replay version
# (decision 2/3): the registry's placeholder version for pre-execution
# strategy identity, distinct from each row's own strategy_version.
REGISTRY_PROVENANCE_VERSION = "v0.0"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_deterministic_gzip(path: Path, payload: bytes) -> None:
    """Write gzip bytes with a zeroed mtime so repeat runs are byte-identical."""

    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(payload)


def database_identity(database: Path) -> dict[str, Any]:
    stat = database.stat()
    return {
        "path": str(database),
        "sha256": sha256_file(database),
        "size": stat.st_size,
        "inode": stat.st_ino,
    }


def open_database_readonly(database: Path) -> sqlite3.Connection:
    """Open an existing SQLite file without creating journals or new files."""

    database = database.resolve()
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    uri = f"file:{database}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def bet_index_column_present(connection: sqlite3.Connection) -> bool:
    columns = [
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(strategy_prediction_replays)"
        ).fetchall()
    ]
    return "bet_index" in columns


def canonical_view_present(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='view' "
        "AND name='draws_big_lotto_canonical_main'"
    ).fetchone()
    return row is not None


@dataclass(frozen=True)
class RawTicketRow:
    id: int
    target_draw: str
    target_date: str | None
    strategy_id: str
    strategy_name: str
    strategy_version: str
    history_cutoff_draw: str | None
    replay_status: str
    reject_reason: str | None
    predicted_numbers: list[int]
    predicted_special: int | None
    actual_numbers: list[int] | None
    actual_special: int | None
    hit_numbers: list[int] | None
    hit_count: int | None
    special_hit: int | None
    replay_run_id: str | None
    generated_at: str | None
    bet_index: int
    bet_index_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_draw": self.target_draw,
            "target_date": self.target_date,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "history_cutoff_draw": self.history_cutoff_draw,
            "replay_status": self.replay_status,
            "reject_reason": self.reject_reason,
            "predicted_numbers": self.predicted_numbers,
            "predicted_special": self.predicted_special,
            "actual_numbers": self.actual_numbers,
            "actual_special": self.actual_special,
            "hit_numbers": self.hit_numbers,
            "hit_count": self.hit_count,
            "special_hit": self.special_hit,
            "replay_run_id": self.replay_run_id,
            "generated_at": self.generated_at,
            "bet_index": self.bet_index,
            "bet_index_source": self.bet_index_source,
        }


def _parse_numbers(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    value = json.loads(raw)
    return [int(number) for number in value]


def load_raw_rows(
    connection: sqlite3.Connection, strategy_ids: Sequence[str]
) -> list[RawTicketRow]:
    """Load every BIG_LOTTO row for the given strategies in native DB order."""

    has_bet_index = bet_index_column_present(connection)
    select_columns: list[str] = list(RAW_ROW_COLUMNS)
    if has_bet_index:
        select_columns.append("bet_index")
    placeholders = ",".join("?" for _ in strategy_ids)
    query = (
        f"SELECT {', '.join(select_columns)} FROM strategy_prediction_replays "
        f"WHERE lottery_type=? AND strategy_id IN ({placeholders}) "
        "ORDER BY strategy_id, target_draw, id"
    )
    cursor = connection.execute(query, (LOTTERY_TYPE, *strategy_ids))
    column_names = [description[0] for description in cursor.description]

    rows: list[RawTicketRow] = []
    group_counters: dict[tuple[str, str], int] = {}
    for raw_row in cursor.fetchall():
        record = dict(zip(column_names, raw_row))
        group_key = (record["strategy_id"], record["target_draw"])
        if has_bet_index and record.get("bet_index") is not None:
            bet_index = int(record["bet_index"])
            bet_index_source = "stored_column"
        else:
            bet_index = group_counters.get(group_key, 0)
            bet_index_source = "derived_native_order"
        group_counters[group_key] = bet_index + 1

        rows.append(
            RawTicketRow(
                id=int(record["id"]),
                target_draw=str(record["target_draw"]),
                target_date=record["target_date"],
                strategy_id=str(record["strategy_id"]),
                strategy_name=str(record["strategy_name"]),
                strategy_version=str(record["strategy_version"]),
                history_cutoff_draw=record["history_cutoff_draw"],
                replay_status=str(record["replay_status"]),
                reject_reason=record["reject_reason"],
                predicted_numbers=_parse_numbers(record["predicted_numbers"]) or [],
                predicted_special=record["predicted_special"],
                actual_numbers=_parse_numbers(record["actual_numbers"]),
                actual_special=record["actual_special"],
                hit_numbers=_parse_numbers(record["hit_numbers"]),
                hit_count=record["hit_count"],
                special_hit=record["special_hit"],
                replay_run_id=(
                    str(record["replay_run_id"])
                    if record["replay_run_id"] is not None
                    else None
                ),
                generated_at=record["generated_at"],
                bet_index=bet_index,
                bet_index_source=bet_index_source,
            )
        )
    return rows


def load_canonical_draws(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Map every canonical BIG_LOTTO draw id to its recorded outcome."""

    rows = connection.execute(
        "SELECT draw, date, numbers, special FROM draws_big_lotto_canonical_main"
    ).fetchall()
    canonical: dict[str, dict[str, Any]] = {}
    for draw, date, numbers_raw, special in rows:
        canonical[str(draw)] = {
            "draw": str(draw),
            "date": date,
            "numbers": sorted(int(number) for number in json.loads(numbers_raw)),
            "special": int(special),
        }
    return canonical


def group_raw_rows(
    raw_rows: Iterable[RawTicketRow],
) -> dict[tuple[str, str], list[RawTicketRow]]:
    groups: dict[tuple[str, str], list[RawTicketRow]] = {}
    for row in raw_rows:
        key = (row.strategy_id, row.target_draw)
        groups.setdefault(key, []).append(row)
    return groups


def _is_causal(history_cutoff_draw: str, target_draw: str) -> bool:
    if history_cutoff_draw.isdecimal() and target_draw.isdecimal():
        return int(history_cutoff_draw) < int(target_draw)
    return history_cutoff_draw != target_draw


@dataclass(frozen=True)
class ClosedGroup:
    strategy_id: str
    target_draw: str
    history_cutoff_draw: str | None
    closure_reason: str
    raw_row_ids: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "target_draw": self.target_draw,
            "history_cutoff_draw": self.history_cutoff_draw,
            "closure_reason": self.closure_reason,
            "raw_row_ids": list(self.raw_row_ids),
        }


@dataclass(frozen=True)
class PortfolioGroup:
    strategy_id: str
    strategy_name: str
    strategy_version: str
    target_draw: str
    history_cutoff_draw: str
    replicate_id: int
    replicate_observed: bool
    tickets: tuple[tuple[int, ...], ...]
    metadata: dict[str, Any]
    raw_row_ids: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "registry_provenance_version": REGISTRY_PROVENANCE_VERSION,
            "target_draw": self.target_draw,
            "history_cutoff_draw": self.history_cutoff_draw,
            "replicate_id": self.replicate_id,
            "replicate_observed": self.replicate_observed,
            "tickets": [list(ticket) for ticket in self.tickets],
            "metadata": self.metadata,
            "raw_row_ids": list(self.raw_row_ids),
        }


def classify_group(
    strategy_id: str,
    target_draw: str,
    rows: Sequence[RawTicketRow],
    canonical_draws: Mapping[str, dict[str, Any]],
) -> ClosedGroup | PortfolioGroup:
    history_cutoff_draw = rows[0].history_cutoff_draw
    raw_row_ids = tuple(row.id for row in rows)

    if history_cutoff_draw is None or (
        target_draw not in canonical_draws or history_cutoff_draw not in canonical_draws
    ):
        return ClosedGroup(
            strategy_id=strategy_id,
            target_draw=target_draw,
            history_cutoff_draw=history_cutoff_draw,
            closure_reason=SOURCE_DRAW_REFERENCE_UNAVAILABLE,
            raw_row_ids=raw_row_ids,
        )

    if not _is_causal(history_cutoff_draw, target_draw):
        return ClosedGroup(
            strategy_id=strategy_id,
            target_draw=target_draw,
            history_cutoff_draw=history_cutoff_draw,
            closure_reason=NONCAUSAL_HISTORY_CUTOFF,
            raw_row_ids=raw_row_ids,
        )

    result = construct_strategy_preserving_20_ticket(
        ConstructorRequest(
            strategy_id=strategy_id,
            draw_id=target_draw,
            replicate_id=LEGACY_DB_SINGLE_SEQUENCE_SENTINEL,
            raw_tickets=[row.predicted_numbers for row in rows],
            historical_cutoff_identity=history_cutoff_draw,
            user_seed=TASK_ID,
        )
    )
    if not isinstance(result, ConstructorSuccess):
        return ClosedGroup(
            strategy_id=strategy_id,
            target_draw=target_draw,
            history_cutoff_draw=history_cutoff_draw,
            closure_reason=f"CONSTRUCTOR_FAILURE:{result.reason.value}",
            raw_row_ids=raw_row_ids,
        )

    return PortfolioGroup(
        strategy_id=strategy_id,
        strategy_name=rows[0].strategy_name,
        strategy_version=rows[0].strategy_version,
        target_draw=target_draw,
        history_cutoff_draw=history_cutoff_draw,
        replicate_id=LEGACY_DB_SINGLE_SEQUENCE_SENTINEL,
        replicate_observed=False,
        tickets=result.tickets,
        metadata=result.metadata.to_dict(),
        raw_row_ids=raw_row_ids,
    )


def build_groups(
    raw_rows: Sequence[RawTicketRow], canonical_draws: Mapping[str, dict[str, Any]]
) -> tuple[list[PortfolioGroup], list[ClosedGroup]]:
    portfolios: list[PortfolioGroup] = []
    closed: list[ClosedGroup] = []
    for (strategy_id, target_draw), rows in group_raw_rows(raw_rows).items():
        outcome = classify_group(strategy_id, target_draw, rows, canonical_draws)
        if isinstance(outcome, PortfolioGroup):
            portfolios.append(outcome)
        else:
            closed.append(outcome)
    portfolios.sort(key=lambda item: (item.strategy_id, item.target_draw))
    closed.sort(key=lambda item: (item.strategy_id, item.target_draw))
    return portfolios, closed


def evaluate_ticket_hits(ticket: Sequence[int], actual_numbers: Sequence[int]) -> int:
    return len(set(ticket) & set(actual_numbers))


def build_outcomes(
    portfolios: Sequence[PortfolioGroup], canonical_draws: Mapping[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Score already-finalized portfolios against recorded target outcomes.

    Outcomes are computed strictly after portfolio finalization and are never
    fed back into ticket construction (decision 8: no target leakage).
    """

    outcomes: list[dict[str, Any]] = []
    for portfolio in portfolios:
        target = canonical_draws[portfolio.target_draw]
        actual_numbers = target["numbers"]
        actual_special = target["special"]
        hit_counts = [
            evaluate_ticket_hits(ticket, actual_numbers) for ticket in portfolio.tickets
        ]
        outcomes.append(
            {
                "strategy_id": portfolio.strategy_id,
                "target_draw": portfolio.target_draw,
                "actual_numbers": actual_numbers,
                "actual_special": actual_special,
                "ticket_hit_counts": hit_counts,
                "max_hit_count": max(hit_counts, default=0),
                "m4plus": int(max(hit_counts, default=0) >= 4),
            }
        )
    outcomes.sort(key=lambda item: (item["strategy_id"], item["target_draw"]))
    return outcomes


def build_census(raw_rows: Sequence[RawTicketRow]) -> list[dict[str, Any]]:
    return [row.to_dict() for row in raw_rows]


@dataclass(frozen=True)
class ExportResult:
    census: list[dict[str, Any]]
    portfolios: list[dict[str, Any]]
    closed_rows: list[dict[str, Any]]
    outcomes: list[dict[str, Any]]
    manifest: dict[str, Any]


def run_export(
    database: Path, strategy_ids: Sequence[str] = EXPECTED_STRATEGY_IDS
) -> ExportResult:
    identity_before = database_identity(database)
    connection = open_database_readonly(database)
    try:
        raw_rows = load_raw_rows(connection, strategy_ids)
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    identity_after = database_identity(database)
    if identity_before != identity_after:
        raise RuntimeError("canonical DB identity changed during read-only export")

    observed_strategy_ids = sorted({row.strategy_id for row in raw_rows})
    portfolios, closed = build_groups(raw_rows, canonical_draws)
    outcomes = build_outcomes(portfolios, canonical_draws)
    census = build_census(raw_rows)
    portfolio_dicts = [group.to_dict() for group in portfolios]
    closed_dicts = [group.to_dict() for group in closed]

    manifest = {
        "task_id": TASK_ID,
        "lottery_type": LOTTERY_TYPE,
        "expected_strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "observed_strategy_ids": observed_strategy_ids,
        "strategy_ids_match_expected": observed_strategy_ids
        == sorted(EXPECTED_STRATEGY_IDS),
        "expected_census_row_count": EXPECTED_CENSUS_ROW_COUNT,
        "observed_census_row_count": len(census),
        "census_row_count_matches_expected": len(census) == EXPECTED_CENSUS_ROW_COUNT,
        "portfolio_group_count": len(portfolios),
        "closed_group_count": len(closed),
        "total_group_count": len(portfolios) + len(closed),
        "database_identity_before": identity_before,
        "database_identity_after": identity_after,
        "census_sha256": sha256_bytes(canonical_json_bytes(census)),
        "portfolios_sha256": sha256_bytes(canonical_json_bytes(portfolio_dicts)),
        "closed_rows_sha256": sha256_bytes(canonical_json_bytes(closed_dicts)),
        "outcomes_sha256": sha256_bytes(canonical_json_bytes(outcomes)),
    }
    return ExportResult(
        census=census,
        portfolios=portfolio_dicts,
        closed_rows=closed_dicts,
        outcomes=outcomes,
        manifest=manifest,
    )


def write_export(result: ExportResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "census": output_dir / "census.json.gz",
        "portfolios": output_dir / "portfolios.json.gz",
        "closed_rows": output_dir / "closed_rows.json.gz",
        "outcomes": output_dir / "outcomes.json.gz",
        "manifest": output_dir / "manifest.json",
    }
    write_deterministic_gzip(paths["census"], canonical_json_bytes(result.census))
    write_deterministic_gzip(
        paths["portfolios"], canonical_json_bytes(result.portfolios)
    )
    write_deterministic_gzip(
        paths["closed_rows"], canonical_json_bytes(result.closed_rows)
    )
    write_deterministic_gzip(paths["outcomes"], canonical_json_bytes(result.outcomes))
    paths["manifest"].write_bytes(canonical_json_bytes(result.manifest))
    return {name: str(path) for name, path in paths.items()}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    result = run_export(args.db)
    paths = write_export(result, args.output_dir)
    print(json.dumps({"manifest": result.manifest, "paths": paths}, indent=2))
    return 0 if result.manifest["strategy_ids_match_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
