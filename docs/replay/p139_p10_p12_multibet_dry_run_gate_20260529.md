# P139: P10/P12 Multi-Bet Dry-Run Gate After Legacy Remark

**Generated:** 2026-05-29T04:02:42.970688+00:00
**Classification:** `P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY`
**Worktree:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`
**Branch:** `claude/zen-gates-ff6802`

---

## 1. Executive Summary

P139 is a **read-only dry-run gate** re-evaluating `power_precision_3bet` (P10) and
`power_orthogonal_5bet` (P12) for multi-bet controlled_apply readiness.

Following P138B's authorized LEGACY_UNVERIFIED re-mark, both strategies now have:
- 1500 clean production baseline rows + 50 governed LEGACY_UNVERIFIED rows (1550 total)
- 0 NULL-provenance legacy selector rows
- Adapter functions available and both blockers cleared (RSR6 + legacy governance)

**P139 conclusion:** Both strategies are **dry-run ready**. Apply uses 1500 production
baseline rows (LEGACY_UNVERIFIED excluded). Authorization required before P140 (P10) and P141 (P12).

**No DB writes. No controlled_apply. No row insertions or deletions.**

---

## 2. Canonical Repo / Branch Confirmation

| Field | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | ✅ |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | ✅ |
| DB rows | `85924` | `85924` | ✅ |

---

## 3. P138B Recap

**P138B classification:** `P138B_P10_P12_LEGACY_ROWS_REMARKED`
**P138B actual rows remarked:** 100
**P138B governance resolved:** P10=True, P12=True

P138B updated 100 NULL-provenance rows to `truth_level='LEGACY_UNVERIFIED'`, `source='P138B_LEGACY_REMARK'`,
and deterministic `provenance_hash`. DB total unchanged at 85924.

---

## 4. Why P10/P12 Are Now Eligible for Dry-Run Gate Re-evaluation

Two blockers were preventing P10/P12 from entering the dry-run gate:

| Blocker | Status |
|---------|--------|
| RSR6: orphan bet_index=2 rows | ✅ RESOLVED — RSR6 deleted 20 orphan rows per strategy |
| Legacy governance: 50 NULL-provenance rows per strategy | ✅ RESOLVED — P138B re-marked as LEGACY_UNVERIFIED |

Both blockers are now resolved. P10/P12 can proceed to dry-run planning.

---

## 5. Current P10/P12 Row Distribution

| Strategy | bet-1 rows | bet-2+ rows | apply_ready |
|----------|-----------|-------------|-------------|
| `power_precision_3bet` | 1550 | 0 | Pending P140 |
| `power_orthogonal_5bet` | 1550 | 0 | Pending P141 |

---

## 6. LEGACY_UNVERIFIED Audit

| Strategy | LEGACY_UNVERIFIED rows | Production baseline rows | NULL-prov selector |
|----------|----------------------|--------------------------|-------------------|
| `power_precision_3bet` | 50 | 1500 | — |
| `power_orthogonal_5bet` | 50 | 1500 | — |
| **Total** | **100** | — | **0 (✅ zero)** |

---

## 7. Adapter Contract Status

| Strategy | Adapter Function | Module | Status | Blockers Cleared |
|----------|-----------------|--------|--------|-----------------|
| `power_precision_3bet` | `get_all_bets_power_precision` | `p128_wave2_phase2_adapters.py` | ✅ AVAILABLE | RSR6 + P138B |
| `power_orthogonal_5bet` | `get_all_bets_power_orthogonal` | `p128_wave2_phase2_adapters.py` | ✅ AVAILABLE | RSR6 + P138B |

**Gap to resolve before apply:** draw_context key used by adapters is `'history'` (list of draw dicts),
not `'historical_draws'` as spec'd in P127. Must reconcile before P140/P141.

---

## 8. Legacy Row Handling Decision

**Decision: EXCLUDE LEGACY_UNVERIFIED rows from apply base**

Apply base: **1500 production baseline rows** per strategy
(`truth_level = 'POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'`)

**Rationale:** The 50 LEGACY_UNVERIFIED rows per strategy (draws 99000055–99000104) were inserted from early replay runs (replay_run_id 2 and 6) before the P20 production backfill pipeline was established. Although P138B assigned synthetic provenance_hash, these rows represent pre-production legacy draws. For the first multi-bet controlled_apply, only the 1500 production baseline rows (truth_level=POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED) should be used as the base. This keeps the apply clean, avoids mixing legacy and production data in multi-bet rows, and simplifies the apply selector. If legacy multi-bet coverage is needed later, it can be addressed as a separate authorized task.

**Apply selector:**
```sql
WHERE strategy_id=? AND bet_index=1 AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED' AND provenance_hash IS NOT NULL AND controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520'
```

**Excluded rows:** 50 per strategy (truth_level=LEGACY_UNVERIFIED)

---

## 9. Per-Strategy Dry-Run Plan

### power_precision_3bet (P10)

| Field | Value |
|-------|-------|
| Lottery type | POWER_LOTTO |
| Target bet count | 3 |
| Current bet-1 rows | 1550 |
| Apply base rows | 1500 (production baseline) |
| Missing bet indices | 2, 3 |
| Estimated insert rows | **3,000** (1500 × 2) |
| Adapter | `get_all_bets_power_precision` ✅ |
| Dry-run ready | ✅ YES |
| Apply authorization | REQUIRED — not authorized in P139 |

**Remaining gaps:**
- draw_context key 'history' vs P127 spec 'historical_draws' — must reconcile before apply
- Adapter docstring still shows stale RSR-6 warning — cosmetic only, not a blocker
- Full DB backup required before controlled_apply

---

### power_orthogonal_5bet (P12)

| Field | Value |
|-------|-------|
| Lottery type | POWER_LOTTO |
| Target bet count | 5 |
| Current bet-1 rows | 1550 |
| Apply base rows | 1500 (production baseline) |
| Missing bet indices | 2, 3, 4, 5 |
| Estimated insert rows | **6,000** (1500 × 4) |
| Adapter | `get_all_bets_power_orthogonal` ✅ |
| Dry-run ready | ✅ YES |
| Apply authorization | REQUIRED — not authorized in P139 |

**Remaining gaps:**
- draw_context key 'history' vs P127 spec 'historical_draws' — must reconcile before apply
- Adapter docstring still shows stale RSR-6 warning — cosmetic only, not a blocker
- Full DB backup required before controlled_apply
- 4 missing bet indices — larger apply than P10; higher insert volume (6000 rows)

---

## 10. Estimated Insert Rows Summary

| Strategy | Apply base | Missing indices | Estimated insert rows | DB total after |
|----------|-----------|----------------|-----------------------|----------------|
| `power_precision_3bet` | 1500 | 2,3 | **3,000** | 88,924 |
| `power_orthogonal_5bet` | 1500 | 2,3,4,5 | **6,000** | 91,924 |
| **Combined (if both)** | — | — | **9,000** | **94,924** |

---

## 11. Recommended Apply Order

**P10_FIRST**

power_precision_3bet (P10) should be applied first because: (1) lower estimated row count (3000 vs 6000), reducing blast radius on first apply; (2) only 2 missing bet indices vs 4 for P12; (3) P10 has implementation_priority=10 (lower = higher priority per P127); (4) P10 algorithm (precision_scoring) is simpler than P12 (orthogonal_diversification). Apply P12 after P10 is verified. Each requires separate authorization.

| Step | Strategy | Task | Est. rows | Authorization |
|------|----------|------|-----------|---------------|
| 1 | `power_precision_3bet` | P140 | 3,000 | Required |
| 2 | `power_orthogonal_5bet` | P141 | 6,000 | Required |

---

## 12. Authorization Phrase Templates

> These phrases are templates for future use. P139 does NOT authorize either apply.

**P10 (power_precision_3bet) apply authorization:**
```
P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529
```

**P12 (power_orthogonal_5bet) apply authorization:**
```
P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529
```

These phrases must be provided verbatim before executing P140 and P141 respectively. Paraphrasing or partial repetition does not constitute authorization. P139 does NOT authorize either apply — these templates are for future use.

---

## 13. Explicit Non-Actions

- ❌ No DB writes executed
- ❌ No controlled_apply executed
- ❌ No replay rows inserted or deleted
- ❌ No P131–P134 / P126B–P126F rows touched
- ❌ No Wave 2 safe candidate rows touched
- ❌ No 4_STAR / P108 / P117 / P118 execution
- ❌ No scheduler / cron / launchd install
- ❌ No strategy lifecycle / champion / registry mutation
- ✅ DB rows: 85924 (unchanged)
- ✅ dry_run_gate_only = true

---

## 14. Remaining Risks

- draw_context key mismatch: adapter uses 'history' but P127 spec says 'historical_draws' — must reconcile before P140/P141.
- Adapter docstrings still show stale RSR-6 warnings — cosmetic only, not a blocker.
- LEGACY_UNVERIFIED rows (50 per strategy) are excluded from apply base — if legacy multi-bet coverage is needed, a separate authorized task is required.
- P10/P12 are watchlist quality (p125_rank_score 31/35) — apply provides replay coverage but does not imply production deployment.
- After P140+P141, drift guard baseline will shift to 94,924 — drift guard may need a comment update.
- Full DB backup required before each controlled_apply (P140, P141).

---

## 15. Recommended Next Task

**P140: power_precision_3bet multi-bet controlled_apply (bet-2 + bet-3, 3000 rows, requires authorization phrase P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529).**

---

## 16. Final Classification

```
P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY
```
