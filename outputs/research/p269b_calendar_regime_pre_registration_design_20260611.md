# P269B: Calendar Regime Pre-Registration Design

**Date:** 2026-06-11 Asia/Taipei
**Classification:** `P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_COMPLETE_READY_FOR_REGISTRY`
**Task Type:** Type B read-only pre-registration design artifact (no statistical test, no DB write, no registry write)
**Status:** Design only. No H1 test run. No Hypothesis Registry write. No strategy. No betting advice.

**No-Claim Statement:** This artifact does not improve win rate, does not predict lottery numbers, does not authorize betting advice, and does not constitute a strategy recommendation. No statistical test has been run.

---

## 0. Inherited Boundaries

### P268D4 Closure (CLOSED)

The draw-order (`drawNumberAppear`) arc is permanently closed:
- H1 PRIMARY_FAIL: DAILY_539 p=0.3051 >= alpha=0.01
- H1_holdout, H2, H3: NOT AUTHORIZED
- No re-parameterization of draw-order / exit-rank-heterogeneity is authorized

### P269A-Lite NO_GO Boundary

P269A-Lite (PR #413 merged 2026-06-11, HEAD 85b09c2):
- 9 external signal families evaluated from repo-only evidence
- Top candidate recommendation: **NO_GO**
- No high-plausibility hit-rate external signal found
- WATCHLIST only: **C05** (weekday regime) and **C06** (calendar gap) — both LOW plausibility

---

## 1. Low Plausibility Warning

**This is a LOW-plausibility WATCHLIST pathway.** P269A-Lite's top recommendation was NO_GO.

P269B proceeds because the user explicitly accepted the WATCHLIST path. This is not a high-confidence research direction.

**Honest prior:** Lottery ball draws are random. Weekday identity does not causally affect the physical RNG. A Saturday vs weekday effect would require a structural confound (e.g., different ball sets on Saturdays) — no evidence exists for this. **Expected result: null**, consistent with L82 (DAILY_539 signal space exhausted, H001-H008 all REJECT).

This must be treated as a **single-shot test**. If H1 is null in P269C, C05 and C06 are permanently CLOSED.

---

## 2. Candidate Scope

| ID | Signal Family | Status |
|---|---|---|
| **C05** | Draw weekday / schedule regime | **PRIMARY** |
| **C06** | Calendar gap / days_since_last_draw | **SECONDARY** (conditional) |
| C01 | draw-order (P268D4) | ALREADY_NULL — excluded |
| C02-C04, C09 | sales / jackpot / winner-count | EV_ONLY — excluded |
| C07-C08 | machine era / abnormal draw | DATA_UNAVAILABLE — excluded |

### Why C05 and C06 are Different Draw Subsets

- **C05 (Saturday):** Tests draws that fall on Saturday (gap=1 from previous Friday draw)
- **C06 (gap >= 2 days):** Tests draws following a >= 2-day calendar gap — primarily Monday draws (gap=2 from Saturday) and post-holiday draws

These subsets do NOT overlap for the same draw. No double-counting.

---

## 3. Primary Game Selection: DAILY_539 Only

| Lottery | Weekday Distribution | Verdict |
|---|---|---|
| **DAILY_539** | Mon(1015)/Tue(1015)/Wed(1015)/Thu(1014)/Fri(1014)/**Sat(806)**/Sun(6) | **PRIMARY** |
| POWER_LOTTO | Mon(959)/Thu(959) only | EXCLUDED — no Saturday, symmetric biweekly gap |
| BIG_LOTTO | Tue/Fri biweekly | EXCLUDED — L90/L91 CLOSED (fair random) |

DAILY_539 Saturday (806 draws) provides a natural, pre-identified regime boundary. P213 H_REGIME_SEGMENTATION explicitly flagged DAILY_539 + POWER_LOTTO as valid design scope — this design selects DAILY_539 only.

---

## 4. Proposed H1

**H1 statement:** In DAILY_539, the M3+ hit rate of [strategy to be named in P269C registry entry] differs significantly between Saturday draws and weekday draws (Mon-Fri), measured in the OOS temporal window (last 30% of draws).

| Parameter | Value |
|---|---|
| Lottery | DAILY_539 |
| Regime boundary | Saturday (day_of_week=6) vs Mon-Fri (day_of_week=1-5) |
| Metric | M3+ hit rate (any-bet draw-level; special_hit excluded; P265A SSOT) |
| Direction | Two-tailed |
| Alpha | 0.01 |
| Bonferroni k | 1 (C05 only) or 2 (C05+C06 if declared simultaneously) |
| Strategy | TO BE DECLARED in P269C registry entry before data look |
| Null model | Permutation T=10,000, seed=42 (regime label shuffle) |
| OOS split | Temporal 70/30, cutoff to be locked in registry before data look |
| Excluded | Sunday draws (~6), NULL date rows, first draw in DB |

**Status:** NOT REGISTERED. Requires P269C to append to `lottery_api/data/hypothesis_registry.jsonl` before any test is run.

---

## 5. OOS Split Design

- **IS window** (~70%, first ~4120 draws): directional consistency check only — NOT the primary gate
- **OOS window** (~30%, last ~1765 draws): PRIMARY ENDPOINT
  - OOS Saturday: ~242 draws
  - OOS Weekday: ~1524 draws

The exact IS/OOS cutoff draw number must be **locked in the registry entry before any per-regime statistics are computed**.

---

## 6. Statistical Method

**Primary:** Two-tailed permutation test on OOS window
1. Compute observed M3+ rate difference: Saturday mean minus Weekday mean
2. Shuffle regime labels T=10,000 times (preserving Saturday/weekday counts), seed=42
3. p-value = fraction of |permuted differences| >= |observed difference|

**Fisher's exact backup:** If OOS Saturday M3+ events < 5, use Fisher's exact two-tailed test instead (permutation unreliable for sparse outcomes).

**Binomial MC cross-check:** T=10,000, seed=42 — if permutation p and binomial p disagree by > 0.05, report both and flag.

---

## 7. Pass/Fail Gates

### Primary Gate
- OOS permutation p < alpha_corrected (0.01 for k=1, 0.005 for k=2)
- If FAIL: **CLOSED** — permanent null for C05 (and C06 if declared)
- If PASS: proceed to secondary gates

### Secondary Gates (all must pass for VALIDATED)

| Gate | Test | Fail result |
|---|---|---|
| SG-1 | IS sign == OOS sign (directional consistency) | DIAGNOSTICS_ONLY |
| SG-2 | OOS Saturday M3+ events >= 3 | DIAGNOSTICS_ONLY |
| SG-3 | Cohen's h >= 0.10 | DIAGNOSTICS_ONLY |
| SG-4 | Three-window consistency (150/500/all-OOS, same direction) | DIAGNOSTICS_ONLY |

**Full VALIDATED:** All gates pass → McNemar comparison vs full-history strategy performance.

---

## 8. P-Hacking Controls

| Risk | Control |
|---|---|
| Best-weekday selection | Binary boundary (Sat vs Mon-Fri) only. Testing individual weekdays requires k=7 Bonferroni and new registry entry. |
| Gap threshold optimization | C06 threshold locked at >= 2 days. Cannot change after data look. |
| Metric switching | M3+ locked. Cannot switch to M2+ or M1+ after seeing results. |
| Strategy selection | Must be declared in registry entry before OOS data touch. |
| Lottery switching | DAILY_539 is primary. Testing POWER_LOTTO after DAILY_539 null requires k=2 correction and new entry. |
| OOS window shifting | Cutoff locked in registry. Cannot expand or shift after any data look. |
| C06 as salvage | C06 may not be added post-hoc after C05 null. Must be declared simultaneously. |

---

## 9. Leakage Controls

- **LC-1:** IS/OOS cutoff declared in registry before any per-regime statistics computed
- **LC-2:** Strategy pre-specified in registry; no post-hoc substitution
- **LC-3:** Regime boundary (Sat vs Mon-Fri) locked; no post-hoc weekday optimization
- **LC-4:** C06 gap threshold (>= 2 days) locked; no optimization
- **LC-5:** No interaction testing (C05 AND C06 combined subset) without separate registration
- **LC-6:** Sunday draws excluded before any analysis (pre-declared here)

---

## 10. Power Analysis (Qualitative)

**Warning: LOW POWER for Saturday vs Weekday comparison.**

| Parameter | Value |
|---|---|
| OOS Saturday N | ~242 draws |
| OOS Weekday N | ~1524 draws |
| M3+ baseline estimate | ~1-3% per draw (strategy-dependent) |
| Expected Saturday M3+ events | ~2-7 events |
| Minimum detectable effect (approx.) | Saturday rate >= ~5% (approximately 2.5× baseline) |

The test has power only for **large effects**. Small-to-medium regime effects cannot be detected at this sample size. A null result does not prove "no effect" — it proves "no large effect detectable at N=242."

Fisher's exact test is the appropriate method given sparse expected event counts.

---

## 11. Why This May / May Not Affect Hit Rate

**Why it might (speculative):**
- Saturday draws attract a different player pool (casual vs regular), creating different crowd-coverage patterns
- Operational differences in Saturday draws (speculative — no evidence)

**Why it won't:**
- Lottery RNG is independent of calendar labels
- L82 found null across 5885 draws (all H001-H008); testing 806-draw Saturday subset loses power
- L103 (H009 Lag-1 neighbor) showed even structurally plausible hypotheses fail at p=0.840
- Anti-crowd EV conditioning (L101/L102): unconditional edge remains negative regardless of conditioning day

**Honest assessment:** The test is methodologically valid. The primary value of P269C is **permanent closure of C05/C06**, not expected discovery.

---

## 12. Stop Rule

> If OOS primary gate p >= alpha_corrected: the test is COMPLETE and the result is NULL. C05 is permanently CLOSED. C06 (if declared) is permanently CLOSED. No re-testing with modified regime boundaries, metrics, or strategies is authorized under this pre-registration.

---

## 13. Design Verdict: READY_FOR_REGISTRY

**Verdict:** `READY_FOR_REGISTRY`

The design is technically sound and p-hacking-proof:
- Binary boundary pre-identified in P213 H_REGIME_SEGMENTATION (valid design direction for DAILY_539)
- Feature confirmed NOT tested in P219 M10 MI sweep (P253H draw_history_feature)
- Data fully available in-repo (draws.date column, no external fetch)
- OOS split, k, alpha, strategy selection rules all declarable before any data look

**Caveats:**
1. Hit-rate plausibility is LOW; P269A-Lite recommendation was NO_GO
2. Power limited: OOS Saturday N~242, can only detect very large effects
3. Expected result: null (consistent with L82)
4. This is a single-shot test; if null, C05/C06 permanently closed

**Why not NO_GO_DESIGN_TOO_WEAK:** The design can be formulated without p-hacking. N=242 Saturday draws is sparse but testable. C05 is genuinely untested (not covered by L82 H001-H008). A null result will permanently close this direction — low cost for getting certainty.

---

## 14. Proposed P269C Task

| Requirement | Detail |
|---|---|
| Registry write | **REQUIRED** — append H1 to `lottery_api/data/hypothesis_registry.jsonl` before test |
| Statistical test | **REQUIRED** in P269C |
| DB write | NOT required |
| External fetch | NOT required |
| Strategy declaration | Must name production strategy from RSM in registry entry before data look |
| Model | Sonnet 中模型, thinking 中 |
| Task type | Type D (registry write + statistical test) |

---

## 15. Final Classification

`P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_COMPLETE_READY_FOR_REGISTRY`

This artifact does not improve win rate, does not predict lottery numbers, does not authorize betting advice, and does not authorize any DB write, Hypothesis Registry write, or strategy promotion. All of those actions are deferred to P269C.
