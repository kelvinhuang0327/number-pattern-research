# P258F - D3 Read-Only Contract Validators

**Date:** 2026-06-08
**Task:** `P258F`
**Type:** Type C small implementation - read-only contract validators only
**Source decision:** `P258E_D3_READ_ONLY_SKELETON_CONTRACT_TESTS_READY`
**Final Decision:** `P258F_D3_READ_ONLY_CONTRACT_VALIDATORS_READY`

## Mandatory Boundary

P258F is **contract validation only**.

D3 `AdversarialNullSurvivorGate` remains a validation/adversarial-null contract boundary, not a prediction model.

- Contract validation is not strategy evaluation.
- Passing validators does not imply improved prediction accuracy.
- `NOT_YET_REJECTED` is not approval.
- Passing validators does not allow production, registry, recommendation, controlled_apply, deployment, or DB use.
- P258F does not run D3 on real candidate methods.

## Validators Implemented

Implemented in `lottery_api/research/d3_gate/gate_validation.py`:

- `validate_candidate_provenance_contract`
- `validate_timestamp_cutoff_contract`
- `validate_p257a_baseline_contract`
- `validate_matched_null_family_contract`
- `validate_correction_family_contract`
- `validate_no_approval_status_contract`

Each validator is pure/read-only. Success returns an immutable `ValidationResult`; failure raises `ContractValidationError`.

## Validation Semantics

Successful validation means only that a provided contract object is structurally complete and internally aligned. It is not gate survival, not candidate scoring, not approval, not production readiness, not recommendation permission, and not an accuracy claim.

Implemented checks:

- Candidate/provenance: required fields, positive N-bet count, positive numbers per bet, positive feature/parameter counts, integer random seed.
- Timestamp cutoff: cutoff parses, cutoff is not after `generated_at`, and cutoff precedes `target_draw_date`.
- P257A baseline: required fields and `(lottery_type, target_draw_id, n_bet_count)` alignment.
- Matched null family: required dimensions and matching lottery/N/numbers/window/feature/parameter metadata; `null_count` is positive; seed is declared but not used.
- Correction family: candidate methods, null variants, lottery types, N values, metrics, and windows are all declared.
- Approval safety: `GateStatus` remains exactly `REJECTED` and `NOT_YET_REJECTED`; `APPROVED`, `PROMOTED`, `PRODUCTION_READY`, and `RECOMMENDED` are rejected.

## Proofs

- **No executable gate evaluation:** no orchestrator/evaluator module exists; validators inspect metadata only.
- **No null generation:** no null factory exists; `null_generation_seed` is checked only as declared metadata.
- **No p-values/statistical tests/backtests:** no p-value computation, paired test, bootstrap, McNemar test, draw loop, strategy execution, or backtest function exists.
- **No forbidden paths touched:** validators import only stdlib helpers and local schemas. No DB, recommendation, registry, production, controlled_apply, deployment, backtest, fetcher, network, random, numpy, or scipy imports.

## Next Allowed Task

`P258G` - D3 synthetic-fixture-only contract validator hardening, if explicitly authorized later.

P258G may add more synthetic fixtures and edge-case hardening only. It may not run real candidate methods, evaluate the gate, generate nulls, compute p-values, run paired tests, backtest, write DB, mutate recommendations, or integrate with production.

## Forbidden Next Tasks

- executable gate evaluation/backtest
- running D3 on real candidate methods
- production integration
- recommendation mutation
- DB write
- treating `NOT_YET_REJECTED` as `APPROVED`

## Required Completion Check

1. Completed: yes - read-only contract validators, tests, and artifacts.
2. Tests: see `tests/test_p258f_d3_readonly_contract_validators.py`.
3. Blocking issue: none; P258G requires separate explicit authorization.
4. Modified files: validator module, P258F artifacts, P258F tests, narrow P258E test alignment, governance files.
5. Staging/commit/push: file-by-file only; no broad add.
6. Next round allowed: yes, P258G synthetic-fixture-only contract validator hardening.
7. Final Classification: `P258F_D3_READ_ONLY_CONTRACT_VALIDATORS_READY`
