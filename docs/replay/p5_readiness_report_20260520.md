# P5 Historical Reconstruction Dry-run Readiness Report

Generated: 2026-05-20  
Branch: `claude/clever-villani-2f0ef7`  
Agent: LotteryNew Replay Track CTO Agent

---

## 1. P0–P4 Baseline Recap

| Phase | Status | Key Fact |
|-------|--------|----------|
| P0 | ✅ PASS | 460 legacy rows, schema migrated, drift guard PASS |
| P1 | ✅ PASS | 59 catalog entries planned (REGISTERED=6, RECON=12, ARTIFACT=41) |
| P2 | ✅ PASS (dry-run) | strategy_catalog apply dry-run; NOT live applied |
| P3 | ✅ PASS | API/UI contract: 5-state readiness flags, DB→P2→P1 fallback |
| P4 | ✅ PASS | Coverage matrix: 59-entry denominator, 50 draws, 400 cells, COVERED=0 |

---

## 2. P4 Freshness Gap Recap

**P4 key finding:** All 50 most recent draws are DAILY_539 draws (115000072–115000121).  
Coverage for those 50 draws:

| Status | Count |
|--------|-------|
| COVERED | **0** (0.0%) |
| MISSING_REPLAY_ROW | 100 (2 production-registered strategies × 50 draws) |
| RECONSTRUCTIBLE_PENDING | **300** (6 DAILY_539 RECONSTRUCTIBLE strategies × 50 draws) |

The 460 legacy rows cover older draws only. P5 is the plan to begin closing this gap — but only for strategies that have historical prediction payload.

---

## 3. P5 Scope: Dry-run Plan Only

P5 **does not insert any rows**. It produces a `rows_to_insert` plan that P7 Controlled Apply can execute after P6 Source Promotion Policy approval.

- Scope: DAILY_539 RECONSTRUCTIBLE strategies, 50 most recent draws
- All output: `dry_run_only=True`, `can_apply=False`, `truth_level=RECONSTRUCTION_PLAN_ONLY`
- No strategy logic executed; no prediction numbers invented

---

## 4. Reconstructible Strategy Count

**Total RECONSTRUCTIBLE in catalog: 12**  
In P5 scope (DAILY_539, in P4 matrix range): **6 strategies**

| Strategy | Lifecycle | Artifact Source | Evidence Class |
|----------|-----------|-----------------|----------------|
| `acb_markov_midfreq_3bet` | RETIRED | PREDICTION_LOG | SOURCE_AVAILABLE |
| `acb_1bet` | RETIRED | PREDICTION_LOG | SOURCE_AVAILABLE |
| `midfreq_acb_2bet` | RETIRED | PREDICTION_LOG | SOURCE_AVAILABLE |
| `acb_markov_midfreq` | RETIRED | CODE_SCAN | NEEDS_P6_POLICY |
| `midfreq_fourier_2bet` | RETIRED | CODE_SCAN | NEEDS_P6_POLICY |
| `p1_deviation_2bet_539` | REJECTED | REJECTED_JSON | PROVENANCE_MISSING |

