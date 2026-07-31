# P19 Replay Product Follow-Up Decision - 2026-05-11

## 1. Goal

Turn the P18 replay product gap inventory into a concrete follow-up decision.

This round is docs / governance only:

- no DB writes
- no replay backfill
- no replay row generation
- no scheduler or cron changes
- no strategy promotion, retirement, or reactivation actions
- no runtime code, dashboard, endpoint, registry adapter, package, or config changes

## 2. Main State

- `main` HEAD: `62ad549`
- latest commit message: `docs(replay): record P18 replay product gap inventory (#48)`

## 3. Artifact Verification

All three prerequisite artifacts are present on main:

- `outputs/replay/p0_governance_baseline_report_20260511.md`
- `outputs/replay/p17_strategy_history_replay_product_roadmap_20260511.md`
- `outputs/replay/p18_replay_product_gap_inventory_20260511.md`

P18 markers confirmed in the inventory report:

- `P18_REPLAY_PRODUCT_GAP_INVENTORY_REVIEWED`
- `P18_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P18_NO_PROMOTION_ACTION_CONFIRMED`

## 4. P18 Gap Inventory Summary

P18 established the current product state with read-only evidence:

- lifecycle metadata: 16 strategies total
- ONLINE: 6
- REJECTED: 4
- OBSERVATION: 1
- RETIRED: 5
- OFFLINE: 0
- replay history rows: 460 total
- PREDICTED: 420
- REPLAY_ERROR: 40

The critical result is unchanged:

- the 6 ONLINE strategies have replay rows
- the 10 non-ONLINE strategies still have 0 replay rows
- OFFLINE still has 0 canonical strategies and 0 replay rows

## 5. Lifecycle Metadata Summary

The lifecycle registry is complete enough to expose the gap honestly:

- `biglotto_deviation_2bet`
- `biglotto_triple_strike`
- `daily539_f4cold`
- `daily539_markov_cold`
- `power_orthogonal_5bet`
- `power_precision_3bet`

These are the only executable ONLINE strategies.

The non-ONLINE set remains:

- REJECTED: `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `power_shlc_midfreq`, `p1_deviation_2bet_539`
- OBSERVATION: `h6_gate_mk20_ew85`
- RETIRED: `acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`

## 6. Replay History Availability Summary

Replay history is still ONLINE-only:

| strategy_id | lifecycle_status | rows |
|---|---|---:|
| `biglotto_deviation_2bet` | ONLINE | 70 |
| `biglotto_triple_strike` | ONLINE | 70 |
| `daily539_f4cold` | ONLINE | 90 |
| `daily539_markov_cold` | ONLINE | 90 |
| `power_orthogonal_5bet` | ONLINE | 70 |
| `power_precision_3bet` | ONLINE | 70 |

No non-ONLINE strategy has any replay rows.

## 7. Non-ONLINE History Gap Conclusion

The gap is real and still unresolved:

- non-ONLINE strategies are visible in lifecycle metadata
- non-ONLINE strategies are not represented in replay history rows
- the current UI is correctly showing honest empty state
- the current API is correctly returning zero-row history for those filters

This is not a rendering bug and not a data corruption symptom. It is a product coverage gap.

## 8. Gap Type Classification

### Data gap

The underlying replay table lacks rows for 10 non-ONLINE strategies.

### UI gap

There is no UI failure. The honest empty state is correct and should remain.

### Governance gap

The gap cannot be closed by directly writing production data or running an uncontrolled backfill.

### Fixture gap

The next useful artifact must be a fixture-only replay spec, not a production mutation.

## 9. P17 Roadmap vs P18 Inventory Alignment

P17 predicted the right next direction:

- lifecycle metadata visibility is not the same as replay row availability
- non-ONLINE history must be handled with no-write discipline
- fixture-only work is the appropriate bridge before any real data population

P18 confirmed that prediction with concrete evidence:

- 16 lifecycle strategies exist
- only 6 have replay rows
- 10 non-ONLINE strategies remain empty

So P17 and P18 are aligned. P18 did not invalidate the roadmap; it sharpened it.

## 10. Next Step Decision

The next step should be:

**P20 = non-ONLINE replay fixture spec**

The P20 spec must be:

- fixture-only
- no production DB write
- no backfill
- no lifecycle status changes
- no claim that a strategy has edge
- no claim that a strategy has been promoted or reactivated

The only acceptable output shape is a no-write dry-run design that explains how non-ONLINE replay history could be represented as fixtures later.

## 11. No-Write Evidence

Read-only evidence used in this round:

- `git log` / `git status` / artifact existence checks
- P18 report review
- P17 roadmap review
- `scripts/report_strategy_lifecycle_registry.py --json`
- targeted lifecycle smoke suite

The registry CLI reports:

- `no_db_write: true`
- `no_db_write_note: All data sourced from in-memory registry. No sqlite3 connection opened.`

## 12. No-Backfill Evidence

No backfill was run in this round.

The observed gap still exists:

- 10 non-ONLINE strategies have 0 replay rows
- replay history remains ONLINE-only
- the inventory report already documents the gap

That means the follow-up decision should stay on the spec side, not the apply side.

## 13. No-Promotion Evidence

No promotion, retirement, reactivation, or strategy action was performed.

The endpoint contract still forbids:

- non-ONLINE → executable transitions
- replay backfill
- scheduler triggers
- DB write paths

## 14. Remaining Local Runtime Dirt

Local workspace still contains known runtime artifacts from earlier work:

- `data/lottery_v2.db`
- `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json`

They were not modified or staged in this task.

## 15. Risks and Limitations

- OFFLINE remains unpopulated, so the lifecycle taxonomy still has a visible gap.
- The product can describe the problem, but not resolve it without a separate fixture spec.
- A future fixture path must not quietly become a production backfill path.
- If P20 blurs the line between fixtures and applied history, it will overclaim product completeness.

## 16. P20 Recommendation

P20 should produce a non-ONLINE replay fixture spec that defines:

- which lifecycle states are eligible for fixture-only representation
- how fixture rows are labeled
- how provenance is preserved
- how the UI should keep honest empty state until fixtures exist
- how to keep production DB untouched

## 17. Final Markers

- `P19_REPLAY_PRODUCT_FOLLOW_UP_REVIEWED`
- `P19_P18_MARKER_CONTINUITY_CONFIRMED`
- `P19_NON_ONLINE_HISTORY_GAP_CONFIRMED`
- `P19_FIXTURE_ONLY_NEXT_STEP_RECOMMENDED`
- `P19_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P19_NO_PROMOTION_ACTION_CONFIRMED`

