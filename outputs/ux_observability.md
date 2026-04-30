UX Observability — Orchestration Events (last 24h)

Summary

- Source: runtime/agent_orchestrator/orchestrator.db agent_task_runs (last 24h).
- UI surface: Frontend orchestration panel (index.html + src/ui/OrchestrationManager.js) renders run outcomes as free text and maps classes via _outcome_class (success/error/muted/neutral).
- lottery_api: No per-event explicit handlers found for these outcome tokens in lottery_api/ (search returned no matches).

Event coverage (last 24h)

| event_type | count | last_seen (UTC) | UI classification (OrchestrationManager) | Explicit support in lottery_api | Gap note |
|------------|------:|----------------:|------------------------------------------:|:-------------------------------:|:--------|
| LIGHT_WORKER_SKIP_IDLE_NO_TASK | 73 | 2026-04-28T17:56:17.546533+00:00 | muted | No | displayed as muted text; OK but no dedicated label/tooltip |
| LIGHT_WORKER_SKIP_SLOTS_FULL | 1 | 2026-04-28T17:53:14.289948+00:00 | muted | No | muted |
| WORKER_SKIP_DAEMON_PROVIDER | 48 | 2026-04-28T17:51:22.475938+00:00 | muted | No | muted |
| PLANNER_SKIP_PREV_RUNNING | 45 | 2026-04-28T17:51:22.023160+00:00 | muted | No | muted |
| LIGHT_WORKER_TIMEOUT | 2 | 2026-04-28T17:47:07.727544+00:00 | neutral | No | neutral — no special UI affordance for timeouts |
| LIGHT_WORKER_CLAIMED | 14 | 2026-04-28T17:42:06.408585+00:00 | success | No | shown with success styling via _outcome_class → good visibility |
| PLANNER_CREATE_FALLBACK_TASK | 5 | 2026-04-28T17:41:21.890022+00:00 | neutral | No | NO explicit UI support; marked HIGH priority per handoff |
| PLANNER_SKIP_FALLBACK_DAILY_CAP | 10 | 2026-04-28T17:41:21.884619+00:00 | muted | No | muted |
| PLANNER_SKIP_MONITORING_DAILY_CAP | 7 | 2026-04-28T17:41:21.873271+00:00 | muted | No | muted (search: referenced in orchestrator code but not lottery_api) |
| PLANNER_REPLACE_WITH_MONITORING | 39 | 2026-04-28T17:41:21.867478+00:00 | neutral | No | neutral — no specific label or explanation in UI |
| LIGHT_WORKER_COMPLETED | 13 | 2026-04-28T17:34:57.029962+00:00 | neutral | No | completed appears as text (not mapped to 'success' by _outcome_class) — potential UI inconsistency |
| WORKER_MANUAL_TRIGGERED | 1 | 2026-04-28T16:28:04.791443+00:00 | neutral | No | neutral |
| PLANNER_PRODUCED | 42 | 2026-04-28T16:26:12.558820+00:00 | success | No | good visibility (mapped to success) |
| PLANNER_PROVIDER_FALLBACK | 42 | 2026-04-28T16:26:12.554211+00:00 | neutral | No | neutral — consider 'fallback' badge |
| PLANNER_COLD_REGIME_TASK | 42 | 2026-04-28T16:26:12.552292+00:00 | neutral | No | neutral |
| PLANNER_MANUAL_TRIGGERED | 3 | 2026-04-28T16:26:12.305159+00:00 | neutral | No | neutral |
| PLANNER_SKIP_DEDUPE | 6 | 2026-04-28T15:31:18.685798+00:00 | muted | No | muted |
| CTO_PROVIDERS_UPDATED | 1 | 2026-04-28T15:17:27.617480+00:00 | neutral | No | neutral |
| PLANNER_SKIP_DUPLICATE_MONITORING | 6 | 2026-04-28T15:01:17.797280+00:00 | muted | No | muted |
| PLANNER_LONG_RUNNER_ACTIVE | 2 | 2026-04-28T14:01:16.665277+00:00 | neutral | No | long-runner panel exists but this exact outcome not specially annotated |
| PROVIDERS_UPDATED | 3 | 2026-04-28T13:57:17.188763+00:00 | neutral | No | neutral |
| COPILOT_DAEMON_STARTED | 5 | 2026-04-28T13:30:38.812691+00:00 | neutral | No | neutral |
| WORKER_FINALIZED | 38 | 2026-04-28T10:24:28.537427+00:00 | success | No | success mapping applied |
| WORKER_HEARTBEAT | 31 | 2026-04-28T10:23:54.578513+00:00 | muted | No | muted |
| COPILOT_DAEMON_CLAIMED | 38 | 2026-04-28T10:18:14.214237+00:00 | success | No | success mapping |
| WORKER_CLAIMED | 38 | 2026-04-28T10:18:14.207784+00:00 | success | No | success mapping |
| LIGHT_WORKER_SKIP_CPU_OVERLOAD | 3 | 2026-04-28T07:37:58.193180+00:00 | muted | No | muted |
| PLANNER_SKIP_SOFT_SUPPRESS | 20 | 2026-04-28T07:33:52.064227+00:00 | muted | No | muted |
| PLANNER_SKIP_STUCK_TASK | 1 | 2026-04-28T06:18:39.310222+00:00 | muted | No | muted |
| PLANNER_SKIP_PROVIDER_FAILURE | 1 | 2026-04-28T04:54:41.052420+00:00 | muted | No | muted |
| PLANNER_FALLBACK_LOCAL | 1 | 2026-04-28T04:54:41.044652+00:00 | neutral | No | neutral |
| PLANNER_RETRY_TYPE_BLOCK | 1 | 2026-04-28T04:53:23.379326+00:00 | neutral | No | neutral |
| WORKER_FAILED | 1 | 2026-04-28T04:39:18.868243+00:00 | error | No | error styling applied |
| PLANNER_SKIP_DISABLED | 6 | 2026-04-27T01:58:42.475734+00:00 | muted | No | muted |
| WORKER_SKIP_DISABLED | 6 | 2026-04-27T01:58:42.458343+00:00 | muted | No | muted |

