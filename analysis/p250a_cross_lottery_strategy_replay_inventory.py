"""P250A — Cross-lottery strategy/replay inventory.

Read-only inventory that reconciles:
  - current registry state from lottery_api/models/replay_strategy_registry.py
  - historical replay snapshot from outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json
  - live DB row counts and tables, read-only only

The goal is to include every developed strategy in historical replay/catalog
views regardless of lifecycle status, while keeping lifecycle itself as a label
or badge rather than an exclusion filter.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


TASK_ID = "P250A"
SCHEMA_VERSION = "1.0"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
CANONICAL_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
HISTORICAL_SCOREBOARD_PATH = OUTPUT_DIR / "p232a_all_catalog_strategy_replay_scoreboard_20260604.json"
CURRENT_STATE_PATH = REPO_ROOT / "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md"
ROADMAP_PATH = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan/roadmap/active_task.md"

JSON_OUTPUT = OUTPUT_DIR / f"p250a_cross_lottery_strategy_replay_inventory_{DATE_SLUG}.json"
MD_OUTPUT = OUTPUT_DIR / f"p250a_cross_lottery_strategy_replay_inventory_{DATE_SLUG}.md"

TOLERATED_DIRTY_ITEMS = [
    "backend.pid",
    "frontend.pid",
    "claude-code-showcase",
    "claude-code-showcase.worktrees/",
    "runtime/",
    "data/lottery_v2.db metadata-only same-size touch",
]

CURRENT_STATEFUL_CLASSIFICATIONS = {
    "ONLINE": "active",
    "OFFLINE": "offline",
    "REJECTED": "rejected",
    "OBSERVATION": "observation",
    "RETIRED": "retired",
    "ARTIFACT_ONLY": "artifact-only",
}


def _run_git(args: List[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _maybe_read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_current_registry() -> Dict[Tuple[str, str], Dict[str, Any]]:
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata

    registry: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for meta in list_strategy_lifecycle_metadata():
        for lottery_type in meta["supported_lottery_types"]:
            key = (meta["strategy_id"], lottery_type)
            registry[key] = {
                "strategy_id": meta["strategy_id"],
                "strategy_name": meta["strategy_name"],
                "strategy_version": meta["strategy_version"],
                "lottery_type": lottery_type,
                "current_lifecycle_status": meta["lifecycle_status"],
                "current_lifecycle_source": "MAIN_REGISTRY",
                "current_registry_presence": True,
                "registry_min_history": meta["min_history"],
            }
    return registry


def _load_historical_scoreboard() -> Dict[Tuple[str, str], Dict[str, Any]]:
    data = json.loads(HISTORICAL_SCOREBOARD_PATH.read_text(encoding="utf-8"))
    scoreboard: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in data["all_strategy_scoreboard"]:
        key = (row["strategy_id"], row["lottery_type"])
        scoreboard[key] = row
    return scoreboard


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _db_scalar(conn: sqlite3.Connection, sql: str) -> Any:
    return conn.execute(sql).fetchone()[0]


def db_read_status(db_path: Path) -> Dict[str, Any]:
    conn = _connect_ro(db_path)
    try:
        integrity = _db_scalar(conn, "SELECT integrity_check FROM pragma_integrity_check")
        replay_rows = _db_scalar(conn, "SELECT COUNT(*) FROM strategy_prediction_replays")
        draw_rows = _db_scalar(conn, "SELECT COUNT(*) FROM draws")
        canonical_rows = _db_scalar(
            conn, "SELECT COUNT(*) FROM draws_big_lotto_canonical_main"
        )
        rows_by_lottery = [
            dict(r)
            for r in conn.execute(
                """
                SELECT lottery_type,
                       COUNT(*) AS replay_rows,
                       COUNT(DISTINCT strategy_id) AS strategy_count,
                       COUNT(DISTINCT target_draw) AS distinct_draws
                FROM strategy_prediction_replays
                GROUP BY lottery_type
                ORDER BY lottery_type
                """
            ).fetchall()
        ]
        return {
            "read_only": True,
            "db_path": str(db_path),
            "integrity_check": integrity,
            "replay_rows_total": replay_rows,
            "draw_rows_total": draw_rows,
            "canonical_big_lotto_rows": canonical_rows,
            "rows_by_lottery": rows_by_lottery,
        }
    finally:
        conn.close()


def tables_found(db_path: Path) -> List[Dict[str, str]]:
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE type IN ('table', 'view')
            ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _classification_for_entry(current_lifecycle: str, row_count: int) -> str:
    if current_lifecycle == "ARTIFACT_ONLY":
        return "artifact-only"
    if row_count == 0:
        return "no-data"
    return CURRENT_STATEFUL_CLASSIFICATIONS.get(current_lifecycle, "unknown")


def _current_registry_status_note(current_lifecycle: str, historical_lifecycle: str) -> str | None:
    if current_lifecycle == historical_lifecycle:
        return None
    return f"historical snapshot={historical_lifecycle}; current registry={current_lifecycle}"


def build_strategy_inventory() -> List[Dict[str, Any]]:
    registry = _load_current_registry()
    historical = _load_historical_scoreboard()

    inventory: List[Dict[str, Any]] = []
    for key, row in sorted(historical.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        registry_row = registry.get(key)
        current_lifecycle = (
            registry_row["current_lifecycle_status"] if registry_row else "ARTIFACT_ONLY"
        )
        current_registry_presence = registry_row is not None
        historical_lifecycle = row["lifecycle_status"]
        row_count = int(row.get("row_count", 0))
        inventory.append(
            {
                "strategy_id": row["strategy_id"],
                "strategy_name": row["strategy_name"],
                "strategy_version": row["strategy_version"],
                "lottery_type": row["lottery_type"],
                "current_lifecycle_status": current_lifecycle,
                "historical_snapshot_lifecycle_status": historical_lifecycle,
                "current_registry_presence": current_registry_presence,
                "historical_scoreboard_presence": True,
                "current_lifecycle_source": (
                    registry_row["current_lifecycle_source"] if registry_row else "P47_WAVE4"
                ),
                "catalog_source_snapshot": row["catalog_source"],
                "replay_presence": bool(row.get("replay_presence", False)),
                "replay_rows": row_count,
                "distinct_target_draws": int(row.get("distinct_target_draws", 0)),
                "bet_index_values": row.get("bet_index_values", []),
                "historical_replay_classification": row.get("historical_classification"),
                "latest_classification": _classification_for_entry(current_lifecycle, row_count),
                "included_in_historical_replay_or_catalog_views": True,
                "evidence_source": [
                    "lottery_api/models/replay_strategy_registry.py"
                    if current_registry_presence
                    else "outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json (P47_WAVE4 artifact-only snapshot)",
                    "outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json",
                ],
                "status_note": _current_registry_status_note(current_lifecycle, historical_lifecycle),
            }
        )
    return inventory


def _group_inventory_by_lottery(inventory: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in inventory:
        grouped[item["lottery_type"]].append(item)
    return grouped


def build_replay_coverage_by_lottery(inventory: List[Dict[str, Any]], db_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    grouped = _group_inventory_by_lottery(inventory)
    draw_rows_lookup = {
        "BIG_LOTTO": 22_238,
        "DAILY_539": 5_879,
        "POWER_LOTTO": 1_916,
    }
    canonical_lookup = {"BIG_LOTTO": 2_113}
    notes_lookup = {
        "BIG_LOTTO": [
            "replay rows are strategy_prediction_replays rows, not draw rows",
            "raw BIG_LOTTO draw rows remain 22,238; canonical main-draw rows are 2,113",
            "19,100 add-on/special-prize rows stay raw-accessible and are excluded from canonical 6/49 research",
            "P249B fixes the replay-row vs draw-row label ambiguity",
        ],
        "DAILY_539": [
            "replay rows are strategy_prediction_replays rows, not draw rows",
            "no canonical/raw split currently tracked beyond the draw table count",
            "P230C closed the prior DAILY_539 survivor as rejected/historical artifact",
        ],
        "POWER_LOTTO": [
            "replay rows are strategy_prediction_replays rows, not draw rows",
            "three P47 artifact-only strategies remain in the historical inventory",
            "current registry has no active deployable candidate",
        ],
    }

    result: List[Dict[str, Any]] = []
    for lottery_type in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO"):
        lottery_items = grouped.get(lottery_type, [])
        replay_items = [x for x in lottery_items if x["replay_presence"]]
        live_db_rows = next(
            (row for row in db_status["rows_by_lottery"] if row["lottery_type"] == lottery_type),
            None,
        )
        result.append(
            {
                "lottery_type": lottery_type,
                "developed_strategy_entries": len(lottery_items),
                "replay_strategy_entries": len(replay_items),
                "replay_rows": sum(x["replay_rows"] for x in lottery_items),
                "draw_rows": draw_rows_lookup[lottery_type],
                "distinct_replay_draws": live_db_rows["distinct_draws"] if live_db_rows else 0,
                "canonical_rows": canonical_lookup.get(lottery_type),
                "row_semantics": (
                    "replay_rows = rows in strategy_prediction_replays; draw_rows = rows in draws table; "
                    "canonical_rows = canonical main-draw rows when a canonical view exists"
                ),
                "notes": notes_lookup[lottery_type],
                "live_db_rows_by_lottery": live_db_rows,
            }
        )
    return result


def build_phase0_expected_state(phase0: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "canonical_repo": phase0["repo_root"],
        "canonical_branch": phase0["branch"],
        "head_short": phase0["head_short"],
        "origin_main_short": phase0["origin_main_short"],
        "head_matches_origin_main": phase0["head_short"] == phase0["origin_main_short"],
        "p249b_merge_visible": phase0["p249b_merge_visible"],
        "active_task_status": phase0["active_task_status"],
        "tolerated_dirty_items": TOLERATED_DIRTY_ITEMS,
        "canonical_db_path": str(CANONICAL_DB_PATH.relative_to(REPO_ROOT)),
        "canonical_db_is_ssot": True,
        "root_db_dirty_note": phase0["root_db_dirty_note"],
        "no_db_write": True,
        "no_registry_mutation": True,
        "no_strategy_logic_change": True,
        "no_production_recommendation_change": True,
    }


def build_research_state() -> Dict[str, Any]:
    return {
        "big_lotto": {
            "status": "GREEN_CANONICAL_RANDOMNESS_NO_PREDICTION_EDGE",
            "note": "P246K canonical NIST audit is GREEN on 2,113 canonical rows; this is a data-quality result, not a strategy signal.",
        },
        "daily_539": {
            "status": "REJECTED_BY_BACKWARD_OOS",
            "note": "P230C closed the prior survivor; no active candidate remains.",
        },
        "power_lotto": {
            "status": "NULL_OR_BASELINE_LIKE",
            "note": "P231B first-zone backward-OOS dry-run was NULL; any new hypothesis would require fresh pre-registration.",
        },
        "star_3_4": {
            "status": "UNDERPOWERED_NO_SIGNAL_AND_STRAIGHT_PLAY_BLOCKED",
            "note": "P227C box-play was underpowered; P214C straight-play was NULL and positional order is lost in sorted storage.",
        },
        "inventory_note": "Current registry is the live SSOT; P232A historical scoreboard is retained as a replay snapshot and is reconciled here rather than used as the sole current-state source.",
    }


def build_candidate_next_directions() -> List[Dict[str, Any]]:
    return [
        {
            "rank": 1,
            "title": "Cross-lottery null/positive evidence dashboard",
            "value": "High — one place to compare active / rejected / retired / artifact-only rows, replay coverage, and historical classifications.",
            "risk": "Low — read-only reporting and view composition only.",
            "urgency": "Medium — the current inventory spans multiple lifecycle labels and benefits from a single honest view.",
            "prerequisites": "Read-only access to current registry + replay snapshot; no DB write.",
        },
        {
            "rank": 2,
            "title": "Replay/catalog lifecycle badge and filter refresh",
            "value": "High — makes lifecycle visible without hiding historical replay rows.",
            "risk": "Low-medium — UI/API behavior change only if surfaced to users.",
            "urgency": "Medium — current state already contains active, rejected, retired, observation, and artifact-only entries.",
            "prerequisites": "Define the exact badge vocabulary and keep historical rows visible by default.",
        },
        {
            "rank": 3,
            "title": "Canonical replay refresh and stale-label cleanup",
            "value": "Medium-high — rebuild the current scoreboard from the current registry so the historical snapshot is not mistaken for live state.",
            "risk": "Low — read-only unless a new artifact is written.",
            "urgency": "Medium — the 20260604 scoreboard is historically useful but stale relative to the current registry.",
            "prerequisites": "Use the current registry as SSOT; keep P232A as historical evidence only.",
        },
        {
            "rank": 4,
            "title": "Raw history add-on labeling for user-facing views",
            "value": "Medium — clarifies the BIG_LOTTO raw/canonical split and similar label semantics.",
            "risk": "Medium — touches UI/API display behavior.",
            "urgency": "Low-medium — useful for truthfulness, but not required for current research governance.",
            "prerequisites": "Frontend/API authorization and explicit display contract.",
        },
        {
            "rank": 5,
            "title": "Archived script reactivation / migration only when a script is revived",
            "value": "Low-medium — keeps dormant code aligned with canonical helpers when reactivated.",
            "risk": "Low — narrow code migration, but only worth doing when a script is truly in use again.",
            "urgency": "Low — no active deployable candidate depends on it today.",
            "prerequisites": "Explicit reactivation decision for the specific archived script.",
        },
        {
            "rank": 6,
            "title": "Annotation table Type D only if a downstream consumer appears",
            "value": "Low-medium — would label row families without mutating strategy logic.",
            "risk": "Medium — requires a controlled DB write and backup discipline.",
            "urgency": "Low — the current inventory does not require it.",
            "prerequisites": "Explicit Type D authorization and a concrete consumer need.",
        },
    ]


def _phase0_snapshot() -> Dict[str, Any]:
    status_short = _run_git(["status", "--short"])
    status_sb = _run_git(["status", "-sb"])
    root_db_status = _run_git(["status", "--short", "--", "data/lottery_v2.db"])
    root_db_size = (REPO_ROOT / "data" / "lottery_v2.db").stat().st_size
    log = _run_git(["log", "--oneline", "-12"])
    return {
        "repo_root": _run_git(["rev-parse", "--show-toplevel"]),
        "branch": _run_git(["branch", "--show-current"]),
        "head_short": _run_git(["rev-parse", "--short", "HEAD"]),
        "origin_main_short": _run_git(["rev-parse", "--short", "origin/main"]),
        "status_short": status_short,
        "status_sb": status_sb,
        "git_log": log,
        "p249b_merge_visible": "75a4aad" in log,
        "active_task_status": "WAITING_FOR_USER_AUTHORIZATION"
        if "WAITING_FOR_USER_AUTHORIZATION" in _maybe_read(ACTIVE_TASK_PATH)
        else "UNKNOWN",
        "root_db_dirty_note": {
            "path": "data/lottery_v2.db",
            "git_status": root_db_status or "clean",
            "size_bytes": root_db_size,
            "canonical_db_path": str(CANONICAL_DB_PATH.relative_to(REPO_ROOT)),
        },
    }


def build_report() -> Dict[str, Any]:
    phase0 = _phase0_snapshot()
    db_status = db_read_status(CANONICAL_DB_PATH)
    inventory = build_strategy_inventory()

    current_registry_entries = [item for item in inventory if item["current_registry_presence"]]
    current_registry_count = len(current_registry_entries)
    historical_snapshot_count = len(inventory)
    artifact_only_count = sum(1 for item in inventory if item["current_lifecycle_status"] == "ARTIFACT_ONLY")
    current_registry_lifecycle_counts: Dict[str, int] = defaultdict(int)
    for item in current_registry_entries:
        current_registry_lifecycle_counts[item["current_lifecycle_status"]] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "CROSS_LOTTERY_STRATEGY_REPLAY_INVENTORY",
        "phase0_expected_state": build_phase0_expected_state(phase0),
        "phase0_snapshot": phase0,
        "db_read_status": db_status,
        "tables_found": tables_found(CANONICAL_DB_PATH),
        "inventory_granularity": "(strategy_id, lottery_type)",
        "inventory_counts": {
            "current_registry_entries": current_registry_count,
            "historical_inventory_entries": historical_snapshot_count,
            "artifact_only_entries": artifact_only_count,
            "current_registry_lifecycle_counts": dict(sorted(current_registry_lifecycle_counts.items())),
        },
        "strategy_inventory": inventory,
        "replay_coverage_by_lottery": build_replay_coverage_by_lottery(inventory, db_status),
        "research_state": build_research_state(),
        "candidate_next_directions": build_candidate_next_directions(),
        "source_artifacts": {
            "current_registry": "lottery_api/models/replay_strategy_registry.py",
            "historical_scoreboard": str(HISTORICAL_SCOREBOARD_PATH.relative_to(REPO_ROOT)),
            "current_state": str(CURRENT_STATE_PATH.relative_to(REPO_ROOT)),
            "roadmap": str(ROADMAP_PATH.relative_to(REPO_ROOT)),
            "active_task": str(ACTIVE_TASK_PATH.relative_to(REPO_ROOT)),
        },
        "compliance": {
            "read_only": True,
            "no_db_write": True,
            "no_registry_mutation": True,
            "no_strategy_logic_change": True,
            "no_production_recommendation_change": True,
            "no_betting_advice": True,
        },
    }


def build_md_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    A = lines.append

    A("# P250A — Cross-Lottery Strategy Replay Inventory")
    A("")
    A(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    A(f"**Task:** `{TASK_ID}`  ")
    A(f"**Classification:** `{report['classification']}`  ")
    A("")
    A("## Executive Summary")
    A("")
    A(
        "This inventory reconciles the current registry with the historical P232A "
        "replay scoreboard so that every developed strategy appears in replay/catalog "
        "views regardless of lifecycle status. Lifecycle is shown as a label or badge, "
        "not as an exclusion filter."
    )
    A("")
    A(f"- Current registry entries: `{report['inventory_counts']['current_registry_entries']}`")
    A(f"- Historical inventory entries: `{report['inventory_counts']['historical_inventory_entries']}`")
    A(f"- Artifact-only entries: `{report['inventory_counts']['artifact_only_entries']}`")
    A(f"- Replay rows total: `{report['db_read_status']['replay_rows_total']}`")
    A(f"- Draw rows total: `{report['db_read_status']['draw_rows_total']}`")
    A(f"- Canonical BIG_LOTTO rows: `{report['db_read_status']['canonical_big_lotto_rows']}`")
    A("")
    A("## Phase 0")
    A("")
    A(f"- Repo: `{report['phase0_snapshot']['repo_root']}`")
    A(f"- Branch: `{report['phase0_snapshot']['branch']}`")
    A(f"- HEAD short: `{report['phase0_snapshot']['head_short']}`")
    A(f"- `origin/main` short: `{report['phase0_snapshot']['origin_main_short']}`")
    A(f"- P249B merge visible: `{report['phase0_snapshot']['p249b_merge_visible']}`")
    A(f"- Active task: `{report['phase0_expected_state']['active_task_status']}`")
    A(f"- Canonical DB: `{report['phase0_expected_state']['canonical_db_path']}`")
    A("")
    A("### Tolerated Dirty Items")
    A("")
    for item in report["phase0_expected_state"]["tolerated_dirty_items"]:
        A(f"- `{item}`")
    A("")
    A("## DB Read Status")
    A("")
    A(f"- Integrity check: `{report['db_read_status']['integrity_check']}`")
    A(f"- `strategy_prediction_replays` rows: `{report['db_read_status']['replay_rows_total']}`")
    A(f"- `draws` rows: `{report['db_read_status']['draw_rows_total']}`")
    A(f"- `draws_big_lotto_canonical_main` rows: `{report['db_read_status']['canonical_big_lotto_rows']}`")
    A("")
    A("### Tables Found")
    A("")
    for item in report["tables_found"]:
        A(f"- `{item['type']}` `{item['name']}`")
    A("")
    A("## Replay Coverage by Lottery")
    A("")
    A("| Lottery | Developed entries | Replay entries | Replay rows | Draw rows | Distinct replay draws | Canonical rows |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for item in report["replay_coverage_by_lottery"]:
        A(
            f"| {item['lottery_type']} | {item['developed_strategy_entries']} | {item['replay_strategy_entries']} | "
            f"{item['replay_rows']} | {item['draw_rows']} | {item['distinct_replay_draws']} | "
            f"{item['canonical_rows'] if item['canonical_rows'] is not None else ''} |"
        )
        for note in item["notes"]:
            A(f"- {item['lottery_type']}: {note}")
    A("")
    A("## Strategy Inventory")
    A("")
    for lottery_type in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO"):
        A(f"### {lottery_type}")
        A("")
        A("| Strategy ID | Current lifecycle | Historical snapshot | Latest classification | Replay rows | Source |")
        A("|---|---|---|---|---:|---|")
        for item in [x for x in report["strategy_inventory"] if x["lottery_type"] == lottery_type]:
            source = item["current_lifecycle_source"]
            if source == "P47_WAVE4":
                source = "P47_WAVE4 artifact-only"
            note = item["status_note"] or ""
            A(
                f"| {item['strategy_id']} | {item['current_lifecycle_status']} | "
                f"{item['historical_snapshot_lifecycle_status']} | {item['latest_classification']} | "
                f"{item['replay_rows']} | {source} |"
            )
            if note:
                A(f"- note: {note}")
        A("")
    A("### 3_STAR / 4_STAR")
    A("")
    A(
        "No registry entries and no replay rows are present in the current replay inventory. "
        "P227C and P214C remain the controlling historical references."
    )
    A("")
    A("## Research State")
    A("")
    for key, item in report["research_state"].items():
        if isinstance(item, dict):
            A(f"- **{key}**: {item['status']} — {item['note']}")
        else:
            A(f"- **{key}**: {item}")
    A("")
    A("## Candidate Next Directions")
    A("")
    for item in report["candidate_next_directions"]:
        A(f"### {item['rank']}. {item['title']}")
        A("")
        A(f"- Value: {item['value']}")
        A(f"- Risk: {item['risk']}")
        A(f"- Urgency: {item['urgency']}")
        A(f"- Prerequisites: {item['prerequisites']}")
        A("")
    A("## Compliance")
    A("")
    for key, value in report["compliance"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## Sources")
    A("")
    for label, source in report["source_artifacts"].items():
        A(f"- {label}: `{source}`")
    A("")
    A("Final Classification: `P250A_CROSS_LOTTERY_STRATEGY_REPLAY_INVENTORY_COMPLETE`")
    return "\n".join(lines)


def main() -> int:
    report = build_report()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUTPUT.write_text(build_md_report(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
