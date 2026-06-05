# P213 New Hypothesis Scouting Plan

**Date:** 2026-06-05
**Classification:** `P213_NEW_HYPOTHESIS_SCOUTING_PLAN_COMPLETE`
**Task Type:** Type B (read-only design doc / artifact) under P240D governance simplification rules
**Status:** Design plan only — no code changes, no DB write, no registry mutation
**Authorization:** `Authorize P213 new hypothesis scouting plan (read-only design doc, no code changes, no DB write)`

---

## 1. Scope and Non-Goals

### In Scope
- Survey of closed research lines and their authoritative final status
- Lottery-by-lottery status summary
- Candidate new hypothesis categories for future work
- Required gates before any future implementation
- Single recommended next direction with authorization phrase
- Same-PR governance closeout under P240D Type B rule

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Code changes | Not authorized |
| DB write | Not authorized |
| Registry mutation | Not authorized |
| Statistical scan execution | Not authorized |
| Strategy promotion | Not authorized |
| Production / recommendation change | Not authorized |
| Betting advice or wagering recommendation | Never authorized |
| P211 restart | P211R is complete; result is HISTORICAL_ARTIFACT |
| P238B NIST escalation | YELLOW is observation-only |

---

## 2. Current Closed Lines

The following research chains are complete and must not be reopened without new external evidence:

| Chain | Final Status | Authority |
|---|---|---|
| P211R short/mid-window diagnostic | `P211R_IS_CANDIDATES_PRIOR_OOS_REJECTED_HISTORICAL_ARTIFACT` | PR #298 |
| P212 POWER_LOTTO backward-OOS gap check | `P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_HISTORICAL_ARTIFACT` | PR #299 |
| P231B POWER_LOTTO first-zone backward-OOS | `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL` | PR #272 |
| P230C DAILY_539 survivor | `REJECTED_BY_BACKWARD_OOS_HISTORICAL_ARTIFACT_DIRECTION` | PR #270 |
| P227C 3_STAR/4_STAR box-play | `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL` | PR #265 |
| P238B NIST randomness audit | `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY` | PR #289 |
| BIG_LOTTO signal boundary | L90/L91 — 7 signals all p>0.05; 49C6 with fair random process | roadmap.md |
| P211A second-zone | NULL / display-only confirmed | PR #255 |

---

## 3. Lottery-by-Lottery Status

### BIG_LOTTO
- **Status:** Signal space exhausted. Maintenance mode.
- **Evidence:** L90 — 7 signal types (ACB, MidFreq, Markov, Fourier, Regime, P1_Neighbor, MicroFish) — zero reach p<0.05. L91 — 6 randomness tests pass; MI=0.006 bits (1.18% of baseline entropy); 49C6 pool with fair random process.
- **Gate to reopen:** New draws >3,000 beyond current, or external structural change evidence. Not currently actionable.
- **Recommendation:** Do not reopen.

### DAILY_539
- **Status:** P224B gate — WAIT_FOR_OOS. Gate requires ≥300 new live draws (preferred 500). Prior shifted toward NULL after P230B1.
- **Evidence:** P230C REJECTED backward-OOS (4,265 draws, mean below baseline). P224 clean-slice p=0.0674 (WAIT_FOR_OOS). P230B1 backward-OOS mean 0.6375 < baseline 0.6410.
- **Draw count in replay table:** 1,550 draws (all historical, not live).
- **Gate to reopen:** ≥300 new live draws added to DB. Not currently actionable without ingestion.
- **Recommendation:** Passive monitoring only. No new hypothesis scan until gate opens.

### POWER_LOTTO
- **Status:** IS-window diagnostic chain complete. All candidates confirmed historical artifacts.
- **Evidence:** P211R — 9 IS-window candidates, all prior OOS rejection. P212 — fourier30/zonal_entropy temporal split below baseline. P231B — midfreq_fourier_mk_3bet backward-OOS p=0.3018 NULL.
- **Draw count in replay table:** 1,551 draws.
- **Recommendation:** Do not run new IS-window scans on existing replay data. Passive monitoring only.

