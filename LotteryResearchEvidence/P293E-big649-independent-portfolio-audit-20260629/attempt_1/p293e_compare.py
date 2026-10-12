#!/usr/bin/env python3
"""P293E post-compute comparator (stdlib-only, DB-free).

Run ONLY after the independent two-run output is complete and hashed. Reads the P293D result artifacts
(read-only) and the P293E run1 artifacts and compares them field-by-field. Also independently recomputes
the hypergeometric references and verifies the outcome-blind tie-break from the recorded audit-sample
tickets. Writes nothing except COMPARISON_RESULTS.json under the P293E evidence root; prints a full report.
Does not import or execute any engine.
"""
import csv
import itertools
import json
import math
import os
import sys

MINE = "/Users/kelvin/LotteryResearchEvidence/P293E-big649-independent-portfolio-audit-20260629/attempt_1"
P293D = "/Users/kelvin/LotteryResearchEvidence/P293D-big649-fixed-budget-diversity-20260629/attempt_1"
TOL = 1e-9
C49_6 = math.comb(49, 6)
SEGMENTS = ["ALL", "LATEST_750", "LATEST_300", "LATEST_50", "BLOCK_1", "BLOCK_2", "BLOCK_3", "BLOCK_4"]
BUDGETS = [2, 3, 4]
STRAT_ORDER = ["freq_50", "freq_300", "freq_750", "prior_draw",
               "exp_recency_50", "exp_recency_300", "exp_recency_750"]


def rd(path):
    with open(path, newline="") as fh:
        return list(csv.reader(fh))


def hyperg_pmf(K, n=6, N=49):
    out = []
    for k in range(7):
        if k > K or (n - k) > (N - K):
            out.append(0.0)
        else:
            out.append(math.comb(K, k) * math.comb(N - K, n - k) / C49_6)
    return out


def close(a, b, tol=TOL):
    return abs(float(a) - float(b)) <= tol


report = []
def log(s=""):
    report.append(s)
    print(s)


results = {}

# ---------------------------------------------------------------- (A) rowwise 4110 ---------------
log("=" * 78)
log("(A) ROWWISE RESULT-TABLE COMPARISON (4110 rows)")
log("=" * 78)
pmat = rd(os.path.join(P293D, "FIXED_BUDGET_PORTFOLIO_RESULT_TABLE.csv"))
mmat = rd(os.path.join(MINE, "run1", "PORTFOLIO_RESULT_TABLE.csv"))
ph, pr = pmat[0], pmat[1:]
mh, mr = mmat[0], mmat[1:]
# P293D cols: target_index,target_draw,budget_B,selected_subset,union_size_M,redundancy,total_pairwise_overlap,union_hits
P = {(int(r[0]), int(r[2])): r for r in pr}
# mine: target_index,draw_id,budget,subset_indices,subset_names,union_size,redundancy,pairwise_overlap,union_hits,ref_a,ref_b
M = {(int(r[0]), int(r[2])): r for r in mr}
log("P293D header: " + ",".join(ph))
log("P293E header: " + ",".join(mh))
log("P293D rows=%d  P293E rows=%d" % (len(pr), len(mr)))
keys = sorted(set(P) | set(M))
total = matched = 0
mismatches = []
field_checks = ["target_draw", "selected_subset(ordered)", "union_size_M", "redundancy",
                "total_pairwise_overlap", "union_hits"]
for k in keys:
    total += 1
    if k not in P or k not in M:
        mismatches.append((k, "row_presence", str(k in P), str(k in M)))
        continue
    p, m = P[k], M[k]
    p_subset = p[3].split("+")
    m_subset = m[4].split("|")
    row_ok = True
    for field, pv, mv in [
        ("target_draw", int(p[1]), int(m[1])),
        ("selected_subset(ordered)", p_subset, m_subset),
        ("union_size_M", int(p[4]), int(m[5])),
        ("redundancy", int(p[5]), int(m[6])),
        ("total_pairwise_overlap", int(p[6]), int(m[7])),
        ("union_hits", int(p[7]), int(m[8])),
    ]:
        if pv != mv:
            row_ok = False
            if len(mismatches) < 25:
                mismatches.append((k, field, str(pv), str(mv)))
    if row_ok:
        matched += 1
