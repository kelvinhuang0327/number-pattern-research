# P94D Best Strategy Overview — Data Contract

**Date**: 2026-05-27  
**Task**: P94D  
**Classification**: P94D_BEST_STRATEGY_OVERVIEW_CONTRACT_READY  
**DB Writes**: false  
**Replay Row Changes**: 0  
**Lifecycle Promotions**: 0

---

## 1. Purpose

Define the unified data contract for the 「最佳策略總覽」(Best Strategy Overview) page.

Benchmark ranking data from P94A / P94B / P94C artifacts feeds this page.  
The raw historical replay list (draw-by-draw prediction-vs-actual) remains a separate view.

This document is **design / contract only**. No DB writes. No replay row inserts. No prediction apply.

---

## 2. Design Decisions (Binding)

| # | Decision |
|---|----------|
| D1 | Rankings belong in 「最佳策略總覽」, **not** the raw historical replay list |
| D2 | Raw replay list remains for draw-by-draw prediction-vs-actual audit |
| D3 | Benchmark JSONs (P94A/P94B/P94C) are the canonical source for ranking data |
| D4 | Adapter/prediction runner is the source for next-period numbers |
| D5 | Rejected/offline strategies may appear in benchmark ranking **with caveat** |
| D6 | Rejected/offline strategies must **not** be the default next-number recommendation unless operator enables `replay_only_mode` |
| D7 | Unsupported bet-count cases must show `generation_status: UNSUPPORTED_BET_COUNT`, never fabricated numbers |
| D8 | POWER_LOTTO special number must be shown separately (`predicted_special`) |
| D9 | DAILY_539 has no special number (`predicted_special: null`) |
| D10 | BIG_LOTTO has 6 main numbers, no special (`predicted_special: null`) |

---

## 3. Data Sources

| Lottery | Benchmark Artifact | PR / Status |
|---------|--------------------|-------------|
| BIG_LOTTO | `outputs/replay/p94a_biglotto_all_strategy_betcount_benchmark_20260526.json` | PR #221 merged |
| POWER_LOTTO | `outputs/replay/p94b_powerlotto_all_strategy_betcount_benchmark_20260527.json` | PR #220 merged |
| DAILY_539 | `outputs/replay/p94c_daily539_all_strategy_betcount_benchmark_*.json` | PR #222 OPEN — **planning-only for P94D** |

> P94C artifact not yet available. DAILY_539 contract sections are schema-specified here and will be populated once PR #222 merges.

---

## 4. Ranking Filters

```
lottery_type:       BIG_LOTTO | POWER_LOTTO | DAILY_539
bet_count:          1 | 2 | 3 | 5
observation_window: 30 | 100 | 500 | 1500
ranking_metric:     m3plus_rate (default) | avg_hit_count | m4plus_rate | stability_score
```

---

## 5. Ranking Card Schema

Each card in the 「最佳策略總覽」 grid must include:

```json
{
  "rank": 1,
  "strategy_id": "ts3_regime_3bet",
  "display_name": "大樂透 TS3+Regime 3注",
  "lottery_type": "BIG_LOTTO",
  "bet_count": 3,
  "observation_window": 1500,
  "lifecycle_status": "PRODUCTION",
  "source_category": "row-backed",
  "row_backed": true,
  "benchmark_only": false,
  "adapter_generated": false,
  "rejected_or_offline_caveat": null,
  "sample_size": 1500,
  "m3plus_rate": 0.107,
  "avg_hit_count": 1.82,
  "m4plus_rate": 0.012,
  "m5_rate": 0.001,
  "m6_rate": 0.0,
  "zero_hit_rate": 0.14,
  "special_hit_rate": null,
  "stability_score": null,
  "stability_across_windows": {
    "30": { "m3plus_rate": 0.107 },
    "100": { "m3plus_rate": 0.110 },
    "500": { "m3plus_rate": 0.105 },
    "1500": { "m3plus_rate": 0.107 }
  },
  "warning_flags": []
}
```

### Field Notes

| Field | BIG_LOTTO | POWER_LOTTO | DAILY_539 |
|-------|-----------|-------------|-----------|
| `m5_rate` | applicable | applicable | applicable |
| `m6_rate` | applicable (6 main nums) | not applicable | not applicable |
| `special_hit_rate` | **null** | required | **null** |
| `bet_count` range | 1–5 | 1–5 | 1–5 |

### `rejected_or_offline_caveat` Values

| Value | Meaning |
|-------|---------|
| `null` | Strategy is online/production — no caveat |
| `"REJECTED: historical benchmark only"` | Strategy failed validation; shown for historical comparison only |
| `"OFFLINE: decommissioned"` | Strategy retired; shown for reference only |
| `"DRY_RUN: not yet production"` | Strategy in evaluation; not recommended for real bets |

### `warning_flags` Values

| Flag | Trigger Condition |
|------|-------------------|
| `"SMALL_SAMPLE"` | `sample_size < 100` |
| `"SHORT_WINDOW_ONLY"` | Strategy only has data in w30/w100, missing w500/w1500 |
| `"BENCHMARK_ONLY"` | Strategy has no production replay rows |
| `"REJECTED_STRATEGY"` | lifecycle is REJECTED or OFFLINE |
| `"NO_ADAPTER"` | No adapter exists for next-number generation |
| `"UNSUPPORTED_BET_COUNT"` | Requested bet_count not supported by adapter |

---

## 6. Next Prediction Schema

Each strategy card may optionally display the next predicted numbers:

```json
{
  "next_draw_lottery_type": "BIG_LOTTO",
  "next_draw_source": "adapter",
  "next_draw_number": null,
  "prediction_generated_at": "2026-05-27T10:00:00Z",
  "strategy_id": "ts3_regime_3bet",
  "bet_count": 3,
  "predicted_bets": [
    [11, 15, 22, 33, 41, 43],
    [5, 18, 27, 35, 38, 42],
    [3, 9, 20, 31, 36, 48]
  ],
  "predicted_special": null,
  "adapter_name": "ts3_regime_adapter",
  "generation_status": "READY",
  "disclaimer": "Benchmark ranking does not guarantee next-draw performance. Past edge is not a predictor of future returns."
}
```

### `generation_status` Values

| Status | Meaning |
|--------|---------|
| `READY` | Adapter exists and produced valid predictions |
| `ADAPTER_MISSING` | No adapter registered for this strategy |
| `UNSUPPORTED_BET_COUNT` | Adapter does not support the requested bet_count |
| `REJECTED_REPLAY_ONLY` | Strategy is REJECTED/OFFLINE; next-number generation blocked unless `replay_only_mode=true` |
| `SOURCE_UNAVAILABLE` | Benchmark artifact not yet available (P94C/DAILY_539 planning-only case) |

### Lottery-Specific Rules

```
BIG_LOTTO:
  predicted_bets:    list of up to bet_count lists, each 6 integers in [1, 49]
  predicted_special: null   # no special ball

POWER_LOTTO:
  predicted_bets:    list of up to bet_count lists, each 6 integers in [1, 38]
  predicted_special: integer in [1, 8] per bet  # mandatory; show separately

DAILY_539:
  predicted_bets:    list of up to bet_count lists, each 5 integers in [1, 39]
  predicted_special: null   # no special ball
```

---

## 7. UI Placement Decision

```
「最佳策略總覽」 page
├── Filters bar:  lottery_type / bet_count / observation_window / ranking_metric
├── Ranking grid: RankingCard × N (sorted by ranking_metric desc)
│   └── Each card expands to show:
│       ├── Benchmark metrics (from P94A/B/C artifact)
│       ├── Stability across windows chart
│       ├── Warning flags & caveats
│       └── Next Prediction panel (from adapter, with disclaimer)
└── Footer note: "Rankings based on historical benchmark. Not financial advice."

Raw Replay List (separate page / tab):
├── Per-draw prediction-vs-actual table
├── Shows all production replay rows from strategy_prediction_replays
└── No ranking, no next-number recommendation
```

---

## 8. Rejected / Offline Strategy Policy

- Rejected and offline strategies **may** appear in benchmark ranking tabs with `rejected_or_offline_caveat` set.
- They are sorted **after** PRODUCTION / ONLINE / DRY_RUN strategies at the same rank tier.
- Their `generation_status` must be `REJECTED_REPLAY_ONLY` unless operator explicitly enables `replay_only_mode`.
- The UI must render a yellow warning banner on rejected/offline cards.
- They must never be auto-selected as the default recommendation.

---

## 9. Unsupported Bet Count Policy

Some strategies only support certain native bet counts (e.g., `ts3_regime_3bet` natively generates 3 bets).

- If a user filters for `bet_count=5` and the strategy's adapter cannot generate 5 bets, set `generation_status: UNSUPPORTED_BET_COUNT`.
- Never fabricate extra bets.
- Show the card in the ranking (benchmark metrics are still valid for the window), but disable the next-prediction panel.

---

## 10. DAILY_539 Planning-Only Note

P94C (DAILY_539 benchmark) PR #222 is open as of 2026-05-27.

For P94D:
- The DAILY_539 section of the contract is **schema-complete** (all field types and rules specified above apply).
- The **ranking data** cannot be populated until PR #222 merges.
- Implementation of the DAILY_539 tab in the UI must wait for the P94C artifact to be available.
- P95 implementation should include a graceful `SOURCE_UNAVAILABLE` state for the DAILY_539 tab until the artifact loads.

---

## 11. Stability Score (Optional Metric)

`stability_score` is computed as:

```
stability_score = 1.0 - std(m3plus_rate across windows that have sample_size >= 30) / mean(m3plus_rate)
```

Range: 0.0 (unstable) to 1.0 (perfectly stable across all windows).  
Set to `null` if fewer than 2 windows have `sample_size >= 30`.

---

## 12. Recommended P95 Implementation

P95 should implement:

1. **API endpoint**: `GET /api/best-strategy-overview`
   - Query params: `lottery_type`, `bet_count`, `observation_window`, `ranking_metric`
   - Reads from P94A/B/C benchmark JSON files (not DB)
   - Returns ranked `RankingCard[]`

2. **Next prediction endpoint**: `GET /api/best-strategy-overview/{strategy_id}/next-prediction`
   - Calls adapter runner for fresh prediction
   - Returns `NextPrediction` object

3. **Frontend**: New tab/page 「最佳策略總覽」
   - Filter bar + responsive grid of RankingCards
   - Expand-on-click prediction panel
   - Graceful `SOURCE_UNAVAILABLE` for DAILY_539 until P94C artifact available

4. **Benchmark refresh**: When a new P94A/B/C artifact is produced, the overview auto-updates.

5. **No DB mutations** in any P95 implementation path.

---

## 13. Baseline Snapshot

At P94D contract creation:

| Metric | Value |
|--------|-------|
| `strategy_prediction_replays` rows | 54462 |
| POWER_LOTTO max draw | 115000041 |
| DB writes | false |
| Replay row changes | 0 |

---

## 14. Artifact Checklist

| Artifact | Status |
|----------|--------|
| `docs/replay/p94d_best_strategy_overview_contract_20260527.md` | CREATED |
| `outputs/replay/p94d_best_strategy_overview_contract_20260527.json` | CREATED |
| `tests/test_p94d_best_strategy_overview_contract.py` | CREATED |

---

**Classification**: P94D_BEST_STRATEGY_OVERVIEW_CONTRACT_READY
