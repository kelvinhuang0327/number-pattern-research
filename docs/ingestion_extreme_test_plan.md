# Extreme Validation Test Plan — Lottery Data Ingestion System

Generated: 2026-03-23 | Environment: macOS Darwin 25.3.0 | Adversarial mindset

---

## ASSUMPTIONS TO BREAK

| # | Assumption | How to Break |
|---|-----------|--------------|
| A1 | DB has no duplicates | Insert same draw twice |
| A2 | Numbers are always valid range | Insert numbers out of range |
| A3 | ROC date parsing is correct | Feed Gregorian dates, boundary ROC years |
| A4 | Gap detection is correct | Create artificial gaps, year boundaries |
| A5 | Backfill is idempotent | Run 10x, count rows after each |
| A6 | Conflict detection catches all mismatches | Same numbers, different special |
| A7 | HTTP failures are handled | Simulate timeout, partial HTML, bad encoding |
| A8 | Parser handles malformed HTML | Feed garbage, extra numbers, missing fields |
| A9 | Logger is consistent | Fill disk, concurrent writes, read-back integrity |
| A10 | API validates all input | Send malformed JSON, wrong types, SQL injection |

---

## PHASE 1 — UNIT TESTS

### T1.1 ROC Date Conversion
- Input: `115/03/20` → expect `2026/03/20`
- Input: `115年03月20日` → expect `2026/03/20`
- Input: `2026/03/20` → expect `2026/03/20` (passthrough)
- Input: `2026/15/50` → expect stored as-is (bad date not rejected!)
- Input: `200/03/20` → expect year 2111 (overflow, should FAIL)
- Input: `""` → expect graceful empty string
- Input: `"abc"` → expect passthrough, no crash

### T1.2 Draw Number Validation
- `115000037` (9-digit) → valid
- `1150000370` (10-digit) → valid
- `11500003` (8-digit) → invalid, rejected
- `abc000037` → invalid, rejected
- `000000000` → edge case

### T1.3 _split() Year/Seq Parsing
- `115000037` → year=115, seq=37
- `96000104` → year=96, seq=104
- `100000001` → year=100, seq=1
- `11500007` (8-digit) → wrong split detected?
- `1150000370` (10-digit) → year=1150, seq=370 (wrong!)

### T1.4 Gap Detection Year Boundaries
- [96000104, 97000001] → NOT a gap (year change)
- [115000036, 115000038] → gap=1 (within-year)
- [115000037, 116000001] → NOT a gap (year change)
- [115000037, 115000039] → gap=1 detected

### T1.5 Number Normalization
- Input: [5, 1, 3, 2, 4] → stored as [1, 2, 3, 4, 5]
- Input: [1, 1, 2, 3, 4, 5] → duplicate detected before insert
- Input: [0, 1, 2, 3, 4, 5] → 0 invalid (range 1+)
- Input: [50, 1, 2, 3, 4, 5] → 50 invalid for BIG_LOTTO (max 49)

---

## PHASE 2 — DATA CONSISTENCY TESTS

### T2.1 Duplicate Insert
- Insert draw `TEST000001` for BIG_LOTTO
- Insert same draw again
- Verify: count=1, no exception, inserted=0 on second attempt

### T2.2 Conflict: Same Draw, Different Numbers
- Insert draw `TEST000002` with numbers [1,2,3,4,5,6]
- Attempt insert with numbers [1,2,3,4,5,7]
- Verify: conflict detected, original unchanged

### T2.3 Cross-Game Contamination
- Insert draw `TEST000003` for BIG_LOTTO
- Verify it does NOT appear in POWER_LOTTO queries
- Verify same draw number can exist for different lottery types

### T2.4 Sorted vs Unsorted
- Insert numbers [6,5,4,3,2,1] for BIG_LOTTO
- Read back and verify stored as [1,2,3,4,5,6]

### T2.5 Special Number Edge Cases
- DAILY_539 with special=5 → stored as special=0? or 5?
- BIG_LOTTO with special=0 → valid?
- BIG_LOTTO with special=50 → invalid (max 49)

---

## PHASE 3 — BACKFILL DESTRUCTION TESTS

### T3.1 Idempotency Test
- Run backfill engine 5x on same game
- Count DB rows before and after each run
- Verify: row count never increases after first run

### T3.2 Overlapping Backfill
- Prepare draw list [A, B, C, D, E]
- Run backfill for [A, B, C]
- Run backfill for [C, D, E]  ← C is overlap
- Verify: C not duplicated

### T3.3 Empty DB Backfill
- (Do not run on prod DB — simulate with temp DB)
- Empty → backfill → verify correct count and ordering

### T3.4 Interrupted Backfill Resume
- Backfill list of 10, simulate failure after 5
- Run backfill again with same 10
- Verify: only remaining 5 inserted, no duplicates

---

## PHASE 4 — FETCH FAILURE TESTS

### T4.1 HTTP Timeout Simulation
- Patch requests.get to raise requests.exceptions.Timeout
- Call fetch_latest()
- Verify: returns None, no crash, error logged

### T4.2 HTTP 500 Response
- Patch requests.get to return status=500
- Call fetch_latest()
- Verify: returns None, no crash

### T4.3 Empty HTTP Response
- Patch to return status=200 with body=""
- Call fetch_latest()
- Verify: returns None, no crash, no insert

