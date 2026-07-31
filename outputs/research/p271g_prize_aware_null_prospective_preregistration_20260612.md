# P271G — Prize-Aware Null Baseline & Prospective Holdout Preregistration

- **Task ID:** P271G
- **Mode:** `prize_aware_null_and_prospective_preregistration`
- **Preregistration version:** `p271g_v1`
- **Repo HEAD before task:** `6ce381e73fadb828cf0d4a367922eb400f6ea4a9`
- **Branch:** `task/p271g-prize-aware-null-prospective-preregistration`
- **Artifact paths (corrected canonical convention `outputs/research/`):**
  - `outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.json`
  - `outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.md`
- **Final classification:** `P271G_NULL_AND_PROSPECTIVE_PREREGISTRATION_DESIGN_COMPLETE_WITH_PRIOR_OUTCOME_EXPOSURE`
- **Source verification status:** `MANUAL_VERIFICATION_REQUIRED`
- **This is design-only and is not betting advice.**

---

## 1. Executive Summary

P271G freezes a **design contract** — a preregistration — for how a prize-aware predictive signal could, in the future, be **confirmed** rather than merely described. It is **design-only**: it generates no random tickets, executes no scorer or adapter, queries no database, runs no simulation, and calculates no statistic.

The contract fixes, in advance and immutably:

1. A **prize-aware random/null ticket generator** (uniform over the valid ticket space per lottery).
2. A **dependence-safe statistical unit** — the `target_draw` cluster within a lottery type — explicitly rejecting replay-row independence.
3. A **prospective confirmatory holdout** that only counts predictions created after an immutable cutoff.
4. **Fixed primary, secondary, and descriptive-only endpoints.**
5. **Multiple-testing correction and decision gates** (Holm family-wise control, α = 0.05, per family).
6. A hard **separation of retrospective exploratory evidence from prospective confirmatory evidence.**
7. **Versioning, leakage controls, and amendment rules.**

Strict outcome blindness was not achieved because mandatory governance exposed prior P271F outcomes. The parameters below were fixed by the externally supplied task contract and were not selected or adapted from those outcomes.

## 2. Why P271F Cannot Be Treated As Untouched Confirmation

P271F was an **aggregate descriptive evaluation** of already-existing historical replay rows. It ran **no null baseline, no inferential test, no strategy comparison, and made no predictive-improvement claim**. Its results already exist and have already been observed at the governance level.

Evidence that has already been looked at cannot serve as its own untouched confirmation: any statistic computed now on the same historical rows is **retrospective and exploratory**, subject to selection and look-elsewhere effects. **P271F is retrospective and exploratory.** **Confirmatory claims require prospective post-preregistration data** — predictions made before their draws close, after the cutoff frozen by this document. P271G therefore treats P271F strictly as a hypothesis-generating (exploratory) population and builds a separate confirmatory track.

## 3. Prior Outcome Exposure and Design Independence

Mandatory governance files exposed prior P271F outcomes before this preregistration was completed. This is disclosed as `strict_outcome_blindness=false` and `prior_outcome_exposure=true`.

- The numerical values are not reproduced in this artifact.
- Prior outcomes were not used to select endpoints, null rules, thresholds, multiplicity, sample gates, lottery-specific rules, or decision criteria.
- The P271F result artifacts were not ingested, parsed, imported, or executed by P271G.
- Only permitted structural scope metadata is retained: lottery type, eligibility labels, and total / eligible / excluded / processed row counts.
- No retrospective row can support an untouched confirmatory claim.

An interrupted pre-commit test draft contained exact historical outcome values as blacklist fixtures. Those fixtures were removed before commit. No exact historical outcome values remain in the final P271G JSON, Markdown, or test source. Semantic result-schema guards, result-artifact-ingestion guards, and executable-absence guards replace the contaminated blacklist. No design rule was changed because of those values.

## 4. Retrospective Exploratory Population

- **Population id:** `retrospective_exploratory`; **label:** exploratory; **confirmatory:** no.
- **Source:** existing P271F structurally eligible historical replay rows (read-only, already merged).
- **Permitted use:** only explicitly retrospective exploratory benchmarking.
- It **cannot support untouched confirmatory claims**, and **no strategy ranking, promotion, or production decision may rely on this population alone**.
- **POWER remains eligible-subset-only** (see §16 / power_eligible_subset_limitation).
- Structural scope (authorized counts, not outcomes): POWER_LOTTO total 36,104 / eligible 9,000 / excluded 27,104 (`MISSING_PREDICTED_SECOND_ZONE`); BIG_LOTTO 24,140 / 24,140 / 0 (FULL); DAILY_539 34,680 / 34,680 / 0 (FULL).

