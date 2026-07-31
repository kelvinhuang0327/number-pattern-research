# P334A — POWER_LOTTO Prediction Pipeline Inventory

All paths read from `origin/main` (`ce2c042e…`) via `git show`/`git grep
<pattern> origin/main`, never from the stale local worktree.

## 1. Two generations of POWER_LOTTO prediction-generation code

### Generation A — "wave" single-bet adapters (2026-05-20 .. 05-25), DOES emit second zone

- `lottery_api/models/p47_wave4_powerlotto_adapters.py` (Wave 4 — P47/P48)
- `lottery_api/models/p56_wave5_powerlotto_adapters.py` (Wave 5 — P56/P58/P59)
- (Wave 6, P64/P66, reuses the same pattern per the `cold_complement`/
  `zonal_entropy` rows carrying `predicted_special`.)

Each defines a shared base-adapter class (e.g. `_P47BaseAdapter` in the
Wave-4 file) whose `get_one_bet(history, lottery_type)` method does:

```python
numbers = self._predict(history)      # strategy-specific main-number model
special = _special_predict(history)   # generic, strategy-agnostic 2nd-zone model
...
return sorted(numbers), special
```

`_special_predict(history, window=100)` (defined once per wave-adapter
file, identical logic — `p56_wave5_powerlotto_adapters.py:124-128` explicitly
comments "Identical to p47_wave4_powerlotto_adapters._special_predict()")
is a **frequency-based mean-reversion** model over the historical `special`
field. It takes only `history` and is **completely independent of which
main-number strategy calls it** — every Generation-A strategy gets a real
second-zone prediction "for free" through this shared wrapper.

The corresponding batch-apply scripts (`scripts/p48_powerlotto_wave4_production_apply.py`,
`scripts/p58_powerlotto_wave5_controlled_apply.py` /
`scripts/p59_powerlotto_wave5_controlled_apply.py`,
`scripts/p66_wave6_controlled_apply.py`) read `predicted_special` straight
out of the regenerated row dict and persist it into
`strategy_prediction_replays.predicted_special`. **This is the entire
source of the populated 9,000 rows.**

### Generation B — multi-bet extension adapters (2026-05-26 .. 05-29), does NOT emit second zone

- `lottery_api/models/p93_tierb_replay_adapters.py` (Tier-B, P94)
- A `p128_wave2_phase2_adapters.py`-style module exposing `get_all_bets_*`
  functions (`get_all_bets_midfreq_fourier_mk`, `get_all_bets_power_precision`,
  `get_all_bets_power_orthogonal`, etc.) — used by the multi-bet backfill
  scripts below.

Batch-apply scripts using Generation B:
`scripts/p94_tierb_controlled_apply.py` (P94),
`scripts/p126b_apply_power_fourier_rhythm_2bet.py`-equivalent (P126B, commit
`0fd9166`), `scripts/p132_apply_midfreq_fourier_mk_3bet.py` (P132, commit
`436b2ca`), `scripts/p133_apply_pp3_freqort_4bet.py`-equivalent (P133,
commit `749a01e`), `scripts/p134_apply_fourier_rhythm_3bet.py`-equivalent
(P134, commit `211e3aa`), `scripts/p140_apply_power_precision_3bet.py` (P140,
commit `cfff33a`), `scripts/p141_apply_power_orthogonal_5bet.py` (P141,
commit `6a3f49b`).

Each `get_all_bets_*` function returns **main-number bet lists only** — no
second-zone value. Confirmed directly in the row-builder of every
Generation-B apply script (verbatim, e.g. P132/P140/P141):

```python
insert_rows.append({
    ...
    "predicted_special":       None,     # hardcoded, unconditional
    "actual_special":          row["actual_special"],
    ...
    "special_hit":             0,        # forced 0, not computed from a real prediction
    ...
})
```

