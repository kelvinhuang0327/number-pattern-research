#!/usr/bin/env python3
"""P294A-R1 locked historical-split engine; standard library only."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path
import sqlite3
import sys


EVIDENCE_ROOT = Path(
    "/Users/kelvin/LotteryResearchEvidence/"
    "P294A-r1-big649-locked-split-trend-family-20260629/attempt_1"
)
DB_PATH = Path(
    "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
)
DB_URI = (
    "file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/"
    "lottery_v2.db?mode=ro"
)
EXPECTED_DB_SHA256 = (
    "41e9c37948650c1d881502f7d204a2656c16e61e8e7b96058d23da76dd666cab"
)
VIEW = "draws_big_lotto_canonical_main"
ORDER_SQL = "CAST(draw AS INTEGER) ASC, id ASC"
EXPECTED_ROWS = 2120
DISCOVERY_END = 1600
DISCOVERY_TARGET_START = 750
LOCKBOX_TARGET_START = 1600
LOCKBOX_TARGET_END = 2119
CANDIDATES = (
    "trend_hot_50_300",
    "trend_cold_50_300",
    "trend_hot_300_750",
    "trend_cold_300_750",
)
BLOCKS = (
    (1, 1600, 1729),
    (2, 1730, 1859),
    (3, 1860, 1989),
    (4, 1990, 2119),
)
DECIMAL_PRECISION = 100
getcontext().prec = DECIMAL_PRECISION


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def durable_write(path: Path, data: bytes) -> None:
    if path.parent.resolve() not in {
        (EVIDENCE_ROOT / "run1").resolve(),
        (EVIDENCE_ROOT / "run2").resolve(),
    }:
        raise RuntimeError(f"output outside authorized run directories: {path}")
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def write_text(path: Path, text: str) -> None:
    durable_write(path, text.encode("utf-8"))


def write_json(path: Path, value: object) -> None:
    write_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def csv_text(fieldnames: list[str], rows: list[dict[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def event(run_dir: Path, name: str) -> None:
    path = run_dir / "DB_ACCESS_EVENTS.jsonl"
    record = {
        "event": name,
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    mode = "ab" if path.exists() else "xb"
    with path.open(mode) as handle:
        handle.write(
            (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
                "utf-8"
            )
        )
        handle.flush()
        os.fsync(handle.fileno())


def connect_read_only(run_dir: Path, phase: str) -> sqlite3.Connection:
    event(run_dir, f"before_{phase}_sqlite_connect")
    connection = sqlite3.connect(DB_URI, uri=True)
    connection.execute("PRAGMA query_only=ON")
    value = connection.execute("PRAGMA query_only").fetchone()[0]
    if value != 1:
        connection.close()
        raise RuntimeError(f"query_only verification failed in {phase}: {value!r}")
    event(run_dir, f"after_{phase}_query_only_verified")
    return connection


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def parse_main_numbers(raw: object, index: int) -> tuple[int, ...]:
    if not isinstance(raw, str):
        raise RuntimeError(f"numbers is not text at ordered index {index}")
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != 6:
        raise RuntimeError(f"numbers is not a six-element array at index {index}")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise RuntimeError(f"numbers contains non-integers at index {index}")
    if len(set(value)) != 6 or any(item < 1 or item > 49 for item in value):
        raise RuntimeError(f"numbers violates unique 1..49 contract at index {index}")
    return tuple(sorted(value))


def inspect_schema_and_identity(
    connection: sqlite3.Connection,
) -> tuple[list[tuple[object, object, object]], str, list[str]]:
    view_row = connection.execute(
        "SELECT type, sql FROM sqlite_master WHERE name=?", (VIEW,)
    ).fetchone()
    if view_row is None or view_row[0] != "view":
        raise RuntimeError(f"required source view absent or wrong type: {view_row!r}")
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({VIEW})")]
    required = {"id", "draw", "numbers"}
    if not required.issubset(columns):
        raise RuntimeError(f"source columns missing: {sorted(required - set(columns))}")
    date_candidates = [name for name in ("date", "draw_date", "issue_date") if name in columns]
    if len(date_candidates) != 1:
        raise RuntimeError(f"expected exactly one date metadata column: {date_candidates!r}")
    date_column = date_candidates[0]
    count = connection.execute(f"SELECT COUNT(*) FROM {VIEW}").fetchone()[0]
    if count != EXPECTED_ROWS:
        raise RuntimeError(f"source row count mismatch: {count}")
    identity_sql = (
        f"SELECT id, draw, {quote_identifier(date_column)} FROM {VIEW} "
        f"ORDER BY {ORDER_SQL}"
    )
    rows = connection.execute(identity_sql).fetchall()
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError("identity query length mismatch")
    identities = [(row[0], str(row[1])) for row in rows]
    if len(set(identities)) != EXPECTED_ROWS:
        raise RuntimeError("duplicate (id, draw) identity")
    draws = [str(row[1]) for row in rows]
    if len(set(draws)) != EXPECTED_ROWS:
        raise RuntimeError("duplicate draw identity")
    try:
        draw_ints = [int(draw) for draw in draws]
    except ValueError as exc:
        raise RuntimeError("non-integer draw identity") from exc
    if draw_ints[0] != 96000001 or draw_ints[-1] != 115000065:
        raise RuntimeError(
            f"draw endpoint mismatch: {draw_ints[0]}..{draw_ints[-1]}"
        )
    if any(draw_ints[i] > draw_ints[i + 1] for i in range(len(draw_ints) - 1)):
        raise RuntimeError("draw ordering is not ascending")
    return rows, date_column, columns


def read_discovery_numbers(
    connection: sqlite3.Connection,
    identities: list[tuple[object, object, object]],
) -> list[tuple[int, ...]]:
    sql = (
        f"SELECT id, draw, numbers FROM {VIEW} ORDER BY {ORDER_SQL} "
        f"LIMIT {DISCOVERY_END}"
    )
    rows = connection.execute(sql).fetchall()
    if len(rows) != DISCOVERY_END:
        raise RuntimeError(f"discovery number row count mismatch: {len(rows)}")
    parsed: list[tuple[int, ...]] = []
    for index, row in enumerate(rows):
        expected = (identities[index][0], str(identities[index][1]))
        actual = (row[0], str(row[1]))
        if actual != expected:
            raise RuntimeError(f"discovery identity mismatch at {index}")
        parsed.append(parse_main_numbers(row[2], index))
    return parsed


def window_counts(history: list[tuple[int, ...]], size: int) -> Counter[int]:
    if len(history) < size:
        raise RuntimeError(f"insufficient history for window {size}")
    counts: Counter[int] = Counter()
    for draw in history[-size:]:
        counts.update(draw)
    return counts


def make_ticket(candidate: str, history: list[tuple[int, ...]]) -> tuple[int, ...]:
    c50 = window_counts(history, 50)
    c300 = window_counts(history, 300)
    c750 = window_counts(history, 750) if "750" in candidate else None
    scores: dict[int, Fraction] = {}
    for number in range(1, 50):
        if candidate.endswith("50_300"):
            score = Fraction(c50[number], 50) - Fraction(c300[number], 300)
        elif candidate.endswith("300_750") and c750 is not None:
            score = Fraction(c300[number], 300) - Fraction(c750[number], 750)
        else:
            raise RuntimeError(f"unknown candidate: {candidate}")
        scores[number] = score
    if "_hot_" in candidate:
        ordered = sorted(range(1, 50), key=lambda number: (-scores[number], number))
    elif "_cold_" in candidate:
        ordered = sorted(range(1, 50), key=lambda number: (scores[number], number))
    else:
        raise RuntimeError(f"unknown temperature direction: {candidate}")
    ticket = tuple(sorted(ordered[:6]))
    if len(ticket) != 6 or len(set(ticket)) != 6:
        raise RuntimeError(f"invalid ticket for {candidate}: {ticket}")
    return ticket


def decimal_from_fraction(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def fixed(value: Decimal, places: int = 50) -> str:
    return format(value, f".{places}f")


def discovery_evaluation(
    numbers: list[tuple[int, ...]],
) -> tuple[list[dict[str, object]], str]:
    totals = {candidate: 0 for candidate in CANDIDATES}
    for target in range(DISCOVERY_TARGET_START, DISCOVERY_END):
        history = numbers[:target]
        actual = set(numbers[target])
        for candidate in CANDIDATES:
            ticket = make_ticket(candidate, history)
            totals[candidate] += len(set(ticket) & actual)
    null_mean = Fraction((DISCOVERY_END - DISCOVERY_TARGET_START) * 36, 49)
    best_total = max(totals.values())
    selected = next(
        candidate for candidate in CANDIDATES if totals[candidate] == best_total
    )
    rows: list[dict[str, object]] = []
    rank_order = sorted(CANDIDATES, key=lambda c: (-totals[c], CANDIDATES.index(c)))
    for candidate in CANDIDATES:
        excess = Fraction(totals[candidate], 1) - null_mean
        rows.append(
            {
                "candidate": candidate,
                "total_hits": totals[candidate],
                "null_mean": fixed(decimal_from_fraction(null_mean), 24),
                "excess": fixed(decimal_from_fraction(excess), 24),
                "selection_rank": rank_order.index(candidate) + 1,
                "selected": "true" if candidate == selected else "false",
            }
        )
    return rows, selected


def selection_record_text(rows: list[dict[str, object]], selected: str) -> str:
    maximum = max(int(row["total_hits"]) for row in rows)
    tied = [str(row["candidate"]) for row in rows if int(row["total_hits"]) == maximum]
    lines = [
        "# LOCKBOX SELECTION RECORD — P294A-R1",
        "",
        "lockbox_outcomes_accessed=false",
        "",
        "Discovery scope: targets 750..1599 only (n=850).",
        "Selection metric: greatest discovery excess = total_hits - 850 * 36/49.",
        "",
        "| Candidate | Total hits | Null mean | Excess |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['candidate']}` | {row['total_hits']} | "
            f"{row['null_mean']} | {row['excess']} |"
        )
    lines.extend(
        [
            "",
            f"Greatest discovery total: {maximum}.",
            "Candidates tied at greatest total, in frozen candidate order: "
            + ", ".join(f"`{candidate}`" for candidate in tied)
            + ".",
            "Frozen tie order: `trend_hot_50_300`, `trend_cold_50_300`, "
            "`trend_hot_300_750`, `trend_cold_300_750`.",
            f"Selected candidate: `{selected}`.",
            "Tie-break application: "
            + ("not needed; unique greatest total." if len(tied) == 1 else "needed; earliest tied candidate selected."),
            "",
            "This canonical record contains no volatile timestamp.",
        ]
    )
    return "\n".join(lines) + "\n"


def create_and_verify_selection_record(
    run_dir: Path, rows: list[dict[str, object]], selected: str
) -> str:
    record = selection_record_text(rows, selected).encode("utf-8")
    path = run_dir / "LOCKBOX_SELECTION_RECORD.md"
    durable_write(path, record)
    expected = sha256_bytes(record)
    observed = sha256_file(path)
    if observed != expected:
        raise RuntimeError("durable selection-record SHA-256 verification failed")
    write_text(
        run_dir / "LOCKBOX_SELECTION_RECORD.sha256",
        f"{observed}  LOCKBOX_SELECTION_RECORD.md\n",
    )
    return observed


def read_lockbox_numbers(
    connection: sqlite3.Connection,
    identities: list[tuple[object, object, object]],
    run_dir: Path,
) -> list[tuple[int, ...]]:
    event(run_dir, "before_lockbox_winning_number_query")
    sql = (
        f"SELECT id, draw, numbers FROM {VIEW} ORDER BY {ORDER_SQL} "
        f"LIMIT {EXPECTED_ROWS - LOCKBOX_TARGET_START} OFFSET {LOCKBOX_TARGET_START}"
    )
    rows = connection.execute(sql).fetchall()
    event(run_dir, "after_lockbox_winning_number_query")
    if len(rows) != EXPECTED_ROWS - LOCKBOX_TARGET_START:
        raise RuntimeError(f"lockbox number row count mismatch: {len(rows)}")
    parsed: list[tuple[int, ...]] = []
    for offset, row in enumerate(rows):
        index = LOCKBOX_TARGET_START + offset
        expected = (identities[index][0], str(identities[index][1]))
        actual = (row[0], str(row[1]))
        if actual != expected:
            raise RuntimeError(f"lockbox identity mismatch at {index}")
        parsed.append(parse_main_numbers(row[2], index))
    return parsed


def evaluate_selected_lockbox(
    selected: str,
    discovery_numbers: list[tuple[int, ...]],
    lockbox_numbers: list[tuple[int, ...]],
) -> tuple[int, list[dict[str, object]]]:
    history = list(discovery_numbers)
    total = 0
    block_totals = {block_id: 0 for block_id, _, _ in BLOCKS}
    for offset, actual_tuple in enumerate(lockbox_numbers):
        target = LOCKBOX_TARGET_START + offset
        ticket = make_ticket(selected, history)
        hits = len(set(ticket) & set(actual_tuple))
        total += hits
        for block_id, start, end in BLOCKS:
            if start <= target <= end:
                block_totals[block_id] += hits
                break
        else:
            raise RuntimeError(f"target not assigned to block: {target}")
        history.append(actual_tuple)
    if len(history) != EXPECTED_ROWS:
        raise RuntimeError("full validated outcome coverage mismatch")
    block_rows: list[dict[str, object]] = []
    for block_id, start, end in BLOCKS:
        target_count = end - start + 1
        mean = Fraction(target_count * 36, 49)
        observed = block_totals[block_id]
        excess = Fraction(observed, 1) - mean
        block_rows.append(
            {
                "block": block_id,
                "target_start": start,
                "target_end": end,
                "target_count": target_count,
                "observed_S": observed,
                "null_mean": fixed(decimal_from_fraction(mean), 24),
                "excess": fixed(decimal_from_fraction(excess), 24),
                "excess_nonnegative": "true" if excess >= 0 else "false",
            }
        )
    return total, block_rows


def exact_null(target_count: int, observed: int) -> dict[str, object]:
    denominator = math.comb(49, 6)
    pmf = [
        Decimal(math.comb(6, k) * math.comb(43, 6 - k)) / Decimal(denominator)
        for k in range(7)
    ]
    pmf_sum_error = abs(sum(pmf, Decimal(0)) - Decimal(1))
    if pmf_sum_error > Decimal("1e-40"):
        raise RuntimeError(f"per-target PMF normalization failed: {pmf_sum_error}")
    distribution = [Decimal(1)]
    for _ in range(target_count):
        next_distribution = [Decimal(0)] * (len(distribution) + 6)
        for current_hits, probability in enumerate(distribution):
            for k, pk in enumerate(pmf):
                next_distribution[current_hits + k] += probability * pk
        distribution = next_distribution
    convolution_sum_error = abs(sum(distribution, Decimal(0)) - Decimal(1))
    if convolution_sum_error > Decimal("1e-30"):
        raise RuntimeError(
            f"convolution normalization failed: {convolution_sum_error}"
        )
    computed_mean = sum(
        (Decimal(index) * probability for index, probability in enumerate(distribution)),
        Decimal(0),
    )
    computed_variance = sum(
        (
            (Decimal(index) - computed_mean) ** 2 * probability
            for index, probability in enumerate(distribution)
        ),
        Decimal(0),
    )
    per_mean = Decimal(36) / Decimal(49)
    analytic_mean = Decimal(target_count) * per_mean
    per_variance = (
        Decimal(6)
        * (Decimal(6) / Decimal(49))
        * (Decimal(43) / Decimal(49))
        * (Decimal(43) / Decimal(48))
    )
    analytic_variance = Decimal(target_count) * per_variance
    mean_error = abs(computed_mean - analytic_mean)
    variance_error = abs(computed_variance - analytic_variance)
    if mean_error > Decimal("1e-40"):
        raise RuntimeError(f"analytic/computed mean mismatch: {mean_error}")
    if variance_error > Decimal("1e-40"):
        raise RuntimeError(f"analytic/computed variance mismatch: {variance_error}")
    upper_tail = sum(distribution[observed:], Decimal(0))
    return {
        "decimal_precision": DECIMAL_PRECISION,
        "per_target_pmf": [fixed(value, 90) for value in pmf],
        "pmf_sum_error": format(pmf_sum_error, ".10E"),
        "convolution_sum_error": format(convolution_sum_error, ".10E"),
        "analytic_mean": fixed(analytic_mean, 50),
        "computed_mean": fixed(computed_mean, 50),
        "mean_error": format(mean_error, ".10E"),
        "analytic_variance": fixed(analytic_variance, 50),
        "computed_variance": fixed(computed_variance, 50),
        "variance_error": format(variance_error, ".10E"),
        "upper_tail_p": fixed(upper_tail, 80),
    }


def run(run_dir: Path) -> None:
    run_dir = run_dir.resolve()
    if run_dir not in {
        (EVIDENCE_ROOT / "run1").resolve(),
        (EVIDENCE_ROOT / "run2").resolve(),
    }:
        raise RuntimeError(f"unauthorized run directory: {run_dir}")
    if any(run_dir.iterdir()):
        raise RuntimeError(f"run directory is not empty: {run_dir}")
    if DB_PATH.resolve() != Path(
        "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
    ):
        raise RuntimeError("authorized DB realpath mismatch")
    if sha256_file(DB_PATH) != EXPECTED_DB_SHA256:
        raise RuntimeError("authorized DB SHA-256 mismatch before engine DB open")

    discovery_connection = connect_read_only(run_dir, "discovery")
    try:
        identities, date_column, columns = inspect_schema_and_identity(
            discovery_connection
        )
        discovery_numbers = read_discovery_numbers(discovery_connection, identities)
    finally:
        discovery_connection.close()
    discovery_rows, selected = discovery_evaluation(discovery_numbers)
    write_text(
        run_dir / "DISCOVERY_CANDIDATE_SUMMARY.csv",
        csv_text(
            [
                "candidate",
                "total_hits",
                "null_mean",
                "excess",
                "selection_rank",
                "selected",
            ],
            discovery_rows,
        ),
    )
    selection_sha = create_and_verify_selection_record(
        run_dir, discovery_rows, selected
    )
    write_text(
        run_dir / "LOCKBOX_ACCESS_GATE.md",
        "# Lockbox Access Gate\n\n"
        "- Discovery connection closed before lockbox access: PASS.\n"
        "- Durable deterministic selection record written and fsync-completed: PASS.\n"
        "- Selection record re-read and SHA-256 verified: PASS.\n"
        f"- Selection record SHA-256: `{selection_sha}`.\n"
        "- Selection record states `lockbox_outcomes_accessed=false`: PASS.\n"
        "- Lockbox phase uses a fresh `mode=ro`, `uri=True`, `query_only=1` connection: PASS.\n"
        "- Only the selected candidate is passed to lockbox evaluation: PASS.\n",
    )

    lockbox_connection = connect_read_only(run_dir, "lockbox")
    try:
        lockbox_numbers = read_lockbox_numbers(
            lockbox_connection, identities, run_dir
        )
    finally:
        lockbox_connection.close()
    observed, block_rows = evaluate_selected_lockbox(
        selected, discovery_numbers, lockbox_numbers
    )
    null = exact_null(len(lockbox_numbers), observed)
    null_mean_decimal = Decimal(str(null["analytic_mean"]))
    excess_decimal = Decimal(observed) - null_mean_decimal
    p_decimal = Decimal(str(null["upper_tail_p"]))
    nonnegative_blocks = sum(
        row["excess_nonnegative"] == "true" for row in block_rows
    )
    retention = (
        excess_decimal > 0 and p_decimal < Decimal("0.05") and nonnegative_blocks >= 3
    )
    classification = (
        "P294A_R1_LOCKED_SPLIT_TREND_FAMILY_COMPLETE_EXPLORATORY_RETENTION_ONLY"
        if retention
        else "P294A_R1_LOCKED_SPLIT_TREND_FAMILY_COMPLETE_NO_HOLDOUT_RETENTION"
    )

    result_rows = [
        {
            "selected_candidate": selected,
            "target_start": LOCKBOX_TARGET_START,
            "target_end": LOCKBOX_TARGET_END,
            "target_count": len(lockbox_numbers),
            "observed_S": observed,
            "null_mean": null["analytic_mean"],
            "excess": fixed(excess_decimal, 50),
            "exact_upper_tail_p": null["upper_tail_p"],
            "nonnegative_blocks": nonnegative_blocks,
            "retention": "PASS" if retention else "FAIL",
            "classification": classification,
        }
    ]
    write_text(
        run_dir / "LOCKBOX_RESULT_TABLE.csv",
        csv_text(list(result_rows[0].keys()), result_rows),
    )
    write_text(
        run_dir / "LOCKBOX_BLOCK_STABILITY.csv",
        csv_text(list(block_rows[0].keys()), block_rows),
    )
    write_text(
        run_dir / "LOCKBOX_EXACT_NULL_RESULTS.md",
        "# Lockbox Exact Null Results\n\n"
        f"- Selected candidate: `{selected}`.\n"
        f"- Lockbox targets: {LOCKBOX_TARGET_START}..{LOCKBOX_TARGET_END} (n={len(lockbox_numbers)}).\n"
        f"- Observed S: {observed}.\n"
        f"- Exact null mean: {null['analytic_mean']}.\n"
        f"- Excess: {fixed(excess_decimal, 50)}.\n"
        f"- Exact upper-tail p-value P(S_null >= observed S): {null['upper_tail_p']}.\n"
        f"- Nonnegative block excesses: {nonnegative_blocks}/4.\n"
        f"- Historical-lockbox exploratory retention: {'PASS' if retention else 'FAIL'}.\n"
        f"- Final classification: `{classification}`.\n\n"
        "No block p-values and no nonselected-candidate lockbox results were computed.\n",
    )
    write_text(
        run_dir / "NUMERICAL_VALIDATION.md",
        "# Numerical Validation\n\n"
        f"- Decimal precision: {null['decimal_precision']}.\n"
        f"- Per-target PMF normalization error: {null['pmf_sum_error']} (threshold 1E-40): PASS.\n"
        f"- Convolution normalization error: {null['convolution_sum_error']} (threshold 1E-30): PASS.\n"
        f"- Analytic/computed mean error: {null['mean_error']} (threshold 1E-40): PASS.\n"
        f"- Analytic/computed variance error: {null['variance_error']} (threshold 1E-40): PASS.\n"
        "- Exact Decimal PGF convolution: PASS.\n"
        "- Simulation, random seed, and normal approximation: NONE.\n",
    )
    source_validation = {
        "authorized_db_uri": DB_URI,
        "authorized_db_sha256_before_engine_open": EXPECTED_DB_SHA256,
        "date_metadata_column": date_column,
        "eligible_target_count": LOCKBOX_TARGET_END - DISCOVERY_TARGET_START + 1,
        "eligible_target_indices": [DISCOVERY_TARGET_START, LOCKBOX_TARGET_END],
        "first_draw": int(identities[0][1]),
        "full_main_arrays_validated_after_selection": len(discovery_numbers)
        + len(lockbox_numbers),
        "identity_rows_read_before_selection": len(identities),
        "last_draw": int(identities[-1][1]),
        "lockbox_main_arrays_read_before_selection": 0,
        "query_only_discovery": 1,
        "query_only_lockbox": 1,
        "source_columns": columns,
        "source_order": ORDER_SQL,
        "source_row_count": len(identities),
        "source_view": VIEW,
        "special_number_queried": False,
        "valid_main_array_count": len(discovery_numbers) + len(lockbox_numbers),
    }
    write_json(run_dir / "DB_SOURCE_REVALIDATION.json", source_validation)
    canonical_result = {
        "block_results": block_rows,
        "classification": classification,
        "discovery_results": discovery_rows,
        "exact_null": null,
        "lockbox_result": result_rows[0],
        "selected_candidate": selected,
        "selection_record_sha256": selection_sha,
    }
    write_json(run_dir / "CANONICAL_RESULT.json", canonical_result)
    deterministic_files = [
        "DISCOVERY_CANDIDATE_SUMMARY.csv",
        "LOCKBOX_SELECTION_RECORD.md",
        "LOCKBOX_SELECTION_RECORD.sha256",
        "LOCKBOX_ACCESS_GATE.md",
        "LOCKBOX_RESULT_TABLE.csv",
        "LOCKBOX_BLOCK_STABILITY.csv",
        "LOCKBOX_EXACT_NULL_RESULTS.md",
        "NUMERICAL_VALIDATION.md",
        "DB_SOURCE_REVALIDATION.json",
        "CANONICAL_RESULT.json",
    ]
    hashes = {name: sha256_file(run_dir / name) for name in deterministic_files}
    hashes["exact_p_value_serialization"] = str(null["upper_tail_p"])
    hashes["canonical_result_hash"] = hashes["CANONICAL_RESULT.json"]
    write_json(run_dir / "RUN_HASHES.json", hashes)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: p294a_r1_engine.py RUN_DIRECTORY")
    run(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

