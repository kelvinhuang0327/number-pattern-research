# P112: Cross-Lottery Prediction-Helpfulness Audit

**Date:** 2026-05-27  
**Classification:** `P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY`  
**Task ID:** `P112_CROSS_LOTTERY_PREDICTION_HELPFULNESS_AUDIT`

---

## PROJECT_CONTEXT_LOCK

```
Project         = LotteryNew
Canonical Repo  = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Canonical Branch = main
```

If any context, artifact, or task belongs to a different project
(Betting-pool, Stock-Prediction-System, Novel, SCB, etc.), classify as
`P112_BLOCKED_BY_CONTEXT_CONTAMINATION` and stop.

---

## Why P112 Exists

P107B repaired two stale baseline tests (`test_p98::test_11`, `test_p99::test_14`)
that assumed 4_STAR rows = 0. Those tests now reflect the accepted DB state
(4_STAR count = 2922). With governance health restored, the next productive
action is to audit prediction quality across mature row-backed lotteries.

P112 provides an evidence-based read-only answer to: *"Are our row-backed
replay strategies actually prediction-helpful, or are they merely adding replay
coverage without improving quality?"*

---

## Post-P107B Baseline

| Invariant | Value | Source |
|---|---|---|
| replay_rows | 54462 | `strategy_prediction_replays` |
| 3_STAR count / max_draw | 4179 / 115000106 | `draws` |
| 4_STAR count / max_draw | 2922 / 115000103 | `draws` |
| POWER_LOTTO count / max_draw | 1913 / 115000041 | `draws` |
| Drift guard | PASS | `replay_lifecycle_drift_guard.py` |
| Branch governance guard | PASS | `replay_branch_governance_guard.py` |

---

## P108 Is Blocked — Do Not Confuse With P112

> **Special3 (3_STAR) 100-draw re-evaluation is NOT run in this task.**
>
> P107A classification: `P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS`  
> Special3 prospective draws after P99 cutoff: **63 / 100**  
> Remaining draws needed: **37**  
> P108 is not executable until those 37 draws are observed.

This task (`P112`) audits **POWER_LOTTO, DAILY_539, and BIG_LOTTO** only.

---

## 4_STAR Backtest Remains Unauthorized

> `four_star_backtest_authorized: false`
>
> Reason: source_unknown caveat established in P105.  
> 4_STAR rows (2922) exist in DB but provenance is unverified.  
> No 4_STAR backtest is run here or authorized by this task.

---

## Governance Flags

| Flag | Value |
|---|---|
| `db_writes` | `false` |
| `replay_rows_before` | 54462 |
| `replay_rows_after` | 54462 |
| `no_strategy_promotion` | `true` |
| `no_lifecycle_mutation` | `true` |
| `no_registry_mutation` | `true` |
| `no_4star_backtest` | `true` |
| `no_special3_p108_rerun` | `true` |
| `source_unknown_caveat_preserved` | `true` |

---

## Methodology

### Game Rules & Baselines

Each strategy predicts exactly one set of main numbers per draw.
The baseline is the hypergeometric expected hit count for random selection:

```
E[hits] = k * k / N
```

where `k` = draw size (numbers drawn) and `N` = pool size.

| Lottery Type | Pool Size (N) | Draw Size (k) | Baseline E[hits] | Special Pool |
|---|---|---|---|---|
| POWER_LOTTO | 38 | 6 | 6×6/38 = **0.9474** | 1 from 8 (baseline = 0.1250) |
| DAILY_539 | 39 | 5 | 5×5/39 = **0.6410** | None |
| BIG_LOTTO | 49 | 6 | 6×6/49 = **0.7347** | Bonus ball (not predicted) |

### Classification Thresholds (Edge vs Baseline)

| Classification | Main Edge Condition |
|---|---|
| `PREDICTION_HELPFUL` | edge ≥ +0.050 |
| `WATCHLIST_CANDIDATE` | +0.010 ≤ edge < +0.050 |
| `FALLBACK_EQUIVALENT` | -0.010 ≤ edge < +0.010 |
| `SUB_BASELINE` | edge < -0.010 |

