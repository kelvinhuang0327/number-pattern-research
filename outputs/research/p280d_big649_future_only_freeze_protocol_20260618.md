# P280D BIG 6/49 Future-Only Freeze and Immutable Publication Protocol

## Status

- Freeze ID: `P280D_BIG649_FUTURE_ONLY_FREEZE_20260618`
- Status: `PROTOCOL_FROZEN_NOT_ACTIVATED`
- Base: `origin/main` at `fc8225222430f2bfde3b480df75441c8e93ed05b`
- Protocol SHA-256: `c5c004044b44599c7ff6d6d3bc424dda02885d721e38caeb7138be9772cf649f`
- Prediction-success claim: `false`
- Strategy promoted: `false`
- Activation authorized: `false`
- Formal future evaluation: `NOT_STARTED_NOT_AUTHORIZED`
- Real target selected: `false`
- Real future ticket published: `false`

This is a local-only protocol freeze. It neither activates a strategy nor publishes a prediction.

## Frozen Research Contract

- Game: BIG / 大樂透 / 6-49
- Strategies: exactly 11, lexical strategy-ID order
- Primary budget: `N=1`
- Bet index: `1`
- Ticket: six unique main numbers in `1..49`
- Endpoint: `BIG_ANY_PRIZE_AWARE_WIN`
- Endpoint rule: `hit_count >= 3 OR (hit_count == 2 AND special_hit == true)`
- `hit_count` uses only the six actual main numbers.
- `special_hit` means the actual special number is among the predicted six main numbers.
- No special number is predicted.
- Strategy ranking: `NONE`
- Historical candidate selection: `NONE`
- Native N=3/N=4 portfolios: out of scope

All 11 identities are frozen without deletion, ranking, or exclusion based on historical results:

1. `bet2_fourier_expansion_biglotto`
2. `biglotto_deviation_2bet`
3. `biglotto_echo_aware_3bet`
4. `biglotto_triple_strike`
5. `biglotto_ts3_markov_4bet_w30`
6. `cold_complement_biglotto`
7. `coldpool15_biglotto`
8. `fourier30_markov30_biglotto`
9. `markov_2bet_biglotto`
10. `markov_single_biglotto`
11. `ts3_regime_3bet`

Different strategy identities remain separate even when tickets collide. A manifest records the other strategy IDs sharing the same ticket hash; it never merges them.

## Source Freeze

Each strategy record in the JSON artifact binds a repository-relative source path, Git blob SHA-1, file SHA-256, and generator/function identity. Shared source files are intentionally repeated per strategy so the manifest can require exact 11-ID digest coverage.

