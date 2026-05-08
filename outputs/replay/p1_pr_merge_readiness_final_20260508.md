# P1-3 — PR Merge Readiness Final Gate Report

**Date**: 2026-05-08  
**Agent Role**: Senior PR Merge Readiness Gate Agent (reporting to CTO)  
**Branch**: `release/p0-replay-20260508`  
**PR**: #1 — https://github.com/kelvinhuang0327/number-pattern-research/pull/1  
**Marker**: `P1_3_PR_MERGE_READINESS_FINAL_VERIFIED`

---

## 1. Executive Summary

PR #1 for the LotteryNew P0 Replay / Governance release is **structurally ready
for merge** with two items requiring CTO Go-No-Go decision before merge is
authorized. The release branch passes all 89 release-critical tests, contains no
prohibited binary files, and all governance artifacts are in place.

**Merge is NOT authorized to proceed automatically.** Two CTO decisions are
required (see §8 Merge Blockers).

---

## 2. PR State

| Item | Value |
|------|-------|
| PR number | #1 |
| PR state | OPEN |
| Base branch | `main` (`2164b65`) |
| Head branch | `release/p0-replay-20260508` |
| Remote head | `origin/release/p0-replay-20260508` |
| Commits in PR | 3 |
| Merge state | None (no active merge / conflict) |
| Merge conflicts | None |
| PR URL | https://github.com/kelvinhuang0327/number-pattern-research/pull/1 |

---

## 3. Branch / Commit State

| Commit | Message |
|--------|---------|
| `a7fc772` (HEAD) | `chore: harden replay PR review artifacts` |
| `66a329e` | `test: guard replay live-db tests with requires_db marker` |
| `0b33c88` (tag) | `release: package P0 replay governance readiness` |

Tag `p0-replay-release-20260508` → `0b33c88` (unchanged, intact).  
`origin/main` → `2164b65` (unchanged since P0-12 authorized force-push).  
No unexpected staged changes. `data/lottery_v2.db` is ` M` (runtime modified,
not staged). `memory/lessons.md` is ` M` (local append, not staged).

---

## 4. Release Scope Confirmation

### 4.1 — Files in PR (28 files, +8767 / -617 lines)

| Category | Files |
|----------|-------|
| Replay API / backend | `lottery_api/app.py`, `lottery_api/database.py`, `lottery_api/models/replay_strategy_registry.py`, `lottery_api/routes/replay.py` |
| Replay governance UI | `index.html` (see §6 for detail) |
| Release-critical tests | `tests/test_randomness_audit_cadence.py`, `tests/test_strategy_replay_history_cutoff_integrity.py`, `tests/test_replay_browser_smoke.py`, `tests/test_replay_api_contract.py`, `tests/test_replay_freshness_cadence.py` |
| CI DB fixture guard | `pytest.ini`, `tests/conftest.py` |
| Scripts | `scripts/backfill_replay_history_cutoff.py`, `scripts/snapshot_replay_db.py` |
| Governance docs / wiki | `docs/REPLAY_OPERATION_SOP.md`, `wiki/system/randomness_final_verdict.md`, `wiki/system/replay_data_hygiene.md` |
| Outputs / artifacts | `outputs/db_snapshots/SHA256SUMS`, `outputs/randomness_audit/...`, `outputs/replay/p0_*`, `outputs/replay/p1_*`, `outputs/replay/replay_history_cutoff_audit_*` |
| .gitignore | `.gitignore` (WAL journal rules added) |
| Memory | `memory/lessons.md` |

### 4.2 — Prohibited Content Check

| Item | In PR? |
|------|--------|
| `lottery_v2.db` (DB binary) | ❌ NOT in PR ✅ |
| `*.db-shm` (WAL journal) | ❌ NOT in PR ✅ |
| `*.db-wal` (WAL journal) | ❌ NOT in PR ✅ |
| `test_mab_ensemble.py` fixes | ❌ NOT in PR ✅ |
| Strategy mining changes | ❌ NOT in PR ✅ |
| Replay generation changes | ❌ NOT in PR ✅ |
| Force-push evidence | N/A — PR committed via normal push ✅ |

---

## 5. Validation Result

**Command run**:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_randomness_audit_cadence.py \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_browser_smoke.py \
  tests/test_replay_api_contract.py \
  tests/test_replay_freshness_cadence.py \
  -q
