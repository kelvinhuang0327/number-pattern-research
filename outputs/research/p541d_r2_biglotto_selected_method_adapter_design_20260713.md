# P541D_R2 BIG_LOTTO Selected-Method Adapter Design (No DB)

## Executive summary

Pinned static design at generation base `8db53f9cb829d658ea47f01476ec52a61c5c583c` for exactly five P541C_R2-selected methods. Two designs are implementation-ready, two require CTO identity decisions, and one is rejected as not an adapter candidate. No selected module was imported or executed; no DB, data, runtime, network, environment, or registry runtime state was accessed or changed. Canonical registry Git source was inspected at the pinned reference commit.

## Pinned source identities

- P541C artifact: commit `a68b5ca8663e82b7dad5da7c66d53eec10e517c0`, blob `0406f78c4d42b5551b12843f2d0d1443a55a9971`, 1407881 bytes, SHA-256 `ce0fa64f9b3b04dec4b42fddadce119c8f44ff5d36f10bf85a2dc0d3c2f3ac6c`, selector `p541c-r2-selector-v5`.
- P541C-declared source/reference: commit `1777e15556d41f1ff829f9ac18aa3f58d7f8f54f`, tree `5582783e56a930d7c9e637485b3c9749e66f470a`.
- P541D generation source: commit `8db53f9cb829d658ea47f01476ec52a61c5c583c`, tree `f0d26bd7235e3af02ba12790e18964b947e79d6f`.
- Five selected method source blobs: historical source commit `9572d994e94fae44cf7730297e7537c0901d5a78`, tree `2cd6113c8450102d434044b7641a9d89f74cd682`.
- Canonical adapter references: current commit `8db53f9cb829d658ea47f01476ec52a61c5c583c`; compared with historical commit `9572d994e94fae44cf7730297e7537c0901d5a78`.

## P541C readiness boundary

P541C `ready_for_replay_readiness_now`: **0**. P541D `ready_for_implementation` grades only static design readiness; it does not promote P541C replay readiness or production status.

## Record and shortlist stability

P541C v5 contains 580 records, with 580 unique method IDs and 580 unique source paths. Method-ID and source-path order both match the historical v4 artifact. The five-member shortlist order is unchanged: `tools/advanced_prediction_engine.py`, `lottery_api/models/social_wisdom_predictor.py`, `tools/quick_ml_predict.py`, `tools/big_lotto_exhaustive_audit.py`, `lottery_api/models/zone_split.py`.

## Five-method decision table

| Method | Equivalent audit | Design status | Ready | Proposed strategy |
|---|---|---|---:|---|
| `tools/advanced_prediction_engine.py` | EXISTING_PARTIAL_EQUIVALENT | CTO_REVIEW_REQUIRED | no | `—` |
| `lottery_api/models/social_wisdom_predictor.py` | EXISTING_EQUIVALENT_REUSE | LAZY_DIRECT_WRAPPER_READY | yes | `biglotto_social_wisdom_anti_popularity` |
| `tools/quick_ml_predict.py` | EXISTING_PARTIAL_EQUIVALENT | CTO_REVIEW_REQUIRED | no | `—` |
| `tools/big_lotto_exhaustive_audit.py` | NO_EXISTING_EQUIVALENT | NOT_AN_ADAPTER_CANDIDATE | no | `—` |
| `lottery_api/models/zone_split.py` | EXISTING_PARTIAL_EQUIVALENT | DETERMINISTIC_REIMPLEMENTATION_READY | yes | `biglotto_zone_split_3bet_bet1` |

## Detailed method sections

### `tools/advanced_prediction_engine.py`

