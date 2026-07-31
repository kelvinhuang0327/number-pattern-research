"""Build a deterministic candidate-linked per-draw contract from read-only inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote


class SchemaError(ValueError):
    """Raised when the committed artifacts or read-only schema are insufficient."""


MAX_ROWS_PER_CANDIDATE = 50
REQUIRED_REPLAY_COLUMNS = (
    "id",
    "lottery_type",
    "target_draw",
    "target_date",
    "strategy_id",
    "strategy_name",
    "bet_index",
    "predicted_numbers",
    "predicted_special",
    "actual_numbers",
    "actual_special",
    "hit_count",
    "special_hit",
    "replay_status",
)
SQL_CATEGORIES = (
    "PRAGMA query_only=ON",
    "SELECT sqlite_master table inventory",
    "PRAGMA table_info schema inventory",
    "SELECT candidate linkage aggregates",
    "SELECT capped candidate contract rows",
)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{label} must be an object")
    return value


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sort_value(value: Any) -> tuple[int, Any]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, value)
    return (1, str(value))


def _source_metadata(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _decode(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaError(f"{label} is not valid UTF-8 JSON") from exc
    return _mapping(value, label)


def read_only_uri(db_path: str) -> str:
    """Return the only accepted connection form: a SQLite URI with mode=ro."""
    if not db_path or db_path.startswith("file:") or "?" in db_path:
        raise ValueError("--db-path must be a filesystem path; the read-only URI is constructed internally")
    raw_path = Path(db_path).expanduser()
    if not raw_path.is_absolute() or raw_path.suffix != ".db":
        raise ValueError("--db-path must be an absolute .db file")
    path = raw_path.resolve()
    return "file:" + quote(str(path), safe="/") + "?mode=ro"


def _connect_read_only(db_path: str) -> tuple[sqlite3.Connection, str]:
    uri = read_only_uri(db_path)
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection, uri


def _schema_inventory(connection: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    inventory: dict[str, list[str]] = {}
    for table in tables:
        escaped = table.replace("'", "''")
        inventory[table] = [row[1] for row in connection.execute("PRAGMA table_info('" + escaped + "')")]
    return inventory


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("lottery", "")),
        str(row.get("section", "")),
        _sort_value(row.get("bucket", "")),
        str(row.get("candidate_id", "")),
    )


def _candidate_subset(p543a: Mapping[str, Any], top_n: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packet = _mapping(p543a.get("candidate_packet"), "p543a.candidate_packet")
    stable = packet.get("multi_window_stable")
    if not isinstance(stable, list):
        raise SchemaError("p543a.candidate_packet.multi_window_stable must be a list")
    selected: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted((item for item in stable if isinstance(item, Mapping)), key=_candidate_sort_key):
        candidate_id = row.get("candidate_id")
        if not _identifier(candidate_id) or candidate_id in seen:
            continue
        candidate_id = str(candidate_id)
        if " + " in candidate_id or ":" not in candidate_id:
            blocked.append({"candidate_id": candidate_id, "reason": "candidate_id is not a simple strategy_id:bet_index linkage"})
            continue
        strategy_id, bet_index_text = candidate_id.rsplit(":", 1)
        if not strategy_id or not bet_index_text.isdigit() or int(bet_index_text) < 1:
            blocked.append({"candidate_id": candidate_id, "reason": "candidate_id has no positive integer bet_index"})
            continue
        selected.append(
            {
                "candidate_id": candidate_id,
                "lottery": row.get("lottery", "UNKNOWN"),
                "section": row.get("section", "UNKNOWN"),
                "bucket": row.get("bucket", "UNKNOWN"),
                "observed_windows": row.get("observed_windows", []),
                "strategy_id": strategy_id,
                "bet_index": int(bet_index_text),
            }
        )
        seen.add(candidate_id)
        if len(selected) == top_n:
            break
    if not selected:
        raise SchemaError("No simple candidate_id values are available for a contract attempt")
    return selected, sorted(blocked, key=lambda row: row["candidate_id"])


def _validate_p543b_gap(p543b: Mapping[str, Any]) -> None:
    summary = _mapping(p543b.get("summary"), "p543b.summary")
    expected = {
        "walk_forward_possible_from_committed_artifacts": 0,
        "permutation_possible_from_committed_artifacts": 0,
        "aggregate_only_not_validatable": 402,
        "unsupported": 6,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise SchemaError(f"p543b.summary.{key} does not match the committed feasibility gap")
    pilot = _mapping(p543b.get("pilot"), "p543b.pilot")
    if pilot.get("computed") is not False:
        raise SchemaError("p543b.pilot must remain not computed for this contract task")


def _linkage_aggregate(connection: sqlite3.Connection, candidate: Mapping[str, Any]) -> dict[str, Any]:
    row = connection.execute(
        """SELECT COUNT(*) AS total_rows,
                  SUM(CASE WHEN predicted_numbers IS NOT NULL THEN 1 ELSE 0 END) AS predicted_rows,
                  SUM(CASE WHEN actual_numbers IS NOT NULL THEN 1 ELSE 0 END) AS actual_rows,
                  SUM(CASE WHEN predicted_numbers IS NOT NULL AND actual_numbers IS NOT NULL THEN 1 ELSE 0 END) AS complete_rows,
                  MIN(target_draw) AS earliest_draw,
                  MAX(target_draw) AS latest_draw
           FROM strategy_prediction_replays
           WHERE lottery_type = ? AND strategy_id = ? AND bet_index = ?""",
        (candidate["lottery"], candidate["strategy_id"], candidate["bet_index"]),
    ).fetchone()
    return {
        "candidate_id": candidate["candidate_id"],
        "strategy_id": candidate["strategy_id"],
        "bet_index": candidate["bet_index"],
        "total_rows": int(row[0] or 0),
        "predicted_rows": int(row[1] or 0),
        "actual_rows": int(row[2] or 0),
        "complete_rows": int(row[3] or 0),
        "earliest_draw": row[4],
        "latest_draw": row[5],
    }


def _numbers(value: Any, label: str) -> list[int]:
    if not isinstance(value, str):
        raise SchemaError(f"{label} must be JSON text")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, int) and not isinstance(item, bool) for item in parsed):
        raise SchemaError(f"{label} must be a list of integers")
    return parsed


def _contract_rows(connection: sqlite3.Connection, candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT lottery_type, target_draw, target_date, strategy_id, strategy_name, bet_index,
                  predicted_numbers, actual_numbers, predicted_special, actual_special,
                  hit_count, special_hit, replay_status, id
           FROM strategy_prediction_replays
           WHERE lottery_type = ? AND strategy_id = ? AND bet_index = ?
             AND predicted_numbers IS NOT NULL AND actual_numbers IS NOT NULL
           ORDER BY target_date DESC, target_draw DESC, id DESC
           LIMIT ?""",
        (candidate["lottery"], candidate["strategy_id"], candidate["bet_index"], MAX_ROWS_PER_CANDIDATE),
    ).fetchall()
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "lottery": row[0],
                "draw_id": row[1],
                "draw_date": row[2],
                "candidate_id": candidate["candidate_id"],
                "candidate_label": row[4] or candidate["candidate_id"],
                "strategy_ids": [row[3]],
                "strategy_names": [row[4]] if row[4] else [],
                "selected_numbers": _numbers(row[6], "predicted_numbers"),
                "actual_numbers": _numbers(row[7], "actual_numbers"),
                "special_selected": row[8],
                "special_actual": row[9],
                "zone2_selected": None,
                "zone2_actual": None,
                "hit_count": row[10],
                "special_hit": row[11],
                "zone2_hit": None,
                "replay_status": row[12],
                "source_tables": ["strategy_prediction_replays"],
                "contract_status": "complete",
                "_row_id": row[13],
            }
        )
    normalized.sort(key=lambda item: (_sort_value(item["draw_date"]), _sort_value(item["draw_id"]), item["_row_id"]))
    for order, row in enumerate(normalized, start=1):
        row["draw_order"] = order
        del row["_row_id"]
    return normalized


