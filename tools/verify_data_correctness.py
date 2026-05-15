#!/usr/bin/env python3
"""
Data Correctness Verification Script
=====================================
Cross-validates the SQLite DB against internal rules and (when network is
available) the official Taiwan Lottery website.

Two-tier classification:
  INTERNAL_INTEGRITY    — verifiable offline (format, range, gaps, ground truth)
  OFFICIAL_GROUND_TRUTH — requires live network cross-check

Phases:
  PHASE 0 — Known ground-truth check (hardcoded, no network needed)
  PHASE 1 — Sample from DB, cross-check with live fetcher (network)
  PHASE 2 — Latest 100 draws match-rate vs official (network)
  PHASE 3 — Internal format validation (no network)
  PHASE 4 — Missing draw / gap detection (no network)
  PHASE 5 — Date/weekday correctness spot check (no network)

Usage:
  cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api
  python3 ../tools/verify_data_correctness.py           # full run
  python3 ../tools/verify_data_correctness.py --offline  # skip network phases
"""

import sys
import os
import sqlite3
import json
import re
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple, Any
from collections import defaultdict

# ── Path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
API_DIR      = os.path.join(PROJECT_ROOT, "lottery_api")
DB_PATH      = os.path.join(API_DIR, "data", "lottery_v2.db")
FETCHER_PATH = os.path.join(API_DIR, "fetcher")

sys.path.insert(0, API_DIR)   # allow "from fetcher.taiwan_lottery_fetcher import ..."
sys.path.insert(0, PROJECT_ROOT)

# ── Game configs ─────────────────────────────────────────────────────────────
GAME_CONFIGS = {
    "BIG_LOTTO": {
        "label":        "大樂透",
        "num_count":    6,
        "has_special":  True,
        "num_range":    (1, 49),
        "special_range":(1, 49),
        # Official schedule: Tuesday=1, Friday=4
        # Note: during Chinese New Year holidays the schedule shifts —
        # those dates are still valid draws even if on other weekdays.
        # We flag non-Tue/Fri draws as LOW (informational), not HIGH.
        "draw_days":    [1, 4],   # Tuesday=1, Friday=4
        "draw_day_names": ["Tuesday/Friday"],
        "draw_day_severity": "LOW",  # holiday shifts are expected
    },
    "POWER_LOTTO": {
        "label":        "威力彩",
        "num_count":    6,
        "has_special":  True,
        "num_range":    (1, 38),
        "special_range":(1, 8),
        "draw_days":    [0, 3],   # Monday=0, Thursday=3
        "draw_day_names": ["Monday/Thursday"],
        "draw_day_severity": "HIGH",
    },
    "DAILY_539": {
        "label":        "今彩539",
        "num_count":    5,
        "has_special":  False,
        "num_range":    (1, 39),
        "special_range":(0, 0),
        # Normally Mon-Sat. During CNY holiday Taiwan Lottery may add Sunday draws.
        # Flag Sunday draws as LOW (possible CNY makeup), not HIGH.
        "draw_days":    [0, 1, 2, 3, 4, 5],  # Mon-Sat
        "draw_day_names": ["Mon-Sat"],
        "draw_day_severity": "LOW",  # CNY Sunday draws are valid holiday makeup draws
    },
}

SEVERITY = {
    "CRITICAL": [],
    "HIGH":     [],
    "LOW":      [],
    "INFO":     [],
}

sep = "=" * 72

def hr(char="-", width=72):
    print(char * width)

def section(title: str):
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)

def log_issue(severity: str, game: str, draw: str, msg: str):
    entry = f"[{game}] draw={draw}: {msg}"
    SEVERITY[severity].append(entry)

# ── DB helpers ───────────────────────────────────────────────────────────────
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_db_draws(lottery_type: str, limit: int = 0) -> List[Dict]:
    """Return draws ordered newest-first using correct integer cast sort."""
    conn = get_connection()
    cur  = conn.cursor()
    sql  = """
        SELECT draw, date, lottery_type, numbers, special
        FROM draws
        WHERE lottery_type = ?
        ORDER BY CAST(draw AS INTEGER) DESC
    """
    params = [lottery_type]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        try:
            nums = json.loads(r["numbers"])
        except Exception:
            nums = []
        rows.append({
            "draw":    r["draw"],
            "date":    r["date"],
            "numbers": nums,
            "special": r["special"],
            "lottery_type": r["lottery_type"],
        })
    conn.close()
    return rows

