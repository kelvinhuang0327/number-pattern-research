# Next Draw Prediction Page — Phase 2: API Contract
**Date**: 2026-03-19
**Phase**: 2 — Data Contract Design

---

## 1. New Endpoint

### `GET /api/next-draw-summary`

Returns coordinator-predicted bets for all three games at the recommended bet counts, along with RSM strategy metadata.

**No request parameters required** (uses backend's own latest data).

Optional query params:
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `mode` | string | `"direct"` | Coordinator mode: `direct` or `hybrid` |
| `recent_count` | int | 500 | History window size |

---

## 2. Strategy Status Derivation

Computed from `strategy_states_*.json` fields at request time:

```python
def derive_status(state: dict) -> str:
    edge = state.get("edge_300p", 0)
    trend = state.get("trend", "STABLE")
    alert = state.get("alert", False)
    if alert:
        return "WATCH"
    if edge >= 0.03 and trend in ("STABLE", "IMPROVING"):
        return "PRODUCTION"
    if edge > 0:
        return "WATCH"
    return "ADVISORY_ONLY"
```

Game-level status is separate (editorial, from research):
- `DAILY_539`: `"MAINTENANCE"` — signal space exhausted (L82), strategies monitored
- `BIG_LOTTO`: `"MAINTENANCE"` — signal space exhausted (L91), strategies monitored
- `POWER_LOTTO`: `"PRODUCTION"` — active signal detection, RSM monitored

---

## 3. Recommended Bet Configs per Game

These define which bet counts and which strategy keys to display on the page.
Strategy keys used for metadata only (edge, trend, badge); predictions come from coordinator.

### DAILY_539
| Display | Bet Count | Primary Strategy Key | RSM Edge |
|---------|-----------|----------------------|----------|
| 1注 | 1 | `acb_1bet` | +3.27% |
| 2注 ★ | 2 | `midfreq_acb_2bet` | +8.46% |
| 3注 ★ | 3 | `acb_markov_midfreq_3bet` | +8.50% |
| 5注 | 5 | `f4cold_5bet` | +6.61% |

### BIG_LOTTO
| Display | Bet Count | Primary Strategy Key | RSM Edge |
|---------|-----------|----------------------|----------|
| 2注 ★ | 2 | `regime_2bet` | +3.64% |
| 3注 ★ | 3 | `ts3_regime_3bet` | +3.51% |
| 5注 ★ | 5 | `p1_dev_sum5bet` | +4.04% |

### POWER_LOTTO
| Display | Bet Count | Primary Strategy Key | RSM Edge |
|---------|-----------|----------------------|----------|
| 3注 ★ | 3 | `fourier_rhythm_3bet` | +3.16% |
| 4注 ★ | 4 | `pp3_freqort_4bet` | +3.40% |
| 5注 | 5 | `orthogonal_5bet` | +2.76% |

---

## 4. Response Schema

```json
{
  "generated_at": "2026-03-19T10:30:00.000Z",
  "mode": "direct",
  "games": {
    "DAILY_539": {
      "game_status": "MAINTENANCE",
      "game_status_note": "信號空間窮盡（L82），現有策略持續監控中",
      "latest_period": "115000068",
      "next_period": "115000069",
      "bets": [
        {
          "bet_count": 1,
          "strategy_key": "acb_1bet",
          "strategy_label": "ACB 1注",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0327,
          "trend": "STABLE",
          "alert": false,
          "sharpe_300p": 0.092,
          "numbers": [
            [4, 18, 19, 25, 34]
          ],
          "special": null
        },
        {
          "bet_count": 2,
          "strategy_key": "midfreq_acb_2bet",
          "strategy_label": "MidFreq+ACB 2注",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0846,
          "trend": "STABLE",
          "alert": false,
          "sharpe_300p": 0.185,
          "numbers": [
            [4, 18, 19, 25, 34],
            [5, 7, 10, 12, 23]
          ],
          "special": null
        },
        {
          "bet_count": 3,
          "strategy_key": "acb_markov_midfreq_3bet",
          "strategy_label": "ACB+Markov+MidFreq 3注",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0850,
          "trend": "STABLE",
          "alert": false,
          "sharpe_300p": 0.174,
          "numbers": [
            [4, 18, 19, 25, 34],
            [5, 7, 10, 12, 23],
            [6, 17, 29, 31, 35]
          ],
          "special": null
        },
        {
          "bet_count": 5,
          "strategy_key": "f4cold_5bet",
          "strategy_label": "F4Cold 5注",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0661,
          "trend": "STABLE",
          "alert": false,
          "sharpe_300p": 0.132,
          "numbers": [
            [4, 18, 19, 25, 34],
            [5, 7, 10, 12, 23],
            [6, 17, 29, 31, 35],
            [2, 3, 8, 11, 20],
            [15, 16, 22, 28, 39]
          ],
          "special": null
        }
      ]
    },
    "BIG_LOTTO": {
      "game_status": "MAINTENANCE",
      "game_status_note": "信號邊界研究確認（L91）：49C6 與公平隨機過程無差異，策略維護中",
      "latest_period": "115000036",
      "next_period": "115000037",
      "bets": [
        {
          "bet_count": 2,
          "strategy_key": "regime_2bet",
          "strategy_label": "Regime 2注",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0364,
          "trend": "STABLE",
          "alert": false,
          "sharpe_300p": 0.140,
          "numbers": [[1, 8, 22, 30, 38, 43], [3, 12, 19, 26, 34, 47]],
          "special": null
        }
      ]
    },
    "POWER_LOTTO": {
      "game_status": "PRODUCTION",
      "game_status_note": "RSM 持續監控中，策略穩定",
      "latest_period": "115000021",
      "next_period": "115000022",
      "bets": [
        {
          "bet_count": 3,
          "strategy_key": "fourier_rhythm_3bet",
          "strategy_label": "Fourier Rhythm 3注",
          "strategy_status": "PRODUCTION",
          "edge_300p": 0.0316,
          "trend": "STABLE",
          "alert": false,
          "sharpe_300p": 0.090,
          "numbers": [[3, 10, 19, 26, 36, 37], [8, 14, 22, 27, 30, 35], [5, 12, 17, 20, 25, 38]],
          "special": 8
        }
      ]
    }
  }
}
```

---

## 5. Error Contract

| HTTP Status | Meaning | Frontend Behavior |
|-------------|---------|-------------------|
| 200 | Success | Render predictions |
| 500 | Coordinator failure | Show error state, "無法生成預測，請稍後再試" |
| 503 | Service unavailable | Show offline state |

Partial failure: if one game fails, others still returned. Failed game includes:
```json
{
  "game_status": "ERROR",
  "error": "Coordinator failed: <message>",
  "bets": []
}
```

---

## 6. Strategy Status Labels (Display)

| Status | Display Text | Color | Icon |
|--------|-------------|-------|------|
| `PRODUCTION` | `PRODUCTION` | green | ✅ |
| `WATCH` | `WATCH` | amber | ⚠️ |
| `ADVISORY_ONLY` | `ADVISORY` | blue | 🔵 |
| `MAINTENANCE` | `MAINTENANCE` | red/gray | 🔴 |
| `ERROR` | `ERROR` | red | ❌ |

---

## 7. Period Number Logic

Period numbers are derived from the stats endpoint `GET /api/data/stats` or from `dataRange` in coordinator response.

```
latest_period = max draw_id in history
next_period = latest_period + 1   (simple integer increment)
```

For DAILY_539: `115000068` → `115000069`
For BIG_LOTTO: `115000036` → `115000037`
For POWER_LOTTO: `115000021` → `115000022`

---

## 8. Frontend Fetch Pattern

```javascript
// Single call — no frontend prediction computation
async function fetchNextDrawSummary() {
    const response = await apiClient.get('/api/next-draw-summary', { mode: 'direct' });
    return response;   // Render games.DAILY_539, games.BIG_LOTTO, games.POWER_LOTTO
}
```

Single call, single render, no multiple-request coordination needed.

---

## 9. What This Contract Does NOT Include

- No frontend prediction computation (all from backend)
- No strategy evolution or new strategy creation
- No manual override of numbers
- No real-time auto-refresh (user-triggered only)
- No advisory section in this contract (Phase 6 adds optional advisory)
