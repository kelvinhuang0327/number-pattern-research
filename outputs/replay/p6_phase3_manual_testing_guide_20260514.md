# Phase 3: Live API Verification — Manual Testing Guide

**Date**: 2026-05-14  
**For**: Deployment Environment with Python 3.9 + fastapi Installed  
**Status**: READY FOR EXECUTION  

---

## Prerequisites

```bash
# Verify environment is ready
python3.9 --version          # Should be Python 3.9.x
python3.9 -c "import fastapi; print(fastapi.__version__)"  # Should print version
python3.9 -c "import uvicorn; print(uvicorn.__version__)" # Should print version
python3.9 -c "import sqlite3; print('OK')"  # Built-in
```

---

## Step 1: Start Backend Server

**Location**: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean`

```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean

# Start uvicorn server
python3.9 -m uvicorn lottery_api.app:app \
  --host 127.0.0.1 \
  --port 8001 \
  --log-level info
```

**Expected output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

**Verify server started**:
```bash
# In another terminal
curl http://127.0.0.1:8001/api/replay/strategies
# Should return JSON with strategy list
```

---

## Step 2: Test All 6 Executable Strategies

Run these curl tests **in sequence** and capture responses. Each should include `"truth_level"` field with value `"REGENERATED_RETROSPECTIVE"`.

### Strategy 1: biglotto_deviation_2bet

```bash
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=BIG_LOTTO&strategy_id=biglotto_deviation_2bet&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: Contains "truth_level": "REGENERATED_RETROSPECTIVE"
# VERIFY: Check actual_numbers, hit_count, generated_at all present
```

**Screenshot/Output Location**: Save to `outputs/replay/p6_phase3_test_strategy1_biglotto_deviation_2bet.json`

---

### Strategy 2: biglotto_triple_strike

```bash
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=BIG_LOTTO&strategy_id=biglotto_triple_strike&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: Contains "truth_level": "REGENERATED_RETROSPECTIVE"
```

**Screenshot/Output Location**: Save to `outputs/replay/p6_phase3_test_strategy2_biglotto_triple_strike.json`

---

### Strategy 3: daily539_f4cold

```bash
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=DAILY_539&strategy_id=daily539_f4cold&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: Contains "truth_level": "REGENERATED_RETROSPECTIVE"
```

**Screenshot/Output Location**: Save to `outputs/replay/p6_phase3_test_strategy3_daily539_f4cold.json`

---

### Strategy 4: daily539_markov_cold

```bash
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=DAILY_539&strategy_id=daily539_markov_cold&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: Contains "truth_level": "REGENERATED_RETROSPECTIVE"
```

**Screenshot/Output Location**: Save to `outputs/replay/p6_phase3_test_strategy4_daily539_markov_cold.json`

---

### Strategy 5: power_orthogonal_5bet

```bash
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=POWER_LOTTO&strategy_id=power_orthogonal_5bet&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: Contains "truth_level": "REGENERATED_RETROSPECTIVE"
```

**Screenshot/Output Location**: Save to `outputs/replay/p6_phase3_test_strategy5_power_orthogonal_5bet.json`

---

### Strategy 6: power_precision_3bet

```bash
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=POWER_LOTTO&strategy_id=power_precision_3bet&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: Contains "truth_level": "REGENERATED_RETROSPECTIVE"
```

**Screenshot/Output Location**: Save to `outputs/replay/p6_phase3_test_strategy6_power_precision_3bet.json`

---

## Step 3: Verify Response Contract

For each response, confirm:

```json
{
  "records": [
    {
      "id": <number>,
      "lottery_type": "BIG_LOTTO|DAILY_539|POWER_LOTTO",
      "target_draw": "<string>",
      "target_date": "<YYYY-MM-DD>",
      "strategy_id": "<string>",
      "strategy_name": "<string>",
      "strategy_version": "<string>",
      "history_cutoff": "<string>",
      "replay_status": "PREDICTED|REJECTED|...",
      "reject_reason": null|"<string>",
      "predicted_numbers": [<int>, ...],
      "predicted_special": <int>|null,
      "actual_numbers": [<int>, ...],
      "actual_special": <int>|null,
      "hit_numbers": [<int>, ...],
      "hit_count": <int>,
      "special_hit": 0|1,
      "replay_run_id": <int>,
      "generated_at": "<ISO-8601 timestamp>",
      "truth_level": "REGENERATED_RETROSPECTIVE",  ← REQUIRED FIELD
      "lifecycle_status": "ONLINE|...",
      "strategy_lifecycle_status": "ONLINE|..."
    }
  ],
  "total": <int>,
  "page": 1,
  "page_size": 1,
  "pages": <int>,
  "filter_lifecycle_status": null|"<string>"
}
```

**Checklist**:
- [ ] `truth_level` field present
- [ ] `truth_level` value is `"REGENERATED_RETROSPECTIVE"`
- [ ] All other fields (actual_numbers, hit_count, etc.) are populated
- [ ] HTTP 200 response code
- [ ] No errors in server logs

---

## Step 4: Verify Row Count Consistency

```bash
# Test pagination to ensure all 50 rows per strategy are accessible
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=BIG_LOTTO&strategy_id=biglotto_deviation_2bet&page_size=50" | jq '.total'

