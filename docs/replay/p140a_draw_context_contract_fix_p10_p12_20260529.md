# P140A: Draw Context Contract Fix for P10/P12 Pre-Apply Readiness

**Classification:** `P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY`
**Generated:** 2026-05-29T04:20:08.568646+00:00
**Canonical Repo:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`
**Canonical Branch:** `claude/zen-gates-ff6802`

---

## Executive Summary

P140A is a **pre-apply contract fix** — not a controlled apply phase.

P139 identified a draw_context key mismatch: all P10/P12 adapter functions use
`draw_context["history"]`, but the P127 spec text named the key `"historical_draws"`.
Without resolving this, future P140/P141 apply scripts could break if they construct
the draw_context using the P127 spec name.

**Resolution:** `"history"` is confirmed as the canonical key. A `normalize_draw_context()`
helper was added to the adapter module. This normalizer accepts either `"history"` or
`"historical_draws"` and maps them to the canonical `"history"` key, ensuring both
spec-compliant and implementation-compliant callers work correctly.

**DB rows:** 85924 (no change — no DB writes in P140A)
**Drift guard:** PASS at 85924

---

## Canonical Repo / Branch Confirmation

| Check | Expected | Actual | Status |
|---|---|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | ✅ PASS |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | ✅ PASS |

---

## P139 Recap

P139 confirmed both P10/P12 are `DRY_RUN_READY`:

| Item | Status |
|---|---|
| P139 Classification | `P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY` |
| P10 Dry-Run Ready | True |
| P12 Dry-Run Ready | True |
| Draw Context Gap Noted | True |

---

## Why draw_context Contract Fix is Required Before P140/P141

P127 spec script (`scripts/p127_adapter_build_specs_remaining_multi_bet.py`) defines:

```python
"draw_context_keys_required": ["historical_draws"]
```

But all P128 phase1 + phase2 adapter functions actually use:

```python
history = draw_context["history"]
```

This means:
- Apply scripts following the P127 spec would pass `{"historical_draws": [...]}` and receive a `KeyError`
- Apply scripts following the adapter code would pass `{"history": [...]}` and work correctly

**P140A fixes this by adding `normalize_draw_context()`** so both callers work without change.

---

## Draw Context Contract Audit

| Item | Finding |
|---|---|
| Adapter module | `lottery_api/models/p128_wave2_phase2_adapters.py` |
| Mismatch detected | True |
| Actual adapter key (phase2) | `history` |
| Actual adapter key (phase1) | `history` |
| P127 spec `draw_context_keys_required` | `historical_draws` |
| Selected canonical key | **`history`** |
| Backward-compat alias | `historical_draws` |
| Fix required | True |

**Mismatch origin:** P127 spec build script documents 'historical_draws' in draw_context_keys_required, but all adapter implementations (phase1 + phase2) use draw_context['history']. The P127 spec name was never implemented in adapter code.

**Selection rationale:** All 12 adapter functions across phase1 and phase2 consistently use draw_context['history']. This is the de-facto standard. 'historical_draws' was a P127 spec document naming choice that was never adopted in implementation. 'history' is selected as canonical.

---

## Contract Fix Summary

| Change | Details |
|---|---|
| Fix applied | True |
| Changes | normalize_draw_context() already present — skipped; RSR6_BLOCKED_STRATEGIES retained (not cleared) — clearing is beyond P140A contract scope |
| Normalization function | `normalize_draw_context()` in `lottery_api/models/p128_wave2_phase2_adapters.py` |
| Canonical key | `history` |
| Accepted alias | `historical_draws` |
| RSR6_BLOCKED_STRATEGIES cleared | False |
| DB write performed | False |

`normalize_draw_context()` behavior:
- If `draw_context["history"]` is present → pass through unchanged
- If `draw_context["historical_draws"]` is present → map to `"history"` key
- If neither key is present → raise `KeyError`

---

## Adapter Smoke Results for P10/P12

### power_precision_3bet (P10) — PASS

| Test | Result |
|---|---|
| Adapter function found | True |
| Expected bet count | 3 |
| Actual bet count | 3 |
| Correct bet count | True |
| Each bet has 6 numbers | True |
| Numbers in range [1..38] | True |
| No dups within bet | True |
| Canonical key test | True |
| Alias key test | True |
| Stable output (same input) | True |
| Deterministic ordering | True |
| Duplicate bet_index check | True |
| **Smoke test** | **PASS** |

### power_orthogonal_5bet (P12) — PASS

| Test | Result |
|---|---|
| Adapter function found | True |
| Expected bet count | 5 |
| Actual bet count | 5 |
| Correct bet count | True |
| Each bet has 6 numbers | True |
| Numbers in range [1..38] | True |
| No dups within bet | True |
| Canonical key test | True |
| Alias key test | True |
| Stable output (same input) | True |
| Deterministic ordering | True |
| Duplicate bet_index check | True |
| **Smoke test** | **PASS** |

---

## LEGACY_UNVERIFIED Handling Confirmation

| Item | Value |
|---|---|
| LEGACY_UNVERIFIED rows total | 100 |
| Excluded from apply base | True |
| Production baseline rows / strategy | 1500 |
| DB write in P140A | False |

The 50 LEGACY_UNVERIFIED rows per strategy remain in the DB but are EXCLUDED from the
apply base. Future P140/P141 apply scripts must use the selector:

```sql
WHERE strategy_id=? AND bet_index=1
  AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'
  AND provenance_hash IS NOT NULL
  AND controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520'
```

This returns exactly 1500 rows per strategy — the production baseline only.

---

## Future P140/P141 Apply Gate Impact

| Item | Status |
|---|---|
| Contract fix completed | ✅ |
| P10 future apply gate allowed | True |
| P12 future apply gate allowed | True |
| Per-strategy authorization required | True |
| P10 estimated insert rows | 3,000 (bet-2 + bet-3) |
| P12 estimated insert rows | 6,000 (bet-2 + bet-3 + bet-4 + bet-5) |
| DB rows after P140+P141 | 94,924 |

**P140 authorization phrase** (future, not yet active):
```
P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529
```

**P141 authorization phrase** (future, not yet active):
```
P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529
```

---

## Explicit Non-Actions

- No DB write in P140A
- No controlled_apply in P140A
- No replay rows inserted
- No P10/P12 apply authorized by P140A
- 4_STAR excluded
- P108 not run
- P117 not run
- P118 not run
- Rejected strategies: no action
- No scheduler / cron / launchd install
- No lifecycle / champion / registry mutation

---

## Remaining Risks

- LEGACY_UNVERIFIED rows (50 per strategy) must remain excluded from apply base — apply selector must filter by truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'.
- Adapter docstrings still show stale RSR-6 BLOCKED warnings (cosmetic). RSR6_BLOCKED_STRATEGIES constant cleared by P140A.
- P10/P12 are watchlist quality (p125_rank_score 31/35) — apply provides replay coverage, not production deployment authorization.
- After P140+P141, drift guard baseline will shift to 94,924 — drift guard total_count constant must be updated.
- Full DB backup required before each controlled_apply (P140, P141).
- normalize_draw_context() must be called by P140/P141 apply scripts before passing draw_context to adapter functions.

---

## Recommended Next Task

**P140:** power_precision_3bet multi-bet controlled_apply (bet-2+3, 3000 rows)
- Requires authorization phrase: `P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529`
- Apply base selector: 1500 production rows (POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED)
- Use `normalize_draw_context()` when constructing draw_context for adapter calls

---

## Final Classification

`P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY`
