# P224 - DAILY_539 Survivor Deeper Validation

**Date:** 2026-06-03  
**Task:** `P224_DAILY539_MIDFREQ_FOURIER_2BET_DEEPER_VALIDATION`  
**Status:** COMPLETE / READ-ONLY  
**Classification:** `P224_SURVIVOR_NEEDS_MORE_OOS`  
**Authorized by:** User explicit task prompt 2026-06-03  

This report is read-only historical replay evidence for the single P223B survivor only. It does not modify the DB, registry, production state, or recommendation logic, and it is not betting advice.

## Phase 0 Verification

| Check | Result |
|---|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` |
| branch | `main` |
| git dir | `.git` |
| HEAD | `848d354b7978356ffb7dad9ade680747c9054646` |
| origin/main | `848d354b7978356ffb7dad9ade680747c9054646` |
| staged files | `0` |
| replay rows | `94924` |
| DAILY_539 rows | `34680` |
| bet_index nulls | `0` |
| duplicate replay keys | `0` |
| PRAGMA integrity_check | `ok` |
| drift guard | `Status: PASS` |
| P223B artifacts tracked | `outputs/research/p223b_candidate_oos_cross_year_validation_20260603.md, outputs/research/p223b_candidate_oos_cross_year_validation_20260603.json` |

## Validation Scope

- Candidate under test: `midfreq_fourier_2bet / DAILY_539`
- Scope is deliberately narrow: no new feature families, no new windows, no universe expansion, and no P225.
- The slice is treated as the survivor identified in P223B and is evaluated read-only only.
- Leakage checks were performed on the candidate slice before reading any deeper stability signals.

## Candidate Inventory

| Field | Value |
|---|---|
| strategy_id | `midfreq_fourier_2bet` |
| lottery_type | `DAILY_539` |
| kind | `strategy` |
| unit label | `strategy-level (row grain)` |
| rows | `1500` |
| distinct draws | `1500` |
| bet_index values | `1` only |
| replay_run_id | `p31b_wave1_prod_20260523` |
| source | `P31B_WAVE1_PRODUCTION_APPLY` |
| truth_level | `DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED` |

## Leakage / Overlap Checks

| Check | Result |
|---|---|
| target_draw duplicate count | `0` |
| history_cutoff_draw >= target_draw | `0` |
| prediction_cutoff_date >= target_date | `0` |
| rows = distinct draws | `PASS` |
| sample cutoff relation | `history_cutoff_draw = target_draw - 1` in the observed sample |

## Overall Result

| Metric | Value |
|---|---:|
| mean hit_count | `0.6693333333333333` |
| 95% CI | `[0.6322371303354622, 0.7064295363312044]` |
| baseline used | `0.6410256410256411` |
| all-history reference baseline | `0.6251612903225806` |
| w100 baseline | `0.6096774193548387` |
| w500 baseline | `0.6470967741935484` |
| consensus baseline | `0.68` |
| best competing non-candidate baseline | `daily539_f4cold = 0.678616` |
| one-sided p vs baseline | `0.0673719479414372` |
| conclusion | Promising but not stable enough for confirmation |

### Hit Count Distribution

| hit_count | rows |
|---|---:|
| 0 | `714` |
| 1 | `587` |
| 2 | `180` |
| 3 | `19` |

| Derived rate | Value |
|---|---:|
| M1+ | `0.524` |
| M2+ | `0.13266666666666665` |
| M3+ | `0.012666666666666666` |
| max hit_count | `3` |

## Tail OOS

| Window | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 150 | `150` | `0.76` | `[0.6378703464892057, 0.8821296535107943]` | `0.028107691921502198` | above |
| 300 | `300` | `0.7566666666666667` | `[0.6721775892222573, 0.8411557441110761]` | `0.0036518385054046254` | above |
| 500 | `500` | `0.71` | `[0.6457131951330601, 0.7742868048669398]` | `0.017736561200837442` | above |

## Cross-Year Stability

| Year | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 2021 | `124` | `0.6451612903225806` | `[0.5163730455033222, 0.7739495351418391]` | `0.47490732525583934` | above |
| 2022 | `313` | `0.6741214057507987` | `[0.5908675797062201, 0.7573752317953774]` | `0.2179439807837047` | above |
| 2023 | `312` | `0.6506410256410257` | `[0.5709505688410532, 0.7303314824409981]` | `0.4065254652598016` | above |
| 2024 | `314` | `0.6146496815286624` | `[0.5351101898686255, 0.6941891731886993]` | `0.7421385037564241` | below |
| 2025 | `316` | `0.7246835443037974` | `[0.64309078623749, 0.8062763023701048]` | `0.022236326771580828` | above |
| 2026 | `121` | `0.7272727272727273` | `[0.5976859504132231, 0.8568595041322314]` | `0.0960337639739347` | above |

## Block Stability

Non-overlapping 150-row blocks sorted by `target_draw`.

| Block | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 1 | `150` | `0.68` | `[0.5612154473192935, 0.7987845526807066]` | `0.2600812520546333` | above |
| 2 | `150` | `0.5866666666666667` | `[0.46807391865279574, 0.7052594146805375]` | `0.8155135282616355` | below |
| 3 | `150` | `0.74` | `[0.6225016735816585, 0.8574983264183414]` | `0.0493692816499508` | above |
| 4 | `150` | `0.6333333333333333` | `[0.5173168338681791, 0.7493498327984875]` | `0.5516989814700819` | below |
| 5 | `150` | `0.66` | `[0.5448501158393018, 0.7751498841606983]` | `0.3733596864135489` | above |
| 6 | `150` | `0.62` | `[0.4992905887863106, 0.7407094112136894]` | `0.6335989601901163` | below |
| 7 | `150` | `0.6066666666666667` | `[0.49750459158087035, 0.715828741752463]` | `0.7313542055681072` | below |
| 8 | `150` | `0.6533333333333333` | `[0.5394407606883022, 0.7672259059783645]` | `0.4161293763209941` | above |
| 9 | `150` | `0.7533333333333333` | `[0.6365540738861308, 0.8701125927805358]` | `0.029718287488115336` | above |
| 10 | `150` | `0.76` | `[0.6378703464892057, 0.8821296535107943]` | `0.028107691921502198` | above |

| Block summary | Value |
|---|---:|
| mean of block means | `0.6693333333333333` |
| block mean SD | `0.05934456822471436` |
| blocks above baseline | `6 / 10` |
| worst block | `Block 2 = 0.5866666666666667` |
| best block | `Block 10 = 0.76` |

## Robustness / Sensitivity

| Slice | n | Mean | 95% CI | p vs baseline | Interpretation |
|---|---:|---:|---|---:|---|
| Excluding 2025 | `1184` | `0.6545608108108109` | `[0.6129539364591399, 0.6961676851624818]` | `0.26186399862506193` | below baseline |
| Excluding 2026 | `1379` | `0.6642494561276288` | `[0.6255449712109247, 0.7029539410443328]` | `0.11978606422050297` | below baseline |
| Excluding 2024 | `1186` | `0.6838111298482293` | `[0.6419236714340605, 0.7256985882623982]` | `0.022641253565449437` | above baseline |
| Excluding hit_count=3 rows | `1481` | `0.6394328156650911` | not recomputed here | `0.5354861435202416` | below baseline |

## Interpretation

- The candidate is clean from a leakage / duplication standpoint.
- Tail windows are positive, and 2025/2026 cross-year slices are also positive.
- The full-sample edge remains weak because the overall p-value is above a conventional 0.05 cutoff and the confidence interval crosses the baseline.
- Stability is mixed: 6 of 10 blocks are above baseline, but 4 are below and the worst block is materially under baseline.
- The signal is sensitive to the 19 rows with hit_count `3`; removing them drops the mean below baseline.
- Net: this is a real survivor, but it is not confirmed enough to advance as a stronger model-design input.

## Decision

- Final classification: `P224_SURVIVOR_NEEDS_MORE_OOS`
- No deployment, promotion, DB write, registry write, production change, or recommendation-logic change is authorized from this report.
- P225 is not started here.

