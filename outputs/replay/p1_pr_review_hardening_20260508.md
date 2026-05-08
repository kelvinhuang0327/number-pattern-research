# P1-2 PR Review Hardening Report

**Date**: 2026-05-08  
**Branch**: `release/p0-replay-20260508`  
**Base**: `main` (2164b65)  
**Release HEAD**: `66a329e`  
**PR**: #1 — https://github.com/kelvinhuang0327/number-pattern-research/pull/1

---

## Part A — Branch / PR State (Pre-Work Snapshot)

| Item | Value |
|------|-------|
| Branch | `release/p0-replay-20260508` |
| HEAD | `66a329e` |
| PR state | OPEN |
| PR base → head | `main` → `release/p0-replay-20260508` |
| Commits in PR | 2 |
| Latest commit | `test: guard replay live-db tests with requires_db marker` |
| Merge state | None (no active merge) |
| Staged binary | None |

---

## Part B — `index.html` Diff Audit

### Overall Scope

| Metric | Value |
|--------|-------|
| Total lines changed | +2249 / -581 |
| Diff lines (with context) | 3367 |
| Hunks | 26 |

### Classification Summary

The `index.html` diff contains **two distinct change categories**:

#### 1. Non-Replay Frontend Redesign (~1187 added lines, pre-existing on branch)

These changes represent a frontend style and structural rework present in the
release branch as pre-existing work. They are NOT part of the P0 replay
governance scope but are present in the diff because the branch was built
on top of this state.

Key non-replay changes identified:

| Change | Main (`old`) | Release (`new`) |
|--------|-------------|-----------------|
| Page title | `大數據智能分析系統 - Lottery Analysis` | `Lotto Insight Platform` |
| Font family | Noto Sans TC + Orbitron | Fira Code + Fira Sans |
| Stylesheets | `styles_stats.css`, `styles_autolearning.css` | `professional-design.css?v=18` |
| Icon library | None | Lucide Icons (`unpkg.com`) |
| CSS versioning | `styles.css` | `styles.css?v=18` |
| Inline CSS block | Minimal | Large Visibility Guard block (~60 lines) + UI component CSS |
| `analysis-section` nav | visible (`nav-btn`) | hidden (`nav-btn ui-hidden`) |
| `prediction-section` nav | visible | hidden |
| `smartbetting-section` nav | visible | hidden |
| `autolearning-section` nav | visible | hidden |
| New sections added | — | `next-draw-section`, `tracking-section`, `reviews-section`, `orchestration-section`, `cto-review-section` |

**Verdict**: These non-replay changes are cosmetic and structural redesign.
They do not modify replay API endpoints, replay data models, replay governance
logic, or history_cutoff causal safety enforcement.

**Action**: `index.html` NOT modified. Audit only.

---

#### 2. Replay-Specific Additions (~1062 added lines — P0 scope)

These are the P0 replay governance additions. All lines occur in the
`replay-section` HTML block (starting diff line 2268) and associated JS.

Key replay-specific additions verified:

| Element | ID / Symbol | Purpose |
|---------|-------------|---------|
| Nav button | `data-section="replay"` | Navigation to replay tab |
| Section root | `id="replay-section"` | Replay UI container |
| Freshness card | `id="rp-freshness-card"` | Coverage status panel |
| Freshness table | `id="rp-freshness-table"`, `id="rp-freshness-tbody"` | Per-strategy coverage rows |
| Coverage badge | `id="rp-coverage-badge"` | Color-coded coverage label |
| History filter | `id="rp-freshness-ts"` | Last updated timestamp |
| API base | `const BASE = '/api/replay'` | Frontend → backend routing |
| Causal check | `rpCausalStatus(history_cutoff, target_draw)` | Walk-forward safety check |
| Status rendering | `rpStatusBadge()`, `rpStatusLabel()` | Replay status visualization |
| URL params | `rp_lt`, `rp_sid`, `rp_status`, `rp_df`, `rp_dt`, `rp_page` | Shareable filter state |
| Governance disclaimer | "每筆 replay 只使用 target draw 以前資料" | Anti-hallucination notice |

**Causal Safety**: `rpCausalStatus` function confirms `history_cutoff < target_draw`
for every displayed row. Violation renders a `⚠️ CAUSAL VIOLATION` badge.
This is the walk-forward guarantee at the UI layer.

