# P151: Replay UI Multi-Bet Display

**Classification**: `P151_REPLAY_UI_MULTI_BET_DISPLAY_READY`
**Task ID**: P151
**Generated**: 2026-05-30

---

## 1. Executive Summary

P151 adds multi-bet (`bet_index`) display and zero-row strategy visibility to the replay UI. Starting from a clean worktree (confirmed by P151B), this task modifies `index.html` to:
1. Show `bet_index` badge ("Bet N") in replay history rows for multi-bet strategies
2. Show `bet_index` in the drill-down detail panel
3. Add a new **全策略目錄** section calling `/api/replay/all-strategy-catalog` (P150 endpoint)
4. Display `no_data_reason` badges for all zero-row strategies
5. Make `h6_gate_mk20_ew85` (ONLINE_ZERO_REPLAY_ROWS) and 4 REJECTED strategies visible in UI

No DB writes. No replay rows inserted. DB remains at 94924.

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | ✅ PASS |

---

## 3. P151B Clean-Worktree Recap

P151B (commit `4daf36c`) confirmed:
- 5 historical P145B/P146A rerun pollution files restored to HEAD
- Only `backups/` untracked (not staged, not deleted)
- DB = 94924, drift guard PASS
- P151 UI explicitly declared unblocked

---

## 4. P150 Recap and UI Gaps

P150 (commit `136f739`) added:
- `bet_index` column to `/api/replay/history` response
- `no_data_reason` field to source-controlled registry
- `/api/replay/all-strategy-catalog` endpoint (40 strategies, zero-row included)
- 22 DB-only lifecycle stubs registered
- `h6_gate_mk20_ew85` marked `ONLINE_ZERO_REPLAY_ROWS`
- 4 REJECTED strategies marked `REJECTED_NO_REPLAY_DATA`

**P150 UI gap**: `index.html` did not yet render `bet_index` or call `/api/replay/all-strategy-catalog`. P151 closes this gap.

---

## 5. UI Entrypoint Audit

| Item | Finding |
|------|---------|
| UI framework | Vanilla JavaScript SPA |
| UI file | `index.html` (4085+ lines) |
| Replay section | `id="replay-section"` |
| Replay JS | Inline `<script>` (IIFE) |
| Existing endpoints called | `/api/replay/strategies`, `/api/replay/history`, `/api/replay/summary`, `/api/replay/strategy-catalog`, `/api/replay/strategy-lifecycle` |
| TypeScript types | None (vanilla JS) |
| `bet_index` before P151 | Not rendered |
| `no_data_reason` before P151 | Not rendered |
| `/api/replay/all-strategy-catalog` before P151 | Not called |

---

## 6. Replay UI Changes

All changes are in `index.html`.

### CSS additions (after line ~298)
```css
.rp-bet-index-badge  — multi-bet "Bet N" pill badge
.rp-ndr-badge        — no_data_reason badge base
.rp-ndr-zero-online  — ONLINE_ZERO_REPLAY_ROWS (amber warning)
.rp-ndr-rejected     — REJECTED_NO_REPLAY_DATA (red)
.rp-ndr-db-only      — DB_ONLY_MISSING_LIFECYCLE (blue info)
.rp-ndr-artifact     — ARTIFACT_ONLY / NO_REPLAY_DATA (gray)
.rp-ndr-none         — has rows (green)
```

### HTML addition (after `rp-catalog-card`)
New card `rp-all-catalog-card` — **全策略目錄（含零回放列策略）**:
- Summary chips (ONLINE / OBSERVATION / RETIRED / REJECTED / DB-only counts)
- Coverage footnote (row-backed N/total, zero-row count)
- Table: strategy_id / strategy_name / 彩種 / lifecycle / rows / 無資料原因
- Disclaimer: zero-row entries are lifecycle completeness records, not prediction claims

### JS additions
1. **`rpNoDataReasonBadge(reason)`** — renders no_data_reason as colored badge
2. **`rpLoadAllStrategyCatalog()`** — fetches `/api/replay/all-strategy-catalog`, renders table with no_data_reason badges
3. Wired in nav click handler and `DOMContentLoaded` init

---

## 7. Multi-Bet / bet_index Display

### History table (`rpBuildHistoryRows`)
- Strategy ID cell: appends `<span class="rp-bet-index-badge">Bet N</span>` when `bet_index > 1`
- Badge only shown for multi-bet rows (bet_index == 1 unchanged — backwards compatible)
- `data-testid="rp-bet-index-badge"` for test automation

