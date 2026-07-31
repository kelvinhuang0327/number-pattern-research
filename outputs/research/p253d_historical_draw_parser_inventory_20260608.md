# P253D — Historical Draw Parser Inventory

**Date:** 2026-06-08 11:30:55  
**Task:** P253D  
**Classification:** HISTORICAL_DRAW_PARSER_INVENTORY_COMPLETE  

## Executive Summary

P253D inventories historical draw parser scripts, queries the DB for positional coverage, and adjudicates 3_STAR/4_STAR status. Key findings: **3_STAR and 4_STAR both have 100% positional coverage** (draw order preserved in `numbers_positional`). BIG_LOTTO/POWER_LOTTO/DAILY_539 have 0% positional (not needed). M1 gap is a unified parser SSOT module — **READY_FOR_NEXT_TASK** (Type C, LOW risk).

## Parser / Source Inventory

| Path | Classification | Lottery Types | Positional Support |
|------|---------------|--------------|-------------------|
| `lottery_api/routes/ingest.py` | ACTIVE_PARSER | BIG_LOTTO, POWER_LOTTO, DAILY_539 | False |
| `scripts/p213g_3star_4star_dry_run_source_parser.py` | OFFICIAL_DRY_RUN_PARSER | 3_STAR, 4_STAR | True |
| `scripts/p213i_3star_4star_real_source_dry_run_validation.py` | OFFICIAL_DRY_RUN_PARSER | 3_STAR, 4_STAR | True |
| `scripts/p213h_3star_4star_controlled_positional_backfill.py` | CONTROLLED_APPLY_COMPLETE | 3_STAR, 4_STAR | True |
| `scripts/p213l_3star_4star_controlled_missing_row_ingestion.py` | CONTROLLED_APPLY_COMPLETE | 3_STAR, 4_STAR | True |
| `tools/upload_big_lotto_csv.py` | HISTORICAL_IMPORT_SCRIPT | BIG_LOTTO | False |
| `tools/upload_daily539_txt.py` | HISTORICAL_IMPORT_SCRIPT | DAILY_539 | False |
| `tools/upload_lottery_data.py` | HISTORICAL_IMPORT_SCRIPT | BIG_LOTTO, POWER_LOTTO, DAILY_539 | False |
| `scripts/p214b_3star_4star_straight_play_readonly_diagnostic.py` | ARCHIVED_OR_EXPLORATORY_DEFER | 3_STAR, 4_STAR | True |
| `scripts/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py` | ARCHIVED_OR_EXPLORATORY_DEFER | 3_STAR, 4_STAR | True |

## DB Positional Coverage Table

| Lottery Type | Draw Rows | has_positional | null_positional | Coverage |
|-------------|----------|---------------|-----------------|---------|
| `38_LOTTO` | 1774 | 0 | 1774 | 0.0% |
| `39_LOTTO` | 4890 | 0 | 4890 | 0.0% |
| `3_STAR` | 5850 | 5850 | 0 | 100.0% |
| `49_LOTTO` | 2130 | 0 | 2130 | 0.0% |
| `4_STAR` | 5850 | 5850 | 0 | 100.0% |
| `BIG_LOTTO` | 22239 | 0 | 22239 | 0.0% |
| `BIG_LOTTO_BONUS` | 11941 | 0 | 11941 | 0.0% |
| `DAILY_539` | 5882 | 0 | 5882 | 0.0% |
| `DOUBLE_WIN` | 1782 | 0 | 1782 | 0.0% |
| `LOTTO_6_38` | 111 | 0 | 111 | 0.0% |
| `POWER_LOTTO` | 1917 | 0 | 1917 | 0.0% |

## 3_STAR Positional Status

- **Status:** COMPLETE  
- **Draw rows:** 5850  
- **Coverage:** 100.0%  
- **Draw order preserved:** True  
- **Rows where positional ≠ sorted:** 4525  
- **Source:** 40 Taiwan Lottery CSV files, 獎號1..N columns (P213I verified)  
- **Backfill:** P213H (7101 updated) + P213L (4599 inserted) = 100% complete  

> **Power caveat (P214B):** At N=5850, expected exact-match hits = 5.85. Bonferroni threshold requires ~14 hits. Exact-match power is **MARGINAL** — per-position analysis TRACTABLE.

## 4_STAR Positional Status

- **Status:** COMPLETE  
- **Draw rows:** 5850  
- **Coverage:** 100.0%  
- **Draw order preserved:** True  
- **Rows where positional ≠ sorted:** 5427  
- **Source:** Same 40 CSV files as 3_STAR; P213H+P213L applied  

> **Power caveat (P214B):** At N=5850, expected exact-match hits = 0.585. 4_STAR exact-match is **INOPERABLE** — per-position analysis TRACTABLE only.

## Straight-Play Storage Caveats

- `numbers` column stores **sorted** digits for all lottery types (correct for pool draws).
- For 3_STAR/4_STAR straight-play, **`numbers_positional` must be used** — `numbers` loses draw order.
- Future parser SSOT must enforce: `numbers`=sorted canonical, `numbers_positional`=draw-order for 3_STAR/4_STAR, `None` for pool-draw games.

## Future Parser SSOT Readiness

**Decision: READY_FOR_NEXT_TASK**  

3_STAR and 4_STAR positional data is COMPLETE (100% coverage, draw order preserved). Source format is understood (40 CSV files, 獎號1..N columns, P213I). BIG_LOTTO/POWER_LOTTO/DAILY_539 use ad-hoc scripts without shared schema contract. The M1 gap is now clearly a unified parser SSOT module, not data recovery. No blocked prerequisites remain.

**SSOT module should implement:**

- Define ParsedDraw dataclass: draw_id, date, lottery_type, numbers (sorted), numbers_positional (draw-order for 3_STAR/4_STAR, None otherwise), special
- Implement parse_taiwan_lottery_csv(path, lottery_type) -> List[ParsedDraw]
- Implement parse_taiwan_lottery_txt(path, lottery_type) -> List[ParsedDraw]
- Implement parse_ingest_api_response(data, lottery_type) -> ParsedDraw
- Enforce: numbers always sorted; numbers_positional set for 3_STAR/4_STAR only
- Pure stdlib only; no DB connection inside module
- Schema contract: positional=None for pool-draw games (BIG_LOTTO etc.)

## Recommended Next Task

**P253E — Historical Draw Parser SSOT (M1, Type C implementation)**  
Authorization phrase: `Authorize P253E M1 historical draw parser SSOT`  
Alternative: **HOLD** if parser standardization is not an immediate priority.

## Non-Actions

- Did **not** modify any parser, DB, registry, API, strategy, or artifact.
- Did **not** run any DB write query.
- Did **not** re-run P213H/P213L (already applied).

## Explicit No-Overclaim Statement

> A 100% positional-coverage result means data is available for straight-play > analysis. It does **not** imply any predictive edge. > GREEN randomness does not imply any exploitable signal. No betting advice.

## Compliance

- **No DB write.**  - **No registry mutation.**  - **No strategy promotion.**  - **No betting advice.**

---
*Generated by P253D — Historical Draw Parser Inventory*