- Source identity: commit `9572d994e94fae44cf7730297e7537c0901d5a78`, blob `5c72f7e87de6d2f7721d7fc9eb7eb57f4e848744`, 24006 bytes, SHA-256 `f92be0a25fc2da83eb9d999081a80d59c4c9af089edcefcdf44f6f3cfc16a8ce`; UTF-8/AST `PASS/PASS`.
- Decision: **CTO_REVIEW_REQUIRED** — The file exposes five predict_next_draw modes. Default ensemble behavior changes with optional sklearn/XGBoost availability, imports print warnings, and an untrained ensemble silently falls back to statistical mode. P541C selected only the file identity, so choosing one mode would invent the selected identity.
- Entry point: `UNRESOLVED / NONE`.
- Equivalent audit: EXISTING_PARTIAL_EQUIVALENT; overlapping frequency/hot-cold/statistical features, not exact engine identity; native deterministic scoring precedent, not an equivalent adapter
- History/cutoff: Unresolved: statistical paths use oldest-to-newest DataFrame tail windows; P541C does not select a mode. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: ML model seeds are fixed at 42, but dependency-conditional mode selection remains unresolved.
- External state/import plan: Do not import the source. CTO must select a single identity; then prefer adapter-owned pure extraction or explicitly approve a dependency-pinned implementation.
- Normalization/validation: unresolved until mode selection → one flat six-number list after selection; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: blocked — CTO must pin the exact mode and optional-dependency semantics before parity can be defined..
- Blockers/CTO decisions: Select exactly one legacy prediction identity.; Decide whether sklearn/XGBoost availability is part of identity or prohibited..

### `lottery_api/models/social_wisdom_predictor.py`

- Source identity: commit `9572d994e94fae44cf7730297e7537c0901d5a78`, blob `1a1f4119f4ade1b5605a988f595c7ed8300e6a40`, 12772 bytes, SHA-256 `a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b`; UTF-8/AST `PASS/PASS`.
- Decision: **LAZY_DIRECT_WRAPPER_READY** — SocialWisdomPredictor.predict is import-safe, deterministic and already accepts in-memory history. The random generate_8_bets and empty-history random branch of predict_with_balance are explicitly excluded.
- Entry point: `SocialWisdomPredictor.predict(history, pick_count=6)`.
- Equivalent audit: EXISTING_EQUIVALENT_REUSE; social_wisdom_predict delegates to SocialWisdomPredictor.predict; reuse the selected pure callable, not the facade's logging/special-number work
- History/cutoff: Canonical replay supplies oldest-to-newest; wrapper passes reversed(history[-50:]) because the legacy callable treats history[:50] as newest-first. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: Use predict() only; never call predict_with_balance(empty history) or generate_8_bets().
- External state/import plan: Lazy-import only SocialWisdomPredictor inside _call_strategy; module has no import-time executable output or I/O.
- Normalization/validation: copy strictly-prior history, keep last 50, reverse to newest-first → the returned sorted list[int]; ignore facade confidence/meta/special; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: direct-call parity — exact six-number equality.
- Blockers/CTO decisions: none.

- Current registry source: `biglotto_social_wisdom_anti_popularity` appears in `lottery_api/models/replay_strategy_registry.py` at `8db53f9cb829d658ea47f01476ec52a61c5c583c` (blob `21be32d9f0db2a600683dc1788a57f28b87f2529`); factory source declares `ONLINE`. Runtime state was not observed. Review the existing source implementation against this design; do not create a duplicate strategy ID.

### `tools/quick_ml_predict.py`

