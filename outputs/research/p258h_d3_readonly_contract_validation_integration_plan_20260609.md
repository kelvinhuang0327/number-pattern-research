# P258H — D3 Read-Only Contract-Validation Integration Plan

**Date:** 2026-06-09
**Status:** PLAN_ONLY
**Classification:** `P258H_D3_READ_ONLY_CONTRACT_VALIDATION_INTEGRATION_PLAN_READY`

---

## Mandatory Safety Semantics

> **D3 is not a prediction model.**
> **Contract validation is not strategy evaluation.**
> **Passing contract validation does NOT imply improved prediction accuracy.**
> **NOT_YET_REJECTED is NOT approval.**
> **Passing validators does NOT allow production or recommendation use.**
> **P258H must not claim any lottery edge.**
> **P258H must not authorize implementation beyond future skeleton planning.**

---

## Scope Declaration

P258H is a **plan and artifact only** task. No implementation code was created. Specifically:

- No real candidate methods were used or run
- No executable gate evaluation was performed
- No null generation occurred
- No p-values were computed
- No paired tests or backtests were run
- No DB writes occurred
- No recommendation, production, registry, controlled_apply, or deployment paths were touched

---

## Predecessor State

| Task | Classification | Key Output |
|------|---------------|------------|
| P258E | `P258E_D3_READ_ONLY_SKELETON_CONTRACT_TESTS_READY` | `d3_gate/schemas.py` with `GateStatus`, `CandidateInput`, `P257ABaselineInput`, `MatchedNullFamily`, `GateOutput` |
| P258F | `P258F_D3_READ_ONLY_CONTRACT_VALIDATORS_READY` | `d3_gate/gate_validation.py` with 6 validators |
| P258G | `P258G_D3_SYNTHETIC_FIXTURE_VALIDATOR_HARDENING_READY` | Synthetic fixture hardening — no real methods used |

---

## Integration Flow Placement

Contract validation sits **before** any gate evaluation in a future read-only D3 flow:

```
Step 1 (P258H scope — READY):
  ┌─────────────────────────────────────────────┐
  │  Contract Validation (metadata guard)        │
  │  Validates all 5 input contracts             │
  │  Fail-closed — ContractValidationError stops │
  └─────────────────────────────────────────────┘
           ↓ (only if all contracts valid)

Step 2 (STOP — requires future authorization):
  Candidate method execution

Step 3 (STOP — requires future authorization):
  Null generation

Step 4 (STOP — requires future authorization):
  Gate statistics / p-values

Step 5 (STOP — requires future authorization):
  Paired test / backtest
```

**Rationale:** Contract validation is a pure metadata guard. Running it first ensures that no downstream statistical computation is attempted with a malformed or policy-violating object.

---

## Allowed Input Contract Boundaries

### 1. Candidate Provenance Contract (`CandidateInput`)

| Field | Type | Constraint |
|-------|------|------------|
| `candidate_id` | str | non-empty |
| `lottery_type` | str | non-empty |
| `target_draw_id` | str | non-empty |
| `target_draw_date` | str | ISO temporal |
| `n_bet_count` | int | > 0 |
| `numbers_per_bet` | int | > 0 |
| `feature_dimensionality` | int | > 0 |
| `regime_count_or_parameter_count` | int | > 0 |
| `window_schedule` | str | non-empty |
| `generated_at` | str | ISO temporal |
| `available_information_cutoff` | str | ISO temporal, < target_draw_date |
| `random_seed` | int | any int |
| `source_artifact_path` | str | non-empty |
| `provenance_digest` | str | non-empty |

**Source requirement:** Frozen OOS artifact — must not be derived from live DB at validation time.

### 2. P257A Baseline Contract (`P257ABaselineInput`)

| Field | Type | Alignment |
|-------|------|-----------|
| `baseline_id` | str | non-empty |
| `lottery_type` | str | must match `CandidateInput.lottery_type` |
| `target_draw_id` | str | must match `CandidateInput.target_draw_id` |
| `n_bet_count` | int | must match `CandidateInput.n_bet_count` |
| `source_artifact_path` | str | non-empty |
| `baseline_digest` | str | non-empty |

