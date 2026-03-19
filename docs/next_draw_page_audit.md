# Next Draw Prediction Page — Phase 1 Audit
**Date**: 2026-03-19
**Phase**: 1 — Prediction Flow Audit

---

## 1. How Current Predictions Are Generated

### Primary Production Path
```
Frontend → POST /api/predict-coordinator
          → _build_coordinator_result()
          → coordinator_predict()  (lottery_api/engine/strategy_coordinator.py)
          → Individual Agent scorers (_acb_score_all, _fourier_score_all, etc.)
          → RSM-weighted aggregation → Top-N numbers
```

The coordinator:
1. Loads history from `lottery_v2.db` (via `load_backend_history`)
2. Each agent scores ALL numbers 1..max (not just top-N)
3. Scores normalized 0–1, then weighted by `edge_30p` from `strategy_states_*.json`
4. Negative-edge agents get weight = 0
5. Aggregated scores produce a ranked list; each `num_bets` sliced without overlap

### Secondary Paths (not used for NEXT DRAW page)
- `POST /api/predict-from-backend` — supports same coordinator via `modelType=coordinator_direct`
- `POST /api/predict` — accepts frontend-provided history (no longer recommended)
- Individual model endpoints (prophet, xgboost, etc.) — not RSM-aligned

---

## 2. Backend Modules Producing Next-Draw Outputs

| Module | Path | Role |
|--------|------|------|
| `strategy_coordinator.py` | `lottery_api/engine/` | Primary coordinator; scores all numbers, outputs bets |
| `strategy_states_*.json` | `lottery_api/data/` | Per-strategy RSM metrics (edge, trend, alert) |
| `rolling_monitor_*.json` | `data/` | Per-draw history of each strategy |
| `predictions_*.jsonl` | `lottery_api/data/` | MicroFish prediction log (ts, period, bets, actual) |
| `special_predictor.py` | `lottery_api/models/` | POWER_LOTTO special number (V3 MAB) |
| `regime_monitor.py` | `lottery_api/models/` | L3 variance waterline (STANDBY/NORMAL/HOT/COLD) |

### Coordinator API Response Shape
```json
{
  "numbers": [1, 2, 3, 4, 5, 6],
  "confidence": 0.78,
  "method": "coordinator_direct_3bet",
  "notes": "Coordinator mode=direct, n_bets=3, periods=500",
  "bets": [
    {"numbers": [1, 2, 3, 4, 5, 6], "source": "coordinator_direct_1"},
    {"numbers": [7, 8, 9, 10, 11, 12], "source": "coordinator_direct_2"},
    {"numbers": [13, 14, 15, 16, 17, 18], "source": "coordinator_direct_3", "special": 8}
  ],
  "analysis": {"num_bets": 3, "mode": "direct", "lottery_type": "DAILY_539", ...},
  "dataRange": {"total_count": 5812, "date_range": "...", "draw_range": "..."},
  "modelInfo": { ... }
}
```

Note: `special` field present only in POWER_LOTTO bets.

---

## 3. Where Strategy Labels / Status Are Stored

### strategy_states_*.json Structure (per strategy key)
```json
{
  "name": "acb_1bet",
  "lottery_type": "DAILY_539",
  "num_bets": 1,
  "total_records": 318,
  "edge_30p": 0.05267,
  "edge_100p": 0.046,
  "edge_300p": 0.03267,
  "rate_30p": 0.16667,
  "rate_100p": 0.16,
  "rate_300p": 0.14667,
  "trend": "STABLE",
  "z_score": 0.294,
  "sharpe_300p": 0.0923,
  "consecutive_neg_30p": 0,
  "alert": false,
  "last_updated": "2026-03-18T10:43:46",
  "note": ""
}
```

### Status Derivation Rules (no explicit field — derived at runtime)
| Status | Condition |
|--------|-----------|
| `PRODUCTION` ✅ | `edge_300p > 0.03` AND `trend ∈ {STABLE, IMPROVING}` AND `alert == false` |
| `WATCH` ⚠️ | `edge_300p > 0` AND (`trend == DECLINING` OR `0 < edge_300p ≤ 0.03`) |
| `ADVISORY_ONLY` 🔵 | Strategy is prediction-log only, not in RSM; or `edge_300p ≤ 0` |
| `MAINTENANCE` 🔴 | Game-level — BIG_LOTTO: signal space exhausted (L90/L91). DAILY_539: in maintenance mode (L82). |

### Active Strategies per Game
**DAILY_539** — `strategy_states_DAILY_539.json`
| Key | Bets | 300p Edge | Status |
|-----|------|-----------|--------|
| `acb_1bet` | 1 | +3.27% | PRODUCTION |
| `midfreq_acb_2bet` | 2 | +8.46% | PRODUCTION ★ |
| `acb_markov_midfreq_3bet` | 3 | +8.50% | PRODUCTION ★ |
| `acb_markov_fourier_3bet` | 3 | secondary | WATCH |
| `f4cold_5bet` | 5 | +6.61% | PRODUCTION |
| `f4cold_3bet` | 3 | +0.17% (30p negative) | WATCH |