**Special downgrade rule:** A `WATCHLIST_CANDIDATE` strategy that actively predicts
the special number (avg_sp > 0) but shows special_edge < -0.015 is downgraded to
`OBSERVE_MORE`. Strategies that do not predict a special (avg_sp = 0) are NOT
penalised.

**Temporal stability:** Not computed in this audit (single pooled window over all
available replay rows). Future P114 audit should compute rolling-window stability.

---

## DB Inventory

### Audit Scope

| Lottery Type | Draw Count | Replay Rows | Strategies | Min Draw | Max Draw |
|---|---|---|---|---|---|
| POWER_LOTTO | 1913 | 15142 | 10 | 101000002 | 99000104 |
| DAILY_539 | 5865 | 22680 | 15 | 110000190 | 99000261 |
| BIG_LOTTO | 22235 | 16640 | 11 | 102000010 | 99000105 |

### Excluded Scope

| Lottery Type | Reason |
|---|---|
| 3_STAR | P108 not run — only 63/100 prospective draws available (37 remaining) |
| 4_STAR | Backtest unauthorized — source_unknown caveat from P105 |

---

## Per-Lottery Summary

### POWER_LOTTO

| Classification | Count |
|---|---|
| PREDICTION_HELPFUL | 2 |
| WATCHLIST_CANDIDATE | 6 |
| FALLBACK_EQUIVALENT | 2 |

**Strongest signal lottery.** Two strategies show clear positive edge (> +0.05)
vs hypergeometric baseline. Six more are watchlist-worthy.

### DAILY_539

| Classification | Count |
|---|---|
| WATCHLIST_CANDIDATE | 11 |
| FALLBACK_EQUIVALENT | 3 |
| SUB_BASELINE | 1 |

**Broadly positive coverage.** 11 of 15 strategies show positive edge. Cold-pool
and orthogonal approaches consistently outperform markov-only approaches.

### BIG_LOTTO

| Classification | Count |
|---|---|
| WATCHLIST_CANDIDATE | 1 |
| FALLBACK_EQUIVALENT | 6 |
| SUB_BASELINE | 4 |

**Weakest signal lottery.** Only 1 strategy (`biglotto_deviation_2bet`) shows
meaningful edge. 4 strategies are clearly sub-baseline. BIG_LOTTO appears to be
the most resistant lottery to pattern-based strategies, likely due to its large
pool (49 numbers).

---

## Per-Strategy Results

### POWER_LOTTO (baseline_main = 0.9474)

| Strategy | n | avg_hit | edge_main | edge_special | Classification |
|---|---|---|---|---|---|
| midfreq_fourier_mk_3bet | 1500 | 1.0273 | +0.0800 | -0.0063 (near) | **PREDICTION_HELPFUL** |
| pp3_freqort_4bet | 1500 | 1.0020 | +0.0546 | -0.0063 (near) | **PREDICTION_HELPFUL** |
| fourier_rhythm_3bet | 1501 | 0.9927 | +0.0453 | N/A | WATCHLIST_CANDIDATE |
| power_fourier_rhythm_2bet | 1500 | 0.9927 | +0.0453 | N/A | WATCHLIST_CANDIDATE |
| power_orthogonal_5bet | 1570 | 0.9924 | +0.0450 | N/A | WATCHLIST_CANDIDATE |
| power_precision_3bet | 1570 | 0.9924 | +0.0450 | N/A | WATCHLIST_CANDIDATE |
| midfreq_fourier_2bet | 1500 | 0.9727 | +0.0253 | -0.0063 (near) | WATCHLIST_CANDIDATE |
| fourier30_markov30_2bet | 1501 | 0.9647 | +0.0173 | -0.0004 (near) | WATCHLIST_CANDIDATE |
| zonal_entropy_2bet | 1500 | 0.9460 | -0.0014 | -0.011 (below) | FALLBACK_EQUIVALENT |
| cold_complement_2bet | 1500 | 0.9407 | -0.0067 | -0.011 (below) | FALLBACK_EQUIVALENT |

