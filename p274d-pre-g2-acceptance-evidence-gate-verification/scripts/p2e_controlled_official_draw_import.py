#!/usr/bin/env python3
"""
P2E Controlled Official Draw Import Script
==========================================
Controlled import of BIG_LOTTO draws 115000051 and 115000052 from verified P2D dry-run output.

Default mode: DRY-RUN (no DB write)
Write mode:   Requires explicit --apply flag AND --controlled-import-id P2E_20260515

AUTHORIZATION GATE: operator must pass --apply to write DB

Usage (dry-run, default):
    python3 scripts/p2e_controlled_official_draw_import.py \
        --db lottery_api/data/lottery_v2.db \
        --dryrun-json outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json \
        --draws 115000051,115000052 \
        --controlled-import-id P2E_20260515 \
        --json-out outputs/replay/p2e_controlled_big_lotto_draw_import_receipt_20260515.json

Usage (apply — requires explicit operator authorization):
    python3 scripts/p2e_controlled_official_draw_import.py \
        --db lottery_api/data/lottery_v2.db \
        --dryrun-json outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json \
        --draws 115000051,115000052 \
        --controlled-import-id P2E_20260515 \
        --json-out outputs/replay/p2e_controlled_big_lotto_draw_import_receipt_20260515.json \
        --apply
"""

import argparse
import json
import sqlite3
import sys
import datetime
from pathlib import Path

# ─── Authorization constants ──────────────────────────────────────────────────
AUTHORIZED_IMPORT_ID = "P2E_20260515"
AUTHORIZED_DRAWS = {"115000051", "115000052"}
NOT_PUBLISHED_DRAWS = {"115000053"}
LOTTERY_TYPE = "BIG_LOTTO"

# ─── Validation bounds ────────────────────────────────────────────────────────
MAIN_NUMBER_MIN = 1
MAIN_NUMBER_MAX = 49
MAIN_NUMBER_COUNT = 6
SPECIAL_MIN = 1
SPECIAL_MAX = 49


def parse_args():
    p = argparse.ArgumentParser(description="P2E Controlled Official Draw Import")
    p.add_argument("--db", required=True, help="Path to lottery_v2.db")
    p.add_argument("--dryrun-json", required=True, help="Path to P2D dry-run JSON output")
    p.add_argument("--draws", required=True, help="Comma-separated draw IDs to import (e.g. 115000051,115000052)")
    p.add_argument("--controlled-import-id", required=True, help="Must be P2E_20260515")
    p.add_argument("--json-out", required=True, help="Path for output receipt JSON")
    p.add_argument("--apply", action="store_true", default=False,
                   help="AUTHORIZATION GATE: write to DB. Requires explicit operator authorization.")
    return p.parse_args()


def validate_import_id(import_id: str):
    if import_id != AUTHORIZED_IMPORT_ID:
        print(f"HARD FAIL: controlled-import-id must be '{AUTHORIZED_IMPORT_ID}', got '{import_id}'")
        sys.exit(1)


def validate_requested_draws(requested: list[str]):
    for draw in requested:
        if draw in NOT_PUBLISHED_DRAWS:
            print(f"HARD FAIL: draw {draw} is NOT_PUBLISHED — explicitly rejected, cannot import")
            sys.exit(1)
        if draw not in AUTHORIZED_DRAWS:
            print(f"HARD FAIL: draw {draw} is not in the authorized draw list {AUTHORIZED_DRAWS}")
            sys.exit(1)


def load_p2d_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"HARD FAIL: P2D dry-run JSON not found: {path}")
        sys.exit(1)
    with open(p) as f:
        data = json.load(f)
    # Verify this is actually a P2D output
    if data.get("run_id", "").startswith("p2d_") is False:
        print(f"WARNING: run_id does not look like a P2D output: {data.get('run_id')}")
    return data


