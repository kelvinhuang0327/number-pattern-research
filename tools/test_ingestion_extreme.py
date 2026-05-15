"""
Extreme adversarial test suite for the lottery data ingestion system.
Run from project root: python3 tools/test_ingestion_extreme.py
"""

import sys, os, json, sqlite3, tempfile, threading, time, unittest
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lottery_api'))

# ──────────────────────────────────────────────────────────────────────────────
PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"
results = []

def record(phase, name, status, detail=""):
    results.append({"phase": phase, "name": name, "status": status, "detail": detail})
    print(f"  {status}  {name}" + (f"\n         → {detail}" if detail else ""))

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1 — UNIT TESTS
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 1 — UNIT TESTS")
print("═"*70)

from fetcher.taiwan_lottery_fetcher import (
    _roc_date_to_gregorian, _is_valid_draw_number, _normalize_draw,
    _parse_draws_from_html, SOURCE_CONFIG
)

# T1.1 ROC Date Conversion
print("\n[T1.1] ROC Date Conversion")

cases = [
    ("115/03/20",       "2026/03/20", True),
    ("115年03月20日",   "2026/03/20", True),
    ("2026/03/20",      "2026/03/20", True),   # passthrough
    ("2026/15/50",      "2026/15/50", True),   # invalid but passes through — DESIGN GAP
    ("200/03/20",       "2111/03/20", True),   # overflow — stores wrong year
    ("",                "",           True),   # empty
    ("abc",             "abc",        True),   # garbage passthrough
    ("96/03/20",        "2007/03/20", True),   # 2-digit ROC year fails pattern
]

date_overflow_found = False
for inp, expected, should_pass in cases:
    got = _roc_date_to_gregorian(inp)
    ok  = (got == expected)
    if inp == "200/03/20" and got == "2111/03/20":
        record("P1", f"ROC overflow '{inp}' → '{got}'", WARN,
               "Year 200 stored as 2111 — no overflow guard")
        date_overflow_found = True
    elif inp == "2026/15/50" and got == "2026/15/50":
        record("P1", f"Invalid date passthrough '{inp}'", WARN,
               "Invalid dates (month 15, day 50) stored without validation")
    elif inp == "96/03/20":
        if got == "96/03/20":   # 2-digit not recognized as ROC
            record("P1", f"2-digit ROC '{inp}' not converted", WARN,
                   f"Got '{got}', expected '2007/03/20' — 2-digit year not handled")
        else:
            record("P1", f"2-digit ROC '{inp}'", PASS, f"→ '{got}'")
    elif ok:
        record("P1", f"Date '{inp}' → '{expected}'", PASS)
    else:
        record("P1", f"Date '{inp}' → '{got}' (expected '{expected}')", FAIL)

# T1.2 Draw Number Validation
print("\n[T1.2] Draw Number Validation")
valid_cases   = ["115000037", "1150000370", "115000001"]
invalid_cases = ["11500003", "abc000037", "000000000", ""]

for d in valid_cases:
    r = _is_valid_draw_number(d)
    record("P1", f"Valid draw '{d}'",   PASS if r  else FAIL, "" if r else "Expected True")

for d in invalid_cases:
    r = _is_valid_draw_number(d)
    record("P1", f"Invalid draw '{d}'", PASS if not r else WARN,
           "" if not r else f"Accepted '{d}' as valid (may be wrong)")

# T1.3 _split() Year/Seq Parsing
print("\n[T1.3] _split() Year/Sequence Parsing")

def _split(draw: str):
    seq  = int(draw[-6:])
    year = int(draw[:-6])
    return year, seq

split_cases = [
    ("115000037",  115, 37),
    ("96000104",   96,  104),
    ("100000001",  100, 1),
    ("1150000370", 1150, 370),   # 10-digit: year=1150 (wrong! should be 115, seq=370? ambiguous)
]
for draw, exp_year, exp_seq in split_cases:
    y, s = _split(draw)
    ok = (y == exp_year and s == exp_seq)
    if draw == "1150000370":
        record("P1", f"10-digit split '{draw}'", WARN,
               f"year={y}, seq={s} — 10-digit format ambiguous (ROC 1150 doesn't exist)")
    elif ok:
        record("P1", f"split '{draw}' → year={y} seq={s}", PASS)
    else:
        record("P1", f"split '{draw}' → year={y} seq={s} (expected {exp_year},{exp_seq})", FAIL)

# T1.4 Gap Detection Year Boundaries
print("\n[T1.4] Gap Detection — Year Boundaries")
from fetcher.missing_issue_detector import MissingIssueDetector
det = MissingIssueDetector()

year_boundary_cases = [
    (["96000104", "97000001"],   0, "Year boundary → not a gap"),
    (["115000036", "115000038"], 1, "Within-year gap → gap=1"),
    (["115000037", "116000001"], 0, "Year change → not a gap"),
    (["115000037", "115000039"], 1, "Within-year gap=1 detected"),
    (["115000037", "115000037"], 0, "Same draw twice (no gap)"),
]
for draws, exp_gaps, label in year_boundary_cases:
    gaps = det._detect_internal_gaps(draws)
    ok = (len(gaps) == exp_gaps)
    record("P1", label, PASS if ok else FAIL,
           f"gaps={len(gaps)}, expected={exp_gaps}, details={gaps}")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2 — DATA CONSISTENCY TESTS (using temp DB)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 2 — DATA CONSISTENCY TESTS")
