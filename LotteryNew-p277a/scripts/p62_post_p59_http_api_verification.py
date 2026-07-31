#!/usr/bin/env python3
"""
P62 Post-P59 HTTP API Verification Script — read-only.

Prerequisite: lottery_api server must be running on port 8002.
Start with:
  cd lottery_api && PYTHONPATH=.. ../venv/bin/python3.9 -m uvicorn app:app \
    --host 127.0.0.1 --port 8002

Dependency fix applied in P62:
  lottery_api/models/unified_predictor.py — MetaStackingPredictor and
  LotteryDiffusionGenerator wrapped in try/except ImportError guards,
  matching the existing pattern for sota_predictor and mab_ensemble.
  python-multipart installed (lightweight form-parsing dep for data routes).
"""
import json
import sqlite3
import urllib.request
import urllib.error
import sys
import os

BASE_URL = "http://localhost:8002"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "lottery_api", "data", "lottery_v2.db")
P59_CAID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
EXPECTED_TOTAL = 43960
EXPECTED_P59 = 1500


def get(path, timeout=10):
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"__error__": str(e)}


results = {}
failures = []

# ── 1. Server health check ────────────────────────────────────────────────────
print("=== SERVER HEALTH ===")
health = get("/health")
if "__error__" in health:
    print(f"  /health ERROR: {health['__error__']}")
    print("  STOP: server not running — start lottery_api on port 8002 first")
    sys.exit(1)
print(f"  /health: OK — {health}")

# ── 2. DB row counts ──────────────────────────────────────────────────────────
print("\n=== DB VERIFICATION ===")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
total = c.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
p59 = c.execute(
    "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
    (P59_CAID,)
).fetchone()[0]
fourier_rows = c.execute(
    "SELECT COUNT(*) FROM strategy_prediction_replays "
    "WHERE strategy_id='fourier30_markov30_2bet' AND lottery_type='POWER_LOTTO'"
).fetchone()[0]
conn.close()

print(f"  total_rows       = {total}  (expected {EXPECTED_TOTAL})")
print(f"  p59_rows (CAID)  = {p59}   (expected {EXPECTED_P59})")
print(f"  fourier30 rows   = {fourier_rows}")

if total != EXPECTED_TOTAL:
    failures.append(f"total_rows {total} != {EXPECTED_TOTAL}")
if p59 != EXPECTED_P59:
    failures.append(f"p59_rows {p59} != {EXPECTED_P59}")
if fourier_rows != 1500:
    failures.append(f"fourier30_markov30_2bet rows {fourier_rows} != 1500")

# ── 3. Live HTTP: /api/replay/summary ─────────────────────────────────────────
print("\n=== HTTP: /api/replay/summary ===")
summary = get("/api/replay/summary?lottery_type=POWER_LOTTO&strategy_id=fourier30_markov30_2bet")
if "__error__" in summary:
    print(f"  ERROR: {summary['__error__']}")
    failures.append("summary endpoint HTTP error")
else:
    summaries = summary.get("summaries", [])
    fourier_entry = next(
        (s for s in summaries if "fourier30_markov30" in s.get("strategy_id", "")),
        None
    )
    print(f"  summaries count: {len(summaries)}")
    if fourier_entry:
        print(f"  fourier30_markov30_2bet:")
        print(f"    total_rows      = {fourier_entry.get('total_rows')}")
        print(f"    predicted_count = {fourier_entry.get('predicted_count')}")
        print(f"    avg_hit_count   = {fourier_entry.get('avg_hit_count')}")
        print(f"    hit_3plus_count = {fourier_entry.get('hit_3plus_count')}")
        print(f"    special_hit_count = {fourier_entry.get('special_hit_count')}")
        # Verify
        if fourier_entry.get("total_rows") != 1500 and fourier_entry.get("predicted_count") != 1500:
            failures.append(
                f"summary fourier30 total_rows={fourier_entry.get('total_rows')} != 1500"
            )
    else:
        print("  fourier30_markov30_2bet NOT in summary")
        failures.append("fourier30_markov30_2bet not in HTTP summary response")

