#!/usr/bin/env python3
"""
P128: Native Multi-Bet Replay Storage Design
=============================================
PURPOSE : Design-only. Produces storage design decision + migration plan.
          ZERO DB writes. ZERO schema changes. read-only throughout.
INPUTS  : P124 / P125 / P126 artifacts on disk + live DB schema query
OUTPUTS : outputs/replay/p128_native_multi_bet_storage_design_20260528.json
          docs/replay/p128_native_multi_bet_storage_design_20260528.md
GOVERNANCE:
  - PRAGMA query_only = ON on every DB connection
  - NO INSERT / UPDATE / DELETE
  - replay_rows must remain 54462
  - NO scheduler, NO DB writes, NO strategy promotion
  - 4_STAR / P108 / P117 / P118 are blocked
"""

import json
import sqlite3
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_ID                   = "P128"
CLASSIFICATION            = "P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY"
DATE_SUFFIX               = "20260528"
REPO_ROOT                 = Path(__file__).resolve().parent.parent

P124_ARTIFACT             = REPO_ROOT / "outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json"
P125_ARTIFACT             = REPO_ROOT / "outputs/replay/p125_adapter_gap_plan_from_p124_20260528.json"
P126_ARTIFACT             = REPO_ROOT / "outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"

OUT_JSON                  = REPO_ROOT / "outputs/replay/p128_native_multi_bet_storage_design_20260528.json"
OUT_MD                    = REPO_ROOT / "docs/replay/p128_native_multi_bet_storage_design_20260528.md"
DB_PATH                   = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS      = 54462
EXPECTED_3STAR_COUNT      = 4179
EXPECTED_3STAR_MAX        = 115000106
EXPECTED_4STAR_COUNT      = 2922
EXPECTED_4STAR_MAX        = 115000103
EXPECTED_POWER_COUNT      = 1913
EXPECTED_POWER_MAX        = 115000041

P126_EXPECTED_NEW_ROWS    = 18000
P126_EXPECTED_TOTAL_AFTER = 72462

# ---------------------------------------------------------------------------
# Read-only DB helper
# ---------------------------------------------------------------------------
def _ro_conn() -> sqlite3.Connection:
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Phase 1: DB invariant verification
# ---------------------------------------------------------------------------
def verify_db_invariants() -> dict:
    print("[P128] Phase 1: verifying DB invariants...")
    conn = _ro_conn()
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    replay_rows = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = '3_STAR'")
    r3 = cur.fetchone(); c3, m3 = r3[0], r3[1]

    cur.execute("SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = '4_STAR'")
    r4 = cur.fetchone(); c4, m4 = r4[0], r4[1]

    cur.execute("SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = 'POWER_LOTTO'")
    rp = cur.fetchone(); cp, mp = rp[0], rp[1]

    conn.close()

    ok = True
    drift = []
    if replay_rows != EXPECTED_REPLAY_ROWS:
        drift.append(f"replay_rows={replay_rows} expected={EXPECTED_REPLAY_ROWS}"); ok = False
    if c3 != EXPECTED_3STAR_COUNT:
        drift.append(f"3_STAR count={c3} expected={EXPECTED_3STAR_COUNT}"); ok = False
    if m3 != EXPECTED_3STAR_MAX:
        drift.append(f"3_STAR max={m3} expected={EXPECTED_3STAR_MAX}"); ok = False
    if c4 != EXPECTED_4STAR_COUNT:
        drift.append(f"4_STAR count={c4} expected={EXPECTED_4STAR_COUNT}"); ok = False
    if m4 != EXPECTED_4STAR_MAX:
        drift.append(f"4_STAR max={m4} expected={EXPECTED_4STAR_MAX}"); ok = False
    if cp != EXPECTED_POWER_COUNT:
        drift.append(f"POWER count={cp} expected={EXPECTED_POWER_COUNT}"); ok = False
    if mp != EXPECTED_POWER_MAX:
        drift.append(f"POWER max={mp} expected={EXPECTED_POWER_MAX}"); ok = False

    if not ok:
        print(f"[P128] ABORT: DB DRIFT DETECTED: {drift}")
        sys.exit(1)

    snap = {
        "replay_rows": replay_rows,
        "3_STAR":      {"count": c3, "max_draw": m3},
        "4_STAR":      {"count": c4, "max_draw": m4},
        "POWER_LOTTO": {"count": cp, "max_draw": mp}
    }
    print(f"[P128]   replay_rows={replay_rows} — PASS")
    return snap


# ---------------------------------------------------------------------------
# Phase 2: Schema introspection
# ---------------------------------------------------------------------------
def introspect_schema() -> dict:
    print("[P128] Phase 2: schema introspection...")
    conn = _ro_conn()
    cur  = conn.cursor()

    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'")
    table_ddl = cur.fetchone()[0]

    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='strategy_prediction_replays'")
    indexes = [{"name": r[0], "sql": r[1]} for r in cur.fetchall()]

    # Check for bet_index column
    cur.execute("PRAGMA table_info(strategy_prediction_replays)")
    columns = [r[1] for r in cur.fetchall()]
    has_bet_index = "bet_index" in columns

    # Sample P94 rows for null-replay_run_id check
    cur.execute("""
        SELECT strategy_id, replay_run_id, source, COUNT(*) as cnt
        FROM strategy_prediction_replays
        WHERE source LIKE 'P94_TIERB%'
        GROUP BY strategy_id, replay_run_id, source
        ORDER BY strategy_id
    """)
    p94_groups = [{"strategy_id": r[0], "replay_run_id": r[1], "source": r[2], "count": r[3]}
                  for r in cur.fetchall()]

    all_null_replay_run_id = all(g["replay_run_id"] is None for g in p94_groups)

    # Current UNIQUE constraint extraction
    import re
    unique_matches = re.findall(r'UNIQUE\(([^)]+)\)', table_ddl)
    current_unique_constraints = unique_matches

    conn.close()

    result = {
        "table_ddl_excerpt": table_ddl[:1200],
        "columns": columns,
        "has_bet_index_column": has_bet_index,
        "indexes": [i["name"] for i in indexes],
        "current_unique_constraints": current_unique_constraints,
        "p94_tierb_groups": p94_groups,
        "all_p94_replay_run_id_null": all_null_replay_run_id,
        "sqlite_null_uniqueness_note": (
            "SQLite treats NULL values as distinct in UNIQUE constraints. "
            "All P94 Tier-B rows have replay_run_id=NULL, which technically permits "
            "multiple rows per (lottery_type, target_draw, strategy_id) with NULL replay_run_id. "
            "This is accidental behavior — NOT a valid storage convention."
        )
    }
    print(f"[P128]   has_bet_index={has_bet_index}, unique={current_unique_constraints}, p94_groups={len(p94_groups)}")
    return result


