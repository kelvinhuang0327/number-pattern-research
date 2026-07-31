# POWER_LOTTO Source Audit

## Scope
Read-only repo inspection plus SQLite metadata reads through `file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db?mode=ro&immutable=1`.

## Inspected DB Objects
- `draws`: present. POWER_LOTTO raw/source draw rows observed: 1,924.
- `strategy_prediction_replays`: present. POWER_LOTTO replay rows observed: 36,104.
- `draws_big_lotto_canonical_main`: present as the only DB view whose name/schema contains `canonical`.
- POWER_LOTTO canonical DB view: absent. No `draws_power_lotto_canonical_*` or equivalent POWER_LOTTO canonical view was found in `sqlite_master`.

## Inspected Source Files / Evidence
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/database.py`: `get_canonical_draws()` has a BIG_LOTTO view-backed path and a non-BIG_LOTTO direct `draws WHERE lottery_type = ?` path. This confirms no POWER_LOTTO-specific canonical helper/view path in this file.
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/memory/lessons.md`: governance notes distinguish POWER_LOTTO draw rows from replay rows and document that BIG_LOTTO canonical isolation work was separate.
- `/Users/kelvin/Kelvin-WorkSpace/p297a_read_only_contract_20260630_140000/*`: P297A states the canonical replay DB is inferred as `lottery_api/data/lottery_v2.db`, confirms no POWER_LOTTO canonical view, and records the 27,104 / 36,104 missing `predicted_special` blocker.

## Findings
- Confirmed: POWER_LOTTO raw/source draw data exists in `draws` within the inferred replay DB.
- Confirmed: POWER_LOTTO replay rows exist in `strategy_prediction_replays`.
- Confirmed: no POWER_LOTTO canonical view exists in inspected SQLite views.
- Inferred: the minimum safe unblock path requires defining and validating a POWER_LOTTO canonical source/view contract before full prize-aware replay can be considered. The existing non-BIG_LOTTO `get_canonical_draws()` direct query is not a DB-level POWER_LOTTO canonical view.
- Unknown: whether POWER_LOTTO needs exclusions analogous to BIG_LOTTO contamination families. This audit did not derive or apply a new canonical filter.
