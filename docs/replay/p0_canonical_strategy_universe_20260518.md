# P0 Canonical Strategy Universe

**Generated:** 2026-05-18  
**Mission:** P0 Schema Stabilization  
**Branch:** feat/p0-schema-stabilization-20260518  

---

## Canonical Total: 18 Strategies

This document supersedes all prior strategy counts for replay governance purposes.

### Denomination History

| Count | Source | Status |
|-------|--------|--------|
| 506 | `docs/replay/strategy_historical_replay_roadmap_20260515.md` | SUPERSEDED (broad codebase scan, includes EXPERIMENTAL/UNKNOWN candidates not in formal registry) |
| 91 | `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` | SUPERSEDED (point-in-time DB+registry snapshot) |
| **18** | `lottery_api/models/replay_strategy_registry.py` | **CURRENT CANONICAL** |

### Note on 512

The mission briefing references "512 total strategies." As of 2026-05-18, the formal `replay_strategy_registry` contains **18 strategies**. The gap of ~494 reflects strategies from the broader codebase (`tools/`, `models/`) that have not been onboarded into the formal replay governance registry. These candidates are `DISPLAY_ONLY` or unevaluated, and are not tracked in this canonical universe until they pass P0 governance review.

---

## Four-Category Classification

| Category | Count | Description |
|----------|-------|-------------|
| **row_backed** | 13 | Has prediction rows in `strategy_prediction_replays` — can display actual vs predicted |
| **historical_reconstructable** | 0 | Has artifacts but no rows yet — reconstruction pending |
| **display_only** | 1 | In registry, no rows, no reconstruction path — shows as catalog entry |
| **tombstone** | 4 | RETIRED/REJECTED with no rows — audit trail only |
| **Total** | **18** | ✅ Sum matches canonical total |

---

## By Lifecycle Status

| Status | Count | Replay-Active |
|--------|-------|---------------|
| ONLINE | 8 | Yes |
| REJECTED | 4 | No (rows preserved for audit) |
| RETIRED | 5 | No (rows preserved where applicable) |
| OBSERVATION | 1 | No (pending evaluation) |

---

## Strategy Registry (18 entries)

### ONLINE (8) — Active in replay generation

| Canonical ID | Strategy Name | Lottery Type | Replay Rows | Category |
|---|---|---|---|---|
| power_precision_3bet | 威力彩 Precision 3注 | POWER_LOTTO | 120 | row_backed |
| power_orthogonal_5bet | 威力彩 Orthogonal 5注 | POWER_LOTTO | 120 | row_backed |
| fourier_rhythm_3bet | 威力彩 Fourier Rhythm 3注 | POWER_LOTTO | 3 | row_backed |
| biglotto_triple_strike | 大樂透 Triple Strike | BIG_LOTTO | 120 | row_backed |
| biglotto_deviation_2bet | 大樂透 Deviation 2注 | BIG_LOTTO | 120 | row_backed |
| ts3_regime_3bet | 大樂透 TS3+Regime 3注 | BIG_LOTTO | 9 | row_backed |
| daily539_f4cold | 今彩539 F4 Cold | DAILY_539 | 140 | row_backed |
| daily539_markov_cold | 今彩539 Markov Cold | DAILY_539 | 140 | row_backed |

### REJECTED (4) — Governance rejected; rows preserved for audit

| Canonical ID | Strategy Name | Lottery Type | Replay Rows | Category |
|---|---|---|---|---|
| biglotto_ts3_acb_4bet | 大樂透 TS3+ACB 4注 | BIG_LOTTO | 50 | row_backed |
| biglotto_ts3_markov_freq_5bet | 大樂透 TS3+Markov 頻率正交 5注 | BIG_LOTTO | 50 | row_backed |
| power_shlc_midfreq | 威力彩 SHLC 中頻指標 | POWER_LOTTO | 50 | row_backed |
| p1_deviation_2bet_539 | 今彩539 P1號+偏差互補 2注 | DAILY_539 | 50 | row_backed |

### RETIRED (5) — Formally retired

| Canonical ID | Strategy Name | Lottery Type | Replay Rows | Category |
|---|---|---|---|---|
| acb_1bet | 今彩539 ACB 1注 | DAILY_539 | 0 | tombstone |
| acb_markov_midfreq | 今彩539 ACB+Markov 中頻 | DAILY_539 | 0 | tombstone |
| acb_markov_midfreq_3bet | 今彩539 ACB+Markov 中頻 3注 | DAILY_539 | 3 | row_backed |
| midfreq_acb_2bet | 今彩539 中頻 ACB 2注 | DAILY_539 | 0 | tombstone |
| midfreq_fourier_2bet | 今彩539 中頻 Fourier 2注 | DAILY_539 | 0 | tombstone |

### OBSERVATION (1) — Under shadow evaluation

| Canonical ID | Strategy Name | Lottery Type | Replay Rows | Category |
|---|---|---|---|---|
| h6_gate_mk20_ew85 | 威力彩 H6 Gate mk20 ew85 | POWER_LOTTO | 0 | display_only |

---

## Source of Truth

- **Registry code:** `lottery_api/models/replay_strategy_registry.py`
- **DB:** `lottery_api/data/lottery_v2.db` table `strategy_prediction_replays`
- **Canonical IDs:** No duplicates confirmed (all 18 unique)
- **JSON artifact:** `outputs/replay/p0_canonical_strategy_universe_20260518.json`
