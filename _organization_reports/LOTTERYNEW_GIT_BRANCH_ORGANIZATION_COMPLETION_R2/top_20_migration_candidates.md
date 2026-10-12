# Top 20 Functional Migration Candidates

Task ID: `LOTTERYNEW_GIT_BRANCH_ORGANIZATION_COMPLETION_R2`  
Location: `_organization_reports/LOTTERYNEW_GIT_BRANCH_ORGANIZATION_COMPLETION_R2/top_20_migration_candidates.md`

## Candidate List

### 1. [P0] Prize-Aware Inferential Validation Vertical (P273A) (`cand_087_p273a_prize_aware_inferential_validation`)

- **Representative Ref**: `refs/remotes/origin/task/p273a-prize-aware-inferential-validation`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: LOW
- **Reason Selected**: P273A is self-contained, target lacks inferential prize-aware validation module, clear tests exist, no DB write, <24h migration.
- **Missing Paths Count**: 12
- **Different Paths Count**: 11
- **Focused Test Paths**:
  - `tests/test_p257b_best_strategy_overview_readonly_api.py`
  - `tests/test_p261a_replay_detail_row_expand.py`
  - `tests/test_p354a_replay_lottery_type_query_normalization.py`
  - `tests/test_p355a_replay_detail_enum_query_normalization.py`
  - `tests/test_p360a_predraw_metadata_instrumentation.py`

---

### 2. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_002_biglotto_p0_2bet_two_id_target_native_vertical_r1`)

- **Representative Ref**: `refs/heads/task/biglotto-p0-2bet-two-id-target-native-vertical-r1`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 78
- **Different Paths Count**: 16
- **Focused Test Paths**:
  - `.claude/commands/backtest.md`
  - `research/p1_reproduction_environment_authority_r1/tests/test_environment_authority.py`
  - `research/p1_reproduction_environment_authority_r2/tests/test_environment_authority.py`
  - `research/p1_reproduction_environment_authority_r3/tests/test_environment_authority.py`
  - `tests/fixtures/biglotto_p0_2bet_parity.json`

---

### 3. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_075_p14b_biglotto_dry_run`)

- **Representative Ref**: `refs/heads/p14b-biglotto-dry-run`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 4
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `tests/test_p14b_biglotto_single_strategy_replay_dry_run.py`

---

### 4. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_076_p14c_biglotto_tempdb_rehearsal`)

- **Representative Ref**: `refs/heads/p14c-biglotto-tempdb-rehearsal`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 4
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `tests/test_p14c_biglotto_single_strategy_tempdb_rehearsal.py`

---

### 5. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_077_p14d_biglotto_production_readiness`)

- **Representative Ref**: `refs/heads/p14d-biglotto-production-readiness`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 6
- **Different Paths Count**: 6
- **Focused Test Paths**:
  - `tests/test_p14b_biglotto_single_strategy_replay_dry_run.py`
  - `tests/test_p14c_biglotto_single_strategy_tempdb_rehearsal.py`
  - `tests/test_p14d_biglotto_production_apply_readiness.py`
  - `tests/test_replay_branch_governance_guard.py`
  - `tests/test_replay_lifecycle_drift_guard.py`

---

### 6. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_078_p15_biglotto_replay_api_integration`)

- **Representative Ref**: `refs/heads/p15-biglotto-replay-api-integration`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 3
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `tests/test_p15_biglotto_replay_api_integration.py`

---

### 7. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_079_p16_biglotto_remaining_strategies_backfill`)

- **Representative Ref**: `refs/heads/p16-biglotto-remaining-strategies-backfill`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 10
- **Different Paths Count**: 8
- **Focused Test Paths**:
  - `tests/test_p14b_biglotto_single_strategy_replay_dry_run.py`
  - `tests/test_p14c_biglotto_single_strategy_tempdb_rehearsal.py`
  - `tests/test_p14d_biglotto_production_apply_readiness.py`
  - `tests/test_p15_biglotto_replay_api_integration.py`
  - `tests/test_p16_biglotto_remaining_strategies_backfill.py`

---

### 8. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_080_p17_biglotto_replay_timestamp_api`)

- **Representative Ref**: `refs/heads/p17-biglotto-replay-timestamp-api`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 3
- **Different Paths Count**: 1
- **Focused Test Paths**:
  - `tests/test_p17_biglotto_replay_timestamp_api.py`

---

### 9. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_093_p41_wave3_biglotto_adapter_bootstrap_planning`)

- **Representative Ref**: `refs/heads/p41-wave3-biglotto-adapter-bootstrap-planning`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 3
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `tests/test_p41_wave3_biglotto_adapter_bootstrap_planning.py`

---

### 10. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_094_p42_wave3_biglotto_dryrun_rehearsal`)

- **Representative Ref**: `refs/heads/p42-wave3-biglotto-dryrun-rehearsal`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 6
- **Different Paths Count**: 2
- **Focused Test Paths**:
  - `tests/test_p35_wave2_candidate_planning.py`
  - `tests/test_p41_wave3_biglotto_adapter_bootstrap_planning.py`
  - `tests/test_p42_wave3_biglotto_dryrun_rehearsal.py`

