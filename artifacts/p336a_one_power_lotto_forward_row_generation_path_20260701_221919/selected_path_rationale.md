# P336A — Selected Path & Rationale

## Inventory of in-tree POWER_LOTTO forward row-generation / persistence entrypoints (origin/main ce2c042)

| Path | Kind | Writes canonical DB? | On origin/main? | Sets `predicted_special`? |
|------|------|----------------------|-----------------|---------------------------|
| `lottery_api/models/p47_wave4_powerlotto_adapters.py::generate_dryrun_rows` | Gen-A row generator | No (returns dicts) | Yes | Yes, via **local** `_special_predict` |
| `scripts/p47_powerlotto_wave4_dryrun_rehearsal.py` | Gen-A dry-run apply | Temp `/tmp` DB only | Yes | Yes (imports p47) |
| `scripts/p48_powerlotto_wave4_production_apply.py` | Gen-A **production** apply | Yes (historically) | Yes | Yes (imports `generate_dryrun_rows` @ line 560) |
| `scripts/p56/p58/p59 …` | Gen-A wave-5 | temp / prod | Yes | Yes |
| `lottery_api/models/p93_tierb_replay_adapters.py` | Gen-B Tier-B | No (`DRY_RUN`, `production_eligible=False`) | Yes | **No** (frozen, content-phrase-guarded) |
| `p132…p141_apply_*.py` | Gen-B multi-bet | Yes | **No** (side-branch only) | No (hardcoded `None`) |
| `tools/quick_predict.py::power_special_v3` | live stdout tool | No | Yes | Yes (prints only) |

Persistence pipeline is **dormant** — no POWER row persisted since 2026-05-29.

## Options considered

**Option A — edit the p47 Gen-A path in place** (swap `_special_predict` →
`second_zone_predict`, add the guard in `generate_dryrun_rows`).
- ✗ **High blast radius.** `generate_dryrun_rows` is imported by the **production
  apply** `scripts/p48_powerlotto_wave4_production_apply.py:560` and by 6+ test
  modules (`test_p47…`, `test_p48…`, `test_p48_…null_policy`, `test_p231b…`,
  `test_p232a…`, `test_p56…`). Editing it would change the p48 production model
  (diverging the code from the 9,000 rows already in the DB) and risk breaking
  those tests. Violates "Minimal Impact" and "smallest **safe** path".

**Option B — edit the Tier-B `p93` Gen-B dry-run adapter.**
- ✗ Frozen `DRY_RUN`/`production_eligible=False`, content-phrase-guarded; P335A
  deliberately avoided it (risk without benefit). Not a "live" path.

**Option C — reuse a side-branch `p132…p141` script.**
- ✗ Forbidden: those files are not on origin/main; must not be used as canonical
  source.

**Option D (SELECTED) — add ONE new, isolated, forward-only row-builder module**
`lottery_api/models/power_lotto_forward_replay_row.py` with a single function
`build_power_lotto_forward_replay_row(...)` that:
- sources the second zone **only** from `second_zone_predict(history)` (P335A
  helper → reuses `PowerLottoSpecialPredictor`; no new algorithm), and
- runs `assert_power_lotto_predicted_special(row)` at the output boundary, and
- takes the first-zone bet as an input from any existing predictor (the
  complete-path test feeds a real p47 `predict_midfreq_fourier_mk_3bet_bet1`), and
- returns a canonical `strategy_prediction_replays`-shaped **forward** row
  (`actual_*`/`hit_*` = `None`, `replay_status="PREDICTED"`) and **writes no DB**.

## Why Option D is the smallest *safe* path

1. **Zero blast radius.** No existing file is modified — p47/p48/p56 lineage and
   all their tests are byte-for-byte untouched (git shows only 2 new P336A files).
   Satisfies CLAUDE.md "Minimal Impact: 不允許策略修改影響既有系統穩定性".
2. **Forward-only by construction.** It builds a NEW row for a target draw from
   strictly-causal history; it has no code path that reads or rewrites the 27,104
   existing historical NULL rows.
3. **Cannot silently default.** The only way past `second_zone_predict(history)`
   is a real in-range value; `< 30` draws raises `InsufficientHistoryError`. So
   the builder can only *return a non-NULL-second-zone row or raise* — the exact
   property P334A §4 / P335A wanted.
4. **Uses both P335A entrypoints** as mandated (`second_zone_predict` +
   `assert_power_lotto_predicted_special`).
5. **No DB write / no pipeline resume.** It returns a dict; persistence is a
   separate, separately-authorized step left out of scope.
6. **It is the natural resume point.** When the dormant POWER pipeline is
   (separately) authorized to resume, this is the one function it calls to obtain
   a guarded, non-NULL-second-zone row — "one function, one call-site".

**Selected path:** `lottery_api/models/power_lotto_forward_replay_row.py::build_power_lotto_forward_replay_row`.
