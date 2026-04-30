# Strategy Monitoring Status

## 1. Summary
Overall status: ESCALATE

Reason: Required strategy tables (active_strategy_state, strategy_reviews, strategy_live_state) are missing from the monitored DB; monitoring cannot complete end-to-end. Evidence and snapshot data are provided below.

## 2. Active Strategy State
| Game | Active | Active Edge | Shadow | Shadow Edge | Mode | Status |
|---|---:|---:|---|---:|---|---|
| BIG_LOTTO | p1_dev_sum5bet | 0.0374 | regime_2bet | 0.0357 | MAINTENANCE | OK (matches expected)
| DAILY_539 | acb_markov_midfreq_3bet | 0.0881 | midfreq_acb_2bet | 0.0865 | WATCH_MAINTENANCE | WATCH (edge present but monotonic decline noted)
| POWER_LOTTO | pp3_freqort_4bet | 0.0328 | orthogonal_5bet | 0.0294 | MONITOR | OK (shadow present; not fourier_rhythm_3bet)

## 3. Watchdog Check
| Game | Watchdog | Current Value | Threshold | Result |
|---|---|---:|---:|---|
| DAILY_539 | 3000p edge | +4.50 pp (noted in planner text) | +2.0 pp -> DEGRADED if <= +2.0 | WATCH — value above threshold but trend monotonic decline; prepare for DEGRADED if it falls.
| POWER_LOTTO | Shadow identity | orthogonal_5bet | must NOT be fourier_rhythm_3bet | OK
| BIG_LOTTO | Mode | MAINTENANCE / EXHAUSTED | expected MAINTENANCE | OK

## 4. Live Outcome / Drift Check
NO_LIVE_OUTCOME_DATA_AVAILABLE

Evidence: strategy_live_state table is missing or empty in the DB used by monitoring (see Evidence section).

## 5. Recent Failure Check
Cannot compute failure-category counts: agent_tasks table lacks the required failure_category column in the accessible DB (see Evidence). Query failed with: "no such column: failure_category". Action: escalate to CTO to provide DB access or corrected schema.

## 6. Action Items
ESCALATE_TO_CTO

## 7. Evidence
- outputs/sql_schema_info.txt (schema probe):

> Table: active_strategy_state
> active_strategy_state: MISSING
> Table: strategy_reviews
> strategy_reviews: MISSING
> Table: strategy_live_state
> strategy_live_state: MISSING
> Table: agent_tasks
> agent_tasks: EXISTS

- outputs/sql_errors.txt (SQL probe errors):

> Error: in prepare, no such table: active_strategy_state
> Error: in prepare, no such table: strategy_reviews
> Error: in prepare, no such column: failure_category

- Operational snapshot (watchdog_status.md) — active snapshot excerpt:

| DAILY_539 | acb_markov_midfreq_3bet | 0.0881 | midfreq_acb_2bet | 0.0865 | planner_focus: WATCH_MAINTENANCE; "+4.50pp at 3000p"; trend: monotonic decline |
| BIG_LOTTO | p1_dev_sum5bet | 0.0374 | regime_2bet | 0.0357 | maintenance |
| POWER_LOTTO | pp3_freqort_4bet | 0.0328 | orthogonal_5bet | 0.0294 | shadow tracking |

---

Handoff questions:
1) 本輪結論是否達到 Acceptance Criteria？
   - No. Missing DB tables (active_strategy_state, strategy_reviews, strategy_live_state) prevent full monitoring. Report includes three games and watchdog snapshot, but SQL evidence shows missing tables. Final overall status: ESCALATE.

2) 若未達標，下一輪需要調整哪個假設或範圍？
   - Provide read access to the correct orchestrator DB (runtime/agent_orchestrator/orchestrator.db) or populate lottery_v2.db with the required tables. Ensure agent_tasks has failure_category column or provide alternate failure log.

