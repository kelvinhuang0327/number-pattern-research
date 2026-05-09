# P1-6F Branch Protection / Required Checks Decision Report

Date: 2026-05-08  
Branch: `main`  
Workspace: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge`

## 1. Executive Summary
P1-6A through P1-6E established a replay CI stack with:
- stable default replay validation lane,
- synthetic fixture-backed dedicated DB lane,
- integrity gate + zero-skip no-fake-pass enforcement.

Decision for this round:
1. recommend `replay-default-validation` as required now.
2. keep `replay-dedicated-db-validation` in observation mode first.
3. promote dedicated lane to required only after explicit stability criteria are met.

No GitHub branch protection settings were changed in this round.

## 2. P1-6A to P1-6E Baseline
- P1-6A: local/script matrix + dedicated fail-fast
- P1-6B: workflow with default and dedicated lanes
- P1-6C: fixture policy + dependency map
- P1-6D: synthetic fixture implementation
- P1-6E: fixture integrity validator + dedicated integrity-gated flow

Current dedicated pass profile with fixture:
- `32 passed, 4 deselected, 1 warning`
- zero skipped in requires_db lane

## 3. Current CI Check Inventory

### Check A — `replay-default-validation`
- Source: `.github/workflows/replay-governance-ci.yml`
- Trigger: `pull_request`, `push` to `main`
- Runs on PR: Yes
- Runs on push-main: Yes
- workflow_dispatch only: No
- Required-check suitability: High
- Failure meaning: non-DB replay governance regression
- Rollback path: temporary policy exception only if CI outage; keep test semantics unchanged

### Check B — `replay-dedicated-db-validation`
- Trigger: `workflow_dispatch`
- Runs on PR: No (unless manual dispatch)
- Runs on push-main: No
- workflow_dispatch only: Yes
- Required-check suitability: Medium (after observation stabilization)
- Failure meaning: fixture build/integrity regression, schema drift, or requires_db regression
- Rollback path: keep non-required/manual while remediating; do not permit fake pass

### Embedded Gate — Fixture Integrity Validation
- Location: dedicated lane (`--validate-fixture`)
- Trigger: dedicated lane invocation
- Runs on PR: No (unless manual)
- Required-check suitability: tied to dedicated lane promotion
- Failure meaning: invalid/missing fixture schema/metadata/integrity
- Rollback path: remediate fixture pipeline; never bypass integrity and still claim dedicated green

## 4. Required Check Recommendation

### Recommended Required Now
1. `replay-default-validation`

Why:
- stable and already runs on PR + push
- validates non-DB replay governance behavior in DB-absent CI
- low operational complexity

### Recommended Not Required Yet
1. `replay-dedicated-db-validation`  
2. embedded fixture integrity gate (within dedicated lane)

Why:
- currently manual trigger path
- needs additional observation run history before becoming merge blocker

## 5. Observation Mode Recommendation
Dedicated lane should stay observation mode until:
- reliability trend is proven,
- failure modes are consistently triaged,
- team runbook for fixture incidents is exercised.

Observation matrix is captured in:
- `outputs/replay/p1_6f_required_checks_matrix_20260508.json`

## 6. Dedicated Lane Promotion Criteria
Recommend promotion to required only after all are met:
1. >= 5 consecutive main-branch dedicated runs PASS
2. >= 3 PR dry-runs PASS without manual patching
3. fixture integrity validator PASS each run
4. no-skip enforcement remains effective (no false green)
5. failures are classifiable/remediated within one business day

## 7. Failure Handling Policy

### Default lane fail
- Classification: replay governance regression
- Action: block PR merge until fix + rerun pass

### Dedicated lane fail (runtime/test)
- Classification: dedicated requires_db regression or fixture pipeline issue
- Action: open dedicated incident task; do not downgrade to skip-pass behavior

### Fixture integrity fail
- Classification: fixture drift/build metadata/schema issue
- Action: fail dedicated lane immediately; regenerate/fix fixture pipeline

### Missing DB / fixture build fail
- Classification: fixture availability pipeline failure
- Action: explicit fail-fast (expected behavior), investigate build path or env wiring

### Schema drift fail
- Classification: test/route-schema mismatch
- Action: update fixture schema/seed deterministically with review evidence

### Unexpected skip in dedicated lane
- Classification: no-fake-pass enforcement failure
- Action: fail lane, investigate skip source, keep blocker semantics

## 8. Rollback Policy
If CI becomes broadly blocking:
1. keep default lane required unless platform outage requires temporary exception.
2. dedicated lane may remain observation/manual while remediating fixture stack.
3. rollback must not reintroduce silent skip or fake pass in dedicated mode.
4. no rollback path should disable integrity gate while claiming dedicated success.

## 9. Branch Protection Recommendation
Policy recommendation only (no execution this round):

1. Require pull request before merge: **Yes**
2. Required status checks now: **`replay-default-validation`**
3. Require branches up to date before merging: **Yes**
4. Include administrators: **Yes**
5. Require linear history: **Optional (prefer Yes if org-wide policy aligns)**
6. Allow force pushes: **No**
7. Allow deletions: **No**

Dedicated lane recommendation:
- keep non-required during observation phase,
- promote to required after criteria in section 6 are met.

## 10. Validation Results
Executed commands:

1. Default validation:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py
```
Result:
- `57 passed, 32 skipped, 1 warning` (equivalent result accepted)

