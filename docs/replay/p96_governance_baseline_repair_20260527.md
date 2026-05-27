# P96 Governance Baseline Repair — 2026-05-27

## Classification: P96_GOVERNANCE_BASELINE_REPAIR_READY

## Summary

This document records the P96 governance baseline repair task executed on 2026-05-27.
Several active guards and tests retained a stale pre-P94 replay row expectation of **46962**.
After the P94 Tier B Controlled Apply (2026-05-26), the correct production baseline is **54462**.
P96 updates all *active* guards to use 54462, while leaving all *historical* artifacts at 46962.

---

## Baseline Change

| Field               | Before (pre-P94) | After (P96 repair) |
|---------------------|------------------|--------------------|
| replay_rows         | 46962            | **54462**          |
| delta               | —                | +7500              |
| POWER_LOTTO max_draw| 115000041        | 115000041 (unchanged) |
| reason              | P94 Tier B Controlled Apply | — |

### P94 Controlled Apply Details
- `controlled_apply_id`: `P94_TIERB_CONTROLLED_APPLY_20260526`
- `truth_level`: `TIERB_DRYRUN_VALIDATED`
- Rows added: 7500
- Date: 2026-05-26

---

## Updated Files (Active Guards)

### `scripts/replay_lifecycle_drift_guard.py`
- Added `p94_apply_id = 'P94_TIERB_CONTROLLED_APPLY_20260526'` to `BASELINE`
- Added `p94_count = 7500` to `BASELINE`
- Updated `total_count: 46962 → 54462`
- Added `'TIERB_DRYRUN_VALIDATED'` to `ALLOWED_TRUTH_LEVELS`
- Added `p94_count` DB query in `run_checks()`
- Added `p94` violation check
- Added `'p94'` key to `row_counts` output dict
- Added `BASELINE['p94_apply_id']` to `known_apply_ids` set

### `tests/test_replay_lifecycle_drift_guard.py`
- Added `'TIERB_DRYRUN_VALIDATED'` to `ALLOWED_TRUTH_LEVELS`
- Updated `test_db_counts_match_baseline` docstring (P94 post-apply baseline)
- Added assertion `rc.get('p94') == 7500`
- Updated total assertion: `46962 → 54462`

### `tests/test_p82_replay_freshness_guard.py`
- Updated `EXPECTED_REPLAY_ROWS = 46962 → 54462` (live DB guard `test_17_replay_rows_db`)
- Added `HISTORICAL_P82_ARTIFACT_ROWS = 46962` constant for historical artifact assertion
- `test_09_replay_rows_total` now uses `HISTORICAL_P82_ARTIFACT_ROWS` (historical snapshot check, pre-P94)
- `test_17_replay_rows_db` uses `EXPECTED_REPLAY_ROWS = 54462` (live DB check)

### `tests/test_replay_branch_governance_guard.py`
- Updated `--expected-rows "46962" → "54462"` in `test_02_script_passes_on_canonical`

---

## Intentionally Untouched Historical Files

The following files reference `46962` as a **past state** and are intentionally preserved:

| File | Reason |
|------|--------|
| `tests/test_p79_batch_a_controlled_apply.py` | 46962 = correct P79 post-apply historical state; reads historical JSON artifacts |
| `tests/test_p83_stable_baseline_closure.py` | 46962 = P83 baseline snapshot; reads historical JSON artifact |
| `tests/test_p84_browser_e2e_launch_signoff.py` | id=46962 is a ROW ID sentinel (not row count); live row-count assertions were not added in P84 |
| `tests/test_p85_launch_closure_operator_release.py` | 46962 = P85 launch baseline; reads historical JSON artifact |
| `tests/test_p87_live_operations_runbook.py` | 46962 = P87 runbook snapshot; reads historical artifact |
| `tests/test_p89_steady_state_monitoring_snapshot.py` | 46962 = P89 snapshot; reads historical artifact |
| `tests/test_p91_all_strategy_replay_expansion_inventory.py` | 46962 = P91 inventory baseline; historical |
| `tests/test_p92_tier_b_adapter_audit_dry_run_plan.py` | 46962 = P92 pre-apply baseline; historical artifact |
| `tests/test_p93_tier_b_replay_adapter_bootstrap_dryrun.py` | 46962 = P93 expected pre-apply state; historical |
| `tests/test_p94_tier_b_controlled_apply.py` | `EXPECTED_BEFORE = 46962` = correct pre-apply state being tested |
| `tests/test_p94a_biglotto_all_strategy_betcount_benchmark.py` | Row ID 46962 sentinel, not row count |
| `outputs/replay/p82_replay_freshness_guard_20260526.json` | Historical snapshot from 2026-05-26 (before P94) |

---

## Test Results (Post-Repair)

| Suite | Result |
|-------|--------|
| P82 freshness guard | **19/19 PASS** |
| Drift guard | **8/8 PASS** |
| Branch governance guard | **15/15 PASS** |
| Active guard total | **42/42 PASS** |
| P95 BSO tests | **30/30 PASS** |
| P94A BIG_LOTTO benchmark | **27/27 PASS** |
| P94B POWER_LOTTO benchmark | **27/27 PASS** |
| P94C Daily539 benchmark | **27/27 PASS** |
| P94D contract | **27/27 PASS** |
| Regression total | **138/138 PASS** |

---

## Governance Confirmations

| Check | Result |
|-------|--------|
| DB writes | false |
| Replay rows inserted | 0 |
| replay_rows before / after | 54462 / 54462 |
| POWER_LOTTO max_draw before / after | 115000041 / 115000041 |
| Special3/Special4 touched | false |
| claude-code-showcase touched | false |
| lifecycle/champion/registry touched | false |
| Forbidden staging scan | CLEAN |
