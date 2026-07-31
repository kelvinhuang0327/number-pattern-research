# P103 Special3 Source Acquisition Decision

**Phase**: P103  
**Generated**: 2026-05-27  
**Classification**: `P103_SPECIAL3_SOURCE_ACQUISITION_DECISION_READY`  
**Default Recommendation**: HOLD_AWAITING_USER_SOURCE  

---

## Summary

P102 audited all local sources and confirmed no 3_STAR draw > 115000024 exists in the repository, any backup DB, or any raw file. P103 defines the three authorized paths for acquiring the next 3_STAR draw source. No ingestion, no DB writes, no strategy promotion occur in this phase. The decision artifact is **READY** — the default recommendation is **HOLD** until the user selects an option.

---

## P102 Input State

| Field | Value |
|---|---|
| P102 Classification | `P102_SPECIAL3_SOURCE_DECISION_HOLD_NO_LOCAL_SOURCE` |
| history_end_draw | 115000024 |
| DB max 3_STAR draw | 115000024 |
| 3_STAR draws in DB | 4,115 |
| 4_STAR draws in DB | 0 |
| Sources inspected | 10 |
| Sources with new draw | 0 |
| Backup DBs checked | 16 |
| Backup DBs with new draw | 0 |
| Fetcher API supports 3_STAR | false |
| Ingest log 3_STAR entries | 0 |
| Local raw draw files found | 0 |
| P103 gate (as of P102) | NOT_YET_ELIGIBLE |

---

## Phase 1 — Source Gap Reconfirmation

P102 source audit result is authoritative:

- No local source contains any 3_STAR draw > 115000024
- `taiwan_lottery_fetcher.py` SOURCE_CONFIG: `['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']` — no `3_STAR` entry
- All 16 backup DBs: max = 115000024, count = 4,115 — identical to live DB
- `ingest_log.jsonl`: 0 entries for `lottery_type=3_STAR` — never auto-ingested
- No CSV, XLSX, or JSON raw 3_STAR draw file found anywhere in repo
- P103 remains blocked unless user provides source or authorizes endpoint addition

---

## Phase 2 — Source Acquisition Options Matrix

### Option A — User Uploads Raw 3_STAR Source File

| Property | Detail |
|---|---|
| Accepted formats | CSV, JSON, XLSX |
| Required fields | draw number, draw date, 3-digit result |
| Leading-zero preservation | **REQUIRED** — results are fixed-width 3-digit strings |
| Safety level | HIGHEST |
| Authorization needed | User provides file |
| DB writes | false |
| Ingestion | false (in P103) |
| Next phase | P104_UPLOADED_SOURCE_VALIDATION |
| Current status | **BLOCKED** — no file provided as of 2026-05-27 |

**Leading-zero requirement**: 3_STAR results are 3-digit fixed-width. Values like `007`, `042`, `100` must be stored as strings. CSV/XLSX parsers that cast to integer will corrupt results. Validation must verify leading-zero integrity before any ingestion planning proceeds.

**Next phase action (P104)**: Validate file schema, draw range, leading-zero integrity, deduplication against existing DB draws, then produce ingestion plan.

---

### Option B — Add Official 3_STAR API Endpoint to Fetcher

| Property | Detail |
|---|---|
| Target file | `lottery_api/fetcher/taiwan_lottery_fetcher.py` |
| Change scope | Add `3_STAR` entry to `SOURCE_CONFIG` |
| Discovery mode | Read-only — no DB writes during discovery |
| Authorization needed | **Explicit user authorization required** |
| DB writes | false |
| Ingestion | false (in P103/P104 discovery) |
| Next phase | P104_OFFICIAL_ENDPOINT_DISCOVERY |
| Current status | **BLOCKED** — no authorization as of 2026-05-27 |

