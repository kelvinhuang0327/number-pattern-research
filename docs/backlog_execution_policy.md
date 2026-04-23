# Backlog Execution Policy

> **Version**: 1.0 · **Status**: Active  
> Transforms the scheduler from a greedy algorithm into a stable decision system.

---

## Problem Statement

A pure priority-ordered scheduler produces three failure modes:

| Problem | Symptom |
|---------|---------|
| **Priority Drift** | New high-severity findings always displace older items; the queue never drains |
| **Starvation** | P2/P3 items are never executed; medium problems become invisible |
| **Category Bias** | One category (e.g. `architecture`) monopolizes all execution slots |

---

## Solution: Execution Policy Engine

Three interoperable mechanisms address these problems:

1. **Weighted Selection** — probabilistic pool split (P0/P1 vs P2/P3)  
2. **Aging Bonus** — passive score boost for long-waiting items  
3. **Category Quota** — cap on consecutive selections from the same category  

These are controlled by a configurable **scheduler mode**.

---

## Scheduler Modes

### `strict_priority` (original behavior + fairness gate)

> Always pick the highest P0 → P1 → P2 → P3 item.  
> Fairness gate: every **N** ticks (default: 7), forces one non-P0 selection.

Use when: critical incidents, all hands on deck, controlled deploys.

### `balanced` _(recommended default)_

> 70% of ticks → P0/P1 pool · 30% → P2/P3 pool  
> Enforced via `consecutive_high` counter: after 7 high-priority ticks, force one low-priority tick.  
> Category quota still applies.

Use when: normal operations, steady-state backlog execution.

### `fairness`

> Round-robin across categories + aging score.  
> Selection algorithm: pick the category with lowest recent usage whose best candidate  
> has the highest priority level, then break ties by effective score.  
> All three failure modes are fully prevented.

Use when: diverse backlog, many categories, long-running projects.

---

## Weighted Selection Algorithm (balanced mode)

```
high_pool  = tasks where priority_level in (P0, P1)
low_pool   = tasks where priority_level in (P2, P3)

if consecutive_high >= FAIRNESS_EVERY_N:
    pick from low_pool              # force fairness
elif random() < HIGH_POOL_RATIO:
    pick from high_pool             # 70% chance
else:
    pick from low_pool              # 30% chance

if category_consecutive_count >= CATEGORY_MAX_CONSECUTIVE:
    exclude dominant category from pool
```

**Constants:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `HIGH_POOL_RATIO` | 0.70 | Fraction of ticks for P0/P1 |
| `FAIRNESS_EVERY_N` | 7 | Force non-P0 after N consecutive high picks |
| `CATEGORY_MAX_CONSECUTIVE` | 5 | Block same category after 5 consecutive selections |

---

## Aging Mechanism

Every worker tick, `apply_aging_bonus()` runs automatically.

Items waiting in QUEUED state accumulate a bonus:

```
aging_bonus += AGING_PTS_PER_INTERVAL
             per AGING_INTERVAL_HOURS of inactivity
             capped at AGING_CAP
```

**Constants:**

| Constant | Value | Effect |
|----------|-------|--------|
| `AGING_INTERVAL_HOURS` | 6 | One interval = 6h of waiting |
| `AGING_PTS_PER_INTERVAL` | 3.0 | +3 pts per interval |
| `AGING_CAP` | 30.0 | Maximum bonus ever |

**Effective score** used for ordering:
```
effective_score = priority_score + aging_bonus
```

A P2 item waiting 60 hours earns +30 pts, potentially jumping to P1 effective range.

---

## Category Quota

Tracked via `consecutive_category` and `consecutive_category_count` in `execution_policy_state`.

After 5 consecutive selections from the same category:
- That category is **excluded** from the candidate pool for this tick
- Counter resets when a different category is selected

If all categories have hit their quota simultaneously, the guard is lifted (no deadlock).

---

## Database Schema Changes

```sql
-- cto_backlog_items: new execution tracking columns
last_selected_at   TEXT,                          -- ISO timestamp of last scheduler pick
selection_count    INTEGER NOT NULL DEFAULT 0,    -- total times this item has been selected
aging_bonus        REAL    NOT NULL DEFAULT 0,    -- accumulated aging pts (0–30)

-- execution_policy_state: single-row policy config + rolling window
CREATE TABLE execution_policy_state (
    id                        INTEGER PRIMARY KEY CHECK (id = 1),
    mode                      TEXT NOT NULL DEFAULT 'balanced',
    consecutive_high          INTEGER NOT NULL DEFAULT 0,
    consecutive_category      TEXT,
    consecutive_category_count INTEGER NOT NULL DEFAULT 0,
    recent_selections         TEXT NOT NULL DEFAULT '[]',  -- JSON array, last 20
    updated_at                TEXT NOT NULL
);
```

