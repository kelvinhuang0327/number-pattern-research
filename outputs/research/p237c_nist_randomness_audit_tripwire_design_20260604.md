# P237C - NIST-Style Randomness-Audit Tripwire Design

**Task ID:** P237C
**Date:** 2026-06-04 Asia/Taipei
**Type:** Design document only. Read-only governance/statistical design. No build, no code, no scripts, no tests, no DB write, no registry mutation, no production/recommendation change, no strategy adapter, no monitoring job.
**Authorization:** User explicitly authorized: "YES start P237C NIST randomness-audit design-doc only, read-only, no build."
**Final Classification:** `P237C_NIST_RANDOMNESS_AUDIT_TRIPWIRE_DESIGN_READY`

---

## 1. Executive Summary

This document defines a future **NIST-style randomness-audit tripwire** for LotteryNew. The layer is diagnostics-only. It cannot predict lottery numbers, cannot improve win rate, cannot produce betting advice, and cannot justify strategy promotion.

The purpose is narrower and more conservative: ask whether observed draw behavior remains statistically compatible with expected randomness. A clean result is expected and useful. If the audit returns GREEN, the correct conclusion is that the draw stream remains compatible with random behavior and no downstream strategy work should start.

The tripwire is a future single-source-of-truth (SSOT) null-baseline artifact. It would support governance by making the project's "random baseline" explicit, reproducible, and periodically auditable. It would not change production behavior.

## 2. Scope And Non-Scope

### In Scope

- Draw-sequence diagnostics at draw-level units.
- Uniformity checks for ball frequencies and number sets.
- Independence checks across chronological draws.
- Serial, adjacency, and correlation checks where the data unit supports them.
- Rolling-window stability checks with pre-registered windows.
- Multiple-testing correction across tests, lotteries, windows, zones, and positions.
- Alert taxonomy that separates weak observations from governance-significant anomalies.
- Future artifact schema for Markdown and JSON outputs.
- Governance STOP conditions and future build acceptance criteria.

### Out Of Scope

- Prediction of future draws.
- Strategy scoring, candidate generation, or recommendation ranking.
- Betting advice or any claim of improved odds.
- DB writes, production monitoring, registry mutation, scheduler/cron jobs, or controlled apply.
- Strategy adapters, executable modules, scripts, tests, or old sweep reruns in this task.
- Treating any alert as an automatic reason to deploy a strategy.

## 3. Governance Anchors

This design inherits the P236A conclusion: the NIST-style audit is the single net-new diagnostic gap, and it is not a predictor. P236A also identifies the main risk: running many randomness tests across lotteries and windows can manufacture false alarms unless the family is pre-registered and corrected.

It also inherits P221F and P234:

- Pre-register tests, lotteries, windows, baselines, family size, and escalation rules before any audit execution.
- Use corrected inference. Bonferroni is the conservative default for tripwire escalation; BH-FDR may be reported for exploratory context only.
- Keep exploratory scans separate from confirmatory future out-of-sample checks.
- Treat NULL as success. Random-compatible draws are the desired steady state.
- Keep the statistical unit honest: distinct draw observations, not replay rows.

P211 remains `HELD_BY_USER`. P237C does not restart it. No deployable candidate exists in any lottery.

## 4. Data Inventory For A Future Build

The future build should read draw observations, not prediction replay rows.

### Primary Draw Source

`lottery_api/data/lottery_v2.db`, table `draws`:

- `draw`: draw identifier.
- `date`: draw date.
- `lottery_type`: lottery identifier.
- `numbers`: stored number set for the draw.
- `special`: special or second-zone number where applicable; `0` or null-like semantics must be interpreted per lottery rules.
- `jackpot_amount`, `sell_amount`, `total_amount`: payout/sales context only, not needed for randomness tests.

The future build should preserve these unit labels in every output row:

- `lottery_type`
- `draw_id`
- `draw_date`
- `zone`: first-zone, second-zone, or all-zone where applicable
- `number_unit`: sorted number set, raw position, special number, or derived bit/vector encoding
- `position_available`: true or false
- `sample_size_draws`
- `window_id`
- `window_start_draw`
- `window_end_draw`

### Replay Source Warning

