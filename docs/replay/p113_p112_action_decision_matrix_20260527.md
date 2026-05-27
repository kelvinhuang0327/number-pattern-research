# P113: P112 Action Decision Matrix

## PROJECT_CONTEXT_LOCK

```
Project  = LotteryNew
Repo     = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Branch   = p113-p112-action-decision-matrix (base: main)
Task     = P113_P112_ACTION_DECISION_MATRIX
Date     = 2026-05-27
```

This document applies **ONLY** to LotteryNew.  
If any content references Betting-pool, Stock-Prediction-System, Stock, Novel, or SCB: **STOP — context contamination.**

---

## Why P113 Exists

P112 completed a read-only cross-lottery prediction-helpfulness audit of 36 strategies across POWER_LOTTO, DAILY_539, and BIG_LOTTO.  
P112 answered: "which strategies are above/below/equivalent to hypergeometric baseline?"

P113 answers: "given those classifications, what concrete governance actions should be queued, and for which lottery type should the next wave of optimization be prioritized?"

P113 is **decision-support only**. It does not promote any strategy, mutate any lifecycle field, modify any registry, or write to the production database.

---

## Critical Governance Constraints

| Constraint | Status |
|---|---|
| Strategy promotion authorized | **NO** — not from P112/P113 alone |
| Lifecycle / champion metadata mutation | **NO** |
| Registry write | **NO** |
| DB write | **NO** |
| replay row insert | **NO** |
| 4_STAR backtest | **NO — source/provenance unknown** |
| Special3 P108 100-draw re-evaluation | **NO — only 63/100 prospective draws available; 37 more needed** |
| Modify P98–P112 historical artifacts | **NO** |
| API / UI changes | **NO** |

---

## P112 Findings Summary

| Field | Value |
|---|---|
| P112 classification | `P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY` |
| P112 PR | #238 |
| P112 merge commit | `4db894a` |
| Strategies audited | 36 |
| Lotteries covered | POWER_LOTTO, DAILY_539, BIG_LOTTO |
| DB writes | None |
| replay_rows | 54462 (unchanged) |

### P112 Classification Breakdown

| Classification | Count |
|---|---|
| PREDICTION_HELPFUL | 2 |
| WATCHLIST_CANDIDATE | 18 |
| FALLBACK_EQUIVALENT | 11 |
| SUB_BASELINE | 5 |

---

## P113 Action Definitions

| Action | Trigger Classification | Meaning |
|---|---|---|
| `WATCHLIST_QUEUE` | PREDICTION_HELPFUL | Strategy has positive edge above baseline. Queue for controlled OOS monitoring design. **Promotion NOT authorized.** |
| `OBSERVATION_QUEUE` | WATCHLIST_CANDIDATE | Positive edge but more evidence needed. Accumulate prospective draws; eligible for Wave-N planning. |
| `CONTINUE_OBSERVATION` | OBSERVE_MORE | Sample size or stability insufficient. Passive monitoring only. |
| `FALLBACK_DISCLOSURE_CANDIDATE` | FALLBACK_EQUIVALENT | Performance indistinguishable from random. Disclose as fallback when used in production. |
| `DEMOTE_OR_QUARANTINE_CANDIDATE` | SUB_BASELINE | Below baseline. Quarantine/demotion candidate for P115 or equivalent. **Not auto-demoted here.** |
| `HOLD_FOR_MORE_DATA` | INCONCLUSIVE / INSUFFICIENT_DATA | No action until sufficient data available. |

---

## Current Post-P112 Baseline

| Lottery | Baseline (main) | Max Observed Edge | Best Strategy |
|---|---|---|---|
| POWER_LOTTO | 0.9474 (6/38 × 6) | +0.0800 | midfreq_fourier_mk_3bet |
| DAILY_539 | 0.6410 (5/39 × 5) | +0.0363 | p0b_539_3bet_f_cold_fmid / p0c_539_3bet_f_cold_x2 |
| BIG_LOTTO | 0.7347 (6/49 × 6) | +0.0226 | biglotto_deviation_2bet |

---

## Per-Lottery Decision Matrix

### POWER_LOTTO — Priority: HIGH

