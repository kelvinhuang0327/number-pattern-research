# P274A — Prospective Confirmation Protocol (Design & Pre-registration Only)

- **Task:** `P274A_PROSPECTIVE_CONFIRMATION_PROTOCOL_DESIGN`
- **Mode:** `DESIGN_AND_PREREGISTRATION_ONLY_READ_ONLY_NO_DB_NO_EXECUTION`
- **Generated:** 2026-06-15 (Asia/Taipei)
- **Final classification:** `P274A_PROSPECTIVE_CONFIRMATION_PROTOCOL_DESIGN_COMPLETE`
- **Canonical payload digest:** `f2294716699368a9c2b21fb14301d84d70f662b882aef9eab896f96825f18ffc`
- **Base origin/main:** `91dc783f40def5142391664fc34b7691805a745d` · **Task branch:** `task/p274a-prospective-confirmation-protocol-design`

> **This document designs a protocol. It does not start the clock, create an activation record, capture any future row, or evaluate any prospective outcome.** `design_only=true`, `preregistration_only=true`, `execution_started=false`, `activation_started=false`, `production_db_accessed=false`, `prediction_success_claim=false`, `betting_advice=false`. Production apply remains `NOT_READY_FOR_APPLY`; P273B is not started.

---

## 1. Why retrospective P273A is NOT prospective confirmation

P273A established, on **already-observed** DAILY_539 history, a prize-aware edge that survives exact distinct-ticket without-replacement nulls and Bonferroni correction across 108 hypotheses (`PRIZE_AWARE_EDGE_CORRECTION_SURVIVING`, `prediction_success_claim=false`). That is the **retrospective confirmation ceiling**: the windows, candidate set, and endpoint were all chosen with the outcomes already in view. A retrospective edge — however well corrected — cannot rule out selection, look-ahead, or survivorship effects baked into the historical record. **Confirmation of a research edge requires genuinely unseen, future-only draws** scored under a frozen boundary, which is exactly what this protocol pre-registers. P274A reuses P273A's governed endpoint and exact null but applies them only to draws that do not yet exist.

**Primary research question.** After a future-only boundary is activated under a separately authorized task, does each frozen DAILY_539 strategy produce a draw-level prize-aware success rate **above its exact distinct-ticket random null** on genuinely unseen future draws?

## 2. The three frozen candidates (DAILY_539 only)

| ID | Strategy | Expected N (distinct tickets/draw) | Exact null q_N |
|----|----------|-----------------------------------|----------------|
| C1 | `acb_markov_midfreq_3bet` | 3 | 0.304431435743 |
| C2 | `daily539_f4cold_3bet` | 3 | 0.304431435743 |
| C3 | `daily539_f4cold_5bet` | 5 | 0.453949563750 |

Exactly these three; **no substitution, addition, removal, cross-lottery candidate, or strategy-version swap** (any version change needs a separate amendment authorized *before* prospective outcomes begin). Cross-lottery transfer remains unresolved and is **outside** P274A. Candidate order does not affect statistical treatment.

## 3. Endpoint and exact null

- **Endpoint:** `D539_ANY_PRIZE_AWARE_WIN` — draw-level any-bet prize-aware success; DAILY_539 success = **at least two main-number hits** (`hit_count >= 2`) under the committed scorer. One statistical unit per target draw; **actual** distinct-ticket count per draw; no replay-row pseudo-replication; no outcome-dependent ticket deduplication.
- **Exact null:** `q_N = 1 - C(T-W,N) / C(T,N)` with `T = 575757` (= C(39,5)) and `W = 65621`. `q_1=0.113973429763`, `q_3=0.304431435743`, `q_5=0.453949563750`.
- The independent-with-replacement approximation `1-(1-W/T)^N` is **rejected for final confirmation** (diagnostic only). Constant-N draws use the exact one-sided binomial; if per-draw N varies, the final test uses the exact one-sided **Poisson-binomial** over the actual per-draw q values. Actual N **must be verified** from prospective canonical ticket identities, never inferred from the strategy name.

## 4. Future-only boundary

- No historical or already-observed draw may count toward prospective confirmation.
- A separately authorized activation task must write concrete activation_timestamp_utc and first_eligible_target_draw BEFORE any eligible outcome is observed or ingested.
- first_eligible_target_draw = the first official DAILY_539 draw whose scheduled draw time is strictly later than BOTH (1) the P274A protocol merge timestamp AND (2) the separately recorded activation_timestamp_utc.
- All target draws earlier than first_eligible_target_draw are permanently excluded.
- No backfill across the boundary; no replacement of missing future draws with historical draws.
- A delayed ingestion remains eligible only when its official draw identity is after the frozen boundary.
- Boundary amendments after any eligible outcome becomes observable are prohibited.

**Concrete boundary status:** `activation_timestamp_utc = UNSET_PENDING_SEPARATE_ACTIVATION_AUTHORIZATION`, `first_eligible_target_draw = UNSET_PENDING_SEPARATE_ACTIVATION_AUTHORIZATION`. This is **not** an incomplete design — the deterministic boundary-selection algorithm is fully frozen. Execution readiness remains `false` until a future authorized task records the concrete values **before** any eligible outcome is observable.