### DAILY_539 (baseline_main = 0.6410)

| Strategy | n | avg_hit | edge_main | Classification |
|---|---|---|---|---|
| p0b_539_3bet_f_cold_fmid | 1500 | 0.6773 | +0.0363 | WATCHLIST_CANDIDATE |
| p0c_539_3bet_f_cold_x2 | 1500 | 0.6773 | +0.0363 | WATCHLIST_CANDIDATE |
| daily539_f4cold | 1570 | 0.6758 | +0.0348 | WATCHLIST_CANDIDATE |
| daily539_f4cold_3bet | 1500 | 0.6727 | +0.0316 | WATCHLIST_CANDIDATE |
| daily539_f4cold_5bet | 1500 | 0.6727 | +0.0316 | WATCHLIST_CANDIDATE |
| 539_3bet_orthogonal | 1500 | 0.6720 | +0.0310 | WATCHLIST_CANDIDATE |
| acb_1bet | 1500 | 0.6720 | +0.0310 | WATCHLIST_CANDIDATE |
| acb_markov_midfreq_3bet | 1500 | 0.6720 | +0.0310 | WATCHLIST_CANDIDATE |
| acb_single_539 | 1500 | 0.6720 | +0.0310 | WATCHLIST_CANDIDATE |
| midfreq_acb_2bet | 1500 | 0.6693 | +0.0283 | WATCHLIST_CANDIDATE |
| midfreq_fourier_2bet | 1500 | 0.6693 | +0.0283 | WATCHLIST_CANDIDATE |
| acb_markov_midfreq | 1500 | 0.6367 | -0.0044 | FALLBACK_EQUIVALENT |
| markov_1bet_539 | 1500 | 0.6340 | -0.0070 | FALLBACK_EQUIVALENT |
| daily539_markov_cold | 1570 | 0.6338 | -0.0073 | FALLBACK_EQUIVALENT |
| zone_gap_3bet_539 | 1500 | 0.6287 | -0.0124 | **SUB_BASELINE** |

### BIG_LOTTO (baseline_main = 0.7347)

| Strategy | n | avg_hit | edge_main | Classification |
|---|---|---|---|---|
| biglotto_deviation_2bet | 1570 | 0.7573 | +0.0226 | WATCHLIST_CANDIDATE |
| biglotto_echo_aware_3bet | 1500 | 0.7393 | +0.0046 | FALLBACK_EQUIVALENT |
| cold_complement_biglotto | 1500 | 0.7353 | +0.0006 | FALLBACK_EQUIVALENT |
| coldpool15_biglotto | 1500 | 0.7353 | +0.0006 | FALLBACK_EQUIVALENT |
| biglotto_triple_strike | 1570 | 0.7280 | -0.0067 | FALLBACK_EQUIVALENT |
| markov_2bet_biglotto | 1500 | 0.7280 | -0.0067 | FALLBACK_EQUIVALENT |
| markov_single_biglotto | 1500 | 0.7280 | -0.0067 | FALLBACK_EQUIVALENT |
| bet2_fourier_expansion_biglotto | 1500 | 0.7240 | -0.0107 | **SUB_BASELINE** |
| biglotto_ts3_markov_4bet_w30 | 1500 | 0.7220 | -0.0127 | **SUB_BASELINE** |
| ts3_regime_3bet | 1500 | 0.7220 | -0.0127 | **SUB_BASELINE** |
| fourier30_markov30_biglotto | 1500 | 0.7213 | -0.0134 | **SUB_BASELINE** |

---

## Classification Definitions

