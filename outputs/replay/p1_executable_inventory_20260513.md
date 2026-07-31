# P1 Executable Inventory — 2026-05-13

**Branch**: `frontend/p78-configurable-api-base-20260513`  
**PR #92**: OPEN / CI: ALL_CHECKS_PASS  
**DB hash**: `de0e27bb800bc7183773a0dc596d66b8`  
**Registry hash**: `3ea71cfc20c882714f3824ad68202f6e`

## Summary

| Classification | Count |
|----------------|-------|
| EXECUTABLE_NOW | 6 |
| EXECUTABLE_WITH_FIX | 0 |
| ARTIFACT_ONLY | 4 |
| CODE_MISSING | 6 |
| TOMBSTONE | 0 |
| NEEDS_MANUAL_DECISION | 0 |

## Per-Strategy Table

| # | strategy_id | lifecycle | adapter | get_one_bet | dry_call | rejected_json | strategy_dir | classification |
|---|-------------|-----------|---------|-------------|----------|---------------|--------------|----------------|
| 1 | `power_precision_3bet` | ONLINE | ✅ | ✅ | ❌ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 2 | `power_orthogonal_5bet` | ONLINE | ✅ | ✅ | ❌ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 3 | `biglotto_triple_strike` | ONLINE | ✅ | ✅ | ❌ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 4 | `biglotto_deviation_2bet` | ONLINE | ✅ | ✅ | ✅ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 5 | `daily539_f4cold` | ONLINE | ✅ | ✅ | ❌ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 6 | `daily539_markov_cold` | ONLINE | ✅ | ✅ | ❌ | ❌ | ❌ | **EXECUTABLE_NOW** |
| 7 | `biglotto_ts3_acb_4bet` | REJECTED | ❌ | ❌ | ⏭️ | ✅ | ✅ | **ARTIFACT_ONLY** |
| 8 | `biglotto_ts3_markov_freq_5bet` | REJECTED | ❌ | ❌ | ⏭️ | ✅ | ✅ | **ARTIFACT_ONLY** |
| 9 | `power_shlc_midfreq` | REJECTED | ❌ | ❌ | ⏭️ | ✅ | ❌ | **ARTIFACT_ONLY** |
| 10 | `p1_deviation_2bet_539` | REJECTED | ❌ | ❌ | ⏭️ | ✅ | ❌ | **ARTIFACT_ONLY** |
| 11 | `acb_1bet` | RETIRED | ❌ | ❌ | ⏭️ | ❌ | ❌ | **CODE_MISSING** |
| 12 | `acb_markov_midfreq` | RETIRED | ❌ | ❌ | ⏭️ | ❌ | ❌ | **CODE_MISSING** |
| 13 | `acb_markov_midfreq_3bet` | RETIRED | ❌ | ❌ | ⏭️ | ❌ | ❌ | **CODE_MISSING** |
| 14 | `midfreq_acb_2bet` | RETIRED | ❌ | ❌ | ⏭️ | ❌ | ❌ | **CODE_MISSING** |
| 15 | `midfreq_fourier_2bet` | RETIRED | ❌ | ❌ | ⏭️ | ❌ | ❌ | **CODE_MISSING** |
| 16 | `h6_gate_mk20_ew85` | OBSERVATION | ❌ | ❌ | ⏭️ | ❌ | ❌ | **CODE_MISSING** |

## Retrospective Readiness

| strategy_id | can_regenerate | regeneration_source | required_fix | proposed_truth_level | p3_candidate |
|-------------|---------------|---------------------|--------------|----------------------|--------------|
| `power_precision_3bet` | True | production_adapter | none | PRODUCTION_REPLAY | True |
| `power_orthogonal_5bet` | True | production_adapter | none | PRODUCTION_REPLAY | True |
| `biglotto_triple_strike` | True | production_adapter | none | PRODUCTION_REPLAY | True |
| `biglotto_deviation_2bet` | True | production_adapter | none | PRODUCTION_REPLAY | True |
| `daily539_f4cold` | True | production_adapter | none | PRODUCTION_REPLAY | True |
| `daily539_markov_cold` | True | production_adapter | none | PRODUCTION_REPLAY | True |
| `biglotto_ts3_acb_4bet` | False | rejected_artifact | artifact_parser | ARTIFACT_PROVENANCE_ONLY | False |
| `biglotto_ts3_markov_freq_5bet` | False | rejected_artifact | artifact_parser | ARTIFACT_PROVENANCE_ONLY | False |
| `power_shlc_midfreq` | False | rejected_artifact | artifact_parser | ARTIFACT_PROVENANCE_ONLY | False |
| `p1_deviation_2bet_539` | False | rejected_artifact | artifact_parser | ARTIFACT_PROVENANCE_ONLY | False |
| `acb_1bet` | False | none | missing_source_code | TOMBSTONE_NO_SOURCE | False |
| `acb_markov_midfreq` | False | none | missing_source_code | TOMBSTONE_NO_SOURCE | False |
| `acb_markov_midfreq_3bet` | False | none | missing_source_code | TOMBSTONE_NO_SOURCE | False |
| `midfreq_acb_2bet` | False | none | missing_source_code | TOMBSTONE_NO_SOURCE | False |
| `midfreq_fourier_2bet` | False | none | missing_source_code | TOMBSTONE_NO_SOURCE | False |
| `h6_gate_mk20_ew85` | False | none | missing_source_code | TOMBSTONE_NO_SOURCE | False |