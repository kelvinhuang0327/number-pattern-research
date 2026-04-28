# Strategy Monitoring Status

## 1. Summary
Overall status: ESCALATE

Reason: required database tables/columns are missing, preventing verification of active/shadow strategies and live outcomes. Per BIG_LOTTO rule (missing active_strategy_state -> ESCALATE) this run escalates.

## 2. Active Strategy State
| Game | Active | Active Edge | Shadow | Shadow Edge | Mode | Status |
|---|---:|---:|---|---:|---|---|
| BIG_LOTTO | DATA_MISSING | DATA_MISSING | DATA_MISSING | DATA_MISSING | DATA_MISSING | ESCALATE (missing active_strategy_state) |
| DAILY_539 | DATA_MISSING | DATA_MISSING | DATA_MISSING | DATA_MISSING | DATA_MISSING | ESCALATE |
| POWER_LOTTO | DATA_MISSING | DATA_MISSING | DATA_MISSING | DATA_MISSING | DATA_MISSING | ESCALATE |

## 3. Watchdog Check
| Game | Watchdog | Current Value | Threshold | Result |
|---|---|---|---:|---|
| BIG_LOTTO | signal_status | N/A | EXHAUSTED/MAINTENANCE | MISSING_DATA |
| DAILY_539 | 3000p_edge | N/A | > +2.0pp (WATCH threshold) | MISSING_DATA |
| POWER_LOTTO | shadow_strategy_check | N/A | shadow != fourier_rhythm_3bet | MISSING_DATA |

Notes: Watchdog checks cannot be evaluated because active_strategy_state and related data are unavailable.

## 4. Live Outcome / Drift Check
NO_LIVE_OUTCOME_DATA_AVAILABLE

## 5. Recent Failure Check
agent_tasks query failed due to missing column or table; see Evidence section. SQL probe returned errors indicating schema change or missing data.

| Failure Category | Count | Action |
|---|---:|---|
| NO_DATA / SCHEMA_ERROR | N/A | ESCALATE_TO_CTO; Investigate DB schema and pipeline |

## 6. Action Items
- ESCALATE_TO_CTO
- INVESTIGATE_DB_SCHEMA_CHANGE (agent_tasks missing expected column: failure_category)
- RESTORE or DOCUMENT expected tables: active_strategy_state, strategy_reviews, strategy_live_state
- PAUSE_AUTOMATED_MONITORING until root cause fixed

## 7. Evidence
Raw SQL probe output (from sqlite3 against lottery_api/data/lottery_v2.db):

Error: in prepare, no such column: failure_category
  SELECT failure_category, COUNT(*) AS cnt FROM agent_tasks WHERE created_at > d
         ^--- error here
=== active_strategy_state ===
NO_TABLE
=== strategy_reviews ===
NO_TABLE
=== strategy_live_state ===
NO_LIVE_OUTCOME_DATA_AVAILABLE
=== agent_tasks_failures_24h ===


--- End of evidence ---
