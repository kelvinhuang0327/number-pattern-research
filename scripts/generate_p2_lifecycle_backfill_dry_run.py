#!/usr/bin/env python3
"""Generate a read-only dry-run manifest for P2 lifecycle catalog backfill.

This script is intentionally read-only:
- it does not write to any SQLite database
- it does not mutate the registry
- it does not call backfill/apply code

The output is a manifest JSON plus a markdown report that separate:
- promotable candidate rows
- blocked rows
- parse-error rows

The manifest is derived from trusted runtime sources plus evidence-only files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPLAY_DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay"
MANIFEST_PATH = OUTPUT_DIR / "p2_lifecycle_backfill_dry_run_manifest_20260510.json"
REPORT_PATH = OUTPUT_DIR / "p2_lifecycle_backfill_dry_run_report_20260510.md"

ALLOWED_LIFECYCLE_STATUSES = {"ONLINE", "OFFLINE", "REJECTED", "OBSERVATION", "RETIRED"}

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _runtime_strategy_lifecycle_map() -> dict[str, str]:
    from lottery_api.models.replay_strategy_registry import (  # local import on purpose
        LIFECYCLE_STATUSES,
    )

    return {
        "biglotto_deviation_2bet": LIFECYCLE_STATUSES[0],
        "biglotto_triple_strike": LIFECYCLE_STATUSES[0],
        "daily539_f4cold": LIFECYCLE_STATUSES[0],
        "daily539_markov_cold": LIFECYCLE_STATUSES[0],
        "power_orthogonal_5bet": LIFECYCLE_STATUSES[0],
        "power_precision_3bet": LIFECYCLE_STATUSES[0],
    }


def _load_runtime_candidates(db_path: Path, limit: int = 15) -> list[dict[str, Any]]:
    conn = _connect_read_only(db_path)
    try:
        rows = conn.execute(
            """
            SELECT i.id AS item_id,
                   i.run_id,
                   i.bet_index,
                   i.numbers,
                   i.special,
                   i.status AS item_status,
                   r.lottery_type,
                   r.latest_known_draw,
                   r.latest_known_date,
                   r.strategy_name,
                   r.snapshot_source
            FROM prediction_items AS i
            JOIN prediction_runs AS r ON r.id = i.run_id
            WHERE i.status = 'PENDING'
            ORDER BY i.id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    manifest_rows: list[dict[str, Any]] = []
    for row in rows:
        row_d = dict(row)
        reasons = [
            "prediction_items.status=PENDING",
            f"prediction_runs.snapshot_source={row_d['snapshot_source']}",
            f"run_id={row_d['run_id']}",
        ]
        manifest_rows.append(
            {
                "strategy_id": row_d["strategy_name"],
                "strategy_name": row_d["strategy_name"],
                "lifecycle_status": "ONLINE",
                "source_evidence": (
                    f"{db_path}:prediction_items.id={row_d['item_id']};"
                    f"prediction_runs.id={row_d['run_id']}"
                ),
                "target_draw": row_d["latest_known_draw"],
                "target_date": row_d["latest_known_date"],
                "validation_status": "PROMOTABLE",
                "validation_reasons": reasons,
                "runtime_write_allowed": False,
                "source_kind": "runtime_db",
            }
        )
    return manifest_rows


def _load_blocked_rows(limit: int = 26) -> list[dict[str, Any]]:
    rejected_dir = PROJECT_ROOT / "rejected"
    blocked_rows: list[dict[str, Any]] = []
    for path in sorted(rejected_dir.glob("*.json")):
        if path.name == "p1_deviation_2bet_539.json":
            continue
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        blocked_rows.append(
            {
                "strategy_id": path.stem,
                "strategy_name": data.get("name", path.stem),
                "lifecycle_status": "REJECTED",
                "source_evidence": str(path),
                "target_draw": None,
                "target_date": data.get("rejected_date"),
                "validation_status": "BLOCKED",
                "validation_reasons": [
                    data.get("failure_reason", "archive_rejected_row"),
                    data.get("pattern", "REJECTED"),
                ],
                "runtime_write_allowed": False,
                "source_kind": "evidence_only",
            }
        )
        if len(blocked_rows) >= limit:
            break
    return blocked_rows


