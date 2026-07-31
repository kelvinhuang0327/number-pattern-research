# P238A - NIST Randomness-Audit Artifact-Only Build Plan

**Task ID:** P238A
**Date:** 2026-06-04 Asia/Taipei
**Type:** Read-only implementation planning / artifact-only future-build specification. No production build.
**Authorization:** User explicitly authorized P238A build-plan only: read-only, no DB write, no registry mutation, no production/recommendation change, no monitoring job, no strategy.
**Final Classification:** `P238A_NIST_RANDOMNESS_AUDIT_ARTIFACT_ONLY_BUILD_PLAN_READY`

---

## 1. Executive Summary

P238A converts the merged P237C NIST-style randomness-audit tripwire design into a concrete future-build plan. It does not implement the audit.

The future audit remains diagnostics-only. It would read historical draw observations, test whether draw behavior remains statistically compatible with expected randomness, and emit Markdown/JSON artifacts. It would not predict lottery numbers, improve win rate, advise betting, score strategies, alter recommendations, monitor production, write DB rows, or mutate registry state.

The correct steady-state result for a future build may be GREEN / NULL: observed draws remain compatible with randomness, so no downstream strategy work should start.

## 2. P237C Design Inheritance

This plan inherits the P237C boundaries:

- Statistical unit is draw-level observation, not replay row.
- `draws` is the primary future data source.
- `strategy_prediction_replays` is not an audit unit and may only be used for read-only consistency checks.
- Tests must be pre-registered before execution.
- Multiple-testing correction is required.
- RED alert means human diagnostic review only, not a prediction claim or strategy authorization.
- P211 remains `HELD_BY_USER`.
- Build remains separate explicit authorization.

The future audit should preserve P237C classification language:

- diagnostics-only
- no predictor
- no win-rate claim
- no betting advice
- no production/recommendation implication
- NULL is success

## 3. Future Build Non-Scope

The future build must not include:

- DB writes or migrations
- registry mutation
- production/recommendation changes
- strategy adapters
- strategy scoring or candidate generation
- scheduler, cron, launchd, daemon, or monitoring job
- old sweep reruns
- P211 restart
- betting advice
- any claim that randomness diagnostics improve hit rate

The future build is artifact-only unless a later prompt explicitly expands scope. Even then, expansion must remain diagnostics-only.

## 4. Exact Read-Only Data Sources

### Primary Data Source

`lottery_api/data/lottery_v2.db`, table `draws`.

Schema verified read-only in P238A:

```text
id INTEGER PRIMARY KEY AUTOINCREMENT
draw TEXT NOT NULL
date TEXT NOT NULL
lottery_type TEXT NOT NULL
numbers TEXT NOT NULL
special INTEGER DEFAULT 0
created_at TEXT DEFAULT CURRENT_TIMESTAMP
jackpot_amount REAL DEFAULT NULL
sell_amount REAL DEFAULT NULL
total_amount REAL DEFAULT NULL
UNIQUE(draw, lottery_type)
```

Future build must open SQLite in read-only mode, for example via URI `file:lottery_api/data/lottery_v2.db?mode=ro`.

Required draw fields:

- `lottery_type`
- `draw`
- `date`
- `numbers`
- `special`

Optional metadata fields:

- `jackpot_amount`
- `sell_amount`
- `total_amount`

The optional metadata fields are not randomness-test inputs. They may appear only in data-inventory sections if useful.

### Current Draw Inventory

Read-only P238A inventory:

| Lottery Type | Draw Rows | Min Draw | Max Draw | Min Date | Max Date |
|---|---:|---:|---:|---|---|
| 38_LOTTO | 1,774 | 96000001 | 112000104 | 2007-01-01 | 2023-12-28 |
| 39_LOTTO | 4,890 | 99000001 | 115000106 | 2010-09-06 | 2026-04-30 |
| 3_STAR | 4,179 | 96000002 | 115000106 | 2007/01/02 | 2026/01/28 |
| 49_LOTTO | 2,130 | 96000001 | 115000048 | 2007-01-02 | 2026-04-28 |
| 4_STAR | 2,922 | 96000002 | 115000103 | 2007-01-02 | 2026-04-27 |
| BIG_LOTTO | 22,238 | 20090727 | 115000058 | 2007/01/02 | 2026/06/02 |
| BIG_LOTTO_BONUS | 11,941 | 113000011 | 115000032 | 2024-02-06 | 2026-03-03 |
| DAILY_539 | 5,879 | 96000001 | 115000135 | 2007/01/01 | 2026/06/03 |
| DOUBLE_WIN | 1,782 | 107000001 | 112000312 | 2018-04-23 | 2023-12-30 |
| LOTTO_6_38 | 111 | 96000001 | 97000006 | 2007-01-01 | 2008-01-21 |
| POWER_LOTTO | 1,916 | 97000001 | 115000044 | 2008/01/24 | 2026/06/01 |