| Strategy | Canonical generator identity | Source SHA-256 |
|---|---|---|
| `bet2_fourier_expansion_biglotto` | `predict_fourier_expansion_bet1` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `biglotto_deviation_2bet` | `deviation_complement_2bet[bet_index=1]` | `bb97c0bf044c5f9f37de7c6f27629e479bda650ca33dfeb7d0fbff840537bfba` |
| `biglotto_echo_aware_3bet` | `echo_aware_mixed_3bet(...)[bet_index=1]` | `ed4878fb59e22c44f26313646a762e034c7f92355e5df56a6f72eed887d11320` |
| `biglotto_triple_strike` | `generate_triple_strike[bet_index=1]` | `236fe529c01f1c39f4297258db6dc591e4612365720245fc8051540ed69954b7` |
| `biglotto_ts3_markov_4bet_w30` | `generate_ts3_markov_4bet(...)[bet_index=1]` | `25760472baa09835b560f146ff4a0ce23fa2f2373a75d60c64ed557286dfbc2a` |
| `cold_complement_biglotto` | `predict_cold_complement_bet1` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `coldpool15_biglotto` | `predict_coldpool15` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `fourier30_markov30_biglotto` | `predict_fourier30_markov30_bet1` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `markov_2bet_biglotto` | `predict_markov_2bet_bet1` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `markov_single_biglotto` | `predict_markov_single` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` |
| `ts3_regime_3bet` | `fourier_rhythm_bet via ts3_regime_3bet[bet_index=1]` | `b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e` |

### P280AJ Publication-Interface Revision (2026-06-19)

The frozen `bet_index=1` outputs structurally duplicate sibling strategies, so the
no-DB publication adapter cannot emit eleven unique complete tickets. Under explicit
Owner authorization, two frozen source files gained additive deterministic
candidate callables and the source SHA-256 values above were reconciled to the new
bytes. This is a forward publication-interface revision, **not** retroactive
evidence: the `bet_index=1` semantics and the P280D semantic goldens are unchanged.

| Source file | Previous SHA-256 | Current SHA-256 | Additive callables |
|---|---|---|---|
| `lottery_api/models/p42_wave3_biglotto_adapters.py` | `19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b` | `f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da` | `predict_markov_2bet_candidates`, `predict_coldpool15_candidates` |
| `tools/backtest_biglotto_enhancements.py` | `088e0815a0f1afb2aa884b0215882090efa72afeea0cc020d6ec8145cb143260` | `b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e` | `ts3_regime_candidates` |

Per-strategy publication rebind: `markov_2bet_biglotto` publishes Markov bet-2
(next-6 by score) while `markov_single_biglotto` keeps the top-6 bet-1 identity;
`coldpool15_biglotto` publishes a distinct 6-of-15 from the same ranked cold pool
while `cold_complement_biglotto` keeps the coldest-6 identity; `ts3_regime_3bet`
publishes the next TS3-family bet when the fourier bet-1 collides with a sibling.
The adapter selects the first non-duplicate candidate deterministically and fails
closed if none remain. No fabricated fallback, no outcome-aware selection, no
historical-best selection, no registry mutation, no DB access, no network access.

## Historical Evidence Boundary

The controlling conclusion remains `P280C_BIG649_POST_HOC_ARTIFACT_TIMING_NOT_VERIFIED`.

- The 11-strategy long-window record contains 8,250 strategy-by-draw cells.
- Verified immutable pre-draw publications: 0 of 8,250.
- Historical ticket artifacts: `POST_HOC_ARTIFACT_NOT_READY`.
- Source cutoff guard: `PASS_SOURCE_SEMANTICS_ONLY`.
- A local generation timestamp is not immutable publication evidence.
- Historical outcomes cannot rank, select, exclude, or promote any of the 11 frozen strategies.
- Historical evidence is excluded from formal future confirmation.

## Prediction Manifest

The builder accepts only explicit history ending strictly before the target and exactly one bet-index-1 ticket for every frozen strategy. It emits an in-memory `UNPUBLISHED_LOCAL_DRAFT` containing the frozen source identities, sorted tickets, ticket hashes, duplicate relationships, optional previous-manifest hash, and a self hash.

Canonical serialization is UTF-8 JSON with lexical key sorting, compact comma/colon separators, one trailing LF, and no insignificant whitespace. `manifest_sha256` is computed over the full manifest except the `manifest_sha256` field itself. Strategy input order and history input order do not change the canonical manifest or its hash.

The validator fails closed for a missing, extra, or duplicate strategy; non-one bet index; malformed ticket; target at/before cutoff; target/future history row; supplied target outcome; outcome field; missing or malformed source identity; freeze mismatch; local generation at/after deadline; malformed previous hash; duplicate-relationship mismatch; or any mutation that invalidates the manifest hash. It never repairs invalid input.

## Immutable Publication Design

This section is a procedure definition only. P280D does not execute it.

1. The protocol commit must already be merged before a prediction is generated.
2. The target outcome must not exist, and the explicit history cutoff must be strictly earlier than the target.
3. Generate the manifest once. Do not rerun alternatives and select among them.
4. Use a new independent prediction branch for that target and a normal push. Force push is prohibited.
5. Create a GitHub PR before the governed deadline.
6. Immutable evidence is the GitHub server-side PR `createdAt`, exact head SHA, manifest Git blob SHA, and manifest SHA-256.
7. GitHub server time controls timeliness; a local timestamp does not.
8. After PR creation, the prediction head must not change. Retain the branch and PR until evaluation closeout.
9. Never write the target outcome back into the prediction manifest. Post-draw evaluation belongs in a separate artifact and separately authorized workflow.
10. If no valid PR exists before the deadline, classify `NO_VALID_PRE_DRAW_PUBLICATION`. Post-deadline backfill is prohibited.

No real prediction branch or prediction PR is created by this protocol task.

## Authorization Boundary

Future publication, target selection, official deadline lookup, outcome evaluation, activation, registry mutation, DB access, page/API work, scheduling, production, deployment, and controlled apply remain unauthorized. Packaging and PR state are determined from current GitHub state and are not encoded in this artifact; merge still requires separate authorization and independent review.

Durable artifact classification: `P280D_BIG649_FUTURE_ONLY_FREEZE_PROTOCOL_IMPLEMENTED_NOT_ACTIVATED`.