POWER_LOTTO has the strongest evidence of prediction edge.  
Two strategies (midfreq_fourier_mk_3bet, pp3_freqort_4bet) are PREDICTION_HELPFUL — the highest classification tier.  
Six additional strategies are WATCHLIST_CANDIDATE with positive edges.

| Metric | Value |
|---|---|
| Watchlist Queue count | 2 |
| Observation Queue count | 6 |
| Fallback Disclosure count | 2 |
| Demote/Quarantine count | 0 |
| Recommended next task | P114 temporal stability audit; OOS monitoring design for helpful strategies |

### DAILY_539 — Priority: MEDIUM

DAILY_539 shows broad observation value with 11 WATCHLIST_CANDIDATE strategies.  
Cold-pool and orthogonal variants consistently outperform Markov-based strategies.  
One strategy (zone_gap_3bet_539) is SUB_BASELINE and should be quarantined via P115.

| Metric | Value |
|---|---|
| Watchlist Queue count | 0 |
| Observation Queue count | 11 |
| Fallback Disclosure count | 3 |
| Demote/Quarantine count | 1 |
| Recommended next task | P114 temporal stability audit; P115 quarantine for zone_gap_3bet_539 |

### BIG_LOTTO — Priority: LOW / REPAIR FIRST

BIG_LOTTO is the hardest mature lottery to beat.  
Only one strategy (biglotto_deviation_2bet) qualifies as WATCHLIST_CANDIDATE.  
Four strategies are SUB_BASELINE and four more are FALLBACK_EQUIVALENT.  
Strategy redesign should precede any expansion work.

| Metric | Value |
|---|---|
| Watchlist Queue count | 0 |
| Observation Queue count | 1 |
| Fallback Disclosure count | 6 |
| Demote/Quarantine count | 4 |
| Recommended next task | P115 quarantine for 4 sub-baseline strategies; strategy redesign before Wave-N expansion |

---

## Per-Strategy Action Matrix

### POWER_LOTTO (10 strategies)

| Strategy | P112 Classification | P113 Action | Edge vs Baseline | Next Task Candidate |
|---|---|---|---|---|
| midfreq_fourier_mk_3bet | PREDICTION_HELPFUL | **WATCHLIST_QUEUE** | +0.0800 | P114/P116 OOS monitoring design |
| pp3_freqort_4bet | PREDICTION_HELPFUL | **WATCHLIST_QUEUE** | +0.0546 | P114/P116 OOS monitoring design |
| fourier_rhythm_3bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0453 | P114 temporal stability / Wave-N |
| power_fourier_rhythm_2bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0453 | P114 temporal stability / Wave-N |
| power_orthogonal_5bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0450 | P114 temporal stability / Wave-N |
| power_precision_3bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0450 | P114 temporal stability / Wave-N |
| midfreq_fourier_2bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0253 | P114 temporal stability / Wave-N |
| fourier30_markov30_2bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0173 | P114 temporal stability / Wave-N |
| zonal_entropy_2bet | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0014 | P116 fallback disclosure or no action |
| cold_complement_2bet | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0067 | P116 fallback disclosure or no action |

All strategies: `promotion_authorized = false`

### DAILY_539 (15 strategies)

| Strategy | P112 Classification | P113 Action | Edge vs Baseline | Next Task Candidate |
|---|---|---|---|---|
| p0b_539_3bet_f_cold_fmid | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0363 | P114 / Wave-N |
| p0c_539_3bet_f_cold_x2 | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0363 | P114 / Wave-N |
| daily539_f4cold | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0348 | P114 / Wave-N |
| daily539_f4cold_3bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0316 | P114 / Wave-N |
| daily539_f4cold_5bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0316 | P114 / Wave-N |
| 539_3bet_orthogonal | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0310 | P114 / Wave-N |
| acb_1bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0310 | P114 / Wave-N |
| acb_markov_midfreq_3bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0310 | P114 / Wave-N |
| acb_single_539 | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0310 | P114 / Wave-N |
| midfreq_acb_2bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0283 | P114 / Wave-N |
| midfreq_fourier_2bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0283 | P114 / Wave-N |
| acb_markov_midfreq | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0044 | No immediate action |
| daily539_markov_cold | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0073 | No immediate action |
| markov_1bet_539 | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0070 | No immediate action |
| zone_gap_3bet_539 | SUB_BASELINE | **DEMOTE_OR_QUARANTINE_CANDIDATE** | -0.0124 | P115 quarantine governance |

