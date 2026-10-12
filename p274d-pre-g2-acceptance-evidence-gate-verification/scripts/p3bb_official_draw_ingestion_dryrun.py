#!/usr/bin/env python3
"""
P3B-B Official Draw Ingestion Dry-run
=======================================
Fetches DAILY_539 and POWER_LOTTO draws from Taiwan Lottery official source.
PREVIEW ONLY — no DB writes.

Targets:
  - DAILY_539  draw 115000106 → items 1087, 1088, 1089
  - POWER_LOTTO draw 115000035 → items 1072, 1073, 1074

Usage:
    python3 scripts/p3bb_official_draw_ingestion_dryrun.py \
        --db lottery_api/data/lottery_v2.db \
        --targets DAILY_539:115000106,POWER_LOTTO:115000035 \
        --json-out outputs/replay/p3bb_official_draw_ingestion_dryrun_20260516.json \
        --csv-out  outputs/replay/p3bb_official_draw_ingestion_dryrun_20260516.csv
"""

import argparse
import csv
import datetime
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Constants — lottery rules + API endpoints
# ---------------------------------------------------------------------------

BASE_API_URL = "https://api.taiwanlottery.com/TLCAPIWeB"

LOTTERY_RULES = {
    "DAILY_539": {
        "name": "今彩539",
        "api_endpoint": f"{BASE_API_URL}/Lottery/Daily539Result",
        "api_result_key": "daily539Res",
        # drawNumberSize has exactly 5 items (no special ball)
        "draw_numbers_field": "drawNumberSize",
        "api_date_field": "lotteryDate",
        "api_period_field": "period",
        "main_min": 1, "main_max": 39, "pick_count": 5,
        "has_special": False,
    },
    "POWER_LOTTO": {
        "name": "威力彩",
        "api_endpoint": f"{BASE_API_URL}/Lottery/SuperLotto638Result",
        "api_result_key": "superLotto638Res",
        # drawNumberSize has 7 items: first 6 = main numbers (sorted), last = special (1-8)
        "draw_numbers_field": "drawNumberSize",
        "api_date_field": "lotteryDate",
        "api_period_field": "period",
        "main_min": 1, "main_max": 38, "pick_count": 6,
        "has_special": True,
        "special_min": 1, "special_max": 8,
    },
}

# Map from lottery_type to affected PENDING item IDs (for status reporting)
PENDING_ITEMS = {
    "DAILY_539":  {"115000106": [1087, 1088, 1089]},
    "POWER_LOTTO": {"115000035": [1072, 1073, 1074]},
}


# ---------------------------------------------------------------------------
# HTTP fetch helper
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: int = 15):
    """Return parsed JSON from URL, or error dict on failure."""
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
    Fetch a single draw from api.taiwanlottery.com.
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

    content = raw.get("content", {})
    if not content:
        result["fetch_status"] = "BLOCKED_NOT_PUBLISHED"
        result["raw_content"] = raw
        return result

    res_list = content.get(rules["api_result_key"], [])
    if not res_list:
        result["fetch_status"] = "BLOCKED_NOT_PUBLISHED"
        result["raw_content"] = content
        return result

    draw_data = res_list[0]
    result["raw_content"] = draw_data

    draw_nums = draw_data.get(rules["draw_numbers_field"], [])
    date_val = draw_data.get(rules["api_date_field"], "")
    # Normalize date: "2026-04-30T00:00:00" -> "2026/04/30"
    if "T" in str(date_val):
        date_val = date_val.split("T")[0].replace("-", "/")

    period = draw_data.get(rules["api_period_field"], "")

    expected_len = rules["pick_count"] + (1 if rules["has_special"] else 0)
    if len(draw_nums) < expected_len:
        result["fetch_status"] = "PARSE_ERROR"
        result["error"] = f"drawNumberSize has {len(draw_nums)} items, expected {expected_len}"
        return result

    try:
        numbers = sorted([int(n) for n in draw_nums[:rules["pick_count"]]])
        special = int(draw_nums[rules["pick_count"]]) if rules["has_special"] else None
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
    """Validate fetched numbers are within expected ranges."""
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

    if len(set(numbers)) != len(numbers):
        issues.append("duplicate main numbers")

    if rules["has_special"] and special is not None:
        smin = rules.get("special_min", rules["main_min"])
        smax = rules.get("special_max", rules["main_max"])
        if not (smin <= special <= smax):
            issues.append(f"special {special} out of range [{smin}-{smax}]")
    elif rules["has_special"] and special is None:
        issues.append("special is None but lottery requires special ball")

    result["validation"] = {
        "passed": len(issues) == 0,
        "issues": issues,
    }
    return result


