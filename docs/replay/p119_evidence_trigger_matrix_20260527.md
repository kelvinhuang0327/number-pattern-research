# P119: Evidence Consolidation and Trigger Matrix

**Date**: 2026-05-27  
**Task ID**: P119_EVIDENCE_TRIGGER_MATRIX  
**Final Classification**: `P119_EVIDENCE_TRIGGER_MATRIX_READY`

---

## PROJECT_CONTEXT_LOCK

Project = LotteryNew  
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew  
Canonical Branch = main

This document applies ONLY to LotteryNew. Any artifact from another project (Betting-pool, Stock-Prediction-System, Stock, Novel, SCB, etc.) must be treated as context contamination and rejected.

---

## Why P119 Exists

After P117 confirmed WAIT_MORE_DRAWS status for POWER_LOTTO OOS monitoring, the governance chain P105–P117 has multiple blocked tasks, each requiring different triggers. P119 consolidates all evidence into a single authoritative index so that:

1. Future agents can immediately see what is completed, what is blocked, and under what exact condition each blocked task becomes eligible.
2. No ambiguity about which authorization phrases are required.
3. The trigger matrix replaces guesswork with deterministic conditions.

**This task is documentation / governance consolidation only. No blocked task was executed.**

---

## Current Post-P117 Baseline

| Metric | Value |
|--------|-------|
| Merge commit (P117) | `9765485` |
| replay_rows | 54462 |
| 3_STAR count / max draw | 4179 / 115000106 |
| 4_STAR count / max draw | 2922 / 115000103 |
| POWER_LOTTO count / max draw | 1913 / 115000041 |
| New POWER_LOTTO draws after P116 baseline | 0 |
| Special3 prospective draws (estimated) | 63 / 100 |
| Drift guard | PASS |
| Branch governance guard | PASS |

---

## Evidence Index: P105 → P117

| Phase | Classification | Key Conclusion | PR | Merge Commit |
|-------|---------------|---------------|-----|-------------|
| P105 | `P105_DB_STATE_ACCEPTED_FOR_SPECIAL3_EVALUATION_ONLY` | DB state accepted for Special3 evaluation only. 4_STAR source unknown. source_unknown caveat propagated. | — | `ceea6e9` |
| P106 | `P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL` | 63 Special3 prospective draws found after P99 cutoff. 37 more needed for 100-draw gate. | — | `bfa2653` |
| P107A | `P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS` | P108 blocked at WAIT_MORE_DRAWS gate (100 prospective draws required). | — | `782e261` |
| P107B | `P107B_STALE_BASELINE_GUARD_REPAIR_READY` | Stale baseline guards repaired. replay_rows=54462 established as accepted baseline. | — | `e79b5e9` |
| P112 | `P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY` | Cross-lottery prediction helpfulness audit. BIG_LOTTO and POWER_LOTTO strategies assessed. | #238 | `4db894a` |
| P113 | `P113_P112_ACTION_DECISION_MATRIX_READY` | Action decision matrix from P112 audit. Governance decisions documented per strategy. | #239 | `be3716e` |
| P114 | `P114_TEMPORAL_STABILITY_AUDIT_READY` | Temporal stability audit. Strategy drift checked across draw windows. | #240 | `3ffae64` |
| P116 | `P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY` | OOS monitoring design for POWER_LOTTO candidates. Thresholds: 30 draws (midfreq), 40 draws (pp3). | #241 | `f4b7ae4` |
| P115 | `P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY` | Quarantine governance design for `fourier30_markov30_biglotto`. Actual quarantine NOT applied. | #242 | `c4ce85e` |
| P117 | `P117_POWERLOTTO_OOS_WAIT_MORE_DRAWS` | 0 new POWER_LOTTO draws after baseline 115000041. Both candidates below threshold. No OOS conclusions. | #243 | `9765485` |

> Note: P108–P111 artifacts not found in `outputs/replay/` under the current naming convention. These phases may have been executed under a different artifact schema or were superseded. Evidence index covers available artifacts only.