All strategies: `promotion_authorized = false`

### BIG_LOTTO (11 strategies)

| Strategy | P112 Classification | P113 Action | Edge vs Baseline | Next Task Candidate |
|---|---|---|---|---|
| biglotto_deviation_2bet | WATCHLIST_CANDIDATE | OBSERVATION_QUEUE | +0.0226 | P114 / Wave-N |
| biglotto_echo_aware_3bet | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | +0.0046 | No immediate action |
| cold_complement_biglotto | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | +0.0006 | No immediate action |
| coldpool15_biglotto | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | +0.0006 | No immediate action |
| biglotto_triple_strike | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0067 | No immediate action |
| markov_2bet_biglotto | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0067 | No immediate action |
| markov_single_biglotto | FALLBACK_EQUIVALENT | FALLBACK_DISCLOSURE_CANDIDATE | -0.0067 | No immediate action |
| bet2_fourier_expansion_biglotto | SUB_BASELINE | **DEMOTE_OR_QUARANTINE_CANDIDATE** | -0.0107 | P115 quarantine governance |
| biglotto_ts3_markov_4bet_w30 | SUB_BASELINE | **DEMOTE_OR_QUARANTINE_CANDIDATE** | -0.0127 | P115 quarantine governance |
| ts3_regime_3bet | SUB_BASELINE | **DEMOTE_OR_QUARANTINE_CANDIDATE** | -0.0127 | P115 quarantine governance |
| fourier30_markov30_biglotto | SUB_BASELINE | **DEMOTE_OR_QUARANTINE_CANDIDATE** | -0.0134 | P115 quarantine governance |

All strategies: `promotion_authorized = false`

---

## Action Summary Counts

| Action | Count | Lotteries |
|---|---|---|
| WATCHLIST_QUEUE | 2 | POWER_LOTTO |
| OBSERVATION_QUEUE | 18 | POWER_LOTTO(6), DAILY_539(11), BIG_LOTTO(1) |
| FALLBACK_DISCLOSURE_CANDIDATE | 11 | POWER_LOTTO(2), DAILY_539(3), BIG_LOTTO(6) |
| DEMOTE_OR_QUARANTINE_CANDIDATE | 5 | DAILY_539(1), BIG_LOTTO(4) |
| **Total** | **36** | |

---

## Wave-N Backlog

| Priority | Lottery | Label | Candidate Scope |
|---|---|---|---|
| 1 | POWER_LOTTO | WAVE_N_POWER_LOTTO_OOS_MONITORING | midfreq_fourier_mk_3bet, pp3_freqort_4bet |
| 2 | POWER_LOTTO | WAVE_N_POWER_LOTTO_WATCHLIST_EXPANSION | 6 watchlist candidates |
| 3 | DAILY_539 | WAVE_N_DAILY_539_OBSERVATION_EXPANSION | 11 watchlist candidates |
| 4 | BIG_LOTTO | WAVE_N_BIG_LOTTO_SINGLE_WATCHLIST | biglotto_deviation_2bet |
| 5 | BIG_LOTTO | WAVE_N_BIG_LOTTO_QUARANTINE_REVIEW | 4 sub-baseline strategies → P115 |

All Wave-N items require explicit authorization before execution. P112/P113 alone does **NOT** authorize execution.

---

## Explicit Holds

### SPECIAL3_P108_HOLD

Special3 P108 100-draw re-evaluation is **NOT EXECUTABLE**.

- Prospective draws after P99 cutoff: **63/100**
- Remaining draws needed: **37**
- Unblock condition: 37 additional 3_STAR draws completed

This hold is unchanged from P107A.

### FOUR_STAR_BACKTEST_HOLD

4_STAR backtest remains **NOT AUTHORIZED**.

- 4_STAR row source/provenance: **unknown**
- source_unknown caveat preserved
- Unblock condition: source determination + explicit backtest authorization