---

### 11. [P1] BigLotto Native Strategy & Vertical Adaptation (P541/P358) (`cand_095_p43_wave3_biglotto_production_apply`)

- **Representative Ref**: `refs/heads/p43-wave3-biglotto-production-apply`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: BigLotto historical strategy recovery vertical; requires catalog sync.
- **Missing Paths Count**: 4
- **Different Paths Count**: 5
- **Focused Test Paths**:
  - `tests/test_p42_wave3_biglotto_dryrun_rehearsal.py`
  - `tests/test_p43_wave3_biglotto_production_apply.py`
  - `tests/test_replay_branch_governance_guard.py`
  - `tests/test_replay_lifecycle_drift_guard.py`

---

### 12. [P2] Functional Vertical: P360A-PREDRAW-METADATA-INSTRUMENTATION (`cand_001_p360a_predraw_metadata_instrumentation`)

- **Representative Ref**: `refs/heads/feature/P360A-predraw-metadata-instrumentation`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 5
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `tests/test_p360a_predraw_metadata_instrumentation.py`

---

### 13. [P2] Functional Vertical: CEO-DECISION-AFTER-P66-2026-05-26 (`cand_003_ceo_decision_after_p66_2026_05_26`)

- **Representative Ref**: `refs/heads/ceo-decision-after-p66-2026-05-26`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 6157
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `.claude/commands/backtest.md`
  - `.claude/skills/backtest-framework/SKILL.md`
  - `ai_lab/automl_biglotto/backtest_engine.py`
  - `ai_lab/automl_biglotto/integration_test_report.json`
  - `archive/LATEST_PREDICTION_METHODS_2025.md`

---

### 14. [P2] Functional Vertical: CHORE/FIX-DRIFT-GUARD-TEST-FIXTURES-20260520 (`cand_004_chore/fix_drift_guard_test_fixtures_20260520`)

- **Representative Ref**: `refs/heads/chore/fix-drift-guard-test-fixtures-20260520`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 5918
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `.claude/commands/backtest.md`
  - `.claude/skills/backtest-framework/SKILL.md`
  - `ai_lab/automl_biglotto/backtest_engine.py`
  - `ai_lab/automl_biglotto/integration_test_report.json`
  - `archive/LATEST_PREDICTION_METHODS_2025.md`

---

### 15. [P2] Functional Vertical: CHORE/INGESTION-PIPELINE-DIAGNOSTIC-20260515 (`cand_005_chore/ingestion_pipeline_diagnostic_20260515`)

- **Representative Ref**: `refs/heads/chore/ingestion-pipeline-diagnostic-20260515`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 5733
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `.claude/commands/backtest.md`
  - `.claude/skills/backtest-framework/SKILL.md`
  - `ai_lab/automl_biglotto/backtest_engine.py`
  - `ai_lab/automl_biglotto/integration_test_report.json`
  - `archive/LATEST_PREDICTION_METHODS_2025.md`

---

### 16. [P2] Functional Vertical: CHORE/P2-CONTROLLED-REPLAY-BACKFILL-DRYRUN-20260515 (`cand_006_chore/p2_controlled_replay_backfill_dryrun_20260515`)

- **Representative Ref**: `refs/heads/chore/p2-controlled-replay-backfill-dryrun-20260515`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 5732
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - `.claude/commands/backtest.md`
  - `.claude/skills/backtest-framework/SKILL.md`
  - `ai_lab/automl_biglotto/backtest_engine.py`
  - `ai_lab/automl_biglotto/integration_test_report.json`
  - `archive/LATEST_PREDICTION_METHODS_2025.md`

---

### 17. [P2] Functional Vertical: CHORE/P2C-DRAW-115000051-WATCHER-20260515 (`cand_007_chore/p2c_draw_115000051_watcher_20260515`)

- **Representative Ref**: `refs/heads/chore/p2c-draw-115000051-watcher-20260515`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 2
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - None explicitly matched

---

### 18. [P2] Functional Vertical: CHORE/P2C-TS3-REGIME-READINESS-20260515 (`cand_008_chore/p2c_ts3_regime_readiness_20260515`)

- **Representative Ref**: `refs/heads/chore/p2c-ts3-regime-readiness-20260515`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 2
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - None explicitly matched

---

### 19. [P2] Functional Vertical: CODEX/DAILY-ENGINEERING-HANDOFF-20260509 (`cand_009_codex/daily_engineering_handoff_20260509`)

- **Representative Ref**: `refs/heads/codex/daily-engineering-handoff-20260509`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 1
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - None explicitly matched

---

### 20. [P2] Functional Vertical: CODEX/FINAL-DAILY-ENGINEERING-HANDOFF-20260509 (`cand_010_codex/final_daily_engineering_handoff_20260509`)

- **Representative Ref**: `refs/heads/codex/final-daily-engineering-handoff-20260509`
- **Source Repository**: `repo_1_lotterynew`
- **Migration Risk**: MEDIUM
- **Reason Selected**: Requires cross-layer integration and test suite review.
- **Missing Paths Count**: 1
- **Different Paths Count**: 0
- **Focused Test Paths**:
  - None explicitly matched

---

