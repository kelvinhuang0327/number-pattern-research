# P107B: Stale Baseline Guard Repair

**Date:** 20260527  
**Classification:** `P107B_STALE_BASELINE_GUARD_REPAIR_READY`  
**Artifact:** `outputs/replay/p107b_stale_baseline_guard_repair_20260527.json`

---

## PROJECT CONTEXT LOCK

| Field | Value |
|---|---|
| Repository | LotteryNew |
| DB | `lottery_api/data/lottery_v2.db` |
| DB status | **READ-ONLY** — no writes in this task |
| Replay rows (before / after) | 54462 / 54462 |
| Branch at task start | `main` @ `782e261` (P107A squash merge) |
| Working branch | `p107b-stale-baseline-guard-repair` |

---

## Why P107B Exists

After P104 ingested 4_STAR draws and P105/P106/P107A accepted the new DB baseline,
two active test files retained assertions from the pre-P104 era:

| Test | Stale Assertion |
|---|---|
| `test_p98::test_11_no_4star_backtest_metrics` | `assert star4_rows == 0` |
| `test_p99::test_14_special4_data_gap_blocking` | `assert star4_count == 0` |

Both tests correctly captured the DB state at the time they were written.
After P104 ingested 2922 4_STAR rows, these assertions became stale and caused
spurious CI failures. P107B surgically repairs only the live-DB cross-check
assertions. Historical artifact facts are preserved unchanged.

---

## Accepted Post-P104 Baseline

| Field | Value |
|---|---|
| Replay rows | **54462** |
| 3_STAR count | **4179** |
| 3_STAR max draw | **115000106** |
| 4_STAR count | **2922** |
| 4_STAR max draw | **115000103** |
| POWER_LOTTO count | **1913** |
| POWER_LOTTO max draw | **115000041** |

This baseline was confirmed by P105 (acceptance decision), P106 (prospective
evaluation rerun), and P107A (100-draw monitoring gate, 63/100 draws observed,
37 more needed).

---

## Historical vs Current Distinction

### Historical baselines (P98/P99 era, pre-P104)

| Field | Historical Value |
|---|---|
| 3_STAR count | 4115 |
| 3_STAR max draw | 115000024 |
| 4_STAR count | **0** |
| special4_status | DATA_GAP_BLOCKING |

These values were recorded correctly in the P98 and P99 JSON artifacts.
P107B does **NOT** rewrite any historical artifact files.

### Current accepted baseline (post-P104)

See table above. P104 ingested 2922 4_STAR draws from an `source_unknown`
provenance. P105 accepted this state for Special3 evaluation only.
The `source_unknown` caveat remains on record; it is not cleared by P107B.

---

## Repaired Tests

### `tests/test_p98_special3_oos_permutation_review.py` — `test_11`

**Old (stale):**
```python
assert star4_rows == 0, f"4_STAR has {star4_rows} rows — expected 0"
```

**New (P107B repaired):**
```python
assert star4_rows == 2922, (
    f"4_STAR count mismatch: expected 2922 (P104 accepted baseline), got {star4_rows}."
    " If rows changed, re-run P107B baseline repair."
)
```

**Rationale:** P104 ingested 2922 4_STAR rows. The first assertion (no 4_STAR
in `strategy_results`) remains correct and is preserved. Only the live-DB
cross-check is updated.

---

### `tests/test_p99_special3_prospective_dryrun_plan.py` — `test_14`

**Old (stale):**
```python
assert star4_count == 0, f"4_STAR rows should be 0, got {star4_count}"
```

**New (P107B repaired):**
```python
assert star4_count == 2922, (
    f"4_STAR count mismatch: expected 2922 (P104 accepted baseline), "
    f"got {star4_count}. Historical artifact DATA_GAP_BLOCKING remains valid."
)
```

**Rationale:** The P99 artifact assertions (`special4_status=DATA_GAP_BLOCKING`,
`star4_backtest=NOT_RUN`) are historically correct and are preserved verbatim.
Only the live-DB cross-check is updated to the post-P104 accepted baseline.

---

## Historical Artifacts NOT Rewritten

The following files are **unchanged** by P107B:

- `outputs/replay/p98_special3_oos_permutation_review_20260527.json`
- `docs/replay/p98_special3_oos_permutation_review_20260527.md`
- `outputs/replay/p99_special3_prospective_dryrun_plan_20260527.json`
- `docs/replay/p99_special3_prospective_dryrun_plan_20260527.md`

