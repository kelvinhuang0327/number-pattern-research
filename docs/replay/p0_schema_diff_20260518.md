# P0 Schema Diff Report

**Generated:** 2026-05-18  
**Mission:** P0 Schema Stabilization  
**Branch:** feat/p0-schema-stabilization-20260518  

---

## Summary

**Overall status: IN_SYNC**

All expected governance columns are present in the live DB. No missing columns detected. The P0 migration applied 3 new governance indexes.

---

## Table: strategy_prediction_replays

### ORM Expected vs DB Actual

| Column | ORM Expected | DB Status | Notes |
|--------|-------------|-----------|-------|
| id | INTEGER PK | ✅ PRESENT | — |
| lottery_type | TEXT NOT NULL | ✅ PRESENT | — |
| target_draw | TEXT NOT NULL | ✅ PRESENT | — |
| target_date | TEXT | ✅ PRESENT | — |
| strategy_id | TEXT NOT NULL | ✅ PRESENT | — |
| strategy_name | TEXT NOT NULL | ✅ PRESENT | — |
| strategy_version | TEXT NOT NULL | ✅ PRESENT | — |
| history_cutoff_draw | TEXT | ✅ PRESENT | — |
| replay_status | TEXT NOT NULL | ✅ PRESENT | — |
| reject_reason | TEXT | ✅ PRESENT | — |
| predicted_numbers | TEXT | ✅ PRESENT | — |
| predicted_special | INTEGER | ✅ PRESENT | — |
| actual_numbers | TEXT | ✅ PRESENT | — |
| actual_special | INTEGER | ✅ PRESENT | — |
| hit_numbers | TEXT | ✅ PRESENT | — |
| hit_count | INTEGER DEFAULT 0 | ✅ PRESENT | — |
| special_hit | INTEGER DEFAULT 0 | ✅ PRESENT | — |
| replay_run_id | INTEGER FK | ✅ PRESENT | — |
| generated_at | TEXT | ✅ PRESENT | — |
| **truth_level** | TEXT | ✅ PRESENT | Governance col — triggers API contract test + drift guard |
| **source** | TEXT | ✅ PRESENT | Governance col |
| **provenance_hash** | TEXT | ✅ PRESENT | Governance col |
| **provenance_source** | TEXT | ✅ PRESENT | Governance col |
| **controlled_apply_id** | TEXT | ✅ PRESENT | Governance col — triggers drift guard |
| **dry_run_only** | INTEGER DEFAULT 0 | ✅ PRESENT | Governance col |

**Missing columns: 0**  
**Extra columns: 0**

### Indexes

| Index | Status | Notes |
|-------|--------|-------|
| sqlite_autoindex_strategy_prediction_replays_1 | ✅ EXISTS | UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id) |
| idx_spr_lottery | ✅ EXISTS | — |
| idx_spr_strategy | ✅ EXISTS | — |
| idx_spr_draw | ✅ EXISTS | — |
| idx_spr_status | ✅ EXISTS | — |
| idx_spr_run | ✅ EXISTS | — |
| idx_spr_hit | ✅ EXISTS | — |
| **idx_spr_truth_level** | ✅ ADDED by P0 migration | New governance index |
| **idx_spr_controlled_apply** | ✅ ADDED by P0 migration | New governance index |
| **idx_spr_dry_run** | ✅ ADDED by P0 migration | New governance index |

---

## Table: prediction_runs

| Status | Columns Expected | Columns Present |
|--------|-----------------|-----------------|
| ✅ IN_SYNC | 11 | 11 |

---

## Table: prediction_items

| Status | Columns Expected | Columns Present |
|--------|-----------------|-----------------|
| ✅ IN_SYNC | 10 | 10 |

---

## Table: strategy_replay_runs

| Status | Columns Expected | Columns Present |
|--------|-----------------|-----------------|
| ✅ IN_SYNC | 10 | 10 |

---

## P1 Governance Lifecycle 7-State

The P1 governance lifecycle uses these states in `replay_strategy_registry.py`:

- **ONLINE** — deployed and active in replay generation
- **OFFLINE** — previously deployed, suspended; rows preserved
- **REJECTED** — evaluated and rejected during governance review
- **OBSERVATION** — under shadow evaluation
- **RETIRED** — formally retired; rows preserved

The `truth_level` column in `strategy_prediction_replays` tracks row provenance:

- `REGENERATED` / `REGENERATED_RETROSPECTIVE`
- `ARTIFACT` / `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`
- `OFFICIAL` / `OFFICIAL_DRAW_RESULT`
- `FIXTURE_SYNTHETIC` / `FIXTURE_SYNTHETIC_INLINE`

The enum is enforced at application layer (drift guard + API route), not as SQL CHECK constraint (intentional for SQLite compatibility).

---

## Migration Action Taken

Migration `0001_p0_schema_stabilization` applied 2026-05-18:
- All 6 governance columns already present (no ALTER TABLE needed)
- 3 governance indexes added: `idx_spr_truth_level`, `idx_spr_controlled_apply`, `idx_spr_dry_run`
- DB backup created: `lottery_api/data/backups/lottery_v2_pre_p0_<ts>.db`

**Rollback:** `cp lottery_api/data/backups/lottery_v2_pre_p0_<ts>.db lottery_api/data/lottery_v2.db`