| Classification | Meaning |
|---|---|
| `PREDICTION_HELPFUL` | Clear positive edge vs baseline (≥ +0.05); sufficient sample size |
| `WATCHLIST_CANDIDATE` | Positive edge (+0.01 to +0.05); monitor before promotion decision |
| `OBSERVE_MORE` | Mixed signal; strategy predicts special but underperforms on it |
| `FALLBACK_EQUIVALENT` | Indistinguishable from random/historical-frequency baseline |
| `SUB_BASELINE` | Consistently below baseline; quarantine review recommended |
| `INCONCLUSIVE` | Metric support incomplete or schema insufficient |
| `INSUFFICIENT_DATA` | Too few evaluated draws for meaningful conclusion |

---

## Concrete Recommendations

### POWER_LOTTO

1. **PREDICTION_HELPFUL → PROMOTE_TO_WATCHLIST_CANDIDATES**
   - `midfreq_fourier_mk_3bet` (edge=+0.080): Strongest strategy overall; top promotion candidate.
   - `pp3_freqort_4bet` (edge=+0.055): Second-strongest; queue for governance watchlist.
   - Next task: **P113 Watchlist Promotion Governance Review**

2. **WATCHLIST_CANDIDATE → CONTINUE_OBSERVATION**
   - 6 strategies show positive edge (+0.017 to +0.045); maintain replay coverage.
   - Priority for temporal stability audit: `fourier_rhythm_3bet`, `power_fourier_rhythm_2bet`.
   - Next task: **P114 Temporal Stability Audit**

3. **FALLBACK_EQUIVALENT → MARK_FALLBACK_EQUIVALENT**
   - `zonal_entropy_2bet`, `cold_complement_2bet`: Consider replacing with more differentiated strategies.
   - Next task: **P116 Strategy Replacement Planning**

### DAILY_539

1. **WATCHLIST_CANDIDATE → CONTINUE_OBSERVATION**
   - 11 strategies show positive edge; this is a strong result for a 39-number pool.
   - Top performers: `p0b_539_3bet_f_cold_fmid`, `p0c_539_3bet_f_cold_x2`, `daily539_f4cold`.
   - Cold-pool + orthogonal approaches consistently outperform pure Markov.
   - Next task: **P114 Temporal Stability Audit**

2. **FALLBACK_EQUIVALENT → MARK_FALLBACK_EQUIVALENT**
   - `acb_markov_midfreq`, `markov_1bet_539`, `daily539_markov_cold`.
   - All Markov-only strategies underperform; avoid promoting Markov-only 539 strategies.

3. **SUB_BASELINE → QUARANTINE_REVIEW**
   - `zone_gap_3bet_539` (edge=-0.0124): Only clearly sub-baseline 539 strategy.
   - Recommend quarantine review before next replay run.
   - Next task: **P115 Strategy Quarantine Governance**

### BIG_LOTTO

1. **WATCHLIST_CANDIDATE → CONTINUE_OBSERVATION**
   - `biglotto_deviation_2bet` (edge=+0.0226): Only candidate with meaningful edge.
   - Monitor across next 500 draws before promotion decision.

2. **FALLBACK_EQUIVALENT → MARK_FALLBACK_EQUIVALENT**
   - 6 strategies are indistinguishable from baseline. BIG_LOTTO (49-number pool)
     is harder to beat than POWER_LOTTO or DAILY_539.
   - Recommend Wave-N targeted optimization: focus on deviation/cold-pool approach
     rather than Markov/regime strategies.

3. **SUB_BASELINE → QUARANTINE_REVIEW**
   - `fourier30_markov30_biglotto` (edge=-0.0134): Worst performer.
   - `biglotto_ts3_markov_4bet_w30`, `ts3_regime_3bet`, `bet2_fourier_expansion_biglotto`:
     All clearly below baseline.
   - Next task: **P115 Strategy Quarantine Governance**

---

## Key Findings

1. **POWER_LOTTO** is the highest-signal lottery. Fourier + midfreq strategies consistently show positive edges. `midfreq_fourier_mk_3bet` is the standout.

