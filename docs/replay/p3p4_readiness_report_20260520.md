# P3+P4 Readiness Report

Generated: 2026-05-20  
Branch: `claude/clever-villani-2f0ef7`  
Agent: LotteryNew Replay Track CTO Agent

---

## 1. P0/P1/P2 Baseline

| Phase | Status | Key Facts |
|-------|--------|-----------|
| P0 | ✅ PASS | 460 legacy rows, schema migrated (truth_level, provenance_hash), drift guard PASS |
| P1 | ✅ PASS | 59 planned entries: REGISTERED_WITH_REPLAY_ROWS=6, RECONSTRUCTIBLE=12, ARTIFACT_CANDIDATE=41 |
| P2 | ✅ PASS (dry-run) | strategy_catalog apply dry-run complete; **NOT applied to live DB** (awaiting CEO YES) |

Baseline tests: **103/103 PASS** (44 P0 contract + 29 P1 + 30 P2)

---

## 2. P3 Completion Status

### Files Delivered
| File | Purpose |
|------|---------|
| `lottery_api/services/replay_catalog_source.py` | Catalog source adapter (DB→P2→P1 fallback) |
| `lottery_api/models/replay_catalog_api_contract.py` | API response contract, readiness flags, state messages |
| `frontend/src/replay/replayCatalogState.ts` | UI badge/state mapping (TypeScript) |
| `tests/test_p3_replay_catalog_api_contract.py` | 56 API contract tests |
| `tests/test_p3_replay_catalog_ui_state_contract.py` | 11 UI state contract tests |
| `docs/replay/p3_replay_catalog_api_ui_contract_20260520.md` | P3 contract documentation |

### P3 Test Results: **67/67 PASS**

### Key Contracts Verified
- 59 catalog entries loadable from fallback JSON ✅
- Filter by visibility state (6/12/41 counts) ✅
- Filter by lifecycle state ✅
- `RECONSTRUCTIBLE → can_show_replay_rows = False` ✅
- `ARTIFACT_CANDIDATE → is_artifact_only = True, lifecycle ≠ ONLINE` ✅
- All 5 visibility states have UI badges ✅
- TypeScript file exports `CATALOG_STATE_BADGES`, `getStateBadge` ✅
- `dry_run_only = True` for all fallback-JSON sources ✅

---

## 3. P4 Completion Status

### Files Delivered
| File | Purpose |
|------|---------|
| `scripts/p4_replay_coverage_matrix.py` | Coverage matrix planner (read-only) |
| `outputs/replay/p4_coverage_matrix_dry_run_20260520.json` | Coverage matrix artifact |
| `docs/replay/p4_coverage_matrix_dry_run_20260520.md` | Human-readable coverage report |
| `tests/test_p4_replay_coverage_matrix.py` | 34 coverage matrix tests |

### P4 Test Results: **34/34 PASS**

### P4 Coverage Matrix Summary (50 most recent draws)

| Metric | Value |
|--------|-------|
| Catalog denominator | 59 strategies |
| Draw denominator | 50 most recent draws |
| All draws were DAILY_539 | (most frequent lottery — no BIG/POWER in top 50) |
| Total cells | 400 |
| COVERED | 0 (0.0%) |
| MISSING_REPLAY_ROW | 100 (REGISTERED strategies, recent draws not covered) |
| RECONSTRUCTIBLE_PENDING | 300 (12 RECONSTRUCTIBLE DAILY_539 strategies × 50 draws... wait no, 6 per draw) |
| ARTIFACT_ONLY | 0 (41 ARTIFACT_CANDIDATE have lottery_type=UNKNOWN, no draws) |
| DB rows unchanged | 460 → 460 ✅ |

### Key P4 Finding: Freshness Gap
The 460 existing replay rows cover **older draws** only. For the 50 most recent DAILY_539 draws:
- 2 production-registered strategies show 0% coverage (MISSING_REPLAY_ROW)
- 6 RECONSTRUCTIBLE strategies show RECONSTRUCTIBLE_PENDING
- **Product impact**: the replay page cannot show recent history even for "live" strategies

This is the core motivation for P5 Historical Reconstruction.

---

## 4. Full Test Results

```
tests/test_replay_api_contract.py         44/44  PASS
tests/test_p1_catalog_visibility_contract.py  13/13  PASS
tests/test_p1_catalog_visibility_plan.py  16/16  PASS
tests/test_p2_catalog_apply_contract.py   10/10  PASS
tests/test_p2_catalog_apply_dry_run.py    13/13  PASS
tests/test_p2_catalog_apply_idempotency.py  7/7  PASS
tests/test_p3_replay_catalog_api_contract.py  56/56  PASS
tests/test_p3_replay_catalog_ui_state_contract.py  11/11  PASS (11 unique tests)
tests/test_p4_replay_coverage_matrix.py   34/34  PASS
TOTAL:                                   204/204  PASS
```

Drift guard: **REPLAY_LIFECYCLE_DRIFT_GUARD_PASS**

---

## 5. Safety Confirmation

| Check | Result |
|-------|--------|
| strategy_prediction_replays rows | 460 unchanged ✅ |
| strategy_catalog NOT applied to live DB | Confirmed ✅ |
| No replay rows generated | Confirmed ✅ |
| No prediction rows added | Confirmed ✅ |
| No LotteryNew-clean reads/writes | Confirmed ✅ |
| ARTIFACT_CANDIDATE not marked ONLINE | Confirmed ✅ |
| RECONSTRUCTIBLE not marked as replay success | Confirmed ✅ |
| All P4 ops read-only | Confirmed ✅ |

---

## 6. Next Step: P5 Historical Reconstruction Dry-run Row Plan

P5 should address the freshness gap identified in P4.

### P5 Recommended Scope
1. **Target**: 12 RECONSTRUCTIBLE strategies (those with artifact/log source)
2. **Method**: dry-run only — plan which draws can be reconstructed, how many rows
3. **Gate**: no actual row insertion without explicit CEO YES
4. **Priority**: DAILY_539 strategies first (8 in catalog, most frequent game)

### P5 Prerequisite
- P2 strategy_catalog apply (CEO YES required) — P5 should reference live catalog, not dry-run JSON
- Alternatively: P5 can proceed with P2 dry-run JSON as catalog source (same pattern as P3/P4)

### P5 Deliverables
- `scripts/p5_reconstruction_dry_run.py` — per-strategy reconstruction row plan
- `outputs/replay/p5_reconstruction_dry_run_YYYYMMDD.json` — row plan artifact
- `docs/replay/p5_reconstruction_plan_YYYYMMDD.md` — human report
- `tests/test_p5_reconstruction_dry_run.py` — contract tests

### P5 Decision Gate
Before any row insertion, P5 must produce a `p5_reconstruction_plan` with:
- `rows_to_insert: N` per strategy
- `estimated_coverage_delta: +X%`
- `requires_ceo_yes: True`

**No reconstruction row may be inserted in P5.**
