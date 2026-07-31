#!/usr/bin/env python3
# =============================================================================
# P294B independent locked-split reproduction engine
# -----------------------------------------------------------------------------
# Standard library ONLY. Read-only DB access (SQLite URI mode=ro + PRAGMA
# query_only=1). Writes ONLY under the run directory passed as argv[1].
#
# This engine is an INDEPENDENT re-implementation of the verified P294A-R1 frozen
# contract (FROZEN_REPRODUCTION_SPEC.md / FROZEN_REPRODUCTION_DECISION_RULE.md).
# It imports, executes, copies, or patches NO P294A engine code. It performs no
# network access, no subprocess, no randomness, no simulation, no DB write, no DB
# copy, and no write outside the run directory.
#
# Usage:  python3 independent_engine.py <run_output_dir>
# =============================================================================

import sys
import os
import json
import csv
import hashlib
import sqlite3
from math import comb
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from fractions import Fraction
from datetime import datetime, timezone

# ---- Decimal precision per frozen contract (100; floor is 80) ----
DECIMAL_PREC = 100
getcontext().prec = DECIMAL_PREC

# ----------------------------- frozen constants ------------------------------
AUTHORIZED_DB = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
EXPECT_DB_SHA256 = "41e9c37948650c1d881502f7d204a2656c16e61e8e7b96058d23da76dd666cab"
EXPECT_ROWS = 2120
EXPECT_FIRST_DRAW = 96000001
EXPECT_LAST_DRAW = 115000065
ELIGIBLE_LO, ELIGIBLE_HI = 750, 2119          # inclusive 0-based target indices
DISCOVERY_LO, DISCOVERY_HI = 750, 1599        # 850 targets
LOCKBOX_LO, LOCKBOX_HI = 1600, 2119           # 520 targets
DISCOVERY_FETCH_LIMIT = 1600                  # parse numbers for rows 0..1599 only
BLOCKS = [(1600, 1729), (1730, 1859), (1860, 1989), (1990, 2119)]
CANDIDATES = ["trend_hot_50_300", "trend_cold_50_300",
              "trend_hot_300_750", "trend_cold_300_750"]
POOL, DRAWN, TICKET = 49, 6, 6                 # 49-number pool, 6 drawn, 6-number ticket

# Literal read-only SQL with the fixed authorized view name (no interpolation).
Q_COUNT = "SELECT COUNT(*) FROM draws_big_lotto_canonical_main"
Q_META = ("SELECT draw, id FROM draws_big_lotto_canonical_main "
          "ORDER BY CAST(draw AS INTEGER) ASC, id ASC")
Q_DISC = ("SELECT draw, id, numbers FROM draws_big_lotto_canonical_main "
          "ORDER BY CAST(draw AS INTEGER) ASC, id ASC LIMIT 1600")
Q_FULL = ("SELECT draw, id, numbers FROM draws_big_lotto_canonical_main "
          "ORDER BY CAST(draw AS INTEGER) ASC, id ASC")

EVENTS = []


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def log_event(kind, detail):
    EVENTS.append({"utc": utcnow(), "event": kind, "detail": detail})