# ---------------------------------------------------------------------------
# Phase 3: Load prerequisites
# ---------------------------------------------------------------------------
def load_prerequisites() -> dict:
    print("[P128] Phase 3: loading P124/P125/P126 artifacts...")
    results = {}
    for name, path in [("p124", P124_ARTIFACT), ("p125", P125_ARTIFACT), ("p126", P126_ARTIFACT)]:
        if not path.exists():
            print(f"[P128] ABORT: missing artifact {path}")
            sys.exit(1)
        with open(path) as f:
            results[name] = json.load(f)
        print(f"[P128]   loaded {name} — classification={results[name].get('classification', '?')}")

    # Validate P126 classification
    p126 = results["p126"]
    if p126.get("classification") != "P126_DRY_RUN_PLAN_READY":
        print(f"[P128] ABORT: P126 classification mismatch: {p126.get('classification')}")
        sys.exit(1)
    if p126.get("summary", {}).get("total_new_rows_if_all_applied") != P126_EXPECTED_NEW_ROWS:
        print(f"[P128] ABORT: P126 new_rows mismatch: {p126.get('summary',{}).get('total_new_rows_if_all_applied')}")
        sys.exit(1)

    return results


# ---------------------------------------------------------------------------
# Phase 4: Build storage options analysis
# ---------------------------------------------------------------------------
def build_storage_options(schema: dict) -> list:
    print("[P128] Phase 4: building storage options analysis...")

    options = [
        {
            "option_id": "A",
            "title": "Schema Migration: add bet_index column + update UNIQUE constraint",
            "approach": "one_row_per_bet_with_schema_migration",
            "description": (
                "ADD COLUMN bet_index INTEGER NOT NULL DEFAULT 1 to strategy_prediction_replays. "
                "Replace UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id) with "
                "UNIQUE(lottery_type, target_draw, strategy_id, bet_index). "
                "Existing rows get bet_index=1 automatically via DEFAULT. "
                "New multi-bet rows inserted as bet_index=2, 3, ... per draw."
            ),
            "pros": [
                "Clean, normalized, permanent solution",
                "Enables GROUP BY bet_index for per-bet analysis",
                "Removes dependency on NULL replay_run_id accident",
                "Provenance hash can be scoped per bet",
                "Future-proof for N-bet strategies (N up to ~10 safely)",
                "Duplicate prevention via UNIQUE is enforced by DB engine"
            ],
            "cons": [
                "Requires SQLite 12-step table recreation (CREATE NEW → COPY → DROP → RENAME)",
                "Schema migration must be formally authorized and executed before P126 apply",
                "Adds 4 bytes per row (INTEGER column)",
                "API/UI consumers must be updated to filter by bet_index=1 for single-bet views"
            ],
            "migration_required": True,
            "p126_apply_readiness": "READY after migration executed and Kelvin auth phrases provided",
            "recommended": True
        },
        {
            "option_id": "B",
            "title": "Interim workaround: encode bet_index in source/controlled_apply_id + exploit NULL uniqueness",
            "approach": "one_row_per_bet_no_schema_change",
            "description": (
                "No schema change. Encode bet index in existing text fields: "
                "source='P94_TIERB_CONTROLLED_APPLY_BET_2', "
                "controlled_apply_id='P94_TIERB_CONTROLLED_APPLY_20260526_BET_2'. "
                "Relies on SQLite's NULL-distinct behavior in UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id) "
                "since all P94 rows have replay_run_id=NULL — so multiple rows per key can coexist."
            ),
            "pros": [
                "No migration needed — can proceed to P126 apply immediately",
                "Zero risk of table recreation failure",
                "Bet index is encoded and recoverable via source field parsing"
            ],
            "cons": [
                "Exploits accidental SQLite NULL-distinct behavior — fragile if any row ever has non-NULL replay_run_id",
                "No formal bet_index column — queries require LIKE 'BET_%' parsing",
                "Downstream API/UI consumers see duplicate (strategy, draw) pairs with no structural differentiator",
                "Provenance hash is per-strategy not per-bet — ambiguous for multi-bet dedup",
                "Technical debt: must be resolved by Option A eventually",
                "Risk of silent duplicate inserts if NULL behavior assumption breaks"
            ],
            "migration_required": False,
            "p126_apply_readiness": "CONDITIONALLY READY — requires explicit Kelvin authorization of workaround",
            "recommended": False
        },
        {
            "option_id": "C",
            "title": "Array-of-arrays per row (compact multi-bet)",
            "approach": "multi_bet_json_array_in_predicted_numbers",
            "description": (
                "Store all bets for a single (strategy, draw) in one row by encoding "
                "predicted_numbers as JSON array-of-arrays: [[bet1], [bet2], [bet3]]. "
                "One row per (strategy, draw) preserved."
            ),
            "pros": [
                "Preserves one-row-per-draw semantics",
                "Zero schema migration required",
                "No UNIQUE constraint changes needed"
            ],
            "cons": [
                "BREAKS all existing consumers — predicted_numbers is currently a flat JSON array",
                "hit_count, hit_numbers columns become ambiguous (which bet?)",
                "Cannot analyze per-bet performance independently",
                "Requires rewriting all API endpoints, analysis scripts, dashboard",
                "Breaks P94 existing rows — would need data migration",
                "High risk, high cost, zero benefit for current scale"
            ],
            "migration_required": True,
            "p126_apply_readiness": "NOT RECOMMENDED — too disruptive",
            "recommended": False
        }
    ]

    print(f"[P128]   {len(options)} storage options analyzed — recommended: Option A")
    return options


