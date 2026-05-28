# P128 Wave 2 Phase 1 — Multi-Bet Adapter Implementation

**Task ID:** P128  
**Classification:** `P128_WAVE2_ADAPTER_PHASE1_READY`  
**Generated:** 2026-05-28T12:00:47.984164+00:00  
**Scope:** Adapter-only (no DB write, no controlled_apply, no replay row insertion)

---

## Executive Summary

P128 Phase 1 implements `get_all_bets()` adapter functions for **priority 1-6**
(all 2-bet strategies) from the P127 build spec. This is a **spec-only adapter
implementation** — no rows are written to the production database.

| Item | Value |
|------|-------|
| DB rows before | 72462 |
| DB rows after  | 72462 |
| Replay rows inserted | 0 |
| controlled_apply executed | No |
| Adapters implemented | 6 |
| All smoke tests pass | True |
| Classification | `P128_WAVE2_ADAPTER_PHASE1_READY` |

---

## P127 Source Recap

- **Artifact:** `outputs/replay/p127_adapter_build_specs_remaining_multi_bet_20260528.json`
- **Classification:** `P127_ADAPTER_BUILD_SPECS_READY`
- **Total strategies in P127:** 12
- **Phase 1 scope:** Priority 1-6 (all 2-bet strategies)

---

## Why P128 Phase 1 is Adapter-Only

The P127 spec identified 12 strategies needing `get_all_bets()` adapters.
Phase 1 implements priority 1-6 (the simpler 2-bet strategies) as
adapter functions only. The reasons:

1. **Safety gate:** All adapters must be smoke-tested before any controlled_apply.
2. **RSR-6 isolation:** Priority 10 and 12 have RSR-6 considerations — deferred to Phase 2.
3. **Incremental validation:** Phase 1 → Phase 2 → controlled_apply is the safe path.
4. **No data risk:** Adapter code is pure logic — no risk to the production 72,462-row DB.

---

## Priority 1-6 Implementation Matrix

| Priority | Strategy ID | Lottery Type | Function | Bets | Status |
|----------|-------------|--------------|----------|------|--------|
| P1 | `midfreq_acb_2bet` | `DAILY_539` | `get_all_bets_midfreq_acb()` | 2 | PASS |
| P2 | `midfreq_fourier_2bet` | `DAILY_539` | `get_all_bets_fourier_d539()` | 2 | PASS |
| P3 | `zonal_entropy_2bet` | `POWER_LOTTO` | `get_all_bets_zonal_entropy()` | 2 | PASS |
| P4 | `cold_complement_2bet` | `POWER_LOTTO` | `get_all_bets_cold_complement()` | 2 | PASS |
| P5 | `midfreq_fourier_2bet` | `POWER_LOTTO` | `get_all_bets_fourier_power()` | 2 | PASS |
| P6 | `fourier30_markov30_2bet` | `POWER_LOTTO` | `get_all_bets_fourier30_markov30()` | 2 | PASS |

All 6 adapters implemented in:
`lottery_api/models/p128_wave2_phase1_adapters.py`

---

## get_all_bets() Contract

```python
def get_all_bets(strategy_id: str, draw_context: dict) -> list[list[int]]
```

**draw_context keys:**
- `history`: list of past draw dicts (each with `numbers`, optionally `special`)
- `lottery_type`: `'DAILY_539'` or `'POWER_LOTTO'`

**Returns:** `list[list[int]]` — 2 sublists
- `[0]` = bet-1 (`bet_index=1`): primary prediction (highest model confidence)
- `[1]` = bet-2 (`bet_index=2`): secondary prediction (diversified/orthogonal)

**Guarantees:**
- Deterministic: same inputs → same output
- No future data: `history` must be draws strictly before target draw
- No DB write: `True`
- Bet numbers sorted ASC within each bet

---

## Adapter Algorithm Summary

### P1: `midfreq_acb_2bet` (DAILY_539)
- bet-1: **MidFreq** — top-5 numbers closest to expected frequency (mean-reversion)
- bet-2: **ACB** — top-5 most underrepresented numbers (anomaly capture)

### P2: `midfreq_fourier_2bet` (DAILY_539)
- bet-1: **MidFreq** — top-5 by mean-reversion score
- bet-2: **Fourier** — top-5 by FFT period alignment (rhythm detection)

