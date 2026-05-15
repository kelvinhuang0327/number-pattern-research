# Phase 4 Locked Manifest

Date: 2026-05-10
Scope: P0 Replay clean-branch rebuild only. Include only files required for replay-dedicated-db-validation and DEBT-001 import cleanup. Exclude H6 monitoring / rollback work, UI product expansion, catalog promotion execution, and lifecycle expansion work that is outside this manifest.

## Three-Source Resolution

Sources reviewed:
- Handover / roadmap: `00-LotteryPlan/20260510/lottery_roadmap_20260510.md`
- Source checkout state: `git status --short` plus recent local files in the noisy LotteryNew checkout
- Remote feature tree: `origin/feature/phase4-required-check-20260509`

Decision rule:
- INCLUDE only if the file is necessary for the Phase 4 required-check path and is consistent with the handoff + local validated source.
- EXCLUDE if the file is lifecycle/UI/catalog scope, unrelated noise, or not needed for the required-check path.

## Locked Manifest

| Path | SHA-256 | Source | Justification |
|---|---|---|---|
| `.github/workflows/replay-governance-ci.yml` | `79a69e79c6a6ec33e74951985d6963c44705bd79f061d603c5d9176075a061b2` | git-head | Required CI entrypoint for default and dedicated replay validation lanes. |
| `lottery_api/models/replay_strategy_registry.py` | `8cbb9fce9b1eaf003561f5d4add564d26bd37b827f21a03e53f5449ae57a421f` | worktree | Needed by replay fixture validation and the replay route import-cleanup check. |
| `lottery_api/routes/replay.py` | `d640b782a3601d630ce25c3f0fa1da66a68e52b0dfb9e2e65fb77666a3475c6f` | worktree | Anchor for replay import-cleanup coverage; required by the Phase 4 DB validation path. |
| `outputs/replay/p0_replay_lifecycle_coverage_20260509.md` | `229aee85d9dc3498313d8913cb8bcacce5314bd94acbcbb75d144e1922dc05ef` | worktree | Evidence artifact for Phase 4 replay validation context. |
| `outputs/replay/p0_replay_lifecycle_schema_diff_20260509.json` | `33c1057749166a10d7d6b724fc44b508d237a36d07f0f9d5be072569550b65de` | worktree | Evidence artifact for fixture/schema alignment used by the dedicated lane. |
| `outputs/replay/p0_replay_lifecycle_ui_20260509.md` | `71707b826881560b4c0012ae703bb3cbe49d103a669c3ba0c84583d57b1f104a` | worktree | Evidence artifact preserved with the Phase 4 replay set; no behavior change. |
| `scripts/build_replay_test_fixture.py` | `e537f8d17735820bad5973151985fe34881b50986ad5e5499299fae0841b61e7` | worktree | Builds the isolated synthetic DB fixture for the dedicated replay validation lane. |
| `scripts/run_replay_ci_db_validation.py` | `0723e34ea1af07ae1ad0af15948cde9eea9b6c1ca6b83fd67c10f410efa0e3c5` | worktree | Executes the dedicated DB lane against the synthetic fixture; core Phase 4 validation runner. |
| `scripts/run_replay_ci_default_validation.py` | `3a8de30a309930c9b0d1c8a0f5d52a13b0f50df5458a71c9f342b121b4d7fd55` | git-head | Default replay validation wrapper used by the governance workflow. |
| `scripts/validate_replay_test_fixture.py` | `55ed45ab704400bdacf8b2b53621782e3796ca7d1ce2bac633a9928e70e9f338` | git-head | Fixture integrity checker used by the dedicated validation path. |
| `tests/test_no_in_function_imports.py` | `e8384c738445d0e10b48ca8ba3914da2be15f963cd49aa61d19b99f8e1237ac4` | worktree | Guards DEBT-001 import cleanup by enforcing no in-function imports in replay route code. |
| `tests/test_dedicated_db_lane.py` | `138e2ded12159042ad951012cf66f4d891c9cf438597f5d12cf883cf97fb3448` | worktree | Unit coverage for the fixture builder and dedicated DB validation path. |
| `wiki/system/replay_data_hygiene.md` | `d7ee364467d458349c9e23e2d4c051eb3f73fe2aeee877c07c38dc5bc821010b` | worktree | Governs replay audit rules; required for the validation and safety posture. |

## Exclusions

The following files were examined in one or more sources but are excluded from the locked manifest because they are outside the Phase 4 required-check scope:

- `index.html` — lifecycle/UI work, not part of the required-check rebuild.
- `tools/verify_phase4_final.py` — not required by the acceptance commands.
- `scripts/check_replay_lifecycle_drift.py` — later lifecycle hardening, not part of the required-check path.
- `tests/test_replay_api_contract.py` — earlier replay UI/API contract coverage, not required here.
- `tests/test_replay_browser_smoke.py` — browser/UI coverage, outside this rebuild scope.
- `tests/test_replay_freshness_cadence.py` — default replay freshness gate, not part of the dedicated lane rebuild.
- `tests/test_replay_lifecycle_aligned_fixture.py` — lifecycle/UI follow-up work, outside scope.
- `tests/test_replay_lifecycle_browser_e2e.py` — lifecycle browser automation, outside scope.
- `tests/test_replay_lifecycle_drift_guard.py` — later drift-guard hardening, outside scope.
- `tests/test_replay_lifecycle_multistate_fixture.py` — later lifecycle fixture expansion, outside scope.
- `tests/test_h6_cli_scripts.py` — H6 live-monitoring acceptance coverage; imports `engine.h6_live_monitor`, which is absent from the clean `origin/main` worktree and belongs to a separate H6 monitoring/rollback lane.
- `tests/test_h6_e2e_phase4.py` — H6 feedback-loop E2E coverage; requires `/api/h6-monitoring` behavior and production-monitoring dependencies, not Replay audit product readiness.
- `lottery_api/engine/h6_live_monitor.py` — source exists only in the noisy source worktree, not clean `origin/main`; adding it would expand this Replay manifest into H6 rollback-monitoring scope.
- `outputs/replay/p0_replay_commit_scope_manifest_20260508.md` — prior manifest artifact, superseded.
- `outputs/replay/p0_replay_release_handoff_20260508.md` — prior handoff artifact, superseded.
- `outputs/replay/p0_replay_lifecycle_browser_e2e_ci_*` — browser-e2e lifecycle evidence, not part of required-check rebuild.
- `outputs/replay/p0_replay_lifecycle_catalog_*` — catalog promotion planning, not part of required-check rebuild.
- `outputs/replay/p1_replay_lifecycle_*` — later lifecycle hardening / drift-guard material, out of scope for this Phase 4 rebuild.

## Locked Outcome

- Manifest file count: 13
- No DB binaries included
- No branch-protection changes included
- No production DB I/O included
- Phase 4 lock status: ACTIVE
