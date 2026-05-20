# P9 Canonical Artifact Index — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Purpose**: Single reference for all authoritative P0-P9 outputs. Use this index  
to locate any artifact without scanning the full `docs/replay/` or `outputs/replay/` dirs.

---

## Ground Truth Markers

| Item | Value |
|------|-------|
| Production rows | **460** |
| Registry strategies | **18** |
| Total catalog universe | **59** (18 + 41 artifact-only) |
| Coverage matrix cells | **1,288** |
| Real replay successes | **300** |
| Fake successes | **0** |

---

## Scripts (canonical — do not duplicate)

| Script | Purpose | Phase |
|--------|---------|-------|
| `scripts/replay_lifecycle_drift_guard.py` | Schema + count drift detection | P0 |
| `scripts/report_strategy_lifecycle_registry.py` | Registry lifecycle report | P0 |
| `scripts/p7_controlled_replay_row_apply.py` | P7 actual apply (gate-protected) | P0/P7 |
| `scripts/p7_controlled_replay_row_apply_dry_run.py` | P7 dry-run preview | P7 |
| `scripts/p2_full_catalog_visibility_plan.py` | 59-strategy visibility classification | P2 |
| `scripts/p3_per_draw_all_strategy_coverage_matrix.py` | 1,288-cell coverage matrix | P3 |
| `scripts/p5_replay_visual_api_verification.py` | API gap audit | P5 |
| `scripts/p6_catalog_apply_plan_v1.py` | Apply decision map | P6 |
| `scripts/p8_reconstructible_backfill_dry_run.py` | 121-candidate payload preview | P8 |

---

## Test Suites (canonical — 185 total)

| Test File | Count | Phase |
|-----------|-------|-------|
| `tests/test_replay_api_contract.py` | 44 | P0 |
| `tests/test_p7_controlled_apply_actual_gate.py` | 17 | P0/P7 |
| `tests/test_p2_full_catalog_visibility_plan.py` | 24 | P2 |
| `tests/test_p3_per_draw_all_strategy_coverage_matrix.py` | 32 | P3 |
| `tests/test_p6_catalog_apply_plan_v1.py` | 31 | P6 |
| `tests/test_p8_reconstructible_backfill_dry_run.py` | 37 | P8 |
| `tests/test_p9_replay_launch_readiness_lock.py` | 68 | P9 |

---

## Documentation (canonical)

| Document | Phase | Key Finding |
|----------|-------|------------|
| `docs/replay/p1b_registry_reconciliation_20260520.md` | P1 | 16→18 discrepancy resolved; canonical=18 |
| `docs/replay/p7_readiness_report_20260520.md` | P0/P7 | FK root cause + gate hardening |
| `docs/replay/p2_full_catalog_visibility_plan_20260520.md` | P2 | 4-state, 59-entry universe |
| `docs/replay/p3_per_draw_all_strategy_coverage_matrix_20260520.md` | P3 | 1,288 cells, fake_success=0 |
| `docs/replay/p4_apply_readiness_review_20260520.md` | P4 | 28 rows ready, 93 deferred |
| `docs/replay/p5_replay_visual_api_verification_20260520.md` | P5 | API gap + 4-field patch |
| `docs/replay/p6_catalog_apply_plan_v1_20260520.md` | P6 | 59-entry apply decisions |
| `docs/replay/p7_authorized_apply_gate_review_20260520.md` | P7 | BLOCKED — phrase not received |
| `docs/replay/p8_reconstructible_backfill_dry_run_20260520.md` | P8 | 121/121 complete, 28 ready |
| `docs/replay/p9_replay_launch_readiness_lock_20260520.md` | P9 | **This session's source of truth** |
| `docs/replay/p9_canonical_artifact_index_20260520.md` | P9 | **This file** |

---

## JSON Outputs (canonical machine-readable)

| JSON File | Phase | Contents |
|-----------|-------|---------|
| `outputs/replay/p7_controlled_apply_dry_run_20260520.json` | P7 | 121 all_plan_rows, 28 p7_insert_rows |
| `outputs/replay/p7_authorized_apply_gate_review_20260520.json` | P7 | Gate state: BLOCKED |
| `outputs/replay/p7_controlled_apply_apply_result_20260520.json` | P7 | Prior failed apply: 28 FK errors, 0 inserted |
| `outputs/replay/p2_full_catalog_visibility_plan_20260520.json` | P2 | 59-entry catalog with visibility states |
| `outputs/replay/p3_per_draw_all_strategy_coverage_matrix_20260520.json` | P3 | 1,288-entry matrix |
| `outputs/replay/p3_per_draw_all_strategy_coverage_summary_20260520.json` | P3 | Coverage pcts, fake_success=0 |
| `outputs/replay/p5_replay_visual_api_verification_20260520.json` | P5 | API field gap analysis |
| `outputs/replay/p6_catalog_apply_plan_v1_20260520.json` | P6 | Apply decisions for 59 entries |
| `outputs/replay/p8_reconstructible_backfill_dry_run_20260520.json` | P8 | 121-candidate payload previews |
| `outputs/replay/p9_replay_launch_readiness_lock_20260520.json` | P9 | **Canonical state lock** |

---

## Modified API (canonical current state)

`lottery_api/routes/replay.py` — `GET /api/replay/history` now returns:

```python
# P5 minimal patch (added to each record, non-breaking)
"visibility_state":         "ROW_BACKED",          # all current rows
"display_status":           "SHOW_REPLAY_RESULT",   # all current rows
"should_count_as_success":  bool,                   # True if actual+hit not NULL
"source_trace":             str | None,             # combined provenance chain
```

After P7 ONLINE apply (when authorized), new rows will have:
- `visibility_state` = `"ROW_BACKED"`
- `source_trace` = `"P7_CONTROLLED_APPLY|RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD|<hash>"`

---

## Apply Decision Map (canonical from P6)

| Decision | Count | Strategies |
|----------|-------|-----------|
| `SKIP` (ROW_BACKED) | 6 | biglotto_deviation_2bet, biglotto_triple_strike, daily539_f4cold, daily539_markov_cold, power_orthogonal_5bet, power_precision_3bet |
| `PLAN_INSERT_PENDING_P7_AUTH` | 2 | fourier_rhythm_3bet, ts3_regime_3bet |
| `PLAN_INSERT_PENDING_HUMAN_REVIEW` | 3 | acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet |
| `REGISTER_VISIBILITY_ONLY` | 7 | biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539, acb_markov_midfreq, midfreq_fourier_2bet, h6_gate_mk20_ew85 |
| `SKIP_NOT_REGISTERED` | 41 | All artifact-only strategies in `rejected/` |

---

## Deprecated / Superseded (do not reference)

These files exist in the repo but are superseded by the canonical artifacts above:

| Old Document | Superseded By |
|-------------|--------------|
| `docs/replay/p1_catalog_visibility_plan_20260519.md` | `p2_full_catalog_visibility_plan_20260520.md` |
| `docs/replay/p6_readiness_report_20260520.md` (old P6 from prior track) | `p6_catalog_apply_plan_v1_20260520.md` |
| `docs/replay/p7_controlled_apply_dry_run_20260520.md` | `p7_authorized_apply_gate_review_20260520.md` |
| `outputs/replay/p1_catalog_visibility_plan_20260519.json` | `p2_full_catalog_visibility_plan_20260520.json` |
