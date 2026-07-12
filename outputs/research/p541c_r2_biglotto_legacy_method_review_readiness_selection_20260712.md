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
| safe_confirmed_method | 12 |
| safe_identity_unresolved_needs_cto_review | 10 |
| needs_adapter_or_refactor_before_readiness | 0 |
| needs_cto_review | 448 |
| excluded_from_replay | 110 |

## Verified Input Provenance

- Implementation base commit: `137dbff5938a74117bb33a4a3db5ccc5de2e8454`
- Input: `outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json` — 10,478,598 bytes, SHA-256 `9c9a28d871113c63f3de024f056d7a4e2d6949e934e76da161a9c891e662103f`, verification **PASS**
- Fail-closed behavior: any input hash, schema, record, or contract mismatch aborts generation.

## Bucket Definitions

- **safe_confirmed_method**: P541B_R2 risk_level=low (low_risk_eligible=True) AND P541B historical is_actual_prediction_method=True. Safety-clear and identity-confirmed; the only bucket eligible for the shortlist.
- **safe_identity_unresolved_needs_cto_review**: P541B_R2 risk_level=low AND P541B historical is_actual_prediction_method=unknown. Safety-clear but identity itself is unresolved; routed to CTO review for identity confirmation only, never silently promoted to the shortlist.
- **needs_adapter_or_refactor_before_readiness**: P541B_R2 risk_level=medium AND P541B historical is_actual_prediction_method=True. Confirmed method with a bounded, non-high-risk blocker needing adapter or refactor work.
- **needs_cto_review**: P541B_R2 risk_level=unknown (any identity), OR risk_level=medium with unresolved/negative identity. Unresolved risk is never resolved to safe; carried through to human review verbatim.
- **excluded_from_replay**: P541B_R2 risk_level=high (any identity, safety-blocking regardless of confidence), OR P541B historical recommended_action is mark_duplicate/mark_not_strategy/mark_deprecated, OR risk_level=low with is_actual_prediction_method=False (safe but not a prediction method).

## Shortlist Rule

BUCKET_SAFE_CONFIRMED members only, deduplicated by method_id, round-robin diversified across method_family, capped at 20, sorted deterministically by method_id within each family. Never padded: if fewer candidates qualify, the shortlist is exactly that smaller set.

## Shortlist (n=12)

| method_id | method_family | source_path | reason |
|---|---|---|---|
| lottery_api/models/autogluon_model.py | ML_like | lottery_api/models/autogluon_model.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/social_wisdom_predictor.py | folklore | lottery_api/models/social_wisdom_predictor.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| tools/quick_ml_predict.py | frequency | tools/quick_ml_predict.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/big_lotto_optimizer.py | hot_cold | lottery_api/models/big_lotto_optimizer.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| tools/big_lotto_exhaustive_audit.py | report | tools/big_lotto_exhaustive_audit.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/core_satellite.py | unknown | lottery_api/models/core_satellite.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/p47_wave4_powerlotto_adapters.py | utility | lottery_api/models/p47_wave4_powerlotto_adapters.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/zone_split.py | zone | lottery_api/models/zone_split.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/bayesian_ensemble.py | ML_like | lottery_api/models/bayesian_ensemble.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| tools/analyze_theoretical_vs_actual.py | unknown | tools/analyze_theoretical_vs_actual.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| lottery_api/models/optimized_ensemble.py | ML_like | lottery_api/models/optimized_ensemble.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |
| tools/advanced_prediction_engine.py | ML_like | tools/advanced_prediction_engine.py | P541B_R2: risk_level=low (STATIC_LOW_RISK_ELIGIBLE); P541B historical: confirmed actual prediction method. Safe and identity-confirmed. |

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
  - Bucket/priority assignment is a deterministic function of P541B_R2's own risk evidence and P541B's historical identity fields; it is a triage aid for the next task, not a safety guarantee.
- **disclaimer**: Historical legacy method review and replay-readiness selection only; not a prediction, betting edge, future-winning, or production-readiness claim.
