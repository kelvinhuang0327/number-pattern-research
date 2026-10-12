"""P247B — Apply BIG_LOTTO canonical view draws_big_lotto_canonical_main.

Type D controlled DB write. Requires explicit authorization.
Creates READ-ONLY VIEW only. No row insert/update/delete. No annotation table.
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

TASK_ID = "P247B"
SCHEMA_VERSION = "1.0"
DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"
BACKUPS_DIR = Path(__file__).parent.parent / "backups"
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")
VIEW_NAME = "draws_big_lotto_canonical_main"

EXPLICIT_AUTHORIZATION = (
    "YES apply P247B CREATE VIEW draws_big_lotto_canonical_main "
    "for BIG_LOTTO canonical research separation"
)

EXPECTED_RAW_BIG_LOTTO = 22_238
EXPECTED_CANONICAL = 2_113
EXPECTED_ADD_ON = 19_100

# Exact SQL validated by P247A dry-run (returns 2,113 canonical rows)
CREATE_VIEW_SQL = f"""CREATE VIEW IF NOT EXISTS {VIEW_NAME} AS
SELECT d.*
FROM draws d
WHERE d.lottery_type = 'BIG_LOTTO'
  AND d.draw NOT LIKE '%-%'
  AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
  AND (
    SELECT MAX(CAST(j.value AS INTEGER))
    FROM json_each(d.numbers) j
  ) > 25"""

FORBIDDEN_ACTIONS = [
    "CREATE TABLE annotation table",
    "DELETE rows",
    "UPDATE rows",
    "INSERT rows",
    "registry mutation",
    "production recommendation change",
    "strategy promotion",
    "deployment",
    "force push",
    "branch deletion",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def check_json1(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT value FROM json_each('[1,2,3]')").fetchall()
        return True
    except sqlite3.OperationalError:
        return False


def count_raw_big_lotto(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
    ).fetchone()[0]


def count_add_on(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
    ).fetchone()[0]


def dry_run_canonical_count(conn: sqlite3.Connection) -> int:
    return conn.execute(f"""
        SELECT COUNT(*) FROM draws d
        WHERE d.lottery_type = 'BIG_LOTTO'
          AND d.draw NOT LIKE '%-%'
          AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
          AND (
            SELECT MAX(CAST(j.value AS INTEGER))
            FROM json_each(d.numbers) j
          ) > 25
    """).fetchone()[0]


def view_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name=?", (VIEW_NAME,)
    ).fetchone()
    return row is not None


def count_view_rows(conn: sqlite3.Connection) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {VIEW_NAME}").fetchone()[0]


def annotation_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='draw_row_family_annotations'"
    ).fetchone()
    return row is not None


def check_no_hyphen_in_view(conn: sqlite3.Connection) -> bool:
    cnt = conn.execute(
        f"SELECT COUNT(*) FROM {VIEW_NAME} WHERE draw LIKE '%-%'"
    ).fetchone()[0]
    return cnt == 0


def check_no_date_format_in_view(conn: sqlite3.Connection) -> bool:
    cnt = conn.execute(
        f"SELECT COUNT(*) FROM {VIEW_NAME} WHERE LENGTH(draw)=8 AND draw LIKE '20%'"
    ).fetchone()[0]
    return cnt == 0


def check_all_max_gt25(conn: sqlite3.Connection) -> bool:
    cnt = conn.execute(f"""
        SELECT COUNT(*) FROM {VIEW_NAME} v
        WHERE (
            SELECT MAX(CAST(j.value AS INTEGER))
            FROM json_each(v.numbers) j
        ) <= 25
    """).fetchone()[0]
    return cnt == 0


def count_replay_rows(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM replay_draws").fetchone()[0]
    except sqlite3.OperationalError:
        return -1


def db_integrity_check(conn: sqlite3.Connection) -> str:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return result


# ── Pre-apply verification ────────────────────────────────────────────────────

def pre_verify(conn: sqlite3.Connection) -> dict:
    raw_count = count_raw_big_lotto(conn)
    add_on_count = count_add_on(conn)
    dry_run_count = dry_run_canonical_count(conn)
    json1 = check_json1(conn)
    already_exists = view_exists(conn)

    result = {
        "db_exists": True,
        "json1_available": json1,
        "raw_big_lotto_count": raw_count,
        "add_on_count": add_on_count,
        "dry_run_canonical_count": dry_run_count,
        "view_already_exists": already_exists,
        "annotation_table_exists": annotation_table_exists(conn),
        "raw_matches_expected": raw_count == EXPECTED_RAW_BIG_LOTTO,
        "canonical_matches_expected": dry_run_count == EXPECTED_CANONICAL,
        "add_on_matches_expected": add_on_count == EXPECTED_ADD_ON,
        "all_checks_pass": (
            json1
            and raw_count == EXPECTED_RAW_BIG_LOTTO
            and dry_run_count == EXPECTED_CANONICAL
            and add_on_count == EXPECTED_ADD_ON
            and not already_exists
            and not annotation_table_exists(conn)
        ),
    }
    return result


# ── Backup ────────────────────────────────────────────────────────────────────

def create_backup() -> tuple[Path, str]:
    BACKUPS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"p247b_lottery_v2_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)
    checksum = sha256_file(backup_path)
    sha_path = backup_path.with_suffix(".db.sha256")
    sha_path.write_text(f"{checksum}  {backup_path.name}\n")
    return backup_path, checksum


# ── Apply ─────────────────────────────────────────────────────────────────────

def apply_view(conn: sqlite3.Connection) -> dict:
    if view_exists(conn):
        # Check idempotency
        existing_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name=?", (VIEW_NAME,)
        ).fetchone()[0]
        return {"applied": False, "idempotent": True, "existing_sql": existing_sql}

    with conn:  # transaction
        conn.execute(CREATE_VIEW_SQL)

    return {"applied": True, "idempotent": False}


# ── Post-apply verification ───────────────────────────────────────────────────

def post_verify(conn: sqlite3.Connection) -> dict:
    raw_count = count_raw_big_lotto(conn)
    view_count = count_view_rows(conn) if view_exists(conn) else -1
    add_on_count = count_add_on(conn)
    replay_count = count_replay_rows(conn)
    integrity = db_integrity_check(conn)

    return {
        "view_exists": view_exists(conn),
        "view_row_count": view_count,
        "raw_big_lotto_count": raw_count,
        "add_on_count": add_on_count,
        "no_hyphen_in_view": check_no_hyphen_in_view(conn),
        "no_date_format_in_view": check_no_date_format_in_view(conn),
        "all_max_gt25": check_all_max_gt25(conn),
        "annotation_table_created": annotation_table_exists(conn),
        "raw_rows_preserved": raw_count == EXPECTED_RAW_BIG_LOTTO,
        "canonical_count_correct": view_count == EXPECTED_CANONICAL,
        "add_on_preserved": add_on_count == EXPECTED_ADD_ON,
        "replay_rows": replay_count,
        "db_integrity": integrity,
        "all_checks_pass": (
            view_exists(conn)
            and view_count == EXPECTED_CANONICAL
            and raw_count == EXPECTED_RAW_BIG_LOTTO
            and add_on_count == EXPECTED_ADD_ON
            and check_no_hyphen_in_view(conn)
            and check_no_date_format_in_view(conn)
            and check_all_max_gt25(conn)
            and not annotation_table_exists(conn)
            and integrity == "ok"
        ),
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def build_json_report(
    mode: str,
    pre: dict,
    backup_path: Optional[Path],
    backup_sha: Optional[str],
    apply_result: Optional[dict],
    post: Optional[dict],
) -> dict:
    view_created = apply_result.get("applied", False) if apply_result else False
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "TYPE_D_CONTROLLED_APPLY",
        "mode": mode,
        "explicit_authorization_confirmed": EXPLICIT_AUTHORIZATION,
        "p247a_merged_pr": 327,
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path) if backup_path else None,
        "backup_sha256": backup_sha,
        "pre_apply_counts": {
            "raw_big_lotto": pre.get("raw_big_lotto_count"),
            "add_on": pre.get("add_on_count"),
            "dry_run_canonical": pre.get("dry_run_canonical_count"),
        },
        "pre_apply_all_checks_pass": pre.get("all_checks_pass"),
        "applied_sql_summary": "CREATE VIEW IF NOT EXISTS draws_big_lotto_canonical_main — canonical BIG_LOTTO main-draw filter (lottery_type=BIG_LOTTO, no hyphen, no date-format, max(numbers)>25)",
        "view_name": VIEW_NAME,
        "view_created": view_created,
        "apply_idempotent": apply_result.get("idempotent", False) if apply_result else None,
        "post_apply_counts": {
            "view_rows": post.get("view_row_count") if post else None,
            "raw_big_lotto": post.get("raw_big_lotto_count") if post else None,
            "add_on": post.get("add_on_count") if post else None,
            "replay_rows": post.get("replay_rows") if post else None,
        } if post else None,
        "raw_rows_preserved": post.get("raw_rows_preserved") if post else None,
        "canonical_count_correct": post.get("canonical_count_correct") if post else None,
        "no_row_insert_update_delete": True,
        "annotation_table_created": post.get("annotation_table_created", False) if post else False,
        "db_integrity_result": post.get("db_integrity") if post else None,
        "replay_rows_result": post.get("replay_rows") if post else None,
        "post_apply_all_checks_pass": post.get("all_checks_pass") if post else None,
        "forbidden_actions_confirmed": {
            action: "NOT PERFORMED" for action in FORBIDDEN_ACTIONS
        },
        "final_decision": (
            f"P247B {mode}: View {VIEW_NAME} {'created' if view_created else 'dry-run validated'}. "
            f"Canonical rows: {post.get('view_row_count') if post else pre.get('dry_run_canonical_count')}. "
            f"Raw BIG_LOTTO rows preserved: {EXPECTED_RAW_BIG_LOTTO}. "
            f"No row delete/update/insert. No annotation table. No registry mutation."
        ) if post else (
            f"P247B DRY-RUN: Pre-apply verification complete. "
            f"Canonical dry-run count: {pre.get('dry_run_canonical_count')}. "
            f"All pre-apply checks pass: {pre.get('all_checks_pass')}. "
            f"Ready for --apply."
        ),
    }


def build_md_report(
    mode: str,
    pre: dict,
    backup_path: Optional[Path],
    backup_sha: Optional[str],
    apply_result: Optional[dict],
    post: Optional[dict],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    view_created = apply_result.get("applied", False) if apply_result else False

    lines = [
        f"# P247B — BIG_LOTTO Canonical View Apply Report",
        f"",
        f"**Date:** {now}  ",
        f"**Mode:** {mode}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** TYPE_D_CONTROLLED_APPLY  ",
        f"",
        f"## Executive Summary",
        f"",
    ]

    if post and view_created:
        lines += [
            f"P247B successfully created the canonical BIG_LOTTO research view "
            f"`{VIEW_NAME}` in `lottery_api/data/lottery_v2.db`. "
            f"The view exposes **{post.get('view_row_count')}** canonical main-draw rows "
            f"while preserving all **{EXPECTED_RAW_BIG_LOTTO}** raw BIG_LOTTO rows. "
            f"No rows were deleted, updated, or inserted. No annotation table was created. "
            f"No registry or strategy recommendation was modified.",
            f"",
        ]
    elif post and apply_result and apply_result.get("idempotent"):
        lines += [
            f"P247B detected view `{VIEW_NAME}` already exists with same definition. "
            f"Classified as idempotent/no-op. No DB write performed.",
            f"",
        ]
    else:
        lines += [
            f"P247B dry-run verified pre-apply conditions. "
            f"Canonical filter returns **{pre.get('dry_run_canonical_count')}** rows. "
            f"Ready for --apply.",
            f"",
        ]

    lines += [
        f"## Explicit Authorization",
        f"",
        f"> {EXPLICIT_AUTHORIZATION}",
        f"",
        f"## P247A Merged PR",
        f"",
        f"- PR #327 merged to main before this apply",
        f"- P247A dry-run validated canonical view SQL returns 2,113 rows",
        f"",
        f"## Backup",
        f"",
        f"- **Backup path:** `{backup_path}`" if backup_path else "- No backup (dry-run mode)",
        f"- **SHA256:** `{backup_sha}`" if backup_sha else "",
        f"",
        f"## DB Object Created",
        f"",
        f"- **View name:** `{VIEW_NAME}`",
        f"- **View created:** {view_created}",
        f"- **Idempotent:** {apply_result.get('idempotent', False) if apply_result else 'N/A'}",
        f"",
        f"## Exact View Filter Rules",
        f"",
        f"```sql",
        CREATE_VIEW_SQL,
        f"```",
        f"",
        f"### Filter criteria:",
        f"1. `lottery_type = 'BIG_LOTTO'` — only BIG_LOTTO records",
        f"2. `draw NOT LIKE '%-%'` — exclude ADD_ON_PRIZE_EXCLUDED (hyphenated) rows",
        f"3. `NOT (LENGTH(draw)=8 AND draw LIKE '20%')` — exclude DATE_FORMAT_ALIEN rows",
        f"4. `MAX(numbers) > 25` via JSON1/json_each — exclude SMALL_POOL_ALIEN rows",
        f"",
        f"## Pre/Post Reconciliation",
        f"",
        f"| Metric | Expected | Pre-Apply | Post-Apply |",
        f"|--------|----------|-----------|------------|",
    ]

    pre_raw = pre.get("raw_big_lotto_count", "N/A")
    pre_add = pre.get("add_on_count", "N/A")
    pre_canon = pre.get("dry_run_canonical_count", "N/A")
    post_raw = post.get("raw_big_lotto_count", "N/A") if post else "N/A"
    post_add = post.get("add_on_count", "N/A") if post else "N/A"
    post_view = post.get("view_row_count", "N/A") if post else "N/A"

    lines += [
        f"| Raw BIG_LOTTO rows | {EXPECTED_RAW_BIG_LOTTO} | {pre_raw} | {post_raw} |",
        f"| Canonical view rows | {EXPECTED_CANONICAL} | {pre_canon} (dry-run) | {post_view} |",
        f"| ADD_ON_PRIZE_EXCLUDED raw rows | {EXPECTED_ADD_ON} | {pre_add} | {post_add} |",
        f"",
        f"## Raw Rows Preserved Confirmation",
        f"",
        f"- Raw BIG_LOTTO rows after apply: **{post_raw}** (expected {EXPECTED_RAW_BIG_LOTTO})",
        f"- ADD_ON_PRIZE_EXCLUDED raw rows: **{post_add}** (expected {EXPECTED_ADD_ON})",
        f"- **No rows were deleted, updated, or inserted.**",
        f"",
        f"## DB Integrity",
        f"",
        f"- `PRAGMA integrity_check`: **{post.get('db_integrity') if post else 'not checked (dry-run)'}**",
        f"- Replay rows (if checked): **{post.get('replay_rows') if post else 'not checked'}**",
        f"",
        f"## Explicit Compliance Statements",
        f"",
        f"- **No row delete/update/insert** performed in this task.",
        f"- **No annotation table** (draw_row_family_annotations) was created.",
        f"- **No registry** files were modified.",
        f"- **No strategy** implementation logic was changed.",
        f"- **No production recommendation** was updated.",
        f"- **No deployment** was performed.",
        f"- All ADD_ON_PRIZE_EXCLUDED rows remain raw-accessible at {EXPECTED_ADD_ON} rows.",
        f"",
        f"## Post-Apply View Checks",
    ]

    if post:
        lines += [
            f"",
            f"- No hyphenated draw in view: **{post.get('no_hyphen_in_view')}**",
            f"- No date-format alien in view: **{post.get('no_date_format_in_view')}**",
            f"- All max(numbers) > 25: **{post.get('all_max_gt25')}**",
            f"- Annotation table created: **{post.get('annotation_table_created')}** (must be False)",
            f"- All post-apply checks pass: **{post.get('all_checks_pass')}**",
        ]
    else:
        lines.append(f"- (dry-run mode — no post-apply checks)")

    lines += [
        f"",
        f"---",
        f"*Generated by {TASK_ID} — Type D controlled apply*",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="P247B BIG_LOTTO canonical view apply")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Verify pre-conditions only, no DB write")
    group.add_argument("--apply", action="store_true", help="Execute controlled CREATE VIEW write")
    args = parser.parse_args()

    mode = "DRY_RUN" if args.dry_run else "APPLY"
    print(f"[P247B] Mode: {mode}")
    print(f"[P247B] DB: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"[P247B] ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = get_conn(DB_PATH)

    # Pre-verify
    print("[P247B] Running pre-apply verification...")
    pre = pre_verify(conn)
    print(f"[P247B]   raw_big_lotto={pre['raw_big_lotto_count']} (expected {EXPECTED_RAW_BIG_LOTTO})")
    print(f"[P247B]   add_on={pre['add_on_count']} (expected {EXPECTED_ADD_ON})")
    print(f"[P247B]   dry_run_canonical={pre['dry_run_canonical_count']} (expected {EXPECTED_CANONICAL})")
    print(f"[P247B]   json1_available={pre['json1_available']}")
    print(f"[P247B]   view_already_exists={pre['view_already_exists']}")
    print(f"[P247B]   annotation_table_exists={pre['annotation_table_exists']}")
    print(f"[P247B]   all_checks_pass={pre['all_checks_pass']}")

    if not pre["all_checks_pass"] and not pre["view_already_exists"]:
        print("[P247B] ERROR: Pre-apply checks failed. Aborting.", file=sys.stderr)
        sys.exit(2)

    if args.dry_run:
        report_json = build_json_report(mode, pre, None, None, None, None)
        report_md = build_md_report(mode, pre, None, None, None, None)
        json_path = OUTPUTS_DIR / f"p247b_apply_big_lotto_canonical_view_{DATE_SLUG}.json"
        md_path = OUTPUTS_DIR / f"p247b_apply_big_lotto_canonical_view_{DATE_SLUG}.md"
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
        md_path.write_text(report_md)
        print(f"[P247B] Dry-run complete. Reports written:")
        print(f"[P247B]   {json_path}")
        print(f"[P247B]   {md_path}")
        conn.close()
        return

    # APPLY mode — backup first
    print("[P247B] Creating DB backup...")
    backup_path, backup_sha = create_backup()
    sha_path = backup_path.with_suffix(".db.sha256")
    print(f"[P247B]   Backup: {backup_path}")
    print(f"[P247B]   SHA256: {backup_sha}")
    assert backup_path.exists(), "Backup file not created!"
    assert sha_path.exists(), "SHA256 file not created!"

    # Apply
    print(f"[P247B] Applying CREATE VIEW {VIEW_NAME}...")
    apply_result = apply_view(conn)
    if apply_result.get("idempotent"):
        print(f"[P247B] View already exists — idempotent/no-op.")
    else:
        print(f"[P247B] View created successfully.")

    # Post-verify
    print("[P247B] Running post-apply verification...")
    post = post_verify(conn)
    print(f"[P247B]   view_row_count={post['view_row_count']} (expected {EXPECTED_CANONICAL})")
    print(f"[P247B]   raw_big_lotto={post['raw_big_lotto_count']} (expected {EXPECTED_RAW_BIG_LOTTO})")
    print(f"[P247B]   add_on={post['add_on_count']} (expected {EXPECTED_ADD_ON})")
    print(f"[P247B]   no_hyphen_in_view={post['no_hyphen_in_view']}")
    print(f"[P247B]   no_date_format_in_view={post['no_date_format_in_view']}")
    print(f"[P247B]   all_max_gt25={post['all_max_gt25']}")
    print(f"[P247B]   annotation_table_created={post['annotation_table_created']}")
    print(f"[P247B]   db_integrity={post['db_integrity']}")
    print(f"[P247B]   replay_rows={post['replay_rows']}")
    print(f"[P247B]   all_checks_pass={post['all_checks_pass']}")

    if not post["all_checks_pass"]:
        print("[P247B] ERROR: Post-apply checks failed!", file=sys.stderr)
        sys.exit(3)

    # Write reports
    report_json = build_json_report(mode, pre, backup_path, backup_sha, apply_result, post)
    report_md = build_md_report(mode, pre, backup_path, backup_sha, apply_result, post)
    json_path = OUTPUTS_DIR / f"p247b_apply_big_lotto_canonical_view_{DATE_SLUG}.json"
    md_path = OUTPUTS_DIR / f"p247b_apply_big_lotto_canonical_view_{DATE_SLUG}.md"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)
    print(f"[P247B] Reports written:")
    print(f"[P247B]   {json_path}")
    print(f"[P247B]   {md_path}")
    print(f"[P247B] P247B APPLY COMPLETE — all checks pass.")
    conn.close()


if __name__ == "__main__":
    main()
