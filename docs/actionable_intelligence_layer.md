# Phase Q — Actionable Intelligence Layer

> Version: v1.0 | Status: COMPLETE

---

## Overview

Phase Q upgrades the Explainability Layer (Phase P) from passive explanation into **active decision guidance**.

| Phase P (Explainability) | Phase Q (Actionable Intelligence) |
|--------------------------|-----------------------------------|
| What happened | What happened + What to do next |
| Passive trace | Active recommendations |
| Historical record | Operator-level decision hints |

**Core constraint**: Does NOT modify prediction results, validation logic, or any system state. Only generates recommendations.

---

## Architecture

```
strategy_states_*.json  +  latest explanation (DB or live fallback)
        │
        ▼
engine/actionable_intelligence.py
    ├── _load_strategy_states()        — reads strategy_states JSON
    ├── _load_latest_explanation()     — DB first, live fallback
    ├── _analyze_signals()             — Phase 1: signal analysis
    ├── _apply_rules()                 — Phase 2: 10 rule-based insights
    ├── _compute_health()              — Phase 4: GOOD / WATCH / RISK
    └── get_actionable_summary()       — public entry point
        │
        ▼
routes/actionable.py
    └── GET /api/actionable/summary
        │
        ▼
src/ui/components/ActionableRenderer.js
    └── renderActionableBlock(data, opts?)
        │
        ▼
NextDrawHandler.js — "🧠 系統建議" block per game card
```

---

## Input Sources

All insights trace to **real system data only**. No hallucination.

| Source | Fields Used |
|--------|-------------|
| `strategy_states_{lt}.json` | `validated_status`, `composite_score`, `edge_150p/500p/1500p`, `perm_p`, `mcnemar_p`, `sharpe`, `max_drawdown_rate` |
| Latest explanation (DB / live) | `learning.gate`, `learning.research_score`, `learning.ranking_changed`, `quality.ranking_changed`, `quality.quality_label`, `quality.total_abs_delta` |

---

## Phase 1 — Signal Analysis

`_analyze_signals()` computes:

| Signal Group | Metrics |
|-------------|---------|
| Validation | `validated_count`, `watch_count`, `has_validated`, `all_watch` |
| Stability | `edge_degrading` (150>500>1500 decreasing), `sharpe_weak` (< 0.05) |
| Learning | `gate`, `research_score`, `ranking_changed`, `effective`, `weak_signal` |
| Quality | `dominant` (ranking_changed), `total_abs_delta` |

---

## Phase 2 — Rule-Based Insight Engine

10 rules, each mapping **data → insight → action**:

| Code | Trigger | Priority | Message |
|------|---------|----------|---------|
| R01 | VALIDATED + edge_degrading | P1 | 策略可能進入衰退期，建議觀察或降權 |
| R02 | WATCH + edge_1500p > 0 + perm_p < 0.15 | P2 | 策略接近驗證門檻，建議持續觀察或擴充樣本 |
| R03 | learning enabled + ranking_changed=False | P2 | Learning 未對排序產生影響 |
| R04 | quality.ranking_changed=True | P2 | Winning Quality 為主要決策因子 |
| R05 | abs(research_score) < 0.05 | P2 | 研究訊號弱，learning 僅具保護作用 |
| R06 | validated_count = 0 | **P0** | 目前無完整驗證策略，需保守使用 |
| R07 | all_watch = True (without R06) | P1 | 所有策略仍在觀察期，建議謹慎投注 |
| R08 | sharpe < 0.05 and ≥ 0 | P2 | 策略 Sharpe 偏低，風險調整後報酬空間有限 |
| R09 | max_drawdown_rate > 0.05 | P1 | 近期回撤超過警戒線 |
| R10 | learning.gate = DISABLED | P1 | Learning 系統停用中，缺少即時修正能力 |

---

## Phase 3 — Action Format

Each insight generates a structured action:

```json
{
  "priority": "P0 | P1 | P2",
  "title": "短句行動標題",
  "reason": "觸發此行動的原因",
  "expected_effect": "預期效果",
  "risk": "執行風險",
  "condition_to_stop": "停止/完成條件"
}
```

**Priority rules**:
- **P0**: No validated strategy, severe data issues
- **P1**: Degradation trends, learning disabled, high drawdown
- **P2**: Monitoring opportunities, weak signals, informational

---

## Phase 4 — System Health

| Health | Condition |
|--------|-----------|
| ✅ GOOD | ≥ 1 VALIDATED + no P0 + no P1 insights |
| ⚠️ WATCH | No P0 but has P1 insights |
| 🔴 RISK | P0 insight present OR validated_count = 0 |

---

## API Contract

### `GET /api/actionable/summary`

**Response**:
```json
{
  "ok": true,
  "summary": {
    "DAILY_539": {
      "lottery_type": "DAILY_539",
      "health": "GOOD",
      "health_label": "✅ 穩定",
      "health_color": "#00c864",
      "signals_summary": {
        "validated_count": 5,
        "watch_count": 1,
        "total": 6,
        "best_strategy": "f4cold_5bet",
        "best_validated_status": "VALIDATED",
        "learning_gate": "ENABLED",
        "learning_effective": false,
        "quality_dominant": true
      },
      "insights": [
        {
          "priority": "P2",
          "code": "R03_LEARNING_INEFFECTIVE",
          "title": "Learning 未產生實質影響",
          "message": "Learning 未對排序產生影響，可能訊號不足或同質性過高",
          "detail": "Learning gate=ENABLED，但 ranking_changed=False...",
          "data_source": "learning.gate=ENABLED, learning.ranking_changed=False, research_score=0.2133"
        }
      ],
      "top_actions": [
        {
          "priority": "P2",
          "title": "觀察 Learning 系統效益",
          "reason": "Learning bonus 已套用但未改變最終排名",
          "expected_effect": "了解 learning 影響力以決定是否調整假說或擴大樣本",
          "risk": "無直接損失風險，為信息類觀察",
          "condition_to_stop": "research_score 顯著提升後 ranking_changed=True"
        }
      ],
      "key_observations": [
        "Learning 未對排序產生影響，可能訊號不足或同質性過高",
        "Winning Quality 為主要決策因子（降低分獎風險）"
      ]
    },
    "BIG_LOTTO": { ... },
    "POWER_LOTTO": { ... }
  }
}
```

