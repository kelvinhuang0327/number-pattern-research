# P258B — External Response Evaluation

**Date:** 2026-06-08
**Task:** `P258B`
**Classification:** `P258B_READ_ONLY_PREREGISTRATION_CANDIDATE_SELECTED`
**Type:** Type B read-only evaluation artifact (no code, no DB write)
**Final Decision:** `P258B_READ_ONLY_PREREGISTRATION_CANDIDATE_SELECTED`

---

## Executive Summary

The external response contained exactly 3 method directions, each with all 9 required fields. Structure check **PASSED**. Evaluation against P258A rubric, hard-rejection rules, and eligibility criteria yielded:

| Direction | Method | Classification |
|---|---|---|
| D1 | `CrossLotteryLaggedEntropyRegime` | **REJECT_INSUFFICIENT_EVIDENCE** |
| D2 | `DrawSetGeometryResidualConformal` | **HARD_REJECT** |
| D3 | `AdversarialNullSurvivorGate` | **ACCEPT_FOR_READ_ONLY_PREREGISTRATION** |

Selected candidate for next read-only pre-registration: **D3 `AdversarialNullSurvivorGate`** — with the explicit caveat that it is a **validation/methodology gate, not a predictive signal or production edge**.

---

## Phase 0 — Actual State Verification

