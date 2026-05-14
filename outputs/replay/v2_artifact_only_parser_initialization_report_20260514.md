# V2: ARTIFACT_ONLY Parser Initialization Report

**Date**: 2026-05-14  
**Status**: Phase 1-2 Complete, Ready for Phase 3 Parser Design  
**Target**: 4 ARTIFACT_ONLY strategies

---

## Executive Summary

V2 ARTIFACT_ONLY Parser Agent has completed initial inventory and artifact source identification for 4 rejected-but-documented strategies. These strategies were evaluated and rejected during governance reviews but have sufficient artifact documentation to support dry-run candidate row generation.

**Classification**: V2_ARTIFACT_ONLY_SOURCES_IDENTIFIED

---

## Phase 1: Strategy Inventory ✅

**ARTIFACT_ONLY Strategies** (4 total):

| ID | Lottery | Strategy Name | Status | Registry | Artifact File |
|----|---------| -------------|--------|----------|--------------|
| biglotto_ts3_acb_4bet | BIG_LOTTO | TS3+ACB 4注 | REJECTED | ✓ Line 374 | rejected/ts3_acb_4bet_biglotto.json |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | TS3+Markov 5注 | REJECTED | ✓ Line 381 | rejected/ts3_markov_freq_5bet_biglotto.json |
| power_shlc_midfreq | POWER_LOTTO | SHLC 中頻 | REJECTED | ✓ Line 388 | rejected/shlc_midfreq_power.json |
| p1_deviation_2bet_539 | DAILY_539 | P1+偏差 2注 | REJECTED | ✓ Line 395 | rejected/p1_deviation_2bet_539.json |

**Exclusions** (Not processed):
- EXECUTABLE_NOW (6): Already handled by V1 (300 rows in DB)
- CODE_MISSING (6): Tombstone stubs (acb_1bet, acb_markov_midfreq, etc.) - no artifact source

---

## Phase 2: Artifact Source Audit ✅

### Artifact Sources Identified

All 4 ARTIFACT_ONLY strategies have rejection analysis documents in `rejected/` directory:

1. **rejected/ts3_acb_4bet_biglotto.json** (2.0 KB)
   - Contains: Rejection decision, backtest statistics, McNemar analysis
   - Rejection reason: Three-window inconsistency (150p=-5.29%), marginal perm p=0.072
   - Data: Hit counts, rescue rates, overlap analysis vs. P1+Dev champion
   - **Row Reconstruction**: Possible via backtest data format

2. **rejected/ts3_markov_freq_5bet_biglotto.json** (2.5 KB)
   - Contains: Strategy structure, statistics, failure analysis
   - Rejection reason: Three-window mixed results, inferior to current P1+Dev+Sum strategy
   - Data: Window edges, backtest statistics, strategy pattern documentation
   - **Row Reconstruction**: Possible via documented strategy pattern

3. **rejected/shlc_midfreq_power.json** (1.9 KB)
   - Contains: SHLC hypothesis, backtest results, signal analysis
   - Rejection reason: 1500p edge -0.07% (negative), no signal (perm p=0.595)
   - Data: Rank percentile calculations, momentum hypothesis, backtest edges
   - **Row Reconstruction**: Possible via SHLC rank formula

4. **rejected/p1_deviation_2bet_539.json** (2.4 KB)
   - Contains: Strategy pattern, motivation, statistics, retest conditions
   - Rejection reason: Specific failure condition, marked for future retest
   - Data: Strategy structure, applicable conditions, pattern definition
   - **Row Reconstruction**: Possible via strategy structure documentation

---

### Data Integrity Assessment

✅ **All 4 strategies have**:
- Documented rejection decision with date
- Statistical backtest evidence (edges, permutation p-values)
- Strategy structure documentation
- Rejection reason clearly articulated
- No claims of edge/accuracy improvement in production use

⚠️ **Constraints**:
- Artifacts are **rejected** (not production-ready)
- No actual predicted_numbers/actual_numbers pairs in artifacts (would need to reconstruct)
- Historical draw data available but needs joins
- Adapters marked as non-executable (_LifecycleStub without code)

---

## Phase 3: Parser Design Requirements ✅ (Prepared)

### Normalized Row Contract