log("fields compared per row: " + ", ".join(field_checks))
log("TOTAL=%d  MATCHED=%d  MISMATCHED=%d" % (total, matched, total - matched))
if mismatches:
    log("FIRST MISMATCHES (up to 25):")
    for mm in mismatches[:25]:
        log("  target/B=%s field=%s P293D=%s P293E=%s" % mm)
else:
    log("FIRST MISMATCH: NONE")
results["rowwise"] = {"total": total, "matched": matched, "mismatched": total - matched,
                      "first_mismatch": (None if not mismatches else
                                         {"key": list(mismatches[0][0]), "field": mismatches[0][1],
                                          "p293d": mismatches[0][2], "p293e": mismatches[0][3]})}

# ---------------------------------------------------------------- (B) selection frequency --------
log("")
log("=" * 78)
log("(B) SELECTION-FREQUENCY COMPARISON (per budget x segment x subset)")
log("=" * 78)
pf = rd(os.path.join(P293D, "PORTFOLIO_SELECTION_FREQUENCY.csv"))[1:]
mf = rd(os.path.join(MINE, "run1", "PORTFOLIO_SELECTION_FREQUENCY.csv"))[1:]
# P293D: budget_B,segment,selected_subset,count,fraction
PF = {(int(r[0]), r[1], tuple(sorted(r[2].split("+")))): (int(r[3]), float(r[4])) for r in pf}
# mine: budget,segment,subset_indices,subset_names,count,fraction
MF = {(int(r[0]), r[1], tuple(sorted(r[3].split("|")))): (int(r[4]), float(r[5])) for r in mf}
fkeys = sorted(set(PF) | set(MF), key=lambda x: (x[0], SEGMENTS.index(x[1]) if x[1] in SEGMENTS else 9, x[2]))
ftotal = fmatched = 0
fmm = []
for k in fkeys:
    ftotal += 1
    if k not in PF or k not in MF:
        fmm.append((k, "presence", k in PF, k in MF)); continue
    pc, pfr = PF[k]; mc, mfr = MF[k]
    if pc == mc and close(pfr, mfr):
        fmatched += 1
    else:
        fmm.append((k, "count/frac", (pc, pfr), (mc, mfr)))
log("entries: P293D=%d  P293E=%d  union=%d" % (len(PF), len(MF), ftotal))
log("MATCHED=%d  MISMATCHED=%d" % (fmatched, ftotal - fmatched))
for mm in fmm[:15]:
    log("  MISMATCH " + str(mm))
if not fmm:
    log("FIRST MISMATCH: NONE")
results["selection_frequency"] = {"total": ftotal, "matched": fmatched, "mismatched": ftotal - fmatched}

# ---------------------------------------------------------------- (C) overlap matrix -------------
log("")
log("=" * 78)
log("(C) SEVEN-TICKET OVERLAP MATRIX (21 pairs: mean_overlap, mean_jaccard)")
log("=" * 78)
pov = rd(os.path.join(P293D, "SEVEN_TICKET_OVERLAP_MATRIX.csv"))[1:]
POV = {(r[0], r[1]): (float(r[2]), float(r[3])) for r in pov}
mres = json.load(open(os.path.join(MINE, "run1", "RESULTS.json")))
MOV = {(p["name_i"], p["name_j"]): (p["mean_overlap"], p["mean_jaccard"]) for p in mres["strategy_pairs"]}
ov_total = ov_match = 0
ov_maxdiff = 0.0
ovmm = []
for k in sorted(set(POV) | set(MOV)):
    ov_total += 1
    if k not in POV or k not in MOV:
        ovmm.append((k, "presence")); continue
    (po, pj), (mo, mj) = POV[k], MOV[k]
    d = max(abs(po - mo), abs(pj - mj))
    ov_maxdiff = max(ov_maxdiff, d)
    if d <= TOL:
        ov_match += 1
    else:
        ovmm.append((k, po, mo, pj, mj))
log("pairs=%d  MATCHED=%d  MISMATCHED=%d  max_abs_diff=%.3e" % (ov_total, ov_match, ov_total - ov_match, ov_maxdiff))
for mm in ovmm[:10]:
    log("  MISMATCH " + str(mm))
if not ovmm:
    log("FIRST MISMATCH: NONE")
results["overlap_matrix"] = {"pairs": ov_total, "matched": ov_match, "max_abs_diff": ov_maxdiff}

