# P87 — Live Operations Runbook and Monitoring Cadence

**Classification:** `P87_LIVE_OPERATIONS_RUNBOOK_READY`  
**Date:** 2026-05-26  
**System Status:** LAUNCH READY  

---

## 1. System Status Summary

| Item | Value |
|------|-------|
| System | Strategy Historical Replay |
| Launch status | **LAUNCH READY** |
| replay_rows | **46,962** |
| POWER_LOTTO max_draw | **115000041** (2026/05/21) |
| Batch A coverage | **100.0%** |
| Backend port | **8002** |
| Date format | **YYYY/MM/DD** (e.g. `2026/05/21`) |
| P82 freshness | FRESHNESS_PASS |
| P85 status | P85_REPLAY_LAUNCH_CLOSURE_OPERATOR_PACKAGE_READY |
| P86 status | P86_LIVE_MONITORING_SOURCE_DECISION_GUARD_READY |

---

## 2. Backend Port Warning

**Port 8002** — Strategy Historical Replay API (correct)

**Port 8000** — UNRELATED application (Personal Health Platform). Do NOT use port 8000 for any replay operations.

---

## 3. Date Format

All replay API calls must use **slash format** `YYYY/MM/DD`, not hyphen format.

```
✅ CORRECT:  2026/05/21
❌ WRONG:    2026-05-21  (returns no rows)
```

---

## 4. Monitoring Cadence

### 4.1 Daily Check (every day draws are expected)

Run in order:

```bash
# Step 1 — P86 Source Decision Guard (read-only)
python scripts/p86_live_monitoring_source_decision_guard.py

# Step 2 — P82 Replay Freshness Guard
.venv/bin/python scripts/p82_replay_freshness_guard.py --lottery POWER_LOTTO

# Step 3 — Lifecycle Drift Guard
.venv/bin/python scripts/replay_lifecycle_drift_guard.py

# Step 4 — Replay row count verification
python3 -c "
import sqlite3
con = sqlite3.connect('lottery_api/data/lottery_v2.db')
cur = con.cursor()
cur.execute('SELECT COUNT(*) FROM strategy_prediction_replays')
print(f'replay_rows={cur.fetchone()[0]}')
cur.execute(\"SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'\")
print(f'max_draw={cur.fetchone()[0]}')
con.close()
"
```

### 4.2 Per-Draw Check (when a new POWER_LOTTO draw is expected)

```bash
# Run P86 with source snapshot
python scripts/p86_live_monitoring_source_decision_guard.py \
  --source-snapshot /path/to/operator_snapshot.json

# If SOURCE_DECISION_REQUIRED is returned:
# STOP. Do not ingest. Make explicit source decision first.
```

### 4.3 Weekly Check

```bash
# Browser smoke (50 tests)
.venv/bin/pytest tests/test_replay_browser_smoke.py -v --tb=no -q

# Full test suite
.venv/bin/pytest tests/test_p86_live_monitoring_source_decision_guard.py \
                 tests/test_p85_launch_closure_operator_release.py \
                 tests/test_p84_browser_e2e_launch_signoff.py \
                 -v --tb=short -q
```

---

## 5. Expected Stable Outputs

| Metric | Expected Until New Controlled Apply |
|--------|-------------------------------------|
| replay_rows | **46,962** |
| POWER_LOTTO max_draw | **115000041** |
| P86 classification | `STABLE_NO_NEW_DRAW` or `SOURCE_DECISION_REQUIRED` |
| P82 classification | `FRESHNESS_PASS` |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |

---

## 6. Source Decision Guard Commands

### Run without source (read DB only)

```bash
python scripts/p86_live_monitoring_source_decision_guard.py
```

### Run with source snapshot

```bash
python scripts/p86_live_monitoring_source_decision_guard.py \
  --source-snapshot /path/to/snapshot.json
```

Source snapshot format:
```json
{
  "lottery_type": "POWER_LOTTO",
  "max_draw": 115000041,
  "source": "operator_upload",
  "as_of": "2026-05-26"
}
```

### Run with read-only local API check

```bash
python scripts/p86_live_monitoring_source_decision_guard.py --allow-network-read
```

---

## 7. Replay API Spot-Check

Verify draw 115000041 is accessible via the replay API:

```bash
# Start backend first if not running
# cd lottery_api && python -m uvicorn main:app --port 8002

# Spot-check draw 115000041 (slash date format)
curl "http://localhost:8002/api/strategy-replays?lottery_type=POWER_LOTTO&draw=115000041"

# Verify replay count for a specific strategy
curl "http://localhost:8002/api/strategy-replays?lottery_type=POWER_LOTTO&strategy_id=fourier_rhythm_3bet" | python3 -m json.tool | grep total
```

