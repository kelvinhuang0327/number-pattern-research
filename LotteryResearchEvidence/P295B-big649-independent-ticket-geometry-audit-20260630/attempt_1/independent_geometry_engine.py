#!/usr/bin/env python3
"""
P295B — Independent exact ticket-geometry reproduction engine.

Independent re-derivation of the P295A BIG649 abstract ticket-geometry coverage
analysis. This engine is authored from scratch from the frozen reproduction
contract (FROZEN_REPRODUCTION_GEOMETRY_SPEC.md / FROZEN_REPRODUCTION_DECISION_RULE.md)
and shares no code with the P295A engine.

NON-PREDICTIVE / LOCAL-ONLY / ARTIFACT-ONLY:
  * Uses only the Python standard library.
  * No sqlite / DB path / SQL / network / subprocess / random / simulation / Monte Carlo.
  * No historical lottery outcomes are read; no actual selectable lottery numbers are emitted.
  * Pure exact integer combinatorial counting (math.comb) with fractions.Fraction
    probabilities and decimal.Decimal (prec >= 100) rendering. No float is ever used.

Model (frozen):
  Universe of N=49 abstract positions; a draw is 6 distinct positions; total outcomes C(49,6).
  For budget B and geometry (core size c, unique size u, c+u=6):
    - one common-core group C of size c (in all B tickets),
    - B ticket-unique groups U_1..U_B each of size u (U_i in ticket i only),
    - one outside group O of size o = 49 - c - B*u (in no ticket).
  Enumerate every draw by group-membership counts (a, k_1..k_B, w) with a+sum(k_i)+w=6;
  exact integer count = C(c,a) * prod(C(u,k_i)) * C(o,w).
  Ticket i hits = a + k_i ; union hits = a + sum(k_i) = 6 - w ; max hit = a + max(k_i).

Outputs (written to --out dir, byte-identical across fresh runs):
  EXACT_GEOMETRY_RESULTS.csv, GEOMETRY_THRESHOLD_SUMMARY.csv,
  NUMERICAL_VALIDATION.md, CANONICAL_RESULT.json, CANONICAL_RESULT.sha256
"""

import argparse
import hashlib
import itertools
import json
import os
import sys
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from fractions import Fraction
from math import comb

# ---- frozen constants (must not change after FROZEN_SPEC_HASH_RECORD.md is hashed) ----
N_UNIVERSE = 49
DRAW_SIZE = 6
TOTAL_OUTCOMES = comb(N_UNIVERSE, DRAW_SIZE)  # C(49,6) = 13,983,816
BUDGETS = (2, 3, 4)
# (geometry name, core size c, unique size u); c + u == 6 for every geometry
GEOMETRIES = (
    ("disjoint_core_0", 0, 6),
    ("shared_core_2", 2, 4),
    ("shared_core_4", 4, 2),
    ("shared_core_5", 5, 1),
)
THRESHOLDS = (3, 4, 5, 6)

DECIMAL_PREC = 120          # >= 100 significant digits for full-precision rendering
SUMMARY_PLACES = 24         # fixed decimal places for the human-readable threshold summary
getcontext().prec = DECIMAL_PREC


def dec_full(fr):
    """Full-precision (>=100 sig digit) deterministic decimal rendering of a Fraction."""
    return str(Decimal(fr.numerator) / Decimal(fr.denominator))


def dec_round(fr, places=SUMMARY_PLACES):
    """Deterministic fixed-decimal-places rendering (ROUND_HALF_EVEN)."""
    q = Decimal(1).scaleb(-places)
    return str((Decimal(fr.numerator) / Decimal(fr.denominator)).quantize(q, rounding=ROUND_HALF_EVEN))


def frac_obj(fr):
    """Serialize a Fraction as exact numerator/denominator + full-precision decimal."""
    return {"num": fr.numerator, "den": fr.denominator, "decimal": dec_full(fr)}


def hyp_mass(N, K, n, h):
    """Exact integer mass of Hypergeometric(N, K, n) at h: C(K,h)*C(N-K,n-h)."""
    if h < 0 or h > n or h > K or (n - h) > (N - K):
        return 0
    return comb(K, h) * comb(N - K, n - h)