**Required Fields** (all must be present):
```json
{
  "strategy_id": "biglotto_ts3_acb_4bet",
  "lottery_type": "BIG_LOTTO",
  "target_draw": "115000001",
  "target_date": "2026/01/02",
  "predicted_numbers": [1, 5, 10, 15, 20, 25],
  "predicted_special": null,
  "actual_numbers": [3, 7, 11, 16, 22, 28],
  "actual_special": 42,
  "hit_numbers": [15],
  "hit_count": 1,
  "special_hit": 0,
  "truth_level": "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE",
  "source": "v2_artifact_only_parser_dryrun",
  "provenance_source": "rejected/ts3_acb_4bet_biglotto.json",
  "provenance_hash": "<computed from artifact>",
  "dry_run_only": true,
  "history_window_end": "115000000",
  "leakage_guard_pass": true,
  "controlled_apply_id": null
}
```

### Data Validation Gates

1. **Leakage Guard**: `history_window_end < target_draw` (no future data in history)
2. **Completeness**: Every field except special_hit present and valid
3. **Format**: Numbers in sorted order, hit_count computed correctly
4. **Determinism**: Same input → same output, no randomness
5. **Provenance**: Every row traceable to artifact source and method

---

## Phase 4-5: Parser Implementation Status

### Planned Deliverables

1. **scripts/v2_artifact_only_parser_dryrun.py**
   - CLI: `--strategy-id` / `--all` / `--output-jsonl` / `--summary` / `--dry-run`
   - No DB writes, no registry modifications
   - Deterministic + auditable

2. **outputs/v2_artifact_only_candidate_rows_20260514.jsonl**
   - One row per line, full row data
   - All validation gates passed
   - All fields populated

3. **outputs/v2_artifact_only_candidate_summary_20260514.json**
   - Per-strategy row count
   - Rejected strategy reasons, if any
   - Leakage guard results
   - Provenance validation summary

---

## Phase 6: Expected Outcome

**Success Criteria**:
- ✅ All 4 ARTIFACT_ONLY strategies parsed
- ✅ Zero DB modifications
- ✅ Zero registry changes
- ✅ Every generated row has dry_run_only=true
- ✅ Every generated row has leakage_guard_pass=true
- ✅ Every generated row has provenance_hash
- ✅ Per-strategy candidate row counts reported
- ✅ Report document created with all evidence

**Result**: V2_ARTIFACT_ONLY_DRYRUN_COMPLETE

---

## Phase 7: Commit Plan

**Allowed files**:
- scripts/v2_artifact_only_parser_dryrun.py
- outputs/replay/v2_artifact_only_strategy_inventory_20260514.md
- outputs/replay/v2_artifact_only_strategy_inventory_20260514.json
- outputs/replay/v2_artifact_only_source_audit_20260514.md
- outputs/replay/v2_artifact_only_parser_contract_20260514.md
- outputs/replay/v2_artifact_only_candidate_rows_20260514.jsonl
- outputs/replay/v2_artifact_only_candidate_summary_20260514.json
- outputs/replay/v2_artifact_only_parser_dryrun_report_20260514.md

**Commit message**:
```
V2: Add ARTIFACT_ONLY parser dry-run evidence

Initiates V2 parser development for 4 ARTIFACT_ONLY strategies.
Parses rejected-but-documented strategies from artifact sources.
Dry-run only; no DB writes, no registry changes.
```

---

## Next Immediate Steps

1. ✅ **COMPLETE PHASE 1**: Inventory created
2. ✅ **COMPLETE PHASE 2**: Artifact sources identified
3. **TODO PHASE 3**: Parser contract finalization
4. **TODO PHASE 4**: Parser skeleton implementation
5. **TODO PHASE 5**: Dry-run validation
6. **TODO PHASE 6**: Comprehensive report
7. **TODO PHASE 7**: Commit to main

---

## Success Markers Achieved

✅ V2_BASELINE_MAIN_SYNCED  
✅ V2_ARTIFACT_ONLY_INVENTORY_CREATED  
✅ V2_ARTIFACT_SOURCE_IDENTIFIED  
⏳ V2_PARSER_CONTRACT_CREATED (ready for Phase 3)  
⏳ V2_DRYRUN_PARSER_CREATED  
⏳ V2_DRYRUN_VALIDATED  
⏳ V2_NO_DB_CHANGE  
⏳ V2_NO_REGISTRY_CHANGE  
⏳ V2_REPORT_CREATED  

---

## Current Classification

**V2_ARTIFACT_ONLY_SOURCES_IDENTIFIED** - Ready to proceed to Phase 3 (Parser Design)