def _contract_attempt(connection: sqlite3.Connection, candidates: list[dict[str, Any]], inventory: Mapping[str, list[str]]) -> dict[str, Any]:
    columns = inventory.get("strategy_prediction_replays")
    if columns is None:
        return {
            "contract_status": "blocked",
            "rows": [],
            "linkage": [],
            "blockers": ["missing table: strategy_prediction_replays"],
        }
    missing_columns = sorted(set(REQUIRED_REPLAY_COLUMNS) - set(columns))
    if missing_columns:
        return {
            "contract_status": "blocked",
            "rows": [],
            "linkage": [],
            "blockers": ["missing columns: " + ", ".join(missing_columns)],
        }

    linkage = [_linkage_aggregate(connection, candidate) for candidate in candidates]
    blockers: list[str] = []
    for item in linkage:
        if item["total_rows"] == 0:
            blockers.append(f"candidate linkage missing: {item['candidate_id']}")
        elif item["predicted_rows"] == 0:
            blockers.append(f"predicted numbers missing: {item['candidate_id']}")
        elif item["actual_rows"] == 0:
            blockers.append(f"actual outcomes missing: {item['candidate_id']}")
        elif item["complete_rows"] == 0:
            blockers.append(f"complete per-draw rows missing: {item['candidate_id']}")
    if blockers:
        return {"contract_status": "blocked", "rows": [], "linkage": linkage, "blockers": sorted(blockers)}

    rows: list[dict[str, Any]] = []
    try:
        for candidate in candidates:
            rows.extend(_contract_rows(connection, candidate))
    except SchemaError as exc:
        return {"contract_status": "blocked", "rows": [], "linkage": linkage, "blockers": [str(exc)]}
    return {
        "contract_status": "generated",
        "rows": sorted(rows, key=lambda row: (row["lottery"], row["candidate_id"], row["draw_order"])),
        "linkage": linkage,
        "blockers": [],
    }


