# P88 — New Draw Source Decision Gate: Monitoring Snapshot

**Classification:** `P88_STABLE_NO_NEW_DRAW_MONITORING_SNAPSHOT`  
**Date:** 2026-05-26  
**System Status:** STABLE  

---

## 1. Phase 1 Monitoring Results

| Check | Result |
|-------|--------|
| P86 source decision guard | `SOURCE_UNAVAILABLE` |
| P82 freshness guard | `FRESHNESS_PASS` |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |
| draw_gap_detected | `false` |
| replay_gap_detected | `false` |
| Batch A coverage | `100.0%` |
| New draw detected | **NO** |

---

## 2. Classification Rationale

**Classification: STABLE_NO_NEW_DRAW**

Evidence:
- P86 returns `SOURCE_UNAVAILABLE` — no external source snapshot provided, no network read authorized, therefore no evidence of any POWER_LOTTO draw beyond 115000041
- P82 returns `FRESHNESS_PASS` — `draw_gap_detected=false`, `replay_gap_detected=false`
- DB `max_draw` remains **115000041** (2026/05/21)
- Drift guard: zero violations

Decision: **HOLD — continue monitoring. No action required.**

---

## 3. Production Baseline (Unchanged)

| Metric | Value |
|--------|-------|
| replay_rows | **46,962** |
| replay_row_changes | **0** |
| POWER_LOTTO max_draw | **115000041** |
| max_draw date | **2026/05/21** |
| max_draw numbers | `[6, 14, 22, 28, 35, 38]` |
| max_draw special | `1` |
| Batch A coverage | **100%** |
| P79 sentinels | id=46961, id=46962 (dry_run=0) |
| DB writes | **false** |

---

## 4. Source Decision Policy

### When to trigger P88 controlled refresh

P88 transitions from `STABLE_NO_NEW_DRAW` to `SOURCE_DECISION_REQUIRED` when:

1. Operator uploads a source snapshot where `source_max_draw > 115000041`
2. A read-only official API check confirms draw > 115000041
3. Manual operator verification confirms draw > 115000041

At that point:

```bash
python scripts/p86_live_monitoring_source_decision_guard.py \
  --source-snapshot /path/to/snapshot.json
# Returns SOURCE_DECISION_REQUIRED
# → STOP. Operator must choose explicit source decision.
```

### Allowed source decisions (when SOURCE_DECISION_REQUIRED)

- `uploaded_source_provided_by_operator`
- `official_api_explicitly_authorized`
- `manual_verification_required`
- `hold_no_action`

---

## 5. Forbidden Actions

The following are strictly forbidden until an explicit controlled refresh authorization exists:

| Forbidden Action |
|-----------------|
| `INSERT INTO draws` or any DB write |
| Auto-ingest without source decision |
| Create replay rows without authorization |
| Call official API for writes |
| Create new tables |
| `git reset --hard` |
| `git clean` |
| `git push --force` |
| Stage `lottery_v2.db` or `.bak` files |
| Modify lifecycle/champion/registry/strategy metadata |

---

## 6. Daily Operator Commands

```bash
# Step 1 — P86 source decision guard
python scripts/p86_live_monitoring_source_decision_guard.py

# Step 2 — P82 freshness guard
.venv/bin/python scripts/p82_replay_freshness_guard.py --lottery POWER_LOTTO

# Step 3 — If new draw snapshot available:
python scripts/p86_live_monitoring_source_decision_guard.py \
  --source-snapshot /path/to/snapshot.json
# If SOURCE_DECISION_REQUIRED → STOP. Decide.
```

---

## 7. What Happens When a New Draw is Detected

```
Source snapshot provided with max_draw > 115000041
│
└─ P86 returns: SOURCE_DECISION_REQUIRED
   │
   └─ STOP. Do NOT ingest.
      │
      ├─ Operator chooses:
      │   - uploaded_source_provided_by_operator
      │   - official_api_explicitly_authorized
      │   - manual_verification_required
      │   - hold_no_action
      │
      └─ Only after explicit decision:
         Prepare controlled apply plan (P88 controlled refresh)
         Obtain written authorization
         Proceed with controlled draw ingestion and replay apply
```

---

## 8. Evidence Chain

| Phase | Classification | PR | Commit |
|-------|---------------|----|--------|
| P83 | Stable baseline | #208 | f019ae8 |
| P84 | Browser E2E | #209 | a18523d |
| P85 | Launch closure | #210 | d386066 |
| P86 | Source decision guard | #211 | 34e7ea9 |
| P87 | Live operations runbook | #212 | 0de6044 |
| **P88** | **New draw gate — this doc** | — | — |

---

## 9. Next Steps

- **If no new draw (current state):** Continue daily monitoring. No action.
- **If new draw detected:** Re-run P86 with source snapshot → SOURCE_DECISION_REQUIRED → operator decision required before any ingestion.
- **Next classification if new draw:** `P88_SOURCE_DECISION_REQUIRED`
