# P116: POWER_LOTTO OOS Monitoring Design

## PROJECT_CONTEXT_LOCK

Project = LotteryNew  
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew  
Canonical Branch = main  
Task = P116_POWERLOTTO_OOS_MONITORING_DESIGN  
Generated = 20260527  

This document applies ONLY to LotteryNew.  
If any content, commit, or artifact belongs to another project, classify as `P116_BLOCKED_BY_CONTEXT_CONTAMINATION`.

---

## Why P116 Exists

P112 audited 36 strategies across POWER_LOTTO, DAILY_539, and BIG_LOTTO for prediction helpfulness.  
P113 assigned governance actions to each strategy based on P112 results.  
P114 performed temporal stability audit across chronological thirds for all 36 strategies.

P114 identified two POWER_LOTTO strategies warranting formal OOS monitoring design:

| Strategy | P114 Stability | P114 Decision |
|---|---|---|
| midfreq_fourier_mk_3bet | STABLE_POSITIVE | READY_FOR_OOS_MONITORING_DESIGN |
| pp3_freqort_4bet | MOSTLY_POSITIVE | READY_FOR_CONTROLLED_OBSERVATION_PLAN |

P116 formalizes what OOS monitoring must look like for these strategies before any future promotion discussion is permitted.

---

## Explicit Governance Constraints

> **This task does NOT authorize promotion of any strategy.**  
> **This task does NOT implement live monitoring infrastructure.**  
> **P108 Special3 100-draw re-evaluation is BLOCKED until 37 more 3_STAR draws are available.**  
> **4_STAR backtest remains NOT AUTHORIZED (source_unknown caveat active).**  
> **P115 quarantine governance for fourier30_markov30_biglotto is a SEPARATE task and NOT part of P116.**

---

## Current Post-P114 Baseline

| Metric | Value |
|---|---|
| replay_rows | 54462 |
| 3_STAR count | 4179 |
| 3_STAR max draw | 115000106 |
| 4_STAR count | 2922 |
| 4_STAR max draw | 115000103 |
| POWER_LOTTO count | 1913 |
| POWER_LOTTO max draw | 115000041 |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| Branch governance | BRANCH_GOVERNANCE_PASS |
| P114 merge commit | 3ffae64 |

---

## Input Artifacts

| Task | Classification | Path |
|---|---|---|
| P112 | P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY | outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json |
| P113 | P113_P112_ACTION_DECISION_MATRIX_READY | outputs/replay/p113_p112_action_decision_matrix_20260527.json |
| P114 | P114_TEMPORAL_STABILITY_AUDIT_READY | outputs/replay/p114_temporal_stability_audit_20260527.json |

---

## Evidence Summary from P112 / P113 / P114

### midfreq_fourier_mk_3bet

| Attribute | Value |
|---|---|
| Lottery type | POWER_LOTTO |
| P112 classification | PREDICTION_HELPFUL |
| P112 avg_hit_count | 1.027333 |
| P112 edge vs baseline | +0.0800 |
| P112 replay rows | 1500 |
| P113 action | WATCHLIST_QUEUE |
| P114 stability label | STABLE_POSITIVE |
| P114 decision | READY_FOR_OOS_MONITORING_DESIGN |
| P114 first-third edge | +0.0766 |
| P114 middle-third edge | +0.1026 |
| P114 last-third edge | +0.0606 |
| P114 rolling-100 edge | +0.0526 |
| P114 rolling-250 edge | +0.0566 |
| Positive thirds count | 3/3 |

All three chronological thirds and both rolling windows are positive. This is the strongest temporal stability profile across all 36 audited strategies.

### pp3_freqort_4bet

| Attribute | Value |
|---|---|
| Lottery type | POWER_LOTTO |
| P112 classification | PREDICTION_HELPFUL |
| P112 avg_hit_count | 1.002 |
| P112 edge vs baseline | +0.0546 |
| P112 replay rows | 1500 |
| P113 action | WATCHLIST_QUEUE |
| P114 stability label | MOSTLY_POSITIVE |
| P114 decision | READY_FOR_CONTROLLED_OBSERVATION_PLAN |
| P114 first-third edge | +0.0846 |
| P114 middle-third edge | +0.0946 |
| P114 last-third edge | -0.0154 |
| P114 rolling-100 edge | -0.0874 |
| P114 rolling-250 edge | -0.0714 |
| Positive thirds count | 2/3 |

The last chronological third is negative, and both rolling windows (100/250) are also negative. This indicates recent softness. Controlled observation before any promotion discussion is warranted.

---

## Hypergeometric Baseline

POWER_LOTTO baseline avg hit count (hypergeometric expected): **0.947368**  
(5 balls drawn from 38 pool; 5 predicted; expected overlap ≈ 5 × 5/38)

---

## OOS Monitoring Design

### 1. midfreq_fourier_mk_3bet

**OOS Status: DESIGN_READY**

#### Monitoring Horizon

