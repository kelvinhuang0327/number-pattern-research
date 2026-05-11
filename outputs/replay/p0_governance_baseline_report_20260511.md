# P0 Governance Baseline Cleanup Report — 2026-05-11

**Session:** P0 Governance Baseline Cleanup + UI Verification  
**Agent Role:** Governance auditor, reporting to CTO  
**Scope:** Read-only audit + PR queue triage + UI verification + taxonomy clarification  
**Constraints:** No replay backfill, no production DB writes, no commit of `data/lottery_v2.db`

---

## 1. Local Dirty State — Root Cause Analysis

### 1a. `data/lottery_v2.db` (fixture DB contamination)

| Attribute | Value |
|-----------|-------|
| Committed size | 28,672 bytes (7 pages) |
| Working tree size | 217,088 bytes (53 pages) |
| Tables in committed version | `draws` only |
| Tables in working tree | All 13 replay tables added, **0 rows** in all |

**Root cause:** `lottery_api/database.py::DatabaseManager.__init__` defaults to `db_path="data/lottery_v2.db"` (relative path). When any code invoking `DatabaseManager()` with no arguments runs from the **project root** (CWD = `LotteryNew-clean/`), SQLite creates `project_root/data/lottery_v2.db` rather than `lottery_api/data/lottery_v2.db`.

Specifically: `lottery_api/routes/replay.py` line 61 — `_get_db()` returns `DatabaseManager()` with no path argument. When this module is imported during a test run from the project root (e.g., `pytest tests/` from project root), `DatabaseManager.__init__` calls `_init_database()` which executes `CREATE TABLE IF NOT EXISTS` for all 13 tables against the fixture. No data rows were written.

**Evidence:** `lottery_api/routes/replay.py:66-67` correctly uses `Path(_api_root) / "data" / "lottery_v2.db"` for `_open_conn()`. The runtime DB at `lottery_api/data/lottery_v2.db` (14.9 MB, 460 rows) was never touched.

**Action:** Do NOT commit `data/lottery_v2.db`. Revert this file before finalising the governance PR.

**Recommended fix (deferred, not in scope):** Harden `DatabaseManager.__init__` to resolve the default path relative to `__file__` rather than CWD, or add a `.gitattributes` entry marking `data/lottery_v2.db` as a read-only fixture.

---

### 1b. `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json` (timestamp drift)

**Change:** Only `generated_at` field changed: `2026-05-10T09:32:43` → `2026-05-11T04:40:34`.  
**Root cause:** The dry-run manifest script regenerated its `generated_at` timestamp when re-run on 2026-05-11. Content is otherwise identical; `db_sha256_unchanged: true` confirmed.  
**Action:** Do NOT commit this file. Revert before finalising the governance PR.

---

### 1c. `outputs/replay/p17_strategy_history_replay_product_roadmap_20260511.md` (untracked)

**Content:** CTO-level product roadmap document identifying the gap between lifecycle dashboard closure (P16) and the full Strategy Historical Replay product (non-ONLINE strategies have 0 replay rows). Documents verified state, product implication, and proposed next engineering direction.  
**Action:** Commit this file as part of the governance PR — it is a valid docs artifact with no code or DB side-effects.

---

## 2. PR Queue Triage

### PR #46 — `docs(replay): record P16 lifecycle dashboard closure summary`
- **Branch:** `docs/p16-lifecycle-dashboard-closure-summary-20260511`
- **Merge state:** CLEAN
- **CI:** `replay-default-validation` ✅ PASS · `replay-browser-e2e-validation` ✅ PASS · `replay-dedicated-db-validation` SKIPPED (expected — workflow_dispatch only)
- **Diff scope:** Docs-only (`outputs/replay/p16_lifecycle_dashboard_closure_summary_20260511.md`)
- **Decision:** **MERGE** — all gates pass, clean state, docs-only, no risk.

### PR #35 — `docs(replay): triage pr queue and inventory all lifecycle strategies`
- **Branch:** `feature/p1-strategy-lifecycle-inventory-20260511`
- **Merge state:** BEHIND
- **Diff scope:** 4 docs files — `p0_dirty_scope_resolution_20260511.md`, `p0_pr_queue_triage_20260511.md`, `p1_strategy_lifecycle_inventory_20260511.json`, `p1_strategy_lifecycle_inventory_20260511.md`
- **Decision:** **CLOSE** — content is superseded by this P0 governance report. The inventory and triage findings are captured here with greater completeness. Rebasing BEHIND branches for docs artifacts creates noise; closing is cleaner.

