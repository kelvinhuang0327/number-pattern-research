# P269A-Lite: Next External Signal Family Candidate Matrix v0

**Date:** 2026-06-11 Asia/Taipei  
**Classification:** `P269A_LITE_NEXT_EXTERNAL_SIGNAL_REPO_ONLY_SCOUTING_COMPLETE_NO_GO`  
**Task Type:** Type B read-only scouting artifact (repo-only, no external research)  
**Status:** Repo-only scouting only. No DB write. No registry mutation. No statistical test. No strategy. No betting advice.

**No-Claim Statement:** This artifact does not improve win rate, does not predict lottery numbers, does not authorize betting advice, and does not constitute a strategy recommendation.

---

## 0. P268D4 Closure Boundary

The draw-order (`drawNumberAppear`) exit-rank-heterogeneity arc (P268A–P268D4) is **CLOSED**:
- H1 PRIMARY_FAIL: DAILY_539 p=0.3051 ≥ alpha=0.01
- H1_holdout, H2, H3: **NOT AUTHORIZED, NOT OPENED**
- No strategy may be derived from the draw-order line
- `analysis/p268d3_h1_draw_order_confirmatory_permutation_test.py` **must not be re-run**

Future success-rate research must target a **new external signal family**, not a re-parameterization of this closed H1 line.

---

## 1. Repo-Only Limitation

This is a downgraded (Lite) version of P269A:
- **No external web search** — only repo artifacts, roadmap, `outputs/research/`, `analysis/`, and `lottery_api/data/`
- **No statistical tests** — all assessments are qualitative + evidence-from-artifacts only
- **No data fetching** from external APIs
- **No DB writes**
- **No Hypothesis Registry writes**
- Intended output: candidate matrix v0 to inform a potential P269B pre-registration decision

---

## 2. Key Repo Evidence Used

| Evidence | Key Finding |
|---|---|
| `lottery_api/data/lottery_v2.db` schema | `draws` table has `jackpot_amount`, `sell_amount`, `total_amount` columns |
| DAILY_539 sales data | `sell_amount` populated for 5,861/5,885 draws (full history 2007–2026); BIG_LOTTO/POWER_LOTTO: 0 rows |
| DAILY_539 draw schedule | Mon(1015)/Tue(1015)/Wed(1015)/Thu(1014)/Fri(1014)/Sat(806)/Sun(6) — natural weekday vs Saturday regime |
| POWER_LOTTO draw schedule | Mon(959)/Thu(959) only — strict biweekly |
| P268C | TLCAPIWeB API exposes **no machine/ball-set ID field** |
| P268A-S | winnerCount/prize-distribution = Track B payout/EV-only (not hit-rate) |
| P213 H_REGIME_SEGMENTATION | Design-only, not authorized, P221F gate not passed — weekday/calendar regime flagged |
| P253H draw_history_feature | `days_since_last_draw` **NOT tested** in P219 M10 MI sweep |
| L82/L90/L91 | DAILY_539 signal space exhausted; BIG_LOTTO 49C6 fair-random |
| L101/L102 | Anti-crowd / pool-size conditioning: advisory-only, unconditional edge remains negative |
| P245A/P245B | All external methods EV-only or diagnostic; P245B bias gate design complete; BOCPD gated on NIST reaching ORANGE/RED |

---

## 3. Candidate Matrix

| ID | Signal Family | Availability | Hit-rate Plausibility | EV/Pop Risk | Recommendation | Classification |
|---|---|---|---|---|---|---|
| **C01** | draw-order / drawNumberAppear exit-rank | AVAILABLE_IN_REPO | LOW | LOW | **REJECT** | ALREADY_NULL |
| **C02** | prize-tier / winner-count history | SOURCE_HINT_ONLY | LOW | HIGH | **REJECT** | EV_ONLY_OR_POPULARITY_ONLY |
| **C03** | DAILY_539 sell_amount / total_amount | AVAILABLE_IN_REPO | LOW | HIGH | **REJECT** | EV_ONLY_OR_POPULARITY_ONLY |
| **C04** | BIG_LOTTO/POWER_LOTTO jackpot / rollover | SOURCE_HINT_ONLY | LOW | HIGH | **REJECT** | EV_ONLY_OR_POPULARITY_ONLY |
| **C05** | draw weekday / schedule regime | AVAILABLE_IN_REPO | LOW | LOW | **WATCHLIST** | HIT_RATE_PLAUSIBLE (low) |
| **C06** | calendar gap / days_since_last_draw | AVAILABLE_IN_REPO | LOW | LOW | **WATCHLIST** | HIT_RATE_PLAUSIBLE (low) |
| **C07** | game-rule / machine / ball-set era | UNKNOWN | MEDIUM (if break detected) | LOW | **REJECT** | DATA_UNAVAILABLE |
| **C08** | delayed/cancelled/abnormal draw markers | UNKNOWN | LOW | LOW | **REJECT** | DATA_UNAVAILABLE |
| **C09** | official sales data BIG_LOTTO/POWER_LOTTO | SOURCE_HINT_ONLY | LOW | HIGH | **REJECT** | EV_ONLY_OR_POPULARITY_ONLY |

---

## 4. Detailed Candidate Notes

### C01 — draw-order / drawNumberAppear (ALREADY_NULL)
P268D4 CLOSED. H1 PRIMARY_FAIL. Do not re-open without genuinely new signal source and fresh pre-registration.  
The P268D-1 JSONL artifact (21,682 records) remains available for a **structurally different** statistic on the same field — but that requires its own pre-registration, not a continuation of H1/H2/H3.

