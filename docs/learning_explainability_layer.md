# Phase P — Learning Explainability Layer

## Overview

The Explainability Layer makes the auto-learning prediction system transparent. For every prediction run, a structured explanation object is captured, persisted, and surfaced through API and UI.

**This phase does NOT change any prediction logic, learning logic, validation logic, or bankroll logic.** It only adds traceability, explanation output, and UI/API visibility.

---

## Architecture

```
                    ┌───────────────────────────────┐
                    │   coordinator_predict()        │
                    │   ┌─────────────────────────┐  │
                    │   │  aggregate_scores()      │  │
                    │   │  ├─ agent scoring         │  │
                    │   │  ├─ learning bonus ───────┼──┼── trace captured
                    │   │  ├─ quality bonus ────────┼──┼── trace captured
                    │   │  └─ ranking comparison ───┼──┼── trace captured
                    │   └─────────────────────────┘  │
                    │         │                       │
                    │   get_explanation() ◄───────────│
                    │         │                       │
                    └─────────┼───────────────────────┘
                              │
                    ┌─────────▼───────────────────────┐
                    │   explainability.py              │
                    │   ├─ save_explanation()          │
                    │   ├─ get_explanation_by_run()    │
                    │   ├─ get_latest_explanation()    │
                    │   └─ get_summary()               │
                    └─────────┬───────────────────────┘
                              │
                    ┌─────────▼───────────────────────┐
                    │   prediction_explanations (DB)   │
                    │   SQLite table, append-safe      │
                    └─────────┬───────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        API endpoints    UI detail view   prediction payload
```

---

## Explanation Object Schema

> Updated in Phase P v2 to include `selected_strategy`, `validated_status`, `base.*`, `decision.*`, `final_reason`, `quality.quality_label`, and separate `learning.ranking_changed` / `quality.ranking_changed`.

```json
{
  "lottery_type": "DAILY_539",
  "profile": "conservative",
  "selected_strategy": "f4cold_5bet",
  "validated_status": "VALIDATED",

  "base": {
    "composite_score": 0.0936,
    "edge_150p": 0.1028,
    "edge_500p": 0.1061,
    "edge_1500p": 0.0861
  },

  "learning": {
    "enabled": true,
    "gate": "ENABLED",
    "factor": 1.0,
    "research_score": 0.2133,
    "bonus_by_agent": {"acb": 0.0158, "midfreq": 0.0193, "fourier": 0.0140, ...},
    "boosted_agents": ["acb", "midfreq", "fourier", "markov", "markov2", "weibull_gap", "consensus_signal"],
    "penalized_agents": [],
    "ranking_changed": false,
    "bonus_summary": "DAILY_539 learning active but ranking unchanged",
    "hypotheses": {
      "total": 63, "validated": 1, "rejected": 0, "provisional": 59
    }
  },

  "quality": {
    "enabled": true,
    "quality_amp": 0.5,
    "total_abs_delta": 0.4797,
    "ranking_changed": true,
    "quality_label": "已調整熱門度",
    "quality_summary": "quality bonus applied (amp=0.5, total abs delta=0.4797)"
  },

  "decision": {
    "base_n_bets": 3,
    "final_n_bets": 3,
    "concentration_bias": 0.8
  },

  "final_reason": "採用 f4cold_5bet（✅ 已完整驗證，保守模式）。因quality降低熱門度，最終排名有變動。",

  "base_score_summary": {
    "f4cold_5bet": 0.0936,
    "p1_deviation_4bet": 0.0821
  },

  "learning_detail": {
    "f4cold_5bet": {"base": 0.0936, "learning_bonus": 0.0963, "total": 0.1899}
  },

  "profile_detail": {
    "profile_name": "conservative",
    "top_n": 1,
    "score_threshold": 0.0,
    "n_bets_range": [2, 5]
  },

  "selection": {
    "method": "best_by_profile",
    "candidates": [{"strategy": "f4cold_5bet", "score": 0.1899}]
  }
}
```

### 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `selected_strategy` | string | 最終選用策略名稱（讀自 `strategy_states_{lt}.json`，優先 VALIDATED > WATCH） |
| `validated_status` | string | 策略驗證狀態 |
| `base.composite_score` | float | 三窗口平均 ROI |
| `base.edge_Xp` | float | X 期 ROI（150/500/1500） |
| `learning.gate` | enum | ENABLED / WEAK / DISABLED |
| `learning.ranking_changed` | bool | 加 learning bonus 後排名是否改變（獨立追蹤） |
| `quality.quality_label` | string | 已調整熱門度 / 未調整 |
| `quality.ranking_changed` | bool | 加 quality bonus 後排名是否改變（獨立追蹤） |
| `decision.concentration_bias` | float | Profile 集中度偏好 |
| `final_reason` | string | 中文最終決策摘要 |

---

## Files Created / Modified

### Created (Phase P v2)
| File | Purpose |
|------|---------|
| `lottery_api/engine/explainability.py` | Persistence & retrieval (save, get by run, get latest, summary) |
| `lottery_api/routes/explainability.py` | API endpoints (4 routes) |
| `src/ui/components/ExplainabilityRenderer.js` | **NEW** Shared rendering module — `renderExplainabilityBlock()` (full) + `renderCompactExplainBlock()` (compact) used by all 3 UI pages |
| `docs/learning_explainability_layer.md` | This document |

