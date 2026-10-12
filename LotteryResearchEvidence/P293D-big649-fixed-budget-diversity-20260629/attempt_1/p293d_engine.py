#!/usr/bin/env python3
"""P293D BIG649 fixed-budget diversity-portfolio observational audit engine.

Self-contained, stdlib-only, READ-ONLY. Implements FROZEN_PORTFOLIO_SPEC.md exactly.
Opens ONLY the authorized DB via SQLite URI mode=ro (uri=True) + PRAGMA query_only=1,
no immutable mode (WAL/SHM exist). No write SQL. Writes only inside --outdir, which must
be inside the durable attempt directory. Deterministic: no RNG, no wall-clock in outputs.

Descriptive observational research only. No p-values, promotion, or prediction claims.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sqlite3
import sys
from itertools import combinations

# ----------------------------------------------------------------------------- constants (frozen)
AUTHORIZED_DB = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
DURABLE_ROOT = "/Users/kelvin/LotteryResearchEvidence/P293D-big649-fixed-budget-diversity-20260629/attempt_1"
VIEW = "draws_big_lotto_canonical_main"
EXPECTED_COLS = ["id", "draw", "date", "numbers", "special"]
POOL_MIN, POOL_MAX, TICKET_SIZE = 1, 49, 6
POOL_N = POOL_MAX - POOL_MIN + 1          # 49
C_TOTAL = math.comb(POOL_N, TICKET_SIZE)  # C(49,6) = 13983816
EXPECTED_TOTAL = 2120
EXPECTED_FIRST = "96000001"
EXPECTED_LAST = "115000065"
ELIGIBLE_START = 750                       # first eligible target position (0-based)

STRATEGY_ORDER = ["freq_50", "freq_300", "freq_750", "prior_draw",
                  "exp_recency_50", "exp_recency_300", "exp_recency_750"]
FREQ_K = {"freq_50": 50, "freq_300": 300, "freq_750": 750}
EXP_NH = {"exp_recency_50": (50, 10), "exp_recency_300": (300, 60), "exp_recency_750": (750, 150)}
BUDGETS = [2, 3, 4]

SEGMENTS = {  # name -> (start_pos_inclusive, end_pos_inclusive)
    "ALL": (750, 2119),
    "LATEST_750": (1370, 2119),
    "LATEST_300": (1820, 2119),
    "LATEST_50": (2070, 2119),
    "BLOCK_1": (750, 1091),
    "BLOCK_2": (1092, 1433),
    "BLOCK_3": (1434, 1776),
    "BLOCK_4": (1777, 2119),
}
SEGMENT_ORDER = ["ALL", "LATEST_750", "LATEST_300", "LATEST_50",
                 "BLOCK_1", "BLOCK_2", "BLOCK_3", "BLOCK_4"]

EXP2_METHOD = "math.exp2" if hasattr(math, "exp2") else "2.0**y"


def _w(lag, H):
    y = -(lag - 1) / H
    return math.exp2(y) if hasattr(math, "exp2") else (2.0 ** y)


def fail(msg):
    sys.stderr.write("P293D_STOP: " + msg + "\n")
    sys.exit(3)


# ----------------------------------------------------------------------------- DB (read-only)
def open_ro(path):
    if not os.path.isfile(path):
        fail("authorized DB not a regular file: " + path)
    uri = "file:" + path + "?mode=ro"           # absolute path; mode=ro; NO immutable
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=1;")         # connection setting, not a DB write
    val = conn.execute("PRAGMA query_only;").fetchone()[0]
    if int(val) != 1:
        fail("PRAGMA query_only not 1 (got %r)" % (val,))
    return conn


def load_draws(conn, identity):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name=?", (VIEW,)
    ).fetchone()
    if not row:
        fail("source view missing: " + VIEW)
    cur = conn.execute(
        "SELECT id, draw, date, numbers, special FROM %s "
        "ORDER BY CAST(draw AS INTEGER) ASC, id ASC" % VIEW
    )
    cols = [d[0] for d in cur.description]
    identity["columns_returned"] = cols
    if cols != EXPECTED_COLS:
        fail("unexpected columns: %r" % (cols,))
    draws = []
    prev_cast = None
    seen = set()
    specials_in_range = 0
    specials_null = 0
    for (rid, draw, date, numbers_json, special) in cur.fetchall():
        nums = json.loads(numbers_json)
        if not isinstance(nums, list):
            fail("numbers not a list for draw %s" % draw)
        nums = [int(x) for x in nums]
        if len(nums) != TICKET_SIZE:
            fail("draw %s has %d main numbers (expected 6)" % (draw, len(nums)))
        if len(set(nums)) != TICKET_SIZE:
            fail("draw %s main numbers not unique: %r" % (draw, nums))
        if any(x < POOL_MIN or x > POOL_MAX for x in nums):
            fail("draw %s main number out of [1,49]: %r" % (draw, nums))
        c = int(draw)
        if prev_cast is not None and c < prev_cast:
            fail("ordering violation at draw %s (CAST not non-decreasing)" % draw)
        prev_cast = c
        if draw in seen:
            fail("duplicate draw identity: %s" % draw)
        seen.add(draw)
        if special is None:
            sp = None
            specials_null += 1
        else:
            sp = int(special)
            if sp < POOL_MIN or sp > POOL_MAX:
                fail("special out of [1,49] for draw %s: %r" % (draw, sp))
            specials_in_range += 1
        draws.append({"id": rid, "draw": draw, "date": date,
                      "main": frozenset(nums), "main_sorted": sorted(nums), "special": sp})
    # frozen identity checks
    if len(draws) != EXPECTED_TOTAL:
        fail("total draws %d != expected %d" % (len(draws), EXPECTED_TOTAL))
    if draws[0]["draw"] != EXPECTED_FIRST:
        fail("first draw %s != %s" % (draws[0]["draw"], EXPECTED_FIRST))
    if draws[-1]["draw"] != EXPECTED_LAST:
        fail("last draw %s != %s" % (draws[-1]["draw"], EXPECTED_LAST))
    n_targets = len(draws) - ELIGIBLE_START
    identity.update({
        "query_only": 1,
        "total_draws": len(draws),
        "first_draw": draws[0]["draw"],
        "last_draw": draws[-1]["draw"],
        "eligible_target_first": ELIGIBLE_START,
        "eligible_target_last": len(draws) - 1,
        "n_eligible_targets": n_targets,
        "special_in_range_count": specials_in_range,
        "special_null_count": specials_null,
    })
    if n_targets != 1370:
        fail("n_eligible_targets %d != 1370" % n_targets)
    return draws


# ----------------------------------------------------------------------------- strategies
def freq_ticket(draws, t, K):
    counts = [0] * (POOL_MAX + 1)
    for pos in range(t - K, t):
        for x in draws[pos]["main"]:
            counts[x] += 1
    ranked = sorted(range(POOL_MIN, POOL_MAX + 1), key=lambda x: (-counts[x], x))
    return frozenset(ranked[:TICKET_SIZE])


def exp_ticket(draws, t, N, H):
    score = [0.0] * (POOL_MAX + 1)
    for lag in range(1, N + 1):
        w = _w(lag, H)
        for x in draws[t - lag]["main"]:
            score[x] += w
    ranked = sorted(range(POOL_MIN, POOL_MAX + 1), key=lambda x: (-score[x], x))
    return frozenset(ranked[:TICKET_SIZE])


def strategy_tickets(draws, t):
    tk = {}
    for name in STRATEGY_ORDER:
        if name in FREQ_K:
            tk[name] = freq_ticket(draws, t, FREQ_K[name])
        elif name == "prior_draw":
            tk[name] = frozenset(draws[t - 1]["main"])
        else:
            N, H = EXP_NH[name]
            tk[name] = exp_ticket(draws, t, N, H)
    return [tk[name] for name in STRATEGY_ORDER]   # index 0..6 in fixed order


# ----------------------------------------------------------------------------- portfolio
def select_portfolio(ticket_list, B):
    """Outcome-blind selection: maximize union M; tie -> min total pairwise overlap;
    tie -> earliest itertools.combinations(range(7),B) subset. Returns dict (no outcome)."""
    best_key = None
    best = None
    for subset in combinations(range(7), B):
        union = set()
        for i in subset:
            union |= ticket_list[i]
        M = len(union)
        overlap = 0
        for a in range(B):
            ta = ticket_list[subset[a]]
            for b in range(a + 1, B):
                overlap += len(ta & ticket_list[subset[b]])
        key = (-M, overlap)
        if best_key is None or key < best_key:        # strict: earliest wins ties
            best_key = key
            best = {"subset": subset, "M": M, "overlap": overlap, "union": frozenset(union)}
    return best


# ----------------------------------------------------------------------------- hypergeometric
def hyp_pmf(M, k):
    if k < 0 or k > TICKET_SIZE or k > M or (TICKET_SIZE - k) > (POOL_N - M):
        return 0.0
    return math.comb(M, k) * math.comb(POOL_N - M, TICKET_SIZE - k) / C_TOTAL


# ----------------------------------------------------------------------------- helpers
def subset_label(subset):
    return "+".join(STRATEGY_ORDER[i] for i in subset)


def canon(obj):
    if isinstance(obj, float):
        return round(obj, 12)
    if isinstance(obj, dict):
        return {k: canon(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [canon(v) for v in obj]
    return obj


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt(x):
    return "%.10f" % x


# ----------------------------------------------------------------------------- main analysis
def run(outdir):
    real_out = os.path.realpath(outdir)
    if real_out != DURABLE_ROOT and not real_out.startswith(DURABLE_ROOT + os.sep):
        fail("outdir outside durable root: " + real_out)
    os.makedirs(real_out, exist_ok=True)

    identity = {"db_path": AUTHORIZED_DB, "view": VIEW}
    conn = open_ro(AUTHORIZED_DB)
    try:
        draws = load_draws(conn, identity)
    finally:
        conn.close()

    eligible = list(range(ELIGIBLE_START, len(draws)))   # 750..2119
    recs = {}
    for t in eligible:
        tlist = strategy_tickets(draws, t)
        target_main = draws[t]["main"]
        ind_hits = [len(tlist[i] & target_main) for i in range(7)]
        ports = {}
        for B in BUDGETS:
            sel = select_portfolio(tlist, B)
            hits = len(sel["union"] & target_main)
            ports[B] = {"subset": sel["subset"], "M": sel["M"], "overlap": sel["overlap"],
                        "redundancy": TICKET_SIZE * B - sel["M"], "hits": hits}
        recs[t] = {"t": t, "draw": draws[t]["draw"], "tickets": tlist,
                   "ind_hits": ind_hits, "ports": ports}

    # ---- per-target CSV (all integers) ----
    with open(os.path.join(real_out, "FIXED_BUDGET_PORTFOLIO_RESULT_TABLE.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["target_index", "target_draw", "budget_B", "selected_subset",
                    "union_size_M", "redundancy", "total_pairwise_overlap", "union_hits"])
        for t in eligible:
            r = recs[t]
            for B in BUDGETS:
                p = r["ports"][B]
                w.writerow([t, r["draw"], B, subset_label(p["subset"]),
                            p["M"], p["redundancy"], p["overlap"], p["hits"]])

    # ---- aggregation ----
    portfolio_summary = {}    # B -> seg -> {...}
    for B in BUDGETS:
        portfolio_summary[str(B)] = {}
        for seg in SEGMENT_ORDER:
            lo, hi = SEGMENTS[seg]
            positions = [t for t in eligible if lo <= t <= hi]
            n = len(positions)
            sum_hits = 0
            hit_dist = [0] * 7
            sum_M = 0
            sum_red = 0
            sum_overlap = 0
            ref_a_dist = [0.0] * 7
            sel_freq = {}
            for t in positions:
                p = recs[t]["ports"][B]
                sum_hits += p["hits"]
                hit_dist[p["hits"]] += 1
                sum_M += p["M"]
                sum_red += p["redundancy"]
                sum_overlap += p["overlap"]
                for k in range(7):
                    ref_a_dist[k] += hyp_pmf(p["M"], k)
                lab = subset_label(p["subset"])
                sel_freq[lab] = sel_freq.get(lab, 0) + 1
            mean_M = sum_M / n
            ref_a_mean = TICKET_SIZE * mean_M / POOL_N
            ref_b_mean = (TICKET_SIZE * (TICKET_SIZE * B)) / POOL_N
            ref_b_dist = [hyp_pmf(TICKET_SIZE * B, k) for k in range(7)]
            obs_mean = sum_hits / n
            portfolio_summary[str(B)][seg] = {
                "n_targets": n,
                "mean_union_hits": obs_mean,
                "union_hit_distribution_0to6": hit_dist,
                "mean_union_size_M": mean_M,
                "mean_redundancy": sum_red / n,
                "mean_pairwise_overlap": sum_overlap / n,
                "ref_a_conditioned_mean": ref_a_mean,
                "ref_a_conditioned_dist_0to6": [v / n for v in ref_a_dist],
                "ref_b_diversified_mean": ref_b_mean,
                "ref_b_diversified_dist_0to6": ref_b_dist,
                "delta_vs_ref_a": obs_mean - ref_a_mean,
                "delta_vs_ref_b": obs_mean - ref_b_mean,
                "selection_frequency": sel_freq,
            }

    # ---- individual strategy context (supporting only) ----
    individual = {}
    for seg in SEGMENT_ORDER:
        lo, hi = SEGMENTS[seg]
        positions = [t for t in eligible if lo <= t <= hi]
        n = len(positions)
        individual[seg] = {}
        for i, name in enumerate(STRATEGY_ORDER):
            sh = 0
            dist = [0] * 7
            for t in positions:
                h = recs[t]["ind_hits"][i]
                sh += h
                dist[h] += 1
            individual[seg][name] = {"n_targets": n, "mean_hits": sh / n,
                                     "hit_distribution_0to6": dist}

    # ---- seven-ticket overlap / jaccard (mean over ALL eligible) + mean unique ----
    all_positions = eligible
    nall = len(all_positions)
    pair_overlap = {}
    pair_jacc = {}
    for i in range(7):
        for j in range(i + 1, 7):
            pair_overlap[(i, j)] = 0
            pair_jacc[(i, j)] = 0.0
    sum_unique = 0
    for t in all_positions:
        tl = recs[t]["tickets"]
        u7 = set()
        for s in tl:
            u7 |= s
        sum_unique += len(u7)
        for i in range(7):
            for j in range(i + 1, 7):
                inter = len(tl[i] & tl[j])
                uni = len(tl[i] | tl[j])
                pair_overlap[(i, j)] += inter
                pair_jacc[(i, j)] += inter / uni
    seven_pairs = []
    for i in range(7):
        for j in range(i + 1, 7):
            seven_pairs.append({
                "strategy_i": STRATEGY_ORDER[i],
                "strategy_j": STRATEGY_ORDER[j],
                "mean_overlap": pair_overlap[(i, j)] / nall,
                "mean_jaccard": pair_jacc[(i, j)] / nall,
            })
    seven_ticket = {"pairs": seven_pairs, "mean_unique_numbers_across_seven": sum_unique / nall,
                    "n_targets": nall}

    # ---- duplication / redundancy reduction per budget (over ALL) ----
    duplication = {}
    for B in BUDGETS:
        s = portfolio_summary[str(B)]["ALL"]
        duplication[str(B)] = {
            "total_slots_6B": TICKET_SIZE * B,
            "mean_union_size_M": s["mean_union_size_M"],
            "mean_redundancy": s["mean_redundancy"],
            "unique_slot_fraction": s["mean_union_size_M"] / (TICKET_SIZE * B),
        }

    # ---- audit samples (leakage proof) ----
    audit = {}
    middle = eligible[len(eligible) // 2]   # 1435
    for label, t in [("first", eligible[0]), ("middle", middle), ("last", eligible[-1])]:
        tl = recs[t]["tickets"]
        strat_detail = {}
        for i, name in enumerate(STRATEGY_ORDER):
            if name in FREQ_K:
                K = FREQ_K[name]
                lo, hi = t - K, t - 1
            elif name == "prior_draw":
                lo, hi = t - 1, t - 1
            else:
                N, _ = EXP_NH[name]
                lo, hi = t - N, t - 1
            strat_detail[name] = {
                "window_pos_start": lo, "window_pos_end": hi,
                "window_draw_start": draws[lo]["draw"], "window_draw_end": draws[hi]["draw"],
                "ticket_sorted": sorted(tl[i]),
            }
        ports_blind = {}
        for B in BUDGETS:
            p = recs[t]["ports"][B]
            ports_blind[str(B)] = {
                "selected_subset": subset_label(p["subset"]),
                "union_size_M_pre_outcome": p["M"],
                "pairwise_overlap_pre_outcome": p["overlap"],
                "union_hits_post_outcome": p["hits"],
                "redundancy": p["redundancy"],
            }
        audit[label] = {
            "target_index": t,
            "target_draw": draws[t]["draw"],
            "selection_computed_before_outcome": True,
            "strategies": strat_detail,
            "target_main_sorted_REVEALED_AFTER_SELECTION": draws[t]["main_sorted"],
            "portfolios": ports_blind,
        }

    # ---- assemble RESULTS payload (no wall-clock, no outdir path) ----
    results = {
        "schema": "P293D_FIXED_BUDGET_DIVERSITY_PORTFOLIO_RESULTS_v1",
        "meta": {
            "task_id": "P293D-BIG649-FIXED-BUDGET-DIVERSITY-PORTFOLIO-OBSERVATIONAL-AUDIT",
            "db_path": AUTHORIZED_DB,
            "view": VIEW,
            "strategy_order": STRATEGY_ORDER,
            "budgets": BUDGETS,
            "segments": {k: list(SEGMENTS[k]) for k in SEGMENT_ORDER},
            "exp2_method": EXP2_METHOD,
            "pool": [POOL_MIN, POOL_MAX],
            "ticket_size": TICKET_SIZE,
            "C_49_6": C_TOTAL,
            "descriptive_only": True,
            "p_values": False,
            "promotion": False,
            "prediction_success_claim": False,
        },
        "data_identity": identity,
        "portfolio_summary": portfolio_summary,
        "individual_strategy_context": individual,
        "seven_ticket": seven_ticket,
        "duplication_reduction": duplication,
        "audit_samples": audit,
    }
    results_canon = canon(results)
    blob = json.dumps(results_canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    canonical_digest = hashlib.sha256(blob.encode("ascii")).hexdigest()
    with open(os.path.join(real_out, "RESULTS.json"), "w") as f:
        f.write(blob)

    # ---- INDIVIDUAL_STRATEGY_CONTEXT.csv ----
    with open(os.path.join(real_out, "INDIVIDUAL_STRATEGY_CONTEXT.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["segment", "strategy", "n_targets", "mean_hits",
                    "hit0", "hit1", "hit2", "hit3", "hit4", "hit5", "hit6"])
        for seg in SEGMENT_ORDER:
            for name in STRATEGY_ORDER:
                d = individual[seg][name]
                w.writerow([seg, name, d["n_targets"], fmt(d["mean_hits"])] +
                           d["hit_distribution_0to6"])

    # ---- SEVEN_TICKET_OVERLAP_MATRIX.csv (upper triangle of symmetric 7x7) ----
    with open(os.path.join(real_out, "SEVEN_TICKET_OVERLAP_MATRIX.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["strategy_i", "strategy_j", "mean_overlap", "mean_jaccard"])
        for p in seven_pairs:
            w.writerow([p["strategy_i"], p["strategy_j"],
                        fmt(p["mean_overlap"]), fmt(p["mean_jaccard"])])

    # ---- PORTFOLIO_SELECTION_FREQUENCY.csv ----
    with open(os.path.join(real_out, "PORTFOLIO_SELECTION_FREQUENCY.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["budget_B", "segment", "selected_subset", "count", "fraction"])
        for B in BUDGETS:
            for seg in SEGMENT_ORDER:
                s = portfolio_summary[str(B)][seg]
                n = s["n_targets"]
                items = sorted(s["selection_frequency"].items(), key=lambda kv: (-kv[1], kv[0]))
                for lab, cnt in items:
                    w.writerow([B, seg, lab, cnt, fmt(cnt / n)])

    # ---- per-run hash record ----
    out_files = ["FIXED_BUDGET_PORTFOLIO_RESULT_TABLE.csv", "INDIVIDUAL_STRATEGY_CONTEXT.csv",
                 "SEVEN_TICKET_OVERLAP_MATRIX.csv", "PORTFOLIO_SELECTION_FREQUENCY.csv",
                 "RESULTS.json"]
    file_hashes = {fn: sha256_file(os.path.join(real_out, fn)) for fn in out_files}
    combined = hashlib.sha256(
        "\n".join("%s:%s" % (fn, file_hashes[fn]) for fn in sorted(file_hashes)).encode("ascii")
    ).hexdigest()
    run_hashes = {
        "canonical_results_digest": canonical_digest,
        "file_sha256": file_hashes,
        "combined_artifact_digest": combined,
        "headline": {
            "n_eligible_targets": identity["n_eligible_targets"],
            "total_draws": identity["total_draws"],
            "first_draw": identity["first_draw"],
            "last_draw": identity["last_draw"],
            "mean_union_hits_ALL": {str(B): portfolio_summary[str(B)]["ALL"]["mean_union_hits"]
                                    for B in BUDGETS},
            "ref_a_mean_ALL": {str(B): portfolio_summary[str(B)]["ALL"]["ref_a_conditioned_mean"]
                               for B in BUDGETS},
            "ref_b_mean_ALL": {str(B): portfolio_summary[str(B)]["ALL"]["ref_b_diversified_mean"]
                               for B in BUDGETS},
        },
    }
    with open(os.path.join(real_out, "RUN_HASHES.json"), "w") as f:
        f.write(json.dumps(canon(run_hashes), sort_keys=True, indent=2))

    print(json.dumps({"status": "OK", "outdir": real_out,
                      "canonical_results_digest": canonical_digest,
                      "combined_artifact_digest": combined,
                      "file_sha256": file_hashes,
                      "headline": run_hashes["headline"]}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    run(args.outdir)


if __name__ == "__main__":
    main()