# ---------------------------------------------------------------------------
# Phase 5: Build migration plan
# ---------------------------------------------------------------------------
def build_migration_plan() -> dict:
    return {
        "migration_type": "SQLite_12_step_table_recreation",
        "target_schema_changes": [
            {
                "change": "add_column",
                "column": "bet_index",
                "type": "INTEGER",
                "not_null": True,
                "default": 1,
                "note": "All existing rows will receive bet_index=1 via DEFAULT"
            },
            {
                "change": "replace_unique_constraint",
                "old_unique": "UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)",
                "new_unique": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
                "note": "replay_run_id removed from UNIQUE; bet_index added for per-bet dedup"
            }
        ],
        "steps": [
            {
                "step": 1,
                "sql": "PRAGMA foreign_keys = OFF",
                "purpose": "Disable FK checks during table recreation"
            },
            {
                "step": 2,
                "sql": "BEGIN TRANSACTION",
                "purpose": "Atomic migration"
            },
            {
                "step": 3,
                "sql": (
                    "CREATE TABLE strategy_prediction_replays_new (\n"
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                    "  lottery_type TEXT NOT NULL,\n"
                    "  target_draw TEXT NOT NULL,\n"
                    "  target_date TEXT,\n"
                    "  strategy_id TEXT NOT NULL,\n"
                    "  strategy_name TEXT,\n"
                    "  strategy_version TEXT,\n"
                    "  history_cutoff_draw TEXT,\n"
                    "  replay_status TEXT NOT NULL,\n"
                    "  reject_reason TEXT,\n"
                    "  predicted_numbers TEXT,\n"
                    "  predicted_special INTEGER,\n"
                    "  actual_numbers TEXT,\n"
                    "  actual_special INTEGER,\n"
                    "  hit_numbers TEXT,\n"
                    "  hit_count INTEGER DEFAULT 0,\n"
                    "  special_hit INTEGER DEFAULT 0,\n"
                    "  replay_run_id INTEGER,\n"
                    "  generated_at TEXT DEFAULT (datetime('now')),\n"
                    "  truth_level TEXT DEFAULT NULL,\n"
                    "  controlled_apply_id TEXT DEFAULT NULL,\n"
                    "  source TEXT DEFAULT NULL,\n"
                    "  provenance_hash TEXT DEFAULT NULL,\n"
                    "  provenance_source TEXT DEFAULT NULL,\n"
                    "  dry_run INTEGER DEFAULT 0,\n"
                    "  prediction_cutoff_date TEXT,\n"
                    "  prediction_generated_at TEXT,\n"
                    "  bet_index INTEGER NOT NULL DEFAULT 1,\n"
                    "  UNIQUE(lottery_type, target_draw, strategy_id, bet_index),\n"
                    "  FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id)\n"
                    ")"
                ),
                "purpose": "Create new table with bet_index and updated UNIQUE constraint"
            },
            {
                "step": 4,
                "sql": (
                    "INSERT INTO strategy_prediction_replays_new "
                    "SELECT id, lottery_type, target_draw, target_date, strategy_id, "
                    "strategy_name, strategy_version, history_cutoff_draw, replay_status, "
                    "reject_reason, predicted_numbers, predicted_special, actual_numbers, "
                    "actual_special, hit_numbers, hit_count, special_hit, replay_run_id, "
                    "generated_at, truth_level, controlled_apply_id, source, provenance_hash, "
                    "provenance_source, dry_run, prediction_cutoff_date, prediction_generated_at, "
                    "1 AS bet_index "
                    "FROM strategy_prediction_replays"
                ),
                "purpose": "Copy all existing rows with bet_index=1"
            },
            {
                "step": 5,
                "sql": "DROP TABLE strategy_prediction_replays",
                "purpose": "Remove old table"
            },
            {
                "step": 6,
                "sql": "ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays",
                "purpose": "Rename new table to production name"
            },
            {
                "step": 7,
                "sql": "CREATE INDEX idx_spr_lottery ON strategy_prediction_replays(lottery_type)",
                "purpose": "Recreate index"
            },
            {
                "step": 8,
                "sql": "CREATE INDEX idx_spr_strategy ON strategy_prediction_replays(strategy_id)",
                "purpose": "Recreate index"
            },
            {
                "step": 9,
                "sql": "CREATE INDEX idx_spr_draw ON strategy_prediction_replays(target_draw)",
                "purpose": "Recreate index"
            },
            {
                "step": 10,
                "sql": "CREATE INDEX idx_spr_status ON strategy_prediction_replays(replay_status)",
                "purpose": "Recreate index"
            },
            {
                "step": 11,
                "sql": "CREATE INDEX idx_spr_run ON strategy_prediction_replays(replay_run_id)",
                "purpose": "Recreate index"
            },
            {
                "step": 12,
                "sql": "CREATE INDEX idx_spr_hit ON strategy_prediction_replays(hit_count)",
                "purpose": "Recreate index"
            },
            {
                "step": 13,
                "sql": "CREATE INDEX idx_spr_controlled_apply_id ON strategy_prediction_replays(controlled_apply_id)",
                "purpose": "Recreate index"
            },
            {
                "step": 14,
                "sql": "CREATE INDEX idx_spr_truth_level ON strategy_prediction_replays(truth_level)",
                "purpose": "Recreate index"
            },
            {
                "step": 15,
                "sql": "CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index)",
                "purpose": "New index for bet_index filtering"
            },
            {
                "step": 16,
                "sql": "COMMIT",
                "purpose": "Commit atomic migration"
            },
            {
                "step": 17,
                "sql": "PRAGMA foreign_keys = ON",
                "purpose": "Re-enable FK constraints"
            },
            {
                "step": 18,
                "sql": "SELECT COUNT(*) FROM strategy_prediction_replays",
                "purpose": "Post-migration invariant check — must equal 54462"
            }
        ],
        "preconditions_before_execution": [
            "Kelvin explicitly authorizes: YES authorize migration_plan_p128 because <reason>",
            "DB backup created and verified before execution",
            "All current DB invariants confirmed: replay_rows=54462",
            "No active replay job or write transaction on DB",
            "Drift guard expected count updated to 54462 + new_rows after migration + apply"
        ],
        "post_migration_invariants": [
            "SELECT COUNT(*) FROM strategy_prediction_replays = 54462 (unchanged)",
            "All existing rows have bet_index = 1",
            "UNIQUE constraint is (lottery_type, target_draw, strategy_id, bet_index)",
            "All 8 original indexes + idx_spr_bet_index exist",
            "SQLite PRAGMA integrity_check = ok"
        ],
        "authorization_required": True,
        "authorization_phrase": "YES authorize migration_plan_p128 because <reason>",
        "not_executed_in_p128": True
    }