# ---------------------------------------------------------------- (D) segment aggregates ---------
log("")
log("=" * 78)
log("(D) SEGMENT AGGREGATE COMPARISON (portfolio_summary, per B x segment)")
log("=" * 78)
dp = json.load(open(os.path.join(P293D, "RESULTS.json")))
ps_all = dp["portfolio_summary"]
ms_by = {(s["B"], s["segment"]): s for s in mres["segment_summary"]}
seg_total = seg_match = 0
seg_maxdiff = 0.0
segmm = []
scalar_map = [
    ("mean_union_hits", "mean_union_hits"),
    ("mean_union_size_M", "mean_union_size"),
    ("mean_redundancy", "mean_redundancy"),
    ("mean_pairwise_overlap", "mean_pairwise_overlap"),
    ("ref_a_conditioned_mean", "ref_a_cond_mean"),
    ("ref_b_diversified_mean", "ref_b_div_mean"),
    ("delta_vs_ref_a", "delta_vs_ref_a"),
    ("delta_vs_ref_b", "delta_vs_ref_b"),
]
for B in BUDGETS:
    for seg in SEGMENTS:
        seg_total += 1
        pseg = ps_all[str(B)][seg]
        mseg = ms_by[(B, seg)]
        ok = True
        if pseg["n_targets"] != mseg["n_targets"]:
            ok = False; segmm.append((B, seg, "n_targets", pseg["n_targets"], mseg["n_targets"]))
        for pk, mk in scalar_map:
            d = abs(float(pseg[pk]) - float(mseg[mk]))
            seg_maxdiff = max(seg_maxdiff, d)
            if d > TOL:
                ok = False; segmm.append((B, seg, pk, pseg[pk], mseg[mk]))
        if pseg["union_hit_distribution_0to6"] != mseg["hits_dist"]:
            ok = False; segmm.append((B, seg, "union_hit_distribution", pseg["union_hit_distribution_0to6"], mseg["hits_dist"]))
        for k in range(7):
            d = abs(pseg["ref_a_conditioned_dist_0to6"][k] - mseg["ref_a_dist"][k])
            seg_maxdiff = max(seg_maxdiff, d)
            if d > TOL:
                ok = False; segmm.append((B, seg, "ref_a_dist[%d]" % k, pseg["ref_a_conditioned_dist_0to6"][k], mseg["ref_a_dist"][k]))
            d = abs(pseg["ref_b_diversified_dist_0to6"][k] - mseg["ref_b_dist"][k])
            seg_maxdiff = max(seg_maxdiff, d)
            if d > TOL:
                ok = False; segmm.append((B, seg, "ref_b_dist[%d]" % k, pseg["ref_b_diversified_dist_0to6"][k], mseg["ref_b_dist"][k]))
        if ok:
            seg_match += 1
log("cells (B x segment)=%d  MATCHED=%d  MISMATCHED=%d  max_abs_diff=%.3e" %
    (seg_total, seg_match, seg_total - seg_match, seg_maxdiff))
for mm in segmm[:20]:
    log("  MISMATCH " + str(mm))
if not segmm:
    log("FIRST MISMATCH: NONE")
results["segment_aggregates"] = {"cells": seg_total, "matched": seg_match, "max_abs_diff": seg_maxdiff}

# ---------------------------------------------------------------- (E) duplication / seven --------
log("")
log("=" * 78)
log("(E) DUPLICATION-REDUCTION (per B) + SEVEN-TICKET mean-unique")
log("=" * 78)
dr = dp["duplication_reduction"]
mpb = {pb["B"]: pb for pb in mres["per_budget"]}
dup_max = 0.0
dupmm = []
for B in BUDGETS:
    p = dr[str(B)]; m = mpb[B]
    for pk, mk in [("mean_union_size_M", "mean_M"), ("mean_redundancy", "mean_redundancy"),
                   ("unique_slot_fraction", "unique_slot_fraction")]:
        d = abs(float(p[pk]) - float(m[mk])); dup_max = max(dup_max, d)
        if d > TOL:
            dupmm.append((B, pk, p[pk], m[mk]))
    log("  B=%d M: P=%.10f E=%.10f | redund P=%.10f E=%.10f | uniqfrac P=%.10f E=%.10f" %
        (B, p["mean_union_size_M"], m["mean_M"], p["mean_redundancy"], m["mean_redundancy"],
         p["unique_slot_fraction"], m["unique_slot_fraction"]))