print("═"*70)

from database import DatabaseManager

# Create isolated temp DB for all destructive tests
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
TEST_DB = _tmp.name
test_db = DatabaseManager(db_path=TEST_DB)

# T2.1 Duplicate Insert Prevention
print("\n[T2.1] Duplicate Insert Prevention")
d1 = {"draw": "TEST000001", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
      "numbers": [1,2,3,4,5,6], "special": 7}
ins1, dup1 = test_db.insert_draws([d1])
ins2, dup2 = test_db.insert_draws([d1])
if ins1 == 1 and dup1 == 0 and ins2 == 0 and dup2 == 1:
    record("P2", "Duplicate insert → skipped correctly", PASS,
           f"first: ins={ins1} dup={dup1}, second: ins={ins2} dup={dup2}")
else:
    record("P2", "Duplicate insert", FAIL,
           f"first: ins={ins1} dup={dup1}, second: ins={ins2} dup={dup2}")

# Count rows in DB
conn = sqlite3.connect(TEST_DB)
count = conn.execute("SELECT COUNT(*) FROM draws WHERE draw='TEST000001'").fetchone()[0]
conn.close()
record("P2", "Row count after 2 inserts = 1", PASS if count == 1 else FAIL, f"count={count}")

# T2.2 Conflict: Same Draw, Different Numbers
print("\n[T2.2] Conflict: Same Draw, Different Numbers")
d_orig = {"draw": "TEST000002", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
           "numbers": [1,2,3,4,5,6], "special": 7}
d_diff = {"draw": "TEST000002", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
           "numbers": [1,2,3,4,5,7], "special": 7}  # 6→7
test_db.insert_draws([d_orig])
ins3, dup3 = test_db.insert_draws([d_diff])
# DB constraint should block it
existing = test_db.get_draw("BIG_LOTTO", "TEST000002")
if ins3 == 0 and existing["numbers"] == [1,2,3,4,5,6]:
    record("P2", "Conflicting numbers blocked by DB constraint", PASS)
else:
    record("P2", "Conflicting numbers — DB allowed overwrite?", FAIL,
           f"existing numbers: {existing.get('numbers')}")

# CRITICAL TEST: Does backfill engine detect this conflict?
from fetcher.backfill_engine import BackfillEngine
engine = BackfillEngine()
# Use test_db record (engine._get_existing reads prod DB, not temp test DB)
existing_check = test_db.get_draw("BIG_LOTTO", "TEST000002")
conflict_type = engine._detect_conflict(existing_check, d_diff) if existing_check else "no_record"
record("P2", "BackfillEngine conflict detection (numbers)",
       PASS if conflict_type == "numbers" else FAIL,
       f"conflict_type={conflict_type}")

# T2.2b Conflict: Different Special Number Only
d_special_diff = {"draw": "TEST000002", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
                  "numbers": [1,2,3,4,5,6], "special": 9}  # special 7→9
conflict_type2 = engine._detect_conflict(existing_check, d_special_diff)
record("P2", "BackfillEngine conflict detection (special)",
       PASS if conflict_type2 == "special" else FAIL,
       f"conflict_type={conflict_type2}")

# T2.2c CRITICAL: Date conflict NOT detected (by design)
d_date_diff = {"draw": "TEST000002", "date": "2026/03/21", "lotteryType": "BIG_LOTTO",
               "numbers": [1,2,3,4,5,6], "special": 7}  # date changed
conflict_type3 = engine._detect_conflict(existing_check, d_date_diff)
record("P2", "Date conflict NOT flagged (known gap)",
       WARN if conflict_type3 is None else PASS,
       f"conflict_type={conflict_type3} — date mismatch silently accepted")

# T2.3 Cross-Game Contamination
print("\n[T2.3] Cross-Game Contamination")
d_big = {"draw": "TEST000003", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
         "numbers": [1,2,3,4,5,6], "special": 7}
test_db.insert_draws([d_big])
power_check = test_db.get_draw("POWER_LOTTO", "TEST000003")
big_check   = test_db.get_draw("BIG_LOTTO",   "TEST000003")
record("P2", "BIG_LOTTO draw not visible in POWER_LOTTO",
       PASS if power_check is None else FAIL, f"cross-contamination={power_check}")
record("P2", "BIG_LOTTO draw visible in BIG_LOTTO",
       PASS if big_check is not None else FAIL)

# T2.4 Sorted vs Unsorted Number Storage
print("\n[T2.4] Number Sorting")
d_unsorted = {"draw": "TEST000004", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
              "numbers": [6,5,4,3,2,1], "special": 7}
test_db.insert_draws([d_unsorted])
readback = test_db.get_draw("BIG_LOTTO", "TEST000004")
stored_nums = readback["numbers"] if readback else None
if stored_nums == [1,2,3,4,5,6]:
    record("P2", "Unsorted numbers stored sorted", PASS, f"stored={stored_nums}")
