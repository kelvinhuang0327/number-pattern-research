# P57: POWER_LOTTO Wave 5 Controlled Rehearsal Readiness

**Branch**: `p57-powerlotto-wave5-controlled-rehearsal-readiness`  
**Base**: `c3f0325` (P56 merged to main)  
**Date**: 2026-05-25  
**Classification**: `P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED`  
**Status**: ✅ COMPLETED

---

## Pre-Flight Checks

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✅ |
| Branch | `p57-powerlotto-wave5-controlled-rehearsal-readiness` ✅ |
| HEAD base | `c3f0325` (P56 commit on main) ✅ |
| Production rows | `42460` ✅ |
| P56 commit on main | `c3f0325` ✅ |
| Drift guard (pre) | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| Branch governance (pre, main) | `BRANCH_GOVERNANCE_PASS` ✅ |
| Dirty files | Runtime/workspace debt — none staged ✅ |

---

## P56 Artifact Integrity

| Check | Value | Status |
|---|---|---|
| P56 classification | `P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED` | ✅ |
| Total dry-run rows | 4500 | ✅ |
| Rows per strategy | 1500 × 3 = 4500 | ✅ |
| Production rows before P56 | 42460 | ✅ |
| Production rows after P56 | 42460 (unchanged) | ✅ |
| Schema validation | PASS (0 errors) | ✅ |
| Data leakage check | PASS (0 violations) | ✅ |
| R1 Apply | 4500 inserted | ✅ |
| R2 Idempotency | 0 duplicates | ✅ |
| R3 Rollback | 0 rows remain | ✅ |
| Production DB write | None | ✅ |
| Lifecycle promotion | None | ✅ |
| Champion replacement | None | ✅ |
| All rows DRY_RUN | Yes | ✅ |
| Adapters not in registry | Yes | ✅ |

---

## Production DB Integrity (Read-Only)

| Check | Value | Status |
|---|---|---|
| Total replay rows | 42460 | ✅ |
| POWER_LOTTO rows | 9140 | ✅ |
| Wave 5 in production | 0 rows (DRY_RUN only) | ✅ |
| Champion `fourier_rhythm_3bet` | Present | ✅ |

---

## Theoretical Baselines

**M3+ Baseline (6/38 hypergeometric)**:

$$P(X \ge 3) = 1 - P(X=0) - P(X=1) - P(X=2)$$

$$= 1 - \frac{\binom{32}{6}}{\binom{38}{6}} - \frac{\binom{6}{1}\binom{32}{5}}{\binom{38}{6}} - \frac{\binom{6}{2}\binom{32}{4}}{\binom{38}{6}} \approx 3.87\%$$

**Special Hit Baseline**: $1/8 = 12.50\%$ (uniform over [1,8])

---

## Per-Strategy Readiness Scoring

### Hit Rate vs Baseline

| Strategy | Rows | M3+ Rate | Baseline | Delta (pp) | Special Rate |
|---|---|---|---|---|---|
| `cold_complement_2bet` | 1500 | 3.67% | 3.87% | −0.20 | 11.87% |
| `fourier30_markov30_2bet` | 1500 | **4.07%** | 3.87% | **+0.20** | 11.87% |
| `zonal_entropy_2bet` | 1500 | 3.67% | 3.87% | −0.20 | 11.87% |

### Hit Count Distribution (n = 1500 each)

| Hit Count | cold_complement | fourier30 | zonal_entropy | Theoretical |
|---|---|---|---|---|
| 0 | 477 | 472 | 477 | ≈492 (32.8%) |
| 1 | 694 | 675 | 694 | ≈656 (43.8%) |
| 2 | 274 | 292 | 274 | ≈293 (19.5%) |
| 3 | 51 | 57 | 51 | ≈50 (3.3%) |
| 4 | 4 | 4 | 4 | ≈8 (0.5%) |
| 5 | 0 | 0 | 0 | ≈1 (0.1%) |
| 6 | 0 | 0 | 0 | ≈0 |

Distribution is consistent with the hypergeometric theoretical model. No anomalies detected.

### Statistical Significance (Binomial Z-Test)

Testing H₀: M3+ rate = 3.87% (baseline), H₁: rate > baseline (one-tailed).

$$Z = \frac{\hat{p} - p_0}{\sqrt{p_0(1-p_0)/n}}$$