# Should return 50 (or exact count from controlled_apply_id='20260514033100-13acaf34996e')
```

**Expected**:
- biglotto_deviation_2bet: 50 rows
- biglotto_triple_strike: 50 rows
- daily539_f4cold: 50 rows
- daily539_markov_cold: 50 rows
- power_orthogonal_5bet: 50 rows
- power_precision_3bet: 50 rows

---

## Step 5: Verify Fixture Mode Still Works

```bash
# Fixture mode should still work and include truth_level='FIXTURE_SYNTHETIC'
curl -s "http://127.0.0.1:8001/api/replay/history?lottery_type=BIG_LOTTO&fixture_mode=true&page=1&page_size=1" | jq '.records[0]'

# EXPECTED: "truth_level": "FIXTURE_SYNTHETIC"
```

---

## Step 6: Verify Legacy Rows Still Present

```bash
# Check that legacy rows (null controlled_apply_id) still exist
# This requires direct DB query, not API test
sqlite3 lottery_api/data/lottery_v2.db << EOF
SELECT COUNT(*) as legacy_count FROM strategy_prediction_replays 
WHERE controlled_apply_id IS NULL;
EOF

# EXPECTED: 460 rows (or your baseline legacy count)
```

---

## Capture Results

Create a summary document at:  
`outputs/replay/p6_phase3_api_verification_results_20260514.md`

**Contents should include**:

```markdown
# Phase 3 Live API Verification Results

**Date**: 2026-05-14  
**Environment**: Python 3.9, uvicorn running on port 8001  
**Status**: PASS / FAIL

## Test Results

### Strategy Tests (all should show truth_level present)
- [ ] biglotto_deviation_2bet: PASS
- [ ] biglotto_triple_strike: PASS
- [ ] daily539_f4cold: PASS
- [ ] daily539_markov_cold: PASS
- [ ] power_orthogonal_5bet: PASS
- [ ] power_precision_3bet: PASS

### Row Count Verification
- biglotto_deviation_2bet: 50 rows ✓
- biglotto_triple_strike: 50 rows ✓
- daily539_f4cold: 50 rows ✓
- daily539_markov_cold: 50 rows ✓
- power_orthogonal_5bet: 50 rows ✓
- power_precision_3bet: 50 rows ✓

### Legacy Rows
- Legacy rows preserved: 460 ✓

### Fixture Mode
- Fixture mode truth_level='FIXTURE_SYNTHETIC': PASS ✓

## Evidence
- Sample response: [paste first record JSON]
- Server logs: [attach relevant startup/request logs]

## Conclusion
✅ V1_API_TRUTH_LEVEL_VERIFIED (ready for Phase 4 UI smoke test)
```

---

## If Tests Fail

### Issue: 404 Not Found
**Cause**: Wrong endpoint path or server not listening  
**Fix**: Verify `http://127.0.0.1:8001` is correct, check `uvicorn` logs

### Issue: truth_level field missing
**Cause**: Code patch not applied, or old process still running  
**Fix**: 
- Verify file `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api/routes/replay.py` line 435 and 467
- Kill old uvicorn: `pkill -f "uvicorn lottery_api.app"`
- Restart with fresh `python3.9 -m uvicorn ...`

### Issue: truth_level is NULL instead of REGENERATED_RETROSPECTIVE
**Cause**: DB rows don't have truth_level set properly  
**Fix**: Verify controlled_apply run completed successfully:
```bash
sqlite3 lottery_api/data/lottery_v2.db << EOF
SELECT strategy_id, COUNT(*), COUNT(DISTINCT truth_level) 
FROM strategy_prediction_replays 
WHERE controlled_apply_id='20260514033100-13acaf34996e'
GROUP BY strategy_id;
EOF
```

---

## Next: Phase 4 (UI Browser Smoke Test)

Once Phase 3 passes, proceed to:
- Start frontend dev server
- Navigate to replay history page  
- Verify 6 strategies expand with 50 rows each
- Confirm truth-level badge renders correctly
- Check legacy rows still visible

**See**: `outputs/replay/p6_phase4_ui_smoke_guide.md` (to be created after Phase 3 passes)

---

## Success Marker

Once all 6 curl tests return 200 with `"truth_level": "REGENERATED_RETROSPECTIVE"` in records:

```
✅ V1_API_TRUTH_LEVEL_VERIFIED
```

This enables Phase 4 → Phase 5 → Phase 6 closure.

