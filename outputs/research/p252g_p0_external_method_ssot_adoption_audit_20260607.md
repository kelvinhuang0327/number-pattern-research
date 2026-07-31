# P252G — P0 External Method SSOT Adoption Audit

**Date:** 2026-06-07 16:53:58  
**Task:** P252G  
**Classification:** P0_EXTERNAL_METHOD_SSOT_ADOPTION_AUDIT  

## Executive Summary

P252G audits the adoption state of the four P252C-F SSOT modules (P252C, P252D, P252E, P252F). All modules are implemented and verified. **6 active scripts** still carry duplicate logic; **9 are historical artifacts** (frozen); **4 are deferred**. Recommended next: P252H — additive SSOT import/comment blocks (no logic rewrite).

## P0 SSOT Modules Verified

| Module ID | Task | Module | Exists | Safe (no DB) | Classification OK |
|-----------|------|--------|--------|--------------|-------------------|
| M4 | P252C | `lottery_api/utils/baseline_calculator.py` | ✓ | ✓ | ✓ |
| M6 | P252D | `lottery_api/utils/correction_gate.py` | ✓ | ✓ | ✓ |
| M5 | P252E | `lottery_api/utils/permutation_test.py` | ✓ | ✓ | ✓ |
| M3 | P252F | `lottery_api/utils/rolling_window.py` | ✓ | ✓ | ✓ |

## Coverage / Adoption Matrix

| Classification | Count |
|---------------|-------|
| ALREADY_USING_SSOT | 5 |
| ACTIVE_DUPLICATE_NEEDS_MIGRATION | 6 |
| HISTORICAL_ARTIFACT_DO_NOT_EDIT | 9 |
| ARCHIVED_OR_EXPLORATORY_DEFER | 4 |
| **Total** | **24** |

## Active Duplicate Logic (needs migration)

| File | Domain | Priority | Action |
|------|--------|----------|--------|
| `analysis/p219_external_method_diagnostic_sweep.py` | baseline+correction+permutation+rolling_window | **P0** | P252H: add import header block; new research tasks should import SSOT. P219 itse… |
| `lottery_api/engine/rolling_strategy_monitor.py` | rolling_window | **P0** | P252H (Type C): replace RSM WINDOWS dict with import from rolling_window.RSM_WIN… |
| `scripts/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py` | correction | **P1** | P252H: add import comment pointing to correction_gate.py; do not rewrite — it is… |
| `scripts/p227c_star_box_play_dryrun_scan.py` | correction+permutation | **P1** | P252H: add import comment; completed task — do not rewrite.… |
| `scripts/p211r_short_mid_window_diagnostic.py` | correction+rolling_window | **P1** | P252H: add comment block citing SSOT; completed task — do not rewrite.… |
| `lottery_api/utils/benchmark_framework.py` | baseline | **P1** | P252H: new backtest code should use baseline_calculator. benchmark_framework.py … |

## Historical Artifacts (freeze — do not edit)

| File | Rationale |
|------|-----------|
| `scripts/p238b_nist_randomness_audit_artifact_build.py` | Completed task (P238B NIST audit). Read-only historical artifact.… |
| `analysis/p252b_unified_external_method_coverage_audit.py` | P252B audit script; documents gaps now closed by P252C-F. Completed artifact.… |
| `analysis/power_lotto/p161_effectiveness_baseline.py` | zen-gates era research artifact (P161). Completed. Freeze.… |
| `analysis/power_lotto/p167_ensemble_voting_research.py` | zen-gates era research artifact (P167). Completed. Freeze.… |
| `analysis/power_lotto/p173_new_strategy_minimal_prototype_read_only.py` | zen-gates era read-only prototype. Completed. Freeze.… |
| `analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py` | zen-gates era read-only prototype. Completed. Freeze.… |
| `tools/p3_shuffle_permutation_test.py` | The original P3 shuffle permutation test (2026-02). Historical reference; empiri… |
| `scripts/special3_oos_permutation_review.py` | Completed special3 OOS permutation review task. Uses scipy.stats binomial (analy… |
| `scripts/p214b_3star_4star_straight_play_readonly_diagnostic.py` | Completed read-only diagnostic task (P214B). Freeze.… |

## Archived / Deferred

| File | Priority |
|------|----------|
| `tools/rgf_walkforward_validator.py` | P2 |
| `tools/stability_coverage_study.py` | P2 |
| `tools/exhaustive_nbet_benchmark.py` | P2 |
| `lottery_api/tools/backtest_2025_*.py (4 files)` | P2 |

## Recommended Next Migration: P252H

**Type C — additive comment/import blocks only, no logic rewrite**

| Priority | Target | Action |
|----------|--------|--------|
| P0 | `lottery_api/engine/rolling_strategy_monitor.py` | Import RSM_WINDOWS from rolling_window SSOT |
| P0 | `analysis/p219_external_method_diagnostic_sweep.py` | Add SSOT import header comment block |
| P1 | `scripts/p214c, p211r, p227c` | Add governance comment referencing SSOT |

Authorization phrase required: `Authorize P252H SSOT adoption migration`

## Non-Goals

- P252G does **not** migrate any script
- P252G does **not** modify completed task artifacts
- P252G does **not** claim any consolidation improves P(win)
- P252G does **not** recommend betting

## No-Overclaim Statement

> SSOT consolidation improves code maintainability and false-positive control infrastructure. **It does not imply any deployable prediction edge.** All research arcs remain NULL/REJECTED/UNDERPOWERED.

## Compliance

- **No DB write performed in P252G.**
- **No registry mutation.**
- **No strategy promotion.**
- **No betting advice** is given or implied.

---
*Generated by P252G — P0 External Method SSOT Adoption Audit*