# ---------------------------------------------------------------------------
# Phase 6: Build duplicate key contract
# ---------------------------------------------------------------------------
def build_duplicate_key_contract() -> dict:
    return {
        "primary_unique_constraint": {
            "columns": ["lottery_type", "target_draw", "strategy_id", "bet_index"],
            "description": (
                "After migration: UNIQUE(lottery_type, target_draw, strategy_id, bet_index). "
                "Each (strategy, draw, bet slot) is exactly one row. "
                "Insert of duplicate (strategy, draw, bet_index) is rejected by DB engine."
            ),
            "current_constraint_before_migration": "UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)",
            "migration_required_to_enforce": True
        },
        "provenance_hash_guard": {
            "column": "provenance_hash",
            "description": (
                "provenance_hash must be set per inserted row. "
                "For multi-bet rows: provenance_hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers + controlled_apply_id). "
                "Pre-insert check: if (lottery_type, target_draw, strategy_id, bet_index, provenance_hash) already exists, skip (idempotent)."
            ),
            "hash_input_fields": ["strategy_id", "target_draw", "bet_index", "predicted_numbers", "controlled_apply_id"]
        },
        "predicted_numbers_fingerprint": {
            "description": (
                "predicted_numbers stored as JSON-sorted array string. "
                "Fingerprint = SHA256 of sorted predicted_numbers string. "
                "Two bets with same numbers for same draw = logical duplicate, must be rejected."
            ),
            "fingerprint_check": "Reject if (strategy_id, target_draw, bet_index, sorted(predicted_numbers)) already exists"
        },
        "full_dedup_tuple": [
            "lottery_type",
            "target_draw",
            "strategy_id",
            "bet_index",
            "predicted_numbers_fingerprint",
            "provenance_hash"
        ],
        "dedup_enforcement_order": [
            "1. UNIQUE constraint (lottery_type, target_draw, strategy_id, bet_index) — DB level",
            "2. provenance_hash pre-insert check — application level",
            "3. predicted_numbers fingerprint check — application level",
            "4. controlled_apply_id prefix guard — application level"
        ],
        "forbidden_duplicates": [
            "Same (strategy, draw, bet_index) with different predicted_numbers = ERROR (bet slot collision)",
            "Same (strategy, draw) with same predicted_numbers for bet_index > 1 = WARN (likely duplicate bet)",
            "Any row with provenance_hash=NULL after migration = ERROR (must be set)"
        ]
    }


