#!/usr/bin/env python3
"""P293E independent engine — BIG649 fixed-budget diversity-portfolio reproduction audit.

Self-contained and stdlib-only. Implemented independently from FROZEN_REPRODUCTION_SPEC.md, which
restates the verified P293D FROZEN_PORTFOLIO_SPEC.md (SHA-256 6f650aa5...). This engine does NOT import,
execute, copy, or patch the P293D engine, and imports nothing from the repository.

Safety invariants (statically reviewed before DB open — see ENGINE_STATIC_REVIEW.md):
  * stdlib-only imports.
  * Opens only the authorized DB via SQLite URI mode=ro, uri=True; sets+verifies PRAGMA query_only=1;
    no `immutable` (WAL/SHM exist). No write SQL of any kind.
  * Writes only inside the directory passed as --outdir.
  * No network, no subprocess, no os.environ mutation, no alternative DB path.
  * Deterministic: no RNG, no wall-clock inside any hashed payload; fixed-precision float formatting.

Descriptive observational research only. No p-values, significance, promotion, prediction-success claim,
betting recommendation, or portfolio activation.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sys

# ---- frozen constants (from FROZEN_REPRODUCTION_SPEC.md) ----------------------------------------
AUTHORIZED_DB = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
SOURCE_VIEW = "draws_big_lotto_canonical_main"
POOL = 49
MAIN_K = 6
EXPECTED_ROWS = 2120
EXPECTED_FIRST_ID = 96000001
EXPECTED_LAST_ID = 115000065
TARGET_START = 750          # eligible target positions are [750, 2119]
BUDGETS = (2, 3, 4)
C49_6 = math.comb(49, 6)    # 13983816

STRAT_NAMES = [
    "freq_50", "freq_300", "freq_750", "prior_draw",
    "exp_recency_50", "exp_recency_300", "exp_recency_750",
]
FREQ_WINDOWS = {0: 50, 1: 300, 2: 750}             # strategy idx -> window K
EXP_PARAMS = {4: (50, 10), 5: (300, 60), 6: (750, 150)}   # strategy idx -> (N, H)
STRAT_K = {0: 50, 1: 300, 2: 750, 3: 1, 4: 50, 5: 300, 6: 750}  # source-window length

SEGMENTS = [
    ("ALL", 750, 2119),
    ("LATEST_750", 1370, 2119),
    ("LATEST_300", 1820, 2119),
    ("LATEST_50", 2070, 2119),
    ("BLOCK_1", 750, 1091),
    ("BLOCK_2", 1092, 1433),
    ("BLOCK_3", 1434, 1776),
    ("BLOCK_4", 1777, 2119),
]
AUDIT_TARGETS = [750, 1435, 2119]   # first, middle (eligible[685]), last


def stop(msg: str) -> "None":
    sys.stderr.write("P293E_STOP: " + msg + "\n")
    raise SystemExit(3)


def fmt(x: float) -> str:
    """Fixed-precision deterministic float formatting for CSVs and the canonical digest."""
    return f"{x:.10f}"


# ---- DB load + validation ----------------------------------------------------------------------
def load_and_validate(db_path: str):
    if db_path != AUTHORIZED_DB:
        stop("alternative DB path is forbidden: " + db_path)
    uri = "file:" + db_path + "?mode=ro"
    conn = sqlite3_connect_ro(uri)
    try:
        conn.execute("PRAGMA query_only=1")
        qo = conn.execute("PRAGMA query_only").fetchone()[0]
        if int(qo) != 1:
            stop("PRAGMA query_only != 1 (got %r)" % (qo,))
        view = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name=?", (SOURCE_VIEW,)
        ).fetchone()
        if not view:
            stop("source view %s missing" % SOURCE_VIEW)
        cur = conn.execute(
            "SELECT id, draw, date, numbers, special FROM " + SOURCE_VIEW
            + " ORDER BY CAST(draw AS INTEGER) ASC, id ASC"
        )
        columns = [d[0] for d in cur.description]
        raw = cur.fetchall()
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()

    if columns != ["id", "draw", "date", "numbers", "special"]:
        stop("unexpected columns: " + repr(columns))
    if len(raw) != EXPECTED_ROWS:
        stop("row count %d != %d" % (len(raw), EXPECTED_ROWS))

    parsed = []          # (draw_id:int=int(draw), draw_str:str, mains:tuple(sorted 6 ints), special:int|None)
    seen_draw = set()
    prev_cast = None
    special_in_range = True
    for (rid, draw, _date, numbers, special) in raw:
        nums = json.loads(numbers)
        if not isinstance(nums, list) or len(nums) != 6:
            stop("numbers not a list of 6 at id=%r" % (rid,))
        if any(not isinstance(n, int) for n in nums):
            stop("non-int main number at id=%r" % (rid,))
        if len(set(nums)) != 6:
            stop("duplicate main number at id=%r" % (rid,))
        if any(n < 1 or n > 49 for n in nums):
            stop("main number out of [1,49] at id=%r" % (rid,))
        c = int(draw)
        if prev_cast is not None and c < prev_cast:
            stop("ordering not non-decreasing in CAST(draw) at id=%r" % (rid,))
        prev_cast = c
        if draw in seen_draw:
            stop("duplicate draw identity %r" % (draw,))
        seen_draw.add(draw)
        sp = None
        if special is not None:
            sp = int(special)
            if sp < 1 or sp > 49:
                special_in_range = False
        # The frozen spec's "draw id" is the `draw` column value (the ordering key + identity),
        # NOT the autoincrement PK `id`. Use int(draw) as the draw identifier everywhere.
        parsed.append((int(draw), str(draw), tuple(sorted(nums)), sp))

    if parsed[0][0] != EXPECTED_FIRST_ID:
        stop("first draw %r != %d" % (parsed[0][0], EXPECTED_FIRST_ID))
    if parsed[-1][0] != EXPECTED_LAST_ID:
        stop("last draw %r != %d" % (parsed[-1][0], EXPECTED_LAST_ID))
    if not special_in_range:
        stop("a present special is outside [1,49]")

    n = len(parsed)
    n_eligible = n - TARGET_START
    data_identity = {
        "source_view": SOURCE_VIEW,
        "columns": columns,
        "query_only": 1,
        "journal_mode": journal_mode,
        "page_count": int(page_count),
        "page_size": int(page_size),
        "db_logical_size_bytes": int(page_count) * int(page_size),
        "total_rows": n,
        "first_draw_id": parsed[0][0],
        "last_draw_id": parsed[-1][0],
        "n_eligible_targets": n_eligible,
        "target_index_range": [TARGET_START, n - 1],
        "all_special_present": all(p[3] is not None for p in parsed),
        "validations_passed": True,
    }
    return parsed, data_identity


def sqlite3_connect_ro(uri: str):
    import sqlite3  # stdlib; local import keeps the module list explicit
    return sqlite3.connect(uri, uri=True)


# ---- strategy tickets --------------------------------------------------------------------------
def precompute_exp_weights():
    weights = {}
    for (N, H) in EXP_PARAMS.values():
        weights[(N, H)] = [math.exp2(-(lag - 1) / H) for lag in range(1, N + 1)]
    return weights


def freq_ticket(t, K, mains):
    counts = [0] * (POOL + 1)
    for pos in range(t - K, t):
        for x in mains[pos]:
            counts[x] += 1
    order = sorted(range(1, POOL + 1), key=lambda x: (-counts[x], x))
    return tuple(sorted(order[:MAIN_K]))


def exp_ticket(t, N, H, mains, weights):
    w = weights[(N, H)]
    scores = [0.0] * (POOL + 1)
    for lag in range(1, N + 1):
        wl = w[lag - 1]
        for x in mains[t - lag]:
            scores[x] += wl
    order = sorted(range(1, POOL + 1), key=lambda x: (-scores[x], x))
    return tuple(sorted(order[:MAIN_K]))


def build_tickets(t, mains, weights):
    return [
        freq_ticket(t, 50, mains),
        freq_ticket(t, 300, mains),
        freq_ticket(t, 750, mains),
        mains[t - 1],                                   # prior_draw, already sorted
        exp_ticket(t, 50, 10, mains, weights),
        exp_ticket(t, 300, 60, mains, weights),
        exp_ticket(t, 750, 150, mains, weights),
    ]


def mask_of(ticket):
    m = 0
    for x in ticket:
        m |= (1 << x)
    return m


def select_subset(B, tmasks, pair_ov):
    """Return (subset_tuple, M, overlap, union_mask). Outcome-blind. Minimize (-M, overlap);
    earliest enumeration position wins via strictly-better replacement."""
    best_key = None
    best = None
    for subset in itertools.combinations(range(7), B):
        union = 0
        for i in subset:
            union |= tmasks[i]
        M = union.bit_count()
        ov = 0
        for a in range(len(subset)):
            for b in range(a + 1, len(subset)):
                ov += pair_ov[subset[a]][subset[b]]
        key = (-M, ov)
        if best_key is None or key < best_key:    # strictly-better -> earliest wins on ties
            best_key = key
            best = (subset, M, ov, union)
    return best


# ---- hypergeometric reference -------------------------------------------------------------------
def hyperg_pmf(K, n=MAIN_K, N=POOL):
    pmf = [0.0] * 7
    for k in range(0, 7):
        if k > K or (n - k) > (N - K):
            pmf[k] = 0.0
        else:
            pmf[k] = math.comb(K, k) * math.comb(N - K, n - k) / C49_6
    return pmf


# ---- main analysis ------------------------------------------------------------------------------
def run_analysis(parsed):
    n = len(parsed)
    ids = [p[0] for p in parsed]
    mains = [p[2] for p in parsed]
    specials = [p[3] for p in parsed]
    target_masks = [mask_of(m) for m in mains]
    weights = precompute_exp_weights()

    eligible = list(range(TARGET_START, n))

    # per (t, B) rows
    rows = []   # dict per row
    # distinctness accumulators over ALL eligible targets
    pair_overlap_sum = [[0 for _ in range(7)] for _ in range(7)]
    pair_jaccard_sum = [[0.0 for _ in range(7)] for _ in range(7)]
    unique7_sum = 0
    audit = {}

    for t in eligible:
        tickets = build_tickets(t, mains, weights)
        tmasks = [mask_of(tk) for tk in tickets]
        # pairwise overlaps among the seven
        pair_ov = [[0] * 7 for _ in range(7)]
        for i in range(7):
            for j in range(i + 1, 7):
                inter = (tmasks[i] & tmasks[j]).bit_count()
                pair_ov[i][j] = inter
                pair_ov[j][i] = inter
                uni = (tmasks[i] | tmasks[j]).bit_count()
                pair_overlap_sum[i][j] += inter
                pair_jaccard_sum[i][j] += inter / uni
        union7 = 0
        for m in tmasks:
            union7 |= m
        unique7_sum += union7.bit_count()

        tmask_t = target_masks[t]
        selections = {}
        for B in BUDGETS:
            subset, M, ov, union = select_subset(B, tmasks, pair_ov)
            hits = (union & tmask_t).bit_count()
            redundancy = MAIN_K * B - M
            ref_a = MAIN_K * M / POOL
            ref_b = (MAIN_K * MAIN_K) * B / POOL  # 36*B/49
            rows.append({
                "t": t, "draw_id": ids[t], "B": B,
                "subset": subset, "M": M, "redundancy": redundancy,
                "overlap": ov, "hits": hits, "ref_a": ref_a, "ref_b": ref_b,
            })
            selections[B] = {"subset": subset, "M": M, "overlap": ov, "hits": hits}

        if t in AUDIT_TARGETS:
            strat_rec = []
            for idx in range(7):
                K = STRAT_K[idx]
                wstart = t - K
                strat_rec.append({
                    "idx": idx, "name": STRAT_NAMES[idx],
                    "window_start_pos": wstart, "window_end_pos": t - 1,
                    "window_start_id": ids[wstart], "window_end_id": ids[t - 1],
                    "ticket": list(tickets[idx]),
                })
            audit[t] = {
                "t": t,
                "strategies": strat_rec,
                "selections_outcome_blind": {
                    str(B): {
                        "subset_indices": list(selections[B]["subset"]),
                        "subset_names": [STRAT_NAMES[i] for i in selections[B]["subset"]],
                        "M": selections[B]["M"], "overlap": selections[B]["overlap"],
                    } for B in BUDGETS
                },
                "outcome_revealed_after_selection": {
                    "draw_id": ids[t], "main_numbers": list(mains[t]), "special": specials[t],
                },
                "union_hits": {str(B): selections[B]["hits"] for B in BUDGETS},
            }

    # ---- segment summaries ----
    n_elig = len(eligible)
    segment_summary = []
    for (seg, lo, hi) in SEGMENTS:
        for B in BUDGETS:
            srows = [r for r in rows if r["B"] == B and lo <= r["t"] <= hi]
            ns = len(srows)
            hits_dist = [0] * 7
            sum_hits = 0
            sum_M = 0
            sum_red = 0
            sum_ov = 0
            sum_ref_a = 0.0
            ref_a_dist = [0.0] * 7
            sel_counter = {}
            for r in srows:
                hits_dist[r["hits"]] += 1
                sum_hits += r["hits"]
                sum_M += r["M"]
                sum_red += r["redundancy"]
                sum_ov += r["overlap"]
                sum_ref_a += r["ref_a"]
                pmf = hyperg_pmf(r["M"])
                for k in range(7):
                    ref_a_dist[k] += pmf[k]
                sel_counter[r["subset"]] = sel_counter.get(r["subset"], 0) + 1
            mean_hits = sum_hits / ns
            mean_M = sum_M / ns
            mean_red = sum_red / ns
            mean_ov = sum_ov / ns
            ref_a_mean = sum_ref_a / ns
            ref_b_mean = (MAIN_K * MAIN_K) * B / POOL
            ref_a_dist = [v / ns for v in ref_a_dist]
            ref_b_dist = hyperg_pmf(MAIN_K * B)
            sel_freq = []
            for subset in sorted(sel_counter.keys()):
                c = sel_counter[subset]
                sel_freq.append({
                    "subset": list(subset),
                    "names": [STRAT_NAMES[i] for i in subset],
                    "count": c, "fraction": c / ns,
                })
            segment_summary.append({
                "segment": seg, "B": B, "n_targets": ns,
                "mean_union_hits": mean_hits, "mean_union_size": mean_M,
                "mean_redundancy": mean_red, "mean_pairwise_overlap": mean_ov,
                "hits_dist": hits_dist, "hits_frac": [c / ns for c in hits_dist],
                "ref_a_cond_mean": ref_a_mean, "ref_b_div_mean": ref_b_mean,
                "delta_vs_ref_a": mean_hits - ref_a_mean, "delta_vs_ref_b": mean_hits - ref_b_mean,
                "ref_a_dist": ref_a_dist, "ref_b_dist": ref_b_dist,
                "selection_freq": sel_freq,
            })

    # ---- strategy pair distinctness (over ALL eligible) ----
    strategy_pairs = []
    for i in range(7):
        for j in range(i + 1, 7):
            strategy_pairs.append({
                "i": i, "j": j, "name_i": STRAT_NAMES[i], "name_j": STRAT_NAMES[j],
                "mean_overlap": pair_overlap_sum[i][j] / n_elig,
                "mean_jaccard": pair_jaccard_sum[i][j] / n_elig,
            })
    mean_unique_seven = unique7_sum / n_elig

    per_budget = []
    for B in BUDGETS:
        brows = [r for r in rows if r["B"] == B and TARGET_START <= r["t"] <= (n - 1)]
        nb = len(brows)
        mM = sum(r["M"] for r in brows) / nb
        mR = sum(r["redundancy"] for r in brows) / nb
        per_budget.append({
            "B": B, "mean_M": mM, "mean_redundancy": mR,
            "unique_slot_fraction": mM / (MAIN_K * B),
        })

    return rows, segment_summary, strategy_pairs, mean_unique_seven, per_budget, audit


# ---- writers ------------------------------------------------------------------------------------
def write_result_table(path, rows):
    lines = ["target_index,draw_id,budget,subset_indices,subset_names,union_size,redundancy,"
             "pairwise_overlap,union_hits,ref_a_cond_expected_hits,ref_b_diversified_expected_hits"]
    for r in rows:
        si = "|".join(str(i) for i in r["subset"])
        sn = "|".join(STRAT_NAMES[i] for i in r["subset"])
        lines.append(",".join([
            str(r["t"]), str(r["draw_id"]), str(r["B"]), si, sn,
            str(r["M"]), str(r["redundancy"]), str(r["overlap"]), str(r["hits"]),
            fmt(r["ref_a"]), fmt(r["ref_b"]),
        ]))
    write_text(path, "\n".join(lines) + "\n")


def write_selection_freq(path, segment_summary):
    lines = ["budget,segment,subset_indices,subset_names,count,fraction"]
    for s in segment_summary:
        for sf in s["selection_freq"]:
            si = "|".join(str(i) for i in sf["subset"])
            sn = "|".join(sf["names"])
            lines.append(",".join([
                str(s["B"]), s["segment"], si, sn, str(sf["count"]), fmt(sf["fraction"]),
            ]))
    write_text(path, "\n".join(lines) + "\n")


def write_overlap_matrix(path, strategy_pairs):
    ov = [[0.0] * 7 for _ in range(7)]
    for p in strategy_pairs:
        ov[p["i"]][p["j"]] = p["mean_overlap"]
        ov[p["j"]][p["i"]] = p["mean_overlap"]
    for i in range(7):
        ov[i][i] = float(MAIN_K)   # a ticket overlaps itself in all 6 numbers
    lines = ["strategy," + ",".join(STRAT_NAMES)]
    for i in range(7):
        lines.append(STRAT_NAMES[i] + "," + ",".join(fmt(ov[i][j]) for j in range(7)))
    write_text(path, "\n".join(lines) + "\n")


def write_segment_summary_csv(path, segment_summary):
    lines = ["budget,segment,n_targets,mean_union_hits,mean_union_size,mean_redundancy,"
             "mean_pairwise_overlap,hits0,hits1,hits2,hits3,hits4,hits5,hits6,"
             "ref_a_cond_mean,ref_b_div_mean,delta_vs_ref_a,delta_vs_ref_b"]
    for s in segment_summary:
        lines.append(",".join([
            str(s["B"]), s["segment"], str(s["n_targets"]),
            fmt(s["mean_union_hits"]), fmt(s["mean_union_size"]), fmt(s["mean_redundancy"]),
            fmt(s["mean_pairwise_overlap"]),
            *[str(c) for c in s["hits_dist"]],
            fmt(s["ref_a_cond_mean"]), fmt(s["ref_b_div_mean"]),
            fmt(s["delta_vs_ref_a"]), fmt(s["delta_vs_ref_b"]),
        ]))
    write_text(path, "\n".join(lines) + "\n")


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_digest(data_identity, rows, segment_summary, strategy_pairs, mean_unique_seven, per_budget):
    payload = {
        "data_identity": {
            "source_view": data_identity["source_view"],
            "total_rows": data_identity["total_rows"],
            "first_draw_id": data_identity["first_draw_id"],
            "last_draw_id": data_identity["last_draw_id"],
            "n_eligible_targets": data_identity["n_eligible_targets"],
        },
        "rows": [[r["t"], r["draw_id"], r["B"], list(r["subset"]), r["M"], r["redundancy"],
                  r["overlap"], r["hits"], fmt(r["ref_a"]), fmt(r["ref_b"])] for r in rows],
        "segments": [[s["B"], s["segment"], s["n_targets"], fmt(s["mean_union_hits"]),
                      fmt(s["mean_union_size"]), fmt(s["mean_redundancy"]), fmt(s["mean_pairwise_overlap"]),
                      s["hits_dist"], fmt(s["ref_a_cond_mean"]), fmt(s["ref_b_div_mean"]),
                      fmt(s["delta_vs_ref_a"]), fmt(s["delta_vs_ref_b"]),
                      [fmt(v) for v in s["ref_a_dist"]], [fmt(v) for v in s["ref_b_dist"]],
                      [[sf["subset"], sf["count"]] for sf in s["selection_freq"]]] for s in segment_summary],
        "pairs": [[p["i"], p["j"], fmt(p["mean_overlap"]), fmt(p["mean_jaccard"])] for p in strategy_pairs],
        "mean_unique_seven": fmt(mean_unique_seven),
        "per_budget": [[pb["B"], fmt(pb["mean_M"]), fmt(pb["mean_redundancy"]),
                        fmt(pb["unique_slot_fraction"])] for pb in per_budget],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--db", default=AUTHORIZED_DB)
    args = ap.parse_args()

    outdir = os.path.abspath(args.outdir)
    root_allow = "/Users/kelvin/LotteryResearchEvidence/P293E-big649-independent-portfolio-audit-20260629/"
    if not outdir.startswith(root_allow):
        stop("outdir outside P293E evidence root: " + outdir)
    os.makedirs(outdir, exist_ok=True)

    parsed, data_identity = load_and_validate(args.db)
    rows, segment_summary, strategy_pairs, mean_unique_seven, per_budget, audit = run_analysis(parsed)

    if len(rows) != data_identity["n_eligible_targets"] * len(BUDGETS):
        stop("row count %d != eligible*budgets" % len(rows))

    p_table = os.path.join(outdir, "PORTFOLIO_RESULT_TABLE.csv")
    p_freq = os.path.join(outdir, "PORTFOLIO_SELECTION_FREQUENCY.csv")
    p_mat = os.path.join(outdir, "SEVEN_TICKET_OVERLAP_MATRIX.csv")
    p_seg = os.path.join(outdir, "SEGMENT_SUMMARY.csv")
    p_res = os.path.join(outdir, "RESULTS.json")
    p_hash = os.path.join(outdir, "RUN_HASHES.json")

    write_result_table(p_table, rows)
    write_selection_freq(p_freq, segment_summary)
    write_overlap_matrix(p_mat, strategy_pairs)
    write_segment_summary_csv(p_seg, segment_summary)

    results = {
        "task": "P293E",
        "data_identity": data_identity,
        "budgets": list(BUDGETS),
        "segments": [{"name": s, "lo": lo, "hi": hi, "n": hi - lo + 1} for (s, lo, hi) in SEGMENTS],
        "n_result_rows": len(rows),
        "segment_summary": segment_summary,
        "strategy_pairs": strategy_pairs,
        "mean_unique_seven": mean_unique_seven,
        "per_budget": per_budget,
        "audit_samples": [audit[t] for t in AUDIT_TARGETS],
    }
    write_text(p_res, json.dumps(results, sort_keys=True, indent=2) + "\n")

    digest = canonical_digest(data_identity, rows, segment_summary, strategy_pairs,
                              mean_unique_seven, per_budget)
    run_hashes = {
        "canonical_result_digest": digest,
        "files": {
            "PORTFOLIO_RESULT_TABLE.csv": sha256_file(p_table),
            "PORTFOLIO_SELECTION_FREQUENCY.csv": sha256_file(p_freq),
            "SEVEN_TICKET_OVERLAP_MATRIX.csv": sha256_file(p_mat),
            "SEGMENT_SUMMARY.csv": sha256_file(p_seg),
            "RESULTS.json": sha256_file(p_res),
        },
    }
    write_text(p_hash, json.dumps(run_hashes, sort_keys=True, indent=2) + "\n")

    sys.stdout.write("P293E_OK rows=%d eligible=%d canonical_digest=%s\n"
                     % (len(rows), data_identity["n_eligible_targets"], digest))
    sys.stdout.write("data_identity rows=%d first=%d last=%d view=%s query_only=%d\n" % (
        data_identity["total_rows"], data_identity["first_draw_id"],
        data_identity["last_draw_id"], data_identity["source_view"], data_identity["query_only"]))


if __name__ == "__main__":
    main()