Future build must explicitly pre-register the active audit universe. It must not silently include every lottery type in `draws`.

Recommended initial future universe:

- `BIG_LOTTO`
- `DAILY_539`
- `POWER_LOTTO`
- `3_STAR`
- `4_STAR`

Other draw-table lottery types may be inventory-only unless separately pre-registered.

### Secondary Read-Only Cross-Check Source

`lottery_api/data/lottery_v2.db`, table `strategy_prediction_replays`.

Schema fields include replay metadata such as `lottery_type`, `target_draw`, `target_date`, `strategy_id`, `predicted_numbers`, `actual_numbers`, `actual_special`, `hit_count`, `special_hit`, and `bet_index`.

Use is restricted:

- Allowed: cross-check actual draw values against `draws` for data-quality diagnostics.
- Forbidden: use replay rows as statistical units.
- Forbidden: aggregate randomness results over strategy rows, bet slots, or replay lifecycle labels.

## 5. Statistical Unit Discipline

The future audit unit is one chronological draw observation:

```text
(lottery_type, draw, date, zone, number_unit)
```

Rules:

- A draw must count once per lottery-zone-window.
- Multi-bet replay rows must not inflate sample size.
- Strategy IDs are irrelevant to randomness testing.
- `bet_index` is irrelevant to randomness testing.
- Sorted number sets are acceptable for set-level tests.
- Position-aware tests require raw positional data. If raw position is unavailable, report `POSITION_DATA_UNAVAILABLE`.
- `special` / second-zone values must be handled as their own zone with separate baselines.

Every future output table must include:

- `lottery_type`
- `zone`
- `unit_type`
- `sample_size_draws`
- `position_available`
- `replay_rows_used_as_unit=false`

## 6. Proposed Future Command Interface

This is proposed CLI design only. P238A creates no script.

Proposed future command:

```bash
python3 scripts/p238b_nist_randomness_audit_artifact_build.py \
  --db lottery_api/data/lottery_v2.db \
  --mode read-only \
  --lotteries BIG_LOTTO,DAILY_539,POWER_LOTTO,3_STAR,4_STAR \
  --windows 150,500,1000,all-history \
  --correction bonferroni \
  --emit-json outputs/research/p238b_nist_randomness_audit_artifact_YYYYMMDD.json \
  --emit-md outputs/research/p238b_nist_randomness_audit_artifact_YYYYMMDD.md
```

CLI requirements:

- refuse to run unless DB is opened read-only
- require explicit `--lotteries`
- require explicit `--windows`
- require explicit `--correction`
- require explicit output paths under `outputs/research/`
- default to no position-aware tests unless raw position is confirmed
- emit `predictability_claim=false`
- emit `win_rate_claim=false`
- emit `betting_advice=false`
- emit `strategy_authorized=false`
- emit `production_change_authorized=false`

Suggested future flags:

- `--pre_registration_id`
- `--family-size-declared`
- `--include-inventory-only-lotteries`
- `--allow-bh-fdr-report-only`
- `--fail-on-replay-unit`
- `--data-quality-only`

## 7. Proposed Future File Whitelist

For a future artifact-only implementation task, recommended allowlist:

- `scripts/p238b_nist_randomness_audit_artifact_build.py`
- `tests/test_p238b_nist_randomness_audit_artifact_build.py`
- `outputs/research/p238b_nist_randomness_audit_artifact_YYYYMMDD.md`
- `outputs/research/p238b_nist_randomness_audit_artifact_YYYYMMDD.json`

Optional governance closeout after artifact completion:

