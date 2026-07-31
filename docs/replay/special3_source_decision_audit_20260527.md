# P102 Special3 Draw Source Decision Audit — 2026-05-27

## Summary

| Field | Value |
|---|---|
| **Phase** | P102 |
| **Classification** | `P102_SPECIAL3_SOURCE_DECISION_HOLD_NO_LOCAL_SOURCE` |
| **Audit Status** | HOLD |
| **draw > history_end found locally** | `false` |
| **Generated** | 2026-05-27 |

P102 performs a read-only audit of all local repo sources to determine whether a new 3_STAR draw (draw > 115000024) exists anywhere in the codebase. This phase does **not** ingest data, does not evaluate predictions, and does not write to any database.

---

## P101 / P100 Input State

| Field | Value |
|---|---|
| **P101 artifact** | `outputs/replay/special3_actual_draw_monitor_20260527.json` |
| **P101 classification** | `P101_SPECIAL3_ACTUAL_DRAW_MONITOR_HOLD` |
| **P100 artifact** | `outputs/replay/special3_prospective_evaluation_20260527.json` |
| **P100 classification** | `P100_SPECIAL3_PROSPECTIVE_EVALUATION_HOLD_NO_ACTUAL_DRAW` |
| **P99/P100 history_end_draw** | `115000024` |

---

## Phase 1 — Source Availability Audit

### Candidate Source Table

| # | Path | Classification | Supports 3_STAR | New Draw (> 115000024) | Notes |
|---|---|---|---|---|---|
| 1 | `lottery_api/fetcher/taiwan_lottery_fetcher.py` | `script_only` | No | No | SOURCE_CONFIG covers BIG_LOTTO / POWER_LOTTO / DAILY_539 only. No 3_STAR API endpoint. |
| 2 | `lottery_api/data/ingest_log.jsonl` | `artifact_only_not_source` | No | No | 0 entries for `lottery_type=3_STAR`. Never ingested via fetcher. |
| 3 | `lottery_api/data/lottery_v2.db` (live DB) | `artifact_only_not_source` | No | No | 3_STAR max=115000024, 4115 draws. Current baseline — not a source. |
| 4 | `backups/` (16 backup DBs) | `artifact_only_not_source` | No | No | All 16 checked. All have max=115000024, count=4115. No newer draws. |
| 5 | `research/3_star_analysis/` | `historical_report` | No | No | Scripts + reports only. Operates on DB data. No raw draw CSV/JSON. |
| 6 | `scripts/special3_*.py` (4 scripts) | `script_only` | No | No | Read-only analysis/backtest. No raw draw source data embedded. |
| 7 | `data/rolling_monitor_DAILY_539.json` | `artifact_only_not_source` | No | No | DAILY_539 draw IDs 115000025–115000030+. Not 3_STAR draws. |
| 8 | `archive/data/*.csv`, `data/*.csv`, `tests/*.csv` | `artifact_only_not_source` | No | No | BIG_LOTTO supplement draws, sample data. No 3_STAR draw records. |
| 9 | `rejected/*.json` | `historical_report` | No | No | Strategy metadata. Draw refs are DAILY_539 context. lottery_type absent. |
| 10 | `outputs/replay/special3_*.json` | `artifact_only_not_source` | No | No | Phase artifacts only. Not raw draw source data. |

**Total sources inspected**: 10  
**Sources with new draw (> 115000024)**: 0

---

## Phase 2 — Key Findings

### Official Fetcher Gap

The `taiwan_lottery_fetcher.py` API client covers exactly three lottery types:

```
BIG_LOTTO   → /Lottery/Lotto649Result
POWER_LOTTO → /Lottery/SuperLotto638Result
DAILY_539   → /Lottery/Daily539Result
```

**3_STAR has no registered API endpoint.** This means 3_STAR data has never been auto-fetched by the ingestion pipeline. All 4,115 historical 3_STAR draws were ingested through a different (manual or batch) method not reflected in the current ingest log.