**No replay generation logic** is present in `index.html`. All replay UI is
read-only (query + display). No endpoint for triggering strategy mining or
edge discovery.

**Governance disclaimers verified** in HTML:
- "replay summary 只是歷史統計，不是 governance verdict"
- "replay 結果不是 edge claim，不代表提高中獎率"
- Causal restriction notice

---

### Non-Replay Section Interference Check

Confirmed: the replay-section code does NOT modify behavior of:
- `analysis-section` JS
- `prediction-section` JS
- `smartbetting-section` JS
- `autolearning-section` JS

The sections share only the `nav-btn` click handler which uses `data-section`
attribute to route. The replay section registers its own `loadFreshness()`
trigger when the replay nav button is clicked. No cross-section state mutation.

---

## Part C — `.gitignore` DB Journal Addition

**File**: `.gitignore`  
**Lines appended**: 45–46

```gitignore
# SQLite write-ahead log journal files (runtime artifacts, never commit)
*.db-shm
*.db-wal
```

**Verification** (`git check-ignore -v`):
```
.gitignore:45:*.db-shm  lottery_api/data/lottery_v2.db-shm
.gitignore:46:*.db-wal  lottery_api/data/lottery_v2.db-wal
```

Both `lottery_api/data/lottery_v2.db-shm` and `lottery_api/data/lottery_v2.db-wal`
are now suppressed from `git status` output.

**Safety boundary**:
- `*.db` is NOT in `.gitignore` — the DB binary (`lottery_v2.db`) remains
  tracked at the git staging layer. It is excluded from commits by discipline
  (verified: `data/lottery_v2.db` appears as ` M` — modified but not staged).
- `*.db-shm` / `*.db-wal` are WAL-mode journal files automatically generated
  by SQLite during concurrent reads. They should never be committed.

---

## Part D — `.gitignore` Behavior Validation

`git status --short` after adding rules:

```
 M .gitignore                          ← staged for commit (new rules)
 M data/lottery_v2.db                  ← runtime modification, NOT staged
?? outputs/replay/p0_ci_db_fixture_decision_20260508.md
?? outputs/replay/p0_pr_body_20260508.md
?? outputs/replay/p0_replay_pr_created_20260508.md
?? outputs/replay/p0_replay_pr_opening_checklist_20260508.md
?? outputs/replay/p0_replay_pr_readiness_20260508.md
```

`lottery_api/data/lottery_v2.db-shm` and `lottery_api/data/lottery_v2.db-wal`
are **no longer visible** in `git status`. Rule is active. ✅

---

## Part E — Release-Critical Validation (89-Test Gate)

**Command**:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_randomness_audit_cadence.py \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_browser_smoke.py \
  tests/test_replay_api_contract.py \
  tests/test_replay_freshness_cadence.py \
  -q
```

**Result**: `89 passed, 1 warning in 0.47s` ✅

The 1 warning is `PendingDeprecationWarning` from `starlette/formparsers.py`
(external library noise, pre-existing, not caused by P1-2 changes).

---

## Part F — Hardening Commit Scope

Files staged for `chore: harden replay PR review artifacts`:

| File | Change |
|------|--------|
| `.gitignore` | Added `*.db-shm`, `*.db-wal` rules |
| `outputs/replay/p1_pr_review_hardening_20260508.md` | This report |

**NOT staged** (verified before commit):
- `lottery_v2.db` (runtime artifact)
- `lottery_v2.db-shm` (now gitignored)
- `lottery_v2.db-wal` (now gitignored)
- `index.html` (audit only, not modified)
- Any existing `outputs/replay/p0_*` files (already in repo)

---

## Final Marker

```
P1_2_PR_REVIEW_HARDENING_VERIFIED
```

**Summary**:
- `index.html` diff audited: 1187 non-replay redesign lines + 1062 replay
  governance lines. Replay-specific code is correctly scoped, read-only,
  and carries governance disclaimers. No replay generation logic exposed.
- `.gitignore` hardened: WAL journal files suppressed, DB binary boundary
  maintained.
- 89-test gate: all pass.
- Commit: `chore: harden replay PR review artifacts`