- `00-Plan/roadmap/active_task.md`
- `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
- `00-Plan/roadmap/roadmap.md`
- `00-Plan/roadmap/CEO-Decision.md`

Forbidden future files unless separately authorized:

- DB files
- registry files
- production code
- recommendation logic
- scheduler or monitoring config
- strategy adapter modules
- broad generated directories

## 8. Proposed Future JSON Schema

Future JSON artifact should be deterministic and explicit:

```json
{
  "task_id": "P238B",
  "artifact_type": "NIST_STYLE_RANDOMNESS_AUDIT_ARTIFACT_ONLY",
  "diagnostics_only": true,
  "predictability_claim": false,
  "win_rate_claim": false,
  "betting_advice": false,
  "strategy_authorized": false,
  "production_change_authorized": false,
  "monitoring_job_authorized": false,
  "db_write_performed": false,
  "registry_write_performed": false,
  "data_snapshot": {
    "repo": "/Users/kelvin/Kelvin-WorkSpace/LotteryNew",
    "branch": "",
    "head": "",
    "db_path": "lottery_api/data/lottery_v2.db",
    "db_open_mode": "read-only",
    "draw_table": "draws",
    "replay_table": "strategy_prediction_replays",
    "replay_rows_used_as_unit": false
  },
  "pre_registration": {
    "pre_registration_id": "",
    "lotteries": [],
    "zones": [],
    "test_families": [],
    "windows": [],
    "family_size_declared_before_run": 0,
    "primary_correction": "bonferroni",
    "secondary_report_only_correction": "bh_fdr"
  },
  "data_inventory": [
    {
      "lottery_type": "",
      "draw_rows": 0,
      "min_draw": "",
      "max_draw": "",
      "min_date": "",
      "max_date": "",
      "position_available": false,
      "included_in_primary_audit": false,
      "inventory_only_reason": ""
    }
  ],
  "data_quality": {
    "draw_table_exists": true,
    "duplicate_draw_keys": 0,
    "invalid_number_rows": 0,
    "invalid_special_rows": 0,
    "date_parse_warnings": [],
    "position_data_unavailable_lotteries": []
  },
  "test_results": [
    {
      "lottery_type": "",
      "zone": "",
      "window": "",
      "test_family": "",
      "unit_type": "draw",
      "sample_size_draws": 0,
      "statistic": null,
      "p_value_raw": null,
      "p_value_corrected": null,
      "correction_method": "bonferroni",
      "alert_level": "GREEN",
      "diagnostics_only": true,
      "limitations": []
    }
  ],
  "alert_summary": {
    "overall_level": "GREEN",
    "green_count": 0,
    "yellow_count": 0,
    "orange_count": 0,
    "red_count": 0,
    "red_authorizes_strategy": false,
    "red_authorizes_human_review_only": true
  },
  "classification": "RANDOMNESS_AUDIT_GREEN_NULL_SUCCESS",
  "final_recommendation": "HOLD"
}
```

## 9. Proposed Future Markdown Schema

Future Markdown artifact should include:

1. Executive summary
2. Authorization and non-scope
3. Data snapshot
4. Draw-level unit declaration
5. Pre-registration table
6. Data inventory by lottery
7. Data-quality checks
8. Test family definitions
9. Multiple-testing correction summary
10. Rolling-window summary
11. Alert taxonomy results
12. Limitations and false-positive risks
13. No-predictability / no-betting-advice statement
14. Governance recommendation
15. Validation commands and results
16. Required completion check
17. Final classification

Required visible statements:

- "This artifact is diagnostics-only."
- "This artifact does not predict lottery numbers."
- "This artifact does not improve win rate."
- "This artifact is not betting advice."
- "RED alert authorizes human review only."
- "NULL / GREEN is success."

## 10. Proposed Test Plan

Future tests should be narrow and contract-focused:

### Unit / Contract Tests

- DB open mode is read-only.
- `draws` table is required.
- missing `draws` table returns blocked classification.
- replay rows cannot be used as statistical units.
- active lottery universe must be explicit.
- JSON output contains required no-claim booleans.
- Markdown output contains required no-claim statements.
- RED alert does not authorize strategy or production.
- family size must be declared before test execution.
- correction method must be present for every p-value.
- position-aware tests skip when positional data is unavailable.

### Data Quality Tests

- duplicate `(lottery_type, draw)` count is zero or reported.
- invalid `numbers` rows are reported.
- invalid `special` rows are reported.
- sample size by lottery matches draw inventory.
- date ordering is deterministic.

### Governance Tests

- no writes to DB path
- no registry files touched
- no production/recommendation files touched
- output files only under whitelisted `outputs/research/`
- final classification must be one of allowed non-promotional tokens

### Suggested Future Test File

`tests/test_p238b_nist_randomness_audit_artifact_build.py`

P238A does not create this file.

## 11. Proposed STOP Conditions

Future build must STOP if:

- repo is not `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- branch/HEAD baseline does not match task prompt
- staged files exist before task
- DB integrity is not `ok`
- replay row baseline unexpectedly changes
- `draws` table is missing
- `draws` schema lacks `draw`, `date`, `lottery_type`, or `numbers`
- DB cannot be opened read-only
- implementation needs DB write
- implementation needs registry mutation
- implementation needs production/recommendation change
- implementation needs scheduler/monitoring setup
- implementation tries to create a strategy adapter
- implementation uses `strategy_prediction_replays` as the statistical unit
- test family/window/lottery universe is not pre-registered
- artifact text claims prediction, win-rate improvement, or betting advice
- RED alert semantics imply strategy or production authorization
- output path is outside the allowed whitelist