Findings and gap summary

- The orchestration UI (frontend) renders run outcomes generically; visually important outcomes (PRODUCED, CLAIMED, FINALIZED, FAILED, SKIP, HEARTBEAT) are mapped to three visual classes via _outcome_class. Many newer domain-specific outcomes (e.g., CREATE_FALLBACK_TASK, PROVIDER_FALLBACK, REPLACE_WITH_MONITORING) are shown only as neutral text.
- lottery_api contains no explicit per-event UI logic for these tokens; orchestrator module owns run outcomes and the frontend mapping.
- High priority gap: PLANNER_CREATE_FALLBACK_TASK — per handoff, if no UI support mark HIGH PRIORITY. Currently neutral → no distinct badge or tooltip explaining fallback creation.

Recommendations (prioritized)

1. High (P0): PLANNER_CREATE_FALLBACK_TASK — add a clear badge (e.g., 'FALLBACK TASK CREATED') and a tooltip explaining why a fallback task was created and provide a link to the task (task_id). This is critical for operator awareness.
2. Medium (P1): PLANNER_PROVIDER_FALLBACK, PLANNER_FALLBACK_LOCAL — show 'FALLBACK' badge and reason (provider failure, local fallback). Improves root-cause triage.
3. Medium (P1): LIGHT_WORKER_TIMEOUT, LIGHT_WORKER_COMPLETED — consider mapping COMPLETED → success and TIMEOUT → error/warning for consistency.
4. Low (P2): PLANNER_REPLACE_WITH_MONITORING, PLANNER_COLD_REGIME_TASK, PLANNER_RETRY_TYPE_BLOCK — add optional tooltip descriptions where operators may want context.

Acceptance notes

- All observations derived from runtime DB + frontend code analysis; no source files modified.
- For any UI change, prefer minimal additions: map string keywords to _outcome_class and add badges/tooltips in OrchestrationManager rendering.

Generated at: 2026-05-01T02:30:30+08:00

- Validation: event set re-extracted from runtime/agent_orchestrator/logs/*.jsonl on 2026-05-01T02:30:30+08:00. See outputs/task_result_ux_observability_20260501.json for the extracted event list and priorities.
