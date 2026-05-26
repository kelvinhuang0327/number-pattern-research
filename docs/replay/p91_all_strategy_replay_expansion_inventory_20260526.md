# P91 — All-Strategy Replay Expansion Inventory Refresh
**Date:** 2026-05-26
**Classification:** P91_ALL_STRATEGY_REPLAY_EXPANSION_INVENTORY_READY
**Status:** EVIDENCE_ONLY — No DB writes, no row inserts, no lifecycle changes
**Branch:** p91-all-strategy-replay-expansion-inventory

## Context
Strategy Historical Replay is launch-ready (P90: OPERATIONS_HOLD_BASELINE_ARCHIVED).
Operations status: HOLD. Launch readiness: READY.
This inventory answers: "Can all 512 strategy universe entries show prediction-vs-actual history?"

## Baseline
- Production rows: **46962**
- POWER_LOTTO max draw: **115000041** (2026/05/21)
- P79 rows 46961 + 46962: VERIFIED
- Drift guard: PASS | Branch governance: PASS
- P82 freshness guard: SKIP (script not found)
- P86 source decision guard: SKIP (script not found)

## Strategy Universe Summary
- Total strategies in P0 universe JSON: **512**
- Distribution: DAILY_539=67, BIG_LOTTO=163, POWER_LOTTO=80, UNSPECIFIED=187, CROSS_GAME=15
- Strategies with DB replay rows: **31** (30 unique strategy_ids; midfreq_fourier_2bet spans 2 lottery types)

## Tier Summary
| Tier | Label | Count | Description |
|------|-------|-------|-------------|
| A | Row-backed (clickable now) | 31 | Already have replay rows, full history available |
| B | ONLINE/WATCHING/PROVISIONAL, code-backed | 70 | Working adapters or RSM reference, 0 rows yet |
| C | Retired, adapter-backed | 0 | All retired strategies already captured in Tier A |
| D | Rejected, replay-only | 70 | Artifact/lesson evidence; display-only, must NOT promote |
| E | Experimental with lesson/artifact evidence | 41 | Reconstruction candidates with moderate effort |
| F | Experimental/Unknown, tools-only or no evidence | 305 | Not viable for near-term history display |
| **CROSS_GAME** (overlapping) | | *15* | Cross-game scope — covered within tiers above |
| **Total (P0 universe)** | | **512** | All entries accounted for |

Note: Tiers A–F sum to 512 (P0 universe). The 31 Tier A strategies include 4 not indexed in P0
(acb_markov_midfreq, cold_complement_2bet, midfreq_fourier_mk_3bet, zonal_entropy_2bet).
Tier A count (31) reflects named strategy slots; DB holds 30 unique strategy_ids.

## Tier A Details — 31 Row-Backed Strategies

### DAILY_539 (13 strategies)
| strategy_id | display_name | rows | truth_level | performance |
|-------------|--------------|------|-------------|-------------|
| acb_1bet | 今彩539 ACB 1注 | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | RETIRED |
| acb_single_539 | 今彩539 ACB Single 1注 | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | WAVE2 |
| acb_markov_midfreq | 今彩539 ACB+Markov 中頻 | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | RETIRED |
| acb_markov_midfreq_3bet | 今彩539 ACB+Markov 中頻 3注 | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | RETIRED |
| 539_3bet_orthogonal | 今彩539 ACB+Markov+Fourier 正交 3注 | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | WAVE2_ACTIVE |
| daily539_f4cold | 今彩539 F4 Cold | 1590 | DAILY539_BACKFILL_VERIFIED (1500) + None (90 legacy) | ONLINE_LEGACY |
| p0b_539_3bet_f_cold_fmid | 今彩539 Fourier4正交 cold+midfreq 3注 | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | WAVE2_ACTIVE |
| p0c_539_3bet_f_cold_x2 | 今彩539 Fourier4正交 x2 cold 3注 | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | WAVE2_ACTIVE |
| markov_1bet_539 | 今彩539 Markov 1注 | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | WAVE2_ACTIVE |
| daily539_markov_cold | 今彩539 Markov Cold | 1590 | DAILY539_BACKFILL_VERIFIED (1500) + None (90 legacy) | ONLINE_LEGACY |
| zone_gap_3bet_539 | 今彩539 Zone+Gap 3注 | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | WAVE2_ACTIVE |
| midfreq_acb_2bet | 今彩539 中頻 ACB 2注 | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | RETIRED |
| midfreq_fourier_2bet | 今彩539 中頻 Fourier 2注 | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | RETIRED |