```

**Result**: `89 passed, 1 warning in 0.46s` ✅

The 1 warning is a `PendingDeprecationWarning` from `starlette/formparsers.py`
(external library, pre-existing, not caused by P0/P1 changes).

**DB status during run**: `lottery_api/data/lottery_v2.db` present locally
→ all 89 tests ran (none skipped via `requires_db` guard).

---

## 6. index.html Reviewer Decision Summary

### 6.1 — Change Breakdown

| Category | Approx. Lines Added | Classification |
|----------|--------------------|-|
| Replay governance UI | ~1062 | ✅ P0 scope — accepted |
| Non-replay frontend redesign | ~1187 | ⚠️ Reviewer Go-No-Go required |
| Total additions | ~2249 | |
| Deletions | ~581 | Mostly old CSS references + hidden sections |

### 6.2 — Replay-Scope (Accepted)

The following additions are confirmed P0 replay governance scope:

- `<section id="replay-section">` — Replay history table + freshness panel
- `id="rp-freshness-card"`, `id="rp-freshness-table"`, `id="rp-coverage-badge"` — Coverage status UI
- `const BASE = '/api/replay'` — Frontend route binding
- `rpCausalStatus(history_cutoff, target_draw)` — Walk-forward causal safety check (UI layer)
- `rpStatusBadge()`, `rpStatusLabel()` — Status rendering
- URL params: `rp_lt`, `rp_sid`, `rp_status`, `rp_df`, `rp_dt`, `rp_page` — Shareable filter state
- `<button data-section="replay">` — Nav button for replay tab
- Governance disclaimers embedded in HTML:
  - "每筆 replay 只使用 target draw 以前資料（walk-forward / causal 限制）"
  - "replay summary 只是歷史統計，不是 governance verdict"
  - "replay 結果不是 edge claim，不代表提高中獎率"

**Risk**: LOW. All replay UI is read-only (query + display). No replay
generation endpoint exposed. Causal safety enforced at both API and UI layers.

### 6.3 — Non-Replay Redesign (Requires Go-No-Go)

The following pre-existing changes are present on the branch but are NOT part
of P0 replay governance scope:

| Change | Old value | New value |
|--------|-----------|-----------|
| Page `<title>` | `大數據智能分析系統 - Lottery Analysis` | `Lotto Insight Platform` |
| Font family | Noto Sans TC + Orbitron | Fira Code + Fira Sans |
| Stylesheets removed | `styles_stats.css`, `styles_autolearning.css` | — |
| Stylesheet added | — | `professional-design.css?v=18` |
| Icon library | None | Lucide Icons (`unpkg.com/lucide@latest`) |
| `analysis-section` nav | visible | hidden (`ui-hidden`) |
| `prediction-section` nav | visible | hidden |
| `smartbetting-section` nav | visible | hidden |
| `autolearning-section` nav | visible | hidden |
| Sections newly added | — | `next-draw-section`, `tracking-section`, `reviews-section`, `orchestration-section`, `cto-review-section` |
| Inline CSS | Minimal | Large Visibility Guard block + draw-entry / af-card component CSS |

These changes appear to be a frontend redesign from the dirty branch
(`auto/inbox/20260430`) that was incorporated into the release branch
when it was built. They do **not** interfere with replay section
JavaScript behavior — sections share only the `nav-btn` click handler
via `data-section` attribute.

### 6.4 — Reviewer Decision Required

**⚠️ MERGE BLOCKER — CTO GO-NO-GO REQUIRED**

The non-replay redesign (~1187 lines) must receive an explicit CTO decision:

| Option | Action |
|--------|--------|
| **Go (include as-is)** | Merge PR as-is; redesign ships with replay |
| **Go (include with caveat)** | Merge; follow-up commit to restore hidden sections or revert specific stylesheet changes |
| **No-Go (strip before merge)** | Revert `index.html` to `main` baseline, preserve only replay-section additions |

**Current agent decision**: No-Go until CTO explicitly authorizes inclusion.
`index.html` was **not modified** in P1-2 or P1-3 (audit only).

---

## 7. CI DB Fixture Decision Summary

### 7.1 — Current State

| Item | Status |
|------|--------|
| `requires_db` guard (`pytest.ini` + `tests/conftest.py`) | ✅ Implemented (P1-1) |
| Live-DB tests in CI (no DB) | Will **skip** (not fail) |
| Tests at risk of CI skip | 32 of 89 (3 in history_cutoff + 4 in freshness + ~25 in api_contract) |
| DB binary committed | ❌ NO — correct by policy |
| `LOTTERY_TEST_DB_PATH` env override | ✅ Supported — CI can point to fixture |
| In-memory DB fixture | ❌ NOT YET IMPLEMENTED |
| `test_replay_browser_smoke.py` (30 tests) | ✅ No DB dependency |
| `test_randomness_audit_cadence.py` (23 tests) | ✅ No DB dependency |
| `TestCadencePolicyLogic` in freshness (4 tests) | ✅ No DB dependency |

### 7.2 — CI DB Fixture Options (from `p0_ci_db_fixture_decision_20260508.md`)

| Option | Description | Effort | Status |
|--------|-------------|--------|--------|
| A | Commit minimal SQLite fixture | Medium | Not implemented |
| B | In-memory `conftest.py` with synthetic data | Medium | Not implemented |
| C | CI DB download step | Low code, CI config required | Not implemented |
| D (current) | `requires_db` skip guard only | ✅ Implemented | Safe for merge; live-DB tests skip in CI |

### 7.3 — CTO Decision Required

**⚠️ MERGE DECISION POINT**

| Policy | Merge Blocker? |
|--------|---------------|
| CTO accepts: live-DB tests skip in CI (Option D) | **NOT a blocker** — merge safe |
| CTO requires: all 89 tests run in CI before merge | **BLOCKER** — in-memory fixture must be implemented first |

**Current agent position**: Option D (skip guard) is safe for merge from a
CI-stability standpoint. No test will fail; tests will skip with a clear
diagnostic message. However, the policy decision belongs to CTO.

---

## 8. Merge Blockers

| # | Blocker | Severity | Owner |
|---|---------|----------|-------|
| **B1** | `index.html` non-replay redesign (~1187 lines): CTO must decide Go/No-Go before merge | 🔴 HARD BLOCKER | CTO |
| **B2** | CI live-DB fixture policy: CTO must decide whether skip-guard (Option D) is acceptable for merge, or whether in-memory fixture (Option B) is required first | 🟡 SOFT BLOCKER (CTO policy decision) | CTO |

**No other merge blockers identified.**

---

## 9. Reviewer Go-No-Go Items

| Item | Required From | Decision Needed |
|------|--------------|-----------------|
| B1: `index.html` non-replay redesign | CTO | Approve as-is / approve with caveat / strip |
| B2: CI DB fixture policy | CTO | Option D (skip) acceptable OR require Option B first |
| PR merge authorization | CTO | Explicit "merge PR #1" instruction |

---

## 10. What Was NOT Changed in P1-3

- `index.html` — **not modified** (audit only)
- Any replay API endpoint — not modified
- Any replay data / DB schema — not modified
- Any active strategy state — not modified
- `test_mab_ensemble.py` — not touched
- No replay generation executed
- No strategy mining / edge discovery
- No in-memory DB fixture implemented
- No force-push
- No push to `main`
- No PR merge

---

## 11. Final Recommendation

**Status**: `READY FOR CTO MERGE AUTHORIZATION — PENDING TWO DECISIONS`

All technical prerequisites are met:
- ✅ 89/89 release-critical tests pass
- ✅ No prohibited binary files in PR
- ✅ `.gitignore` covers WAL journal files
- ✅ `requires_db` guard prevents CI breakage
- ✅ Governance disclaimers present in replay UI
- ✅ Causal safety (`history_cutoff < target_draw`) enforced
- ✅ All prior governance markers recorded

Pending CTO decisions:
- 🔴 B1: `index.html` Go-No-Go
- 🟡 B2: CI DB fixture policy

Once CTO provides Go on both items, merge can proceed with:
```bash
gh pr merge 1 --merge --subject "release: P0 replay governance readiness"
```
(or equivalent GitHub web UI action)

---

## 12. Commands NOT Executed in P1-3

| Command | Reason |
|---------|--------|
| `gh pr merge` | Hard rule — no auto-merge |
| `git push --force` | Hard rule — no force-push |
| `git push origin main` | Hard rule — no push main |
| Replay generation / strategy mining | Out of scope |
| `index.html` modification | Out of scope — audit only |
| In-memory DB fixture implementation | Out of scope — P2 task |

---

## 13. Post-Merge Tasks

| Priority | Task |
|----------|------|
| P1 | Implement in-memory DB fixture (Option B) if CTO selects that policy |
| P1 | Review external dirty delta from `auto/inbox/20260430` separately |
| P2 | Consider Playwright e2e tests for replay UI |
| P2 | Address `test_mab_ensemble.py` 6 KeyError pre-existing failures (separate scope) |
| P2 | Add `LOTTERY_TEST_DB_PATH` documentation to `docs/REPLAY_OPERATION_SOP.md` |
| P3 | CI pipeline configuration (download DB or use in-memory fixture) |

---

## 14. Reports Reviewed in P1-3

| Report | Status | Key Finding |
|--------|--------|------------|
| `outputs/replay/p0_replay_pr_created_20260508.md` | ✅ Read | PR created OK; CI DB fixture marked OPEN; two remaining risks identified |
| `outputs/replay/p0_replay_pr_opening_checklist_20260508.md` | ✅ Read | `index.html` non-replay changes flagged as P0 review item; `.gitignore` as P1 |
| `outputs/replay/p0_ci_db_fixture_decision_20260508.md` | ✅ Read | Options A–D documented; Option D (skip guard) implemented in P1-1 |
| `outputs/replay/p1_ci_db_fixture_guard_20260508.md` | ✅ Read | `requires_db` guard verified; 32 tests safely skippable; DB not committed |
| `outputs/replay/p1_pr_review_hardening_20260508.md` | ✅ Read | `index.html` 1187 non-replay + 1062 replay lines; `.gitignore` WAL rules confirmed |

---

## Final Marker

```
P1_3_PR_MERGE_READINESS_FINAL_VERIFIED
```