**Discovery constraints**:
- No DB writes during endpoint discovery phase
- HTTP GET only — read-only requests
- Results logged to `outputs/` for review before any ingestion planning
- No ingest in P104 discovery — separate P105 ingestion phase would follow

**Next phase action (P104)**: Add read-only `3_STAR` SOURCE_CONFIG entry, run endpoint discovery, log candidate draws to `outputs/replay/`, no ingestion.

---

### Option C — Keep HOLD

| Property | Detail |
|---|---|
| Action | Maintain HOLD state — monitoring only |
| Authorization needed | None |
| DB writes | false |
| Ingestion | false |
| Next phase | MONITORING_ONLY |
| Current status | **ALWAYS ELIGIBLE** |

**Monitoring scope**: DB baseline integrity (replay_rows=54462), POWER_LOTTO max_draw stability, 3_STAR max_draw unchanged at 115000024, 4_STAR remains DATA_GAP_BLOCKING.

**Re-evaluation trigger**: User provides a raw 3_STAR draw file, or grants authorization to add fetcher endpoint.

---

## Decision Matrix Summary

| Option | Eligible Now | Blocker | Safety |
|---|---|---|---|
| A — Upload raw file | No | No file provided | HIGHEST |
| B — Add API endpoint | No | No authorization | HIGH |
| C — Keep HOLD | **Yes** | None | MAXIMUM |

**Default recommendation: Option C (HOLD)**  
Reason: No source file and no endpoint authorization available. HOLD is the only currently authorized path.

---

## What NOT to Do

- Do NOT write to `lottery_v2.db`
- Do NOT insert replay rows
- Do NOT ingest draws without explicit Option A file or Option B authorization
- Do NOT call any official API for writes
- Do NOT promote Special3 strategies to production
- Do NOT backtest 4_STAR
- Do NOT modify fetcher SOURCE_CONFIG without Option B authorization
- Do NOT stage DB / backup / runtime files

---

## Governance Verification

| Guard | Status |
|---|---|
| DB writes | false |
| DB ingestion | false |
| Replay row inserts | false |
| Strategy promotion | false |
| Special3 production promotion | false |
| 4_STAR backtest | false |
| replay_rows | 54,462 |
| POWER_LOTTO max_draw | 115,000,041 |
| 3_STAR max_draw | 115,000,024 |
| 4_STAR status | DATA_GAP_BLOCKING |

---

## P104 Gate

| Condition | P104 Path |
|---|---|
| User provides Option A file | P104_UPLOADED_SOURCE_VALIDATION |
| User grants Option B authorization | P104_OFFICIAL_ENDPOINT_DISCOVERY |
| Option C (default) | P104 NOT_YET_ELIGIBLE — monitoring only |

---

## Phase Chain Summary (P96–P103)

| Phase | Result |
|---|---|
| P96 | Governance baseline repair — replay_rows updated 46962→54462 |
| P97 | Special3/Special4 dry-run closure — 5 PROVISIONAL, 1 REJECT, 4_STAR DATA_GAP_BLOCKING |
| P98 | OOS + permutation review — 5 ADVANCE_TO_P99_CANDIDATE, ensemble_v2 PROCEED |
| P99 | Prospective dry-run planning — 6 strategies × 4 prediction sets |
| P100 | Prospective evaluation gate — HOLD_NO_ACTUAL_DRAW |
| P101 | Actual draw availability monitor — HOLD_NO_ACTUAL_DRAW confirmed |
| P102 | Source decision audit — HOLD_NO_LOCAL_SOURCE (10 sources, 16 backups) |
| P103 | **Source acquisition decision — READY, default=HOLD_AWAITING_USER_SOURCE** |

---

## Output Artifacts

| Artifact | Path |
|---|---|
| JSON decision | `outputs/replay/special3_source_acquisition_decision_20260527.json` |
| Markdown report | `docs/replay/special3_source_acquisition_decision_20260527.md` |
| Test suite | `tests/test_p103_special3_source_acquisition_decision.py` |