### Backup DB Sweep

All 16 backup databases were read-only queried:
- Range: `lottery_v2_pre_p0_20260519` → `lottery_v2.db.bak_p94_pre_apply_20260526`
- Result: **every backup has 3_STAR max=115000024, count=4115**
- No snapshot was taken after a newer 3_STAR draw arrived

### Ingest Log

`lottery_api/data/ingest_log.jsonl`: **0 rows** with `lottery_type=3_STAR`. Confirmed 3_STAR has never been auto-ingested through the fetcher pipeline.

---

## HOLD Classification

`P102_SPECIAL3_SOURCE_DECISION_HOLD_NO_LOCAL_SOURCE`

No local source in this repository contains a new 3_STAR draw (draw > 115000024). The pipeline is blocked at the data availability layer.

---

## What NOT to Do

- **DO NOT** fabricate or infer a draw result
- **DO NOT** add a 3_STAR API endpoint without explicit authorization
- **DO NOT** ingest any draw data without explicit authorization + controlled procedure
- **DO NOT** evaluate P99 predictions against a draw that does not exist in DB
- **DO NOT** promote any Special3 strategy to production

---

## Recommended Next Action

User must choose one of two paths:

| Option | Description | Next Phase |
|---|---|---|
| **A** | Provide a raw 3_STAR draw CSV/JSON file containing draws > 115000024 for controlled ingestion planning | P103: Controlled Ingestion Plan |
| **B** | Authorize adding a 3_STAR API endpoint to `taiwan_lottery_fetcher.py` and define an official ingestion procedure | P103: API Endpoint + Ingestion Plan |

Without an explicit source authorization, the evaluation pipeline (P100 → EVALUATED → P101 → READY → P102+) remains blocked.

---

## Governance Verification

| Invariant | Status |
|---|---|
| DB writes | `false` |
| DB ingestion | `false` |
| Replay row inserts | `false` |
| Strategy promotion | `false` |
| 4_STAR backtest | `false` |
| Special3 production promotion | `false` |
| replay_rows | 54,462 (unchanged) |
| POWER_LOTTO max_draw | 115000041 (unchanged) |
| Forbidden file staging | CLEAN |

---

## Output Artifacts

| Artifact | Path |
|---|---|
| **JSON** | `outputs/replay/special3_source_decision_audit_20260527.json` |
| **Markdown** | `docs/replay/special3_source_decision_audit_20260527.md` |
| **Tests** | `tests/test_p102_special3_source_decision_audit.py` |

---

## P103 Readiness Gate

| Gate | Status |
|---|---|
| **P103 gate** | `NOT_YET_ELIGIBLE` |
| **Trigger A** | User provides raw 3_STAR draw file with draws > 115000024 |
| **Trigger B** | User authorizes 3_STAR API endpoint addition to fetcher |

---

## Phase Chain Summary

| Phase | Classification | Status |
|---|---|---|
| P96 | Governance Baseline Repair | COMPLETE (PR #225) |
| P97 | Special3/Special4 Dry-Run Closure | COMPLETE (PR #226) |
| P98 | Special3 OOS + Permutation Review | COMPLETE (PR #227) |
| P99 | Special3 Prospective Dry-run Planning | COMPLETE (PR #228) |
| P100 | Special3 Prospective Evaluation Gate | HOLD (PR #229) — awaiting actual draw |
| P101 | Special3 Actual Draw Availability Monitor | HOLD (PR #230) — awaiting actual draw |
| **P102** | **Special3 Draw Source Decision Audit** | **HOLD — no local source with new draw** |
| P103 | Controlled Ingestion Plan or API Endpoint Plan | NOT_YET_ELIGIBLE |

---

## 4_STAR Status

4_STAR draws = 0 in DB. `DATA_GAP_BLOCKING` status unchanged. No 4_STAR backtest authorized.