pmu = dp["seven_ticket"]["mean_unique_numbers_across_seven"]
mmu = mres["mean_unique_seven"]
dup_max = max(dup_max, abs(pmu - mmu))
log("  mean_unique_across_seven: P293D=%.12f  P293E=%.12f  diff=%.3e" % (pmu, mmu, abs(pmu - mmu)))
log("  duplication/seven max_abs_diff=%.3e  mismatches=%d" % (dup_max, len(dupmm)))
for mm in dupmm:
    log("  MISMATCH " + str(mm))
results["duplication_seven"] = {"max_abs_diff": dup_max, "mismatches": len(dupmm)}

# ---------------------------------------------------------------- (F) independent hyperg recompute
log("")
log("=" * 78)
log("(F) INDEPENDENT HYPERGEOMETRIC REFERENCE RECOMPUTATION (vs P293D and P293E)")
log("=" * 78)
# recompute per-target M from the P293D result table, segment ALL, and rebuild ref_a mean+dist
M_by_Bseg = {}
for r in pr:
    M_by_Bseg.setdefault((int(r[2]),), []).append((int(r[0]), int(r[4])))
ref_max = 0.0
for B in BUDGETS:
    Ms = [m for (_t, m) in M_by_Bseg[(B,)]]
    ref_a_mean = sum(6 * m / 49 for m in Ms) / len(Ms)
    dist = [0.0] * 7
    for m in Ms:
        pm = hyperg_pmf(m)
        for k in range(7):
            dist[k] += pm[k]
    dist = [v / len(Ms) for v in dist]
    ref_b_mean = 36 * B / 49
    ref_b_dist = hyperg_pmf(6 * B)
    p_a = ps_all[str(B)]["ALL"]["ref_a_conditioned_mean"]
    p_b = ps_all[str(B)]["ALL"]["ref_b_diversified_mean"]
    da = abs(ref_a_mean - p_a); db = abs(ref_b_mean - p_b)
    ref_max = max(ref_max, da, db)
    log("  B=%d ALL: recompute ref_a_mean=%.12f (P293D=%.12f d=%.2e) ref_b_mean=%.12f (P293D=%.12f d=%.2e)" %
        (B, ref_a_mean, p_a, da, ref_b_mean, p_b, db))
    for k in range(7):
        ref_max = max(ref_max, abs(dist[k] - ps_all[str(B)]["ALL"]["ref_a_conditioned_dist_0to6"][k]))
        ref_max = max(ref_max, abs(ref_b_dist[k] - ps_all[str(B)]["ALL"]["ref_b_diversified_dist_0to6"][k]))
log("  independent-reference max_abs_diff vs P293D = %.3e (C(49,6)=%d)" % (ref_max, C49_6))
results["independent_reference"] = {"max_abs_diff_vs_p293d": ref_max, "C49_6": C49_6}

# ---------------------------------------------------------------- (G) tie-break audit ------------
log("")
log("=" * 78)
log("(G) OUTCOME-BLIND TIE-BREAK AUDIT (re-derived from recorded audit-sample tickets)")
log("=" * 78)
tb_ok = True
for samp in mres["audit_samples"]:
    t = samp["t"]
    tickets = [None] * 7
    for s in samp["strategies"]:
        tickets[s["idx"]] = set(s["ticket"])
    for B in BUDGETS:
        best = None
        for subset in itertools.combinations(range(7), B):
            uni = set()
            for i in subset:
                uni |= tickets[i]
            Mu = len(uni)
            ov = 0
            for a in range(len(subset)):
                for b in range(a + 1, len(subset)):
                    ov += len(tickets[subset[a]] & tickets[subset[b]])
            key = (-Mu, ov)
            if best is None or key < best[0]:
                best = (key, subset, Mu, ov)
        sel_names = [STRAT_ORDER[i] for i in best[1]]
        rec = samp["selections_outcome_blind"][str(B)]["subset_names"]
        recM = samp["selections_outcome_blind"][str(B)]["M"]
        recov = samp["selections_outcome_blind"][str(B)]["overlap"]
        ok = (sel_names == rec and best[2] == recM and best[3] == recov)
        tb_ok = tb_ok and ok
        log("  t=%d B=%d derived=%s (M=%d ov=%d) recorded=%s (M=%d ov=%d) %s" %
            (t, B, "+".join(sel_names), best[2], best[3], "+".join(rec), recM, recov, "OK" if ok else "MISMATCH"))
