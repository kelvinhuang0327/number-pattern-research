# P267C — M3+ Success-Metric Strategy Revalidation

Generated: 2026-06-10T13:26:34.921497  |  DB access: read-only (mode=ro)

## Pre-Registration (declared before results)

```json
{
  "registry_id": "HR-P267B-M3PLUS-REVAL-001",
  "registry_path": "lottery_api/data/hypothesis_registry.jsonl",
  "registered_entries": [
    {
      "hypothesis_id": "DA_p267c_m3plus_reval_primary_20260610132509",
      "name": "p267c_m3plus_reval_primary",
      "lottery": "DAILY_539",
      "status": "REGISTERED"
    },
    {
      "hypothesis_id": "BI_p267c_m3plus_reval_primary_20260610132509",
      "name": "p267c_m3plus_reval_primary",
      "lottery": "BIG_LOTTO",
      "status": "REGISTERED"
    },
    {
      "hypothesis_id": "PO_p267c_m3plus_reval_primary_20260610132509",
      "name": "p267c_m3plus_reval_primary",
      "lottery": "POWER_LOTTO",
      "status": "REGISTERED"
    },
    {
      "hypothesis_id": "DA_p267c_h6_m3plus_decomposition_conditional_20260610132509",
      "name": "p267c_h6_m3plus_decomposition_conditional",
      "lottery": "DAILY_539",
      "status": "REGISTERED"
    }
  ],
  "primary_hypothesis": "H-P267B-1: at least one replay-backed cell's draw-level M3+ rate differs from its strategy-specific conditional fair-draw baseline (two-sided, full-family corrected); expected outcome NULL",
  "secondary_hypotheses": [
    "H-P267B-2: descriptive excess ranking (observed - MC baseline), no promotion claims",
    "H-P267B-3: same-lottery same-N McNemar vs unique ONLINE incumbent (exploratory)",
    "H-P267B-4: H6 M2-only vs M3+ decomposition, CONDITIONAL on reproducible evidence"
  ],
  "success_metric": "draw_success = any bet_index with hit_count >= 3; denominator = distinct target_draw",
  "special_hit_excluded": true,
  "family_m": 36,
  "bonferroni_alpha": 0.001388888888888889,
  "bh_fdr_q": 0.1,
  "primary_endpoint": "most-recent 1500 distinct target_draw",
  "stability_windows_sign_check_only": [
    150,
    500
  ],
  "null_design": "per-draw Bernoulli(p_i) MC (L96); label-shuffle forbidden",
  "circular_match_guard": "predict-vs-actual only (L132/L139); historical-pool max-hit never computed",
  "seed": 42,
  "mc_baseline_M": 10000,
  "null_iterations_T": 10000,
  "feasibility_look_disclosure": "P267B design round inspected cell-level aggregate M3+ rates; mitigation: family = exhaustive 36-cell universe (no observation-driven selection), two-sided tests, full-family correction, and this run recomputes everything from raw rows with fixed seed.",
  "power_statement": "n=1500, p0=1.0% (DAILY_539 1-bet): Bonferroni-corrected minimum detectable excess ~ +0.98pp at 80% power; short windows are sign-checks only because they are structurally underpowered."
}
```

## Data-Quality Gates

```json
{
  "total_replay_rows": 94924,
  "expected_replay_rows": 94924,
  "causality_violations": 0,
  "non_predicted_rows": 0,
  "dry_run_rows": 0,
  "null_field_rows": 0
}
```

## 1-Bet Baseline Sanity (exact vs MC)

```json
{
  "DAILY_539": {
    "exact": 0.010041,
    "mc": 0.010067,
    "abs_diff_pp": 0.0026,
    "tolerance_pp": 0.05,
    "pass": true
  },
  "BIG_LOTTO": {
    "exact": 0.018638,
    "mc": 0.018342,
    "abs_diff_pp": 0.0296,
    "tolerance_pp": 0.05,
    "pass": true
  },
  "POWER_LOTTO": {
    "exact": 0.038698,
    "mc": 0.038788,
    "abs_diff_pp": 0.009,
    "tolerance_pp": 0.05,
    "pass": true
  }
}
```

## Results (36 replay-backed cells)

