# P9 Replay Launch Readiness Lock — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Classification**: `P9_LOCKED_AWAITING_CEO_DECISION`  
**Lock JSON**: `outputs/replay/p9_replay_launch_readiness_lock_20260520.json`  
**Tests**: `tests/test_p9_replay_launch_readiness_lock.py` — **68/68 PASS**

---

## Purpose

This document is the single source of truth for the Replay Track state as of
2026-05-20. Its purpose is to prevent future agents from re-deriving context,
repeating dry-runs already completed, or taking unauthorized actions.

**Rule**: Any agent reading this document must first check the CEO phrase gate
before performing any DB writes.

---

## Production Ground Truth

| Metric | Value | Verified By |
|--------|-------|------------|
| `strategy_prediction_replays` rows | **460** | `sqlite3 + drift guard` |
| Drift guard | **PASS** | `replay_lifecycle_drift_guard.py --strict` |
| All tests | **185/185 PASS** | pytest full sweep |
| Unauthorized apply | **NONE** | `safety_flags.unauthorized_apply_performed=false` |

---

## Phase Completion Summary

| Phase | Status | Commit | Key Output |
|-------|--------|--------|-----------|
| P0 Schema stabilization | ✅ COMPLETE | `0a722dc` | P7 actual apply gate hardened |
| P1 Catalog visibility + reconciliation | ✅ COMPLETE | `0a722dc` | 18 canonical strategies, 16→18 resolved |
| P2 Full-catalog visibility plan v2 | ✅ COMPLETE | `0a722dc` | 59 entries, 4-state classification |
| P3 Per-draw coverage matrix | ✅ COMPLETE | `5c62bfa` | 1,288 cells, fake_success=0 |
| P4 Apply readiness review | ✅ COMPLETE | `5c62bfa` | 28 ONLINE rows ready |
| P5 API verification + minimal patch | ✅ COMPLETE | `fb6aad1` | 4 fields added to /history response |
| P6 Catalog apply plan v1 | ✅ COMPLETE | `fb6aad1` | 59-entry apply decision map |
| P7 Apply gate | ⏳ **BLOCKED** | `d9afe19` | Awaiting CEO phrase |
| P8 Reconstructible backfill dry-run | ✅ COMPLETE | `d9afe19` | 121/121 complete, 28 ready |
| P9 Source-of-truth hardening | ✅ COMPLETE | this commit | This document |

---

## Catalog Universe (frozen)

| Visibility State | Count | Description |
|-----------------|-------|-------------|
| ROW_BACKED | 6 | Already has `strategy_prediction_replays` rows |
| RECONSTRUCTIBLE | 5 | Has `prediction_items` data; rows can be inserted |
| NO_DATA | 7 | In registry; no source data — permanent gap |
| ARTIFACT_ONLY | 41 | Not registered; `rejected/*.json` only |
| **Total** | **59** | 18 registry + 41 artifact-only |

---

## Coverage Matrix (frozen)

| Metric | Value |
|--------|-------|
| Active draw universe | 209 draws |
| Total matrix cells | 1,288 |
| ROW_BACKED cells | 300 (23.3%) |
| RECONSTRUCTIBLE cells | 121 (9.4%) |
| NO_DATA cells | 867 (67.3%) |
| `real_replay_success_count` | 300 |
| `fake_success_count` | **0** |

**The 867 NO_DATA cells are permanent structural gaps** — no action will fill them without fabricating data.

---

## P7 Gate State (frozen)

| Item | Value |
|------|-------|
| Authorization phrase | `YES apply P7 controlled replay rows` |
| Phrase received | **NO** |
| ONLINE scope | `fourier_rhythm_3bet`×12 + `ts3_regime_3bet`×16 = **28 rows** |
| Projected rows after ONLINE apply | 460 → **488** |
| RETIRED scope | 93 rows — **DEFERRED** |
| Projected rows after ONLINE+RETIRED | 460 → 581 |
| FK root cause | Fixed (`replay_run_id=None` in `_build_payload()`) |
| Temp rehearsal | 460→488 verified, idempotency verified, rollback verified |

---

## P8 Reconstructible State (frozen)

| Item | Value |
|------|-------|
| Total candidates | 121 |
| Have `prediction_items` | 121/121 — 100% |
| Have draw result | 121/121 — 100% |
| Have both (fully constructable) | 121/121 — 100% |
| `READY_FOR_ONLINE_APPLY` | 28 |
| `PENDING_HUMAN_REVIEW_RETIRED` | 93 |

All 28 ONLINE rows are data-complete. **No waiting for data.**  
The only blocker is the CEO authorization phrase.

---

## API State (frozen)

`GET /api/replay/history` now returns 4 additional fields (P5 minimal patch):
- `visibility_state` = `"ROW_BACKED"` for all current rows
- `display_status` = `"SHOW_REPLAY_RESULT"` for all current rows
- `should_count_as_success` = `true` if `actual_numbers` and `hit_count` are not NULL
- `source_trace` = combined `source|truth_level|provenance_hash` or `null`

No UI redesign performed. 44/44 API contract tests PASS.

---

## Invariants (must not be violated)

| Invariant | Value |
|-----------|-------|
| No RETIRED rows in P7 ONLINE apply | ✅ |
| No ARTIFACT_ONLY marked ONLINE | ✅ |
| NO_DATA never counted as success | ✅ |
| `fake_success_count` = 0 always | ✅ |
| Production rows = 460 (until CEO auth) | ✅ |
| All tests green | ✅ |
| Drift guard PASS | ✅ |

---

## Two Valid Next Actions

### ACTION_A — P7 ONLINE Apply (requires CEO phrase)

```
YES apply P7 controlled replay rows
```

Effect: 460 → 488 rows. ROW_BACKED cells 300 → 328.  
Scope: ONLINE only (28 rows). RETIRED (93) remain deferred.  
Pre-apply: create backup, verify count=460, run apply script.  
Post-apply: verify count=488, rerun idempotency (0 inserts), API contract PASS, drift guard PASS.

### ACTION_B — P10 Operations Readiness (no DB change)

Continue without CEO phrase. Produce:
- Operations runbook (monitoring, alerting, on-call procedure)
- Post-apply verification checklist for when P7 is eventually authorized
- Nothing written to DB; production stays at 460

---

## Do Not

- ❌ Re-run P0-P8 dry-runs (already done; results frozen)
- ❌ Apply 93 RETIRED rows without separate human review + CEO auth
- ❌ Mark any ARTIFACT_ONLY strategy as ONLINE
- ❌ Count RECONSTRUCTIBLE/NO_DATA rows as replay successes
- ❌ Fabricate `actual_numbers`, `hit_count`, or predictions
- ❌ Modify `strategy_prediction_replays` without CEO phrase