`strategy_prediction_replays` is not a draw-observation table. It has replay rows by lottery, target draw, strategy, and bet index. It is useful for strategy evidence, but it must not be the primary unit for randomness testing. Replay rows can over-count a single draw many times and can mix prediction metadata with actual draw outcomes.

Replay rows may be used only for cross-checking whether actual draw fields are consistent with `draws`, never as the randomness-audit unit.

### Positional Data Warning

For many LotteryNew use cases, stored `numbers` are sorted sets. If raw draw order or ball position is not preserved, position-aware tests are out of scope for that lottery and must be marked `POSITION_DATA_UNAVAILABLE`. This is especially important for 3_STAR / 4_STAR, where prior governance records positional-order loss for straight-play analysis.

### Observed Draw Inventory At Design Time

Read-only inventory from `draws` confirms the table contains multiple lottery families, including current core types:

- `BIG_LOTTO`: 22,238 draw rows, through 2026-06-02.
- `DAILY_539`: 5,879 draw rows, through 2026-06-03.
- `POWER_LOTTO`: 1,916 draw rows, through 2026-06-01.
- `3_STAR`: 4,179 draw rows.
- `4_STAR`: 2,922 draw rows.

The future build must define the active audit universe explicitly instead of silently including every legacy lottery type in `draws`.

## 5. Candidate NIST-Style Test Families

The tests below are design-level candidates. A future build must implement only a pre-registered subset and must report family size before computing significance.

### 5.1 Frequency / Monobit-Style Uniformity Analogue

- **Measures:** Whether each number appears at approximately its expected marginal frequency.
- **Required unit:** Draw-level first-zone number set, second-zone special number, or binary inclusion vector per draw.
- **Diagnostics-only reason:** Detecting a frequency imbalance does not identify the next draw; it only tests whether historical inclusion rates are compatible with the lottery's expected distribution.
- **Limitations:** Small samples have low power. Sorted multi-number sets are not independent bits because each draw has fixed cardinality.
- **Multiple-testing implication:** Correct across lottery, zone, number, and window.

### 5.2 Block Frequency / Rolling-Window Uniformity

- **Measures:** Whether frequency behavior remains stable across pre-registered windows.
- **Required unit:** Chronologically ordered draw observations and fixed window definitions.
- **Diagnostics-only reason:** A rolling anomaly is a stability warning, not a forecast.
- **Limitations:** Short windows are noisy and can produce false alerts. Window tuning after seeing results is forbidden.
- **Multiple-testing implication:** Window count multiplies the family. Escalation requires correction and future confirmation.

### 5.3 Runs / Adjacency / Serial Behavior Analogue

- **Measures:** Whether inclusion/exclusion runs for each number, or adjacency patterns among sorted sets, depart from expected behavior.
- **Required unit:** Chronological inclusion vector per number; optionally pair adjacency within number sets.
- **Diagnostics-only reason:** Runs can show non-random-looking clustering, but they do not identify a profitable next value.
- **Limitations:** Lottery draws have fixed set sizes, so simple binary-run assumptions need adaptation. Adjacent numbers are common under random sorted sets.
- **Multiple-testing implication:** Correct across numbers, pair classes, and windows.

### 5.4 Approximate Entropy / Pattern Repetition Analogue

- **Measures:** Whether short patterns in encoded draw streams repeat more or less often than expected.
- **Required unit:** A pre-defined encoding, such as inclusion bit-vectors, sorted number deltas, parity/zone category strings, or second-zone sequences.
- **Diagnostics-only reason:** Pattern repetition is a randomness diagnostic. It is not a strategy signal unless independently validated under future OOS, and this design does not authorize that.
- **Limitations:** Encoding choice can create artifacts. Must be pre-registered and kept simple.
- **Multiple-testing implication:** Correct across encodings, pattern lengths, lotteries, and windows.

### 5.5 Chi-Square / Multinomial Uniformity For Balls

- **Measures:** Whether observed counts over categories match the theoretical distribution.
- **Required unit:** Draw-level category counts: ball number, zone bucket, parity, high/low, or special number.
- **Diagnostics-only reason:** Goodness-of-fit tests can reject a null distribution but do not rank future recommendations.
- **Limitations:** Sparse expected counts invalidate naive chi-square approximations; exact or simulation-based nulls may be required.
- **Multiple-testing implication:** Each lottery-zone-category-window combination is part of the family.

