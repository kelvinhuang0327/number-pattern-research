# P4 — PR #36 / PR #37 Merge Readiness Gate

**Date:** 2026-05-11  
**Reviewer:** Merge Readiness / Governance Review Agent  
**Branch at review time:** `feature/p3-strategy-lifecycle-exposure-20260511`

---

## 1. Objective

Execute the merge readiness gate for PR #36 and PR #37 (stacked).  
Verify lifecycle registry + exposure layer do not write DB, do not backfill, and do not make non-ONLINE strategies executable.  
No merges performed. User YES required before any merge.

---

## 2. Phase A — Baseline / Open PR Gate

| Check | Result |
|-------|--------|
| Working tree clean | NOTE: `data/lottery_v2.db` modified locally (not staged, runtime DB) — not part of any PR |
| Staged changes | None |
| Untracked files | None |
| PR #36 open | ✅ OPEN |
| PR #37 open | ✅ OPEN |
| PR #37 stacked correctly | ✅ head=`feature/p3` → base=`feature/p2` |
| Total open PRs | 5 (#37, #36, #35, #34, #2) |
| PR #36 mergeable | MERGEABLE / CLEAN |
| PR #37 mergeable | MERGEABLE / CLEAN |

**Verdict: PASS**

---

## 3. Phase B — PR #36 Readiness Check

### GitHub State
| Field | Value |
|-------|-------|
| Number | #36 |
| Title | `feat(replay): register non-online strategy lifecycle metadata` |
| State | OPEN |
| Mergeable | MERGEABLE |
| Merge state | CLEAN |
| CI checks | 2 passing, 1 skipped, 0 failing |
| Base | `main` |
| Head | `feature/p2-non-online-strategy-lifecycle-registry-20260511` |
| Commits | 2 |
| Files changed | 9 |

### Diff Scope
| File | +Lines | Purpose |
|------|--------|---------|
| `lottery_api/models/replay_strategy_registry.py` | +121 | Core: stubs, LifecycleNotExecutable, _ALL_ADAPTERS |
| `outputs/replay/p0_*.md` (×2) | +173 | PR triage docs |
| `outputs/replay/p1_*.json` | +1320 | Inventory output |
| `outputs/replay/p1_*.md` | +149 | Inventory doc |
| `outputs/replay/p2_*.md` (×2) | +164 | Classification + completion reports |
| `pytest.ini` | +1 | `pythonpath = .` (test discovery fix) |
| `tests/test_replay_strategy_lifecycle_registry.py` | +204 | 22-test deterministic suite |

Scope is appropriate — no unrelated files touched.

### Test Results (on PR #36 branch)
```
tests/test_replay_strategy_lifecycle_registry.py   22 passed in 0.03s
```

### Key Invariants Verified
| Invariant | Status |
|-----------|--------|
| `_REGISTRY` contains exactly 6 ONLINE IDs | ✅ |
| `_ALL_ADAPTERS` = 16 total | ✅ |
| `get_adapter()` raises `KeyError` for all 10 non-ONLINE IDs | ✅ (tested 3 samples) |
| `_LifecycleStub.get_one_bet()` raises `LifecycleNotExecutable` | ✅ (tested 2 samples) |
| No `sqlite3` import in registry module | ✅ (AST confirmed) |
| `test_no_db_write_on_import` passes | ✅ |

**PR #36 Readiness: PASS**

---

## 4. Phase C — PR #37 Readiness Check

### GitHub State
| Field | Value |
|-------|-------|
| Number | #37 |
| Title | `feat(replay): expose strategy lifecycle metadata via public API and CLI` |
| State | OPEN |
| Mergeable | MERGEABLE |
| Merge state | CLEAN |
| CI checks | 2 passing, 1 skipped, 0 failing |
| Base | `feature/p2-non-online-strategy-lifecycle-registry-20260511` (stacked on #36) |
| Head | `feature/p3-strategy-lifecycle-exposure-20260511` |
| Commits | 1 (`cb5d741`) |
| Files changed | 4 |

### Diff Scope
| File | +Lines | Purpose |
|------|--------|---------|
| `lottery_api/models/replay_strategy_registry.py` | +91 | 5 new public API functions |
| `scripts/report_strategy_lifecycle_registry.py` | +143 | CLI report tool (new file) |
| `tests/test_replay_strategy_lifecycle_exposure.py` | +367 | 39 P3 tests (new file) |
| `outputs/replay/p3_strategy_lifecycle_exposure_20260511.md` | +190 | Governance report |

Scope is appropriate — 4 files only, all P3-specific.

### Test Results (on PR #37 branch)
```
tests/test_replay_strategy_lifecycle_registry.py   22 passed
tests/test_replay_strategy_lifecycle_exposure.py   39 passed
──────────────────────────────────────────────────────────
TOTAL:  61 passed in 0.09s
```

### API Verification
| Check | Result |
|-------|--------|
| `list_strategy_lifecycle_metadata()` returns 16 entries | ✅ |
| ONLINE count = 6 | ✅ |
| REJECTED count = 4 | ✅ |
| RETIRED count = 5 | ✅ |
| OBSERVATION count = 1 | ✅ |
| `list_executable_strategy_ids()` = 6 ONLINE IDs only | ✅ |
| `list_non_executable_strategy_ids()` = 10 IDs | ✅ |
| `get_strategy_lifecycle_metadata(unknown)` raises `KeyError` | ✅ |
| Ordering deterministic (sorted) | ✅ |
| No adapter instances returned | ✅ (all entries `type(m) is dict`) |

### CLI Verification
| Check | Result |
|-------|--------|
| Text mode runs without error | ✅ |
| Text mode contains marker `P3_LIFECYCLE_REPORT_CLI_READY` | ✅ |
| JSON mode produces valid JSON | ✅ |
| JSON `total` = 16 | ✅ |
| JSON `no_db_write` = `true` | ✅ |
| JSON schema has all required keys | ✅ |
| No sqlite3 import in CLI script (AST) | ✅ |

**PR #37 Readiness: PASS**

---

## 5. Phase D — Integration Risk Review

### Risk Items Assessed

#### R1: Replay Execution Path Isolation
- `lottery_api/routes/replay.py` imports only `get_strategy_lifecycle_status`, `list_strategies`, `normalise_lifecycle_status` — none of these execute replays directly.
- `get_adapter()` and `get_one_bet()` have zero callers outside the registry and its tests.
- `get_adapters_for_lottery()` filters by `_GENERATION_STATUSES` — verified returns only ONLINE adapters for all 3 lottery types after P2 `_ALL_ADAPTERS` expansion.
- **Verdict: PASS**

#### R2: Non-ONLINE Strategy Executability
- `_REGISTRY` dict contains only ONLINE adapters (6 keys).
- `get_adapter()` gates on `_REGISTRY` — any non-ONLINE ID raises `KeyError`.
- `_LifecycleStub.get_one_bet()` raises `LifecycleNotExecutable` regardless of arguments.
- `get_adapters_for_lottery()` filters by `_GENERATION_STATUSES` (double guard).
- **Verdict: PASS**

#### R3: DB Write / Backfill
- Registry module: no `sqlite3` import (AST confirmed).
- CLI script: no `sqlite3` import (AST confirmed — only in comments/strings).
- P3 new API functions iterate `_ALL_ADAPTERS` in-memory only.
- `test_no_db_write_on_import` (P2), `TestNoDbWrite` (P3 × 3) all pass — monkeypatch confirms zero sqlite3.connect calls.
- `data/lottery_v2.db` locally modified is the runtime application DB — NOT touched by PR #36 or #37 code, not staged, not committed.
- **Verdict: PASS**

#### R4: _ALL_ADAPTERS Loop Risk
- Existing `list_strategies()` iterates `_ALL_ADAPTERS` — expansion to 16 is expected and handled correctly via filters.
- No unbounded loops that call `get_one_bet()` on all adapters.
- `check_replay_lifecycle_drift.py` uses `list_strategies()` for counting only — count of 16 is now correct.
- **Verdict: PASS**

#### R5: pytest.ini `pythonpath = .`
- Standard pytest configuration. Adds project root to sys.path during test runs only.
- No production side effects. Already needed for `from lottery_api.models import ...` resolution.
- **Verdict: PASS**

#### R6: Stacked PR Merge Order
- PR #37 base is `feature/p2-...` not `main`. GitHub will correctly show only the P3-specific diff (+4 files).
- After PR #36 merges to `main`, PR #37 must be **retargeted to `main`** (or rebased) before final merge.
- PR #37 cannot be merged before PR #36 without creating orphan commits on main.
- **Verdict: PASS_WITH_NOTES** — merge order must be enforced: #36 first, then retarget #37 → main.

#### R7: P3 API Misuse as Executable Source
- `list_strategy_lifecycle_metadata()`, `list_executable_strategy_ids()`, etc. return plain dicts and strings only.
- No adapter instances are returned from any P3 API.
- A caller cannot execute a bet by calling any P3 function — the functions have no execution path.
- **Verdict: PASS**

### Risk Summary

| Risk | Verdict |
|------|---------|
| R1: Replay execution path isolation | PASS |
| R2: Non-ONLINE non-executable | PASS |
| R3: No DB write / backfill | PASS |
| R4: `_ALL_ADAPTERS` loop safety | PASS |
| R5: pytest.ini side effects | PASS |
| R6: Stacked PR merge order | PASS_WITH_NOTES |
| R7: P3 API misuse as executable source | PASS |

**Overall Risk Verdict: PASS_WITH_NOTES**  
Note: PR #36 must merge before PR #37. After PR #36 merges, retarget PR #37 base to `main` and rerun CI before final merge.

---

## 6. Phase E — Minimal Fix

**No blockers found. No code changes required.**

---

## 7. No DB Write Evidence

1. **AST import scan** — `sqlite3` not imported in `lottery_api/models/replay_strategy_registry.py` or `scripts/report_strategy_lifecycle_registry.py`.
2. **P2 test** — `test_no_db_write_on_import` patches `sqlite3.connect` and asserts zero calls on registry import.
3. **P3 tests** — `TestNoDbWrite` (3 tests) patch `sqlite3.connect` and assert zero calls across all 5 exposure API functions and both CLI modes.
4. All 4 no-DB-write tests PASS on the P3 branch.

---

## 8. No Backfill Evidence

- Zero `INSERT`, `UPDATE`, `DELETE` SQL in registry module (no SQL at all).
- CLI script reads only in-memory registry data, no DB connection code.
- No `replay_history` table access in any P2/P3 file.
- P3 branch does not modify `scripts/backfill_replay_history_cutoff.py` or any DB write script.

---

## 9. ONLINE-Only Executable Invariant

- `_REGISTRY` = `{a.strategy_id: a for a in _ALL_ADAPTERS if a.meta.status in _GENERATION_STATUSES}`
- `_GENERATION_STATUSES = frozenset({"ONLINE", "ACTIVE"})`
- `get_adapter()` checks `strategy_id not in _REGISTRY` — raises `KeyError` for non-ONLINE.
- `get_adapters_for_lottery()` filters by `_GENERATION_STATUSES` explicitly.
- Verified: POWER_LOTTO=2, BIG_LOTTO=2, DAILY_539=2 — all ONLINE.

---

## 10. Non-ONLINE Non-Executable Invariant

- `_LifecycleStub.get_one_bet()` raises `LifecycleNotExecutable` unconditionally.
- 10 stubs registered: 4 REJECTED + 5 RETIRED + 1 OBSERVATION.
- `test_get_one_bet_raises_lifecycle_not_executable_all_lottery_types` verifies against all 3 lottery types.
- `get_strategy_lifecycle_metadata()` returns plain dict — no `get_one_bet()` method exposed.
- `list_non_executable_strategy_ids()` returns strings only — no callable or adapter.

---

## 11. Test Results Summary

### PR #36 Branch
```
22 passed in 0.03s
```

### PR #37 Branch (includes P2 tests)
```
61 passed in 0.09s  (22 P2 + 39 P3)
```

---

## 12. CLI Verification Summary
```
$ python3 scripts/report_strategy_lifecycle_registry.py
  ONLINE: 6, REJECTED: 4, OBSERVATION: 1, RETIRED: 5, TOTAL: 16
  Marker: P3_LIFECYCLE_REPORT_CLI_READY

$ python3 scripts/report_strategy_lifecycle_registry.py --json
  total: 16, no_db_write: true, marker: P3_LIFECYCLE_REPORT_CLI_READY
  All JSON keys present and correct
```

---

## 13. Blocker List

**No blockers found.**

---

## 14. Merge Recommendation

```
Recommendation: READY_FOR_USER_YES_GATE

Merge order:
  1. User says YES → Merge PR #36 into main
  2. Retarget PR #37 base from feature/p2 → main
     (or: git checkout feature/p3 && git rebase origin/main)
  3. Re-run PR #37 CI checks (expect PASS — only additive changes)
  4. User says YES → Merge PR #37 into main
```

---

## 15. Final Markers

```
P4_PR36_READINESS_REVIEWED
P4_PR37_READINESS_REVIEWED
P4_STACKED_PR_ORDER_CONFIRMED
P4_NO_DB_WRITE_NO_BACKFILL_CONFIRMED
P4_ONLINE_ONLY_EXECUTABLE_CONFIRMED
P4_PR36_PR37_MERGE_READY
```