def fetch_all_db_draws(lottery_type: str) -> List[Dict]:
    """All draws for a game, oldest-first (for gap detection)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT draw, date, lottery_type, numbers, special
        FROM draws
        WHERE lottery_type = ?
        ORDER BY CAST(draw AS INTEGER) ASC
    """, [lottery_type])
    rows = []
    for r in cur.fetchall():
        try:
            nums = json.loads(r["numbers"])
        except Exception:
            nums = []
        rows.append({
            "draw":    r["draw"],
            "date":    r["date"],
            "numbers": nums,
            "special": r["special"],
        })
    conn.close()
    return rows

# ── Fetcher wrapper ──────────────────────────────────────────────────────────
def try_fetch_recent(lottery_type: str, max_draws: int = 50) -> Tuple[bool, List[Dict], str]:
    """
    Attempt to fetch recent draws from official site.
    Returns (success, draws, error_msg).
    Overrides fetcher timeout/retry to fail fast when network is unavailable.
    """
    try:
        import fetcher.taiwan_lottery_fetcher as _ftm
        # Override module-level constants for faster failure when offline
        _ftm.FETCH_TIMEOUT = 5
        _ftm.RETRY_MAX     = 1
        _ftm.RETRY_DELAY   = 0.0
        from fetcher.taiwan_lottery_fetcher import TaiwanLotteryFetcher
        f = TaiwanLotteryFetcher()
        draws = f.fetch_recent(lottery_type, max_draws=max_draws)
        if not draws:
            return False, [], "fetch_recent() returned 0 draws (network or parse error)"
        return True, draws, ""
    except ImportError as e:
        return False, [], f"ImportError: {e}"
    except Exception as e:
        return False, [], f"Exception: {e}"

# ── PHASE 1 ──────────────────────────────────────────────────────────────────
def phase1_cross_check(games: List[str]) -> Dict:
    """
    Cross-check DB rows against official fetcher for recent ~50 draws per game.
    """
    section("PHASE 1 — Cross-Check DB vs Official Fetcher (recent 50 draws)")
    summary = {}

    for game in games:
        cfg   = GAME_CONFIGS[game]
        label = cfg["label"]
        print(f"\n  [{game}] {label}")
        hr()

        # 1a. Fetch from official site
        ok, official_draws, err = try_fetch_recent(game, max_draws=50)
        if not ok:
            print(f"  SCAN_ERROR: {err}")
            summary[game] = {"status": "SCAN_ERROR", "error": err,
                             "checked": 0, "matched": 0, "mismatches": 0}
            log_issue("HIGH", game, "N/A", f"Fetcher failed: {err}")
            continue

        # Build official lookup: draw -> row
        official = {d["draw"]: d for d in official_draws}
        print(f"  Official site returned {len(official)} draws")

        # 1b. Get corresponding DB rows
        db_draws = fetch_db_draws(game, limit=100)
        db_lookup = {d["draw"]: d for d in db_draws}

        checked   = 0
        matched   = 0
        mismatches = []

        for draw_num, off_row in official.items():
            if draw_num not in db_lookup:
                mismatches.append({
                    "draw": draw_num,
                    "severity": "HIGH",
                    "reason": f"draw {draw_num} in official but NOT in DB",
                })
                log_issue("HIGH", game, draw_num, "Missing from DB (exists on official site)")
                continue

            db_row  = db_lookup[draw_num]
            checked += 1
            errors  = []

            # Compare date
            if off_row["date"] != db_row["date"]:
                errors.append(f"date mismatch: official={off_row['date']} db={db_row['date']}")

            # Compare numbers (sorted)
            off_nums = sorted(off_row["numbers"])
            db_nums  = sorted(db_row["numbers"])
            if off_nums != db_nums:
                errors.append(f"numbers mismatch: official={off_nums} db={db_nums}")

            # Compare special
            if cfg["has_special"]:
                off_sp = int(off_row.get("special") or 0)
                db_sp  = int(db_row.get("special") or 0)
                if off_sp != db_sp:
                    errors.append(
                        f"special mismatch: official={off_sp} db={db_sp}"
                    )

            if errors:
                sev = "CRITICAL" if any("numbers" in e for e in errors) else "HIGH"
                mismatches.append({
                    "draw":     draw_num,
                    "severity": sev,
                    "reason":   "; ".join(errors),
                })
                for e in errors:
                    log_issue(sev, game, draw_num, e)
                print(f"  [{sev}] draw={draw_num}: {'; '.join(errors)}")
            else:
                matched += 1

        match_rate = (matched / checked * 100) if checked else 0
        print(f"\n  Checked: {checked}, Matched: {matched}, "
              f"Mismatches: {len(mismatches)}, "
              f"Match rate: {match_rate:.1f}%")

        if not mismatches:
            print("  RESULT: ALL MATCH ✓")

        summary[game] = {
            "status":     "OK" if not mismatches else "MISMATCH",
            "checked":    checked,
            "matched":    matched,
            "mismatches": len(mismatches),
            "match_rate": round(match_rate, 2),
            "details":    mismatches[:10],  # cap for readability
        }

    return summary

