# P269D: Calendar Regime H1 Null Closeout

**Date:** 2026-06-11 Asia/Taipei
**Classification:** `P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_COMPLETE`
**Task Type:** Type E — governance closeout artifact (no statistical test, no DB write, no registry write)
**Status:** Closeout only. No H1 test run in P269D. No statistical computation. No Hypothesis Registry write. No strategy. No betting advice.

**No-Claim Statement:** This artifact does not improve win rate, does not predict lottery numbers, does not authorize betting advice, and does not constitute a strategy recommendation. It is a governance closeout record only.

---

## Closeout Verdict

> **`CALENDAR_REGIME_DIAGNOSTICS_ONLY_NULL_CLOSURE`**

The P269 calendar regime arc is permanently closed. C05 (Saturday vs Mon-Fri) failed the pre-registered primary H1 gate with p=0.8526 >> alpha=0.01. Per the P269B single-shot stop rule, C06 is also closed for this arc.

---

## 0. Inherited Boundaries

### P268 Draw-Order: ALREADY_NULL
- P268D4 H1 PRIMARY_FAIL: DAILY_539 p=0.3051 >= alpha=0.01
- H2, H3: NOT AUTHORIZED. Draw-order (drawNumberAppear) arc permanently closed.
- PR #412, commit `ee4a306`

### P269A-Lite: NO_GO
- 9 external signal families evaluated from repo-only evidence
- Top candidate recommendation: **NO_GO**
- WATCHLIST only: C05 and C06 — both **LOW plausibility**
- PR #413, commit `85b09c2`

### P269B: READY_FOR_REGISTRY (Design only)
- Pre-registration design for C05 primary H1 with LOW plausibility caveats
- Declared single-shot test; if null → permanent closure
- PR #414, commit `71d03b2`

### P269C: H1_PRIMARY_FAIL
- Registry entry `HR-P269C-H1-DAILY539-SATURDAY-M3PLUS-001` appended BEFORE any data look
- PR #415, commit `e2c2798`

---

## 1. P269C H1 Result

| Parameter | Value |
|---|---|
| Primary game | DAILY_539 |
| Strategy | `acb_markov_midfreq_3bet` |
| OOS window | Last 1,765 eligible draws |
| Evaluable (OOS ∩ replay coverage) | **1,494 draws** |
| Saturday N | **249** |
| Mon-Fri N | **1,245** |
| Permutations / seed | 10,000 / 42 |
| **Saturday M3+ events** | **8 / 249 = 3.21%** |
| **Mon-Fri M3+ events** | **44 / 1,245 = 3.53%** |
| Rate difference (Sat − Mon-Fri) | **−0.32pp** |
| **p-value (two-tailed)** | **0.8526** |
| Alpha | 0.01 |
| Fisher backup | Not triggered (Saturday events = 8 ≥ 5) |
| **H1 Classification** | **H1_PRIMARY_FAIL** |
| C06 run | NOT_RUN |
| Scans performed | NONE |

---

## 2. Closed Candidates

### C05: Saturday vs Mon-Fri — **CLOSED**
- H1_PRIMARY_FAIL: p=0.8526 >> alpha=0.01
- Saturday rate (3.21%) slightly **lower** than Mon-Fri (3.53%)
- Direction is slightly negative; magnitude trivially small
- Clean null consistent with L82 DAILY_539 signal space exhaustion
- No re-test authorized under this pre-registration

### C06: Calendar Gap ≥ 2 Days — **NOT_RUN_CLOSED_FOR_THIS_ARC**
- C06 was declared secondary in P269B design
- C06 was NOT simultaneously declared in the P269C registry entry
- Per P269B stop rule: "C06 (if declared) is permanently CLOSED" — and since it was not declared, it cannot be salvaged post-hoc
- Permanently closed for this arc

---

## 3. Stop Rule Applied

From P269B design Section 12:

> "IF OOS primary gate p >= alpha_corrected: the test is COMPLETE and the result is NULL. C05 is permanently CLOSED. C06 (if declared) is permanently CLOSED. No re-testing with modified regime boundaries, metrics, or strategies is authorized under this pre-registration."

**Triggered:** p=0.8526 >> alpha=0.01. Calendar regime arc permanently closed.

---

## 4. Why No Signal (Consistent With Prior Lessons)

- **L82**: DAILY_539 H001–H008 all REJECT — signal space exhausted across 5885 draws
- **L103**: H009 Lag-1 neighbor p=0.840 — even structurally plausible hypotheses fail
- **L104/L105**: Digit tail and consecutive patterns — null in 539
- **P267C**: 0/36 cells pass Bonferroni under M3+ SSOT metric
- **Causal**: Lottery RNG is independent of calendar labels. No mechanism exists for day-of-week to affect ball draw outcomes.

**Power note:** OOS Saturday N=249 can only detect very large effects (Saturday rate ≥ ~5%, approximately 2.5× baseline). A null result proves "no large effect" — not "no effect whatsoever." However, per the single-shot stop rule, no re-test is authorized.

---

## 5. Future Reopen Rule

**No re-test of C05/C06 calendar regime is authorized under this pre-registration.**

Future research would require:
1. A genuinely new external signal source beyond repo-only evidence (e.g., confirmed structural draw-day difference from Taiwan Lottery official data)
2. A fresh pre-registration with a new hypothesis ID
3. User authorization

**Forbidden post-hoc adjustments:**
- Modified regime boundaries (individual weekday, weekend vs weekday, etc.)
- Modified metrics (M2+, M1+)
- Modified strategy after seeing C05 null
- Modified OOS window
- C06 as post-hoc salvage under this arc

---

## 6. Arc Summary

| Task | Status | PR |
|---|---|---|
| P269A-Lite | NO_GO scouting complete | PR #413 |
| P269B | Pre-registration design READY_FOR_REGISTRY | PR #414 |
| P269C | Formal H1 test — H1_PRIMARY_FAIL (p=0.8526) | PR #415 |
| **P269D** | **Null closeout — CALENDAR_REGIME_DIAGNOSTICS_ONLY_NULL_CLOSURE** | *(this PR)* |

---

## 7. Recommended Next Step

**HOLD** — per L137, no further active signal mining is authorized until the P245B bias gate opens or a genuinely new external data source appears. Mining within the current repo-only evidence boundary is equivalent to p-hacking.

---

## 8. Final Classification

`P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_COMPLETE`

This artifact does not improve win rate, does not predict lottery numbers, does not authorize betting advice, and does not constitute a strategy recommendation.