| Parameter | Value |
|---|---|
| Minimum new POWER_LOTTO draws | 30 |
| Preferred new POWER_LOTTO draws | 50 |
| Promotion discussion minimum | 80 |

#### Rolling Windows

10 draws / 20 draws / 30 draws

#### Metrics to Track

| Metric | Description |
|---|---|
| avg_hit_count | Average number overlap per draw |
| edge_vs_hypergeometric_baseline | avg_hit_count − 0.947368 |
| positive_edge_rate_by_window | Fraction of rolling windows with positive edge |
| hit_count_distribution | Distribution of hit counts (0, 1, 2, 3, 4, 5) |
| draw_coverage | Draws observed since monitoring start |
| freshness_status | Whether source data is current |

#### PASS Criteria

- Minimum 30 new POWER_LOTTO draws completed
- edge_vs_baseline positive over the full OOS window
- Positive edge in at least 2 of 3 rolling windows (10 / 20 / 30)
- No freshness guard failure
- replay_rows unchanged except under explicitly authorized future apply
- Branch governance guard passes

#### WATCH Criteria

- Edge positive but unstable across rolling windows
- Positive edge in only 1 of 3 rolling windows
- Insufficient draw count (< 30 new draws) but direction positive
- Edge magnitude decreasing trend but still above zero

#### FAIL Criteria

- Negative edge over full OOS window
- Negative edge in at least 2 of 3 rolling windows
- Data freshness guard failure
- Any unauthorized DB mutation detected
- replay_rows changed without explicit authorization

#### Future Promotion Proposal Requirements

All of the following must hold before any promotion task may be opened:

1. Minimum 80 new POWER_LOTTO draws observed post-OOS monitoring start
2. PASS status sustained for at least 50 new draws
3. edge_vs_baseline positive over the full 80+ draw OOS window
4. Positive edge in at least 2 of 3 rolling windows (10 / 20 / 30)
5. Freshness guard passing throughout
6. Explicit governance authorization in a new numbered task (P117 or later)
7. source_unknown caveat resolved or explicitly accepted
8. P108 Special3 100-draw gate satisfied (37 more 3_STAR draws needed as of P116)
9. Branch governance guard passing at promotion-task commit

#### Demotion / Quarantine Triggers

- Negative edge over full OOS window at any evaluation checkpoint
- Negative edge in at least 2 of 3 rolling windows, sustained across 2+ evaluations
- Data freshness failure lasting 10+ draws
- Unauthorized DB mutation detected
- Stability label degrades to UNSTABLE or STABLE_NEGATIVE in future re-audit
- replay_rows changed without explicit future authorization

---

### 2. pp3_freqort_4bet

**OOS Status: CONTROLLED_OBSERVATION_READY**

#### Monitoring Horizon

| Parameter | Value |
|---|---|
| Minimum new POWER_LOTTO draws | 40 |
| Preferred new POWER_LOTTO draws | 60 |
| Promotion discussion minimum | 100 |

The higher draw requirement reflects the recent negative rolling windows and MOSTLY_POSITIVE (rather than STABLE_POSITIVE) stability label. More draws are needed to determine whether recent softness is transient or structural.

#### Rolling Windows

10 draws / 20 draws / 40 draws

#### Metrics to Track

| Metric | Description |
|---|---|
| avg_hit_count | Average number overlap per draw |
| edge_vs_hypergeometric_baseline | avg_hit_count − 0.947368 |
| positive_edge_rate_by_window | Fraction of rolling windows with positive edge |
| stability_label_change | Whether stability improves from MOSTLY_POSITIVE to STABLE_POSITIVE |
| draw_coverage | Draws observed since monitoring start |
| freshness_status | Whether source data is current |

#### PASS Criteria

- Minimum 40 new POWER_LOTTO draws completed
- edge_vs_baseline positive over the full OOS window
- Positive edge in at least 2 of 3 rolling windows (10 / 20 / 40)
- Stability label improves from MOSTLY_POSITIVE to STABLE_POSITIVE in a future re-audit
- No freshness guard failure
- replay_rows unchanged except under explicitly authorized future apply

#### WATCH Criteria

- Edge positive but mixed across rolling windows
- Stability remains MOSTLY_POSITIVE (no regression, no improvement)
- Positive edge over full window but only 1 of 3 rolling windows positive
- Insufficient draw count (< 40 new draws) but recent direction recovering

#### FAIL Criteria

- Negative edge over full OOS window
- Stability degrades to MIXED or UNSTABLE in future re-audit
- Negative edge in at least 2 of 3 rolling windows
- Data freshness guard failure
- Any unauthorized DB mutation detected
- replay_rows changed without explicit authorization

#### Future Promotion Proposal Requirements

All of the following must hold before any promotion task may be opened:

1. Minimum 100 new POWER_LOTTO draws observed post-OOS monitoring start
2. PASS status sustained for at least 60 new draws
3. edge_vs_baseline positive over the full 100+ draw OOS window
4. Stability label must improve to STABLE_POSITIVE in a future temporal re-audit
5. Positive edge in at least 2 of 3 rolling windows (10 / 20 / 40)
6. Freshness guard passing throughout
7. Explicit governance authorization in a new numbered task (P118 or later)
8. source_unknown caveat resolved or explicitly accepted
9. P108 Special3 100-draw gate satisfied (37 more 3_STAR draws needed as of P116)
10. Branch governance guard passing at promotion-task commit

#### Demotion / Quarantine Triggers

- Stability degrades to MIXED or UNSTABLE in future re-audit
- Negative edge over full OOS window
- Negative edge in at least 2 of 3 rolling windows, sustained across 2+ evaluations
- rolling-100-draw edge remains negative after 40 new draws
- Data freshness failure lasting 10+ draws
- Unauthorized DB mutation detected
- replay_rows changed without explicit future authorization

---

## Global Monitoring Invariants

These must hold at every future evaluation checkpoint:

1. replay_rows must remain 54462 unless a future apply is explicitly authorized in a separate numbered task.
2. No DB writes in the OOS monitoring design phase.
3. Freshness guard must pass before any evaluation checkpoint.
4. Branch governance guard must pass at every commit.
5. No lifecycle/champion/registry mutation without explicit future authorization in a new numbered task.
6. No strategy promotion without explicit future authorization.
7. No 4_STAR backtest until source_unknown caveat is resolved and explicitly authorized.
8. P108 Special3 re-evaluation blocked until 37 more 3_STAR draws complete.
9. P115 quarantine governance for fourier30_markov30_biglotto is a separate task.

---

## Limitations

- This design is read-only. No OOS draw data is available yet; design is based on historical replay rows only.
- hit_count measures number overlap only; prize-tier weighting not applied.
- Temporal stability assessed on historical replay rows only; OOS performance may differ from in-sample patterns.
- 4_STAR backtest remains unauthorized due to source_unknown caveat.
- Special3/P106/P108 evaluation excluded; blocked until 100 prospective draws.
- No live monitoring job is implemented by this task.
- Promotion discussion minimum thresholds are guidelines, not guarantees; all promotion requires explicit future authorization in a new numbered task.
- P115 quarantine governance for fourier30_markov30_biglotto is out of scope for P116.

---

## Forbidden-Staging Scan Summary

| Check | Result |
|---|---|
| DB files staged | DB_STAGE_CLEAN |
| lottery_history.json staged | CLEAN |
| .wal / .shm files staged | CLEAN |
| Non-whitelist files staged | CLEAN |

Staged files (exactly 4):
- `outputs/replay/p116_powerlotto_oos_monitoring_design_20260527.json`
- `docs/replay/p116_powerlotto_oos_monitoring_design_20260527.md`
- `tests/test_p116_powerlotto_oos_monitoring_design.py`
- `scripts/p116_powerlotto_oos_monitoring_design.py`

---

## Test Summary

| Test file | Status |
|---|---|
| tests/test_replay_lifecycle_drift_guard.py | PASS |
| tests/test_replay_branch_governance_guard.py | PASS |
| tests/test_p112_cross_lottery_prediction_helpfulness_audit.py | PASS |
| tests/test_p113_p112_action_decision_matrix.py | PASS |
| tests/test_p114_temporal_stability_audit.py | PASS |
| tests/test_p116_powerlotto_oos_monitoring_design.py | PASS (≥40 tests) |

---

## Guard Summary

| Guard | Status |
|---|---|
| replay_lifecycle_drift_guard --strict | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| replay_branch_governance_guard (pre-commit, P116 branch) | BRANCH_GOVERNANCE_PASS |
| replay_branch_governance_guard (post-merge, main) | BRANCH_GOVERNANCE_PASS |

---

## Explicit Holds

| Hold | Reason | Unblock Condition |
|---|---|---|
| P108 Special3 re-evaluation | Only 63/100 prospective draws; 37 more needed | 37 more 3_STAR draws |
| 4_STAR backtest | source_unknown caveat active | Source verification + explicit authorization |
| Strategy promotion | No promotion authorized in P116 | Separate future numbered task with explicit authorization |
| P115 quarantine governance | Separate scope for fourier30_markov30_biglotto | Separate P115 task |

---

## Final Classification

**P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY**

---

## Next Recommended Task

| Priority | Task | Scope |
|---|---|---|
| 1 | P115 | Quarantine governance for fourier30_markov30_biglotto (BIG_LOTTO, STABLE_NEGATIVE) |
| 2 | P117 | OOS monitoring execution checkpoint (after minimum new POWER_LOTTO draws become available) |
| 3 | P108 | Special3 100-draw re-evaluation (after 37 more 3_STAR draws) |

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
| P114 | Temporal stability audit — READY | 3ffae64 |
| **P116** | **POWER_LOTTO OOS monitoring design — READY** | *(this task)* |
