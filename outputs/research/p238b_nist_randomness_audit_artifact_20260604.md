# P238B - NIST Randomness-Audit Artifact-Only Build

**Task ID:** P238B
**Type:** diagnostics-only artifact build; read-only DB mode
**Generated At:** 2026-06-04T09:58:57.569543+00:00
**Final Classification:** `P238B_NIST_RANDOMNESS_AUDIT_ARTIFACT_ONLY_BUILD_COMPLETE`
**Audit Classification:** `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`

## Executive Summary

This artifact is diagnostics-only.
This artifact does not predict lottery numbers.
This artifact does not improve win rate.
This artifact is not betting advice.
RED alert authorizes human review only.
NULL / GREEN is success.

Overall alert level: **YELLOW**. Final recommendation: **HOLD**.

## Authorization And Non-Scope

- Authorized: P238B artifact-only implementation using read-only DB mode.
- Not authorized: DB write, registry mutation, production/recommendation change, monitoring job, scheduler, controlled_apply, strategy adapter, strategy promotion, P211 restart, betting advice.
- `strategy_prediction_replays` is not used as the randomness-test unit.

## Data Snapshot

- Repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Branch: `codex/p238b-nist-randomness-audit-artifact-build`
- HEAD: `2b38b85a6e6ed79a0c96fdc273cc030ce8d2f403`
- DB path: `lottery_api/data/lottery_v2.db`
- DB open mode: `read-only`
- Replay rows before/after: `94924` / `94924`
- Replay rows used as unit: `False`

## Draw-Level Unit Declaration

The statistical unit is one chronological draw observation: `(lottery_type, draw, date, zone, number_unit)`. Multi-bet replay rows, strategy IDs, and bet indexes are not audit units.

## Pre-Registration

| Field | Value |
|---|---|
| ID | `P238B_NIST_RANDOMNESS_AUDIT_ACTIVE_UNIVERSE_20260604` |
| Active lotteries | `BIG_LOTTO, DAILY_539, POWER_LOTTO, 3_STAR, 4_STAR` |
| Windows | `150, 500, 1000, all-history` |
| Primary correction | `bonferroni` |
| Family size | `32` |

## Data Inventory

| Lottery | Draw Rows | Included | Min Draw | Max Draw | Min Date | Max Date |
|---|---:|---|---:|---:|---|---|
| 38_LOTTO | 1774 | False | 100000001 | 99000104 | 2007-01-01 | 2023-12-28 |
| 39_LOTTO | 4890 | False | 100000001 | 99000085 | 2010-09-06 | 2026-04-30 |
| 3_STAR | 4179 | True | 100000002 | 99000261 | 2007/01/02 | 2026/01/28 |
| 49_LOTTO | 2130 | False | 100000001 | 99000105 | 2007-01-02 | 2026-04-28 |
| 4_STAR | 2922 | True | 100000003 | 99000261 | 2007-01-02 | 2026-04-27 |
| BIG_LOTTO | 22238 | True | 100000001 | 99000105 | 2007/01/02 | 2026/06/02 |
| BIG_LOTTO_BONUS | 11941 | False | 113000011-01 | 115000032-99 | 2024-02-06 | 2026-03-03 |
| DAILY_539 | 5879 | True | 100000001 | 99000261 | 2007/01/01 | 2026/06/03 |
| DOUBLE_WIN | 1782 | False | 107000001 | 112000312 | 2018-04-23 | 2023-12-30 |
| LOTTO_6_38 | 111 | False | 96000001 | 97000006 | 2007-01-01 | 2008-01-21 |
| POWER_LOTTO | 1916 | True | 100000001 | 99000104 | 2008/01/24 | 2026/06/01 |

## Data-Quality Checks

- Draw table exists: `True`
- Duplicate `(lottery_type, draw)` keys: `0`
- Invalid number rows: `0`
- Invalid special rows: `0`
- Position-aware status: `POSITION_DATA_UNAVAILABLE` for `BIG_LOTTO, DAILY_539, POWER_LOTTO, 3_STAR, 4_STAR`

## Test Family Results