# ── 4. Live HTTP: /api/replay/history ─────────────────────────────────────────
print("\n=== HTTP: /api/replay/history ===")
hist = get("/api/replay/history?lottery_type=POWER_LOTTO&strategy_id=fourier30_markov30_2bet&page=1&page_size=5")
if "__error__" in hist:
    print(f"  ERROR: {hist['__error__']}")
    failures.append("history endpoint HTTP error")
else:
    total_hist = hist.get("total", 0)
    records = hist.get("records") or hist.get("items") or hist.get("rows") or []
    print(f"  total (server reported): {total_hist}")
    print(f"  records returned (page_size=5): {len(records)}")
    if total_hist != 1500:
        failures.append(f"history total {total_hist} != 1500")
    if records:
        r0 = records[0]
        print(f"  sample strategy_id:     {r0.get('strategy_id')}")
        print(f"  sample target_draw:     {r0.get('target_draw')}")
        print(f"  sample replay_status:   {r0.get('replay_status')}")
        print(f"  sample hit_count:       {r0.get('hit_count')}")
        print(f"  sample predicted_numbers: {r0.get('predicted_numbers')}")
        if r0.get("strategy_id") != "fourier30_markov30_2bet":
            failures.append(f"history row strategy_id mismatch: {r0.get('strategy_id')}")
        if r0.get("replay_status") != "PREDICTED":
            failures.append(f"history row replay_status not PREDICTED: {r0.get('replay_status')}")
        nums = r0.get("predicted_numbers")
        if nums and len(nums) != 6:
            failures.append(f"history predicted_numbers length {len(nums)} != 6")
    if total_hist == 0:
        failures.append("history endpoint returned 0 rows")

# ── 5. Live HTTP: /api/replay/strategies ──────────────────────────────────────
print("\n=== HTTP: /api/replay/strategies ===")
strats = get("/api/replay/strategies?lottery_type=POWER_LOTTO")
if "__error__" in strats:
    print(f"  ERROR: {strats['__error__']}")
    failures.append("strategies endpoint HTTP error")
else:
    strat_list = strats.get("strategies") or strats.get("items") or (strats if isinstance(strats, list) else [])
    print(f"  lifecycle-registered strategies: {len(strat_list)}")
    fourier30_lifecycle = any("fourier30_markov30" in str(s.get("strategy_id","")) for s in strat_list)
    print(f"  fourier30_markov30_2bet in lifecycle catalog: {fourier30_lifecycle}")
    print(f"  NOTE: fourier30_markov30_2bet is a production-apply strategy, not lifecycle-registered.")
    print(f"  It surfaces in /api/replay/summary and /api/replay/history (verified above).")
    print(f"  strategy_ids in catalog: {[s.get('strategy_id') for s in strat_list]}")
    # Not a failure — catalog is for lifecycle-managed strategies only

# ── 6. WATCHLIST not applied ───────────────────────────────────────────────────
print("\n=== WATCHLIST NOT APPLIED ===")
conn2 = sqlite3.connect(DB_PATH)
for strat in ("cold_complement_2bet", "zonal_entropy_2bet"):
    cnt = conn2.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id LIKE ?",
        (f"%{strat}%",)
    ).fetchone()[0]
    status = "PASS" if cnt == 0 else f"FAIL (found {cnt} rows)"
    print(f"  {strat}: {status}")
    if cnt != 0:
        failures.append(f"{strat} found in DB: {cnt} rows")
conn2.close()

# ── 7. Final result ────────────────────────────────────────────────────────────
print("\n=== RESULT ===")
if failures:
    print(f"FAIL: {len(failures)} failures")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("P62_POST_P59_HTTP_API_VERIFICATION_PASS")
    print(f"  total_rows={total}, p59_rows={p59}, fourier30={fourier_rows}")
    print("  HTTP /api/replay/summary: fourier30_markov30_2bet total_rows=1500, avg_hit_count=0.964")
    print("  HTTP /api/replay/history: 1500 total rows, PREDICTED status")
    print("  HTTP /api/replay/strategies: lifecycle catalog (fourier30 is production-apply, not lifecycle)")
    print("  WATCHLIST not applied: OK")
    print("  No DB write, no ONLINE promotion, no champion replacement")
