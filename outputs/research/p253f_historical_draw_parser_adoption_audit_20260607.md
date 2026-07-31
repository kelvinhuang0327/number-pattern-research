# P253F — Historical Draw Parser SSOT Adoption Audit

**Date:** 2026-06-07 22:17:48  
**Task:** P253F  
**Classification:** HISTORICAL_DRAW_PARSER_ADOPTION_AUDIT_COMPLETE  

## Executive Summary

P253F audits adoption of the P253E Historical Draw Parser SSOT. The module `lottery_api/utils/historical_draw_parser.py` is verified pure, safe, and complete. Repository scan found **0 active duplicates requiring migration**: completed controlled-apply scripts are frozen, production `common.py` uses a separate semantic domain for API routing, and legacy upload tools are deferred. No M1 migration task is warranted.

## P253E SSOT Verification

| Check | Result |
|-------|--------|
| Module exists | True |
| Module pure/safe (no DB/registry/numpy imports) | True |
| Artifact exists | True |
| Artifact classification match | True |
| Tests exist | True |

## Parser Adoption Matrix

| Path | Classification | Recommended Action |
|------|---------------|-------------------|
| `lottery_api/utils/historical_draw_parser.py` | ALREADY_USING_SSOT | NONE — is the SSOT |
| `tests/test_p253e_historical_draw_parser_ssot.py` | ALREADY_USING_SSOT | NONE — already SSOT |
| `lottery_api/common.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — intentional: common.py normalize_lottery_type se |
| `lottery_api/routes/prediction.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — production route, different semantic domain |
| `lottery_api/routes/ingest.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — active production route. Future enhancement: cou |
| `lottery_api/routes/data.py` | SEPARATE_PRODUCTION_DOMAIN | NO CHANGE — production data route, different semantic domain |
| `scripts/p213g_3star_4star_dry_run_source_parser.py` | CONTROLLED_APPLY_DO_NOT_EDIT | DO NOT EDIT — completed P-numbered dry-run artifact. Histori |
| `scripts/p213i_3star_4star_real_source_dry_run_validation.py` | CONTROLLED_APPLY_DO_NOT_EDIT | DO NOT EDIT — completed P-numbered dry-run; frozen historica |
| `scripts/p213h_3star_4star_controlled_positional_backfill.py` | CONTROLLED_APPLY_DO_NOT_EDIT | DO NOT EDIT — completed controlled apply. Do not re-run with |
| `scripts/p213l_3star_4star_controlled_missing_row_ingestion.py` | CONTROLLED_APPLY_DO_NOT_EDIT | DO NOT EDIT — completed controlled apply. Do not re-run with |
| `tools/upload_big_lotto_csv.py` | HISTORICAL_IMPORT_SCRIPT_DEFER | DEFER — legacy upload tool; no active production dependency. |
| `tools/upload_daily539_txt.py` | HISTORICAL_IMPORT_SCRIPT_DEFER | DEFER — legacy upload tool, low priority |
| `tools/upload_lottery_data.py` | HISTORICAL_IMPORT_SCRIPT_DEFER | DEFER — legacy general upload tool |
| `scripts/p214b_3star_4star_straight_play_readonly_diagnostic.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — completed research artifact; not a parser |
| `scripts/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — completed research artifact; not a parser |
| `scripts/p227c_star_box_play_dryrun_scan.py` | ARCHIVED_OR_EXPLORATORY_DEFER | DEFER — completed historical artifact; not a parser |

## Active Duplicate Logic

**Count: 0** — No active callers with duplicate parser logic requiring migration.

## Separate Production Domain (DO NOT MIGRATE)

- `lottery_api/common.py` — Production API helper. Has its own normalize_lottery_type() for mapping frontend/API input
- `lottery_api/routes/prediction.py` — Production prediction route. Uses common.normalize_lottery_type for incoming API request n
- `lottery_api/routes/ingest.py` — Production ingest API route. Fetches latest draws from official Taiwan Lottery site. Uses 
- `lottery_api/routes/data.py` — Production data route. Uses common.normalize_lottery_type for API routing. Not a source-fi

`common.py` has its own `normalize_lottery_type()` for API routing normalization (mapping frontend/API input strings to DB canonical types). This is **intentionally distinct** from `historical_draw_parser.normalize_lottery_type()` which resolves file-format aliases.

## Controlled-Apply Scripts (DO NOT EDIT)

- `scripts/p213g_3star_4star_dry_run_source_parser.py`
- `scripts/p213i_3star_4star_real_source_dry_run_validation.py`
- `scripts/p213h_3star_4star_controlled_positional_backfill.py`
- `scripts/p213l_3star_4star_controlled_missing_row_ingestion.py`

These P-numbered scripts are completed controlled-apply artifacts. Their inline positional parsing logic captures the exact computation used in the original backfill. Do not edit.

## Historical Import Scripts (Defer)

- `tools/upload_big_lotto_csv.py` — Legacy manual CSV import for BIG_LOTTO. Uses stale DB path (lottery.db, not lott
- `tools/upload_daily539_txt.py` — Legacy manual TXT import for DAILY_539. Uses stale DB path. No positional suppor
- `tools/upload_lottery_data.py` — General legacy data upload tool. No schema contract. No positional support.

Legacy upload tools use stale DB paths (lottery.db not lottery_v2.db) and have no active production consumers. Deferred.

## Deferred Exploratory Scripts

- `scripts/p214b_3star_4star_straight_play_readonly_diagnostic.py`
- `scripts/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py`
- `scripts/p227c_star_box_play_dryrun_scan.py`

## Recommended Next Task

**P253G — M8 Feature Bottleneck Report Inventory (Type B read-only)**  
Zero active duplicates means no M1 migration task is needed. New parser scripts should import `historical_draw_parser` going forward.  
Alternative: **HOLD** if no new parser work is imminent.

## Non-Goals

- Does **not** migrate any existing parser, DB, registry, API, strategy, or artifact
- Does **not** modify common.py normalize_lottery_type
- Does **not** re-run any controlled-apply script
- Does **not** claim complete positional coverage implies predictive edge

## Explicit No-Overclaim Statement

> Parser SSOT vocabulary is an interpretability tool. > A complete positional coverage result does **not** imply a deployable prediction edge. > GREEN randomness does not imply any exploitable signal. No betting advice.

## Compliance

- **No DB write.**  - **No registry mutation.**  - **No strategy promotion.**  - **No betting advice.**

---
*Generated by P253F — Historical Draw Parser SSOT Adoption Audit*