# P268B: Official drawNumberAppear Ingestion + Positional-Bias Audit Prototype

Generated: 2026-06-10T13:10:57.521835+00:00

## P267C Conclusion Boundary
P267C (M3+ revalidation) found NO_VALIDATED_M3_EDGE across 36/36 cells for the existing replay-backed strategy family. This does NOT close the broader success-rate research line, and does NOT cover the official drawNumberAppear field, which is absent from the replay-backed family and from the internal sorted-number draws table.

## P268A Top-1 Rationale
P268A-S ranked 'official drawNumberAppear draw-order positional bias test' as the Top-1 hit-rate candidate because it is a genuinely new official field (physical draw-order sequence) not present in, or derivable from, the internal sorted-number `draws` table. winnerCount/prize-distribution (Direction B) is payout/EV-only and is explicitly excluded from this task.

## Data Source Endpoint Summary
- **BIG_LOTTO**: `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result` (array key `lotto649Res`) — status=OK, records_fetched=17
- **POWER_LOTTO**: `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result` (array key `superLotto638Res`) — status=OK, records_fetched=17
- **DAILY_539**: `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Daily539Result` (array key `daily539Res`) — status=OK, records_fetched=52
- **3_STAR**: `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/3DResult` (array key `lotto3DRes`) — status=OK, records_fetched=52
- **4_STAR**: `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/4DResult` (array key `lotto4DRes`) — status=OK, records_fetched=52

## Sample Scope
- **months_sampled**: ['2026-04', '2026-05']
- **games_sampled**: ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539', '3_STAR', '4_STAR']
- **page_size**: 31
- **note**: Bounded prototype sample: 2 calendar months per game, no full-history backfill.

## Parse Success/Failure Counts
### BIG_LOTTO
- records sampled: 17
- drawNumberAppear present: 17
- parsed as ordered int sequence: 17
- correct length (7): 17
- drawNumberSize present: 17
- sorted(drawNumberAppear) == drawNumberSize (main numbers): 17
- parse failures: 0

### POWER_LOTTO
- records sampled: 17
- drawNumberAppear present: 17
- parsed as ordered int sequence: 17
- correct length (7): 17
- drawNumberSize present: 17
- sorted(drawNumberAppear) == drawNumberSize (main numbers): 17
- parse failures: 0

### DAILY_539
- records sampled: 52
- drawNumberAppear present: 52
- parsed as ordered int sequence: 52
- correct length (5): 52
- drawNumberSize present: 52
- sorted(drawNumberAppear) == drawNumberSize (main numbers): 52
- parse failures: 0

### 3_STAR
- records sampled: 52
- drawNumberAppear present: 52
- parsed as ordered int sequence: 52
- correct length (3): 52
- parse failures: 0

### 4_STAR
- records sampled: 52
- drawNumberAppear present: 52
- parsed as ordered int sequence: 52
- correct length (4): 52
- parse failures: 0

## DB Alignment Summary
- **db_path**: data/lottery_v2.db
- **open_mode**: read-only (sqlite3 mode=ro URI)
- **local_draws_table_row_count**: 0
- **note**: Local draws table currently has 0 rows in this checkout; alignment check is schema-level only (column structure compatible: draw/date/lottery_type/numbers/special exist), not row-level, when total_draw_rows == 0.
- **BIG_LOTTO**: status=NO_LOCAL_ROWS, sample_periods_checked=17, matched=0
- **POWER_LOTTO**: status=NO_LOCAL_ROWS, sample_periods_checked=17, matched=0
- **DAILY_539**: status=NO_LOCAL_ROWS, sample_periods_checked=52, matched=0
- **3_STAR**: status=NO_LOCAL_ROWS, sample_periods_checked=52, matched=0
- **4_STAR**: status=NO_LOCAL_ROWS, sample_periods_checked=52, matched=0

## Position-Frequency Diagnostic Table (descriptive only)
### BIG_LOTTO (n=17)
| position | value pool | top values (value, count) | chi2 vs uniform | df |
|---|---|---|---|---|
| 0 | [1, 49] | [(1, 2), (25, 1), (14, 1), (40, 1), (43, 1)] | 37.7647 | 48 |
| 1 | [1, 49] | [(37, 2), (43, 2), (32, 1), (20, 1), (22, 1)] | 43.5294 | 48 |
| 2 | [1, 49] | [(12, 2), (14, 1), (47, 1), (17, 1), (45, 1)] | 37.7647 | 48 |
| 3 | [1, 49] | [(10, 2), (19, 2), (21, 2), (16, 2), (25, 2)] | 60.8235 | 48 |
| 4 | [1, 49] | [(6, 2), (16, 2), (4, 2), (18, 2), (20, 2)] | 60.8235 | 48 |
| 5 | [1, 49] | [(48, 2), (26, 1), (7, 1), (40, 1), (10, 1)] | 37.7647 | 48 |
| 6 | [1, 49] | [(30, 3), (34, 2), (7, 1), (22, 1), (18, 1)] | 55.0588 | 48 |
- adjacent |diff|==1 rate: 0.0392 (4/102)