# ---------------------------------------------------------------------------
# Phase 7: P126 apply readiness assessment
# ---------------------------------------------------------------------------
def build_p126_apply_readiness(schema: dict) -> dict:
    all_candidates = [
        {"strategy_id": "biglotto_echo_aware_3bet",      "lottery_type": "BIG_LOTTO",   "target_bets": 3, "new_rows": 3000, "auth_phrase": "YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>"},
        {"strategy_id": "daily539_f4cold_5bet",           "lottery_type": "DAILY_539",   "target_bets": 5, "new_rows": 6000, "auth_phrase": "YES authorize controlled_apply for daily539_f4cold_5bet because <reason>"},
        {"strategy_id": "daily539_f4cold_3bet",           "lottery_type": "DAILY_539",   "target_bets": 3, "new_rows": 3000, "auth_phrase": "YES authorize controlled_apply for daily539_f4cold_3bet because <reason>"},
        {"strategy_id": "power_fourier_rhythm_2bet",      "lottery_type": "POWER_LOTTO", "target_bets": 2, "new_rows": 1500, "auth_phrase": "YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>"},
        {"strategy_id": "biglotto_ts3_markov_4bet_w30",  "lottery_type": "BIG_LOTTO",   "target_bets": 4, "new_rows": 4500, "auth_phrase": "YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>"},
    ]

    total_new_rows    = sum(c["new_rows"] for c in all_candidates)
    rows_after_apply  = EXPECTED_REPLAY_ROWS + total_new_rows

    preconditions = [
        {
            "check": "p128_migration_executed",
            "status": "PENDING",
            "detail": "Schema migration must be authorized and executed before P126 apply. P128 design is now complete; migration plan is ready."
        },
        {
            "check": "kelvin_migration_authorization",
            "status": "REQUIRED",
            "detail": "Kelvin must state: YES authorize migration_plan_p128 because <reason>"
        },
        {
            "check": "kelvin_per_strategy_authorization_phrases",
            "status": "REQUIRED",
            "detail": "5 individual authorization phrases required — one per strategy",
            "phrases_required": [c["auth_phrase"] for c in all_candidates]
        },
        {
            "check": "drift_guard_expected_count_update",
            "status": "REQUIRED",
            "detail": f"replay_lifecycle_drift_guard.py expected count must be updated to {rows_after_apply} after apply"
        },
        {
            "check": "db_backup_before_migration",
            "status": "REQUIRED",
            "detail": "Backup lottery_api/data/lottery_v2.db before executing migration plan"
        },
        {
            "check": "api_ui_consumer_review",
            "status": "RECOMMENDED",
            "detail": "RSR-4: API endpoints and dashboard should be updated to filter bet_index=1 for single-bet views before or in parallel with apply"
        }
    ]

    return {
        "p128_resolved_rsr": ["RSR-1", "RSR-2"],
        "rsr_remaining": ["RSR-3 (drift guard update — after apply)", "RSR-4 (API/UI consumer update — can be parallel)"],
        "overall_readiness": "CONDITIONALLY_READY",
        "readiness_detail": (
            "P128 design is complete and resolves RSR-1 (storage format decided: one-row-per-bet with bet_index column) "
            "and RSR-2 (bet_index column defined with migration plan). "
            "P126 apply is CONDITIONALLY READY pending: (1) migration authorization, (2) migration execution, "
            "(3) per-strategy authorization phrases from Kelvin."
        ),
        "total_new_rows_if_applied": total_new_rows,
        "total_rows_after_apply": rows_after_apply,
        "candidates": all_candidates,
        "preconditions": preconditions,
        "db_writes_in_p128": 0,
        "migration_not_executed_in_p128": True
    }


# ---------------------------------------------------------------------------
# Phase 8: Build governance block
# ---------------------------------------------------------------------------
def build_governance() -> dict:
    return {
        "db_writes": 0,
        "schema_changes_executed": False,
        "scheduler_installed": False,
        "strategy_promoted": False,
        "fabricated_rows": 0,
        "4_STAR_included": False,
        "P108_executed": False,
        "P117_executed": False,
        "P118_executed": False,
        "p126_apply_executed": False,
        "pragma_query_only": "ON (enforced on every DB connection)",
        "forbidden_files_staged": False,
        "migration_plan_status": "DESIGN_ONLY_NOT_EXECUTED"
    }


# ---------------------------------------------------------------------------
# Phase 9: Build blocked/excluded list
# ---------------------------------------------------------------------------
def build_blocked_excluded() -> list:
    return [
        {"item": "4_STAR", "reason": "Explicitly excluded from all Tier-B multi-bet work per governance"},
        {"item": "P108",   "reason": "P108 execution blocked — not within P128 scope"},
        {"item": "P117",   "reason": "P117 execution blocked — not within P128 scope"},
        {"item": "P118",   "reason": "P118 execution blocked — not within P128 scope"},
        {"item": "rejected_strategies", "reason": "No rejected strategies may be promoted or included in multi-bet apply"},
        {"item": "strategy_promotion",  "reason": "No lifecycle/champion/registry mutation in P128"},
        {"item": "scheduler_cron_launchd", "reason": "No scheduler installation in P128"},
        {"item": "db_writes",          "reason": "P128 is design-only — zero DB writes permitted"},
        {"item": "migration_execution", "reason": "Migration plan defined but not executed — requires separate authorization"},
        {"item": "p126_apply",         "reason": "P126 apply not executed in P128 — RSR-1/RSR-2 now resolved by design; execution requires authorization"}
    ]


# ---------------------------------------------------------------------------
# Phase 10: Write JSON artifact
# ---------------------------------------------------------------------------
def write_json(data: dict) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[P128] JSON written → {OUT_JSON}")