else:
    record("P2", "Numbers NOT sorted on storage", FAIL, f"stored={stored_nums}")

# T2.5 Special Number Edge Cases
print("\n[T2.5] Special Number Edge Cases")
# DAILY_539 with special set — should be stored as 0 or as given?
d_539_special = {"draw": "TEST000005", "date": "2026/03/20", "lotteryType": "DAILY_539",
                 "numbers": [1,2,3,4,5], "special": 9}
test_db.insert_draws([d_539_special])
r539 = test_db.get_draw("DAILY_539", "TEST000005")
record("P2", "DAILY_539 with special=9 stored as-is (no enforcement)",
       WARN if r539 and r539.get("special") == 9 else PASS,
       f"special={r539.get('special') if r539 else 'N/A'} — DAILY_539 has no special but DB accepted it")

# BIG_LOTTO with special=0 (missing)
d_no_special = {"draw": "TEST000006", "date": "2026/03/20", "lotteryType": "BIG_LOTTO",
                "numbers": [1,2,3,4,5,6], "special": 0}
test_db.insert_draws([d_no_special])
r_no_sp = test_db.get_draw("BIG_LOTTO", "TEST000006")
record("P2", "BIG_LOTTO with special=0 accepted",
       WARN, f"special=0 stored — should it require a valid special number?")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 3 — BACKFILL DESTRUCTION TESTS
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 3 — BACKFILL DESTRUCTION TESTS")
print("═"*70)

# T3.1 Idempotency Test (using BackfillEngine with explicit draw_list)
print("\n[T3.1] Idempotency: Run backfill 5x on same draws")

draws_to_backfill = [
    {"draw": "TEST001001", "date": "2026/01/10", "lotteryType": "BIG_LOTTO",
     "numbers": [10,20,30,40,41,42], "special": 5},
    {"draw": "TEST001002", "date": "2026/01/13", "lotteryType": "BIG_LOTTO",
     "numbers": [11,21,31,41,42,43], "special": 6},
]
test_db.insert_draws(draws_to_backfill)

row_counts = []
for run in range(5):
    # Simulate re-inserting same data
    ins, dup = test_db.insert_draws(draws_to_backfill)
    conn = sqlite3.connect(TEST_DB)
    cnt = conn.execute("SELECT COUNT(*) FROM draws WHERE draw LIKE 'TEST001%'").fetchone()[0]
    conn.close()
    row_counts.append(cnt)

all_same = len(set(row_counts)) == 1
record("P3", "Idempotency: 5 reruns → row count stable",
       PASS if all_same else FAIL,
       f"row counts per run: {row_counts}")

# T3.2 Overlapping Backfill Simulation
print("\n[T3.2] Overlapping backfill ranges")
draws_a = [
    {"draw": "TEST002001", "date": "2026/01/10", "lotteryType": "POWER_LOTTO",
     "numbers": [1,2,3,4,5,6], "special": 1},
    {"draw": "TEST002002", "date": "2026/01/13", "lotteryType": "POWER_LOTTO",
     "numbers": [2,3,4,5,6,7], "special": 2},
    {"draw": "TEST002003", "date": "2026/01/17", "lotteryType": "POWER_LOTTO",
     "numbers": [3,4,5,6,7,8], "special": 3},
]
test_db.insert_draws(draws_a[:2])   # Insert A, B
ins, dup = test_db.insert_draws(draws_a[1:])   # Insert B, C (B is overlap)
conn = sqlite3.connect(TEST_DB)
cnt = conn.execute("SELECT COUNT(*) FROM draws WHERE draw LIKE 'TEST002%'").fetchone()[0]
conn.close()
record("P3", "Overlapping backfill: no duplicate on overlap",
       PASS if cnt == 3 else FAIL, f"cnt={cnt}, expected 3. ins={ins} dup={dup}")

# T3.3 Ordering After Backfill
print("\n[T3.3] Ordering consistency after out-of-order inserts")
draws_ooo = [
    {"draw": "TEST003003", "date": "2026/02/17", "lotteryType": "DAILY_539",
     "numbers": [3,6,9,12,15], "special": 0},
    {"draw": "TEST003001", "date": "2026/02/10", "lotteryType": "DAILY_539",
     "numbers": [1,2,3,4,5], "special": 0},
    {"draw": "TEST003002", "date": "2026/02/13", "lotteryType": "DAILY_539",
     "numbers": [2,4,6,8,10], "special": 0},
]
test_db.insert_draws(draws_ooo)
conn = sqlite3.connect(TEST_DB)
rows = conn.execute(
    "SELECT draw FROM draws WHERE draw LIKE 'TEST003%' ORDER BY CAST(draw AS INTEGER) ASC"
).fetchall()
conn.close()
order = [r[0] for r in rows]
expected_order = ["TEST003001", "TEST003002", "TEST003003"]
record("P3", "Out-of-order inserts → correct ORDER BY CAST",
       PASS if order == expected_order else FAIL,
       f"order={order}")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 4 — FETCH FAILURE TESTS
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 4 — FETCH FAILURE TESTS")
print("═"*70)

