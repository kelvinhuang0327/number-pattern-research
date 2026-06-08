# P258E — D3 `AdversarialNullSurvivorGate` Read-Only Skeleton + Contract Tests

**Date:** 2026-06-08
**Task:** `P258E`
**Type:** Type C small additive implementation — non-executing skeleton + contract tests only (no DB write, no executable gate, no backtest)
**Source decision:** `P258D_D3_READ_ONLY_IMPLEMENTATION_PLAN_READY`
**Final Decision:** `P258E_D3_READ_ONLY_SKELETON_CONTRACT_TESTS_READY`

---

## ⚠️ Mandatory Interpretation

> **D3 `AdversarialNullSurvivorGate` is a VALIDATION / adversarial-null survivor gate, not a prediction model.**
> - Cannot claim improved prediction accuracy.
> - Cannot approve production. **Passing the gate means only "not yet rejected," never "approved."**
> - Cannot touch recommendation logic, write DB, or trigger controlled_apply / deployment.
> - **P258E is skeleton + contract tests only** — no executable gate, no scoring, no null generation, no paired tests, no p-values, no candidate evaluation, no backtest.

---

## Phase 0 Verification

| Check | Result |
|---|---|
| Canonical repo / branch | PASS |
| P258D PR #375 | merged (CI green) |
| main HEAD at branch | `bd3a517` |
| P258D artifacts present | PASS |
| DB integrity / replay rows | ok / 94,924 |

---

## Skeleton Files Created

All under the P258D-proposed (previously absent) subpackage `lottery_api/research/d3_gate/`. Brand-new package; nothing imports it; the production app does not load it at startup; stdlib-only imports.

```
lottery_api/research/__init__.py
lottery_api/research/d3_gate/__init__.py
lottery_api/research/d3_gate/schemas.py
lottery_api/research/d3_gate/gate_validation.py
```

---

## Gate Status Enum (`schemas.GateStatus`)

| Allowed | Explicitly absent (by design) |
|---|---|
| `REJECTED` | `APPROVED` |
| `NOT_YET_REJECTED` | `PROMOTED` |
| | `PRODUCTION_READY` |
| | `RECOMMENDED` |

`NOT_YET_REJECTED` is explicitly **not** approval — the candidate stays observation-only pending a separate human-authorized prototype + later corrected-OOS confirmation. There is no enum value that could be read as a promotion.

---

## Schemas Defined (`schemas.py`)

- **`CandidateInput`** — candidate_id, lottery_type, target_draw_id, target_draw_date, n_bet_count, numbers_per_bet, feature_dimensionality, regime_count_or_parameter_count, window_schedule, generated_at, available_information_cutoff, random_seed, source_artifact_path, provenance_digest.
- **`P257ABaselineInput`** — baseline_id, lottery_type, target_draw_id, n_bet_count, source_artifact_path, baseline_digest.
- **`MatchedNullFamily`** — null_family_id, matched_lottery_type, matched_n_bet_count, matched_numbers_per_bet, matched_window_schedule, matched_feature_dimensionality, matched_regime_or_parameter_count, null_generation_seed, null_count, source_artifact_path.
- **`GateOutput`** — gate_decision (`GateStatus`), rejection_reasons, not_yet_rejected_reasons, paired_baseline_summary, null_percentile_summary, correction_family_summary, short_mid_long_summary, leakage_provenance_summary, audit_trail.

All are frozen dataclasses. No methods perform computation.

---

## Validation Stubs (`gate_validation.py`)

Each of the following **raises `NotImplementedError`** with a planning-only message — no real evaluation:

- `validate_candidate_provenance_contract`
- `validate_timestamp_cutoff_contract`
- `validate_p257a_baseline_contract`
- `validate_matched_null_family_contract`
- `validate_correction_family_contract`
- `validate_no_approval_status_contract`

---

## Proofs (verified by contract tests)

- **No executable gate** — no orchestrator/evaluator module; no function scores a candidate, generates nulls, computes p-values, or loops over draws. Only callables are stubs that immediately raise `NotImplementedError`.
- **No backtest** — no backtest loop, no strategy-execution function, no draw iteration.
- **No forbidden paths touched** — skeleton imports only stdlib (`dataclasses`, `enum`, `typing`) + intra-package `schemas`. Contract tests scan module source and assert no `db` / recommendation / registry / production / controlled_apply / deployment import substrings appear.

---

## Contract Tests Added

`tests/test_p258e_d3_gate_readonly_skeleton_contract_tests.py` — verifies enum values (and absence of approval values), stub `NotImplementedError`, import bans, absence of execution/backtest functions, and the artifact's no-approval / no-DB / no-accuracy-claim statements.

---

## Next Allowed Task: P258F

**P258F — D3 gate read-only CONTRACT VALIDATOR implementation only** (if explicitly authorized later).
- Implements the validation **stubs** as pure schema/contract checks **only** (field presence, timestamp ordering, N-bet matching).
- **Still no** scoring, null generation, paired tests, p-values, candidate evaluation, or backtest.
- Precondition: P258E merged **and** separate explicit authorization.

### Forbidden next tasks
- executable gate evaluation / backtest
- production integration
- recommendation mutation
- DB write
- treating `NOT_YET_REJECTED` as `APPROVED`

---

## Required Completion Check

1. **真的完成？** 是 — skeleton modules + JSON/MD artifact + contract tests.
2. **測試結果：** 見 `tests/test_p258e_d3_gate_readonly_skeleton_contract_tests.py`.
3. **仍卡住的唯一問題：** 無 — 等 P258F contract validator (separate explicit authorization).
4. **修改檔案：** `lottery_api/research/d3_gate/*`、`outputs/research/p258e_*`、`tests/test_p258e_*`、governance files.
5. **staged / commit / push：** file-by-file (no `git add -A`).
6. **是否允許進入下一輪：** 是 — P258F read-only contract validator implementation only.
7. **Final Classification：** `P258E_D3_READ_ONLY_SKELETON_CONTRACT_TESTS_READY`
