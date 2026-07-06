# P298A Handoff Report

## Final Classification
`P298A_POWERLOTTO_READINESS_AUDIT_COMPLETE_WITH_RISKS`

Risk basis: the repo was dirty before this run, and the inferred replay DB has pre-existing sidecars. No repo tracked files were intentionally modified by this audit, and sidecar pre/after inventories are identical.

## Answer
POWER_LOTTO full prize-aware replay cannot be safely unblocked now. The blocking gaps are:

1. No POWER_LOTTO canonical DB view/source contract exists in the inspected replay DB. The only canonical view found is `draws_big_lotto_canonical_main`.
2. 27,104 of 36,104 POWER_LOTTO replay rows have `predicted_special IS NULL`, so full second-zone prize-aware scoring would require missing values. This audit did not fill, substitute, or manufacture those values.

A valid research-only subset can be described as: `strategy_prediction_replays WHERE lottery_type='POWER_LOTTO' AND predicted_special IS NOT NULL`. It contains 9,000 rows across 6 strategies and 1,500 distinct target draws, with target draw range 101000002..115000040 and target date range 2012/01/05..2026/05/18. The excluded complement is 27,104 rows where `predicted_special IS NULL`.

## Confirmed
- P297A evidence root exists and required evidence inputs are present.
- Inferred replay DB: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db`.
- SQLite metadata reads used immutable read-only URI mode.
- `draws` contains POWER_LOTTO source draw rows, but this is not a canonical POWER_LOTTO view.
- `strategy_prediction_replays` contains POWER_LOTTO replay rows.
- POWER_LOTTO predicted second-zone counts: 27,104 NULL and 9,000 non-null.
- DB sidecar pre/after inventories are identical.

## Inferred
- The minimum safe unblock path is to define and validate a POWER_LOTTO canonical source/view contract, then replay or regenerate POWER_LOTTO predictions so `predicted_special` is structurally complete for the intended prize-aware scope.
- Existing non-BIG_LOTTO `get_canonical_draws()` behavior is a direct source query and should not be treated as proof of a POWER_LOTTO canonical DB view.

## Unknown
- Whether POWER_LOTTO raw draw rows require exclusions analogous to BIG_LOTTO contamination families.
- Which branch/worktree should become canonical for future apply work; this audit is read-only and did not sync or publish.

## Validation
- PASS: evidence root exists.
- PASS: required output artifacts were created.
- PASS: manifest covers all non-manifest artifacts in this evidence root; manifest self-hash is excluded and documented.
- PASS: DB sidecar pre/after inventories are identical.
- PASS_WITH_RISK: repo was already dirty before run; this audit made no intentional repo writes.
- PASS: staged files after run: none observed if the staged-status section below is empty.
- PASS: no DB sidecar creation caused by this run.
- PASS: no missing predicted second-zone values were filled, substituted, or manufactured.
- NOT RUN: commit, push, PR, merge.
- NOT RUN: DB write, migration, checkpoint.
- NOT RUN: registry publication.
- NOT RUN: future-ticket creation.

## Final Repo State Capture
Captured: 2026-06-30 15:57:24 UTC+08:00+0800

### `git status --short`
```text
M 00-Plan/roadmap/agent_bootstrap/SHARED_AGENT_BOOTSTRAP.md
 M 00-Plan/roadmap/agent_bootstrap/TASK_TEMPLATES.md
 M backend.pid
 M claude-code-showcase
 M data/lottery_v2.db
 M frontend.pid
 M lottery_api/data/performance_history.json
?? .gstack/
?? ".schema strategy_replay_runs"
?? claude-code-showcase.worktrees/
?? data/performance_history.json
?? lottery_api/data/ingest_log.jsonl
?? outputs/research/p245a_external_predictive_method_scouting_20260605.json
?? outputs/research/p245a_external_predictive_method_scouting_20260605.md
?? outputs/research/p251d_evidence_dashboard_readonly_api_route_20260609.json
?? outputs/research/p251d_evidence_dashboard_readonly_api_route_20260609.md
?? runtime/
?? tests/test_p245a_external_predictive_method_scouting.py
```

### `git diff --cached --name-status`
```text

```
