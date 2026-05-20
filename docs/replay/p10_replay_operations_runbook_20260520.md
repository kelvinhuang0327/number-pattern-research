# P10 Replay Operations Runbook — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Launch Readiness**: `BLOCKED_BY_CEO_APPLY_PHRASE`  
**Production Rows**: 460 (pre-apply baseline)

---

## 1. Current Locked State

| Item | Value |
|------|-------|
| Production rows | **460** |
| P7 gate | **BLOCKED — phrase not received** |
| Next authorized apply | 28 ONLINE rows → 488 |
| RETIRED rows | 93 — deferred |
| All tests | **253/253 PASS** |
| Drift guard | **PASS** |

---

## 2. Exact Apply Phrase

The only phrase that authorizes P7 ONLINE apply:

```
YES apply P7 controlled replay rows
```

**This phrase must appear verbatim in the CEO/operator message.** No paraphrase, no partial match.

---

## 3. Pre-Apply Checklist

Before executing P7 ONLINE apply, complete ALL items in order:

### 3.1 DB State Verification
```bash
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
# MUST return: 460
# STOP if any other value
```

### 3.2 Test Suite Green
```bash
.venv/bin/python -m pytest -q \
  tests/test_replay_api_contract.py \
  tests/test_p7_controlled_apply_actual_gate.py
# MUST return: 44+17 PASS, 0 FAIL
# STOP if any failure
```

### 3.3 Drift Guard PASS
```bash
.venv/bin/python scripts/replay_lifecycle_drift_guard.py \
  --strict --json-out /tmp/pre_apply_drift_$(date +%Y%m%d).json
# MUST return: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
# STOP if any violation
```

### 3.4 Backup Creation
```bash
mkdir -p backups/
sqlite3 lottery_api/data/lottery_v2.db \
  ".backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db"

# Verify backup row count
sqlite3 backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
# MUST return: 460
```

### 3.5 Scope Confirmation
```bash
# Dry-run preview (no write) — confirm 28 planned inserts
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --scope ONLINE_ONLY \
  --db lottery_api/data/lottery_v2.db
# Look for: WILL INSERT: 28, SKIP (duplicate): 0
```

---

## 4. Apply Command

**Only execute after ALL pre-apply checks pass AND CEO exact phrase received.**

```bash
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --apply \
  --scope ONLINE_ONLY \
  --backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  --expected-rows 460 \
  --json-out outputs/replay/p7_authorized_apply_result_20260520.json
```

Expected output:
```
[APPLY RESULT]
  Inserted:   28
  Errors:     0
  Rows after: 488
  Expected:   488
```

---

## 5. Post-Apply Verification

Execute **immediately** after apply, in this order:

### 5.1 Row Count
```bash
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
# MUST return: 488
# ROLLBACK if any other value
```

### 5.2 Idempotency Rerun
```bash
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --scope ONLINE_ONLY \
  --db lottery_api/data/lottery_v2.db
# MUST show: WILL INSERT: 0, SKIP (duplicate): 28
```

### 5.3 API Contract
```bash
.venv/bin/python -m pytest -q tests/test_replay_api_contract.py
# MUST return: 44/44 PASS
```

### 5.4 Drift Guard
```bash
.venv/bin/python scripts/replay_lifecycle_drift_guard.py \
  --strict --json-out /tmp/post_apply_drift_$(date +%Y%m%d).json
# MUST return: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
```

### 5.5 New Strategies Visible
```bash
# Verify fourier_rhythm_3bet rows visible
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='fourier_rhythm_3bet';"
# MUST return: 12

# Verify ts3_regime_3bet rows visible
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='ts3_regime_3bet';"
# MUST return: 16
```

### 5.6 No Retired Rows in Apply Batch
```bash
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT strategy_id FROM strategy_prediction_replays \
   WHERE source='P7_CONTROLLED_APPLY' AND \
   strategy_id NOT IN ('fourier_rhythm_3bet','ts3_regime_3bet');"
# MUST return: (empty)
```

---

## 6. API Verification

After apply, verify the API serves the new rows:

```bash
# Start server if not running
# curl http://localhost:8000/api/replay/history?lottery_type=POWER_LOTTO&strategy_id=fourier_rhythm_3bet
# Expected: total > 0, records with visibility_state="ROW_BACKED"
```

Each returned record should have:
- `visibility_state` = `"ROW_BACKED"`
- `display_status` = `"SHOW_REPLAY_RESULT"`
- `should_count_as_success` = `true` (for records with actual_numbers not NULL)
- `source_trace` = `"P7_CONTROLLED_APPLY|RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD|<hash>"`

---

## 7. UI Verification

After apply, the replay UI history list should show:
- `fourier_rhythm_3bet` entries with actual vs predicted numbers
- `ts3_regime_3bet` entries with actual vs predicted numbers
- No `visibility_state` = `"RECONSTRUCTIBLE_PENDING"` for these strategies (they are now ROW_BACKED)
- Hit counts computed correctly from actual draw numbers

---

## 8. Drift Guard Final
```bash
.venv/bin/python scripts/replay_lifecycle_drift_guard.py --strict
# MUST PASS before marking apply as complete
```

---

## 9. Idempotency Final
```bash
# Run dry-run one more time to confirm no additional inserts possible
.venv/bin/python scripts/p7_controlled_replay_row_apply.py --scope ONLINE_ONLY
# MUST show: WILL INSERT: 0, SKIP (duplicate): 28
```

---

## 10. Escalation Path

| Condition | Action |
|-----------|--------|
| Post-apply rows ≠ 488 | Execute rollback immediately (Section 5 of rollback checklist) |
| API contract fails | Do not expose new rows in UI; investigate regression |
| Drift guard fails | Halt all further apply operations; investigate root cause |
| Retired rows in apply batch | Execute rollback immediately; audit P7 JSON |
| Any test failure | Do not mark apply as complete until all tests pass |
| CTO not reachable | Default to rollback; preserve 460-row state |

---

## Scope Restrictions (permanent)

| Action | Status |
|--------|--------|
| Apply 93 RETIRED rows | ❌ BLOCKED until separate auth |
| Apply NO_DATA rows | ❌ BLOCKED — no source data |
| Apply ARTIFACT_ONLY rows | ❌ BLOCKED — not registered |
| Count RECONSTRUCTIBLE as success | ❌ BLOCKED |
| Fabricate actual_numbers | ❌ NEVER |
| Mark ARTIFACT_ONLY as ONLINE | ❌ NEVER |