### C02 — prize-tier / winner-count (EV_ONLY)
P268A-S explicitly classified winnerCount as Track B, payout/EV-only. L101/L102: anti-crowd conditioning is advisory-only and unconditional edge remains negative. Not a hit-rate signal.

### C03 — DAILY_539 sell_amount (EV_ONLY, data available)
The most data-rich candidate: 5,861/5,885 DAILY_539 rows with full history. However, DAILY_539 is a **fixed-prize** lottery — ticket sales volume does not affect prize amounts, making sell_amount purely a crowd-level proxy. Anti-crowd EV is L101/L102 territory. Not a hit-rate signal. **Data note:** if a future team wants to test a sell_amount-gated regime hypothesis (high-volume vs low-volume draws), the data is immediately available in-repo without fetch. Expected result: null (consistent with L101/L102).

### C04 — BIG_LOTTO/POWER_LOTTO jackpot (EV_ONLY, no data yet)
Schema column exists (`jackpot_amount`) but 0 rows populated for BIG_LOTTO/POWER_LOTTO. Would require external fetch + Type D DB write. Same EV-only logic as C03. Not recommended.

### C05 — Weekday/schedule regime (WATCHLIST)
**Most actionable WATCHLIST candidate.** Data fully available from `draws.date`. P213 H_REGIME_SEGMENTATION identified this as a valid design direction (DAILY_539 + POWER_LOTTO). P253H confirms NOT tested in P219. Natural regime boundary: DAILY_539 Saturday (806 draws) vs weekday (1014–1015); POWER_LOTTO Mon/Thu biweekly.  
**Key constraint:** Hit-rate plausibility is LOW for fair random draws (weekday doesn't causally affect ball-draw randomness; L73/L82 closure). Power per regime is lower than full-history tests that already returned null. P221F pre-registration required before any scan.

### C06 — Calendar gap (WATCHLIST, overlaps C05)
P253H explicitly lists `days_since_last_draw` as NOT tested in P219. Structurally overlaps with C05 (post-holiday gaps correlate with weekday). If testing both C05/C06, must declare combined family k for Bonferroni correction.

### C07 — Machine/ball-set era (DATA_UNAVAILABLE)
Theoretically the most interesting external signal (structural breaks → real non-randomness windows). But P268C confirmed: **API exposes no machine/ball-set ID field**. BOCPD path (P245A recommendation) is gated on P238B NIST reaching ORANGE/RED (currently YELLOW). No data available in repo. Cannot upgrade to TOP_CANDIDATE from repo-only evidence.

### C08 — Abnormal draw markers (DATA_UNAVAILABLE)
Missing issue detector handles draw gaps as data quality only. No structured "abnormal draw" flag in DB. No in-repo source for this signal.

### C09 — BIG_LOTTO/POWER_LOTTO sales (EV_ONLY, no data)
Same analysis as C03 but data not yet in DB. Lower priority than C03.

---

## 5. Top Candidate Recommendation: NO_GO

**No external signal family with HIGH or MEDIUM hit-rate plausibility and confirmed available data was found from repo-only evidence.**

### Reason
After the P268D4 null closure, the remaining external signal families are:
- **EV/popularity-only**: C02 (winner count), C03 (DAILY_539 sales), C04 (jackpot), C09 (BIG/POWER sales)
- **Data unavailable**: C07 (machine era — most interesting, not accessible), C08 (abnormal markers)
- **WATCHLIST (LOW plausibility, not external)**: C05/C06 (calendar regime — derivable from existing date column, not a truly new external source)

The calendar/weekday regime (C05/C06) is a legitimate design direction per P213, but:
1. It is not a truly external signal family — derived from the existing `date` column
2. Hit-rate plausibility is LOW for fair random draws
3. L82 closed the DAILY_539 full-history signal space; regime sub-sampling loses power
4. Expected to reproduce null consistent with L73/L82

### Conditions for upgrading to GO
1. NIST gate reaches ORANGE/RED → enables BOCPD + machine-era hypothesis (C07)
2. Official machine/ball-set change dates confirmed from press releases or official history
3. A new external data source beyond TLCAPIWeB (e.g., draw audit reports, third-party verification)
4. P245B sequential bias monitor accumulates e-value evidence K≥100

---

## 6. Recommended P269B Task (Conditional)

**If user explicitly decides to pursue the WATCHLIST calendar regime path:**

| Requirement | Detail |
|---|---|
| External data fetch | NOT required |
| Pre-registration | **REQUIRED** — declare regime boundaries before data look |
| Hypothesis Registry write | **REQUIRED** |
| DB write | NOT required |
| Statistical test | NOT in P269B (design doc only) |
| Strong model | NOT required (Sonnet 中模型) |
| Task type | Type B read-only design doc |

**If user decides NOT to pursue WATCHLIST path:**
- **HOLD** — no P269B at this time
- Wait for P245B NIST gate to reach ORANGE/RED, or for a new external data source

---

## 7. Final Classification

`P269A_LITE_NEXT_EXTERNAL_SIGNAL_REPO_ONLY_SCOUTING_COMPLETE_NO_GO`

This artifact does not improve win rate, does not predict lottery numbers, does not authorize betting advice, and does not authorize any DB write, Hypothesis Registry write, or strategy promotion.