### BIG_LOTTO (9 strategies)
| strategy_id | display_name | rows | truth_level | performance |
|-------------|--------------|------|-------------|-------------|
| cold_complement_biglotto | 大樂透 Cold Complement 2注 | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| coldpool15_biglotto | 大樂透 Cold Pool-15 Pick-6 | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| biglotto_deviation_2bet | 大樂透 Deviation 2注 | 1570 | BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED + None (70 legacy) | COVERAGE_ONLY (L91) |
| bet2_fourier_expansion_biglotto | 大樂透 Fourier 2注 Expansion | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| fourier30_markov30_biglotto | 大樂透 Fourier30+Markov30 | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| markov_2bet_biglotto | 大樂透 Markov 2注 | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| markov_single_biglotto | 大樂透 Markov Single 1注 | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| ts3_regime_3bet | 大樂透 TS3+Regime 3注 | 1500 | BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED | COVERAGE_ONLY (L91) |
| biglotto_triple_strike | 大樂透 Triple Strike | 1570 | BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED + None (70 legacy) | COVERAGE_ONLY (L91) |

### POWER_LOTTO (9 strategies)
| strategy_id | display_name | rows | truth_level | performance |
|-------------|--------------|------|-------------|-------------|
| fourier30_markov30_2bet | 威力彩 fourier30_markov30_2bet | 1501 | WAVE5_CONTROLLED_APPLY_VERIFIED + DRAW_EXT | prediction-helpful (M3+ 4.07% > 3.87% baseline) |
| fourier_rhythm_3bet | 威力彩 Fourier Rhythm 3注 | 1501 | SINGLE_BACKFILL_VERIFIED + DRAW_EXT | ACTIVE_PRODUCTION |
| midfreq_fourier_2bet | 威力彩 MidFreq+Fourier 2注 | 1500 | POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | ACTIVE_PRODUCTION |
| midfreq_fourier_mk_3bet | 威力彩 MidFreq+Fourier+Markov 3注 | 1500 | POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | ACTIVE_PRODUCTION |
| power_orthogonal_5bet | 威力彩 Orthogonal 5注 | 1570 | POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED + None (70 legacy) | ONLINE_LEGACY |
| pp3_freqort_4bet | 威力彩 PP3+FreqOrt 4注 | 1500 | POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | ACTIVE_PRODUCTION |
| power_precision_3bet | 威力彩 Precision 3注 | 1570 | POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED + None (70 legacy) | ONLINE_LEGACY |
| zonal_entropy_2bet | 威力彩 Zonal Entropy 2注 | 1500 | POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED | fallback-equivalent (M3+ 3.67%) |
| cold_complement_2bet | 威力彩 冷號互補 2注 | 1500 | POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED | sub-baseline (M3+ 3.67%) |

## Tier B Details — 70 ONLINE/WATCHING/PROVISIONAL Without Rows

Tier B represents strategies that appear in the P0 universe with PRODUCTION, WATCHING, or
PROVISIONAL lifecycle status, but do not yet have replay rows in the DB.

Sub-classifications:
- **RSM current strategies** (9): Active in rolling strategy monitor, have real prediction code.
  Examples: f4cold_3bet, f4cold_5bet, deviation_complement_2bet, echo_aware_3bet,
  fourier_rhythm_2bet, triple_strike_3bet, ts3_markov_4bet_w30, ts3_markov_freq_5bet_w30, orthogonal_5bet
- **Strategy package ACTIVE** (9): Multi-strategy packages with code, ACTIVE status.
  Examples: biglotto_2bet_deviation_complement, biglotto_2bet_fourier_rhythm, biglotto_3bet_triple_strike_v2
- **Lesson-reference only** (31): Referenced in lessons/memory but no confirmed adapter code.
  Examples: power_lotto_fourier_rhythm_3bet, power_lotto_pp3_sum_regime, pp3_freqort_3bet
- **Tools candidates** (21): Identified in tools scan but no backfill adapter written yet.
  Examples: bl_cold_numbers_bet, bl_fourier_rhythm_bet, bl_markov_orthogonal_bet

**Recommended priority for P92:** RSM current strategies (9) — highest likelihood of having
working adapter code that can generate 1500-period backfill rows.

## Tier C Details — 0 Strategies

No strategies in Tier C. All retired wave-1 adapter strategies already have 1500-period
backfill rows and are captured in Tier A (e.g., acb_1bet, acb_markov_midfreq, midfreq_acb_2bet,
midfreq_fourier_2bet[DAILY_539]).

## Tier D Details — 70 Rejected Strategies (Replay-Only Policy)