### 5.6 Serial Correlation / Lag Checks

- **Measures:** Whether encoded draw values correlate with prior draws at pre-registered lags.
- **Required unit:** Chronological numeric encodings, such as number inclusion vectors, count summaries, or second-zone values.
- **Diagnostics-only reason:** Lag correlation is a dependence test, not a production strategy.
- **Limitations:** Many encodings and lags create many chances for false positives. Lottery draw mechanisms can change schedule or machine without creating predictability.
- **Multiple-testing implication:** Correct across lags, encodings, lotteries, zones, and windows.

### 5.7 Gap / Inter-Arrival Checks Per Number

- **Measures:** Whether waiting times between appearances of each number resemble the expected inter-arrival distribution.
- **Required unit:** Chronological draw-level inclusion by number.
- **Diagnostics-only reason:** "Overdue" or "hot" framing is forbidden. Gap behavior is only an audit statistic.
- **Limitations:** Human intuition overreads gaps; long gaps are expected under random sampling.
- **Multiple-testing implication:** Correct across numbers, lotteries, zones, and windows.

### 5.8 Position-Aware Tests

- **Measures:** Whether raw ball position has uniformity, serial, or correlation anomalies.
- **Required unit:** Raw positional draw data, not sorted stored sets.
- **Diagnostics-only reason:** Position bias would be an audit concern about the draw mechanism, not a prediction feature.
- **Limitations:** If position is unavailable or the DB stores sorted numbers, these tests must be marked unavailable.
- **Multiple-testing implication:** Correct across positions, numbers, lotteries, and windows.

## 6. Tripwire Alert Taxonomy

The future build should classify every audit run conservatively.

| Level | Meaning | Allowed Consequence |
|---|---|---|
| GREEN | Compatible with random behavior after correction. | Maintain hold. No strategy work. Report NULL as success. |
| YELLOW | Weak anomaly or exploratory uncorrected/corrected-borderline observation. | Observation only. No production, no strategy, no monitoring escalation. |
| ORANGE | Repeated anomaly across pre-registered windows with correction, but not yet independently confirmed in future data. | Human review may authorize a new pre-registered diagnostic confirmation task. No strategy. |
| RED | Strong corrected anomaly across independent future windows, with data-quality checks passed. | Human review may authorize a new diagnostic investigation. Still not a prediction claim and not a production strategy. |

RED must not automatically authorize:

- strategy generation
- recommendation ranking changes
- registry mutation
- controlled apply
- betting advice
- production monitoring
- DB writes

RED means only: "the draw stream may deserve independent diagnostic review." It does not mean "we can predict the next draw."

## 7. Multiple Testing And Anti-Overfit Gate

The audit itself is a multiple-testing surface. A 15-test battery across lotteries, zones, windows, positions, and encodings can create chance failures.

Future build rules:

1. Pre-register the active audit universe.
2. Pre-register test families and parameters.
3. Pre-register windows and confirmation windows.
4. Declare family size before running tests.
5. Use Bonferroni for tripwire escalation by default.
6. Report BH-FDR as secondary exploratory context only unless separately authorized.
7. Separate exploratory historical scan from confirmatory future OOS.
8. Require independent future confirmation before ORANGE or RED escalation.
9. Mark NULL as success.
10. Never tune windows, encodings, or thresholds after seeing p-values.

## 8. Rolling-Window Design

A future build may use these pre-registered window families, subject to sample-size checks:

- Short: 100, 125, 150 draws, for sensitivity only.
- Mid: 500, 750, 1000 draws, for primary stability checks where enough data exists.
- All-history: reference context only, not an escalation gate.

Short windows have limited power and high false-positive risk. They may generate YELLOW observations, but should not escalate without mid-window and future-OOS confirmation.

A future build should report:

- `window_family`
- `window_size_draws`
- `window_role`: exploratory, primary, or reference
- `effective_sample_size`
- `power_warning`
- `minimum_draws_required`
- `escalation_allowed`: true or false

## 9. Future Output Artifact Schema

This is a schema design only. No JSON artifact is created in P237C.

### JSON Fields

