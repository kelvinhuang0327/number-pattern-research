# P280AJ BIG 6/49 No-DB Strategy-Output Adapter — Interface + Freeze Remediation

## Classification

`P280AJ_BIG649_STRATEGY_INTERFACE_AND_FREEZE_REMEDIATED_PR461_UPDATED_NOT_ACTIVATED`

(Supersedes the P280AG/P280AH/P280AI blocked states on this branch.)

The fail-closed no-DB adapter now returns a P280AD-compatible set of **11 unique
complete tickets**. It calls only the exact P280D-frozen sources plus the
deterministic candidate callables added under P280AJ to those same frozen source
files. It never substitutes a fabricated output, never selects by outcome, and
never selects by past performance.

## Original Root Cause (P280AG / P280AH)

The frozen `bet_index=1` outputs structurally duplicate sibling strategies, so a
single primary ticket per strategy cannot yield eleven unique complete tickets.
On the synthetic fixture the duplicate complete-ticket groups were:

1. `bet2_fourier_expansion_biglotto`, `biglotto_triple_strike`,
   `biglotto_ts3_markov_4bet_w30`, `ts3_regime_3bet`
2. `cold_complement_biglotto`, `coldpool15_biglotto`
3. `markov_2bet_biglotto`, `markov_single_biglotto`

P280AH proved adapter-only distinct selection could resolve 8 of 11 but not
`coldpool15_biglotto`, `markov_single_biglotto`, or `ts3_regime_3bet`, because
their frozen interfaces expose only a single candidate.

## P280AI Freeze-Scope Blocker

Source-interface remediation changes the bytes of two P280D-pinned source files
(`lottery_api/models/p42_wave3_biglotto_adapters.py` and
`tools/backtest_biglotto_enhancements.py`). P280AI stopped because that breaks the
merged P280D freeze-reconcile test unless the freeze artifact is reconciled. Owner
authorized P280AJ to do the interface remediation **and** the P280D freeze
reconciliation together.

## Interface Changes (additive only; bet-1 semantics preserved)

| Source file | Additive callables | Previous SHA-256 | Current SHA-256 |
|---|---|---|---|
| `lottery_api/models/p42_wave3_biglotto_adapters.py` | `predict_markov_2bet_candidates`, `predict_coldpool15_candidates` | `19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `tools/backtest_biglotto_enhancements.py` | `ts3_regime_candidates` | `088e0815a0f1afb2aa884b0215882090efa72afeea0cc020d6ec8145cb143260` | `b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e` |

No existing function was modified; no strategy algorithm was rewritten; the frozen
`bet_index=1` outputs and the P280D semantic goldens are byte-unchanged. No
strategy registry was mutated.

## Per-Strategy Candidate Selection

The adapter enumerates an ordered candidate list per strategy and selects, in
canonical frozen order, the first complete ticket not already claimed by an
earlier strategy. Selection rule: *first deterministic source candidate whose
complete ticket is not already claimed by an earlier frozen strategy; fail closed
if none remain.*

| Strategy | Candidate source callable | Idx / Count | Rebound | Published ticket |
|---|---|---|---|---|
| `bet2_fourier_expansion_biglotto` | `…p42_wave3…:predict_fourier_expansion_bet1` | 0 / 1 | no | `[8, 9, 16, 30, 44, 45]` |
| `biglotto_deviation_2bet` | `…predict_biglotto_deviation_2bet:deviation_complement_2bet` | 0 / 2 | no | `[5, 8, 29, 30, 32, 35]` |
| `biglotto_echo_aware_3bet` | `…predict_biglotto_echo_3bet:echo_aware_mixed_3bet` | 0 / 3 | no | `[2, 5, 9, 20, 26, 30]` |
| `biglotto_triple_strike` | `…predict_biglotto_triple_strike:generate_triple_strike` | 1 / 3 | yes | `[10, 19, 23, 26, 27, 40]` |
| `biglotto_ts3_markov_4bet_w30` | `…backtest_biglotto_5bet_ts3markov:generate_ts3_markov_4bet` | 2 / 4 | yes | `[4, 5, 12, 20, 39, 41]` |
| `cold_complement_biglotto` | `…p42_wave3…:predict_cold_complement_bet1` | 0 / 1 | no | `[4, 5, 20, 30, 39, 44]` |
| `coldpool15_biglotto` | `…p42_wave3…:predict_coldpool15_candidates` | 1 / 3 | yes | `[8, 9, 12, 29, 32, 35]` |
| `fourier30_markov30_biglotto` | `…p42_wave3…:predict_fourier30_markov30_bet1` | 0 / 1 | no | `[2, 5, 9, 20, 30, 35]` |
| `markov_2bet_biglotto` | `…p42_wave3…:predict_markov_2bet_candidates` | 0 / 3 | yes | `[8, 9, 18, 25, 39, 41]` |
| `markov_single_biglotto` | `…p42_wave3…:predict_markov_single` | 0 / 1 | no | `[4, 5, 7, 20, 30, 44]` |
| `ts3_regime_3bet` | `…backtest_biglotto_enhancements:ts3_regime_candidates` | 1 / 3 | yes | `[23, 26, 27, 31, 34, 40]` |

- `markov_single_biglotto` keeps the top-6 bet-1 identity; `markov_2bet_biglotto`
  rebinds to the Markov bet-2 (next-6 by score).
- `cold_complement_biglotto` keeps the coldest-6; `coldpool15_biglotto` rebinds to
  a distinct 6-of-15 from the same ranked cold pool.
- `ts3_regime_3bet` rebinds to the next TS3-family bet when the fourier bet-1
  collides with a sibling.

Duplicate complete-ticket groups **before** remediation: 3 groups (8 strategies).
Duplicate complete-ticket groups **after** remediation: **0**. Resolved output
digest `65917f6ed24122c4dbd08932730965e5752c8f8da5591e21f44840f66c6b5e32`,
byte-stable on an identical rerun.

## P280AD Compatibility

The eleven resolved tickets pass the P280AD `SAFE_VALIDATE_ONLY` manifest builder
(`PASS_SAFE_VALIDATE_ONLY`): exact 11 frozen IDs, `N=1`, `bet_index=1`,
`BIG_ANY_PRIZE_AWARE_WIN`, six unique numbers in `1..49`, and zero duplicate
complete tickets. No real artifact is written; no target/deadline is selected.

## P280D Freeze Reconciliation

The P280D freeze artifact and markdown were reconciled to the new source bytes,
preserving the previous hashes in a `p280aj_publication_interface_revision`
section recorded as a forward publication-interface revision (not retroactive
evidence). The P280D freeze-reconcile test passes (`38 passed`). The P280D test
file required no change because it recomputes source hashes dynamically.

## Safety Record

- Contract: exact 11 IDs, `N=1`, `bet_index=1`, `BIG_ANY_PRIZE_AWARE_WIN`
- DB opened / queried / copied / written: **NO / NO / NO / NO**
- Network or GitHub side effect: **NO**
- Real target selected / official deadline lookup: **NO / NO**
- Real ticket or publication PR: **NO**
- Outcome access or future evaluation: **NO**
- Fabricated fallback / outcome-aware selection / historical-best selection: **NO / NO / NO**
- Strategy algorithm rewrite / registry mutation: **NO / NO**
- Prediction success claim / strategy promotion / activation: **NO / NO / NO**

## Next Step

Independent audit of the P280AJ strategy-interface and freeze reconciliation is
recommended before merge. The first real publication remains a separate Owner
authorization and must not start from this task.
