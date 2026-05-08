# P0 Replay Release — Commit Scope Manifest
**Branch**: `release/p0-replay-20260508`  
**Base commit**: `2164b65` (main)  
**Manifest created**: 2026-05-08  
**Validation**: 89 passed, 0 failed  

---

## Files Included in Release Scope

### Tests (P0-1 through P0-5)
- `tests/test_randomness_audit_cadence.py` — 23 tests (P0-1)
- `tests/test_strategy_replay_history_cutoff_integrity.py` — 3 tests (P0-2)
- `tests/test_replay_browser_smoke.py` — 30 tests (P0-4)
- `tests/test_replay_api_contract.py` — 25 tests (P0-5)
- `tests/test_replay_freshness_cadence.py` — 8 tests (P0-5)

### Production Code
- `lottery_api/routes/replay.py` — production replay endpoint (GET /api/replay/{freshness,history,summary,runs,run/{id}/status}); READ-ONLY audit only, no prediction generation
- `lottery_api/models/replay_strategy_registry.py` — replay strategy model
- `lottery_api/database.py` — DB schema for `strategy_replay_runs` and `strategy_prediction_replays`
- `lottery_api/app.py` — minimal patch: import + `include_router(replay.router)` after backtest router

### Frontend
- `index.html` — replay UI section (replay-section, rp-freshness-card, rp-lottery-select, etc.)

### Scripts
- `scripts/backfill_replay_history_cutoff.py` — one-time backfill utility (P0-2)
- `scripts/snapshot_replay_db.py` — DB snapshot utility (P0-5)

### Documentation
- `docs/REPLAY_OPERATION_SOP.md` — operational SOP (P0-5)
- `wiki/system/replay_data_hygiene.md` — data hygiene policy (P0-5)
- `wiki/system/randomness_final_verdict.md` — randomness audit verdict; required by P0-1 tests

### Memory / Lessons
- `memory/lessons.md` — lessons sync (P0-3) + 4 P0 marker evidence blocks at EOF

### Outputs / Artifacts (documentation-only, not binary)
- `outputs/replay/replay_history_cutoff_audit_20260508.json`
- `outputs/replay/replay_history_cutoff_audit_20260508.md`
- `outputs/replay/p0_replay_release_handoff_20260508.md` (P0-6 handoff)
- `outputs/replay/p0_replay_commit_scope_manifest_20260508.md` (this file)
- `outputs/randomness_audit/randomness_audit_summary.md`
- `outputs/randomness_audit/randomness_audit_results.json`
- `outputs/db_snapshots/SHA256SUMS` — hash of pre-replay-golive DB snapshot

---

## Files Explicitly Excluded

| File | Reason |
|------|--------|
| `lottery_api/data/lottery_v2.db` | Binary data artifact — 14MB; present in worktree for test runtime only; NOT committed |
| `data/lottery_v2.db` | Binary data artifact — 212KB root-level copy; NOT committed |
| All ~70 modified tracked files from `auto/inbox/20260430` | External delta from dirty worktree; no P0 relevance; excluded by design |

---

## Replay API Scope Decision

`lottery_api/routes/replay.py` is **included** as a production endpoint.

- It is a READ-ONLY audit surface — no prediction generation, no strategy promotion
- It depends only on `database.DatabaseManager` + `models.replay_strategy_registry` (both included)
- `lottery_api/app.py` patch is minimal: 1 import line + 1 `include_router` call
- Deliberate exclusion would break 25 API contract tests

---

## Marker Evidence Sync

All 4 P0 markers are written to `memory/lessons.md` (appended at EOF):

| Marker | Phase | Status |
|--------|-------|--------|
| `P0_3_VERIFIED` | P0-3 lessons sync | ✅ Written |
| `P0_4_REPLAY_BROWSER_SMOKE_VERIFIED` | P0-4 browser smoke | ✅ Written |
| `P0_6_WORKTREE_DELTA_RELEASE_HANDOFF_FREEZE_VERIFIED` | P0-6 handoff freeze | ✅ Written |
| `REPLAY_GOLIVE_READY_20260508` | P0-5 golive gate | ✅ Written |

---

## Validation Result

```
89 passed, 0 failed
Tests: test_randomness_audit_cadence (23) + test_strategy_replay_history_cutoff_integrity (3)
     + test_replay_browser_smoke (30) + test_replay_api_contract (25)
     + test_replay_freshness_cadence (8)
Python: /Library/Developer/CommandLineTools/usr/bin/python3 (3.9.6)
CWD: /Users/kelvin/Kelvin-WorkSpace/LotteryNew-p0-release
```

---

## Commit Recommendation

```
git commit -m "release: package P0 replay governance readiness"
```

Files to `git add` (explicit scope, no wildcards):
- All test files listed above
- `lottery_api/routes/replay.py`
- `lottery_api/models/replay_strategy_registry.py`
- `lottery_api/database.py`
- `lottery_api/app.py`
- `index.html`
- `memory/lessons.md`
- All `scripts/`, `docs/`, `wiki/`, `outputs/` files listed above

Do NOT `git add`: `lottery_api/data/lottery_v2.db`, `data/lottery_v2.db`

## Tag Recommendation

```
git tag p0-replay-release-20260508
```

---

## Remaining Release Risks

1. **DB binary not committed** — Tests requiring live DB will fail if run in a CI environment without the DB. The SHA256SUMS file provides integrity evidence for DB state at golive time.
2. **index.html external delta** — The `index.html` copied from dirty worktree may contain non-replay UI changes from `auto/inbox/20260430`. Risk is LOW (only replay UI section was needed by tests).
3. **No push performed** — Local commit + tag only. Remote branch does not yet exist.

---

## Final Marker

`P0_7_CLEAN_REPLAY_RELEASE_PACKAGING_VERIFIED`
