# P5A Replay Source Promotion Policy - 20260517

## Final Classification
P5A_REPLAY_SOURCE_PROMOTION_POLICY_COMPLETED

## P5 Input Summary
- Canonical runtime source: DB
- Deployment safe: False
- Local-only risk: True
- Required policy gaps: no deployable promotion policy, DB copies ambiguity, local ignored DB risk, fixture/runtime mismatch.

## Promotion Methods Compared
- MIGRATION: safe=True reproducible=True auditable=True requires_db_write=True human_approval=True rollback=True recommended_for_historical_reconstruction=True risk=MEDIUM
- SEED: safe=True reproducible=True auditable=True requires_db_write=True human_approval=True rollback=True recommended_for_historical_reconstruction=True risk=MEDIUM
- ARTIFACT_PROMOTION: safe=True reproducible=True auditable=True requires_db_write=False human_approval=True rollback=True recommended_for_historical_reconstruction=True risk=LOW
- CONTROLLED_DB_APPLY: safe=True reproducible=True auditable=True requires_db_write=True human_approval=True rollback=True recommended_for_historical_reconstruction=True risk=MEDIUM
- HYBRID: safe=True reproducible=True auditable=True requires_db_write=True human_approval=True rollback=True recommended_for_historical_reconstruction=True risk=MEDIUM
- UNSUPPORTED: safe=False reproducible=False auditable=False requires_db_write=False human_approval=False rollback=False recommended_for_historical_reconstruction=False risk=HIGH

## Recommended Policy
- Primary method: ARTIFACT_PROMOTION
- Secondary method: CONTROLLED_DB_APPLY
- Long-term method: MIGRATION or SEED depending deployment model
- Rationale: P0/P3 already produce auditable JSON artifacts; artifact promotion keeps reviewable diffs before a controlled DB apply, while the ignored local DB cannot be treated as source of truth.

## P4 Acceptance Dependency
- Can P4 run now: False
- Reason: Replay page acceptance must verify deployable source, not local ignored DB.

## Required Gates Before Actual DB Apply
- explicit CEO/CTO approval
- dry-run diff artifact
- rollback plan
- post-apply verification
- drift guard pass

## Safety Confirmation
- No DB write
- No draw import
- No replay row generation
- No prediction update
- No strategy execution
- No promotion executed

## Current Conclusion
The deployable path must be artifact-led first, then controlled DB apply. The ignored local DB remains non-canonical.
