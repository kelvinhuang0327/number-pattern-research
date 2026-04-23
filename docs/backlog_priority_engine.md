# Backlog Priority Engine

> **Version**: 1.0 · **Status**: Active  
> Transforms the CTO backlog from a flat list into a decision-ready ranked system.

---

## Overview

Every item added to the CTO backlog is automatically assigned a **priority score** (0–100) and a **priority level** (P0–P3). Items are then globally ranked so the worker scheduler always claims the highest-priority task first.

---

## Priority Formula

```
priority_score = (severity_pts × 0.35)
              + (impact_score  × 0.30)
              + (urgency_pts   × 0.20)
              + (category_weight × 10.0)
              + recency_pts
```

Capped at **100**. CRITICAL items always score ≥ 85 regardless of recency.

### Severity Points (`severity_pts`)

| Severity   | Points |
|------------|--------|
| CRITICAL   | 100    |
| HIGH       | 70     |
| MEDIUM     | 40     |
| LOW        | 15     |

### Urgency Points (`urgency_pts`)

| Urgency    | Points |
|------------|--------|
| IMMEDIATE  | 100    |
| HIGH       | 80     |
| SHORT      | 55     |
| MEDIUM     | 30     |
| LOW        | 10     |

### Category Weights (`category_weight × 10`)

| Category     | Weight | Score contribution |
|--------------|--------|-------------------|
| architecture | 1.0    | +10               |
| validation   | 1.0    | +10               |
| security     | 1.0    | +10               |
| performance  | 0.8    | +8                |
| quality      | 0.7    | +7                |
| tech_debt    | 0.6    | +6                |
| uiux         | 0.5    | +5                |
| other        | 0.4    | +4                |
| knowledge    | 0.3    | +3                |

### Recency Bonus (`recency_pts`)

| Age          | Bonus | Note                          |
|--------------|-------|-------------------------------|
| ≤ 3 days     | +5    | Fresh findings get a boost    |
| ≤ 7 days     | +3    | Still recent                  |
| > 7 days     | 0     |                               |
| CRITICAL     | —     | Immune; always ≥ 85           |

---

## Priority Levels

| Level | Score Range | Color    | Meaning                     |
|-------|-------------|----------|-----------------------------|
| P0    | ≥ 80        | #f85149  | Critical — act immediately  |
| P1    | ≥ 58        | #d29922  | High — next sprint          |
| P2    | ≥ 35        | #58a6ff  | Medium — schedule it        |
| P3    | < 35        | #8b949e  | Low — backlog grooming      |

---

## Sort Order

Items are ranked globally by:

1. `priority_level` ASC (`P0 < P1 < P2 < P3`)
2. `priority_score` DESC (higher score first within same level)
3. `id` ASC (stable tie-breaking by insertion order)

The `rank` column is updated atomically whenever items are inserted in batch or `/rescore` is called.

---

## Database Schema

```sql
-- cto_backlog_items additions
priority_score  REAL     NOT NULL DEFAULT 0,   -- 0-100
priority_level  TEXT     NOT NULL DEFAULT 'P3', -- P0/P1/P2/P3
rank            INTEGER                          -- global rank 1..N

-- Index for fast priority queries
CREATE INDEX idx_cbi_priority ON cto_backlog_items(priority_level, priority_score DESC);
```

---

## Python Functions (`orchestrator/db.py`)

### `compute_priority_score(severity, impact_score, urgency, category, created_at=None)`

Computes and returns `(float priority_score, str priority_level)`.

```python
score, level = compute_priority_score("HIGH", 75, "SHORT", "architecture")
# → (score=75.25, level="P1")
```

### `rescore_all_backlog_items()`

Recomputes `priority_score`, `priority_level`, and `rank` for every item in the table. Returns a list of all items sorted by rank. Call after bulk inserts or when scoring constants change.

### `list_cto_backlog_items_prioritized(status_filter=None, limit=200)`