Migrations are handled automatically in `db.init_db()`.

---

## Python Functions (`orchestrator/db.py`)

| Function | Description |
|----------|-------------|
| `get_policy_state()` | Return current policy state dict |
| `set_policy_mode(mode)` | Set `strict_priority` / `balanced` / `fairness` |
| `apply_aging_bonus()` | Apply aging pts to all waiting QUEUED items; returns count |
| `get_next_task_by_policy()` | Policy-aware task selection; updates state after pick |
| `get_policy_stats()` | Full stats dict: mode, queue snapshot, category distribution, recent selections |
| `_update_policy_state_after_selection(conn, ...)` | Internal: update rolling state + item counters |

---

## API Endpoints

### `GET /api/orchestrator/cto/backlog/policy`

Returns full policy stats.

```json
{
  "mode": "balanced",
  "consecutive_high": 3,
  "consecutive_category": "architecture",
  "consecutive_category_count": 2,
  "recent_selections": [ {"level":"P0","category":"security","task_id":42}, ... ],
  "queue_by_level": {"P0":1, "P1":4, "P2":8, "P3":3},
  "queue_by_category": {"architecture":5, "quality":4, "performance":3},
  "aging_items_count": 2,
  "policy_constants": { ... }
}
```

### `POST /api/orchestrator/cto/backlog/policy`

Change the active mode.

```json
{ "mode": "fairness" }
```

### `POST /api/orchestrator/cto/backlog/aging`

Manually trigger aging bonus application.

```json
{ "ok": true, "aged_count": 3, "message": "Applied aging bonus to 3 items" }
```

---

## Scheduler Integration (`worker_tick.py`)

On each tick:

1. `apply_aging_bonus()` — boost long-waiting items
2. `get_next_task_by_policy()` — policy-based selection (updates state)
3. Fallback: `get_next_queued_task_by_priority()` — pure priority
4. Last resort: `list_tasks(status="QUEUED", limit=1)` — FIFO

Each fallback is only reached if the previous query returns nothing.

---

## UI: Scheduler Execution Policy Panel

Located at the top of the CTO Review tab, the `#orc-policy-panel` shows:

- **Current mode badge** (color-coded: red/blue/green)
- **Mode selector + Save button** — live mode change without restart
- **Queue by level** (P0/P1/P2/P3 counts)
- **Consecutive high / category** counters
- **"⏫ 觸發 Aging"** button — manual aging trigger
- **Category distribution bar chart** (collapsible)
- **Recent 10 selections** — rolling history with level + category badges

---

## Example Execution Sequence

Given queue: 5×P0(architecture), 3×P1(quality), 4×P2(performance), 2×P3(tech_debt)

**`balanced` mode** over 10 ticks:

| Tick | consecutive_high | Pool | Selected | Category |
|------|-----------------|------|----------|----------|
| 1 | 0→1 | high | P0 architecture | architecture |
| 2 | 1→2 | high | P0 architecture | architecture |
| 3 | 2→3 | high | P0 architecture | ~~architecture~~ (quota→3) → P1 quality |
| 4 | 3→4 | high | P0 architecture | architecture |
| 5 | 4→5 | high | P1 quality | quality |
| 6 | 5→6 | high | P0 architecture | architecture |
| 7 | 6→7 | **force low** | P2 performance | performance ✓ |
| 8 | 0→1 | high | P0 architecture | architecture |
| 9 | 1→2 | 30% low | P2 performance | performance |
| 10 | 0→1 | high | P1 quality | quality |

Result: P2 items **selected twice in 10 ticks** (≥ design target of 30%).

---

## Acceptance Criteria

| Criterion | How it's met |
|-----------|-------------|
| P2/P3 items will be executed | `balanced`: forced every 7 ticks; `fairness`: category rotation |
| Different categories are selected | Category quota (≤5 consecutive) + fairness round-robin |
| Old backlog items don't get stuck | Aging bonus: +3 pts/6h, cap +30 — eventually rivals P1 |
| P0 items still have priority | 70% high-pool allocation; P0 always first within pool |

---

## Changing Mode Without Restart

```bash
# Via API
curl -X POST http://localhost:8100/api/orchestrator/cto/backlog/policy \
  -H 'Content-Type: application/json' \
  -d '{"mode": "fairness"}'

# Via UI
# CTO tab → Scheduler Execution Policy → mode dropdown → 儲存模式
```

The new mode takes effect on the **next worker tick**.