### T4.4 Partial HTML Response
- Return truncated HTML mid-table
- Verify: parser handles gracefully, no partial data

### T4.5 Wrong Encoding Response
- Return HTML in Latin-1 encoding
- Verify: no crash, warning logged

### T4.6 JSON Response Instead of HTML
- Return `{"error": "not found"}` as response
- Verify: parser finds no tables, returns None

---

## PHASE 5 — PARSER ATTACK TESTS

### T5.1 Extra Numbers in HTML
- Inject HTML with 10 numbers instead of 6
- Verify: only correct count used

### T5.2 HTML Number Injection
- Inject `<span class="ball">99</span>` (out of range)
- Verify: 99 rejected for BIG_LOTTO (max 49)

### T5.3 Wrong Special Number
- HTML shows special=55 for BIG_LOTTO (max 49)
- Verify: rejected or at least flagged

### T5.4 Missing Special Number
- BIG_LOTTO HTML with no special number element
- Verify: defaults to 0, not crash

### T5.5 Duplicate Numbers in HTML
- HTML has [5, 10, 15, 5, 20, 25]
- Verify: warning logged, dedup applied

### T5.6 XSS-like HTML in Scan Error
- scan_error contains `<script>alert(1)</script>`
- Verify: frontend renders as text, not executes

---

## PHASE 6 — DB INTEGRITY TESTS

### T6.1 Duplicate Scan
```sql
SELECT draw, lottery_type, COUNT(*) FROM draws
GROUP BY draw, lottery_type HAVING COUNT(*)>1
```
- Expect: 0 rows

### T6.2 Missing Fields
```sql
SELECT COUNT(*) FROM draws WHERE draw IS NULL OR date IS NULL
OR lottery_type IS NULL OR numbers IS NULL
```
- Expect: 0

### T6.3 Invalid JSON Numbers
```sql
SELECT COUNT(*) FROM draws WHERE json_valid(numbers)=0
```
- Expect: 0

### T6.4 Number Range Validation
- Parse all number arrays
- Verify no number outside valid range per lottery type

### T6.5 Special Number Range
- BIG_LOTTO: special in 0..49
- POWER_LOTTO: special in 0..8
- DAILY_539: special = 0 always

### T6.6 Date Format
- All dates match `YYYY/MM/DD` pattern
- No ROC dates stored raw (e.g., "115/03/20")

---

## PHASE 7 — REPLAY TEST

### T7.1 DB Snapshot Consistency
- Take snapshot of current draw counts
- Re-import same draws via insert_draws()
- Verify: counts unchanged (all duplicates)

### T7.2 Number Integrity After Roundtrip
- Read numbers from DB
- Re-insert same numbers
- Read again
- Verify: bit-for-bit identical

---

## PHASE 8 — LOGGING AUDIT

### T8.1 Every Action Logged
- Run fetch_latest → check log entry created
- Run scan_missing → check log entry created
- Run backfill → check log entry per draw

### T8.2 Conflict Logged
- Create conflict scenario
- Verify conflict log entry exists with correct data

### T8.3 Error Logged
- Simulate network failure
- Verify error log entry exists

### T8.4 Log Read-Back Integrity
- Write 100 entries
- Read all back
- Verify: count=100, no corruption

### T8.5 Concurrent Log Writes
- Write 10 entries from 5 threads simultaneously
- Read all back
- Verify: count=50, no truncated JSON lines

---

## PHASE 9 — PERFORMANCE TESTS

### T9.1 Batch Insert Speed
- Insert 1000 draws
- Measure time

### T9.2 DB Query Speed
- Query all 13945 draws
- Measure time

### T9.3 Log Read Speed
- Write 10000 log entries
- Read them all back
- Measure time

---

## PHASE 10 — API ADVERSARIAL TESTS

### T10.1 Malformed JSON Body
- POST /api/ingest/fetch-latest with `{"lottery_type": 12345}`
- Expect: 422 Unprocessable Entity, not 500

### T10.2 SQL Injection Attempt
- POST /api/ingest/scan-missing?lottery_type=BIG_LOTTO'; DROP TABLE draws;--
- Expect: handled safely (parameterized queries)

### T10.3 Oversized draw_list
- POST /api/ingest/backfill with draw_list of 1000 items
- Expect: capped at max_draws=30

### T10.4 Negative max_draws
- POST /api/ingest/backfill with max_draws=-1
- Expect: 422 or safe default

### T10.5 Repeated Rapid Calls
- Call /api/ingest/fetch-latest 20x in 2 seconds
- Verify: no crash, no duplicate inserts

---

## PHASE 11 — FINAL VERDICT CRITERIA

| Criterion | Pass Condition |
|-----------|----------------|
| No duplicate rows | 0 rows with COUNT>1 on (draw, lottery_type) |
| Idempotency | Row count stable after 3+ backfill runs |
| Conflict detection | All number/special mismatches caught |
| HTTP failure safety | No crash on any network failure type |
| Parser safety | No out-of-range numbers stored |
| Logging completeness | Every operation has log entry |
| Date correctness | All dates in YYYY/MM/DD Gregorian format |
| API input safety | No crash on malformed input |
| XSS safety | Scan error not rendered as HTML |

**Production readiness threshold:** PASS on 9/9 above criteria.