### 3_STAR / 4_STAR
- **Status:** UNDERPOWERED_NO_SIGNAL (box-play). Straight-play BLOCKED — positional order lost in sorted DB storage.
- **Draw data in DB:** 3_STAR 4,179 draws; 4_STAR 2,922 draws (draw-side only; replay rows = 0 for both).
- **Box-play gate:** 3_STAR needs ≥10,000 draws; 4_STAR needs ≥17,000 draws.
- **Straight-play gate:** Requires positional re-ingestion (Type D DB write, separate authorization).
- **Recommendation:** Only actionable if positional re-ingestion is authorized OR natural draw accumulation reaches threshold.

### Second Zone (POWER_LOTTO special ball)
- **Status:** Display-only / NULL. P211A confirmed all Bonferroni-corrected p > 0.04. P210 protocol bias diagnostic also confirmed.
- **Recommendation:** Display-only policy remains. Do not reopen.

---

## 4. Hypothesis Categories

Each category below is design-level only. None are immediately implementable without separate explicit authorization and P221F pre-registration.

---

### H-P213-1: 3_STAR/4_STAR Positional Data Recovery Design

**Hypothesis name:** `H_STAR_POSITIONAL_REINGEST`
**Lottery scope:** 3_STAR, 4_STAR
**Category type:** Data readiness design (Type B design-doc → Type D ingestion when authorized)
**Current blocker:** `POSITIONAL_ORDER_LOST_REINGEST_REQUIRED`

**Problem:** The DB stores 3_STAR and 4_STAR draw numbers in sorted order. Straight-play requires knowing the exact position each ball was drawn. Sorted storage makes this impossible.

**Design questions:**
1. What is the original data source for 3_STAR/4_STAR draws? Is positional order available upstream?
2. What schema changes would be needed to store positional data?
3. What new replay table columns would enable straight-play hit computation?
4. What is the correct ingestion procedure to avoid position-loss?

**Required gates before implementation:**
- Read-only design/feasibility doc confirming source data has positional order
- Separate Type D DB-write authorization for any ingestion
- P221F pre-registration before any scan on re-ingested data
- New test battery for straight-play hit semantics

**P2.4 fields required:** `sample_size`, `window_definition`, `baseline_method` (1/A(10,3) for 3_STAR straight), `family_size_k`, `correction_method`

**Why not immediately implementable:** Source data positional availability is unconfirmed. DB write is Type D and requires separate explicit authorization.

**Allowed next action:** `"Authorize P213B 3_STAR/4_STAR positional data recovery feasibility design (read-only, no DB write)"`

**Forbidden next action:** `db_write`, `reingest_without_authorization`, `strategy_promotion`, `betting_advice`

---

### H-P213-2: DAILY_539 Future Live Draw Monitoring Gate

**Hypothesis name:** `H_DAILY539_FUTURE_OOS_GATE`
**Lottery scope:** DAILY_539
**Category type:** Passive monitoring gate (no new hypothesis — existing P224B protocol)
**Current blocker:** `P224B_GATE_NOT_OPEN` (need ≥300 new live draws since P230C)

**Gate condition:** When ≥300 new DAILY_539 live draws have been ingested to the replay DB, recheck `midfreq_fourier_2bet` against the new OOS window per P224B protocol.

**Note:** This is not a new hypothesis. It is a re-evaluation gate on an existing strategy. Prior evidence shifted toward NULL after P230B1. The gate only authorizes a re-evaluation, not deployment.

**Why not immediately actionable:** No live draw ingestion is currently running. The gate count has not advanced since P230C.

**Allowed next action:** Monitor draw count; when ≥300 new draws are confirmed, authorize `"Authorize P214 DAILY_539 future OOS gate check (no DB write beyond draw ingestion)"`

**Forbidden next action:** `strategy_promotion`, `deploy_before_gate`, `betting_advice`

---

### H-P213-3: Regime Segmentation Design

**Hypothesis name:** `H_REGIME_SEGMENTATION`
**Lottery scope:** DAILY_539, POWER_LOTTO (not BIG_LOTTO — exhausted)
**Category type:** Design-only (requires new scan authorization)
**Current blocker:** `P221F_GATE_NOT_PASSED` (new windows must be pre-registered)

**Problem:** Existing analysis uses rolling windows and full-history baselines. A regime-segmentation approach would test whether distinct structural periods exist (e.g., pre/post mechanical changes, number-pool changes) that might show different hit-rate distributions.

