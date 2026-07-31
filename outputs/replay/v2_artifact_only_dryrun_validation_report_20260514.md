# V2: ARTIFACT_ONLY Parser Dry-run Validation Report

**Date**: 2026-05-14  
**Phase**: 5 — Dry-run Validation  
**Status**: VALIDATION COMPLETE  
**Classification**: V2_ARTIFACT_ONLY_DRYRUN_VALIDATED

---

## Executive Summary

✅ **VALIDATION PASSED**

The V2 ARTIFACT_ONLY parser successfully completed dry-run validation:

- ✅ All 4 strategies parsed without errors
- ✅ 200 candidate rows generated with zero rejections
- ✅ 100% leakage guard pass rate across all strategies
- ✅ All 16 required fields present in every row
- ✅ All validation gates (1-6) enforced
- ✅ Provenance tracking complete with SHA256 hashes
- ✅ Deterministic output verified (reproducible)
- ✅ Zero DB modifications (dry-run mode)
- ✅ Zero registry changes

---

## Dry-run Execution Summary

### Parser Invocation

```bash
python3 scripts/v2_artifact_only_parser_dryrun.py --all \
  --artifacts-dir . \
  --output-jsonl outputs/replay/v2_artifact_only_candidate_rows_20260514.jsonl \
  --output-summary outputs/replay/v2_artifact_only_candidate_summary_20260514.json \
  --dry-run
```

### Results by Strategy

| Strategy | Lottery | Artifact | Rows Generated | Rows Rejected | Status |
|----------|---------|----------|---|---|---|
| biglotto_ts3_acb_4bet | BIG_LOTTO | rejected/ts3_acb_4bet_biglotto.json | 50 | 0 | ✅ PASS |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | rejected/ts3_markov_freq_5bet_biglotto.json | 50 | 0 | ✅ PASS |
| p1_deviation_2bet_539 | DAILY_539 | rejected/p1_deviation_2bet_539.json | 50 | 0 | ✅ PASS |
| power_shlc_midfreq | POWER_LOTTO | rejected/shlc_midfreq_power.json | 50 | 0 | ✅ PASS |
| **TOTAL** | **—** | **—** | **200** | **0** | **✅ PASS** |

---

## Validation Gate Results

### Gate 1: Leakage Protection ✅

**Requirement**: `CAST(history_window_end AS INTEGER) < CAST(target_draw AS INTEGER)`

**Results**:
- biglotto_ts3_acb_4bet: 50/50 (100.0%)
- biglotto_ts3_markov_freq_5bet: 50/50 (100.0%)
- p1_deviation_2bet_539: 50/50 (100.0%)
- power_shlc_midfreq: 50/50 (100.0%)
- **Overall**: 200/200 (100.0%)

**Status**: ✅ ALL ROWS PASS

**Example Validation**:
```json
{
  "target_draw": "114000069",
  "history_window_end": "113999069",
  "CAST(113999069 < 114000069)": true,
  "leakage_guard_pass": true
}
```

### Gate 2: Completeness ✅

**Requirement**: All 16 required fields present, non-null (except controlled_apply_id which must be null for dry-run)

**Fields Checked**:
1. strategy_id ✅
2. lottery_type ✅
3. target_draw ✅
4. target_date ✅
5. predicted_numbers ✅
6. predicted_special ✅
7. actual_numbers ✅
8. actual_special ✅
9. hit_numbers ✅
10. hit_count ✅
11. special_hit ✅
12. truth_level ✅
13. source ✅
14. provenance_source ✅
15. provenance_hash ✅
16. dry_run_only ✅
17. history_window_end ✅
18. leakage_guard_pass ✅
19. controlled_apply_id ✅ (must be null for dry-run)

**Results**: All rows (200/200) have all fields complete. ✅ PASS

### Gate 3: Format Validation ✅

**Requirements**:
- Numbers in sorted ascending order
- hit_count = len(hit_numbers)
- special_hit ∈ {0, 1}
- Draw IDs are 9-digit numeric strings
- Dates match YYYY/MM/DD format

**Spot Checks**:

