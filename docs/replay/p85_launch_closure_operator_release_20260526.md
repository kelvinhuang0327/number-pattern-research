# P85 — Launch Closure and Operator Release Package

**Classification:** `P85_REPLAY_LAUNCH_CLOSURE_OPERATOR_PACKAGE_READY`  
**Date:** 2026-05-26  
**Status:** READY  

---

## 1. Production Baseline

| Metric | Value |
|--------|-------|
| `replay_rows` | **46,962** |
| `POWER_LOTTO max_draw` | **115000041** |
| Max draw date | 2026/05/21 |
| Max draw numbers | [6, 14, 22, 28, 35, 38] special=1 |
| Batch A coverage | **100.0%** |
| DB writes (P85) | **false** |
| Browser E2E result | **PASS** (CI run 26443569347, 70/70 post-merge) |

### P79 Sentinel Production Rows

| id | strategy_id | draw | hit_count | dry_run | truth_level |
|----|------------|------|-----------|---------|-------------|
| 46961 | fourier_rhythm_3bet | 115000041 | 1 | 0 | POWERLOTTO_DRAW_EXT_VERIFIED |
| 46962 | fourier30_markov30_2bet | 115000041 | 2 | 0 | POWERLOTTO_DRAW_EXT_VERIFIED |

---

## 2. Evidence Chain: P77C → P84

| Phase | Title | PR | Commit | Outcome |
|-------|-------|----|--------|---------|
| P77C | Draw re-import recovery | #203 | 4b2eebc | max_draw=115000041 restored |
| P78 | Batch A dry-run plan readiness | #202 | 71511ff | 2 rows dry-run verified |
| P79 | Controlled apply — 2 production replay rows | #204 | 00d5bbe | 46960→46962 rows, dry_run=0 |
| P80 | Replay API/UI visibility verification | #205 | d9c4da4 | API confirmed on port 8002 |
| P81 | Monitoring/scoring pipeline verification | #206 | 8c50144 | Pipeline verified |
| P82 | Freshness/source gap guard | #207 | 0a76f75 | FRESHNESS_PASS, 100% coverage |
| P83 | Stable-baseline closure | #208 | f019ae8 | Full evidence consolidated |
| P84 | Browser E2E stabilization / launch signoff | #209 | a18523d | 70/70 PASS, CI green |

---

## 3. Operator Guide

### 3.1 Correct Backend Port

The Lottery API runs on **port 8002**.

> ⚠️ Port 8000 is an unrelated Personal Health Platform. Never use port 8000 for lottery queries.

```bash
# Correct
curl http://127.0.0.1:8002/api/replay?lottery_type=POWER_LOTTO&draw=115000041

# Wrong — do not use
curl http://127.0.0.1:8000/...
```

### 3.2 Correct Date Format

The Replay API date filter requires **slash-separated format**: `YYYY/MM/DD`

```
Correct:  2026/05/21
Wrong:    2026-05-21   ← will not match any rows
```

### 3.3 Querying POWER_LOTTO Draw 115000041

```bash
curl 'http://127.0.0.1:8002/api/replay?lottery_type=POWER_LOTTO&draw=115000041'
```

Expected draw metadata:
- date: `2026/05/21`
- numbers: `[6, 14, 22, 28, 35, 38]`
- special: `1`

### 3.4 Filtering by Strategy

Two production strategies have replay rows for draw 115000041:

| strategy_id | Expected hit_count | Notes |
|-------------|-------------------|-------|
| `fourier_rhythm_3bet` | 1 | P79 row id=46961 |
| `fourier30_markov30_2bet` | 2 | P79 row id=46962 |

```bash
curl 'http://127.0.0.1:8002/api/replay?lottery_type=POWER_LOTTO&draw=115000041&strategy_id=fourier_rhythm_3bet'
curl 'http://127.0.0.1:8002/api/replay?lottery_type=POWER_LOTTO&draw=115000041&strategy_id=fourier30_markov30_2bet'
```

### 3.5 What `dry_run=0` Means

- **`dry_run=0`** — Real production replay row. Counts toward official accuracy metrics.
- **`dry_run=1`** — Planning artifact / simulation only. Not counted in production metrics.

Both P79 sentinel rows (ids 46961, 46962) have `dry_run=0`.

### 3.6 Freshness Guard Usage

```bash
python scripts/p82_replay_freshness_guard.py --lottery POWER_LOTTO
```

Expected output:
```
replay_gap_detected: False
batch_a_coverage_pct: 100.0%
classification     : FRESHNESS_PASS
```

**Interpretation:**
- `FRESHNESS_PASS` — All Batch A draws have replay rows. System is current.
- `replay_gap_detected: True` — One or more draws are missing replay coverage. Investigate before adding new rows.
- `batch_a_coverage_pct < 100.0` — Coverage gap exists; find missing draw(s) before proceeding.

---

## 4. Launch Checklist

| Item | Status | Phase |
|------|--------|-------|
| Source recovery complete | ✅ COMPLETE | P77C |
| Draw freshness verified | ✅ COMPLETE | P82 |
| Controlled replay apply complete | ✅ COMPLETE | P79 (2 rows applied) |
| API visibility verified | ✅ COMPLETE | P80 |
| UI / Browser E2E stable PASS | ✅ PASS | P84 (CI run 26443569347) |
| Monitoring path verified | ✅ COMPLETE | P81 |
| Freshness guard available | ✅ COMPLETE | P82 |
| Risk register updated | ✅ COMPLETE | P85 |

---

## 5. Risk Register

### CLOSED

| Risk | Closed By | Resolution |
|------|-----------|-----------|
| Browser E2E flaky | P84 | 3 root causes resolved: timeout 5000ms→15000ms, `.evaluate` click → Playwright `.click()`, missing `src/config/apiConfig.js` added to git |

### DOCUMENTED

| Risk | Notes |
|------|-------|
| Port confusion (8000 vs 8002) | Port 8000 is unrelated Personal Health Platform. Lottery API always on 8002. |
| Date format slash requirement | API requires `YYYY/MM/DD`. Hyphen format will return no rows. |
| DB local-only nature | `lottery_v2.db` must never be staged or committed to git. |
| Official API ingestion not used | P79 rows were applied from local plan artifacts. External API used for verification (read) only. |

### OPEN

| Risk | Notes |
|------|-------|
| Future draw freshness | New draws beyond 115000041 require an explicit source decision. Freshness guard will flag `gap_detected=True`. |

---

## 6. Rollback / Recovery Reference

> ⚠️ Rollback requires **explicit operator authorization** and is **not part of P85**.

**P79 rollback SQL** (if authorized):
```sql
DELETE FROM strategy_prediction_replays WHERE id IN (46961, 46962);
```

**P79 backup file:**
```
lottery_api/data/lottery_v2.db.bak_p79_pre_apply_20260526_160020
```

---

## 7. P84 Root Cause Summary (for reference)

P84 resolved a 3-layer browser E2E CI failure:

| Fix | Root Cause | Change |
|-----|-----------|--------|
| fix1 | `wait_for_function` timeout 5000ms too short for CI runners | 5000 → 15000ms (3 occurrences) |
| fix2 | `.evaluate('(el) => el.click()')` bypassed Playwright actionability checks | `wait_until="networkidle"` + `.click()` |
| fix3 (root) | `src/config/apiConfig.js` untracked → 404 on CI → App.js import chain failed → nav click had no effect | Added file to git |

---

## 8. Governance

- Branch: `p85-launch-closure-operator-release`
- No DB writes
- No replay row insertions  
- No ingestion
- No new tables
- No lifecycle/champion/registry mutation
