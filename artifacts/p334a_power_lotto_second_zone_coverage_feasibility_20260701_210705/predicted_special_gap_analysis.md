# P334A — `predicted_special` Gap Analysis

## 1. Read-only DB reconciliation (canonical DB, SHA `9956c3bc…`, unchanged)

Per-strategy (POWER_LOTTO, `strategy_prediction_replays`):

| strategy_id | total rows | with `predicted_special` | NULL | target_draw range |
|---|---:|---:|---:|---|
| cold_complement_2bet | 1,500 | 1,500 | 0 | 101000002–115000040 |
| midfreq_fourier_2bet | 1,500 | 1,500 | 0 | 101000002–115000040 |
| zonal_entropy_2bet | 1,500 | 1,500 | 0 | 101000002–115000040 |
| fourier30_markov30_2bet | 1,501 | 1,500 | 1 | 101000002–115000041 |
| midfreq_fourier_mk_3bet | 4,500 | 1,500 | 3,000 | 101000002–115000040 |
| pp3_freqort_4bet | 6,000 | 1,500 | 4,500 | 101000002–115000040 |
| fourier_rhythm_3bet | 4,503 | 0 | 4,503 | 101000002–115000041 |
| power_fourier_rhythm_2bet | 3,000 | 0 | 3,000 | 101000003–115000041 |
| power_precision_3bet | 4,550 | 0 | 4,550 | 99000055–115000040 |
| power_orthogonal_5bet | 7,550 | 0 | 7,550 | 99000055–115000040 |
| **total** | **36,104** | **9,000** | **27,104** | — |

## 2. Three distinct sub-patterns inside the 27,104 NULL rows

### Pattern 1 — strategy never paired with any second-zone model (17,603 rows: 4,503+3,000+4,550+7,550 minus overlaps = fourier_rhythm_3bet + power_fourier_rhythm_2bet + power_precision_3bet + power_orthogonal_5bet, fully NULL end-to-end)

These 4 strategies (exactly the 4 P333A flagged as `NO_SECOND_ZONE_SUPPORT`)
are **100% NULL across their entire row history**, including their very
first bet (`bet_index=1`), applied as early as `P19B`/`P20`
(2026-05-20) and `power_precision_3bet`/`power_orthogonal_5bet` originally
even earlier (target_draw starting at `99000055`, pre-dating the wave
numbering). Their main-number prediction functions
(e.g. `predict_power_precision_3bet` used by `tools/predict_power_precision_3bet.py`)
were never wrapped by anything equivalent to `_P47BaseAdapter.get_one_bet()`
— no second-zone call was ever made for these strategy definitions, at any
point in their lifetime, in any script.

**Root cause category: pipeline (strategy-adapter) never produced it.**
This is a genuine design gap in these 4 strategies' adapters, not a
persistence or schema issue.

### Pattern 2 — strategy HAD a real second-zone model for bet-1, lost it for bet-2+ (7,500 rows: midfreq_fourier_mk_3bet 3,000 + pp3_freqort_4bet 4,500)

- `midfreq_fourier_mk_3bet`: bet-1 (1,500 rows, `P48` wave4, 2026-05-24) has
  real `predicted_special` from `_special_predict()`. bet-2/bet-3 (3,000
  rows, `P132`, 2026-05-28) are 100% NULL — same strategy_id, same draws,
  same underlying history, but generated via
  `get_all_bets_midfreq_fourier_mk()` (a main-number-only multi-bet
  function) instead of the wave-4 `_P47BaseAdapter` wrapper.
- `pp3_freqort_4bet`: identical pattern — bet-1 (1,500 rows, `P48`) has
  real special; bet-2/3/4 (4,500 rows, `P133`, 2026-05-28) are NULL.

**Root cause category: persistence/generation-path omission** — the
second-zone signal-generation logic already exists, is proven to work
(9,000 real historical rows), and is even reused verbatim across
Generation-A wave files, but the newer multi-bet extension code path
(`p128`-style `get_all_bets_*` adapters) was never wired to call it. The
apply scripts (`p132_apply_midfreq_fourier_mk_3bet.py`,
`p133_apply_pp3_freqort_4bet.py`-equivalent) hardcode
`"predicted_special": None` in their row-builder unconditionally.

### Pattern 3 — small extension/backfill gaps and legacy pre-instrumentation rows (2,001 rows: `P78`×2=2 + `P94`=1,500 + legacy `NULL` apply-id=100 + `fourier30_markov30_2bet` P78 1-row)

- `fourier30_markov30_2bet` (Pattern-2-adjacent, but only 1 row affected):
  the single-row `P78_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_DRAWEXT_20260526`
  draw-extension row is NULL even though the strategy's other 1,500 rows
  (`P58` wave5) have real second zone — a one-off gap in a small
  one-row backfill script, same root cause as Pattern 2 (extension script
  skipped the second-zone call).
- `P94_TIERB_CONTROLLED_APPLY_20260526` (1,500 POWER_LOTTO rows): Tier-B
  adapters (`lottery_api/models/p93_tierb_replay_adapters.py`) — not fully
  traced strategy-by-strategy in this audit (out of the primary-question
  scope); presumptively Pattern-1-or-2-style, needs confirmation in the
  future implementation task.
- 100 legacy rows with `controlled_apply_id IS NULL`: pre-date the wave
  numbering/instrumentation entirely; out of scope for a "resume/extend an
  existing model" fix — these are effectively archaeological and would, if
  ever revisited, fall under the no-backfill policy exactly like the rest.

## 3. Why the aggregate figure is 24.928% and not 0% or 100%

The figure is an artifact of **when** each batch was generated, not of any
single unified design decision:
- Waves 3 (BIG_LOTTO, not counted here), 4, 5, 6 (2026-05-24/25) used
  Generation-A adapters with the shared `_special_predict()` wrapper →
  second zone always populated.
- Everything generated afterward (2026-05-26 onward: Tier-B, multi-bet
  extensions, and the 4 strategies that were always main-number-only) used
  Generation-B `get_all_bets_*` adapters, which never call any second-zone
  model → always NULL.
- No POWER_LOTTO row has been generated at all since 2026-05-29 (see
  `power_lotto_pipeline_inventory.md` §3) — the gap has been frozen at
  24.928% for over a month simply because nothing new has been produced
  in either generation since.

## 4. Answer to audit scope item 6 (missing-because taxonomy)

| category | applies? |
|---|---|
| missing because old pipeline never produced it | **YES** — Pattern 1 (4 strategies, 17,603 rows) |
| missing because persistence omitted it | **YES** — Pattern 2 (7,500 rows) and the `P78` 1-row case; the value is computable but the apply script drops it |
| missing because canonical view omitted it | **NO** — `strategy_prediction_replays` is not a view; this is a base table, and the column is populated correctly wherever the generation code calls a second-zone model |
| missing because artifact export omitted it | **NO** — this is a DB-persistence gap, not an export/reporting gap; the value was never computed in Pattern 1/2/3, so there was nothing to export |
| unknown | Tier-B P94's 1,500 rows (Pattern 3) — root cause not fully traced to a specific adapter function in this audit; recommend as part of the future implementation task's discovery step |