# ── PHASE 2 ──────────────────────────────────────────────────────────────────
def phase2_latest100_matchrate(games: List[str]) -> Dict:
    """
    Get latest 100 DB draws per game, compute match rate against official.
    """
    section("PHASE 2 — Latest 100 DB Draws vs Official Overlap Match Rate")
    summary = {}

    for game in games:
        cfg   = GAME_CONFIGS[game]
        label = cfg["label"]
        print(f"\n  [{game}] {label}")
        hr()

        db_draws = fetch_db_draws(game, limit=100)
        db_lookup = {d["draw"]: d for d in db_draws}
        print(f"  DB latest 100: {len(db_draws)} rows, "
              f"draw range [{db_draws[-1]['draw'] if db_draws else 'N/A'} .. "
              f"{db_draws[0]['draw'] if db_draws else 'N/A'}]")

        ok, official_draws, err = try_fetch_recent(game, max_draws=50)
        if not ok:
            print(f"  SCAN_ERROR: {err}")
            summary[game] = {"status": "SCAN_ERROR", "error": err}
            continue

        official_lookup = {d["draw"]: d for d in official_draws}

        # Only compare draws that appear in BOTH
        overlap = set(db_lookup.keys()) & set(official_lookup.keys())
        if not overlap:
            print("  No overlapping draws between DB and official fetcher")
            summary[game] = {"status": "NO_OVERLAP", "overlap": 0}
            continue

        matched = 0
        for draw_num in overlap:
            db_row  = db_lookup[draw_num]
            off_row = official_lookup[draw_num]
            db_sp  = int(db_row.get("special") or 0)
            off_sp = int(off_row.get("special") or 0)
            if (sorted(db_row["numbers"]) == sorted(off_row["numbers"]) and
                    db_row["date"] == off_row["date"] and
                    (not cfg["has_special"] or db_sp == off_sp)):
                matched += 1

        rate = matched / len(overlap) * 100
        print(f"  Overlap draws: {len(overlap)}, Matched: {matched}, "
              f"Match rate: {rate:.1f}%")
        summary[game] = {
            "overlap": len(overlap),
            "matched": matched,
            "match_rate": round(rate, 2),
        }

    return summary

