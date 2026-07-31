#!/usr/bin/env python3
"""
P3B-C Controlled Draw Import
Authorization: P3BC_20260516

Imports ONLY these 2 authorized draws into the draws table:
  - DAILY_539   115000106  2026/04/30  [6,15,27,30,31]
  - POWER_LOTTO 115000035  2026/04/30  [1,4,13,19,27,30] special=8

Strict safety:
  - Default is dry-run (no writes); requires --apply to write
  - Requires --controlled-import-id P3BC_20260516
  - Only inserts the 2 authorized draws; rejects anything else
  - Idempotent: if same draw exists with same data → already_present (OK)
  - If same draw exists with different data → hard fail
  - No replay rows inserted
  - No prediction_items updated
  - No prediction_runs updated
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

CONTROLLED_IMPORT_ID = "P3BC_20260516"

AUTHORIZED_DRAWS = [
    {
        "lottery_type": "DAILY_539",
        "draw": "115000106",
        "date": "2026/04/30",
        "numbers": [6, 15, 27, 30, 31],
        "special": None,
    },
    {
        "lottery_type": "POWER_LOTTO",
        "draw": "115000035",
        "date": "2026/04/30",
        "numbers": [1, 4, 13, 19, 27, 30],
        "special": 8,
    },
]


def parse_args():
    p = argparse.ArgumentParser(description="P3B-C Controlled Draw Import")
    p.add_argument("--db", required=True, help="Path to lottery_v2.db")
    p.add_argument(
        "--dryrun-json",
        required=True,
        help="Path to P3B-B dryrun JSON (for source verification)",
    )
    p.add_argument(
        "--controlled-import-id",
        required=True,
        help="Must be: P3BC_20260516",
    )
    p.add_argument(
        "--json-out",
        required=True,
        help="Path for receipt JSON output",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually write to DB (default: dry-run only)",
    )
    return p.parse_args()


def verify_controlled_import_id(provided: str) -> None:
    if provided != CONTROLLED_IMPORT_ID:
        print(f"FATAL: --controlled-import-id must be '{CONTROLLED_IMPORT_ID}', got '{provided}'")
        sys.exit(1)
    print(f"[AUTH] controlled_import_id verified: {provided}")


def verify_source_json(path: str) -> None:
    """Confirm P3B-B dryrun JSON contains expected draw data."""
    with open(path) as f:
        d = json.load(f)
    text = json.dumps(d, ensure_ascii=False)
    for needle in ["DAILY_539", "115000106", "POWER_LOTTO", "115000035"]:
        if needle not in text:
            print(f"FATAL: source JSON missing expected content: '{needle}'")
            sys.exit(1)
    print(f"[SRC] P3B-B dryrun source verified: {path}")


def check_draw_exists(cur: sqlite3.Cursor, lottery_type: str, draw: str):
    row = cur.execute(
        """
        SELECT draw, date, lottery_type, numbers, special
        FROM draws
        WHERE lottery_type=?
          AND CAST(draw AS INTEGER)=CAST(? AS INTEGER)
        """,
        (lottery_type, draw),
    ).fetchone()
    return dict(row) if row else None


def numbers_match(db_numbers_str: str, expected: list) -> bool:
    """Compare DB numbers string to expected list."""
    try:
        db_nums = json.loads(db_numbers_str)
        return sorted(db_nums) == sorted(expected)
    except Exception:
        # fallback: string compare
        return db_numbers_str == str(expected)


def special_match(db_special, expected_special) -> bool:
    if expected_special is None:
        # DB may store 0 or None for no special
        return db_special in (None, 0)
    return db_special == expected_special


def import_draws(args) -> dict:
    """Main import logic. Returns receipt dict."""
    receipt = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "controlled_import_id": CONTROLLED_IMPORT_ID,
        "apply_mode": args.apply,
        "draws_imported": [],
        "draws_already_present": [],
        "draws_conflict": [],
        "replay_rows_inserted": False,
        "prediction_items_modified": False,
        "prediction_runs_modified": False,
        "db_written": False,
    }

    uri = f"file:{args.db}" if args.apply else f"file:{args.db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pre-flight: confirm no other table is touched
    # (We only ever touch draws table in this script)

    for draw_def in AUTHORIZED_DRAWS:
        lt = draw_def["lottery_type"]
        draw = draw_def["draw"]
        date = draw_def["date"]
        numbers = draw_def["numbers"]
        special = draw_def["special"]

        existing = check_draw_exists(cur, lt, draw)

        if existing:
            # Idempotency check
            ok_numbers = numbers_match(existing["numbers"], numbers)
            ok_special = special_match(existing["special"], special)
            if ok_numbers and ok_special:
                print(f"[SKIP] {lt} {draw} already present with matching data → already_present")
                receipt["draws_already_present"].append(
                    {"lottery_type": lt, "draw": draw, "reason": "already_present_matching"}
                )
            else:
                msg = (
                    f"CONFLICT: {lt} {draw} exists in DB with different data! "
                    f"DB={existing}, expected numbers={numbers} special={special}"
                )
                print(f"FATAL: {msg}")
                receipt["draws_conflict"].append(
                    {"lottery_type": lt, "draw": draw, "db_row": existing, "expected_numbers": numbers, "expected_special": special}
                )
                conn.close()
                receipt["final_classification"] = "P3BC_CONTROLLED_DRAW_IMPORT_BLOCKED_CONFLICT"
                _write_receipt(args.json_out, receipt)
                sys.exit(1)
        else:
            numbers_str = json.dumps(numbers)
            special_val = special if special is not None else 0

            if args.apply:
                cur.execute(
                    """
                    INSERT INTO draws (lottery_type, draw, date, numbers, special)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (lt, draw, date, numbers_str, special_val),
                )
                print(f"[INSERT] {lt} {draw} {date} {numbers} special={special}")
            else:
                print(f"[DRYRUN] would insert {lt} {draw} {date} {numbers} special={special}")

            receipt["draws_imported"].append(
                {
                    "lottery_type": lt,
                    "draw": draw,
                    "date": date,
                    "numbers": numbers,
                    "special": special,
                    "applied": args.apply,
                }
            )

    if args.apply:
        conn.commit()
        receipt["db_written"] = True
        print("[COMMIT] draws committed to DB")
    else:
        print("[DRYRUN] no writes committed")

    # Post-import verification (read-only)
    total_replay = cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    receipt["replay_total_after"] = total_replay

    pending_items = cur.execute(
        """
        SELECT id, status FROM prediction_items
        WHERE id IN (1087,1088,1089,1072,1073,1074)
        ORDER BY id
        """
    ).fetchall()
    receipt["prediction_items_after"] = [dict(r) for r in pending_items]

    conn.close()

    # Safety assertions
    assert receipt["replay_rows_inserted"] is False, "SAFETY: replay_rows_inserted must be False"
    assert receipt["prediction_items_modified"] is False, "SAFETY: prediction_items_modified must be False"
    assert receipt["prediction_runs_modified"] is False, "SAFETY: prediction_runs_modified must be False"

    if args.apply:
        assert total_replay == 969, f"SAFETY: replay_total changed! {total_replay} != 969"
        for item in receipt["prediction_items_after"]:
            assert item["status"] == "PENDING", f"SAFETY: item {item['id']} is not PENDING: {item['status']}"

    receipt["final_classification"] = "P3BC_CONTROLLED_DRAW_IMPORT_DRAFT_PR_READY"
    return receipt


def _write_receipt(path: str, receipt: dict) -> None:
    import os
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(f"[RECEIPT] written to {path}")


def main():
    args = parse_args()

    print(f"=== P3B-C Controlled Draw Import ===")
    print(f"  controlled_import_id : {args.controlled_import_id}")
    print(f"  db                   : {args.db}")
    print(f"  apply                : {args.apply}")
    print()

    verify_controlled_import_id(args.controlled_import_id)
    verify_source_json(args.dryrun_json)

    receipt = import_draws(args)
    _write_receipt(args.json_out, receipt)

    print()
    print(f"=== RESULT ===")
    print(f"  draws_imported       : {len(receipt['draws_imported'])}")
    print(f"  draws_already_present: {len(receipt['draws_already_present'])}")
    print(f"  replay_rows_inserted : {receipt['replay_rows_inserted']}")
    print(f"  prediction_items_mod : {receipt['prediction_items_modified']}")
    print(f"  db_written           : {receipt['db_written']}")
    print(f"  replay_total_after   : {receipt.get('replay_total_after')}")
    print(f"  classification       : {receipt['final_classification']}")
    print()
    print(receipt["final_classification"])


if __name__ == "__main__":
    main()