def analyze_cell(B, name, c, u):
    """Exact enumeration for one (budget, geometry) cell. Returns a result dict."""
    o = N_UNIVERSE - c - B * u
    M = c + B * u
    R = 6 * B - M
    if o < 0:
        raise ValueError(f"negative outside group: B={B} {name} c={c} u={u} o={o}")
    if c + u != DRAW_SIZE:
        raise ValueError(f"c+u != 6: B={B} {name} c={c} u={u}")

    total_mass = 0
    union_hit_mass = [0] * (DRAW_SIZE + 1)            # h = 0..6
    max_hit_mass = [0] * (DRAW_SIZE + 1)              # m = 0..6
    single_ticket_marginal_mass = [0] * (DRAW_SIZE + 1)  # ticket-0 marginal, j = 0..6
    qual_weighted = {t: 0 for t in THRESHOLDS}        # sum over draws of (#tickets>=t)*weight
    unique_max_mass = 0                               # draws with exactly one strict-max ticket

    for a in range(c + 1):
        c_a = comb(c, a)
        for ks in itertools.product(range(u + 1), repeat=B):
            s = a + sum(ks)
            w = DRAW_SIZE - s
            if w < 0 or w > o:
                continue
            weight = c_a * comb(o, w)
            for k in ks:
                weight *= comb(u, k)

            total_mass += weight
            union_hit_mass[s] += weight              # union hits = a + sum(ks) = 6 - w
            ticket_hits = [a + k for k in ks]
            mx = max(ticket_hits)
            max_hit_mass[mx] += weight
            single_ticket_marginal_mass[ticket_hits[0]] += weight
            for t in THRESHOLDS:
                cnt = sum(1 for hh in ticket_hits if hh >= t)
                if cnt:
                    qual_weighted[t] += cnt * weight
            if ticket_hits.count(mx) == 1:
                unique_max_mass += weight

    # ---- probabilities as exact Fractions ----
    expected_union_hits = Fraction(6 * M, N_UNIVERSE)
    union_hit_dist = [Fraction(union_hit_mass[h], total_mass) for h in range(DRAW_SIZE + 1)]
    max_hit_dist = [Fraction(max_hit_mass[m], total_mass) for m in range(DRAW_SIZE + 1)]
    p_at_least_one = {t: Fraction(sum(max_hit_mass[m] for m in range(t, DRAW_SIZE + 1)), total_mass)
                      for t in THRESHOLDS}
    e_qual = {t: Fraction(qual_weighted[t], total_mass) for t in THRESHOLDS}
    clear_best = Fraction(unique_max_mass, total_mass)
    single_tail_mass = {t: sum(single_ticket_marginal_mass[j] for j in range(t, DRAW_SIZE + 1))
                        for t in THRESHOLDS}

    return {
        "B": B, "geometry": name, "c": c, "u": u, "o": o, "M": M, "redundancy": R,
        "total_mass": total_mass,
        "expected_union_hits": expected_union_hits,
        "union_hit_mass": union_hit_mass,
        "max_hit_mass": max_hit_mass,
        "single_ticket_marginal_mass": single_ticket_marginal_mass,
        "single_tail_mass": single_tail_mass,
        "qual_weighted": qual_weighted,
        "unique_max_mass": unique_max_mass,
        "union_hit_dist": union_hit_dist,
        "max_hit_dist": max_hit_dist,
        "p_at_least_one": p_at_least_one,
        "e_qual": e_qual,
        "clear_best": clear_best,
    }