def extract_draw_from_p2d(p2d_data: dict, draw_id: str):
    for result in p2d_data.get("draw_results", []):
        if str(result.get("draw")) == str(draw_id):
            return result
    return None


def validate_draw_data(draw_record: dict):
    """Validate a draw record. Returns (ok, error_message)."""
    draw_id = draw_record.get("draw", "?")

    # Check fetch status
    fetch_status = draw_record.get("fetch_status", "UNKNOWN")
    if fetch_status != "FETCHED":
        return False, f"draw {draw_id} fetch_status={fetch_status} (expected FETCHED)"

    # Validate numbers
    numbers = draw_record.get("numbers", [])
    if not isinstance(numbers, list) or len(numbers) != MAIN_NUMBER_COUNT:
        return False, f"draw {draw_id}: expected {MAIN_NUMBER_COUNT} main numbers, got {len(numbers)}"
    for n in numbers:
        if not isinstance(n, int) or not (MAIN_NUMBER_MIN <= n <= MAIN_NUMBER_MAX):
            return False, f"draw {draw_id}: main number {n} out of range [{MAIN_NUMBER_MIN},{MAIN_NUMBER_MAX}]"
    if len(set(numbers)) != len(numbers):
        return False, f"draw {draw_id}: duplicate main numbers detected"

    # Validate special
    special = draw_record.get("special")
    if not isinstance(special, int) or not (SPECIAL_MIN <= special <= SPECIAL_MAX):
        return False, f"draw {draw_id}: special {special} out of range [{SPECIAL_MIN},{SPECIAL_MAX}]"

    # Validate date format (YYYY/MM/DD)
    date_str = draw_record.get("date", "")
    try:
        datetime.datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        return False, f"draw {draw_id}: date '{date_str}' does not match expected format YYYY/MM/DD"

    return True, "OK"


def check_existing_draw(conn: sqlite3.Connection, draw_id: str):
    """Check if draw already exists in DB. Returns existing row dict or None."""
    cur = conn.cursor()
    row = cur.execute(
        """SELECT draw, date, lottery_type, numbers, special
           FROM draws
           WHERE lottery_type=? AND CAST(draw AS INTEGER)=CAST(? AS INTEGER)""",
        (LOTTERY_TYPE, draw_id)
    ).fetchone()
    if row is None:
        return None
    return {
        "draw": row[0],
        "date": row[1],
        "lottery_type": row[2],
        "numbers": row[3],
        "special": row[4],
    }


def numbers_match(existing: dict, candidate: dict) -> bool:
    """Check if existing DB row matches candidate draw data."""
    existing_nums = json.loads(existing["numbers"]) if isinstance(existing["numbers"], str) else existing["numbers"]
    candidate_nums = sorted(candidate["numbers"])
    existing_nums_sorted = sorted(existing_nums)
    return (
        existing_nums_sorted == candidate_nums
        and int(existing["special"]) == int(candidate["special"])
        and existing["date"] == candidate["date"]
    )


def format_preview_table(draws_preview: list[dict]) -> str:
    lines = []
    lines.append(f"{'DRAW':<14} {'DATE':<12} {'NUMBERS':<30} {'SPECIAL':<8} {'STATUS':<20}")
    lines.append("-" * 90)
    for d in draws_preview:
        nums = str(d["numbers"])
        lines.append(f"{d['draw']:<14} {d['date']:<12} {nums:<30} {d['special']:<8} {d['status']:<20}")
    return "\n".join(lines)