### PR #34 — `docs(replay): record 24h no-write skeleton implementation review readiness`
- **Branch:** `docs/p2-24h-no-write-skeleton-implementation-review-readiness-20260510`
- **Merge state:** BEHIND
- **Diff scope:** 1 docs file — `p2_24h_no_write_skeleton_implementation_review_readiness_20260510.md`
- **Decision:** **CLOSE** — the skeleton implementation it reviewed is now shipped and has been through PRs #36–#46. The "readiness" context is historical; merging a stale BEHIND review document adds no governance value.

### PR #2 — `docs: record replay branch protection execution`
- **Branch:** `codex/p1-6g-branch-protection-execution`
- **Merge state:** BEHIND
- **Diff scope:** 3 docs files — `p1_6g_branch_protection_execution_20260508.md`, `p1_6g_branch_protection_settings_20260508.json`, `p1_6g_dedicated_lane_observation_log_template_20260508.md`
- **Decision:** **CLOSE** — branch protection execution records from 2026-05-08. Protection has been active throughout all subsequent PRs. The docs are verifiable from git history without needing to merge a BEHIND branch.

---

## 3. API / Lifecycle Dashboard Verification

**Server:** `lottery_api/` started via uvicorn, Python 3.9, PYTHONPATH includes project root and `lottery_api/`.

### 3a. `/api/replay/strategy-lifecycle` ✅

Returns full lifecycle registry as an in-memory snapshot (no DB connection). Client-side filtering in `index.html` applies `lifecycle_status`, `supported_lottery_types`, and `strategy_id` search filters correctly.

```json
{
  "total": 16,
  "lifecycle_counts": {
    "ONLINE": 6,
    "REJECTED": 4,
    "OBSERVATION": 1,
    "RETIRED": 5
  }
}
```

Note: the endpoint does NOT support server-side `?lifecycle_status=` filtering (by design — it is always a full registry snapshot). Server-side filtering lives on `/api/replay/strategies`. The UI uses client-side filtering, which works correctly.

### 3b. `/api/replay/history?lifecycle_status=REJECTED` ✅ honest empty

```
total: 0, records: 0, filter_lifecycle_status: REJECTED
```

Confirmed: non-ONLINE strategies have 0 replay rows. The filter pipeline correctly resolves REJECTED strategy IDs, queries the DB, and returns empty results without error. This is the expected honest-empty state — **no backfill was performed**.

### 3c. `/api/replay/freshness` ✅

```json
{
  "coverage_mode": "LIMITED",
  "total_rows": 460,
  "total_predicted": 420,
  "total_replay_error": 40,
  "legacy_error_count": 40,
  "latest_run_id": 7,
  "latest_run_status": "DONE"
}
```

460 rows across 6 ONLINE strategies. LIMITED coverage reflects that only the most recent run window is in the DB (not all historical draws).

### 3d. UI Lifecycle Dashboard — functional status

| Feature | Status |
|---------|--------|
| Summary badges (ONLINE/REJECTED/RETIRED/OBS counts) | ✅ rendered correctly |
| Table renders all 16 strategies | ✅ |
| Client-side filter by lifecycle_status | ✅ filters correctly |
| Client-side filter by lottery type | ✅ |
| Client-side strategy_id search | ✅ |
| Sort by strategy_id / lifecycle_status / lottery_type | ✅ |
| "顯示 N / 16 筆" row count | ✅ updates on filter change |
| Non-ONLINE history tab: honest empty | ✅ (0 rows returned, no error) |

---

## 4. OFFLINE Lifecycle Taxonomy Clarification

### Current state
OFFLINE strategy count: **0**  
OFFLINE is defined in the registry SSOT (`replay_strategy_registry.py:23`):

> OFFLINE — previously deployed, now suspended; old rows preserved in DB

### OFFLINE vs RETIRED — taxonomy decision matrix

| Criterion | OFFLINE | RETIRED |
|-----------|---------|---------|
| Was it ever deployed (had ONLINE replay rows)? | Required | Required |
| Is suspension temporary / reversible? | Yes | No |
| Can it return to ONLINE? | Yes (with re-validation) | No (archived) |
| Old replay rows preserved? | Yes | Yes |
| Adapter code remains? | Yes (disabled) | Stub only |
| Registry presence | ✅ with metadata | ✅ with metadata |

### When to use OFFLINE (not RETIRED)