---

## 8. Alert Criteria

Trigger an alert and STOP operations if ANY of these occur:

| Alert | Condition | Action |
|-------|-----------|--------|
| New draw detected | `source_max_draw > DB max_draw` | SOURCE_DECISION_REQUIRED — stop, decide |
| Replay gap detected | `replay_gap_detected = True` in P82 | Investigate before any apply |
| Browser smoke fails | Any of 50 browser smoke tests fail | Investigate frontend/API |
| replay_rows changed unexpectedly | `replay_rows != 46962` without approved phase | STOP — audit trail required |
| max_draw changed unexpectedly | `max_draw != 115000041` without source decision | STOP — investigate |
| DB file modified without approved phase | `git status` shows lottery_v2.db staged | STOP — do not commit |
| Source stale | `source_max_draw < DB max_draw` | Investigate source provider |

---

## 9. Decision Tree

```
Run P86 source decision guard
│
├─ STABLE_NO_NEW_DRAW ──────────────────→ HOLD. Continue monitoring.
│
├─ SOURCE_DECISION_REQUIRED ────────────→ STOP. New draws detected.
│                                          Operator chooses one of:
│                                          - uploaded_source_provided_by_operator
│                                          - official_api_explicitly_authorized
│                                          - hold_no_action
│                                          - manual_verification_required
│                                          → Only proceed after explicit decision.
│
├─ SOURCE_STALE ────────────────────────→ Source behind DB. Check provider.
│                                          Verify source file as_of date.
│                                          Do NOT ingest stale data.
│
└─ SOURCE_UNAVAILABLE ──────────────────→ Provide --source-snapshot or
                                           --allow-network-read.
                                           No action on DB until source resolved.
```

If **replay gap detected** (P82 returns `replay_gap_detected = True`):

```
P82 replay gap detected
│
└─ Identify missing draw(s) and missing strategy(ies)
   → Do NOT auto-apply
   → Prepare controlled apply plan (P88+)
   → Obtain explicit operator authorization
   → Only then proceed with controlled apply
```

---

## 10. Forbidden Actions

The following are **strictly forbidden** without an approved phase and explicit operator authorization:

| Forbidden Action | Reason |
|-----------------|--------|
| Direct DB write (`INSERT`, `UPDATE`, `DELETE` on any table) | Corrupts baseline; requires full audit |
| Automatic official API ingestion (without source decision) | Unauthorized data provenance |
| Replay row apply without plan + authorization | Breaks traceability |
| `git reset --hard` | Destroys working changes |
| `git clean` | Destroys untracked work |
| Force push (`git push --force`) | Rewrites shared history |
| Staging `lottery_v2.db` or `.bak` files | Leaks private data |
| Creating new tables without approved schema phase | Breaks migration chain |
| Modifying lifecycle/champion/registry/strategy metadata | Invalidates governance |

---

## 11. Evidence Chain

| Phase | Classification | PR | Commit |
|-------|---------------|----|--------|
| P77C | Draw re-import | — | — |
| P79 | Batch A apply | — | — |
| P82 | Replay freshness guard | — | — |
| P83 | Stable baseline closure | #208 | f019ae8 |
| P84 | Browser E2E stabilized | #209 | a18523d |
| P85 | Launch closure / operator release | #210 | d386066 |
| **P86** | Source decision guard | **#211** | **34e7ea9** |
| **P87** | Live operations runbook | — | — |

---

## 12. Next Controlled Phases

| Trigger | Next Phase |
|---------|-----------|
| New POWER_LOTTO draws confirmed via source decision | P88 — New Draw Controlled Apply |
| P82 replay gap detected | P88 — Gap Remediation Apply |
| New strategy approved | New phase — Strategy Expansion Apply |
| Batch B strategy development | Separate branch / new phase |

---

## 13. Operator Quick Reference

```
Daily:      python scripts/p86_live_monitoring_source_decision_guard.py
            .venv/bin/python scripts/p82_replay_freshness_guard.py --lottery POWER_LOTTO

Per-draw:   python scripts/p86_live_monitoring_source_decision_guard.py --source-snapshot <file>
            → If SOURCE_DECISION_REQUIRED: STOP and decide.

Weekly:     .venv/bin/pytest tests/test_replay_browser_smoke.py -v --tb=no -q

Backend:    port 8002 only (never port 8000)
Date fmt:   YYYY/MM/DD (never YYYY-MM-DD)
Baseline:   replay_rows=46962, max_draw=115000041
```