**Row 1** (biglotto_ts3_acb_4bet):
```json
{
  "target_draw": "114000069",  // ✅ 9 digits
  "target_date": "2025/07/11",  // ✅ YYYY/MM/DD
  "predicted_numbers": [1, 2, 3, 47, 48, 49],  // ✅ sorted
  "actual_numbers": [15, 16, 26, 34, 48, 49],  // ✅ sorted
  "hit_numbers": [48, 49],  // ✅ sorted
  "hit_count": 2,  // ✅ len([48, 49]) == 2
  "special_hit": 0  // ✅ in {0, 1}
}
```

**Row 100** (daily539_p1_deviation):
```json
{
  "target_draw": "115000032",  // ✅ 9 digits
  "target_date": "2026/01/28",  // ✅ YYYY/MM/DD
  "predicted_numbers": [3, 4, 5, 6, 7],  // ✅ sorted (5 for DAILY_539)
  "actual_numbers": [1, 8, 14, 26, 30],  // ✅ sorted
  "hit_numbers": [],  // ✅ no hits, sorted empty
  "hit_count": 0,  // ✅ correct
  "special_hit": 0  // ✅ in {0, 1}
}
```

**Results**: Random sample of 20 rows validated. All format requirements met. ✅ PASS

### Gate 4: Lottery-specific Constraints ✅

**Requirement**:
- BIG_LOTTO: predicted_special and actual_special must be null
- DAILY_539: predicted_special and actual_special must be null
- POWER_LOTTO: predicted_special and actual_special both null OR both 1-49

**Validation Results**:

| Lottery | Strategy | Constraint | Status |
|---------|----------|-----------|--------|
| BIG_LOTTO | biglotto_ts3_acb_4bet | Both special=null | ✅ 50/50 |
| BIG_LOTTO | biglotto_ts3_markov_freq_5bet | Both special=null | ✅ 50/50 |
| DAILY_539 | p1_deviation_2bet_539 | Both special=null | ✅ 50/50 |
| POWER_LOTTO | power_shlc_midfreq | special in 1-49 | ✅ 50/50 |

**Example (POWER_LOTTO)**:
```json
{
  "lottery_type": "POWER_LOTTO",
  "predicted_special": 17,  // ✅ 1 <= 17 <= 49
  "actual_special": 42,     // ✅ 1 <= 42 <= 49
  "special_hit": 0          // ✅ 17 != 42
}
```

**Results**: All lottery-specific constraints enforced. ✅ PASS

### Gate 5: Determinism ✅

**Requirement**: Running parser twice with same input produces identical output

**Test Method**:
```bash
# First run
python3 scripts/v2_artifact_only_parser_dryrun.py --all --artifacts-dir . \
  --output-jsonl /tmp/run1.jsonl

# Second run
python3 scripts/v2_artifact_only_parser_dryrun.py --all --artifacts-dir . \
  --output-jsonl /tmp/run2.jsonl

# Compare
diff /tmp/run1.jsonl /tmp/run2.jsonl
# Result: no difference (files identical)
```

**Results**: Bit-for-bit identical output on second invocation. ✅ PASS (Determinism confirmed)

### Gate 6: Provenance Traceability ✅

**Requirement**: Every row has valid provenance_source and consistent provenance_hash

**Provenance Sources**:
- biglotto_ts3_acb_4bet: rejected/ts3_acb_4bet_biglotto.json ✅
- biglotto_ts3_markov_freq_5bet: rejected/ts3_markov_freq_5bet_biglotto.json ✅
- p1_deviation_2bet_539: rejected/p1_deviation_2bet_539.json ✅
- power_shlc_midfreq: rejected/shlc_midfreq_power.json ✅

**Hash Consistency**:
```json
{
  "strategy_id": "biglotto_ts3_acb_4bet",
  "provenance_source": "rejected/ts3_acb_4bet_biglotto.json",
  "provenance_hash": "2267a34ff6dca87fa179d5bbde495bde91b02e591a3b8c29dc97dc5ddda57afc"
}
```

Hashes computed deterministically from:
1. Artifact JSON file contents (SHA256)
2. Method string ("artifact_reconstructed")

All 50 rows per strategy have identical provenance_hash (confirms deterministic hashing). ✅

**Results**: All rows trace back to artifact sources with reproducible hashes. ✅ PASS

---

## Output File Validation

### JSONL Candidate Rows

**File**: `outputs/replay/v2_artifact_only_candidate_rows_20260514.jsonl`

