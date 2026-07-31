# P80 Replay UI / API Verification — POWER_LOTTO Draw 115000041

**Date**: 2026-05-26  
**Branch**: `p80-replay-ui-api-verification`  
**Final Classification**: `P80_REPLAY_UI_API_VERIFICATION_PASS`

---

## Pre-flight

| Check | Result |
|-------|--------|
| PR #203 (P77C) merged | PASS |
| PR #204 (P79) merged | PASS |
| replay_rows = 46962 | PASS |
| P79 rows present (ids 46961, 46962) | PASS |
| P79 dry_run = 0 | PASS |

---

## API Verification

**Backend**: `http://localhost:8002`

### Health Check
```
GET /health → {"status": "healthy", ...}
```
PASS

### Replay History — Date Filter
```
GET /api/replay/history?lottery_type=POWER_LOTTO&date_from=2026/05/21&date_to=2026/05/21
→ total: 2
```

| id | strategy_id | hit_count | hit_numbers | truth_level | dry_run |
|----|-------------|-----------|-------------|-------------|---------|
| 46961 | fourier_rhythm_3bet | 1 | [28] | POWERLOTTO_DRAW_EXT_VERIFIED | 0 |
| 46962 | fourier30_markov30_2bet | 2 | [14, 38] | POWERLOTTO_DRAW_EXT_VERIFIED | 0 |

PASS — both P79 rows visible with correct data.

> **Note**: API date filter uses slash format `2026/05/21` matching DB storage format.

### Strategy Filters
```
GET /api/replay/history?lottery_type=POWER_LOTTO&strategy_id=fourier_rhythm_3bet&date_from=2026/05/21&date_to=2026/05/21
→ total: 1, hit_count: 1  ✓

GET /api/replay/history?lottery_type=POWER_LOTTO&strategy_id=fourier30_markov30_2bet&date_from=2026/05/21&date_to=2026/05/21
→ total: 1, hit_count: 2  ✓
```

PASS

### Replay Summary
```
GET /api/replay/summary?lottery_type=POWER_LOTTO
→ fourier_rhythm_3bet:     total_rows=1501 (1500 historical + 1 draw-ext)
→ fourier30_markov30_2bet: total_rows=1501 (1500 historical + 1 draw-ext)
```

PASS

---

## Frontend

```
GET http://localhost:3000 → HTTP 200
```

PASS

---

## DB State

- `total_replay_rows`: 46962
- P79 rows: id=46961 (fourier_rhythm_3bet), id=46962 (fourier30_markov30_2bet)
- Both `dry_run=0`, `truth_level=POWERLOTTO_DRAW_EXT_VERIFIED`

---

## Summary

All P80 verification checks passed. The 2 P79 Batch A draw-ext rows for POWER_LOTTO draw 115000041 are correctly stored, queryable via the replay history API with proper filtering, and reflected in strategy summary counts.
