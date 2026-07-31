# P544B — Read-Only Replay Artifact Inventory

> Descriptive inventory only: not betting advice, no prediction, no production or go-live readiness claim.
> Content is read from git blobs at the pinned commit; the working tree, databases, and untracked files are never read.

## Provenance

- head_commit: `28fa79055c9cad6ea182e942570e58d5508462cc`
- scope: `outputs/research/` (tracked blobs only)
- schema: `p544b_readonly_replay_artifact_inventory.v1`
- canonical_payload_digest: `eeb81a115c404c55b04f6e6560fbb91dfff0c3249a1ced8327d8f726177cc2e6`
- chain_integrity: `DIGEST_MISMATCH_FOUND`
- final_classification: `P544B_READONLY_REPLAY_ARTIFACT_INVENTORY_COMPLETE`

## Corpus Summary

- tracked research artifacts: **497** (70,412,124 bytes)
- replay-related artifacts: **361** (48,718,778 bytes)
- JSON parse errors: 0
- replay artifact date range: 20260531 → 20260710

### Classification Tiers (whole corpus)

| classification | files |
|---|---:|
| `non_replay` | 136 |
| `replay_linked` | 1 |
| `replay_named` | 43 |
| `replay_table_consumer` | 105 |
| `replay_term_content` | 212 |

## Replay Lineage (by task id)

