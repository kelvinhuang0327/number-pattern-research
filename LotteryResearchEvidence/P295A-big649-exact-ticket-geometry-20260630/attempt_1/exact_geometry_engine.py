#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P295A — BIG649 exact ticket-set geometry coverage audit (NON-PREDICTIVE).

Self-contained, standard-library-only, exact integer combinatorial engine.

Frozen contract: FROZEN_GEOMETRY_SPEC.md + FROZEN_DECISION_RULE.md (hash-pinned in
FROZEN_SPEC_HASH_RECORD.md before this file was authored).

This engine:
  * opens NO database, executes NO SQL, imports NO sqlite, reads NO historical outcomes;
  * uses NO network, NO subprocess, NO random module, NO Monte Carlo, NO normal approximation;
  * imports NO repository code and NO prior engine;
  * emits NO actual selectable lottery numbers and NO future-ticket output;
  * performs ONLY exact integer combinatorial counting over abstract membership groups,
    dividing integer masses by C(49,6) to obtain exact rational probabilities.

Usage:  python3 exact_geometry_engine.py <output_dir>
The output_dir must be the caller-supplied run directory under the P295A evidence root.

Outputs (deterministic, byte-identical across fresh processes):
  EXACT_GEOMETRY_RESULTS.csv, GEOMETRY_THRESHOLD_SUMMARY.csv,
  CANONICAL_RESULT.json, NUMERICAL_VALIDATION.md, CANONICAL_RESULT.sha256
