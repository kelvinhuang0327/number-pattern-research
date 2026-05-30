# P156: DB_ONLY_MISSING_LIFECYCLE Governance Audit

**Classification**: `P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT_READY`
**Task ID**: P156
**Generated**: 2026-05-30

---

## 1. Executive Summary

P156 audits all 22 `DB_ONLY_MISSING_LIFECYCLE` strategies from the P154 risk register. Based on DB evidence (source, controlled_apply_id, truth_level, row count, bet_index), each strategy receives a lifecycle recommendation.

**Results**:
- **ONLINE recommended**: 10 strategies (actively maintained)
- **RETIRED recommended**: 12 strategies (historical backfill only)
- **Human review required**: 4 strategies

**No changes made.** The registry is source-controlled Python. P156B required for actual updates.

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `.../zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | PASS | ✅ PASS |

---

## 3. P154 RC Recap

P154 formally closed the replay product RC with 4 non-blocking risks. R001 was:
> "22 DB_ONLY_MISSING_LIFECYCLE strategies need formal lifecycle governance"

P156 addresses R001 via read-only audit.

---

## 4. DB_ONLY Lifecycle Inventory

| Item | Value |
|------|-------|
| Expected count (from P154) | 22 |
| Actual count (from registry) | 22 |
| Registry source | `lottery_api/models/replay_strategy_registry.py` |
| Discrepancy | None |

---

## 5. Lifecycle Recommendation Matrix

### Group A — ONLINE (HIGH confidence, 7 strategies)
Active multi-bet strategies with P94 TIERB + P126x / P13x controlled_apply:

| Strategy ID | Lottery | Rows | Max Bet | Source Evidence |
|------------|---------|------|---------|----------------|
| biglotto_echo_aware_3bet | BIG_LOTTO | 4500 | 3 | P94+P126C |
| biglotto_ts3_markov_4bet_w30 | BIG_LOTTO | 6000 | 4 | P94+P126E |
| daily539_f4cold_3bet | DAILY_539 | 4500 | 3 | P94+P126D |
| daily539_f4cold_5bet | DAILY_539 | 7500 | 5 | P94+P126F |
| power_fourier_rhythm_2bet | POWER_LOTTO | 3000 | 2 | P94+P126B |
| midfreq_fourier_mk_3bet | POWER_LOTTO | 4500 | 3 | P48+P132 |
| pp3_freqort_4bet | POWER_LOTTO | 6000 | 4 | P48+P133 |

### Group B — ONLINE (MEDIUM confidence, 3 strategies, human review required)
Recent Wave5/6 production apply, no follow-up expansion:

| Strategy ID | Lottery | Rows | Source | Note |
|------------|---------|------|--------|------|
| cold_complement_2bet | POWER_LOTTO | 1500 | P66 Wave6 | Review: still active? |
| zonal_entropy_2bet | POWER_LOTTO | 1500 | P66 Wave6 | Review: still active? |
| fourier30_markov30_2bet | POWER_LOTTO | 1501 | P59+P78 | Draw extension present; review |

### Group C — RETIRED (MEDIUM confidence, 6 strategies)
DAILY_539 Wave2 backfill only (P37), no subsequent controlled_apply:

| Strategy ID | Rows | Source |
|------------|------|--------|
| 539_3bet_orthogonal | 1500 | P37 Wave2 |
| acb_single_539 | 1500 | P37 Wave2 |
| markov_1bet_539 | 1500 | P37 Wave2 |
| p0b_539_3bet_f_cold_fmid | 1500 | P37 Wave2 |
| p0c_539_3bet_f_cold_x2 | 1500 | P37 Wave2 |
| zone_gap_3bet_539 | 1500 | P37 Wave2 |

*Pattern*: All 1500-row Wave2 backfill (like existing RETIRED acb_1bet, midfreq_acb_2bet etc.), no subsequent promotion.

### Group D — RETIRED (HIGH confidence, 6 strategies, 1 needs human review)
BIG_LOTTO Wave3 backfill only (P43), BIG_LOTTO 49C6 signal space exhausted (L91):

| Strategy ID | Rows | Note |
|------------|------|------|
| bet2_fourier_expansion_biglotto | 1500 | L91 exhausted |
| cold_complement_biglotto | 1500 | L91 exhausted |
| coldpool15_biglotto | 1500 | L91 exhausted |
| fourier30_markov30_biglotto | 1500 | L91 exhausted + P118 quarantine candidate ⚠️ |
| markov_2bet_biglotto | 1500 | L91 exhausted |
| markov_single_biglotto | 1500 | L91 exhausted |

⚠️ `fourier30_markov30_biglotto` is the P118 quarantine candidate — human review recommended before marking RETIRED.

---

## 6. Recommended Decision Groups

| Group | Count | Lifecycle | Confidence |
|-------|-------|-----------|------------|
| A — Active multi-bet | 7 | ONLINE | HIGH |
| B — Wave5/6 recent | 3 | ONLINE | MEDIUM |
| C — 539 Wave2 backfill | 6 | RETIRED | MEDIUM |
| D — BIG Wave3 backfill | 6 | RETIRED | HIGH |
| **Total** | **22** | | |
| Human review required | 4 | — | — |

---

## 7. Registry Storage Assessment

| Item | Value |
|------|-------|
| Registry type | Source-controlled Python (`replay_strategy_registry.py`) |
| DB mutation required | ❌ No |
| Code change required | ✅ Yes (Python file edit) |
| Safe to update in P156 | ❌ No — audit-only |

---

## 8. Authorization Gate Requirement

P156B is required before any lifecycle updates. Each strategy needs explicit authorization:

```
YES update lifecycle for {strategy_id} to {recommended_lifecycle} per P156 recommendation
```

**P156B scope**: Update `lottery_api/models/replay_strategy_registry.py` for each approved strategy.

**Human review required before P156B**: cold_complement_2bet, zonal_entropy_2bet, fourier30_markov30_2bet, fourier30_markov30_biglotto.

---

## 9. Explicit Non-Actions

All confirmed false/0: DB write, lifecycle update, replay rows, controlled_apply, champion/registry promotion, live API, scheduler.

The registry file `lottery_api/models/replay_strategy_registry.py` was NOT staged or modified.

---

## 10. Dirty File Hygiene Note

- `backups/` untracked — not staged, not deleted
- Registry file not staged
- Only P156 whitelist files staged

---

## 11. Remaining Risks

1. 4 strategies need human review (Groups B + fourier30_markov30_biglotto)
2. P156B requires per-strategy authorization phrases before update
3. After P156B updates, all-strategy catalog UI will auto-reflect new lifecycle (no UI change needed)

---

## 12. Recommended Next Task

`P156B_DB_ONLY_LIFECYCLE_DECISION_GATE`

Per-strategy authorization gate. User confirms each strategy's recommended lifecycle with the exact phrase:
```
YES update lifecycle for {strategy_id} to {recommended_lifecycle} per P156 recommendation
```

---

## 13. Final Classification

```
P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT_READY
```