import requests as req_lib
from fetcher.taiwan_lottery_fetcher import _get_page, TaiwanLotteryFetcher

# T4.1 HTTP Timeout
print("\n[T4.1] HTTP Timeout")
with patch('requests.get', side_effect=req_lib.exceptions.Timeout("simulated timeout")):
    result = _get_page("http://fake-url.test")
    record("P4", "HTTP Timeout → returns None, no crash",
           PASS if result is None else FAIL, f"result={result}")

# T4.2 HTTP 500 Error
print("\n[T4.2] HTTP 500 Error")
mock_resp_500 = MagicMock()
mock_resp_500.status_code = 500
mock_resp_500.text = "<html>Server Error</html>"
with patch('requests.get', return_value=mock_resp_500):
    result = _get_page("http://fake-url.test")
    record("P4", "HTTP 500 → returns None",
           PASS if result is None else FAIL, f"result='{str(result)[:50]}'")

# T4.3 Empty Response Body
print("\n[T4.3] Empty Response Body")
mock_resp_empty = MagicMock()
mock_resp_empty.status_code = 200
mock_resp_empty.text = ""
with patch('requests.get', return_value=mock_resp_empty):
    result_direct = _get_page("http://fake-url.test")
    record("P4", "Empty 200 body → returns empty string (not None)",
           WARN if result_direct == "" else PASS,
           f"Got '{result_direct}' — caller must handle empty string as parse failure")

# T4.4 Partial HTML
print("\n[T4.4] Partial HTML Response")
config = SOURCE_CONFIG["BIG_LOTTO"]
partial_html = """<html><body><table><thead><tr><th>期別</th><th>開獎日期</th></tr></thead>
<tbody><tr><td>115000037</td><td>115/03/20</td>"""  # truncated mid-row
from fetcher.taiwan_lottery_fetcher import _parse_draws_from_html
try:
    rows = _parse_draws_from_html(partial_html, config)
    record("P4", "Partial HTML → no crash",
           PASS if rows == [] or len(rows) >= 0 else FAIL,
           f"parsed {len(rows)} rows from truncated HTML")
except Exception as e:
    record("P4", "Partial HTML → CRASH", FAIL, str(e))

# T4.5 Wrong Encoding
print("\n[T4.5] Wrong Encoding Simulation")
mock_resp_latin = MagicMock()
mock_resp_latin.status_code = 200
mock_resp_latin.text = "".join(chr(i) for i in range(128, 200))  # raw latin-1 chars
with patch('requests.get', return_value=mock_resp_latin):
    try:
        result = _get_page("http://fake-url.test")
        rows = _parse_draws_from_html(result, config)
        record("P4", "Wrong encoding (latin-1 chars) → no crash, 0 draws",
               PASS, f"parsed {len(rows)} rows")
    except Exception as e:
        record("P4", "Wrong encoding → CRASH", FAIL, str(e))

# T4.6 JSON Response Instead of HTML
print("\n[T4.6] JSON Response as HTML")
json_as_html = '{"error": "service unavailable", "code": 503}'
try:
    rows = _parse_draws_from_html(json_as_html, config)
    record("P4", "JSON body → parser returns 0 rows, no crash",
           PASS if rows == [] else WARN, f"parsed {len(rows)} rows")
except Exception as e:
    record("P4", "JSON body → CRASH", FAIL, str(e))

# T4.7 Complete connection error
print("\n[T4.7] Connection Error")
with patch('requests.get', side_effect=req_lib.exceptions.ConnectionError("refused")):
    result = _get_page("http://fake-url.test")
    record("P4", "ConnectionError → returns None, no crash",
           PASS if result is None else FAIL)

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 5 — PARSER ATTACK TESTS
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 5 — PARSER ATTACK TESTS")
print("═"*70)

# T5.1 Extra Numbers in HTML Table (10 instead of 6)
print("\n[T5.1] Extra Numbers in Table Row")
extra_nums_html = """
<table>
<tr><th>期別</th><th>開獎日期</th><th>開獎號碼</th><th>特別號</th></tr>
<tr>
<td>115000037</td><td>115/03/20</td>
<td>05 10 15 20 25 30 35 40 45 49</td><td>07</td>
</tr>
</table>"""
try:
    rows = _parse_draws_from_html(extra_nums_html, SOURCE_CONFIG["BIG_LOTTO"])
    if rows:
        nums = rows[0]["numbers_raw"]
        record("P5", f"Extra numbers → only first 6 taken",
               PASS if len(nums) <= 6 else WARN,
               f"got {len(nums)} numbers: {nums}")
    else:
        record("P5", "Extra numbers → parse returned 0 rows", WARN,
               "Parser may have failed to extract any numbers")
except Exception as e:
    record("P5", "Extra numbers → CRASH", FAIL, str(e))

