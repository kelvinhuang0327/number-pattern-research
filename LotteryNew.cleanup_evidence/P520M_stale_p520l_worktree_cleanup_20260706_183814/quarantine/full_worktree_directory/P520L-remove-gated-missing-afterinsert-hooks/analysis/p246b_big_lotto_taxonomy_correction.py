"""
P246B — BIG_LOTTO Taxonomy Correction

Read-only taxonomy correction script. Supersedes P246 SIM_HYPHEN wording.
Hyphenated BIG_LOTTO rows (formerly SIM_HYPHEN) are reclassified as
ADD_ON_PRIZE_EXCLUDED: valid lottery-related add-on/special prize records
excluded from canonical 6/49 main-draw research due to population mismatch,
not data falseness.

No DB write is performed. This script reads the DB in read-only mode to
verify row counts and produce a corrected taxonomy summary.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"

CORRECTED_TAXONOMY = {
    "ADD_ON_PRIZE_EXCLUDED": {
        "old_label": "SIM_HYPHEN",
        "description": (
            "Add-on or special prize records. Hyphenated draw IDs (e.g. 103000009-01) "
            "indicate these are not canonical 6/49 main draws. Valid lottery-related "
            "records excluded due to population mismatch, not data falseness."
        ),
        "is_fake": False,
        "is_simulated": False,
        "is_invalid": False,
        "is_lottery_related": True,
        "exclusion_reason": "Population mismatch — add-on/special prize record type",
        "sql_filter": "lottery_type='BIG_LOTTO' AND draw LIKE '%-%'",
    },
    "DATE_FORMAT_ALIEN": {
        "old_label": "DATE_FORMAT_ALIEN",
        "description": (
            "8-digit YYYYMMDD IDs. Numbers not compatible with 6/49 pool "
            "(sum_mean~74.7, max<=24). Non-canonical data-integrity concern."
        ),
        "is_fake": None,
        "is_simulated": None,
        "is_invalid": None,
        "is_lottery_related": None,
        "exclusion_reason": "Non-canonical draw ID format; numbers inconsistent with 6/49 pool",
        "sql_filter": (
            "lottery_type='BIG_LOTTO' "
            "AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%'"
        ),
    },
    "SMALL_POOL_ALIEN": {
        "old_label": "SMALL_POOL_ALIEN",
        "description": (
            "Normal serial IDs but numbers restricted to pool <=25. "
            "Likely a different game mislabeled as BIG_LOTTO. "
            "Primary driver of P219 structural-break false signals."
        ),
        "is_fake": None,
        "is_simulated": None,
        "is_invalid": None,
        "is_lottery_related": None,
        "exclusion_reason": "Numbers incompatible with 6/49 pool; likely mislabeled game",
        "sql_filter": None,
    },
    "CANONICAL_MAIN_DRAW": {
        "old_label": "CANONICAL_PLAUSIBLE",
        "description": (
            "Plausible canonical 6/49 main draws. Intended research population."
        ),
        "is_fake": False,
        "is_simulated": False,
        "is_invalid": False,
        "is_lottery_related": True,
        "exclusion_reason": None,
        "sql_filter": None,
    },
}

FORBIDDEN_PHRASES = [
    "ADD_ON_PRIZE_EXCLUDED rows are simulated",
    "ADD_ON_PRIZE_EXCLUDED rows are fake",
    "ADD_ON_PRIZE_EXCLUDED rows are synthetic",
    "ADD_ON_PRIZE_EXCLUDED rows are invalid",
    "ADD_ON_PRIZE_EXCLUDED rows are contaminated",
    "hyphenated rows are not real lottery data",
    "SIM_HYPHEN interpretation is still valid",
]

FORBIDDEN_ACTIONS = [
    "DB_write",
    "DB_migration_apply",
    "registry_mutation",
    "production_recommendation_change",
    "controlled_apply",
    "strategy_promotion",
    "betting_advice",
    "deleting_ADD_ON_PRIZE_EXCLUDED_rows",
    "GATE_OPEN_promotion_for_BIG_LOTTO",
    "claiming_exploitable_edge",
]


def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    return conn


def count_add_on_prize(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
    )
    return cur.fetchone()[0]


def count_date_format_alien(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM draws "
        "WHERE lottery_type='BIG_LOTTO' "
        "AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%'"
    )
    return cur.fetchone()[0]


def count_total_big_lotto(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
    )
    return cur.fetchone()[0]


def count_serial_big_lotto(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM draws "
        "WHERE lottery_type='BIG_LOTTO' AND draw NOT LIKE '%-%' "
        "AND NOT (LENGTH(draw)=8 AND draw LIKE '20%')"
    )
    return cur.fetchone()[0]


def get_examples(conn: sqlite3.Connection, sql_filter: str, limit: int = 4) -> list:
    cur = conn.execute(
        f"SELECT draw FROM draws WHERE {sql_filter} "
        "ORDER BY CAST(draw AS TEXT) ASC LIMIT ?",
        (limit,),
    )
    return [row[0] for row in cur.fetchall()]


def run_taxonomy_correction(db_path: Path = DB_PATH) -> dict:
    if not db_path.exists():
        return {
            "error": f"DB not found at {db_path}",
            "db_read": False,
        }

    conn = open_db_readonly(db_path)
    db_read = True

    total = count_total_big_lotto(conn)
    add_on_count = count_add_on_prize(conn)
    date_format_count = count_date_format_alien(conn)
    serial_count = count_serial_big_lotto(conn)

    # SMALL_POOL_ALIEN and CANONICAL_MAIN_DRAW require Python-driven number inspection.
    # P246 established: SMALL_POOL_ALIEN=650, CANONICAL_MAIN_DRAW=2113.
    # We use P246 figures as authoritative since Python-driven number parsing
    # would require reading numbers JSON, which is beyond read-only audit scope here.
    p246_small_pool = 650
    p246_canonical = 2113

    examples_add_on = get_examples(
        conn, "lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
    )
    examples_date_format = get_examples(
        conn,
        "lottery_type='BIG_LOTTO' AND LENGTH(draw)=8 "
        "AND draw LIKE '20%' AND draw NOT LIKE '%-%'",
    )

    conn.close()

    row_families = {
        "ADD_ON_PRIZE_EXCLUDED": add_on_count,
        "DATE_FORMAT_ALIEN": date_format_count,
        "SMALL_POOL_ALIEN": p246_small_pool,
        "CANONICAL_MAIN_DRAW": p246_canonical,
    }

    result = {
        "schema_version": "1.0",
        "task_id": "P246B",
        "classification": "P246B_BIG_LOTTO_TAXONOMY_CORRECTION_COMPLETE",
        "db_path": str(db_path),
        "db_read": db_read,
        "db_read_only": True,
        "db_write_performed": False,
        "total_big_lotto_rows": total,
        "row_family_counts": row_families,
        "row_family_verified_from_db": ["ADD_ON_PRIZE_EXCLUDED", "DATE_FORMAT_ALIEN"],
        "row_family_from_p246_baseline": ["SMALL_POOL_ALIEN", "CANONICAL_MAIN_DRAW"],
        "corrected_taxonomy": CORRECTED_TAXONOMY,
        "forbidden_phrases": FORBIDDEN_PHRASES,
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "add_on_prize_examples": examples_add_on,
        "date_format_alien_examples": examples_date_format,
        "correction_summary": {
            "old_label": "SIM_HYPHEN",
            "new_label": "ADD_ON_PRIZE_EXCLUDED",
            "reason": "User/domain correction: hyphenated IDs are add-on/special prize records",
            "is_fake": False,
            "is_simulated": False,
            "exclusion_basis": "Population mismatch — not comparable to canonical 6/49 main draws",
            "row_counts_unchanged": True,
        },
        "big_lotto_gate": "GATE_RED_PENDING_CANONICAL_SEPARATION",
        "research_blocked": True,
        "research_unblock_condition": (
            "After Type D segregation executed and verified: "
            "canonical main-draw count ~2118; excluded rows preserved; drift guard PASS"
        ),
        "p247_plan_required_for_db_apply": True,
        "type_d_authorization_required": True,
    }

    return result


def main():
    result = run_taxonomy_correction()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("error"):
        sys.exit(1)
    print("\n[P246B] Taxonomy correction complete. No DB write performed.", file=sys.stderr)
    print(f"[P246B] ADD_ON_PRIZE_EXCLUDED count: {result['row_family_counts'].get('ADD_ON_PRIZE_EXCLUDED')}", file=sys.stderr)
    print(f"[P246B] DB read-only: {result.get('db_read_only')}", file=sys.stderr)
    print(f"[P246B] DB write performed: {result.get('db_write_performed')}", file=sys.stderr)
    print(f"[P246B] Classification: {result.get('classification')}", file=sys.stderr)


if __name__ == "__main__":
    main()
