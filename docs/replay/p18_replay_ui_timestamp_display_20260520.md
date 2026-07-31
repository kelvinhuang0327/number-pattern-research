# P18 — Replay UI Timestamp Badge Display

**Date:** 2026-05-20  
**Phase:** P18_REPLAY_UI_TIMESTAMP_DISPLAY  
**Classification:** P18_REPLAY_UI_TIMESTAMP_DISPLAY_READY

---

## 1. Objective

Add prediction timestamp display to the replay history drilldown (expanded row
detail), allowing users to see:
1. The data cutoff date used when the prediction was made (`prediction_cutoff_date`)
2. When the replay row was created or backfilled (`prediction_generated_at`)
3. A `補登 metadata` label on P14D rows whose timestamps were backfilled by P17B

---

## 2. UI Files Changed

| File | Change type |
|------|-------------|
| `index.html` | CSS + JS: timestamp badges, truth-level badges, `rpRenderDetail` update |

No new files created in the frontend. Changes are additive-only.

---

## 3. API Fields Verified

All fields confirmed present in `GET /api/replay/history` response:

| Field | ts3_regime_3bet | biglotto_triple_strike | biglotto_deviation_2bet |
|-------|-----------------|------------------------|------------------------|
| `prediction_cutoff_date` | `2026/05/12` ✓ | `2026/05/12` ✓ | `2026/05/12` ✓ |
| `prediction_generated_at` | `2026-05-20T13:33:33Z` ✓ | `2026-05-20T13:01:31Z` ✓ | `2026-05-20T13:01:31Z` ✓ |
| `truth_level` | `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` ✓ | `BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED` ✓ | same ✓ |
| `display_status` | `SHOW_REPLAY_RESULT` ✓ | ✓ | ✓ |

No API patch was needed — all fields were already present from P17.

---

## 4. Display Rules

### In `rpRenderDetail` (expanded row detail):

| Condition | Display |
|-----------|---------|
| `prediction_cutoff_date` has value | `預測基準日：2026/05/12` (blue bold) |
| `prediction_cutoff_date` is NULL | `預測基準日未知（legacy）` (grey, small) |
| `prediction_generated_at` has value | `建立時間：2026-05-20 13:33` |
| `prediction_generated_at` is NULL | `建立時間：—` |
| `truth_level = BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` | `補登 metadata` badge appended to 建立時間 |

### New truth-level badges in `renderTruthLevelBadge`:

| truth_level | Badge | Color |
|-------------|-------|-------|
| `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` | `BIG LOTTO BACKFILL` | Blue (#0969da) |
| `BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED` | `BIG LOTTO BACKFILL (P16)` | Green (#1a7f37) |

---

## 5. Legacy Fallback Behavior

When `prediction_cutoff_date` is NULL (which would only occur if P17B had not
been applied), the UI displays:

```
預測基準日未知（legacy）
```

After P17B, all 1500 P14D ts3_regime_3bet rows have `prediction_cutoff_date`
populated, so this fallback is currently not triggered for P14D rows. It acts
as a safe guard for any future rows that may lack the field.

---

## 6. Metadata Backfill Semantics

The `補登 metadata` label appears when `truth_level = 'BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED'`.

This tells the user:
- `prediction_cutoff_date` = the actual historical data cutoff (accurate)
- `prediction_generated_at` = when the P17B backfill script ran (2026-05-20),
  **NOT** the original 2026-05-20 prediction time

The label prevents users from misinterpreting the `建立時間` as the original
prediction generation time.

---

## 7. Tests Run

| Test file | Tests | Result |
|-----------|-------|--------|
| `test_p18_replay_ui_timestamp_display.py` | 22 | PASS |
| Full suite (284 + 22 P18) | 306 | PASS |

---

## 8. Production Rows

Production rows: **4960** (unchanged — no DB writes).

---

## 9. Remaining UX Gaps

- The timestamp badge is only visible in the **drilldown** (expanded detail
  row), not in the table summary row. A future P18B could add a compact
  timestamp column or tooltip to the summary row.
- `prediction_generated_at` for P17B rows shows the backfill time
  (2026-05-20). A future enhancement could store the original prediction
  context (e.g., "Prediction regenerated from P14D replay run").
- No timezone conversion is applied — times are shown in UTC as-is.

---

## 10. Next Recommendation

### P19 — POWER_LOTTO Replay Backfill

Apply the P14B→P14C→P14D pipeline to POWER_LOTTO ONLINE strategies to extend
replay store coverage beyond BIG_LOTTO. The same timestamp pattern would apply.

### P18B (Optional) — Timestamp Column in Summary Row

Add a compact `prediction_cutoff_date` display to the table summary row for
at-a-glance visibility, without expanding the drilldown.