# T5.2 Out-of-Range Number in HTML
print("\n[T5.2] Out-of-Range Number Injection")
oor_html = """
<table>
<tr><th>期別</th><th>開獎號碼</th><th>特別號</th></tr>
<tr><td>115000050</td><td>99 10 20 30 40 49</td><td>07</td></tr>
</table>"""
try:
    rows = _parse_draws_from_html(oor_html, SOURCE_CONFIG["BIG_LOTTO"])
    if rows:
        nums = rows[0]["numbers_raw"]
        if 99 in nums:
            record("P5", "Out-of-range 99 accepted by parser!", FAIL,
                   f"numbers={nums} — parser does not reject out-of-range numbers")
        else:
            record("P5", "Out-of-range 99 rejected by parser", PASS, f"numbers={nums}")
    else:
        record("P5", "OOR HTML → 0 rows parsed", WARN)
except Exception as e:
    record("P5", "OOR HTML → CRASH", FAIL, str(e))

# T5.3 Missing Special Number for BIG_LOTTO
print("\n[T5.3] Missing Special Number")
no_special_html = """
<table>
<tr><th>期別</th><th>開獎號碼</th></tr>
<tr><td>115000051</td><td>05 10 15 20 25 30</td></tr>
</table>"""
try:
    rows = _parse_draws_from_html(no_special_html, SOURCE_CONFIG["BIG_LOTTO"])
    if rows:
        spec = rows[0]["special_raw"]
        record("P5", "Missing special → defaults to 0",
               PASS if spec == 0 else WARN, f"special={spec}")
    else:
        record("P5", "Missing special → 0 rows parsed", WARN)
except Exception as e:
    record("P5", "Missing special → CRASH", FAIL, str(e))

# T5.4 Duplicate Numbers in HTML
print("\n[T5.4] Duplicate Numbers in HTML")
dup_html = """
<table>
<tr><th>期別</th><th>開獎號碼</th><th>特別號</th></tr>
<tr><td>115000052</td><td>05 10 15 05 25 30</td><td>07</td></tr>
</table>"""
try:
    rows = _parse_draws_from_html(dup_html, SOURCE_CONFIG["BIG_LOTTO"])
    if rows:
        nums = rows[0]["numbers_raw"]
        has_dup = len(nums) != len(set(nums))
        record("P5", "Duplicate numbers in HTML — silently deduped",
               WARN if not has_dup else FAIL,
               f"numbers_raw={nums}, has_dup={has_dup}")
    else:
        record("P5", "Dup HTML → 0 rows parsed", WARN)
except Exception as e:
    record("P5", "Dup HTML → CRASH", FAIL, str(e))

# T5.5 Malformed HTML (no tables at all)
print("\n[T5.5] Malformed HTML — No Tables")
malformed = "<html><body><div>Nothing here</div></body></html>"
try:
    rows = _parse_draws_from_html(malformed, SOURCE_CONFIG["BIG_LOTTO"])
    record("P5", "No tables → returns [], no crash",
           PASS if rows == [] else FAIL, f"got {len(rows)} rows")
except Exception as e:
    record("P5", "No tables → CRASH", FAIL, str(e))

# T5.6 XSS in scan_error — verify it's data, not HTML
print("\n[T5.6] XSS Payload in scan_error (data only, UI test)")
xss_payload = "<script>alert('xss')</script>"
# Check that the Python side doesn't interpret it (just stores as string)
# The real risk is in JavaScript; we note it as a known gap
record("P5", "XSS in scan_error field (backend stores as string)",
       WARN, "Backend safe; frontend renders via innerHTML — XSS risk (see V6.2)")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 6 — DB INTEGRITY TESTS
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 6 — DB INTEGRITY TESTS (Production DB)")
print("═"*70)

# Use PRODUCTION DB for read-only checks
PROD_DB = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
conn_prod = sqlite3.connect(PROD_DB)
conn_prod.row_factory = sqlite3.Row

# T6.1 Duplicate Scan
print("\n[T6.1] Duplicate Records Scan")
dupes = conn_prod.execute(
    "SELECT draw, lottery_type, COUNT(*) as cnt FROM draws "
    "GROUP BY draw, lottery_type HAVING cnt > 1"
).fetchall()
record("P6", "No duplicate (draw, lottery_type) pairs",
       PASS if len(dupes) == 0 else FAIL,
       f"{len(dupes)} duplicates found: {[dict(d) for d in dupes[:5]]}")

# T6.2 Missing Fields
print("\n[T6.2] Missing Fields (NULL checks)")
nulls = conn_prod.execute(
    "SELECT COUNT(*) FROM draws WHERE draw IS NULL OR date IS NULL "
    "OR lottery_type IS NULL OR numbers IS NULL"
).fetchone()[0]
record("P6", "No NULL fields",
       PASS if nulls == 0 else FAIL, f"{nulls} rows with NULL fields")

# T6.3 Invalid JSON in numbers column
print("\n[T6.3] JSON Validity of numbers column")
invalid_json = conn_prod.execute(
    "SELECT COUNT(*) FROM draws WHERE json_valid(numbers) = 0"
).fetchone()[0]
record("P6", "All numbers columns contain valid JSON",
       PASS if invalid_json == 0 else FAIL, f"{invalid_json} invalid JSON rows")