### 3. Matched-Null Metadata Contract (`MatchedNullFamily`)

| Field | Type | Alignment |
|-------|------|-----------|
| `null_family_id` | str | non-empty |
| `matched_lottery_type` | str | must match `CandidateInput.lottery_type` |
| `matched_n_bet_count` | int | must match `CandidateInput.n_bet_count` |
| `matched_numbers_per_bet` | int | must match `CandidateInput.numbers_per_bet` |
| `matched_window_schedule` | str | must match `CandidateInput.window_schedule` |
| `matched_feature_dimensionality` | int | must match `CandidateInput.feature_dimensionality` |
| `matched_regime_or_parameter_count` | int | must match `CandidateInput.regime_count_or_parameter_count` |
| `null_generation_seed` | int | any int |
| `null_count` | int | > 0 |
| `source_artifact_path` | str | non-empty |

**Important:** This validates metadata alignment only. No nulls are generated.

### 4. Correction-Family Declaration Contract

| Field | Type | Constraint |
|-------|------|-----------|
| `candidate_methods` | collection | non-empty |
| `null_variants` | collection | non-empty |
| `lottery_types` | collection | non-empty |
| `n_bet_counts` | collection | non-empty |
| `metrics` | collection | non-empty |
| `windows` | collection | non-empty |

**Important:** Declares family membership only — does not compute corrections.

### 5. Status/Result Contract (`GateOutput`)

| Field | Allowed Values |
|-------|---------------|
| `gate_decision` | `GateStatus.REJECTED` or `GateStatus.NOT_YET_REJECTED` |

**Forbidden values:** `APPROVED`, `PROMOTED`, `PRODUCTION_READY`, `RECOMMENDED`

`GateStatus` enum is sealed — no new values may be added without explicit authorization.

---

## Validator Invocation Order

Validators must run in this order. Any `ContractValidationError` is immediately fatal — later validators are not run.

| Step | Validator | Input | Purpose |
|------|-----------|-------|---------|
| 1 | `validate_no_approval_status_contract` | `GateOutput` | Block forbidden approval tokens first |
| 2 | `validate_candidate_provenance_contract` | `CandidateInput` | All required fields present and non-empty |
| 3 | `validate_timestamp_cutoff_contract` | `CandidateInput` | Cutoff < draw_date AND cutoff <= generated_at |
| 4 | `validate_p257a_baseline_contract` | `CandidateInput` + `P257ABaselineInput` | Baseline aligned to candidate by lottery/draw/N-bet |
| 5 | `validate_matched_null_family_contract` | `CandidateInput` + `MatchedNullFamily` | Null metadata aligned to candidate on 6 dimensions |
| 6 | `validate_correction_family_contract` | correction_family object | All 6 collection fields non-empty |

**Ordering rationale:**
- Step 1 runs first so that a partial GateOutput with a forbidden approval token is caught before any candidate data is examined.
- Steps 2–3 confirm candidate completeness and leakage safety before alignment checks.
- Steps 4–5 require a valid candidate object (guaranteed by steps 2–3) before checking cross-object alignment.
- Step 6 is independent of the candidate but runs last as it depends on the correction family having been declared after all candidate metadata is confirmed.

---

## Fail-Closed Behavior

1. **Any `ContractValidationError` blocks further validation** — no catching and continuing.
2. **Failure cannot be converted into warning-only** — no `warnings.warn()` on ContractValidationError.
3. **`NOT_YET_REJECTED` remains not-approval** — it is not equivalent to `APPROVED`.

### Forbidden Patterns

```python
# FORBIDDEN — do not catch and continue
try:
    validate_candidate_provenance_contract(candidate)
except ContractValidationError:
    pass  # This is a forbidden pattern

# FORBIDDEN — do not convert to warning
try:
    validate_timestamp_cutoff_contract(candidate)
except ContractValidationError as e:
    warnings.warn(str(e))  # This is a forbidden pattern

# FORBIDDEN — treating NOT_YET_REJECTED as approval
if gate_output.gate_decision == GateStatus.NOT_YET_REJECTED:
    deploy_to_production()  # This is a forbidden pattern
```