| Lottery | Strategy | N | Bets | Observed M3+ | MC baseline | Excess (pp) | p (emp) | p (exact PB) | Bonf | BH | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DAILY_539 | daily539_f4cold_5bet | 1500 | 5 | 6.33% | 5.01% | +1.32 | 0.0308 | 0.0267 | no | no | — |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 1500 | 3 | 11.13% | 9.65% | +1.48 | 0.0634 | 0.0618 | no | no | — |
| POWER_LOTTO | power_fourier_rhythm_2bet | 1500 | 2 | 9.07% | 7.73% | +1.33 | 0.0656 | 0.0638 | no | no | — |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 1500 | 4 | 8.67% | 7.44% | +1.23 | 0.0786 | 0.0829 | no | no | — |
| POWER_LOTTO | midfreq_fourier_2bet | 1500 | 1 | 4.67% | 3.87% | +0.80 | 0.1330 | 0.1315 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| POWER_LOTTO | fourier_rhythm_3bet | 1500 | 3 | 12.07% | 10.87% | +1.20 | 0.1432 | 0.1509 | no | no | — |
| BIG_LOTTO | biglotto_triple_strike | 1500 | 1 | 2.40% | 1.86% | +0.54 | 0.1470 | 0.1578 | no | no | — |
| BIG_LOTTO | biglotto_echo_aware_3bet | 1500 | 3 | 6.47% | 5.58% | +0.88 | 0.1520 | 0.1554 | no | no | — |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 1500 | 1 | 2.40% | 1.86% | +0.54 | 0.1570 | 0.1578 | no | no | — |
| BIG_LOTTO | ts3_regime_3bet | 1500 | 1 | 2.40% | 1.86% | +0.54 | 0.1578 | 0.1578 | no | no | BET_AVAILABILITY_MISMATCH(name~3,stored=1) |
| BIG_LOTTO | biglotto_deviation_2bet | 1500 | 1 | 2.40% | 1.86% | +0.54 | 0.1590 | 0.1578 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| BIG_LOTTO | fourier30_markov30_biglotto | 1500 | 1 | 1.40% | 1.86% | -0.46 | 0.1984 | 0.2105 | no | no | — |
| DAILY_539 | acb_markov_midfreq | 1500 | 1 | 1.33% | 1.00% | +0.33 | 0.2454 | 0.2542 | no | no | — |
| BIG_LOTTO | coldpool15_biglotto | 1500 | 1 | 1.47% | 1.86% | -0.40 | 0.2952 | 0.2955 | no | no | — |
| BIG_LOTTO | cold_complement_biglotto | 1500 | 1 | 1.47% | 1.86% | -0.40 | 0.2964 | 0.2955 | no | no | — |
| POWER_LOTTO | pp3_freqort_4bet | 1500 | 4 | 12.13% | 11.27% | +0.87 | 0.3074 | 0.3075 | no | no | — |
| DAILY_539 | acb_markov_midfreq_3bet | 1500 | 3 | 3.47% | 2.99% | +0.47 | 0.3240 | 0.3175 | no | no | — |
| POWER_LOTTO | power_orthogonal_5bet | 1500 | 5 | 12.27% | 11.46% | +0.80 | 0.3556 | 0.3483 | no | no | — |
| DAILY_539 | zone_gap_3bet_539 | 1500 | 1 | 0.73% | 1.00% | -0.27 | 0.3610 | 0.3588 | no | no | BET_AVAILABILITY_MISMATCH(name~3,stored=1) |
| DAILY_539 | midfreq_acb_2bet | 1500 | 1 | 1.27% | 1.00% | +0.26 | 0.3622 | 0.3676 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| DAILY_539 | midfreq_fourier_2bet | 1500 | 1 | 1.27% | 1.00% | +0.26 | 0.3752 | 0.3676 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| BIG_LOTTO | markov_single_biglotto | 1500 | 1 | 1.53% | 1.86% | -0.33 | 0.3944 | 0.3993 | no | no | — |
| BIG_LOTTO | markov_2bet_biglotto | 1500 | 1 | 1.53% | 1.86% | -0.33 | 0.4078 | 0.3993 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| DAILY_539 | daily539_f4cold_3bet | 1500 | 3 | 3.40% | 3.01% | +0.39 | 0.4172 | 0.4157 | no | no | — |
| POWER_LOTTO | power_precision_3bet | 1500 | 3 | 11.87% | 11.27% | +0.59 | 0.4824 | 0.4893 | no | no | — |
| DAILY_539 | markov_1bet_539 | 1500 | 1 | 1.13% | 1.00% | +0.13 | 0.6749 | 0.6826 | no | no | — |
| DAILY_539 | daily539_markov_cold | 1500 | 1 | 1.13% | 1.00% | +0.13 | 0.6961 | 0.6826 | no | no | — |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 1500 | 1 | 0.87% | 1.00% | -0.14 | 0.7071 | 0.7128 | no | no | BET_AVAILABILITY_MISMATCH(name~3,stored=1) |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 1500 | 1 | 0.87% | 1.00% | -0.14 | 0.7137 | 0.7128 | no | no | BET_AVAILABILITY_MISMATCH(name~3,stored=1) |
| DAILY_539 | daily539_f4cold | 1500 | 1 | 0.87% | 1.00% | -0.14 | 0.7185 | 0.7128 | no | no | — |
| POWER_LOTTO | cold_complement_2bet | 1500 | 1 | 3.67% | 3.87% | -0.20 | 0.7229 | 0.7470 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| POWER_LOTTO | fourier30_markov30_2bet | 1500 | 1 | 4.07% | 3.87% | +0.20 | 0.7279 | 0.7288 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| POWER_LOTTO | zonal_entropy_2bet | 1500 | 1 | 3.67% | 3.87% | -0.20 | 0.7567 | 0.7470 | no | no | BET_AVAILABILITY_MISMATCH(name~2,stored=1) |
| DAILY_539 | 539_3bet_orthogonal | 1500 | 1 | 1.07% | 1.00% | +0.06 | 0.8547 | 0.8764 | no | no | BET_AVAILABILITY_MISMATCH(name~3,stored=1) |
| DAILY_539 | acb_1bet | 1500 | 1 | 1.07% | 1.00% | +0.06 | 0.8755 | 0.8764 | no | no | — |
| DAILY_539 | acb_single_539 | 1500 | 1 | 1.07% | 1.00% | +0.06 | 0.8821 | 0.8764 | no | no | — |