**BIG_LOTTO** — `strategy_states_BIG_LOTTO.json`
| Key | Bets | 300p Edge | Status |
|-----|------|-----------|--------|
| `regime_2bet` | 2 | +3.64% | PRODUCTION ★ |
| `ts3_regime_3bet` | 3 | +3.51% | PRODUCTION ★ |
| `p1_deviation_4bet` | 4 | +1.10% | WATCH |
| `p1_dev_sum5bet` | 5 | +3.71% | PRODUCTION ★ |
| others | — | legacy | ADVISORY_ONLY |

**POWER_LOTTO** — `strategy_states_POWER_LOTTO.json`
| Key | Bets | 300p Edge | Status |
|-----|------|-----------|--------|
| `fourier_rhythm_2bet` | 2 | — RSM monitoring | WATCH |
| `midfreq_fourier_2bet` | 2 | — RSM monitoring | WATCH |
| `fourier_rhythm_3bet` | 3 | +3.16% | PRODUCTION ★ |
| `midfreq_fourier_mk_3bet` | 3 | +1.83% RSM | WATCH |
| `pp3_freqort_4bet` | 4 | +3.40% | PRODUCTION ★ |
| `orthogonal_5bet` | 5 | +2.76% | PRODUCTION |

---

## 4. Existing API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/predict-coordinator` | POST | ★ Primary — coordinator predict (all 3 games) |
| `GET /api/data/stats` | GET | Latest draw counts, date range |
| `GET /api/performance/regime` | GET | L3 waterline status |
| `POST /api/predict-from-backend` | POST | Secondary (supports coordinator_direct) |

### No Existing Endpoint For:
- Strategy states (edge, trend, alert) — data only in JSON files on disk
- Batch multi-game predictions in one call
- Next-draw period numbers

---

## 5. Recommended Frontend Fetch Strategy

### Option A: Multiple Parallel Frontend Calls (NO new endpoint)
- 6–9 calls to `/api/predict-coordinator` per page load (3 games × 2–3 bet counts)
- Additional read needed for strategy states — but NO endpoint exists for this
- **Problem**: Strategy status labels not accessible without file read or new endpoint

### Option B: Single `/api/next-draw-summary` Endpoint ✅ RECOMMENDED
- One call returns all games × all recommended bet counts
- Includes coordinator predictions + strategy_state metadata
- Includes special numbers (POWER_LOTTO)
- Response cached for ~30s (data doesn't change mid-session)
- ~100 lines of Python, minimal new code

### Option B Response Contract (draft)
```json
{
  "generated_at": "2026-03-19T...",
  "games": {
    "DAILY_539": {
      "latest_period": "115000069",
      "next_period": "115000070",
      "game_status": "PRODUCTION",
      "bets": [
        {
          "bet_count": 1,
          "strategy_key": "acb_1bet",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0327,
          "trend": "STABLE",
          "alert": false,
          "numbers": [[4, 18, 19, 25, 34]]
        },
        {
          "bet_count": 2,
          "strategy_key": "midfreq_acb_2bet",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0846,
          "trend": "STABLE",
          "alert": false,
          "numbers": [[4, 18, 19, 25, 34], [5, 7, 10, 12, 23]]
        }
      ]
    },
    "BIG_LOTTO": { ... },
    "POWER_LOTTO": {
      "bets": [
        {
          "bet_count": 3,
          "numbers": [[3, 10, 19, 26, 36, 37], ...],
          "special": 8,
          ...
        }
      ]
    }
  }
}
```

---

## 6. Frontend Integration Points

### Where to Add the New Page
- Add `next-draw` section to `index.html` nav (after existing nav buttons)
- New section div: `<section id="next-draw-section" class="section">`
- New handler: `src/core/handlers/NextDrawHandler.js`
- Wire in `src/core/App.js` (import + instantiate)

### No Changes Needed To:
- `src/services/ApiClient.js` (add one method for new endpoint)
- `lottery_api/engine/strategy_coordinator.py` (untouched)
- `lottery_api/routes/prediction.py` (add one new route)
- `lottery_api/data/strategy_states_*.json` (read-only)
- All prediction logic (MUST NOT be modified)

---

## 7. Game Status Labels (page-level)

| Game | Status | Reason |
|------|--------|--------|
| DAILY_539 | PRODUCTION — MAINTENANCE MODE | Signal space exhausted (L82), existing strategies monitored |
| BIG_LOTTO | PRODUCTION — MAINTENANCE MODE | Signal space exhausted (L91), zero new signals detected |
| POWER_LOTTO | PRODUCTION | Active RSM monitoring, strategies in good standing |

---

## Summary

**Primary API**: `POST /api/predict-coordinator` (already exists, production-ready)
**Required**: One new minimal endpoint `/api/next-draw-summary` (~100 LOC)
**No new strategies**: Page reads only from existing RSM pipeline outputs
**No fake data**: All numbers come from coordinator + strategy_states files
**Frontend impact**: Add 1 nav item, 1 section, 1 handler (~200 LOC total)
