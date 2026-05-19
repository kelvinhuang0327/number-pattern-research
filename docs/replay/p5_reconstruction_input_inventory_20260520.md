# P5 Reconstruction Input Inventory

Generated: 2026-05-19T13:09:55.503406Z
Catalog source: `p2_json`  
RECONSTRUCTIBLE strategies: 12  
Target draw range: `115000072-115000121`  
Target cells total: 300  
Plannable cells: 62  
Skippable cells: 238  

## Evidence Class Summary

| Class | Strategies |
|-------|-----------|
| `SOURCE_MISSING` | fourier_rhythm_3bet, ts3_regime_3bet |
| `NEEDS_P6_POLICY` | biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, acb_markov_midfreq, midfreq_fourier_2bet, h6_gate_mk20_ew85 |
| `PROVENANCE_MISSING` | p1_deviation_2bet_539 |
| `SOURCE_AVAILABLE` | acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet |

## Per-Strategy Detail

| Strategy | LT | Lifecycle | Evidence | Target | Plannable | Skippable |
|---|---|---|---|---|---|---|
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | `SOURCE_MISSING` | 0 | 0 | 0 |
| ts3_regime_3bet | BIG_LOTTO | ONLINE | `SOURCE_MISSING` | 0 | 0 | 0 |
| biglotto_ts3_acb_4bet | BIG_LOTTO | REJECTED | `NEEDS_P6_POLICY` | 0 | 0 | 0 |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | REJECTED | `NEEDS_P6_POLICY` | 0 | 0 | 0 |
| power_shlc_midfreq | POWER_LOTTO | REJECTED | `NEEDS_P6_POLICY` | 0 | 0 | 0 |
| p1_deviation_2bet_539 | DAILY_539 | REJECTED | `PROVENANCE_MISSING` | 50 | 0 | 50 |
| acb_1bet | DAILY_539 | RETIRED | `SOURCE_AVAILABLE` | 50 | 9 | 41 |
| acb_markov_midfreq | DAILY_539 | RETIRED | `NEEDS_P6_POLICY` | 50 | 0 | 50 |
| acb_markov_midfreq_3bet | DAILY_539 | RETIRED | `SOURCE_AVAILABLE` | 50 | 44 | 6 |
| midfreq_acb_2bet | DAILY_539 | RETIRED | `SOURCE_AVAILABLE` | 50 | 9 | 41 |
| midfreq_fourier_2bet | DAILY_539 | RETIRED | `NEEDS_P6_POLICY` | 50 | 0 | 50 |
| h6_gate_mk20_ew85 | POWER_LOTTO | OBSERVATION | `NEEDS_P6_POLICY` | 0 | 0 | 0 |

## Safety
- DB rows before: 460
- DB rows after:  460
- Rows unchanged: True
- **No rows inserted in this inventory run.**