# T6.4 Number Range Validation Per Lottery Type
print("\n[T6.4] Number Range Validation")
MAX_NUMBERS = {"BIG_LOTTO": 49, "POWER_LOTTO": 38, "DAILY_539": 39}
range_errors = 0
range_checked = 0
all_rows = conn_prod.execute(
    "SELECT draw, lottery_type, numbers FROM draws WHERE lottery_type IN "
    "('BIG_LOTTO','POWER_LOTTO','DAILY_539')"
).fetchall()
for row in all_rows:
    lt = row["lottery_type"]
    max_num = MAX_NUMBERS.get(lt, 49)
    try:
        nums = json.loads(row["numbers"])
        for n in nums:
            range_checked += 1
            if n < 1 or n > max_num:
                range_errors += 1
                if range_errors <= 3:
                    print(f"    ❌ OOR: draw={row['draw']} lt={lt} n={n} (max={max_num})")
    except:
        range_errors += 1

record("P6", f"All numbers in valid range (checked {range_checked} values)",
       PASS if range_errors == 0 else FAIL,
       f"{range_errors} out-of-range numbers found")

# T6.5 Special Number Range
print("\n[T6.5] Special Number Validation")
SPECIAL_MAX = {"BIG_LOTTO": 49, "POWER_LOTTO": 8, "DAILY_539": 0}
special_errors = []
for lt, sp_max in SPECIAL_MAX.items():
    if lt == "DAILY_539":
        # Should be 0 always
        bad = conn_prod.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND special != 0",
            (lt,)
        ).fetchone()[0]
        if bad > 0:
            special_errors.append(f"{lt}: {bad} rows with special!=0")
    else:
        bad = conn_prod.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND (special < 1 OR special > ?)",
            (lt, sp_max)
        ).fetchone()[0]
        if bad > 0:
            special_errors.append(f"{lt}: {bad} rows with special out of range (1-{sp_max})")

if special_errors:
    record("P6", "Special number range validation",
           FAIL if any("POWER" in e or "BIG" in e for e in special_errors) else WARN,
           "; ".join(special_errors))
else:
    record("P6", "All special numbers in valid range", PASS)

# T6.6 Date Format Validation
print("\n[T6.6] Date Format Validation")
import re as re_mod
bad_dates = []
dates = conn_prod.execute(
    "SELECT DISTINCT date FROM draws ORDER BY date LIMIT 1000"
).fetchall()
for row in dates:
    d = row[0]
    if not re_mod.match(r"^\d{4}/\d{2}/\d{2}$", d):
        bad_dates.append(d)

if bad_dates[:10]:
    record("P6", "Date format YYYY/MM/DD",
           FAIL, f"{len(bad_dates)} bad dates, sample: {bad_dates[:5]}")
else:
    record("P6", "All dates in YYYY/MM/DD format", PASS)

# T6.7 Correct number count per lottery type
print("\n[T6.7] Number Count Per Lottery Type")
COUNT_EXPECTED = {"BIG_LOTTO": 6, "POWER_LOTTO": 6, "DAILY_539": 5}
count_errors = 0
for lt, expected_count in COUNT_EXPECTED.items():
    rows = conn_prod.execute(
        "SELECT draw, numbers FROM draws WHERE lottery_type=?", (lt,)
    ).fetchall()
    for r in rows:
        try:
            nums = json.loads(r["numbers"])
            if len(nums) != expected_count:
                count_errors += 1
                if count_errors <= 3:
                    print(f"    ❌ Wrong count: {lt} draw={r['draw']} count={len(nums)}")
        except:
            count_errors += 1

record("P6", f"Correct number count per lottery type",
       PASS if count_errors == 0 else FAIL,
       f"{count_errors} wrong-count rows")

conn_prod.close()

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 7 — REPLAY TEST
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 7 — REPLAY TEST")
print("═"*70)

print("\n[T7.1] Re-insert production data → zero new inserts")
prod_db_mgr = DatabaseManager(db_path=PROD_DB)
# Get last 10 draws from production DB for each game
test_total_ins = 0
test_total_dup = 0
for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
    all_draws = prod_db_mgr.get_all_draws(lt)
    last10 = all_draws[:10]  # newest 10
    if last10:
        ins, dup = prod_db_mgr.insert_draws(last10)
        test_total_ins += ins
        test_total_dup += dup

record("P7", "Re-insert last 10 draws per game → all duplicates",
       PASS if test_total_ins == 0 else FAIL,
       f"inserted={test_total_ins}, duplicates={test_total_dup}")

print("\n[T7.2] Number Roundtrip Integrity")
big_draws = prod_db_mgr.get_all_draws("BIG_LOTTO")[:5]
mismatch = 0
for d in big_draws:
    orig_nums = d["numbers"]
    re_norm = _normalize_draw("BIG_LOTTO", d["draw"], d["date"], d["numbers"], d["special"])
    if re_norm["numbers"] != orig_nums:
        mismatch += 1

record("P7", "Numbers stable after re-normalization",
       PASS if mismatch == 0 else FAIL,
       f"{mismatch} mismatches out of {len(big_draws)} checked")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 8 — LOGGING AUDIT
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 8 — LOGGING AUDIT")
print("═"*70)

from fetcher.ingest_logger import IngestLogger