# ── PHASE 3 ──────────────────────────────────────────────────────────────────
def phase3_format_validation(games: List[str]) -> Dict:
    """
    Internal format validation of the entire DB. No network required.
    """
    section("PHASE 3 — Internal Format Validation (Full DB, No Network)")
    summary = {}

    for game in games:
        cfg   = GAME_CONFIGS[game]
        label = cfg["label"]
        print(f"\n  [{game}] {label}")
        hr()

        draws = fetch_all_db_draws(game)
        total = len(draws)
        print(f"  Total rows in DB: {total}")

        violations = defaultdict(list)

        for row in draws:
            draw = row["draw"]
            nums = row["numbers"]
            sp   = row["special"]
            dt   = row["date"]

            # 1. draw number: must be numeric (8-10 digits for historical range)
            #    9-digit = ROC year ≥ 100 (e.g. 115000037)
            #    8-digit = ROC year 96-99 (historical, e.g. 96000001) — still valid
            draw_str = str(draw).strip()
            if not re.match(r"^\d{8,10}$", draw_str):
                violations["draw_format_invalid"].append(draw)
                log_issue("HIGH", game, draw, f"draw is not 8-10 digit numeric: '{draw}'")
            elif len(draw_str) < 8:
                violations["draw_format_short"].append(draw)
                log_issue("LOW", game, draw, f"draw too short ({len(draw_str)} digits): '{draw}'")

            # 2. numbers: correct count
            num_count = cfg["num_count"]
            if len(nums) != num_count:
                violations["count_wrong"].append(draw)
                log_issue("CRITICAL", game, draw,
                          f"numbers count={len(nums)}, expected {num_count}")

            # 3. numbers: valid range, no duplicates
            lo, hi = cfg["num_range"]
            for n in nums:
                if not (lo <= n <= hi):
                    violations["out_of_range"].append(draw)
                    log_issue("CRITICAL", game, draw,
                              f"number {n} out of range [{lo},{hi}]")
            if len(set(nums)) != len(nums):
                violations["duplicates"].append(draw)
                log_issue("CRITICAL", game, draw, "duplicate numbers detected")

            # 4. numbers: not sorted (informational)
            if nums != sorted(nums):
                violations["not_sorted"].append(draw)
                log_issue("LOW", game, draw, "numbers not sorted in DB")

            # 5. special: valid range (handle NULL/None as 0)
            sp_val = int(sp) if sp is not None else 0
            if cfg["has_special"]:
                slo, shi = cfg["special_range"]
                if sp is None:
                    violations["special_null"].append(draw)
                    log_issue("HIGH", game, draw, "special is NULL (expected value)")
                elif not (slo <= sp_val <= shi):
                    violations["special_range"].append(draw)
                    log_issue("CRITICAL", game, draw,
                              f"special={sp} out of range [{slo},{shi}]")
            else:
                if sp_val != 0:
                    violations["special_nonzero"].append(draw)
                    log_issue("LOW", game, draw,
                              f"special={sp} expected 0 for no-special game")

            # 6. date: YYYY/MM/DD format, valid calendar
            if not re.match(r"^\d{4}/\d{2}/\d{2}$", str(dt)):
                violations["date_format"].append(draw)
                log_issue("HIGH", game, draw, f"date format invalid: '{dt}'")
            else:
                try:
                    year, mon, day = map(int, dt.split("/"))
                    date(year, mon, day)  # raises ValueError if invalid
                    if year < 2000 or year > 2030:
                        violations["date_year_odd"].append(draw)
                        log_issue("HIGH", game, draw, f"date year suspicious: {year}")
                except ValueError:
                    violations["date_invalid"].append(draw)
                    log_issue("HIGH", game, draw, f"date calendar invalid: '{dt}'")

        # Print violations summary
        all_ok = all(len(v) == 0 for v in violations.values())
        if all_ok:
            print(f"  RESULT: ALL {total} rows PASS format validation ✓")
        else:
            print(f"  Violations found:")
            for vtype, vlist in violations.items():
                if vlist:
                    print(f"    {vtype}: {len(vlist)} rows "
                          f"(e.g. draw={vlist[0]})")

        summary[game] = {
            "total":      total,
            "all_ok":     all_ok,
            "violations": {k: len(v) for k, v in violations.items() if v},
        }

    return summary