### Detail panel (`rpRenderDetail`)
- Changed from: `一注預測：每策略每期只保留一注` (hardcoded)
- Changed to: `注次（bet_index）：Bet N` with actual value from API
- `data-testid="rp-detail-bet-index"` for test automation
- Shows "multi-bet" badge when bet_index > 1, "(單注)" when bet_index == 1

---

## 8. NO_DATA / no_data_reason Display

| no_data_reason | Badge Style | Example Strategy |
|----------------|-------------|-----------------|
| `ONLINE_ZERO_REPLAY_ROWS` | ⚠️ amber | h6_gate_mk20_ew85 |
| `REJECTED_NO_REPLAY_DATA` | ✕ red | 4 REJECTED strategies |
| `DB_ONLY_MISSING_LIFECYCLE` | ℹ️ blue | 22 DB-only stubs |
| `ARTIFACT_ONLY` | 📋 gray | RETIRED/OFFLINE strategies |
| `NO_REPLAY_DATA` | — gray | other zero-row |
| `null` (has rows) | ✓ green | ONLINE row-backed |

---

## 9. h6_gate_mk20_ew85 Handling

| Field | Value |
|-------|-------|
| Visible in catalog | ✅ Yes (rp-all-catalog-card) |
| Lifecycle | OBSERVATION |
| Replay rows inserted | ❌ false |
| `no_data_reason` | `ONLINE_ZERO_REPLAY_ROWS` |
| UI badge | `⚠️ ONLINE_ZERO_REPLAY_ROWS` (amber, rp-ndr-zero-online) |

`h6_gate_mk20_ew85` is visible in the new all-strategy catalog section with an amber warning badge. No rows were added. The strategy must go through authorized controlled_apply to get actual replay rows.

---

## 10. Rejected No-Data Strategy Handling

4 REJECTED strategies are now visible in the all-strategy catalog with `✕ REJECTED_NO_REPLAY_DATA` red badge. No rows were inserted. These entries serve as lifecycle completeness records only.

---

## 11. Truth Level / Source Display Readiness

| Field | Status |
|-------|--------|
| `truth_level` | ✅ Already rendered (renderTruthLevelBadge in history rows + lifecycle registry) |
| `source` | ⏳ Deferred to P152 — API returns it but UI doesn't surface it |
| `controlled_apply_id` | ⏳ Deferred to P152 — API returns it but UI doesn't surface it |

---

## 12. Tests and Verification

| Suite | Result |
|-------|--------|
| `tests/test_p151_replay_ui_multi_bet_display.py` | **53 passed** |
| `tests/test_p151b_historical_artifact_pollution_reconciliation.py` | 30 passed |
| `tests/test_p150_replay_api_all_strategy_coverage.py` | 72 passed |
| `tests/test_p149_replay_product_coverage_audit.py` | 21 passed |
| Drift guard | PASS |
| DB rows | 94924 (unchanged) |

---

## 13. Explicit Non-Actions

| Action | Executed |
|--------|----------|
| DB write | ❌ false |
| Replay rows inserted | ❌ 0 |
| Replay rows updated | ❌ 0 |
| Replay rows deleted | ❌ 0 |
| `controlled_apply` | ❌ false |
| Champion promotion | ❌ false |
| Registry promotion | ❌ false |
| Live API call | ❌ false |
| Scheduler install | ❌ false |
| 4★ executed | ❌ false |
| P108 executed | ❌ false |
| P117 executed | ❌ false |
| P118 executed | ❌ false |

---

## 14. Dirty File Hygiene Note

- `backups/` untracked — not staged, not deleted
- Only P151 whitelist files staged (index.html, scripts/p151_*, outputs/replay/p151_*, docs/replay/p151_*, tests/test_p151_*, roadmap files)
- No DB, drift guard, history, runtime, pid, pycache, champion/registry files staged

---

## 15. Remaining Risks

1. `source` and `controlled_apply_id` fields from `/api/replay/history` not yet surfaced in UI — deferred to P152
2. All-strategy catalog uses `supported_lottery_types[]` (array); existing strategy-catalog uses `lottery_type` (string) — kept as two separate sections
3. `bet_index == 1` rows appear unchanged (intentional backwards compatibility)
4. `backups/` untracked in worktree
5. Champion evaluation (P147) remains blocked
6. P108/P117/P118/4★ triggers remain blocked

---

## 16. Recommended Next Task

`P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY`

Surface `source` and `controlled_apply_id` fields from `/api/replay/history` in the replay history detail panel.

---

## 17. Final Classification

```
P151_REPLAY_UI_MULTI_BET_DISPLAY_READY
```
