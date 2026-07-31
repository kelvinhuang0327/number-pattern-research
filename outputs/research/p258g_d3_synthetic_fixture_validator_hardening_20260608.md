# P258G - D3 Synthetic-Fixture-Only Contract Validator Hardening

**Date:** 2026-06-08
**Task:** `P258G`
**Type:** Type C small additive implementation - synthetic-fixture-only contract validator hardening
**Source decision:** `P258F_D3_READ_ONLY_CONTRACT_VALIDATORS_READY`
**Final Decision:** `P258G_D3_SYNTHETIC_FIXTURE_VALIDATOR_HARDENING_READY`

## Boundary

P258G is synthetic-fixture-only hardening.

- D3 is not a prediction model.
- Contract validation is not strategy evaluation.
- `NOT_YET_REJECTED` is not approval.
- Passing validators does not imply improved prediction accuracy.
- Passing validators does not allow production or recommendation use.
- No real candidate methods were used as fixture inputs.

## Synthetic Fixtures Added

The tests use synthetic literal builders only:

- `candidate_fixture`
- `baseline_fixture`
- `null_family_fixture`
- `correction_family_fixture`
- inline mutation helpers for missing-field and mismatch cases

These fixtures are intentionally not derived from real candidate methods or real strategy outputs.

## Edge Cases Hardened

Covered cases include:

- complete valid synthetic candidate/provenance contract
- missing required candidate fields
- invalid numeric candidate fields
- invalid timestamp ordering and format
- baseline alignment mismatches
- matched-null field omissions and mismatches
- null count and seed validation
- correction-family declaration omissions
- forbidden gate statuses
- allowed gate statuses remain exactly `REJECTED` and `NOT_YET_REJECTED`

## Validators Hardened

The following validators were hardened via synthetic fixture coverage:

- `validate_candidate_provenance_contract`
- `validate_timestamp_cutoff_contract`
- `validate_p257a_baseline_contract`
- `validate_matched_null_family_contract`
- `validate_correction_family_contract`
- `validate_no_approval_status_contract`

The validators remain pure/read-only. Success returns an immutable `ValidationResult`; failure raises `ContractValidationError`.

## Proofs

- **No real candidate methods used:** all fixtures are synthetic literals in tests.
- **No executable gate evaluation:** no orchestrator/evaluator module exists; validators inspect metadata only.
- **No null generation:** no null factory exists; null-related fields are declared only.
- **No p-values/statistical tests/backtests:** no p-value computation, paired test, bootstrap, draw loop, strategy execution, or backtest function exists.
- **No forbidden paths touched:** no DB, recommendation, registry, production, controlled_apply, deployment, backtest, fetcher, network, random, numpy, or scipy imports.

## Next Allowed Task

`P258H` - D3 read-only contract-validation integration plan only, if explicitly authorized later.

P258H may only plan how these synthetic-fixture validators would be wired into read-only validation flow. It may not run real candidate methods, evaluate the gate, generate nulls, compute p-values, run paired tests, backtest, write DB, mutate recommendations, or integrate with production.

## Forbidden Next Tasks

- executable gate evaluation/backtest
- running D3 on real candidate methods
- null generation
- p-value or paired statistical testing
- production integration
- recommendation mutation
- DB write
- treating `NOT_YET_REJECTED` as `APPROVED`

## Required Completion Check

1. Completed: yes - synthetic-fixture hardening tests, artifacts, and governance updates.
2. Tests: see `tests/test_p258g_d3_synthetic_fixture_validator_hardening.py`.
3. Blocking issue: none; P258H requires separate explicit authorization.
4. Modified files: P258G test/artifact files, governance files, and the P258E regression alignment file.
5. Staging/commit/push: file-by-file only; no broad add.
6. Next round allowed: yes, P258H read-only contract-validation integration plan only.
7. Final Classification: `P258G_D3_SYNTHETIC_FIXTURE_VALIDATOR_HARDENING_READY`
