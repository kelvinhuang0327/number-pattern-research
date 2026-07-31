# P114: Temporal Stability Audit

**Date:** 2026-05-27  
**Classification:** P114_TEMPORAL_STABILITY_AUDIT_READY  
**Task ID:** P114_TEMPORAL_STABILITY_AUDIT  
**Branch:** p114-temporal-stability-audit  
**Governance Chain:** P105 → P106 → P107A → P107B → P112 → P113 → **P114**

---

## PROJECT_CONTEXT_LOCK

Project = LotteryNew  
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew  
Canonical Branch = main  

This task applies ONLY to LotteryNew.  
If any task, file, commit, roadmap, artifact, or context belongs to another project
(Betting-pool, Stock-Prediction-System, Stock, Novel, SCB, etc.):  
**STOP immediately. Do NOT modify code. Classify as P114_BLOCKED_BY_CONTEXT_CONTAMINATION.**

---

## Why P114 Exists

P112 computed prediction-helpfulness audit (single pooled window) and classified 36
strategies across POWER_LOTTO, DAILY_539, and BIG_LOTTO. P113 converted those
classifications into an action decision matrix with WATCHLIST_QUEUE, OBSERVATION_QUEUE,
DEMOTE_OR_QUARANTINE_CANDIDATE, and FALLBACK_DISCLOSURE_CANDIDATE labels — but noted that
"temporal stability across sub-windows not computed (single pooled window)" as an explicit
caveat in every strategy's P112 entry.

P114 resolves that caveat by computing chronological window-based edge stability for all 36
strategies. The goal is to distinguish strategies whose positive edge is stable across time
from those where the edge is concentrated in one period or reversal-prone. This audit is
**read-only** — no strategy is promoted, no lifecycle or registry mutation occurs, and no DB
writes are made.

---

## Current Post-P113 Baseline

| Metric | Value |
|---|---|
| replay_rows | **54462** (unchanged) |
| 3_STAR draws | 4179 / max 115000106 |
| 4_STAR draws | 2922 / max 115000103 |
| POWER_LOTTO draws | 1913 / max 115000041 |
| P113 merge commit | be3716e |
| Drift guard | PASS |
| Branch governance guard | PASS |

---

## Governance Constraints (Explicit)

| Constraint | Status |
|---|---|
| Strategy promotion authorized | **NO** |
| Lifecycle mutation authorized | **NO** |
| Registry mutation authorized | **NO** |
| DB writes | **NO** |
| 4_STAR backtest | **NOT AUTHORIZED** (source_unknown caveat active) |
| Special3 P108 re-evaluation | **BLOCKED** — 63/100 prospective draws; 37 more needed |
| Modification of P98–P113 artifacts | **FORBIDDEN** |

---

## Input Artifacts

| Artifact | Path | Classification |
|---|---|---|
| P112 | `outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json` | P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY |
| P113 | `outputs/replay/p113_p112_action_decision_matrix_20260527.json` | P113_P112_ACTION_DECISION_MATRIX_READY |

---

## Methodology

For each of the 36 strategies in the P113 action matrix:

