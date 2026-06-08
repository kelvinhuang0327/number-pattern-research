# P258C — D3 `AdversarialNullSurvivorGate` Read-Only Pre-registration Design

**Date:** 2026-06-08
**Task:** `P258C`
**Type:** Type B read-only design artifact (no code, no DB write, no prototype)
**Source decision:** `P258B_READ_ONLY_PREREGISTRATION_CANDIDATE_SELECTED` (D3 selected)
**Final Decision:** `P258C_D3_READ_ONLY_PREREGISTRATION_DESIGN_READY`

---

## ⚠️ Mandatory Interpretation — Methodology Gate, Not Predictor

> **D3 `AdversarialNullSurvivorGate` is a VALIDATION / FALSIFICATION gate, not a number-prediction model.**
> - It proposes **no** number-scoring rule and generates **no** recommended bets.
> - It **cannot** improve prediction accuracy and may **not** be described as doing so.
> - It can only define **stricter falsification criteria** for future candidate methods.
> - It can only **REJECT** or mark **not-yet-rejected** — it can **never PROMOTE**.
> - All outputs are `diagnostic_only` / `read_only` / `observation_only`.
> - A gate survivor remains observation-only and requires a **separate human-authorized** prototype task plus later corrected-OOS confirmation before any further consideration.

---

## Goal and Non-Goals

**Goal.** Pre-register (design-only) an adversarial-null survivor gate that strengthens falsification of any future candidate prediction method. A candidate is credible only if it beats **both** the P257A best-N-bet baseline **and** a matched adversarial-null family in paired OOS, after multiple-testing correction, across short/mid/long windows. The gate's value is **rejection discipline**: detect when an apparent edge is indistinguishable from a null artifact given the same mechanical degrees of freedom.

**Non-goals.**
- Not a predictor; generates no recommended bets.
- Does not improve accuracy; no accuracy claims.
- Does not auto-approve or auto-promote — passing the gate is **not** approval.
- Does not touch recommendation logic, production, registry, controlled_apply, deployment, or DB.
- P258C is design only — no prototype, no executable gate, no backtest.

---

## Phase 0 Verification

| Check | Result |
|---|---|
| Canonical repo | PASS |
| P258B PR #373 | merged (fast-forward, CI green) |
| main HEAD at branch | `3104588` |
| P258A + P258B artifacts present | PASS |
| DB integrity / replay rows | ok / 94,924 |

---

## Candidate Method Input Requirements

A candidate enters the gate only if it provides:

1. **Frozen generator** — logic + parameters locked before any OOS; freeze timestamp recorded.
2. **Output contract** — N-bet portfolio matching the P257A baseline contract (exact bet count, number count per bet, valid pool range).
3. **Declared degrees of freedom** — feature dimensionality, regime/parameter count, window schedule, prediction cadence, available-information timestamp cutoff — so the matched null can mirror them.
4. **Provenance metadata** — per output: feature source timestamps, freeze timestamp, parameter set hash, `target_draw_id`, produced before outcome evaluation.
5. **Leakage self-declaration** — every feature uses only `source_time < target_draw_time`; no full-history normalization.

---

## Matched Adversarial-Null Family

For each candidate, build **M ≥ 1000** decoy strategies preserving the candidate's mechanical degrees of freedom but with predictive structure destroyed. The candidate's apparent edge is credible only if it ranks **at or above the 95th percentile** of its matched null family after correction.

**Construction methods.**
- **Feature-time-permutation null** — break the temporal link between feature vector and target draw while preserving feature marginals and the candidate's selection mechanism.
- **Random-parameter decoy null** — instantiate the candidate's own generator with randomly drawn parameters (same parameter count), no fitting on real outcomes ("same knobs, random settings").
- **Synthetic-regime null** — if the candidate uses K regimes, generate K random regime assignments with the same marginal frequencies but no link to outcomes.
- **Per-draw Binomial Monte-Carlo null** — for hit endpoints, draw outcomes from `Binomial(1, baseline_i)` per draw. **Not** label-shuffling (L96: shuffling preserves the mean → p=1.0).

### Null matching dimensions

`lottery_type` · `n_bet_count` · `number_count_per_bet` · `window_schedule` · `candidate_feature_dimensionality` · `regime_count_or_parameter_count` · `prediction_cadence` · `available_information_timestamp_cutoff`

---

## Provenance & Leakage Gates

**Provenance requirements.** Every candidate and decoy output carries `target_draw_id`, feature source timestamps, freeze timestamp, parameter set hash. Provenance completeness must be **100%** before any endpoint is computed. Null generators record that they were frozen before OOS and not fitted on outcomes.

**Leakage-prevention tests (fail-closed).**
- assert every feature `source_time < target_draw_time` (candidate **and** nulls)
- assert no full-history normalization / quantile fitting (rolling/train-only allowed)
- assert null decoys not fitted on target outcomes
- assert provenance completeness == 100% before endpoint computation
- assert no same-day later draw / target draw / post-target draw enters any feature
- any failure invalidates the candidate's gate result (rollback trigger)

---

## OOS Split & Window Schedule

**Chronological split:** train → validation → untouched test. Candidate generator, parameters, null generators, regime definitions, and the correction family are all locked using train/validation only; final evidence on untouched test. **Walk-forward** replication required for robustness (no re-tuning).

