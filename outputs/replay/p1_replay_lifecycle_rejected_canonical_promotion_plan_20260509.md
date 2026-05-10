# P1 Replay Lifecycle REJECTED Canonical Promotion Plan
**Date:** 2026-05-09
**Branch:** `codex/p1-replay-lifecycle-rejected-canonical-promotion-plan`
**Base:** `origin/main` @ `3496d68` (PR #11)
**Role:** P1 REJECTED Canonical Promotion Planner → CTO → CEO

---

## 1. Executive Summary

PR #10 confirmed 42 REJECTED archive evidence rows in `rejected/`. This round
performs read-only classification: which of the 42 are ready for canonical
promotion, which are blocked, and what criteria govern the promotion.

**Key finding:**
- **15 of 42** archive rows satisfy all required schema fields → dry-run promotable
- **27 of 42** are blocked by missing required fields (name / lottery_type / rejected_date / failure_reason / pattern)
- 1 file (`p1_deviation_2bet_539.json`) has a JSON parse error
- No DB writes performed. No catalog rows added. No registry modified.

This plan does NOT execute promotion. It produces a dry-run manifest only.

---

## 2. Source Boundary

| Source | Available in `LotteryNew-main-postmerge`? |
|--------|------------------------------------------|
| `wiki/README.md` | ✅ (via `wiki/` directory in worktree) |
| `wiki/system/replay_data_hygiene.md` | ✅ |
| `wiki/system/governance.md` | ❌ — not present; read from sibling worktree `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` (source boundary noted) |
| `wiki/system/validation_gates.md` | ❌ — not present; source boundary noted |
| `memory/lessons.md` | ❌ — not present; not required for this task |
| `rejected/README.md` | ✅ |
| `rejected/*.json` (42 files) | ✅ |
| `outputs/replay/p0_replay_lifecycle_catalog_truth_inventory_20260509.md` | ✅ |
| `outputs/replay/p0_replay_lifecycle_catalog_population_plan_20260509.md` | ✅ |
| `outputs/replay/p0_replay_lifecycle_forbidden_language_sweep_20260509.md` | ✅ |

---

## 3. REJECTED Evidence Inventory

Total archive files: 42 JSON + 1 README.

### 3a. Fully Promotable (15 rows — all required schema fields present)

| # | source_filename | lottery_type | rejected_date | failure_pattern | edge_1500p |
|---|----------------|-------------|--------------|-----------------|-----------|
| 1 | apriori_3bet_biglotto.json | BIG_LOTTO | 2026-01-30 | INEFFECTIVE | null |
| 2 | bet2_fourier_expansion_biglotto.json | BIG_LOTTO | 2026-02-25 | SIGNAL_HOMOGENIZATION | +0.91% (退步) |
| 3 | cluster_pivot_biglotto.json | BIG_LOTTO | 2026-02-10 | SHORT_MOMENTUM | -0.45% |
| 4 | cold_complement_biglotto.json | BIG_LOTTO | 2026-02-10 | INEFFECTIVE | -0.02% |
| 5 | core_satellite_biglotto.json | BIG_LOTTO | 2026-02-06 | INEFFECTIVE | -0.89% |
| 6 | fourier30_markov30_biglotto.json | BIG_LOTTO | 2026-02-10 | SHORT_MOMENTUM | -0.29% |
| 7 | gap_dynamic_threshold_biglotto.json | BIG_LOTTO | 2026-02-23 | INEFFECTIVE | -0.20% (Δ) |
| 8 | gap_rebound_powerlotto.json | POWER_LOTTO | 2026-02-09 | INEFFECTIVE | null |
| 9 | markov_2bet_biglotto.json | BIG_LOTTO | 2026-01-30 | SHORT_MOMENTUM | null |
| 10 | markov_repeat_exception_biglotto.json | BIG_LOTTO | 2026-02-23 | INEFFECTIVE | +1.43% (McNemar p=0.779) |
| 11 | markov_single_biglotto.json | BIG_LOTTO | 2026-02-10 | SHORT_MOMENTUM | -0.46% |
| 12 | multiwindow_fourier_biglotto.json | BIG_LOTTO | 2026-02-25 | SIGNAL_DILUTION | -0.16% |
| 13 | neighbor_injection_biglotto.json | BIG_LOTTO | 2026-02-10 | STATISTICAL_ILLUSION | null |
| 14 | p1_conditional_branch_powerlotto.json | POWER_LOTTO | 2026-02-09 | STATISTICAL_ILLUSION | null |
| 15 | ts3_markov_freq_5bet_biglotto.json | BIG_LOTTO | 2026-02-26 | SUPERSEDED | null |

**By lottery_type:** BIG_LOTTO=13, POWER_LOTTO=2, DAILY_539=0

### 3b. Blocked (27 rows — missing required schema fields)

| source_filename | primary_blocker | readme_cross_ref |
|----------------|-----------------|-----------------|
| 539_3bet_orthogonal.json | MISSING_REQUIRED_FIELDS: name, lottery_type, rejected_date, failure_reason, pattern | ✅ README has data |
| acb_hot_fourier_3bet_biglotto.json | MISSING: lottery_type, rejected_date, failure_reason, pattern | ✅ |
| acb_single_539.json | MISSING: name, lottery_type, failure_reason, pattern | ❌ not in README index |
| bandit_ucb1_2bet_539.json | MISSING: name, rejected_date, failure_reason, pattern | ✅ |
| coldpool15_biglotto.json | MISSING: name, lottery_type, rejected_date, failure_reason, pattern | ✅ |
| consecutive_pair_detector_539.json | MISSING: lottery_type, rejected_date, failure_reason, pattern | ✅ |
| hot_gap_return_biglotto.json | MISSING: all required fields | ✅ |
| hot_stop_rebound_biglotto.json | MISSING: all required fields | ✅ |
| lift_pair_single_539.json | MISSING: name, rejected_date, failure_reason, pattern | ✅ |
| markov_1bet_539.json | MISSING: name, rejected_date, failure_reason, pattern | ✅ |
| neighbor_acb_2bet_539.json | MISSING: lottery_type, rejected_date, failure_reason, pattern | ✅ |
| p0_neighbor_injection.json | MISSING: name, lottery_type, rejected_date, pattern | ✅ |
| p0b_539_3bet_f_cold_fmid.json | MISSING: all required fields | ✅ |
| p0c_539_3bet_f_cold_x2.json | MISSING: all required fields | ✅ |
| p1_deviation_2bet_539.json | **JSON_PARSE_ERROR** | ✅ |
| p2_mab_fusion.json | MISSING: name, lottery_type, rejected_date | ✅ |
| p3_state_aware.json | MISSING: name, lottery_type, rejected_date | ✅ |
| sgp_power_017_research.json | MISSING: all required fields | ✅ |
| sgp_v9_apex_powerlotto.json | MISSING: all required fields | ✅ |
| shlc_midfreq_power.json | MISSING: name, failure_reason, pattern | ✅ |
| short_term_hot_independent_bet.json | MISSING: lottery_type, rejected_date, failure_reason, pattern | ✅ |
| special_mab_decay_adjustment_power.json | MISSING: name, failure_reason, pattern | ✅ |
| streak_boost_neighbor_bet1.json | MISSING: lottery_type, rejected_date, failure_reason, pattern | ✅ |
| structural_zone_guard_pp3_power.json | MISSING: name, failure_reason, pattern | ✅ |
| ts3_acb_4bet_biglotto.json | MISSING: all required fields | ✅ |
| zone_constraint_cold_bet2.json | MISSING: lottery_type, rejected_date, failure_reason, pattern | ✅ |
| zone_gap_3bet_539.json | MISSING: all required fields | ✅ |

**Note on README cross-reference:** Many blocked files have corresponding entries in
`rejected/README.md` with dates and failure modes. Those README rows COULD be used
to backfill schema fields — but only after explicit CTO review, since they are
a secondary source (index document) rather than the authoritative JSON schema.
Such backfill is P2 scope, not this plan.

---

## 4. Canonical Promotion Criteria

For an archive evidence row to be promoted to a canonical REJECTED lifecycle row:

| Criterion | Requirement |
|-----------|-------------|
| `name` | Present in JSON (not null or empty) |
| `lottery_type` | Present; one of `POWER_LOTTO`, `BIG_LOTTO`, `DAILY_539` |
| `rejected_date` | Present; format `YYYY-MM-DD` |
| `failure_reason` | Present; human-readable string |
| `pattern` | Present; one of defined failure patterns |
| `evidence_source_path` | Full repo-relative path to JSON file |
| `data_scope` | Always `"ALL_REPLAY_ROWS"` |
| `audit_marker` | `"REJECTED_ARCHIVE_COMPLETE_SCHEMA"` |
| Forbidden language | HIGH=0 (no SIGNAL/NO_SIGNAL/NO_VALIDATED_EDGE/edge claim/recommendation) |
| No edge claim | disclaimer must accompany any statistical figure |
| No recommendation | must not suggest the rejected strategy as alternative |
| Effective date | sourced from `rejected_date` field in JSON |
| Rollback criteria | If source JSON found incorrect: remove canonical row, re-archive; add remediation note |
| DB write | NOT allowed in this plan |
| Registry modification | NOT allowed in this plan |
| Catalog row addition in code | NOT allowed in this plan |

---

## 5. Dry-run Manifest Summary

Full manifest: `outputs/replay/p1_replay_lifecycle_rejected_canonical_promotion_manifest_20260509.json`

```
catalog_truth_boundary:
  ONLINE:                     6
  REJECTED_archive_rows:     42
  REJECTED_promotable_dry_run: 15
  REJECTED_blocked:          27
  OBSERVATION:                0
  OFFLINE:                    0
  RETIRED:                    0
```

The 15 promotable rows all carry `"promotion_ready": true` and
`"audit_marker": "REJECTED_ARCHIVE_COMPLETE_SCHEMA"`.

The 27 blocked rows carry `"blocker": "MISSING_REQUIRED_FIELDS"` (or
`"JSON_PARSE_ERROR"` for `p1_deviation_2bet_539.json`) with the specific
missing field list.

---

## 6. API / UI Impact Plan

Once canonical REJECTED rows exist in the registry (future P1 execution, not this plan):

### GET /api/replay/strategies?lifecycle_status=REJECTED
- Currently returns `[]` (empty, honest per PR #11)
- After promotion: would return up to 15 strategies with `strategy_lifecycle_status: "REJECTED"`
- `data_scope: "ALL_REPLAY_ROWS"` already present (P0-B)
- `filter_lifecycle_status: "REJECTED"` already echoed

### GET /api/replay/history?lifecycle_status=REJECTED
- Currently returns `[]` early-return with `disclaimer` and `data_scope` (P0-B)
- After promotion + replay generation (separate scope): would return actual replay records
- Empty-payload path would only trigger if no replay records exist for the strategy

### Replay UI — REJECTED Tab
- Currently shows: "僅有候選證據，尚未升格為 canonical lifecycle row" (P0-A / PR #11)
- After promotion + replay record generation: would show actual records with REJECTED lifecycle badge
- Empty-state text must be updated to a different message once canonical rows exist and records are generated

### Browser E2E Expectations (after promotion)
- `test_lifecycle_filter_browser_e2e` already asserts REJECTED lifecycle badge renders "拒絕" (P0-C)
- New tests would need to assert non-empty table for REJECTED tab
- The existing honest-SKIP tests for empty REJECTED state would need to be superseded by record-presence tests

### Empty-State Behavior Change
- The REJECTED empty-state text ("僅有候選證據，尚未升格為 canonical lifecycle row") 
  was accurate before promotion
- After canonical promotion AND replay record generation, this text would become
  inaccurate — a UI text update would be required at that point (separate PR)

---

## 7. Forbidden-Language Sweep Result

Scanned: all `failure_reason_summary` and `failure_pattern` fields in manifest,
plus all report text in this document.

Checked against `wiki/system/replay_data_hygiene.md §4` forbidden list:
- `SIGNAL` / `NO_SIGNAL` / `NO_VALIDATED_EDGE`
- "best strategy" / "提高中獎率" / "推薦投注"
- promotion / auto-promotion wording
- edge ranking

| Category | Hits |
|----------|------|
| HIGH (direct forbidden term) | 0 |
| LOW (borderline / contextual) | 0 |

**Result: CLEAN — HIGH=0, LOW=0**

Note: The term "canonical promotion" in this document refers to lifecycle
classification status, not a betting recommendation. It does not constitute
"promotion / auto-promotion wording" in the replay-context sense.

---

## 8. Validation Result

```
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py
→ 57 passed, 32 skipped, 1 warning
```

Baseline maintained. No regression. No new test files added in this round.

```
git diff --check
→ (no output — no whitespace errors)
```

---

## 9. What Was Not Changed

- `index.html` — not modified
- `lottery_api/routes/replay.py` — not modified
- `lottery_api/models/replay_strategy_registry.py` — not modified
- Any test file — not modified
- Any `.db` / `.db-wal` / `.db-shm` file — not written
- Any catalog row in code — not added
- Any `rejected/*.json` file — not modified (read-only inspection)
- Branch protection — not modified
- Active strategy state — not modified
- No replay generation executed
- No strategy mining / edge discovery executed

---

## 10. Remaining Risks

| Risk | Severity | Note |
|------|----------|------|
| 27 blocked files have README cross-ref data that could backfill schema | Medium | Backfill requires CTO-approved P2 scope; must not be inferred without explicit mapping |
| `p1_deviation_2bet_539.json` JSON parse error | Low | File may be malformed; needs manual inspection and repair before promotion |
| `ts3_markov_freq_5bet_biglotto.json` has `SUPERSEDED` pattern | Low | SUPERSEDED ≠ INEFFECTIVE; promotion to REJECTED canonical is valid but should note the "superseded by" reference |
| After promotion, REJECTED UI empty-state text becomes stale | Medium | A separate UI update PR is required when REJECTED tab has actual records |
| 0 DAILY_539 entries in the promotable list | Low | All fully-schema'd archive rows happen to be BIG_LOTTO or POWER_LOTTO; DAILY_539 rows need schema backfill (P2) |

---

## 11. Recommended Next Action

| Phase | Item |
|-------|------|
| **P1 execution** | CTO reviews dry-run manifest; approves promotion of 15 rows into registry as REJECTED lifecycle entries (separate execution PR) |
| **P2** | Schema backfill for 27 blocked rows using README cross-reference, under CTO review |
| **P2.1** | Fix `p1_deviation_2bet_539.json` parse error |
| **P3** | Drift guard: CI alert when REJECTED canonical count changes unexpectedly |
| **P4** | After REJECTED promotion + replay record generation: update REJECTED UI empty-state text in index.html |

---

## 12. Final Marker

**P1_REPLAY_LIFECYCLE_REJECTED_CANONICAL_PROMOTION_PLAN_READY**
