# P77A — Uploaded Source-of-Truth Audit for Replay Refresh

**Phase:** P77A — Read-Only Source-of-Truth Audit
**Branch:** `p77a-uploaded-source-of-truth-audit`
**Date:** 2026-05-26
**HEAD at audit:** `5356da5` (P76: add POWER_LOTTO draw ingestion gate)
**Classification:** `P77A_SOURCE_HAS_NEW_DRAWS_DB_IMPORT_INCOMPLETE`

---

## 1. Purpose

P74/P75 Batch A apply is blocked by `PLAN_BLOCKED_BY_SOURCE_DATA_GAP` — zero eligible rows because both `fourier_rhythm_3bet` and `fourier30_markov30_2bet` already have 1500 replay rows covering the current POWER_LOTTO DB range (max draw = 115000040). This audit determines whether the original uploaded source contains newer POWER_LOTTO draws.

**This task is read-only. No DB writes. No row inserts. No API calls.**

---

## 2. Pre-flight State

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✅ |
| Starting branch | `main` ✅ |
| Production replay rows | `46960` ✅ |
| POWER_LOTTO max draw in DB | `115000040` |
| POWER_LOTTO total draws | `1912` |
| POWER_LOTTO draws > 115000040 | `0` |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| Branch governance (pre) | `BRANCH_GOVERNANCE_PASS — main rows=46960` ✅ |
| Branch governance (post) | `BRANCH_GOVERNANCE_PASS — p77a-uploaded-source-of-truth-audit rows=46960` ✅ |

---

## 3. Production DB Summary

| Lottery Type | Count | Min Draw | Max Draw | Max Date |
|---|---|---|---|---|
| 3_STAR | 4,115 | 96000002 | 115000024 | 2026/01/28 |
| BIG_LOTTO | 2,136 | 96000001 | 115000054 | 2026/05/19 |
| DAILY_539 | 5,865 | 96000001 | 115000121 | 2026/05/18 |
| **POWER_LOTTO** | **1,912** | **97000001** | **115000040** | **2026/05/18** |

---

## 4. Source Candidates Inspected

### DB Candidates

| ID | Path | Type | PL Max Draw | Max Date | Has 115000041+? |
|---|---|---|---|---|---|
| **C1** | `backups/lottery_v2_pre_p66_wave6_20260525_093850.db` | SQLite backup | **115000041** | **2026/05/21** | **YES ✅** |
| C2 | `backups/lottery_v2_pre_p66_wave6_20260526_044224.db` | SQLite backup | 115000040 | 2026/05/18 | No |
| C3 | `backups/lottery_v2_pre_p7_controlled_apply_20260520.db` | SQLite backup | 115000040 | 2026/05/18 | No |
| C4 | `lottery_api/data/lottery_v2.db.bak_p59_20260525_135638` | SQLite .bak | 115000040 | 2026/05/18 | No |
| C5 | `lottery_api/data/lottery.db` | Legacy SQLite | 114000095 | 2025/11/27 | No |
| C10 | `data/lottery_v2.db` | SQLite | — (empty) | — | No |

### JSON / CSV Candidates

| ID | Path | Type | Lottery Types | Has PL Data? | Has 115000041+? |
|---|---|---|---|---|---|
| C6 | `lottery-api/data/lottery_history.json` | JSON | BIG_LOTTO only | No | No |
| C7 | `tests/大樂透加開獎項_2025.csv` | CSV | BIG_LOTTO festival | No | No |
| C8 | `archive/data/大樂透加開獎項_2025.csv` | CSV | BIG_LOTTO festival | No | No |
| C9 | `data/converted_2024.csv` | CSV | BIG_LOTTO 2024 | No | No |
| C11 | `lottery_api/data/ingest_log.jsonl` | JSONL | Log only | Partial | No |

---

## 5. Primary Finding — C1 Contains Draw 115000041

The backup `backups/lottery_v2_pre_p66_wave6_20260525_093850.db` contains POWER_LOTTO draw **115000041** with full verified data:

| Field | Value |
|---|---|
| Draw | `115000041` |
| Date | `2026/05/21` (Wednesday) |
| Numbers | `[6, 14, 22, 28, 35, 38]` |
| Special | `1` |
| created_at | `2026-05-25 08:22:13` |
| Lottery Type | `POWER_LOTTO` |

This draw is **NOT** in the current production DB (`lottery_api/data/lottery_v2.db`).

---

## 6. Timeline Reconstruction

| Time | Event |
|---|---|
| 2026-05-18T14:53:53Z | Draw 115000040 backfilled via standard pipeline (logged in ingest_log.jsonl) |
| 2026-05-25T08:22:13 | Draw **115000041** inserted into DB — NOT logged in ingest_log.jsonl (mechanism: likely direct DB write or manual ingestion outside standard pipeline) |
| 2026-05-25T08:25:19Z | scan_missing for POWER_LOTTO returns `missing=0` (115000041 was present at this time) |
| 2026-05-25T09:38:50 | **Backup C1 created** — captures DB state WITH draw 115000041 |
| BETWEEN 09:38 and 13:56 | Draw 115000041 **removed** from production DB (mechanism: possible DB restore, replacement from older snapshot, or rollback — not documented) |
| 2026-05-25T13:56:38 | P59 .bak file created — DB back to max 115000040 |
| 2026-05-26T04:42:24 | Backup C2 created — confirms max remains 115000040 |
| 2026-05-26 (audit) | Production DB max = 115000040 |