Non-DAILY_539 RECONSTRUCTIBLE (6 strategies: `fourier_rhythm_3bet`, `ts3_regime_3bet`, `h6_gate_mk20_ew85`, `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `power_shlc_midfreq`) are outside the P4 50-draw window (which only captured DAILY_539 draws) and are not classified in this P5 run.

---

## 5. Candidate Cell Count

| Metric | Value |
|--------|-------|
| P4 RECONSTRUCTIBLE_PENDING cells (P5 scope) | 300 |
| PLAN_INSERT_REPLAY_ROW | **62** |
| SKIP_NO_HISTORICAL_PAYLOAD | 88 |
| SKIP_SOURCE_MISSING | 50 |
| NEEDS_P6_POLICY | 100 |
| **Total classified** | **300** ✅ |

---

## 6. rows_to_insert_planned: 62

**Breakdown by strategy:**

| Strategy | Plannable Draws | Skip Draws | Skip Reason |
|----------|----------------|-----------|-------------|
| `acb_markov_midfreq_3bet` | **44** | 6 | SKIP_NO_HISTORICAL_PAYLOAD (draws outside log coverage) |
| `acb_1bet` | **9** | 41 | SKIP_NO_HISTORICAL_PAYLOAD (log only covers up to draw ~115000085) |
| `midfreq_acb_2bet` | **9** | 41 | SKIP_NO_HISTORICAL_PAYLOAD (same as acb_1bet) |
| `acb_markov_midfreq` | 0 | 50 | NEEDS_P6_POLICY (CODE_SCAN; cannot re-execute in P5) |
| `midfreq_fourier_2bet` | 0 | 50 | NEEDS_P6_POLICY (CODE_SCAN; cannot re-execute in P5) |
| `p1_deviation_2bet_539` | 0 | 50 | SKIP_SOURCE_MISSING (REJECTED_JSON has no per-draw payload) |

---

## 7. Skipped by Reason

| Reason | Count | Explanation |
|--------|-------|-------------|
| `NEEDS_P6_POLICY` | 100 | CODE_SCAN source; P5 prohibits strategy re-execution |
| `SKIP_NO_HISTORICAL_PAYLOAD` | 88 | PREDICTION_LOG source but no entry for this specific draw |
| `SKIP_SOURCE_MISSING` | 50 | REJECTED_JSON artifact has no per-draw prediction data |

---

## 8. Provenance Quality Summary

| Metric | Value |
|--------|-------|
| Plan rows with provenance_hash | 62 |
| Plan rows without provenance_hash | 238 (all are SKIP rows) |
| ARTIFACT_DERIVED trust level | 62 |
| UNKNOWN trust level | 238 (SKIP rows) |

All 62 `PLAN_INSERT_REPLAY_ROW` entries have:
- `provenance_hash` (SHA-256 of `P5|strategy|draw|run_id|source`)
- `predicted_numbers` from `prediction_items.numbers` in DB
- `run_id` reference to source `prediction_runs` row
- `trust_level = ARTIFACT_DERIVED`

---

## 9. Risks and Unknowns

1. **RETIRED strategies**: `acb_1bet`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet` are RETIRED. Inserting replay rows for retired strategies requires a policy decision: are retired strategies visible on the UI replay page?

2. **MULTI_STRATEGY sub-item attribution**: `acb_1bet` and `midfreq_acb_2bet` items live inside MULTI_STRATEGY orchestrator runs. The sub-item attribution is reliable (via `prediction_items.strategy_name`) but the relationship is indirect.

3. **Draw gap for `acb_1bet` and `midfreq_acb_2bet`**: Only 9 of 50 draws covered. The MULTI_STRATEGY log stops at draw ~115000085; the 41 later draws have no log entries. P7 apply would create a sparse history.

4. **CODE_SCAN strategies need human review before P6**: `acb_markov_midfreq` and `midfreq_fourier_2bet` could theoretically be re-run from code to generate historical predictions. This requires a P6 Source Promotion Policy decision and an explicit approval.

5. **Non-DAILY_539 strategies not yet inventoried**: `fourier_rhythm_3bet` (POWER_LOTTO, ONLINE) and `ts3_regime_3bet` (BIG_LOTTO, ONLINE) both have PREDICTION_LOG source. A P5 run with `--lottery-type ALL` could plan rows for those too, but requires BIG/POWER draws in the denominator.

---

## 10. Why P6 Source Promotion Policy is Required Before P7 Apply

**P5 identifies what can be reconstructed. P6 decides what should be reconstructed.**

P6 must answer:
- Which trust levels are acceptable for P7 apply? (ARTIFACT_DERIVED only? LOG_DERIVED too?)
- Should RETIRED strategies' rows appear in the UI replay page?
- For CODE_SCAN strategies: is re-execution allowed? Under what audit trail?
- What rollback mechanism is required? (P7 must provide a rollback path)
- What provenance_hash format will the production `strategy_prediction_replays` rows carry?

Without P6 policy, P7 apply is unsafe: rows could be inserted with wrong truth_level, wrong provenance, or for strategies that should not appear in the UI.

---

## 11. Next Step Recommendation: P6 Source Promotion Policy

### P6 Deliverables

1. **Promotion tiers policy** — which evidence classes can proceed to P7:
   - Tier 1 (auto-approve): ARTIFACT_DERIVED from PREDICTION_LOG
   - Tier 2 (human review): LOG_DERIVED from JSONL
   - Tier 3 (blocked until audit): CODE_SCAN re-execution

2. **Rollback plan** — `p6_rollback_plan.md` specifying:
   - Rollback tag per batch
   - Verification query after P7 apply
   - Revert procedure

3. **Lifecycle policy** — whether RETIRED/REJECTED strategies appear in UI

4. **Provenance standard** — finalize `provenance_hash` scheme and `truth_level` mapping for P7 rows

### P6 Is Unblocked When
- P5 plan is reviewed and approved
- CEO YES received for P7 scope
- Rollback plan written

### P7 Controlled Apply Is Unblocked When
- P6 source promotion policy is approved
- P5 plan's 62 PLAN_INSERT_REPLAY_ROW rows reviewed one more time
- Backup taken
- Rollback tested in staging

---

## 12. Test Results

```
tests/test_replay_api_contract.py              44/44  PASS
tests/test_p1_catalog_visibility_contract.py   13/13  PASS
tests/test_p1_catalog_visibility_plan.py       16/16  PASS
tests/test_p2_catalog_apply_contract.py        10/10  PASS
tests/test_p2_catalog_apply_dry_run.py         13/13  PASS
tests/test_p2_catalog_apply_idempotency.py      7/7   PASS
tests/test_p3_replay_catalog_api_contract.py   56/56  PASS
tests/test_p3_replay_catalog_ui_state_contract.py 11/11 PASS
tests/test_p4_replay_coverage_matrix.py        34/34  PASS
tests/test_p5_reconstruction_plan_contract.py  39/39  PASS
tests/test_p5_reconstruction_input_inventory.py 18/18 PASS
tests/test_p5_historical_reconstruction_plan.py 26/26 PASS
TOTAL:                                         287/287 PASS
```

Drift guard: **REPLAY_LIFECYCLE_DRIFT_GUARD_PASS**