## McNemar (secondary, exploratory)

```json
[
  {
    "group": "BIG_LOTTO/N=1",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=3)"
  },
  {
    "group": "BIG_LOTTO/N=3",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "BIG_LOTTO/N=4",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "DAILY_539/N=1",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=2)"
  },
  {
    "group": "DAILY_539/N=3",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "DAILY_539/N=5",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "POWER_LOTTO/N=1",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "POWER_LOTTO/N=2",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "POWER_LOTTO/N=3",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=2)"
  },
  {
    "group": "POWER_LOTTO/N=4",
    "status": "NOT_RUN",
    "reason": "non-unique ONLINE incumbent (count=0)"
  },
  {
    "group": "POWER_LOTTO/N=5",
    "status": "NOT_RUN",
    "reason": "no challenger cell in group"
  }
]
```

## H6 Evidence Verification

```json
{
  "status": "H6_EVIDENCE_NOT_REPRODUCIBLE",
  "checks": {
    "replay_rows": 0,
    "prediction_runs_rows": 0,
    "shadow_experiments_rows": 0,
    "docs/H6_PRODUCTION_GO_LIVE_SUMMARY.md": false,
    "strategies/H6_gate_mk20_ew85_spec.md": false,
    "lottery_api/engine/h6_alert_engine.py": false
  },
  "note": "git history contains only a 7-line spec, strategy-state JSON and a leakage transcript (commits 515f9a4/4356b95/79e15ec); no per-draw OOS records exist on main or in history; wiki summary claims (+4.00pp/3000p) are therefore unverifiable and are NOT used in any computation here (CLAUDE.md traceability rule: non-reproducible results are invalid)."
}
```

## NO_DATA / Orphan Cells

- NO_DATA (registered, no replay rows): ['BIG_LOTTO:biglotto_ts3_acb_4bet', 'BIG_LOTTO:biglotto_ts3_markov_freq_5bet', 'DAILY_539:p1_deviation_2bet_539', 'POWER_LOTTO:h6_gate_mk20_ew85', 'POWER_LOTTO:power_shlc_midfreq']
- Orphans (rows, not registered): ['POWER_LOTTO:midfreq_fourier_2bet', 'POWER_LOTTO:midfreq_fourier_mk_3bet', 'POWER_LOTTO:pp3_freqort_4bet']

## Summary

```json
{
  "bonferroni_significant_cells": 0,
  "bh_fdr_flagged_cells": 0,
  "candidate_cells": []
}
```

## Disclaimers

- 本報告不構成投注建議，不保證任何中獎結果。
- M3+ 成功率為歷史 walk-forward replay 的描述統計，不代表未來表現。
- 任何通過校正的訊號僅為 CANDIDATE_SIGNAL，必須經人類審查（L144），不得自動晉級。
- special_hit 一律不計入 M3+（P265A SSOT contract）。
- This report does not improve win rate and does not authorize betting action.

## Final Classification

`P267C_M3PLUS_REVALIDATION_COMPLETE_NO_VALIDATED_M3_EDGE`
