# P50: POWER_LOTTO Wave 4 Performance Analysis

**Classification**: `P50_NOT_COMMITTED_ANALYSIS_ONLY`  
**Status**: Committed under P51 to preserve audit trail  
**Date**: 2026-05-25  
**Apply ID**: `P48_POWERLOTTO_WAVE4_4500_PROD_20260524`

---

## Governance Note

P50 findings were originally produced in-conversation only.  
The main branch write hook blocked file writes at the time.  
No new branch was created because explicit authorization was not yet granted.  
These artifacts are committed under P51 solely to preserve the audit trail.

**P50 governance facts:**
- No DB write
- No lifecycle promotion
- No registry mutation
- Production rows stayed `42460` throughout

---

## P50 Findings Summary

### Strategies Analyzed
| Strategy | Rows | Draw Range | Mean Hit | Lifecycle |
|---|---|---|---|---|
| `pp3_freqort_4bet` | 1500 | 101000002–115000040 | 1.0020 | DRY_RUN |
| `midfreq_fourier_mk_3bet` | 1500 | 101000002–115000040 | 1.0273 | DRY_RUN |
| `midfreq_fourier_2bet` | 1500 | 101000002–115000040 | 0.9727 | DRY_RUN |

### POWER_LOTTO Semantics Verified
- `hit_count` = first-zone hits only
- `special_hit` = special-zone match only
- Special hit is **not** folded into `hit_count`

### Theoretical Baseline
- First-zone baseline: `0.9474`
- Special hit theoretical rate: `1/8 = 0.125`

### Special Hit Rate (all three strategies)
- Special hits: `178 / 1500 = 11.87%`
- Within expected theoretical range around `1/8`

### P50 Assessment
- Best performing: `midfreq_fourier_mk_3bet` (mean_hit 1.0273, above baseline)
- `pp3_freqort_4bet`: mean_hit 1.002, slightly above baseline
- `midfreq_fourier_2bet`: mean_hit 0.9727, slightly below baseline
- Effect sizes are **small**; formal rolling-window, permutation, and McNemar tests required

### P50 Conclusion
Formal promotion-gate tests (G1–G7) deferred to **P51**.

---

## Next Step

P51: Formal rolling-window verification + McNemar gate  
(`docs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.md`)