## 5. Prospective Confirmatory Population

- **Population id:** `prospective_confirmatory`; **label:** confirmatory; it is the **only** confirmatory population.
- **Inclusion:** only prediction records created strictly **after** the immutable prospective cutoff.
- The prediction must exist **before** the official draw close; the outcome is joined **only after** draw completion; prediction and result timestamps must be auditable.
- **No retrospective row may migrate** into the prospective population; **no post-draw regeneration, replacement, or amendment** is permitted; **no strategy may be added after the cutoff without a new preregistration version**.

## 6. Draw-Cluster Statistical Unit

Replay-row independence is **explicitly rejected**. **Replay rows within one target draw are not independent**: all tickets, all strategies, and all `bet_index` rows for a single `target_draw` (within a lottery type) belong to **one cluster**.

- **Primary cluster unit:** `target_draw` within lottery type.
- **Naive row-level binomial p-values are prohibited.** Inference must preserve within-draw dependence.
- **Permitted future primary method:** a draw-clustered randomization/permutation test under a frozen deterministic seed schedule.
- **Permitted future sensitivity method:** a draw-cluster bootstrap confidence interval.
- Neither method is executed in P271G.

## 7. Random/Null Ticket Generator

For each eligible prediction row, the generator **uniformly samples from the valid ticket space** for that row's lottery type. It **preserves** lottery type, target draw, ticket count per target draw, and total row/ticket count; it **does not preserve** the model-selected numbers and **does not use outcomes**.

**Seed derivation** is a deterministic cryptographic derivation over, in order, `preregistration_version` + `lottery_type` + `replication_index`. **Seeds exclude** `strategy_id`, winning numbers, P271F outcomes, and observed performance.

Lottery contracts (canonical game structure):

| Lottery | Main pick | Main range | Second / auxiliary |
|---|---|---|---|
| POWER_LOTTO | 6 | 1–38 | second zone: 1 number from 1–8 (null **samples second zone**) |
| BIG_LOTTO | 6 | 1–49 | **no predicted special field** |
| DAILY_539 | 5 | 1–39 | **no auxiliary number** |

**Repetitions are frozen:** primary repetitions = **100,000**; minimum valid repetitions = **99,900**; **no adaptive repetitions**; **no early stopping**; failed repetitions are reported and **not selectively replaced**. No simulation is executed in P271G.

## 8. Frozen Endpoints

- **Primary endpoint (each lottery):** the **draw-cluster mean of the `any_prize_aware_win` indicator** across submitted tickets.
- **Secondary endpoint (each lottery):** the **draw-cluster mean of the `M3+` indicator** across submitted tickets.
- **Descriptive-only endpoints:** main-hit distribution, auxiliary-hit distribution, prize-tier distribution, tier-class distribution, and the prize-aware / M3+ overlap matrix.

Descriptive endpoints receive **no confirmatory p-value**, **cannot independently trigger GO**, and **cannot be promoted after results are viewed**. **No strategy-specific endpoint is allowed.**

## 9. Effect Statistic

- **Primary observed statistic:** the mean of the target-draw cluster win proportions.
- **Null statistic:** the same statistic recomputed for each null replication.
- **Effect direction:** observed statistic minus the **median** null statistic.
- **Alternative:** one-sided, observed greater than null.

No values are calculated in P271G.

## 10. Multiple-Testing Correction

- **Primary family:** exactly **three** lottery-specific primary tests (one per lottery), **Holm** family-wise error control, **α = 0.05**.
- **Secondary family:** exactly **three** lottery-specific M3+ tests, under a **separate** Holm family-wise error control, **α = 0.05**. **Secondary success cannot override primary failure.**
- There is **no confirmatory testing** of the prize-tier or any other descriptive endpoint.

## 11. Minimum Evidence Gate

A `PROSPECTIVE_SIGNAL_CANDIDATE` requires **all** of:

- primary Holm-adjusted p-value < 0.05;
- observed-minus-null effect > 0;
- draw-cluster bootstrap 95% CI lower bound > 0;
- at least **100** completed target draws;
- at least **500** eligible prediction tickets;
- zero causality / timestamp violations;
- POWER second-zone prediction present where required;
- null integrity checks pass;
- a positive result under the preregistered sensitivity analysis.

Otherwise the result is classified `NO_CONFIRMED_PROSPECTIVE_SIGNAL`, `INSUFFICIENT_PROSPECTIVE_SAMPLE`, or `INVALID_PROSPECTIVE_EVIDENCE`. **This gate does not authorize production deployment or strategy promotion.**

## 12. Prospective Cutoff and Sample Gate

