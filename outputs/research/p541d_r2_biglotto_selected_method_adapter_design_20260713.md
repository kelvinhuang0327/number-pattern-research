# P541D_R2 BIG_LOTTO Selected-Method Adapter Design (No DB)

## Executive summary

Pinned static design at `9572d994e94fae44cf7730297e7537c0901d5a78` for exactly five P541C_R2-selected methods. Three designs are implementation-ready, one requires a CTO identity decision, and one is rejected as not an adapter candidate. No selected module was imported or executed; no DB, data, runtime, network, environment, registry or lifecycle state was accessed or changed.

## Five-method decision table

| Method | Equivalent audit | Design status | Ready | Proposed strategy |
|---|---|---|---:|---|
| `tools/advanced_prediction_engine.py` | EXISTING_PARTIAL_EQUIVALENT | CTO_REVIEW_REQUIRED | no | `—` |
| `lottery_api/models/social_wisdom_predictor.py` | EXISTING_EQUIVALENT_REUSE | LAZY_DIRECT_WRAPPER_READY | yes | `biglotto_social_wisdom_anti_popularity` |
| `tools/quick_ml_predict.py` | EXISTING_PARTIAL_EQUIVALENT | ADAPTER_OWNED_PURE_EXTRACTION_READY | yes | `biglotto_quickml_advanced_ensemble` |
| `tools/big_lotto_exhaustive_audit.py` | NO_EXISTING_EQUIVALENT | NOT_AN_ADAPTER_CANDIDATE | no | `—` |
| `lottery_api/models/zone_split.py` | EXISTING_PARTIAL_EQUIVALENT | DETERMINISTIC_REIMPLEMENTATION_READY | yes | `biglotto_zone_split_3bet_bet1` |

## Detailed method sections

### `tools/advanced_prediction_engine.py`

- Source identity: blob `5c72f7e87de6d2f7721d7fc9eb7eb57f4e848744`, 24006 bytes, SHA-256 `f92be0a25fc2da83eb9d999081a80d59c4c9af089edcefcdf44f6f3cfc16a8ce`; UTF-8/AST `PASS/PASS`.
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

- Source identity: blob `1a1f4119f4ade1b5605a988f595c7ed8300e6a40`, 12772 bytes, SHA-256 `a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b`; UTF-8/AST `PASS/PASS`.
- Decision: **LAZY_DIRECT_WRAPPER_READY** — SocialWisdomPredictor.predict is import-safe, deterministic and already accepts in-memory history. The random generate_8_bets and empty-history random branch of predict_with_balance are explicitly excluded.
- Entry point: `SocialWisdomPredictor.predict(history, pick_count=6)`.
- Equivalent audit: EXISTING_EQUIVALENT_REUSE; social_wisdom_predict delegates to SocialWisdomPredictor.predict; reuse the selected pure callable, not the facade's logging/special-number work
- History/cutoff: Canonical replay supplies oldest-to-newest; wrapper passes reversed(history[-50:]) because the legacy callable treats history[:50] as newest-first. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: Use predict() only; never call predict_with_balance(empty history) or generate_8_bets().
- External state/import plan: Lazy-import only SocialWisdomPredictor inside _call_strategy; module has no import-time executable output or I/O.
- Normalization/validation: copy strictly-prior history, keep last 50, reverse to newest-first → the returned sorted list[int]; ignore facade confidence/meta/special; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: direct-call parity — exact six-number equality.
- Blockers/CTO decisions: none.

### `tools/quick_ml_predict.py`

- Source identity: blob `36cf12dcef80d7f0bada22e024336eb22f8bfee5`, 11213 bytes, SHA-256 `8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80`; UTF-8/AST `PASS/PASS`.
- Decision: **ADAPTER_OWNED_PURE_EXTRACTION_READY** — The constructor's CSV read and printing cannot enter replay. The selected deterministic predict_advanced_ensemble formula can be extracted unchanged to a pure in-memory helper, including newest-first ordering and stable numeric tie order.
- Entry point: `adapter-owned pure extraction of QuickMLPredictor.predict_advanced_ensemble(top_n=10)`.
- Equivalent audit: EXISTING_PARTIAL_EQUIVALENT; overlapping statistical features but not the same ten-weight QuickML formula
- History/cutoff: Canonical oldest-to-newest history is truncated to the last 50 then reversed; this preserves legacy DataFrame.head() newest-first semantics. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: predict_advanced_ensemble contains no random call; preserve ascending number tie-breaks.
- External state/import plan: Never import or construct QuickMLPredictor in replay. Extract the selected scoring formula into the future adapter module with source/blob provenance comments.
- Normalization/validation: list[dict] -> newest-first list[list[int]] without pandas or CSV → take ranked top six, sorted; discard confidence/top_n metadata; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: controlled legacy oracle — future isolated parity test only, with in-memory-vs-legacy fixture conversion outside prediction; never a runtime temp CSV.
- Blockers/CTO decisions: none.

### `tools/big_lotto_exhaustive_audit.py`

- Source identity: blob `ff9efe54d3519c47798c9f6b47a5e3dc44f0b730`, 3292 bytes, SHA-256 `694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c`; UTF-8/AST `PASS/PASS`.
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