| task | files | bytes |
|---|---:|---:|
| `p161` | 2 | 44,948 |
| `p162` | 2 | 10,187 |
| `p163` | 2 | 22,158 |
| `p164` | 2 | 19,916 |
| `p165b` | 2 | 10,350 |
| `p167` | 2 | 26,447 |
| `p171` | 2 | 40,944 |
| `p172` | 2 | 27,297 |
| `p173` | 1 | 4,850 |
| `p174` | 2 | 21,129 |
| `p175` | 2 | 30,972 |
| `p177` | 2 | 22,042 |
| `p178a` | 2 | 20,086 |
| `p179` | 2 | 18,949 |
| `p180` | 2 | 26,085 |
| `p181` | 2 | 26,764 |
| `p181c` | 2 | 13,299 |
| `p182` | 2 | 15,128 |
| `p183` | 2 | 33,084 |
| `p184` | 3 | 21,196 |
| `p185` | 3 | 20,680 |
| `p186` | 2 | 21,397 |
| `p187` | 2 | 23,146 |
| `p188` | 3 | 15,366 |
| `p189` | 2 | 10,804 |
| `p190` | 2 | 29,971 |
| `p191` | 2 | 36,052 |
| `p193` | 2 | 19,933 |
| `p194` | 2 | 22,272 |
| `p195` | 2 | 25,989 |
| `p196` | 3 | 10,727 |
| `p211a` | 2 | 18,092 |
| `p211r` | 2 | 99,364 |
| `p212` | 2 | 13,604 |
| `p213` | 2 | 20,305 |
| `p213b` | 2 | 19,617 |
| `p213c` | 1 | 7,257 |
| `p213d` | 2 | 24,913 |
| `p213e` | 2 | 24,676 |
| `p213f` | 2 | 10,959 |
| `p213g` | 2 | 10,502 |
| `p213h` | 3 | 5,851 |
| `p213i` | 1 | 4,229 |
| `p213k` | 2 | 16,302 |
| `p213l` | 3 | 7,706 |
| `p214` | 2 | 30,839 |
| `p214b` | 2 | 14,832 |
| `p214c` | 2 | 14,157 |
| `p219` | 1 | 8,037 |
| `p221` | 2 | 13,867 |
| `p222` | 2 | 185,975 |
| `p223b` | 2 | 33,067 |
| `p224` | 2 | 17,403 |
| `p224b` | 2 | 6,629 |
| `p227a` | 2 | 36,274 |
| `p227b` | 2 | 11,962 |
| `p227c` | 2 | 127,914 |
| `p229` | 2 | 27,837 |
| `p230a` | 2 | 34,423 |
| `p230b1` | 2 | 19,630 |
| `p231b` | 2 | 13,428 |
| `p232a` | 2 | 122,734 |
| `p233a` | 2 | 29,288 |
| `p233b` | 2 | 10,111 |
| `p235a` | 2 | 20,441 |
| `p236a` | 2 | 28,191 |
| `p237c` | 1 | 18,129 |
| `p238a` | 1 | 17,912 |
| `p238b` | 2 | 62,815 |
| `p240b` | 1 | 14,483 |
| `p241b` | 2 | 23,893 |
| `p242` | 1 | 3,189 |
| `p243a` | 1 | 4,625 |
| `p244c` | 1 | 4,862 |
| `p245b` | 2 | 27,654 |
| `p246` | 2 | 15,588 |
| `p246c` | 2 | 29,418 |
| `p246d` | 2 | 31,928 |
| `p246f` | 1 | 5,596 |
| `p246g` | 1 | 7,966 |
| `p246j` | 2 | 21,211 |
| `p247` | 2 | 14,048 |
| `p247a` | 2 | 12,279 |
| `p247b` | 2 | 5,112 |
| `p247d` | 2 | 17,037 |
| `p247e` | 2 | 5,117 |
| `p247f` | 2 | 11,624 |
| `p249a` | 2 | 17,323 |
| `p249b` | 2 | 7,560 |
| `p250a` | 4 | 137,568 |
| `p251a` | 2 | 15,959 |
| `p251b` | 2 | 76,534 |
| `p251c` | 2 | 26,542 |
| `p251d` | 4 | 11,314 |
| `p251e` | 2 | 10,922 |
| `p254a` | 2 | 7,637 |
| `p254b` | 2 | 15,292 |
| `p255a` | 2 | 38,164 |
| `p255b` | 2 | 39,157 |
| `p255c` | 2 | 14,182 |
| `p255d` | 2 | 15,739 |
| `p256a` | 2 | 37,085 |
| `p257a` | 2 | 107,213 |
| `p257b` | 2 | 11,151 |
| `p257c` | 2 | 8,680 |
| `p258a` | 2 | 23,111 |
| `p258b` | 1 | 8,667 |
| `p258c` | 2 | 25,278 |
| `p258d` | 2 | 23,157 |
| `p258e` | 2 | 12,421 |
| `p258l` | 2 | 15,411 |
| `p258m` | 2 | 21,839 |
| `p258n` | 3 | 23,422 |
| `p258o` | 2 | 6,228 |
| `p258o0` | 2 | 5,239 |
| `p258p` | 2 | 8,041 |
| `p259a` | 2 | 8,297 |
| `p259b` | 2 | 11,133 |
| `p259c` | 1 | 2,571 |
| `p262a` | 2 | 63,166 |
| `p262b` | 2 | 10,144 |
| `p263a` | 2 | 29,551 |
| `p263b` | 2 | 10,022 |
| `p264a` | 2 | 5,780 |
| `p264b` | 2 | 4,971 |
| `p265a` | 2 | 7,679 |
| `p267c` | 2 | 50,726 |
| `p268b` | 2 | 33,599 |
| `p268c` | 2 | 28,865 |
| `p268d1` | 1 | 9,030 |
| `p268d2` | 2 | 8,697 |
| `p269b` | 1 | 25,627 |
| `p269c` | 2 | 6,383 |
| `p269d` | 2 | 13,801 |
| `p271a` | 2 | 52,193 |
| `p271b` | 2 | 41,893 |
| `p271c` | 2 | 22,541 |
| `p271d` | 2 | 33,024 |
| `p271e` | 3 | 13,515 |
| `p271f` | 2 | 28,540 |
| `p271g` | 2 | 34,178 |
| `p271h` | 2 | 44,913 |
| `p271i` | 2 | 39,666 |
| `p271j` | 2 | 38,278 |
| `p271k` | 2 | 19,932 |
| `p271l` | 4 | 161,345 |
| `p272b` | 2 | 31,495 |
| `p273a` | 7 | 31,653,780 |
| `p274a` | 2 | 45,394 |
| `p274b` | 2 | 181,010 |
| `p274c` | 2 | 381,651 |
| `p274d` | 2 | 163,250 |
| `p275b` | 1 | 480,030 |
| `p276b` | 1 | 138,071 |
| `p277a` | 2 | 175,872 |
| `p278a` | 2 | 670,773 |
| `p279b` | 2 | 33,716 |
| `p280amr` | 2 | 60,641 |
| `p280at` | 2 | 127,413 |
| `p280aw` | 2 | 13,202 |
| `p281a` | 2 | 707,019 |
| `p282b` | 2 | 61,047 |
| `p333` | 2 | 1,346,068 |
| `p341a` | 1 | 10,215 |
| `p536c` | 2 | 1,765,233 |
| `p536k` | 2 | 411,972 |
| `p537a` | 2 | 461,814 |
| `p538a` | 2 | 53,576 |
| `p539a` | 2 | 221,888 |
| `p539b` | 2 | 27,273 |
| `p540a` | 2 | 32,382 |
| `p540b` | 2 | 12,350 |
| `p540c` | 2 | 27,734 |
| `p541a` | 2 | 57,630 |
| `p541b` | 2 | 1,135,713 |
| `p542a` | 2 | 2,015,442 |
| `p543a` | 2 | 1,062,109 |
| `p543b` | 1 | 229,734 |
| `p543c` | 2 | 520,915 |
| `p543d` | 1 | 32,517 |
| `unparsed` | 3 | 601,883 |

## Declared Source-Link Integrity (replay-owned links)

- links extracted: **115** (distinct targets: 58)

| verification | links |
|---|---:|
| `digest_mismatch` | 1 |
| `path_not_relative` | 9 |
| `path_not_tracked_at_commit` | 7 |
| `verified_raw_bytes` | 98 |

### Digest Mismatches

- `outputs/research/p273a_prize_aware_inferential_validation_20260615.json` → `analysis/p273a_distinct_ticket_identity_export.py` (declared `ace452ddadbd2409…`) — declared digest matches the file at commit `be6365da9479` (P273A export distinct ticket identities read-only); the file was modified by a later commit, so this is stale-reference drift, not unexplained content

### Upstream Non-Replay Inputs Declared by Replay Artifacts

- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p536c_success_matrix_lift_extension_20260708.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p536k_lift_candidate_shortlist_20260708.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p537a_shortlist_robustness_review_20260709.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-readonly-per-draw-replay-export/outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p536c_success_matrix_lift_extension_20260708.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p536k_lift_candidate_shortlist_20260708.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p537a_shortlist_robustness_review_20260709.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539B-oos-availability-ingest-gap-gate/outputs/research/p539a_readonly_per_draw_replay_export_20260709.json`
- `analysis/p273a_distinct_ticket_identity_export.py`
- `analysis/p273a_primary_window_observed_counts_export.py`
- `analysis/p273a_prize_aware_inferential_validation.py`
- `backups/p188_lottery_v2_backup_20260601_153821.db`
- `lottery_api/data/lottery_v2.db`
- `lottery_api/prize_aware_replay_adapter.py`
- `lottery_api/prize_aware_scorer.py`
- `lottery_api/prospective_capture_ledger.py`
- `scripts/p271k_prospective_capture_ledger_migration_rehearsal.py`
- `scripts/p271l_controlled_deployment_preflight.py`
- `scripts/p271l_readonly_production_schema_inspection.py`
- `tests/test_p271j_prospective_capture_ledger_implementation.py`
- `tests/test_p271k_prospective_capture_ledger_migration_rehearsal.py`
- `tests/test_p271l_controlled_deployment_preflight.py`
- `tests/test_p271l_readonly_production_schema_inspection.py`

## Largest Replay Artifacts

| path | bytes | classification |
|---|---:|---|
| `outputs/research/p273a_distinct_ticket_identity_20260615.json` | 26,707,364 | `replay_table_consumer` |
| `outputs/research/p273a_prize_aware_inferential_validation_20260615.json` | 4,658,516 | `replay_term_content` |
| `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json` | 1,999,750 | `replay_table_consumer` |
| `outputs/research/p536c_success_matrix_lift_extension_20260708.json` | 1,761,713 | `replay_table_consumer` |
| `outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json` | 1,340,027 | `replay_table_consumer` |
| `outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json` | 1,120,976 | `replay_table_consumer` |
| `outputs/research/p543a_scoreboard_stability_packet_20260710.json` | 987,573 | `replay_term_content` |
| `outputs/research/p281a_cross_lottery_prize_aware_validation_20260619.json` | 695,172 | `replay_table_consumer` |
| `outputs/research/p278a_hit_spectrum_data_contract_20260617.json` | 663,647 | `replay_term_content` |
| `outputs/research/big649_measurement_export_20260621.json` | 590,912 | `replay_table_consumer` |

## Unpaired JSON/MD Artifacts (whole corpus)

- `outputs/research/big649_measurement_export_20260621.json`
- `outputs/research/p213g_3star_4star_dry_run_source_parser_rows_20260605.json`
- `outputs/research/p213h_3star_4star_controlled_positional_backfill_audit_20260605.json`
- `outputs/research/p213h_3star_4star_controlled_positional_backfill_rows_20260605.json`
- `outputs/research/p213i_3star_4star_real_source_mismatches_20260605.json`
- `outputs/research/p213i_3star_4star_real_source_rows_20260605.json`
- `outputs/research/p213l_3star_4star_controlled_missing_row_ingestion_audit_20260605.json`
- `outputs/research/p213l_3star_4star_controlled_missing_row_ingestion_rows_20260605.json`
- `outputs/research/p214b_3star_4star_straight_play_readonly_diagnostic_rows_20260605.json`
- `outputs/research/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_rows_20260605.json`
- `outputs/research/p219_external_method_diagnostic_sweep_plan_20260605.md`
- `outputs/research/p237c_nist_randomness_audit_tripwire_design_20260604.md`
- `outputs/research/p238a_nist_randomness_audit_artifact_only_build_plan_20260604.md`
- `outputs/research/p258n_d3_strategy_status_audit_payload_20260609.json`
- `outputs/research/p259c_hit_highlighting_20260609.json`
- `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.ledger.json`
- `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.md`
- `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.summary.json`
- `outputs/research/p268d1_draw_order_registry_freeze_20260610.json`
- `outputs/research/p271e_scoped_prize_aware_replay_adapter_smoke_20260612.json`
- `outputs/research/p341a_integration_report_20260702.md`

## Limitations

- Descriptive inventory only: no statistical, predictive, betting, or deployment claim.
- Classification tiers are heuristic (filename/content/link based) and may over-include prose mentions of 'replay'.
- Link extraction pairs a path with a digest only when both sit alone in one JSON object under a bare digest key; qualified digests (e.g. production_db_sha256_before) and multi-value objects are never verified.
- Only artifacts tracked at head_commit are inventoried; untracked working-tree artifacts are out of scope.
- Declared paths that are expected to be untracked (e.g. database files) report path_not_tracked_at_commit by design.
- verified_embedded_self_declared means the declared digest is a canonical payload digest restated inside the target, not a raw-byte hash match.

## Recommended Next Task

Owner decision on remediating any digest_mismatch/unpaired findings and on whether untracked working-tree research artifacts should be landed or archived.