- `preregistration_created_at` = 2026-06-12T12:00:00+08:00; `preregistration_commit` = `PENDING_P271G_MERGE_COMMIT`.
- `prospective_prediction_start_at` = **`PENDING_P271G_MERGE_TIMESTAMP`** — a **pending merge marker, not a date**. **No historical or pre-merge start timestamp is used.**
- `minimum_draws_per_lottery` = 100; `minimum_tickets_per_lottery` = 500.
- No outcome before the start timestamp is confirmatory. The **end condition is sample-based** (frozen sample gates), not time-based and not peeking-based.
- **No repeated-peeking GO decision.** Interim descriptive monitoring may contain **no p-values and no GO decision**. The **final confirmatory analysis runs exactly once** after the frozen sample gates pass.
- Prospective activation requires a **separate authorized task after P271G merges**.

## 13. Leakage and Integrity Gates

The gates **fail closed**. Any of the following invalidates the affected prospective target-draw cluster:

- `prediction_created_at` is not before `draw_close_at`;
- timestamps are missing or ambiguous;
- the source prediction changes after draw close;
- the actual result was available during prediction generation;
- an actual special / second-zone value populated a predicted field;
- the target-draw join is missing or non-unique;
- prediction identity is duplicated;
- a prediction was amended after the cutoff;
- a prospective row was manually backfilled;
- the POWER predicted second zone is missing;
- the lottery type is unsupported.

## 14. Versioning and Amendment Policy

Frozen versions: `preregistration_version=p271g_v1`, `metric_contract_version=p271g_metrics_v1`, `null_generator_version=p271g_null_v1`, `clustering_contract_version=p271g_cluster_v1`, `prospective_protocol_version=p271g_prospective_v1`.

Amendments after merge **require a new version**, **cannot silently reinterpret already-collected evidence**, **must state whether prospective sample collection resets**, and **cannot modify the treatment of prior confirmatory data without explicit invalidation/versioning**.

## 15. Explicit Non-Actions

P271G did **not**: generate random/null tickets; execute the scorer or adapter; query or write the database; run any simulation; calculate any p-value, confidence interval, lift, effect size, power, or ranking; compare or rank strategies; rerun P271F; ingest P271F result artifacts; start temporal-window research or feature mining; or add any production integration. **Strategy-level comparison/ranking is excluded.** **No p-value, CI, lift, or effect value was calculated.**

## 16. Activation Requirements

- **Prospective collection** activates only via a separate, explicitly authorized task **after** P271G merges; `prospective_prediction_start_at` resolves to the merge timestamp at that point.
- **Null-baseline execution** requires its own explicit authorization and dedicated whitelist.
- **Scorer/adapter execution** against prospective data requires separate explicit authorization.
- **POWER eligible-subset limitation:** POWER_LOTTO retrospective evidence is eligible-subset-only because the predicted second zone is structurally present for only a subset of rows (the remainder excluded as `MISSING_PREDICTED_SECOND_ZONE`, never defaulted or inferred). Prospective POWER predictions must carry a predicted second zone before draw close.
- **P270C remains unauthorized.** **Temporal-window research and feature mining were not started.**

## 17. Final Classification

**`P271G_NULL_AND_PROSPECTIVE_PREREGISTRATION_DESIGN_COMPLETE_WITH_PRIOR_OUTCOME_EXPOSURE`** — the null/prospective preregistration design is frozen and complete with prior exposure truthfully disclosed. No execution, no data access, no inference. System remains `HOLD / WAITING_FOR_USER_AUTHORIZATION`.

---

## Required Declarations

- P271G is **design-only**.
- **Strict outcome blindness was not achieved.**
- **Mandatory governance exposed prior P271F outcomes.**
- **The numerical values are not reproduced in this artifact or any final P271G file.**
- **Design choices are frozen by the externally supplied task contract.**
- **Prior outcomes were not used to select endpoints, null rules, thresholds, multiplicity, or sample gates.**
- **The interrupted test-draft blacklist fixtures were removed and replaced with semantic/schema guards.**
- **No baseline was executed.**
- **No scorer or adapter execution occurred.**
- **No database was accessed.**
- **P271F is retrospective and exploratory.**
- **Confirmatory claims require new prospective post-activation data.**
- **Replay rows within one target draw are not independent.**
- **Strategy-level comparison/ranking is excluded.**
- **No p-value, CI, lift, effect value, ranking, or improvement claim was calculated.**
- **No production or strategy promotion is authorized.**
- **Official source status remains MANUAL_VERIFICATION_REQUIRED.**
- **P270C remains unauthorized.**
- **Temporal-window research and feature mining were not started.**
