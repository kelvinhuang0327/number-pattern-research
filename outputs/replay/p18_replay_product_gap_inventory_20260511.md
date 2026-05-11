# P18 Replay Product Gap Inventory - 2026-05-11

## 1. Goal

Inventory the gap between lifecycle metadata and replay history availability, using read-only evidence only.

Scope for this round:

- docs and governance only
- no DB writes
- no replay backfill
- no promotion or retirement actions
- no runtime code changes

## 2. Main State and Verified Artifacts

- `main` HEAD: `f318e4b`
- PR #47: merged
- Verified artifact: `outputs/replay/p0_governance_baseline_report_20260511.md`
- Verified artifact: `outputs/replay/p17_strategy_history_replay_product_roadmap_20260511.md`

Baseline markers confirmed in the P0 report:

- `P0_DB_DIRT_ROOT_CAUSE`
- `P0_PR_QUEUE_FINAL`
- `P1_DASHBOARD_UI_VERIFIED`
- `P1_OFFLINE_DECISION_DRAFT_READY`

## 3. Lifecycle Metadata Summary

The registry snapshot contains 16 strategies:

- ONLINE: 6
- REJECTED: 4
- OBSERVATION: 1
- RETIRED: 5
- OFFLINE: 0

Executable strategies are the 6 ONLINE entries:

- `biglotto_deviation_2bet`
- `biglotto_triple_strike`
- `daily539_f4cold`
- `daily539_markov_cold`
- `power_orthogonal_5bet`
- `power_precision_3bet`

Non-executable strategies are the remaining 10 entries:

- REJECTED: `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `power_shlc_midfreq`, `p1_deviation_2bet_539`
- OBSERVATION: `h6_gate_mk20_ew85`
- RETIRED: `acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`

## 4. Replay History Availability Summary

Read-only DB inspection shows 460 replay rows total:

- PREDICTED: 420
- REPLAY_ERROR: 40

Replay rows exist for exactly 6 strategies, and all 6 are ONLINE:

| strategy_id | lifecycle_status | rows | predicted | replay_error |
|---|---|---:|---:|---:|
| `biglotto_deviation_2bet` | ONLINE | 70 | 70 | 0 |
| `biglotto_triple_strike` | ONLINE | 70 | 70 | 0 |
| `daily539_f4cold` | ONLINE | 90 | 70 | 20 |
| `daily539_markov_cold` | ONLINE | 90 | 70 | 20 |
| `power_orthogonal_5bet` | ONLINE | 70 | 70 | 0 |
| `power_precision_3bet` | ONLINE | 70 | 70 | 0 |

No non-ONLINE strategy currently has any replay rows.

## 5. Missing-History Inventory

These 10 lifecycle strategies have 0 replay rows:

| strategy_id | lifecycle_status | rows | gap classification |
|---|---|---:|---|
| `biglotto_ts3_acb_4bet` | REJECTED | 0 | missing replay history |
| `biglotto_ts3_markov_freq_5bet` | REJECTED | 0 | missing replay history |
| `power_shlc_midfreq` | REJECTED | 0 | missing replay history |
| `p1_deviation_2bet_539` | REJECTED | 0 | missing replay history |
| `h6_gate_mk20_ew85` | OBSERVATION | 0 | missing replay history |
| `acb_1bet` | RETIRED | 0 | missing replay history |
| `acb_markov_midfreq` | RETIRED | 0 | missing replay history |
| `acb_markov_midfreq_3bet` | RETIRED | 0 | missing replay history |
| `midfreq_acb_2bet` | RETIRED | 0 | missing replay history |
| `midfreq_fourier_2bet` | RETIRED | 0 | missing replay history |

OFFLINE is currently a taxonomy state only:

- OFFLINE lifecycle strategies: 0
- OFFLINE replay rows: 0

## 6. Product Interpretation

The product gap is now well bounded:

1. lifecycle metadata is complete and visible
2. replay history is complete only for executable ONLINE strategies
3. non-ONLINE strategies are correctly shown as honest empty state
4. OFFLINE is not yet populated, so there is no OFFLINE history to render
5. any future fill-in for non-ONLINE strategies must start with a no-write fixture spec, not a production backfill

That means the current UI and API behavior are correct for now:

- lifecycle dashboard can show all 16 strategies
- history endpoint can return zero rows for non-ONLINE filters without error
- missing history is a product gap, not a data corruption symptom

## 7. No-Write Evidence

Read-only commands used in this round:

- `scripts/report_strategy_lifecycle_registry.py --json`
- direct `sqlite3` SELECT queries against `lottery_api/data/lottery_v2.db`
- lifecycle endpoint contract review

The registry CLI explicitly reports:

- `no_db_write: true`
- `no_db_write_note: All data sourced from in-memory registry. No sqlite3 connection opened.`

The DB inspection was read-only and grouped by strategy and replay status only.

## 8. No-Backfill Evidence

No backfill script was run against production data.

Observed facts support the no-backfill position:

- 10 non-ONLINE strategies still have 0 replay rows
- the history endpoint returns an honest empty state for non-ONLINE filters
- replay rows exist only for the 6 ONLINE strategies already considered executable

## 9. No-Promotion Evidence

No lifecycle promotion or retirement action was performed.

The endpoint contract and registry rules still enforce:

- GET only
- no DB write
- no replay backfill
- no scheduler trigger
- no non-ONLINE promotion into executable state

## 10. Test and Smoke Results

Targeted lifecycle suite:

- `143 passed` with `uv run --with pytest ...`

CLI smoke:

- `scripts/report_strategy_lifecycle_registry.py --json` completed successfully
- marker returned: `P3_LIFECYCLE_REPORT_CLI_READY`

## 11. Remaining Local Runtime Dirt

None in this clean repo session.

The working tree was clean before this report was added, and no DB file or runtime artifact was mutated in this round.

## 12. Risks and Limitations

- OFFLINE remains unpopulated, so this inventory is about a missing lifecycle state as much as a missing replay history.
- Non-ONLINE strategies do not yet have a fixture-only history path.
- Any future backfill or row generation must be gated by a separate no-write manifest and explicit approval.

## 13. Next Direction

The next useful step is a fixture-only, no-write spec for non-ONLINE replay rows:

- define which non-ONLINE rows can be represented as evidence-only fixtures
- define how honest empty states should remain visible until fixtures exist
- keep production DB and runtime code untouched

## 14. Final Markers

- `P18_REPLAY_PRODUCT_GAP_INVENTORY_REVIEWED`
- `P18_LIFECYCLE_METADATA_16_CONFIRMED`
- `P18_NON_ONLINE_HISTORY_GAP_CONFIRMED`
- `P18_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P18_NO_PROMOTION_ACTION_CONFIRMED`