**Hypothesis:** If a structural break exists, the pre-break baseline differs from the post-break baseline, and strategies tuned to one regime might show different performance across regimes.

**Required gates:**
1. Read-only historical analysis confirming evidence of a regime break (draw distribution test)
2. P221F pre-registration: pre-specified regime boundaries before any scan
3. Bonferroni-corrected test: K = number of regimes × strategies × windows
4. OOS confirmation: strategy must perform above baseline in held-out regime data

**P2.4 fields required:** `split_boundary` (regime boundary), `window_definition` (regime window), `family_size_k`, `baseline_method` (regime-specific), `is_oos` (True for held-out regime)

**Why not immediately implementable:** No evidence of regime break currently documented. Requires a new Type B design-doc establishing the regime boundary criteria before any scan.

**Allowed next action:** `"Authorize P214 POWER_LOTTO regime segmentation design (read-only design doc, no code changes)"`

**Forbidden next action:** `scan_without_pre_registration`, `strategy_promotion`, `db_write`, `betting_advice`

---

### H-P213-4: NIST ORANGE/RED Confirmation Design (Contingent)

**Hypothesis name:** `H_NIST_CONFIRMATION_DESIGN`
**Lottery scope:** All (BIG_LOTTO was the primary YELLOW signal)
**Category type:** Contingent design (only if new draws produce ORANGE/RED alert)
**Current blocker:** `NIST_YELLOW_OBSERVATION_ONLY_NO_TRIGGER`

**Current state:** P238B result is YELLOW (3 BIG_LOTTO frequency/serial alerts). YELLOW is observation-only and does not authorize any strategy, production, or DB change.

**Trigger condition for future design:** If a new NIST audit on fresh draw data produces ORANGE or RED alert for a specific test, THEN a confirmation design task would be warranted. ORANGE/RED would authorize human diagnostic review only — not strategy.

**Why not immediately actionable:** No new draws since P238B. No ORANGE/RED trigger. Under the No-op HOLD rule (P240D), this is not a valid task without a new external trigger.

**Allowed next action:** Monitor; if ORANGE/RED appears in a re-run with fresh data, authorize `"Authorize NIST confirmation design (observation-only, no strategy)"`

**Forbidden next action:** `treat_yellow_as_signal`, `strategy_promotion`, `betting_advice`

---

## 5. Recommendation

**Recommended next direction: H-P213-1 — 3_STAR/4_STAR Positional Data Recovery Design**

**Rationale:**
1. **Only genuinely new signal space remaining.** BIG_LOTTO is exhausted. DAILY_539 gate is closed. POWER_LOTTO IS-window chain complete. 3_STAR/4_STAR straight-play is the only lottery family where the analysis has never been run, and the blocker is a data engineering issue, not a statistical null result.
2. **Modest scope.** A feasibility design doc (Type B) answers whether the source data has positional information before committing to a Type D ingestion task.
3. **Does not repeat known-null work.** This is a genuinely different signal type (straight-play vs box-play) with a much higher baseline granularity.
4. **Clear P2.4 integration path.** The schema module (P242), fixture vocabulary (P243A), and integration plan (P244C) all support straight-play diagnostics once data is available.

**Exact authorization phrase:**
```
Authorize P213B 3_STAR/4_STAR positional data recovery feasibility design (read-only, no DB write)
```

**If user prefers to HOLD:**
No action needed. System remains at `WAITING_FOR_USER_AUTHORIZATION`. No new task starts without explicit authorization.

---

## 6. Safety Attestation

This scouting plan:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about higher winning probability
- Provides **no wagering recommendation**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not restart P211 (P211R is complete; result is HISTORICAL_ARTIFACT)
- Does not escalate P238B NIST YELLOW result
- All safety booleans: `db_write_authorized=False`, `registry_write_authorized=False`, `production_authorized=False`, `betting_advice=False`, `strategy_authorized=False`
- P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`

---

## 7. Type B Same-PR Closeout Rationale

This task is **Type B** under P240D §Task Type Classification because:
- It produces only Markdown and JSON artifact files (no code changes)
- Governance changes affect ≤4 files and add ≤120 governance lines
- CI passes on a single PR
- No merge conflict

**Same-PR governance closeout is allowed. No separate closeout PR is required.**
