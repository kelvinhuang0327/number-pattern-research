# P10 Replay Monitoring Plan — 2026-05-20

**Production baseline**: 460 rows (pre-apply) / 488 rows (post-P7-ONLINE-apply)  
**Drift guard**: must pass on every check

---

## 1. Daily Row Count Check

```bash
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
```

| State | Expected Count | Alert If |
|-------|---------------|---------|
| Pre-P7-apply | 460 | count ≠ 460 |
| Post-P7-ONLINE-apply | 488 | count ≠ 488 |
| Post-P7-ONLINE+RETIRED | 581 | count ≠ 581 |

**Alert severity**: CRITICAL if count changes unexpectedly.

---

## 2. Drift Guard Check

```bash
.venv/bin/python scripts/replay_lifecycle_drift_guard.py \
  --strict --json-out /tmp/daily_drift_$(date +%Y%m%d_%H%M).json
```

Expected: `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`

Alert if: any violation message appears, or non-zero exit code.

---

## 3. API Contract Check

```bash
.venv/bin/python -m pytest -q tests/test_replay_api_contract.py
```

Expected: `44/44 passed`

Alert if: any test fails. Do not deploy API changes without green tests.

---

## 4. Fake Success Count Check

```bash
python3 -c "
import json
d = json.load(open('outputs/replay/p3_per_draw_all_strategy_coverage_summary_20260520.json'))
fsc = d.get('fake_success_count', -1)
print(f'fake_success_count = {fsc}')
assert fsc == 0, f'ALERT: fake_success_count={fsc}'
print('OK')
"
```

Expected: `fake_success_count = 0`  
Alert if: count > 0. This is a critical data integrity invariant.

---

## 5. Coverage Matrix Check

Run after any apply or registry change:

```bash
.venv/bin/python scripts/p3_per_draw_all_strategy_coverage_matrix.py \
  --summary-out /tmp/coverage_check_$(date +%Y%m%d).json
```

Verify:
- `fake_success_count` = 0
- `row_backed_cells` increases by expected amount after apply
- `reconstructible_cells` decreases correspondingly

---

## 6. Unauthorized Apply Detection

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('lottery_api/data/lottery_v2.db')
count = conn.execute('SELECT COUNT(*) FROM strategy_prediction_replays').fetchone()[0]
lock = json.load(open('outputs/replay/p9_replay_launch_readiness_lock_20260520.json'))
assert not lock['safety_flags']['unauthorized_apply_performed'], 'UNAUTHORIZED APPLY DETECTED'
print(f'Rows: {count}, lock OK')
"
```

Alert if lock reports `unauthorized_apply_performed = true`.

---

## 7. Artifact Freshness Check

Verify key artifacts are not stale (dates in filename match current operation):

```bash
ls -la outputs/replay/p9_replay_launch_readiness_lock_20260520.json
ls -la outputs/replay/p8_reconstructible_backfill_dry_run_20260520.json
ls -la outputs/replay/p7_controlled_apply_dry_run_20260520.json
```

Alert if any canonical artifact is missing or zero-byte.

---

## 8. Alert Thresholds

| Alert ID | Condition | Severity | Response Time |
|----------|-----------|----------|--------------|
| `ALERT_ROW_COUNT_DRIFT` | rows ≠ expected | CRITICAL | Immediate |
| `ALERT_DRIFT_GUARD_FAIL` | drift guard non-PASS | CRITICAL | Immediate |
| `ALERT_API_CONTRACT_FAIL` | any test failure | HIGH | < 1 hour |
| `ALERT_FAKE_SUCCESS` | fake_success_count > 0 | CRITICAL | Immediate |
| `ALERT_UNAUTHORIZED_APPLY` | rows change without auth | CRITICAL | Immediate |
| `ALERT_ARTIFACT_MISSING` | canonical file missing | HIGH | < 4 hours |

---

## 9. Registry Health Check

```bash
.venv/bin/python scripts/report_strategy_lifecycle_registry.py
# Expected: TOTAL: 18, ONLINE: 8
```

Alert if ONLINE count drops below 8 (strategies removed from registry).

---

## 10. Post-Apply Monitoring Window

After P7 ONLINE apply executes (460→488), run enhanced monitoring for 24 hours:

| Check | Frequency | Duration |
|-------|-----------|---------|
| Row count | Every 30 min | 24 hours |
| Drift guard | Every 2 hours | 24 hours |
| API contract | Every 4 hours | 24 hours |
| Idempotency dry-run | Once at T+1h | Once |
| UI smoke test | T+1h, T+12h, T+24h | 24 hours |

---

## 11. Scheduled Verification Commands (cron-ready)

```bash
#!/bin/bash
# daily_replay_health.sh
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew

echo "=== Replay Health Check $(date) ===" >> /tmp/replay_health.log

# Row count
COUNT=$(sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;")
echo "rows=$COUNT" >> /tmp/replay_health.log

# Drift guard
.venv/bin/python scripts/replay_lifecycle_drift_guard.py \
  --strict --json-out /tmp/drift_$(date +%Y%m%d).json \
  >> /tmp/replay_health.log 2>&1

# API contract
.venv/bin/python -m pytest -q tests/test_replay_api_contract.py \
  >> /tmp/replay_health.log 2>&1

echo "=== Done ===" >> /tmp/replay_health.log
```
