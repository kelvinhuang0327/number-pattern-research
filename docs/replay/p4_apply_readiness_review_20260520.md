# P4 Apply Readiness Review — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Date**: 2026-05-20  
**Review type**: Readiness Gate Only — NO production apply performed.

---

## 1. Authorization Status

| Gate | Status |
|------|--------|
| CEO exact phrase `YES apply P7 controlled replay rows` | **NOT RECEIVED** |
| Production apply executed | **NO** |
| Today's classification | `P0P1P2_ALL_GREEN_AWAITING_CEO_APPLY_PHRASE` |

**P7 production apply is blocked until the exact authorization phrase is received.**

---

## 2. P7 ONLINE_ONLY Apply Package — 28 Rows Ready

### Scope

| Strategy | Lottery | Draw Count | Draw Range |
|----------|---------|-----------|-----------|
| fourier_rhythm_3bet | POWER_LOTTO | 12 | 115000016–115000030 |
| ts3_regime_3bet | BIG_LOTTO | 16 | 115000025–115000044 |
| **Total ONLINE** | | **28** | |

### Readiness Checklist

| Item | Status |
|------|--------|
| `test_p7_controlled_apply_actual_gate.py` 17/17 PASS | ✅ |
| `test_replay_api_contract.py` 44/44 PASS | ✅ |
| `test_p3_per_draw_all_strategy_coverage_matrix.py` 32/32 PASS | ✅ |
| `test_p2_full_catalog_visibility_plan.py` 24/24 PASS | ✅ |
| Drift guard `--strict` PASS | ✅ |
| Production rows = 460 | ✅ |
| FK root cause fixed (`replay_run_id=None`) | ✅ |
| Temp DB rehearsal 460→488 verified | ✅ |
| Idempotency (second run = 0 inserts) verified | ✅ |
| Rollback via `controlled_apply_id` verified | ✅ |
| Zero duplicates in ONLINE scope | ✅ |
| Backup procedure documented | ✅ |
| Rollback SQL documented | ✅ |
| P7 dry-run JSON frozen | ✅ |

### Pre-Apply Command (for when authorized)

```bash
# Step 1: Create backup
sqlite3 lottery_api/data/lottery_v2.db \
  ".backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db"

# Step 2: Verify backup
sqlite3 backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
# Expected: 460

# Step 3: Dry-run preview (no write)
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --scope ONLINE_ONLY \
  --expected-rows 460

# Step 4: Actual apply (requires CEO authorization phrase first)
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --apply \
  --scope ONLINE_ONLY \
  --backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  --expected-rows 460

# Expected post-apply: 488 rows
# Rollback if needed:
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --apply \
  --rollback-plan <controlled_apply_id> \
  --rollback-apply \
  --backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  --expected-rows 488
```

---

## 3. P7 RETIRED Scope — 93 Rows Deferred

| Strategy | Lottery | Draw Count | P7 Decision | Barrier |
|----------|---------|-----------|------------|---------|
| acb_1bet | DAILY_539 | 31 | PLAN_MANUAL_REVIEW_REQUIRED | RETIRED lifecycle warning |
| acb_markov_midfreq_3bet | DAILY_539 | 31 | PLAN_MANUAL_REVIEW_REQUIRED | RETIRED lifecycle warning |
| midfreq_acb_2bet | DAILY_539 | 31 | PLAN_MANUAL_REVIEW_REQUIRED | RETIRED lifecycle warning |
| **Total RETIRED** | | **93** | | |

**Requirements before RETIRED apply:**
1. Human review of lifecycle warnings for all 93 rows
2. Run with `--scope INCLUDE_RETIRED_WITH_WARNING --include-retired-reviewed`
3. Separate CEO authorization (not covered by ONLINE_ONLY phrase)

---

## 4. P3 Coverage Impact — Post-Apply Projection

If P7 ONLINE apply is authorized and executed:

| State | Before P7 | After P7 |
|-------|-----------|----------|
| ROW_BACKED | 300 (23.3%) | 328 (25.5%) |
| RECONSTRUCTIBLE | 121 (9.4%) | 93 (7.2%) |
| NO_DATA | 867 (67.3%) | 867 (67.3%) |

- 28 cells move from RECONSTRUCTIBLE → ROW_BACKED
- `real_replay_success_count`: 300 → 328
- `fake_success_count`: remains **0**

If P7 RETIRED apply is also authorized:

| State | After P7 ONLINE+RETIRED |
|-------|------------------------|
| ROW_BACKED | 421 (32.7%) |
| RECONSTRUCTIBLE | 0 (0%) |
| NO_DATA | 867 (67.3%) |

---

## 5. NO_DATA Gap Analysis

The 867 NO_DATA cells cannot be resolved without one of:
- Re-running strategy predictions for the relevant draws (not permitted without CEO auth)
- External data source providing historical predictions (not available)
- Accepting NO_DATA as the permanent state for those cells

**Recommendation**: Accept NO_DATA as permanent for:
- REJECTED strategies (biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet,
  power_shlc_midfreq, p1_deviation_2bet_539) — governance decision to not backfill
- RETIRED strategies without prediction_items (acb_markov_midfreq, midfreq_fourier_2bet)
- Legacy 99000xxx draws for strategies added after that window

---

## 6. ARTIFACT_ONLY Governance

41 strategies in `rejected/` artifacts but not in runtime registry.
No action needed for P4 apply scope. Governance review deferred.

---

## 7. API Contract Verification

Current API endpoints serving replay data:

| Endpoint | Coverage | Status |
|----------|----------|--------|
| `GET /api/replay/strategies` | 8 ONLINE strategies | ✅ |
| `GET /api/replay/strategies?public_only=true` | 8 ONLINE strategies | ✅ |
| `GET /api/replay/history/{strategy_id}` | 6 ROW_BACKED strategies | ✅ |
| Drift guard | All schema/count checks | ✅ PASS |

Post-P7-apply: `history` endpoint will gain 2 new strategies with data
(fourier_rhythm_3bet and ts3_regime_3bet).

---

## 8. Summary

| Phase | Status |
|-------|--------|
| P0 Gate hardening | ✅ COMPLETE |
| P1 Clean commit + reconciliation | ✅ COMPLETE |
| P2 Full-catalog visibility plan | ✅ COMPLETE |
| P3 Per-draw coverage matrix | ✅ COMPLETE |
| P4 Production apply | ⏳ AWAITING CEO PHRASE |

**Classification**: `P0P1P2P3_ALL_GREEN_AWAITING_CEO_APPLY_PHRASE`

To authorize P7 ONLINE apply, CEO must respond with:
```
YES apply P7 controlled replay rows
```
