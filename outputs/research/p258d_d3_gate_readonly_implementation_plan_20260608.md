# P258D — D3 `AdversarialNullSurvivorGate` Read-Only Implementation Plan

**Date:** 2026-06-08
**Task:** `P258D`
**Type:** Type B read-only implementation plan (planning/schema/test-contract only — no executable code, no DB write, no backtest)
**Source decision:** `P258C_D3_READ_ONLY_PREREGISTRATION_DESIGN_READY`
**Final Decision:** `P258D_D3_READ_ONLY_IMPLEMENTATION_PLAN_READY`

---

## ⚠️ Mandatory Interpretation

> **D3 `AdversarialNullSurvivorGate` is a VALIDATION / FALSIFICATION gate, not a prediction model.**
> - It cannot claim improved prediction accuracy.
> - It cannot approve production. **Passing the gate means only "not yet rejected," never "approved."**
> - It cannot touch recommendation logic, write DB, or trigger controlled_apply / deployment.
> - It cannot run live or production-like evaluation.
> - **P258D is an implementation plan only — not executable implementation.** No module is created; names are proposed for a future P258E.

---

## Goal and Non-Goals

**Goal.** Translate the merged P258C pre-registration design into a safe, read-only **implementation plan**: module boundaries, data contracts, artifact schemas, validation contracts, a future test plan, and explicit STOP gates. Describe *what* a future P258E read-only skeleton would build, without building anything executable now.

**Non-goals.** No gate/module implementation (names proposed only). No run against any real candidate. No backtest / execution. No DB write, registry mutation, recommendation/controlled_apply/deployment touch. No accuracy claim. No conversion into an approval gate.

---

## Phase 0 Verification

| Check | Result |
|---|---|
| Canonical repo / branch | PASS |
| P258C PR #374 | merged (CI green) |
| main HEAD at branch | `9ca9d98` |
| P258B + P258C artifacts present | PASS |
| DB integrity / replay rows | ok / 94,924 |

---

## Source Artifacts Used

- **P258B** — D3 selection + methodology-not-predictor caveat.
- **P258C** — gate pre-registration design (matched null family, endpoints, correction family, risk triggers).
- **P257A** — best-N-bet baseline every candidate must beat (HISTORICAL_REPLAY_ONLY).
- **P256A** — NULL risk boundary.

---

## Module Boundary Proposal

**Principle.** Strict separation between (a) read-only ingest adapters, (b) pure null-construction + statistics functions with no I/O, (c) a thin orchestrator that only reads artifacts and writes a diagnostic artifact, and (d) a fail-closed validation layer. **No module may import production, registry, recommendation, controlled_apply, or DB-write code.**

| Layer | Responsibility |
|---|---|
| `ingest_adapter` | Read-only loaders for candidate output + P257A baseline artifacts; no DB write, no live fetch |
| `null_factory` | Pure functions building the matched adversarial-null family from declared degrees of freedom; deterministic given seeds |
| `statistics` | Pure McNemar / paired-bootstrap / empirical-null-percentile / BH-FDR / Bonferroni; no I/O |
| `validation` | Leakage / provenance / timestamp / N-bet / null-match / correction-family / no-mutation guards; fail-closed |
| `orchestrator` | Reads inputs, calls null_factory + statistics under validation, emits diagnostic-only artifact; **never promotes** |
| `audit` | Structured audit-trail writer to the artifact only (no DB, no logs-as-state) |

**Import ban.** The validation layer asserts that the orchestrator and all gate modules do **not** import recommendation/registry/production/controlled_apply/deployment/DB-write paths.

### Proposed future module names (P258E only — NOT created now)

```
lottery_api/research/d3_gate/candidate_ingest.py
lottery_api/research/d3_gate/baseline_ingest.py
lottery_api/research/d3_gate/null_factory.py
lottery_api/research/d3_gate/gate_statistics.py
lottery_api/research/d3_gate/gate_validation.py
lottery_api/research/d3_gate/gate_orchestrator.py
lottery_api/research/d3_gate/gate_audit.py
lottery_api/research/d3_gate/schemas.py
```

---

## Data Contracts

### Candidate input contract

Required: `candidate_method_name`, `lottery_type`, `n_bet_count`, `number_count_per_bet`, `frozen_parameter_set_hash`, `freeze_timestamp`, `feature_dimensionality`, `regime_count_or_parameter_count`, `window_schedule`, `prediction_cadence`, `available_information_timestamp_cutoff`, `per_draw_outputs`.

Per-draw: `target_draw_id`, `target_draw_date`, `predicted_bets`, `feature_source_timestamps`, `generated_before_outcome_evaluation`.

Constraints: `predicted_bets` length == `n_bet_count`; each bet length == `number_count_per_bet` within pool range; all `feature_source_timestamps` < cutoff < target draw time.

### P257A baseline input contract

Required: `lottery_type`, `n_bet_count`, `baseline_strategy_name`, `per_draw_best_hit_count`, `draws`. Aligned to candidate by `(lottery_type, n_bet_count, target_draw_id)`; unmatched draws excluded from paired comparison and logged; coverage reported.