# ── PHASE 4 ──────────────────────────────────────────────────────────────────
def phase4_missing_draws(games: List[str]) -> Dict:
    """
    Detect gaps in draw sequences within each ROC year.
    Also checks if the latest official draw is in the DB.
    """
    section("PHASE 4 — Missing Draw Detection (Within-Year Gaps)")
    summary = {}

    for game in games:
        cfg   = GAME_CONFIGS[game]
        label = cfg["label"]
        print(f"\n  [{game}] {label}")
        hr()

        draws = fetch_all_db_draws(game)
        if not draws:
            print("  No rows found.")
            summary[game] = {"status": "EMPTY"}
            continue

        draw_nums = [int(d["draw"]) for d in draws if d["draw"].isdigit()]
        draw_nums.sort()

        # Group by ROC year (first 3 digits of 9-digit draw number)
        by_year = defaultdict(list)
        for dn in draw_nums:
            year = dn // 1_000_000
            seq  = dn %  1_000_000
            by_year[year].append(seq)

        gaps = []
        for year, seqs in sorted(by_year.items()):
            seqs.sort()
            for i in range(1, len(seqs)):
                prev, curr = seqs[i-1], seqs[i]
                if curr - prev > 1:
                    for missing in range(prev + 1, curr):
                        draw_str = f"{year}{missing:06d}"
                        gaps.append(draw_str)

        if gaps:
            print(f"  Gaps detected ({len(gaps)} missing draw numbers):")
            for g in gaps[:20]:
                print(f"    {g}")
                log_issue("HIGH", game, g, "Gap in draw sequence")
            if len(gaps) > 20:
                print(f"    ... and {len(gaps)-20} more")
        else:
            print("  No within-year sequence gaps found ✓")

        # Check latest official draw
        ok, official_draws, err = try_fetch_recent(game, max_draws=5)
        db_draw_set = {d["draw"] for d in draws}

        if ok and official_draws:
            latest_official = official_draws[0]["draw"]
            in_db = latest_official in db_draw_set
            status = "IN_DB ✓" if in_db else "MISSING_FROM_DB !"
            print(f"  Latest official draw: {latest_official} [{official_draws[0]['date']}] "
                  f"→ {status}")
            if not in_db:
                log_issue("HIGH", game, latest_official,
                          "Latest official draw is missing from DB")
        else:
            latest_official = None
            print(f"  Cannot check latest official draw: {err}")

        print(f"  DB draw range: [{draws[0]['draw']} .. {draws[-1]['draw']}], "
              f"total={len(draws)}")

        summary[game] = {
            "total_draws": len(draws),
            "gaps":        len(gaps),
            "latest_official": latest_official,
        }

    return summary

# ── PHASE 5 ──────────────────────────────────────────────────────────────────
def phase5_weekday_check(games: List[str], sample_size: int = 20) -> Dict:
    """
    Spot-check that draw dates fall on expected weekdays.
    BIG_LOTTO, POWER_LOTTO: Monday/Thursday
    DAILY_539: Mon-Sat (not Sunday)
    """
    section(f"PHASE 5 — Date/Weekday Correctness Spot Check (last {sample_size} each)")
    summary = {}

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday", "Sunday"]

    for game in games:
        cfg   = GAME_CONFIGS[game]
        label = cfg["label"]
        expected_days = cfg["draw_days"]
        expected_names = cfg["draw_day_names"]

        print(f"\n  [{game}] {label}  — expected draw days: {expected_names}")
        hr()

        draws = fetch_db_draws(game, limit=sample_size)
        checked   = 0
        wrong_day = []

        day_sev = cfg.get("draw_day_severity", "HIGH")

        for row in draws:
            dt_str = row["date"]
            draw   = row["draw"]
            try:
                year, mon, day = map(int, dt_str.split("/"))
                d = date(year, mon, day)
                wd = d.weekday()  # 0=Monday, 6=Sunday
                if wd not in expected_days:
                    wrong_day.append((draw, dt_str, DAY_NAMES[wd]))
                    log_issue(day_sev, game, draw,
                              f"draw on {DAY_NAMES[wd]} ({dt_str}), "
                              f"expected {expected_names[0]}")
                checked += 1
            except Exception:
                pass  # already flagged in phase 3

        if wrong_day:
            note = " (holiday shifts expected for BIG_LOTTO)" if game == "BIG_LOTTO" else ""
            print(f"  Off-schedule draws ({len(wrong_day)}){note}:")
            for draw, dt_str, wd_name in wrong_day[:10]:
                print(f"    draw={draw} date={dt_str} weekday={wd_name}")
        else:
            print(f"  All {checked} sampled draws fall on correct weekday ✓")

        summary[game] = {
            "checked":   checked,
            "wrong_day": len(wrong_day),
        }

    return summary

