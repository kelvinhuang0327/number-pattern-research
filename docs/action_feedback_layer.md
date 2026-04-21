# Phase R — Action Feedback & Outcome Tracking Layer

**Date**: 2026-04  
**Depends on**: Phase Q (Actionable Intelligence)  
**Files added/modified**: see [Modified Files](#modified-files)

---

## Objective

Close the intelligence feedback loop:

```
Actionable Intelligence → Action Tracking → Outcome Measurement
    → Effectiveness Classification → Rule Scoring → Meta Insights
```

The system must answer:
- 哪些建議真的有效
- 哪些規則在浪費時間
- 哪些規則應該調整或刪除

---

## Strict Constraints

- Does NOT modify prediction logic
- Does NOT modify validation logic
- Does NOT modify ranking logic
- Does NOT auto-execute any action
- Only tracks and evaluates outcomes against real data
- All deltas traceable to strategy_states JSON ground truth

---

## Architecture

### Data Flow

```
/api/actionable/summary (Phase Q)
    │
    ├── register_actions_from_summary()
    │       creates tracking records for new insights (deduped by draw bucket)
    │
/api/actionable/feedback (Phase R)
    │
    ├── evaluate_pending_actions()
    │       compares current strategy metrics to baseline at window close
    │
    ├── _aggregate_rule_stats()
    │       groups EFFECTIVE/NEUTRAL/NEGATIVE by rule code
    │
    └── _build_meta_insights()
            KEEP / TUNE / REMOVE recommendations
```

### Persistence

All tracking data is stored in:

```
lottery_api/data/action_feedback.json
```

Structure:
```json
{
  "actions": [...],
  "last_updated": "ISO-8601"
}
```

---

## Phase 1 — Action Tracking Schema

Each action record:

```json
{
  "action_id":        "uuid4",
  "lottery_type":     "DAILY_539 | BIG_LOTTO | POWER_LOTTO",
  "strategy":         "strategy_name",
  "priority":         "P0 | P1 | P2",
  "action_type":      "R01_DEGRADING | R03_LEARNING_INEFFECTIVE | ...",
  "action_title":     "策略可能進入衰退期",
  "created_at":       "ISO-8601",
  "created_draw_ref": 5030,
  "baseline": {
    "edge_1500p": 0.0903,
    "sharpe":     0.1749,
    "drawdown":   0.016
  },
  "tracking_window":  30,
  "status":           "OPEN | TRACKING | COMPLETED",
  "evaluated_at":     "ISO-8601 or null",
  "outcome":          null
}
```

Deduplication fingerprint:
```
"{lottery_type}|{action_code}|{strategy}|{draw_bucket}"
```
where `draw_bucket = (created_draw_ref // 10) * 10`. One record per 10-draw bucket.

---

## Phase 2 — Tracking Windows

| Window | Purpose |
|--------|---------|
| 10 draws (status: TRACKING) | Mark as in-progress |
| 30 draws (default evaluation) | Outcome measured |
| 100 draws (optional) | Not yet implemented — extend `tracking_window` field |

Actions are NOT evaluated immediately upon creation.

---

## Phase 3 — Outcome Measurement

At evaluation time, current strategy metrics are read from `strategy_states_{lt}.json`:

```python
edge_delta     = current_edge_1500p - baseline_edge_1500p
sharpe_delta   = current_sharpe     - baseline_sharpe
drawdown_delta = current_drawdown   - baseline_drawdown
```

Baseline is snapshotted at action creation time.

---

## Phase 4 — Effectiveness Classification

| Class | Conditions |
|-------|-----------|
| **EFFECTIVE** | `edge_delta > 0.003` AND `sharpe_delta > 0.005` AND `drawdown_delta ≤ 0.002` |
| **NEUTRAL** | All changes within noise floor |
| **NEGATIVE** | `edge_delta < -0.003` OR `sharpe_delta < -0.005` OR `drawdown_delta > 0.002` |

Noise floors (configurable):
- `EDGE_NOISE = 0.003` (0.3 percentage points)
- `SHARPE_NOISE = 0.005`
- `DRAWDOWN_NOISE = 0.002`

---

## Phase 5 — Completed Action Outcome

```json
{
  "edge_delta":     0.0042,
  "sharpe_delta":   0.0021,
  "drawdown_delta": -0.002,
  "effectiveness":  "EFFECTIVE",
  "draws_elapsed":  32,
  "current_metrics": {
    "edge_1500p": 0.0903,
    "sharpe":     0.1749,
    "drawdown":   0.016
  }
}
```

---

## Phase 6 — Rule Performance Tracking

Per `action_type` (rule code):

```json
{
  "action_type":        "R03_LEARNING_INEFFECTIVE",
  "total":              2,
  "effective_count":    1,
  "neutral_count":      1,
  "negative_count":     0,
  "effectiveness_rate": 0.5,
  "avg_edge_delta":     0.0022,
  "avg_sharpe_delta":   0.0016,
  "avg_drawdown_delta": -0.0005,
  "rule_score":         0.5,
  "recommendation":     "TUNE"
}
```

---

## Phase 7 — Rule Scoring

```
rule_score = (effective_count - negative_count) / total
```

Range: [-1.0, +1.0]  
- `+1.0` = all outcomes EFFECTIVE  
- `0.0`  = equal effective/negative, or all NEUTRAL  
- `-1.0` = all outcomes NEGATIVE

Requires ≥ 2 samples before issuing KEEP/TUNE/REMOVE recommendation.

---

## Phase 8 — Meta Insights

| Recommendation | Condition |
|---------------|-----------|
| KEEP   | `rule_score > 0.5` AND `total >= 2` |
| TUNE   | `0 < rule_score ≤ 0.5` AND `total >= 2` |
| REMOVE | `rule_score ≤ 0` AND `total >= 2` |
| INSUFFICIENT_DATA | `total < 2` |

Meta summary labels:
- `"60% 建議有效 — 系統整體表現穩健"`
- `"45% 建議有效 — 部分規則需調整"`
- `"僅 30% 建議有效 — 多數規則效果有限，需重新檢視"`

---

## Phase 9 — API Contract

### `GET /api/actionable/summary` (modified)
Phase Q endpoint, now also registers new actions as a side-effect.

### `GET /api/actionable/feedback`
```json
{
  "ok": true,
  "feedback": {
    "totals": {
      "all": 11, "open": 1, "tracking": 1, "completed": 9
    },
    "effectiveness": {
      "effective_count": 3, "neutral_count": 4, "negative_count": 2,
      "effective_pct": 0.33, "negative_pct": 0.22,
      "summary_label": "33% 建議有效 — 部分規則需調整"
    },
    "rule_stats": { ... },
    "meta_insights": {
      "total_evaluated": 9, "total_effective": 3, "overall_rate": 0.33,
      "top_rules": [...], "worst_rules": [...],
      "keep": [], "tune": ["R03_LEARNING_INEFFECTIVE"], "remove": ["R06_NO_VALIDATED"],
      "summary": "..."
    },
    "recent_completed": [...],
    "last_updated": "ISO-8601"
  }
}
```

### `GET /api/actionable/actions`
| Param | Type | Description |
|-------|------|-------------|
| `status` | string? | Filter: OPEN \| TRACKING \| COMPLETED |
| `lottery` | string? | Filter: DAILY_539 \| BIG_LOTTO \| POWER_LOTTO |
| `limit` | int | Default 100, max 500 |

### `GET /api/actionable/rules`
Returns rules sorted by `rule_score` descending:
```json
{
  "ok": true,
  "count": 8,
  "rules": [
    { "action_type": "R05_WEAK_RESEARCH", "rule_score": 1.0, "recommendation": "INSUFFICIENT_DATA", ... },
    { "action_type": "R03_LEARNING_INEFFECTIVE", "rule_score": 0.5, "recommendation": "TUNE", ... },
    ...
  ]
}
```

---

## Phase 10 — UI

UI block: **📊 建議成效** rendered by `FeedbackRenderer.js`

Displayed once per page (on DAILY_539 game card) with collapsible panel.

Shows:
- 3 stat cards: 已完成 / 追蹤中 / 有效率 %
- Summary label (color-coded by effectiveness rate)
- Effectiveness bar (green/grey/red segments)
- Top/worst rule rows with rule_score and recommendation
- KEEP/TUNE/REMOVE tag cloud
- Recent 5 completed actions

---

## Sample Output (3 Lotteries)

### Summary label
```
僅 30% 建議有效 — 多數規則效果有限，需重新檢視
```

### Rule ranking (10 actions evaluated)

| Rule | Score | Eff% | Rec |
|------|-------|------|-----|
| R05_WEAK_RESEARCH | +1.00 | 100% | INSUFFICIENT_DATA (n=1) |
| R03_LEARNING_INEFFECTIVE | +0.50 | 50% | TUNE |
| R08_LOW_SHARPE | 0.00 | 0% | INSUFFICIENT_DATA |
| R06_NO_VALIDATED | 0.00 | 50% | REMOVE |
| R07_ALL_WATCH | 0.00 | 0% | INSUFFICIENT_DATA |
| R02_NEAR_THRESHOLD | 0.00 | 0% | INSUFFICIENT_DATA |
| R09_HIGH_DRAWDOWN | -1.00 | 0% | INSUFFICIENT_DATA |
| R01_DEGRADING | -1.00 | 0% | INSUFFICIENT_DATA |

### Meta conclusions
- **TUNE**: `R03_LEARNING_INEFFECTIVE` — 有效率 50%，尚有改善空間
- **REMOVE**: `R06_NO_VALIDATED` — 即使出現 EFFECTIVE 結果仍有同比例 NEGATIVE，規則方向不一致

---

## Modified Files

| File | Type | Description |
|------|------|-------------|
| `lottery_api/engine/action_feedback.py` | NEW | Core engine: tracking, evaluation, scoring, meta insights |
| `lottery_api/routes/actionable.py` | MODIFIED | Added 3 new Phase R endpoints; summary endpoint now registers actions |
| `src/ui/components/FeedbackRenderer.js` | NEW | `renderFeedbackBlock()` UI component |
| `src/core/handlers/NextDrawHandler.js` | MODIFIED | Imports FeedbackRenderer; fetches feedback API; renders block on DAILY_539 card |
| `lottery_api/data/action_feedback.json` | AUTO-CREATED | Persistent tracking store (created on first API call) |

---

## Validation Guarantees

1. All deltas computed against real `strategy_states_{lt}.json` data — no fabricated metrics
2. Action deduplication prevents double-counting per draw bucket
3. No modification to prediction, validation, or ranking pipelines
4. Atomic file writes (tmp + os.replace) prevent corrupt state on crash
5. All recommendations require ≥ 2 samples — avoids noise-driven false conclusions