`predicted_special` is not merely omitted from the schema or the INSERT
statement — the INSERT statement includes the column and binds it to the
Python literal `None` on every row, for every Generation-B batch. **This is
the entire source of the 27,104 NULL rows.** Exact reconciled per-batch
counts (read-only DB query, `controlled_apply_id` grouped, POWER_LOTTO
only): legacy/`NULL` apply-id 100, `P19B` 1,500, `P20` 3,000, `P78`(×2) 2,
`P94` 1,500, `P126B` 1,500, `P132` 3,000, `P133` 4,500, `P134` 3,002,
`P140` 3,000, `P141` 6,000 → sum **27,104** exactly. (Note: the
`replay_lifecycle_drift_guard.py` baseline's `p94_count=7500` is P94's
*total* multi-lottery batch size, not the POWER_LOTTO-only subset; the
figure above is filtered to `lottery_type='POWER_LOTTO'`.) See
`predicted_special_gap_analysis.md` for the per-strategy breakdown that
separates "never had a second-zone model at all" from "had one for bet-1,
lost it in the multi-bet extension."

## 2. Current live prediction entry point — `tools/quick_predict.py`

This is the interactive CLI tool memory/CLAUDE.md references as "預測入口."
Read directly (`git show origin/main:tools/quick_predict.py`):

- `def predict_power(history, rules, num_bets=2)` (line ~438) calls
  `special_top = power_special_v3(history)` and sets `bet['special'] =
  special` on every generated bet.
- `def power_special_v3(history)` (line ~407) tries
  `models.special_predictor.PowerLottoSpecialPredictor` first, falling back
  to a `Counter`-based frequency model over the last 50 draws' `special`
  field if the import fails.
- `PowerLottoSpecialPredictor` (`lottery_api/models/special_predictor.py`)
  is a **multi-strategy fusion model** (frequency + a 2nd-order Markov
  chain via `MarkovChain2ndOrderPredictor`) — a materially more
  sophisticated second-zone model than the Generation-A `_special_predict()`
  frequency-only model.
- `quick_predict.py` was grepped for any DB-write primitive
  (`INSERT`/`cursor.execute` with a write verb/`.commit(`): **zero matches**
  for writes. It is a **read + stdout-print tool only** (`print_prediction`)
  — it never calls `strategy_prediction_replays` INSERT logic.

**Conclusion: the best second-zone model in the codebase today is already
being run, on every live prediction, but its output is discarded after
being printed to a terminal — it is never persisted anywhere.**

## 3. Staleness of the replay table for POWER_LOTTO

Read-only query against the canonical DB:

| lottery_type | MAX(target_draw) | MAX(generated_at) |
|---|---|---|
| POWER_LOTTO | 115000041 | 2026-05-29 06:30:32 |
| BIG_LOTTO | 115000055 | (not queried — out of scope) |
| DAILY_539 | 115000121 | (not queried — out of scope) |
| `draws` (raw POWER_LOTTO results) | up to draw 115000052 | — |

No `strategy_prediction_replays` row for POWER_LOTTO has been created since
**2026-05-29** — over a month before this audit (2026-07-01) — even though
11 more POWER_LOTTO draws have since occurred (115000041 → 115000052 in
`draws`). **There is currently no active, scheduled, or automatic pipeline
that creates new POWER_LOTTO replay rows at all**, second-zone or otherwise.
This is a second, independent gap layered on top of the second-zone gap:
even main-number predictions have stopped being persisted into the replay
table for this lottery type.

`tools/post_draw_pipeline.py`, referenced in project memory as the 7-step
post-draw pipeline entry point, **does not exist at `origin/main` HEAD**
(`git cat-file -e origin/main:tools/post_draw_pipeline.py` fails). No
alternate current path for it was located within this audit's scope.

## 4. Schema fact

`strategy_prediction_replays.predicted_special` is an ordinary nullable
`INTEGER` column, present in every row regardless of generation. There is
**no schema gap** — the column has always existed and is always bound in
every INSERT statement across both generations. The gap is 100%
generation-logic, not schema, not artifact-export, not canonical-view.