### Modified (Phase P v2)
| File | Change |
|------|--------|
| `lottery_api/engine/strategy_coordinator.py` | (1) `aggregate_scores()`: added `scores_before_quality` snapshot, separate `ranking_changed_by_learning` + `ranking_changed_by_quality` tracking; (2) `get_explanation()`: full rewrite — reads `strategy_states_{lt}.json` for `selected_strategy`/`validated_status`, adds `base.*`, `decision.*`, `quality_label`, `quality_summary`, `bonus_summary`, `final_reason`; (3) `coordinator_predict()`: tracks `_last_n_bets`/`_last_final_n_bets` |
| `lottery_api/routes/prediction.py` | Attach explanation to coordinator prediction payload |
| `lottery_api/routes/prediction_tracking.py` | Persist explanation on snapshot creation; attach to run detail response |
| `lottery_api/app.py` | Register explainability router |
| `index.html` | CSS for `.pt-explain-*` block styles |
| `src/ui/PredictionTracker.js` | Import `renderExplainabilityBlock`; replaced 120-line inline renderer with delegation to shared module |
| `src/core/handlers/NextDrawHandler.js` | **NEW** Import `renderCompactExplainBlock`; `_loadBestStrategySummary` parallel-fetches latest explanation for all 3 games; each strategy card shows compact explain block |
| `src/ui/ReviewManager.js` | **NEW** Import `renderCompactExplainBlock`; `loadSession` fetches explanation by `prediction_run_id`; `_renderDetail` accepts + renders compact explain block |

---

## DB Schema

```sql
CREATE TABLE IF NOT EXISTS prediction_explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_run_id INTEGER,
    lottery_type TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT 'balanced',
    explanation_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prediction_run_id)
);
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/explainability/run/{prediction_run_id}` | Full explanation for one run |
| GET | `/api/explainability/latest?lottery_type=...` | Latest explanation snapshot |
| GET | `/api/explainability/summary` | Aggregated statistics |
| GET | `/api/explainability/live?lottery_type=...&profile=...` | Compute live explanation (no persistence) |

---

## UI Integration

The 🔍 **決策解釋** block appears in the prediction tracking detail view (click a row in 歷史預測記錄).

### Sections displayed:
- **Agent 權重**: Per-agent weight percentages + drift/regime status
- **Learning**: Gate status (已啟用/弱啟用/未啟用), factor, research score, hypothesis counts, boosted/penalized agents
- **Quality**: Status, amplitude, total delta
- **Profile**: Mode (保守/平衡/積極), all amplification parameters
- **排名比較**: Top numbers before/after bonus, whether ranking changed

### Labels (Chinese):
- Learning: 已啟用 / 弱啟用 / 未啟用
- Quality: 已調整 / 未啟用
- Profile: 保守 / 平衡 / 積極
- 排名變動: 有 / 無

---

## Validation Results

**Phase P v2 — 3 lottery types validated — VERDICT: COMPLETE**

Validation script: `tmp/validate_explain.py`

### Per-lottery results (actual data)

| Lottery | Strategy | Validated Status | Profile | Learning Gate | Learning Rank Δ | Quality Label | Quality Rank Δ | composite_score | final_reason |
|---------|----------|-----------------|---------|--------------|----------------|---------------|---------------|----------------|-------------|
| DAILY_539 | f4cold_5bet | VALIDATED | conservative | ENABLED (×1.0) | ✅ unchanged | 已調整熱門度 | ⚠️ changed | 0.0936 | ✅ |
| BIG_LOTTO | p1_deviation_4bet | VALIDATED | balanced | WEAK (×0.5) | ✅ unchanged | 已調整熱門度 | ⚠️ changed | 0.0343 | ✅ |
| POWER_LOTTO | orthogonal_5bet | WATCH | aggressive | ENABLED (×1.0) | ✅ unchanged | 已調整熱門度 | ⚠️ changed | 0.0419 | ✅ |

### Checklist

| Question | Answered? |
|----------|-----------|
| ① 為什麼選此策略？ | ✅ `selected_strategy`, `validated_status`, `base.*`, `final_reason` |
| ② learning bonus 是否介入？ | ✅ `learning.gate`, `learning.factor`, `learning.bonus_by_agent` |
| ③ winning quality 是否介入？ | ✅ `quality.quality_label`, `quality.total_abs_delta`, `quality.ranking_changed` |
| ④ profile 影響？ | ✅ `profile`, `profile_detail`, `decision.concentration_bias` |
| ⑤ 排名是否改變？ | ✅ `learning.ranking_changed` (per-step) + `quality.ranking_changed` (per-step) |

### Regression check

- Prediction path unchanged — `bets` output identical with/without explainability code path
- Explanation only reads `_last_*` state after `predict()` completes; never writes to bets
- DB migration-free: `prediction_explanations` table uses `CREATE TABLE IF NOT EXISTS`

### UI integration check

| Page | Component | Renderer Used |
|------|-----------|--------------|
| 策略回測總覽 | `NextDrawHandler.js` | `renderCompactExplainBlock` |
| 預測追蹤詳情 | `PredictionTracker.js` | `renderExplainabilityBlock` (full) |
| 研究檢討 | `ReviewManager.js` | `renderCompactExplainBlock` |