---

## Future Validation Report Schema

A future P258I integration skeleton would produce a report with this schema:

```json
{
  "validation_scope": "string — identifies which contracts were in scope",
  "validators_run": ["list of validator function names, in invocation order"],
  "validation_results": [
    {
      "validator": "string",
      "checked_fields": ["list of field names checked"]
    }
  ],
  "failures": [
    {
      "validator": "string",
      "error": "ContractValidationError message"
    }
  ],
  "forbidden_actions_confirmed": [
    "no null generation",
    "no p-value computation",
    "no DB write",
    "no recommendation change",
    "no production change"
  ],
  "final_contract_status": "ALL_CONTRACTS_VALID | CONTRACT_VALIDATION_FAILED",
  "no_approval_semantics": true
}
```

### Invariants

- `final_contract_status == "ALL_CONTRACTS_VALID"` does **not** imply approval
- `final_contract_status == "ALL_CONTRACTS_VALID"` does **not** imply improved prediction accuracy
- `final_contract_status == "ALL_CONTRACTS_VALID"` does **not** allow production or recommendation use
- `no_approval_semantics` must be `true` in every report
- `failures` must be non-empty when `final_contract_status == "CONTRACT_VALIDATION_FAILED"`

---

## Allowed Import Boundary Plan

### Future integration may import (only):
- `lottery_api.research.d3_gate.schemas`
- `lottery_api.research.d3_gate.gate_validation`

### Future integration must NOT import:
- Any database module
- Any recommendation logic module
- Any production code path
- Any strategy registry module
- `controlled_apply` (any module)
- Any deployment path module
- Any backtest module
- `null_factory` (not created)
- `gate_statistics` (not created)
- `gate_orchestrator` (not created)
- `random` (stdlib — no randomness in contract validation)
- `numpy` (no statistical computation)
- `scipy` (no statistical computation)

---

## STOP Gates for Future Implementation

| Gate | Condition | Status |
|------|-----------|--------|
| STOP-1 | Real candidate methods required | FORBIDDEN — separate task + explicit authorization |
| STOP-2 | Executable gate evaluation required | FORBIDDEN — `gate_statistics`, `gate_orchestrator`, `integration_runner` not created |
| STOP-3 | Null generation required | FORBIDDEN — `null_factory` not created |
| STOP-4 | p-value or statistical computation required | FORBIDDEN — no numpy/scipy in contract validation |
| STOP-5 | Paired test or backtest required | FORBIDDEN — no backtest execution in P258H |
| STOP-6 | DB / recommendation / production / registry / controlled_apply / deployment required | FORBIDDEN — all such paths forbidden in P258 arc |
| STOP-7 | `NOT_YET_REJECTED` treated as `APPROVED` | FATAL POLICY VIOLATION — `GateStatus` has no `APPROVED` value |

---

## Forbidden Modules (Confirmed Not Created in P258H)

- `candidate_ingest.py`
- `baseline_ingest.py`
- `null_factory.py`
- `gate_statistics.py`
- `gate_orchestrator.py`
- `gate_audit.py`
- `integration_runner.py`

---

## Future Task Split

| Task | Authorized Scope |
|------|-----------------|
| **P258I** (next, requires separate explicit authorization) | Read-only contract-validation integration skeleton only — may import `schemas.py` and `gate_validation.py`, invoke validators in specified order; no executable gate, no nulls, no real candidates, no statistical computation |
| Executable gate evaluation | FORBIDDEN — requires separate future task beyond P258I and explicit authorization |
| Running D3 on real candidate methods | FORBIDDEN — requires separate future task beyond P258I and explicit authorization |

---

## Governance

- **Next authorized task:** P258I — read-only contract-validation integration skeleton only (requires separate explicit authorization)
- **P258H scope:** Complete — plan and artifact only
- **Merge status:** To be determined by CI