## 5. Confirmatory family, correction, and power

- **Family:** exactly **3** candidate-level confirmatory hypotheses (one final test per candidate). H0: rate ≤ q_N; H1: rate > q_N.
- **Correction:** Bonferroni **m=3**, family α=0.05, per-candidate final α = **0.05/3 = 0.0166666666666667**. BH-FDR is descriptive only. **No post-outcome family shrinkage** — a stopped or insufficient candidate still counts in m=3. No confirmatory subfamily may be built from 50/300 monitoring, bet slots, alternative windows, or retrospective subsets.
- **Power assumption (governed, primary):** candidate-specific **50%-shrunken** retrospective excess at the 750 window, `p_alt = q_N + 0.5·(obs_rate_750 − q_N)`. The **unshrunk** retrospective effect is **not** used as the governed assumption (reported only as a secondary descriptive figure).
- **Method:** exact one-sided binomial at α=0.05/3; power = P(X ≥ k* | n, p_alt) with k* the smallest k such that P(X ≥ k | n, q_N) ≤ α. Integer-draw search from 300 up to a bound of 6000 (≥5000). Two independent algorithms (incomplete-beta continued fraction vs direct log-pmf summation) agree to 1.79e-12.

### 5.1 Candidate-specific power results

| ID | Strategy | N | q_N | obs@750 | excess@750 | 50%-shrunk p_alt | N@80% | N@90% |
|----|----------|---|-----|---------|------------|------------------|-------|-------|
| C1 | `acb_markov_midfreq_3bet` | 3 | 0.304431 | 0.357333 | 0.052902 | 0.330882 | 2730 | 3605 |
| C2 | `daily539_f4cold_3bet` | 3 | 0.304431 | 0.366667 | 0.062235 | 0.335549 | 1986 | 2612 |
| C3 | `daily539_f4cold_5bet` | 5 | 0.453950 | 0.566667 | 0.112717 | 0.510308 | 695 | 915 |

**Common final horizon = max(N@90%) = 3605 draws** (binding candidate C1 (acb_markov_midfreq_3bet)). The horizon is *not* reduced because another candidate has a larger observed effect. At this horizon every candidate reaches ≥0.90 power under the governed shrunken alternative (C1 0.9010, C2 0.9699, C3 1.0000).

**Calendar (descriptive only):** at the committed DAILY_539 cadence of 6 draws/week (≈313.07 draws/year, source P268D1 via P272B), 3605 draws ≈ **11.515 years**. Draw counts are primary; the calendar figure does not govern.

If any candidate cannot reach 90% power within the bound, the protocol fails closed as `P274A_BLOCKED_POWER_HORIZON_NOT_ESTABLISHED` (not the case here).

## 6. Sequential monitoring — no interim efficacy

Equivalent-control design: **all efficacy α is preserved for the final analysis**; checkpoints A and B spend **zero** α.

- **Checkpoint A (50 future draws):** operational / data-integrity review only — support, identity traceability, candidate version, boundary adherence, missingness. **No efficacy, no p-value promotion, no success declaration.** SHORT-50 is a guardrail only.
- **Checkpoint B (300 future draws):** operational review **plus non-binding futility**. Conditional power is computed under the pre-registered 50%-shrunken alternative with accumulated data; a candidate may be **recommended** for futility closure only when conditional power is below the frozen threshold (**conditional power < 10% (0.10), evaluated at checkpoint B (300 draws) under the pre-registered 50%-shrunken alternative**). Futility is non-binding for Type-I error; stopping a candidate does **not** reduce m=3; continuing despite non-binding futility needs a documented owner decision before the next look and cannot change final α. **No GO/confirmation decision at B.**
- **Final checkpoint (3605 draws):** the **only** checkpoint that can confirm. Exact one-sided binomial (or Poisson-binomial), Bonferroni m=3 fixed, **no optional extension after inspecting results**.

## 7. Integrity stops (classified separately from statistical failure)

Any of the following invalidates or pauses the affected candidate and is recorded as an **integrity** failure, never as a statistical result: boundary violation; retrospective row leakage; candidate/version substitution; missing canonical ticket identity; untraceable distinct-ticket count; duplicated target draw; outcome available before ticket capture; scorer/endpoint drift; registry/recommendation mutation; production-capture schema mismatch; unauthorized manual correction; insufficient provenance.

## 8. Pre-registered decision outcomes

**Candidate-level:**