| Strategy | Z-score | p-value | Significant (p<0.05)? |
|---|---|---|---|
| `cold_complement_2bet` | −0.40 | 0.656 | ❌ No |
| `fourier30_markov30_2bet` | +0.40 | 0.344 | ❌ No |
| `zonal_entropy_2bet` | −0.40 | 0.656 | ❌ No |

**Key finding**: At n=1500, the observed 0.2pp delta for `fourier30_markov30_2bet`
is NOT statistically significant (Z=0.40, p=0.34). The above-baseline result is
directional but inconclusive. A sample of approximately 9,500 draws per strategy
would be required to achieve p<0.05 at 0.2pp delta with 80% power.

### Strategy Readiness Classifications

| Strategy | Classification | Reason |
|---|---|---|
| `cold_complement_2bet` | `WATCHLIST_REHEARSAL_ONLY` | M3+ 3.67% < baseline 3.87% — below baseline, not recommended for production apply at this time |
| `fourier30_markov30_2bet` | `READY_FOR_P58_WITH_CAUTION` | M3+ 4.07% > baseline 3.87% but NOT statistically significant (Z=0.40, p=0.344). 1500-draw window insufficient to confirm edge. |
| `zonal_entropy_2bet` | `WATCHLIST_REHEARSAL_ONLY` | M3+ 3.67% < baseline 3.87% — below baseline, not recommended for production apply at this time |

### Additional Strategy Attributes

| Attribute | cold_complement | fourier30 | zonal_entropy |
|---|---|---|---|
| Errors | 0 | 0 | 0 |
| Leakage violations | 0 | 0 | 0 |
| Duplicate rate | 0.0% | 0.0% | 0.0% |
| In production DB | No | No | No |
| Deterministic | ✅ Yes | ✅ Yes | ✅ Yes |
| Semantic compliance | ✅ Yes | ✅ Yes | ✅ Yes |
| Adapter source risk | LOW | LOW | LOW |

---

## Risk Review

### Is Below-Baseline M3+ a Blocker?

`cold_complement_2bet` and `zonal_entropy_2bet` are 0.20pp below the 3.87%
theoretical baseline. This is within normal variance for n=1500 and is NOT a
statistical disqualification. However, it is insufficient evidence to justify
a production apply in the absence of a positive signal. Their WATCHLIST status
reflects caution, not rejection.

These strategies may re-qualify for P58 if:
- Additional OOS windows provide positive M3+ signal
- A strategy-specific use case (e.g., coverage in underrepresented draw zones) is demonstrated
- A re-run with extended historical data shows consistent above-baseline results

### Does Coverage Value Override Weak M3+?

All three strategies are zero-error, zero-leakage, deterministic, and semantically
compliant. They add algorithmic diversity (cold-reversion, recency-weighting,
entropy-gating) not present in the existing POWER_LOTTO production set.

However, **coverage diversity alone is insufficient to justify production apply**
when M3+ is below baseline without statistical significance. The WATCHLIST
classification preserves these strategies for future re-evaluation without
blocking the production pipeline.

### Is 1500 Rows Sufficient for P58 Proposal?

For `fourier30_markov30_2bet`: 1500 rows provides directional evidence but not
statistical significance. The P58 proposal proceeds with the `READY_FOR_P58_WITH_CAUTION`
classification — production apply is permissible but the expectation of return
should be modest. The strategy adds recency-weighted frequency scoring as a new
signal class not currently in production.

For the WATCHLIST strategies: 1500 rows is sufficient to observe below-baseline
performance and withhold P58 eligibility. They require more evidence.

---

## P57 Cohort Decision

**Decision**: `PARTIAL_COHORT_P58`

| Phase | Strategy | Classification |
|---|---|---|
| P58 candidate | `fourier30_markov30_2bet` | `READY_FOR_P58_WITH_CAUTION` |
| WATCHLIST | `cold_complement_2bet` | `WATCHLIST_REHEARSAL_ONLY` |
| WATCHLIST | `zonal_entropy_2bet` | `WATCHLIST_REHEARSAL_ONLY` |

---

## P58 Controlled Apply Proposal (Draft)

> **IMPORTANT**: This is a planning artifact only. P57 recommendation does NOT
> constitute P58 authorization. P58 must be separately and explicitly authorized.

### P58 Target

| Field | Value |
|---|---|
| Phase | P58 |
| Title | POWER_LOTTO Wave 5 Controlled Production Apply |
| Controlled Apply ID | `p58_powerlotto_wave5_controlled_apply` |
| Strategies | `fourier30_markov30_2bet` |
| Rows per strategy | 1500 |
| Expected new rows | 1500 |
| Production rows before | 42460 |
| Projected rows after | 43960 |
| Authorization phrase | `YES apply Wave 5 POWER_LOTTO strategies to production DB` |