log("  tie-break re-derivation matches recorded selection: %s" % tb_ok)
results["tiebreak_audit"] = {"all_match": tb_ok}

# ---------------------------------------------------------------- (H) audit-sample cross-compare --
log("")
log("=" * 78)
log("(H) AUDIT-SAMPLE CROSS-COMPARISON vs P293D (tickets, windows, outcome, selections, hits)")
log("=" * 78)
pa = dp["audit_samples"]
pos_map = {750: "first", 1435: "middle", 2119: "last"}
aud_ok = True
audmm = []
for samp in mres["audit_samples"]:
    t = samp["t"]
    pp = pa[pos_map[t]]
    if pp["target_index"] != t:
        aud_ok = False; audmm.append((t, "target_index", pp["target_index"], t))
    if int(pp["target_draw"]) != samp["outcome_revealed_after_selection"]["draw_id"]:
        aud_ok = False; audmm.append((t, "target_draw", pp["target_draw"], samp["outcome_revealed_after_selection"]["draw_id"]))
    if list(pp["target_main_sorted_REVEALED_AFTER_SELECTION"]) != list(samp["outcome_revealed_after_selection"]["main_numbers"]):
        aud_ok = False; audmm.append((t, "revealed_main", pp["target_main_sorted_REVEALED_AFTER_SELECTION"], samp["outcome_revealed_after_selection"]["main_numbers"]))
    for s in samp["strategies"]:
        nm = s["name"]; pst = pp["strategies"][nm]
        if list(pst["ticket_sorted"]) != list(s["ticket"]):
            aud_ok = False; audmm.append((t, nm + ".ticket", pst["ticket_sorted"], s["ticket"]))
        if pst["window_pos_start"] != s["window_start_pos"] or pst["window_pos_end"] != s["window_end_pos"]:
            aud_ok = False; audmm.append((t, nm + ".window_pos", (pst["window_pos_start"], pst["window_pos_end"]), (s["window_start_pos"], s["window_end_pos"])))
        if int(pst["window_draw_start"]) != s["window_start_id"] or int(pst["window_draw_end"]) != s["window_end_id"]:
            aud_ok = False; audmm.append((t, nm + ".window_draw", (pst["window_draw_start"], pst["window_draw_end"]), (s["window_start_id"], s["window_end_id"])))
    for B in BUDGETS:
        pbp = pp["portfolios"][str(B)]
        msel = samp["selections_outcome_blind"][str(B)]
        if pbp["selected_subset"].split("+") != msel["subset_names"]:
            aud_ok = False; audmm.append((t, "B%d.subset" % B, pbp["selected_subset"], msel["subset_names"]))
        if pbp["union_size_M_pre_outcome"] != msel["M"] or pbp["pairwise_overlap_pre_outcome"] != msel["overlap"]:
            aud_ok = False; audmm.append((t, "B%d.M/ov" % B, (pbp["union_size_M_pre_outcome"], pbp["pairwise_overlap_pre_outcome"]), (msel["M"], msel["overlap"])))
        if pbp["union_hits_post_outcome"] != samp["union_hits"][str(B)]:
            aud_ok = False; audmm.append((t, "B%d.hits" % B, pbp["union_hits_post_outcome"], samp["union_hits"][str(B)]))
log("  audit-sample full match (first/middle/last): %s  mismatches=%d" % (aud_ok, len(audmm)))
for mm in audmm[:20]:
    log("  MISMATCH " + str(mm))
results["audit_samples"] = {"all_match": aud_ok, "mismatches": len(audmm)}

# ---------------------------------------------------------------- verdict ------------------------
log("")
log("=" * 78)
overall = (results["rowwise"]["mismatched"] == 0 and results["selection_frequency"]["mismatched"] == 0
           and results["overlap_matrix"]["matched"] == results["overlap_matrix"]["pairs"]
           and results["segment_aggregates"]["matched"] == results["segment_aggregates"]["cells"]
           and results["duplication_seven"]["mismatches"] == 0
           and results["tiebreak_audit"]["all_match"] and results["audit_samples"]["all_match"])
results["OVERALL_REPRODUCED"] = overall
log("OVERALL P293D REPRODUCED (descriptive-only): %s" % overall)
log("=" * 78)

with open(os.path.join(MINE, "COMPARISON_RESULTS.json"), "w") as fh:
    json.dump(results, fh, sort_keys=True, indent=2)