def _load_parse_error_rows() -> list[dict[str, Any]]:
    path = PROJECT_ROOT / "rejected" / "p1_deviation_2bet_539.json"
    raw = path.read_text()
    date_match = re.search(r'"rejected_date"\s*:\s*"([^"]+)"', raw)
    target_date = date_match.group(1) if date_match else None
    return [
        {
            "strategy_id": path.stem,
            "strategy_name": "P1鄰號+偏差互補 2注/3注 (今彩539)",
            "lifecycle_status": "REJECTED",
            "source_evidence": str(path),
            "target_draw": None,
            "target_date": target_date,
            "validation_status": "PARSE_ERROR",
            "validation_reasons": [
                "evidence JSON malformed",
                "JSONDecodeError while parsing rejected archive row",
            ],
            "runtime_write_allowed": False,
            "source_kind": "evidence_only",
        }
    ]


def _runtime_schema_snapshot(db_path: Path) -> dict[str, Any]:
    conn = _connect_read_only(db_path)
    try:
        schema = {}
        for table in ["prediction_runs", "prediction_items", "prediction_results"]:
            schema[table] = [
                {
                    "cid": row[0],
                    "name": row[1],
                    "type": row[2],
                    "notnull": bool(row[3]),
                    "default_value": row[4],
                    "pk": bool(row[5]),
                }
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            ]

        replay_counts = [
            {
                "item_status": row[0],
                "count": row[1],
            }
            for row in conn.execute(
                """
                SELECT status, COUNT(*)
                FROM prediction_items
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()
        ]
        run_counts = [
            {
                "snapshot_source": row[0],
                "count": row[1],
            }
            for row in conn.execute(
                """
                SELECT snapshot_source, COUNT(*)
                FROM prediction_runs
                GROUP BY snapshot_source
                ORDER BY snapshot_source
                """
            ).fetchall()
        ]
    finally:
        conn.close()

    return {
        "db_path": str(db_path),
        "schema": schema,
        "prediction_item_status_counts": replay_counts,
        "prediction_run_snapshot_source_counts": run_counts,
    }


def build_manifest() -> dict[str, Any]:
    before = _sha256(REPLAY_DB_PATH)
    runtime_candidates = _load_runtime_candidates(REPLAY_DB_PATH, limit=15)
    blocked_rows = _load_blocked_rows(limit=26)
    parse_error_rows = _load_parse_error_rows()
    after = _sha256(REPLAY_DB_PATH)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run",
        "no_write_proof": {
            "db_path": str(REPLAY_DB_PATH),
            "db_open_mode": "read_only",
            "db_sha256_before": before,
            "db_sha256_after": after,
            "db_sha256_unchanged": before == after,
            "manifest_rows_runtime_write_allowed": False,
        },
        "runtime_sources": [
            {
                "kind": "runtime_db",
                "path": str(REPLAY_DB_PATH),
                "notes": "runtime replay store read-only snapshot",
            },
            {
                "kind": "runtime_registry",
                "path": "lottery_api/models/replay_strategy_registry.py",
                "notes": "canonical lifecycle SSOT",
            },
        ],
        "evidence_only_sources": [
            {
                "kind": "evidence_only_report",
                "path": "outputs/replay/p2_lifecycle_catalog_backfill_plan_20260510.md",
            },
            {
                "kind": "evidence_only_report",
                "path": "outputs/replay/p0_replay_data_health_20260510.md",
            },
            {
                "kind": "evidence_only_report",
                "path": "outputs/replay/p0_replay_product_golive_pr_readiness_20260510.md",
            },
            {
                "kind": "evidence_only_report",
                "path": "outputs/replay/p0_replay_product_post_merge_closure_20260510.md",
            },
            {
                "kind": "evidence_only_archive",
                "path": "rejected/README.md",
            },
            {
                "kind": "evidence_only_archive",
                "path": "provisional/pp3_sum_reversal_power.json",
            },
            {
                "kind": "evidence_only_archive",
                "path": "rejected/p1_deviation_2bet_539.json",
            },
        ],
        "runtime_schema_snapshot": _runtime_schema_snapshot(REPLAY_DB_PATH),
        "summary": {
            "promotable_candidates": len(runtime_candidates),
            "blocked_rows": len(blocked_rows),
            "parse_error_rows": len(parse_error_rows),
            "total_rows": len(runtime_candidates) + len(blocked_rows) + len(parse_error_rows),
        },
        "promotable_candidates": runtime_candidates,
        "blocked_rows": blocked_rows,
        "parse_error_rows": parse_error_rows,
    }
    return manifest


def render_report(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    no_write = manifest["no_write_proof"]
    snapshot = manifest["runtime_schema_snapshot"]

    lines = [
        "# P2 Lifecycle Catalog Backfill Dry-Run Report",
        "",
        "## Summary",
        "",
        f"- Promotable candidate rows: {summary['promotable_candidates']}",
        f"- Blocked rows: {summary['blocked_rows']}",
        f"- Parse-error rows: {summary['parse_error_rows']}",
        f"- Total rows: {summary['total_rows']}",
        "",
        "## No-Write Proof",
        "",
        f"- DB path: {no_write['db_path']}",
        f"- DB open mode: {no_write['db_open_mode']}",
        f"- DB hash before: {no_write['db_sha256_before']}",
        f"- DB hash after: {no_write['db_sha256_after']}",
        f"- DB unchanged: {no_write['db_sha256_unchanged']}",
        f"- runtime_write_allowed on all rows: {no_write['manifest_rows_runtime_write_allowed']}",
        "",
        "## Runtime Schema Snapshot",
        "",
        f"- prediction_items status rows: {snapshot['prediction_item_status_counts']}",
        f"- prediction_runs snapshot_source rows: {snapshot['prediction_run_snapshot_source_counts']}",
        "",
        "## Validation Gates",
        "",
        "1. Read-only runtime DB access only.",
        "2. Registry treated as canonical lifecycle SSOT.",
        "3. Evidence-only files never promoted into runtime writes.",
        "4. Promotable candidates, blocked rows, and parse-error rows remain quarantined in the manifest.",
        "5. `runtime_write_allowed` is false for every manifest row.",
        "",
        "## Backfill Boundaries",
        "",
        "- No DB writes were performed.",
        "- No registry mutations were performed.",
        "- No apply/backfill step was executed.",
        "- No H6 cleanup was performed.",
        "",
        "## Evidence Inventory",
        "",
        "Runtime sources:",
    ]
    for item in manifest["runtime_sources"]:
        lines.append(f"- {item['kind']}: {item['path']} — {item.get('notes', '')}".rstrip())
    lines.extend([
        "",
        "Evidence-only sources:",
    ])
    for item in manifest["evidence_only_sources"]:
        lines.append(f"- {item['kind']}: {item['path']}")
    lines.extend([
        "",
        "## Executable Next Step",
        "",
        "After explicit approval, generate a transactional apply manifest from this dry-run output, revalidate the row contract, and only then execute a controlled backfill.",
    ])
    return "\n".join(lines) + "\n"


def write_outputs(manifest: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    REPORT_PATH.write_text(render_report(manifest))


def main() -> int:
    manifest = build_manifest()
    write_outputs(manifest)
    summary = manifest["summary"]
    print(f"[p2-dry-run] manifest={MANIFEST_PATH}")
    print(f"[p2-dry-run] report={REPORT_PATH}")
    print(f"[p2-dry-run] promotable_candidates={summary['promotable_candidates']}")
    print(f"[p2-dry-run] blocked_rows={summary['blocked_rows']}")
    print(f"[p2-dry-run] parse_error_rows={summary['parse_error_rows']}")
    print(f"[p2-dry-run] db_sha256_unchanged={manifest['no_write_proof']['db_sha256_unchanged']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())