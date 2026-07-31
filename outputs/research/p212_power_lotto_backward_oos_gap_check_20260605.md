# P212 POWER_LOTTO Backward-OOS Gap Check

**Date:** 2026-06-05
**Classification:** `P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_HISTORICAL_ARTIFACT`
**Task Type:** Type C (additive read-only gap check script) under P240D governance simplification rules
**Status:** Read-only diagnostic only — no DB write, no registry mutation, no production change
**Authorization:** Authorize P212 POWER_LOTTO backward-OOS for fourier30_markov30_2bet and zonal_entropy_2bet (read-only, no DB write)

---

## 1. Scope and Non-Goals

### In Scope
- Backward-OOS gap check for exactly two P211R untested POWER_LOTTO strategies
- P231B boundary method (draws < 101000002)
- Temporal split proxy when backward-OOS is unavailable
- P242/P244C schema discipline

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| DB write | Not authorized |
| Registry mutation | Not authorized |
| Strategy promotion | Not authorized |
| Production / recommendation change | Not authorized |
| Betting advice or wagering recommendation | Never authorized |
| Other lotteries or strategies beyond the two target IDs | Not in scope |

---

## 2. Authorization

This gap check was authorized by: `"Authorize P212 POWER_LOTTO backward-OOS for fourier30_markov30_2bet and zonal_entropy_2bet (read-only, no DB write)"`

P211R identified these two strategies as IS-window Bonferroni-significant without prior dedicated backward-OOS evidence. P211S flagged them as the only candidates worth a follow-up gap check.

---

## 3. Source Evidence

| Source | Finding |
|---|---|
| P211R w150 `fourier30_markov30_2bet` | mean=1.0667 vs baseline 0.9825; IS-window significant |
| P211R w150 `zonal_entropy_2bet` | mean=1.0333 vs baseline 0.9825; IS-window significant |
| P231B backward-OOS boundary | 101000002 (pre-2012 historical draws) |
| P231B result | `midfreq_fourier_mk_3bet` backward-OOS p=0.3018 (NULL) |
| P230C result | `midfreq_fourier_2bet` backward-OOS mean below baseline (REJECTED) |

---

## 4. Backward-OOS Window and Method

| Parameter | Value |
|---|---|
| Boundary (P231B method) | Draw < 101000002 |
| Backward draws available | **0 for both strategies** |
| Reason | Both strategies' replay history starts at 101000002 |
| Fallback method | Temporal split: early 500 draws (oldest) vs late draws (most recent) |
| Baseline | All-history bet_index=1 mean = 0.9825 |
| Family K | 2 (Bonferroni correction) |

**Key finding: No pre-boundary draws exist.** Unlike `midfreq_fourier_mk_3bet` (which had 382 draws before 101000002 for P231B), these two strategies have no historical data before the current replay window. A true P231B-style backward-OOS cannot be performed.

The temporal split uses the **first 500 draws** (earliest chronologically) as an OOS approximation. If early performance is below the all-history baseline, this is consistent with the IS-window significance being concentrated in recent draws — the historical artifact pattern.

---

## 5. Per-Strategy Results

| Strategy | Backward Draws | Early N | Early Mean | Early Δ | p_early | p_corr | Early>Base | Late Mean | Classification |
|---|---|---|---|---|---|---|---|---|---|
| fourier30_markov30_2bet | 0 | 500 | 0.9420 | -0.0405 | 1.0000 | 1.0000 | no | 0.9760 | P212_TEMPORAL_SPLIT_EARLY_BELOW_BASELINE_HISTORICAL_ARTIFACT |
| zonal_entropy_2bet | 0 | 500 | 0.9100 | -0.0725 | 1.0000 | 1.0000 | no | 0.9640 | P212_TEMPORAL_SPLIT_EARLY_BELOW_BASELINE_HISTORICAL_ARTIFACT |

All-history baseline (bet_index=1): **0.9825**

---

## 6. Multiple-Testing Summary

| Metric | Value |
|---|---|
| Family K | 2 |
| Bonferroni threshold | 0.0250 |
| Corrected-significant strategies | 0 (early period) |
| Strategies with early_mean < baseline | 2 / 2 |

---

## 7. Robustness Summary

Both strategies show **early-period performance BELOW the all-history baseline** (0.9825):
- `fourier30_markov30_2bet` early mean = 0.9420 (delta -0.0405)
- `zonal_entropy_2bet` early mean = 0.9100 (delta -0.0725)

The IS-window significance from P211R (w150 and w500) is driven by **recent draws only** — not consistent performance across the full replay history. This is the same temporal pattern observed in P230C (DAILY_539 REJECTED) and consistent with P231B (POWER_LOTTO NULL).

---

## 8. Feature-Bottleneck Table

| Bottleneck | Description |
|---|---|
| `no_pre_boundary_draws_available_for_backward_oos` | assigned |
| `both_strategies_start_at_draw_101000002` | assigned |
| `temporal_split_proxy_used_as_oos_approximation` | assigned |
| `early_period_below_all_history_baseline_for_both_strategies` | assigned |
| `is_window_significance_concentrated_in_recent_draws_consistent_with_historical_artifact` | assigned |

---

## 9. Classification and Confidence Language

**Overall Classification:** `P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_HISTORICAL_ARTIFACT`

Both strategies' IS-window significance is a recency artifact. Early performance is below the all-history baseline. No backward-OOS data is available to provide independent historical confirmation. Consistent with the historical artifact pattern established by P231B and P230C.

**Confidence language (overall):** Historical IS-window evidence only. Temporal split proxy shows early period below baseline for both strategies. No independent OOS confirmation. No higher winning probability claim. Not a wagering recommendation. No strategy is authorized for promotion.

---

## 10. Allowed Next Actions

- observation_only
- future_backward_oos_only_if_pre_boundary_draws_are_ever_added_to_replay_table
- passive_monitoring_until_new_draws_accumulate
- return_to_waiting_for_user_authorization

---

## 11. Forbidden Next Actions

- strategy_promotion
- production_change
- registry_write
- db_write
- betting_advice
- wagering_recommendation
- claim_deployable_edge

---

## 12. No-Claim Attestation

This gap check produces no claim about lottery number predictability, higher winning probability, or wagering recommendations. Both strategies have no pre-boundary draws available for P231B-style backward-OOS. The temporal split proxy confirms early-period performance is below the all-history baseline, consistent with the historical artifact pattern seen in P231B and P230C. All safety booleans are False. No strategy is authorized for promotion.

All safety booleans:
- `db_write_authorized = False`
- `registry_write_authorized = False`
- `production_authorized = False`
- `betting_advice = False`
- `strategy_authorized = False`
- `monitoring_authorized = False`

---

## 13. Type C Same-PR Closeout Rationale

This task is **Type C** under P240D: additive script and artifact files only, no existing production paths modified, no DB write, governance changes ≤4 files. **No separate P212 closeout PR is required.**

---

## 14. Recommended Next Options

| Option | Authorization Phrase |
|---|---|
| Remain HOLD | *(none needed)* |
| Passive monitoring (≥300 new DAILY_539 live draws) | *(wait; no task needed)* |
| New hypothesis from scratch | `"Authorize P213 new hypothesis [description]"` |