### Matched adversarial-null contract

- **Input:** candidate degrees of freedom (8 dims), `family_size_min ≥ 1000`, null construction methods (feature-time-permutation / random-parameter-decoy / synthetic-regime / per-draw-Binomial), seeds.
- **Output:** per-null-member `(null_id, construction_method, per_draw_outputs_or_hit_series)`; family distribution `(metric_name, null_metric_values, candidate_metric_value, candidate_percentile)`.
- **Matching rule:** each null mirrors the candidate's declared degrees of freedom exactly; mismatch → rollback STOP gate.
- **L96 guard:** hit-based nulls use per-draw `Binomial(1, baseline_i)`, NOT label-shuffle.

### Provenance contract

`candidate_generation_timestamp`, `available_information_cutoff`, `lottery_type`, `target_draw_id`, `target_draw_date`, `n_bet_count`, `number_count_per_bet`, `feature_dimensionality`, `regime_count_or_parameter_count`, `window_schedule`, `random_seed`, `null_generation_seed`. **100% completeness required** before any endpoint is computed.

---

## Validation Contract

1. **leakage/provenance** — every feature timestamp < cutoff < target draw time; provenance completeness == 100%.
2. **timestamp cutoff** — no same-day later / target / post-target draw enters features.
3. **exact N-bet matching** — `predicted_bets` length == `n_bet_count`; number count matches lottery contract.
4. **null-family matching** — every null mirrors candidate degrees of freedom; family ≥ 1000.
5. **correction-family declaration** — full `candidate × null × lottery × N × metric × window` family declared before evaluation; untested-but-declared combinations still count.
6. **no production/recommendation mutation** — assert no import/call into recommendation/registry/production/controlled_apply/deployment/DB-write; artifact-only output.

---

## Future Artifact Schema (P258E)

- **inputs:** `candidate_artifact_ref`, `p257a_baseline_artifact_ref`, `null_family_spec`, `correction_family_spec`, `window_schedule`, `seeds`.
- **outputs:** `gate_decision ∈ {REJECTED, NOT_YET_REJECTED}`, `per_metric_results`, `audit_trail_ref`.
- **rejection_reasons:** fails_paired_vs_p257a · below_95th_percentile_vs_matched_null · leakage_or_provenance_failure · single_window_or_year_or_draw_only · significance_removed_by_correction · null_family_too_weak_or_mismatched · used_to_approve_production_directly.
- **NOT_YET_REJECTED semantics:** explicitly **not** approval; candidate stays observation-only pending separate human-authorized prototype + later corrected-OOS confirmation.
- **metrics:** paired_win_rate_vs_p257a, hit_count≥1 rate, average hit_count, hit_count≥2/≥3 (diagnostic).
- **corrected_p_values:** bh_fdr_p, bonferroni_p, empirical_null_p. **null_percentile:** candidate percentile within matched null family.
- **paired_comparison_summary:** McNemar net wins/losses/ties; paired-bootstrap CI. **short/mid/long summary:** per-tier effect, non-negative/positive counts, calendar-year span. **audit_trail:** input hashes, seeds, excluded draws, validation results, timestamp.

---

## Future Test Plan (P258E)

`schema_tests` · `leakage_guard_tests` · `null_matching_tests` · `baseline_matching_tests` · `correction_family_tests` · `no_auto_approval_tests` · `no_db_write_tests` · `no_recommendation_mutation_tests`.

---

## STOP Gates for Future Implementation

- missing P257A baseline
- missing candidate provenance
- missing timestamp cutoff
- unmatched null family
- unregistered metric / window / N value
- production or recommendation code touched
- DB write required
- broad package / config change required

---

## Next Allowed Task: P258E

**P258E — D3 gate read-only SKELETON / contract tests only** (if explicitly authorized later).
- Read-only skeleton + contract tests only — **no executable gate evaluation, no backtest, no DB write.**
- Precondition: P258D plan merged **and** separate explicit authorization for P258E.
- P258E may create non-executing skeleton modules + schema/contract tests; it may **not** run the gate against any candidate.

### Forbidden next tasks
- executable gate evaluation / backtest unless explicitly authorized later
- production integration
- recommendation mutation
- DB write

---

## Required Completion Check

1. **真的完成？** 是 — JSON + MD implementation plan + tests.
2. **測試結果：** 見 `tests/test_p258d_d3_gate_readonly_implementation_plan.py`.
3. **仍卡住的唯一問題：** 無 — 等 P258E read-only skeleton (separate explicit authorization required).
4. **修改檔案：** `outputs/research/p258d_*.json/.md`、`tests/test_p258d_*.py`、governance files.
5. **staged / commit / push：** file-by-file (no `git add -A`).
6. **是否允許進入下一輪：** 是 — P258E read-only skeleton / contract tests only, with separate authorization.
7. **Final Classification：** `P258D_D3_READ_ONLY_IMPLEMENTATION_PLAN_READY`