# ---------------------------------------------------------------------------
# Phase 11: Write Markdown artifact
# ---------------------------------------------------------------------------
def write_md(data: dict) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    schema     = data["schema_introspection"]
    opts       = data["storage_options_considered"]
    rec        = data["recommended_storage_design"]
    one_rpb    = data["one_row_per_bet_decision"]
    dup        = data["duplicate_key_contract"]
    mig        = data["migration_plan_if_needed"]
    readiness  = data["p126_apply_readiness_after_p128"]
    governance = data["governance"]
    blocked    = data["blocked_or_excluded"]
    snap_b     = data["db_snapshot_before"]
    snap_a     = data["db_snapshot_after"]

    auth_phrases = readiness["preconditions"][2]["phrases_required"]
    migration_auth = mig["authorization_phrase"]

    lines = [
        f"# P128: Native Multi-Bet Replay Storage Design",
        f"",
        f"**Classification:** `{data['classification']}`",
        f"**Task ID:** {data['task_id']}",
        f"**Generated:** {data['generated_at']}",
        f"**DB rows before / after:** {snap_b['replay_rows']} / {snap_a['replay_rows']} (no writes)",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"P128 formally decides the native multi-bet replay storage format, resolving the RSR-1 and RSR-2 blockers",
        f"identified in P126. The recommended design is **one-row-per-bet with a schema migration** that adds a",
        f"`bet_index` column and updates the UNIQUE constraint.",
        f"",
        f"Key decisions:",
        f"- ✅ **one-row-per-bet convention APPROVED** as the storage model",
        f"- ✅ **bet_index column required** — migration plan defined (not executed in P128)",
        f"- ✅ **Duplicate key contract defined**: `(lottery_type, target_draw, strategy_id, bet_index)` as UNIQUE",
        f"- ✅ **P126 apply is CONDITIONALLY READY** pending migration authorization + per-strategy auth phrases from Kelvin",
        f"- 🚫 **Zero DB writes** in P128 — design only",
        f"",
        f"---",
        f"",
        f"## 2. P124 / P125 / P126 Recap",
        f"",
        f"| Task | Classification | Key Output |",
        f"|---|---|---|",
        f"| P124 | `P124_COVERAGE_MATRIX_READY` | 36-row matrix; 5 candidates with `available` adapters |",
        f"| P125 | `P125_ADAPTER_GAP_PLAN_READY` | 12 adapters need `get_all_bets()`; 5 Tier-B candidates identified |",
        f"| P126 | `P126_DRY_RUN_PLAN_READY` | +18000 rows estimated if all 5 applied; blocked by RSR-1 (no bet_index) |",
        f"",
        f"P126 found that the current schema has no `bet_index` column and the UNIQUE constraint",
        f"`(lottery_type, target_draw, strategy_id, replay_run_id)` does not support multi-bet rows cleanly.",
        f"P128 resolves this.",
        f"",
        f"---",
        f"",
        f"## 3. Why P128 Is Required Before Apply",
        f"",
        f"Current schema UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)`",
        f"",
        f"All 5 P94 Tier-B strategies have `replay_run_id = NULL`. SQLite treats NULLs as distinct in UNIQUE",
        f"constraints, which technically allows inserting multiple rows per `(strategy, draw)` when `replay_run_id`",
        f"is NULL. However:",
        f"",
        f"1. **Accidental behavior** — relying on NULL-distinct semantics is a fragile side effect, not a contract",
        f"2. **No bet_index column** — without it, there is no way to distinguish bet-1, bet-2, bet-N in queries",
        f"3. **Consumer breakage** — API and dashboard assume one row per `(strategy, draw)`; multi-bet rows appear as duplicates",
        f"4. **Dedup is impossible** — without bet_index, the duplicate key contract cannot be enforced at the DB level",
        f"",
        f"P128 defines the permanent solution.",
        f"",
        f"---",
        f"",
        f"## 4. Storage Options Considered",
        f"",
        f"| Option | Approach | Migration? | Recommended |",
        f"|---|---|---|---|",
    ]

    for opt in opts:
        rec_mark = "✅ YES" if opt["recommended"] else "❌ NO"
        lines.append(f"| {opt['option_id']} | {opt['title']} | {'Yes' if opt['migration_required'] else 'No'} | {rec_mark} |")

    lines += [
        f"",
        f"### Option A (Recommended): Schema Migration",
        f"",
        f"Add `bet_index INTEGER NOT NULL DEFAULT 1` column.",
        f"Replace UNIQUE constraint with `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`.",
        f"All existing rows receive `bet_index=1` automatically via DEFAULT.",
        f"",
        f"**Pros:** Clean, normalized, permanent, queryable, enforced at DB level.",
        f"**Cons:** Requires SQLite 12-step table recreation (one-time operation); API consumers need to add `bet_index=1` filter for single-bet views.",
        f"",
        f"### Option B: Interim workaround (NULL replay_run_id exploit)",
        f"",
        f"Encode bet_index in `source`/`controlled_apply_id` fields. Relies on SQLite NULL-distinct behavior.",
        f"",
        f"**Pros:** No migration needed.",
        f"**Cons:** Fragile, no formal bet_index column, breaks consumer queries, technical debt, not maintainable.",
        f"",
        f"### Option C: Array-of-arrays per row",
        f"",
        f"Store all bets as JSON array-of-arrays in `predicted_numbers`.",
        f"",
        f"**Cons:** Breaks all existing consumers, requires data migration of existing rows, no per-bet analysis. **NOT recommended.**",
        f"",
        f"---",
        f"",
        f"## 5. Recommended Design",
        f"",
        f"**Option A: one-row-per-bet with bet_index schema migration.**",
        f"",
        f"| Aspect | Decision |",
        f"|---|---|",
        f"| Storage model | one-row-per-bet |",
        f"| bet_index column | Required — INTEGER NOT NULL DEFAULT 1 |",
        f"| UNIQUE constraint | (lottery_type, target_draw, strategy_id, bet_index) |",
        f"| Existing rows | Unchanged — all receive bet_index=1 via migration |",
        f"| New multi-bet rows | bet_index=2, 3, ... N per draw |",
        f"| Row count after migration | 54462 (unchanged — migration copies, does not add) |",
        f"",
        f"---",
        f"",
        f"## 6. One-Row-Per-Bet Convention Decision",
        f"",
        f"**APPROVED**: one-row-per-bet is the canonical storage convention for multi-bet replay rows.",
        f"",
        f"Rationale:",
        f"- Consistent with existing single-bet rows (bet_index=1 = current rows)",
        f"- Enables per-bet hit analysis, per-bet performance comparison",
        f"- Preserves all existing query patterns with `WHERE bet_index = 1`",
        f"- Scales to N-bet strategies (N up to ~10 safely; higher N requires storage impact review)",
        f"- P126's +18,000 row estimate is based on this convention and is correct",
        f"",
        f"---",
        f"",
        f"## 7. Bet Index Representation",
        f"",
        f"| Field | Value | Note |",
        f"|---|---|---|",
        f"| `bet_index` column | `1` (existing bet) / `2`, `3`, ... N (new bets) | New column after migration |",
        f"| `controlled_apply_id` | `P94_TIERB_CONTROLLED_APPLY_20260526` | Same for all bets (identifies apply batch) |",
        f"| `source` | `P94_TIERB_CONTROLLED_APPLY` | Same for all bets |",
        f"| `provenance_hash` | SHA256(strategy_id + target_draw + bet_index + predicted_numbers + controlled_apply_id) | Per-bet hash |",
        f"",
        f"**No encoding hack needed** — bet_index is a proper column after migration.",
        f"Interim (before migration): if Option B workaround is authorized, encode as `source = 'P94_TIERB_CONTROLLED_APPLY_BET_N'`",
        f"and note the technical debt in the apply record.",
        f"",
        f"---",
        f"",
        f"## 8. Duplicate / Provenance Guard Contract",
        f"",
        f"Full dedup tuple: `(lottery_type, target_draw, strategy_id, bet_index, predicted_numbers_fingerprint, provenance_hash)`",
        f"",
        f"| Layer | Mechanism | Enforcement |",
        f"|---|---|---|",
        f"| 1 | UNIQUE(lottery_type, target_draw, strategy_id, bet_index) | DB engine — rejects on INSERT |",
        f"| 2 | provenance_hash pre-insert check | Application level — skip if hash exists |",
        f"| 3 | predicted_numbers fingerprint | Application level — reject same numbers for same bet_index |",
        f"| 4 | controlled_apply_id prefix guard | Application level — must match P94_TIERB_CONTROLLED_APPLY prefix |",
        f"",
        f"Forbidden duplicates:",
        f"- Same (strategy, draw, bet_index) with different predicted_numbers → ERROR (bet slot collision)",
        f"- Same (strategy, draw) with same predicted_numbers for bet_index > 1 → WARN (likely duplicate bet)",
        f"- Any row with provenance_hash=NULL after migration → ERROR",
        f"",
        f"---",
        f"",
        f"## 9. Migration Plan",
        f"",
        f"**Migration type:** SQLite 12-step table recreation (standard SQLite migration pattern).",
        f"**Status in P128:** DESIGN ONLY — not executed.",
        f"**Authorization required:** `{migration_auth}`",
        f"",
        f"### Migration Steps (18 steps)",
        f"",
        f"| Step | SQL | Purpose |",
        f"|---|---|---|",
    ]

    for step in mig["steps"]:
        sql_short = step["sql"][:80].replace("|", "\\|") + ("..." if len(step["sql"]) > 80 else "")
        lines.append(f"| {step['step']} | `{sql_short}` | {step['purpose']} |")

    lines += [
        f"",
        f"### Pre-conditions before execution",
        f"",
    ]
    for pre in mig["preconditions_before_execution"]:
        lines.append(f"- {pre}")

    lines += [
        f"",
        f"### Post-migration invariants",
        f"",
    ]
    for inv in mig["post_migration_invariants"]:
        lines.append(f"- {inv}")

    lines += [
        f"",
        f"---",
        f"",
        f"## 10. P126 Apply Readiness After P128",
        f"",
        f"**Overall readiness:** `{readiness['overall_readiness']}`",
        f"",
        readiness["readiness_detail"],
        f"",
        f"### Row delta (if all 5 P126 candidates applied)",
        f"",
        f"| Strategy | Lottery | Bets | +New Rows | After Apply |",
        f"|---|---|---|---|---|",
    ]

    cum = EXPECTED_REPLAY_ROWS
    for c in readiness["candidates"]:
        cum_after = cum + c["new_rows"]
        lines.append(f"| `{c['strategy_id']}` | {c['lottery_type']} | {c['target_bets']} | +{c['new_rows']} | — |")

    lines += [
        f"| **TOTAL** | | | **+{readiness['total_new_rows_if_applied']}** | **{readiness['total_rows_after_apply']}** |",
        f"",
        f"### Preconditions for P126 apply",
        f"",
    ]
    for pre in readiness["preconditions"]:
        lines.append(f"- **{pre['check']}** [{pre['status']}]: {pre['detail']}")

    lines += [
        f"",
        f"### Required authorization phrases (DO NOT apply until provided)",
        f"",
        f"```",
        f"{migration_auth}",
    ]
    for phrase in auth_phrases:
        lines.append(phrase)
    lines += [
        f"```",
        f"",
        f"---",
        f"",
        f"## 11. Explicit Non-Actions",
        f"",
        f"The following were NOT performed in P128:",
        f"",
    ]
    for item in blocked:
        lines.append(f"- 🚫 **{item['item']}**: {item['reason']}")

    lines += [
        f"",
        f"---",
        f"",
        f"## 12. Final Classification",
        f"",
        f"```",
        f"task_id      : {data['task_id']}",
        f"classification: {data['classification']}",
        f"db_rows_before: {snap_b['replay_rows']}",
        f"db_rows_after : {snap_a['replay_rows']}",
        f"db_writes     : 0",
        f"migration_status: DESIGN_ONLY_NOT_EXECUTED",
        f"p126_readiness: CONDITIONALLY_READY",
        f"```",
        f"",
        f"```text",
        f"P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY",
        f"```",
        f"",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print(f"[P128] MD  written → {OUT_MD}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"[P128] === P128 Native Multi-Bet Replay Storage Design ===")
    generated_at = datetime.now(timezone.utc).isoformat()

    # Phase 1: DB invariants
    snap = verify_db_invariants()

    # Phase 2: Schema introspection
    schema = introspect_schema()

    # Phase 3: Load prerequisites
    prereqs = load_prerequisites()

    # Phase 4: Storage options
    storage_opts = build_storage_options(schema)

    # Phase 5: Migration plan
    migration_plan = build_migration_plan()

    # Phase 6: Duplicate key contract
    dup_contract = build_duplicate_key_contract()

    # Phase 7: P126 apply readiness
    p126_readiness = build_p126_apply_readiness(schema)

    # Phase 8: Governance
    governance = build_governance()

    # Phase 9: Blocked
    blocked = build_blocked_excluded()

    # Phase 10: One-row-per-bet decision
    one_rpb_decision = {
        "decision": "APPROVED",
        "convention": "one_row_per_bet",
        "bet_index_column_required": True,
        "rationale": [
            "Consistent with existing single-bet rows (all existing = bet_index=1)",
            "Enables per-bet hit analysis and per-bet performance comparison",
            "Preserves all existing query patterns with WHERE bet_index = 1 filter",
            "P126 +18000 row estimate based on this convention is validated",
            "Scales linearly with bet count — no structural limits for N<=10"
        ],
        "approved_for_p126_apply": True,
        "approval_condition": "Subject to: migration authorization + per-strategy Kelvin authorization"
    }

    # Phase 11: P126 source summary
    p126_src = prereqs["p126"]
    p126_summary = {
        "classification": p126_src["classification"],
        "candidate_count": p126_src["summary"]["candidate_count"],
        "total_new_rows_if_all_applied": p126_src["summary"]["total_new_rows_if_all_applied"],
        "total_replay_rows_after_all_applied": p126_src["summary"]["total_replay_rows_after_all_applied"],
        "all_prov_guard_pass": p126_src["summary"]["all_candidates_prov_guard_pass"],
        "all_dup_guard_pass": p126_src["summary"]["all_candidates_dup_guard_pass"],
        "p128_pending_was": True,
        "p128_now_resolved": True
    }

    # Recommended storage design summary
    recommended = {
        "option_selected": "A",
        "title": "one-row-per-bet with bet_index schema migration",
        "approach": "one_row_per_bet_with_schema_migration",
        "bet_index_column": "bet_index INTEGER NOT NULL DEFAULT 1",
        "new_unique_constraint": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
        "migration_required": True,
        "existing_rows_impacted": "All 54462 rows receive bet_index=1 via DEFAULT — no data change",
        "row_count_after_migration": EXPECTED_REPLAY_ROWS
    }

    # Assemble artifact
    artifact = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": generated_at,
        "p124_source_artifact": str(P124_ARTIFACT.relative_to(REPO_ROOT)),
        "p125_source_artifact": str(P125_ARTIFACT.relative_to(REPO_ROOT)),
        "p126_source_artifact": str(P126_ARTIFACT.relative_to(REPO_ROOT)),
        "db_snapshot_before": snap,
        "db_snapshot_after": snap,   # read-only — identical
        "schema_introspection": schema,
        "p126_source_summary": p126_summary,
        "storage_options_considered": storage_opts,
        "recommended_storage_design": recommended,
        "one_row_per_bet_decision": one_rpb_decision,
        "bet_index_representation": {
            "column_name": "bet_index",
            "column_type": "INTEGER NOT NULL DEFAULT 1",
            "bet_1_meaning": "Primary bet (existing rows and first bet of any multi-bet strategy)",
            "bet_n_meaning": "Additional bets (N=2,3,...) inserted during controlled apply",
            "encoding_in_source_if_no_migration": "FALLBACK ONLY: source='P94_TIERB_CONTROLLED_APPLY_BET_N' — requires explicit Option B authorization",
            "preferred": "bet_index column (Option A migration)"
        },
        "duplicate_key_contract": dup_contract,
        "migration_plan_if_needed": migration_plan,
        "p126_apply_readiness_after_p128": p126_readiness,
        "blocked_or_excluded": blocked,
        "required_authorization_phrases": {
            "migration_authorization": migration_plan["authorization_phrase"],
            "per_strategy_apply_authorization": [
                c["auth_phrase"] for c in p126_readiness["candidates"]
            ],
            "note": "All phrases must be provided before any DB changes or apply execution"
        },
        "governance": governance,
        "summary": {
            "task_id": TASK_ID,
            "classification": CLASSIFICATION,
            "db_writes": 0,
            "schema_changes_executed": False,
            "migration_plan_status": "DESIGN_ONLY_NOT_EXECUTED",
            "p126_apply_readiness": "CONDITIONALLY_READY",
            "total_new_rows_if_p126_applied": P126_EXPECTED_NEW_ROWS,
            "total_rows_after_p126_apply": P126_EXPECTED_TOTAL_AFTER,
            "rsr_resolved": ["RSR-1", "RSR-2"],
            "rsr_remaining": ["RSR-3", "RSR-4"],
            "one_row_per_bet_approved": True,
            "bet_index_column_required": True,
            "migration_authorization_required": True,
            "per_strategy_authorization_required": True
        }
    }

    # Write artifacts
    write_json(artifact)
    write_md(artifact)

    print()
    print("[P128] === SUMMARY ===")
    print(f"  classification   : {CLASSIFICATION}")
    print(f"  db_rows          : {snap['replay_rows']} (unchanged)")
    print(f"  db_writes        : 0")
    print(f"  storage_decision : one-row-per-bet (Option A — schema migration)")
    print(f"  bet_index_req    : True")
    print(f"  migration_status : DESIGN_ONLY_NOT_EXECUTED")
    print(f"  p126_readiness   : CONDITIONALLY_READY")
    print(f"  RSR resolved     : RSR-1, RSR-2")
    print(f"  4_STAR/P108/P117/P118: BLOCKED")
    print(f"  JSON → {OUT_JSON}")
    print(f"  MD   → {OUT_MD}")
    print("[P128] DONE")


if __name__ == "__main__":
    main()