def main():
    args = parse_args()

    print("=" * 70)
    print("P2E Controlled Official Draw Import")
    print(f"Mode: {'*** APPLY — DB WILL BE WRITTEN ***' if args.apply else 'DRY-RUN (read-only)'}")
    print(f"Controlled Import ID: {args.controlled_import_id}")
    print("=" * 70)

    # ── Validation ─────────────────────────────────────────────────────────────
    validate_import_id(args.controlled_import_id)

    requested_draws = [d.strip() for d in args.draws.split(",") if d.strip()]
    validate_requested_draws(requested_draws)
    print(f"Requested draws: {requested_draws}")

    # ── Load P2D source ────────────────────────────────────────────────────────
    p2d_data = load_p2d_json(args.dryrun_json)
    print(f"P2D source: {p2d_data.get('run_id')} / {p2d_data.get('overall_classification')}")

    # ── Verify P2D safety flag ─────────────────────────────────────────────────
    safety = p2d_data.get("safety", {})
    if safety.get("db_written", True):
        print("HARD FAIL: P2D JSON claims db_written=true — refusing to use as source")
        sys.exit(1)
    if safety.get("draw_rows_inserted", True):
        print("HARD FAIL: P2D JSON claims draw_rows_inserted=true — refusing to use as source")
        sys.exit(1)

    # ── Open DB ────────────────────────────────────────────────────────────────
    if args.apply:
        conn = sqlite3.connect(args.db)
    else:
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # ── Process each draw ─────────────────────────────────────────────────────
    draws_imported = []
    draws_skipped = []
    draws_already_present = []
    draws_failed = []
    draws_preview = []

    for draw_id in requested_draws:
        print(f"\n--- Processing draw {draw_id} ---")

        # Explicitly reject NOT_PUBLISHED
        if draw_id in NOT_PUBLISHED_DRAWS:
            print(f"  SKIP: {draw_id} is NOT_PUBLISHED")
            draws_skipped.append({"draw": draw_id, "reason": "NOT_PUBLISHED"})
            draws_preview.append({"draw": draw_id, "date": "N/A", "numbers": [], "special": "N/A", "status": "SKIPPED_NOT_PUBLISHED"})
            continue

        # Extract from P2D source
        draw_record = extract_draw_from_p2d(p2d_data, draw_id)
        if draw_record is None:
            msg = f"draw {draw_id} not found in P2D JSON"
            print(f"  HARD FAIL: {msg}")
            draws_failed.append({"draw": draw_id, "reason": msg})
            draws_preview.append({"draw": draw_id, "date": "N/A", "numbers": [], "special": "N/A", "status": "FAIL_NOT_IN_SOURCE"})
            continue

        # Validate draw data
        ok, err = validate_draw_data(draw_record)
        if not ok:
            print(f"  HARD FAIL: validation: {err}")
            draws_failed.append({"draw": draw_id, "reason": err})
            draws_preview.append({"draw": draw_id, "date": draw_record.get("date", "?"), "numbers": draw_record.get("numbers", []), "special": draw_record.get("special", "?"), "status": "FAIL_VALIDATION"})
            continue

        print(f"  Validated: {draw_record['date']} / numbers={draw_record['numbers']} / special={draw_record['special']}")

        # Check DB for existing row
        existing = check_existing_draw(conn, draw_id)
        if existing:
            if numbers_match(existing, draw_record):
                print(f"  already_present: draw {draw_id} already in DB with matching values — skipping")
                draws_already_present.append({
                    "draw": draw_id,
                    "existing": existing,
                })
                draws_preview.append({"draw": draw_id, "date": draw_record["date"], "numbers": draw_record["numbers"], "special": draw_record["special"], "status": "ALREADY_PRESENT"})
            else:
                msg = f"CONFLICT: draw {draw_id} exists in DB with DIFFERENT values. DB={existing}, source={draw_record}"
                print(f"  HARD FAIL: {msg}")
                draws_failed.append({"draw": draw_id, "reason": msg, "db_existing": existing, "source": draw_record})
                draws_preview.append({"draw": draw_id, "date": draw_record["date"], "numbers": draw_record["numbers"], "special": draw_record["special"], "status": "FAIL_CONFLICT"})
                conn.close()
                sys.exit(1)
            continue

        # Draw is MISSING — prepare for import
        numbers_json = json.dumps(sorted(draw_record["numbers"]))
        raw = draw_record.get("raw_content", {})
        jackpot_amount = None
        sell_amount = None
        total_amount = None
        if raw:
            jackpot_info = raw.get("jackpotAssign", {})
            jackpot_amount = jackpot_info.get("perPrize")
            sell_amount = raw.get("sellAmount")
            total_amount = raw.get("totalAmount")

        if args.apply:
            cur = conn.cursor()
            cur.execute(
                """INSERT OR IGNORE INTO draws
                   (draw, date, lottery_type, numbers, special, jackpot_amount, sell_amount, total_amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(draw_id),
                    draw_record["date"],
                    LOTTERY_TYPE,
                    numbers_json,
                    draw_record["special"],
                    jackpot_amount,
                    sell_amount,
                    total_amount,
                )
            )
            conn.commit()
            print(f"  IMPORTED: draw {draw_id} written to DB (rows affected={cur.rowcount})")
            draws_imported.append({
                "draw": draw_id,
                "date": draw_record["date"],
                "numbers": sorted(draw_record["numbers"]),
                "special": draw_record["special"],
            })
            draws_preview.append({"draw": draw_id, "date": draw_record["date"], "numbers": draw_record["numbers"], "special": draw_record["special"], "status": "IMPORTED"})
        else:
            print(f"  DRY-RUN: would import draw {draw_id} → numbers={sorted(draw_record['numbers'])} special={draw_record['special']}")
            draws_imported.append({
                "draw": draw_id,
                "date": draw_record["date"],
                "numbers": sorted(draw_record["numbers"]),
                "special": draw_record["special"],
                "note": "DRY_RUN_NOT_WRITTEN",
            })
            draws_preview.append({"draw": draw_id, "date": draw_record["date"], "numbers": sorted(draw_record["numbers"]), "special": draw_record["special"], "status": "WOULD_IMPORT (DRY-RUN)"})

    conn.close()

    # ── Print preview table ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PREVIEW TABLE")
    print("=" * 70)
    print(format_preview_table(draws_preview))

    # ── Build receipt ──────────────────────────────────────────────────────────
    db_written = args.apply and len(draws_imported) > 0 and len(draws_failed) == 0
    receipt = {
        "controlled_import_id": args.controlled_import_id,
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apply_mode": args.apply,
        "db_written": db_written,
        "lottery_type": LOTTERY_TYPE,
        "source_p2d_json": str(args.dryrun_json),
        "draws_imported": draws_imported,
        "draws_skipped": draws_skipped,
        "draws_already_present": draws_already_present,
        "draws_failed": draws_failed,
        "summary": {
            "n_imported": len(draws_imported),
            "n_skipped": len(draws_skipped),
            "n_already_present": len(draws_already_present),
            "n_failed": len(draws_failed),
        },
        "safety": {
            "db_written": db_written,
            "replay_rows_generated": False,
            "prediction_items_promoted": False,
            "strategy_logic_changed": False,
        },
        "next_step": (
            "Run post-draw pipeline or P2C replay with newly imported draws"
            if db_written else
            "AUTHORIZATION_GATE: operator must pass --apply to write DB"
        ),
    }

    # ── Write receipt ──────────────────────────────────────────────────────────
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(f"\nReceipt written: {out_path}")

    # ── Final status ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    if not args.apply:
        print("AUTHORIZATION_GATE: operator must pass --apply to write DB")
        print(f"db_written: FALSE (dry-run)")
    elif db_written:
        print(f"IMPORT COMPLETE: {len(draws_imported)} draw(s) written to DB")
        print(f"db_written: TRUE")
    else:
        print("WARNING: apply mode but nothing imported — check logs above")

    if draws_failed:
        print(f"FAILURES: {len(draws_failed)}")
        for f_ in draws_failed:
            print(f"  - {f_['draw']}: {f_['reason']}")
        sys.exit(1)

    print("=" * 70)


if __name__ == "__main__":
    main()