2. **DAILY_539** shows broadly positive coverage (11/15 strategies above baseline). Cold-pool + frequency approaches are structurally superior to pure Markov.

3. **BIG_LOTTO** is the hardest lottery to beat. The 49-number pool dilutes any pattern signal. Only `biglotto_deviation_2bet` is worth watching.

4. **Markov-only strategies underperform** across all three lotteries. This is a consistent signal.

5. **No strategy has been promoted.** All classifications are advisory only.

---

## Limitations

1. `hit_count` measures number overlap only; prize-tier weighting not applied.
2. Temporal stability across sub-windows not computed (single pooled window).
3. Baseline is hypergeometric expected value `E[hits]=k²/N` (simple random).
4. `hit_count=0` rows included in average; `REPLAY_ERROR` rows excluded from hit average.
5. 4_STAR excluded: backtest remains unauthorized (source_unknown).
6. 3_STAR excluded: Special3 P108 blocked until 37 more prospective draws.
7. BIG_LOTTO special (bonus ball) not predicted by any audited strategy.
8. DAILY_539 special not applicable (no separate special ball).
9. Two DAILY_539 strategies (`daily539_f4cold`, `daily539_markov_cold`) have 20 `REPLAY_ERROR` rows each; these are excluded from hit averages.

---

## Forbidden-Staging Scan

Before commit, verify:

```
git diff --cached --name-only | grep -E '\.db$|\.db-|\.wal$|\.shm$|lottery_history' && echo "DB_STAGED_ABORT" || echo "DB_STAGE_CLEAN"
```

Expected: `DB_STAGE_CLEAN`

Allowed staged files (exactly 4):
```
outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json
docs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.md
tests/test_p112_cross_lottery_prediction_helpfulness_audit.py
scripts/p112_cross_lottery_prediction_helpfulness_audit.py
```

---

## Test Summary

- Test file: `tests/test_p112_cross_lottery_prediction_helpfulness_audit.py`
- Minimum tests: 35
- Coverage: JSON artifact, MD artifact, governance flags, DB invariants,
  classification validity, recommendations, limitations, script safety

---

## Guard Summary

| Guard | Status |
|---|---|
| `replay_lifecycle_drift_guard.py --strict` | PASS |
| `replay_branch_governance_guard.py --expected-rows 54462` | PASS |

---

## Final Classification

```
P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY
```

- Audited lotteries: POWER_LOTTO (10 strategies), DAILY_539 (15 strategies), BIG_LOTTO (11 strategies)
- Total strategies audited: 36
- DB writes: NONE
- Replay rows: 54462 (unchanged)
- Strategy promotion: NONE
- 4_STAR backtest: NOT RUN (unauthorized)
- Special3 P108: NOT RUN (63/100 draws only)

---

## Next Recommended Tasks

| Priority | Task | Reason |
|---|---|---|
| P113 | Watchlist Promotion Governance Review | `midfreq_fourier_mk_3bet` and `pp3_freqort_4bet` are PREDICTION_HELPFUL candidates |
| P114 | Temporal Stability Audit | Confirm that WATCHLIST edges hold across rolling windows |
| P115 | Strategy Quarantine Governance | `zone_gap_3bet_539`, 4 BIG_LOTTO sub-baseline strategies |
| P108 | Special3 100-Draw Re-evaluation | Wait for 37 more 3_STAR draws first |

---

## Governance Chain

| Task | Classification | Commit |
|---|---|---|
| P105 | DB state acceptance (Option A, Special3 eval only) | ceea6e9 |
| P106 | Special3 Prospective Evaluation Rerun — PARTIAL | bfa2653 |
| P107A | Special3 100-draw monitoring gate — 63/100 | 782e261 |
| P107B | Stale baseline guard repair — READY | e79b5e9 |
| **P112** | **Cross-lottery prediction-helpfulness audit — READY** | *(this PR)* |