"""

import sys
import os
import csv
import json
import hashlib
from math import comb
from fractions import Fraction
from decimal import Decimal, getcontext
from itertools import product

# ----- Frozen universe constants (mirror FROZEN_GEOMETRY_SPEC.md exactly) -----
N = 49                      # universe size (abstract positions)
DRAW = 6                    # winning numbers per draw
TOTAL = comb(N, DRAW)       # C(49,6) = 13,983,816  (exact integer)
BUDGETS = (2, 3, 4)
# geometry name -> (core_size c, per-ticket-unique size u); c + u == 6 for all.
GEOMETRIES = (
    ("disjoint_core_0", 0, 6),
    ("shared_core_2", 2, 4),
    ("shared_core_4", 4, 2),
    ("shared_core_5", 5, 1),
)
THRESHOLDS = (3, 4, 5, 6)
DECIMAL_PREC = 120          # >= 100 significant digits, per frozen spec
getcontext().prec = DECIMAL_PREC


def dec(fr):
    """Exact Fraction -> Decimal string at >=100 sig digits (deterministic)."""
    return str(Decimal(fr.numerator) / Decimal(fr.denominator))


def frac_str(fr):
    """Reduced rational 'numerator/denominator'."""
    return "%d/%d" % (fr.numerator, fr.denominator)


def hyper_mass(K, h):
    """Exact integer count of 6-subsets of 49 hitting a fixed K-set in exactly h points:
       C(K,h) * C(49-K, 6-h)."""
    return comb(K, h) * comb(N - K, DRAW - h)


def analyze(B, c, u):
    """Exact enumeration for budget B and geometry (core c, unique u)."""
    M = c + B * u                 # union size
    R = DRAW * B - M              # redundancy = c*(B-1)
    o = N - M                     # outside-group size
    assert c + u == DRAW
    assert R == c * (B - 1)
    assert o >= 0

    union_mass = [0] * (DRAW + 1)      # by union hit count h
    maxhit_mass = [0] * (DRAW + 1)     # by max single-ticket hit count
    single_mass = [0] * (DRAW + 1)     # marginal of ticket index 0
    exp_qual_num = {t: 0 for t in THRESHOLDS}   # sum weight * (#tickets >= t)
    unique_max_num = 0                 # mass where a strict unique max exists
    total = 0

    a_hi = min(c, DRAW)
    k_hi = min(u, DRAW)
    for a in range(a_hi + 1):
        wa = comb(c, a)
        if wa == 0:
            continue
        for ks in product(range(k_hi + 1), repeat=B):
            s = a + sum(ks)
            w = DRAW - s
            if w < 0 or w > o:
                continue
            weight = wa * comb(o, w)
            for ki in ks:
                weight *= comb(u, ki)
            if weight == 0:
                continue
            total += weight
            h = s                       # union hits = a + sum(ks) = 6 - w
            union_mass[h] += weight
            hits = [a + ki for ki in ks]
            mx = max(hits)
            maxhit_mass[mx] += weight
            single_mass[hits[0]] += weight
            if hits.count(mx) == 1:
                unique_max_num += weight
            for t in THRESHOLDS:
                cge = 0
                for hh in hits:
                    if hh >= t:
                        cge += 1
                if cge:
                    exp_qual_num[t] += weight * cge

    return {
        "B": B, "c": c, "u": u, "M": M, "R": R, "o": o,
        "total": total,
        "union_mass": union_mass,
        "maxhit_mass": maxhit_mass,
        "single_mass": single_mass,
        "exp_qual_num": exp_qual_num,
        "unique_max_num": unique_max_num,
    }


def validate(res):
    """Return (checks list of (name, bool), all_pass bool). Exact integer/rational checks only."""
    B, M = res["B"], res["M"]
    total = res["total"]
    checks = []

    checks.append(("total_mass_equals_C(49,6)", total == TOTAL))

    checks.append(("union_dist_sums_to_total", sum(res["union_mass"]) == TOTAL))

    union_match = all(res["union_mass"][h] == hyper_mass(M, h) for h in range(DRAW + 1))
    checks.append(("union_dist_equals_Hypergeometric(49,M,6)", union_match))

    single_match = all(res["single_mass"][j] == hyper_mass(DRAW, j) for j in range(DRAW + 1))
    checks.append(("single_ticket_marginal_equals_Hypergeometric(49,6,6)", single_match))

    checks.append(("maxhit_dist_sums_to_total", sum(res["maxhit_mass"]) == TOTAL))

    max_tails = [sum(res["maxhit_mass"][m] for m in range(t, DRAW + 1)) for t in THRESHOLDS]
    mono = all(max_tails[i] >= max_tails[i + 1] for i in range(len(max_tails) - 1))
    checks.append(("threshold_monotone_P(max>=3)>=...>=P(max>=6)", mono))

    # E[# tickets >= t] == B * (single-ticket tail mass), exact integer identity.
    eq_xcheck = True
    for t in THRESHOLDS:
        single_tail = sum(res["single_mass"][j] for j in range(t, DRAW + 1))
        if res["exp_qual_num"][t] != B * single_tail:
            eq_xcheck = False
    checks.append(("E[#tickets>=t]==B*P(single>=t)_exact", eq_xcheck))

    # E[union hits] == 6M/49 exactly.
    e_union = Fraction(sum(h * res["union_mass"][h] for h in range(DRAW + 1)), total)
    checks.append(("E[union_hits]==6M/49", e_union == Fraction(DRAW * M, N)))

    all_pass = all(ok for _, ok in checks)
    return checks, all_pass


def build_cell_record(res):
    B, M, total = res["B"], res["M"], res["total"]

    def P(num):
        return Fraction(num, total)

    union_dist = []
    for h in range(DRAW + 1):
        p = P(res["union_mass"][h])
        union_dist.append({"hits": h, "mass": res["union_mass"][h],
                           "prob_fraction": frac_str(p), "prob_decimal": dec(p)})
    maxhit_dist = []
    for m in range(DRAW + 1):
        p = P(res["maxhit_mass"][m])
        maxhit_dist.append({"max_hits": m, "mass": res["maxhit_mass"][m],
                            "prob_fraction": frac_str(p), "prob_decimal": dec(p)})
    single_dist = []
    for j in range(DRAW + 1):
        p = P(res["single_mass"][j])
        single_dist.append({"hits": j, "mass": res["single_mass"][j],
                            "prob_fraction": frac_str(p), "prob_decimal": dec(p)})

    thr_at_least_one = {}
    exp_qual = {}
    for t in THRESHOLDS:
        tail = sum(res["maxhit_mass"][m] for m in range(t, DRAW + 1))
        p = P(tail)
        thr_at_least_one[str(t)] = {"mass": tail, "prob_fraction": frac_str(p),
                                    "prob_decimal": dec(p)}
        eq = Fraction(res["exp_qual_num"][t], total)
        exp_qual[str(t)] = {"sum_mass": res["exp_qual_num"][t],
                            "expected_count_fraction": frac_str(eq),
                            "expected_count_decimal": dec(eq)}

    pum = P(res["unique_max_num"])
    e_union = Fraction(sum(h * res["union_mass"][h] for h in range(DRAW + 1)), total)

    checks, all_pass = validate(res)
    return {
        "budget": B,
        "core_size": res["c"],
        "unique_size_per_ticket": res["u"],
        "union_size_M": M,
        "redundancy_R": res["R"],
        "outside_size": res["o"],
        "total_integer_mass": total,
        "mass_equals_C49_6": (total == TOTAL),
        "expected_union_hits_fraction": frac_str(e_union),
        "expected_union_hits_decimal": dec(e_union),
        "union_hit_distribution": union_dist,
        "single_ticket_marginal": single_dist,
        "max_hit_distribution": maxhit_dist,
        "threshold_at_least_one_ticket": thr_at_least_one,
        "expected_qualifying_ticket_count": exp_qual,
        "prob_unique_strict_max": {"mass": res["unique_max_num"],
                                   "prob_fraction": frac_str(pum), "prob_decimal": dec(pum)},
        "validations": {name: ok for name, ok in checks},
        "validations_all_pass": all_pass,
    }


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: exact_geometry_engine.py <output_dir>\n")
        return 2
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)

    cells = []
    global_pass = True
    val_lines = []
    for B in BUDGETS:
        for name, c, u in GEOMETRIES:
            res = analyze(B, c, u)
            rec = build_cell_record(res)
            rec["geometry"] = name
            cells.append(rec)
            checks, all_pass = validate(res)
            global_pass = global_pass and all_pass
            for cname, ok in checks:
                val_lines.append((B, name, cname, ok))

    canonical = {
        "task_id": "P295A-BIG649-EXACT-TICKET-GEOMETRY-COVERAGE-AUDIT",
        "method": "exact_integer_combinatorial_enumeration_over_abstract_membership_groups",
        "universe": {"N": N, "draw_size": DRAW, "total_draw_outcomes_C_49_6": TOTAL},
        "decimal_precision_sig_digits": DECIMAL_PREC,
        "budgets": list(BUDGETS),
        "geometries": [g[0] for g in GEOMETRIES],
        "thresholds": list(THRESHOLDS),
        "nonpredictive_boundary": (
            "Abstract membership labels only; no actual lottery numbers; no prediction, edge, "
            "betting, prize, payout, EV, activation, or promotion claim. Overlap geometry only "
            "rearranges joint probability mass between coverage and concentration objectives and "
            "cannot create predictive information."),
        "all_validations_pass": global_pass,
        "results": cells,
    }

    # CANONICAL_RESULT.json (deterministic: sorted keys, fixed indent, ASCII, no floats).
    json_bytes = json.dumps(canonical, sort_keys=True, indent=2,
                            ensure_ascii=True).encode("utf-8") + b"\n"
    with open(os.path.join(outdir, "CANONICAL_RESULT.json"), "wb") as f:
        f.write(json_bytes)
    digest = hashlib.sha256(json_bytes).hexdigest()
    with open(os.path.join(outdir, "CANONICAL_RESULT.sha256"), "w", newline="") as f:
        f.write("%s  CANONICAL_RESULT.json\n" % digest)

    # EXACT_GEOMETRY_RESULTS.csv
    res_path = os.path.join(outdir, "EXACT_GEOMETRY_RESULTS.csv")
    with open(res_path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        header = ["budget", "geometry", "core_size", "unique_size_per_ticket", "union_size_M",
                  "redundancy_R", "outside_size", "total_integer_mass", "mass_equals_C49_6",
                  "expected_union_hits_fraction", "expected_union_hits_decimal",
                  "prob_unique_strict_max_fraction", "prob_unique_strict_max_decimal"]
        header += ["union_mass_h%d" % h for h in range(DRAW + 1)]
        header += ["maxhit_mass_m%d" % m for m in range(DRAW + 1)]
        header += ["single_ticket_mass_j%d" % j for j in range(DRAW + 1)]
        w.writerow(header)
        for rec in cells:
            row = [rec["budget"], rec["geometry"], rec["core_size"], rec["unique_size_per_ticket"],
                   rec["union_size_M"], rec["redundancy_R"], rec["outside_size"],
                   rec["total_integer_mass"], rec["mass_equals_C49_6"],
                   rec["expected_union_hits_fraction"], rec["expected_union_hits_decimal"],
                   rec["prob_unique_strict_max"]["prob_fraction"],
                   rec["prob_unique_strict_max"]["prob_decimal"]]
            row += [d["mass"] for d in rec["union_hit_distribution"]]
            row += [d["mass"] for d in rec["max_hit_distribution"]]
            row += [d["mass"] for d in rec["single_ticket_marginal"]]
            w.writerow(row)

    # GEOMETRY_THRESHOLD_SUMMARY.csv
    thr_path = os.path.join(outdir, "GEOMETRY_THRESHOLD_SUMMARY.csv")
    with open(thr_path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["budget", "geometry", "union_size_M", "redundancy_R", "threshold_t",
                    "p_at_least_one_ticket_ge_t_fraction", "p_at_least_one_ticket_ge_t_decimal",
                    "expected_qualifying_ticket_count_fraction",
                    "expected_qualifying_ticket_count_decimal"])
        for rec in cells:
            for t in THRESHOLDS:
                a1 = rec["threshold_at_least_one_ticket"][str(t)]
                eq = rec["expected_qualifying_ticket_count"][str(t)]
                w.writerow([rec["budget"], rec["geometry"], rec["union_size_M"], rec["redundancy_R"],
                            t, a1["prob_fraction"], a1["prob_decimal"],
                            eq["expected_count_fraction"], eq["expected_count_decimal"]])

    # NUMERICAL_VALIDATION.md (deterministic; no timestamps/paths)
    nv_path = os.path.join(outdir, "NUMERICAL_VALIDATION.md")
    lines = []
    lines.append("# NUMERICAL VALIDATION — P295A exact ticket geometry")
    lines.append("")
    lines.append("Exact integer / exact rational checks. C(49,6) = %d. Decimal precision = %d "
                 "significant digits." % (TOTAL, DECIMAL_PREC))
    lines.append("")
    lines.append("Overall: ALL CHECKS PASS = %s" % ("YES" if global_pass else "NO"))
    lines.append("")
    lines.append("| budget | geometry | check | result |")
    lines.append("|---|---|---|---|")
    for (B, name, cname, ok) in val_lines:
        lines.append("| %d | %s | %s | %s |" % (B, name, cname, "PASS" if ok else "FAIL"))
    lines.append("")
    with open(nv_path, "w", newline="") as f:
        f.write("\n".join(lines) + "\n")

    sys.stdout.write("P295A_ENGINE cells=%d all_validations=%s canonical_sha256=%s\n"
                     % (len(cells), "PASS" if global_pass else "FAIL", digest))
    return 0 if global_pass else 1


if __name__ == "__main__":
    sys.exit(main())
