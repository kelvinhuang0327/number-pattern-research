# SB3 Repo Audit — Lottery RL Integration
**Date:** 2026-03-18 | **Auditor:** LLM Research Board

---

## 1. Prediction Candidate Generation Points

| Entry Point | File | Function | Output |
|-------------|------|----------|--------|
| **Unified Predict** | `tools/quick_predict.py` | `predict_539/biglotto/power()` | `(list[list[int]], strategy_str)` |
| **Coordinator** | `lottery_api/engine/strategy_coordinator.py` | `coordinator_predict(lt, history, n_bets, mode)` | `(list[list[int]], desc)` |
| **RSM Bootstrap** | `tools/rsm_bootstrap.py` | `get_*_strategies_inline()` | `list[{name, predict_func, num_bets}]` |
| **Per-Agent Scores** | `strategy_coordinator.py` | `_acb_score_all()`, `_fourier_score_all()`, `_markov_score_all()`, `_midfreq_score_all()` | `Dict[int, float]` (full number space) |

### Agent Score Flow
```
_acb_score_all(history, window=100)     ─┐
_fourier_score_all(history, window=500) ─┤→ normalize → weighted_aggregate → rank-slice → bets
_markov_score_all(history, window=30)   ─┤
_midfreq_score_all(history, window=100) ─┘
  + S2: _markov2_score_all()
  + S2: _weibull_gap_score_all()
```

---

## 2. Strategy Score Computation

### Primary Source: `strategy_states_DAILY_539.json`
```json
{
  "acb_1bet": {
    "edge_30p": 0.0527, "edge_100p": 0.046, "edge_300p": 0.0327,
    "rate_30p": 0.167, "rate_100p": 0.16, "rate_300p": 0.147,
    "trend": "STABLE", "z_score": 0.294, "sharpe_300p": 0.092,
    "consecutive_neg_30p": 0, "alert": false
  }
}
```

### RSM Rolling Records: `data/rolling_monitor_DAILY_539.json`
```json
{
  "records": {
    "acb_1bet": [
      {"draw_id":"114000070", "date":"2025-03-19",
       "predicted_bets": [[4,17,21,23,31]],
       "actual": [11,15,25,29,34],
       "match_counts": [1], "best_match": 1,
       "is_m2plus": false, "is_m3plus": false, "num_bets": 1}
    ]
  }
}
```

**318 records** per strategy, all strategies aligned by draw_id.

---

## 3. Report Generation Points

| Report | File | Trigger |
|--------|------|---------|
| RSM 30/100/300 state | `tools/rsm_bootstrap.py` | Manual / scheduled |
| Per-period predictions | `lottery_api/data/predictions_DAILY_539.jsonl` | Every `quick_predict.py` run |
| Strategy leaderboard | `tools/strategy_leaderboard.py` | Manual |
| DriftDetector | `lottery_api/models/regime_monitor.py` | Auto on API calls |
| LLM analysis | `lottery_api/engine/llm_analyzer.py` | Post-RSM update |

---

## 4. RL Insertion Points (Ranked by Priority)

| Priority | Component | Location | What RL Replaces |
|----------|-----------|----------|------------------|
| **P1** | Agent weight selection | `strategy_coordinator.py:90-120` | Fixed RSM-derived weights |
| **P2** | Strategy/bet-count selection | `quick_predict.py:_coordinator_bets()` | Hard-coded default bets |
| **P3** | Skip/no-skip decision | `quick_predict.py:main()` | Always-bet behavior |
| **P4** | Anti-crowd reranking | Player behavior advisory module | Static popularity check |

**Recommended first insertion (P1):** Replace `rsm_weights_for_lottery()` with RL policy output.

---

## 5. Available State Variables

### Per-Draw (pre-draw, no leakage)
| Feature | Type | Source | Range |
|---------|------|--------|-------|
| `edge_30p` × 6 strats | float | RSM rolling | [-0.1, 0.2] |
| `edge_100p` × 6 strats | float | RSM rolling | [-0.1, 0.2] |
| `edge_300p` × 6 strats | float | RSM rolling | [-0.1, 0.2] |
| `sharpe_300p` × 6 strats | float | RSM rolling | [-1, 3] |
| `z_score` × 6 strats | float | TrendClassifier | [-3, 3] |
| `recent_5_hits` × 6 strats | float | rolling_monitor | [0, 1] |
| `trend_id` × 6 strats | int | TrendClassifier | {0,1,2,3} |
| `max_edge_300p` | float | cross-strategy | [-0.1, 0.2] |
| `edge_dispersion` | float | cross-strategy | [0, 0.1] |
| `consensus_positive` | float | cross-strategy | [0, 1] |
| `period_cycle` | float | draw number % 52 | [0, 1] |

**Total observation dimension: 6×6 + 3 = 39**

---

## 6. Baselines (M2+ Random Rate)

| Strategy | Bets | M2+ Baseline | Current Edge |
|----------|------|-------------|-------------|
| acb_1bet | 1 | 11.40% | +3.27% |
| midfreq_acb_2bet | 2 | 21.54% | +8.46% |
| acb_markov_midfreq_3bet | 3 | 30.50% | +8.50% |
| acb_markov_fourier_3bet | 3 | 30.50% | +5.17% |
| f4cold_3bet | 3 | 30.50% | +0.17% |
| f4cold_5bet | 5 | 45.39% | +6.61% |

---

## 7. Architecture Constraints

1. **Data leakage**: RL state MUST use only `draws[:i]` (enforced in `env.py`)
2. **Reward sparsity**: M2+ events are rare; use edge-normalized reward
3. **Small dataset**: 318 records → require multiple episode passes, careful regularization
4. **Non-stationarity**: Strategy performance drifts; favor short memory in observations
5. **Track separation**: RL layer modular, fallback to RSM if model unavailable

---

## 8. Package Status After Audit

| Package | Status | Version |
|---------|--------|---------|
| `stable-baselines3` | ✅ (Python 3.13 venv) | 2.7.1 |
| `gymnasium` | ✅ | 1.2.3 |
| `torch` | ✅ | 2.10.0 |
| `tensorboard` | ✅ (system Python) | 2.20.0 |
| `numpy`, `pandas` | ✅ | installed |

**SB3 venv path**: `/tmp/sb3_env/bin/python3`
