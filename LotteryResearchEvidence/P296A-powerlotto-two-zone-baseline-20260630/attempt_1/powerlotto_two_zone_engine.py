#!/usr/bin/env python3
"""
P296A — PowerLotto (威力彩) two-zone frequency baseline engine.

LOCAL, READ-ONLY, DESCRIPTIVE-ONLY. Reads historical draws from the authorized canonical view via a
strictly read-only SQLite connection (URI mode=ro, PRAGMA query_only=1), forms three FIXED frequency
baselines per eligible target from PRIOR-ONLY windows, scores main_hits (0..6) and special_hit (0/1)
against each target, and reports descriptive summaries.

Forbidden and absent here: any write SQL / DB write / schema change / DB copy; immutable mode; network;
random / simulation / Monte Carlo; p-values / inference / candidate selection / retention / ranking;
prize/payout/EV; future-ticket output; mixing the second-zone (special) value into the main zone.

Standard library only. Writes only under the --out directory (a run dir under the P296A root).
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from fractions import Fraction

# ---- frozen constants (must not change after FROZEN_SPEC_HASH_RECORD.md is hashed) ----
DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
SOURCE_VIEW = "draws_power_lotto_canonical_main"
SOURCE_FIELDS = ("id", "draw", "date", "numbers", "special")
MAIN_LO, MAIN_HI, MAIN_K = 1, 38, 6
SPECIAL_LO, SPECIAL_HI = 1, 8
WINDOWS = (50, 300, 750)
HISTORY_REQUIRED = 750
SEGMENTS = ("ALL", "LATEST_750", "LATEST_300", "LATEST_50")
SEGMENT_MIN = {"ALL": 0, "LATEST_750": 750, "LATEST_300": 300, "LATEST_50": 50}
EXPECTED_MAIN = Fraction(36, 38)      # 6 * 6/38
EXPECTED_SPECIAL = Fraction(1, 8)
DECIMAL_PREC = 50
DECIMAL_PLACES = 12
getcontext().prec = DECIMAL_PREC


def dec(fr):
    q = Decimal(1).scaleb(-DECIMAL_PLACES)
    return str((Decimal(fr.numerator) / Decimal(fr.denominator)).quantize(q, rounding=ROUND_HALF_EVEN))


def frac_obj(fr):
    return {"num": fr.numerator, "den": fr.denominator, "decimal": dec(fr)}


def stop(code, msg):
    sys.stderr.write(f"{code}: {msg}\n")
    sys.exit(2)


def open_readonly():
    if not os.path.isfile(DB_PATH):
        stop("P296A_STOPPED_DB_ASSET_MISSING_OR_UNSAFE", f"db not a regular file: {DB_PATH}")
    uri = "file:" + DB_PATH + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA query_only=1")
    val = con.execute("PRAGMA query_only").fetchone()[0]
    if int(val) != 1:
        stop("P296A_STOPPED_DB_ASSET_MISSING_OR_UNSAFE", "PRAGMA query_only not enforced")
    return con


def decode_ints(s):
    return [int(x) for x in re.findall(r"\d+", "" if s is None else str(s))]


def load_and_validate(con):
    # confirm the source view exists
    has_view = con.execute(
        "SELECT count(*) FROM sqlite_master WHERE name=? AND type IN ('view','table')",
        (SOURCE_VIEW,),
    ).fetchone()[0]
    if not has_view:
        stop("P296A_STOPPED_SOURCE_VIEW_OR_SCHEMA_MISMATCH", f"missing source view: {SOURCE_VIEW}")
    sql = ("SELECT id, draw, date, numbers, special FROM " + SOURCE_VIEW +
           " ORDER BY CAST(draw AS INTEGER) ASC, id ASC")
    rows = con.execute(sql).fetchall()

    draws = []
    seen_draws = set()
    for r in rows:
        rid, draw, date, numbers, special = r[0], r[1], r[2], r[3], r[4]
        mains = decode_ints(numbers)
        sp = decode_ints(special)
        if len(mains) != MAIN_K or len(set(mains)) != MAIN_K or any(not (MAIN_LO <= x <= MAIN_HI) for x in mains):
            stop("P296A_STOPPED_SOURCE_VIEW_OR_SCHEMA_MISMATCH",
                 f"main contract violation id={rid} draw={draw} numbers={numbers!r}")
        if len(sp) != 1 or not (SPECIAL_LO <= sp[0] <= SPECIAL_HI):
            stop("P296A_STOPPED_SOURCE_VIEW_OR_SCHEMA_MISMATCH",
                 f"special contract violation id={rid} draw={draw} special={special!r}")
        key = str(draw)
        if key in seen_draws:
            stop("P296A_STOPPED_SOURCE_VIEW_OR_SCHEMA_MISMATCH", f"duplicate draw identity: {draw}")
        seen_draws.add(key)
        draws.append({
            "id": rid, "draw": key, "date": str(date),
            "main": sorted(mains), "main_set": set(mains), "special": sp[0],
        })

    if len(draws) < HISTORY_REQUIRED + 1:
        stop("P296A_STOPPED_SOURCE_VIEW_OR_SCHEMA_MISMATCH",
             f"insufficient valid draws: {len(draws)} < {HISTORY_REQUIRED + 1}")
    return draws


def select_main(window):
    cnt = Counter()
    for d in window:
        cnt.update(d["main"])
    order = sorted(range(MAIN_LO, MAIN_HI + 1), key=lambda n: (-cnt.get(n, 0), n))
    return order[:MAIN_K]


def select_special(window):
    cnt = Counter()
    for d in window:
        cnt[d["special"]] += 1
    order = sorted(range(SPECIAL_LO, SPECIAL_HI + 1), key=lambda n: (-cnt.get(n, 0), n))
    return order[0]


def analyze(draws):
    n = len(draws)
    eligible_positions = list(range(HISTORY_REQUIRED, n))  # i with >=750 strictly-preceding draws
    per_target = []   # rows: (target_pos, target_draw, target_date, N, baseline, selected_main, sel_special, main_hits, special_hit)
    results = {N: [] for N in WINDOWS}  # N -> list of (pos, main_hits, special_hit) in eligible order

    for i in eligible_positions:
        target = draws[i]
        for N in WINDOWS:
            window = draws[i - N:i]
            sel_main = select_main(window)
            sel_sp = select_special(window)
            main_hits = len(set(sel_main) & target["main_set"])
            special_hit = 1 if sel_sp == target["special"] else 0
            per_target.append((i, target["draw"], target["date"], N,
                               "freq_%d_two_zone" % N, sel_main, sel_sp, main_hits, special_hit))
            results[N].append((i, main_hits, special_hit))

    # audit samples (prior-only proof): first / middle / last eligible target per N
    audit = {}
    if eligible_positions:
        idxs = [0, len(eligible_positions) // 2, len(eligible_positions) - 1]
        labels = ["first", "middle", "last"]
        for N in WINDOWS:
            samples = []
            for lab, k in zip(labels, idxs):
                i = eligible_positions[k]
                w_start, w_end = i - N, i - 1
                samples.append({
                    "which": lab, "target_pos": i, "target_draw": draws[i]["draw"],
                    "window_size_N": N,
                    "window_start_pos": w_start, "window_end_pos": w_end,
                    "window_first_draw": draws[w_start]["draw"], "window_last_draw": draws[w_end]["draw"],
                    "target_strictly_after_window": (w_end == i - 1) and (w_end < i),
                })
            audit[str(N)] = samples
    return eligible_positions, per_target, results, audit


def summarize_segment(rows):
    # rows: list of (pos, main_hits, special_hit)
    c = len(rows)
    main_dist = [0] * (MAIN_K + 1)
    main_sum = 0
    sp_count = 0
    ge3 = 0
    for _, mh, sh in rows:
        main_dist[mh] += 1
        main_sum += mh
        sp_count += sh
        if mh >= 3:
            ge3 += 1
    mean_main = Fraction(main_sum, c)
    mean_sp = Fraction(sp_count, c)
    return {
        "target_count": c,
        "mean_main_hits": frac_obj(mean_main),
        "main_hit_distribution": main_dist,
        "mean_special_hit": frac_obj(mean_sp),
        "special_hit_count": sp_count,
        "special_hit_rate": frac_obj(Fraction(sp_count, c)),
        "main_excess_vs_36_38": frac_obj(mean_main - EXPECTED_MAIN),
        "special_excess_vs_1_8": frac_obj(mean_sp - EXPECTED_SPECIAL),
        "main_hits_ge3_count": ge3,
    }


def build_summaries(results):
    out = {}
    for N in WINDOWS:
        rows = results[N]
        seg_out = {}
        for seg in SEGMENTS:
            need = SEGMENT_MIN[seg]
            if seg == "ALL":
                subset = rows
            elif len(rows) >= need:
                subset = rows[-need:]
            else:
                seg_out[seg] = "NOT_APPLICABLE"
                continue
            if not subset:
                seg_out[seg] = "NOT_APPLICABLE"
                continue
            seg_out[seg] = summarize_segment(subset)
        out["freq_%d_two_zone" % N] = seg_out
    return out


def write_result_table(path, per_target):
    cols = ["target_pos", "target_draw", "target_date", "N", "baseline",
            "selected_main", "selected_special", "main_hits", "special_hit"]
    lines = [",".join(cols)]
    for (pos, draw, date, N, baseline, sel_main, sel_sp, mh, sh) in per_target:
        lines.append(",".join([
            str(pos), str(draw), str(date), str(N), baseline,
            "|".join(str(x) for x in sel_main), str(sel_sp), str(mh), str(sh),
        ]))
    data = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def write_summary_csv(path, summaries):
    cols = ["baseline", "segment", "target_count", "mean_main_hits", "main_excess_vs_36_38",
            "mean_special_hit", "special_hit_count", "special_hit_rate", "special_excess_vs_1_8",
            "main_dist_0", "main_dist_1", "main_dist_2", "main_dist_3", "main_dist_4", "main_dist_5",
            "main_dist_6", "main_hits_ge3_count"]
    lines = [",".join(cols)]
    for N in WINDOWS:
        baseline = "freq_%d_two_zone" % N
        for seg in SEGMENTS:
            s = summaries[baseline][seg]
            if s == "NOT_APPLICABLE":
                row = [baseline, seg, "NOT_APPLICABLE"] + [""] * (len(cols) - 3)
            else:
                d = s["main_hit_distribution"]
                row = [baseline, seg, str(s["target_count"]),
                       s["mean_main_hits"]["decimal"], s["main_excess_vs_36_38"]["decimal"],
                       s["mean_special_hit"]["decimal"], str(s["special_hit_count"]),
                       s["special_hit_rate"]["decimal"], s["special_excess_vs_1_8"]["decimal"],
                       str(d[0]), str(d[1]), str(d[2]), str(d[3]), str(d[4]), str(d[5]), str(d[6]),
                       str(s["main_hits_ge3_count"])]
            lines.append(",".join(row))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_source_validation(path, draws, eligible_positions):
    n = len(draws)
    all_main = [m for d in draws for m in d["main"]]
    all_sp = [d["special"] for d in draws]
    lines = [
        "P296A SOURCE VALIDATION (deterministic)",
        "source_view=%s" % SOURCE_VIEW,
        "ordering=CAST(draw AS INTEGER) ASC, id ASC",
        "row_count=%d" % n,
        "unique_draws=%d" % len({d["draw"] for d in draws}),
        "all_rows_valid=True",
        "first_draw=%s" % draws[0]["draw"],
        "last_draw=%s" % draws[-1]["draw"],
        "first_date=%s" % draws[0]["date"],
        "last_date=%s" % draws[-1]["date"],
        "main_min=%d main_max=%d" % (min(all_main), max(all_main)),
        "special_min=%d special_max=%d" % (min(all_sp), max(all_sp)),
        "history_required=%d" % HISTORY_REQUIRED,
        "eligible_count=%d" % len(eligible_positions),
        "first_eligible_pos=%s" % (eligible_positions[0] if eligible_positions else "NONE"),
        "last_eligible_pos=%s" % (eligible_positions[-1] if eligible_positions else "NONE"),
        "first_eligible_draw=%s" % (draws[eligible_positions[0]]["draw"] if eligible_positions else "NONE"),
        "last_eligible_draw=%s" % (draws[eligible_positions[-1]]["draw"] if eligible_positions else "NONE"),
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_audit_samples(path, audit):
    lines = ["P296A PRIOR-ONLY AUDIT SAMPLES (deterministic)"]
    for N in WINDOWS:
        lines.append("N=%d" % N)
        for s in audit.get(str(N), []):
            lines.append(
                "  %-6s target_pos=%d target_draw=%s window=[pos %d..%d] [draw %s..%s] prior_only=%s"
                % (s["which"], s["target_pos"], s["target_draw"], s["window_start_pos"],
                   s["window_end_pos"], s["window_first_draw"], s["window_last_draw"],
                   s["target_strictly_after_window"]))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="P296A PowerLotto two-zone frequency baseline engine")
    ap.add_argument("--out", required=True, help="output dir (a run dir under the P296A evidence root)")
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    con = open_readonly()
    try:
        draws = load_and_validate(con)
    finally:
        con.close()

    eligible_positions, per_target, results, audit = analyze(draws)
    if not eligible_positions:
        stop("P296A_STOPPED_SOURCE_VIEW_OR_SCHEMA_MISMATCH", "no eligible targets")
    summaries = build_summaries(results)

    rt_path = os.path.join(out_dir, "POWERLOTTO_BASELINE_RESULT_TABLE.csv")
    rt_sha = write_result_table(rt_path, per_target)
    write_summary_csv(os.path.join(out_dir, "POWERLOTTO_DESCRIPTIVE_SUMMARY.csv"), summaries)
    write_source_validation(os.path.join(out_dir, "SOURCE_VALIDATION.txt"), draws, eligible_positions)
    write_audit_samples(os.path.join(out_dir, "AUDIT_SAMPLES.txt"), audit)

    canonical = {
        "schema": "P296A-powerlotto-two-zone-baseline/v1",
        "task_id": "P296A-POWERLOTTO-TWO-ZONE-FREQUENCY-BASELINE",
        "method": "read_only_db_descriptive_frequency_baselines_no_inference_no_selection",
        "source": {
            "view": SOURCE_VIEW, "fields": list(SOURCE_FIELDS),
            "ordering": "CAST(draw AS INTEGER) ASC, id ASC",
            "db_sha256_expected": "41e9c37948650c1d881502f7d204a2656c16e61e8e7b96058d23da76dd666cab",
            "main_zone": "6 of 1..38", "second_zone": "1 of 1..8",
        },
        "source_validation": {
            "row_count": len(draws),
            "unique_draws": len({d["draw"] for d in draws}),
            "all_rows_valid": True,
            "first_draw": draws[0]["draw"], "last_draw": draws[-1]["draw"],
            "first_date": draws[0]["date"], "last_date": draws[-1]["date"],
            "main_min": min(m for d in draws for m in d["main"]),
            "main_max": max(m for d in draws for m in d["main"]),
            "special_min": min(d["special"] for d in draws),
            "special_max": max(d["special"] for d in draws),
            "history_required": HISTORY_REQUIRED,
            "eligible_count": len(eligible_positions),
            "first_eligible_pos": eligible_positions[0],
            "last_eligible_pos": eligible_positions[-1],
            "first_eligible_draw": draws[eligible_positions[0]]["draw"],
            "last_eligible_draw": draws[eligible_positions[-1]]["draw"],
        },
        "baselines": ["freq_%d_two_zone" % N for N in WINDOWS],
        "windows": list(WINDOWS),
        "expected_reference": {"main_hits": "36/38", "special_hit": "1/8"},
        "summaries": summaries,
        "audit_samples": audit,
        "result_table_sha256": rt_sha,
        "decimal_places": DECIMAL_PLACES,
        "nonpredictive_boundary": (
            "Descriptive frequency baselines over past PowerLotto draws only. Prior-only windows. "
            "No inference, p-values, candidate selection/retention, ranking, prediction, prize/payout, "
            "or future ticket. Second zone scored separately from main zone."
        ),
    }
    canonical_json = json.dumps(canonical, sort_keys=True, indent=2, ensure_ascii=True)
    canonical_bytes = (canonical_json + "\n").encode("utf-8")
    with open(os.path.join(out_dir, "CANONICAL_RESULT.json"), "wb") as fh:
        fh.write(canonical_bytes)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    with open(os.path.join(out_dir, "CANONICAL_RESULT.sha256"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(digest + "  CANONICAL_RESULT.json\n")

    sys.stdout.write("P296A engine OK: rows=%d eligible=%d targets; CANONICAL_RESULT.sha256=%s\n"
                     % (len(draws), len(eligible_positions), digest))


if __name__ == "__main__":
    main()