- Source identity: blob `5ce1ce023cab846791550bd7240106600ee9b95e`, 3916 bytes, SHA-256 `b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211`; UTF-8/AST `PASS/PASS`.
- Decision: **DETERMINISTIC_REIMPLEMENTATION_READY** — Preserve the exact three-zone boundaries, overlap=2 and first-bet selection, but replace global random.sample with a local random.Random instance seeded from canonical strategy identity plus strictly-prior causal history. No historical signal or equivalent strategy is borrowed.
- Entry point: `deterministic reimplementation of get_zone_split_predictor('BIG_LOTTO', 3), first bet only`.
- Equivalent audit: EXISTING_PARTIAL_EQUIVALENT; multiple zone variants exist, but their pools/weighting differ from ZoneSplitStrategy.generate_bets; front-end zone strategy is a separate implementation surface, not a ReplayStrategyAdapter; runtime route calls the exact selected factory; no replay adapter exists
- History/cutoff: Canonical oldest-to-newest history is retained only for seed material; all rows must be strictly prior and canonicalized by draw/date/numbers. Every input draw must be strictly before the target draw; reject equal/future rows.
- Randomness: Build UTF-8 canonical JSON of {strategy_id, lottery_type, causal_history:[{draw,date,numbers}]}; SHA-256 it; seed local random.Random with the full digest integer; sample each legacy zone sequentially; record bet 1 only. Never seed or call global RNG.
- External state/import plan: Do not import the selected module because it uses global random. Reimplement only its 1..49, three-zone, overlap=2 candidate-pool construction in the future adapter.
- Normalization/validation: canonical history used only in deterministic seed preimage → first of three sequential local-RNG bets; validate and discard other bets/coverage metadata; Pass the flat result to repository-native _validate_numbers(numbers, 'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted.
- Parity oracle: algorithm parity — same pools and sample count; deterministic seed intentionally replaces nondeterministic global RNG.
- Blockers/CTO decisions: none.

## Duplicate/equivalent findings

- `tools/advanced_prediction_engine.py` — EXISTING_PARTIAL_EQUIVALENT: `tools/quick_ml_predict.py` (overlapping frequency/hot-cold/statistical features, not exact engine identity); `lottery_api/models/p42_wave3_biglotto_adapters.py` (native deterministic scoring precedent, not an equivalent adapter)
- `lottery_api/models/social_wisdom_predictor.py` — EXISTING_EQUIVALENT_REUSE: `lottery_api/models/unified_predictor.py` (social_wisdom_predict delegates to SocialWisdomPredictor.predict; reuse the selected pure callable, not the facade's logging/special-number work)
- `tools/quick_ml_predict.py` — EXISTING_PARTIAL_EQUIVALENT: `tools/advanced_prediction_engine.py` (overlapping statistical features but not the same ten-weight QuickML formula)
- `tools/big_lotto_exhaustive_audit.py` — NO_EXISTING_EQUIVALENT: `tools/big_lotto_exhaustive_audit.py` (only the batch auditor identity was found; no genuine one-draw callable or adapter exists)
- `lottery_api/models/zone_split.py` — EXISTING_PARTIAL_EQUIVALENT: `tools/zone_split_optimizer.py` (multiple zone variants exist, but their pools/weighting differ from ZoneSplitStrategy.generate_bets); `src/engine/strategies/ZoneSplitStrategy.js` (front-end zone strategy is a separate implementation surface, not a ReplayStrategyAdapter); `lottery_api/routes/prediction.py` (runtime route calls the exact selected factory; no replay adapter exists)

## Shared architecture

Future implementations must reuse `ReplayStrategyAdapter`, `_StrategyMeta`, `_validate_numbers`, `RejectPrediction`, `InsufficientHistory`, `InvalidOutput`, and `UnsupportedLotteryType`. History is strictly before target; prediction reads no DB/file/env/network state; the result is one validated six-number BIG_LOTTO bet with special `None`. This design assigns no lifecycle and does not imply ONLINE status.

## Implementation waves

- Wave 1: `lottery_api/models/social_wisdom_predictor.py` — safe lazy direct reuse.
- Wave 2: `tools/quick_ml_predict.py` — pure in-memory extraction and parity vectors.
- Wave 3: `lottery_api/models/zone_split.py` — local deterministic RNG reimplementation.
- Wave CTO: `tools/advanced_prediction_engine.py` — select exact mode/dependency identity.
- Wave REJECTED: `tools/big_lotto_exhaustive_audit.py` — outcome-aware audit is not a predictor.

## CTO decisions

- Select one AdvancedPredictionEngine mode and decide whether optional sklearn/XGBoost availability is identity-defining or prohibited.
- BigLottoAuditor remains rejected; any new hot/cold predictor must have a new identity and separate authorization.

## Future test plan

- Assert strictly-prior cutoff, canonical ordering, minimum history, unsupported lottery mapping and one-bet storage.
- Run exact synthetic vectors and parity oracles for Social Wisdom and QuickML.
- Run ZoneSplit in separate processes and assert identical tickets, local-RNG isolation and first-zone membership.
- Monkeypatch DB/file/env/network APIs to fail and prove prediction reaches none of them.
- Exercise malformed, duplicate, out-of-range and deliberate no-bet outputs through canonical exceptions.

## Non-claims

- No runtime adapter, registry entry, replay row, DB access, target execution, promotion, production lifecycle or ONLINE status exists from this task.
- Static design does not establish future parity or production readiness.
- Static adapter-design research only; not a runtime adapter, replay result, production-readiness claim, prediction, betting edge, or betting advice. Lottery outcomes remain random; this material is for research and entertainment only.
