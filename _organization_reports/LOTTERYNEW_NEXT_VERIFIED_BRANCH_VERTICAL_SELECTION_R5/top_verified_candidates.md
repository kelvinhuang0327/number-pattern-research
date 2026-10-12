# R5 Top Verified Candidates

The bounded shortlist was chosen from corrected verified-function authorities by functional priority, small exact deltas, and safe implementation potential. No score was invented.

| Rank | Candidate | Classification | Decision | Load-bearing evidence |
|---:|---|---|---|---|
| 1 | `cand_006_chore/p2_controlled_replay_backfill_dryrun_20260515` | `AUDIT_OR_RESEARCH_TOOL` | `NEXT_SINGLE_VERTICAL` | Read-only SQLite URI; explicit CLI entrypoint and output paths; live `get_adapter("ts3_regime_3bet")` consumer; four missing paths are collision-free. |
| 2 | `cand_005_chore/ingestion_pipeline_diagnostic_20260515` | `AUDIT_OR_RESEARCH_TOOL` | Excluded | Hard-coded workspace and production DB; no focused tests or isolated CLI contract. |
| 3 | `cand_004_chore/fix_drift_guard_test_fixtures_20260520` | Test governance | Excluded | Exact source/target diff would roll the current database baseline back to 460 rows. |
| 4 | `cand_109_p96_governance_baseline_repair` | Test governance | Excluded | Six of seven paths already match; the only remaining diff removes post-P188 baselines. |
| 5 | `cand_082_p18_replay_ui_timestamp_display` | UI | Excluded | Requires protected dirty `index.html` and contains stale production-DB row assertions. |

## Selection boundary

The selected candidate is not a production runtime capability. It is a bounded, read-only audit CLI. Any later production replay-row insert remains a separate `OWNER_DECISION_REQUIRED` task.

The source branch also contains historical report/output examples. They are evidence only and must not be copied as current results. The Worker must generate fresh outputs only inside an authorized runtime sandbox.