```json
{
  "task_id": "P237D_OR_FUTURE",
  "audit_type": "NIST_STYLE_RANDOMNESS_AUDIT_TRIPWIRE",
  "diagnostics_only": true,
  "predictability_claim": false,
  "win_rate_claim": false,
  "betting_advice": false,
  "data_snapshot": {
    "repo": "",
    "head": "",
    "db_path": "",
    "draw_table": "draws",
    "replay_rows_used_as_unit": false
  },
  "pre_registration": {
    "lotteries": [],
    "zones": [],
    "test_families": [],
    "windows": [],
    "family_size": 0,
    "correction_methods": ["bonferroni", "bh_fdr_report_only"]
  },
  "data_inventory": [],
  "test_results": [],
  "alert_summary": {
    "overall_level": "GREEN",
    "green_count": 0,
    "yellow_count": 0,
    "orange_count": 0,
    "red_count": 0
  },
  "governance": {
    "null_is_success": true,
    "no_strategy_authorized": true,
    "no_build_authorized_by_design_doc": true,
    "required_next_authorization": "human_review_only"
  },
  "final_classification": "RANDOMNESS_AUDIT_TRIPWIRE_RESULT_GREEN_OR_REVIEW_REQUIRED"
}
```

### Markdown Report Sections

- Executive summary.
- Data snapshot and unit labels.
- Pre-registration record.
- Data quality checks.
- Test family results.
- Multiple-testing correction summary.
- Rolling-window summary.
- Alert taxonomy outcome.
- No-predictability statement.
- Governance recommendation.
- Required completion check.

### Classification Tokens

Future build classification tokens should be explicit and non-promotional:

- `RANDOMNESS_AUDIT_GREEN_NULL_SUCCESS`
- `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`
- `RANDOMNESS_AUDIT_ORANGE_NEEDS_INDEPENDENT_CONFIRMATION`
- `RANDOMNESS_AUDIT_RED_HUMAN_REVIEW_ONLY`
- `RANDOMNESS_AUDIT_BLOCKED_DATA_QUALITY`
- `RANDOMNESS_AUDIT_BLOCKED_POSITION_DATA_UNAVAILABLE`

## 10. Governance Integration For A Future Build

If a future build is separately authorized, it should be a new task, not a continuation of P237C.

Allowed files for a future artifact-only build should be narrow, for example:

- `outputs/research/p237d_nist_randomness_audit_tripwire_build_YYYYMMDD.md`
- `outputs/research/p237d_nist_randomness_audit_tripwire_build_YYYYMMDD.json`
- optionally one script and one test file only if the future prompt explicitly authorizes code.

Files that must remain forbidden unless explicitly authorized:

- DB files.
- registry files.
- production or recommendation logic.
- scheduler/cron/automation files.
- strategy adapter files.
- active task/governance files except a narrow closeout update after the artifact is complete.

Future STOP conditions must include:

- wrong repo, wrong branch, detached HEAD, or HEAD != origin/main at Phase 0
- staged files before task
- DB integrity or row baseline mismatch
- drift guard failure
- missing `draws` table or invalid draw schema
- attempt to use replay rows as the statistical unit
- unregistered test/window/encoding expansion
- any claim of prediction, win-rate improvement, or betting advice
- any request to mutate DB, registry, production, or recommendation behavior

## 11. Future Build Acceptance Criteria

A future build is acceptable only if it:

- reads draw data in read-only mode
- writes artifacts only to explicitly whitelisted `outputs/research/` files
- documents the data snapshot and draw-level unit labels
- uses pre-registered tests/windows/family size
- applies multiple-testing correction
- separates exploratory from confirmatory findings
- reports GREEN/YELLOW/ORANGE/RED conservatively
- reports `predictability_claim=false`
- reports `win_rate_claim=false`
- reports `betting_advice=false`
- leaves DB rows unchanged
- leaves registry and production unchanged
- runs `git diff --check`
- runs drift guard after completion

## 12. Final Recommendation

P237C design is sufficient to proceed only to a future, separately authorized artifact-only build. The conservative default remains HOLD.

Recommended next state:

- Complete P237C as design-doc only.
- Do not build the audit in this task.
- Do not start monitoring.
- Do not start P211.
- Do not start strategy research.
- If the user later authorizes a build, start a new pre-registered task with a narrow whitelist and draw-level unit discipline.

Design-doc completion does not authorize implementation.

**Final Classification:** `P237C_NIST_RANDOMNESS_AUDIT_TRIPWIRE_DESIGN_READY`