def _markdown(packet: Mapping[str, Any]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# P543C — Candidate-linked Per-draw Validation Contract",
        "",
        "> 本文件只生成候選與歷史 draw 的資料契約；不執行 walk-forward 或 permutation 驗證。",
        "> 僅供描述性研究，不預測未來，也不構成投注建議。",
        "> 本契約不表示候選可正式使用、可上線或已具備正式環境準備。",
        "",
        "## Sources",
        "",
        "| artifact | SHA256 | bytes |",
        "|---|---|---:|",
    ]
    for source in packet["source_artifacts"]:
        lines.append(f"| `{cell(source['path'])}` | `{source['sha256']}` | {source['bytes']} |")
    lines.extend(
        [
            "",
            "## Read-only Access",
            "",
            f"- DB path: `{packet['db_access']['path']}`",
            f"- DB opened read-only: `{packet['db_access']['opened_read_only']}`",
            "- SQL categories: " + "; ".join(packet["db_access"]["sql_categories"]),
            "",
            "## Schema Evidence",
            "",
            "| table | columns used / inspected |",
            "|---|---|",
        ]
    )
    for table, columns in packet["schema_inventory"].items():
        lines.append(f"| `{cell(table)}` | {cell(', '.join(columns))} |")

    lines.extend(
        [
            "",
            "## Candidate Subset",
            "",
            "| candidate | lottery | strategy ID | bet index | windows |",
            "|---|---|---|---:|---|",
        ]
    )
    for candidate in packet["candidate_subset"]:
        lines.append(
            "| {candidate_id} | {lottery} | {strategy_id} | {bet_index} | {windows} |".format(
                candidate_id=cell(candidate["candidate_id"]),
                lottery=cell(candidate["lottery"]),
                strategy_id=cell(candidate["strategy_id"]),
                bet_index=candidate["bet_index"],
                windows=cell(", ".join(str(value) for value in candidate["observed_windows"])),
            )
        )

    contract = packet["contract"]
    lines.extend(["", "## Contract Result", ""])
    lines.append(f"- contract_status: `{contract['contract_status']}`")
    lines.append(f"- contract rows: {len(contract['rows'])}")
    if contract["blockers"]:
        lines.append("- blockers: " + "; ".join(contract["blockers"]))
    else:
        lines.append("- linkage: candidate_id maps to strategy_prediction_replays.strategy_id plus bet_index.")
        lines.append("- capped rows: latest 50 complete historical rows per selected candidate, emitted in chronological order per candidate.")
    lines.extend(
        [
            "",
            "## Next Recommended Task",
            "",
            "Review the contract provenance and define a separate, authorized validation protocol before any walk-forward or permutation computation.",
            "",
        ]
    )
    return "\n".join(lines)