def fail(msg):
    raise SystemExit("P294B_ENGINE_STOP: " + msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def open_ro(label):
    """Open the authorized DB strictly read-only; verify PRAGMA query_only==1."""
    uri = "file:" + AUTHORIZED_DB + "?mode=ro"
    log_event("db_open_attempt", {"label": label, "uri": uri})
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()
    cur.execute("PRAGMA query_only=1;")
    qo = cur.execute("PRAGMA query_only;").fetchone()[0]
    if int(qo) != 1:
        conn.close()
        fail("PRAGMA query_only != 1 (got %r)" % (qo,))
    log_event("db_open_ok", {"label": label, "query_only": int(qo)})
    return conn


def parse_numbers(raw):
    """Parse the JSON 'numbers' column into a frozenset of six unique ints 1..49."""
    arr = json.loads(raw)
    nums = [int(x) for x in arr]
    if len(nums) != 6:
        fail("numbers length != 6: %r" % (raw,))
    s = set(nums)
    if len(s) != 6:
        fail("numbers not unique: %r" % (raw,))
    for v in nums:
        if v < 1 or v > 49:
            fail("number out of 1..49: %r" % (raw,))
    return frozenset(nums)


# --------------------------- rational/decimal helpers ------------------------
def frac_to_decstr(fr, places=10):
    q = Decimal(1).scaleb(-places)
    d = (Decimal(fr.numerator) / Decimal(fr.denominator)).quantize(q, rounding=ROUND_HALF_EVEN)
    return str(d)


# --------------------------- candidate ticket logic --------------------------
def window_count_vector(draw_sets, t, n):
    """Counts per number over the n draws strictly before t: indices [t-n, t-1]."""
    c = [0] * (POOL + 1)
    for i in range(t - n, t):
        for x in draw_sets[i]:
            c[x] += 1
    return c


def tickets_all_candidates(draw_sets, t):
    """Discovery use: compute all four candidate tickets at target t (windows computed once)."""
    c50 = window_count_vector(draw_sets, t, 50)
    c300 = window_count_vector(draw_sets, t, 300)
    c750 = window_count_vector(draw_sets, t, 750)
    s_50_300 = [Fraction(c50[x], 50) - Fraction(c300[x], 300) for x in range(POOL + 1)]
    s_300_750 = [Fraction(c300[x], 300) - Fraction(c750[x], 750) for x in range(POOL + 1)]
    nums = list(range(1, POOL + 1))
    return {
        "trend_hot_50_300": sorted(nums, key=lambda x: (-s_50_300[x], x))[:6],
        "trend_cold_50_300": sorted(nums, key=lambda x: (s_50_300[x], x))[:6],
        "trend_hot_300_750": sorted(nums, key=lambda x: (-s_300_750[x], x))[:6],
        "trend_cold_300_750": sorted(nums, key=lambda x: (s_300_750[x], x))[:6],
    }


def ticket_one(draw_sets, t, candidate):
    """Lockbox use: compute ONLY the selected candidate's ticket (isolation: others never computed)."""
    nums = list(range(1, POOL + 1))
    if candidate.endswith("50_300"):
        c50 = window_count_vector(draw_sets, t, 50)
        c300 = window_count_vector(draw_sets, t, 300)
        score = [Fraction(c50[x], 50) - Fraction(c300[x], 300) for x in range(POOL + 1)]
    else:
        c300 = window_count_vector(draw_sets, t, 300)
        c750 = window_count_vector(draw_sets, t, 750)
        score = [Fraction(c300[x], 300) - Fraction(c750[x], 750) for x in range(POOL + 1)]
    if candidate.startswith("trend_hot"):
        nums.sort(key=lambda x: (-score[x], x))
    else:
        nums.sort(key=lambda x: (score[x], x))
    return nums[:6]


def hits(ticket, actual_set):
    return sum(1 for x in ticket if x in actual_set)


# --------------------------- exact null convolution --------------------------
def poly_mul_int(a, b):
    res = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        if ai:
            for j, bj in enumerate(b):
                res[i + j] += ai * bj
    return res


def poly_pow_int(base, e):
    result = [1]
    b = base[:]
    while e > 0:
        if e & 1:
            result = poly_mul_int(result, b)
        e >>= 1
        if e > 0:
            b = poly_mul_int(b, b)
    return result


def poly_mul_dec(a, b):
    res = [Decimal(0)] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        if ai != 0:
            for j, bj in enumerate(b):
                res[i + j] += ai * bj
    return res


def poly_pow_dec(base, e):
    result = [Decimal(1)]
    b = base[:]
    while e > 0:
        if e & 1:
            result = poly_mul_dec(result, b)
        e >>= 1
        if e > 0:
            b = poly_mul_dec(b, b)
    return result


# --------------------------------- main --------------------------------------
def main():
    if len(sys.argv) != 2:
        fail("usage: independent_engine.py <run_output_dir>")
    OUTDIR = os.path.abspath(sys.argv[1])
    if not os.path.isdir(OUTDIR):
        fail("output dir is not a directory: " + OUTDIR)

    def wp(name):
        return os.path.join(OUTDIR, name)

    def write_text(name, text):
        p = wp(name)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        return p

    def write_json(name, obj):
        return write_text(name, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def write_csv(name, header, rows):
        p = wp(name)
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            for r in rows:
                w.writerow(r)
            f.flush()
            os.fsync(f.fileno())
        return p

    try:
        # ---- DB file identity (filesystem read; precedes any SQL) ----
        rp = os.path.realpath(AUTHORIZED_DB)
        if rp != AUTHORIZED_DB:
            fail("DB realpath mismatch: " + rp)
        log_event("db_file_sha256_begin", {"path": AUTHORIZED_DB})
        db_sha = sha256_file(AUTHORIZED_DB)
        log_event("db_file_sha256_end", {"sha256": db_sha})
        if db_sha != EXPECT_DB_SHA256:
            fail("DB sha256 mismatch: " + db_sha)

        # =================== PHASE A: discovery (rows 0..1599) ===============
        conn = open_ro("discovery")
        cur = conn.cursor()
        n = cur.execute(Q_COUNT).fetchone()[0]
        log_event("query", {"label": "count", "rows": n})
        if n != EXPECT_ROWS:
            fail("row count != %d: %d" % (EXPECT_ROWS, n))
        meta = cur.execute(Q_META).fetchall()
        log_event("query", {"label": "meta", "rows": len(meta)})
        if len(meta) != EXPECT_ROWS:
            fail("meta rows != %d" % EXPECT_ROWS)
        draws_int = []
        prev_di = None
        for (draw, _rid) in meta:
            di = int(draw)
            if prev_di is not None and di <= prev_di:
                fail("draw not strictly ascending / duplicate identity: %d after %d" % (di, prev_di))
            prev_di = di
            draws_int.append(di)
        if draws_int[0] != EXPECT_FIRST_DRAW:
            fail("first draw mismatch: %d" % draws_int[0])
        if draws_int[-1] != EXPECT_LAST_DRAW:
            fail("last draw mismatch: %d" % draws_int[-1])
        eligible = ELIGIBLE_HI - ELIGIBLE_LO + 1
        if eligible != 1370:
            fail("eligible targets != 1370: %d" % eligible)

        disc_rows = cur.execute(Q_DISC).fetchall()
        log_event("query", {"label": "discovery_numbers", "rows": len(disc_rows), "limit": DISCOVERY_FETCH_LIMIT})
        if len(disc_rows) != DISCOVERY_FETCH_LIMIT:
            fail("discovery numbers fetch != %d" % DISCOVERY_FETCH_LIMIT)
        draw_sets = [None] * EXPECT_ROWS
        for idx, (draw, _rid, numbers) in enumerate(disc_rows):
            if int(draw) != draws_int[idx]:
                fail("discovery row draw mismatch at idx %d" % idx)
            draw_sets[idx] = parse_numbers(numbers)
        conn.close()
        log_event("db_close", {"label": "discovery"})

        # discovery totals over targets 750..1599 for all four candidates
        cand_hits = {c: 0 for c in CANDIDATES}
        for t in range(DISCOVERY_LO, DISCOVERY_HI + 1):
            actual = draw_sets[t]
            tk = tickets_all_candidates(draw_sets, t)
            for c in CANDIDATES:
                cand_hits[c] += hits(tk[c], actual)

        disc_expected = Fraction(850 * 36, 49)  # 30600/49
        cand_rows = []
        for c in CANDIDATES:
            th = cand_hits[c]
            exc = Fraction(th) - disc_expected
            cand_rows.append({"candidate": c, "total_hits": th, "excess": exc})

        # selection: greatest total hits (== greatest excess), tie-break by CANDIDATES order
        selected = None
        sel_hits = None
        for c in CANDIDATES:
            if sel_hits is None or cand_hits[c] > sel_hits:
                selected, sel_hits = c, cand_hits[c]
        tie_at_max = sum(1 for c in CANDIDATES if cand_hits[c] == sel_hits) > 1

        # ---- DISCOVERY_CANDIDATE_SUMMARY.csv ----
        disc_csv_rows = []
        for c in CANDIDATES:
            th = cand_hits[c]
            exc = Fraction(th) - disc_expected
            disc_csv_rows.append([c, th, frac_to_decstr(disc_expected, 10),
                                  frac_to_decstr(exc, 10), "true" if c == selected else "false"])
        write_csv("DISCOVERY_CANDIDATE_SUMMARY.csv",
                  ["candidate", "discovery_total_hits", "discovery_expected_hits",
                   "discovery_excess", "selected"], disc_csv_rows)

        # ---- LOCKBOX_SELECTION_RECORD.md (deterministic; written BEFORE lockbox) ----
        srl = []
        srl.append("# Independent Lockbox Selection Record — P294B")
        srl.append("")
        srl.append("lockbox_outcomes_accessed=false")
        srl.append("")
        srl.append("## Discovery (targets 750..1599, n=850)")
        srl.append("")
        srl.append("expected_hits = 850 * 36/49 = 30600/49 = " + frac_to_decstr(disc_expected, 10))
        srl.append("")
        srl.append("| candidate | discovery_total_hits | discovery_excess |")
        srl.append("|---|---|---|")
        for c in CANDIDATES:
            exc = Fraction(cand_hits[c]) - disc_expected
            srl.append("| %s | %d | %s |" % (c, cand_hits[c], frac_to_decstr(exc, 10)))
        srl.append("")
        srl.append("## Selection")
        srl.append("")
        srl.append("selected_candidate = " + selected)
        srl.append("selected_total_hits = %d" % sel_hits)
        srl.append("selection_rule = greatest discovery excess (equivalently greatest total hits; "
                   "shared null mean); ties broken by immutable candidate order")
        srl.append("tie_at_max = " + ("true" if tie_at_max else "false"))
        srl.append("candidate_order = " + ", ".join(CANDIDATES))
        srl.append("")
        srl.append("## Locked lockbox plan (no lockbox outcomes accessed)")
        srl.append("")
        srl.append("lockbox_targets = 1600..2119 (n=520)")
        srl.append("blocks = 1600..1729, 1730..1859, 1860..1989, 1990..2119")
        srl.append("statistic = total selected-ticket main-number hits S")
        srl.append("null = sum of 520 Hypergeometric(49,6,6); exact Decimal PGF convolution prec=100")
        srl.append("p_value = P(S_null >= S)  (one-sided upper tail, inclusive)")
        srl.append("retention = (excess > 0) AND (p < 0.05) AND (>=3 of 4 block excesses nonnegative)")
        srl.append("")
        sel_md = "\n".join(srl) + "\n"
        sp = write_text("LOCKBOX_SELECTION_RECORD.md", sel_md)
        with open(sp, "rb") as f:
            reread = f.read()
        sel_sha = hashlib.sha256(reread).hexdigest()
        if hashlib.sha256(sel_md.encode("utf-8")).hexdigest() != sel_sha:
            fail("selection record re-read SHA mismatch")
        write_text("LOCKBOX_SELECTION_RECORD.sha256", sel_sha + "  LOCKBOX_SELECTION_RECORD.md\n")
        log_event("selection_record_verified", {"sha256": sel_sha})

        # ---- LOCKBOX_ACCESS_GATE.md (written BEFORE lockbox DB open) ----
        gate_md = (
            "# Lockbox Access Gate — P294B\n\n"
            "The independent discovery selection is locked and SHA-256 verified before any lockbox\n"
            "main-number array is queried or parsed.\n\n"
            "selected_candidate = %s\n"
            "selection_record_sha256 = %s\n"
            "lockbox_outcomes_accessed_at_gate = false\n"
            "only_selected_candidate_evaluated_in_lockbox = true\n"
            "nonselected_candidate_lockbox_evaluation = never_computed\n"
            "lockbox_connection = fresh_read_only_query_only\n"
        ) % (selected, sel_sha)
        write_text("LOCKBOX_ACCESS_GATE.md", gate_md)
        log_event("lockbox_access_gate_written", {"selected": selected})

        # =================== PHASE B: lockbox (fresh ro connection) ==========
        conn2 = open_ro("lockbox")
        cur2 = conn2.cursor()
        n2 = cur2.execute(Q_COUNT).fetchone()[0]
        log_event("query", {"label": "lockbox_count", "rows": n2})
        if n2 != EXPECT_ROWS:
            fail("lockbox count != %d" % EXPECT_ROWS)
        full = cur2.execute(Q_FULL).fetchall()
        log_event("query", {"label": "lockbox_full_numbers", "rows": len(full)})
        if len(full) != EXPECT_ROWS:
            fail("lockbox full fetch != %d" % EXPECT_ROWS)
        full_sets = [None] * EXPECT_ROWS
        for idx, (draw, _rid, numbers) in enumerate(full):
            if int(draw) != draws_int[idx]:
                fail("full row draw mismatch at idx %d" % idx)
            full_sets[idx] = parse_numbers(numbers)
        for idx in range(DISCOVERY_FETCH_LIMIT):
            if full_sets[idx] != draw_sets[idx]:
                fail("discovery/lockbox row array divergence at idx %d" % idx)
        conn2.close()
        log_event("db_close", {"label": "lockbox"})

        # evaluate ONLY the selected candidate over lockbox targets
        per_target = []
        S = 0
        for t in range(LOCKBOX_LO, LOCKBOX_HI + 1):
            tk = ticket_one(full_sets, t, selected)
            h = hits(tk, full_sets[t])
            S += h
            per_target.append((t, draws_int[t], tk, h))

        # blocks
        blk_expected = Fraction(130 * 36, 49)  # 4680/49
        block_rows = []
        block_nonneg = 0
        block_obs_sum = 0
        for bi, (lo, hi) in enumerate(BLOCKS, start=1):
            obs = sum(h for (t, _d, _tk, h) in per_target if lo <= t <= hi)
            block_obs_sum += obs
            exc = Fraction(obs) - blk_expected
            nn = exc >= 0
            if nn:
                block_nonneg += 1
            block_rows.append((bi, lo, hi, hi - lo + 1, obs, exc, nn))
        if block_obs_sum != S:
            fail("block observed sum %d != S %d" % (block_obs_sum, S))

        lock_expected = Fraction(520 * 36, 49)  # 18720/49
        S_excess = Fraction(S) - lock_expected

        # exact null: integer PGF convolution
        D = comb(49, 6)  # 13983816
        a = [comb(6, k) * comb(43, 6 - k) for k in range(7)]
        if sum(a) != D:
            fail("hypergeometric numerator sum %d != C(49,6) %d" % (sum(a), D))
        A = poly_pow_int(a, 520)
        if len(A) != 3121:
            fail("integer convolution length != 3121: %d" % len(A))
        total_mass_int = sum(A)
        if total_mass_int != D ** 520:
            fail("integer mass sum != C(49,6)^520")
        tail_int = sum(A[s] for s in range(S, 3121))
        p_exact = Fraction(tail_int, D ** 520)

        # Decimal PGF convolution (contract method, prec=100)
        pk = [Decimal(a[k]) / Decimal(D) for k in range(7)]
        C = poly_pow_dec(pk, 520)
        if len(C) != 3121:
            fail("decimal convolution length != 3121: %d" % len(C))
        mass_dec = sum(C)
        p_dec = sum(C[s] for s in range(S, 3121))
        mean_pgf_dec = sum(Decimal(s) * C[s] for s in range(3121))
        mean_exact_dec = Decimal(520 * 36) / Decimal(49)

        p_exact_dec = Decimal(tail_int) / Decimal(D ** 520)
        p_abs_delta = abs(p_dec - p_exact_dec)

        # retention
        cond_excess = S_excess > 0
        cond_p = p_dec < Decimal("0.05")
        cond_blocks = block_nonneg >= 3
        retention = "PASS" if (cond_excess and cond_p and cond_blocks) else "FAIL"
        repro_class = ("P294B_LOCKED_SPLIT_REPRODUCTION_CONFIRMED_NO_HOLDOUT_RETENTION"
                       if retention == "FAIL"
                       else "P294B_LOCKED_SPLIT_REPRODUCTION_EXPLORATORY_RETENTION_ONLY")

        # ----------------------------- outputs ------------------------------
        # lockbox result table (aggregate, selected candidate only)
        write_csv("LOCKBOX_RESULT_TABLE.csv",
                  ["selected_candidate", "n_lockbox_targets", "S_total_hits",
                   "null_mean", "excess", "excess_positive",
                   "p_value_upper_tail", "p_value_lt_0_05", "retention"],
                  [[selected, 520, S, frac_to_decstr(lock_expected, 10),
                    frac_to_decstr(S_excess, 10), "true" if cond_excess else "false",
                    frac_to_decstr(p_exact, 12), "true" if cond_p else "false", retention]])

        # block stability
        bsr = []
        for (bi, lo, hi, ncnt, obs, exc, nn) in block_rows:
            bsr.append([bi, lo, hi, ncnt, obs, frac_to_decstr(blk_expected, 10),
                        frac_to_decstr(exc, 10), "true" if nn else "false"])
        write_csv("LOCKBOX_BLOCK_STABILITY.csv",
                  ["block_index", "target_lo", "target_hi", "n_targets",
                   "observed_hits", "null_mean", "excess", "nonnegative"], bsr)

        # per-target detail (deterministic, transparency)
        ptr = []
        for (t, d, tk, h) in per_target:
            ptr.append([t, d, " ".join(str(x) for x in tk), h])
        write_csv("LOCKBOX_PER_TARGET_DETAIL.csv",
                  ["target_index", "draw", "ticket", "hits"], ptr)

        # exact null results
        enr = []
        enr.append("# Independent Lockbox Exact Null Results — P294B")
        enr.append("")
        enr.append("selected_candidate = " + selected)
        enr.append("S_observed_total_hits = %d" % S)
        enr.append("null_mean = 520 * 36/49 = 18720/49 = " + frac_to_decstr(lock_expected, 12))
        enr.append("excess = S - null_mean = " + frac_to_decstr(S_excess, 12))
        enr.append("")
        enr.append("## Exact upper-tail p-value  P(S_null >= %d)" % S)
        enr.append("")
        enr.append("p_value_decimal_pgf_prec100 = " + str(p_dec))
        enr.append("p_value_exact_rational_as_decimal = " + str(p_exact_dec))
        enr.append("p_value_exact_rational_denominator = C(49,6)^520  (== 13983816^520)")
        enr.append("decimal_vs_exact_abs_delta = " + str(p_abs_delta))
        enr.append("p_value_lt_0_05 = " + ("true" if cond_p else "false"))
        enr.append("")
        enr.append("## Per-target null pmf  X ~ Hypergeometric(N=49,K=6,n=6)")
        enr.append("")
        enr.append("| k | numerator a_k = C(6,k)C(43,6-k) | p_k = a_k / C(49,6) |")
        enr.append("|---|---|---|")
        for k in range(7):
            enr.append("| %d | %d | %s |" % (k, a[k], str(pk[k])))
        enr.append("")
        enr.append("denominator C(49,6) = %d" % D)
        enr.append("")
        write_text("LOCKBOX_EXACT_NULL_RESULTS.md", "\n".join(enr) + "\n")

        # numerical validation
        nv = []
        nv.append("# Independent Numerical Validation — P294B")
        nv.append("")
        nv.append("decimal_precision = %d  (frozen contract: precision 100, floor 80)" % DECIMAL_PREC)
        nv.append("")
        nv.append("## Per-target null checks (exact)")
        nv.append("sum_a_k = %d ; C(49,6) = %d ; equal = %s" % (sum(a), D, sum(a) == D))
        mean_one = Fraction(sum(k * a[k] for k in range(7)), D)
        nv.append("per_target_mean_E[X] = sum k*a_k / C(49,6) = %s = 36/49 ? %s"
                  % (str(mean_one), mean_one == Fraction(36, 49)))
        nv.append("")
        nv.append("## Sum-distribution mass checks")
        nv.append("integer_total_mass = sum(A) == C(49,6)^520 ? %s" % (total_mass_int == D ** 520))
        nv.append("decimal_total_mass sum(C) = " + str(mass_dec))
        nv.append("decimal_mass_abs_delta_from_1 = " + str(abs(mass_dec - Decimal(1))))
        nv.append("")
        nv.append("## Mean checks (S over 520 targets)")
        nv.append("analytic_mean_520 = 18720/49 = " + str(mean_exact_dec))
        nv.append("pgf_derived_mean sum s*C[s] = " + str(mean_pgf_dec))
        nv.append("mean_abs_delta = " + str(abs(mean_pgf_dec - mean_exact_dec)))
        nv.append("")
        nv.append("## p-value cross-check")
        nv.append("p_value_decimal_pgf = " + str(p_dec))
        nv.append("p_value_exact_rational_decimal = " + str(p_exact_dec))
        nv.append("abs_delta = " + str(p_abs_delta))
        nv.append("")
        write_text("NUMERICAL_VALIDATION.md", "\n".join(nv) + "\n")

        # DB source revalidation (deterministic; no wall-clock)
        write_json("DB_SOURCE_REVALIDATION.json", {
            "authorized_db": AUTHORIZED_DB,
            "db_realpath": rp,
            "db_sha256": db_sha,
            "db_sha256_matches_expected": db_sha == EXPECT_DB_SHA256,
            "source_view": "draws_big_lotto_canonical_main",
            "query_only_verified": True,
            "ordered_rows": EXPECT_ROWS,
            "first_draw": draws_int[0],
            "last_draw": draws_int[-1],
            "eligible_targets": eligible,
            "discovery_numbers_fetched": DISCOVERY_FETCH_LIMIT,
            "lockbox_full_rows": EXPECT_ROWS,
            "ordering": "CAST(draw AS INTEGER) ASC, id ASC",
        })

        # canonical result (deterministic; byte-identical across runs)
        canonical = {
            "task": "P294B",
            "db_sha256": db_sha,
            "source_view": "draws_big_lotto_canonical_main",
            "ordered_rows": EXPECT_ROWS,
            "first_draw": draws_int[0],
            "last_draw": draws_int[-1],
            "eligible_targets": eligible,
            "discovery": {
                "targets": [DISCOVERY_LO, DISCOVERY_HI],
                "n_targets": DISCOVERY_HI - DISCOVERY_LO + 1,
                "expected_hits_fraction": "%d/%d" % (disc_expected.numerator, disc_expected.denominator),
                "expected_hits_decimal": frac_to_decstr(disc_expected, 12),
                "candidates": [
                    {"candidate": c, "total_hits": cand_hits[c],
                     "excess_decimal": frac_to_decstr(Fraction(cand_hits[c]) - disc_expected, 12)}
                    for c in CANDIDATES
                ],
                "selected_candidate": selected,
                "selected_total_hits": sel_hits,
                "tie_at_max": tie_at_max,
            },
            "lockbox": {
                "targets": [LOCKBOX_LO, LOCKBOX_HI],
                "n_targets": 520,
                "selected_candidate": selected,
                "S_total_hits": S,
                "null_mean_fraction": "%d/%d" % (lock_expected.numerator, lock_expected.denominator),
                "null_mean_decimal": frac_to_decstr(lock_expected, 12),
                "excess_decimal": frac_to_decstr(S_excess, 12),
                "excess_positive": cond_excess,
                "p_value_decimal_pgf_prec100": str(p_dec),
                "p_value_exact_rational_decimal": str(p_exact_dec),
                "p_value_lt_0_05": cond_p,
                "blocks": [
                    {"block": bi, "range": [lo, hi], "n_targets": ncnt,
                     "observed_hits": obs,
                     "null_mean_decimal": frac_to_decstr(blk_expected, 12),
                     "excess_decimal": frac_to_decstr(Fraction(obs) - blk_expected, 12),
                     "nonnegative": bool(nn)}
                    for (bi, lo, hi, ncnt, obs, exc, nn) in block_rows
                ],
                "blocks_nonnegative_count": block_nonneg,
                "retention_conditions": {
                    "excess_positive": cond_excess,
                    "p_lt_0_05": cond_p,
                    "at_least_3_of_4_blocks_nonnegative": cond_blocks,
                },
                "retention": retention,
            },
            "reproduction_classification": repro_class,
        }
        write_json("CANONICAL_RESULT.json", canonical)

        # run hashes over deterministic files (byte-identical across runs)
        det_files = [
            "DISCOVERY_CANDIDATE_SUMMARY.csv", "LOCKBOX_SELECTION_RECORD.md",
            "LOCKBOX_SELECTION_RECORD.sha256", "LOCKBOX_ACCESS_GATE.md",
            "LOCKBOX_RESULT_TABLE.csv", "LOCKBOX_BLOCK_STABILITY.csv",
            "LOCKBOX_PER_TARGET_DETAIL.csv", "LOCKBOX_EXACT_NULL_RESULTS.md",
            "NUMERICAL_VALIDATION.md", "CANONICAL_RESULT.json",
            "DB_SOURCE_REVALIDATION.json",
        ]
        run_hashes = {}
        for fn in det_files:
            run_hashes[fn] = sha256_file(wp(fn))
        run_hashes["__canonical_result_sha256__"] = run_hashes["CANONICAL_RESULT.json"]
        write_json("RUN_HASHES.json", run_hashes)

        # console summary (my own independent result)
        print("P294B RUN COMPLETE")
        print("  selected_candidate :", selected, "(discovery hits %d)" % sel_hits)
        print("  discovery hits     :", {c: cand_hits[c] for c in CANDIDATES})
        print("  lockbox S          :", S, "  null_mean=", frac_to_decstr(lock_expected, 6),
              "  excess=", frac_to_decstr(S_excess, 6))
        print("  p_value (pgf)      :", str(p_dec)[:24])
        print("  p_value (exact)    :", str(p_exact_dec)[:24])
        print("  blocks nonneg      :", block_nonneg, "/4")
        print("  retention          :", retention)
        print("  reproduction_class :", repro_class)
        print("  canonical_result_sha256 :", run_hashes["CANONICAL_RESULT.json"])

    finally:
        # always emit the access-events log (timestamps; not byte-identical across runs)
        try:
            evp = wp("DB_ACCESS_EVENTS.jsonl")
            with open(evp, "w", encoding="utf-8", newline="") as f:
                for ev in EVENTS:
                    f.write(json.dumps(ev, sort_keys=True, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:  # pragma: no cover
            sys.stderr.write("WARN: could not write DB_ACCESS_EVENTS.jsonl: %r\n" % e)


if __name__ == "__main__":
    main()