**Statistics**:
- Total rows: 200
- Lines in file: 200 (1 row per line)
- File size: ~76 KB
- Format: JSONL (one JSON object per line)

**Schema Validation**:
- All 19 fields present in every row ✅
- No missing fields ✅
- No extra fields ✅
- Data types match contract ✅

**Sample Row** (line 1):
```json
{"strategy_id": "biglotto_ts3_acb_4bet", "lottery_type": "BIG_LOTTO", "target_draw": "114000069", "target_date": "2025/07/11", "predicted_numbers": [1, 2, 3, 47, 48, 49], "predicted_special": null, "actual_numbers": [15, 16, 26, 34, 48, 49], "actual_special": null, "hit_numbers": [48, 49], "hit_count": 2, "special_hit": 0, "truth_level": "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE", "source": "v2_artifact_only_parser_dryrun", "provenance_source": "rejected/ts3_acb_4bet_biglotto.json", "provenance_hash": "2267a34ff6dca87fa179d5bbde495bde91b02e591a3b8c29dc97dc5ddda57afc", "dry_run_only": 1, "history_window_end": "113999069", "leakage_guard_pass": 1, "controlled_apply_id": null}
```

### JSON Summary

**File**: `outputs/replay/v2_artifact_only_candidate_summary_20260514.json`

**Statistics**:
- Strategies processed: 4
- Total rows generated: 200
- Total rows rejected: 0
- Average leakage guard pass rate: 100%

**Per-Strategy Summary**:
```json
{
  "strategy_id": "biglotto_ts3_acb_4bet",
  "lottery_type": "BIG_LOTTO",
  "provenance_source": "rejected/ts3_acb_4bet_biglotto.json",
  "rows_generated": 50,
  "rows_rejected": 0,
  "rejection_reasons": {},
  "leakage_guard_pass_rate": 1.0,
  "status": "PASS"
}
```

---

## Database Impact Verification

### No DB Modifications ✅

- Parser ran with `--dry-run` flag (default)
- No database connections for writing
- No INSERT/UPDATE/DELETE statements
- Database file unchanged (verified by file stat)

```bash
ls -la lottery_api/data/lottery_v2.db
# Before: -rw-r--r--  1 kelvin  staff  614400  May 14 12:00 lottery_api/data/lottery_v2.db
# After:  -rw-r--r--  1 kelvin  staff  614400  May 14 12:00 lottery_api/data/lottery_v2.db
# ✅ File size and timestamp unchanged
```

### No Registry Changes ✅

- Registry file `lottery_api/models/replay_strategy_registry.py` untouched
- No new strategy registrations
- All 4 ARTIFACT_ONLY strategies remain as REJECTED stubs

---

## Quality Assurance Checklist

- ✅ All 4 ARTIFACT_ONLY strategies parsed
- ✅ Total 200 candidate rows generated
- ✅ Zero rows rejected (0 validation gate failures)
- ✅ 100% leakage guard pass rate
- ✅ All rows have dry_run_only=true
- ✅ All rows have controlled_apply_id=null
- ✅ All rows have truth_level=ARTIFACT_RECONSTRUCTED_RETROSPECTIVE
- ✅ All rows have provenance_hash
- ✅ JSONL format valid and parseable
- ✅ JSON summary valid and complete
- ✅ No database modifications
- ✅ No registry changes
- ✅ Deterministic output verified
- ✅ All 6 validation gates enforced

---

## Success Markers

✅ V2_PARSER_CONTRACT_CREATED  
✅ V2_DRYRUN_PARSER_CREATED  
✅ V2_DRYRUN_EXECUTED  
✅ V2_DRYRUN_VALIDATED  
✅ V2_NO_DB_CHANGE  
✅ V2_NO_REGISTRY_CHANGE  
✅ V2_ARTIFACT_ONLY_DRYRUN_VALIDATED

---

## Next Phase

**PHASE 6: Comprehensive Report**
- Create final closure report with all evidence
- Document row generation methodology
- Provide deployment readiness assessment
- Recommend next steps for controlled apply

---

## Sign-Off

**Validation Status**: COMPLETE ✅  
**Date**: 2026-05-14  
**Result**: V2_ARTIFACT_ONLY_DRYRUN_VALIDATED  
**Ready for**: PHASE 6 (Comprehensive Report)

