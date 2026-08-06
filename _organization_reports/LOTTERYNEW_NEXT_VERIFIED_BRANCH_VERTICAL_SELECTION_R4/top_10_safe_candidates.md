# Top Safe Migration Candidates (R4 Verified)

## 1. `cand_059_feat/p0_schema_stabilization_20260518` (Selected Winner)
- **Title**: P0 Schema Stabilization & Canonical Strategy Universe Inventory
- **Score**: 97/100
- **Source Ref**: `refs/heads/feat/p0-schema-stabilization-20260518`
- **Domain**: Replay / Strategy Universe / Schema Governance
- **Missing Target Paths**:
  - `scripts/p0_per_draw_coverage_matrix.py`
  - `tests/test_p0_canonical_universe.py`
  - `tests/test_p0_schema_migration_idempotent.py`
  - `docs/replay/p0_canonical_strategy_universe_20260518.md`
  - `docs/replay/p0_schema_diff_20260518.md`
  - `outputs/replay/p0_canonical_strategy_universe_20260518.json`
  - `outputs/replay/p0_migration_log_20260518.json`
  - `outputs/replay/p0_per_draw_coverage_matrix_20260518.json`
  - `outputs/replay/p0_schema_diff_20260518.json`
- **Focused Tests**:
  - `tests/test_p0_canonical_universe.py`
  - `tests/test_p0_schema_migration_idempotent.py`
- **Risk Level**: `LOW`
- **Estimated Completion**: 6 Hours
- **Justification**: Pure single vertical. Implements P0 schema stabilization and canonical strategy universe inventory. Zero production DB writes, zero dirty path collisions, clear unit tests, self-contained contract.

## 2. `cand_063_feat/p1_replay_lifecycle_formalization_20260517`
- **Title**: P1 Replay Lifecycle Formalization & Contract Definition
- **Score**: 92/100
- **Source Ref**: `refs/heads/feat/p1-replay-lifecycle-formalization-20260517`
- **Risk Level**: `LOW`
- **Reason**: Pure contract definition and fixture generator for replay lifecycle.

## 3. `cand_064_feat/p3_replay_pipeline_split_20260517`
- **Title**: P3 Replay Pipeline Split & Classifier Integration
- **Score**: 90/100
- **Source Ref**: `refs/heads/feat/p3-replay-pipeline-split-20260517`
- **Risk Level**: `LOW`
- **Reason**: Bounded pipeline split classifier for replay lifecycle.

## 4. `cand_065_feat/p5_replay_db_source_of_truth_20260517`
- **Title**: P5 Replay DB Source of Truth Audit Script
- **Score**: 88/100
- **Source Ref**: `refs/heads/feat/p5-replay-db-source-of-truth-20260517`
- **Risk Level**: `LOW`
- **Reason**: Audit script verifying replay database source of truth.

## 5. `cand_066_feat/p5a_replay_source_promotion_policy_20260517`
- **Title**: P5A Replay Source Promotion Policy Contract
- **Score**: 86/100
- **Source Ref**: `refs/heads/feat/p5a-replay-source-promotion-policy-20260517`
- **Risk Level**: `LOW`
- **Reason**: Promotion policy contract and unit tests.

## 6. `cand_058_feat/p0_replay_visual_reality_check_20260517`
- **Title**: P0 Replay Visual Reality Check & Audit Tooling
- **Score**: 84/100
- **Source Ref**: `refs/heads/feat/p0-replay-visual-reality-check-20260517`
- **Risk Level**: `LOW`
- **Reason**: Visual audit tooling for replay display semantics.

## 7. `cand_006_chore/p2_controlled_replay_backfill_dryrun_20260515`
- **Title**: P2 Controlled Replay Backfill Dryrun Tooling
- **Score**: 82/100
- **Source Ref**: `refs/heads/chore/p2-controlled-replay-backfill-dryrun-20260515`
- **Risk Level**: `LOW`
- **Reason**: Dryrun script for replay backfill validation.

## 8. `cand_004_chore/fix_drift_guard_test_fixtures_20260520`
- **Title**: Drift Guard Test Fixtures Repair
- **Score**: 80/100
- **Source Ref**: `refs/heads/chore/fix-drift-guard-test-fixtures-20260520`
- **Risk Level**: `LOW`
- **Reason**: Repair script for drift guard test fixtures.

## 9. `cand_005_chore/ingestion_pipeline_diagnostic_20260515`
- **Title**: Ingestion Pipeline Diagnostic Utility
- **Score**: 78/100
- **Source Ref**: `refs/heads/chore/ingestion-pipeline-diagnostic-20260515`
- **Risk Level**: `LOW`
- **Reason**: Diagnostic tool for data ingestion verification.

## 10. `cand_013_codex/p0_replay_lifecycle_browser_e2e_ci_enablement`
- **Title**: P0 Replay Lifecycle Browser E2E CI Enablement
- **Score**: 75/100
- **Source Ref**: `refs/heads/codex/p0-replay-lifecycle-browser-e2e-ci-enablement`
- **Risk Level**: `LOW`
- **Reason**: E2E test setup for browser replay lifecycle.