2. Build fixture:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/build_replay_test_fixture.py --output /tmp/lottery_replay_test_fixture.db
```
Result:
- fixture built with metadata v1 / schema replay-schema-v1

3. Validate fixture integrity:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/validate_replay_test_fixture.py --db /private/tmp/lottery_replay_test_fixture.db
```
Result:
- integrity PASS

4. Dedicated DB validation:
```bash
LOTTERY_TEST_DB_PATH=/tmp/lottery_replay_test_fixture.db \
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_db_validation.py --validate-fixture
```
Result:
- `32 passed, 4 deselected, 1 warning`
- zero skipped in dedicated lane

5. Missing DB fail-fast:
```bash
rm -f /tmp/lottery_replay_test_fixture_missing.db
LOTTERY_TEST_DB_PATH=/tmp/lottery_replay_test_fixture_missing.db \
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_db_validation.py --validate-fixture
```
Result:
- exit code `2`
- clear fixture unavailable error

## 11. Files Changed
- `outputs/replay/p1_6f_branch_protection_required_checks_decision_20260508.md`
- `outputs/replay/p1_6f_required_checks_matrix_20260508.json`

## 12. What Was Not Changed
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- no direct GitHub branch protection change in this round

## 13. Remaining Risks
1. dedicated lane currently manual; observation evidence must accumulate.
2. fixture schema/version drift remains a lifecycle risk.
3. promotion timing can be delayed by CI platform instability unrelated to replay logic.

## 14. Follow-up Tasks
1. run dedicated lane observation campaign and log pass/fail trends.
2. prepare promotion checklist sign-off template for CTO decision.
3. once criteria met, execute branch protection configuration change in P1-6G.

## 15. P1-6G Ready-to-Run Prompt
```text
# ROLE
你是 LotteryNew 的 CI Branch Protection Execution Worker（P1-6G Executor），向 CTO agent 回報。

# TASK
P1-6G — Execute Branch Protection Required Checks Configuration for Replay Governance CI

# GOAL
根據 P1-6F 決策，實際套用 branch protection 設定（若有足夠權限），並回傳設定證據。

# REQUIRED INPUT
- outputs/replay/p1_6f_branch_protection_required_checks_decision_20260508.md
- outputs/replay/p1_6f_required_checks_matrix_20260508.json

# IMPLEMENTATION
1. 驗證 repo/admin 權限與 branch protection API 可用性
2. 套用 required now checks:
   - replay-default-validation
3. 啟用：
   - require pull request before merge
   - require branches up to date
   - include administrators
   - disallow force push
   - disallow deletion
4. dedicated lane 維持 observation mode（暫不 required）

# EVIDENCE
- 輸出 API request/response 摘要或 UI 截圖證據
- 記錄 rollback plan（若設定失敗）

# HARD RULES
- 不修改 Replay API 或產品功能
- 不提交 DB 檔案
- 不放寬 dedicated no-fake-pass 設計

# REPORT
建立 outputs/replay/p1_6g_branch_protection_execution_20260508.md

# FINAL MARKER
P1_6G_BRANCH_PROTECTION_POLICY_APPLIED
```

## 16. Final Recommendation
Approve `replay-default-validation` as required check now; keep dedicated lane in observation mode until promotion criteria are met, then move to P1-6G for execution.

Compliance note:
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- no direct GitHub branch protection change in this round