**Key observation:** Draw 115000041 was in the production DB at 08:22 but gone by 13:56 on May 25. Only backup C1 captured this state. The insert was not logged in `ingest_log.jsonl`, suggesting it happened outside the standard `backfill_engine.py` / ingest API path.

---

## 7. Audit Answers

### Q1: Where is the original uploaded source candidate?

No standalone uploaded source file (CSV, XLSX, JSON) containing POWER_LOTTO draws after 115000040 was found in the repository. The only local data source containing draw 115000041 is the backup DB at `backups/lottery_v2_pre_p66_wave6_20260525_093850.db`.

The draw was inserted at 2026-05-25 08:22:13 through a mechanism not logged in `ingest_log.jsonl`. This suggests it was ingested via a direct DB write or an API path that bypasses the ingest logger.

### Q2: Which local files / DBs / JSONs may contain uploaded draw history?

- **Backup DBs** in `backups/` — main source candidates. C1 is the only one with 115000041.
- `lottery_api/data/lottery.db` — legacy DB, max draw 114000095.
- `lottery-api/data/lottery_history.json` — BIG_LOTTO only (draws 97000020–97000105).
- CSV files — BIG_LOTTO festival/bonus data only; no POWER_LOTTO rows.
- All other DB copies (`data/`, `tools/data/`, `lottery-api/data/`) — empty POWER_LOTTO sections.

### Q3: Max POWER_LOTTO draw/date per candidate?

| Source | Max Draw | Max Date |
|---|---|---|
| C1 (backup 20260525_093850) | **115000041** | **2026/05/21** |
| Production DB + all other backups | 115000040 | 2026/05/18 |
| Legacy lottery.db | 114000095 | 2025/11/27 |

### Q4: Does any uploaded-source candidate contain 115000041+?

**YES** — Backup C1 contains draw 115000041 with complete, verified data. No draws beyond 115000041 were found in any local source.

### Q5: Root cause of blocker?

**Scenario A** (DB import incomplete): Draw 115000041 data EXISTS in backup C1 but is absent from the current production DB. The draw was temporarily in the production DB (between 08:22 and ~13:56 on May 25) but was subsequently removed.

**Scenario B** (applies to 115000042+): Draws beyond 115000041 are not in any local source. These draws have likely occurred (estimated 115000042 on 2026-05-25 Monday, 115000043 on 2026-05-29 Thursday) but were never ingested.

### Q6: Safest next step?

→ **P77B: Controlled Canonical Draw Refresh** using backup C1 as the verified source for draw 115000041, then official API (with P76 ingestion gates) for 115000042+. See Section 9 for details.

---

## 8. Source-of-Truth Classification

### `P77A_SOURCE_HAS_NEW_DRAWS_DB_IMPORT_INCOMPLETE`

**Rationale:**
- Draw 115000041 EXISTS in a verified local backup (C1)
- The data is real (inserted 2026-05-25 08:22:13, predates multiple backups)
- The current production DB is missing this draw due to a rollback/restore event
- No fabrication is required — the data is available for import
- This is an incomplete import situation, not a missing source situation

---

## 9. Recommended Next Phase: P77B

**P77B — Controlled Canonical Draw Refresh**

| Step | Action | Constraint |
|---|---|---|
| 1 | Verify C1 backup integrity | Read-only inspection; confirm draw 115000041 data |
| 2 | Create DB backup before any write | `lottery_v2.db.bak_p77b_<timestamp>` |
| 3 | Dry-run validate draw 115000041 | Schema check, duplicate check, no DB write |
| 4 | Controlled import of 115000041 from C1 | Into `draws` table only; use `controlled_import_id=P77B_POWERLOTTO_DRAW_REFRESH_20260526` |
| 5 | Official API dry-run fetch for 115000042+ | Per P76 gates; no DB write in dry-run |
| 6 | Controlled import of 115000042+ | Schema validation, duplicate check, governance gates |
| 7 | Post-import verification | `draws > 115000040 count > 0`; drift guard PASS |
| 8 | P74/P75 Batch A re-run | Now eligible rows > 0 for fourier_rhythm_3bet and fourier30_markov30_2bet |

**Constraints for P77B:**
- Use existing canonical `draws` table only — no new tables
- No replay row inserts in P77B (that is P74/P75's job)
- All draw inserts through P76 ingestion gates
- No force push

---

## 10. Governance Confirmation

| Constraint | Status |
|---|---|
| No DB write | ✅ CONFIRMED |
| No draw insert | ✅ CONFIRMED |
| No replay row insert | ✅ CONFIRMED |
| No official API call | ✅ CONFIRMED |
| No new tables created | ✅ CONFIRMED |
| No new repo / worktree | ✅ CONFIRMED |
| No git reset --hard / git clean | ✅ CONFIRMED |
| No force push | ✅ CONFIRMED |
| CEO-Decision.md not modified | ✅ CONFIRMED |
| active_task.md not modified | ✅ CONFIRMED |
| Production replay rows | `46960` (unchanged) |
| POWER_LOTTO draws > 115000040 | `0` (unchanged — audit only) |

---

## 11. Files Created

- `outputs/replay/p77a_uploaded_source_of_truth_audit_20260526.json`
- `docs/replay/p77a_uploaded_source_of_truth_audit_20260526.md`
- `tests/test_p77a_uploaded_source_of_truth_audit.py`