- Source identity: commit `9572d994e94fae44cf7730297e7537c0901d5a78`, blob `36cf12dcef80d7f0bada22e024336eb22f8bfee5`, 11213 bytes, SHA-256 `8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80`; UTF-8/AST `PASS/PASS`.
- Decision: **CTO_REVIEW_REQUIRED** — QuickMLPredictor.predict_advanced_ensemble is only a candidate legacy entrypoint; no canonical runtime entrypoint is approved. Its Method 9 terminal iteration always forms a two-row pattern and then reads pattern[2], so the pinned callable raises IndexError for every usable history length (at least five), including the proposed 50-row minimum. A direct crash-faithful wrapper is not a useful replay strategy, while correcting the loop boundary changes executable semantics and requires a separately identified strategy or explicit CTO approval.
- Entry point: `UNRESOLVED / NONE`.
- Equivalent audit: EXISTING_PARTIAL_EQUIVALENT; overlapping statistical features but not the same ten-weight QuickML formula
- History/cutoff: Source-proven observation only: DataFrame.head() treats the CSV as newest-first. This ordering observation does not establish runtime readiness or approve a canonical adapter contract. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: The observed failure is deterministic; absence of random calls does not make the crashing callable implementation-ready.
- External state/import plan: Do not import or construct QuickMLPredictor, do not create a temporary CSV, and do not implement an adapter. A corrected in-memory variant is a future, separately authorized strategy identity rather than a faithful wrapper of the pinned callable.
- Normalization/validation: No canonical runtime input contract is approved; newest-first behavior remains a source observation only → No successful legacy ticket exists for parity; pattern[2] raises IndexError before ranking completes; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: blocked — No successful legacy parity oracle exists. CTO must first decide whether to reject the historical identity or authorize a separately named bounds-repaired strategy and its corrected parity contract..
- Blockers/CTO decisions: Reject the historical QuickML identity entirely; or; Authorize a separately identified bounds-repaired QuickML strategy; and; Specify the corrected loop boundary and parity contract..
- Semantic defect evidence: Method 9 uses `range(3, len(df) - 1)`; at `i = len(df) - 2`, `df.iloc[i:i+3]` has 2 rows while `range(3)` accesses indices [0, 1, 2]. pattern[2] raises IndexError for every history length >= 5.
- Semantic identity consequence: Clamping the loop boundary is a semantic repair, not identity-preserving extraction. The proposed minimum history of 50 cannot produce a successful legacy ticket.

### `tools/big_lotto_exhaustive_audit.py`

- Source identity: commit `9572d994e94fae44cf7730297e7537c0901d5a78`, blob `ff9efe54d3519c47798c9f6b47a5e3dc44f0b730`, 3292 bytes, SHA-256 `694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c`; UTF-8/AST `PASS/PASS`.
- Decision: **NOT_AN_ADAPTER_CANDIDATE** — BigLottoAuditor.run_audit is an outcome-aware multi-period evaluator. It reads CSV in the constructor, silently substitutes synthetic random history on every exception, samples multiple random bets, observes the actual draw, and returns aggregate hit-rate/ROI rather than a ticket.
- Entry point: `UNRESOLVED / NONE`.
- Equivalent audit: NO_EXISTING_EQUIVALENT; only the batch auditor identity was found; no genuine one-draw callable or adapter exists
- History/cutoff: run_audit internally slices prior rows, then consumes the current outcome; it is not a target-time predictor contract. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: global random.sample and synthetic fallback are prohibited; no seed can convert an evaluator into a predictor identity.
- External state/import plan: Never import or wrap. A future task may separately design a new hot/cold predictor, but it must not claim BigLottoAuditor identity.
- Normalization/validation: not normalizable to a one-draw predictor without invention → aggregate metrics; no valid one-bet extraction; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: not applicable — No parity oracle exists for a one-bet adapter because the source has no one-bet output..
- Blockers/CTO decisions: Rejected as adapter candidate. Any new predictor requires a separately named strategy and CTO approval..

### `lottery_api/models/zone_split.py`

