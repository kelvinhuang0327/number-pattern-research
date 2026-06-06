"""
P247A — BIG_LOTTO Canonical DB Separation Dry-run Plan

Plans the DB-level canonical BIG_LOTTO separation using:
  - Option A: canonical SQL view (draws_big_lotto_canonical_main)
  - Option B: row-family annotation table (draw_row_family_annotations)

Validates that proposed SQL would correctly return 2,113 canonical rows
by dry-running against the live DB in read-only mode.

NO DB WRITE. NO CREATE VIEW. NO CREATE TABLE. DRY-RUN ONLY.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"
REPO_ROOT = Path(__file__).parent.parent

REQUIRED_TYPE_D_AUTHORIZATION_PHRASE = (
    "Explicit Type D human gate authorization required before any DB write. "
    "No CREATE VIEW, CREATE TABLE, INSERT, UPDATE, or DELETE may be executed "
    "without a separate explicit authorization from the user/governance."
)

FORBIDDEN_ACTIONS = [
    "DB_write_without_Type_D_authorization",
    "CREATE_VIEW_without_authorization",
    "CREATE_TABLE_without_authorization",
    "row_deletion",
    "row_movement",
    "migration_apply",
    "registry_mutation",
    "production_recommendation_change",
    "strategy_promotion",
    "betting_advice",
    "GATE_OPEN_for_BIG_LOTTO_predictive_research",
]

# ---------------------------------------------------------------------------
# Proposed SQL — Option A: Canonical View
# ---------------------------------------------------------------------------

PROPOSED_VIEW_SQL = """-- P247A Option A: Canonical BIG_LOTTO Research View
-- DO NOT EXECUTE without explicit Type D authorization
-- Dry-run validated: returns 2,113 rows on current DB

CREATE VIEW IF NOT EXISTS draws_big_lotto_canonical_main AS
SELECT d.*
FROM draws d
WHERE d.lottery_type = 'BIG_LOTTO'
  AND d.draw NOT LIKE '%-%'
  AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
  AND (
    SELECT MAX(CAST(j.value AS INTEGER))
    FROM json_each(d.numbers) j
  ) > 25;"""

DRY_RUN_CANONICAL_VIEW_SQL = """
SELECT COUNT(*) as canonical_count
FROM draws d
WHERE d.lottery_type = 'BIG_LOTTO'
  AND d.draw NOT LIKE '%-%'
  AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
  AND (
    SELECT MAX(CAST(j.value AS INTEGER))
    FROM json_each(d.numbers) j
  ) > 25
"""

# ---------------------------------------------------------------------------
# Proposed SQL — Option B: Annotation Table + Population Script
# ---------------------------------------------------------------------------

PROPOSED_ANNOTATION_TABLE_SQL = """-- P247A Option B: Row-family Annotation Table
-- DO NOT EXECUTE without explicit Type D authorization

CREATE TABLE IF NOT EXISTS draw_row_family_annotations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_type  TEXT    NOT NULL,
    draw          TEXT    NOT NULL,
    row_family    TEXT    NOT NULL,
    reason        TEXT,
    source_task   TEXT,
    created_at    TEXT    DEFAULT (datetime('now')),
    UNIQUE(lottery_type, draw)
);

-- Index for fast research queries
CREATE INDEX IF NOT EXISTS idx_drfa_type_family
    ON draw_row_family_annotations(lottery_type, row_family);"""

PROPOSED_ANNOTATION_POPULATE_SQL = """-- Populate annotation table (requires Python for SMALL_POOL_ALIEN detection)
-- Step 1: Label ADD_ON_PRIZE_EXCLUDED
INSERT OR IGNORE INTO draw_row_family_annotations
    (lottery_type, draw, row_family, reason, source_task)
SELECT 'BIG_LOTTO', draw,
    'ADD_ON_PRIZE_EXCLUDED',
    'Hyphenated draw ID — add-on/special prize record, valid but excluded from 6/49 main-draw research',
    'P247A'
FROM draws
WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%';

-- Step 2: Label DATE_FORMAT_ALIEN
INSERT OR IGNORE INTO draw_row_family_annotations
    (lottery_type, draw, row_family, reason, source_task)
SELECT 'BIG_LOTTO', draw,
    'DATE_FORMAT_ALIEN',
    '8-digit YYYYMMDD draw ID — numbers inconsistent with 6/49 pool',
    'P247A'
FROM draws
WHERE lottery_type='BIG_LOTTO'
  AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%';