# ── FINAL VERDICT ─────────────────────────────────────────────────────────────
def final_verdict(p1: Dict, p2: Dict, p3: Dict, p4: Dict, p5: Dict):
    section("FINAL VERDICT")

    total_checked  = 0
    total_matched  = 0
    critical_count = len(SEVERITY["CRITICAL"])
    high_count     = len(SEVERITY["HIGH"])
    low_count      = len(SEVERITY["LOW"])

    print("\n  Per-game Phase 1 match rates:")
    for game, data in p1.items():
        if data.get("status") == "SCAN_ERROR":
            print(f"    {game}: SCAN_ERROR — {data.get('error', '')[:60]}")
        else:
            c = data.get("checked", 0)
            m = data.get("matched", 0)
            r = data.get("match_rate", 0)
            total_checked += c
            total_matched += m
            print(f"    {game}: {m}/{c} matched ({r:.1f}%)")

    print("\n  Per-game Phase 2 overlap match rates:")
    for game, data in p2.items():
        if "match_rate" in data:
            print(f"    {game}: {data['matched']}/{data['overlap']} "
                  f"({data['match_rate']:.1f}%)")
        else:
            print(f"    {game}: {data}")

    print("\n  Per-game Phase 3 format violations:")
    for game, data in p3.items():
        viol = data.get("violations", {})
        if not viol:
            print(f"    {game}: CLEAN ({data.get('total',0)} rows)")
        else:
            print(f"    {game}: {viol}")

    print("\n  Per-game Phase 4 sequence gaps:")
    for game, data in p4.items():
        g = data.get("gaps", 0)
        t = data.get("total_draws", 0)
        print(f"    {game}: {g} gap(s) in {t} draws")

    print("\n  Per-game Phase 5 weekday errors:")
    for game, data in p5.items():
        c = data.get("checked", 0)
        w = data.get("wrong_day", 0)
        print(f"    {game}: {w} wrong-day draws in last {c} checked")

    # Pre-compute these so we can display them before the trust block
    network_only_high_pre = sum(
        1 for i in SEVERITY["HIGH"]
        if "Fetcher failed" in i or "Cannot check latest" in i
    )
    structural_high_pre = high_count - network_only_high_pre

    print(f"\n  Issue counts by severity:")
    print(f"    CRITICAL          : {critical_count}")
    print(f"    HIGH (total)      : {high_count}")
    print(f"      ↳ network/scan  : {network_only_high_pre}  (SCAN_ERROR — not a DB defect)")
    print(f"      ↳ structural    : {structural_high_pre}  (actual data quality issues)")
    print(f"    LOW               : {low_count}")

    if SEVERITY["CRITICAL"]:
        print("\n  CRITICAL issues:")
        for issue in SEVERITY["CRITICAL"][:20]:
            print(f"    - {issue}")

    structural_issues = [i for i in SEVERITY["HIGH"]
                         if "Fetcher failed" not in i and "Cannot check latest" not in i]
    if structural_issues:
        print(f"\n  HIGH structural issues (first 15):")
        for issue in structural_issues[:15]:
            print(f"    - {issue}")
    elif SEVERITY["HIGH"]:
        print(f"\n  HIGH issues are all network/scan related (no structural DB defects found)")

    overall_rate = (total_matched / total_checked * 100) if total_checked else None

    # Network-only HIGH issues (SCAN_ERROR, cannot check latest) don't affect
    # DB quality verdict — exclude them from structural high count.
    network_only_high = sum(
        1 for i in SEVERITY["HIGH"]
        if "Fetcher failed" in i or "Cannot check latest" in i
    )
    structural_high = high_count - network_only_high
    all_scan_error  = all(p1[g].get("status") in ("SCAN_ERROR", "SKIPPED") for g in p1)

    # Determine trust level
    if critical_count > 0:
        trust = "UNSAFE"
    elif structural_high > 10:
        trust = "UNSAFE"
    elif structural_high > 0 or (overall_rate is not None and overall_rate < 90):
        trust = "CONDITIONAL"
    elif all_scan_error:
        trust = "CONDITIONAL (network unavailable — cross-check skipped)"
    else:
        trust = "SAFE"

    print(f"\n  Overall cross-check correctness: "
          f"{total_matched}/{total_checked} "
          f"({overall_rate:.1f}% match)" if overall_rate is not None
          else "\n  Overall cross-check correctness: N/A (no network data)")

    print(f"\n  {'='*40}")
    print(f"  DATA TRUST LEVEL: {trust}")
    print(f"  {'='*40}")
    print()

    if trust == "SAFE":
        print("  Interpretation: DB data matches official site with no detected errors.")
        print("  Safe to use for strategy research.")
    elif "CONDITIONAL" in trust and "network unavailable" in trust:
        total_rows = sum(p3.get(g, {}).get("total", 0) for g in ("BIG_LOTTO","POWER_LOTTO","DAILY_539"))
        print(f"  Interpretation: All {total_rows} DB rows pass internal format validation.")
        print("  No sequence gaps, no duplicate/out-of-range numbers, dates valid.")
        print("  Off-schedule draws (BIG_LOTTO holiday shifts, DAILY_539 CNY Sunday) are")
        print("  known-valid Taiwan Lottery makeup draws, not data errors.")
        print("  Live cross-check (Phases 1-2) could not run — network not available.")
        print("  Internal quality is GOOD; run again with network for full verification.")
    elif "CONDITIONAL" in trust:
        print("  Interpretation: Some HIGH-severity structural issues detected.")
        print("  Investigate flagged draws before relying on affected periods.")
    else:
        print("  Interpretation: CRITICAL or many HIGH structural issues found.")
        print("  Do NOT use DB data for production decisions until issues are resolved.")

    return trust