---

## Trigger Matrix

| Trigger | Type | Current Value | Threshold | Status | Remaining |
|---------|------|:-------------:|:---------:|--------|:---------:|
| P108 Special3 100-draw re-evaluation | draw count | 63 prospective | 100 | **BLOCKED** | 37 draws |
| P117 POWER_LOTTO OOS partial checkpoint (midfreq) | draw count | 0 new PL draws | 30 | **BLOCKED** | 30 draws |
| P117 POWER_LOTTO OOS full checkpoint (both candidates) | draw count | 0 new PL draws | 40 | **BLOCKED** | 40 draws |
| P118 BIG_LOTTO actual quarantine | explicit auth | phrase not provided | exact phrase | **BLOCKED** | authorization phrase |
| 4_STAR provenance + backtest | source decision | source unknown | source confirmed | **BLOCKED** | provenance artifact |

### Trigger Detail

#### P108: Special3 100-draw re-evaluation

- **Condition**: Special3 prospective draws after P99 cutoff ≥ 100
- **Current**: 63 / 100 (37 more needed)
- **Authorization after trigger**: Separate branch + task required; no automatic promotion
- **Draw source**: `3_STAR` draws in DB after max draw 115000106

#### P117 re-trigger: POWER_LOTTO OOS checkpoint

- **Partial condition**: New POWER_LOTTO draws after `115000041` ≥ 30 → `midfreq_fourier_mk_3bet` checkpoint eligible
- **Full condition**: New POWER_LOTTO draws after `115000041` ≥ 40 → both candidates checkpoint eligible
- **Current**: 0 new draws
- **Authorization after trigger**: Promotion is NOT authorized even after checkpoint

#### P118: BIG_LOTTO actual quarantine

- **Trigger type**: Explicit authorization only
- **Required exact phrase**:
  ```
  YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence
  ```
- **After phrase**: Plan P118 as a **separate task** on a new branch. P118 must not delete DB rows unless explicitly authorized separately.
- **Without phrase**: BLOCKED indefinitely

#### 4_STAR provenance and backtest

- **Condition**: Source / provenance of 4_STAR rows confirmed in a separate decision artifact
- **Current**: source_unknown (2922 rows, max 115000103)
- **After source confirmation**: Backtest authorization requires an additional explicit approval

---

## Blocked Task Register

| Task | Status | Blocked Reason | Unblock Condition |
|------|--------|---------------|-------------------|
| P108 Special3 re-evaluation | BLOCKED | 37 more Special3 prospective draws needed | ≥ 100 total prospective draws |
| P117 POWER_LOTTO OOS retrigger | BLOCKED | 0 new PL draws (need ≥ 30 for partial, ≥ 40 for full) | New PL draws after `115000041` |
| P118 BIG_LOTTO actual quarantine | BLOCKED | Exact authorization phrase not provided | Exact phrase: `YES quarantine strategy fourier30_markov30_biglotto...` |
| 4_STAR provenance & backtest | BLOCKED | 4_STAR source unknown | Source provenance artifact + explicit backtest authorization |

---

## Next-Action Selector

**Current recommended action**: `WAIT_FOR_DATA_OR_AUTHORIZATION`

All trigger conditions are currently unmet. Decision rules (evaluated in order):

```
1. if Special3 prospective draws >= 100         → P108_SPECIAL3_100DRAW_REEVALUATION
2. elif new POWER_LOTTO draws >= 30             → P117_POWERLOTTO_OOS_RETRIGGER (partial)
3. elif new POWER_LOTTO draws >= 40             → P117_POWERLOTTO_OOS_RETRIGGER (full)
4. elif exact quarantine phrase present         → P118_BIGLOTTO_ACTUAL_QUARANTINE
5. else                                         → WAIT_FOR_DATA_OR_AUTHORIZATION
```

Nearest triggers:
- **37 more Special3 draws** → P108 becomes eligible
- **30 more POWER_LOTTO draws** → P117 partial checkpoint becomes eligible

---

## Explicit Authorization Phrases

