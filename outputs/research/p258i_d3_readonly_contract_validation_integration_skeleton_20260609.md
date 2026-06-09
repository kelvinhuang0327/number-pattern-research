# P258I — D3 Read-Only Contract-Validation Integration Skeleton

**Date:** 2026-06-09
**Status:** SKELETON_ONLY
**Classification:** `P258I_D3_READ_ONLY_CONTRACT_VALIDATION_INTEGRATION_SKELETON_READY`

---

## Mandatory Safety Semantics

> **D3 is not a prediction model.**
> **Contract validation is not strategy evaluation.**
> **Passing contract validation does NOT imply improved prediction accuracy.**
> **NOT_YET_REJECTED is NOT approval.**
> **Passing validators does NOT allow production or recommendation use.**
> **P258I must not claim any lottery edge.**
> **P258I must not authorize executable gate evaluation.**

---

## Scope Declaration

P258I is a **skeleton / planning artifact only** task. Specifically:

- An integration skeleton module was created (`lottery_api/research/d3_gate/integration_skeleton.py`) containing only static metadata and non-executing stubs
- The executable runner stub (`run_contract_validation_flow`) raises `NotImplementedError` unconditionally
- No real candidate methods were used or run
- No executable gate evaluation was performed
- No null generation occurred
- No p-values were computed
- No paired tests or backtests were run
- No DB writes occurred
- No recommendation, production, registry, controlled_apply, or deployment paths were touched

---

## Integration Skeleton File Created

**`lottery_api/research/d3_gate/integration_skeleton.py`**

Contents:
- `VALIDATOR_INVOCATION_ORDER` — tuple of 6 metadata dicts (with callable references to the P258F validators)
- `ALLOWED_INPUT_CONTRACT_BOUNDARIES` — tuple of 5 metadata dicts
- `FAIL_CLOSED_POLICY` — dict with fail-closed semantics
- `FORBIDDEN_IMPORTS_AND_PATHS` — tuple of 13 forbidden import strings
- Safety semantic constants (`D3_IS_NOT_A_PREDICTION_MODEL`, `CONTRACT_VALIDATION_IS_NOT_STRATEGY_EVALUATION`, `NOT_YET_REJECTED_IS_NOT_APPROVAL`, etc.)
- `build_contract_validation_plan()` — returns static planning-only dict
- `run_contract_validation_flow()` — raises `NotImplementedError`

Allowed imports used:
- `lottery_api.research.d3_gate.gate_validation` (validators + `ContractValidationError`)
- `lottery_api.research.d3_gate.schemas` (schema classes)
- Python stdlib: `__future__`, `dataclasses`, `enum`, `typing`

---

## Validator Invocation Order

| Step | Validator | Input | Fail Behavior |
|------|-----------|-------|--------------|
| 1 | `validate_no_approval_status_contract` | `GateOutput` | `ContractValidationError` → blocks all |
| 2 | `validate_candidate_provenance_contract` | `CandidateInput` | `ContractValidationError` → blocks all |
| 3 | `validate_timestamp_cutoff_contract` | `CandidateInput` | `ContractValidationError` → blocks all |
| 4 | `validate_p257a_baseline_contract` | `CandidateInput` + `P257ABaselineInput` | `ContractValidationError` → blocks all |
| 5 | `validate_matched_null_family_contract` | `CandidateInput` + `MatchedNullFamily` | `ContractValidationError` → blocks all |
| 6 | `validate_correction_family_contract` | correction_family object | `ContractValidationError` → blocks all |

---

## Input/Output Contract Boundaries

### Allowed Inputs

| Contract | Schema Class | Key Constraint |
|----------|-------------|---------------|
| Candidate provenance | `CandidateInput` | Frozen OOS artifact only — not live DB |
| P257A baseline | `P257ABaselineInput` | lottery_type + target_draw_id + n_bet_count aligned to candidate |
| Matched-null metadata | `MatchedNullFamily` | Metadata alignment only — no null generation |
| Correction-family declaration | dict/dataclass | 6 required non-empty collection fields |
| Status/result | `GateOutput` | `gate_decision` ∈ {`REJECTED`, `NOT_YET_REJECTED`} only |

### Allowed Outputs

| Function | Output Type | Description |
|----------|------------|-------------|
| `build_contract_validation_plan()` | `dict` | Static planning metadata only — no evaluation |
| `run_contract_validation_flow()` | never returns | Always raises `NotImplementedError` |

---

## Fail-Closed Semantics

1. **Any `ContractValidationError` blocks further validation** — no catching and continuing.
2. **Failure cannot be converted to warning-only** — no `warnings.warn()` on `ContractValidationError`.
3. **`NOT_YET_REJECTED` remains not-approval** — never equivalent to `APPROVED`.

**Forbidden patterns:**
```python
# FORBIDDEN
try:
    validate_candidate_provenance_contract(candidate)
except ContractValidationError:
    pass                    # swallowed — forbidden

# FORBIDDEN
try:
    validate_timestamp_cutoff_contract(candidate)
except ContractValidationError as e:
    warnings.warn(str(e))  # downgraded — forbidden

# FORBIDDEN
if gate_output.gate_decision == GateStatus.NOT_YET_REJECTED:
    deploy_to_production()  # approval misinterpretation — forbidden
```

---

## Forbidden Imports and Paths

The integration skeleton must not import (confirmed clean in `integration_skeleton.py`):

- DB (any database module)
- recommendation logic
- production code paths
- registry mutation
- `controlled_apply`
- deployment paths
- backtest modules
- `null_factory` (not created)
- `gate_statistics` (not created)
- `gate_orchestrator` (not created)
- `random` (stdlib)
- `numpy`
- `scipy`

---

## Proof of Non-Implementation

| Claim | Status |
|-------|--------|
| Executable integration not implemented | ✓ `run_contract_validation_flow` raises `NotImplementedError` |
| `build_contract_validation_plan` returns static dict only | ✓ No evaluation, no I/O |
| No real candidate methods used | ✓ Confirmed |
| No executable gate evaluation | ✓ Confirmed |
| No null generation | ✓ Confirmed |
| No p-values / statistical tests / backtests | ✓ Confirmed |
| No DB / recommendation / production / registry / controlled_apply / deployment | ✓ Confirmed |
| Forbidden modules NOT created | ✓ `candidate_ingest.py`, `baseline_ingest.py`, `null_factory.py`, `gate_statistics.py`, `gate_orchestrator.py`, `gate_audit.py`, `integration_runner.py` — none created |

---

## Future Task Split

| Task | Authorized Scope |
|------|-----------------|
| **P258J** (next, requires separate explicit authorization) | Read-only synthetic integration skeleton tests / dry-contract fixtures only |
| Executable gate evaluation | FORBIDDEN — requires separate future task beyond P258J |
| Running D3 on real candidate methods | FORBIDDEN — requires separate future task beyond P258J |
| Null generation | FORBIDDEN |
| p-value / paired test / backtest | FORBIDDEN |
| DB / production / recommendation / registry | FORBIDDEN |

---

## Governance

- **Next authorized task:** P258J — read-only synthetic integration skeleton tests / dry-contract fixtures only (requires separate explicit authorization)
- **P258I scope:** Complete — skeleton and artifact only