1. **`PROSPECTIVE_CONFIRMED_RESEARCH_EDGE`** — governed horizon reached, support complete, integrity/provenance pass, observed excess > 0, exact one-sided final p ≤ 0.05/3, lower confidence bound exceeds the exact null, and no amendment after boundary activation. *Meaning: future-only statistical confirmation **for research** — not betting advice, not automatic production promotion, not registry/recommendation authorization.*
2. **`PROSPECTIVE_NULL`** — evaluable horizon reached, integrity pass, confirmation not met, no significant-negative result.
3. **`PROSPECTIVE_FAILED_DIRECTION`** — non-positive final excess, or a pre-registered significantly-below-null criterion met, or futility closure accepted by the owner.
4. **`PROSPECTIVE_INSUFFICIENT_SUPPORT`** — horizon/support unreachable in the governed period; missingness not imputable; no historical substitution.
5. **`PROTOCOL_INVALIDATED`** — leakage/identity/boundary/version/provenance/endpoint breach.

**Project-level:** `AT_LEAST_ONE_PROSPECTIVE_RESEARCH_CONFIRMATION`, `PROSPECTIVE_NULL_ALL_EVALUABLE`, `MIXED_RESULT`, `INSUFFICIENT_SUPPORT`, `PROTOCOL_INVALIDATED`. **No project-level outcome authorizes production apply.**

## 9. Prospective capture contract

Minimum fields required **before** each draw outcome is published: `protocol_version`, `activation_id`, `candidate_id`, `lottery_type`, `strategy_id`, `strategy_version`, `target_draw`, `ticket_generation_timestamp_utc`, `official_scheduled_draw_timestamp_utc`, `normalized_canonical_ticket_identities`, `ticket_fingerprints`, `bet_index_association`, `distinct_ticket_count`, `scorer_endpoint_version`, `source_provenance`, `capture_status`, `outcome_availability_status`, `immutable_record_timestamp`.

Invariants: ticket capture must precede outcome availability; append-only semantics; deterministic identity; no historical backfill into the prospective family; no candidate substitution; no silent missing-ticket inference; no outcome-dependent correction; all future evaluation derives from prospective records only.

## 10. P271 dependency and separate future owner gates

The prospective-capture infrastructure (P271H feasibility → P271I design → P271J implementation → P271K temp-DB rehearsal → P271L preflight + read-only schema inspection) is **referenced but UNACTIVATED**. Production apply remains `NOT_READY_FOR_APPLY`; the prospective production schema state is `ABSENT_CLEAN`; **P271M and P271N are not started**; controlled_apply is not started. **P274A does not authorize P271 controlled apply.** Execution requires a future, separate owner decision covering infrastructure, activation, maintenance, and production safety. **Protocol-design completion is not execution readiness.**

### 10.1 Reconciliation with P272B

- P272B quantified prospective detectability for the M3+ (hit>=3) any-bet endpoint, lottery-wide, under a P267C-derived +1.32pp scenario on a ~1.0% base (p1~2.32%), finding DAILY_539 N*(0.9)=1013 draws and decision POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED.
- P274A targets the prize-aware M2+ endpoint (q_N ~0.30-0.45), is per-candidate (the three frozen P273A survivors), grounds the alternative in P273A's own 750-window excess with 50% shrinkage, and the threshold is now governed by explicit owner authorization.
- P274A's larger common horizon (3605 draws) vs P272B's 1013 reflects a small RELATIVE lift (~1.18-1.25x) on a high base rate, not the ~2.3x lift of a rare event P272B modeled; same exact-binomial method and same alpha=0.05/3.

## 11. Source integrity

All four P273A source artifacts parse and their canonical payload digests were independently recomputed and matched:

- `outputs/research/p273a_prize_aware_inferential_validation_20260615.json` — `5666e67c88e5f3b1233f2d6d5a5f86746c4f7605ae98bda3f2d59ec5aa0b2fb4`
- `outputs/research/p273a_primary_window_observed_counts_20260615.json` — `65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f`
- `outputs/research/p273a_distinct_ticket_identity_20260615.json` — `ad85e447dfc7db7afd70e9fdde928bb12a2ae367d6c1f23f14b7e3504701ae51`
- `outputs/research/p273a_prizeaware_observed_counts_20260614.json` — `859c3889f2c698a27d16caf4195bbd0fd032cad80d8c44e990958658624b3103`

Project class `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING`; `prediction_success_claim=false`; 36 frozen groups and m=108 are historical P273A evidence; the three DAILY_539 candidates are the only authorized prospective candidates; production apply remains `NOT_READY_FOR_APPLY`; P271M/P271N and capture activation remain unstarted; P273B remains unstarted.

## 12. Safety claims

- `design_only = true`
- `preregistration_only = true`
- `execution_started = false`
- `activation_started = false`
- `production_db_accessed = false`
- `production_write = false`
- `registry_mutated = false`
- `recommendation_logic_changed = false`
- `retrospective_remining_performed = false`
- `p273b_started = false`
- `deployment_started = false`
- `controlled_apply_started = false`
- `production_apply_authorized = false`
- `prediction_success_claim = false`
- `betting_advice = false`

---

**Tests:** design/artifact validation only. Source-focused suite **NOT RUN**; full repository suite **NOT RUN** (neither is claimed as PASS).

**Canonical payload digest (recomputed twice, deterministic):** `f2294716699368a9c2b21fb14301d84d70f662b882aef9eab896f96825f18ffc`
