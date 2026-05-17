# P5 Replay Source of Truth Policy

1. Replay runtime canonical source is DB, not JSON governance artifacts.
2. P0/P1/P3 artifacts are dry-run and governance inputs; they are not runtime truth.
3. The local `lottery_api/data/lottery_v2.db` file is not deployable source-of-truth by itself because it is ignored by git and not promoted through a documented migration/seed path.
4. Production replay rows should come from a deployment DB that is produced by explicit promotion policy, not from ad hoc local state.
5. For historical reconstruction, choose one of migration, seed, artifact promotion, or controlled DB apply; compare their operational risk before adopting one, but do not execute any of them in P5.
6. P4 replay page acceptance should validate the deployable source, never only the local checkout.
7. P6 DAILY_539 torch blocker remains dependent on the same deployment source-of-truth decision.

## Decision
- canonical_runtime_source: DB
- deployment_safe: False
- local_only_risk: True
- requires_migration_or_seed_policy: True
- requires_artifact_promotion_policy: True

## Before Replay Page Acceptance
The team should first formalize the deployable DB promotion path so that acceptance can run against the same source that production will actually serve.