1. Load all `replay_status='PREDICTED'` rows from `strategy_prediction_replays` for the
   strategy's `strategy_id` and `lottery_type`, sorted chronologically by `CAST(target_draw
   AS INTEGER)` ascending.
2. Split into three equal chronological thirds (first_third, middle_third, last_third).
3. Compute per-window stats:
   - `avg_hit_count` = mean of `hit_count` for rows in window
   - `baseline_avg_hit_count` = the hypergeometric expected hits from P112 (constant for
     the strategy)
   - `edge_vs_baseline` = avg_hit_count − baseline
4. Assign `stability_label` from the three window edges.
5. Assign `p114_decision` from (P113 action, stability_label) per decision rules.
6. Additional rolling windows (rolling_100, rolling_250) are also computed where sufficient
   rows exist, for reference.

---

## Temporal Window Definitions

| Window | Definition |
|---|---|
| first_third | First 1/3 of rows sorted by target_draw (chronologically earliest draws) |
| middle_third | Middle 1/3 of rows sorted by target_draw |
| last_third | Last 1/3 of rows sorted by target_draw (most recent draws) |
| rolling_100 | Last 100 rows by target_draw (computed when total rows ≥ 100) |
| rolling_250 | Last 250 rows by target_draw (computed when total rows ≥ 250) |

### Stability Labels

| Label | Definition |
|---|---|
| STABLE_POSITIVE | Positive edge in all 3 chronological windows |
| MOSTLY_POSITIVE | Positive edge in 2 of 3 windows |
| MIXED | Positive in 1 of 3 windows; no dominant concentration |
| UNSTABLE | Positive in 1 of 3 windows; that window's edge dominates (>1.5× mean absolute) |
| STABLE_NEGATIVE | Negative edge in all 3 windows |
| INSUFFICIENT_WINDOW_DATA | Fewer than 90 total rows |

### Decision Rules

| P113 Action | Stability | P114 Decision |
|---|---|---|
| WATCHLIST_QUEUE | STABLE_POSITIVE | READY_FOR_OOS_MONITORING_DESIGN |
| WATCHLIST_QUEUE | MOSTLY_POSITIVE | READY_FOR_CONTROLLED_OBSERVATION_PLAN |
| WATCHLIST_QUEUE | MIXED / UNSTABLE / STABLE_NEGATIVE | HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE |
| OBSERVATION_QUEUE | STABLE_POSITIVE / MOSTLY_POSITIVE | KEEP_IN_OBSERVATION_AND_RETEST |
| OBSERVATION_QUEUE | STABLE_NEGATIVE | READY_FOR_QUARANTINE_GOVERNANCE |
| DEMOTE_OR_QUARANTINE_CANDIDATE | STABLE_NEGATIVE | READY_FOR_QUARANTINE_GOVERNANCE |
| DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED / UNSTABLE | HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE |
| FALLBACK_DISCLOSURE_CANDIDATE | STABLE_NEGATIVE | READY_FOR_QUARANTINE_GOVERNANCE |
| FALLBACK_DISCLOSURE_CANDIDATE | other | KEEP_IN_OBSERVATION_AND_RETEST |
| Any | INSUFFICIENT_WINDOW_DATA | HOLD_FOR_MORE_DATA |

---

## Stability Label Distribution

| Label | Count |
|---|---|
| STABLE_POSITIVE | 7 |
| MOSTLY_POSITIVE | 17 |
| MIXED | 9 |
| UNSTABLE | 2 |
| STABLE_NEGATIVE | 1 |
| INSUFFICIENT_WINDOW_DATA | 0 |

## P114 Decision Distribution

| Decision | Count |
|---|---|
| READY_FOR_OOS_MONITORING_DESIGN | 1 |
| READY_FOR_CONTROLLED_OBSERVATION_PLAN | 1 |
| KEEP_IN_OBSERVATION_AND_RETEST | 29 |
| HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE | 4 |
| READY_FOR_QUARANTINE_GOVERNANCE | 1 |
| HOLD_FOR_MORE_DATA | 0 |

---

## Per-Lottery Temporal Results

### POWER_LOTTO (10 strategies)

| strategy_id | P113 Action | Stability | first | middle | last | P114 Decision |
|---|---|---|---|---|---|---|
| midfreq_fourier_mk_3bet | WATCHLIST_QUEUE | STABLE_POSITIVE | +0.0766 | +0.1026 | +0.0606 | **READY_FOR_OOS_MONITORING_DESIGN** |
| pp3_freqort_4bet | WATCHLIST_QUEUE | MOSTLY_POSITIVE | +0.0846 | +0.0946 | −0.0154 | **READY_FOR_CONTROLLED_OBSERVATION_PLAN** |
| midfreq_fourier_2bet | OBSERVATION_QUEUE | STABLE_POSITIVE | +0.0486 | +0.0006 | +0.0266 | KEEP_IN_OBSERVATION_AND_RETEST |
| fourier_rhythm_3bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0606 | +0.0906 | −0.0152 | KEEP_IN_OBSERVATION_AND_RETEST |
| power_fourier_rhythm_2bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0646 | +0.0906 | −0.0194 | KEEP_IN_OBSERVATION_AND_RETEST |
| power_orthogonal_5bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0488 | +0.0985 | −0.0123 | KEEP_IN_OBSERVATION_AND_RETEST |
| power_precision_3bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0488 | +0.0985 | −0.0123 | KEEP_IN_OBSERVATION_AND_RETEST |
| fourier30_markov30_2bet | OBSERVATION_QUEUE | UNSTABLE | −0.0054 | −0.0034 | +0.0606 | KEEP_IN_OBSERVATION_AND_RETEST |
| cold_complement_2bet | FALLBACK_DISCLOSURE_CANDIDATE | MIXED | −0.0234 | +0.0306 | −0.0274 | KEEP_IN_OBSERVATION_AND_RETEST |
| zonal_entropy_2bet | FALLBACK_DISCLOSURE_CANDIDATE | MOSTLY_POSITIVE | −0.0374 | +0.0186 | +0.0146 | KEEP_IN_OBSERVATION_AND_RETEST |

### DAILY_539 (15 strategies)

| strategy_id | P113 Action | Stability | first | middle | last | P114 Decision |
|---|---|---|---|---|---|---|
| daily539_f4cold | OBSERVATION_QUEUE | STABLE_POSITIVE | +0.0588 | +0.0320 | +0.0136 | KEEP_IN_OBSERVATION_AND_RETEST |
| daily539_f4cold_3bet | OBSERVATION_QUEUE | STABLE_POSITIVE | +0.0590 | +0.0130 | +0.0230 | KEEP_IN_OBSERVATION_AND_RETEST |
| daily539_f4cold_5bet | OBSERVATION_QUEUE | STABLE_POSITIVE | +0.0590 | +0.0130 | +0.0230 | KEEP_IN_OBSERVATION_AND_RETEST |
| p0b_539_3bet_f_cold_fmid | OBSERVATION_QUEUE | STABLE_POSITIVE | +0.0630 | +0.0130 | +0.0330 | KEEP_IN_OBSERVATION_AND_RETEST |
| p0c_539_3bet_f_cold_x2 | OBSERVATION_QUEUE | STABLE_POSITIVE | +0.0630 | +0.0130 | +0.0330 | KEEP_IN_OBSERVATION_AND_RETEST |
| 539_3bet_orthogonal | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0490 | +0.0490 | −0.0050 | KEEP_IN_OBSERVATION_AND_RETEST |
| acb_1bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0490 | +0.0490 | −0.0050 | KEEP_IN_OBSERVATION_AND_RETEST |
| acb_markov_midfreq_3bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0490 | +0.0490 | −0.0050 | KEEP_IN_OBSERVATION_AND_RETEST |
| acb_single_539 | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0490 | +0.0490 | −0.0050 | KEEP_IN_OBSERVATION_AND_RETEST |
| daily539_markov_cold | FALLBACK_DISCLOSURE_CANDIDATE | MOSTLY_POSITIVE | +0.0186 | −0.0579 | +0.0174 | KEEP_IN_OBSERVATION_AND_RETEST |
| markov_1bet_539 | FALLBACK_DISCLOSURE_CANDIDATE | MOSTLY_POSITIVE | +0.0150 | −0.0590 | +0.0230 | KEEP_IN_OBSERVATION_AND_RETEST |
| midfreq_acb_2bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0390 | −0.0230 | +0.0690 | KEEP_IN_OBSERVATION_AND_RETEST |
| midfreq_fourier_2bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | +0.0390 | −0.0230 | +0.0690 | KEEP_IN_OBSERVATION_AND_RETEST |
| acb_markov_midfreq | FALLBACK_DISCLOSURE_CANDIDATE | MIXED | +0.0290 | −0.0410 | −0.0010 | KEEP_IN_OBSERVATION_AND_RETEST |
| zone_gap_3bet_539 | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED | +0.0070 | −0.0190 | −0.0250 | HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE |

### BIG_LOTTO (11 strategies)

| strategy_id | P113 Action | Stability | first | middle | last | P114 Decision |
|---|---|---|---|---|---|---|
| fourier30_markov30_biglotto | DEMOTE_OR_QUARANTINE_CANDIDATE | **STABLE_NEGATIVE** | −0.0167 | −0.0187 | −0.0047 | **READY_FOR_QUARANTINE_GOVERNANCE** |
| biglotto_deviation_2bet | OBSERVATION_QUEUE | MOSTLY_POSITIVE | −0.0196 | +0.0072 | +0.0802 | KEEP_IN_OBSERVATION_AND_RETEST |
| cold_complement_biglotto | FALLBACK_DISCLOSURE_CANDIDATE | MOSTLY_POSITIVE | −0.0487 | +0.0033 | +0.0473 | KEEP_IN_OBSERVATION_AND_RETEST |
| coldpool15_biglotto | FALLBACK_DISCLOSURE_CANDIDATE | MOSTLY_POSITIVE | −0.0487 | +0.0033 | +0.0473 | KEEP_IN_OBSERVATION_AND_RETEST |
| biglotto_echo_aware_3bet | FALLBACK_DISCLOSURE_CANDIDATE | UNSTABLE | −0.0127 | −0.0027 | +0.0293 | KEEP_IN_OBSERVATION_AND_RETEST |
| biglotto_triple_strike | FALLBACK_DISCLOSURE_CANDIDATE | MIXED | −0.0005 | +0.0034 | −0.0229 | KEEP_IN_OBSERVATION_AND_RETEST |
| markov_2bet_biglotto | FALLBACK_DISCLOSURE_CANDIDATE | MIXED | −0.0127 | +0.0353 | −0.0427 | KEEP_IN_OBSERVATION_AND_RETEST |
| markov_single_biglotto | FALLBACK_DISCLOSURE_CANDIDATE | MIXED | −0.0127 | +0.0353 | −0.0427 | KEEP_IN_OBSERVATION_AND_RETEST |
| bet2_fourier_expansion_biglotto | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED | −0.0307 | +0.0133 | −0.0147 | HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE |
| biglotto_ts3_markov_4bet_w30 | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED | −0.0167 | +0.0053 | −0.0267 | HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE |
| ts3_regime_3bet | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED | −0.0147 | +0.0053 | −0.0287 | HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE |

---

## OOS Monitoring Candidates

**Strategies eligible for OOS Monitoring Design (P116):**

| strategy_id | lottery_type | Stability | P112 Edge |
|---|---|---|---|
| midfreq_fourier_mk_3bet | POWER_LOTTO | STABLE_POSITIVE | +0.0800 |

Rationale: midfreq_fourier_mk_3bet is the only WATCHLIST_QUEUE strategy with STABLE_POSITIVE
across all three chronological windows (+0.0766, +0.1026, +0.0606). This is the strongest
stability signal in the audit. **Promotion is NOT authorized.** Next recommended task: P116
(OOS monitoring design).

---

## Controlled Observation Candidates

**Strategies eligible for Controlled Observation Plan (P116):**

| strategy_id | lottery_type | Stability | P112 Edge |
|---|---|---|---|
| pp3_freqort_4bet | POWER_LOTTO | MOSTLY_POSITIVE | +0.0546 |

Rationale: pp3_freqort_4bet is WATCHLIST_QUEUE with MOSTLY_POSITIVE (positive in 2/3 windows:
first_third=+0.0846, middle_third=+0.0946, but last_third=−0.0154). The recent weakness in the
last window warrants controlled observation rather than full OOS monitoring. **Promotion is NOT
authorized.**

---

## Quarantine Governance Candidates

**Strategies eligible for Quarantine Governance (P115):**

| strategy_id | lottery_type | Stability | All window edges |
|---|---|---|---|
| fourier30_markov30_biglotto | BIG_LOTTO | STABLE_NEGATIVE | −0.0167 / −0.0187 / −0.0047 |

Rationale: fourier30_markov30_biglotto is a DEMOTE_OR_QUARANTINE_CANDIDATE (from P113) that
shows STABLE_NEGATIVE across all three chronological windows. This is the only strategy in the
audit with confirmed temporal consistency of negative edge. **Next recommended task: P115
(Quarantine Governance).**

---

## Hold for Additional Stability Evidence

**Strategies in HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE:**

| strategy_id | lottery_type | P113 Action | Stability |
|---|---|---|---|
| zone_gap_3bet_539 | DAILY_539 | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED |
| bet2_fourier_expansion_biglotto | BIG_LOTTO | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED |
| biglotto_ts3_markov_4bet_w30 | BIG_LOTTO | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED |
| ts3_regime_3bet | BIG_LOTTO | DEMOTE_OR_QUARANTINE_CANDIDATE | MIXED |

Rationale: These DEMOTE_OR_QUARANTINE_CANDIDATE strategies show MIXED stability — negative in
some windows, positive in others. STABLE_NEGATIVE confirmation is required before quarantine
governance can proceed. More draws are needed for a clear verdict.

---

## Hold for More Data

No strategies in HOLD_FOR_MORE_DATA. All 36 strategies had sufficient rows for temporal windows
(minimum 1500 rows each).

---

## Limitations

1. Temporal windows based on `target_draw` ordering (integer sort), not calendar time. Draw
   numbering is monotonic so this is equivalent to chronological order, but calendar
   seasonality is not modeled.
2. Baseline values carried from P112 (hypergeometric expectation per strategy). These are
   constant for a given strategy's pool size and bet count — they do not vary per draw.
3. `hit_count` measures main number overlap only; prize-tier weighting is not applied.
4. 4_STAR backtest remains unauthorized; 4_STAR strategies excluded from this audit.
5. Special3/P106 evaluation excluded; P108 blocked until 37 more 3_STAR draws (63/100 so far).
6. `source_unknown` caveat preserved from P112: draw data provenance unverified for some entries.
7. Window edges are point estimates; confidence intervals are not computed in this pass.
8. Stability labels derived from chronological thirds of replay rows only; no permutation test
   or bootstrap significance test applied in P114.

---

## Forbidden-Staging Scan

Before commit, the following scan must return `DB_STAGE_CLEAN`:

```
git diff --cached --name-only | grep -E '\.db$|\.db-|\.wal$|\.shm$|lottery_history' && echo "DB_STAGED_ABORT" || echo "DB_STAGE_CLEAN"
```

**Expected result: DB_STAGE_CLEAN**

Allowed staged files (whitelist):

```
outputs/replay/p114_temporal_stability_audit_20260527.json
docs/replay/p114_temporal_stability_audit_20260527.md
tests/test_p114_temporal_stability_audit.py
scripts/p114_temporal_stability_audit.py
```

---

## Script Safety

`scripts/p114_temporal_stability_audit.py` contains:

- No SQL write verbs: INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, REPLACE, VACUUM are absent
- DB opened via `?mode=ro` URI (read-only flag)
- All writes are to the `--json-out` path only
- `--json-out` argument is required (argparse)

---

## Test Summary

Focused suite: `tests/test_p114_temporal_stability_audit.py` contains ≥ 40 tests covering:

- JSON artifact existence and parse validity
- MD artifact existence
- classification valid and recognized
- task_id = P114_TEMPORAL_STABILITY_AUDIT
- p112_reference and p113_reference present
- db_writes = false
- replay_rows_before = replay_rows_after = 54462
- all governance flags (no_strategy_promotion, no_lifecycle_mutation, no_registry_mutation,
  no_4star_backtest, no_special3_p108_rerun, source_unknown_caveat_preserved)
- audited_lottery_types includes POWER_LOTTO, DAILY_539, BIG_LOTTO
- audited_strategy_count ≥ 1
- temporal_window_definitions present
- per_strategy_temporal_results: strategy_id, lottery_type, stability_label, p114_decision,
  promotion_authorized all valid
- all stability_labels from allowed set
- all p114_decisions from allowed set
- all promotion_authorized = false
- oos_monitoring_candidates, controlled_observation_candidates, quarantine_governance_candidates,
  hold_for_more_data_candidates all present
- live DB replay rows remain 54462
- script exists and has no SQL write verbs
- MD: no promotion authorization, P108 blocked, 4_STAR unauthorized, final classification present
- no DB files in staged changes for current commit

---

## Drift Guard / Branch Governance Guard Summary

| Guard | Expected | Status |
|---|---|---|
| replay_lifecycle_drift_guard --strict | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | ✓ PASS |
| replay_branch_governance_guard --expected-branch p114-temporal-stability-audit --expected-rows 54462 | BRANCH_GOVERNANCE_PASS | ✓ PASS |

---

## Explicit Holds

| Hold ID | Reason |
|---|---|
| SPECIAL3_P108_HOLD | P108 re-evaluation blocked until 37 more 3_STAR draws (63/100 so far) |
| FOUR_STAR_BACKTEST_HOLD | 4_STAR backtest unauthorized; source_unknown caveat active |
| NO_PRODUCTION_PROMOTION_FROM_P114 | P114 does not authorize any strategy promotion to production |

---

## Final Classification

**P114_TEMPORAL_STABILITY_AUDIT_READY**

All 36 strategies had sufficient replay rows for temporal window computation (0 with
INSUFFICIENT_WINDOW_DATA). The audit is complete.

---

## Next Recommended Tasks

| Task | Scope | Trigger Condition |
|---|---|---|
| **P115** | Quarantine Governance | fourier30_markov30_biglotto confirmed STABLE_NEGATIVE; formal quarantine governance needed |
| **P116** | OOS Monitoring Design | midfreq_fourier_mk_3bet (READY_FOR_OOS_MONITORING_DESIGN) and pp3_freqort_4bet (READY_FOR_CONTROLLED_OBSERVATION_PLAN) |
| **P108** | Special3 100-Draw Re-evaluation | **BLOCKED** — 37 more 3_STAR draws required (63/100 so far) |

4_STAR backtest remains **NOT AUTHORIZED**. source_unknown caveat remains active.

---

## Governance Chain

| Task | Classification | Commit |
|---|---|---|
| P105 | DB state acceptance (Option A) | ceea6e9 |
| P106 | Special3 Prospective Evaluation Rerun — PARTIAL | bfa2653 |
| P107A | Special3 100-draw monitoring gate — 63/100 | 782e261 |
| P107B | Stale baseline guard repair — READY | e79b5e9 |
| P112 | Cross-lottery prediction-helpfulness audit — READY | 4db894a |
| P113 | P112 action decision matrix — READY | be3716e |
| **P114** | **Temporal stability audit — READY** | *(this branch)* |
