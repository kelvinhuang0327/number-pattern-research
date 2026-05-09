# Replay Data Hygiene Policy

**Version:** v1.0  
**Last Updated:** 2026-05-07  
**Status:** ACTIVE  
**Authority:** This document is part of the wiki/system governance tier. It is authoritative for all agents and processes that interact with the Strategy Historical Replay store.

---

## 1. Source-of-Truth

| Component | Source-of-Truth | Notes |
|-----------|----------------|-------|
| Strategy Historical Replay data | `strategy_prediction_replays` table (DB) | Single authoritative store |
| Replay run metadata | `strategy_replay_runs` table (DB) | Run lineage, status, notes |
| Coverage reports | `outputs/replay/` | **Artifact only — NOT API/UI source** |
| UI / API | Read from DB only | Never from `outputs/` |

`outputs/replay/` contains generated audit artifacts (JSON, Markdown). They are
point-in-time snapshots for human review and are **not** the source-of-truth for
any API endpoint or UI display.

---

## 2. Old Failed Runs — Retention Policy

Old failed / broken replay runs **must never be silently deleted**.

Rationale:
- Audit traceability requires that error rows remain linkable to their source run.
- Silent deletion destroys the ability to distinguish "this strategy never failed"
  from "we deleted the evidence."
- The `strategy_replay_runs` table uses a `status` field to communicate run health.

### Allowed Run Statuses

| Status | Meaning |
|--------|---------|
| `RUNNING` | In progress |
| `DONE` | Completed successfully, all rows are valid |
| `FAILED` | Run failed mid-execution; rows may be partial |
| `FAILED_LEGACY` | Superseded broken run; kept for audit traceability only |
| `CANCELLED` | Manually stopped before completion |

Any run with status `FAILED_LEGACY` must have its `notes` field updated to
explain: what went wrong, which run supersedes it, and what the rows represent.

### Current Known Legacy Error Run

| Run ID | Lottery | Status | Reason |
|--------|---------|--------|--------|
| 3 | DAILY_539 | `FAILED_LEGACY` | Broken adapter before fix — produced 40 REPLAY_ERROR rows (daily539_f4cold×20, daily539_markov_cold×20). Superseded by run #4 and run #7. |

---

## 3. UI / API Presentation Rules

### 3.1 Summary & History Endpoints

- `/api/replay/summary` and `/api/replay/history` query **all** rows in the store.
- They must include a `data_scope` field (or equivalent) indicating this is
  `ALL_REPLAY_ROWS` coverage, not just the latest run.
- They must never hide the `error_count` for a strategy — transparency is required.

### 3.2 Freshness / Coverage Status Endpoint

- `/api/replay/freshness` must identify the **latest** successful run per lottery type.
- It must separately count `legacy_error_count` (errors from `FAILED_LEGACY` runs).
- `has_legacy_errors: true` must trigger a conservative advisory in the UI, NOT
  an alarm — legacy errors do not mean the current coverage run failed.

#### Cadence Policy v0.1

Each lottery type must have at least one `DONE` run whose `started_at` is **within the last 14 days**.

| Rule | Detail |
|------|--------|
| Max staleness | 14 days from `started_at` of latest `DONE` run |
| Excluded statuses | `FAILED_LEGACY` runs must NOT count toward cadence compliance |
| Missing DONE run | Fails cadence gate (treated as stale) |
| Gate test | `tests/test_replay_freshness_cadence.py` enforces this policy |

Rationale: replay data older than 14 days cannot represent recent lottery results. The 14-day window allows for weekend/holiday gaps while preventing long-term staleness.

### 3.3 Coverage Mode

Coverage mode must be accurately reported:

| Mode | Condition |
|------|-----------|
| `LIMITED` | Latest run covered only a subset of historical draws (window < full history) |
| `FULL` | Latest run covered the full draw history |
| `UNKNOWN` | Cannot determine from available metadata |

**Hard rule:** `LIMITED` must never be described to users as full historical coverage.

---

## 4. What Replay Data Is and Is Not

### Replay data IS:
- A historical simulation of what each registered strategy would have predicted
  for each historical draw, given only the data that was available at that time.
- An audit artifact for evaluating adapter correctness, coverage, and causal integrity.
- A basis for identifying implementation bugs (e.g., REPLAY_ERROR rows from broken adapters).

### Replay data IS NOT:
- A validated statistical edge claim.
- A strategy promotion recommendation.
- A prediction of future lottery outcomes.
- Proof that any strategy improves winning probability.

### Forbidden language in replay context:

The following terms and phrases are **forbidden** in replay API responses, UI text,
and report artifacts generated from the replay store:

| Forbidden | Reason |
|-----------|--------|
| `SIGNAL` | Reserved for governance classification only |
| `NO_SIGNAL` | Reserved for governance classification only |
| `NO_VALIDATED_EDGE` | Reserved for governance classification only |
| "best strategy" | Replay hit counts ≠ edge ranking |
| "提高中獎率" | No causal claim may be made from replay data |
| "推薦投注" | Replay is audit, not betting advice |
| promotion / auto-promotion wording | Replay ≠ governance verdict |
| edge ranking | Replay ≠ edge ranking |

---

## 5. Causal Integrity Requirement

Every row in `strategy_prediction_replays` must satisfy:

```
history_cutoff_draw < target_draw
```

This ensures no future data was used when generating the replay prediction.
Any violation is a data quality defect and must be flagged in coverage reports
and the `/api/replay/freshness` endpoint as `causal_violations > 0`.

---

## 6. Limited vs Full Coverage

- Current dataset is **limited coverage** (50-draw window per lottery).
- UI must explicitly display: *"目前為 limited coverage，非全量歷史回放"*
- `/api/replay/freshness` must return `coverage_mode: "LIMITED"` when applicable.
- Coverage reports in `outputs/replay/` must include the `data_scope` limitation note.

---

## 7. Controlled Edge Discovery vs. Replay Audit

These are distinct systems with distinct purposes:

| System | Purpose | Output | Gate |
|--------|---------|--------|------|
| Replay Audit Page | Historical audit, adapter QA | Hit counts, error counts | None required |
| Controlled Edge Discovery | Statistical edge validation | Classification result | `wiki/system/controlled_edge_discovery.md` |
| Governance | Strategy state transitions | PROMOTED / RETIRED | `wiki/system/governance.md` |

Replay summary hit counts must never be passed directly to governance as evidence.
They require formal edge validation via the Controlled Edge Discovery path first.

---

## 8. Agent Rules

- No agent may delete rows from `strategy_prediction_replays` without explicit human approval.
- No agent may update a run's status from `DONE` → `FAILED_LEGACY` without a migration script
  that is logged and committed (not executed inline).
- No agent may create a new `/api/replay/*` endpoint that reads from `outputs/`.
- No agent may add replay data to governance verdicts without formal edge validation.

---

## 9. Operation Runbook

The full operator SOP for daily checks, anomaly handling, rollback procedures, forbidden actions,
and go-live checklist is at:

**`docs/REPLAY_OPERATION_SOP.md`**

All operators must read §6 (Go-Live Checklist) before enabling production traffic on the replay API.
