# P125 Adapter Gap Plan From P124 Matrix

**Generated:** 2026-05-28T03:20:22.522598+00:00
**Classification:** `P125_ADAPTER_GAP_PLAN_READY`
**Task:** P125_ADAPTER_GAP_PLAN_FROM_P124_MATRIX

---

## 1. Executive Summary

P125 reads the P124 multi-bet replay truth and coverage matrix and produces a ranked adapter gap plan. This is a read-only planning artifact. No DB rows are written. No adapters are built. No strategies are promoted. No scheduler is installed.

| Metric | Count |
|---|---|
| P124 coverage matrix rows | 36 |
| Controlled-apply-ready (Tier-B) | 5 |
| Adapter-build-needed | 12 |
| Relabel-only | 2 |
| No-action (kept) | 17 |
| Rejected (no-action-forever) | 12 |
| Native multi-bet strategies | **0** |
| DB writes in P125 | **0** |

---

## 2. What P124 Proved

- **Zero native multi-bet storage.** Every one of the 54462 replay rows stores exactly one `predicted_numbers` list. Even strategies named `_3bet`, `_4bet`, `_5bet` store only bet-1 in the current DB.
- **All 36 strategy×lottery pairs are first_bet_only_fallback, rejected, or already_covered.** No pair is genuinely native_multi_bet.
- **5 Tier-B adapter strategies** exist with working `get_all_bets()` implementations from P93/P94, making them controlled_apply candidates without new adapter code.
- **12 strategies** need new adapters before multi-bet replay rows can be generated.
- **DB invariants confirmed at P125 start:** replay_rows=54462, 3_STAR=4179/max=115000106, POWER_LOTTO=1913/max=115000041.

---

## 3. Controlled-Apply-Ready List (P126 Scope)

These 5 strategies have working Tier-B adapters. They can proceed to P126 controlled_apply dry-run once P128 storage design is approved or the current one-row-per-bet convention is explicitly authorized.

**Every candidate requires `explicit_apply_authorization_required = true`. P125 does NOT apply any of these.**

| Rank | Strategy ID | Lottery | Bets | Quality | Risk | Estimated New Rows |
|---|---|---|---|---|---|---|
| 1 | `biglotto_echo_aware_3bet` | BIG_LOTTO | 3 | fallback_equivalent | low_to_medium | ~4500 (estimate: 1500 draws × 3 bets) |
| 2 | `daily539_f4cold_5bet` | DAILY_539 | 5 | watchlist | medium | ~7500 (estimate: 1500 draws × 5 bets) |
| 3 | `daily539_f4cold_3bet` | DAILY_539 | 3 | watchlist | medium | ~4500 (estimate: 1500 draws × 3 bets) |
| 4 | `power_fourier_rhythm_2bet` | POWER_LOTTO | 2 | watchlist | medium | ~3000 (estimate: 1500 draws × 2 bets) |
| 5 | `biglotto_ts3_markov_4bet_w30` | BIG_LOTTO | 4 | sub_baseline | medium | ~6000 (estimate: 1500 draws × 4 bets) |

---

## 4. Adapter-Build-Needed List (P127 Scope)

These 12 strategies need a new `get_all_bets()` adapter before controlled_apply can be attempted. Ranked by product value (quality × lottery priority × bet count).

| Rank | Strategy ID | Lottery | Bets | Quality | Missing Component |
|---|---|---|---|---|---|
| 1 | `pp3_freqort_4bet` | POWER_LOTTO | 4 | prediction_helpful | pp3_freqort_multi_bet_adapter |
| 2 | `midfreq_fourier_mk_3bet` | POWER_LOTTO | 3 | prediction_helpful | fourier_multi_bet_adapter |
| 3 | `acb_markov_midfreq_3bet` | DAILY_539 | 3 | watchlist | markov_multi_bet_adapter |
| 4 | `midfreq_acb_2bet` | DAILY_539 | 2 | watchlist | midfreq_multi_bet_adapter |
| 5 | `midfreq_fourier_2bet` | DAILY_539 | 2 | watchlist | fourier_multi_bet_adapter |
| 6 | `zonal_entropy_2bet` | POWER_LOTTO | 2 | fallback_equivalent | zonal_multi_bet_adapter |
| 7 | `cold_complement_2bet` | POWER_LOTTO | 2 | fallback_equivalent | cold_complement_multi_bet_adapter |
| 8 | `power_orthogonal_5bet` | POWER_LOTTO | 5 | watchlist | orthogonal_multi_bet_adapter |
| 9 | `power_precision_3bet` | POWER_LOTTO | 3 | watchlist | precision_multi_bet_adapter |
| 10 | `fourier_rhythm_3bet` | POWER_LOTTO | 3 | watchlist | fourier_multi_bet_adapter |
| 11 | `midfreq_fourier_2bet` | POWER_LOTTO | 2 | watchlist | fourier_multi_bet_adapter |
| 12 | `fourier30_markov30_2bet` | POWER_LOTTO | 2 | watchlist | fourier_markov_multi_bet_adapter |

---

## 5. Why Native Multi-Bet Count Is Zero

The P94 Tier-B controlled apply run stored results using the existing replay insert path, which writes one `predicted_numbers` list per row. Even though the Tier-B adapters can produce multiple bets via `get_all_bets()`, only the first bet (or a merged single-bet representation) was stored. Therefore:

- `strategy_prediction_replays` has exactly 54462 rows — unchanged after P94.
- All rows contain a single `predicted_numbers` JSON list.
- Strategies with names like `_3bet`, `_4bet`, `_5bet` were stored as if they were 1-bet strategies.
- This is not incorrect — it is first_bet_only_fallback, not fabrication. But it means the CEO mandate for 1-5 bet historical replay is **not yet satisfied**.

