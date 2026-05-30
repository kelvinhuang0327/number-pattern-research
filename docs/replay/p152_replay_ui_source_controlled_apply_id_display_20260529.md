# P152: Replay UI Source / Controlled Apply ID Display

**Classification**: `P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY_READY`
**Task ID**: P152
**Generated**: 2026-05-30

---

## 1. Executive Summary

P152 surfaces `source`, `controlled_apply_id`, `provenance_hash`, and `truth_level` from the replay history API into the UI. The API already returned all these fields since P150 — no API changes were needed. Changes are purely in `index.html`:

1. Detail panel: source, controlled_apply_id, provenance_hash, truth_level explicitly shown
2. History table row: source shown as subtitle under strategy_id
3. `renderTruthLevelBadge` extended with explicit badges for `LEGACY_UNVERIFIED`, `TIERB_DRYRUN_VALIDATED`, and all production backfill truth levels

No DB writes. DB remains at 94924 rows.

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | ✅ PASS |

---

## 3. P151 Recap and Remaining Gap

P151 (commit `c521254`) added bet_index display and all-strategy-catalog. It deferred:
- `source` — API returned but not displayed
- `controlled_apply_id` — API returned but not displayed
- `provenance_hash` — API returned but not displayed

P152 closes all three.

---

## 4. API Metadata Field Audit

| Field | DB Schema | API Returns (before P152) | API Change Needed |
|-------|-----------|--------------------------|-------------------|
| `source` | ✅ col 21 | ✅ Yes (since P150) | ❌ None |
| `controlled_apply_id` | ✅ col 20 | ✅ Yes (since P150) | ❌ None |
| `provenance_hash` | ✅ col 22 | ✅ Yes (since P150) | ❌ None |
| `truth_level` | ✅ col 19 | ✅ Yes (since P150) | ❌ None |
| `provenance_source` | ✅ col 23 | ✅ Yes | deferred to P153+ |

**Conclusion**: P152 is a pure UI display task. No backend changes.

---

## 5. API Changes

**None.** All fields already in `/api/replay/history` response (lines 525-528 of `lottery_api/routes/replay.py`).

---

## 6. UI Changes

All changes in `index.html`.

### Detail Panel (`rpRenderDetail`) — new fields after 建立時間
```
Truth Level：    [badge via renderTruthLevelBadge]     data-testid="rp-detail-truth-level"
來源（source）：  code block (or "— (legacy/unknown)")   data-testid="rp-detail-source"
Controlled Apply ID： code block (or "N/A（legacy/uncontrolled）")  data-testid="rp-detail-controlled-apply-id"
Provenance Hash：  8-char prefix + …  (or "—")          data-testid="rp-detail-provenance-hash"
```

### History Table Row (`rpBuildHistoryRows`) — source subtitle
- Added `data-testid="rp-row-source"` subtitle under strategy_id
- Shows first 28 chars of `source` (truncated with `…` if longer)
- Full value in `title` attribute for hover tooltip
- Empty if `source` is null

### `renderTruthLevelBadge` extensions
Added explicit badges for truth_level values missing from the map:
| truth_level | Badge |
|-------------|-------|
| `LEGACY_UNVERIFIED` | 🟠 LEGACY UNVERIFIED (orange) |
| `TIERB_DRYRUN_VALIDATED` | 🟢 TIER-B (green) |
| `POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED` | POWER BACKFILL (P20) |
| `POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED` | POWER W4 BACKFILL |
| `DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED` | 539 RETIRED BACKFILL |
| `DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED` | 539 W2 BACKFILL |
| `BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED` | BIG W3 BACKFILL |
| `POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` | POWER SINGLE BACKFILL |
| `DAILY539_BACKFILL_VERIFIED` | 539 BACKFILL |
| `POWER_LOTTO_WAVE5_CONTROLLED_APPLY_VERIFIED` | POWER W5 |
| `POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED` | POWER W6 |
| `POWERLOTTO_DRAW_EXT_VERIFIED` | POWER DRAW EXT |

---

## 7. Source Display Support

| Item | Status |
|------|--------|
| `source` visible in detail panel | ✅ |
| `source` subtitle in history row | ✅ |
| Null source shows "— (legacy/unknown)" | ✅ |
| LEGACY_UNVERIFIED rows: source = P138B_LEGACY_REMARK visible | ✅ |
| Test coverage | ✅ |

---

## 8. controlled_apply_id Display Support

| Item | Status |
|------|--------|
| `controlled_apply_id` visible in detail panel | ✅ |
| Null `controlled_apply_id` → "N/A（legacy/uncontrolled）" | ✅ |
| TIERB rows: P94_TIERB_CONTROLLED_APPLY_20260526 visible | ✅ |
| Test coverage | ✅ |

---

## 9. Provenance Hash Display Readiness

- `provenance_hash` shown as 8-char prefix + `…` in detail panel
- `data-testid="rp-detail-provenance-hash"` for test automation
- Null → `—`
- Full hash available on debug inspection via API response

---

## 10. LEGACY_UNVERIFIED Display Support

| Item | Status |
|------|--------|
| `truth_level = LEGACY_UNVERIFIED` badge (orange) | ✅ Explicit badge added to renderTruthLevelBadge |
| `source = P138B_LEGACY_REMARK` visible in detail + row subtitle | ✅ |
| `controlled_apply_id = null` → "N/A（legacy/uncontrolled）" | ✅ |
| `data-testid="rp-truth-legacy-unverified"` | ✅ |
| Test coverage | ✅ |

---

## 11. TIERB / Controlled Apply Metadata Display

| Item | Status |
|------|--------|
| `truth_level = TIERB_DRYRUN_VALIDATED` → explicit green TIER-B badge | ✅ |
| `source = P94_TIERB_CONTROLLED_APPLY` visible in detail + row | ✅ |
| `controlled_apply_id = P94_TIERB_CONTROLLED_APPLY_20260526` visible | ✅ |
| `data-testid="rp-truth-tierb"` | ✅ |
| Test coverage | ✅ |

---

## 12. Tests and Verification

| Suite | Result |
|-------|--------|
| `tests/test_p152_replay_ui_source_controlled_apply_id_display.py` | **57 passed** |
| `tests/test_p151_replay_ui_multi_bet_display.py` | 53 passed |
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
| API schema change | ❌ false |
| Champion promotion | ❌ false |
| Registry promotion | ❌ false |
| Live API call | ❌ false |
| Scheduler install | ❌ false |
| 4★ / P108 / P117 / P118 | ❌ false |

---

## 14. Dirty File Hygiene Note

- `backups/` untracked — not staged, not deleted
- Only P152 whitelist files staged
- No DB, drift guard, history, runtime, pid, pycache files staged
- All P151 UI additions preserved (bet_index, all-catalog, no_data_reason)

---

## 15. Remaining Risks

1. `provenance_source` (DB col 23) not yet displayed — low priority
2. `backups/` untracked in worktree
3. Champion evaluation (P147) remains BLOCKED
4. P108/P117/P118/4★ triggers remain BLOCKED

---

## 16. Recommended Next Task

`P153_REPLAY_UI_LEGACY_UNVERIFIED_TRUTH_BADGE` or general replay UI polish as needed.

---

## 17. Final Classification

```
P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY_READY
```