| Tier | Windows |
|---|---|
| Short | 100 / 125 / 150 |
| Mid | 500 / 750 / 1000 |
| Long | 1500 where draws permit (DAILY_539); capped at all-available for BIG_LOTTO / POWER_LOTTO |

**Stability rule:** all three tiers non-negative vs P257A; ≥2 tiers positive with CI not crossing materially negative; single-window survival rejected; result must hold across >1 calendar year.

**Data-constraint flag:** ≥5000-draw assumptions hold for DAILY_539 (5,882) but are **infeasible** for BIG_LOTTO canonical (2,114) and POWER_LOTTO (1,917) — long windows capped with explicit flag. Inherits the P221F frozen anti-overfit gate; no re-running the same sweep on the same data.

---

## Endpoints & Paired Tests

**Primary endpoints.**
1. Paired win rate vs P257A best-N-bet baseline.
2. Candidate percentile vs matched adversarial-null family.

**Secondary endpoints.** `hit_count ≥ 1` success rate; average `hit_count`; `hit_count ≥ 2` / `≥ 3` as **corrected diagnostics only**.

**Paired test plan.**
- `hit_count ≥ 1` (binary): **McNemar** paired, per-draw, candidate vs P257A; report net wins/losses/ties.
- average `hit_count`: **paired bootstrap CI** (or Wilcoxon signed-rank) for the per-draw difference; report effect size + CI, not only p.
- null-percentile endpoint: empirical percentile within the null family + corrected (empirical-null) p-value.

**Multiple-testing correction family.** Pre-declare the full family of `candidate_methods × null_variants × lottery_types × N_values × metrics × windows`. Apply **BH-FDR** and **Bonferroni**. Any combination tried but not reported still counts toward the family. Uncorrected significance is diagnostic-only.

---

## Acceptance Thresholds

- zero leakage / provenance failures
- candidate paired win rate vs P257A > 0.50 with corrected significance on the pre-registered primary metric
- candidate exceeds the **95th percentile** of the matched null family after correction
- short/mid/long all non-negative vs P257A; ≥2 positive with CI not crossing materially negative
- average `hit_count` not degraded vs P257A beyond a pre-registered tolerance
- result holds across >1 calendar year / multi-era
- **candidate remains observation-only even if all thresholds are met** (the gate is falsification, not approval)

## Failure Criteria

- candidate does not beat P257A on the paired primary metric
- candidate does not exceed the 95th percentile of the matched null family
- any leakage / provenance / timestamp failure
- survival driven by a single window, year, or high-hit draw
- correction removes significance
- null family too weak or not matched to candidate degrees of freedom
- the gate is used to approve production mutation directly

## Risk-Control Triggers

| Trigger | Action |
|---|---|
| observation-only | survivors stay read-only until a **separate** pre-registered prototype + later corrected-OOS confirmation; gate never promotes |
| auto-downgrade | percentile < 95th OR rolling paired win rate ≤ 0.50 → downgrade to observation-only |
| rollback | null family mismatched OR provenance incomplete → invalidate gate result, revert to P257A baseline |
| stop | no candidate beats matched nulls after correction → stop candidate selection |
| re-pre-registration | any change to null generator / correction family / primary endpoint → new pre-registration |
| ban-from-recommendation | no survivor enters recommendation logic without later corrected-OOS evidence **and** explicit separate authorization |

---

## Explicit Bans (this artifact authorizes NONE)

- ❌ No DB write
- ❌ No production change
- ❌ No registry mutation
- ❌ No controlled_apply
- ❌ No deployment
- ❌ No recommendation mutation
- ❌ No prototype code
- ❌ No strategy backtest
- ❌ No improved-accuracy claim
- ❌ **No conversion of D3 into an auto-approval gate** — falsification-only; reject or mark not-yet-rejected, never promote

---

## Prior-Evidence Guards

- **L96** — label-shuffle permutation preserves the mean (p=1.0); use per-draw `Binomial(1, baseline_i)` Monte-Carlo null.
- **L86 / L89** — ML/evolution feature engineering overfits low-base-rate pools; the matched-null family is designed to expose this degrees-of-freedom overfitting.
- **L82 / L91** — DAILY_539 signal exhausted; BIG_LOTTO 49C6 indistinguishable from fair random; prior probability of any gate survivor is **LOW** — expect rejection.
- **P256A** — feature-information MI NULL (0 Bonferroni survivors); the gate institutionalizes this null boundary as the default expectation.

---

## Next Allowed Task: P258D

**P258D — D3 adversarial-null gate read-only IMPLEMENTATION PLAN (not prototype).**
- Type: read-only implementation plan only — module boundaries, test plan, data contracts.
- **No executable gate, no backtest, no DB write.**
- Building an executable prototype requires a **separate explicit authorization**.

---

## Required Completion Check

1. **真的完成？** 是 — JSON + MD design artifact + tests.
2. **測試結果：** 見 `tests/test_p258c_d3_adversarial_null_gate_preregistration.py`.
3. **仍卡住的唯一問題：** 無 — 等 P258D read-only implementation plan (or explicit prototype authorization).
4. **修改檔案：** `outputs/research/p258c_*.json/.md`、`tests/test_p258c_*.py`、governance files.
5. **staged / commit / push：** file-by-file (no `git add -A`).
6. **是否允許進入下一輪：** 是 — P258D read-only implementation plan only.
7. **Final Classification：** `P258C_D3_READ_ONLY_PREREGISTRATION_DESIGN_READY`