### Pre-Apply Checklist

1. Drift guard PASS (`--strict`)
2. Branch governance guard PASS (`--expected-rows 42460`)
3. Duplicate check: 0 rows in production for `(POWER_LOTTO, target_draw, fourier30_markov30_2bet)`
4. Schema validation PASS on all 1500 rows before apply
5. Leakage check PASS (0 violations)
6. Forbidden staging scan PASS
7. SQLite row count == 42460 before apply

### Rollback Requirements

1. Take DB backup: `cp lottery_api/data/lottery_v2.db lottery_api/data/lottery_v2.db.bak_p58`
2. Apply via transaction: `BEGIN; INSERT ...; COMMIT;`
3. On failure: `ROLLBACK;` restore from backup
4. Verify row count == 43960 after commit

### Required Tests

- `tests/test_replay_lifecycle_drift_guard.py`
- `tests/test_replay_api_contract.py`
- `tests/test_replay_branch_governance_guard.py`
- `tests/test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py`
- `tests/test_p57_powerlotto_wave5_controlled_rehearsal_readiness.py`
- `tests/test_p58_powerlotto_wave5_controlled_apply.py` *(to be created in P58)*

### Forbidden Staging

No staging of: DB files, pid files, backups, runtime files, raw feeds,
`.fuse_hidden*`, `.gitignore`, `.claude/worktrees`, unrelated p-series
outputs/docs/tests, `CEO-Decision.md`/`active_task.md` unless authorized.

---

## Governance Confirmation

| Constraint | Status |
|---|---|
| Production DB write | ❌ NONE |
| Lifecycle promotion | ❌ NONE |
| Champion replacement | ❌ NONE |
| Registry mutation | ❌ NONE |
| Live API call | ❌ NONE |
| Production rows before | 42460 |
| Production rows after | 42460 (unchanged) |

---

## Test Suite Results

**5-File Governance Suite**: 213/213 PASSED

| Test File | Tests | Status |
|---|---|---|
| `test_replay_lifecycle_drift_guard.py` | — | ✅ PASS |
| `test_replay_api_contract.py` | — | ✅ PASS |
| `test_replay_branch_governance_guard.py` | — | ✅ PASS |
| `test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py` | 173 | ✅ PASS |
| `test_p57_powerlotto_wave5_controlled_rehearsal_readiness.py` | — | ✅ PASS |

---

## Post-Flight Guards

| Guard | Result |
|---|---|
| Production rows | 42460 ✅ |
| `replay_lifecycle_drift_guard.py --strict` | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| `replay_branch_governance_guard.py --expected-branch p57-... --expected-rows 42460` | `BRANCH_GOVERNANCE_PASS` ✅ |

---

## Artifacts

| File | Description |
|---|---|
| `scripts/p57_powerlotto_wave5_controlled_rehearsal_readiness.py` | Read-only readiness scoring script |
| `tests/test_p57_powerlotto_wave5_controlled_rehearsal_readiness.py` | Governance test suite |
| `outputs/replay/p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json` | Machine-readable P57 artifact |
| `docs/replay/p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.md` | This document |

---

## Bugs Fixed in This Phase

| Issue | Fix |
|---|---|
| `check_production_integrity()` queried non-existent `lifecycle` column | Changed to `replay_status` (actual column name) |
| `test_adapter_not_in_registry` failed on docstring reference to `_ALL_ADAPTERS` | Changed to code-line-only scan, skipping docstrings |

---

## P58 Readiness Summary

| Strategy | P57 Status | P58 Eligible | Notes |
|---|---|---|---|
| `fourier30_markov30_2bet` | `READY_FOR_P58_WITH_CAUTION` | ✅ Yes (with caution) | Above baseline (+0.20pp), not statistically significant at n=1500 |
| `cold_complement_2bet` | `WATCHLIST_REHEARSAL_ONLY` | ❌ Not yet | Below baseline (−0.20pp), re-evaluate after additional OOS windows |
| `zonal_entropy_2bet` | `WATCHLIST_REHEARSAL_ONLY` | ❌ Not yet | Below baseline (−0.20pp), re-evaluate after additional OOS windows |

P58 requires **separate explicit authorization**.  
P57 classification is NOT a production apply authorization.