### NO_PRODUCTION_PROMOTION_FROM_P112_P113

No strategy promotion from P112 or P113 findings alone.

- P112 = audit
- P113 = decision matrix
- Neither authorizes deployment, lifecycle mutation, or champion change
- Unblock condition: explicit promotion authorization task (P114/P116 equivalent)

---

## Limitations

1. P112 audit window covers only historical replay rows as of 2026-05-27; prospective performance may differ.
2. Edge estimates are point estimates from available replay data; no confidence intervals are computed in P113.
3. P113 decision matrix uses P112 classification as input; any P112 misclassification propagates.
4. No temporal stability analysis is performed in P113; deferred to P114.
5. Promotion decisions require separate explicit governance authorization not present in P112/P113.
6. BIG_LOTTO strategies with FALLBACK_EQUIVALENT classification may still appear in live rotation; this audit does not modify live routing.

---

## Forbidden-Staging Scan

Before commit, scan confirms:

```
git diff --cached --name-only | grep -E '\.db$|\.db-|\.wal$|\.shm$|lottery_history'
```

Expected result: `DB_STAGE_CLEAN`

Whitelisted staged files (exactly 4):
- `outputs/replay/p113_p112_action_decision_matrix_20260527.json`
- `docs/replay/p113_p112_action_decision_matrix_20260527.md`
- `tests/test_p113_p112_action_decision_matrix.py`
- `scripts/p113_p112_action_decision_matrix.py`

---

## Test Summary

Test file: `tests/test_p113_p112_action_decision_matrix.py`

Covers:
- JSON artifact exists and parses
- MD artifact exists
- classification == `P113_P112_ACTION_DECISION_MATRIX_READY`
- task_id == `P113_P112_ACTION_DECISION_MATRIX`
- p112_reference fields
- governance flags (db_writes, no_strategy_promotion, no_lifecycle_mutation, no_registry_mutation, no_4star_backtest, no_special3_p108_rerun, source_unknown_caveat_preserved)
- replay_rows invariants
- action_definitions include required keys
- per_lottery_decision_matrix exists
- per_strategy_action_matrix: all strategies have promotion_authorized=false, rationale, next_task_candidate
- wave_n_backlog exists
- explicit_holds include Special3 P108, 4_STAR, no-promotion
- live DB replay rows remain 54462
- script has no SQL write verbs
- MD content checks (no promotion authorization, P108 blocked, 4_STAR unauthorized, final classification)
- no DB files staged

---

## Guard Summary

| Guard | Expected Result |
|---|---|
| replay_lifecycle_drift_guard.py --strict | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| replay_branch_governance_guard.py --expected-branch p113-p112-action-decision-matrix --expected-rows 54462 | BRANCH_GOVERNANCE_PASS |

---

## Final Classification

`P113_P112_ACTION_DECISION_MATRIX_READY`

---

## Governance Chain

| Task | Classification | Commit |
|---|---|---|
| P105 | DB state acceptance (Option A) | ceea6e9 |
| P106 | Special3 Prospective Evaluation Rerun — PARTIAL | bfa2653 |
| P107A | Special3 100-draw monitoring gate — 63/100 | 782e261 |
| P107B | Stale baseline guard repair — READY | e79b5e9 |
| P112 | Cross-lottery prediction-helpfulness audit — READY | 4db894a |
| P113 | P112 action decision matrix — **READY** | _(this commit)_ |

---

## Next Recommended Tasks

| Priority | Task | Description |
|---|---|---|
| 1 | **P114** | Temporal Stability Audit — confirm WATCHLIST_QUEUE and top OBSERVATION_QUEUE edges hold across rolling windows |
| 2 | **P115** | Strategy Quarantine Governance — quarantine zone_gap_3bet_539 + 4 BIG_LOTTO sub-baseline strategies |
| 3 | **P116** | OOS Monitoring Design — design controlled observation protocol for midfreq_fourier_mk_3bet and pp3_freqort_4bet |
| 4 | **P108** | Special3 100-Draw Re-evaluation — **BLOCKED** until 37 more 3_STAR draws |
