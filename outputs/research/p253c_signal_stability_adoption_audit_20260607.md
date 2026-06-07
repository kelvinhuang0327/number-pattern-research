# P253C — Signal Stability SSOT Adoption Audit

**Date:** 2026-06-07 21:01:17  
**Task:** P253C  
**Classification:** SIGNAL_STABILITY_ADOPTION_AUDIT_COMPLETE  

## Executive Summary

P253C audits adoption of the P253B Signal Stability Diagnostics SSOT. The module `lottery_api/utils/stability_diagnostics.py` is verified pure, safe, and complete. Repository scan found **0 active duplicates requiring migration**: historical P-numbered scripts are frozen, and production files (DriftDetector, RSM, StabilityProfile) use intentionally distinct semantic domains. No M7 migration task is warranted.

## P253B SSOT Verification

| Check | Result |
|-------|--------|
| Module exists | True |
| Module pure/safe (no DB/registry/numpy imports) | True |
| Artifact exists | True |
| Artifact classification match | True |
| Tests exist | True |

## Stability Adoption Matrix

| Path | Classification | Recommended Action |
|------|---------------|-------------------|
| `lottery_api/utils/stability_diagnostics.py` | ALREADY_USING_SSOT | NONE — is the SSOT |
| `tests/test_p253b_signal_stability_diagnostics_ssot.py` | ALREADY_USING_SSOT | NONE — already SSOT |
| `scripts/p227c_star_box_play_dryrun_scan.py` | HISTORICAL_ARTIFACT_DO_NOT_EDIT | FREEZE — do not edit; historical record of P227C research |
| `scripts/p230b1_daily539_backward_oos_dryrun.py` | HISTORICAL_ARTIFACT_DO_NOT_EDIT | FREEZE — historical P230B1 research script |
| `scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py` | HISTORICAL_ARTIFACT_DO_NOT_EDIT | FREEZE — historical P231B research script |
| `analysis/p246k_canonical_big_lotto_nist_reaudit.py` | HISTORICAL_ARTIFACT_DO_NOT_EDIT | FREEZE — completed canonical NIST reaudit; L91 conclusion frozen |
| `lottery_api/engine/drift_detector.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — intentional: DriftDetector production labels differ from research stability_diagnostics labels |
| `lottery_api/engine/rolling_strategy_monitor.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — RSM STABLE refers to strategy momentum, not M7 signal stability |
| `lottery_api/models/stability_profile.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — strategy performance profile, not M7 signal stability |
| `lottery_api/diagnostics/statistical_diagnostics_schema.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — production schema for PSI diagnostics, different domain |
| `lottery_api/models/regime_monitor.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — regime recommendation label, semantically distinct |
| `tools/stability_coverage_study.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — exploratory research tool; no active production dependency |
| `tools/backtest_biglotto_comprehensive.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — backtest research tool; uses different stability concept (strategy decay, not signal) |
| `tools/backtest_structural_group.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — exploratory backtest; strategy decay label, not signal stability |
| `tools/backtest_markov_repeat_exception.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — exploratory backtest |
| `tools/rgf_walkforward_validator.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — exploratory validator; not in active production pipeline |
| `tools/verify_power_config.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — simple local label, not signal-stability semantics |

## Active Duplicate Logic

**Count: 0** — No active callers with duplicate stability logic requiring migration.

Historical P-numbered scripts (p227c, p230b1, p231b, p246k) contain inline block_stability/robustness/era_stability functions. These are **frozen historical artifacts** and must not be edited.

## Historical / Frozen Artifacts (DO NOT EDIT)

- `scripts/p227c_star_box_play_dryrun_scan.py`
- `scripts/p230b1_daily539_backward_oos_dryrun.py`
- `scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py`
- `analysis/p246k_canonical_big_lotto_nist_reaudit.py`

These scripts are P-numbered completed research artifacts. Their inline stability logic captures the exact computation used in the original research. Editing them would corrupt the historical record.

## Separate Production Domains (DO NOT MIGRATE)

- `lottery_api/engine/drift_detector.py` — Production PSI drift detector. Uses STABLE/WARNING/CRITICAL for distribution shift, not signal stability.
- `lottery_api/engine/rolling_strategy_monitor.py` — RSM production monitor. Uses STABLE for strategy momentum trend (z-score based), not signal stability.
- `lottery_api/models/stability_profile.py` — Strategy stability profile loader. Uses ROBUST/SHORT_MOMENTUM/LATE_BLOOMER/STABLE for cross-window strategy decay.
- `lottery_api/diagnostics/statistical_diagnostics_schema.py` — Statistical diagnostics schema. STABLE enum = PSI threshold status, not M7 signal stability.
- `lottery_api/models/regime_monitor.py` — Regime monitor uses STABLE as a recommendation label for regime-switching.

These production files use STABLE/WARNING/CRITICAL or ROBUST/SHORT_MOMENTUM labels for **different semantic domains** (PSI drift, strategy momentum, regime). stability_diagnostics.py intentionally uses STABLE/MIXED/UNSTABLE to avoid confusion.

## Deferred Exploratory Tools

- `tools/stability_coverage_study.py`
- `tools/backtest_biglotto_comprehensive.py`
- `tools/backtest_structural_group.py`
- `tools/backtest_markov_repeat_exception.py`
- `tools/rgf_walkforward_validator.py`
- `tools/verify_power_config.py`

Tools in `tools/` use local stability labels (ROBUST/MODERATE_DECAY/MIXED) for strategy-decay classification, not M7 signal stability. Deferred — no migration value.

## Recommended Next Task

**P253D — M1 Historical Draw Parser Inventory (Type B read-only)**  
Zero active duplicates means no M7 migration task is needed. New research scripts that compute signal stability should import `stability_diagnostics` going forward.  
Alternative: **HOLD** if no new stability-reporting research is imminent.

## Non-Goals

- Does **not** migrate any existing logic
- Does **not** modify strategy implementation, DB, registry, API, or frontend
- Does **not** edit historical research artifacts
- Does **not** claim a stable signal implies predictive edge

## Explicit No-Overclaim Statement

> Signal stability is an interpretability property. A STABLE result from > `classify_stability()` does **not** imply a deployable prediction edge. > GREEN randomness does not imply any exploitable signal. No betting advice.

## Compliance

- **No DB write.**  - **No registry mutation.**  - **No strategy promotion.**  - **No betting advice.**

---
*Generated by P253C — Signal Stability SSOT Adoption Audit*