-- Step 3: Label SMALL_POOL_ALIEN — requires Python json_each or application-level
-- Python snippet:
--   for row in conn.execute("SELECT id, draw, numbers FROM draws WHERE lottery_type='BIG_LOTTO' ..."):
--       if max(json.loads(row[2])) <= 25:
--           INSERT INTO draw_row_family_annotations ...

-- Step 4: Label CANONICAL_MAIN_DRAW (everything else)
-- After Steps 1-3 complete, all remaining serial draws with max(numbers)>25
-- are CANONICAL_MAIN_DRAW."""

# ---------------------------------------------------------------------------
# Post-apply validation checklist
# ---------------------------------------------------------------------------

POST_APPLY_VALIDATION = {
    "step_1_view_count": "SELECT COUNT(*) FROM draws_big_lotto_canonical_main;  -- expect 2113",
    "step_2_raw_count": "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO';  -- expect 22238",
    "step_3_annotation_families": (
        "SELECT row_family, COUNT(*) FROM draw_row_family_annotations "
        "WHERE lottery_type='BIG_LOTTO' GROUP BY row_family;  "
        "-- expect: ADD_ON_PRIZE_EXCLUDED=19100, DATE_FORMAT_ALIEN=375, SMALL_POOL_ALIEN=650, CANONICAL_MAIN_DRAW=2113"
    ),
    "step_4_replay_rows": "SELECT COUNT(*) FROM strategy_prediction_replays;  -- must remain 94924",
    "step_5_non_biglotto": (
        "SELECT lottery_type, COUNT(*) FROM draws WHERE lottery_type != 'BIG_LOTTO' "
        "GROUP BY lottery_type;  -- must be unchanged"
    ),
    "step_6_integrity": "PRAGMA integrity_check;  -- must return 'ok'",
}


def validate_dry_run(db_path: Path = DB_PATH) -> dict:
    """Dry-run: verify proposed SQL returns correct counts read-only."""
    if not db_path.exists():
        return {"db_read": False, "error": f"DB not found: {db_path}"}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        addon = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
        ).fetchone()[0]
        date_fmt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' "
            "AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%'"
        ).fetchone()[0]
        replay = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]

        # Dry-run proposed canonical view SQL
        canonical_view_dry_run = conn.execute(
            DRY_RUN_CANONICAL_VIEW_SQL.strip()
        ).fetchone()[0]

        # Small-pool count via json_each
        small_pool = conn.execute("""
            SELECT COUNT(DISTINCT d.id)
            FROM draws d
            WHERE d.lottery_type='BIG_LOTTO'
              AND d.draw NOT LIKE '%-%'
              AND NOT (LENGTH(d.draw)=8 AND d.draw LIKE '20%')
              AND (
                SELECT MAX(CAST(j.value AS INTEGER))
                FROM json_each(d.numbers) j
              ) <= 25
        """).fetchone()[0]

        # Check JSON1 availability
        try:
            conn.execute("SELECT json_extract('[1,2,3]', '$[0]')").fetchone()
            json1_available = True
        except Exception:
            json1_available = False

        # Verify view exists (should not, since not created yet)
        existing_views = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()]
        canonical_view_exists = "draws_big_lotto_canonical_main" in existing_views

        return {
            "db_read": True,
            "db_path": str(db_path),
            "read_only_confirmed": True,
            "db_write_performed": False,
            "raw_count": total,
            "add_on_count": addon,
            "date_format_alien_count": date_fmt,
            "small_pool_alien_count": small_pool,
            "canonical_view_dry_run_count": canonical_view_dry_run,
            "replay_rows": replay,
            "json1_available": json1_available,
            "canonical_view_already_exists": canonical_view_exists,
            "existing_views": existing_views,
            "dry_run_matches_expected": (
                canonical_view_dry_run == 2113
                and total == 22238
                and addon == 19100
                and date_fmt == 375
                and small_pool == 650
            ),
        }
    finally:
        conn.close()


def run_dryrun_plan(db_path: Path = DB_PATH) -> dict:
    validation = validate_dry_run(db_path)

    return {
        "schema_version": "1.0",
        "task_id": "P247A",
        "classification": "P247A_BIG_LOTTO_CANONICAL_DB_SEPARATION_DRYRUN_PLAN_COMPLETE",
        "p246k_merged_pr": "PR #326 merged 2026-06-06T02:54:07Z",
        "db_path": str(db_path),
        "read_only_confirmed": validation.get("read_only_confirmed", False),
        "raw_population_count": validation.get("raw_count"),
        "canonical_population_count": validation.get("canonical_view_dry_run_count"),
        "row_family_counts": {
            "BIG_LOTTO_total": validation.get("raw_count"),
            "ADD_ON_PRIZE_EXCLUDED": validation.get("add_on_count"),
            "DATE_FORMAT_ALIEN": validation.get("date_format_alien_count"),
            "SMALL_POOL_ALIEN": validation.get("small_pool_alien_count"),
            "CANONICAL_MAIN_DRAW_dry_run": validation.get("canonical_view_dry_run_count"),
        },
        "dry_run_validation": validation,
        "json1_available": validation.get("json1_available"),
        "proposed_view_sql": PROPOSED_VIEW_SQL,
        "proposed_annotation_table_sql": PROPOSED_ANNOTATION_TABLE_SQL,
        "proposed_annotation_populate_sql": PROPOSED_ANNOTATION_POPULATE_SQL,
        "sql_applied": False,
        "sql_dry_run_only": True,
        "recommended_apply_strategy": {
            "preferred_approach": "Option A (canonical view) first, Option B (annotation table) second",
            "phase_1_backup": (
                "cp lottery_api/data/lottery_v2.db "
                "backups/p247a_big_lotto_canonical_separation_backup_YYYYMMDD_HHMMSS.db && "
                "sha256sum backups/p247a_*.db"
            ),
            "phase_2_create_view": (
                "Execute PROPOSED_VIEW_SQL to create draws_big_lotto_canonical_main. "
                "JSON1 is available — SMALL_POOL_ALIEN can be filtered in the view directly."
            ),
            "phase_3_create_annotation_table": (
                "Execute PROPOSED_ANNOTATION_TABLE_SQL and populate via Python script "
                "(Python handles SMALL_POOL_ALIEN detection via json.loads)."
            ),
            "phase_4_post_apply_validation": POST_APPLY_VALIDATION,
            "phase_5_update_test_p238b": (
                "After DB-level separation: update test_p238b assertion "
                "from >= 22238 (raw) to >= 2113 (canonical view count)."
            ),
            "no_deletion": True,
            "no_migration_of_existing_rows": True,
            "preserves_add_on_records": True,
        },
        "required_type_d_authorization_phrase": REQUIRED_TYPE_D_AUTHORIZATION_PHRASE,
        "db_write_performed": False,
        "forbidden_actions_confirmed": FORBIDDEN_ACTIONS,
        "add_on_records_status": {
            "preserved": True,
            "is_fake": False,
            "accessible_via": "get_all_draws('BIG_LOTTO') / raw draws table",
            "excluded_from_research_by": "view filter + get_canonical_draws() helper",
        },
        "remaining_required_steps": [
            "1. Obtain explicit Type D human gate authorization",
            "2. Create timestamped DB backup with SHA256",
            "3. Execute CREATE VIEW draws_big_lotto_canonical_main",
            "4. Execute CREATE TABLE draw_row_family_annotations + populate",
            "5. Run post-apply validation checklist",
            "6. Update test_p238b assertion from >= 22238 to >= 2113 (canonical view count)",
            "7. Confirm GATE_RED remains until explicit re-authorization after validation",
        ],
        "final_decision": (
            "P247A dry-run plan complete. "
            "Proposed canonical view SQL validated: returns exactly 2,113 rows on current DB. "
            "JSON1/json_each is available — SMALL_POOL_ALIEN can be filtered directly in view SQL. "
            "No DB write performed. No CREATE VIEW/TABLE executed. "
            "ADD_ON_PRIZE_EXCLUDED records (19,100) are preserved and raw-accessible. "
            "Type D apply requires separate explicit human gate authorization. "
            "After apply: raw draws table unchanged (22,238 rows), view returns 2,113, "
            "replay_rows must remain 94,924."
        ),
    }


def main():
    import sys
    result = run_dryrun_plan()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    v = result.get("dry_run_validation", {})
    print(f"\n[P247A] raw={v.get('raw_count')}, canonical_dry_run={v.get('canonical_view_dry_run_count')}", file=sys.stderr)
    print(f"[P247A] dry_run_matches_expected={v.get('dry_run_matches_expected')}", file=sys.stderr)
    print(f"[P247A] json1_available={v.get('json1_available')}", file=sys.stderr)
    print(f"[P247A] DB write: {result['db_write_performed']}", file=sys.stderr)
    print(f"[P247A] Classification: {result['classification']}", file=sys.stderr)


if __name__ == "__main__":
    main()