def build_packet_from_bytes(
    p543b_raw: bytes,
    p543b_path: str,
    p543a_raw: bytes,
    p543a_path: str,
    p542a_raw: bytes,
    p542a_path: str,
    db_path: str,
    generated_at: str,
    top_n: int = 10,
) -> tuple[dict[str, Any], str]:
    """Build contract data using one SQLite URI connection opened in mode=ro."""
    if not generated_at:
        raise ValueError("--generated-at is required")
    if top_n < 1:
        raise ValueError("--top-n must be at least 1")
    p543b = _decode(p543b_raw, "p543b")
    p543a = _decode(p543a_raw, "p543a")
    p542a = _decode(p542a_raw, "p542a")
    _validate_p543b_gap(p543b)
    candidates, unlinked = _candidate_subset(p543a, top_n)

    connection, uri = _connect_read_only(db_path)
    try:
        inventory = _schema_inventory(connection)
        contract = _contract_attempt(connection, candidates, inventory)
    finally:
        connection.close()
    contract["unlinked_candidate_ids"] = unlinked
    packet = {
        "classification": "descriptive_only_candidate_per_draw_contract",
        "generated_at": generated_at,
        "source_artifacts": [
            _source_metadata(p543b_path, p543b_raw),
            _source_metadata(p543a_path, p543a_raw),
            _source_metadata(p542a_path, p542a_raw),
        ],
        "p543b_gap_confirmed": True,
        "db_access": {
            "path": str(Path(db_path).expanduser().resolve()),
            "uri": uri,
            "opened_read_only": True,
            "sql_categories": list(SQL_CATEGORIES),
        },
        "schema_inventory": dict(sorted(inventory.items())),
        "candidate_subset": candidates,
        "contract": contract,
        "safety": {
            "contract_generation_only": True,
            "validation_performed": False,
            "no_prediction_claim": True,
            "no_betting_advice": True,
            "no_write_operations": True,
        },
    }
    return packet, _markdown(packet)


def generate(
    p543b_json: Path,
    p543a_json: Path,
    p542a_json: Path,
    db_path: str,
    output_json: Path,
    output_md: Path,
    generated_at: str,
    top_n: int = 10,
) -> None:
    packet, markdown = build_packet_from_bytes(
        p543b_json.read_bytes(),
        str(p543b_json),
        p543a_json.read_bytes(),
        str(p543a_json),
        p542a_json.read_bytes(),
        str(p542a_json),
        db_path,
        generated_at,
        top_n,
    )
    output_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a deterministic read-only candidate per-draw contract.")
    parser.add_argument("--p543b-json", required=True)
    parser.add_argument("--p543a-json", required=True)
    parser.add_argument("--p542a-json", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate(
        Path(args.p543b_json),
        Path(args.p543a_json),
        Path(args.p542a_json),
        args.db_path,
        Path(args.output_json),
        Path(args.output_md),
        args.generated_at,
        args.top_n,
    )


if __name__ == "__main__":
    main()