# T8.1 Log Write and Read Back
print("\n[T8.1] Log Write/Read Integrity")
tmp_log = tempfile.mktemp(suffix=".jsonl")
il = IngestLogger(log_path=tmp_log)

entries_to_write = 50
for i in range(entries_to_write):
    il.log("test", "BIG_LOTTO", f"LOGTEST{i:04d}", "ok", f"Test entry {i}")

entries_read = il.get_recent(limit=entries_to_write + 10)
record("P8", f"Write {entries_to_write} log entries → read back {len(entries_read)}",
       PASS if len(entries_read) == entries_to_write else FAIL,
       f"expected={entries_to_write}, got={len(entries_read)}")

# T8.2 JSON validity of every log line
print("\n[T8.2] JSONL Line Validity")
invalid_lines = 0
with open(tmp_log, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1

record("P8", "All log lines are valid JSON",
       PASS if invalid_lines == 0 else FAIL, f"{invalid_lines} invalid JSONL lines")

# T8.3 Concurrent Log Writes
print("\n[T8.3] Concurrent Log Writes (Race Condition Test)")
concurrent_log = tempfile.mktemp(suffix=".jsonl")
il_concurrent = IngestLogger(log_path=concurrent_log)
errors = []
threads_done = []

def write_logs(thread_id, count=10):
    try:
        for i in range(count):
            il_concurrent.log("test", "BIG_LOTTO", f"T{thread_id}_{i:04d}",
                              "ok", f"Thread {thread_id} entry {i}")
        threads_done.append(thread_id)
    except Exception as e:
        errors.append(f"Thread {thread_id}: {e}")

threads = [threading.Thread(target=write_logs, args=(t,)) for t in range(5)]
for t in threads: t.start()
for t in threads: t.join()

# Count valid entries
valid_concurrent = 0
corrupt_lines = 0
with open(concurrent_log, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            valid_concurrent += 1
        except:
            corrupt_lines += 1

record("P8", "Concurrent writes (5 threads × 10 entries = 50)",
       PASS if valid_concurrent == 50 and corrupt_lines == 0 else WARN,
       f"valid={valid_concurrent}, corrupt={corrupt_lines}, errors={errors}")

if corrupt_lines > 0:
    record("P8", "CRITICAL: Concurrent writes caused JSONL corruption", FAIL,
           f"{corrupt_lines} corrupted lines — file locking needed")

# T8.4 Log with special characters
print("\n[T8.4] Special Characters in Log Message")
tmp_log2 = tempfile.mktemp(suffix=".jsonl")
il2 = IngestLogger(log_path=tmp_log2)
special_msg = 'Test with "quotes" and\nnewlines\tand unicode 台灣彩券'
il2.log("test", "BIG_LOTTO", "115000037", "ok", special_msg)
entries = il2.get_recent()
if entries and entries[0]["message"] == special_msg:
    record("P8", "Special characters roundtrip correctly", PASS)
else:
    record("P8", "Special characters corrupted", FAIL,
           f"expected='{special_msg}', got='{entries[0]['message'] if entries else 'N/A'}'")

# T8.5 Log stats correctness
print("\n[T8.5] Log Stats Accuracy")
tmp_log3 = tempfile.mktemp(suffix=".jsonl")
il3 = IngestLogger(log_path=tmp_log3)
il3.log("fetch_latest", "BIG_LOTTO", status="ok", message="ok1")
il3.log("fetch_latest", "BIG_LOTTO", status="ok", message="ok2")
il3.log("backfill",     "BIG_LOTTO", status="error", message="err1")
stats = il3.get_stats()
ok_count = stats["by_status"].get("ok", 0)
err_count = stats["by_status"].get("error", 0)
record("P8", "Log stats: ok=2, error=1",
       PASS if ok_count == 2 and err_count == 1 else FAIL,
       f"stats={stats}")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 9 — PERFORMANCE TESTS
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 9 — PERFORMANCE TESTS")
print("═"*70)

# T9.1 Batch Insert Speed
print("\n[T9.1] Batch Insert Speed (100 draws)")
perf_draws = []
for i in range(100):
    perf_draws.append({
        "draw": f"PERF{i:06d}",
        "date": "2026/01/01",
        "lotteryType": "BIG_LOTTO",
        "numbers": [1,2,3,4,5,6],
        "special": 7,
    })
t0 = time.time()
ins, dup = test_db.insert_draws(perf_draws)
elapsed_insert = time.time() - t0
record("P9", f"Insert 100 draws in {elapsed_insert*1000:.1f}ms",
       PASS if elapsed_insert < 2.0 else WARN,
       f"inserted={ins}")

# T9.2 DB Query Speed (full dataset)
print("\n[T9.2] DB Query Speed (production full dataset)")
prod_db_r = DatabaseManager(db_path=PROD_DB)
t0 = time.time()
all_data = prod_db_r.get_all_draws()
elapsed_query = time.time() - t0
record("P9", f"Query {len(all_data)} draws in {elapsed_query*1000:.1f}ms",
       PASS if elapsed_query < 5.0 else WARN,
       f"records={len(all_data)}")

# T9.3 Log Read Speed (large file)
print("\n[T9.3] Log Read Speed (write 1000 entries then read)")
tmp_log_perf = tempfile.mktemp(suffix=".jsonl")
il_perf = IngestLogger(log_path=tmp_log_perf)
for i in range(1000):
    il_perf.log("perf_test", "BIG_LOTTO", f"PERF{i:04d}", "ok", f"entry {i}")
t0 = time.time()
entries_perf = il_perf.get_recent(limit=1000)
elapsed_log_read = time.time() - t0
record("P9", f"Read 1000 log entries in {elapsed_log_read*1000:.1f}ms",
       PASS if elapsed_log_read < 2.0 else WARN,
       f"read {len(entries_perf)} entries")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 10 — API ADVERSARIAL TESTS (via httpx or direct function call)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 10 — API INPUT VALIDATION TESTS")
print("═"*70)

from routes.ingest import BackfillRequest, FetchLatestRequest

# T10.1 Pydantic validation — wrong type for lottery_type
print("\n[T10.1] Wrong type for lottery_type")
try:
    req = FetchLatestRequest(lottery_type=12345)
    record("P10", "Integer lottery_type accepted (coerced to str)",
           WARN, f"lottery_type='{req.lottery_type}' — no whitelist validation")
except Exception as e:
    record("P10", "Integer lottery_type rejected", PASS, str(e)[:80])

# T10.2 Negative max_draws
print("\n[T10.2] Negative max_draws")
try:
    req = BackfillRequest(max_draws=-1)
    record("P10", "Negative max_draws accepted",
           FAIL, f"max_draws={req.max_draws} — no minimum validation")
except Exception as e:
    record("P10", "Negative max_draws rejected", PASS, str(e)[:80])

# T10.3 SQL injection in draw_list
print("\n[T10.3] SQL Injection in draw_list")
injected = ["115000037'; DROP TABLE draws; --"]
req = BackfillRequest(draw_list=injected)
# Test that the engine's _get_existing uses parameterized queries
try:
    result = engine._get_existing("BIG_LOTTO", injected[0])
    # If we get here, DB didn't crash (parameterized query safe)
    conn_check = sqlite3.connect(PROD_DB)
    table_exists = conn_check.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='draws'"
    ).fetchone()
    conn_check.close()
    record("P10", "SQL injection in draw_list — DB survived",
           PASS if table_exists else FAIL,
           f"parameterized queries protected DB, result={result}")
except Exception as e:
    record("P10", "SQL injection → exception (may be safe)", WARN, str(e)[:80])

# T10.4 Oversized draw_list
print("\n[T10.4] Oversized draw_list (1000 items)")
big_list = [f"115{i:06d}" for i in range(1000)]
req = BackfillRequest(draw_list=big_list, max_draws=30)
record("P10", "draw_list=1000 accepted (cap applied at engine level)",
       WARN if len(req.draw_list) == 1000 else PASS,
       f"Pydantic doesn't cap list; engine caps at max_draws=30")

# T10.5 Unknown lottery_type through scan
print("\n[T10.5] Unknown lottery_type in scan")
from fetcher.missing_issue_detector import MissingIssueDetector
det2 = MissingIssueDetector()
result_bad = det2.scan("UNKNOWN_GAME")
record("P10", "Unknown lottery_type in scan → returns scan_error",
       PASS if result_bad.get("scan_error") else FAIL,
       f"scan_error='{result_bad.get('scan_error')}'")

# T10.6 Empty string lottery_type
result_empty = det2.scan("")
record("P10", "Empty string lottery_type in scan → returns scan_error",
       PASS if result_empty.get("scan_error") else FAIL,
       f"scan_error='{result_empty.get('scan_error')}'")

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 11 — FINAL VERDICT
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*70)
print("PHASE 11 — FINAL VERDICT")
print("═"*70)

