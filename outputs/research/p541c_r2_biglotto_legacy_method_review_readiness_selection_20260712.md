# P541C_R2 — BIG_LOTTO Legacy Method Review & Replay-Readiness Selection

> generated_at: 2026-07-12T00:00:00+00:00
> task_id: P541C_R2_BIG_LOTTO_LEGACY_METHOD_REVIEW_READINESS_SELECTION_REPLACEMENT

**Disclaimer:** Historical legacy method review and replay-readiness selection only; not a prediction, betting edge, future-winning, or production-readiness claim.

## Supersedes

- task_id: `P541C_BIG_LOTTO_LEGACY_METHOD_REVIEW_AND_REPLAY_READINESS_SELECTION`
- overwrite_policy: HISTORICAL_ARTIFACTS_PRESERVED
- reason: Pre-R2 P541C consumed the retired boolean-only P541B v1 evidence schema, which has no unknown state and coerces missing/absent evidence flags to low risk. Cross-checked against P541B_R2: 135/140 (96%) of its shortlist- eligible pool and 19/20 of its published shortlist are no longer confirmed low-risk under the fail-closed P541B_R2 audit.

## Summary

| Metric | Count |
|---|---|
| total_reviewed_from_p541b_r2 | 580 |
| ready_for_replay_readiness_now | 0 |
| needs_adapter_before_readiness | 12 |
| needs_refactor_before_readiness | 0 |
| needs_cto_review | 458 |
| exclude_from_replay | 110 |

## Contract Reconciliation

- task_id: `P541C_R2_PR686_CONTRACT_RECONCILIATION_R1`
- status: **PASS**
- reconciled_invariant: P541B_R2 safety risk and historical replay readiness are orthogonal: risk_level=low does not erase runnable_status or required change.
- prior_drift: PR #686 v1 labeled 12 low-risk confirmed methods safe_confirmed_method with required_change_before_replay=none even though all 12 upstream records say runnable_status=needs_adapter_wrapper.

## Verified Input Provenance

- Implementation base commit: `137dbff5938a74117bb33a4a3db5ccc5de2e8454`
- Input: `outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json` — 10,478,598 bytes, SHA-256 `9c9a28d871113c63f3de024f056d7a4e2d6949e934e76da161a9c891e662103f`, verification **PASS**
- Fail-closed behavior: any input hash, schema, record, or contract mismatch aborts generation.

## Bucket Definitions

- **ready_for_replay_readiness_now**: P541B_R2 risk_level=low, historical identity confirmed, and historical runnable_status=runnable_with_existing_adapter. No readiness change remains.
- **needs_adapter_before_readiness**: Confirmed method whose historical runnable_status requires an adapter wrapper or parameterization. Low-risk/high-confidence members alone may enter the shortlist.
- **needs_refactor_before_readiness**: Confirmed method whose historical runnable_status requires pure-function or DB-safety refactoring. High safety risk remains excluded.
- **needs_cto_review**: P541B_R2 risk_level=unknown (any identity), unresolved historical identity at low/medium risk, or a confirmed method with a non-actionable readiness status. Unresolved risk is never resolved to safe.
- **exclude_from_replay**: P541B_R2 risk_level=high (any identity, safety-blocking regardless of confidence), OR P541B historical recommended_action is mark_duplicate/mark_not_strategy/mark_deprecated, OR risk_level=low with is_actual_prediction_method=False (safe but not a prediction method).

## Shortlist Rule

needs_adapter_before_readiness members only with P541B_R2 risk_level=low, confirmed method identity, and historical confidence=high; deduplicated by method_id, round-robin diversified across method_family, capped at 20, sorted deterministically by method_id within each family. Never padded: if fewer candidates qualify, the shortlist is exactly that smaller set.

## Shortlist (n=5)

| method_id | method_family | source_path | reason |
|---|---|---|---|
| tools/advanced_prediction_engine.py | ML_like | tools/advanced_prediction_engine.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method with runnable_status=needs_adapter_wrapper. Readiness requirement preserved as adapter_wrapper. |
| lottery_api/models/social_wisdom_predictor.py | folklore | lottery_api/models/social_wisdom_predictor.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method with runnable_status=needs_adapter_wrapper. Readiness requirement preserved as adapter_wrapper. |
| tools/quick_ml_predict.py | frequency | tools/quick_ml_predict.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method with runnable_status=needs_adapter_wrapper. Readiness requirement preserved as adapter_wrapper. |
| tools/big_lotto_exhaustive_audit.py | report | tools/big_lotto_exhaustive_audit.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method with runnable_status=needs_adapter_wrapper. Readiness requirement preserved as adapter_wrapper. |
| lottery_api/models/zone_split.py | zone | lottery_api/models/zone_split.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method with runnable_status=needs_adapter_wrapper. Readiness requirement preserved as adapter_wrapper. |

## Recommended Next Task

`P541D_R2_BIG_LOTTO_ADAPTER_DESIGN_OR_CTO_REVIEW_NO_DB_WRITE`

## Provenance and Limits

- **method**: Static, read-only re-bucketing of exactly one pinned P541B_R2 artifact (which already embeds historical P541B v1 identity fields per record). Strict JSON rejects duplicate keys and non-finite values. Every source is a repository-contained, non-symlink Python file whose size/SHA-256 is recorded per decision. No source is imported or executed; no DB access, replay generation, or scoring/promotion gate.
- **p541b_r2_artifact_consumed**:
  - outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json
- **not_performed_by_this_task**:
  - No DB write, migration, backfill, or replay row generation.
  - No OOS evaluator or strategy scoring/promotion gate.
  - No recomputation of P536-P541B_R2 artifacts.
  - No route/API/UI changes.
  - No adapter code was written; only the decision to route a method to needs_adapter_or_refactor_before_readiness / needs_cto_review.
- **known_limits**:
  - needs_cto_review records (from unknown risk or unresolved/negative identity at medium risk) were not further resolved; P541B_R2's own evidence already represents the limit of static analysis.
  - Source identity verification reads raw bytes only to compute size and SHA-256; this does not constitute new semantic or runtime analysis.
  - Bucket/priority assignment is a deterministic function of P541B_R2's risk evidence plus P541B's historical identity, runnable_status, and confidence fields; it is a triage aid for the next task, not a safety guarantee.
- **disclaimer**: Historical legacy method review and replay-readiness selection only; not a prediction, betting edge, future-winning, or production-readiness claim.
