# P1-6C Replay Dedicated DB Fixture Policy Report

Date: 2026-05-08  
Branch: `main`  
Workspace: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge`

## 1. Executive Summary
P1-6C completed as a policy/design round (no fixture implementation, no DB commit).  
Based on current tests and schema usage, the lowest-risk next step is:

1. keep current fixture-gated dedicated lane behavior (fail-fast when unavailable),
2. implement a **minimal synthetic SQLite fixture generator** in next round (P1-6D),
3. keep secure artifact path as fallback for parity checks against production-like snapshots.

## 2. P1-6A / P1-6B Baseline
- P1-6A delivered local/script matrix with explicit dedicated DB fail-fast.
- P1-6B wired GitHub Actions workflow:
  - default lane (`scripts/run_replay_ci_default_validation.py`)
  - dedicated lane (`scripts/run_replay_ci_db_validation.py`) via `workflow_dispatch`.
- Current main commits include:
  - `4b76af8 chore: harden replay requires_db CI path`
  - `58e6222 chore: add replay governance CI workflow`

## 3. Current Dedicated DB Lane Behavior
- Dedicated lane currently runs only via `workflow_dispatch`.
- DB path can be supplied via input `db_path` -> env `LOTTERY_TEST_DB_PATH`.
- If DB is unavailable, dedicated script exits code `2` with explicit error.
- If tests still skip in dedicated mode, script exits code `3`.
- Therefore dedicated lane does not silently skip and does not fake pass.

## 4. requires_db Dependency Map
Detailed machine-readable map:
- `outputs/replay/p1_6c_requires_db_dependency_map_20260508.json`

Summary:
- requires_db tests are concentrated in three files:
  1. `tests/test_strategy_replay_history_cutoff_integrity.py` (3 tests)
  2. `tests/test_replay_freshness_cadence.py::TestFreshnessCadence` (4 tests)
  3. `tests/test_replay_api_contract.py` classes:
     - `TestFreshnessContract` (10 tests)
     - `TestSummaryContract` (7 tests)
     - `TestHistoryContract` (8 tests)
- Total DB-lane count: 32 tests.
- Core table dependency is stable and narrow:
  - `strategy_replay_runs`
  - `strategy_prediction_replays`
- Queries are read-only and focus on shape/integrity/cadence, not replay generation.

## 5. Required Schema / Data Summary
Schema source inspected:
- `lottery_api/database.py` CREATE TABLE definitions for:
  - `strategy_replay_runs`
  - `strategy_prediction_replays`

Minimum semantic data requirements inferred from test SQL:
1. `strategy_replay_runs` must include DONE rows for:
   - `BIG_LOTTO`, `POWER_LOTTO`, `DAILY_539`
   with `started_at` within 14 days.
2. Optional `FAILED_LEGACY` rows can exist and must not satisfy DONE cadence.
3. `strategy_prediction_replays` rows must satisfy:
   - non-null/valid `history_cutoff_draw` (except documented FAILED_LEGACY exception),
   - `history_cutoff_draw < target_draw`,
   - for non-error rows: populated predicted/actual/hit fields.
4. Route contract tests require output shape consistency from replay routes, but not large historical volume.

Conclusion: full historical DB is not strictly required to satisfy current requires_db contract/integrity checks.

## 6. Fixture Source Options

### Option A — Secure Artifact Fixture
Examples:
- private release asset
- encrypted package downloaded in dedicated lane
- CI secret-backed URL

Pros:
- high parity with production-like snapshot
- minimal test code changes

Risks:
- artifact custody and rotation overhead
- leakage/compliance risk if dataset handling is weak
- stale artifact drift unless versioned and audited

Suitability:
- good as secondary verification lane; not ideal as first minimal hardening step.

CI impact:
- can enforce dedicated lane fully once artifact retrieval is reliable.

### Option B — Local Controlled Fixture Path
Examples:
- `workflow_dispatch` input `db_path`
- local `LOTTERY_TEST_DB_PATH`

Pros:
- already implemented and operational
- zero repository data exposure
- strong manual auditability

Risks:
- reproducibility depends on operator-provided file
- not deterministic across contributors unless fixture spec is standardized

Suitability:
- good interim control mechanism; weak as long-term automated gate by itself.

CI impact:
- remains manually triggerable and non-faking, but not fully standardized.

### Option C — Minimal Synthetic SQLite Fixture
Examples:
- script-generated temporary sqlite DB with only required schema + deterministic seed rows

Pros:
- deterministic and reproducible
- no real DB distribution risk
- smallest governance surface
- strong fit for current requires_db dependency profile

Risks:
- fixture/schema drift if schema evolves
- may miss issues only visible in large/real datasets

Suitability:
- best next step for low-risk controlled enforcement.

CI impact:
- enables dedicated lane to run deterministically in CI without real DB binary.

## 7. Recommended Fixture Policy
Recommended policy (lowest risk, current repo state):

1. **Primary path (P1-6D): Option C minimal synthetic fixture**
   - Generate ephemeral sqlite file during dedicated lane.
   - Use only replay tables and deterministic test-safe rows.
   - No strategy output claims; no active strategy state; no production writes.

2. **Fallback path: Option B local controlled path remains**
   - Keep `db_path` + `LOTTERY_TEST_DB_PATH` entrypoint for manual operations.

3. **Phase-2 path: Option A secure artifact parity run (optional)**
   - Add periodic parity check against controlled snapshot only after governance controls are defined.

## 8. Why This Does Not Fake Pass
- Dedicated script already fails when fixture missing (`exit 2`).
- Dedicated script fails when requires_db tests still skip (`exit 3`).
- Policy requires fixture provisioning before expecting dedicated lane green.
- No route exists that silently converts dedicated lane into skip-green behavior.

## 9. CI Enforcement Roadmap
1. **Now (current):**
   - default lane on PR/push
   - dedicated lane manual + fixture-gated fail-fast
2. **P1-6D:**
   - add minimal fixture generator script + workflow hook
   - dedicated lane becomes deterministic runnable in CI
3. **After P1-6D stabilization:**
   - consider promoting dedicated lane into stronger gate policy
4. **Optional later:**
   - add secure artifact parity lane for production-like drift detection

## 10. Validation / Inspection Evidence
Commands executed:

1. Default validation script:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py
```
Result: `57 passed, 32 skipped, 1 warning`