### P3: `zonal_entropy_2bet` (POWER_LOTTO)
- Regime detection: Shannon entropy of zone distribution (8 zones, window=30)
- bet-1: **Entropy-adaptive** — cold if chaotic (>2.2 bits), hot if stable
- bet-2: **Opposite regime** — hot if bet-1 was cold, cold if hot (maximum diversification)

### P4: `cold_complement_2bet` (POWER_LOTTO)
- bet-1: **Cold top-6** — 6 numbers with lowest frequency over 100 draws (reversion)
- bet-2: **Hot complement** — 6 numbers with highest frequency over 100 draws (momentum)

### P5: `midfreq_fourier_2bet` (POWER_LOTTO)
- bet-1: **MidFreq+Fourier intersection** — top-20 MidFreq ∩ top-20 Fourier, pick 6
- bet-2: **Pure Fourier** — top-6 by FFT rhythm score (window=500)

### P6: `fourier30_markov30_2bet` (POWER_LOTTO)
- bet-1: **Fourier30** — weighted recency frequency (window=30, weight 1.0→3.0)
- bet-2: **Markov30** — Markov transition matrix top-6 (window=30)

---

## RSR-6 Audit Status

**RSR-6 is NOT applicable to Phase 1.**

NONE — Phase 1 priority 1-6 strategies are NOT affected by RSR-6

RSR-6 affects:
- power_orthogonal_5bet (priority 12)
- power_precision_3bet (priority 10)

Deferred to: **PHASE_2**

---

## RSR-7 Note

| Field | Value |
|-------|-------|
| Strategy | `fourier30_markov30_2bet` |
| Lottery | `POWER_LOTTO` |
| Expected rows | 1500 |
| Actual rows | 1501 |
| Extra rows | 1 |
| Severity | LOW |
| Blocks adapter | False |

fourier30_markov30_2bet has 1501 rows (1 extra vs expected 1500). This is RSR-7 (low priority). Adapter implementation proceeds. RSR-7 investigation deferred.

---

## Smoke Test Coverage

| Strategy ID | Lottery Type | Status | Deterministic |
|-------------|--------------|--------|---------------|
| `midfreq_acb_2bet` | `DAILY_539` | PASS | ✓ |
| `midfreq_fourier_2bet` | `DAILY_539` | PASS | ✓ |
| `zonal_entropy_2bet` | `POWER_LOTTO` | PASS | ✓ |
| `cold_complement_2bet` | `POWER_LOTTO` | PASS | ✓ |
| `midfreq_fourier_2bet` | `POWER_LOTTO` | PASS | ✓ |
| `fourier30_markov30_2bet` | `POWER_LOTTO` | PASS | ✓ |

**Total smoke tests:** 6  
**All pass:** True

---

## Apply Gate Rules

The apply gate is **CLOSED** for Phase 1.

controlled_apply requires:
- P128 Phase 2 completion
- full bet_index RSR audit
- CTO sign-off

**Phase 1 output:** adapter functions only. No production DB modification.

---

## Non-Actions (Explicitly Out of Scope)

The following were NOT done in P128 Phase 1:
- No rows written to `lottery_api/data/lottery_v2.db`
- No `controlled_apply` executed
- No replay rows inserted (`replay_rows_inserted = 0`)
- No lifecycle/champion/registry mutation
- No scheduler / cron / launchd changes
- No 4_STAR / P108 / P117 / P118 strategies touched
- Priority 7-12 deferred to Phase 2

---

## DB Snapshot

| Item | Value |
|------|-------|
| Table | `strategy_prediction_replays` |
| Row count | 72462 |
| Expected | 72462 |
| DB write in P128 | False |
| `bet_index` column | present (cid=27, type=INTEGER, default=1) |

---

## Remaining Risks

- RSR-6: power_orthogonal_5bet / power_precision_3bet need bet-2 logic — deferred to Phase 2
- RSR-7: fourier30_markov30_2bet has 1 extra row — low priority, needs investigation
- Phase 1 adapters are smoke-tested only; full 1500-draw backtest validation deferred
- No controlled_apply executed yet — production DB unchanged at 72462 rows

---

## Next Task

**P129 or P128-Phase2: implement priority 7-12 adapters, then controlled_apply for Phase 1**

---

## Final Classification

```
P128_WAVE2_ADAPTER_PHASE1_READY
```

P128 Phase 1 COMPLETE. Implemented get_all_bets() for 6 priority strategies (all 2-bet). No DB write. production_db_rows_after=72462. All 6 smoke tests PASS. RSR-6 deferred to Phase 2. Classification: P128_WAVE2_ADAPTER_PHASE1_READY.