| Purpose | Required Exact Phrase | Task |
|---------|----------------------|------|
| BIG_LOTTO actual quarantine of `fourier30_markov30_biglotto` | `YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence` | P118 |

No other explicit phrases are currently outstanding. Draw-count triggers activate automatically when thresholds are crossed.

---

## Current Holds

### P108: BLOCKED — 37 more 3_STAR draws needed

Special3 (3_STAR) prospective draws after P99 cutoff = 63. Need 100 for re-evaluation. Estimated 37 more draws required. P108 must be a separate branch once eligible.

### P117: BLOCKED — 30 more POWER_LOTTO draws needed (partial)

New POWER_LOTTO draws after baseline `115000041` = 0. Need 30 for `midfreq_fourier_mk_3bet` partial checkpoint, 40 for both candidates. Re-run `scripts/p117_powerlotto_oos_monitoring_checkpoint.py` when draws advance.

### P118: BLOCKED — Awaiting explicit authorization phrase

Exact phrase required (see table above). Without it, no quarantine planning may begin. Even after phrase: P118 must be a new branch; DB deletion requires additional authorization.

### 4_STAR: BLOCKED — Source unknown

2922 rows, max `115000103`. Source has not been confirmed. Backtest not authorized until source provenance is established in a separate decision artifact.

---

## Explicit Statements

**This task does NOT run any blocked task.** P108, P117 OOS execution, P118 quarantine, and 4_STAR backtest were not executed.

**This task does NOT authorize any strategy promotion.** No `midfreq_fourier_mk_3bet`, `pp3_freqort_4bet`, or any other strategy was promoted.

**This task does NOT mutate lifecycle, champion, or registry metadata.** All strategy states remain as-is from P117.

**This task does NOT write to the DB.** replay_rows = 54462 unchanged.

---

## Limitations

1. P108–P111 artifacts not found under current naming convention; evidence index covers P105–P107B and P112–P117 only.
2. P116 artifact lacked explicit baseline draw field; P117 used fallback `115000041`.
3. Special3 prospective draw count (63) is from P106/P107A; actual current count may differ if new 3_STAR draws were ingested — recalculate at next trigger evaluation.
4. This is documentation consolidation only; no live analysis was performed.

---

## Forbidden-Staging Scan

Staged files for this commit (whitelist only):

```
outputs/replay/p119_evidence_trigger_matrix_20260527.json
docs/replay/p119_evidence_trigger_matrix_20260527.md
tests/test_p119_evidence_trigger_matrix.py
scripts/p119_evidence_trigger_matrix.py
```

No DB files (`.db`, `.wal`, `.shm`), history files, runtime files, or backup files are staged.

---

## Test Summary

Tests file: `tests/test_p119_evidence_trigger_matrix.py`  
Minimum 45 tests covering: JSON/MD artifact existence, classification validity, invariant guards, evidence index completeness, trigger matrix entries, blocked task register, next-action selector, explicit holds, forbidden-staging compliance.

---

## Guard Summary

| Guard | Status |
|-------|--------|
| Drift guard (`--strict`) | PASS |
| Branch governance guard (pre-flight on `main`) | PASS |
| Branch governance guard (post-stage on `p119-...`) | PASS |

---

## Final Classification

```
P119_EVIDENCE_TRIGGER_MATRIX_READY
```

Evidence index complete for 10 phases (P105–P117). Trigger matrix encodes 4 distinct unblock conditions. All 4 triggers currently BLOCKED. Next recommended action: `WAIT_FOR_DATA_OR_AUTHORIZATION`.

---

## Next Recommended Task

**Monitor draw counts and re-evaluate triggers.**

- When 3_STAR draws advance past `115000106` by 37+ → plan **P108** Special3 100-draw re-evaluation
- When POWER_LOTTO draws advance past `115000041` by 30+ → re-run **P117** checkpoint script
- When exact quarantine phrase provided → plan **P118** BIG_LOTTO actual quarantine
- When 4_STAR source is confirmed → plan **4_STAR provenance decision** task