- Source identity: commit `9572d994e94fae44cf7730297e7537c0901d5a78`, blob `5ce1ce023cab846791550bd7240106600ee9b95e`, 3916 bytes, SHA-256 `b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211`; UTF-8/AST `PASS/PASS`.
- Decision: **DETERMINISTIC_REIMPLEMENTATION_READY** — Preserve the exact three-zone boundaries, overlap=2 and first-bet selection, but replace global random.sample with a local random.Random instance seeded from canonical strategy identity plus strictly-prior causal history. No historical signal or equivalent strategy is borrowed.
- Entry point: `deterministic reimplementation of get_zone_split_predictor('BIG_LOTTO', 3), first bet only`.
- Equivalent audit: EXISTING_PARTIAL_EQUIVALENT; multiple zone variants exist, but their pools/weighting differ from ZoneSplitStrategy.generate_bets; front-end zone strategy is a separate implementation surface, not a ReplayStrategyAdapter; runtime route calls the exact selected factory; no replay adapter exists
- History/cutoff: Canonical oldest-to-newest history is retained only for seed material; all rows must be strictly prior and canonicalized by draw/date/numbers. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: Build UTF-8 canonical JSON of {strategy_id, lottery_type, causal_history:[{draw,date,numbers}]}; SHA-256 it; seed local random.Random with the full digest integer; sample each legacy zone sequentially; record bet 1 only. Never seed or call global RNG.
- External state/import plan: Do not import the selected module because it uses global random. Reimplement only its 1..49, three-zone, overlap=2 candidate-pool construction in the future adapter.
- Normalization/validation: canonical history used only in deterministic seed preimage → first of three sequential local-RNG bets; validate and discard other bets/coverage metadata; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: algorithm parity — same pools and sample count; deterministic seed intentionally replaces nondeterministic global RNG.
- Blockers/CTO decisions: none.

- Current registry source: `biglotto_zone_split_3bet_bet1` appears in `lottery_api/models/replay_strategy_registry.py` at `8db53f9cb829d658ea47f01476ec52a61c5c583c` (blob `21be32d9f0db2a600683dc1788a57f28b87f2529`); factory source declares `ONLINE`. Runtime state was not observed. Review the existing source implementation against this design; do not create a duplicate strategy ID.

## Canonical adapter reference comparison

| Reference | Historical blob | Current blob | Classification |
|---|---|---|---|
| `lottery_api/models/replay_strategy_registry.py` | `45770dabaa46c80e6f564b61e5dae96b03bd856e` | `21be32d9f0db2a600683dc1788a57f28b87f2529` | DESIGN_CONTRACT_DELTA |
  - ReplayStrategyAdapter.get_one_bet now predicts a POWER_LOTTO special number with power_lotto_second_zone.second_zone_predict(history); BIG_LOTTO still returns special=None, so this change does not alter the five BIG_LOTTO designs.
  - The current registry adds P0 2-bet, BIG_LOTTO ZoneSplit, and Social Wisdom adapter factories. The ZoneSplit Bet1 and Social Wisdom IDs match two P541D proposed IDs, and their factory source declares status=ONLINE.
  - The two matching current registry declarations affect implementation follow-up: inspect and reconcile the existing source before any future implementation, and do not add duplicate strategy IDs. This static source finding is not runtime-state evidence and does not change P541C replay readiness.
| `lottery_api/models/p42_wave3_biglotto_adapters.py` | `213193465f205faac47a23b4e6b07d6701626571` | `213193465f205faac47a23b4e6b07d6701626571` | UNCHANGED |
| `lottery_api/models/p93_tierb_replay_adapters.py` | `297681147267d937383d7f898e59b26f811c6722` | `297681147267d937383d7f898e59b26f811c6722` | UNCHANGED |

P42 and P93 blobs are unchanged, so their recorded identities are provenance-only. The replay registry blob changed and its source-level contract delta is recorded above; Social Wisdom and ZoneSplit IDs already appear in the current source. This is not evidence that a runtime was queried or that those candidates are P541C replay-ready.

## Historical normalized design comparison

Normalized result: **EXACT_EXPLAINED_DIFF**. The five methods, order, source identities, readiness gates, and 2 implementation-ready / 2 CTO-review / 1 rejected status counts are preserved. Explained differences are limited to P541C v5 provenance, separated generation/source bases, and the current registry contract/reference evidence.

## Duplicate/equivalent findings