---

## 6. Replay Storage Risk: One predicted_numbers List Per Row

The current schema forces a single bet per replay row. Before any multi-bet expansion can happen, a storage format decision must be made in P128:

### RSR-1: One predicted_numbers list per replay row

**Detail:** Current strategy_prediction_replays schema stores a single JSON list of predicted numbers per row. Multi-bet strategies with N bets require either: (a) N separate rows per draw, or (b) a JSON array-of-arrays per row. Neither is formally decided or implemented.

**Impact:** Blocks native_multi_bet storage for all strategies

**Mitigation:** P128 must design and approve the storage format before any apply

**Severity:** high

### RSR-2: First-bet-only labeling inconsistency

**Detail:** 19 strategy×lottery pairs have first_bet_only_fallback in P124 matrix but are stored as if they were full multi-bet strategies. Row counts may mislead consumers about actual bet diversity.

**Impact:** User-facing replay may overstate prediction variety

**Mitigation:** P126/P127 controlled_apply and adapter builds must update labels alongside rows

**Severity:** medium

### RSR-3: No replay row deduplication guard for multi-bet inserts

**Detail:** If controlled_apply generates rows for bets 2-5 for already-covered draws, there is no current guard against inserting duplicate bet-1 rows. P126 must enforce upsert-or-skip logic keyed on (strategy_id, draw, bet_index).

**Impact:** Duplicate rows could inflate replay counts and mislead drift guard

**Mitigation:** P126 dry-run must verify row-count delta matches exactly N_bets × N_draws

**Severity:** medium

### RSR-4: Adapter get_all_bets() not uniformly implemented

**Detail:** P93/P94 Tier-B adapters implement get_all_bets() for some strategies, but P124 confirms 12 strategies still lack any multi-bet adapter. P127 must define and implement the missing adapters before apply.

**Impact:** Cannot expand replay coverage for 12 strategies until P127 completes

**Mitigation:** P127 adapter builds with full unit test coverage

**Severity:** medium

---

## 7. Recommended Next Sequence: P126 / P127 / P128

### P126 (Sequence 1): Controlled Apply Dry-Run and Apply for 5 Tier-B Candidates

Run controlled_apply dry-run for each of the 5 Tier-B candidates. Verify bet-count output, no fabrication, and row-count delta. If dry-run passes, apply with explicit authorization. All 5 strategies must have explicit_apply_authorization_required=true.

**Candidates:**
- `daily539_f4cold_3bet`
- `daily539_f4cold_5bet`
- `biglotto_echo_aware_3bet`
- `biglotto_ts3_markov_4bet_w30`
- `power_fourier_rhythm_2bet`

**Preconditions:**
- P128 storage design approved OR apply using current one-row-per-bet convention
- Dry-run passes: row-count delta = N_draws × target_bets
- No duplicate bet-1 rows
- Staging whitelist clean

### P127 (Sequence 2): Adapter Build for 12 Missing Multi-Bet Adapters

Build get_all_bets() adapters for the 12 strategies currently missing them. Priority order: prediction_helpful (pp3_freqort_4bet, midfreq_fourier_mk_3bet) first, then fallback_equivalent, then watchlist. Each adapter must have unit tests and no-future-data-leak assertions.

**Priority order:**
- pp3_freqort_4bet (POWER_LOTTO / prediction_helpful)
- midfreq_fourier_mk_3bet (POWER_LOTTO / prediction_helpful)
- zonal_entropy_2bet (POWER_LOTTO / fallback_equivalent)
- cold_complement_2bet (POWER_LOTTO / fallback_equivalent)
- acb_markov_midfreq_3bet (DAILY_539 / watchlist)
- midfreq_acb_2bet (DAILY_539 / watchlist)
- midfreq_fourier_2bet (DAILY_539 / watchlist)
- power_precision_3bet (POWER_LOTTO / watchlist)
- power_orthogonal_5bet (POWER_LOTTO / watchlist)
- fourier_rhythm_3bet (POWER_LOTTO / watchlist)
- midfreq_fourier_2bet (POWER_LOTTO / watchlist)
- fourier30_markov30_2bet (POWER_LOTTO / watchlist)

### P128 (Sequence 3): Native Multi-Bet Replay Storage Design

Design the storage format for native multi-bet replay rows. Decide between: (a) one row per bet per draw, or (b) array-of-arrays per row. Define schema migration plan, drift guard update, and API compatibility rules. This is a design-only phase; no schema changes in P128 itself.

**Open design questions:**
- Row-per-bet: simpler queries but N× row growth
- Array-per-row: compact but breaks current replay consumer assumptions
- Backward compatibility with existing 54462 rows
- Drift guard update to track multi-bet rows separately

---

## 8. Explicit Non-Actions in P125

| Item | Status |
|---|---|
| DB writes | **None** — P125 is read-only planning |
| Scheduler installation | **None** — no cron / launchd install |
| 4_STAR backtest | **Blocked** — source_unknown, provenance absent |
| P108 Special3 | **Blocked** — needs ~37 more draws |
| P117 POWER_LOTTO OOS | **Blocked** — needs 30-40 more draws |
| P118 BIG_LOTTO quarantine | **Blocked** — authorization phrase absent |
| Rejected strategy expansion | **Forbidden** — no_action_forever |
| Strategy promotion / champion / registry | **None** |
| Fabricated replay rows | **Forbidden** |

---

## 9. Final Classification

```
P125_ADAPTER_GAP_PLAN_READY
```

Next task: **P126_CONTROLLED_APPLY_PLAN_FOR_TIER_B_MULTI_BET_ADAPTERS** (requires explicit apply authorization for each of the 5 candidates).