2. Dedicated DB behavior check:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_db_validation.py
```
Result: exit code `2`, explicit fixture unavailable error

3. requires_db collection:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_freshness_cadence.py \
  tests/test_replay_api_contract.py \
  --collect-only -q
```
Result: `36 tests collected` (includes DB + non-DB class in freshness file)

4. Schema reference:
- `lottery_api/database.py` replay table definitions inspected.

## 11. Files Changed
- `outputs/replay/p1_6c_db_fixture_policy_20260508.md`
- `outputs/replay/p1_6c_requires_db_dependency_map_20260508.json`

## 12. What Was Not Changed
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- no requires_db guard relaxation

## 13. Remaining Risks
1. Minimal fixture can diverge from evolving schema unless generator is tied to schema checks.
2. Route-level contract tests may later require additional columns/data relationships.
3. Dedicated lane remains fixture-gated until controlled fixture implementation lands.

## 14. Follow-up Tasks
1. Implement P1-6D minimal synthetic fixture generator and CI wiring.
2. Add fixture integrity checks (schema version/hash) to prevent stale fixture drift.
3. Define whether dedicated lane should become required branch gate after stabilization.

## 15. P1-6D Ready-to-Run Prompt
```text
# ROLE
你是 LotteryNew 的 DB Fixture Implementation Worker（P1-6D Executor），向 CTO agent 回報。

# TASK
P1-6D — Implement Minimal Synthetic SQLite Fixture for Replay Dedicated DB CI Lane

# PRIMARY GOAL
在不提交任何 DB binary 的前提下，建立可在 CI 產生的最小 sqlite fixture，
讓 dedicated DB lane 可穩定執行 requires_db tests，且不得 fake pass。

# INPUT BASELINE
- 已有 workflow: .github/workflows/replay-governance-ci.yml
- 已有 scripts:
  - scripts/run_replay_ci_default_validation.py
  - scripts/run_replay_ci_db_validation.py
- 已有 policy:
  - outputs/replay/p1_6c_db_fixture_policy_20260508.md
  - outputs/replay/p1_6c_requires_db_dependency_map_20260508.json

# REQUIRED IMPLEMENTATION
1. 新增 fixture generator script（例如 scripts/build_replay_test_fixture.py）
   - 產生 temporary sqlite DB
   - schema 至少含:
     - strategy_replay_runs
     - strategy_prediction_replays
   - seed deterministic rows，滿足:
     - 三種 lottery DONE run within 14 days
     - 可選 FAILED_LEGACY row
     - replay rows具備 history_cutoff < target_draw
     - non-error rows具備 predicted/actual/hit
2. 更新 workflow dedicated lane：
   - 先建 fixture
   - 設定 LOTTERY_TEST_DB_PATH 指向該 fixture
   - 再跑 scripts/run_replay_ci_db_validation.py
3. dedicated lane 不得 skip requires_db tests；若 skip 需 fail。

# HARD RULES
- 不得 commit *.db / *.db-wal / *.db-shm
- 不得修改 Replay API 行為
- 不得修改產品功能
- 不得放寬 requires_db guard
- 不得做 replay generation / strategy mining / edge discovery

# VALIDATION
- 跑 default script smoke
- 跑 dedicated script（有 fixture）應 PASS 且 zero-skip
- collect-only 保留證據

# REQUIRED REPORT
建立 outputs/replay/p1_6d_minimal_fixture_implementation_20260508.md
至少包含：
1. Fixture schema summary
2. Seed data summary
3. Dedicated lane run result
4. Why no fake pass
5. Files changed
6. Risks / follow-up

# COMMIT MESSAGE
chore: add minimal replay db fixture for dedicated CI lane

# FINAL MARKER
P1_6D_MINIMAL_DB_FIXTURE_IMPLEMENTED
```

## 16. Final Recommendation
Proceed with P1-6D using a deterministic minimal synthetic fixture as the primary controlled source.  
Keep dedicated DB lane fixture-gated and fail-fast until that implementation is merged.

Compliance note:
dedicated DB lane remains fixture-gated until controlled fixture is implemented.