## 12. Proposed Validation Checklist

Future build validation should run and report:

- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse --git-dir`
- `git rev-parse HEAD`
- `git rev-parse origin/main`
- `git status --short`
- `git diff --cached --name-only`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT integrity_check FROM pragma_integrity_check;"`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL;"`
- duplicate replay key check
- `python3 scripts/replay_lifecycle_drift_guard.py --strict`
- future targeted tests for P238B
- `git diff --check`

Acceptance requirements:

- artifact Markdown exists
- artifact JSON exists
- DB rows unchanged
- DB integrity `ok`
- drift guard PASS
- no registry change
- no production/recommendation change
- no scheduler/monitoring change
- no strategy adapter
- no P211 restart
- no betting advice

## 13. Multiple-Testing / P221F Alignment

The future audit is itself a multiple-testing surface.

Required alignment:

- pre-register lotteries
- pre-register zones
- pre-register test families
- pre-register windows
- pre-register family size
- declare primary correction before execution
- use Bonferroni for escalation
- use BH-FDR only as report-only unless explicitly authorized
- separate exploratory history from future confirmatory OOS
- forbid post-hoc window tuning
- classify GREEN / NULL as success

Recommended alert escalation:

- GREEN: corrected tests compatible with randomness
- YELLOW: weak observation only
- ORANGE: repeated corrected anomaly needing independent confirmation
- RED: strong corrected anomaly across independent future windows, human review only

No alert level may authorize prediction, strategy creation, production ranking, registry change, or betting advice.

## 14. Governance Integration

Future build should be a new task, not a continuation of P238A.

Before future build:

- user must issue exact authorization phrase
- task prompt must include allowed files
- task prompt must include STOP conditions
- task prompt must require read-only DB mode
- task prompt must require no-predictability statements

After future build:

- governance closeout may record artifact results
- active_task should return to `WAITING_FOR_USER_AUTHORIZATION`
- if GREEN, no further work is recommended
- if YELLOW/ORANGE/RED, only human review or a new pre-registered diagnostic confirmation task may be considered

P238A itself does not update governance files because this build plan artifact is sufficient and active_task already records the system waiting state.

## 15. Required Future Authorization Phrase

An actual future artifact-only build should require a phrase at least this explicit:

```text
YES start P238B NIST randomness-audit artifact-only build, read-only DB mode, artifact outputs only. No DB write, no registry mutation, no production/recommendation change, no monitoring job, no strategy, no betting advice. Use the P238A build plan and P237C design boundaries.
```

Any prompt lacking equivalent explicit boundaries should STOP.

## 16. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Diagnostics misread as prediction | Required no-claim booleans and visible Markdown statements |
| Replay rows inflate sample size | Hard fail if replay rows become audit unit |
| Multiple-testing false alarms | Pre-register family size; Bonferroni for escalation |
| Position-aware tests on sorted data | Mark `POSITION_DATA_UNAVAILABLE` unless raw position exists |
| Scope creep into monitoring | Monitoring/scheduler explicitly forbidden |
| Scope creep into strategy | Strategy adapter/promotion explicitly forbidden |
| Dirty worktree broad staging | Stage only whitelisted files |
| DB mutation by accident | Open DB in read-only mode and validate row count after |

## 17. Final Recommendation

P238A is complete when this build plan artifact exists and validation passes.

The future NIST randomness-audit build remains **not authorized** by this plan. The next state should remain:

```text
WAITING_FOR_USER_AUTHORIZATION
```

Recommended default: HOLD. If the user explicitly authorizes P238B later, run it as a new artifact-only, read-only task with the whitelist and STOP conditions above.

**Final Classification:** `P238A_NIST_RANDOMNESS_AUDIT_ARTIFACT_ONLY_BUILD_PLAN_READY`