def validate_cell(cell):
    """Run the 9 frozen invariant checks. Returns (checks_dict, all_pass_bool)."""
    B, M, c, u, R = cell["B"], cell["M"], cell["c"], cell["u"], cell["redundancy"]
    checks = {}

    # 1: total integer mass exactly equals C(49,6)
    checks["total_mass_eq_C49_6"] = (cell["total_mass"] == TOTAL_OUTCOMES)

    # 2: union-hit masses sum to total (probabilities sum to exactly 1)
    checks["union_mass_sums_to_total"] = (sum(cell["union_hit_mass"]) == TOTAL_OUTCOMES)
    checks["union_prob_sums_to_one"] = (sum(cell["union_hit_dist"]) == Fraction(1))

    # 3: union-hit distribution exactly equals Hypergeometric(49, M, 6)
    checks["union_eq_hypergeom_49_M_6"] = all(
        cell["union_hit_mass"][h] == hyp_mass(N_UNIVERSE, M, DRAW_SIZE, h)
        for h in range(DRAW_SIZE + 1)
    )

    # 4: individual ticket marginal exactly equals Hypergeometric(49, 6, 6)
    checks["single_marginal_eq_hypergeom_49_6_6"] = all(
        cell["single_ticket_marginal_mass"][j] == hyp_mass(N_UNIVERSE, DRAW_SIZE, DRAW_SIZE, j)
        for j in range(DRAW_SIZE + 1)
    )

    # 5: max-hit masses sum to total (probabilities sum to exactly 1)
    checks["max_mass_sums_to_total"] = (sum(cell["max_hit_mass"]) == TOTAL_OUTCOMES)
    checks["max_prob_sums_to_one"] = (sum(cell["max_hit_dist"]) == Fraction(1))

    # 6: threshold tail probabilities monotone non-increasing
    pa = cell["p_at_least_one"]
    checks["threshold_monotone"] = (pa[3] >= pa[4] >= pa[5] >= pa[6])

    # 7: E[#tickets>=t] == B * P(single ticket >= t)  (exact, as integer masses)
    checks["expected_qual_eq_B_times_single"] = all(
        cell["qual_weighted"][t] == B * cell["single_tail_mass"][t] for t in THRESHOLDS
    )

    # 8: E[union hits] == 6M/49 exactly (compare to mass-weighted mean)
    mean_from_dist = Fraction(
        sum(h * cell["union_hit_mass"][h] for h in range(DRAW_SIZE + 1)), cell["total_mass"]
    )
    checks["expected_union_hits_eq_6M_over_49"] = (
        cell["expected_union_hits"] == Fraction(6 * M, N_UNIVERSE) == mean_from_dist
    )

    # 9: R == 6B - M == c*(B-1)
    checks["redundancy_consistent"] = (R == 6 * B - M == c * (B - 1))

    return checks, all(checks.values())


def build_canonical(cells_with_checks):
    """Assemble the deterministic canonical result object (JSON-serializable)."""
    cells_out = []
    for cell, checks, ok in cells_with_checks:
        cells_out.append({
            "B": cell["B"],
            "geometry": cell["geometry"],
            "c": cell["c"], "u": cell["u"], "o": cell["o"],
            "M": cell["M"], "redundancy": cell["redundancy"],
            "total_mass": cell["total_mass"],
            "expected_union_hits": frac_obj(cell["expected_union_hits"]),
            "union_hit_mass": cell["union_hit_mass"],
            "union_hit_distribution": [frac_obj(p) for p in cell["union_hit_dist"]],
            "max_hit_mass": cell["max_hit_mass"],
            "max_hit_distribution": [frac_obj(p) for p in cell["max_hit_dist"]],
            "threshold_at_least_one_probability": {str(t): frac_obj(cell["p_at_least_one"][t]) for t in THRESHOLDS},
            "expected_qualifying_ticket_count": {str(t): frac_obj(cell["e_qual"][t]) for t in THRESHOLDS},
            "clear_best_unique_max_probability": frac_obj(cell["clear_best"]),
            "numerical_validation": {k: bool(v) for k, v in checks.items()},
            "numerical_validation_all_pass": bool(ok),
        })
    return {
        "schema": "P295B-independent-exact-ticket-geometry/v1",
        "task_id": "P295B-INDEPENDENT-EXACT-TICKET-GEOMETRY-REPRODUCTION-AUDIT",
        "method": "exact_integer_combinatorial_enumeration_no_db_no_random_no_simulation",
        "universe": {"N": N_UNIVERSE, "draw_size": DRAW_SIZE, "total_outcomes": TOTAL_OUTCOMES},
        "budgets": list(BUDGETS),
        "geometries": [g[0] for g in GEOMETRIES],
        "thresholds": list(THRESHOLDS),
        "decimal_precision_sig_digits": DECIMAL_PREC,
        "cell_count": len(cells_out),
        "cells": cells_out,
        "all_cells_validation_pass": all(ok for _, _, ok in cells_with_checks),
        "nonpredictive_boundary": (
            "Abstract membership labels only; no actual selectable lottery numbers are produced. "
            "Overlap geometry cannot create predictive information about which numbers will be drawn."
        ),
    }