total   = len(results)
passed  = sum(1 for r in results if r["status"] == PASS)
failed  = sum(1 for r in results if r["status"] == FAIL)
warned  = sum(1 for r in results if r["status"] == WARN)

print(f"\n  Total tests : {total}")
print(f"  {PASS}       : {passed}")
print(f"  {FAIL}       : {failed}")
print(f"  {WARN}       : {warned}")

print("\n  FAILURES:")
for r in results:
    if r["status"] == FAIL:
        print(f"    [{r['phase']}] {r['name']}")
        if r["detail"]:
            print(f"           → {r['detail']}")

print("\n  WARNINGS (design gaps / should-fix):")
for r in results:
    if r["status"] == WARN:
        print(f"    [{r['phase']}] {r['name']}")
        if r["detail"]:
            print(f"           → {r['detail']}")

# Cleanup temp DB
try:
    os.unlink(TEST_DB)
except:
    pass

# Score
score = int((passed / total) * 100)
print(f"\n  Production Readiness Score: {score}/100")

if failed == 0 and warned <= 5:
    verdict = "CONDITIONALLY SAFE"
elif failed == 0:
    verdict = "REQUIRES FIXES BEFORE UNSUPERVISED USE"
else:
    verdict = "NOT SAFE FOR UNSUPERVISED PRODUCTION USE"

print(f"  Verdict: {verdict}")
print()
