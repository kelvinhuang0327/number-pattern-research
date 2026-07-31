# P2 Full-Catalog Visibility Plan — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Generated**: 2026-05-20  
**Script**: `scripts/p2_full_catalog_visibility_plan.py`  
**Output JSON**: `outputs/replay/p2_full_catalog_visibility_plan_20260520.json`  
**Safety**: zero DB writes · zero replay rows generated · zero strategy execution

---

## Universe Summary

| Metric | Value |
|--------|-------|
| Total strategies in universe | 59 |
| Runtime registry strategies | 18 |
| Artifact-only (not registered) | 41 |
| Production replay rows (unchanged) | 460 |

---

## Four-State Visibility Classification

| Visibility State | Count | Definition |
|-----------------|-------|------------|
| **ROW_BACKED** | 6 | Has actual rows in `strategy_prediction_replays` |
| **RECONSTRUCTIBLE** | 5 | Has `prediction_items` rows in DB; can generate replay rows without re-running strategy logic |
| **NO_DATA** | 7 | In registry; no replay rows and no `prediction_items` in DB |
| **ARTIFACT_ONLY** | 41 | Not in runtime registry; exists only as artifact files (e.g., `rejected/*.json`) |

---

## ROW_BACKED Strategies (6)

All entries have actual rows in `strategy_prediction_replays`. No action needed.

| Strategy ID | Lottery | Replay Rows |
|-------------|---------|-------------|
| biglotto_deviation_2bet | BIG_LOTTO | 70 |
| biglotto_triple_strike | BIG_LOTTO | 70 |
| daily539_f4cold | DAILY_539 | 90 |
| daily539_markov_cold | DAILY_539 | 90 |
| power_orthogonal_5bet | POWER_LOTTO | 70 |
| power_precision_3bet | POWER_LOTTO | 70 |

---

## RECONSTRUCTIBLE Strategies (5)

Have `prediction_items` rows. Replay rows can be inserted from DB without re-running
any strategy. All are P7 candidates (2 ONLINE / 3 RETIRED).

| Strategy ID | Lottery | Lifecycle | Prediction Items | P7 Status |
|-------------|---------|-----------|-----------------|-----------|
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | 12+ | PLAN_INSERT (12 draws) |
| ts3_regime_3bet | BIG_LOTTO | ONLINE | 16+ | PLAN_INSERT (16 draws) |
| acb_1bet | DAILY_539 | RETIRED | 36 | PLAN_MANUAL_REVIEW_REQUIRED |
| acb_markov_midfreq_3bet | DAILY_539 | RETIRED | 99 | PLAN_MANUAL_REVIEW_REQUIRED |
| midfreq_acb_2bet | DAILY_539 | RETIRED | 65 | PLAN_MANUAL_REVIEW_REQUIRED |

**ONLINE (2)**: `fourier_rhythm_3bet` and `ts3_regime_3bet` — P7 apply gate hardened
and rehearsed. Awaiting CEO authorization phrase `YES apply P7 controlled replay rows`.

**RETIRED (3)**: Require human review before P7 INCLUDE_RETIRED_WITH_WARNING apply.
93 draws deferred.

---

## NO_DATA Strategies (7)

In runtime registry but have neither replay rows nor `prediction_items` in DB.
Cannot be reconstructed without re-running strategy logic (not permitted) or external data.

| Strategy ID | Lottery | Lifecycle | Reason |
|-------------|---------|-----------|--------|
| biglotto_ts3_acb_4bet | BIG_LOTTO | REJECTED | No prediction_items; governance rejected |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | REJECTED | No prediction_items; governance rejected |
| power_shlc_midfreq | POWER_LOTTO | REJECTED | No prediction_items; governance rejected |
| p1_deviation_2bet_539 | DAILY_539 | REJECTED | No prediction_items; governance rejected |
| acb_markov_midfreq | DAILY_539 | RETIRED | 0 prediction_items |
| midfreq_fourier_2bet | DAILY_539 | RETIRED | 0 prediction_items |
| h6_gate_mk20_ew85 | POWER_LOTTO | OBSERVATION | 0 prediction_items (shadow eval only) |

**Note**: NO_DATA ≠ ARTIFACT_ONLY. These strategies ARE in the runtime registry; they
simply have no source data in the DB to reconstruct from.

---

## ARTIFACT_ONLY Strategies (41)

Not in the runtime registry. Exist only as artifact files (primarily `rejected/*.json`).
Governance review required before any could be considered for registration.

All 41 entries are sourced from `outputs/replay/p1_catalog_visibility_plan_20260519.json`
`artifact_candidates_extra`. See that file for full list.

Classification: `lifecycle_state=NOT_REGISTERED`, `visibility_state=ARTIFACT_ONLY`,
`dry_run_only=True`, `can_generate_replay_rows=False`.

---

## Safety Confirmation

- ✅ **Zero DB writes** — DB opened with `PRAGMA query_only = ON`
- ✅ **Zero replay rows generated** — no INSERT executed
- ✅ **Zero draw imports** — no external data fetched
- ✅ **Zero strategy execution** — no predict_func called
- ✅ **Production rows unchanged** — `strategy_prediction_replays` = 460
- ✅ **All entries dry_run_only=True** — plan is advisory only

---

## Next Steps (Deferred, Requires Authorization)

| Step | Scope | Authorization Needed |
|------|-------|---------------------|
| P7 ONLINE apply | 28 rows (fourier_rhythm_3bet + ts3_regime_3bet) | `YES apply P7 controlled replay rows` |
| P7 RETIRED review | 93 rows (acb_1bet + acb_markov_midfreq_3bet + midfreq_acb_2bet) | Separate authorization + `--scope INCLUDE_RETIRED_WITH_WARNING` |
| NO_DATA governance | 7 strategies | Decision: accept as permanent NO_DATA or reconstruct externally |
| ARTIFACT_ONLY governance | 41 strategies | Governance review before any registration |

---

## Test Coverage

| Suite | Tests | Result |
|-------|-------|--------|
| `test_p2_full_catalog_visibility_plan.py` | 24 | ✅ PASS |
| `test_p7_controlled_apply_actual_gate.py` | 17 | ✅ PASS |
| `test_replay_api_contract.py` | 44 | ✅ PASS |
| **Total** | **85** | **✅ 85 PASS / 0 FAIL** |