Use OFFLINE when:
1. A strategy is **suspended due to external conditions** (e.g., PSI drift, market regime change) but may re-enter ONLINE after re-validation
2. A strategy is **paused for investigation** (e.g., abnormal edge drop in 100-period window)
3. A strategy is **under governance hold** pending a scheduled re-evaluation (e.g., "re-evaluate at period 6010")

Use RETIRED when:
1. The strategy's underlying hypothesis has been permanently refuted (e.g., signal space exhausted, L82/L90/L91 conclusions)
2. The strategy has been superseded by a strictly better version and will never return
3. Formal end-of-lifecycle after full evaluation cycle

### Why OFFLINE = 0 is correct today

All 5 RETIRED strategies (`acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`) meet the RETIRED criterion: they were superseded by validated better versions, and their underlying signal hypotheses were either exhausted or shown inferior. None are candidates for re-activation.

No strategy is currently in a temporary suspension state, so OFFLINE = 0 is accurate.

### Product gap implication for OFFLINE

If a currently-ONLINE strategy needs to be suspended:
- OFFLINE rows would still have replay history from its ONLINE period
- The UI would correctly show those rows when filtering `?lifecycle_status=OFFLINE` (via history endpoint)
- No UI changes are required — the lifecycle filter already supports OFFLINE

---

## 5. Runtime DB Row Coverage — Verified State

| strategy_id | lifecycle_status | total_rows | PREDICTED | REPLAY_ERROR |
|-------------|-----------------|------------|-----------|--------------|
| daily539_f4cold | ONLINE | 90 | 70 | 20 |
| daily539_markov_cold | ONLINE | 90 | 70 | 20 |
| biglotto_deviation_2bet | ONLINE | 70 | 70 | 0 |
| biglotto_triple_strike | ONLINE | 70 | 70 | 0 |
| power_orthogonal_5bet | ONLINE | 70 | 70 | 0 |
| power_precision_3bet | ONLINE | 70 | 70 | 0 |
| **Total** | | **460** | **420** | **40** |

Non-ONLINE strategies (4 REJECTED + 5 RETIRED + 1 OBSERVATION): **0 rows** — honest empty, by design. No backfill performed.

---

## 6. Governance Decisions

| Item | Decision | Rationale |
|------|----------|-----------|
| Commit `data/lottery_v2.db` | ❌ REVERT | Fixture DB contaminated by schema migration, 0 data rows; would bloat repo with no value |
| Commit manifest timestamp drift | ❌ REVERT | Runtime-generated timestamp; content unchanged; must not commit ephemeral timestamps |
| Commit `p17_strategy_history_replay_product_roadmap_20260511.md` | ✅ COMMIT | Valid governance docs artifact |
| Merge PR #46 | ✅ MERGE | CLEAN, CI pass, docs-only |
| Close PR #35 | ✅ CLOSE | Superseded by this report |
| Close PR #34 | ✅ CLOSE | Skeleton shipped; stale readiness doc |
| Close PR #2 | ✅ CLOSE | Branch protection active since 2026-05-08; historical record in git |
| OFFLINE count = 0 | ✅ CORRECT | No strategy currently meets OFFLINE criteria |
| Backfill non-ONLINE replay rows | ❌ OUT OF SCOPE | Not in P0 mandate; tracked in P17 roadmap |

---

## 7. Open Items for CTO Review

1. **DB path hardening (deferred):** `DatabaseManager.__init__` should resolve default path relative to `__file__`. Risk: low-frequency contamination when tests run from project root. Fix: 1-line change + `.gitignore` guard.

2. **P17 product gap:** 10 non-ONLINE strategies have 0 replay rows. UI correctly shows honest empty. CTO decision needed on whether to fund no-write catalog backfill (P17 roadmap available at `outputs/replay/p17_strategy_history_replay_product_roadmap_20260511.md`).

3. **OFFLINE lifecycle trigger:** No current strategy warrants OFFLINE. Monitor: if any ONLINE strategy's 100-period edge turns negative, OFFLINE suspension + re-validation cycle applies.

4. **`acb_1bet` WATCH note (from MEMORY.md):** Listed as WATCH. Now RETIRED in registry. If the WATCH re-evaluation condition (200 periods) has not been completed, this should be noted in the RETIRED stub metadata.

---

*Report generated: 2026-05-11*  
*Author: P0 Governance Agent*  
*No DB writes. No production data modified. All data sourced from registry and read-only DB queries.*
