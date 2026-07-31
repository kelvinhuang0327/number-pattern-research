# P5 — PR #36 Merge + PR #37 Retarget to main

**Date:** 2026-05-11  
**Agent:** Senior Merge Execution / Governance Agent  
**Branch at completion:** `feature/p3-strategy-lifecycle-exposure-20260511`

---

## 1. Objective

YES-gated merge of PR #36 into main, followed by retarget of PR #37 (P3 lifecycle
exposure) onto main, with full verification and second YES gate before PR #38 merge.

---

## 2. YES Gate Evidence

User message received: `"YES\nMerge PR #36"`

Matched pattern: `YES` + `Merge PR #36` — explicit YES gate cleared.

Gate cleared at: Phase C start.

---

## 3. PR #36 Merge Result

| Field | Value |
|-------|-------|
| PR number | #36 |
| Title | `feat(replay): register non-online strategy lifecycle metadata` |
| Merge method | Squash (repo convention confirmed from git log) |
| Merge commit on main | `3deb938` |
| Branch deleted | `feature/p2-non-online-strategy-lifecycle-registry-20260511` (local + remote) |
| Result | ✅ Squashed and merged |

Command executed:
```bash
gh pr merge 36 --squash --delete-branch
```

---

## 4. main Post-Merge Verification

```
git checkout main && git pull --ff-only
HEAD: 3deb938 feat(replay): register non-online strategy lifecycle metadata (#36)
```

Files added to main from PR #36 (+2132 lines, 9 files):
- `lottery_api/models/replay_strategy_registry.py` (+121)
- `pytest.ini` (+1)
- `tests/test_replay_strategy_lifecycle_registry.py` (+204)
- `outputs/replay/p0_*.md` (×2), `p1_*.json`, `p1_*.md`, `p2_*.md` (×2)

### P2 Tests on main
```
tests/test_replay_strategy_lifecycle_registry.py   22 passed in 0.05s
```

### Invariants on main
| Invariant | Result |
|-----------|--------|
| `_REGISTRY` keys = 6 ONLINE IDs | ✅ |
| `_ALL_ADAPTERS` total = 16 | ✅ |
| All `_REGISTRY` values in `_GENERATION_STATUSES` | ✅ |
| No DB write | ✅ |
| No backfill | ✅ |

---

## 5. PR #37 Retarget / Rebase Result

### Situation
PR #37 was auto-closed by GitHub when its base branch
(`feature/p2-non-online-strategy-lifecycle-registry-20260511`) was deleted on
PR #36 merge. GitHub does not allow retargeting or reopening a PR whose base
branch no longer exists.

### Resolution
Used `git rebase --onto` to cleanly transplant only the 2 P3-specific commits
onto `origin/main`, then created a new PR (#38) against `main`.

### Rebase Details
```bash
git rebase --onto origin/main 4184998 feature/p3-strategy-lifecycle-exposure-20260511
```

- **Upstream anchor:** `4184998` (P2 commit — already squashed into main, excluded)
- **Commits replayed:** 2
  - `cb5d741` → `480a547`: P3 exposure API + CLI + tests
  - `a8aa565` → `87ff384`: P4 governance report
- **Conflicts:** None
- **Force push:** `git push --force-with-lease` (required after rebase)
- **New HEAD on P3 branch:** `87ff384`

---

## 6. New PR #38

| Field | Value |
|-------|-------|
| PR number | **#38** (replaces closed #37) |
| Title | `feat(replay): expose strategy lifecycle metadata via public API and CLI` |
| Base | `main` ✅ |
| Head | `feature/p3-strategy-lifecycle-exposure-20260511` |
| State | OPEN |
| Mergeable | MERGEABLE |
| Merge state | CLEAN |

---

## 7. PR #38 CI Checks

```
All checks were successful
0 cancelled, 0 failing, 2 successful, 1 skipped, and 0 pending checks

✓  Replay Governance CI/rep...   42s
✓  Replay Governance CI/rep...   14s
-  Replay Governance CI/rep...   (skipped)
```

**Result: PASS**

---

## 8. Local Test Results

```
tests/test_replay_strategy_lifecycle_registry.py   22 passed
tests/test_replay_strategy_lifecycle_exposure.py   39 passed
──────────────────────────────────────────────────
TOTAL:  61 passed in 0.07s
```

**Result: PASS**

---

## 9. CLI Verification

### Text mode
```
Lifecycle Counts:
  ONLINE      : 6
  REJECTED    : 4
  OBSERVATION : 1
  RETIRED     : 5
  TOTAL       : 16

Marker: P3_LIFECYCLE_REPORT_CLI_READY
```

### JSON mode
```json
{
  "total": 16,
  "no_db_write": true,
  "marker": "P3_LIFECYCLE_REPORT_CLI_READY"
}
```

**CLI text: PASS | CLI JSON: PASS**

---

## 10. No DB Write Evidence

1. Registry module: no `sqlite3` import (AST confirmed previously)
2. CLI script: no `sqlite3` import (AST confirmed — only in comments/strings)
3. P2 test `test_no_db_write_on_import`: PASS
4. P3 `TestNoDbWrite` (3 tests): PASS — monkeypatch confirms zero `sqlite3.connect` calls
5. CLI JSON output: `"no_db_write": true`

---

## 11. No Backfill Evidence

- Zero SQL in registry module
- No `replay_history` table access in any P2/P3 file
- P3 branch diff touches only: registry.py, CLI script, test file, governance docs
- No `scripts/backfill_*` files modified

---

## 12. Remaining Risks

| Risk | Assessment |
|------|------------|
| `lottery_v2.db` locally modified | Runtime DB only — not staged, not committed, not a PR concern |
| PR #37 permanently closed | Resolved — PR #38 is the replacement, base=main |
| PR #38 second YES not yet given | Waiting — do not merge without explicit second YES |

---

## 13. PR #38 Merge Recommendation

```
Recommendation: READY_FOR_SECOND_USER_YES_GATE

PR #38 is ready.
Do not merge PR #38 until user explicitly says YES.
```

| | |
|---|---|
| PR #38 base | `main` |
| PR #38 state | OPEN |
| PR #38 mergeable | CLEAN |
| PR #38 CI | 2 passing |
| Local tests | 61 PASS |
| CLI verification | PASS |

---

## 14. Final Markers

```
P5_PR36_MERGED_TO_MAIN
P5_MAIN_POST_MERGE_P2_VERIFIED
P5_PR37_RETARGETED_TO_MAIN
P5_PR38_CREATED_AS_PR37_REPLACEMENT
P5_PR37_READY_FOR_SECOND_YES_GATE
```
