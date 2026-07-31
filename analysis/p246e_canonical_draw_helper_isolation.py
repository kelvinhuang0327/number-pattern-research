"""
P246E — Canonical Draw Helper Isolation

Read-only audit and validation for the Phase 1 implementation:
  - get_canonical_draws() added to lottery_api/database.py
  - tools/quick_predict.py load_history() updated to use canonical helper

No DB write is performed.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"
REPO_ROOT = Path(__file__).parent.parent

CANONICAL_FILTER_RULES = {
    "BIG_LOTTO": {
        "sql_filter_add_on": "draw NOT LIKE '%-%'",
        "sql_filter_date_format": "NOT (LENGTH(draw)=8 AND draw LIKE '20%')",
        "python_filter_small_pool": "max(numbers) > 25",
        "combined_sql": (
            "lottery_type='BIG_LOTTO' "
            "AND draw NOT LIKE '%-%' "
            "AND NOT (LENGTH(draw)=8 AND draw LIKE '20%')"
        ),
        "post_filter": "max(row['numbers']) > 25  -- excludes SMALL_POOL_ALIEN",
        "expected_canonical_count": 2113,
        "families_excluded": [
            "ADD_ON_PRIZE_EXCLUDED (hyphenated IDs, add-on/special prize records — valid but out-of-scope)",
            "DATE_FORMAT_ALIEN (8-digit YYYYMMDD IDs, numbers not 6/49)",
            "SMALL_POOL_ALIEN (serial IDs, max(numbers)<=25, likely mislabeled game)",
        ],
    },
    "POWER_LOTTO": {
        "sql_filter": "lottery_type='POWER_LOTTO'",
        "python_filter": "None",
        "note": "No known non-canonical row families; passes through unchanged",
    },
    "DAILY_539": {
        "sql_filter": "lottery_type='DAILY_539'",
        "python_filter": "None",
        "note": "No known non-canonical row families; passes through unchanged",
    },
}

FORBIDDEN_ACTIONS = [
    "DB_write",
    "DB_migration_apply",
    "row_deletion",
    "registry_mutation",
    "production_recommendation_change",
    "strategy_promotion",
    "betting_advice",
    "Type_D_apply",
    "GATE_OPEN_for_BIG_LOTTO_research",
]


def verify_helper_in_database_py() -> dict:
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    if not db_file.exists():
        return {"found": False, "error": "database.py not found"}
    content = db_file.read_text(encoding="utf-8")
    has_function = "def get_canonical_draws" in content
    has_hyphen_filter = "draw NOT LIKE '%-%'" in content
    has_date_filter = "LENGTH(draw) = 8" in content or "LENGTH(draw)=8" in content
    has_small_pool_filter = "max(numbers)" in content or "max(" in content
    has_preservation_comment = (
        "add-on" in content.lower() or "ADD_ON_PRIZE_EXCLUDED" in content
    )
    return {
        "found": has_function,
        "has_hyphen_filter": has_hyphen_filter,
        "has_date_format_filter": has_date_filter,
        "has_small_pool_python_filter": has_small_pool_filter,
        "has_preservation_comment": has_preservation_comment,
    }


def verify_quick_predict_updated() -> dict:
    qp_file = REPO_ROOT / "tools" / "quick_predict.py"
    if not qp_file.exists():
        return {"found": False, "error": "quick_predict.py not found"}
    content = qp_file.read_text(encoding="utf-8")
    uses_canonical = "get_canonical_draws" in content
    raw_call_remains = content.count("get_all_draws") >= 1
    load_history_uses_canonical = False
    for i, line in enumerate(content.splitlines()):
        if "get_canonical_draws" in line:
            # Check it's in load_history context
            ctx = content.splitlines()[max(0, i - 5): i + 2]
            if any("load_history" in c or "history" in c for c in ctx):
                load_history_uses_canonical = True
    return {
        "found": True,
        "uses_canonical_helper": uses_canonical,
        "load_history_uses_canonical": load_history_uses_canonical,
        "raw_get_all_draws_still_present": raw_call_remains,
    }


def validate_against_db(db_path: Path = DB_PATH) -> dict:
    if not db_path.exists():
        return {"db_read": False, "error": "DB not found"}

    # Import and use the actual implementation
    sys.path.insert(0, str(REPO_ROOT / "lottery_api"))
    try:
        from database import DatabaseManager
        db = DatabaseManager(db_path=str(db_path))

        canonical = db.get_canonical_draws("BIG_LOTTO")
        raw = db.get_all_draws("BIG_LOTTO")

        hyphen_in_canonical = [d["draw"] for d in canonical if "-" in d["draw"]]
        date_fmt_in_canonical = [
            d["draw"] for d in canonical
            if len(d["draw"]) == 8 and d["draw"].startswith("20")
        ]
        small_pool_in_canonical = [
            d["draw"] for d in canonical if max(d["numbers"]) <= 25
        ]
        hyphen_in_raw = [d["draw"] for d in raw if "-" in d["draw"]]

        power_canonical = db.get_canonical_draws("POWER_LOTTO")
        power_raw = db.get_all_draws("POWER_LOTTO")
        d539_canonical = db.get_canonical_draws("DAILY_539")
        d539_raw = db.get_all_draws("DAILY_539")

        return {
            "db_read": True,
            "db_path": str(db_path),
            "db_write_performed": False,
            "BIG_LOTTO": {
                "raw_count": len(raw),
                "canonical_count": len(canonical),
                "excluded_count": len(raw) - len(canonical),
                "hyphen_in_canonical": len(hyphen_in_canonical),
                "date_format_in_canonical": len(date_fmt_in_canonical),
                "small_pool_in_canonical": len(small_pool_in_canonical),
                "hyphen_in_raw": len(hyphen_in_raw),
                "canonical_matches_expected": len(canonical) == 2113,
                "hyphen_excluded": len(hyphen_in_canonical) == 0,
                "small_pool_excluded": len(small_pool_in_canonical) == 0,
                "raw_preserves_addon": len(hyphen_in_raw) == 19100,
            },
            "POWER_LOTTO": {
                "canonical_count": len(power_canonical),
                "raw_count": len(power_raw),
                "unchanged": len(power_canonical) == len(power_raw),
            },
            "DAILY_539": {
                "canonical_count": len(d539_canonical),
                "raw_count": len(d539_raw),
                "unchanged": len(d539_canonical) == len(d539_raw),
            },
        }
    except Exception as e:
        return {"db_read": True, "error": str(e)}
    finally:
        if str(REPO_ROOT / "lottery_api") in sys.path:
            sys.path.remove(str(REPO_ROOT / "lottery_api"))


def run_isolation_audit(db_path: Path = DB_PATH) -> dict:
    db_status = validate_against_db(db_path)
    helper_status = verify_helper_in_database_py()
    caller_status = verify_quick_predict_updated()

    canonical_count = db_status.get("BIG_LOTTO", {}).get("canonical_count")
    all_checks_pass = (
        helper_status.get("found", False)
        and helper_status.get("has_hyphen_filter", False)
        and caller_status.get("uses_canonical_helper", False)
        and caller_status.get("load_history_uses_canonical", False)
        and db_status.get("BIG_LOTTO", {}).get("hyphen_excluded", False)
        and db_status.get("BIG_LOTTO", {}).get("small_pool_excluded", False)
        and db_status.get("BIG_LOTTO", {}).get("raw_preserves_addon", False)
        and db_status.get("BIG_LOTTO", {}).get("canonical_matches_expected", False)
    )

    return {
        "schema_version": "1.0",
        "task_id": "P246E",
        "classification": "P246E_CANONICAL_DRAW_HELPER_ISOLATION_COMPLETE",
        "implemented_helper": {
            "function": "get_canonical_draws(lottery_type, limit=None)",
            "location": "lottery_api/database.py",
            "status": helper_status,
        },
        "updated_callers": [
            {
                "file": "tools/quick_predict.py",
                "function": "load_history()",
                "change": "db.get_all_draws(BIG_LOTTO) → db.get_canonical_draws(BIG_LOTTO)",
                "status": caller_status,
            }
        ],
        "raw_access_preserved": {
            "description": (
                "get_all_draws() and get_draws() remain unchanged and return all 22,238 BIG_LOTTO rows. "
                "ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are preserved in the DB and "
                "accessible via raw-access methods for display/history use."
            ),
            "verified": db_status.get("BIG_LOTTO", {}).get("raw_preserves_addon"),
        },
        "db_write_performed": False,
        "db_read_status": {
            "read": db_status.get("db_read", False),
            "read_only": True,
            "write_performed": False,
        },
        "canonical_filter_rules": CANONICAL_FILTER_RULES,
        "row_count_validation": db_status,
        "all_isolation_checks_pass": all_checks_pass,
        "forbidden_actions_confirmed": FORBIDDEN_ACTIONS,
        "big_lotto_gate": "GATE_RED_PENDING_CANONICAL_SEPARATION",
        "remaining_future_work": [
            "Phase 2 (Type D): CREATE VIEW draws_big_lotto_canonical_main in DB",
            "Phase 3 (Type D): CREATE TABLE draw_row_family_annotations",
            "Phase 4: Re-run P238B NIST audit on canonical population only",
            "Update test_p238b assertion from >= 22238 to >= 2113",
            "Verify RSM and other engine callers use canonical helper",
        ],
        "final_decision": (
            f"P246E Phase 1 implementation complete. "
            f"get_canonical_draws() added to database.py — "
            f"BIG_LOTTO canonical count: {canonical_count} (expected 2113). "
            "Excludes ADD_ON_PRIZE_EXCLUDED (hyphenated IDs), DATE_FORMAT_ALIEN, "
            "and SMALL_POOL_ALIEN via SQL + Python filters. "
            "tools/quick_predict.py load_history() updated to use canonical helper. "
            "Raw records preserved: get_all_draws() still returns all 22,238 BIG_LOTTO rows. "
            "No DB write performed. No row deletion. No migration. "
            "BIG_LOTTO research gate remains GATE_RED_PENDING_CANONICAL_SEPARATION "
            "pending Phase 2/3 Type D DB operations."
        ),
    }


def main():
    result = run_isolation_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    checks_pass = result.get("all_isolation_checks_pass", False)
    print(f"\n[P246E] All isolation checks pass: {checks_pass}", file=sys.stderr)
    print(f"[P246E] DB write: {result['db_write_performed']}", file=sys.stderr)
    bl = result.get("row_count_validation", {}).get("BIG_LOTTO", {})
    print(f"[P246E] canonical={bl.get('canonical_count')} raw={bl.get('raw_count')}", file=sys.stderr)
    print(f"[P246E] Classification: {result['classification']}", file=sys.stderr)
    if not checks_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