# ---------------------------------------------------------------------------
# DB preflight (read-only)
# ---------------------------------------------------------------------------

def check_db_exists(db_path: str, lottery_type: str, draw_numbers: list) -> dict:
    """Read-only check: which target draws already exist in DB."""
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
            existence[draw] = None
        existence["_db_error"] = str(e)
    return existence


def get_pending_items_status(db_path: str, item_ids: list) -> list:
    """Read-only: return status rows for the given prediction_item IDs."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        placeholders = ",".join("?" * len(item_ids))
        rows = cur.execute(
            f"SELECT id, status, numbers, special FROM prediction_items WHERE id IN ({placeholders}) ORDER BY id",
            item_ids,
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"_db_error": str(e)}]


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_csv(results: list, csv_path: str) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "lottery_type", "draw", "date",
            "num1", "num2", "num3", "num4", "num5", "num6",
            "special", "exists_in_db", "fetch_status", "validation_passed", "validation_issues",
        ])
        for r in results:
            nums = r.get("numbers") or []
            padded = (nums + [""] * 6)[:6]
            v = r.get("validation", {})
            writer.writerow([
                r.get("lottery_type", ""),
                r.get("draw", ""),
                r.get("date", ""),
                *padded,
                r.get("special", "") if r.get("special") is not None else "",
                r.get("exists_in_db", ""),
                r.get("fetch_status", ""),
                v.get("passed", ""),
                "; ".join(v.get("issues", [])),
            ])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="P3B-B Official Draw Ingestion Dry-run (DAILY_539 + POWER_LOTTO)")
    parser.add_argument("--db", required=True, help="Path to lottery_v2.db")
    parser.add_argument(
        "--targets", required=True,
        help="Comma-separated LOTTERY_TYPE:DRAW_NUMBER pairs, e.g. DAILY_539:115000106,POWER_LOTTO:115000035"
    )
    parser.add_argument("--json-out", required=True, help="Output JSON path")
    parser.add_argument("--csv-out", required=True, help="Output CSV path")
    args = parser.parse_args()

    # Parse targets
    targets = []
    for token in args.targets.split(","):
        token = token.strip()
        if ":" not in token:
            print(f"ERROR: invalid target format '{token}', expected LOTTERY_TYPE:DRAW_NUMBER", file=sys.stderr)
            return 1
        lt, draw = token.split(":", 1)
        lt = lt.upper()
        if lt not in LOTTERY_RULES:
            print(f"ERROR: unsupported lottery type '{lt}'. Supported: {list(LOTTERY_RULES.keys())}", file=sys.stderr)
            return 1
        targets.append((lt, draw.strip()))

    if not targets:
        print("ERROR: --targets must be non-empty", file=sys.stderr)
        return 1

    print("[DRY-RUN] P3B-B Official Draw Ingestion")
    print(f"[DRY-RUN] Targets: {targets}")
    print(f"[DRY-RUN] DB: {args.db} (READ-ONLY)")
    print("[DRY-RUN] NO DB WRITES WILL OCCUR")
    print()

    all_results = []
    db_preflight_by_type = {}
    pending_items_by_type = {}

    # Phase 1: DB preflight
    print("Phase 1: DB preflight (read-only)...")
    for lt, draw in targets:
        existence = check_db_exists(args.db, lt, [draw])
        db_preflight_by_type[lt] = existence
        print(f"  {lt} draw {draw}: exists_in_db={existence.get(draw)}")

        # Check associated PENDING items
        item_ids = PENDING_ITEMS.get(lt, {}).get(draw, [])
        if item_ids:
            item_rows = get_pending_items_status(args.db, item_ids)
            pending_items_by_type[f"{lt}:{draw}"] = item_rows
            for row in item_rows:
                print(f"    item {row.get('id')}: status={row.get('status')} nums={row.get('numbers')}")

    print()

    # Phase 2: Fetch from official API
    print("Phase 2: Fetching from api.taiwanlottery.com...")
    for lt, draw in targets:
        print(f"  Fetching {lt} draw {draw}...", end=" ", flush=True)
        result = fetch_single_draw(lt, draw)
        result = validate_draw(result, lt)
        result["exists_in_db"] = db_preflight_by_type.get(lt, {}).get(draw)
        all_results.append(result)
        print(f"-> {result['fetch_status']}", end="")
        if result.get("error"):
            print(f" ({result['error']})", end="")
        print()
        time.sleep(0.4)  # polite delay between API calls

    print()

    # Phase 3: Determine overall classification
    statuses = [r["fetch_status"] for r in all_results]
    validations_ok = all(r.get("validation", {}).get("passed") for r in all_results)

    if all(s == "FETCHED" for s in statuses) and validations_ok:
        overall_status = "P3BB_OFFICIAL_DRAW_INGESTION_DRYRUN_READY"
    elif all(s == "FETCHED" for s in statuses) and not validations_ok:
        overall_status = "P3BB_OFFICIAL_DRAW_INGESTION_DRYRUN_PARTIAL_READY"
    elif all(s == "BLOCKED_NOT_PUBLISHED" for s in statuses):
        overall_status = "P3BB_OFFICIAL_DRAW_INGESTION_BLOCKED_NOT_PUBLISHED"
    elif all(s in ("BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE", "BLOCKED_NO_RESPONSE") for s in statuses):
        overall_status = "P3BB_OFFICIAL_DRAW_INGESTION_BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE"
    elif any(s == "FETCHED" for s in statuses):
        overall_status = "P3BB_OFFICIAL_DRAW_INGESTION_DRYRUN_PARTIAL_READY"
    else:
        overall_status = "P3BB_OFFICIAL_DRAW_INGESTION_BLOCKED_EXTERNAL_SOURCE_UNAVAILABLE"

    # Determine PENDING unblock status per lottery_type
    pending_unblock = {}
    for lt, draw in targets:
        key = f"{lt}:{draw}"
        r = next((x for x in all_results if x["lottery_type"] == lt and x["draw"] == draw), None)
        is_ready = (
            r is not None
            and r["fetch_status"] == "FETCHED"
            and r.get("validation", {}).get("passed")
            and not r.get("exists_in_db")
        )
        item_ids = PENDING_ITEMS.get(lt, {}).get(draw, [])
        pending_unblock[key] = {
            "draw": draw,
            "lottery_type": lt,
            "item_ids": item_ids,
            "unblock_status": "READY_PENDING_IMPORT" if is_ready else "BLOCKED",
        }

    # Build output payload
    output = {
        "run_id": "p3bb_official_draw_ingestion_dryrun_20260516",
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
            "targets": [{"lottery_type": lt, "draw": draw} for lt, draw in targets],
            "db_path": args.db,
            "dry_run": True,
        },
        "db_preflight": {
            "db_path": args.db,
            "existence_by_type": {
                lt: {k: v for k, v in db_preflight_by_type[lt].items() if not k.startswith("_")}
                for lt in db_preflight_by_type
            },
        },
        "pending_items": pending_items_by_type,
        "pending_unblock": pending_unblock,
        "draw_results": all_results,
    }

    # Write outputs
    os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    write_csv(all_results, args.csv_out)

    # Print summary
    print("=" * 70)
    print(f"CLASSIFICATION: {overall_status}")
    print()
    print("Draw preview:")
    print(f"  {'lottery_type':<14} {'draw':<12} {'date':<12} {'numbers':<28} {'SP':<4} {'in_db':<6} {'status':<12} {'valid'}")
    for r in all_results:
        v = r.get("validation", {})
        sp = str(r.get("special")) if r.get("special") is not None else "N/A"
        print(f"  {r['lottery_type']:<14} {r['draw']:<12} {r.get('date','N/A'):<12} "
              f"{str(r.get('numbers','')):<28} {sp:<4} {str(r.get('exists_in_db','?')):<6} "
              f"{r['fetch_status']:<12} {v.get('passed','?')}")
    print()
    print("PENDING unblock status:")
    for key, ub in pending_unblock.items():
        print(f"  {key}: items={ub['item_ids']} -> {ub['unblock_status']}")
    print()
    print(f"JSON output: {args.json_out}")
    print(f"CSV  output: {args.csv_out}")
    print("=" * 70)
    print("[DRY-RUN COMPLETE] No DB writes performed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
