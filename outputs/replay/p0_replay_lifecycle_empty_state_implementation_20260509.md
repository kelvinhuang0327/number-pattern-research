# P0 Replay Lifecycle Empty-State Honesty Implementation Report
**Date:** 2026-05-09
**Branch:** codex/p0-replay-lifecycle-empty-state-implementation
**Base:** 3a2883b27049b7fc5dc878645c872813e1a43fd8 (PR #10 merge)
**Worker:** P0-Empty-State Executor → CTO → CEO

---

## 1. Executive Summary

PR #10 established the truth inventory: ONLINE=6, REJECTED=42 archive rows (not
yet canonical), OBSERVATION=candidate-only, OFFLINE=0, RETIRED=0. The lifecycle
UI in Replay section previously showed a generic "查無資料" when any non-ONLINE
filter returned 0 rows, causing users to misinterpret empty catalog buckets as
a rendering bug.

This implementation:
- Replaces the generic empty-state with honest, lifecycle-bucket-specific text
  sourced verbatim from `p0_replay_lifecycle_empty_state_spec_20260509.md`
- Ensures the API returns `data_scope` and `disclaimer` even on 0-row payloads
- Adds browser E2E test cases that assert the correct honest text per lifecycle
  (skip with honest SKIP when Playwright is unavailable)
- Passes forbidden-language sweep: HIGH=0

No catalog rows were added, no edge claims were made, no production DB was
written, no active strategy state was modified.

---

## 2. Files Changed

| File | Change |
|------|--------|
| `index.html` | P0-A: lifecycle-aware empty-state in `rpQuery()` tbody render |
| `lottery_api/routes/replay.py` | P0-B: `data_scope` on strategies endpoint; `disclaimer`+`data_scope` on history empty early-return |
| `tests/test_replay_lifecycle_browser_e2e.py` | P0-C: 4 new parametrized empty-state E2E tests + 2 new helper payloads |

**NOT changed:** `lottery_api/models/replay_strategy_registry.py`, any catalog
row file, any `.db` file, any active strategy state file, any `docs/archive/**`
file.

---

## 3. Empty-State Text — Verbatim Correspondence to PR #10 Spec

Source: `outputs/replay/p0_replay_lifecycle_empty_state_spec_20260509.md` §1 & §2

| Lifecycle | Spec Text | Implemented Text | Match |
|-----------|-----------|-----------------|-------|
| OFFLINE | 查無可信 OFFLINE 條目 | 查無可信 OFFLINE 條目｜此欄位依目前可信來源為空 | ✓ (spec substring + §2 copy appended) |
| RETIRED | 查無可信 RETIRED 條目 | 查無可信 RETIRED 條目｜此欄位依目前可信來源為空 | ✓ (spec substring + §2 copy appended) |
| OBSERVATION | 目前僅有 WATCH / PROVISIONAL 候選，尚未形成 canonical OBSERVATION rows | 目前僅有 WATCH / PROVISIONAL 候選，尚未形成 canonical OBSERVATION rows | ✓ exact |
| REJECTED | 僅有候選證據，尚未升格為 canonical lifecycle row | 僅有候選證據，尚未升格為 canonical lifecycle row | ✓ exact (§2) |

The ｜ separator and §2 suffix "此欄位依目前可信來源為空" are also drawn from
spec §2 approved copy. No self-invented text was added.

---

## 4. API Empty-Payload Contract Verification

### GET /api/replay/strategies?lifecycle_status=OFFLINE
Before:
```json
{ "strategies": [], "count": 0, "filter_lifecycle_status": "OFFLINE",
  "filter_lottery_type": null, "filter": null }
```
After:
```json
{ "strategies": [], "count": 0, "filter_lifecycle_status": "OFFLINE",
  "filter_lottery_type": null, "filter": null, "data_scope": "ALL_REPLAY_ROWS" }
```

