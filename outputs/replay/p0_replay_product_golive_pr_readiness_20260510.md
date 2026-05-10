# P0 Replay Product Go-Live — PR Readiness — 2026-05-10

## 1) Worktree Convergence

See the detailed before/after list in [p0_replay_data_health_20260510.md](outputs/replay/p0_replay_data_health_20260510.md).

Short version:
- Kept: `LotteryNew` (source-only) and `LotteryNew-clean` (sole working worktree)
- Removed from git/worktree tracking: `LotteryNew-main-postmerge`, `LotteryNew-roadmap-20260509`, `/private/tmp/lotterynew-phase4-clean`
- Cleared stale worktree metadata with `git worktree prune`

## 2) Lifecycle Counts

From the replay store validation pass:
- ONLINE: 460
- OFFLINE: 0
- REJECTED: 0
- OBSERVATION: 0
- RETIRED: 0

Zero-row lifecycle states:
- OFFLINE
- REJECTED
- OBSERVATION
- RETIRED

## 3) API Samples

Freshness sample:

```json
{"filter_lifecycle_status": "ONLINE", "coverage_mode": "LIMITED", "total_rows": 460, "total_predicted": 420, "total_replay_error": 40, "legacy_error_count": 40, "has_legacy_errors": true}
```

History sample, ONLINE:

```json
{"filter_lifecycle_status": "ONLINE", "total": 140, "records_len": 1, "record": {"lottery": "BIG_LOTTO", "target_draw": "99000105", "target_date": "2010/12/31", "strategy_id": "biglotto_deviation_2bet", "lifecycle_status": "ONLINE", "predicted_numbers": [3, 8, 22, 35, 38, 43], "actual_numbers": [4, 9, 27, 36, 38, 39], "hit_numbers": [38], "hit_count": 1, "replay_status": "PREDICTED"}}
```

History sample, empty lifecycle states:

```text
OFFLINE      -> {"filter_lifecycle_status": "OFFLINE", "total": 0, "records_len": 0}
REJECTED     -> {"filter_lifecycle_status": "REJECTED", "total": 0, "records_len": 0}
OBSERVATION  -> {"filter_lifecycle_status": "OBSERVATION", "total": 0, "records_len": 0}
RETIRED      -> {"filter_lifecycle_status": "RETIRED", "total": 0, "records_len": 0}
```

## 4) UI DOM Diff Summary

Playwright replay smoke verified the lifecycle filter changes the history DOM in the replay section.

Observed flow:
- Start on `ONLINE`.
- `#rp-hist-body` shows a populated history row with `PREDICTED`.
- Switch lifecycle filter to `OFFLINE`.
- `#rp-hist-body` changes to the honest empty-state row:
  `目前無此狀態策略，等待 catalog backfill`

No screenshot artifact was saved; the validation was a headless DOM diff check.

## 5) Test Results

Passed validations:
- `python -m pytest tests/test_replay_api_contract.py tests/test_replay_browser_smoke.py -x` -> `68 passed`
- `python -m pytest tests/test_replay_browser_smoke.py -x` -> `31 passed`
- `python scripts/run_replay_ci_default_validation.py` -> `101 passed, 1 skipped`
- `LOTTERY_REPLAY_DB_PATH=/private/tmp/lottery_replay_test_fixture.db python scripts/run_replay_ci_db_validation.py --validate-fixture` -> `25 passed`
- `git diff --check` -> clean

## 6) Forbidden-Language Sweep

Targeted sweep scope:
- Replay block in `index.html` only
- `lottery_api/routes/replay.py`
- `outputs/replay/p0_replay_data_health_20260510.md`

Result:
- Replay block and replay API/report copy are clean for `edge`, `勝率`, `最佳策略`, and `推薦投注`.
- Broader `index.html` still contains legacy H6 / strategy dashboard wording outside the replay block; that legacy copy was not changed in this replay go-live scope.

## 7) Safety Confirmation

- No production DB writes were performed.
- The only database copy was a local validation fixture / local replay DB seed, not a production store.
- No registry backfill or strategy promotion was performed.
- No branch protection settings were modified.
- No active strategy state was modified.

## 8) PR URL

https://github.com/kelvinhuang0327/number-pattern-research/pull/12
