#!/usr/bin/env python3
"""
P2D Official Draw Ingestion Dry-run
=====================================
Fetches BIG_LOTTO draws from Taiwan Lottery official source.
PREVIEW ONLY — no DB writes.

Usage:
    python3 scripts/p2d_official_draw_ingestion_dryrun.py \
        --db lottery_api/data/lottery_v2.db \
        --lottery-type BIG_LOTTO \
        --draws 115000051,115000052,115000053 \
        --json-out outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json \
        --csv-out outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.csv
"""

import argparse
import csv
import datetime
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOTTERY_RULES = {
    "BIG_LOTTO": {
        "name": "大樂透",
        "api_endpoint": "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result",
        "api_result_key": "lotto649Res",
        # drawNumberSize has 7 items: first 6 = main numbers (sorted), last = special
        "draw_numbers_field": "drawNumberSize",
        "api_date_field": "lotteryDate",
        "api_period_field": "period",
        "main_min": 1, "main_max": 49, "pick_count": 6,
        "special_min": 1, "special_max": 49,
    },
}

BASE_API_URL = "https://api.taiwanlottery.com/TLCAPIWeB"

# ---------------------------------------------------------------------------
# HTTP fetch helper
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: int = 15):
    """Return parsed JSON from URL, or None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (LotteryResearch DryRun/1.0)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_http_reason": str(e.reason)}
    except Exception as e:
        return {"_error": str(e)}


# ---------------------------------------------------------------------------
# Fetch a single draw from official API
# ---------------------------------------------------------------------------

def fetch_single_draw(lottery_type: str, draw_number: str) -> dict:
    """
    Try fetching a single draw from api.taiwanlottery.com.
    Returns a dict with keys: source_url, fetch_status, draw, date, numbers, special, raw_content, error.
    """
    rules = LOTTERY_RULES[lottery_type]
    url = f"{rules['api_endpoint']}?period={draw_number}"

    result = {
        "source_url": url,
        "draw": draw_number,
        "lottery_type": lottery_type,
        "fetch_status": None,
        "date": None,
        "numbers": None,
        "special": None,
        "raw_content": None,
        "error": None,
    }

    raw = _http_get(url)

    if raw is None:
        result["fetch_status"] = "BLOCKED_NO_RESPONSE"
        return result

    if "_error" in raw or "_http_error" in raw:
        result["fetch_status"] = "BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE"
        result["error"] = raw.get("_error") or f"HTTP {raw.get('_http_error')}: {raw.get('_http_reason')}"
        return result

    # Parse content: {"rtCode": 0, "content": {"totalSize": N, "lotto649Res": [...]}}
    content = raw.get("content", {})
    if not content:
        result["fetch_status"] = "BLOCKED_NO_TARGET_DRAWS_FOUND"
        result["raw_content"] = raw
        return result

    res_list = content.get(rules["api_result_key"], [])
    if not res_list:
        result["fetch_status"] = "BLOCKED_NO_TARGET_DRAWS_FOUND"
        result["raw_content"] = content
        return result

    draw_data = res_list[0]
    result["raw_content"] = draw_data

    # drawNumberSize: 7 ints — first 6 are main (sorted asc), last is special
    draw_nums = draw_data.get(rules["draw_numbers_field"], [])
    date_val = draw_data.get(rules["api_date_field"], "")
    # Normalize date: "2026-05-05T00:00:00" -> "2026/05/09"
    if "T" in str(date_val):
        date_val = date_val.split("T")[0].replace("-", "/")

    period = draw_data.get(rules["api_period_field"], "")

    if len(draw_nums) < 7:
        result["fetch_status"] = "PARSE_ERROR"
        result["error"] = f"drawNumberSize has {len(draw_nums)} items, expected 7"
        return result

    try:
        numbers = [int(n) for n in draw_nums[:6]]
        special = int(draw_nums[6])
    except Exception as e:
        result["fetch_status"] = "PARSE_ERROR"
        result["error"] = f"numbers parse failed: {e}"
        return result

    result["date"] = date_val
    result["numbers"] = numbers
    result["special"] = special
    result["period_from_api"] = str(period)
    result["fetch_status"] = "FETCHED"
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_draw(result: dict, lottery_type: str) -> dict:
    """
    Validate that fetched numbers are within expected ranges.
    Returns result dict augmented with 'validation' key.
    """
    rules = LOTTERY_RULES[lottery_type]
    issues = []

    if result["fetch_status"] != "FETCHED":
        result["validation"] = {"passed": False, "issues": ["not_fetched"]}
        return result

    numbers = result["numbers"]
    special = result["special"]

    if len(numbers) != rules["pick_count"]:
        issues.append(f"expected {rules['pick_count']} main numbers, got {len(numbers)}")

    for n in numbers:
        if not (rules["main_min"] <= n <= rules["main_max"]):
            issues.append(f"main number {n} out of range [{rules['main_min']}-{rules['main_max']}]")

    if not (rules["special_min"] <= special <= rules["special_max"]):
        issues.append(f"special {special} out of range [{rules['special_min']}-{rules['special_max']}]")

    if len(set(numbers)) != len(numbers):
        issues.append("duplicate main numbers")

    result["validation"] = {
        "passed": len(issues) == 0,
        "issues": issues,
    }
    return result


# ---------------------------------------------------------------------------
# DB existence check (read-only)
# ---------------------------------------------------------------------------

def check_db_exists(db_path: str, lottery_type: str, draw_numbers: list) -> dict:
    """
    Read-only check: which of the target draws already exist in DB.
    Returns dict: draw_number -> bool.
    """
    existence = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        for draw in draw_numbers:
            row = cur.execute(
                "SELECT 1 FROM draws WHERE lottery_type=? AND CAST(draw AS INTEGER)=CAST(? AS INTEGER)",
                (lottery_type, draw),
            ).fetchone()
            existence[draw] = bool(row)
        conn.close()
    except Exception as e:
        for draw in draw_numbers:
            existence[draw] = None  # unknown
        existence["_db_error"] = str(e)
    return existence


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(results: list[dict], csv_path: str) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "draw", "date", "lottery_type",
            "num1", "num2", "num3", "num4", "num5", "num6",
            "special", "exists_in_db", "fetch_status", "validation_passed", "validation_issues",
        ])
        for r in results:
            nums = r.get("numbers") or []
            padded = (nums + [""] * 6)[:6]
            writer.writerow([
                r.get("draw", ""),
                r.get("date", ""),
                r.get("lottery_type", ""),
                *padded,
                r.get("special", ""),
                r.get("exists_in_db", ""),
                r.get("fetch_status", ""),
                r.get("validation", {}).get("passed", ""),
                "; ".join(r.get("validation", {}).get("issues", [])),
            ])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="P2D Official Draw Ingestion Dry-run")
    parser.add_argument("--db", required=True, help="Path to lottery_v2.db")
    parser.add_argument("--lottery-type", default="BIG_LOTTO", help="Lottery type (default: BIG_LOTTO)")
    parser.add_argument("--draws", required=True, help="Comma-separated draw numbers to fetch")
    parser.add_argument("--json-out", required=True, help="Output JSON path")
    parser.add_argument("--csv-out", required=True, help="Output CSV path")
    args = parser.parse_args()

    lottery_type = args.lottery_type.upper()
    if lottery_type not in LOTTERY_RULES:
        print(f"ERROR: unsupported lottery type {lottery_type}. Supported: {list(LOTTERY_RULES.keys())}", file=sys.stderr)
        return 1

    draw_numbers = [d.strip() for d in args.draws.split(",") if d.strip()]
    if not draw_numbers:
        print("ERROR: --draws must be non-empty", file=sys.stderr)
        return 1

    print(f"[DRY-RUN] P2D Official Draw Ingestion — {lottery_type}")
    print(f"[DRY-RUN] Target draws: {draw_numbers}")
    print(f"[DRY-RUN] DB: {args.db} (READ-ONLY)")
    print(f"[DRY-RUN] NO DB WRITES WILL OCCUR")
    print()

    # --- DB preflight ---
    print("Phase 1: DB preflight (read-only)...")
    db_existence = check_db_exists(args.db, lottery_type, draw_numbers)
    for draw, exists in db_existence.items():
        if draw.startswith("_"):
            continue
        print(f"  draw {draw}: exists_in_db={exists}")

    # --- Fetch from official API ---
    print()
    print("Phase 2: Fetching from api.taiwanlottery.com...")
    draw_results = []
    overall_status = None

    for draw in draw_numbers:
        print(f"  Fetching draw {draw}...", end=" ", flush=True)
        result = fetch_single_draw(lottery_type, draw)
        result = validate_draw(result, lottery_type)
        result["exists_in_db"] = db_existence.get(draw)
        draw_results.append(result)
        print(f"  -> {result['fetch_status']}", end="")
        if result.get("error"):
            print(f" ({result['error']})", end="")
        print()
        time.sleep(0.3)  # polite delay

    # --- Determine overall classification ---
    statuses = [r["fetch_status"] for r in draw_results]
    if all(s == "FETCHED" for s in statuses):
        if all(r["validation"]["passed"] for r in draw_results):
            overall_status = "P2D_OFFICIAL_DRAW_INGESTION_DRYRUN_READY"
        else:
            overall_status = "P2D_OFFICIAL_DRAW_INGESTION_DRYRUN_PARTIAL_READY"
    elif all(s in ("BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE", "BLOCKED_NO_RESPONSE") for s in statuses):
        overall_status = "P2D_OFFICIAL_DRAW_INGESTION_BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE"
    elif all(s == "BLOCKED_NO_TARGET_DRAWS_FOUND" for s in statuses):
        overall_status = "P2D_OFFICIAL_DRAW_INGESTION_BLOCKED_NO_TARGET_DRAWS_FOUND"
    elif any(s == "FETCHED" for s in statuses):
        overall_status = "P2D_OFFICIAL_DRAW_INGESTION_DRYRUN_PARTIAL_READY"
    else:
        overall_status = "P2D_OFFICIAL_DRAW_INGESTION_BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE"

    # Determine P2C unblock status
    target_missing = [r for r in draw_results if not r.get("exists_in_db")]
    ready_draws = [r for r in target_missing if r["fetch_status"] == "FETCHED" and r["validation"]["passed"]]
    p2c_unblock = "READY_PENDING_IMPORT" if len(ready_draws) > 0 else "BLOCKED"

    # --- Build output payload ---
    output = {
        "run_id": "p2d_official_draw_ingestion_dryrun_20260515",
        "generated_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "overall_classification": overall_status,
        "safety": {
            "db_written": False,
            "replay_rows_generated": False,
            "draw_rows_inserted": False,
            "prediction_items_promoted": False,
            "strategy_logic_changed": False,
            "api_ui_backend_changed": False,
        },
        "config": {
            "lottery_type": lottery_type,
            "db_path": args.db,
            "target_draws": draw_numbers,
            "dry_run": True,
        },
        "p2c_unblock_status": p2c_unblock,
        "p2c_ready_draws": [r["draw"] for r in ready_draws],
        "db_preflight": {
            "db_path": args.db,
            "existence_by_draw": {k: v for k, v in db_existence.items() if not k.startswith("_")},
        },
        "draw_results": draw_results,
    }

    # --- Write outputs ---
    import os
    os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    write_csv(draw_results, args.csv_out)

    # --- Summary ---
    print()
    print("=" * 60)
    print(f"CLASSIFICATION: {overall_status}")
    print(f"P2C unblock:    {p2c_unblock}")
    print(f"JSON output:    {args.json_out}")
    print(f"CSV output:     {args.csv_out}")
    print()
    print("Draw preview:")
    for r in draw_results:
        v = r.get("validation", {})
        print(f"  {r['draw']} | {r.get('date','N/A')} | {r.get('numbers')} SP={r.get('special')} | "
              f"exists={r.get('exists_in_db')} | {r['fetch_status']} | valid={v.get('passed')}")
    print("=" * 60)
    print("[DRY-RUN COMPLETE] No DB writes performed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