- `tools/advanced_prediction_engine.py` — EXISTING_PARTIAL_EQUIVALENT: `tools/quick_ml_predict.py` (overlapping frequency/hot-cold/statistical features, not exact engine identity); `lottery_api/models/p42_wave3_biglotto_adapters.py` (native deterministic scoring precedent, not an equivalent adapter)
- `lottery_api/models/social_wisdom_predictor.py` — EXISTING_EQUIVALENT_REUSE: `lottery_api/models/unified_predictor.py` (social_wisdom_predict delegates to SocialWisdomPredictor.predict; reuse the selected pure callable, not the facade's logging/special-number work)
- `tools/quick_ml_predict.py` — EXISTING_PARTIAL_EQUIVALENT: `tools/advanced_prediction_engine.py` (overlapping statistical features but not the same ten-weight QuickML formula)
- `tools/big_lotto_exhaustive_audit.py` — NO_EXISTING_EQUIVALENT: `tools/big_lotto_exhaustive_audit.py` (only the batch auditor identity was found; no genuine one-draw callable or adapter exists)
- `lottery_api/models/zone_split.py` — EXISTING_PARTIAL_EQUIVALENT: `tools/zone_split_optimizer.py` (multiple zone variants exist, but their pools/weighting differ from ZoneSplitStrategy.generate_bets); `src/engine/strategies/ZoneSplitStrategy.js` (front-end zone strategy is a separate implementation surface, not a ReplayStrategyAdapter); `lottery_api/routes/prediction.py` (runtime route calls the exact selected factory; no replay adapter exists)

## Shared architecture

The design references `ReplayStrategyAdapter`, `_StrategyMeta`, `_validate_numbers`, `RejectPrediction`, `InsufficientHistory`, `InvalidOutput`, and `UnsupportedLotteryType`. History is strictly before target; prediction reads no DB/file/env/network state; the result is one validated six-number BIG_LOTTO bet with special `None`. This static design assigns no lifecycle. The current registry source declares matching Social Wisdom and ZoneSplit IDs; reconcile those existing sources before any future implementation and do not create duplicate IDs.

## Implementation waves

- Wave 1: `lottery_api/models/social_wisdom_predictor.py` — safe lazy direct reuse.
- Wave 2: `lottery_api/models/zone_split.py` — local deterministic RNG reimplementation.
- Wave CTO: `tools/advanced_prediction_engine.py`, `tools/quick_ml_predict.py` — select Advanced mode/dependency identity and decide QuickML bounds-repair identity.
- Wave REJECTED: `tools/big_lotto_exhaustive_audit.py` — outcome-aware audit is not a predictor.

## CTO decisions

- Select one AdvancedPredictionEngine mode and decide whether optional sklearn/XGBoost availability is identity-defining or prohibited.
- QuickML decision 1: reject the historical QuickML identity entirely; or
- QuickML decision 2: authorize a separately identified bounds-repaired QuickML strategy; and
- QuickML decision 3: specify the corrected loop boundary and parity contract.
- BigLottoAuditor remains rejected; any new hot/cold predictor must have a new identity and separate authorization.

## Future test plan

- Assert strictly-prior cutoff, canonical ordering, minimum history, unsupported lottery mapping and one-bet storage.
- Reconcile the existing Social Wisdom and ZoneSplit source implementations with these designs before any further adapter work; do not create duplicate strategy IDs. QuickML parity remains BLOCKED because the pinned callable has no successful legacy output.
- Preserve an order-asymmetric QuickML defect vector so newest/oldest history drift cannot be hidden by repeated draws.
- Run ZoneSplit in separate processes and assert identical tickets, local-RNG isolation and first-zone membership.
- Monkeypatch DB/file/env/network APIs to fail and prove prediction reaches none of them.
- Exercise malformed, duplicate, out-of-range and deliberate no-bet outputs through canonical exceptions.

## Non-claims

- This task creates or changes no runtime adapter, registry entry, replay row, DB state, target execution, promotion, production lifecycle or ONLINE status.
- Current source code declares matching Social Wisdom and ZoneSplit strategy IDs and status metadata; runtime state was not queried, so this is not a claim of active deployment or P541C replay readiness.
- Static design does not establish future parity or production readiness.
- Static adapter-design research only; not a runtime adapter, replay result, production-readiness claim, prediction, betting edge, or betting advice. Lottery outcomes remain random; this material is for research and entertainment only.