### POWER_LOTTO (n=17)
| position | value pool | top values (value, count) | chi2 vs uniform | df |
|---|---|---|---|---|
| 0 | [1, 38] | [(16, 2), (29, 2), (31, 2), (1, 1), (27, 1)] | 34.4118 | 37 |
| 1 | [1, 38] | [(6, 3), (13, 2), (38, 1), (16, 1), (34, 1)] | 38.8824 | 37 |
| 2 | [1, 38] | [(27, 2), (33, 1), (14, 1), (7, 1), (38, 1)] | 25.4706 | 37 |
| 3 | [1, 38] | [(35, 3), (9, 2), (24, 2), (30, 1), (33, 1)] | 43.3529 | 37 |
| 4 | [1, 38] | [(4, 2), (8, 2), (34, 2), (29, 2), (15, 1)] | 38.8824 | 37 |
| 5 | [1, 38] | [(38, 3), (19, 2), (34, 2), (14, 2), (6, 1)] | 47.8235 | 37 |
| 6 | [1, 8] | [(3, 4), (8, 3), (5, 3), (2, 2), (6, 2)] | 5.1176 | 7 |
- adjacent |diff|==1 rate: 0.0196 (2/102)

### DAILY_539 (n=52)
| position | value pool | top values (value, count) | chi2 vs uniform | df |
|---|---|---|---|---|
| 0 | [1, 39] | [(21, 5), (3, 4), (23, 3), (16, 3), (9, 3)] | 42.5 | 38 |
| 1 | [1, 39] | [(4, 4), (31, 3), (38, 3), (20, 3), (26, 3)] | 30.5 | 38 |
| 2 | [1, 39] | [(25, 5), (2, 5), (13, 3), (30, 2), (36, 2)] | 38.0 | 38 |
| 3 | [1, 39] | [(1, 4), (29, 3), (24, 3), (36, 3), (6, 2)] | 30.5 | 38 |
| 4 | [1, 39] | [(6, 6), (8, 4), (9, 4), (27, 3), (2, 3)] | 53.0 | 38 |
- adjacent |diff|==1 rate: 0.0721 (15/208)

### 3_STAR (n=52)
| position | value pool | top values (value, count) | chi2 vs uniform | df |
|---|---|---|---|---|
| 0 | [0, 9] | [(6, 9), (5, 8), (2, 6), (9, 6), (1, 6)] | 11.0769 | 9 |
| 1 | [0, 9] | [(9, 8), (4, 8), (6, 8), (5, 6), (3, 5)] | 8.3846 | 9 |
| 2 | [0, 9] | [(8, 8), (6, 7), (2, 7), (1, 5), (3, 5)] | 4.5385 | 9 |
- adjacent |diff|==1 rate: 0.2019 (21/104)

### 4_STAR (n=52)
| position | value pool | top values (value, count) | chi2 vs uniform | df |
|---|---|---|---|---|
| 0 | [0, 9] | [(1, 8), (3, 7), (0, 6), (9, 6), (5, 5)] | 4.9231 | 9 |
| 1 | [0, 9] | [(1, 9), (4, 7), (0, 7), (8, 7), (9, 5)] | 8.3846 | 9 |
| 2 | [0, 9] | [(8, 10), (2, 7), (3, 6), (1, 6), (0, 5)] | 9.9231 | 9 |
| 3 | [0, 9] | [(6, 10), (4, 10), (9, 7), (2, 5), (1, 5)] | 14.9231 | 9 |
- adjacent |diff|==1 rate: 0.2115 (33/156)

## Limitations
- Bounded 2-month prototype sample only; not statistically powered for any confirmatory test.
- Chi-square statistics are descriptive only; no p-value table, no multiple-testing correction, no pre-registration (prototype, not a confirmatory scan).
- Local draws table is empty (0 rows) in this checkout, so row-level DB alignment could not be exercised end-to-end; only schema compatibility and a query-path dry-run were verified.
- 3_STAR / 4_STAR draw-order positions are digit draws (0-9, with replacement); BIG_LOTTO/POWER_LOTTO/DAILY_539 positions are without-replacement draws from a larger pool, so a uniform-chi2 null is a rough descriptive diagnostic, not a calibrated test.
- No success-rate / hit-rate improvement is claimed by this prototype.

## Next-Step Recommendation
If this prototype's structural checks (field presence, length, sorted-equivalence with drawNumberSize) hold across a larger bounded re-run, a separate, explicitly-authorized P221F-gated confirmatory task could pre-register a full-history drawNumberAppear backfill + positional-bias hypothesis test. That future task would require its own DB-write authorization (new column/table) and would be a confirmatory test, not this prototype.

## Disclaimer
DIAGNOSTICS ONLY. No betting recommendation. No validated hit-rate edge. No production DB write. No replay row modification. This artifact does not claim any success-rate improvement.

## Final Classification
P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_COMPLETE_DIAGNOSTICS_ONLY
