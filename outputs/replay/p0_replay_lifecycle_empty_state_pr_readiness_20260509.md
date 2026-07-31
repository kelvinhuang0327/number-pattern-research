# P0 Replay Lifecycle Empty-State — PR Readiness Report
**Date:** 2026-05-09
**Branch:** `codex/p0-replay-lifecycle-empty-state-implementation`
**Base:** `origin/main` @ `3a2883b` (PR #10)
**Reviewer role:** P0-Empty-State PR Readiness Reviewer → CTO

---

## Verdict: ✅ READY TO MERGE

All 7 readiness checks pass. No blockers.

---

## 1. Diff Scope

```
git diff --name-only origin/main...HEAD
  index.html
  lottery_api/routes/replay.py
  outputs/replay/p0_replay_lifecycle_empty_state_implementation_20260509.md
  tests/test_replay_lifecycle_browser_e2e.py

4 files changed, 287 insertions(+), 1 deletion(-)
```

**Only the 4 explicitly allowed files appear in the diff.** No prohibited files touched.

---

## 2. Readiness Checks

| # | Check | Result |
|---|-------|--------|
| 1 | No fake catalog rows added | ✅ PASS — diff adds no strategy JSON rows |
| 2 | No lifecycle enum changes | ✅ PASS — `replay_strategy_registry.py` diff = 0 lines |
| 3 | No production DB write | ✅ PASS — no `.db` / `.db-wal` / `.db-shm` in diff |
| 4 | Empty-state text matches PR #10 spec | ✅ PASS — see §3 below |
| 5 | Forbidden-language sweep HIGH=0 | ✅ PASS — grep of `+` lines: 0 hits |
| 6 | Browser E2E skips honestly if Playwright unavailable | ✅ PASS — `1 skipped` (module-level `importorskip`) |
| 7 | Diff contains only allowed files | ✅ PASS — no `docs/archive`, `legacy`, `.db`, registry |

---

## 3. Empty-State Text — Spec Correspondence

Source: `outputs/replay/p0_replay_lifecycle_empty_state_spec_20260509.md`

| Lifecycle | Spec §1 text | Implemented (index.html) | Verdict |
|-----------|-------------|--------------------------|---------|
| OFFLINE | 查無可信 OFFLINE 條目 | 查無可信 OFFLINE 條目｜此欄位依目前可信來源為空 | ✅ spec substring + approved §2 suffix |
| RETIRED | 查無可信 RETIRED 條目 | 查無可信 RETIRED 條目｜此欄位依目前可信來源為空 | ✅ spec substring + approved §2 suffix |
| OBSERVATION | 目前僅有 WATCH / PROVISIONAL 候選，尚未形成 canonical OBSERVATION rows | 目前僅有 WATCH / PROVISIONAL 候選，尚未形成 canonical OBSERVATION rows | ✅ exact |
| REJECTED | (§2) 僅有候選證據，尚未升格為 canonical lifecycle row | 僅有候選證據，尚未升格為 canonical lifecycle row | ✅ exact |

Suffix "此欄位依目前可信來源為空" sourced from spec §2 approved copy. No self-invented text.

---

## 4. API Empty-Payload Contract

### GET /api/replay/strategies (any lifecycle)
Added field `"data_scope": "ALL_REPLAY_ROWS"` unconditionally.

### GET /api/replay/history (0-row early-return path)
Added `"disclaimer": _DISCLAIMER` (pre-existing constant, unchanged) and `"data_scope": "ALL_REPLAY_ROWS"` to the early-return dict.

`_DISCLAIMER` text unchanged:
> 本資料為歷史預測回放資料，用於查詢與稽核；不代表提高中獎率，也不是 edge claim。

No other fields in either endpoint were modified.

---

## 5. Validation Evidence

### replay-ci-default-validation
```
57 passed, 32 skipped, 1 warning
```
Matches `origin/main` baseline exactly. No regression.

### replay-browser-e2e-validation
```
1 skipped in 0.03s
```
Module-level `pytest.importorskip("playwright.sync_api")` fires — honest SKIP.
New parametrized tests (`test_empty_state_honest_text_browser_e2e[OFFLINE/RETIRED/OBSERVATION/REJECTED]`) are collected and will run in CI environments with Playwright installed.

---

## 6. Commit Log

```
88d2c9a docs(replay): record empty-state implementation report
1545ea6 test(replay): cover empty-state lifecycle browser e2e
acebb6a feat(replay-ui): honest empty-state for non-online lifecycle tabs
```

3 atomic commits, each scoped to one concern. Clean linear history on top of `3a2883b`.

---

## 7. What Was Not Changed

- `lottery_api/models/replay_strategy_registry.py` — lifecycle enum unchanged
- Any strategy/catalog JSON — no fake rows added
- `_DISCLAIMER` constant — pre-existing text preserved
- Branch protection — not modified
- Any `.db` file — no production DB writes
- `docs/archive/**` / `legacy/` — untouched
- Active strategy state — untouched
- No REJECTED archive rows promoted (P1 scope)
- No new edge claims

---

## 8. Follow-Up (out of scope for this PR)

| Phase | Item |
|-------|------|
| P1 | REJECTED canonical promotion: formal mapping of `rejected/` archive rows |
| P3 | Drift guard: CI alert when lifecycle bucket counts change unexpectedly |
| P4 | Display-contract hardening: integration test asserting `data_scope` on all lifecycle endpoints |

---

## Final Marker

**P0_REPLAY_LIFECYCLE_EMPTY_STATE_PR_READY**
