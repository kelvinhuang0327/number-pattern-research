# P0 Registry Reconciliation — 2026-05-19

## Summary

The main repo runtime registry (`lottery_api/models/replay_strategy_registry.py`) contains **18 strategies**, not 16 as referenced in the CEO brief. Below is the full reconciliation.

---

## Registry Count: 18 (main repo, 2026-05-19)

| Strategy ID | Lifecycle | Lottery Type | Notes |
|-------------|-----------|--------------|-------|
| power_precision_3bet | **ONLINE** | POWER_LOTTO | Production |
| power_orthogonal_5bet | **ONLINE** | POWER_LOTTO | Production |
| fourier_rhythm_3bet | **ONLINE** | POWER_LOTTO | Production |
| biglotto_triple_strike | **ONLINE** | BIG_LOTTO | Production |
| biglotto_deviation_2bet | **ONLINE** | BIG_LOTTO | Production |
| ts3_regime_3bet | **ONLINE** | BIG_LOTTO | Production (P1.4 bound) |
| daily539_f4cold | **ONLINE** | DAILY_539 | Production |
| daily539_markov_cold | **ONLINE** | DAILY_539 | Production |
| biglotto_ts3_acb_4bet | REJECTED | BIG_LOTTO | Governance rejected |
| biglotto_ts3_markov_freq_5bet | REJECTED | BIG_LOTTO | Governance rejected |
| power_shlc_midfreq | REJECTED | POWER_LOTTO | Governance rejected |
| p1_deviation_2bet_539 | REJECTED | DAILY_539 | Governance rejected |
| acb_1bet | RETIRED | DAILY_539 | V3 tombstone |
| acb_markov_midfreq | RETIRED | DAILY_539 | V3 tombstone |
| acb_markov_midfreq_3bet | RETIRED | DAILY_539 | P3BC resolved (3 rows inserted) |
| midfreq_acb_2bet | RETIRED | DAILY_539 | V3 tombstone |
| midfreq_fourier_2bet | RETIRED | DAILY_539 | V3 tombstone |
| h6_gate_mk20_ew85 | OBSERVATION | POWER_LOTTO | Shadow evaluation |

**Breakdown: ONLINE=8, REJECTED=4, RETIRED=5, OBSERVATION=1 → Total=18**

---

## Why the CEO Brief Said "16"

The CEO brief referenced "registry 16 策略". The most likely explanations:
1. **An earlier registry snapshot** from before `acb_markov_midfreq_3bet` was re-registered as RETIRED (P3BC resolve on 2026-05-16 added it back to the runtime catalog after P3BC_RESOLVE inserted 3 rows).
2. **RETIRED strategies excluded** in some counting convention: 18 total − 5 RETIRED = 13 ONLINE+REJECTED+OBSERVATION. Neither 13 nor 18 equals 16, so the 16 figure likely predates the P3BC update.
3. **LotteryNew-clean snapshot**: the LotteryNew-clean repo may have had a different registry state at the time the CTO reported P0_COMPLETED.

## Authoritative Runtime Count

**Main repo canonical runtime universe: 18 strategies** as of 2026-05-19.

The "506/512" artifact scan count is NOT the runtime denominator. It is the result of code scanning and artifact inventory (see `outputs/replay/p0_strategy_universe_inventory_20260517.json`).

---

## Replay Row Coverage (Post-P0 Schema Migration)

| Lifecycle | Registry Count | Has Replay Rows | Strategy IDs with Rows |
|-----------|---------------|-----------------|------------------------|
| ONLINE | 8 | Partial | biglotto_deviation_2bet, biglotto_triple_strike, daily539_f4cold, daily539_markov_cold, power_orthogonal_5bet, power_precision_3bet |
| REJECTED | 4 | 0 | none |
| RETIRED | 5 | 0 | none |
| OBSERVATION | 1 | 0 | none |

6 of 8 ONLINE strategies have legacy replay rows. `ts3_regime_3bet` and `fourier_rhythm_3bet` have rows in LotteryNew-clean (via P3BC/P2B/P2F) but not yet in main repo — these are RECONSTRUCTIBLE candidates for P5.

---

## Recommendation for P2 Catalog Apply

- Main repo runtime universe = **18** (authoritative)
- The "16" figure in the CEO brief is stale; no action needed beyond this document
- P2 catalog should use 18 as `runtime_canonical_count`