Their recorded values (`draws_loaded=4115`, `special4_status=DATA_GAP_BLOCKING`,
`special4_backtest=NOT_RUN`) remain historically accurate and must not be altered.

---

## 4_STAR Backtest Unauthorized

4_STAR backtest is **NOT AUTHORIZED** as of P107B.

Authorisation chain:
- P105: Accepted DB for Special3 evaluation only; 4_STAR provenance flagged `source_unknown`.
- P106: Prospective evaluation rerun confirmed no 4_STAR backtest performed.
- P107A: Monitoring gate active (63/100 draws observed); 4_STAR backtest blocked.
- P107B: Governance confirmations propagated — `four_star_backtest_authorized: false`.

The existence of 2922 4_STAR rows in `draws` does NOT imply authorisation.

---

## Special3 — No Promotion

Special3 promotion is **NOT AUTHORIZED** as of P107B.

- P107A monitoring gate: 63/100 draws observed, 37 more draws required.
- Promotion is blocked until the 100-draw monitoring gate completes.

---

## DB Invariants

These invariants must not be broken by any future task:

| Invariant | Value |
|---|---|
| `strategy_prediction_replays` rows | 54462 |
| `draws` 3_STAR rows | 4179 |
| `draws` 3_STAR max draw | 115000106 |
| `draws` 4_STAR rows | 2922 |
| `draws` 4_STAR max draw | 115000103 |
| `draws` POWER_LOTTO rows | 1913 |
| `draws` POWER_LOTTO max draw | 115000041 |
| Files NEVER staged | `lottery_api/data/lottery_v2.db`, `lottery_history.json` |

---

## Test Summary

| Suite | Tests | Status |
|---|---|---|
| `test_p98_special3_oos_permutation_review` | 12 | ALL PASS |
| `test_p99_special3_prospective_dryrun_plan` | 15 | ALL PASS |
| `test_replay_lifecycle_drift_guard` | — | PASS |
| `test_replay_branch_governance_guard` | — | PASS |
| `test_p105_db_state_acceptance_decision` | — | PASS |
| `test_p106_special3_prospective_evaluation_rerun` | — | PASS |
| `test_p107a_special3_100draw_monitoring_gate` | — | PASS |
| `test_p107b_stale_baseline_guard_repair` | ≥30 | ALL PASS |

---

## Staged File Scan

Staged files (whitelist — exactly 6):

1. `scripts/p107b_stale_baseline_guard_repair.py` — read-only, no SQL write verbs
2. `outputs/replay/p107b_stale_baseline_guard_repair_20260527.json` — artifact JSON
3. `docs/replay/p107b_stale_baseline_guard_repair_20260527.md` — this document
4. `tests/test_p107b_stale_baseline_guard_repair.py` — ≥30 governance tests
5. `tests/test_p98_special3_oos_permutation_review.py` — stale-test repair (test_11)
6. `tests/test_p99_special3_prospective_dryrun_plan.py` — stale-test repair (test_14)

Forbidden files confirmed NOT staged:
- `lottery_api/data/lottery_v2.db` — NOT staged
- `lottery_history.json` — NOT staged

---

## Guard Summary

| Guard | Result |
|---|---|
| `replay_lifecycle_drift_guard --strict` | PASS — no violations |
| `replay_branch_governance_guard --expected-branch p107b-stale-baseline-guard-repair --expected-rows 54462` | PASS |

---

## Governance Confirmations

| Field | Value |
|---|---|
| `historical_artifacts_rewritten` | **false** |
| `db_writes` | **false** |
| `four_star_backtest_authorized` | **false** |
| `special3_promotion_authorized` | **false** |
| `lifecycle_mutation` | **false** |
| `source_unknown_caveat_preserved` | **true** |
| `p108_100draw_rerun_performed` | **false** |

---

## Final Classification

```
P107B_STALE_BASELINE_GUARD_REPAIR_READY
```

---

## Next Recommended Task

**P108: Special3 100-Draw Monitoring Gate — Rerun Evaluation**

Wait until 37 more 3_STAR draws are observed (current: 63/100, target: 100).
Then re-run the prospective evaluation and revisit Special3 promotion eligibility.
4_STAR source provenance must be resolved before any 4_STAR backtest is considered.