Returns items sorted by priority. Optional `status_filter` is a list of task status strings (e.g. `["QUEUED", "RUNNING"]`).

### `get_next_queued_task_by_priority()`

Returns the single highest-priority `QUEUED` agent_task for the worker scheduler. Falls back gracefully for tasks with no backlog entry (treated as P3/score=0).

---

## API Endpoints

### `GET /api/orchestrator/cto/backlog/prioritized`

Returns all backlog items sorted by priority.

**Query params:**
- `limit` (int, default 200, max 500)
- `active_only` (bool) — only QUEUED/RUNNING items

**Response:**
```json
{
  "items": [ ... ],
  "count": 42,
  "level_counts": { "P0": 2, "P1": 8, "P2": 20, "P3": 12 }
}
```

### `POST /api/orchestrator/cto/backlog/rescore`

Recomputes priority for all items and updates ranks.

**Response:**
```json
{
  "ok": true,
  "rescored_count": 42,
  "level_counts": { "P0": 2, "P1": 8, "P2": 20, "P3": 12 },
  "top_10": [ ... ]
}
```

### `GET /api/orchestrator/cto/backlog/preview-score`

Preview the priority score for given inputs without inserting anything.

**Query params:** `severity`, `impact_score`, `urgency`, `category`

**Response:**
```json
{
  "priority_score": 75.25,
  "priority_level": "P1",
  "formula_breakdown": {
    "severity_pts": 70,
    "urgency_pts": 55,
    "severity_contribution": 24.5,
    "impact_contribution": 22.5,
    "urgency_contribution": 11.0,
    "category_contribution": 10.0,
    "category_weight": 1.0
  }
}
```

---

## Scheduler Integration

`orchestrator/worker_tick.py` now calls `db.get_next_queued_task_by_priority()` instead of `db.list_tasks(status="QUEUED", limit=1)`. The new query uses a `LEFT JOIN` with `cto_backlog_items` so that:

- CTO-sourced tasks are sorted by their assigned priority level/score
- Regular tasks (no backlog entry) default to P3/score=0 and are claimed after all CTO-priority tasks
- Fallback to FIFO (`list_tasks`) is retained in case the priority query returns nothing

---

## UI Behavior

Inside the CTO Run Detail view, a **"Backlog 優先級排序"** panel shows:

- **Level count badges**: P0 / P1 / P2 / P3 counts with their respective colors
- **"⟳ 重算全部優先級" button**: calls `POST /rescore`; reloads the detail view after 1.2s
- **High-priority block (P0/P1)**: red-bordered section listing each item with priority badge, score bar, severity, category, live task status, and global rank
- **Lower-priority section (P2/P3)**: collapsible `<details>` with a simplified row per item

### Priority Colors

| Level | Hex       |
|-------|-----------|
| P0    | `#f85149` |
| P1    | `#d29922` |
| P2    | `#58a6ff` |
| P3    | `#8b949e` |

---

## Example Ranking

Given a batch insert of 4 items:

| #  | Severity | Impact | Urgency   | Category     | Score  | Level |
|----|----------|--------|-----------|--------------|--------|-------|
| 1  | CRITICAL | 90     | IMMEDIATE | security     | 100.0  | P0    |
| 2  | HIGH     | 75     | SHORT     | architecture | 75.25  | P1    |
| 3  | MEDIUM   | 60     | MEDIUM    | quality      | 43.0   | P2    |
| 4  | LOW      | 30     | LOW       | knowledge    | 17.25  | P3    |

Worker claims item #1 first, then #2, and so on.

---

## Triggering Rescore

Rescore happens automatically:
1. On every **batch add** (`POST /api/orchestrator/cto/backlog/batch`)
2. On demand via `POST /api/orchestrator/cto/backlog/rescore`
3. Via the "⟳ 重算全部優先級" button in the UI

Individual inserts (`POST /api/orchestrator/cto/backlog`) compute priority inline on insert; rank is not recomputed unless rescore is called.