| Check | Result |
|---|---|
| Canonical repo `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | PASS |
| Canonical branch `main` | PASS |
| HEAD `c02c70d67fbb…` (P258A merge state) | PASS |
| P258A JSON+MD artifacts + tests present | PASS |
| P258A state marker `P258A_…INTAKE_PROTOCOL_READY` | PASS |
| P258A regression tests | **22/22 PASS** |
| External response present | PASS (inline in task prompt) |
| Staged files | 0 |

---

## Structure Check

- **Exactly 3 directions:** YES
- **All 9 required fields per direction:** YES (all three: `method_name`, `core_idea`, `why_not_a_small_tweak`, `target_accuracy_metric`, `minimum_viable_experiment`, `acceptance_thresholds`, `failure_criteria`, `monitoring_metrics`, `risk_controls`)
- **Result:** PASS → not `HARD_REJECT_INCOMPLETE_RESPONSE`

---

## D2 — `DrawSetGeometryResidualConformal` → HARD_REJECT

**Hard-rejection rule violated: Rule 11** — failure to respect prior negative evidence.

The proposal directly re-proposes the L82/L91-falsified set-geometry feature family (sum band, span, sorted gap vector, odd/even structure, low-mid-high buckets, pairwise distance, modular residue) with no survival argument. The P258A prompt explicitly required: "A credible proposal must explain why it would survive where these failed."

Specific prior evidence it fails to address:
- **L73** — 539 Zone/Sum is white noise (Ljung-Box full-sample non-significant); ZPI permanently closed.
- **L91** — BIG_LOTTO 6 randomness tests all pass, including pairwise correlation and permutation entropy — the exact structural functions D2 proposes.
- **L104** — 539 residue/tail-digit distribution is a pool-structural artifact, not exploitable; permanently closed.
- **L105** — 539 gap/consecutive pattern rejected (χ²=2.035, p=0.565; Lag-1 r=0.005).

The conformal prediction wrapper supplies coverage validity, not predictive power. A well-calibrated geometry band over proven-random draws still spans astronomically many combinations, yielding zero per-number edge. The proposal's own concession ("it may ultimately reduce to a null if lottery draw-set geometry is fully random") is an implicit acknowledgement of L91/L73/L104/L105 without providing the required survival argument.

**D2 is not scored.** Hard-rejected directions are ineligible for pre-registration.

---

## D1 — `CrossLotteryLaggedEntropyRegime` → REJECT_INSUFFICIENT_EVIDENCE

D1 is not hard-rejected — it is not a straightforward L82/L91 repackage and its methodological hygiene is genuine (timestamp filter with failing tests, chronological OOS, ≥3-window stability, BH-FDR+Bonferroni, McNemar vs P257A, observation-only gate). However, it does **not meet the five eligibility criteria** for pre-registration selection:

**Reason 1 — Missing explicit P256A NULL risk boundary.**
P258A required each proposal to "explain why it would survive where [P256A/L82/L91/L86/L89] failed." D1 does not mention P256A, L82, L91, L86, or L89 at all.

**Reason 2 — Cross-lottery signal is a documented NULL (L106).**
L106: BL↔PL (24 periods) and 539↔BL (193 periods), six Pearson cross-lottery tests all p>0.16, zero Bonferroni survivors; "cross-lottery flow signal does not exist, line closed." D1 is adjacent to this closed line and provides no distinguishing argument.

**Reason 3 — L86/L89 composite-overfitting risk.**
D1 proposes a multi-dimensional regime classifier (entropy + dispersion + parity + residue + gap → regime labels → portfolio shapes) over BIG_LOTTO canonical 2,114 draws and POWER_LOTTO 1,917 draws — exactly the low-base-rate, thin-sample scenario L86/L89 identify as catastrophically overfit. No per-regime power analysis is provided.

### Rubric Scores — D1

| Criterion | Score | Notes |
|---|---:|---|
| novelty_of_signal | 3 | New source hypothesis, but cross-lottery already NULL per L106 |
| leakage_safety | 4 | Explicit per-target timestamp filter with failing tests |
| oos_feasibility | 3 | Low draw counts (BIG 2,114 / POWER 1,917) → thin per-regime samples |
| mcnemar_paired_test_feasibility | 4 | McNemar + paired bootstrap vs P257A specified |
| short_mid_long_stability | 2 | Composite regimes over ~2k draws are fragile |
| multiple_testing_discipline | 4 | BH-FDR + Bonferroni, family pre-declared |
| drift_detectability | 4 | Regime distribution drift and feature distribution drift monitored |
| implementation_cost *(capped)* | 2 | Moderate complexity |

**D1 resubmission path:** add (a) explicit P256A/L82/L91 survival argument, (b) L106 differentiation argument, (c) per-regime power analysis for 2,114 and 1,917 draws. Resubmission constitutes a new proposal round, not a continuation of P258B.

---

## D3 — `AdversarialNullSurvivorGate` → ACCEPT_FOR_READ_ONLY_PREREGISTRATION

### Eligibility Check

| Criterion | Result |
|---|---|
| No hard rejection | PASS |
| Explicit P257A baseline comparison | PASS — required for every candidate; candidate must beat P257A in paired OOS |
| Explicit P256A NULL risk boundary | PASS — core premise is that "many prior apparent edges were null artifacts"; directly institutionalises P256A/L82/L91/L86/L89 |
| Feasible OOS and paired comparison plan | PASS — chronological OOS split, McNemar + empirical null percentile, corrected p-values |
| No production/recommendation mutation | PASS — makes production-mutation an explicit *failure criterion* and *ban-from-recommendation trigger* |

### Rubric Scores — D3

| Criterion | Score | Notes |
|---|---:|---|
| novelty_of_signal | 4 | Novel as method; not another number-scoring rule — genuinely different category |
| leakage_safety | 5 | Adds provenance + timestamp verification for candidate outputs and null generators |
| oos_feasibility | 5 | Gate applies to candidate method OOS outputs; highly feasible |
| mcnemar_paired_test_feasibility | 5 | McNemar vs P257A + empirical null-percentile + BH-FDR + Bonferroni specified |
| short_mid_long_stability | 5 | Candidate must beat P257A and matched null across all three windows |
| multiple_testing_discipline | 5 | Correction family includes all candidate methods, null variants, lottery types, N, metrics, windows |
| drift_detectability | 4 | Null-family calibration drift + candidate/null divergence stability monitored |
| implementation_cost *(capped)* | 3 | Moderate — needs null generator construction |

### ⚠️ Mandatory Caveat — Methodology Gate, Not Predictor

> **D3 is a VALIDATION / ADVERSARIAL-NULL SURVIVOR GATE, not a number-prediction method.**
> - It cannot itself improve prediction accuracy.
> - It can only pre-register a stricter falsification gate for future candidate methods.
> - It must remain read-only / observation-only.
> - All gate survivors remain diagnostic until a separate pre-registered prototype task confirms them.
> - It must not touch recommendation logic, production, DB, registry, controlled_apply, or deployment without a separate explicit authorization.

### Human Gate Fork

If the CEO requires this round to yield a genuine *predictive* signal, the honest reading is that zero predictive-signal directions survived (D1 insufficient, D2 hard-rejected), and the round should be classified `P258B_NO_ELIGIBLE_EXTERNAL_DIRECTION`. The current classification selects D3 per the written decision rules (the rules contain no "must be a predictive signal" criterion). **This fork is surfaced for human ruling.**

---

## Recommended Follow-up: P258C

**P258C — D3 `AdversarialNullSurvivorGate` read-only pre-registration design.**
- Precondition: P258B closeout artifact merged.
- Type: Type B read-only design artifact.
- Scope: Design the adversarial null-gating methodology — matched-null construction specification, correction family pre-declaration, endpoints, OOS schedule, provenance requirements, evaluation criteria.
- **No prototype, no DB write, no recommendation mutation, no production change.**
- All designs remain observation-only.
- **Strong model required:** designing matched-null construction, correction family, and OOS schedule requires careful statistical reasoning.

---

## Explicit Non-Actions (This Artifact Authorizes NONE of These)

- ❌ No DB write
- ❌ No prototype strategy code
- ❌ No strategy implementation
- ❌ No registry mutation
- ❌ No recommendation logic change
- ❌ No production write
- ❌ No betting advice
- ❌ No claim of improved prediction accuracy

---

## Required Completion Check

1. **真的完成？** 是 — JSON + MD evaluation artifact + tests.
2. **測試結果：** 見 `tests/test_p258b_external_response_evaluation.py`.
3. **仍卡住的唯一問題：** 無 — 等 P258C (D3 pre-registration design, strong model).
4. **修改檔案：** `outputs/research/p258b_*.json/.md`、`tests/test_p258b_*.py`、governance files.
5. **staged / commit / push：** file-by-file (no `git add -A`).
6. **是否允許進入下一輪：** 是 — P258C awaits strong model.
7. **Final Classification：** `P258B_READ_ONLY_PREREGISTRATION_CANDIDATE_SELECTED`