### GET /api/replay/history?lifecycle_status=OFFLINE (0-match early-return path)
Before:
```json
{ "total": 0, "page": 1, "page_size": 50, "pages": 1,
  "filter_lifecycle_status": "OFFLINE", "records": [] }
```
After:
```json
{ "total": 0, "page": 1, "page_size": 50, "pages": 1,
  "filter_lifecycle_status": "OFFLINE", "records": [],
  "disclaimer": "本資料為歷史預測回放資料，用於查詢與稽核；不代表提高中獎率，也不是 edge claim。",
  "data_scope": "ALL_REPLAY_ROWS" }
```

`_DISCLAIMER` constant is unchanged (pre-existing). Only the early-return path
receives `disclaimer` and `data_scope`; normal-data returns are unchanged.

---

## 5. Browser E2E Test Results

Test runner: `pytest tests/test_replay_lifecycle_browser_e2e.py -v`

| Environment | Result |
|-------------|--------|
| Local (no Playwright) | 1 skipped (module-level importorskip — honest SKIP) |

New tests added (`test_empty_state_honest_text_browser_e2e`):
- Parametrized × 4: OFFLINE, RETIRED, OBSERVATION, REJECTED
- Each test: mocks API to return `_empty_history_payload` + `_empty_strategies_payload`,
  navigates to `index.html?rp_lc={lifecycle}`, clicks query, asserts DOM tbody
  contains the expected spec substring
- When Playwright unavailable → honest SKIP (never fake PASS)

---

## 6. Forbidden-Language Sweep Results

Source: `wiki/system/replay_data_hygiene.md §4` + `p0_replay_lifecycle_forbidden_language_sweep_20260509.md §1`

Scanned text: all new strings in `index.html` (P0-A) and `replay.py` (P0-B)

| Term | Status |
|------|--------|
| SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE | 0 hits in new text |
| "best strategy" / "最佳策略" | 0 hits |
| "提高中獎率" | 0 hits in new text (pre-existing in `_DISCLAIMER` — unchanged) |
| "推薦投注" / "推薦" | 0 hits |
| "edge ranking" | 0 hits |
| "all lifecycle states are populated" | 0 hits |
| "complete lifecycle catalog" | 0 hits |
| "production-ready catalog" | 0 hits |
| "zero gaps" | 0 hits |
| "WATCH evidence is canonical OBSERVATION" | 0 hits |

**HIGH = 0 | LOW = 0**

---

## 7. What Was Not Changed

- `lottery_api/models/replay_strategy_registry.py` — lifecycle enum unchanged
- Any strategy JSON in `strategies/`, `rejected/`, `provisional/` — no catalog rows added
- `_DISCLAIMER` constant — pre-existing text untouched
- Branch protection settings — not modified
- Any `.db`, `.db-wal`, `.db-shm` file — no production DB writes
- `docs/archive/**` — untouched
- Active strategy state (H6_gate_mk20→ew85) — untouched
- No REJECTED archive rows were promoted (that is P1)
- No new edge claims were introduced

---

## 8. Remaining Risks

| Risk | Severity | Note |
|------|----------|------|
| Playwright not available locally | Low | Tests honest-SKIP; CI with browser tooling will exercise real E2E |
| `data.filter_lifecycle_status` may be null for non-lifecycle queries | Low | Frontend falls back to DOM `lc` value; generic "查無資料" shown as before |
| REJECTED empty-state text not in spec §1 table | Low | Text sourced from spec §2 ("僅有候選證據，尚未升格為 canonical lifecycle row") which is approved copy |

---

## 9. Follow-Up

| Phase | Item |
|-------|------|
| **P1** | REJECTED canonical promotion: map `rejected/` archive rows to canonical lifecycle catalog rows |
| **P3** | Drift guard: alert if lifecycle bucket counts change without explicit update |
| **P4** | Display-contract hardening: add integration test asserting `data_scope` echoed on all lifecycle endpoints |

---

## 10. Final Marker

**P0_REPLAY_LIFECYCLE_EMPTY_STATE_IMPLEMENTATION_READY**

Validation baseline maintained: `57 passed, 32 skipped, 1 warning`