---

## Sample Output (Actual Data — 2026-04-17)

### DAILY_539
```
health: GOOD ✅ 穩定
strategies: 5 VALIDATED, 1 WATCH
best: f4cold_5bet (VALIDATED)
learning_gate: ENABLED (not effective — ranking unchanged)
quality_dominant: True

insights:
  [P2] R03 Learning 未對排序產生影響
  [P2] R04 Winning Quality 為主要決策因子
```

### BIG_LOTTO
```
health: GOOD ✅ 穩定
strategies: 1 VALIDATED, 10 WATCH
best: p1_deviation_4bet (VALIDATED)
learning_gate: WEAK (not effective)
quality_dominant: True

insights:
  [P2] R03 Learning 未對排序產生影響
  [P2] R04 Winning Quality 為主要決策因子
  [P2] R05 研究訊號弱
```

### POWER_LOTTO
```
health: RISK 🔴 高風險
strategies: 0 VALIDATED, 7 WATCH
best: orthogonal_5bet (WATCH)
learning_gate: ENABLED (not effective)
quality_dominant: True

insights:
  [P0] R06 目前無完整驗證策略，需保守使用
  [P2] R02 策略接近驗證門檻（orthogonal_5bet）
  [P2] R03 Learning 未對排序產生影響
  [P2] R04 Winning Quality 為主要決策因子
```

---

## UI Mock Text

```
┌─────────────────────────────────────────────┐
│ 🧠 系統建議    [✅ 穩定]              [▼]    │
├─────────────────────────────────────────────┤
│ ▎ Learning 未對排序產生影響，可能訊號不足     │
│ ▎ Winning Quality 為主要決策因子              │
│                                              │
│ [P2 建議] 觀察 Learning 系統效益             │
│   Learning bonus 已套用但未改變最終排名       │
│                                     詳情▾    │
│                                              │
│ [P2 建議] 確認 Quality 調整方向合理          │
│   Quality 調整改變了原始排名                  │
│                                              │
│ 策略：5✅ 1⚠️  Learning：ENABLED  Quality：主導 │
└─────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────┐
│ 🧠 系統建議    [🔴 高風險]           [▼]    │
├─────────────────────────────────────────────┤
│ ▎ 目前無完整驗證策略，需保守使用             │
│ ▎ 策略接近驗證門檻，建議持續觀察             │
│ ▎ Learning 未對排序產生影響                  │
│                                              │
│ [P0 緊急] 切換至保守模式                     │
│   無 VALIDATED 策略代表信號強度不足          │
│                                     詳情▾    │
│   預期效果：減少在低確信策略上的過度依賴      │
│   風險：可能錯過 WATCH 中的短期機會          │
│   停止條件：至少 1 個策略達到 VALIDATED      │
└─────────────────────────────────────────────┘
```

---

## Files Changed

### New Files
| File | Purpose |
|------|---------|
| `lottery_api/engine/actionable_intelligence.py` | Signal analysis + 10 rules + action generation + health scoring |
| `lottery_api/routes/actionable.py` | `GET /api/actionable/summary` endpoint |
| `src/ui/components/ActionableRenderer.js` | `renderActionableBlock()` — collapsible 🧠 block with priority-colored action cards |

### Modified Files
| File | Change |
|------|--------|
| `lottery_api/app.py` | Import + register `actionable.router` with tag `["Actionable"]` |
| `src/core/handlers/NextDrawHandler.js` | Import `renderActionableBlock`; parallel fetch `/api/actionable/summary`; render per game card below explainability block |

---

## Validation Checklist

| Requirement | Status |
|------------|--------|
| ① No hallucinated suggestion — all insights trace to data fields | ✅ `data_source` field on each insight |
| ② No contradiction with explainability layer | ✅ Uses same explanation object as Phase P |
| ③ No impact on prediction output | ✅ Engine is read-only; uses `coordinator_predict` in fallback mode only for explanation state |
| ④ Covers all 3 lottery types | ✅ DAILY_539, BIG_LOTTO, POWER_LOTTO |
| ⑤ System answers: What / Why / What next | ✅ Explainability (What/Why) + Actionable (What next) |
| ⑥ Priority P0/P1/P2 classification | ✅ 10 rules correctly classified |
| ⑦ Per-lottery health GOOD/WATCH/RISK | ✅ Verified with actual data |

---

## Success Criteria Verification

> "System can answer: What is happening / Why it is happening / What should be done next"

| Question | Source |
|----------|--------|
| What is happening | `health`, `key_observations` |
| Why it is happening | `insights[].detail` + `insights[].data_source` |
| What should be done next | `top_actions[].title` + `top_actions[].reason` + `top_actions[].expected_effect` |

**VERDICT: COMPLETE** ✅