def write_results_csv(path, cells_with_checks):
    cols = ["B", "geometry", "c", "u", "o", "M", "redundancy", "total_mass",
            "expected_union_hits_num", "expected_union_hits_den", "expected_union_hits_decimal"]
    for h in range(DRAW_SIZE + 1):
        cols.append(f"union_mass_h{h}")
    for m in range(DRAW_SIZE + 1):
        cols.append(f"max_mass_m{m}")
    for t in THRESHOLDS:
        cols += [f"P_atleast1_ge{t}_num", f"P_atleast1_ge{t}_den", f"P_atleast1_ge{t}_decimal"]
    for t in THRESHOLDS:
        cols += [f"E_qual_ge{t}_num", f"E_qual_ge{t}_den", f"E_qual_ge{t}_decimal"]
    cols += ["clear_best_num", "clear_best_den", "clear_best_decimal"]

    lines = [",".join(cols)]
    for cell, _checks, _ok in cells_with_checks:
        row = [str(cell["B"]), cell["geometry"], str(cell["c"]), str(cell["u"]), str(cell["o"]),
               str(cell["M"]), str(cell["redundancy"]), str(cell["total_mass"]),
               str(cell["expected_union_hits"].numerator), str(cell["expected_union_hits"].denominator),
               dec_full(cell["expected_union_hits"])]
        row += [str(cell["union_hit_mass"][h]) for h in range(DRAW_SIZE + 1)]
        row += [str(cell["max_hit_mass"][m]) for m in range(DRAW_SIZE + 1)]
        for t in THRESHOLDS:
            p = cell["p_at_least_one"][t]
            row += [str(p.numerator), str(p.denominator), dec_full(p)]
        for t in THRESHOLDS:
            e = cell["e_qual"][t]
            row += [str(e.numerator), str(e.denominator), dec_full(e)]
        row += [str(cell["clear_best"].numerator), str(cell["clear_best"].denominator), dec_full(cell["clear_best"])]
        lines.append(",".join(row))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_threshold_summary_csv(path, cells_with_checks):
    cols = ["B", "geometry", "M", "redundancy",
            "P_atleast1_ge3", "P_atleast1_ge4", "P_atleast1_ge5", "P_atleast1_ge6",
            "E_qual_ge3", "E_qual_ge4", "E_qual_ge5", "E_qual_ge6",
            "clear_best_unique_max", "threshold_monotone_pass"]
    lines = [",".join(cols)]
    for cell, checks, _ok in cells_with_checks:
        row = [str(cell["B"]), cell["geometry"], str(cell["M"]), str(cell["redundancy"])]
        row += [dec_round(cell["p_at_least_one"][t]) for t in THRESHOLDS]
        row += [dec_round(cell["e_qual"][t]) for t in THRESHOLDS]
        row += [dec_round(cell["clear_best"]), str(bool(checks["threshold_monotone"]))]
        lines.append(",".join(row))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_validation_md(path, cells_with_checks):
    check_order = [
        "total_mass_eq_C49_6", "union_mass_sums_to_total", "union_prob_sums_to_one",
        "union_eq_hypergeom_49_M_6", "single_marginal_eq_hypergeom_49_6_6",
        "max_mass_sums_to_total", "max_prob_sums_to_one", "threshold_monotone",
        "expected_qual_eq_B_times_single", "expected_union_hits_eq_6M_over_49",
        "redundancy_consistent",
    ]
    out = []
    out.append("# INDEPENDENT NUMERICAL VALIDATION — P295B")
    out.append("")
    out.append(f"Total equally likely draw outcomes C(49,6) = {TOTAL_OUTCOMES}.")
    out.append("All arithmetic is exact (Python int / fractions.Fraction); no float, no randomness,")
    out.append("no simulation, no DB. Each of the 12 cells is checked against the 11 frozen invariants.")
    out.append("")
    out.append("| B | geometry | M | R | " + " | ".join(check_order) + " | ALL |")
    out.append("|" + "---|" * (5 + len(check_order) + 1))
    all_pass = True
    for cell, checks, ok in cells_with_checks:
        all_pass = all_pass and ok
        marks = ["PASS" if checks[k] else "FAIL" for k in check_order]
        out.append(f"| {cell['B']} | {cell['geometry']} | {cell['M']} | {cell['redundancy']} | "
                   + " | ".join(marks) + f" | {'PASS' if ok else 'FAIL'} |")
    out.append("")
    out.append(f"**Cells checked:** {len(cells_with_checks)}")
    out.append(f"**Invariants per cell:** {len(check_order)}")
    out.append(f"**Overall:** {'ALL_PASS' if all_pass else 'FAILURE'}")
    out.append("")
    out.append("Invariant legend:")
    out.append("- `total_mass_eq_C49_6`: exact integer mass == C(49,6)")
    out.append("- `union_mass_sums_to_total` / `union_prob_sums_to_one`: union-hit distribution normalized")
    out.append("- `union_eq_hypergeom_49_M_6`: union-hit distribution == Hypergeometric(49, M, 6)")
    out.append("- `single_marginal_eq_hypergeom_49_6_6`: each ticket marginal == Hypergeometric(49, 6, 6)")
    out.append("- `max_mass_sums_to_total` / `max_prob_sums_to_one`: max-hit distribution normalized")
    out.append("- `threshold_monotone`: P(max>=3) >= P(max>=4) >= P(max>=5) >= P(max>=6)")
    out.append("- `expected_qual_eq_B_times_single`: E[#tickets>=t] == B * P(single ticket >= t)")
    out.append("- `expected_union_hits_eq_6M_over_49`: E[union hits] == 6M/49 (exact)")
    out.append("- `redundancy_consistent`: R == 6B - M == c*(B-1)")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser(description="P295B independent exact ticket-geometry engine")
    ap.add_argument("--out", required=True, help="output directory (must be under the P295B evidence root)")
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    cells_with_checks = []
    for B in BUDGETS:
        for name, c, u in GEOMETRIES:
            cell = analyze_cell(B, name, c, u)
            checks, ok = validate_cell(cell)
            cells_with_checks.append((cell, checks, ok))

    # Fail loud BEFORE writing any accepted output if any invariant fails.
    failed = [(cell["B"], cell["geometry"], k)
              for cell, checks, ok in cells_with_checks if not ok
              for k, v in checks.items() if not v]
    if failed:
        sys.stderr.write("P295B_STOPPED_NUMERICAL_VALIDATION_FAILURE: " + repr(failed) + "\n")
        sys.exit(1)

    canonical = build_canonical(cells_with_checks)
    canonical_json = json.dumps(canonical, sort_keys=True, indent=2, ensure_ascii=True)
    canonical_bytes = (canonical_json + "\n").encode("utf-8")

    write_results_csv(os.path.join(out_dir, "EXACT_GEOMETRY_RESULTS.csv"), cells_with_checks)
    write_threshold_summary_csv(os.path.join(out_dir, "GEOMETRY_THRESHOLD_SUMMARY.csv"), cells_with_checks)
    write_validation_md(os.path.join(out_dir, "NUMERICAL_VALIDATION.md"), cells_with_checks)
    with open(os.path.join(out_dir, "CANONICAL_RESULT.json"), "wb") as fh:
        fh.write(canonical_bytes)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    with open(os.path.join(out_dir, "CANONICAL_RESULT.sha256"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{digest}  CANONICAL_RESULT.json\n")

    # stdout summary only (not part of byte-compared evidence)
    sys.stdout.write(f"P295B engine OK: {len(cells_with_checks)} cells validated; "
                     f"CANONICAL_RESULT.sha256={digest}\n")


if __name__ == "__main__":
    main()