| Lottery | Zone | Window | Family | N Draws | Raw p | Bonferroni p | Alert |
|---|---|---|---|---:|---:|---:|---|
| BIG_LOTTO | first-zone | all-history | ball_frequency_uniformity | 22238 | 0.000e+00 | 0.000e+00 | YELLOW |
| BIG_LOTTO | first-zone | latest-150 | ball_frequency_uniformity | 150 | 0.4558 | 1.0000 | GREEN |
| BIG_LOTTO | first-zone | latest-500 | ball_frequency_uniformity | 500 | 0.8399 | 1.0000 | GREEN |
| BIG_LOTTO | first-zone | latest-1000 | ball_frequency_uniformity | 1000 | 0.8038 | 1.0000 | GREEN |
| BIG_LOTTO | special-zone | all-history | special_zone_uniformity | 3138 | 0.000e+00 | 0.000e+00 | YELLOW |
| BIG_LOTTO | first-zone | all-history | lag_serial_overlap | 22238 | 0.000e+00 | 0.000e+00 | YELLOW |
| BIG_LOTTO | first-zone | all-history | gap_interarrival | 22238 | 0.8656 | 1.0000 | GREEN |
| BIG_LOTTO | position-aware | all-history | position_aware_availability | 22238 | N/A | N/A | GREEN |
| DAILY_539 | first-zone | all-history | ball_frequency_uniformity | 5879 | 0.6889 | 1.0000 | GREEN |
| DAILY_539 | first-zone | latest-150 | ball_frequency_uniformity | 150 | 0.6144 | 1.0000 | GREEN |
| DAILY_539 | first-zone | latest-500 | ball_frequency_uniformity | 500 | 0.4655 | 1.0000 | GREEN |
| DAILY_539 | first-zone | latest-1000 | ball_frequency_uniformity | 1000 | 0.8796 | 1.0000 | GREEN |
| DAILY_539 | first-zone | all-history | lag_serial_overlap | 5879 | 0.6180 | 1.0000 | GREEN |
| DAILY_539 | first-zone | all-history | gap_interarrival | 5879 | 0.8703 | 1.0000 | GREEN |
| DAILY_539 | position-aware | all-history | position_aware_availability | 5879 | N/A | N/A | GREEN |
| POWER_LOTTO | first-zone | all-history | ball_frequency_uniformity | 1916 | 0.6399 | 1.0000 | GREEN |
| POWER_LOTTO | first-zone | latest-150 | ball_frequency_uniformity | 150 | 0.6639 | 1.0000 | GREEN |
| POWER_LOTTO | first-zone | latest-500 | ball_frequency_uniformity | 500 | 0.7519 | 1.0000 | GREEN |
| POWER_LOTTO | first-zone | latest-1000 | ball_frequency_uniformity | 1000 | 0.8216 | 1.0000 | GREEN |
| POWER_LOTTO | special-zone | all-history | special_zone_uniformity | 1916 | 0.2165 | 1.0000 | GREEN |
| POWER_LOTTO | first-zone | all-history | lag_serial_overlap | 1916 | 0.4982 | 1.0000 | GREEN |
| POWER_LOTTO | first-zone | all-history | gap_interarrival | 1916 | 0.6315 | 1.0000 | GREEN |
| POWER_LOTTO | position-aware | all-history | position_aware_availability | 1916 | N/A | N/A | GREEN |
| 3_STAR | first-zone | all-history | ball_frequency_uniformity | 4179 | 0.9937 | 1.0000 | GREEN |
| 3_STAR | first-zone | latest-150 | ball_frequency_uniformity | 150 | 0.8055 | 1.0000 | GREEN |
| 3_STAR | first-zone | latest-500 | ball_frequency_uniformity | 500 | 0.2029 | 1.0000 | GREEN |
| 3_STAR | first-zone | latest-1000 | ball_frequency_uniformity | 1000 | 0.9137 | 1.0000 | GREEN |
| 3_STAR | first-zone | all-history | lag_serial_overlap | 4179 | 0.4726 | 1.0000 | GREEN |
| 3_STAR | first-zone | all-history | gap_interarrival | 4179 | 0.9727 | 1.0000 | GREEN |
| 3_STAR | position-aware | all-history | position_aware_availability | 4179 | N/A | N/A | GREEN |
| 4_STAR | first-zone | all-history | ball_frequency_uniformity | 2922 | 0.8173 | 1.0000 | GREEN |
| 4_STAR | first-zone | latest-150 | ball_frequency_uniformity | 150 | 0.9318 | 1.0000 | GREEN |
| 4_STAR | first-zone | latest-500 | ball_frequency_uniformity | 500 | 0.9868 | 1.0000 | GREEN |
| 4_STAR | first-zone | latest-1000 | ball_frequency_uniformity | 1000 | 0.9594 | 1.0000 | GREEN |
| 4_STAR | first-zone | all-history | lag_serial_overlap | 2922 | 0.0639 | 1.0000 | GREEN |
| 4_STAR | first-zone | all-history | gap_interarrival | 2922 | 0.9049 | 1.0000 | GREEN |
| 4_STAR | position-aware | all-history | position_aware_availability | 2922 | N/A | N/A | GREEN |

## Multiple-Testing Correction Summary

- Primary correction: Bonferroni across `32` p-valued diagnostics.
- BH-FDR values are report-only and do not authorize escalation.
- Historical anomalies are capped at YELLOW observation-only; ORANGE/RED require independent future confirmation.

## Alert Taxonomy Results

- GREEN: `34`
- YELLOW: `3`
- ORANGE: `0`
- RED: `0`
- Overall: `YELLOW`
- RED does not authorize strategy, production, registry, recommendation, monitoring, DB write, or betting action.
- This historical artifact cannot emit ORANGE/RED escalation without a future confirmation task.

## Limitations And False-Positive Risks

- The audit is a multiple-testing surface; corrected p-values are required.
- Chi-square and normal p-values are approximations intended for governance diagnostics.
- Stored numbers are sorted sets, so position-aware tests are skipped.
- A non-GREEN alert is a prompt for human diagnostic review only, not a prediction claim.

## Governance Recommendation

Recommendation: **HOLD**. Do not start strategy work, production changes, registry changes, monitoring jobs, DB writes, or betting actions from this artifact.

## Required Completion Check

1. Artifact generated in read-only DB mode.
2. Markdown and JSON artifacts emitted under `outputs/research/`.
3. DB rows unchanged.
4. No registry / production / recommendation / monitoring / strategy changes authorized.

Final Classification: `P238B_NIST_RANDOMNESS_AUDIT_ARTIFACT_ONLY_BUILD_COMPLETE`