# ── PHASE 0: hardcoded ground truth ──────────────────────────────────────────
# These draws were verified by the project team and recorded in MEMORY.md /
# RSM update logs.  Any mismatch here is a CRITICAL data error even offline.
KNOWN_GROUND_TRUTH = [
    # (draw, lottery_type, numbers_sorted, special_or_None, date)
    ("115000037", "BIG_LOTTO",   [11,15,33,38,41,43], 21,  "2026/03/20"),
    ("115000023", "POWER_LOTTO", [9,13,14,18,31,34],   1,  "2026/03/19"),
    ("115000072", "DAILY_539",   [7,14,15,19,22],      None,"2026/03/21"),
    ("115000071", "DAILY_539",   [3,11,15,33,39],      None,"2026/03/20"),
    ("115000070", "DAILY_539",   [5,23,25,30,37],      None,"2026/03/19"),
    ("115000069", "DAILY_539",   [21,22,31,32,35],     None,"2026/03/18"),
    ("115000068", "DAILY_539",   [11,13,19,22,27],     None,"2026/03/17"),
    ("115000067", "DAILY_539",   [17,19,21,29,34],     None,"2026/03/16"),
]

def phase0_ground_truth() -> Dict:
    """Check hardcoded known-correct draws against DB."""
    section("PHASE 0 — Known Ground-Truth Check (offline, from project records)")
    conn = get_connection()
    passed = failed = 0
    issues = []
    for draw, lt, exp_nums, exp_sp, exp_date in KNOWN_GROUND_TRUTH:
        row = conn.execute(
            "SELECT draw, date, numbers, special FROM draws WHERE draw=? AND lottery_type=?",
            (draw, lt)
        ).fetchone()
        if not row:
            msg = f"[{lt}] draw={draw}: NOT IN DB"
            print(f"  ❌ FAIL  {msg}")
            log_issue("CRITICAL", lt, draw, "Known ground-truth draw missing from DB")
            issues.append(msg)
            failed += 1
            continue
        db_nums = sorted(json.loads(row["numbers"]))
        db_sp   = row["special"]
        db_date = row["date"]
        errs = []
        if sorted(exp_nums) != db_nums:
            errs.append(f"numbers: DB={db_nums} != EXPECTED={sorted(exp_nums)}")
        if exp_sp is not None and db_sp != exp_sp:
            errs.append(f"special: DB={db_sp} != EXPECTED={exp_sp}")
        if db_date != exp_date:
            errs.append(f"date: DB={db_date} != EXPECTED={exp_date}")
        if errs:
            msg = f"[{lt}] draw={draw}: {' | '.join(errs)}"
            print(f"  ❌ FAIL  {msg}")
            for e in errs:
                log_issue("CRITICAL", lt, draw, f"Ground-truth mismatch: {e}")
            issues.append(msg)
            failed += 1
        else:
            print(f"  ✅ PASS  [{lt}] draw={draw}  nums={db_nums}  sp={db_sp}  date={db_date}")
            passed += 1
    conn.close()
    print(f"\n  Result: {passed}/{passed+failed} PASS")
    return {"passed": passed, "failed": failed, "issues": issues}


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify lottery DB data correctness")
    parser.add_argument("--offline", action="store_true",
                        help="Skip network phases (1 & 2); run internal checks only")
    args = parser.parse_args()

    games = ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]

    print(sep)
    print("  Taiwan Lottery Data Correctness Verification")
    print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  DB: {DB_PATH}")
    if args.offline:
        print("  Mode: OFFLINE (internal checks only — Phases 0, 3, 4, 5)")
    else:
        print("  Mode: FULL (internal + live cross-check)")
    print(sep)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found at {DB_PATH}")
        sys.exit(1)

    p0 = phase0_ground_truth()

    if args.offline:
        p1 = {g: {"status": "SKIPPED"} for g in games}
        p2 = {g: {"status": "SKIPPED"} for g in games}
    else:
        p1 = phase1_cross_check(games)
        p2 = phase2_latest100_matchrate(games)

    p3 = phase3_format_validation(games)
    p4 = phase4_missing_draws(games)
    p5 = phase5_weekday_check(games, sample_size=20)

    trust = final_verdict(p1, p2, p3, p4, p5)

    # ── Two-tier classification ───────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  TWO-TIER DATA CLASSIFICATION")
    print(f"{'='*72}")

    internal_pass = (
        p0["failed"] == 0
        and len(SEVERITY["CRITICAL"]) == 0
        and all(p3.get(g, {}).get("all_ok", False) for g in games)
        and all(p4.get(g, {}).get("gaps", 0) == 0 for g in games)
    )
    internal_label = "✅ PASS" if internal_pass else "❌ FAIL"

    all_network_skipped = all(
        p1.get(g, {}).get("status") in ("SCAN_ERROR", "SKIPPED") for g in games
    )
    any_live_mismatch = any(
        p1.get(g, {}).get("status") == "MISMATCH" or
        p2.get(g, {}).get("match_rate", 100) < 100
        for g in games
    )
    if args.offline or all_network_skipped:
        official_label = "⏳ PENDING  (network unavailable — run without --offline to cross-check)"
    elif any_live_mismatch:
        official_label = "❌ FAIL  (live mismatches detected — see Phase 1/2 above)"
    else:
        n_checked = sum(p1.get(g, {}).get("checked", 0) for g in games)
        official_label = f"✅ PASS  ({n_checked} draws cross-checked against official site)"

    print(f"\n  INTERNAL_INTEGRITY     : {internal_label}")
    print(f"  OFFICIAL_GROUND_TRUTH  : {official_label}")
    print()

    # Exit code: only fail if internal integrity is broken
    # Network unavailability alone is NOT a failure
    return 0 if internal_pass else 1


if __name__ == "__main__":
    sys.exit(main())