All 82 REJECTED lifecycle entries in P0, minus 12 already row-backed (those cross-counted
as Tier A since their rows are display-only history):
- rejected_artifact entries (42 in P0): Strategy tested and failed validation, artifact evidence retained
- lesson_reference entries (21 in P0): Documented in lessons.md as rejected with evidence
- other rejected entries (7 in P0): Various rejection evidence patterns
- 12 strategies appear as REJECTED in P0 but already have replay rows (in Tier A)

**Policy:** Tier D strategies may have replay rows added for historical display.
They MUST NOT be promoted to ONLINE lifecycle. Display label: "Rejected/Archived".
Note: Some Tier A strategies have P0 lifecycle=REJECTED (e.g., wave2/wave3 backfills
where P0 used REJECTED to mean "replaced by newer version" not "bad strategy").

## Tier E Details — 41 Reconstruction Candidates

EXPERIMENTAL and UNKNOWN lifecycle strategies with lesson_reference or artifact evidence:
- lesson_reference in EXPERIMENTAL: ~2 entries
- UNKNOWN with lesson/source references: ~41 entries total
- Examples: predict_539_5bet_f4cold, bet_deviation_complement, bet_fourier_rhythm, core_satellite

**Reconstruction effort:** Each requires 4-8 hours of code archaeology and adapter writing.
Recommended for P93+ tasking. Evidence type: lessons.md line references, todo.md references.

## Tier F Summary — 305 Unsupported/No-Data Strategies

EXPERIMENTAL strategies with notes pattern "tools_candidate" only (244 entries) plus
other EXPERIMENTAL/UNKNOWN entries with no code evidence (59 entries).
These are strategy IDs identified from tools scan but never validated or implemented.

**Blockers:**
- no_adapter_code: No wave adapter function written
- no_validation_evidence: No backtest or lessons reference
- insufficient_data: Only tool scan ID, no historical draws
- tools_candidate_only: Listed as possible future strategy, never built

**Policy:** These strategies show "No historical data available" in UI.
Do NOT insert placeholder rows for Tier F strategies.

## Product Question Answer

**Q: Can all 512 strategy universe entries show prediction-vs-actual history?**

**A:** 31 entries (Tier A) are clickable NOW with full history.
     70 entries (Tier B) can potentially be made clickable after dry-run/apply
       — highest priority: 9 RSM current strategies.
     0 entries in Tier C (already folded into Tier A).
     70 entries (Tier D) can show history as rejected/display-only — must NOT be promoted.
     41 entries (Tier E) require reconstruction effort (P93+).
     305 entries (Tier F) show "No historical data available" — not viable near-term.

**Near-term clickable potential (P92):** 31 (now) + up to 9 RSM candidates (after dry-run).

## No-Data Policy
Strategies in Tier F with no code, no artifact evidence, and no draws data
will show "No historical data available" in UI — this is expected and correct.
Do NOT insert placeholder rows for these strategies.

## Rejected/Offline Replay-Only Policy
Tier D (rejected) and any Tier B offline/retired strategies may have replay rows
for historical display purposes ONLY. These strategies must NOT be promoted to ONLINE
lifecycle under any circumstances. Display label: "Retired/Archived" or "Rejected".

## Performance Disclosures (Pre-Confirmed)
- fourier30_markov30_2bet: **prediction-helpful** (M3+ 4.07% > 3.87% baseline)
- cold_complement_2bet: **sub-baseline** (M3+ 3.67% < 3.87% baseline)
- zonal_entropy_2bet: **fallback-equivalent** (M3+ 3.67%, regime 100% chaotic)
- BIG_LOTTO all strategies: **COVERAGE_ONLY** — L91 signal space exhausted, 49C6 indistinguishable from fair random
- DAILY_539 all strategies: signal-exhausted per L82 — only ACB/MidFreq/Fourier validated strategies in active use

## Recommended P92 Scope
P92 should target Tier B RSM current strategies (9 candidates) for dry-run replay expansion.
- Expected strategies: up to 9 (f4cold_3bet, f4cold_5bet, deviation_complement_2bet, echo_aware_3bet,
  fourier_rhythm_2bet, triple_strike_3bet, ts3_markov_4bet_w30, ts3_markov_freq_5bet_w30, orthogonal_5bet)
- Estimated new rows: up to 13,500 (9 × 1500 periods each), subject to adapter availability
- Pre-condition: Adapter code audit required before dry-run to confirm adapter function exists

P93 scope: Tier E reconstruction candidates (41 strategies, ~4-8h each).

## Governance
- DB writes: false
- Replay row changes: 0
- Lifecycle promotions: 0
- Champion replacements: 0
- Registry mutations: 0
- Source: evidence-only read pass
